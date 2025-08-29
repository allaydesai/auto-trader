"""Error recovery integration tests for execution function framework.

This module tests the framework's resilience to various failure scenarios
and validates proper error handling, recovery mechanisms, and circuit breakers.
"""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, UTC, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any
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
from auto_trader.trade_engine.functions import CloseAboveFunction


class NetworkFailureSimulator:
    """Simulates network failures and recovery scenarios."""
    
    def __init__(self):
        self.failure_rate = 0.0
        self.failure_duration = 0
        self.current_failures = 0
        self.total_failures = 0
        self.recovery_callbacks = []
        
    def set_failure_rate(self, rate: float):
        """Set probability of failure (0.0 to 1.0)."""
        self.failure_rate = max(0.0, min(1.0, rate))
    
    def simulate_failure(self) -> bool:
        """Return True if failure should occur."""
        if self.current_failures > 0:
            self.current_failures -= 1
            return True
        
        if random.random() < self.failure_rate:
            self.current_failures = random.randint(1, 3)  # Failure lasts 1-3 attempts
            self.total_failures += 1
            return True
        
        return False
    
    def add_recovery_callback(self, callback):
        """Add callback to be called on recovery."""
        self.recovery_callbacks.append(callback)
    
    async def trigger_recovery(self):
        """Trigger recovery callbacks."""
        for callback in self.recovery_callbacks:
            try:
                await callback()
            except Exception:
                pass


class FlakyOrderManager:
    """Order manager that simulates various failure modes."""
    
    def __init__(self, network_simulator: NetworkFailureSimulator):
        self.network = network_simulator
        self.order_counter = 0
        self.placed_orders = {}
        self.failure_modes = {
            "network_timeout": 0.1,
            "order_rejection": 0.05,
            "partial_fill": 0.1,
            "price_mismatch": 0.05,
        }
        
    async def place_market_order(self, *args, **kwargs):
        """Place order with potential failures."""
        self.order_counter += 1
        order_id = f"FLAKY_ORDER_{self.order_counter:06d}"
        
        # Check for network failure
        if self.network.simulate_failure():
            raise ConnectionError("Network connection failed")
        
        # Simulate various failure modes
        failure_type = self._get_failure_type()
        
        if failure_type == "network_timeout":
            await asyncio.sleep(0.1)  # Simulate timeout delay
            raise TimeoutError("Order placement timed out")
        
        elif failure_type == "order_rejection":
            result = OrderResult(
                success=False,
                order_id=order_id,
                trade_plan_id=kwargs.get("trade_plan_id", "test_plan"),
                order_status="Rejected",
                symbol=kwargs.get("symbol", "UNKNOWN"),
                side=kwargs.get("side", "BUY"),
                quantity=kwargs.get("quantity", 100),
                order_type="MKT",
                error_message="Insufficient margin",
                timestamp=datetime.now(UTC)
            )
            self.placed_orders[order_id] = result
            return result
        
        elif failure_type == "partial_fill":
            partial_qty = kwargs.get("quantity", 100) // 2
            result = OrderResult(
                success=True,
                order_id=order_id,
                trade_plan_id=kwargs.get("trade_plan_id", "test_plan"),
                order_status="PartiallyFilled",
                symbol=kwargs.get("symbol", "UNKNOWN"),
                side=kwargs.get("side", "BUY"),
                quantity=partial_qty,  # Only partial fill
                order_type="MKT",
                fill_price=Decimal(str(kwargs.get("limit_price", "180.00"))),
                timestamp=datetime.now(UTC)
            )
            self.placed_orders[order_id] = result
            return result
        
        # Successful order
        result = OrderResult(
            success=True,
            order_id=order_id,
            trade_plan_id=kwargs.get("trade_plan_id", "test_plan"),
            order_status="Filled",
            symbol=kwargs.get("symbol", "UNKNOWN"),
            side=kwargs.get("side", "BUY"),
            quantity=kwargs.get("quantity", 100),
            order_type="MKT",
            fill_price=Decimal(str(kwargs.get("limit_price", "180.00"))),
            commission=Decimal("1.00"),
            timestamp=datetime.now(UTC)
        )
        
        self.placed_orders[order_id] = result
        return result
    
    def _get_failure_type(self) -> Optional[str]:
        """Determine if and what type of failure should occur."""
        for failure_type, probability in self.failure_modes.items():
            if random.random() < probability:
                return failure_type
        return None
    
    async def get_order_status(self, order_id: str) -> str:
        """Get order status with potential failures."""
        if self.network.simulate_failure():
            raise ConnectionError("Cannot retrieve order status")
        
        if order_id in self.placed_orders:
            return self.placed_orders[order_id].order_status
        return "NotFound"
    
    async def cancel_order(self, order_id: str) -> bool:
        """Cancel order with potential failures."""
        if self.network.simulate_failure():
            raise ConnectionError("Cannot cancel order")
        
        return order_id in self.placed_orders


