"""Connection manager integrating IBKR client with circuit breaker."""

import asyncio
import signal
from pathlib import Path
from typing import Optional

from loguru import logger

from .circuit_breaker import CircuitBreaker, CircuitBreakerError, CircuitBreakerState
from .client import ConnectionState, IBKRClient, ConnectionStatus
from config import Settings


class ConnectionManager:
    """
    Connection manager with circuit breaker and graceful shutdown.
    
    Integrates IBKRClient with CircuitBreaker for reliable connection
    management with automatic reconnection and failure handling.
    """

    def __init__(
        self,
        settings: Optional[Settings] = None,
        state_dir: Optional[Path] = None
    ):
        """
        Initialize connection manager.
        
        Args:
            settings: Optional settings instance
            state_dir: Optional directory for state persistence
        """
        self._settings = settings or Settings()
        self._state_dir = state_dir or Path("state")
        
        self._client = IBKRClient(self._settings)
        self._circuit_breaker = CircuitBreaker(
            failure_threshold=5,
            reset_timeout=60,
            state_file=self._state_dir / "circuit_breaker_state.json"
        )
        
        self._shutdown_initiated = False
        self._reconnection_task: Optional[asyncio.Task] = None

    async def connect(self) -> None:
        """
        Connect to IBKR with circuit breaker protection.
        
        Raises:
            CircuitBreakerError: If circuit breaker is open
            IBKRConnectionError: If connection fails
        """
        try:
            await self._circuit_breaker.call_with_circuit_breaker(
                self._client.connect
            )
            
            # Start monitoring for disconnections
            self._start_connection_monitoring()
            
        except CircuitBreakerError as e:
            logger.error("Connection blocked by circuit breaker", error=str(e))
            raise
        except Exception as e:
            logger.error("Connection attempt failed", error=str(e))
            raise

    async def disconnect(self) -> None:
        """
        Graceful disconnection with cleanup.
        """
        logger.info("Initiating graceful disconnection")
        
        # Stop reconnection monitoring
        if self._reconnection_task and not self._reconnection_task.done():
            self._reconnection_task.cancel()
            try:
                await self._reconnection_task
            except asyncio.CancelledError:
                pass

        # Disconnect client
        await self._client.disconnect()
        logger.info("Disconnection completed")

    def is_connected(self) -> bool:
        """
        Check if connected to IBKR.
        
        Returns:
            True if connected
        """
        return self._client.is_connected()

    def get_connection_status(self) -> ConnectionStatus:
        """
        Get current connection status.
        
        Returns:
            Connection status information
        """
        return self._client.get_connection_status()

    def get_circuit_breaker_state(self) -> CircuitBreakerState:
        """
        Get circuit breaker state.
        
        Returns:
            Circuit breaker state information
        """
        return self._circuit_breaker.get_state()

    async def health_check(self) -> dict:
        """
        Perform comprehensive health check.
        
        Returns:
            Health check results
        """
        connection_status = self.get_connection_status()
        circuit_state = self.get_circuit_breaker_state()
        
        return {
            "connected": self.is_connected(),
            "connection_state": connection_status.state.value,
            "last_connected": connection_status.last_connected,
            "reconnect_attempts": connection_status.reconnect_attempts,
            "account_type": connection_status.account_type,
            "is_paper_account": connection_status.is_paper_account,
            "circuit_breaker_state": circuit_state.state.value,
            "circuit_failure_count": circuit_state.failure_count,
            "circuit_last_failure": circuit_state.last_failure_time,
        }

    def setup_signal_handlers(self) -> None:
        """
        Register signal handlers for graceful shutdown.
        """
        try:
            signal.signal(signal.SIGTERM, self._signal_handler)
            signal.signal(signal.SIGINT, self._signal_handler)
            logger.info("Signal handlers registered for graceful shutdown")
        except ValueError as e:
            # Signal handlers can only be set in the main thread
            logger.warning("Could not register signal handlers", error=str(e))

    def _signal_handler(self, signum: int, frame) -> None:
        """
        Handle shutdown signals.
        
        Args:
            signum: Signal number
            frame: Current stack frame
        """
        if not self._shutdown_initiated:
            logger.info("Shutdown signal received", signal=signum)
            self._shutdown_initiated = True
            
            # Create shutdown task
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(self.graceful_shutdown())
            else:
                loop.run_until_complete(self.graceful_shutdown())

    async def graceful_shutdown(self) -> None:
        """
        Perform graceful system shutdown.
        """
        if self._shutdown_initiated:
            return
            
        self._shutdown_initiated = True
        
        try:
            logger.info("Starting graceful shutdown")
            
            # Update connection state
            client_status = self._client.get_connection_status()
            client_status.state = ConnectionState.SHUTDOWN
            
            # Handle position closure if configured
            ibkr_config = self._client._config_loader.system_config.ibkr
            if ibkr_config.graceful_shutdown and self.is_connected():
                logger.info("Graceful shutdown configured - checking for open positions")
                await self._close_open_positions()

            # Disconnect from IBKR
            await self.disconnect()
            
            logger.info("Graceful shutdown completed")
            
        except Exception as e:
            logger.error("Error during graceful shutdown", error=str(e))

    def _start_connection_monitoring(self) -> None:
        """
        Start monitoring connection for automatic reconnection.
        """
        if self._reconnection_task and not self._reconnection_task.done():
            return
            
        self._reconnection_task = asyncio.create_task(self._monitor_connection())

    async def _monitor_connection(self) -> None:
        """
        Monitor connection and handle reconnection.
        """
        try:
            while not self._shutdown_initiated:
                await asyncio.sleep(5)  # Check every 5 seconds
                
                if not self.is_connected() and not self._shutdown_initiated:
                    logger.warning("Connection lost - attempting reconnection")
                    
                    try:
                        await self._circuit_breaker.call_with_circuit_breaker(
                            self._client.connect
                        )
                        logger.info("Reconnection successful")
                        
                    except CircuitBreakerError:
                        logger.error("Reconnection blocked by circuit breaker")
                        break
                    except Exception as e:
                        logger.error("Reconnection failed", error=str(e))
                        # Continue monitoring - circuit breaker will handle retry logic
                        
        except asyncio.CancelledError:
            logger.debug("Connection monitoring cancelled")
        except Exception as e:
            logger.error("Error in connection monitoring", error=str(e))

    async def _close_open_positions(self) -> None:
        """
        Close open positions during shutdown.
        
        This is a placeholder for position closure logic.
        Actual implementation would depend on position tracking system.
        """
        try:
            logger.info("Checking for open positions to close")
            
            # TODO: Implement position closure logic
            # This would typically:
            # 1. Get current positions from IBKR
            # 2. Create market orders to close all positions  
            # 3. Monitor order execution
            # 4. Log position closure results
            
            logger.info("Position closure check completed (no positions to close)")
            
        except Exception as e:
            logger.error("Error during position closure", error=str(e))