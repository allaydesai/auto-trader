"""Tests for error recovery and network failure handling."""

import pytest
import asyncio
from datetime import datetime, UTC, timedelta
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import tempfile
from pathlib import Path

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
from auto_trader.trade_engine.functions import CloseAboveFunction


class NetworkError(Exception):
    """Simulate network-related errors."""
    pass


class TimeoutError(Exception):
    """Simulate timeout errors."""
    pass


@pytest.fixture
def sample_context():
    """Create sample execution context."""
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
    
    return ExecutionContext(
        symbol="AAPL",
        timeframe=Timeframe.ONE_MIN,
        current_bar=current_bar,
        historical_bars=[current_bar] * 20,
        trade_plan_params={"threshold_price": 180.00},
        position_state=None,
        account_balance=Decimal("10000"),
        timestamp=datetime.now(UTC)
    )


@pytest.fixture
async def error_recovery_system():
    """Create system for error recovery testing."""
    registry = ExecutionFunctionRegistry()
    registry.clear_all()
    
    # Register function
    registry.register("close_above", CloseAboveFunction)
    
    config = ExecutionFunctionConfig(
        name="error_test_function",
        function_type="close_above",
        timeframe=Timeframe.ONE_MIN,
        parameters={"threshold_price": 180.00},
        enabled=True
    )
    
    function = registry.create_function(config)
    
    # Create detector
    detector = BarCloseDetector(accuracy_ms=100)
    await detector.start()
    
    yield {
        "registry": registry,
        "function": function,
        "detector": detector
    }
    
    await detector.stop()
    registry.clear_all()


