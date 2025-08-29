"""End-to-end integration tests for execution function framework."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, UTC, timedelta
from decimal import Decimal

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
from auto_trader.trade_engine.functions import CloseAboveFunction


@pytest.fixture
async def registry():
    """Create function registry."""
    registry = ExecutionFunctionRegistry()
    await registry.clear_all()  # Start fresh
    return registry


@pytest.fixture
def execution_logger():
    """Create execution logger."""
    return ExecutionLogger(enable_file_logging=False)


@pytest.fixture
def mock_bar_close_detector():
    """Create mock bar close detector."""
    detector = Mock(spec=BarCloseDetector)
    detector.add_callback = Mock()
    detector.update_bar_data = Mock()
    detector.stop_monitoring = AsyncMock()
    detector.get_timing_stats = Mock(return_value={})
    
    # Track monitored symbols/timeframes
    monitored_data = {}
    
    async def mock_monitor_timeframe(symbol, timeframe):
        if symbol not in monitored_data:
            monitored_data[symbol] = []
        if timeframe.value not in monitored_data[symbol]:
            monitored_data[symbol].append(timeframe.value)
    
    def mock_get_monitored():
        return monitored_data.copy()
    
    detector.monitor_timeframe = AsyncMock(side_effect=mock_monitor_timeframe)
    detector.get_monitored = Mock(side_effect=mock_get_monitored)
    
    return detector


@pytest.fixture
def mock_order_manager():
    """Create mock order execution manager."""
    manager = Mock()
    manager.place_market_order = AsyncMock(return_value=OrderResult(
        success=True,
        order_id="TEST_ORDER_123",
        trade_plan_id="test_plan",
        order_status="Submitted",
        symbol="AAPL",
        side="BUY",
        quantity=100,
        order_type="MKT",
    ))
    return manager


@pytest.fixture
def market_data_adapter(mock_bar_close_detector, registry, execution_logger):
    """Create market data adapter."""
    return MarketDataExecutionAdapter(
        bar_close_detector=mock_bar_close_detector,
        function_registry=registry,
        execution_logger=execution_logger,
    )


@pytest.fixture
def order_adapter(mock_order_manager):
    """Create order adapter."""
    return ExecutionOrderAdapter(
        order_execution_manager=mock_order_manager,
        default_risk_category=RiskCategory.NORMAL,
    )


def create_sample_bar(symbol="AAPL", close_price=181.50, timestamp=None):
    """Create sample bar data."""
    return BarData(
        symbol=symbol,
        timestamp=timestamp or datetime.now(UTC),
        open_price=Decimal("180.00"),
        high_price=Decimal("182.00"),
        low_price=Decimal("179.50"),
        close_price=Decimal(str(close_price)),
        volume=1000000,
        bar_size="1min",
    )


class TestEndToEndIntegration:
    """Test end-to-end execution function workflow."""

    @pytest.mark.asyncio
    async def test_complete_execution_workflow(
        self,
        registry,
        market_data_adapter,
        order_adapter,
        execution_logger,
    ):
        """Test complete workflow from market data to order execution."""
        
        # Step 1: Register execution function
        await registry.register("close_above", CloseAboveFunction)
        
        config = ExecutionFunctionConfig(
            name="aapl_breakout",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 181.00},
            enabled=True,
        )
        
        function = await registry.create_function(config)
        assert function is not None
        
        # Step 2: Connect order adapter to market data adapter
        market_data_adapter.add_signal_callback(order_adapter.handle_execution_signal)
        
        # Step 3: Start monitoring
        await market_data_adapter.start_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Step 4: Feed historical data (20+ bars for minimum requirement)
        base_time = datetime.now(UTC) - timedelta(minutes=25)
        for i in range(25):
            bar_time = base_time + timedelta(minutes=i)
            bar = create_sample_bar(close_price=180.50, timestamp=bar_time)
            await market_data_adapter.on_market_data_update(bar)
        
        # Step 5: Feed triggering bar (above threshold)
        trigger_bar = create_sample_bar(close_price=181.25, timestamp=datetime.now(UTC))
        await market_data_adapter.on_market_data_update(trigger_bar)
        
        # Step 6: Simulate bar close event
        bar_close_event = BarCloseEvent(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            close_time=datetime.now(UTC),
            bar_data=trigger_bar,
            next_close_time=datetime.now(UTC) + timedelta(minutes=1),
        )
        
        await market_data_adapter._on_bar_close(bar_close_event)
        
        # Verify order was placed
        order_adapter.order_execution_manager.place_market_order.assert_called_once()
        
        # Verify execution was logged
        logs = await execution_logger.query_logs(limit=10)
        assert len(logs) > 0
        
        # Verify order tracking
        execution_orders = order_adapter.get_execution_orders()
        assert len(execution_orders) > 0

    @pytest.mark.asyncio
    async def test_multiple_functions_same_symbol(
        self,
        registry,
        market_data_adapter,
        order_adapter,
    ):
        """Test multiple functions monitoring same symbol."""
        
        # Register multiple functions
        await registry.register("close_above", CloseAboveFunction)
        
        # Create two functions with different thresholds
        config1 = ExecutionFunctionConfig(
            name="aapl_break_181",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 181.00},
        )
        
        config2 = ExecutionFunctionConfig(
            name="aapl_break_182",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 182.00},
        )
        
        function1 = await registry.create_function(config1)
        function2 = await registry.create_function(config2)
        
        assert function1 is not None
        assert function2 is not None
        
        # Connect adapters
        market_data_adapter.add_signal_callback(order_adapter.handle_execution_signal)
        
        # Start monitoring
        await market_data_adapter.start_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Feed historical data
        base_time = datetime.now(UTC) - timedelta(minutes=25)
        for i in range(25):
            bar_time = base_time + timedelta(minutes=i)
            bar = create_sample_bar(close_price=180.50, timestamp=bar_time)
            await market_data_adapter.on_market_data_update(bar)
        
        # Feed bar that triggers first function but not second
        trigger_bar = create_sample_bar(close_price=181.25, timestamp=datetime.now(UTC))
        await market_data_adapter.on_market_data_update(trigger_bar)
        
        # Simulate bar close
        bar_close_event = BarCloseEvent(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            close_time=datetime.now(UTC),
            bar_data=trigger_bar,
            next_close_time=datetime.now(UTC) + timedelta(minutes=1),
        )
        
        await market_data_adapter._on_bar_close(bar_close_event)
        
        # Only one order should be placed (first function triggered)
        assert order_adapter.order_execution_manager.place_market_order.call_count == 1

    @pytest.mark.asyncio
    async def test_insufficient_historical_data(
        self,
        registry,
        market_data_adapter,
        order_adapter,
    ):
        """Test handling of insufficient historical data."""
        
        # Register function
        await registry.register("close_above", CloseAboveFunction)
        
        config = ExecutionFunctionConfig(
            name="aapl_breakout",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 181.00},
        )
        
        await registry.create_function(config)
        market_data_adapter.add_signal_callback(order_adapter.handle_execution_signal)
        
        # Start monitoring
        await market_data_adapter.start_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Feed insufficient historical data (less than minimum required)
        for i in range(5):  # Only 5 bars, need 20
            bar = create_sample_bar(close_price=180.50)
            await market_data_adapter.on_market_data_update(bar)
        
        # Feed triggering bar
        trigger_bar = create_sample_bar(close_price=181.25)
        await market_data_adapter.on_market_data_update(trigger_bar)
        
        # Simulate bar close
        bar_close_event = BarCloseEvent(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            close_time=datetime.now(UTC),
            bar_data=trigger_bar,
            next_close_time=datetime.now(UTC) + timedelta(minutes=1),
        )
        
        await market_data_adapter._on_bar_close(bar_close_event)
        
        # No order should be placed due to insufficient data
        order_adapter.order_execution_manager.place_market_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_function_error_handling(
        self,
        registry,
        market_data_adapter,
        order_adapter,
        execution_logger,
    ):
        """Test error handling when function evaluation fails."""
        
        # Create mock function that raises exception
        mock_function = Mock()
        mock_function.name = "failing_function"
        mock_function.evaluate = AsyncMock(side_effect=ValueError("Test error"))
        
        # Store original method for restoration
        original_get_functions = registry.get_functions_by_timeframe
        
        try:
            # Mock registry to return failing function
            registry.get_functions_by_timeframe = Mock(return_value=[mock_function])
            
            market_data_adapter.add_signal_callback(order_adapter.handle_execution_signal)
            
            # Start monitoring and feed data
            await market_data_adapter.start_monitoring("AAPL", Timeframe.ONE_MIN)
            
            # Feed sufficient historical data
            for i in range(25):
                bar = create_sample_bar(close_price=180.50)
                await market_data_adapter.on_market_data_update(bar)
            
            # Simulate bar close
            trigger_bar = create_sample_bar(close_price=181.25)
            bar_close_event = BarCloseEvent(
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                close_time=datetime.now(UTC),
                bar_data=trigger_bar,
                next_close_time=datetime.now(UTC) + timedelta(minutes=1),
            )
            
            # Should not crash on error
            await market_data_adapter._on_bar_close(bar_close_event)
            
            # Error should be logged
            logs = await execution_logger.query_logs({"has_error": True})
            assert len(logs) > 0
            
            # No order should be placed
            order_adapter.order_execution_manager.place_market_order.assert_not_called()
            
        finally:
            # Always restore original method to prevent test pollution
            registry.get_functions_by_timeframe = original_get_functions

    @pytest.mark.asyncio
    async def test_signal_callback_error_handling(
        self,
        registry,
        market_data_adapter,
        execution_logger,
    ):
        """Test error handling in signal callbacks."""
        
        # Register function
        await registry.register("close_above", CloseAboveFunction)
        
        config = ExecutionFunctionConfig(
            name="aapl_breakout",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 181.00},
        )
        
        await registry.create_function(config)
        
        # Add callback that raises exception
        error_callback = AsyncMock(side_effect=Exception("Callback error"))
        market_data_adapter.add_signal_callback(error_callback)
        
        # Start monitoring and feed data
        await market_data_adapter.start_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Feed sufficient data (below threshold)
        for i in range(25):
            bar = create_sample_bar(close_price=180.50)
            await market_data_adapter.on_market_data_update(bar)
        
        # Trigger signal (above threshold of 181.00)
        trigger_bar = create_sample_bar(close_price=181.25)
        await market_data_adapter.on_market_data_update(trigger_bar)
        
        bar_close_event = BarCloseEvent(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            close_time=datetime.now(UTC),
            bar_data=trigger_bar,
            next_close_time=datetime.now(UTC) + timedelta(minutes=1),
        )
        
        # Should not crash even with callback error
        await market_data_adapter._on_bar_close(bar_close_event)
        
        # Function evaluation should still be logged
        logs = await execution_logger.query_logs({"function_name": "aapl_breakout"})
        assert len(logs) > 0

    @pytest.mark.asyncio
    async def test_adapter_statistics_integration(
        self,
        market_data_adapter,
        order_adapter,
        execution_logger,
    ):
        """Test statistics collection across integrated components."""
        
        # Add some data to each component
        bar = create_sample_bar()
        await market_data_adapter.on_market_data_update(bar)
        
        order_adapter.execution_orders["test_id"] = "order_123"
        
        # Get statistics from each component
        market_stats = await market_data_adapter.get_stats()
        order_stats = order_adapter.get_stats()
        logger_stats = await execution_logger.get_metrics()
        
        # Verify statistics are collected
        assert market_stats["monitored_symbols"] > 0
        assert order_stats["tracked_orders"] > 0
        assert "total_evaluations" in logger_stats

    @pytest.mark.asyncio
    async def test_monitoring_lifecycle(
        self,
        market_data_adapter,
        registry,
    ):
        """Test complete monitoring lifecycle."""
        
        # Register function
        await registry.register("close_above", CloseAboveFunction)
        config = ExecutionFunctionConfig(
            name="test_function",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 181.00},
        )
        await registry.create_function(config)
        
        # Start monitoring
        await market_data_adapter.start_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Verify monitoring is active
        monitored = market_data_adapter.get_active_monitoring()
        assert "AAPL" in monitored
        
        # Add market data
        bar = create_sample_bar()
        await market_data_adapter.on_market_data_update(bar)
        
        # Verify data is stored
        assert "AAPL" in market_data_adapter.historical_data
        
        # Stop monitoring
        await market_data_adapter.stop_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Verify cleanup
        assert "AAPL" not in market_data_adapter.historical_data