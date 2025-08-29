"""Performance tests for high-frequency execution scenarios."""

import pytest
import asyncio
import time
from datetime import datetime, UTC, timedelta
from decimal import Decimal
from statistics import mean, stdev
from concurrent.futures import ThreadPoolExecutor

from auto_trader.models.execution import (
    ExecutionContext,
    ExecutionSignal,
    ExecutionFunctionConfig,
    ExecutionLogEntry,
    BarCloseEvent,
)
from auto_trader.models.enums import ExecutionAction, Timeframe
from auto_trader.models.market_data import BarData
from auto_trader.trade_engine.function_registry import ExecutionFunctionRegistry
from auto_trader.trade_engine.execution_logger import ExecutionLogger
from auto_trader.trade_engine.bar_close_detector import BarCloseDetector
from auto_trader.trade_engine.functions import CloseAboveFunction, CloseBelowFunction


@pytest.fixture
async def performance_registry():
    """Create registry with performance-optimized functions."""
    registry = ExecutionFunctionRegistry()
    await registry.clear_all()
    
    # Register functions
    await registry.register("close_above", CloseAboveFunction)
    await registry.register("close_below", CloseBelowFunction)
    
    yield registry
    
    await registry.clear_all()


@pytest.fixture
def high_frequency_data():
    """Generate high-frequency test data."""
    base_time = datetime.now(UTC)
    bars = []
    
    # Create 1000 bars with realistic price movements
    base_price = Decimal("180.00")
    
    for i in range(1000):
        # Simulate realistic price movement
        price_change = Decimal(str((i % 10 - 5) * 0.01))  # +/- 5 cents
        current_price = base_price + price_change
        
        bar = BarData(
            symbol="AAPL",
            timestamp=base_time + timedelta(seconds=i),
            open_price=current_price - Decimal("0.02"),
            high_price=current_price + Decimal("0.03"),
            low_price=current_price - Decimal("0.05"),
            close_price=current_price,
            volume=1000000 + (i * 1000),
            bar_size="1min",
        )
        bars.append(bar)
    
    return bars


@pytest.fixture
async def performance_detector():
    """Create bar close detector optimized for performance testing."""
    detector = BarCloseDetector(
        accuracy_ms=100,
        schedule_advance_ms=50
    )
    await detector.start()
    yield detector
    await detector.stop()


