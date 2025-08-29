"""Tests for LogFileManager."""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime, UTC
from unittest.mock import patch, Mock

from auto_trader.models.execution import ExecutionSignal, ExecutionLogEntry
from auto_trader.models.enums import ExecutionAction, Timeframe
from auto_trader.trade_engine.log_file_manager import LogFileManager


@pytest.fixture
def temp_log_dir():
    """Create temporary directory for log files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def log_manager(temp_log_dir):
    """Create log file manager for testing."""
    return LogFileManager(
        log_dir=temp_log_dir,
        max_entries_per_file=5,
        max_log_files=3
    )


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


class TestLogFileManager:
    """Test cases for log file manager."""

    def test_initialization(self, temp_log_dir):
        """Test manager initialization."""
        manager = LogFileManager(
            log_dir=temp_log_dir,
            max_entries_per_file=10,
            max_log_files=5
        )
        
        assert manager.log_dir == temp_log_dir
        assert manager.max_entries_per_file == 10
        assert manager.max_log_files == 5
        assert manager.current_file_entries == 0

    def test_write_entry_success(self, log_manager, sample_entry):
        """Test successful entry writing."""
        result = log_manager.write_entry(sample_entry)
        
        assert result is True
        assert log_manager.current_file_entries == 1
        assert log_manager.current_log_file.exists()
        
        # Verify content
        with open(log_manager.current_log_file, 'r') as f:
            line = f.readline().strip()
            data = json.loads(line)
            assert data["function_name"] == "test_function"
            assert data["symbol"] == "AAPL"

    def test_write_entry_file_rotation(self, log_manager, sample_entry):
        """Test file rotation when max entries reached."""
        # Write entries up to the limit
        for i in range(5):
            result = log_manager.write_entry(sample_entry)
            assert result is True
        
        # Get the first log file
        first_file = log_manager.current_log_file
        
        # Write one more entry to trigger rotation
        result = log_manager.write_entry(sample_entry)
        assert result is True
        
        # Should have rotated to new file
        assert log_manager.current_log_file != first_file
        assert log_manager.current_file_entries == 1

    def test_should_rotate_new_manager(self, temp_log_dir):
        """Test rotation check for new manager."""
        manager = LogFileManager(temp_log_dir)
        # New manager should not need to rotate immediately since it creates a current file on init
        assert manager.should_rotate() is False

    def test_should_rotate_max_entries(self, log_manager, sample_entry):
        """Test rotation when max entries reached."""
        # Write entries up to limit
        for i in range(5):
            log_manager.write_entry(sample_entry)
        
        assert log_manager.should_rotate() is True

    def test_should_rotate_daily(self, log_manager):
        """Test daily rotation logic."""
        with patch('auto_trader.trade_engine.log_file_manager.datetime') as mock_dt:
            # Mock current date as different from file date
            mock_dt.now.return_value.strftime.return_value = "20250101"
            
            # Create a file with yesterday's date
            old_file = log_manager.log_dir / "execution_20241231.jsonl"
            old_file.touch()
            log_manager.current_log_file = old_file
            
            assert log_manager.should_rotate() is True

    def test_rotate_log_file(self, log_manager, sample_entry):
        """Test log file rotation."""
        original_file = log_manager.current_log_file
        
        # Fill up current file to trigger timestamped rotation
        for _ in range(log_manager.max_entries_per_file):
            log_manager.write_entry(sample_entry)
        
        log_manager.rotate_log_file()
        
        # Should have new file with timestamp
        assert log_manager.current_log_file != original_file

    def test_get_current_log_path(self, temp_log_dir):
        """Test current log path generation."""
        manager = LogFileManager(temp_log_dir)
        
        path = manager.get_current_log_path()
        
        # Should be in correct directory with date format
        assert path.parent == temp_log_dir
        assert path.name.startswith("execution_")
        assert path.suffix == ".jsonl"

    def test_get_log_files(self, log_manager, sample_entry):
        """Test getting list of log files."""
        # Initially no files
        files = log_manager.get_log_files()
        assert len(files) == 0
        
        # Write some entries to create files
        log_manager.write_entry(sample_entry)
        
        files = log_manager.get_log_files()
        assert len(files) == 1
        assert files[0].name.startswith("execution_")

    def test_get_file_entry_count(self, log_manager, sample_entry):
        """Test counting entries in file."""
        # Write 3 entries
        for _ in range(3):
            log_manager.write_entry(sample_entry)
        
        count = log_manager.get_file_entry_count(log_manager.current_log_file)
        assert count == 3

    def test_get_file_entry_count_nonexistent(self, log_manager):
        """Test counting entries in nonexistent file."""
        fake_file = log_manager.log_dir / "nonexistent.jsonl"
        count = log_manager.get_file_entry_count(fake_file)
        assert count == 0

    def test_cleanup_old_files(self, log_manager, sample_entry):
        """Test cleanup of old log files."""
        # Create more files than max_log_files (3)
        old_files = []
        for i in range(5):
            filename = f"execution_old_{i}.jsonl"
            file_path = log_manager.log_dir / filename
            with open(file_path, 'w') as f:
                f.write('{"test": "data"}\n')
            old_files.append(file_path)
        
        # Write entry to trigger cleanup
        log_manager.write_entry(sample_entry)
        
        # Force cleanup
        log_manager._cleanup_old_files()
        
        # Should only keep max_log_files
        remaining_files = log_manager.get_log_files()
        assert len(remaining_files) <= log_manager.max_log_files

    def test_get_total_entries(self, log_manager, sample_entry):
        """Test getting total entries across all files."""
        # Write entries to first file
        for _ in range(3):
            log_manager.write_entry(sample_entry)
        
        # Force rotation and write more
        log_manager.current_file_entries = log_manager.max_entries_per_file
        for _ in range(2):
            log_manager.write_entry(sample_entry)
        
        total = log_manager.get_total_entries()
        assert total >= 5  # At least 5 entries across files

    def test_reset_current_file_counter(self, log_manager, sample_entry):
        """Test resetting file entry counter."""
        # Write some entries
        for _ in range(3):
            log_manager.write_entry(sample_entry)
        
        assert log_manager.current_file_entries == 3
        
        log_manager.reset_current_file_counter()
        assert log_manager.current_file_entries == 0

    def test_write_entry_failure(self, log_manager, sample_entry):
        """Test handling of write failures."""
        # Mock file writing to fail
        with patch('builtins.open', side_effect=OSError("Permission denied")):
            result = log_manager.write_entry(sample_entry)
            assert result is False

    def test_malformed_filename_rotation(self, log_manager):
        """Test rotation with malformed filename."""
        # Create file with malformed name
        malformed_file = log_manager.log_dir / "malformed_name.jsonl"
        log_manager.current_log_file = malformed_file
        
        # Should handle gracefully and return True to rotate
        assert log_manager.should_rotate() is True

    def test_rotation_with_timestamp(self, log_manager, sample_entry):
        """Test rotation creates timestamped filename."""
        # Fill up current file to force rotation
        for _ in range(log_manager.max_entries_per_file):
            log_manager.write_entry(sample_entry)
        
        original_file = log_manager.current_log_file
        
        # Next write should rotate
        log_manager.write_entry(sample_entry)
        
        # New file should have timestamp format
        new_file = log_manager.current_log_file
        assert new_file != original_file
        assert "_" in new_file.stem  # Should have timestamp format

    def test_concurrent_writes(self, log_manager, sample_entry):
        """Test concurrent writing doesn't corrupt files."""
        import threading
        
        results = []
        
        def write_entries():
            for _ in range(10):
                result = log_manager.write_entry(sample_entry)
                results.append(result)
        
        # Start multiple threads
        threads = []
        for _ in range(3):
            thread = threading.Thread(target=write_entries)
            threads.append(thread)
            thread.start()
        
        # Wait for completion
        for thread in threads:
            thread.join()
        
        # All writes should succeed
        assert all(results)
        
        # Verify total entries
        total = log_manager.get_total_entries()
        assert total == 30