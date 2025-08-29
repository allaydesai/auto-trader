"""Signal emission and callback management for execution framework."""

import asyncio
from typing import List, Callable, Dict, Any

from loguru import logger

from auto_trader.models.execution import ExecutionContext, ExecutionSignal


class SignalEmitter:
    """Manages execution signal emission and callback handling.
    
    Coordinates the emission of execution signals to registered callbacks
    with proper error handling and circuit breaker support.
    """
    
    def __init__(self):
        """Initialize signal emitter."""
        self.signal_callbacks: List[Callable] = []
        
        logger.info("SignalEmitter initialized")
    
    def add_callback(self, callback: Callable) -> None:
        """Add callback for execution signals.
        
        Args:
            callback: Function to call when execution signals are generated
        """
        self.signal_callbacks.append(callback)
        callback_name = getattr(callback, '__name__', repr(callback))
        logger.debug(f"Added execution signal callback: {callback_name}")
    
    def remove_callback(self, callback: Callable) -> None:
        """Remove callback from signal emission.
        
        Args:
            callback: Callback function to remove
        """
        if callback in self.signal_callbacks:
            self.signal_callbacks.remove(callback)
            callback_name = getattr(callback, '__name__', repr(callback))
            logger.debug(f"Removed execution signal callback: {callback_name}")
    
    async def emit_signal(
        self,
        function,
        context: ExecutionContext,
        signal: ExecutionSignal,
    ) -> None:
        """Emit execution signal to registered callbacks.
        
        Args:
            function: Function that generated the signal
            context: Execution context
            signal: Generated execution signal
        """
        signal_data = {
            "function_name": function.name,
            "symbol": context.symbol,
            "timeframe": context.timeframe,
            "signal": signal,
            "context": context,
            "timestamp": context.timestamp,
        }
        
        for callback in self.signal_callbacks:
            try:
                await self._invoke_callback(callback, signal_data)
            except RuntimeError as e:
                # Circuit breaker and other critical errors should propagate
                if "circuit breaker" in str(e).lower():
                    callback_name = getattr(callback, '__name__', repr(callback))
                    logger.error(f"Error in signal callback {callback_name}: {e}")
                    raise  # Re-raise circuit breaker exceptions
                else:
                    callback_name = getattr(callback, '__name__', repr(callback))
                    logger.error(f"Error in signal callback {callback_name}: {e}")
            except Exception as e:
                callback_name = getattr(callback, '__name__', repr(callback))
                logger.error(f"Error in signal callback {callback_name}: {e}")
    
    async def _invoke_callback(self, callback: Callable, signal_data: Dict[str, Any]) -> None:
        """Invoke callback with proper async/sync handling.
        
        Args:
            callback: Callback function to invoke
            signal_data: Signal data to pass to callback
        """
        if asyncio.iscoroutinefunction(callback):
            await callback(signal_data)
        else:
            callback(signal_data)
    
    def get_callback_count(self) -> int:
        """Get number of registered callbacks.
        
        Returns:
            Number of callbacks registered
        """
        return len(self.signal_callbacks)
    
    def clear_callbacks(self) -> None:
        """Clear all registered callbacks."""
        callback_count = len(self.signal_callbacks)
        self.signal_callbacks.clear()
        logger.debug(f"Cleared {callback_count} signal callbacks")