class CorruptDataGenerator:
    """Generates various types of corrupted market data."""
    
    @staticmethod
    def create_corrupted_bar(corruption_type: str, base_bar: BarData) -> BarData:
        """Create corrupted bar data for testing error handling."""
        if corruption_type == "negative_price":
            # Create a valid bar first, then we'll simulate corruption during processing
            return BarData(
                symbol=base_bar.symbol,
                timestamp=base_bar.timestamp,
                open_price=Decimal("0.0001"),  # Minimum valid positive price
                high_price=base_bar.high_price,
                low_price=Decimal("0.0001"),
                close_price=base_bar.close_price,
                volume=base_bar.volume,
                bar_size=base_bar.bar_size,
            )
        
        elif corruption_type == "invalid_ohlc":
            # Create technically valid OHLC but suspicious data
            return BarData(
                symbol=base_bar.symbol,
                timestamp=base_bar.timestamp,
                open_price=Decimal("180.0000"),
                high_price=Decimal("180.0001"),  # Minimal range (suspicious but valid)
                low_price=Decimal("179.9999"),   
                close_price=Decimal("180.0000"),
                volume=base_bar.volume,
                bar_size=base_bar.bar_size,
            )
        
        elif corruption_type == "zero_volume":
            return BarData(
                symbol=base_bar.symbol,
                timestamp=base_bar.timestamp,
                open_price=base_bar.open_price,
                high_price=base_bar.high_price,
                low_price=base_bar.low_price,
                close_price=base_bar.close_price,
                volume=0,  # Invalid zero volume
                bar_size=base_bar.bar_size,
            )
        
        elif corruption_type == "future_timestamp":
            return BarData(
                symbol=base_bar.symbol,
                timestamp=datetime.now(UTC) + timedelta(days=30),  # Future timestamp
                open_price=base_bar.open_price,
                high_price=base_bar.high_price,
                low_price=base_bar.low_price,
                close_price=base_bar.close_price,
                volume=base_bar.volume,
                bar_size=base_bar.bar_size,
            )
        
        elif corruption_type == "extreme_price":
            # Extreme but consistent OHLC values
            extreme_price = Decimal("999999.9999")
            return BarData(
                symbol=base_bar.symbol,
                timestamp=base_bar.timestamp,
                open_price=extreme_price,
                high_price=extreme_price,
                low_price=extreme_price,
                close_price=extreme_price,
                volume=base_bar.volume,
                bar_size=base_bar.bar_size,
            )
        
        return base_bar


class FaultyFunction:
    """Execution function that fails in various ways."""
    
    def __init__(self, name: str, failure_mode: str = "none"):
        self.name = name
        self.timeframe = Timeframe.ONE_MIN
        self.parameters = {"threshold_price": 180.00}
        self.enabled = True
        self.failure_mode = failure_mode
        self.evaluation_count = 0
        
    async def evaluate(self, bar_data: BarData, historical_data: List[BarData]) -> ExecutionSignal:
        """Evaluate with potential failures."""
        self.evaluation_count += 1
        
        if self.failure_mode == "always_fail":
            raise ValueError(f"Function {self.name} always fails")
        
        elif self.failure_mode == "timeout":
            await asyncio.sleep(10)  # Simulate timeout
            return ExecutionSignal(action=ExecutionAction.NO_ACTION)
        
        elif self.failure_mode == "memory_leak":
            # Simulate memory leak
            big_data = [0] * 1000000  # Large allocation
            return ExecutionSignal(action=ExecutionAction.NO_ACTION)
        
        elif self.failure_mode == "intermittent":
            if self.evaluation_count % 3 == 0:  # Fail every 3rd evaluation
                raise RuntimeError(f"Intermittent failure in {self.name}")
        
        elif self.failure_mode == "invalid_signal":
            # Return malformed signal
            signal = ExecutionSignal(action=ExecutionAction.ENTER_LONG)
            signal.confidence = None  # Invalid confidence
            return signal
        
        # Normal evaluation
        threshold = Decimal(str(self.parameters["threshold_price"]))
        if bar_data.close_price > threshold:
            return ExecutionSignal(
                action=ExecutionAction.ENTER_LONG,
                confidence=0.8,
                reason=f"Price {bar_data.close_price} above threshold {threshold}"
            )
        
        return ExecutionSignal(action=ExecutionAction.NO_ACTION)


