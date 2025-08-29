"""Tests for ExecutionMetricsCalculator."""

import pytest
from datetime import datetime, UTC

from auto_trader.models.execution import ExecutionSignal, ExecutionLogEntry
from auto_trader.models.enums import ExecutionAction, Timeframe
from auto_trader.trade_engine.execution_metrics import ExecutionMetricsCalculator


@pytest.fixture
def calculator():
    """Create metrics calculator for testing."""
    return ExecutionMetricsCalculator()


@pytest.fixture
def sample_entry():
    """Create sample log entry."""
    return ExecutionLogEntry(
        timestamp=datetime.now(UTC),
        function_name="test_function",
        symbol="AAPL",
        timeframe=Timeframe.ONE_MIN,
        signal=ExecutionSignal(
            action=ExecutionAction.ENTER_LONG,
            confidence=0.75,
            reasoning="Test signal"
        ),
        duration_ms=15.5,
        context_snapshot={"test": "data"}
    )


@pytest.fixture
def error_entry():
    """Create error log entry."""
    return ExecutionLogEntry(
        timestamp=datetime.now(UTC),
        function_name="test_function",
        symbol="AAPL",
        timeframe=Timeframe.ONE_MIN,
        signal=ExecutionSignal(
            action=ExecutionAction.NONE,
            confidence=0.0,
            reasoning="Error occurred"
        ),
        duration_ms=0.1,
        context_snapshot={},
        error="Test error"
    )