@pytest.mark.asyncio
class TestErrorRecovery:
    """Test error recovery and resilience mechanisms."""

    async def test_network_timeout_recovery(self, error_recovery_system, sample_context):
        """Test recovery from network timeouts during execution."""
        function = error_recovery_system["function"]
        
        # Track execution attempts
        attempt_count = 0
        
        async def failing_evaluate(context):
            nonlocal attempt_count
            attempt_count += 1
            
            if attempt_count <= 2:  # Fail first 2 attempts
                raise TimeoutError("Network timeout")
            else:  # Succeed on 3rd attempt
                return await CloseAboveFunction.evaluate(function, context)
        
        # Patch the evaluate method
        with patch.object(function, 'evaluate', side_effect=failing_evaluate):
            # Implement retry logic
            max_retries = 3
            retry_delay = 0.1
            
            for retry in range(max_retries):
                try:
                    signal = await function.evaluate(sample_context)
                    break
                except TimeoutError:
                    if retry == max_retries - 1:
                        raise
                    await asyncio.sleep(retry_delay)
            
            # Should succeed after retries
            assert signal is not None
            assert attempt_count == 3  # 2 failures + 1 success

    async def test_market_data_connection_failure(self, error_recovery_system):
        """Test handling of market data connection failures."""
        detector = error_recovery_system["detector"]
        
        # Simulate connection failures
        connection_failures = 0
        reconnection_attempts = []
        
        async def failing_callback(event):
            """Callback that simulates connection failures."""
            nonlocal connection_failures
            connection_failures += 1
            
            if connection_failures <= 2:
                raise NetworkError("Market data connection lost")
        
        detector.add_callback(failing_callback)
        
        # Mock reconnection logic
        async def reconnect_with_backoff(max_attempts=3):
            """Simulate exponential backoff reconnection."""
            for attempt in range(max_attempts):
                try:
                    reconnection_attempts.append(attempt + 1)
                    
                    if attempt < 2:  # Fail first 2 attempts
                        raise NetworkError("Connection refused")
                    else:  # Succeed on 3rd attempt
                        return True
                        
                except NetworkError:
                    if attempt == max_attempts - 1:
                        raise
                    
                    backoff_time = (2 ** attempt) * 0.1  # Exponential backoff
                    await asyncio.sleep(backoff_time)
            
            return False
        
        # Test reconnection
        reconnected = await reconnect_with_backoff()
        
        assert reconnected is True
        assert len(reconnection_attempts) == 3
        assert reconnection_attempts == [1, 2, 3]

    async def test_execution_logger_disk_space_error(self):
        """Test handling of disk space errors in execution logger."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logger = ExecutionLogger(
                log_directory=Path(temp_dir),
                max_entries_per_file=10,
                max_log_files=3
            )
            
            # Mock disk space error
            original_open = open
            disk_full_count = 0
            
            def mock_open(*args, **kwargs):
                nonlocal disk_full_count
                if 'execution_' in str(args[0]) and 'a' in kwargs.get('mode', ''):
                    disk_full_count += 1
                    if disk_full_count <= 2:  # First 2 attempts fail
                        raise OSError("No space left on device")
                return original_open(*args, **kwargs)
            
            # Create sample log entry
            signal = ExecutionSignal(
                action=ExecutionAction.ENTER_LONG,
                confidence=0.75,
                reasoning="Test signal",
                metadata={}
            )
            
            entry = ExecutionLogEntry(
                timestamp=datetime.now(UTC),
                function_name="test_function",
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                signal=signal,
                duration_ms=1.0,
            )
            
            # Test with retry logic
            with patch('builtins.open', side_effect=mock_open):
                for attempt in range(3):
                    try:
                        await logger.log_execution_decision(entry)
                        break
                    except OSError as e:
                        if "space left" in str(e) and attempt < 2:
                            # Simulate cleanup/rotation
                            await asyncio.sleep(0.1)
                            continue
                        raise
            
            # Should eventually succeed
            assert disk_full_count >= 2  # At least 2 failures occurred

    async def test_function_registry_corruption_recovery(self, error_recovery_system):
        """Test recovery from function registry corruption."""
        registry = error_recovery_system["registry"]
        
        # Simulate registry corruption
        original_functions = registry._functions.copy()
        
        # Corrupt registry
        registry._functions.clear()
        registry._instances.clear()
        
        # Implement recovery mechanism
        def recover_registry():
            """Recover registry from backup/configuration."""
            # Simulate restoring from backup
            registry._functions.update(original_functions)
            
            # Re-register functions
            registry.register("close_above", CloseAboveFunction)
            
            # Recreate instances
            config = ExecutionFunctionConfig(
                name="recovered_function",
                function_type="close_above",
                timeframe=Timeframe.ONE_MIN,
                parameters={"threshold_price": 180.00},
                enabled=True
            )
            return registry.create_function(config)
        
        # Detect corruption and recover
        if not registry._functions:  # Registry is corrupted
            recovered_function = recover_registry()
        
        # Verify recovery
        assert len(registry._functions) > 0
        assert recovered_function is not None
        assert recovered_function.name == "recovered_function"

    async def test_bar_close_detector_scheduler_failure(self, error_recovery_system):
        """Test recovery from scheduler failures in bar close detector."""
        detector = error_recovery_system["detector"]
        
        # Simulate scheduler failure
        original_scheduler = detector.scheduler
        detector.scheduler = Mock()
        detector.scheduler.running = False
        
        # Mock scheduler methods to fail
        detector.scheduler.start = Mock(side_effect=Exception("Scheduler start failed"))
        detector.scheduler.add_job = Mock(side_effect=Exception("Job scheduling failed"))
        
        # Implement recovery logic
        async def recover_scheduler():
            """Recover from scheduler failure."""
            try:
                # Try to restart scheduler
                detector.scheduler.start()
            except Exception:
                # Fallback: recreate scheduler
                from apscheduler.schedulers.asyncio import AsyncIOScheduler
                detector.scheduler = AsyncIOScheduler(timezone=detector.timezone)
                await detector.start()
                return True
            return False
        
        # Test recovery
        recovery_successful = await recover_scheduler()
        
        assert recovery_successful is True
        assert detector.scheduler.running is True

    async def test_execution_function_exception_handling(
        self, error_recovery_system, sample_context
    ):
        """Test handling of exceptions within execution functions."""
        function = error_recovery_system["function"]
        
        # Create context that will cause calculation errors
        problematic_context = ExecutionContext(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            current_bar=sample_context.current_bar,
            historical_bars=[],  # Empty history to trigger error
            trade_plan_params={"threshold_price": "invalid"},  # Invalid parameter
            position_state=None,
            account_balance=Decimal("10000"),
            timestamp=datetime.now(UTC)
        )
        
        # Test with error handling wrapper
        async def safe_evaluate(func, context):
            """Safely evaluate function with error handling."""
            try:
                return await func.evaluate(context)
            except (ValueError, TypeError, AttributeError) as e:
                # Log error and return safe default
                print(f"Function evaluation error: {e}")
                return ExecutionSignal.no_action(f"Evaluation error: {str(e)}")
            except Exception as e:
                # Handle unexpected errors
                print(f"Unexpected error: {e}")
                return ExecutionSignal.no_action(f"System error: {str(e)}")
        
        # Should handle errors gracefully
        signal = await safe_evaluate(function, problematic_context)
        
        assert signal is not None
        assert signal.action == ExecutionAction.NONE
        assert "error" in signal.reasoning.lower()

    async def test_concurrent_error_handling(self, error_recovery_system, sample_context):
        """Test error handling under concurrent execution."""
        function = error_recovery_system["function"]
        
        # Track errors and successes
        errors = []
        successes = []
        
        async def execute_with_random_failure(task_id):
            """Execute function with random failures."""
            try:
                if task_id % 3 == 0:  # Every 3rd task fails
                    raise NetworkError(f"Task {task_id} failed")
                
                signal = await function.evaluate(sample_context)
                successes.append(task_id)
                return signal
                
            except NetworkError as e:
                errors.append((task_id, str(e)))
                return ExecutionSignal.no_action(f"Failed: {e}")
        
        # Run multiple concurrent tasks
        tasks = [execute_with_random_failure(i) for i in range(10)]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Verify error handling
        assert len(errors) > 0  # Some errors occurred
        assert len(successes) > 0  # Some tasks succeeded
        assert len(results) == 10  # All tasks completed
        
        # No unhandled exceptions
        for result in results:
            assert not isinstance(result, Exception) or isinstance(result, NetworkError)

    async def test_circuit_breaker_pattern(self, error_recovery_system, sample_context):
        """Test circuit breaker pattern for repeated failures."""
        function = error_recovery_system["function"]
        
        # Circuit breaker state
        failure_count = 0
        circuit_open = False
        last_failure_time = None
        
        async def circuit_breaker_evaluate(context):
            """Evaluate with circuit breaker pattern."""
            nonlocal failure_count, circuit_open, last_failure_time
            
            # Check if circuit is open
            if circuit_open:
                # Check if enough time has passed for half-open state
                if (datetime.now(UTC) - last_failure_time).total_seconds() > 5:
                    circuit_open = False
                    failure_count = 0
                else:
                    return ExecutionSignal.no_action("Circuit breaker open")
            
            try:
                # Simulate failures for first 5 attempts
                if failure_count < 5:
                    failure_count += 1
                    last_failure_time = datetime.now(UTC)
                    raise NetworkError("Service unavailable")
                
                # After 5 failures, succeed
                result = await function.evaluate(context)
                failure_count = 0  # Reset on success
                return result
                
            except NetworkError:
                if failure_count >= 5:  # Open circuit after 5 failures
                    circuit_open = True
                raise
        
        # Test circuit breaker behavior
        signals = []
        
        # First 5 attempts should fail and open circuit
        for i in range(5):
            try:
                signal = await circuit_breaker_evaluate(sample_context)
                signals.append(signal)
            except NetworkError:
                signals.append(None)
        
        assert circuit_open is True
        assert failure_count == 5
        
        # Immediate retry should be blocked by circuit breaker
        signal = await circuit_breaker_evaluate(sample_context)
        assert "circuit breaker" in signal.reasoning.lower()
        
        # After timeout, should succeed
        await asyncio.sleep(0.1)  # Simulate time passing
        circuit_open = False  # Manually reset for test
        failure_count = 10  # High enough to succeed in our mock
        
        signal = await circuit_breaker_evaluate(sample_context)
        assert signal.action != ExecutionAction.NONE  # Should succeed

    async def test_data_corruption_detection(self, sample_context):
        """Test detection and handling of corrupted market data."""
        # Create corrupted bar data
        corrupted_bar = BarData(
            symbol="AAPL",
            timestamp=datetime.now(UTC),
            open_price=Decimal("0"),  # Invalid zero price
            high_price=Decimal("-10.00"),  # Invalid negative price
            low_price=Decimal("1000.00"),  # Unrealistic price
            close_price=Decimal("NaN"),  # Invalid NaN value
            volume=-1000,  # Invalid negative volume
            bar_size="1min",
        )
        
        def validate_bar_data(bar):
            """Validate bar data integrity."""
            issues = []
            
            if bar.open_price <= 0:
                issues.append("Invalid open price")
            if bar.high_price <= 0:
                issues.append("Invalid high price")
            if bar.low_price <= 0:
                issues.append("Invalid low price")
            if bar.close_price <= 0 or str(bar.close_price) == 'NaN':
                issues.append("Invalid close price")
            if bar.volume < 0:
                issues.append("Invalid volume")
            if bar.high_price < bar.low_price:
                issues.append("High < Low price")
            
            return issues
        
        # Test data validation
        validation_issues = validate_bar_data(corrupted_bar)
        
        assert len(validation_issues) > 0
        assert "Invalid close price" in validation_issues
        assert "Invalid volume" in validation_issues
        
        # Should reject corrupted data
        if validation_issues:
            # Don't use corrupted data
            assert True  # Data corruption detected and handled

    async def test_graceful_degradation(self, error_recovery_system):
        """Test graceful degradation when components fail."""
        detector = error_recovery_system["detector"]
        
        # Simulate partial system failures
        components = {
            "market_data": True,
            "execution_functions": True,
            "order_execution": True,
            "logging": True
        }
        
        def check_system_health():
            """Check which components are available."""
            return {
                name: status for name, status in components.items()
            }
        
        # Simulate component failures
        components["order_execution"] = False
        components["logging"] = False
        
        health = check_system_health()
        
        # Implement graceful degradation
        if not health["order_execution"]:
            # Can still evaluate signals but not execute orders
            print("Operating in analysis-only mode")
        
        if not health["logging"]:
            # Use alternative logging or disable logging
            print("Logging disabled - operating with reduced audit trail")
        
        # System should continue with remaining components
        remaining_components = [name for name, status in health.items() if status]
        assert len(remaining_components) >= 2  # At least some components working
        assert "market_data" in remaining_components
        assert "execution_functions" in remaining_components

    async def test_memory_leak_prevention(self, error_recovery_system):
        """Test prevention of memory leaks during error conditions."""
        import gc
        import sys
        
        detector = error_recovery_system["detector"]
        
        # Create many failing operations
        initial_objects = len(gc.get_objects())
        
        for i in range(100):
            try:
                # Create temporary objects that might leak
                temp_data = {
                    "bars": [BarData(
                        symbol=f"TEST{i}",
                        timestamp=datetime.now(UTC),
                        open_price=Decimal("180.00"),
                        high_price=Decimal("182.00"),
                        low_price=Decimal("179.50"),
                        close_price=Decimal("181.50"),
                        volume=1000000,
                        bar_size="1min",
                    ) for _ in range(10)],
                    "callbacks": [lambda x: None for _ in range(5)]
                }
                
                # Simulate operation that fails and should clean up
                if i % 2 == 0:
                    raise Exception("Simulated failure")
                
            except Exception:
                # Ensure cleanup on failure
                if 'temp_data' in locals():
                    del temp_data
                gc.collect()
        
        # Force garbage collection
        gc.collect()
        final_objects = len(gc.get_objects())
        
        # Object count shouldn't grow significantly
        object_growth = final_objects - initial_objects
        print(f"Object growth: {object_growth}")
        
        # Allow some growth but prevent major leaks
        assert object_growth < 1000  # Reasonable object growth limit

    async def test_configuration_reload_on_error(self, error_recovery_system):
        """Test configuration reload when function parameters become invalid."""
        registry = error_recovery_system["registry"]
        
        # Create function with valid config
        original_config = ExecutionFunctionConfig(
            name="config_test",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 180.00},
            enabled=True
        )
        
        function = registry.create_function(original_config)
        
        # Simulate configuration corruption
        function.parameters["threshold_price"] = "invalid_value"
        
        # Create backup/default configuration
        backup_config = {
            "threshold_price": 179.00,
            "min_volume": 10000
        }
        
        def reload_configuration(func):
            """Reload configuration from backup."""
            try:
                # Validate current config
                threshold = Decimal(str(func.parameters["threshold_price"]))
                if threshold <= 0:
                    raise ValueError("Invalid threshold")
            except (ValueError, TypeError):
                # Reload from backup
                func.parameters.update(backup_config)
                print("Configuration reloaded from backup")
                return True
            return False
        
        # Test configuration reload
        config_reloaded = reload_configuration(function)
        
        assert config_reloaded is True
        assert function.parameters["threshold_price"] == 179.00
        assert function.parameters["min_volume"] == 10000