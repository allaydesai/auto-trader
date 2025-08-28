"""Market data integration adapter for execution function framework."""

import asyncio
from datetime import datetime, UTC
from typing import Dict, Set, Optional, List, Callable
from threading import Lock

from loguru import logger

from auto_trader.models.market_data import BarData, BarSizeType
from auto_trader.models.execution import BarCloseEvent, ExecutionContext
from auto_trader.models.enums import Timeframe, ExecutionAction
from auto_trader.trade_engine.bar_close_detector import BarCloseDetector
from auto_trader.trade_engine.function_registry import ExecutionFunctionRegistry
from auto_trader.trade_engine.execution_logger import ExecutionLogger


class MarketDataExecutionAdapter:
    """Adapter connecting market data system to execution framework.
    
    Bridges the market data distribution system with bar close detection
    and execution function evaluation.
    """
    
    # Mapping from BarSizeType to Timeframe
    TIMEFRAME_MAPPING = {
        "1min": Timeframe.ONE_MIN,
        "5min": Timeframe.FIVE_MIN,
        "15min": Timeframe.FIFTEEN_MIN,
        "30min": Timeframe.THIRTY_MIN,
        "1hour": Timeframe.ONE_HOUR,
        "4hour": Timeframe.FOUR_HOUR,
        "1day": Timeframe.ONE_DAY,
    }
    
    def __init__(
        self,
        bar_close_detector: BarCloseDetector,
        function_registry: ExecutionFunctionRegistry,
        execution_logger: ExecutionLogger,
    ):
        """Initialize market data execution adapter.
        
        Args:
            bar_close_detector: Bar close detection system
            function_registry: Function registry for execution functions
            execution_logger: Logger for execution decisions
        """
        self.bar_close_detector = bar_close_detector
        self.function_registry = function_registry
        self.execution_logger = execution_logger
        
        # Track monitored symbols and their historical data
        self.historical_data: Dict[str, Dict[Timeframe, List[BarData]]] = {}
        self.historical_data_lock = Lock()
        
        # Track active execution contexts
        self.active_contexts: Dict[str, ExecutionContext] = {}
        
        # Configuration
        self.max_historical_bars = 1000  # Maximum bars to keep per symbol/timeframe
        self.min_bars_for_execution = 20  # Minimum bars needed for function evaluation
        
        # Callbacks for execution signals
        self.signal_callbacks: List[Callable] = []
        
        # Subscribe to bar close events
        self.bar_close_detector.add_callback(self._on_bar_close)
        
        logger.info("MarketDataExecutionAdapter initialized")
    
    def on_market_data_update(self, bar: BarData) -> None:
        """Handle market data updates from IBKR distribution system.
        
        This method is called by the market data distributor when new bars arrive.
        
        Args:
            bar: New bar data received
        """
        try:
            # Convert bar size to timeframe
            timeframe = self._convert_bar_size_to_timeframe(bar.bar_size)
            if not timeframe:
                logger.warning(f"Unsupported bar size: {bar.bar_size}")
                return
            
            # Update historical data
            self._update_historical_data(bar, timeframe)
            
            # Update bar close detector with latest data
            self.bar_close_detector.update_bar_data(bar.symbol, timeframe, bar)
            
            logger.debug(
                f"Updated market data for {bar.symbol} {timeframe.value}",
                timestamp=bar.timestamp.isoformat(),
                close=float(bar.close_price),
            )
            
        except Exception as e:
            logger.error(f"Error processing market data update: {e}", bar=bar.model_dump())
    
    async def start_monitoring(self, symbol: str, timeframe: Timeframe) -> None:
        """Start monitoring a symbol/timeframe for execution functions.
        
        Args:
            symbol: Trading symbol to monitor
            timeframe: Timeframe to monitor
        """
        # Initialize historical data storage if needed
        with self.historical_data_lock:
            if symbol not in self.historical_data:
                self.historical_data[symbol] = {}
            if timeframe not in self.historical_data[symbol]:
                self.historical_data[symbol][timeframe] = []
        
        # Start bar close monitoring
        await self.bar_close_detector.monitor_timeframe(symbol, timeframe)
        
        logger.info(f"Started execution monitoring for {symbol} {timeframe.value}")
    
    async def stop_monitoring(self, symbol: str, timeframe: Optional[Timeframe] = None) -> None:
        """Stop monitoring a symbol/timeframe.
        
        Args:
            symbol: Symbol to stop monitoring
            timeframe: Specific timeframe or None for all timeframes
        """
        await self.bar_close_detector.stop_monitoring(symbol, timeframe)
        
        # Clean up historical data
        with self.historical_data_lock:
            if timeframe and symbol in self.historical_data:
                if timeframe in self.historical_data[symbol]:
                    del self.historical_data[symbol][timeframe]
                    
                # Remove symbol if no timeframes left
                if not self.historical_data[symbol]:
                    del self.historical_data[symbol]
            elif symbol in self.historical_data:
                del self.historical_data[symbol]
        
        logger.info(f"Stopped execution monitoring for {symbol}")
    
    def add_signal_callback(self, callback: Callable) -> None:
        """Add callback for execution signals.
        
        Args:
            callback: Function to call when execution signals are generated
        """
        self.signal_callbacks.append(callback)
        callback_name = getattr(callback, '__name__', repr(callback))
        logger.debug(f"Added execution signal callback: {callback_name}")
    
    def get_active_monitoring(self) -> Dict[str, List[str]]:
        """Get currently monitored symbol/timeframe combinations.
        
        Returns:
            Dictionary mapping symbols to list of timeframes
        """
        return self.bar_close_detector.get_monitored()
    
    async def _on_bar_close(self, event: BarCloseEvent) -> None:
        """Handle bar close events by evaluating execution functions.
        
        Args:
            event: Bar close event
        """
        try:
            symbol = event.symbol
            timeframe = event.timeframe
            
            logger.debug(
                f"Processing bar close for {symbol} {timeframe.value}",
                close_time=event.close_time.isoformat(),
            )
            
            # Get execution functions for this timeframe
            functions = self.function_registry.get_functions_by_timeframe(timeframe.value)
            
            if not functions:
                logger.debug(f"No execution functions registered for {timeframe.value}")
                return
            
            # Get historical data for context
            historical_bars = self._get_historical_bars(symbol, timeframe)
            
            if len(historical_bars) < self.min_bars_for_execution:
                logger.warning(
                    f"Insufficient historical data for {symbol} {timeframe.value}: "
                    f"{len(historical_bars)} bars (need {self.min_bars_for_execution})"
                )
                return
            
            # Create execution context
            context = ExecutionContext(
                symbol=symbol,
                timeframe=timeframe,
                current_bar=event.bar_data,
                historical_bars=historical_bars,
                trade_plan_params={},  # This would come from trade plan system
                position_state=None,   # This would come from position tracking
                account_balance=10000,  # This would come from account info
                timestamp=event.close_time,
            )
            
            # Evaluate each function
            for function in functions:
                await self._evaluate_function(function, context)
                
        except Exception as e:
            logger.error(f"Error processing bar close event: {e}", event=event.model_dump())
    
    async def _evaluate_function(self, function, context: ExecutionContext) -> None:
        """Evaluate a single execution function.
        
        Args:
            function: Execution function to evaluate
            context: Execution context
        """
        start_time = asyncio.get_event_loop().time()
        
        try:
            # Evaluate the function
            signal = await function.evaluate(context)
            
            # Calculate duration
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            # Log the evaluation
            self.execution_logger.log_evaluation(
                function_name=function.name,
                context=context,
                signal=signal,
                duration_ms=duration_ms,
            )
            
            # If signal should execute, notify callbacks
            if signal.should_execute:
                await self._emit_execution_signal(function, context, signal)
                
                logger.warning(
                    f"Execution signal generated: {signal.action.value}",
                    function=function.name,
                    symbol=context.symbol,
                    confidence=signal.confidence,
                    reasoning=signal.reasoning,
                )
            
        except Exception as e:
            duration_ms = (asyncio.get_event_loop().time() - start_time) * 1000
            
            # Log the error
            self.execution_logger.log_error(
                function_name=function.name,
                symbol=context.symbol,
                timeframe=context.timeframe,
                error=e,
                context=context,
            )
            
            logger.error(
                f"Execution function evaluation failed: {e}",
                function=function.name,
                symbol=context.symbol,
                timeframe=context.timeframe.value,
            )
    
    async def _emit_execution_signal(self, function, context: ExecutionContext, signal) -> None:
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
                if asyncio.iscoroutinefunction(callback):
                    await callback(signal_data)
                else:
                    callback(signal_data)
            except Exception as e:
                logger.error(f"Error in signal callback {callback.__name__}: {e}")
    
    def _update_historical_data(self, bar: BarData, timeframe: Timeframe) -> None:
        """Update historical data storage.
        
        Args:
            bar: New bar to add
            timeframe: Timeframe of the bar
        """
        with self.historical_data_lock:
            symbol = bar.symbol
            
            # Initialize storage if needed
            if symbol not in self.historical_data:
                self.historical_data[symbol] = {}
            if timeframe not in self.historical_data[symbol]:
                self.historical_data[symbol][timeframe] = []
            
            # Add the bar
            bars = self.historical_data[symbol][timeframe]
            bars.append(bar)
            
            # Maintain size limit
            if len(bars) > self.max_historical_bars:
                bars[:] = bars[-self.max_historical_bars:]
                
                logger.debug(
                    f"Trimmed historical data for {symbol} {timeframe.value}",
                    kept_bars=len(bars),
                )
    
    def _get_historical_bars(self, symbol: str, timeframe: Timeframe) -> List[BarData]:
        """Get historical bars for a symbol/timeframe.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            
        Returns:
            List of historical bars (most recent last)
        """
        with self.historical_data_lock:
            if symbol in self.historical_data and timeframe in self.historical_data[symbol]:
                return self.historical_data[symbol][timeframe].copy()
            return []
    
    def _convert_bar_size_to_timeframe(self, bar_size: BarSizeType) -> Optional[Timeframe]:
        """Convert bar size string to Timeframe enum.
        
        Args:
            bar_size: Bar size from BarData
            
        Returns:
            Corresponding Timeframe or None if unsupported
        """
        return self.TIMEFRAME_MAPPING.get(bar_size)
    
    def get_stats(self) -> Dict[str, any]:
        """Get adapter statistics.
        
        Returns:
            Dictionary with adapter statistics
        """
        with self.historical_data_lock:
            total_bars = sum(
                len(timeframe_bars)
                for symbol_data in self.historical_data.values()
                for timeframe_bars in symbol_data.values()
            )
            
            total_combinations = sum(
                len(timeframes) for timeframes in self.historical_data.values()
            )
        
        return {
            "monitored_symbols": len(self.historical_data),
            "monitored_combinations": total_combinations,
            "total_historical_bars": total_bars,
            "active_functions": len(self.function_registry.list_instances()),
            "signal_callbacks": len(self.signal_callbacks),
            "timing_stats": self.bar_close_detector.get_timing_stats(),
            "execution_metrics": self.execution_logger.get_metrics(),
        }