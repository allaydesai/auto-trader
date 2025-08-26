"""Circuit breaker with exponential backoff for IBKR reconnection."""

import asyncio
import json
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from loguru import logger
from pydantic import BaseModel


class CircuitState(Enum):
    """Circuit breaker state enumeration."""
    CLOSED = "closed"
    HALF_OPEN = "half_open"  
    OPEN = "open"


class CircuitBreakerState(BaseModel):
    """Circuit breaker state for persistence."""
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: Optional[datetime] = None
    next_attempt_time: Optional[datetime] = None
    reset_timeout: int = 60


class CircuitBreakerError(Exception):
    """Circuit breaker is open, blocking operations."""
    pass


class CircuitBreaker:
    """
    Circuit breaker with exponential backoff for connection failures.
    
    Implements the circuit breaker pattern with:
    - CLOSED: Normal operation
    - OPEN: Blocking calls after failure threshold
    - HALF_OPEN: Testing if service recovered
    
    Uses exponential backoff: 1s, 2s, 4s, 8s, 16s with max 5 attempts.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        reset_timeout: int = 60,
        state_file: Optional[Path] = None
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Max failures before opening circuit
            reset_timeout: Seconds to wait before attempting recovery
            state_file: Optional file path for state persistence
        """
        self._failure_threshold = failure_threshold
        self._reset_timeout = reset_timeout
        self._state_file = state_file or Path("circuit_breaker_state.json")
        
        # Load persisted state or initialize
        self._state = self._load_state()

    def calculate_backoff_delay(self, attempt: int, base_delay: int = 1) -> int:
        """
        Calculate exponential backoff delay.
        
        Args:
            attempt: Current attempt number (0-based)
            base_delay: Base delay in seconds
            
        Returns:
            Delay in seconds: 1s, 2s, 4s, 8s, 16s (max 60s)
        """
        delay = base_delay * (2 ** attempt)
        return min(delay, 60)  # Cap at 60 seconds

    async def call_with_circuit_breaker(
        self, 
        async_func: Callable,
        *args,
        **kwargs
    ):
        """
        Execute function with automatic retry and exponential backoff.
        
        Args:
            async_func: Async function to execute
            *args: Positional arguments for function
            **kwargs: Keyword arguments for function
            
        Returns:
            Function result on success
            
        Raises:
            CircuitBreakerError: If circuit is open
            Exception: Original function exception on failure
        """
        if self._state.state == CircuitState.OPEN:
            if not self._should_attempt_reset():
                raise CircuitBreakerError(
                    f"Circuit breaker is open. Next attempt in "
                    f"{self._time_until_next_attempt():.0f} seconds"
                )
            else:
                self._state.state = CircuitState.HALF_OPEN
                logger.info("Circuit breaker transitioning to HALF_OPEN")

        try:
            # Calculate delay for current attempt
            if self._state.failure_count > 0:
                delay = self.calculate_backoff_delay(self._state.failure_count - 1)
                logger.info(f"Waiting {delay}s before retry attempt {self._state.failure_count + 1}")
                await asyncio.sleep(delay)

            # Execute the function
            result = await async_func(*args, **kwargs)
            
            # Success - reset circuit breaker
            self.record_success()
            return result

        except Exception as e:
            # Failure - record and possibly open circuit
            self.record_failure()
            raise e

    def record_failure(self) -> None:
        """
        Track connection failures for circuit breaker state.
        """
        self._state.failure_count += 1
        self._state.last_failure_time = datetime.now()

        if self._state.failure_count >= self._failure_threshold:
            self._state.state = CircuitState.OPEN
            self._state.next_attempt_time = (
                datetime.now() + timedelta(seconds=self._reset_timeout)
            )
            
            logger.error(
                "Circuit breaker OPENED - maximum retries exceeded",
                failures=self._state.failure_count,
                threshold=self._failure_threshold,
                next_attempt=self._state.next_attempt_time.isoformat()
            )
        else:
            logger.warning(
                "Circuit breaker failure recorded",
                failures=self._state.failure_count,
                threshold=self._failure_threshold
            )

        self._save_state()

    def record_success(self) -> None:
        """
        Reset circuit breaker on successful connection.
        """
        previous_failures = self._state.failure_count
        
        self._state.state = CircuitState.CLOSED
        self._state.failure_count = 0
        self._state.last_failure_time = None
        self._state.next_attempt_time = None

        if previous_failures > 0:
            logger.info(
                "Circuit breaker CLOSED - connection recovered",
                previous_failures=previous_failures
            )

        self._save_state()

    def get_state(self) -> CircuitBreakerState:
        """
        Get current circuit breaker state.
        
        Returns:
            Current circuit breaker state
        """
        return self._state

    def is_open(self) -> bool:
        """
        Check if circuit breaker is open.
        
        Returns:
            True if circuit is open
        """
        return self._state.state == CircuitState.OPEN

    def _should_attempt_reset(self) -> bool:
        """
        Check if enough time has passed to attempt reset.
        
        Returns:
            True if reset should be attempted
        """
        if self._state.next_attempt_time is None:
            return True
            
        return datetime.now() >= self._state.next_attempt_time

    def _time_until_next_attempt(self) -> float:
        """
        Calculate seconds until next attempt is allowed.
        
        Returns:
            Seconds until next attempt
        """
        if self._state.next_attempt_time is None:
            return 0.0
            
        delta = self._state.next_attempt_time - datetime.now()
        return max(0.0, delta.total_seconds())

    def _load_state(self) -> CircuitBreakerState:
        """
        Load circuit breaker state from file.
        
        Returns:
            Loaded or default circuit breaker state
        """
        try:
            if self._state_file.exists():
                with open(self._state_file, 'r') as f:
                    data = json.load(f)
                    
                    # Convert string state back to enum
                    if 'state' in data and isinstance(data['state'], str):
                        data['state'] = CircuitState(data['state'])
                    
                    # Convert ISO datetime strings back to datetime objects
                    if data.get('last_failure_time'):
                        data['last_failure_time'] = datetime.fromisoformat(
                            data['last_failure_time'].replace('Z', '+00:00')
                        )
                    if data.get('next_attempt_time'):
                        data['next_attempt_time'] = datetime.fromisoformat(
                            data['next_attempt_time'].replace('Z', '+00:00')
                        )
                    
                    state = CircuitBreakerState(**data)
                    logger.debug("Circuit breaker state loaded", state=state.state.value)
                    return state
        except Exception as e:
            logger.warning("Failed to load circuit breaker state", error=str(e))
        
        # Return default state on load failure
        return CircuitBreakerState(reset_timeout=self._reset_timeout)

    def _save_state(self) -> None:
        """
        Save circuit breaker state to file.
        """
        try:
            # Convert to dict with ISO datetime strings
            state_dict = self._state.model_dump()
            
            # Convert enum to string value
            if 'state' in state_dict and hasattr(state_dict['state'], 'value'):
                state_dict['state'] = state_dict['state'].value
            
            # Convert datetime objects to ISO strings
            if self._state.last_failure_time:
                state_dict['last_failure_time'] = self._state.last_failure_time.isoformat()
            if self._state.next_attempt_time:
                state_dict['next_attempt_time'] = self._state.next_attempt_time.isoformat()

            self._state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._state_file, 'w') as f:
                json.dump(state_dict, f, indent=2)
                
            logger.debug("Circuit breaker state saved")
        except Exception as e:
            logger.warning("Failed to save circuit breaker state", error=str(e))