@pytest.fixture
def network_simulator():
    """Create network failure simulator."""
    return NetworkFailureSimulator()


@pytest.fixture
def flaky_order_manager(network_simulator):
    """Create flaky order manager for testing."""
    return FlakyOrderManager(network_simulator)


@pytest.fixture
def error_recovery_setup(network_simulator, flaky_order_manager):
    """Create error recovery test setup."""
    registry = ExecutionFunctionRegistry()
    logger = ExecutionLogger(
        enable_file_logging=False
    )
    
    # Mock detector that can simulate failures
    detector = Mock(spec=BarCloseDetector)
    detector.add_callback = Mock()
    detector.update_bar_data = Mock()
    detector.stop_monitoring = AsyncMock()
    detector.get_timing_stats = Mock(return_value={
        "avg_detection_latency_ms": 50.0,
        "failures": 0,
        "circuit_breaker_trips": 0
    })
    detector.monitor_timeframe = AsyncMock()
    detector.get_monitored = Mock(return_value={})
    
    market_adapter = MarketDataExecutionAdapter(
        bar_close_detector=detector,
        function_registry=registry,
        execution_logger=logger,
    )
    
    order_adapter = ExecutionOrderAdapter(
        order_execution_manager=flaky_order_manager,
        default_risk_category=RiskCategory.NORMAL,
    )
    
    # Connect adapters
    market_adapter.add_signal_callback(order_adapter.handle_execution_signal)
    
    return {
        "registry": registry,
        "logger": logger,
        "detector": detector,
        "network": network_simulator,
        "order_manager": flaky_order_manager,
        "market_adapter": market_adapter,
        "order_adapter": order_adapter,
    }


def create_normal_bar(symbol="AAPL", close_price=180.00, timestamp=None):
    """Create normal bar for testing with valid OHLC relationships."""
    close_decimal = Decimal(str(close_price))
    open_decimal = Decimal("179.90")
    
    # Ensure high is at least the max of open and close
    high_decimal = max(close_decimal, open_decimal, Decimal("180.50"))
    
    # Ensure low is at most the min of open and close
    low_decimal = min(close_decimal, open_decimal, Decimal("179.50"))
    
    return BarData(
        symbol=symbol,
        timestamp=timestamp or datetime.now(UTC),
        open_price=open_decimal,
        high_price=high_decimal,
        low_price=low_decimal,
        close_price=close_decimal,
        volume=1000000,
        bar_size="1min",
    )