@pytest.mark.asyncio
class TestHighFrequencyPerformance:
    """Performance tests for high-frequency execution scenarios."""

    async def test_single_function_throughput(
        self, performance_registry, high_frequency_data
    ):
        """Test throughput of single execution function under load."""
        # Create function
        config = ExecutionFunctionConfig(
            name="perf_test",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 180.00},
            enabled=True
        )
        function = await performance_registry.create_function(config)
        
        # Performance metrics
        execution_times = []
        signals_generated = 0
        
        start_time = time.perf_counter()
        
        # Process bars rapidly
        for i, bar in enumerate(high_frequency_data):
            context = ExecutionContext(
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                current_bar=bar,
                historical_bars=high_frequency_data[max(0, i-20):i],
                trade_plan_params={"threshold_price": 180.00},
                position_state=None,
                account_balance=Decimal("10000"),
                timestamp=bar.timestamp
            )
            
            # Measure individual execution time
            exec_start = time.perf_counter()
            signal = await function.evaluate(context)
            exec_time = (time.perf_counter() - exec_start) * 1000  # ms
            
            execution_times.append(exec_time)
            if signal.action != ExecutionAction.NONE:
                signals_generated += 1
        
        total_time = time.perf_counter() - start_time
        
        # Performance assertions
        throughput = len(high_frequency_data) / total_time
        avg_execution_time = mean(execution_times)
        max_execution_time = max(execution_times)
        
        print(f"Throughput: {throughput:.1f} evaluations/second")
        print(f"Average execution time: {avg_execution_time:.3f}ms")
        print(f"Max execution time: {max_execution_time:.3f}ms")
        print(f"Signals generated: {signals_generated}")
        
        # Performance requirements
        assert throughput > 100  # At least 100 evaluations per second
        assert avg_execution_time < 5.0  # Average under 5ms
        assert max_execution_time < 20.0  # Max under 20ms

    async def test_concurrent_function_execution(
        self, performance_registry, high_frequency_data
    ):
        """Test concurrent execution of multiple functions."""
        # Create multiple functions
        functions = []
        for i in range(5):
            config = ExecutionFunctionConfig(
                name=f"perf_test_{i}",
                function_type="close_above",
                timeframe=Timeframe.ONE_MIN,
                parameters={"threshold_price": 179.50 + (i * 0.1)},
                enabled=True
            )
            functions.append(await performance_registry.create_function(config))
        
        async def execute_function_batch(function, data_batch):
            """Execute function on batch of data."""
            results = []
            for bar in data_batch:
                context = ExecutionContext(
                    symbol="AAPL",
                    timeframe=Timeframe.ONE_MIN,
                    current_bar=bar,
                    historical_bars=data_batch[:20],
                    trade_plan_params=function.parameters,
                    position_state=None,
                    account_balance=Decimal("10000"),
                    timestamp=bar.timestamp
                )
                signal = await function.evaluate(context)
                results.append(signal)
            return results
        
        # Test concurrent execution
        start_time = time.perf_counter()
        
        # Create batches for concurrent processing
        batch_size = 100
        batches = [
            high_frequency_data[i:i + batch_size]
            for i in range(0, min(500, len(high_frequency_data)), batch_size)
        ]
        
        # Execute all functions on all batches concurrently
        tasks = [
            execute_function_batch(func, batch)
            for func in functions
            for batch in batches
        ]
        
        results = await asyncio.gather(*tasks)
        
        total_time = time.perf_counter() - start_time
        total_evaluations = len(functions) * len(batches) * batch_size
        throughput = total_evaluations / total_time
        
        print(f"Concurrent throughput: {throughput:.1f} evaluations/second")
        print(f"Total evaluations: {total_evaluations}")
        print(f"Total time: {total_time:.3f}s")
        
        # Should handle concurrent load efficiently
        assert throughput > 200  # Higher throughput with concurrency
        assert len(results) == len(functions) * len(batches)

    async def test_memory_usage_under_load(
        self, performance_registry, high_frequency_data
    ):
        """Test memory usage during high-frequency processing."""
        import psutil
        import os
        
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Create function
        config = ExecutionFunctionConfig(
            name="memory_test",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 180.00},
            enabled=True
        )
        function = await performance_registry.create_function(config)
        
        # Process large dataset
        memory_samples = []
        
        for i in range(0, len(high_frequency_data), 50):  # Sample every 50 bars
            # Process batch
            batch = high_frequency_data[i:i+50]
            for bar in batch:
                context = ExecutionContext(
                    symbol="AAPL",
                    timeframe=Timeframe.ONE_MIN,
                    current_bar=bar,
                    historical_bars=high_frequency_data[max(0, i-20):i],
                    trade_plan_params={"threshold_price": 180.00},
                    position_state=None,
                    account_balance=Decimal("10000"),
                    timestamp=bar.timestamp
                )
                await function.evaluate(context)
            
            # Sample memory usage
            current_memory = process.memory_info().rss / 1024 / 1024
            memory_samples.append(current_memory)
        
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = final_memory - initial_memory
        max_memory = max(memory_samples)
        
        print(f"Initial memory: {initial_memory:.1f}MB")
        print(f"Final memory: {final_memory:.1f}MB")
        print(f"Memory increase: {memory_increase:.1f}MB")
        print(f"Peak memory: {max_memory:.1f}MB")
        
        # Memory usage should be reasonable
        assert memory_increase < 50  # Less than 50MB increase
        assert max_memory < initial_memory + 100  # Peak under 100MB increase

    async def test_bar_close_detector_performance(
        self, performance_detector, high_frequency_data
    ):
        """Test bar close detector performance under high frequency."""
        events_processed = 0
        processing_times = []
        
        async def performance_callback(event: BarCloseEvent):
            """High-performance event callback."""
            nonlocal events_processed
            start_time = time.perf_counter()
            
            # Simulate minimal processing
            events_processed += 1
            
            processing_time = (time.perf_counter() - start_time) * 1000
            processing_times.append(processing_time)
        
        performance_detector.add_callback(performance_callback)
        
        # Process events rapidly
        start_time = time.perf_counter()
        
        for i, bar in enumerate(high_frequency_data[:200]):  # Limit for performance test
            # Update bar data
            performance_detector.update_bar_data("AAPL", Timeframe.ONE_MIN, bar)
            
            # Create and emit bar close event
            event = BarCloseEvent(
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                close_time=bar.timestamp,
                bar_data=bar,
                next_close_time=bar.timestamp + timedelta(minutes=1)
            )
            
            await performance_detector._emit_event(event)
        
        total_time = time.perf_counter() - start_time
        
        # Performance metrics
        event_throughput = events_processed / total_time
        avg_processing_time = mean(processing_times) if processing_times else 0
        
        print(f"Event throughput: {event_throughput:.1f} events/second")
        print(f"Events processed: {events_processed}")
        print(f"Avg processing time: {avg_processing_time:.3f}ms")
        
        # Performance assertions
        assert event_throughput > 500  # At least 500 events per second
        assert avg_processing_time < 1.0  # Under 1ms average processing

    async def test_execution_logger_performance(self, high_frequency_data):
        """Test execution logger performance under high load."""
        import tempfile
        from pathlib import Path
        
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = ExecutionLogger(
                log_directory=Path(temp_dir),
                max_entries_per_file=500,  # Smaller files for performance
                max_log_files=10
            )
            
            # Generate log entries rapidly
            log_times = []
            
            start_time = time.perf_counter()
            
            for i, bar in enumerate(high_frequency_data[:500]):
                signal = ExecutionSignal(
                    action=ExecutionAction.ENTER_LONG if i % 10 == 0 else ExecutionAction.NONE,
                    confidence=0.75,
                    reasoning=f"Test signal {i}",
                    metadata={"bar_index": i}
                )
                
                entry = ExecutionLogEntry(
                    timestamp=bar.timestamp,
                    function_name="perf_test",
                    symbol="AAPL",
                    timeframe=Timeframe.ONE_MIN,
                    signal=signal,
                    duration_ms=1.5,
                    context_snapshot={"price": float(bar.close_price)}
                )
                
                log_start = time.perf_counter()
                await logger.log_execution_decision(entry)
                log_time = (time.perf_counter() - log_start) * 1000
                log_times.append(log_time)
            
            total_time = time.perf_counter() - start_time
            
            # Performance metrics
            log_throughput = len(log_times) / total_time
            avg_log_time = mean(log_times)
            max_log_time = max(log_times)
            
            print(f"Log throughput: {log_throughput:.1f} entries/second")
            print(f"Average log time: {avg_log_time:.3f}ms")
            print(f"Max log time: {max_log_time:.3f}ms")
            
            # Performance assertions
            assert log_throughput > 1000  # At least 1000 log entries per second
            assert avg_log_time < 2.0  # Under 2ms average
            assert max_log_time < 10.0  # Max under 10ms

    async def test_registry_lookup_performance(self, performance_registry):
        """Test function registry performance under high lookup frequency."""
        # Register many functions
        for i in range(100):
            config = ExecutionFunctionConfig(
                name=f"perf_function_{i}",
                function_type="close_above",
                timeframe=Timeframe.ONE_MIN,
                parameters={"threshold_price": 180.0 + i},
                enabled=True
            )
            await performance_registry.create_function(config)
        
        # Measure lookup performance
        lookup_times = []
        
        start_time = time.perf_counter()
        
        for i in range(1000):  # 1000 lookups
            lookup_start = time.perf_counter()
            
            # Various registry operations
            function_name = f"perf_function_{i % 100}"
            function = performance_registry.get_function(function_name)
            
            if function:
                _ = function.is_enabled
                _ = function.timeframe
                _ = function.parameters
            
            lookup_time = (time.perf_counter() - lookup_start) * 1000
            lookup_times.append(lookup_time)
        
        total_time = time.perf_counter() - start_time
        
        # Performance metrics
        lookup_throughput = len(lookup_times) / total_time
        avg_lookup_time = mean(lookup_times)
        
        print(f"Registry lookup throughput: {lookup_throughput:.1f} lookups/second")
        print(f"Average lookup time: {avg_lookup_time:.3f}ms")
        
        # Performance assertions
        assert lookup_throughput > 10000  # Very fast lookups
        assert avg_lookup_time < 0.1  # Sub-millisecond lookups

    async def test_stress_test_all_components(
        self, performance_registry, performance_detector, high_frequency_data
    ):
        """Comprehensive stress test of all components together."""
        import tempfile
        from pathlib import Path
        
        # Setup components
        functions = []
        for i in range(3):
            config = ExecutionFunctionConfig(
                name=f"stress_test_{i}",
                function_type="close_above",
                timeframe=Timeframe.ONE_MIN,
                parameters={"threshold_price": 179.8 + (i * 0.1)},
                enabled=True
            )
            functions.append(await performance_registry.create_function(config))
        
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = ExecutionLogger(
                log_directory=Path(temp_dir),
                max_entries_per_file=100,
                max_log_files=5
            )
            
            # Stress test metrics
            total_evaluations = 0
            total_events = 0
            total_logs = 0
            
            async def stress_callback(event: BarCloseEvent):
                """Stress test callback that exercises all components."""
                nonlocal total_evaluations, total_events, total_logs
                total_events += 1
                
                # Execute all functions
                for function in functions:
                    context = ExecutionContext(
                        symbol=event.symbol,
                        timeframe=event.timeframe,
                        current_bar=event.bar_data,
                        historical_bars=[event.bar_data] * 20,
                        trade_plan_params=function.parameters,
                        position_state=None,
                        account_balance=Decimal("10000"),
                        timestamp=event.close_time
                    )
                    
                    signal = await function.evaluate(context)
                    total_evaluations += 1
                    
                    # Log the decision
                    entry = ExecutionLogEntry(
                        timestamp=event.close_time,
                        function_name=function.name,
                        symbol=event.symbol,
                        timeframe=event.timeframe,
                        signal=signal,
                        duration_ms=0.5,
                    )
                    
                    await logger.log_execution_decision(entry)
                    total_logs += 1
            
            performance_detector.add_callback(stress_callback)
            await performance_detector.monitor_timeframe("AAPL", Timeframe.ONE_MIN)
            
            # Run stress test
            start_time = time.perf_counter()
            
            for bar in high_frequency_data[:100]:  # Limit for stress test
                performance_detector.update_bar_data("AAPL", Timeframe.ONE_MIN, bar)
                
                event = BarCloseEvent(
                    symbol="AAPL",
                    timeframe=Timeframe.ONE_MIN,
                    close_time=bar.timestamp,
                    bar_data=bar,
                    next_close_time=bar.timestamp + timedelta(minutes=1)
                )
                
                await performance_detector._emit_event(event)
            
            total_time = time.perf_counter() - start_time
            
            # Comprehensive performance metrics
            print(f"Stress test completed in {total_time:.3f}s")
            print(f"Total events: {total_events}")
            print(f"Total evaluations: {total_evaluations}")
            print(f"Total logs: {total_logs}")
            print(f"Overall throughput: {total_evaluations / total_time:.1f} ops/second")
            
            # System should handle integrated load
            assert total_events == 100
            assert total_evaluations == 300  # 3 functions × 100 events
            assert total_logs == 300
            assert total_time < 5.0  # Complete within 5 seconds

    async def test_latency_distribution(self, performance_registry, high_frequency_data):
        """Test latency distribution to identify performance outliers."""
        config = ExecutionFunctionConfig(
            name="latency_test",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 180.00},
            enabled=True
        )
        function = await performance_registry.create_function(config)
        
        latencies = []
        
        # Measure latencies for many executions
        for i, bar in enumerate(high_frequency_data[:200]):
            context = ExecutionContext(
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                current_bar=bar,
                historical_bars=high_frequency_data[max(0, i-20):i],
                trade_plan_params={"threshold_price": 180.00},
                position_state=None,
                account_balance=Decimal("10000"),
                timestamp=bar.timestamp
            )
            
            start_time = time.perf_counter()
            await function.evaluate(context)
            latency = (time.perf_counter() - start_time) * 1000
            latencies.append(latency)
        
        # Statistical analysis
        mean_latency = mean(latencies)
        std_latency = stdev(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
        p99_latency = sorted(latencies)[int(len(latencies) * 0.99)]
        max_latency = max(latencies)
        
        print(f"Latency distribution:")
        print(f"  Mean: {mean_latency:.3f}ms")
        print(f"  Std Dev: {std_latency:.3f}ms")
        print(f"  P95: {p95_latency:.3f}ms")
        print(f"  P99: {p99_latency:.3f}ms")
        print(f"  Max: {max_latency:.3f}ms")
        
        # Performance requirements for latency distribution
        assert mean_latency < 5.0  # Mean under 5ms (more lenient)
        assert p95_latency < 15.0  # 95th percentile under 15ms
        assert p99_latency < 30.0  # 99th percentile under 30ms
        assert std_latency < mean_latency * 2  # Reasonable performance consistency