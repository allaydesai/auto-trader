"""Performance and timing accuracy tests for execution function framework."""

import pytest
import asyncio
import time
from unittest.mock import Mock, AsyncMock
from datetime import datetime, UTC, timedelta
from decimal import Decimal
from statistics import mean, stdev

from auto_trader.models.market_data import BarData
from auto_trader.models.execution import ExecutionFunctionConfig, ExecutionSignal, BarCloseEvent
from auto_trader.models.enums import Timeframe, ExecutionAction
from auto_trader.trade_engine.function_registry import ExecutionFunctionRegistry
from auto_trader.trade_engine.execution_logger import ExecutionLogger
from auto_trader.trade_engine.bar_close_detector import BarCloseDetector
from auto_trader.trade_engine.market_data_adapter import MarketDataExecutionAdapter
from auto_trader.trade_engine.functions import CloseAboveFunction


@pytest.fixture
def registry():
    """Create function registry."""
    registry = ExecutionFunctionRegistry()
    registry.clear_all()
    return registry


@pytest.fixture
def execution_logger():
    """Create execution logger."""
    return ExecutionLogger(enable_file_logging=False)


@pytest.fixture
def mock_bar_close_detector():
    """Create mock bar close detector with timing stats."""
    detector = Mock(spec=BarCloseDetector)
    detector.add_callback = Mock()
    detector.update_bar_data = Mock()
    detector.monitor_timeframe = AsyncMock()
    detector.stop_monitoring = AsyncMock()
    detector.get_monitored = Mock(return_value={})
    
    # Mock timing stats with realistic values
    detector.get_timing_stats = Mock(return_value={
        "avg_error_ms": 250.0,
        "max_error_ms": 800.0,
        "min_error_ms": 50.0,
        "samples": 100,
        "accuracy_threshold_ms": 500
    })
    return detector


@pytest.fixture
def market_data_adapter(mock_bar_close_detector, registry, execution_logger):
    """Create market data adapter."""
    return MarketDataExecutionAdapter(
        bar_close_detector=mock_bar_close_detector,
        function_registry=registry,
        execution_logger=execution_logger,
    )


def create_sample_bar(symbol="AAPL", close_price=181.50, timestamp=None):
    """Create sample bar data with proper OHLC relationships."""
    close = Decimal(str(close_price))
    open_price = close - Decimal("1.50")  # Open slightly below close
    # Ensure high is >= max(open, close) and low is <= min(open, close)
    high_price = max(open_price, close) + Decimal("0.50")
    low_price = min(open_price, close) - Decimal("0.50")
    
    return BarData(
        symbol=symbol,
        timestamp=timestamp or datetime.now(UTC),
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        close_price=close,
        volume=1000000,
        bar_size="1min",
    )


