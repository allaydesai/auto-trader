"""Circuit breaker pattern implementation for order execution reliability."""

from datetime import datetime, UTC
from typing import Dict, Any

from loguru import logger


class CircuitBreakerManager:
    """Manages circuit breaker state for order execution resilience.
    
    Implements the circuit breaker pattern to prevent cascading failures
    when order execution encounters repeated errors.
    """
    
    def __init__(
        self,
        max_consecutive_failures: int = 5,
        reset_timeout: float = 0.05,
        enabled: bool = True,
    ):
        """Initialize circuit breaker manager.
        
        Args:
            max_consecutive_failures: Maximum failures before opening circuit
            reset_timeout: Timeout in seconds before attempting reset
            enabled: Whether circuit breaker is enabled
        """
        self.max_consecutive_failures = max_consecutive_failures
        self.reset_timeout = reset_timeout
        self.enabled = enabled
        
        # Circuit breaker state
        self.consecutive_failures = 0
        self.circuit_breaker_open = False
        self.last_failure_time = None
        
        logger.info(
            "CircuitBreakerManager initialized",
            max_failures=max_consecutive_failures,
            timeout=reset_timeout,
            enabled=enabled,
        )
    
    def check_state(self) -> None:
        """Check and enforce circuit breaker state.
        
        Raises:
            RuntimeError: If circuit breaker is open
        """
        if not self.enabled or not self.circuit_breaker_open:
            return
            
        # Check if we should attempt to reset (half-open state)
        if self.last_failure_time:
            current_time = datetime.now(UTC)
            last_failure_utc = self._ensure_utc(self.last_failure_time)
                
            time_since_failure = (current_time - last_failure_utc).total_seconds()
            if time_since_failure >= self.reset_timeout:
                logger.warning("Circuit breaker entering half-open state - allowing test request")
                # Reset to half-open state (will be fully reset on success)
                self.circuit_breaker_open = False
                return
        
        # Circuit breaker is open - reject the request
        logger.error("Circuit breaker is OPEN - rejecting order request")
        raise RuntimeError("Circuit breaker is open due to consecutive failures")
    
    def record_success(self) -> None:
        """Record successful operation for circuit breaker."""
        if self.circuit_breaker_open:
            logger.info("Circuit breaker reset after successful operation")
            self.circuit_breaker_open = False
        
        self.consecutive_failures = 0
        self.last_failure_time = None
    
    def record_failure(self) -> None:
        """Record failed operation for circuit breaker."""
        if not self.enabled:
            return
            
        self.consecutive_failures += 1
        self.last_failure_time = datetime.now(UTC)
        
        logger.warning(
            f"Order execution failure recorded ({self.consecutive_failures}/{self.max_consecutive_failures})"
        )
        
        # Trip circuit breaker if threshold reached
        if self.consecutive_failures >= self.max_consecutive_failures:
            self.circuit_breaker_open = True
            logger.error(
                f"Circuit breaker OPENED after {self.consecutive_failures} consecutive failures"
            )
    
    def reset(self) -> None:
        """Reset circuit breaker state for manual recovery.
        
        This method allows manual reset of the circuit breaker state,
        useful for testing scenarios or administrative reset.
        """
        logger.info("Circuit breaker manually reset")
        self.circuit_breaker_open = False
        self.consecutive_failures = 0
        self.last_failure_time = None
    
    def get_stats(self) -> Dict[str, Any]:
        """Get circuit breaker statistics.
        
        Returns:
            Dictionary with circuit breaker state and statistics
        """
        return {
            "consecutive_failures": self.consecutive_failures,
            "circuit_breaker_open": self.circuit_breaker_open,
            "max_consecutive_failures": self.max_consecutive_failures,
            "reset_timeout": self.reset_timeout,
            "enabled": self.enabled,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
        }
    
    def _ensure_utc(self, timestamp: datetime) -> datetime:
        """Ensure timestamp is UTC timezone-aware.
        
        Args:
            timestamp: Timestamp to convert
            
        Returns:
            UTC timezone-aware timestamp
        """
        if timestamp.tzinfo is None:
            return timestamp.replace(tzinfo=UTC)
        elif timestamp.tzinfo != UTC:
            return timestamp.astimezone(UTC)
        return timestamp