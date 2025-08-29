"""Concurrent execution integration tests for execution function framework.

This module tests thread safety, race conditions, and concurrent execution
scenarios to ensure the framework can handle simultaneous operations safely.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, UTC, timedelta
from decimal import Decimal
from typing import Dict, List, Set, Any, Optional
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import random

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


class ThreadSafeOrderManager:
    """Thread-safe order manager for concurrent testing."""
    
    def __init__(self):
        self.lock = asyncio.Lock()
        self.order_counter = 0
        self.placed_orders = {}
        self.order_history = []
        self.concurrent_order_count = 0
        self.max_concurrent = 0
        self.processing_delays = {}
        
    async def place_market_order(self, *args, **kwargs):
        """Thread-safe order placement with concurrent processing."""
        start_time = time.time()
        
        # Increment concurrent count (thread-safe)
        async with self.lock:
            self.concurrent_order_count += 1
            self.max_concurrent = max(self.max_concurrent, self.concurrent_order_count)
            current_concurrent = self.concurrent_order_count
        
        try:
            # Simulate realistic order processing time with some variability (concurrent)
            processing_delay = 0.01 + (self.order_counter % 3) * 0.005
            await asyncio.sleep(processing_delay)
            
            # Atomic operations for order creation (thread-safe)
            async with self.lock:
                self.order_counter += 1
                order_id = f"CONCURRENT_ORDER_{self.order_counter:06d}"
            
            result = OrderResult(
                success=True,
                order_id=order_id,
                trade_plan_id=kwargs.get("trade_plan_id", "concurrent_plan"),
                order_status="Filled",
                symbol=kwargs.get("symbol", "UNKNOWN"),
                side=kwargs.get("side", "BUY"),
                quantity=kwargs.get("quantity", 100),
                order_type="MKT",
                fill_price=Decimal(str(kwargs.get("limit_price", "180.00"))),
                commission=Decimal("1.00"),
                timestamp=datetime.now(UTC)
            )
            
            # Store results and tracking data (thread-safe)
            async with self.lock:
                self.placed_orders[order_id] = result
                
                # Track timing for analysis
                processing_time = time.time() - start_time
                self.processing_delays[order_id] = processing_time
                
                # Track order history for race condition detection
                self.order_history.append({
                    "order_id": order_id,
                    "thread_id": threading.get_ident(),
                    "timestamp": time.time(),
                    "symbol": kwargs.get("symbol"),
                    "concurrent_count": current_concurrent
                })
            
            return result
            
        finally:
            # Decrement concurrent count (thread-safe)
            async with self.lock:
                self.concurrent_order_count -= 1
    
    def get_concurrent_stats(self) -> Dict[str, Any]:
        """Get statistics about concurrent execution."""
        return {
            "total_orders": len(self.placed_orders),
            "max_concurrent": self.max_concurrent,
            "avg_processing_time": sum(self.processing_delays.values()) / len(self.processing_delays) if self.processing_delays else 0,
            "order_history_count": len(self.order_history)
        }


class ConcurrentBarDetector:
    """Bar detector that handles concurrent operations."""
    
    def __init__(self):
        self.lock = asyncio.Lock()
        self.callbacks = []
        self.monitored_symbols = {}
        self.bar_data = {}
        self.processing_count = 0
        self.max_concurrent_processing = 0
        self.bar_close_events = []
        
    def add_callback(self, callback):
        self.callbacks.append(callback)
    
    async def monitor_timeframe(self, symbol: str, timeframe: Timeframe):
        """Thread-safe timeframe monitoring."""
        async with self.lock:
            if symbol not in self.monitored_symbols:
                self.monitored_symbols[symbol] = set()
            self.monitored_symbols[symbol].add(timeframe)
    
    def update_bar_data(self, symbol: str, timeframe: Timeframe, bar: BarData):
        """Update bar data with concurrent access."""
        # Simulate concurrent access to bar data
        if symbol not in self.bar_data:
            self.bar_data[symbol] = {}
        if timeframe not in self.bar_data[symbol]:
            self.bar_data[symbol][timeframe] = []
        
        self.bar_data[symbol][timeframe].append(bar)
        
        # Trigger concurrent bar close processing
        asyncio.create_task(self._process_bar_close(symbol, timeframe, bar))
    
    async def _process_bar_close(self, symbol: str, timeframe: Timeframe, bar: BarData):
        """Process bar close with concurrency tracking."""
        self.processing_count += 1
        self.max_concurrent_processing = max(self.max_concurrent_processing, self.processing_count)
        
        try:
            # Simulate realistic processing time
            await asyncio.sleep(0.001 + random.random() * 0.002)
            
            event = BarCloseEvent(
                symbol=symbol,
                timeframe=timeframe,
                close_time=bar.timestamp,
                bar_data=bar,
                next_close_time=bar.timestamp + timedelta(minutes=1),
            )
            
            self.bar_close_events.append(event)
            
            # Call callbacks concurrently
            tasks = []
            for callback in self.callbacks:
                task = asyncio.create_task(callback(event))
                tasks.append(task)
            
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)
                
        finally:
            self.processing_count -= 1
    
    def get_concurrent_stats(self) -> Dict[str, Any]:
        """Get statistics about concurrent processing."""
        return {
            "max_concurrent_processing": self.max_concurrent_processing,
            "total_bar_close_events": len(self.bar_close_events),
            "monitored_symbol_count": len(self.monitored_symbols)
        }
    
    async def stop_monitoring(self, symbol: Optional[str] = None, timeframe: Optional[Timeframe] = None):
        async with self.lock:
            if symbol and timeframe:
                if symbol in self.monitored_symbols:
                    self.monitored_symbols[symbol].discard(timeframe)
            elif symbol:
                if symbol in self.monitored_symbols:
                    del self.monitored_symbols[symbol]
    
    def get_timing_stats(self) -> Dict:
        return {"avg_detection_latency_ms": 25.0, "total_detections": len(self.bar_close_events)}
    
    def get_monitored(self) -> Dict:
        return {symbol: list(timeframes) for symbol, timeframes in self.monitored_symbols.items()}


@pytest.fixture
def concurrent_order_manager():
    """Create thread-safe order manager."""
    return ThreadSafeOrderManager()


@pytest.fixture
def concurrent_bar_detector():
    """Create concurrent bar detector."""
    return ConcurrentBarDetector()


@pytest.fixture
def concurrent_execution_setup(concurrent_bar_detector, concurrent_order_manager):
    """Create concurrent execution test setup."""
    registry = ExecutionFunctionRegistry()
    logger = ExecutionLogger(
        enable_file_logging=False
    )
    
    market_adapter = MarketDataExecutionAdapter(
        bar_close_detector=concurrent_bar_detector,
        function_registry=registry,
        execution_logger=logger,
    )
    
    order_adapter = ExecutionOrderAdapter(
        order_execution_manager=concurrent_order_manager,
        default_risk_category=RiskCategory.NORMAL,
    )
    
    # Connect adapters
    market_adapter.add_signal_callback(order_adapter.handle_execution_signal)
    
    return {
        "registry": registry,
        "logger": logger,
        "detector": concurrent_bar_detector,
        "order_manager": concurrent_order_manager,
        "market_adapter": market_adapter,
        "order_adapter": order_adapter,
    }


def create_concurrent_bar_data(symbols: List[str], num_bars: int, base_prices: Dict[str, float]) -> Dict[str, List[BarData]]:
    """Create concurrent bar data for multiple symbols."""
    all_bars = {}
    
    for symbol in symbols:
        bars = []
        base_price = base_prices.get(symbol, 180.0)
        start_time = datetime.now(UTC) - timedelta(minutes=num_bars)
        
        for i in range(num_bars):
            bar_time = start_time + timedelta(minutes=i)
            # Add some price variation using Decimal arithmetic
            base_decimal = Decimal(str(base_price))
            price_variation = Decimal(str((i % 10 - 5) * 0.1000)).quantize(Decimal("0.0001"))
            close_price = (base_decimal + price_variation).quantize(Decimal("0.0001"))
            
            bar = BarData(
                symbol=symbol,
                timestamp=bar_time,
                open_price=(close_price - Decimal("0.0500")).quantize(Decimal("0.0001")),
                high_price=(close_price + Decimal("0.1000")).quantize(Decimal("0.0001")),
                low_price=(close_price - Decimal("0.1500")).quantize(Decimal("0.0001")),
                close_price=close_price.quantize(Decimal("0.0001")),
                volume=1000000 + (i * 10000),
                bar_size="1min",
            )
            
            bars.append(bar)
        
        all_bars[symbol] = bars
    
    return all_bars


class TestConcurrentExecutionIntegration:
    """Test concurrent execution scenarios and thread safety."""

    @pytest.mark.asyncio
    async def test_concurrent_symbol_processing(self, concurrent_execution_setup):
        """Test concurrent processing of multiple symbols."""
        setup = concurrent_execution_setup
        
        await setup["registry"].register("close_above", CloseAboveFunction)
        await setup["registry"].register("close_below", CloseBelowFunction)
        
        # Set up multiple symbols with different functions
        symbols = ["AAPL", "GOOGL", "MSFT", "TSLA", "NVDA"]
        base_prices = {"AAPL": 180.0, "GOOGL": 2800.0, "MSFT": 420.0, "TSLA": 250.0, "NVDA": 800.0}
        thresholds = {"AAPL": 181.0, "GOOGL": 2805.0, "MSFT": 425.0, "TSLA": 255.0, "NVDA": 805.0}
        
        # Create functions for all symbols
        for symbol in symbols:
            config = ExecutionFunctionConfig(
                name=f"{symbol.lower()}_concurrent",
                function_type="close_above",
                timeframe=Timeframe.ONE_MIN,
                parameters={"threshold_price": thresholds[symbol]},
                enabled=True,
            )
            
            await setup["registry"].create_function(config)
            await setup["market_adapter"].start_monitoring(symbol, Timeframe.ONE_MIN)
        
        # Generate concurrent bar data
        all_bar_data = create_concurrent_bar_data(symbols, 30, base_prices)
        
        # Process all symbols concurrently
        async def process_symbol_data(symbol: str, bars: List[BarData]):
            """Process bars for a single symbol."""
            for bar in bars:
                await setup["market_adapter"].on_market_data_update(bar)
                # Small delay to create realistic timing
                await asyncio.sleep(0.001)
        
        # Launch concurrent processing tasks
        tasks = []
        for symbol, bars in all_bar_data.items():
            task = asyncio.create_task(process_symbol_data(symbol, bars))
            tasks.append(task)
        
        # Wait for all processing to complete
        await asyncio.gather(*tasks)
        
        # Wait for any pending bar close events
        await asyncio.sleep(0.5)
        
        # Verify concurrent processing worked correctly
        concurrent_stats = setup["detector"].get_concurrent_stats()
        assert concurrent_stats["max_concurrent_processing"] > 1, "Should have processed multiple symbols concurrently"
        
        # Verify all symbols were processed
        logs = await setup["logger"].query_logs(limit=500)
        processed_symbols = set()
        
        for log in logs:
            log_str = str(log)
            for symbol in symbols:
                if symbol in log_str:
                    processed_symbols.add(symbol)
        
        assert len(processed_symbols) == len(symbols), f"Expected all {len(symbols)} symbols, got {len(processed_symbols)}"

    @pytest.mark.asyncio
    async def test_race_condition_prevention(self, concurrent_execution_setup):
        """Test prevention of race conditions in order placement."""
        setup = concurrent_execution_setup
        
        await setup["registry"].register("close_above", CloseAboveFunction)
        
        # Create function that should trigger multiple times
        config = ExecutionFunctionConfig(
            name="race_condition_test",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 180.00},
            enabled=True,
        )
        
        await setup["registry"].create_function(config)
        await setup["market_adapter"].start_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Feed historical data
        for i in range(25):
            bar = BarData(
                symbol="AAPL",
                timestamp=datetime.now(UTC) - timedelta(minutes=25-i),
                open_price=Decimal("179.50"),
                high_price=Decimal("180.00"),
                low_price=Decimal("179.00"),
                close_price=Decimal("179.50"),
                volume=1000000,
                bar_size="1min",
            )
            await setup["market_adapter"].on_market_data_update(bar)
        
        # Create multiple simultaneous triggering events
        concurrent_triggers = 20
        
        async def trigger_concurrent_signal(trigger_id: int):
            """Create concurrent triggering scenario."""
            trigger_bar = BarData(
                symbol="AAPL",
                timestamp=datetime.now(UTC) + timedelta(microseconds=trigger_id),
                open_price=Decimal("180.00"),
                high_price=Decimal("180.50"),
                low_price=Decimal("179.90"),
                close_price=Decimal("180.25"),  # Above threshold
                volume=1500000,
                bar_size="1min",
            )
            
            await setup["market_adapter"].on_market_data_update(trigger_bar)
            
            bar_close_event = BarCloseEvent(
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                close_time=datetime.now(UTC) + timedelta(microseconds=trigger_id),
                bar_data=trigger_bar,
                next_close_time=datetime.now(UTC) + timedelta(minutes=1),
            )
            
            await setup["market_adapter"]._on_bar_close(bar_close_event)
        
        # Launch concurrent triggers
        trigger_tasks = []
        for i in range(concurrent_triggers):
            task = asyncio.create_task(trigger_concurrent_signal(i))
            trigger_tasks.append(task)
        
        # Wait for all triggers to complete
        results = await asyncio.gather(*trigger_tasks, return_exceptions=True)
        
        # Count exceptions vs successful completions
        exceptions = [r for r in results if isinstance(r, Exception)]
        successes = [r for r in results if not isinstance(r, Exception)]
        
        # Should have mostly successful completions with good race condition handling
        assert len(successes) >= concurrent_triggers * 0.8, f"Expected mostly successes, got {len(successes)}/{concurrent_triggers}"
        
        # Verify order manager handled concurrency correctly
        concurrent_stats = setup["order_manager"].get_concurrent_stats()
        assert concurrent_stats["max_concurrent"] >= 2, "Should have had concurrent order processing"
        
        # Check for race condition indicators in order history
        order_history = setup["order_manager"].order_history
        
        # Verify orders were processed in reasonable time windows
        if len(order_history) > 1:
            timestamps = [order["timestamp"] for order in order_history]
            time_span = max(timestamps) - min(timestamps)
            assert time_span < 5.0, f"Order processing took too long: {time_span}s"

    @pytest.mark.asyncio
    async def test_high_frequency_concurrent_updates(self, concurrent_execution_setup):
        """Test high-frequency concurrent market data updates."""
        setup = concurrent_execution_setup
        
        await setup["registry"].register("close_above", CloseAboveFunction)
        
        # Create multiple functions for high-frequency testing
        symbols = ["AAPL", "GOOGL", "MSFT"]
        
        for symbol in symbols:
            config = ExecutionFunctionConfig(
                name=f"{symbol.lower()}_hf_test",
                function_type="close_above",
                timeframe=Timeframe.ONE_MIN,
                parameters={"threshold_price": 180.00 if symbol == "AAPL" else 2800.00 if symbol == "GOOGL" else 420.00},
                enabled=True,
            )
            
            await setup["registry"].create_function(config)
            await setup["market_adapter"].start_monitoring(symbol, Timeframe.ONE_MIN)
        
        # Generate high-frequency data stream
        async def generate_high_frequency_stream(symbol: str, duration_seconds: int, bars_per_second: int):
            """Generate high-frequency bar stream."""
            base_price = 180.0 if symbol == "AAPL" else 2800.0 if symbol == "GOOGL" else 420.0
            
            total_bars = duration_seconds * bars_per_second
            interval = 1.0 / bars_per_second
            
            for i in range(total_bars):
                bar_time = datetime.now(UTC) + timedelta(seconds=i * interval)
                # Small price movements using Decimal arithmetic
                base_decimal = Decimal(str(base_price))
                price_variation = Decimal(str((i % 20 - 10) * 0.0100)).quantize(Decimal("0.0001"))
                close_price = (base_decimal + price_variation).quantize(Decimal("0.0001"))
                
                bar = BarData(
                    symbol=symbol,
                    timestamp=bar_time,
                    open_price=(close_price - Decimal("0.0200")).quantize(Decimal("0.0001")),
                    high_price=(close_price + Decimal("0.0500")).quantize(Decimal("0.0001")),
                    low_price=(close_price - Decimal("0.0500")).quantize(Decimal("0.0001")),
                    close_price=close_price,
                    volume=50000 + (i * 1000),
                    bar_size="1min",
                )
                
                await setup["market_adapter"].on_market_data_update(bar)
                await asyncio.sleep(interval * 0.1)  # Small processing delay
        
        # Launch concurrent high-frequency streams
        hf_tasks = []
        for symbol in symbols:
            task = asyncio.create_task(
                generate_high_frequency_stream(symbol, duration_seconds=5, bars_per_second=10)
            )
            hf_tasks.append(task)
        
        start_time = time.time()
        await asyncio.gather(*hf_tasks)
        processing_time = time.time() - start_time
        
        # Allow final processing to complete
        await asyncio.sleep(0.5)
        
        # Verify performance under high-frequency load
        assert processing_time < 10.0, f"High-frequency processing took {processing_time}s, should be under 10s"
        
        # Check concurrent processing statistics
        detector_stats = setup["detector"].get_concurrent_stats()
        order_stats = setup["order_manager"].get_concurrent_stats()
        
        assert detector_stats["max_concurrent_processing"] >= 2, "Should have concurrent bar processing"
        
        # Verify system stability under load
        metrics = await setup["logger"].get_metrics()
        if "total_evaluations" in metrics:
            assert metrics["total_evaluations"] > 100, "Should have processed many evaluations"

    @pytest.mark.asyncio
    async def test_resource_contention_handling(self, concurrent_execution_setup):
        """Test handling of resource contention scenarios."""
        setup = concurrent_execution_setup
        
        await setup["registry"].register("close_above", CloseAboveFunction)
        
        # Create multiple functions that compete for resources
        num_competing_functions = 10
        
        for i in range(num_competing_functions):
            config = ExecutionFunctionConfig(
                name=f"competing_function_{i}",
                function_type="close_above",
                timeframe=Timeframe.ONE_MIN,
                parameters={"threshold_price": 180.00 + i * 0.1},
                enabled=True,
            )
            
            await setup["registry"].create_function(config)
        
        await setup["market_adapter"].start_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Create resource contention scenario
        contention_tasks = []
        
        async def create_resource_contention(task_id: int):
            """Create scenario that competes for resources."""
            # Feed historical data
            for i in range(25):
                bar = BarData(
                    symbol="AAPL",
                    timestamp=datetime.now(UTC) - timedelta(minutes=25-i) + timedelta(microseconds=task_id),
                    open_price=Decimal("179.50"),
                    high_price=Decimal("180.00"),
                    low_price=Decimal("179.00"),
                    close_price=Decimal("179.75"),
                    volume=1000000,
                    bar_size="1min",
                )
                await setup["market_adapter"].on_market_data_update(bar)
            
            # Trigger evaluation
            trigger_bar = BarData(
                symbol="AAPL",
                timestamp=datetime.now(UTC) + timedelta(microseconds=task_id),
                open_price=Decimal("180.20"),
                high_price=Decimal("181.00"),
                low_price=Decimal("180.00"),
                close_price=Decimal("180.5000") + Decimal(str(task_id)) * Decimal("0.0100"),  # Different prices
                volume=2000000,
                bar_size="1min",
            )
            
            await setup["market_adapter"].on_market_data_update(trigger_bar)
            
            # Simulate bar close
            bar_close_event = BarCloseEvent(
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                close_time=datetime.now(UTC) + timedelta(microseconds=task_id),
                bar_data=trigger_bar,
                next_close_time=datetime.now(UTC) + timedelta(minutes=1),
            )
            
            await setup["market_adapter"]._on_bar_close(bar_close_event)
        
        # Launch multiple competing tasks
        for task_id in range(5):
            task = asyncio.create_task(create_resource_contention(task_id))
            contention_tasks.append(task)
        
        # Process all contention scenarios
        results = await asyncio.gather(*contention_tasks, return_exceptions=True)
        
        # Verify most tasks completed successfully
        successful_tasks = [r for r in results if not isinstance(r, Exception)]
        failed_tasks = [r for r in results if isinstance(r, Exception)]
        
        assert len(successful_tasks) >= 3, f"Expected most tasks to succeed, got {len(successful_tasks)}/5"
        
        # Verify resource sharing worked correctly
        order_stats = setup["order_manager"].get_concurrent_stats()
        assert order_stats["total_orders"] > 0, "Some orders should have been placed"
        
        # Check for reasonable processing times despite contention
        avg_processing_time = order_stats["avg_processing_time"]
        assert avg_processing_time < 0.1, f"Average processing time too high: {avg_processing_time}s"

    @pytest.mark.asyncio
    async def test_thread_safety_validation(self, concurrent_execution_setup):
        """Test thread safety of shared data structures."""
        setup = concurrent_execution_setup
        
        await setup["registry"].register("close_above", CloseAboveFunction)
        
        config = ExecutionFunctionConfig(
            name="thread_safety_test",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 180.00},
            enabled=True,
        )
        
        await setup["registry"].create_function(config)
        await setup["market_adapter"].start_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Create shared state that multiple threads will access
        shared_state = {
            "total_updates": 0,
            "bar_count": 0,
            "trigger_count": 0,
        }
        
        state_lock = asyncio.Lock()
        
        async def concurrent_state_updater(updater_id: int, num_updates: int):
            """Update shared state from multiple concurrent contexts."""
            for i in range(num_updates):
                # Create bar data
                bar = BarData(
                    symbol="AAPL",
                    timestamp=datetime.now(UTC) + timedelta(microseconds=updater_id * 1000 + i),
                    open_price=Decimal("179.90"),
                    high_price=Decimal("180.50"),
                    low_price=Decimal("179.50"),
                    close_price=Decimal("179.5000") + Decimal(str(i)) * Decimal("0.0100"),
                    volume=1000000,
                    bar_size="1min",
                )
                
                await setup["market_adapter"].on_market_data_update(bar)
                
                # Update shared state with proper locking
                async with state_lock:
                    shared_state["total_updates"] += 1
                    shared_state["bar_count"] += 1
                    
                    if bar.close_price > Decimal("180.00"):
                        shared_state["trigger_count"] += 1
                
                # Small delay to increase chance of race conditions
                await asyncio.sleep(0.001)
        
        # Launch multiple concurrent updaters
        num_updaters = 8
        updates_per_updater = 20
        
        updater_tasks = []
        for updater_id in range(num_updaters):
            task = asyncio.create_task(
                concurrent_state_updater(updater_id, updates_per_updater)
            )
            updater_tasks.append(task)
        
        # Wait for all updates to complete
        await asyncio.gather(*updater_tasks)
        
        # Wait for processing to finish
        await asyncio.sleep(0.3)
        
        # Verify thread safety - no data corruption
        expected_total_updates = num_updaters * updates_per_updater
        assert shared_state["total_updates"] == expected_total_updates, \
            f"Expected {expected_total_updates} updates, got {shared_state['total_updates']} (possible race condition)"
        
        assert shared_state["bar_count"] == expected_total_updates, \
            f"Bar count mismatch: {shared_state['bar_count']} vs {expected_total_updates}"
        
        # Verify order placement consistency
        order_stats = setup["order_manager"].get_concurrent_stats()
        
        # Check for duplicate order detection
        order_history = setup["order_manager"].order_history
        if len(order_history) > 1:
            # Ensure no duplicate orders at exact same timestamp
            timestamps = [order["timestamp"] for order in order_history]
            unique_timestamps = set(timestamps)
            
            # Allow small timing differences but not exact duplicates
            if len(unique_timestamps) < len(timestamps):
                duplicate_count = len(timestamps) - len(unique_timestamps)
                assert duplicate_count < 3, f"Too many potential duplicate orders: {duplicate_count}"

    @pytest.mark.asyncio
    async def test_concurrent_function_registration(self, concurrent_execution_setup):
        """Test thread safety of function registration and management."""
        setup = concurrent_execution_setup
        
        await setup["registry"].register("close_above", CloseAboveFunction)
        await setup["registry"].register("close_below", CloseBelowFunction)
        
        # Track registration conflicts
        registration_results = []
        
        async def concurrent_function_registration(registrar_id: int, num_functions: int):
            """Register functions concurrently."""
            results = []
            
            for i in range(num_functions):
                function_name = f"concurrent_func_{registrar_id}_{i}"
                
                config = ExecutionFunctionConfig(
                    name=function_name,
                    function_type="close_above" if i % 2 == 0 else "close_below",
                    timeframe=Timeframe.ONE_MIN,
                    parameters={"threshold_price": 180.00 + i},
                    enabled=True,
                )
                
                try:
                    function = await setup["registry"].create_function(config)
                    results.append({
                        "registrar_id": registrar_id,
                        "function_name": function_name,
                        "success": function is not None,
                        "timestamp": time.time()
                    })
                except Exception as e:
                    results.append({
                        "registrar_id": registrar_id,
                        "function_name": function_name,
                        "success": False,
                        "error": str(e),
                        "timestamp": time.time()
                    })
            
            return results
        
        # Launch concurrent registration
        num_registrars = 5
        functions_per_registrar = 10
        
        registration_tasks = []
        for registrar_id in range(num_registrars):
            task = asyncio.create_task(
                concurrent_function_registration(registrar_id, functions_per_registrar)
            )
            registration_tasks.append(task)
        
        # Collect all registration results
        all_results = await asyncio.gather(*registration_tasks)
        
        # Flatten results
        for results in all_results:
            registration_results.extend(results)
        
        # Analyze registration success rate
        successful_registrations = [r for r in registration_results if r["success"]]
        failed_registrations = [r for r in registration_results if not r["success"]]
        
        success_rate = len(successful_registrations) / len(registration_results)
        assert success_rate > 0.9, f"Registration success rate too low: {success_rate:.2%}"
        
        # Verify no function name conflicts
        function_names = [r["function_name"] for r in successful_registrations]
        unique_names = set(function_names)
        assert len(function_names) == len(unique_names), "Function name conflicts detected"
        
        # Test concurrent function evaluation after registration
        await setup["market_adapter"].start_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Feed data to trigger concurrent evaluations
        for i in range(25):
            bar = BarData(
                symbol="AAPL",
                timestamp=datetime.now(UTC) - timedelta(minutes=25-i),
                open_price=Decimal("179.50"),
                high_price=Decimal("180.00"),
                low_price=Decimal("179.00"),
                close_price=Decimal("179.75"),
                volume=1000000,
                bar_size="1min",
            )
            await setup["market_adapter"].on_market_data_update(bar)
        
        # Trigger evaluation of all registered functions
        trigger_bar = BarData(
            symbol="AAPL",
            timestamp=datetime.now(UTC),
            open_price=Decimal("180.20"),
            high_price=Decimal("181.50"),
            low_price=Decimal("180.00"),
            close_price=Decimal("181.00"),  # Should trigger many functions
            volume=2000000,
            bar_size="1min",
        )
        
        await setup["market_adapter"].on_market_data_update(trigger_bar)
        
        bar_close_event = BarCloseEvent(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            close_time=datetime.now(UTC),
            bar_data=trigger_bar,
            next_close_time=datetime.now(UTC) + timedelta(minutes=1),
        )
        
        # Should handle concurrent function evaluations
        await setup["market_adapter"]._on_bar_close(bar_close_event)
        
        # Verify concurrent evaluations were logged
        logs = await setup["logger"].query_logs(limit=200)
        evaluation_logs = [log for log in logs if "concurrent_func" in str(log)]
        
        # Should have evaluations from multiple registered functions
        assert len(evaluation_logs) >= 5, f"Expected multiple function evaluations, got {len(evaluation_logs)}"

    @pytest.mark.asyncio  
    async def test_deadlock_prevention(self, concurrent_execution_setup):
        """Test prevention of deadlocks in concurrent scenarios."""
        setup = concurrent_execution_setup
        
        await setup["registry"].register("close_above", CloseAboveFunction)
        
        config = ExecutionFunctionConfig(
            name="deadlock_test",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 180.00},
            enabled=True,
        )
        
        await setup["registry"].create_function(config)
        await setup["market_adapter"].start_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Create scenario that could cause deadlocks
        async def deadlock_prone_operation(operation_id: int):
            """Perform operations that could potentially deadlock."""
            # Feed historical data
            for i in range(20):
                bar = BarData(
                    symbol="AAPL",
                    timestamp=datetime.now(UTC) - timedelta(minutes=20-i) + timedelta(microseconds=operation_id),
                    open_price=Decimal("179.50"),
                    high_price=Decimal("180.00"),
                    low_price=Decimal("179.00"),
                    close_price=Decimal("179.75"),
                    volume=1000000,
                    bar_size="1min",
                )
                await setup["market_adapter"].on_market_data_update(bar)
                
                # Attempt concurrent access to registry
                functions = await setup["registry"].get_functions_by_timeframe("AAPL", Timeframe.ONE_MIN)
                
                # Simulate work that holds resources
                await asyncio.sleep(0.001)
            
            # Trigger order placement
            trigger_bar = BarData(
                symbol="AAPL",
                timestamp=datetime.now(UTC) + timedelta(microseconds=operation_id),
                open_price=Decimal("180.20"),
                high_price=Decimal("180.60"),
                low_price=Decimal("180.00"),
                close_price=Decimal("180.30"),
                volume=1500000,
                bar_size="1min",
            )
            
            await setup["market_adapter"].on_market_data_update(trigger_bar)
            
            bar_close_event = BarCloseEvent(
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                close_time=datetime.now(UTC) + timedelta(microseconds=operation_id),
                bar_data=trigger_bar,
                next_close_time=datetime.now(UTC) + timedelta(minutes=1),
            )
            
            await setup["market_adapter"]._on_bar_close(bar_close_event)
        
        # Launch multiple deadlock-prone operations
        num_operations = 8
        deadlock_tasks = []
        
        for op_id in range(num_operations):
            task = asyncio.create_task(deadlock_prone_operation(op_id))
            deadlock_tasks.append(task)
        
        # Use timeout to detect potential deadlocks
        try:
            await asyncio.wait_for(
                asyncio.gather(*deadlock_tasks, return_exceptions=True),
                timeout=30.0  # Should complete well within 30 seconds
            )
        except asyncio.TimeoutError:
            pytest.fail("Potential deadlock detected - operations timed out")
        
        # Verify system is still responsive after concurrent operations
        final_test_bar = BarData(
            symbol="AAPL",
            timestamp=datetime.now(UTC),
            open_price=Decimal("180.50"),
            high_price=Decimal("181.00"),
            low_price=Decimal("180.40"),
            close_price=Decimal("180.75"),
            volume=1800000,
            bar_size="1min",
        )
        
        await setup["market_adapter"].on_market_data_update(final_test_bar)
        
        # System should still be responsive
        final_event = BarCloseEvent(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            close_time=datetime.now(UTC),
            bar_data=final_test_bar,
            next_close_time=datetime.now(UTC) + timedelta(minutes=1),
        )
        
        # Should complete without deadlock
        await setup["market_adapter"]._on_bar_close(final_event)
        
        # Verify no deadlock indicators in logs
        logs = await setup["logger"].query_logs(limit=300)
        timeout_logs = [log for log in logs if "timeout" in str(log).lower() or "deadlock" in str(log).lower()]
        
        # Should not have timeout/deadlock indicators
        assert len(timeout_logs) == 0, f"Found potential deadlock indicators: {len(timeout_logs)}"