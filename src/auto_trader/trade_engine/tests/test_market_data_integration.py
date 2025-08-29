"""Integration tests between execution function framework and market data system."""

import pytest
import asyncio
from datetime import datetime, UTC, timedelta
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch

from auto_trader.models.execution import (
    ExecutionContext,
    ExecutionSignal,
    ExecutionFunctionConfig,
    BarCloseEvent,
)
from auto_trader.models.enums import ExecutionAction, Timeframe
from auto_trader.models.market_data import BarData
from auto_trader.trade_engine.execution_functions import ExecutionFunctionBase
from auto_trader.trade_engine.function_registry import ExecutionFunctionRegistry
from auto_trader.trade_engine.bar_close_detector import BarCloseDetector
from auto_trader.trade_engine.functions import CloseAboveFunction


@pytest.fixture
def mock_market_data_cache():
    """Create mock market data cache."""
    cache = Mock()
    cache.get_latest_bar = Mock()
    cache.get_historical_bars = Mock()
    cache.is_stale = Mock(return_value=False)
    return cache


@pytest.fixture
def sample_bar_data():
    """Create sample bar data for testing."""
    return BarData(
        symbol="AAPL",
        timestamp=datetime.now(UTC),
        open_price=Decimal("180.00"),
        high_price=Decimal("182.00"),
        low_price=Decimal("179.50"),
        close_price=Decimal("181.50"),
        volume=1000000,
        bar_size="1min",
    )


@pytest.fixture
def historical_bars():
    """Create historical bar data."""
    bars = []
    base_time = datetime.now(UTC) - timedelta(minutes=20)
    
    for i in range(20):
        # Use proper decimal formatting to avoid precision issues
        price_adjustment = round(i * 0.1, 2)
        bar = BarData(
            symbol="AAPL",
            timestamp=base_time + timedelta(minutes=i),
            open_price=Decimal("179.00") + Decimal(str(price_adjustment)),
            high_price=Decimal("180.00") + Decimal(str(price_adjustment)),
            low_price=Decimal("178.50") + Decimal(str(price_adjustment)),
            close_price=Decimal("179.50") + Decimal(str(price_adjustment)),
            volume=1000000 + (i * 10000),
            bar_size="1min",
        )
        bars.append(bar)
    
    return bars


@pytest.fixture
async def execution_system():
    """Create integrated execution system components."""
    registry = ExecutionFunctionRegistry()
    await registry.clear_all()  # Clean state
    
    # Register close above function
    await registry.register("close_above", CloseAboveFunction)
    
    # Create function instance
    config = ExecutionFunctionConfig(
        name="test_close_above",
        function_type="close_above",
        timeframe=Timeframe.ONE_MIN,
        parameters={"threshold_price": 181.00},
        enabled=True
    )
    function = await registry.create_function(config)
    
    # Create bar close detector
    detector = BarCloseDetector(accuracy_ms=100)
    await detector.start()
    
    yield {
        "registry": registry,
        "function": function,
        "detector": detector,
        "config": config
    }
    
    await detector.stop()
    await registry.clear_all()