class TestExecutionMetricsCalculator:
    """Test cases for metrics calculator."""

    def test_initial_state(self, calculator):
        """Test initial metrics state."""
        metrics = calculator.get_summary()
        
        assert metrics["total_evaluations"] == 0
        assert metrics["successful_evaluations"] == 0
        assert metrics["failed_evaluations"] == 0
        assert metrics["actions_triggered"] == 0
        assert metrics["avg_duration_ms"] == 0.0
        assert metrics["max_duration_ms"] == 0.0
        assert metrics["min_duration_ms"] == float("inf")

    def test_update_successful_entry(self, calculator, sample_entry):
        """Test updating metrics with successful entry."""
        calculator.update(sample_entry)
        
        metrics = calculator.get_summary()
        assert metrics["total_evaluations"] == 1
        assert metrics["successful_evaluations"] == 1
        assert metrics["failed_evaluations"] == 0
        assert metrics["actions_triggered"] == 1
        assert metrics["avg_duration_ms"] == 15.5
        assert metrics["max_duration_ms"] == 15.5
        assert metrics["min_duration_ms"] == 15.5

    def test_update_error_entry(self, calculator, error_entry):
        """Test updating metrics with error entry."""
        calculator.update(error_entry)
        
        metrics = calculator.get_summary()
        assert metrics["total_evaluations"] == 1
        assert metrics["successful_evaluations"] == 0
        assert metrics["failed_evaluations"] == 1
        assert metrics["actions_triggered"] == 0
        assert metrics["avg_duration_ms"] == 0.1

    def test_update_multiple_entries(self, calculator, sample_entry, error_entry):
        """Test updating with multiple entries."""
        # Add successful entry
        calculator.update(sample_entry)
        
        # Add error entry
        calculator.update(error_entry)
        
        metrics = calculator.get_summary()
        assert metrics["total_evaluations"] == 2
        assert metrics["successful_evaluations"] == 1
        assert metrics["failed_evaluations"] == 1
        assert metrics["actions_triggered"] == 1
        assert metrics["avg_duration_ms"] == (15.5 + 0.1) / 2

    def test_update_duration_metrics(self, calculator):
        """Test duration metrics calculations."""
        entries = [
            ExecutionLogEntry(
                timestamp=datetime.now(UTC),
                function_name="test",
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                signal=ExecutionSignal.no_action("test"),
                duration_ms=10.0,
                context_snapshot={}
            ),
            ExecutionLogEntry(
                timestamp=datetime.now(UTC),
                function_name="test",
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                signal=ExecutionSignal.no_action("test"),
                duration_ms=20.0,
                context_snapshot={}
            ),
            ExecutionLogEntry(
                timestamp=datetime.now(UTC),
                function_name="test",
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                signal=ExecutionSignal.no_action("test"),
                duration_ms=5.0,
                context_snapshot={}
            )
        ]
        
        for entry in entries:
            calculator.update(entry)
        
        metrics = calculator.get_summary()
        assert metrics["max_duration_ms"] == 20.0
        assert metrics["min_duration_ms"] == 5.0
        assert metrics["avg_duration_ms"] == (10.0 + 20.0 + 5.0) / 3

    def test_get_function_statistics_empty(self, calculator):
        """Test function statistics with no entries."""
        stats = calculator.get_function_statistics("nonexistent", [])
        
        assert stats["function"] == "nonexistent"
        assert stats["evaluations"] == 0
        assert stats["signals"] == 0
        assert stats["errors"] == 0
        assert stats["signal_rate"] == 0.0
        assert stats["error_rate"] == 0.0
        assert stats["avg_duration_ms"] == 0.0

    def test_get_function_statistics_with_data(self, calculator):
        """Test function statistics with data."""
        entries = [
            # Successful signal
            ExecutionLogEntry(
                timestamp=datetime.now(UTC),
                function_name="test_func",
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                signal=ExecutionSignal(
                    action=ExecutionAction.ENTER_LONG,
                    confidence=0.8,
                    reasoning="Signal triggered"
                ),
                duration_ms=12.0,
                context_snapshot={}
            ),
            # No action
            ExecutionLogEntry(
                timestamp=datetime.now(UTC),
                function_name="test_func",
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                signal=ExecutionSignal.no_action("No signal"),
                duration_ms=8.0,
                context_snapshot={}
            ),
            # Error
            ExecutionLogEntry(
                timestamp=datetime.now(UTC),
                function_name="test_func",
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                signal=ExecutionSignal.no_action("Error"),
                duration_ms=1.0,
                context_snapshot={},
                error="Test error"
            )
        ]
        
        stats = calculator.get_function_statistics("test_func", entries)
        
        assert stats["function"] == "test_func"
        assert stats["evaluations"] == 3
        assert stats["signals"] == 1
        assert stats["signal_rate"] == 1/3
        assert stats["errors"] == 1
        assert stats["error_rate"] == 1/3
        assert stats["avg_duration_ms"] == (12.0 + 8.0 + 1.0) / 3

    def test_get_all_function_statistics(self, calculator):
        """Test getting statistics for all functions."""
        entries = [
            ExecutionLogEntry(
                timestamp=datetime.now(UTC),
                function_name="func1",
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                signal=ExecutionSignal.no_action("test"),
                duration_ms=10.0,
                context_snapshot={}
            ),
            ExecutionLogEntry(
                timestamp=datetime.now(UTC),
                function_name="func2",
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                signal=ExecutionSignal.no_action("test"),
                duration_ms=15.0,
                context_snapshot={}
            ),
            ExecutionLogEntry(
                timestamp=datetime.now(UTC),
                function_name="func1",
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                signal=ExecutionSignal.no_action("test"),
                duration_ms=5.0,
                context_snapshot={}
            )
        ]
        
        stats = calculator.get_all_function_statistics(entries)
        
        assert "func1" in stats
        assert "func2" in stats
        assert stats["func1"]["evaluations"] == 2
        assert stats["func2"]["evaluations"] == 1

    def test_calculate_success_rate(self, calculator):
        """Test success rate calculation."""
        # Initially 0%
        assert calculator.calculate_success_rate() == 0.0
        
        # Add successful entry
        calculator.update(ExecutionLogEntry(
            timestamp=datetime.now(UTC),
            function_name="test",
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            signal=ExecutionSignal.no_action("test"),
            duration_ms=10.0,
            context_snapshot={}
        ))
        
        assert calculator.calculate_success_rate() == 100.0
        
        # Add error entry
        calculator.update(ExecutionLogEntry(
            timestamp=datetime.now(UTC),
            function_name="test",
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            signal=ExecutionSignal.no_action("test"),
            duration_ms=10.0,
            context_snapshot={},
            error="Error"
        ))
        
        assert calculator.calculate_success_rate() == 50.0

    def test_calculate_signal_rate(self, calculator):
        """Test signal rate calculation."""
        # Initially 0%
        assert calculator.calculate_signal_rate() == 0.0
        
        # Add entry with signal
        calculator.update(ExecutionLogEntry(
            timestamp=datetime.now(UTC),
            function_name="test",
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            signal=ExecutionSignal(
                action=ExecutionAction.ENTER_LONG,
                confidence=0.8,
                reasoning="Signal"
            ),
            duration_ms=10.0,
            context_snapshot={}
        ))
        
        assert calculator.calculate_signal_rate() == 100.0
        
        # Add entry without signal
        calculator.update(ExecutionLogEntry(
            timestamp=datetime.now(UTC),
            function_name="test",
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            signal=ExecutionSignal.no_action("No signal"),
            duration_ms=10.0,
            context_snapshot={}
        ))
        
        assert calculator.calculate_signal_rate() == 50.0

    def test_reset(self, calculator, sample_entry):
        """Test resetting metrics."""
        calculator.update(sample_entry)
        
        # Verify metrics are populated
        metrics = calculator.get_summary()
        assert metrics["total_evaluations"] > 0
        
        # Reset
        calculator.reset()
        
        # Verify back to initial state
        metrics = calculator.get_summary()
        assert metrics["total_evaluations"] == 0
        assert metrics["successful_evaluations"] == 0
        assert metrics["failed_evaluations"] == 0
        assert metrics["actions_triggered"] == 0
        assert metrics["avg_duration_ms"] == 0.0
        assert metrics["max_duration_ms"] == 0.0
        assert metrics["min_duration_ms"] == float("inf")

    def test_thread_safety(self, calculator):
        """Test that calculator is thread-safe."""
        import threading
        import time
        
        def add_entries():
            for i in range(100):
                entry = ExecutionLogEntry(
                    timestamp=datetime.now(UTC),
                    function_name="test",
                    symbol="AAPL",
                    timeframe=Timeframe.ONE_MIN,
                    signal=ExecutionSignal.no_action("test"),
                    duration_ms=10.0,
                    context_snapshot={}
                )
                calculator.update(entry)
        
        # Start multiple threads
        threads = []
        for _ in range(5):
            thread = threading.Thread(target=add_entries)
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # Should have 500 total evaluations
        metrics = calculator.get_summary()
        assert metrics["total_evaluations"] == 500
        assert metrics["successful_evaluations"] == 500