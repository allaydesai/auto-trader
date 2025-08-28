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

    def test_query_logs_by_symbol(self, logger_instance, temp_log_dir):
        """Test querying logs by symbol."""
        # Create test log file with multiple entries
        log_file = temp_log_dir / "execution_test.jsonl"
        with open(log_file, 'w') as f:
            # AAPL entry
            entry1 = {
                "timestamp": "2025-08-28T10:00:00Z",
                "function_name": "test_func",
                "symbol": "AAPL",
                "timeframe": "1min",
                "signal": {"action": "ENTER_LONG", "confidence": 0.8, "reasoning": "test"},
                "duration_ms": 10.0
            }
            # MSFT entry
            entry2 = {
                "timestamp": "2025-08-28T10:01:00Z",
                "function_name": "test_func",
                "symbol": "MSFT",
                "timeframe": "1min",
                "signal": {"action": "ENTER_LONG", "confidence": 0.7, "reasoning": "test"},
                "duration_ms": 12.0
            }
            f.write(json.dumps(entry1) + "\n")
            f.write(json.dumps(entry2) + "\n")
        
        # Query for AAPL
        results = logger_instance.query_logs({"symbol": "AAPL"})
        
        assert len(results) == 1
        assert results[0]["symbol"] == "AAPL"

    def test_query_logs_by_function_name(self, logger_instance, temp_log_dir):
        """Test querying logs by function name."""
        # Create test log file
        log_file = temp_log_dir / "execution_test.jsonl"
        with open(log_file, 'w') as f:
            entry = {
                "timestamp": "2025-08-28T10:00:00Z",
                "function_name": "close_above",
                "symbol": "AAPL",
                "timeframe": "1min",
                "signal": {"action": "ENTER_LONG", "confidence": 0.8, "reasoning": "test"},
                "duration_ms": 10.0
            }
            f.write(json.dumps(entry) + "\n")
        
        # Query by function name
        results = logger_instance.query_logs({"function_name": "close_above"})
        
        assert len(results) == 1
        assert results[0]["function_name"] == "close_above"

    def test_query_logs_with_limit(self, logger_instance, temp_log_dir):
        """Test query limit functionality."""
        # Create test log file with multiple entries
        log_file = temp_log_dir / "execution_test.jsonl"
        with open(log_file, 'w') as f:
            for i in range(10):
                entry = {
                    "timestamp": f"2025-08-28T10:{i:02d}:00Z",
                    "function_name": "test_func",
                    "symbol": "AAPL",
                    "timeframe": "1min",
                    "signal": {"action": "ENTER_LONG", "confidence": 0.8, "reasoning": "test"},
                    "duration_ms": 10.0
                }
                f.write(json.dumps(entry) + "\n")
        
        # Query with limit
        results = logger_instance.query_logs({}, limit=3)
        
        assert len(results) == 3

    def test_query_logs_time_range(self, logger_instance, temp_log_dir):
        """Test querying logs within time range."""
        # Create test log file
        log_file = temp_log_dir / "execution_test.jsonl"
        with open(log_file, 'w') as f:
            # Entry within range
            entry1 = {
                "timestamp": "2025-08-28T10:00:00Z",
                "function_name": "test_func",
                "symbol": "AAPL",
                "timeframe": "1min",
                "signal": {"action": "ENTER_LONG", "confidence": 0.8, "reasoning": "test"},
                "duration_ms": 10.0
            }
            # Entry outside range
            entry2 = {
                "timestamp": "2025-08-28T12:00:00Z",
                "function_name": "test_func",
                "symbol": "AAPL",
                "timeframe": "1min",
                "signal": {"action": "ENTER_LONG", "confidence": 0.8, "reasoning": "test"},
                "duration_ms": 10.0
            }
            f.write(json.dumps(entry1) + "\n")
            f.write(json.dumps(entry2) + "\n")
        
        # Query within time range
        start_time = datetime(2025, 8, 28, 9, 0, 0, tzinfo=UTC)
        end_time = datetime(2025, 8, 28, 11, 0, 0, tzinfo=UTC)
        
        results = logger_instance.query_logs({}, start_time=start_time, end_time=end_time)
        
        assert len(results) == 1

    def test_get_performance_metrics(self, logger_instance, temp_log_dir):
        """Test performance metrics calculation."""
        # Create test log file with performance data
        log_file = temp_log_dir / "execution_test.jsonl"
        with open(log_file, 'w') as f:
            durations = [10.0, 20.0, 15.0, 25.0, 5.0]
            for i, duration in enumerate(durations):
                entry = {
                    "timestamp": f"2025-08-28T10:{i:02d}:00Z",
                    "function_name": "test_func",
                    "symbol": "AAPL",
                    "timeframe": "1min",
                    "signal": {"action": "ENTER_LONG", "confidence": 0.8, "reasoning": "test"},
                    "duration_ms": duration
                }
                f.write(json.dumps(entry) + "\n")
        
        # Get metrics
        metrics = logger_instance.get_performance_metrics()
        
        assert metrics["total_evaluations"] == 5
        assert metrics["avg_duration_ms"] == 15.0
        assert metrics["max_duration_ms"] == 25.0
        assert metrics["min_duration_ms"] == 5.0

    def test_get_function_statistics(self, logger_instance, temp_log_dir):
        """Test function usage statistics."""
        # Create test log file
        log_file = temp_log_dir / "execution_test.jsonl"
        with open(log_file, 'w') as f:
            # Multiple entries for different functions
            functions = ["close_above", "close_above", "close_below", "trailing_stop"]
            for i, func in enumerate(functions):
                entry = {
                    "timestamp": f"2025-08-28T10:{i:02d}:00Z",
                    "function_name": func,
                    "symbol": "AAPL",
                    "timeframe": "1min",
                    "signal": {"action": "ENTER_LONG", "confidence": 0.8, "reasoning": "test"},
                    "duration_ms": 10.0
                }
                f.write(json.dumps(entry) + "\n")
        
        # Get statistics
        stats = logger_instance.get_function_statistics()
        
        assert stats["close_above"] == 2
        assert stats["close_below"] == 1
        assert stats["trailing_stop"] == 1

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
        results = logger_instance.query_logs({"function_name": "error_func"})
        assert len(results) == 1
        assert results[0]["error"] == "Test error message"

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
        results = logger_instance.query_logs({})
        assert len(results) == 10

    def test_malformed_log_file_handling(self, logger_instance, temp_log_dir):
        """Test handling of malformed log files during queries."""
        # Create log file with malformed JSON
        log_file = temp_log_dir / "execution_malformed.jsonl"
        with open(log_file, 'w') as f:
            f.write('{"valid": "json"}\n')
            f.write('invalid json line\n')  # This will cause JSON parsing error
            f.write('{"another": "valid", "entry": true}\n')
        
        # Query should handle errors gracefully
        results = logger_instance.query_logs({})
        
        # Should return valid entries only
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
        logger_instance._create_new_log_file()
        
        log_files = list(temp_log_dir.glob("execution_*.jsonl"))
        assert len(log_files) == 1
        
        filename = log_files[0].name
        assert filename.startswith("execution_")
        assert filename.endswith(".jsonl")
        assert len(filename.split("_")[1]) == 14  # Timestamp format YYYYMMDDHHMMSS

    def test_get_audit_trail(self, logger_instance, temp_log_dir):
        """Test complete audit trail retrieval."""
        # Create test data across multiple files
        for file_num in range(3):
            log_file = temp_log_dir / f"execution_test_{file_num}.jsonl"
            with open(log_file, 'w') as f:
                entry = {
                    "timestamp": f"2025-08-28T1{file_num}:00:00Z",
                    "function_name": f"func_{file_num}",
                    "symbol": "AAPL",
                    "timeframe": "1min",
                    "signal": {"action": "ENTER_LONG", "confidence": 0.8, "reasoning": "test"},
                    "duration_ms": 10.0
                }
                f.write(json.dumps(entry) + "\n")
        
        # Get complete audit trail
        trail = logger_instance.get_audit_trail("AAPL")
        
        assert len(trail) == 3
        # Should be sorted by timestamp
        timestamps = [entry["timestamp"] for entry in trail]
        assert timestamps == sorted(timestamps)