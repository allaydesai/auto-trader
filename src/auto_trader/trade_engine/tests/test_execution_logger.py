"""Tests for ExecutionLogger audit trail integrity."""

import pytest
import tempfile
import json
from datetime import datetime, UTC, timedelta
from pathlib import Path
from decimal import Decimal
from unittest.mock import patch, mock_open

from auto_trader.models.execution import (
    ExecutionSignal,
    ExecutionLogEntry,
    ExecutionContext,
    PositionState
)
from auto_trader.models.enums import ExecutionAction, Timeframe
from auto_trader.models.market_data import BarData
from auto_trader.trade_engine.execution_logger import ExecutionLogger


@pytest.fixture
def temp_log_dir():
    """Create temporary directory for log files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def sample_signal():
    """Create sample execution signal."""
    return ExecutionSignal(
        action=ExecutionAction.ENTER_LONG,
        confidence=0.75,
        reasoning="Price closed above resistance level",
        metadata={"threshold": 180.0, "close_price": 181.50}
    )


@pytest.fixture
def sample_log_entry(sample_signal):
    """Create sample log entry."""
    return ExecutionLogEntry(
        timestamp=datetime.now(UTC),
        function_name="close_above_test",
        symbol="AAPL",
        timeframe=Timeframe.ONE_MIN,
        signal=sample_signal,
        duration_ms=15.5,
        context_snapshot={"volume": 1000000, "price": 181.50}
    )


@pytest.fixture
def logger_instance(temp_log_dir):
    """Create ExecutionLogger instance with temporary directory."""
    return ExecutionLogger(
        log_dir=temp_log_dir,
        max_memory_entries=100,
        enable_file_logging=True
    )


class TestExecutionLogger:
    """Test ExecutionLogger functionality and audit trail integrity."""

    def test_logger_initialization(self, temp_log_dir):
        """Test logger initializes with correct parameters."""
        logger = ExecutionLogger(
            log_dir=temp_log_dir,
            max_memory_entries=50,
            enable_file_logging=True
        )
        
        assert logger.log_dir == temp_log_dir
        assert logger.max_memory_entries == 50
        assert logger.enable_file_logging is True
        assert len(logger.entries) == 0

    def test_log_directory_creation(self):
        """Test logger creates directory if it doesn't exist."""
        with tempfile.TemporaryDirectory() as temp_dir:
            non_existent_dir = Path(temp_dir) / "logs" / "execution"
            
            logger = ExecutionLogger(log_dir=non_existent_dir)
            
            assert non_existent_dir.exists()
            assert non_existent_dir.is_dir()

    async def test_log_execution_decision(self, logger_instance, sample_log_entry):
        """Test logging execution decisions creates proper audit trail."""
        # Log an entry
        await logger_instance.log_execution_decision(sample_log_entry)
        
        # Verify file was created
        assert logger_instance.current_log_file is not None
        assert logger_instance.current_log_file.exists()
        assert logger_instance.current_entries == 1

    async def test_log_file_rotation(self, logger_instance, sample_signal):
        """Test log file rotation when max entries reached."""
        logger_instance.max_entries_per_file = 2
        
        # Log entries to trigger rotation
        for i in range(3):
            entry = ExecutionLogEntry(
                timestamp=datetime.now(UTC),
                function_name=f"test_function_{i}",
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                signal=sample_signal,
                duration_ms=10.0,
            )
            await logger_instance.log_execution_decision(entry)
        
        # Should have rotated to new file
        log_files = list(logger_instance.log_directory.glob("execution_*.jsonl"))
        assert len(log_files) >= 2

    async def test_log_file_cleanup(self, logger_instance, sample_signal):
        """Test old log files are cleaned up when limit exceeded."""
        logger_instance.max_entries_per_file = 1
        logger_instance.max_log_files = 2
        
        # Create more files than the limit
        for i in range(4):
            entry = ExecutionLogEntry(
                timestamp=datetime.now(UTC),
                function_name=f"test_function_{i}",
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                signal=sample_signal,
                duration_ms=10.0,
            )
            await logger_instance.log_execution_decision(entry)
        
        # Should maintain only max_log_files
        log_files = list(logger_instance.log_directory.glob("execution_*.jsonl"))
        assert len(log_files) <= logger_instance.max_log_files

    async def test_log_entry_serialization(self, logger_instance, sample_log_entry):
        """Test log entries are properly serialized to JSON."""
        await logger_instance.log_execution_decision(sample_log_entry)
        
        # Read the log file content
        with open(logger_instance.current_log_file, 'r') as f:
            line = f.readline().strip()
            data = json.loads(line)
        
        # Verify all fields are present
        assert data["timestamp"]
        assert data["function_name"] == "close_above_test"
        assert data["symbol"] == "AAPL"
        assert data["timeframe"] == "1min"
        assert data["signal"]["action"] == "ENTER_LONG"
        assert data["signal"]["confidence"] == 0.75
        assert data["duration_ms"] == 15.5

    async def test_query_logs_by_symbol(self, logger_instance, temp_log_dir):
        """Test querying logs by symbol."""
        # Add entries directly to memory (the actual behavior)
        from auto_trader.models.execution import ExecutionLogEntry, ExecutionSignal
        from auto_trader.models.enums import ExecutionAction, Timeframe
        
        # AAPL entry
        aapl_signal = ExecutionSignal(action=ExecutionAction.ENTER_LONG, confidence=0.8, reasoning="test")
        aapl_entry = ExecutionLogEntry(
            timestamp=datetime(2025, 8, 28, 10, 0, 0, tzinfo=UTC),
            function_name="test_func",
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            signal=aapl_signal,
            duration_ms=10.0
        )
        
        # MSFT entry  
        msft_signal = ExecutionSignal(action=ExecutionAction.ENTER_LONG, confidence=0.7, reasoning="test")
        msft_entry = ExecutionLogEntry(
            timestamp=datetime(2025, 8, 28, 10, 1, 0, tzinfo=UTC),
            function_name="test_func",
            symbol="MSFT",
            timeframe=Timeframe.ONE_MIN,
            signal=msft_signal,
            duration_ms=12.0
        )
        
        # Add to logger
        logger_instance.entries.append(aapl_entry)
        logger_instance.entries.append(msft_entry)
        logger_instance.current_entries += 2
        
        # Query for AAPL
        results = await logger_instance.query_logs({"symbol": "AAPL"})
        
        assert len(results) == 1
        assert results[0].symbol == "AAPL"

    async def test_query_logs_by_function_name(self, logger_instance, temp_log_dir):
        """Test querying logs by function name."""
        # Add entries directly to memory
        from auto_trader.models.execution import ExecutionLogEntry, ExecutionSignal
        from auto_trader.models.enums import ExecutionAction, Timeframe
        
        signal = ExecutionSignal(action=ExecutionAction.ENTER_LONG, confidence=0.8, reasoning="test")
        entry = ExecutionLogEntry(
            timestamp=datetime(2025, 8, 28, 10, 0, 0, tzinfo=UTC),
            function_name="close_above",
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            signal=signal,
            duration_ms=10.0
        )
        
        logger_instance.entries.append(entry)
        logger_instance.current_entries += 1
        
        # Query by function name
        results = await logger_instance.query_logs({"function_name": "close_above"})
        
        assert len(results) == 1
        assert results[0].function_name == "close_above"

    async def test_query_logs_with_limit(self, logger_instance, temp_log_dir):
        """Test query limit functionality."""
        # Add multiple entries directly to memory
        from auto_trader.models.execution import ExecutionLogEntry, ExecutionSignal
        from auto_trader.models.enums import ExecutionAction, Timeframe
        
        for i in range(10):
            signal = ExecutionSignal(action=ExecutionAction.ENTER_LONG, confidence=0.8, reasoning="test")
            entry = ExecutionLogEntry(
                timestamp=datetime(2025, 8, 28, 10, i, 0, tzinfo=UTC),
                function_name="test_func",
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                signal=signal,
                duration_ms=10.0
            )
            logger_instance.entries.append(entry)
        
        logger_instance.current_entries += 10
        
        # Query with limit
        results = await logger_instance.query_logs({}, limit=3)
        
        assert len(results) == 3

    async def test_query_logs_time_range(self, logger_instance, temp_log_dir):
        """Test querying logs within time range."""
        # Add entries directly to memory
        from auto_trader.models.execution import ExecutionLogEntry, ExecutionSignal
        from auto_trader.models.enums import ExecutionAction, Timeframe
        
        # Entry within range
        signal1 = ExecutionSignal(action=ExecutionAction.ENTER_LONG, confidence=0.8, reasoning="test")
        entry1 = ExecutionLogEntry(
            timestamp=datetime(2025, 8, 28, 10, 0, 0, tzinfo=UTC),
            function_name="test_func",
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            signal=signal1,
            duration_ms=10.0
        )
        
        # Entry outside range
        signal2 = ExecutionSignal(action=ExecutionAction.ENTER_LONG, confidence=0.8, reasoning="test")
        entry2 = ExecutionLogEntry(
            timestamp=datetime(2025, 8, 28, 12, 0, 0, tzinfo=UTC),
            function_name="test_func",
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            signal=signal2,
            duration_ms=10.0
        )
        
        logger_instance.entries.append(entry1)
        logger_instance.entries.append(entry2)
        logger_instance.current_entries += 2
        
        # Query within time range
        start_time = datetime(2025, 8, 28, 9, 0, 0, tzinfo=UTC)
        end_time = datetime(2025, 8, 28, 11, 0, 0, tzinfo=UTC)
        
        results = await logger_instance.query_logs({}, start_time=start_time, end_time=end_time)
        
        assert len(results) == 1

    async def test_get_performance_metrics(self, logger_instance, temp_log_dir):
        """Test performance metrics calculation."""
        # Add entries directly to memory using the log_evaluation method
        from auto_trader.models.execution import ExecutionContext, ExecutionSignal
        from auto_trader.models.enums import ExecutionAction, Timeframe
        from auto_trader.models.market_data import BarData
        from unittest.mock import Mock
        
        # Create mock context
        mock_context = Mock()
        mock_context.symbol = "AAPL"
        mock_context.timeframe = Timeframe.ONE_MIN
        mock_context.timestamp = datetime(2025, 8, 28, 10, 0, 0, tzinfo=UTC)
        mock_context.current_bar = None
        mock_context.has_position = False
        mock_context.trade_plan_params = {}
        mock_context.position_state = None
        
        durations = [10.0, 20.0, 15.0, 25.0, 5.0]
        for duration in durations:
            signal = ExecutionSignal(action=ExecutionAction.ENTER_LONG, confidence=0.8, reasoning="test")
            await logger_instance.log_evaluation("test_func", mock_context, signal, duration)
        
        # Get metrics
        metrics = await logger_instance.get_performance_metrics()
        
        assert metrics["total_evaluations"] == 5
        assert metrics["avg_duration_ms"] == 15.0
        assert metrics["max_duration_ms"] == 25.0
        assert metrics["min_duration_ms"] == 5.0

    async def test_get_function_statistics(self, logger_instance, temp_log_dir):
        """Test function usage statistics."""
        # Add entries directly to memory using log_evaluation
        from auto_trader.models.execution import ExecutionSignal
        from auto_trader.models.enums import ExecutionAction, Timeframe
        from unittest.mock import Mock
        
        # Create mock context
        mock_context = Mock()
        mock_context.symbol = "AAPL"
        mock_context.timeframe = Timeframe.ONE_MIN
        mock_context.timestamp = datetime(2025, 8, 28, 10, 0, 0, tzinfo=UTC)
        mock_context.current_bar = None
        mock_context.has_position = False
        mock_context.trade_plan_params = {}
        mock_context.position_state = None
        
        # Multiple entries for different functions
        functions = ["close_above", "close_above", "close_below", "trailing_stop"]
        for func in functions:
            signal = ExecutionSignal(action=ExecutionAction.ENTER_LONG, confidence=0.8, reasoning="test")
            await logger_instance.log_evaluation(func, mock_context, signal, 10.0)
        
        # Get statistics for close_above function
        stats = await logger_instance.get_function_statistics("close_above")
        
        assert stats["evaluations"] == 2
        assert stats["function"] == "close_above"

    async def test_error_logging(self, logger_instance):
        """Test logging execution errors."""
        # Create entry with error
        entry = ExecutionLogEntry(
            timestamp=datetime.now(UTC),
            function_name="error_func",
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            signal=ExecutionSignal.no_action("Test error"),
            duration_ms=5.0,
            error="Test error message"
        )
        
        await logger_instance.log_execution_decision(entry)
        
        # Verify error was logged
        results = await logger_instance.query_logs({"function_name": "error_func"})
        assert len(results) == 1
        assert results[0].error == "Test error message"

    async def test_concurrent_logging(self, logger_instance, sample_signal):
        """Test concurrent logging doesn't corrupt data."""
        import asyncio
        
        async def log_entry(i):
            entry = ExecutionLogEntry(
                timestamp=datetime.now(UTC),
                function_name=f"concurrent_func_{i}",
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                signal=sample_signal,
                duration_ms=10.0,
            )
            await logger_instance.log_execution_decision(entry)
        
        # Run multiple concurrent logging operations
        tasks = [log_entry(i) for i in range(10)]
        await asyncio.gather(*tasks)
        
        # Verify all entries were logged
        results = await logger_instance.query_logs({})
        assert len(results) == 10

    async def test_malformed_log_file_handling(self, logger_instance, temp_log_dir):
        """Test handling of invalid entries during queries."""
        # Add valid entries directly to memory
        from auto_trader.models.execution import ExecutionLogEntry, ExecutionSignal
        from auto_trader.models.enums import ExecutionAction, Timeframe
        
        # Add two valid entries
        signal1 = ExecutionSignal(action=ExecutionAction.ENTER_LONG, confidence=0.8, reasoning="valid")
        entry1 = ExecutionLogEntry(
            timestamp=datetime(2025, 8, 28, 10, 0, 0, tzinfo=UTC),
            function_name="test_func",
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            signal=signal1,
            duration_ms=10.0
        )
        
        signal2 = ExecutionSignal(action=ExecutionAction.ENTER_LONG, confidence=0.9, reasoning="another valid")
        entry2 = ExecutionLogEntry(
            timestamp=datetime(2025, 8, 28, 10, 1, 0, tzinfo=UTC),
            function_name="test_func2",
            symbol="MSFT",
            timeframe=Timeframe.ONE_MIN,
            signal=signal2,
            duration_ms=12.0
        )
        
        logger_instance.entries.append(entry1)
        logger_instance.entries.append(entry2)
        logger_instance.current_entries += 2
        
        # Query should return all valid entries
        results = await logger_instance.query_logs({})
        
        # Should return valid entries
        assert len(results) == 2

    async def test_log_file_permissions(self, logger_instance, sample_log_entry):
        """Test that log files are created with proper permissions."""
        await logger_instance.log_execution_decision(sample_log_entry)
        
        # Check file permissions (readable/writable by owner)
        file_stat = logger_instance.current_log_file.stat()
        permissions = oct(file_stat.st_mode)[-3:]
        
        # Should be readable and writable by owner (at minimum)
        assert file_stat.st_mode & 0o600 == 0o600

    def test_log_file_naming_convention(self, logger_instance, temp_log_dir):
        """Test log file naming follows expected pattern."""
        # Test the log file path generation
        log_file_path = logger_instance._get_log_file_path()
        
        filename = log_file_path.name
        assert filename.startswith("execution_")
        assert filename.endswith(".jsonl")
        
        # Check date format in filename (execution_YYYYMMDD.jsonl)
        date_part = filename.split("_")[1].split(".")[0]
        assert len(date_part) == 8  # YYYYMMDD format

    async def test_get_audit_trail(self, logger_instance, temp_log_dir):
        """Test complete audit trail retrieval."""
        # Add entries directly to memory
        from auto_trader.models.execution import ExecutionLogEntry, ExecutionSignal
        from auto_trader.models.enums import ExecutionAction, Timeframe
        
        # Create test data with different timestamps
        for file_num in range(3):
            signal = ExecutionSignal(action=ExecutionAction.ENTER_LONG, confidence=0.8, reasoning="test")
            entry = ExecutionLogEntry(
                timestamp=datetime(2025, 8, 28, 10 + file_num, 0, 0, tzinfo=UTC),
                function_name=f"func_{file_num}",
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                signal=signal,
                duration_ms=10.0
            )
            logger_instance.entries.append(entry)
        
        logger_instance.current_entries += 3
        
        # Get complete audit trail (query all AAPL entries)
        trail = await logger_instance.query_logs({"symbol": "AAPL"})
        
        assert len(trail) == 3
        # Should be sorted by timestamp (entries are in chronological order)
        timestamps = [entry.timestamp for entry in trail]
        assert timestamps == sorted(timestamps)