"""Market data integration adapter for execution function framework."""

import asyncio
from typing import Dict, Optional, Any, List

from loguru import logger

from auto_trader.models.market_data import BarData, BarSizeType
from auto_trader.models.execution import BarCloseEvent, ExecutionContext
from auto_trader.models.enums import Timeframe
from auto_trader.trade_engine.bar_close_detector import BarCloseDetector
from auto_trader.trade_engine.function_registry import ExecutionFunctionRegistry
from auto_trader.trade_engine.execution_logger import ExecutionLogger
from auto_trader.trade_engine.market_data_validator import (
    MarketDataValidator,
    MarketDataValidationResult,
)
from auto_trader.trade_engine.historical_data_manager import HistoricalDataManager
from auto_trader.trade_engine.signal_emitter import SignalEmitter




class MarketDataExecutionAdapter:
    """Adapter connecting market data system to execution framework.
    
    Bridges the market data distribution system with bar close detection
    and execution function evaluation using composition pattern.
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
        
        # Initialize components using composition pattern
        self.validator = MarketDataValidator(
            max_reasonable_price=10000.0,
            future_timestamp_tolerance_seconds=1,
        )
        
        self.historical_data_manager = HistoricalDataManager(
            max_historical_bars=1000,
            min_bars_for_execution=20,
        )
        
        self.signal_emitter = SignalEmitter()
        
        # Track active execution contexts
        self.active_contexts: Dict[str, ExecutionContext] = {}
        
        # Subscribe to bar close events
        self.bar_close_detector.add_callback(self._on_bar_close)
        
        logger.info("MarketDataExecutionAdapter initialized with composition pattern")
    
    # Backward compatibility properties for tests
    @property
    def historical_data(self):
        """Access historical data for backward compatibility."""
        return self.historical_data_manager.historical_data
    
    @property
    def signal_callbacks(self):
        """Access signal callbacks for backward compatibility."""
        return self.signal_emitter.signal_callbacks
    
    @property
    def max_historical_bars(self):
        """Access max historical bars setting."""
        return self.historical_data_manager.max_historical_bars
    
    @max_historical_bars.setter
    def max_historical_bars(self, value: int):
        """Set max historical bars setting."""
        self.historical_data_manager.max_historical_bars = value
    
    @property
    def min_bars_for_execution(self):
        """Access min bars for execution setting."""
        return self.historical_data_manager.min_bars_for_execution
    
    async def on_market_data_update(self, bar: BarData) -> None:
        """Handle market data updates from IBKR distribution system.
        
        This method is called by the market data distributor when new bars arrive.
        
        Args:
            bar: New bar data received
        """
        try:
            # Validate market data for corruption using validator component
            validation_result = self.validator.validate(bar)
            if not validation_result.is_valid:
                error_msg = f"Invalid market data detected: {validation_result.error_message}"
                logger.error(
                    error_msg,
                    symbol=bar.symbol,
                    timestamp=bar.timestamp.isoformat(),
                    corruption_type=validation_result.corruption_type,
                )
                
                # Also log to execution logger for test queries
                error_exception = ValueError(error_msg)
                await self.execution_logger.log_error(
                    function_name="market_data_validation",
                    symbol=bar.symbol,
                    timeframe=Timeframe.ONE_MIN,  # Default timeframe for corruption logs
                    error=error_exception,
                    context=None
                )
                
                # Don't process corrupted data
                return
            
            # Convert bar size to timeframe
            timeframe = self._convert_bar_size_to_timeframe(bar.bar_size)
            if not timeframe:
                logger.warning(f"Unsupported bar size: {bar.bar_size}")
                return
            
            # Update historical data using manager component
            await self.historical_data_manager.update_data(bar, timeframe)
            
            # For 1-minute bars, also store them for all monitored timeframes of this symbol
            # This ensures longer timeframes have sufficient historical data for aggregation
            if timeframe == Timeframe.ONE_MIN:
                monitored = self.bar_close_detector.get_monitored()
                await self.historical_data_manager.store_one_minute_for_all_timeframes(bar, monitored)
            
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
        await self.historical_data_manager.initialize_storage(symbol, timeframe)
        
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
        
        # Clean up historical data using manager component
        await self.historical_data_manager.cleanup_storage(symbol, timeframe)
        
        logger.info(f"Stopped execution monitoring for {symbol}")
    
    def add_signal_callback(self, callback) -> None:
        """Add callback for execution signals.
        
        Args:
            callback: Function to call when execution signals are generated
        """
        self.signal_emitter.add_callback(callback)
    
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
            
            # Get historical data for context using manager component
            historical_bars = await self.historical_data_manager.get_historical_bars(symbol, timeframe)
            
            if not await self.historical_data_manager.has_sufficient_data(symbol, timeframe):
                logger.warning(
                    f"Insufficient historical data for {symbol} {timeframe.value}: "
                    f"{len(historical_bars)} bars (need {self.historical_data_manager.min_bars_for_execution})"
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
            
            # Re-raise circuit breaker exceptions to trigger failure cascading
            if isinstance(e, RuntimeError) and "circuit breaker" in str(e).lower():
                raise
    
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
            await self.execution_logger.log_evaluation(
                function_name=function.name,
                context=context,
                signal=signal,
                duration_ms=duration_ms,
            )
            
            # If signal should execute, notify callbacks using signal emitter
            if signal.should_execute:
                await self.signal_emitter.emit_signal(function, context, signal)
                
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
            await self.execution_logger.log_error(
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
            
            # Re-raise circuit breaker exceptions to trigger failure cascading
            if isinstance(e, RuntimeError) and "circuit breaker" in str(e).lower():
                raise
    
    
    
    
    
    def _convert_bar_size_to_timeframe(self, bar_size: BarSizeType) -> Optional[Timeframe]:
        """Convert bar size string to Timeframe enum.
        
        Args:
            bar_size: Bar size from BarData
            
        Returns:
            Corresponding Timeframe or None if unsupported
        """
        return self.TIMEFRAME_MAPPING.get(bar_size)
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get adapter statistics.
        
        Returns:
            Dictionary with adapter statistics
        """
        historical_stats = await self.historical_data_manager.get_stats()
        
        return {
            **historical_stats,
            "active_functions": len(self.function_registry.list_instances()),
            "signal_callbacks": self.signal_emitter.get_callback_count(),
            "timing_stats": self.bar_close_detector.get_timing_stats(),
            "execution_metrics": self.execution_logger.get_metrics(),
        }
    