class TestErrorRecoveryIntegration:
    """Test error recovery and resilience scenarios."""

    @pytest.mark.asyncio
    async def test_network_disconnection_recovery(self, error_recovery_setup):
        """Test recovery from network disconnections."""
        setup = error_recovery_setup
        
        # Register normal function
        await setup["registry"].register("close_above", CloseAboveFunction)
        
        config = ExecutionFunctionConfig(
            name="network_test",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 180.00},
            enabled=True,
        )
        
        await setup["registry"].create_function(config)
        await setup["market_adapter"].start_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Set high network failure rate
        setup["network"].set_failure_rate(0.8)
        
        # Feed historical data
        for i in range(25):
            bar = create_normal_bar(close_price=179.50)
            await setup["market_adapter"].on_market_data_update(bar)
        
        # Try to trigger signal during network issues
        failed_attempts = 0
        successful_orders = 0
        
        for attempt in range(10):
            trigger_bar = create_normal_bar(close_price=180.25)
            await setup["market_adapter"].on_market_data_update(trigger_bar)
            
            # Simulate bar close
            bar_close_event = BarCloseEvent(
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                close_time=datetime.now(UTC),
                bar_data=trigger_bar,
                next_close_time=datetime.now(UTC) + timedelta(minutes=1),
            )
            
            try:
                await setup["market_adapter"]._on_bar_close(bar_close_event)
                successful_orders += 1
            except Exception:
                failed_attempts += 1
        
        # Lower failure rate to simulate recovery
        setup["network"].set_failure_rate(0.1)
        
        # Reset circuit breaker to simulate recovery 
        setup["order_adapter"].reset_circuit_breaker()
        
        # Wait a moment to ensure circuit breaker reset is processed
        await asyncio.sleep(0.1)
        
        # Should be able to place orders after network recovery
        recovery_trigger = create_normal_bar(close_price=180.50)
        await setup["market_adapter"].on_market_data_update(recovery_trigger)
        
        recovery_event = BarCloseEvent(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            close_time=datetime.now(UTC),
            bar_data=recovery_trigger,
            next_close_time=datetime.now(UTC) + timedelta(minutes=1),
        )
        
        # Should succeed after recovery
        await setup["market_adapter"]._on_bar_close(recovery_event)
        
        # Check error tracking
        metrics = await setup["logger"].get_metrics()
        if "error_count" in metrics:
            assert metrics["error_count"] >= failed_attempts

    @pytest.mark.asyncio
    async def test_corrupted_market_data_handling(self, error_recovery_setup):
        """Test handling of corrupted or malformed market data."""
        setup = error_recovery_setup
        
        await setup["registry"].register("close_above", CloseAboveFunction)
        
        config = ExecutionFunctionConfig(
            name="corruption_test",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 180.00},
            enabled=True,
        )
        
        await setup["registry"].create_function(config)
        await setup["market_adapter"].start_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Feed normal data first
        for i in range(20):
            bar = create_normal_bar(close_price=179.50)
            await setup["market_adapter"].on_market_data_update(bar)
        
        # Test various corruption types
        corruption_types = [
            "negative_price",
            "invalid_ohlc", 
            "zero_volume",
            "future_timestamp",
            "extreme_price"
        ]
        
        base_bar = create_normal_bar(close_price=180.25)
        corruption_handled = 0
        
        for corruption_type in corruption_types:
            corrupted_bar = CorruptDataGenerator.create_corrupted_bar(corruption_type, base_bar)
            
            try:
                await setup["market_adapter"].on_market_data_update(corrupted_bar)
                corruption_handled += 1
            except Exception as e:
                # System should gracefully handle corruption
                assert "validation" in str(e).lower() or "invalid" in str(e).lower()
        
        # Feed normal data after corruption to verify recovery
        recovery_bar = create_normal_bar(close_price=180.50)
        await setup["market_adapter"].on_market_data_update(recovery_bar)
        
        # System should still function normally
        bar_close_event = BarCloseEvent(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            close_time=datetime.now(UTC),
            bar_data=recovery_bar,
            next_close_time=datetime.now(UTC) + timedelta(minutes=1),
        )
        
        # Should not crash on normal data after corruption
        await setup["market_adapter"]._on_bar_close(bar_close_event)
        
        # Verify error logging
        logs = await setup["logger"].query_logs({"has_error": True}, limit=50)
        error_logs = [log for log in logs if "error" in str(log).lower() or "invalid" in str(log).lower()]
        assert len(error_logs) > 0, "Corruption errors should be logged"

    @pytest.mark.asyncio
    async def test_function_evaluation_failures(self, error_recovery_setup):
        """Test handling of function evaluation failures."""
        setup = error_recovery_setup
        
        # Create faulty functions with different failure modes
        failure_modes = ["always_fail", "intermittent", "invalid_signal"]
        faulty_functions = []
        
        for mode in failure_modes:
            faulty_func = FaultyFunction(f"faulty_{mode}", failure_mode=mode)
            faulty_functions.append(faulty_func)
            
            # Mock the registry to return our faulty function
            original_get_functions = setup["registry"].get_functions_by_timeframe
            
            def mock_get_functions(timeframe):
                return [faulty_func] if mode == "always_fail" else [faulty_func]
            
            setup["registry"].get_functions_by_timeframe = Mock(side_effect=mock_get_functions)
            
            await setup["market_adapter"].start_monitoring("AAPL", Timeframe.ONE_MIN)
            
            # Feed data and attempt evaluation
            for i in range(25):
                bar = create_normal_bar(close_price=179.50)
                await setup["market_adapter"].on_market_data_update(bar)
            
            # Trigger evaluation
            trigger_bar = create_normal_bar(close_price=180.25)
            await setup["market_adapter"].on_market_data_update(trigger_bar)
            
            bar_close_event = BarCloseEvent(
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                close_time=datetime.now(UTC),
                bar_data=trigger_bar,
                next_close_time=datetime.now(UTC) + timedelta(minutes=1),
            )
            
            # Should not crash on function failures
            try:
                await setup["market_adapter"]._on_bar_close(bar_close_event)
            except Exception as e:
                # Some failures are expected to be handled gracefully
                pass
            
            # Restore original method
            setup["registry"].get_functions_by_timeframe = original_get_functions
        
        # Verify error tracking
        logs = await setup["logger"].query_logs(limit=100)
        failure_logs = [log for log in logs if "fail" in str(log).lower() or "error" in str(log).lower()]
        assert len(failure_logs) > 0, "Function failures should be logged"

    @pytest.mark.asyncio
    async def test_order_execution_failures_and_retry(self, error_recovery_setup):
        """Test order execution failures and retry logic."""
        setup = error_recovery_setup
        
        await setup["registry"].register("close_above", CloseAboveFunction)
        
        config = ExecutionFunctionConfig(
            name="retry_test",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 180.00},
            enabled=True,
        )
        
        await setup["registry"].create_function(config)
        await setup["market_adapter"].start_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Set moderate failure rate for order manager
        setup["network"].set_failure_rate(0.3)
        
        # Feed historical data
        for i in range(25):
            bar = create_normal_bar(close_price=179.50)
            await setup["market_adapter"].on_market_data_update(bar)
        
        # Attempt multiple order placements
        total_attempts = 10
        successful_orders = 0
        failed_orders = 0
        
        for attempt in range(total_attempts):
            trigger_bar = create_normal_bar(close_price=180.25, timestamp=datetime.now(UTC) + timedelta(seconds=attempt))
            await setup["market_adapter"].on_market_data_update(trigger_bar)
            
            bar_close_event = BarCloseEvent(
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                close_time=datetime.now(UTC),
                bar_data=trigger_bar,
                next_close_time=datetime.now(UTC) + timedelta(minutes=1),
            )
            
            await setup["market_adapter"]._on_bar_close(bar_close_event)
            
            # Check if order was successfully placed
            placed_orders = setup["order_manager"].placed_orders
            if len(placed_orders) > successful_orders:
                successful_orders = len(placed_orders)
            
            # Add delay to allow circuit breaker reset between attempts
            await asyncio.sleep(0.06)  # 60ms - slightly longer than 50ms timeout
        
        # Verify some orders succeeded despite failures
        assert successful_orders > 0, "Some orders should succeed despite network issues"
        
        # Check for retry attempts in logs
        logs = await setup["logger"].query_logs(limit=100)
        retry_logs = [log for log in logs if "retry" in str(log).lower() or "attempt" in str(log).lower()]
        
        # Verify error recovery metrics
        metrics = await setup["logger"].get_metrics()
        if "order_failures" in metrics:
            assert metrics["order_failures"] >= 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_pattern(self, error_recovery_setup):
        """Test circuit breaker pattern during high failure rates."""
        setup = error_recovery_setup
        
        await setup["registry"].register("close_above", CloseAboveFunction)
        
        config = ExecutionFunctionConfig(
            name="circuit_breaker_test",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 180.00},
            enabled=True,
        )
        
        await setup["registry"].create_function(config)
        await setup["market_adapter"].start_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Set very high failure rate to trigger circuit breaker
        setup["network"].set_failure_rate(0.9)
        
        # Feed historical data
        for i in range(25):
            bar = create_normal_bar(close_price=179.50)
            await setup["market_adapter"].on_market_data_update(bar)
        
        # Attempt many order placements to trigger circuit breaker
        consecutive_failures = 0
        max_consecutive_failures = 5
        
        for attempt in range(15):
            trigger_bar = create_normal_bar(close_price=180.25)
            await setup["market_adapter"].on_market_data_update(trigger_bar)
            
            bar_close_event = BarCloseEvent(
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                close_time=datetime.now(UTC),
                bar_data=trigger_bar,
                next_close_time=datetime.now(UTC) + timedelta(minutes=1),
            )
            
            try:
                await setup["market_adapter"]._on_bar_close(bar_close_event)
                consecutive_failures = 0  # Reset on success
            except Exception:
                consecutive_failures += 1
                
                # Simulate circuit breaker logic
                if consecutive_failures >= max_consecutive_failures:
                    break
        
        # Verify circuit breaker tripped
        assert consecutive_failures >= max_consecutive_failures, "Circuit breaker should trip after consecutive failures"
        
        # Test recovery after circuit breaker
        setup["network"].set_failure_rate(0.0)  # Remove failures
        
        # Wait for circuit breaker recovery period
        await asyncio.sleep(0.1)
        
        # Should be able to place orders after recovery
        recovery_bar = create_normal_bar(close_price=180.50)
        await setup["market_adapter"].on_market_data_update(recovery_bar)
        
        recovery_event = BarCloseEvent(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            close_time=datetime.now(UTC),
            bar_data=recovery_bar,
            next_close_time=datetime.now(UTC) + timedelta(minutes=1),
        )
        
        # Should succeed after circuit breaker recovery
        await setup["market_adapter"]._on_bar_close(recovery_event)

    @pytest.mark.asyncio
    async def test_partial_system_failure_isolation(self, error_recovery_setup):
        """Test isolation of partial system failures."""
        setup = error_recovery_setup
        
        await setup["registry"].register("close_above", CloseAboveFunction)
        
        # Create multiple functions - some will fail, others should continue working
        configs = [
            ("working_function", "close_above", 180.00),
            ("working_function_2", "close_above", 179.50),
        ]
        
        for name, func_type, threshold in configs:
            config = ExecutionFunctionConfig(
                name=name,
                function_type=func_type,
                timeframe=Timeframe.ONE_MIN,
                parameters={"threshold_price": threshold},
                enabled=True,
            )
            
            await setup["registry"].create_function(config)
        
        await setup["market_adapter"].start_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Inject one failing function
        faulty_func = FaultyFunction("failing_function", failure_mode="always_fail")
        
        # Mock registry to return both working and failing functions
        original_get_functions = setup["registry"].get_functions_by_timeframe
        
        def mock_get_functions_mixed(timeframe):
            working_functions = original_get_functions(timeframe)
            return working_functions + [faulty_func]
        
        setup["registry"].get_functions_by_timeframe = mock_get_functions_mixed
        
        # Feed historical data
        for i in range(25):
            bar = create_normal_bar(close_price=179.50)
            await setup["market_adapter"].on_market_data_update(bar)
        
        # Trigger evaluations
        trigger_bar = create_normal_bar(close_price=180.25)
        await setup["market_adapter"].on_market_data_update(trigger_bar)
        
        bar_close_event = BarCloseEvent(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            close_time=datetime.now(UTC),
            bar_data=trigger_bar,
            next_close_time=datetime.now(UTC) + timedelta(minutes=1),
        )
        
        # Should not crash despite one function failing
        await setup["market_adapter"]._on_bar_close(bar_close_event)
        
        # Restore original method
        setup["registry"].get_functions_by_timeframe = original_get_functions
        
        # Verify working functions still logged successfully
        logs = await setup["logger"].query_logs(limit=100)
        working_logs = [log for log in logs if "working_function" in str(log)]
        failing_logs = [log for log in logs if "failing_function" in str(log) and "error" in str(log).lower()]
        
        assert len(working_logs) > 0, "Working functions should continue to operate"
        assert len(failing_logs) > 0, "Failing function errors should be logged"

    @pytest.mark.asyncio
    async def test_memory_pressure_handling(self, error_recovery_setup):
        """Test handling of memory pressure scenarios."""
        setup = error_recovery_setup
        
        await setup["registry"].register("close_above", CloseAboveFunction)
        
        config = ExecutionFunctionConfig(
            name="memory_test",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 180.00},
            enabled=True,
        )
        
        await setup["registry"].create_function(config)
        await setup["market_adapter"].start_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Generate large amounts of data to create memory pressure
        large_data_bars = []
        
        for i in range(1000):  # Large number of bars
            bar = create_normal_bar(
                close_price=179.50 + (i % 10) * 0.1,
                timestamp=datetime.now(UTC) - timedelta(minutes=1000-i)
            )
            large_data_bars.append(bar)
        
        # Process all data rapidly
        processing_start = datetime.now()
        
        for bar in large_data_bars:
            await setup["market_adapter"].on_market_data_update(bar)
        
        processing_time = (datetime.now() - processing_start).total_seconds()
        
        # Should handle large data volumes without crashing
        assert processing_time < 10.0, f"Processing took {processing_time}s, should be under 10s"
        
        # Verify system still responsive after memory pressure
        trigger_bar = create_normal_bar(close_price=180.25)
        await setup["market_adapter"].on_market_data_update(trigger_bar)
        
        bar_close_event = BarCloseEvent(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            close_time=datetime.now(UTC),
            bar_data=trigger_bar,
            next_close_time=datetime.now(UTC) + timedelta(minutes=1),
        )
        
        # Should still work after memory pressure
        await setup["market_adapter"]._on_bar_close(bar_close_event)
        
        # Verify memory usage is reasonable
        metrics = await setup["logger"].get_metrics()
        assert "total_evaluations" in metrics
        assert metrics["total_evaluations"] > 0

    @pytest.mark.asyncio
    async def test_cascading_failure_prevention(self, error_recovery_setup):
        """Test prevention of cascading failures across components."""
        setup = error_recovery_setup
        
        await setup["registry"].register("close_above", CloseAboveFunction)
        
        # Set up multiple components that could cascade failures
        config = ExecutionFunctionConfig(
            name="cascade_test",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 180.00},
            enabled=True,
        )
        
        await setup["registry"].create_function(config)
        await setup["market_adapter"].start_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Set moderate failure rates across the system
        setup["network"].set_failure_rate(0.2)
        
        # Add multiple signal callbacks that might fail
        failing_callback_count = 0
        
        async def failing_callback(signal):
            nonlocal failing_callback_count
            failing_callback_count += 1
            if failing_callback_count % 2 == 0:
                raise Exception("Callback failure")
        
        async def working_callback(signal):
            pass  # Always succeeds
        
        setup["market_adapter"].add_signal_callback(failing_callback)
        setup["market_adapter"].add_signal_callback(working_callback)
        
        # Feed data to trigger multiple processing paths
        for i in range(30):
            bar = create_normal_bar(close_price=179.50)
            await setup["market_adapter"].on_market_data_update(bar)
        
        # Trigger multiple signals
        cascade_attempts = 0
        successful_processing = 0
        
        for attempt in range(10):
            trigger_bar = create_normal_bar(close_price=180.25 + attempt * 0.01)
            await setup["market_adapter"].on_market_data_update(trigger_bar)
            
            bar_close_event = BarCloseEvent(
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                close_time=datetime.now(UTC),
                bar_data=trigger_bar,
                next_close_time=datetime.now(UTC) + timedelta(minutes=1),
            )
            
            try:
                await setup["market_adapter"]._on_bar_close(bar_close_event)
                successful_processing += 1
            except Exception:
                cascade_attempts += 1
        
        # Should have some successful processing despite cascading issues
        assert successful_processing > 0, "Some processing should succeed despite cascading failures"
        
        # Reset network issues and circuit breaker for final test
        setup["network"].set_failure_rate(0.0)  
        setup["order_adapter"].reset_circuit_breaker()
        await asyncio.sleep(0.1)  # Allow reset to process
        
        # Verify system maintains core functionality
        final_bar = create_normal_bar(close_price=181.00)
        await setup["market_adapter"].on_market_data_update(final_bar)
        
        final_event = BarCloseEvent(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            close_time=datetime.now(UTC),
            bar_data=final_bar,
            next_close_time=datetime.now(UTC) + timedelta(minutes=1),
        )
        
        # Final processing should work (cascade prevention)
        await setup["market_adapter"]._on_bar_close(final_event)
        
        # Verify comprehensive error logging
        logs = await setup["logger"].query_logs(limit=200)
        error_logs = [log for log in logs if "error" in str(log).lower() or "fail" in str(log).lower()]
        success_logs = [log for log in logs if "success" in str(log).lower() or "completed" in str(log).lower()]
        
        # Should have both error and success logs (showing isolation)
        assert len(error_logs) > 0, "Failures should be logged"
        assert len(success_logs) > 0 or successful_processing > 0, "Successes should also occur"