@pytest.mark.asyncio
class TestMarketDataIntegration:
    """Test integration between execution functions and market data system."""

    async def test_market_data_bar_to_execution_context(
        self, sample_bar_data, historical_bars, mock_market_data_cache
    ):
        """Test conversion from market data to execution context."""
        # Setup market data cache
        mock_market_data_cache.get_latest_bar.return_value = sample_bar_data
        mock_market_data_cache.get_historical_bars.return_value = historical_bars
        
        # Create execution context from market data
        context = ExecutionContext(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            current_bar=sample_bar_data,
            historical_bars=historical_bars,
            trade_plan_params={"threshold_price": 181.00},
            position_state=None,
            account_balance=Decimal("10000"),
            timestamp=datetime.now(UTC)
        )
        
        # Verify context properly represents market data
        assert context.current_bar.symbol == sample_bar_data.symbol
        assert context.current_bar.close_price == sample_bar_data.close_price
        assert len(context.historical_bars) == 20
        assert context.symbol == "AAPL"
        assert context.timeframe == Timeframe.ONE_MIN

    async def test_bar_close_event_to_function_execution(
        self, execution_system, sample_bar_data, historical_bars
    ):
        """Test complete flow from bar close event to function execution."""
        function = execution_system["function"]
        detector = execution_system["detector"]
        
        # Set threshold below current close price to trigger signal
        function.parameters["threshold_price"] = 180.00
        
        # Create execution context
        context = ExecutionContext(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            current_bar=sample_bar_data,  # Close price is 181.50
            historical_bars=historical_bars,
            trade_plan_params=function.parameters,
            position_state=None,
            account_balance=Decimal("10000"),
            timestamp=datetime.now(UTC)
        )
        
        # Execute function
        signal = await function.evaluate(context)
        
        # Verify function triggered correctly based on market data
        assert signal.action == ExecutionAction.ENTER_LONG
        assert signal.confidence > 0.5
        assert "181.50" in signal.reasoning  # Should reference actual close price

    async def test_stale_data_handling(
        self, execution_system, mock_market_data_cache
    ):
        """Test handling of stale market data."""
        function = execution_system["function"]
        
        # Create stale bar data (old timestamp)
        stale_bar = BarData(
            symbol="AAPL",
            timestamp=datetime.now(UTC) - timedelta(hours=1),
            open_price=Decimal("180.00"),
            high_price=Decimal("182.00"),
            low_price=Decimal("179.50"),
            close_price=Decimal("181.50"),
            volume=1000000,
            bar_size="1min",
        )
        
        # Setup mock to indicate stale data
        mock_market_data_cache.is_stale.return_value = True
        
        # Create context with stale data
        context = ExecutionContext(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            current_bar=stale_bar,
            historical_bars=[stale_bar] * 20,
            trade_plan_params={"threshold_price": 180.00},
            position_state=None,
            account_balance=Decimal("10000"),
            timestamp=datetime.now(UTC)
        )
        
        # Function should handle stale data gracefully
        signal = await function.evaluate(context)
        assert signal is not None  # Should not crash

    async def test_multiple_timeframe_integration(self, execution_system):
        """Test execution functions with multiple timeframes from market data."""
        registry = execution_system["registry"]
        detector = execution_system["detector"]
        
        # Clear any existing functions from fixture
        await registry.clear_all()
        await registry.register("close_above", CloseAboveFunction)
        
        # Create functions for multiple timeframes
        timeframes = [Timeframe.ONE_MIN, Timeframe.FIVE_MIN, Timeframe.FIFTEEN_MIN]
        functions = {}
        
        for tf in timeframes:
            config = ExecutionFunctionConfig(
                name=f"test_close_above_{tf.value}",
                function_type="close_above",
                timeframe=tf,
                parameters={"threshold_price": 180.00},
                enabled=True
            )
            functions[tf] = await registry.create_function(config)
            
            # Setup monitoring for each timeframe
            await detector.monitor_timeframe("AAPL", tf)
        
        # Verify all timeframes are monitored
        monitored = detector.get_monitored()
        assert "AAPL" in monitored
        assert all(tf.value in monitored["AAPL"] for tf in timeframes)
        
        # Verify functions exist for each timeframe
        for tf in timeframes:
            tf_functions = registry.get_functions_by_timeframe(tf.value)
            assert len(tf_functions) == 1
            assert tf_functions[0].timeframe == tf

    async def test_market_data_quality_validation(
        self, execution_system, historical_bars
    ):
        """Test execution functions handle poor quality market data."""
        function = execution_system["function"]
        
        # Create bar with zero volume (poor quality indicator)
        poor_quality_bar = BarData(
            symbol="AAPL",
            timestamp=datetime.now(UTC),
            open_price=Decimal("180.00"),
            high_price=Decimal("182.00"),
            low_price=Decimal("179.50"),
            close_price=Decimal("181.50"),
            volume=0,  # Zero volume indicates poor quality
            bar_size="1min",
        )
        
        # Set minimum volume requirement
        function.parameters["min_volume"] = 10000
        
        context = ExecutionContext(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            current_bar=poor_quality_bar,
            historical_bars=historical_bars,
            trade_plan_params=function.parameters,
            position_state=None,
            account_balance=Decimal("10000"),
            timestamp=datetime.now(UTC)
        )
        
        # Function should reject due to poor quality data
        signal = await function.evaluate(context)
        assert signal.action == ExecutionAction.NONE
        assert "volume" in signal.reasoning.lower()

    async def test_market_data_cache_integration(self, execution_system):
        """Test integration with market data cache system."""
        function = execution_system["function"]
        
        with patch('auto_trader.trade_engine.tests.test_market_data_integration.Mock') as mock_cache_class:
            cache_instance = Mock()
            mock_cache_class.return_value = cache_instance
            
            # Setup cache responses
            current_bar = BarData(
                symbol="AAPL",
                timestamp=datetime.now(UTC),
                open_price=Decimal("180.00"),
                high_price=Decimal("182.00"),
                low_price=Decimal("179.50"),
                close_price=Decimal("181.50"),
                volume=1000000,
                bar_size="1min",
            )
            
            cache_instance.get_latest_bar.return_value = current_bar
            cache_instance.get_historical_bars.return_value = [current_bar] * 20
            
            # Create context using cache data
            context = ExecutionContext(
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                current_bar=current_bar,
                historical_bars=[current_bar] * 20,
                trade_plan_params={"threshold_price": 180.00},
                position_state=None,
                account_balance=Decimal("10000"),
                timestamp=datetime.now(UTC)
            )
            
            # Execute function
            signal = await function.evaluate(context)
            
            # Verify cache integration worked
            assert signal is not None
            assert signal.action == ExecutionAction.ENTER_LONG  # Above threshold

    async def test_bar_close_timing_integration(self, execution_system, sample_bar_data):
        """Test precise timing integration between market data and execution."""
        detector = execution_system["detector"]
        function = execution_system["function"]
        
        # Mock callback to capture execution events
        execution_events = []
        
        async def execution_callback(event: BarCloseEvent):
            """Simulate execution function trigger on bar close."""
            context = ExecutionContext(
                symbol=event.symbol,
                timeframe=event.timeframe,
                current_bar=event.bar_data,
                historical_bars=[event.bar_data] * 20,
                trade_plan_params={"threshold_price": 180.00},
                position_state=None,
                account_balance=Decimal("10000"),
                timestamp=event.close_time
            )
            
            signal = await function.evaluate(context)
            execution_events.append({
                "event": event,
                "signal": signal,
                "execution_time": datetime.now(UTC)
            })
        
        # Register callback and setup monitoring
        detector.add_callback(execution_callback)
        await detector.monitor_timeframe("AAPL", Timeframe.ONE_MIN)
        detector.update_bar_data("AAPL", Timeframe.ONE_MIN, sample_bar_data)
        
        # Simulate bar close event
        close_event = BarCloseEvent(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            close_time=datetime.now(UTC),
            bar_data=sample_bar_data,
            next_close_time=datetime.now(UTC) + timedelta(minutes=1)
        )
        
        # Trigger event processing
        await detector._emit_event(close_event)
        
        # Verify execution occurred
        assert len(execution_events) == 1
        event_data = execution_events[0]
        assert event_data["signal"].action == ExecutionAction.ENTER_LONG
        
        # Verify timing (execution should happen quickly after bar close)
        timing_diff = (event_data["execution_time"] - close_event.close_time).total_seconds()
        assert timing_diff < 1.0  # Should execute within 1 second

    async def test_market_data_error_propagation(self, execution_system):
        """Test how market data errors propagate to execution functions."""
        function = execution_system["function"]
        
        # Test that invalid bar data creation raises validation error
        with pytest.raises(Exception):  # ValidationError from pydantic
            invalid_bar = BarData(
                symbol="AAPL",
                timestamp=datetime.now(UTC),
                open_price=Decimal("-180.00"),  # Invalid negative price
                high_price=Decimal("182.00"),
                low_price=Decimal("179.50"),
                close_price=Decimal("181.50"),
                volume=1000000,
                bar_size="1min",
            )

    async def test_real_time_data_flow_simulation(
        self, execution_system, historical_bars
    ):
        """Test simulated real-time data flow through execution system."""
        function = execution_system["function"]
        detector = execution_system["detector"]
        
        # Simulate real-time bar updates
        execution_results = []
        
        async def process_bar_update(bar_data):
            """Simulate processing a real-time bar update."""
            context = ExecutionContext(
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                current_bar=bar_data,
                historical_bars=historical_bars,
                trade_plan_params={"threshold_price": 181.00},
                position_state=None,
                account_balance=Decimal("10000"),
                timestamp=datetime.now(UTC)
            )
            
            signal = await function.evaluate(context)
            execution_results.append({
                "bar": bar_data,
                "signal": signal,
                "timestamp": datetime.now(UTC)
            })
        
        # Simulate sequence of bar updates with price progression
        base_time = datetime.now(UTC)
        prices = [180.00, 180.25, 180.75, 181.50]  # Price moves above threshold of 181.00 (from fixture)
        
        for i, price in enumerate(prices):
            bar = BarData(
                symbol="AAPL",
                timestamp=base_time + timedelta(minutes=i),
                open_price=Decimal(str(price - 0.25)),
                high_price=Decimal(str(price + 0.25)),
                low_price=Decimal(str(price - 0.50)),
                close_price=Decimal(str(price)),
                volume=1000000,
                bar_size="1min",
            )
            
            await process_bar_update(bar)
        
        # Verify execution behavior
        assert len(execution_results) == 4
        
        # First three bars should not trigger (below threshold)
        for i in range(3):
            assert execution_results[i]["signal"].action == ExecutionAction.NONE
        
        # Last bar should trigger (above threshold)
        assert execution_results[3]["signal"].action == ExecutionAction.ENTER_LONG

    async def test_concurrent_symbol_processing(self, execution_system):
        """Test concurrent processing of multiple symbols."""
        registry = execution_system["registry"]
        
        symbols = ["AAPL", "MSFT", "GOOGL"]
        functions = {}
        
        # Create function for each symbol
        for symbol in symbols:
            config = ExecutionFunctionConfig(
                name=f"test_{symbol}",
                function_type="close_above",
                timeframe=Timeframe.ONE_MIN,
                parameters={"threshold_price": 180.00},
                enabled=True
            )
            functions[symbol] = await registry.create_function(config)
        
        # Process bars concurrently
        async def process_symbol(symbol):
            bar = BarData(
                symbol=symbol,
                timestamp=datetime.now(UTC),
                open_price=Decimal("179.00"),
                high_price=Decimal("182.00"),
                low_price=Decimal("178.50"),
                close_price=Decimal("181.50"),
                volume=1000000,
                bar_size="1min",
            )
            
            context = ExecutionContext(
                symbol=symbol,
                timeframe=Timeframe.ONE_MIN,
                current_bar=bar,
                historical_bars=[bar] * 20,
                trade_plan_params={"threshold_price": 180.00},
                position_state=None,
                account_balance=Decimal("10000"),
                timestamp=datetime.now(UTC)
            )
            
            return await functions[symbol].evaluate(context)
        
        # Execute concurrently
        tasks = [process_symbol(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks)
        
        # All should trigger (price above threshold)
        for result in results:
            assert result.action == ExecutionAction.ENTER_LONG