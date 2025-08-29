"""Multi-timeframe integration tests for execution function framework.

This module tests the simultaneous monitoring and execution across multiple
timeframes, ensuring proper synchronization and performance.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, UTC, timedelta
from decimal import Decimal
from typing import Dict, List, Set, Optional

from auto_trader.models.market_data import BarData
from auto_trader.models.execution import ExecutionFunctionConfig, ExecutionSignal, BarCloseEvent
from auto_trader.models.enums import Timeframe, ExecutionAction
from auto_trader.models.trade_plan import RiskCategory
from auto_trader.models.order import OrderResult
from auto_trader.trade_engine.function_registry import ExecutionFunctionRegistry
from auto_trader.trade_engine.execution_logger import ExecutionLogger
from auto_trader.trade_engine.bar_close_detector import BarCloseDetector
from auto_trader.trade_engine.market_data_adapter import MarketDataExecutionAdapter
from auto_trader.trade_engine.order_execution_adapter import ExecutionOrderAdapter
from auto_trader.trade_engine.functions import CloseAboveFunction, CloseBelowFunction


class MockMultiTimeframeDetector:
    """Enhanced mock detector that handles multiple timeframes realistically."""
    
    def __init__(self):
        self.monitored_timeframes: Dict[str, Set[Timeframe]] = {}
        self.callbacks: List[callable] = []
        self.bar_data: Dict[str, Dict[Timeframe, List[BarData]]] = {}
        self.timing_stats = {
            "avg_detection_latency_ms": 45.0,
            "max_detection_latency_ms": 120.0,
            "total_detections": 0,
            "timeframe_stats": {}
        }
        
    def add_callback(self, callback):
        self.callbacks.append(callback)
        
    async def monitor_timeframe(self, symbol: str, timeframe: Timeframe):
        """Start monitoring symbol/timeframe combination."""
        if symbol not in self.monitored_timeframes:
            self.monitored_timeframes[symbol] = set()
        self.monitored_timeframes[symbol].add(timeframe)
        
        # Initialize data storage
        if symbol not in self.bar_data:
            self.bar_data[symbol] = {}
        if timeframe not in self.bar_data[symbol]:
            self.bar_data[symbol][timeframe] = []
    
    def update_bar_data(self, symbol: str, timeframe: Timeframe, bar: BarData):
        """Update bar data and trigger close detection if needed."""
        # Initialize data storage for symbol if needed
        if symbol not in self.bar_data:
            self.bar_data[symbol] = {}
        
        # Store bar data for all timeframes (not just 1-minute)
        if timeframe not in self.bar_data[symbol]:
            self.bar_data[symbol][timeframe] = []
            
        self.bar_data[symbol][timeframe].append(bar)
        
        # For 1-minute bars, also store them for ALL monitored timeframes for this symbol
        # This simulates how longer timeframes are built from 1-minute data
        if timeframe == Timeframe.ONE_MIN and symbol in self.monitored_timeframes:
            for monitored_timeframe in self.monitored_timeframes[symbol]:
                # Store the 1-minute bar for each monitored timeframe (for aggregation)
                if monitored_timeframe not in self.bar_data[symbol]:
                    self.bar_data[symbol][monitored_timeframe] = []
                self.bar_data[symbol][monitored_timeframe].append(bar)
                
                # Check if this triggers a bar close for that timeframe
                self._check_bar_close(symbol, monitored_timeframe, bar)
        elif timeframe != Timeframe.ONE_MIN:
            # For non-1min bars, only check their own timeframe
            self._check_bar_close(symbol, timeframe, bar)
    
    def _check_bar_close(self, symbol: str, timeframe: Timeframe, bar: BarData):
        """Simulate realistic bar close detection logic."""
        # Simulate different close timings for different timeframes
        should_close = self._should_trigger_close(timeframe, bar.timestamp)
        
        # Debug output for first few bars
        minute = bar.timestamp.minute
        if minute <= 5 or minute % 15 == 0 or minute == 59:
            print(f"  Checking {timeframe.value}: minute={minute}, should_close={should_close}")
        
        if should_close:
            # Schedule bar close event
            asyncio.create_task(self._trigger_bar_close(symbol, timeframe, bar))
    
    def _should_trigger_close(self, timeframe: Timeframe, timestamp: datetime) -> bool:
        """Determine if a bar close should be triggered based on timeframe."""
        minute = timestamp.minute
        
        if timeframe == Timeframe.ONE_MIN:
            return True  # Every bar closes
        elif timeframe == Timeframe.FIVE_MIN:
            # Trigger every 5th minute (0, 5, 10, 15, etc.) or force trigger for test
            return minute % 5 == 4 or minute % 5 == 0  # More flexible triggering
        elif timeframe == Timeframe.FIFTEEN_MIN:
            # Trigger every 15th minute (0, 15, 30, 45) or force trigger for test  
            return minute % 15 == 14 or minute % 15 == 0  # More flexible triggering
        elif timeframe == Timeframe.THIRTY_MIN:
            return minute % 30 == 29 or minute % 30 == 0
        elif timeframe == Timeframe.ONE_HOUR:
            return minute == 59 or minute == 0
        elif timeframe == Timeframe.FOUR_HOUR:
            return minute == 59 and (timestamp.hour % 4 == 3 or timestamp.hour % 4 == 0)
        elif timeframe == Timeframe.ONE_DAY:
            return timestamp.hour == 23 and minute == 59
        
        return False
    
    async def _trigger_bar_close(self, symbol: str, timeframe: Timeframe, bar: BarData):
        """Trigger bar close event for callbacks."""
        self.timing_stats["total_detections"] += 1
        
        # Create appropriate bar for the timeframe
        close_bar = self._create_timeframe_bar(symbol, timeframe, bar.timestamp)
        
        event = BarCloseEvent(
            symbol=symbol,
            timeframe=timeframe,
            close_time=bar.timestamp,
            bar_data=close_bar,
            next_close_time=self._get_next_close_time(timeframe, bar.timestamp),
        )
        
        # Call all registered callbacks
        for callback in self.callbacks:
            try:
                await callback(event)
            except Exception as e:
                pass  # Ignore callback errors in mock
    
    def _create_timeframe_bar(self, symbol: str, timeframe: Timeframe, timestamp: datetime) -> BarData:
        """Create aggregated bar for the timeframe."""
        # Map timeframe to valid bar_size string
        bar_size_map = {
            Timeframe.ONE_MIN: "1min",
            Timeframe.FIVE_MIN: "5min", 
            Timeframe.FIFTEEN_MIN: "15min",
            Timeframe.THIRTY_MIN: "30min",
            Timeframe.ONE_HOUR: "1hour",
            Timeframe.FOUR_HOUR: "4hour",
            Timeframe.ONE_DAY: "1day",
        }
        
        # For aggregation, use 1-minute bars for longer timeframes
        if timeframe == Timeframe.ONE_MIN:
            # Use the actual 1-minute bars
            recent_bars = self.bar_data.get(symbol, {}).get(timeframe, [])
        else:
            # For longer timeframes, aggregate from 1-minute data
            one_min_bars = self.bar_data.get(symbol, {}).get(Timeframe.ONE_MIN, [])
            
            # Determine how many 1-minute bars to aggregate
            minutes_map = {
                Timeframe.FIVE_MIN: 5,
                Timeframe.FIFTEEN_MIN: 15,
                Timeframe.THIRTY_MIN: 30,
                Timeframe.ONE_HOUR: 60,
                Timeframe.FOUR_HOUR: 240,
                Timeframe.ONE_DAY: 1440,
            }
            
            minutes_needed = minutes_map.get(timeframe, 5)
            recent_bars = one_min_bars[-minutes_needed:] if len(one_min_bars) >= minutes_needed else one_min_bars
        
        if not recent_bars:
            # Create synthetic bar
            return BarData(
                symbol=symbol,
                timestamp=timestamp,
                open_price=Decimal("180.0000"),
                high_price=Decimal("181.0000"),
                low_price=Decimal("179.5000"),
                close_price=Decimal("180.5000"),
                volume=1000000,
                bar_size=bar_size_map.get(timeframe, "1min"),
            )
        
        # Aggregate from available bars
        last_bar = recent_bars[-1]
        
        if len(recent_bars) >= 1:
            open_price = recent_bars[0].open_price
            close_price = last_bar.close_price
            high_price = max(bar.high_price for bar in recent_bars)
            low_price = min(bar.low_price for bar in recent_bars)
            volume = sum(bar.volume for bar in recent_bars)
            
            # Ensure OHLC relationships are valid
            high_price = max(high_price, open_price, close_price)
            low_price = min(low_price, open_price, close_price)
        else:
            open_price = last_bar.open_price
            high_price = last_bar.high_price
            low_price = last_bar.low_price
            close_price = last_bar.close_price
            volume = last_bar.volume
        
        return BarData(
            symbol=symbol,
            timestamp=timestamp,
            open_price=open_price.quantize(Decimal('0.0001')),
            high_price=high_price.quantize(Decimal('0.0001')),
            low_price=low_price.quantize(Decimal('0.0001')),
            close_price=close_price.quantize(Decimal('0.0001')),
            volume=volume,
            bar_size=bar_size_map.get(timeframe, "1min"),
        )
    
    def _get_next_close_time(self, timeframe: Timeframe, current_time: datetime) -> datetime:
        """Calculate next close time for timeframe."""
        if timeframe == Timeframe.ONE_MIN:
            return current_time + timedelta(minutes=1)
        elif timeframe == Timeframe.FIVE_MIN:
            return current_time + timedelta(minutes=5)
        elif timeframe == Timeframe.FIFTEEN_MIN:
            return current_time + timedelta(minutes=15)
        elif timeframe == Timeframe.THIRTY_MIN:
            return current_time + timedelta(minutes=30)
        elif timeframe == Timeframe.ONE_HOUR:
            return current_time + timedelta(hours=1)
        elif timeframe == Timeframe.FOUR_HOUR:
            return current_time + timedelta(hours=4)
        elif timeframe == Timeframe.ONE_DAY:
            return current_time + timedelta(days=1)
        
        return current_time + timedelta(minutes=1)
    
    def get_monitored(self) -> Dict[str, List[str]]:
        """Get currently monitored symbols and timeframes."""
        return {
            symbol: [tf.value for tf in timeframes]
            for symbol, timeframes in self.monitored_timeframes.items()
        }
    
    async def stop_monitoring(self, symbol: Optional[str] = None, timeframe: Optional[Timeframe] = None):
        """Stop monitoring symbol/timeframe."""
        if symbol and timeframe:
            if symbol in self.monitored_timeframes:
                self.monitored_timeframes[symbol].discard(timeframe)
                if not self.monitored_timeframes[symbol]:
                    del self.monitored_timeframes[symbol]
        elif symbol:
            if symbol in self.monitored_timeframes:
                del self.monitored_timeframes[symbol]
        else:
            self.monitored_timeframes.clear()
    
    def get_timing_stats(self) -> Dict:
        return self.timing_stats.copy()


@pytest.fixture
def multi_timeframe_detector():
    """Create multi-timeframe detector mock."""
    return MockMultiTimeframeDetector()


@pytest.fixture
def enhanced_multi_order_manager():
    """Create enhanced order manager for multi-timeframe testing."""
    manager = Mock()
    
    # Track orders by timeframe for analysis
    orders_by_timeframe = {}
    order_counter = 0
    
    async def mock_place_order(*args, **kwargs):
        nonlocal order_counter
        order_counter += 1
        
        # Extract timeframe info if available
        timeframe = kwargs.get("timeframe", "unknown")
        if timeframe not in orders_by_timeframe:
            orders_by_timeframe[timeframe] = []
        
        order_result = OrderResult(
            success=True,
            order_id=f"MTF_ORDER_{order_counter:06d}",
            trade_plan_id=kwargs.get("trade_plan_id", "multi_tf_plan"),
            order_status="Submitted",
            symbol=kwargs.get("symbol", "UNKNOWN"),
            side=kwargs.get("side", "BUY"),
            quantity=kwargs.get("quantity", 100),
            order_type="MKT",
            timestamp=datetime.now(UTC),
        )
        
        orders_by_timeframe[timeframe].append(order_result)
        return order_result
    
    manager.place_market_order = AsyncMock(side_effect=mock_place_order)
    manager.orders_by_timeframe = orders_by_timeframe
    
    return manager


@pytest.fixture
def multi_timeframe_setup(multi_timeframe_detector, enhanced_multi_order_manager):
    """Create complete multi-timeframe test setup."""
    registry = ExecutionFunctionRegistry()
    logger = ExecutionLogger(enable_file_logging=False)
    
    market_adapter = MarketDataExecutionAdapter(
        bar_close_detector=multi_timeframe_detector,
        function_registry=registry,
        execution_logger=logger,
    )
    
    order_adapter = ExecutionOrderAdapter(
        order_execution_manager=enhanced_multi_order_manager,
        default_risk_category=RiskCategory.NORMAL,
    )
    
    # Connect adapters
    market_adapter.add_signal_callback(order_adapter.handle_execution_signal)
    
    return {
        "registry": registry,
        "logger": logger,
        "detector": multi_timeframe_detector,
        "order_manager": enhanced_multi_order_manager,
        "market_adapter": market_adapter,
        "order_adapter": order_adapter,
    }


def create_timeframe_bar_sequence(
    symbol: str,
    start_time: datetime,
    duration_minutes: int,
    base_price: float,
    price_trend: float = 0.0
) -> List[BarData]:
    """Create sequence of 1-minute bars for timeframe testing."""
    bars = []
    current_price = Decimal(str(base_price))
    
    for i in range(duration_minutes):
        bar_time = start_time + timedelta(minutes=i)
        
        # Apply trend (rounded to 4 decimal places)
        price_change = Decimal(str(price_trend * i / duration_minutes)).quantize(Decimal('0.0001'))
        bar_close = (current_price + price_change).quantize(Decimal('0.0001'))
        
        bar = BarData(
            symbol=symbol,
            timestamp=bar_time,
            open_price=current_price.quantize(Decimal('0.0001')),
            high_price=(bar_close + Decimal("0.25")).quantize(Decimal('0.0001')),
            low_price=(current_price - Decimal("0.25")).quantize(Decimal('0.0001')),
            close_price=bar_close,
            volume=1000000 + (i * 10000),
            bar_size="1min",
        )
        
        bars.append(bar)
        current_price = bar_close
    
    return bars


class TestMultiTimeframeIntegration:
    """Test multi-timeframe execution scenarios."""

    @pytest.mark.asyncio
    async def test_simultaneous_timeframe_monitoring(self, multi_timeframe_setup):
        """Test monitoring same symbol across multiple timeframes."""
        setup = multi_timeframe_setup
        
        # Register functions
        await setup["registry"].register("close_above", CloseAboveFunction)
        await setup["registry"].register("close_below", CloseBelowFunction)
        
        # Create functions for different timeframes
        timeframe_configs = [
            (Timeframe.ONE_MIN, "close_above", 180.00),
            (Timeframe.FIVE_MIN, "close_above", 179.50),
            (Timeframe.FIFTEEN_MIN, "close_below", 181.50),
            (Timeframe.ONE_HOUR, "close_above", 178.00),
        ]
        
        created_functions = []
        for timeframe, func_type, threshold in timeframe_configs:
            config = ExecutionFunctionConfig(
                name=f"aapl_{timeframe.value}_{func_type}",
                function_type=func_type,
                timeframe=timeframe,
                parameters={"threshold_price": threshold},
                enabled=True,
            )
            
            function = await setup["registry"].create_function(config)
            assert function is not None
            created_functions.append((timeframe, function))
            
            # Start monitoring for each timeframe
            await setup["market_adapter"].start_monitoring("AAPL", timeframe)
        
        # Verify all timeframes are monitored
        monitored = setup["detector"].get_monitored()
        assert "AAPL" in monitored
        assert len(monitored["AAPL"]) == len(timeframe_configs)
        
        # Debug: Print monitored timeframes
        print(f"Monitored timeframes for AAPL: {monitored['AAPL']}")
        
        # Feed data that spans multiple timeframes
        # Use a past timestamp to avoid "future data" validation errors
        start_time = (datetime.now(UTC) - timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)
        bars = create_timeframe_bar_sequence(
            symbol="AAPL",
            start_time=start_time,
            duration_minutes=75,  # 1 hour and 15 minutes
            base_price=179.0,
            price_trend=2.0  # Upward trend
        )
        
        # Process all bars - the mock detector will automatically trigger multi-timeframe closes
        for i, bar in enumerate(bars):
            await setup["market_adapter"].on_market_data_update(bar)
            
            # Debug: Log what timeframes would trigger on this minute
            minute = bar.timestamp.minute
            hour = bar.timestamp.hour
            if i < 10 or minute % 5 == 0 or minute % 15 == 0 or minute == 59:  # Log some key moments
                print(f"Bar {i}: {bar.timestamp} (minute={minute}, hour={hour})")
                print(f"  - 5min would trigger: {minute % 5 == 4 or minute % 5 == 0}")
                print(f"  - 15min would trigger: {minute % 15 == 14 or minute % 15 == 0}")
                print(f"  - 1hour would trigger: {minute == 59 or minute == 0}")
        
        # Allow time for bar close events to process
        await asyncio.sleep(0.1)
        
        # Verify function evaluations occurred across timeframes
        logs = await setup["logger"].query_logs(limit=200)
        
        # Check that different timeframes were evaluated by looking at log entries
        timeframe_evaluations = {}
        for log in logs:
            # Match log entries to functions by name and timeframe
            for tf, function in created_functions:
                function_name = function.config.name
                if log.function_name == function_name:
                    tf_name = tf.value
                    if tf_name not in timeframe_evaluations:
                        timeframe_evaluations[tf_name] = 0
                    timeframe_evaluations[tf_name] += 1
        
        # Should have evaluations for multiple timeframes
        assert len(timeframe_evaluations) >= 2, f"Expected multiple timeframes, got: {timeframe_evaluations}"

    @pytest.mark.asyncio
    async def test_timeframe_synchronization(self, multi_timeframe_setup):
        """Test proper synchronization between different timeframes."""
        setup = multi_timeframe_setup
        
        await setup["registry"].register("close_above", CloseAboveFunction)
        
        # Create functions with different timeframes but same threshold
        threshold = 180.00
        timeframes = [Timeframe.ONE_MIN, Timeframe.FIVE_MIN, Timeframe.FIFTEEN_MIN]
        
        for tf in timeframes:
            config = ExecutionFunctionConfig(
                name=f"sync_test_{tf.value}",
                function_type="close_above",
                timeframe=tf,
                parameters={"threshold_price": threshold},
                enabled=True,
            )
            
            await setup["registry"].create_function(config)
            await setup["market_adapter"].start_monitoring("AAPL", tf)
        
        # Create data that should trigger at specific timeframe boundaries
        start_time = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        
        # Feed 20 minutes of data with price crossing threshold at minute 15
        bars = []
        for i in range(20):
            bar_time = start_time + timedelta(minutes=i)
            
            # Price crosses threshold at minute 15
            if i < 15:
                close_price = Decimal("179.50")
            else:
                close_price = Decimal("180.50")  # Above threshold
            
            bar = BarData(
                symbol="AAPL",
                timestamp=bar_time,
                open_price=close_price,
                high_price=close_price + Decimal("0.25"),
                low_price=close_price - Decimal("0.25"),
                close_price=close_price,
                volume=1000000,
                bar_size="1min",
            )
            
            bars.append(bar)
        
        # Process all bars
        for bar in bars:
            await setup["market_adapter"].on_market_data_update(bar)
        
        # Allow processing time
        await asyncio.sleep(0.2)
        
        # Verify synchronization: 15-minute timeframe should trigger at minute 15
        logs = await setup["logger"].query_logs(limit=100)
        
        # Look for 15-minute evaluation at the right time
        fifteen_min_logs = [log for log in logs if "15min" in str(log)]
        assert len(fifteen_min_logs) >= 1, "15-minute timeframe should have been evaluated"
        
        # Verify timing accuracy - logs should contain timestamp information
        metrics = await setup["logger"].get_metrics()
        assert "total_evaluations" in metrics
        assert metrics["total_evaluations"] > 0

    @pytest.mark.asyncio
    async def test_cross_timeframe_signal_correlation(self, multi_timeframe_setup):
        """Test correlation of signals across different timeframes."""
        setup = multi_timeframe_setup
        
        await setup["registry"].register("close_above", CloseAboveFunction)
        
        # Create functions with progressive thresholds
        configs = [
            (Timeframe.ONE_MIN, 180.00, "short_term"),
            (Timeframe.FIVE_MIN, 179.75, "medium_term"),
            (Timeframe.FIFTEEN_MIN, 179.50, "long_term"),
        ]
        
        for timeframe, threshold, name in configs:
            config = ExecutionFunctionConfig(
                name=f"correlation_{name}",
                function_type="close_above",
                timeframe=timeframe,
                parameters={"threshold_price": threshold},
                enabled=True,
            )
            
            await setup["registry"].create_function(config)
            await setup["market_adapter"].start_monitoring("AAPL", timeframe)
        
        # Create scenario where all timeframes should trigger
        start_time = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        
        # Build up to strong breakout
        bars = []
        for i in range(30):
            bar_time = start_time + timedelta(minutes=i)
            
            if i < 20:
                # Gradual buildup
                close_price = Decimal("179.00") + Decimal(str(i * 0.02))
            else:
                # Strong breakout above all thresholds
                close_price = Decimal("180.50")
            
            bar = BarData(
                symbol="AAPL",
                timestamp=bar_time,
                open_price=close_price - Decimal("0.10"),
                high_price=close_price + Decimal("0.15"),
                low_price=close_price - Decimal("0.20"),
                close_price=close_price,
                volume=1000000 + (i * 50000),
                bar_size="1min",
            )
            
            bars.append(bar)
        
        # Process all data
        for bar in bars:
            await setup["market_adapter"].on_market_data_update(bar)
        
        # Allow processing time
        await asyncio.sleep(0.3)
        
        # Analyze signal correlation
        logs = await setup["logger"].query_logs(limit=150)
        
        # Count signals by timeframe
        signal_counts = {}
        for log in logs:
            log_str = str(log)
            if "signal" in log_str.lower() or "trigger" in log_str.lower():
                for tf_name in ["1min", "5min", "15min"]:
                    if tf_name in log_str:
                        signal_counts[tf_name] = signal_counts.get(tf_name, 0) + 1
        
        # Expect signals from multiple timeframes due to strong breakout
        assert len(signal_counts) >= 2, f"Expected correlated signals, got: {signal_counts}"

    @pytest.mark.asyncio
    async def test_multi_timeframe_performance(self, multi_timeframe_setup):
        """Test performance under multi-timeframe load."""
        setup = multi_timeframe_setup
        
        await setup["registry"].register("close_above", CloseAboveFunction)
        await setup["registry"].register("close_below", CloseBelowFunction)
        
        # Create many functions across different timeframes
        num_functions_per_tf = 3
        timeframes = [Timeframe.ONE_MIN, Timeframe.FIVE_MIN, Timeframe.FIFTEEN_MIN, Timeframe.ONE_HOUR]
        
        total_functions = 0
        for tf in timeframes:
            for i in range(num_functions_per_tf):
                config = ExecutionFunctionConfig(
                    name=f"perf_test_{tf.value}_{i}",
                    function_type="close_above" if i % 2 == 0 else "close_below",
                    timeframe=tf,
                    parameters={"threshold_price": 180.00 + i},
                    enabled=True,
                )
                
                function = await setup["registry"].create_function(config)
                if function:
                    total_functions += 1
                
                await setup["market_adapter"].start_monitoring("AAPL", tf)
        
        # Generate substantial data load
        start_time = datetime.now()
        
        bars = create_timeframe_bar_sequence(
            symbol="AAPL",
            start_time=datetime.now(UTC),
            duration_minutes=120,  # 2 hours of data
            base_price=179.0,
            price_trend=3.0
        )
        
        # Process data and measure performance
        processing_start = datetime.now()
        
        for bar in bars:
            await setup["market_adapter"].on_market_data_update(bar)
        
        # Allow all processing to complete
        await asyncio.sleep(0.5)
        
        processing_time = (datetime.now() - processing_start).total_seconds()
        
        # Performance assertions
        bars_per_second = len(bars) / processing_time if processing_time > 0 else float('inf')
        assert bars_per_second > 50, f"Processing rate too slow: {bars_per_second} bars/sec"
        
        # Verify all timeframes were handled
        timing_stats = setup["detector"].get_timing_stats()
        assert timing_stats["total_detections"] > 0
        
        # Check metrics for performance indicators
        metrics = await setup["logger"].get_metrics()
        if "avg_evaluation_time_ms" in metrics:
            assert metrics["avg_evaluation_time_ms"] < 100.0, "Function evaluation too slow"

    @pytest.mark.asyncio
    async def test_timeframe_aggregation_accuracy(self, multi_timeframe_setup):
        """Test accuracy of bar aggregation across timeframes."""
        setup = multi_timeframe_setup
        
        await setup["registry"].register("close_above", CloseAboveFunction)
        
        # Create function that tracks aggregated data
        config = ExecutionFunctionConfig(
            name="aggregation_test",
            function_type="close_above",
            timeframe=Timeframe.FIVE_MIN,
            parameters={"threshold_price": 180.00},
            enabled=True,
        )
        
        await setup["registry"].create_function(config)
        await setup["market_adapter"].start_monitoring("AAPL", Timeframe.FIVE_MIN)
        
        # Create precise 1-minute data for 5-minute aggregation
        start_time = datetime.now(UTC).replace(minute=0, second=0, microsecond=0)
        
        # Create 25 bars to ensure we have enough historical data for evaluation
        minute_bars = []
        prices = ([179.00] * 15) + [179.00, 179.25, 179.50, 179.75, 180.00,  # First 5-min period
                 180.25, 180.50, 180.75, 181.00, 181.25]  # Second 5-min period
        
        for i, price in enumerate(prices):
            bar_time = start_time + timedelta(minutes=i)
            
            bar = BarData(
                symbol="AAPL",
                timestamp=bar_time,
                open_price=Decimal(str(price)) - Decimal("0.1000"),
                high_price=Decimal(str(price)) + Decimal("0.1500"),
                low_price=Decimal(str(price)) - Decimal("0.2000"),
                close_price=Decimal(str(price)),
                volume=100000,
                bar_size="1min",
            )
            
            minute_bars.append(bar)
        
        # Process bars one by one
        for bar in minute_bars:
            await setup["market_adapter"].on_market_data_update(bar)
        
        # Allow processing time
        await asyncio.sleep(0.2)
        
        # Verify aggregation occurred
        detector_data = setup["detector"].bar_data
        assert "AAPL" in detector_data
        
        # Check that we have data for the 5-minute timeframe
        if Timeframe.FIVE_MIN in detector_data["AAPL"]:
            five_min_bars = detector_data["AAPL"][Timeframe.FIVE_MIN]
            assert len(five_min_bars) >= 5  # Should have multiple bars stored
        
        # Verify function evaluation occurred
        logs = await setup["logger"].query_logs(limit=50)
        evaluation_logs = [log for log in logs if "aggregation_test" in str(log)]
        assert len(evaluation_logs) > 0, "5-minute function should have been evaluated"

    @pytest.mark.asyncio
    async def test_multi_symbol_multi_timeframe(self, multi_timeframe_setup):
        """Test multiple symbols each with multiple timeframes."""
        setup = multi_timeframe_setup
        
        await setup["registry"].register("close_above", CloseAboveFunction)
        
        # Configure multiple symbols with different timeframes
        symbol_configs = [
            ("AAPL", [Timeframe.ONE_MIN, Timeframe.FIVE_MIN], 180.00),
            ("GOOGL", [Timeframe.FIVE_MIN, Timeframe.FIFTEEN_MIN], 2800.00),
            ("MSFT", [Timeframe.ONE_MIN, Timeframe.FIFTEEN_MIN], 420.00),
        ]
        
        created_configs = []
        for symbol, timeframes, threshold in symbol_configs:
            for tf in timeframes:
                config = ExecutionFunctionConfig(
                    name=f"{symbol.lower()}_{tf.value}_test",
                    function_type="close_above",
                    timeframe=tf,
                    parameters={"threshold_price": threshold},
                    enabled=True,
                )
                
                function = await setup["registry"].create_function(config)
                assert function is not None
                created_configs.append((symbol, tf, config))
                
                await setup["market_adapter"].start_monitoring(symbol, tf)
        
        # Generate data for all symbols
        symbol_prices = {"AAPL": 179.0, "GOOGL": 2795.0, "MSFT": 415.0}
        
        # Use past timestamp to avoid future data validation errors
        start_time = (datetime.now(UTC) - timedelta(hours=2)).replace(minute=0, second=0, microsecond=0)
        
        for symbol, base_price in symbol_prices.items():
            bars = create_timeframe_bar_sequence(
                symbol=symbol,
                start_time=start_time,
                duration_minutes=20,
                base_price=base_price,
                price_trend=5.0  # Strong uptrend to trigger signals
            )
            
            for bar in bars:
                await setup["market_adapter"].on_market_data_update(bar)
        
        # Allow processing
        await asyncio.sleep(0.3)
        
        # Verify monitoring across all combinations
        monitored = setup["detector"].get_monitored()
        
        for symbol, _, _ in created_configs:
            assert symbol in monitored, f"Symbol {symbol} should be monitored"
        
        # Verify logs contain entries for multiple symbols and timeframes
        logs = await setup["logger"].query_logs(limit=200)
        
        symbols_in_logs = set()
        timeframes_in_logs = set()
        
        for log in logs:
            log_str = str(log)
            for symbol in ["AAPL", "GOOGL", "MSFT"]:
                if symbol in log_str:
                    symbols_in_logs.add(symbol)
            
            for tf in ["1min", "5min", "15min"]:
                if tf in log_str:
                    timeframes_in_logs.add(tf)
        
        # Should have processed multiple symbols and timeframes
        assert len(symbols_in_logs) >= 2, f"Expected multiple symbols in logs, got: {symbols_in_logs}"
        assert len(timeframes_in_logs) >= 2, f"Expected multiple timeframes in logs, got: {timeframes_in_logs}"

    @pytest.mark.asyncio
    async def test_timeframe_cleanup_on_stop(self, multi_timeframe_setup):
        """Test proper cleanup when stopping multi-timeframe monitoring."""
        setup = multi_timeframe_setup
        
        await setup["registry"].register("close_above", CloseAboveFunction)
        
        # Start monitoring multiple timeframes
        timeframes = [Timeframe.ONE_MIN, Timeframe.FIVE_MIN, Timeframe.FIFTEEN_MIN]
        
        for tf in timeframes:
            config = ExecutionFunctionConfig(
                name=f"cleanup_test_{tf.value}",
                function_type="close_above",
                timeframe=tf,
                parameters={"threshold_price": 180.00},
                enabled=True,
            )
            
            await setup["registry"].create_function(config)
            await setup["market_adapter"].start_monitoring("AAPL", tf)
        
        # Verify all are monitored
        monitored = setup["detector"].get_monitored()
        assert "AAPL" in monitored
        assert len(monitored["AAPL"]) == len(timeframes)
        
        # Stop monitoring one timeframe
        await setup["market_adapter"].stop_monitoring("AAPL", Timeframe.FIVE_MIN)
        
        # Verify partial cleanup
        monitored_after_partial = setup["detector"].get_monitored()
        if "AAPL" in monitored_after_partial:
            assert "5min" not in monitored_after_partial["AAPL"]
            assert len(monitored_after_partial["AAPL"]) == len(timeframes) - 1
        
        # Stop all monitoring for symbol
        await setup["market_adapter"].stop_monitoring("AAPL")
        
        # Verify complete cleanup
        monitored_after_full = setup["detector"].get_monitored()
        assert "AAPL" not in monitored_after_full or len(monitored_after_full.get("AAPL", [])) == 0