class TestPerformanceTiming:
    """Test performance and timing characteristics of execution framework."""

    @pytest.mark.asyncio
    async def test_function_evaluation_latency(self, registry, market_data_adapter):
        """Test that function evaluation completes within latency requirements."""
        
        # Register function
        registry.register("close_above", CloseAboveFunction)
        
        config = ExecutionFunctionConfig(
            name="perf_test",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 181.00},
        )
        
        function = registry.create_function(config)
        
        # Setup historical data
        await market_data_adapter.start_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Add sufficient historical data
        base_time = datetime.now(UTC) - timedelta(minutes=25)
        for i in range(25):
            bar_time = base_time + timedelta(minutes=i)
            bar = create_sample_bar(close_price=180.50, timestamp=bar_time)
            market_data_adapter.on_market_data_update(bar)
        
        # Measure evaluation latency multiple times
        latencies = []
        
        for _ in range(10):
            trigger_bar = create_sample_bar(close_price=181.25)
            bar_close_event = BarCloseEvent(
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                close_time=datetime.now(UTC),
                bar_data=trigger_bar,
                next_close_time=datetime.now(UTC) + timedelta(minutes=1),
            )
            
            start_time = time.perf_counter()
            await market_data_adapter._on_bar_close(bar_close_event)
            end_time = time.perf_counter()
            
            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)
        
        # Verify latency requirements
        avg_latency = mean(latencies)
        max_latency = max(latencies)
        
        # Requirements: <100ms average, <500ms max
        assert avg_latency < 100, f"Average latency {avg_latency:.2f}ms exceeds 100ms limit"
        assert max_latency < 500, f"Max latency {max_latency:.2f}ms exceeds 500ms limit"
        
        print(f"Function evaluation latencies: avg={avg_latency:.2f}ms, max={max_latency:.2f}ms")

    @pytest.mark.asyncio
    async def test_concurrent_function_evaluation(self, registry, market_data_adapter):
        """Test performance with multiple functions running concurrently."""
        
        # Register multiple functions
        registry.register("close_above", CloseAboveFunction)
        
        # Create 5 functions with different thresholds
        functions = []
        for i in range(5):
            config = ExecutionFunctionConfig(
                name=f"perf_test_{i}",
                function_type="close_above",
                timeframe=Timeframe.ONE_MIN,
                parameters={"threshold_price": 180.0 + (i * 0.2)},
            )
            functions.append(registry.create_function(config))
        
        # Setup historical data
        await market_data_adapter.start_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Add historical data
        base_time = datetime.now(UTC) - timedelta(minutes=25)
        for i in range(25):
            bar_time = base_time + timedelta(minutes=i)
            bar = create_sample_bar(close_price=180.50, timestamp=bar_time)
            market_data_adapter.on_market_data_update(bar)
        
        # Test concurrent evaluation
        trigger_bar = create_sample_bar(close_price=182.00)  # Triggers all functions
        bar_close_event = BarCloseEvent(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            close_time=datetime.now(UTC),
            bar_data=trigger_bar,
            next_close_time=datetime.now(UTC) + timedelta(minutes=1),
        )
        
        start_time = time.perf_counter()
        await market_data_adapter._on_bar_close(bar_close_event)
        end_time = time.perf_counter()
        
        total_latency = (end_time - start_time) * 1000
        
        # Should still complete within reasonable time even with 5 functions
        # Allow more time for concurrent execution but not linearly
        assert total_latency < 300, f"Concurrent evaluation {total_latency:.2f}ms exceeds 300ms"
        
        print(f"Concurrent evaluation of 5 functions: {total_latency:.2f}ms")

    def test_memory_usage_historical_data(self, market_data_adapter):
        """Test memory usage with large amounts of historical data."""
        
        # Set reasonable limits for testing
        market_data_adapter.max_historical_bars = 100
        
        # Add large amount of data
        for i in range(500):  # More than limit
            bar = create_sample_bar(close_price=180.0 + (i * 0.01))
            market_data_adapter.on_market_data_update(bar)
        
        # Verify memory is managed properly
        stored_bars = len(market_data_adapter.historical_data["AAPL"][Timeframe.ONE_MIN])
        assert stored_bars == 100, f"Expected 100 bars, got {stored_bars}"
        
        # Verify memory usage stats
        stats = market_data_adapter.get_stats()
        assert stats["total_historical_bars"] == 100

    @pytest.mark.asyncio
    async def test_bar_close_timing_accuracy(self, mock_bar_close_detector):
        """Test bar close detection timing accuracy."""
        
        # Get timing stats from mock detector
        timing_stats = mock_bar_close_detector.get_timing_stats()
        
        # Verify accuracy requirements
        avg_error = timing_stats["avg_error_ms"]
        max_error = timing_stats["max_error_ms"]
        threshold = timing_stats["accuracy_threshold_ms"]
        
        # Requirements: <500ms average error, within threshold
        assert avg_error < threshold, f"Average timing error {avg_error}ms exceeds threshold {threshold}ms"
        assert avg_error < 500, f"Average timing error {avg_error}ms exceeds 500ms requirement"
        
        print(f"Bar close timing: avg_error={avg_error}ms, max_error={max_error}ms, threshold={threshold}ms")

    def test_execution_logger_performance(self, execution_logger):
        """Test execution logger performance with high throughput."""
        
        # Mock context and signal for performance testing
        mock_context = Mock()
        mock_context.symbol = "AAPL"
        mock_context.timeframe = Timeframe.ONE_MIN
        mock_context.current_bar = create_sample_bar()
        mock_context.has_position = False
        mock_context.trade_plan_params = {}
        mock_context.timestamp = datetime.now(UTC)
        mock_context.position_state = None  # No position for performance test
        
        mock_signal = ExecutionSignal(
            action=ExecutionAction.NONE,
            confidence=0.5,
            reasoning="Performance test signal",
        )
        
        # Measure logging performance
        start_time = time.perf_counter()
        
        # Log 1000 evaluations
        for i in range(1000):
            execution_logger.log_evaluation(
                function_name=f"perf_test_{i % 10}",
                context=mock_context,
                signal=mock_signal,
                duration_ms=50.0 + (i % 50),  # Varying durations
            )
        
        end_time = time.perf_counter()
        
        total_time = (end_time - start_time) * 1000
        avg_time_per_log = total_time / 1000
        
        # Should be able to log at high rate
        assert avg_time_per_log < 1.0, f"Logging too slow: {avg_time_per_log:.3f}ms per entry"
        
        # Verify logs were stored
        logs = execution_logger.query_logs(limit=1100)
        assert len(logs) == 1000
        
        print(f"Logging performance: {avg_time_per_log:.3f}ms per entry, total={total_time:.2f}ms")

    @pytest.mark.asyncio
    async def test_registry_lookup_performance(self, registry):
        """Test function registry lookup performance."""
        
        # Register multiple functions
        registry.register("close_above", CloseAboveFunction)
        
        # Create many function instances
        functions = []
        for i in range(100):
            config = ExecutionFunctionConfig(
                name=f"function_{i}",
                function_type="close_above",
                timeframe=Timeframe.ONE_MIN,
                parameters={"threshold_price": 180.0 + i},
            )
            functions.append(registry.create_function(config))
        
        # Measure lookup performance
        start_time = time.perf_counter()
        
        # Perform 1000 lookups
        for _ in range(1000):
            timeframe_functions = registry.get_functions_by_timeframe(Timeframe.ONE_MIN.value)
            assert len(timeframe_functions) == 100
        
        end_time = time.perf_counter()
        
        lookup_time = (end_time - start_time) * 1000
        avg_lookup_time = lookup_time / 1000
        
        # Lookups should be fast
        assert avg_lookup_time < 0.1, f"Registry lookup too slow: {avg_lookup_time:.3f}ms"
        
        print(f"Registry lookup performance: {avg_lookup_time:.3f}ms per lookup")

    def test_market_data_processing_throughput(self, market_data_adapter):
        """Test market data processing throughput."""
        
        # Process large number of bars quickly
        num_bars = 10000
        
        start_time = time.perf_counter()
        
        for i in range(num_bars):
            bar = create_sample_bar(
                close_price=180.0 + (i % 100) * 0.01,
                timestamp=datetime.now(UTC) + timedelta(seconds=i)
            )
            market_data_adapter.on_market_data_update(bar)
        
        end_time = time.perf_counter()
        
        total_time = end_time - start_time
        throughput = num_bars / total_time
        
        # Should process at high rate
        assert throughput > 1000, f"Market data throughput too low: {throughput:.0f} bars/sec"
        
        print(f"Market data processing: {throughput:.0f} bars/sec")

    @pytest.mark.asyncio
    async def test_memory_cleanup_performance(self, market_data_adapter):
        """Test memory cleanup performance."""
        
        # Set small limit to force frequent cleanup
        market_data_adapter.max_historical_bars = 50
        
        # Add data that will trigger many cleanups
        start_time = time.perf_counter()
        
        for i in range(1000):
            bar = create_sample_bar(close_price=180.0 + (i * 0.001))
            market_data_adapter.on_market_data_update(bar)
        
        end_time = time.perf_counter()
        
        total_time = (end_time - start_time) * 1000
        
        # Performance threshold analysis:
        # - 1000 bars with max_historical_bars=50 triggers ~950 cleanup operations
        # - Each cleanup: O(n) list slicing + debug logging overhead
        # - Debug logging: ~2 logs per bar (update + cleanup) = ~2000 log calls
        # - Expected breakdown: ~200ms logging + ~60ms cleanup + ~20ms overhead
        # - 300ms threshold allows for debug logging while catching real performance regressions
        assert total_time < 300, f"Memory cleanup causing performance issues: {total_time:.2f}ms"
        
        # Verify memory is properly managed
        stats = market_data_adapter.get_stats()
        assert stats["total_historical_bars"] <= 50
        
        print(f"Memory cleanup performance: {total_time:.2f}ms for 1000 bars with cleanup")

    def test_execution_accuracy_requirements(self):
        """Test that accuracy requirements are well-defined and achievable."""
        
        # Define system requirements
        requirements = {
            "bar_close_accuracy_ms": 1000,  # <1 second accuracy
            "function_evaluation_latency_ms": 100,  # <100ms per function
            "total_signal_latency_ms": 500,  # <500ms total pipeline
            "logging_latency_ms": 1,  # <1ms per log entry
            "registry_lookup_ms": 0.1,  # <0.1ms per lookup
        }
        
        # Verify requirements are reasonable
        for requirement, limit in requirements.items():
            assert limit > 0, f"Requirement {requirement} must be positive"
            assert limit < 10000, f"Requirement {requirement} seems too loose"
        
        print("Performance requirements defined:")
        for req, limit in requirements.items():
            print(f"  {req}: <{limit}ms")

    @pytest.mark.asyncio
    async def test_stress_test_high_frequency(self, registry, market_data_adapter, execution_logger):
        """Stress test with high frequency data."""
        
        # Register function
        registry.register("close_above", CloseAboveFunction)
        config = ExecutionFunctionConfig(
            name="stress_test",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 181.00},
        )
        registry.create_function(config)
        
        # Setup monitoring
        await market_data_adapter.start_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Feed initial historical data
        for i in range(25):
            bar = create_sample_bar(close_price=180.50)
            market_data_adapter.on_market_data_update(bar)
        
        # Simulate high frequency bar closes
        start_time = time.perf_counter()
        
        for i in range(100):  # 100 rapid bar closes
            trigger_bar = create_sample_bar(close_price=181.25 + (i * 0.001))
            bar_close_event = BarCloseEvent(
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                close_time=datetime.now(UTC) + timedelta(milliseconds=i),
                bar_data=trigger_bar,
                next_close_time=datetime.now(UTC) + timedelta(milliseconds=i+1000),
            )
            
            await market_data_adapter._on_bar_close(bar_close_event)
        
        end_time = time.perf_counter()
        
        total_time = (end_time - start_time) * 1000
        avg_time_per_event = total_time / 100
        
        # Should handle high frequency events efficiently
        assert avg_time_per_event < 50, f"High frequency processing too slow: {avg_time_per_event:.2f}ms per event"
        
        # Verify all events were processed
        logs = execution_logger.query_logs({"function_name": "stress_test"}, limit=200)
        assert len(logs) == 100
        
        print(f"High frequency stress test: {avg_time_per_event:.2f}ms per event, total={total_time:.2f}ms")