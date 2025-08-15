"""Tests for file watcher functionality."""

import asyncio
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import yaml

from auto_trader.utils.file_watcher import (
    FileWatcher,
    FileWatchConfig,
    FileWatchEvent,
    FileWatchEventType,
    TradeplanFileHandler,
)


class TestTradeplanFileHandler:
    """Test the file handler component."""
    
    def test_yaml_file_detection(self):
        """Test YAML file detection logic."""
        callback = Mock()
        handler = TradeplanFileHandler(callback)
        
        # Valid YAML files
        assert handler._is_yaml_file("test.yaml") is True
        assert handler._is_yaml_file("test.yml") is True
        assert handler._is_yaml_file("/path/to/plan.yaml") is True
        
        # Invalid files
        assert handler._is_yaml_file("test.txt") is False
        assert handler._is_yaml_file("test.json") is False
        assert handler._is_yaml_file(".hidden.yaml") is False
        assert handler._is_yaml_file("test.yaml.tmp") is False
        assert handler._is_yaml_file("test.yaml.bak") is False
        
    def test_event_queuing_and_debouncing(self):
        """Test event queuing and debouncing mechanism."""
        callback = Mock()
        handler = TradeplanFileHandler(callback, debounce_delay=0.1)
        
        event = FileWatchEvent(
            FileWatchEventType.MODIFIED,
            Path("test.yaml"),
            time.time()
        )
        
        # Queue an event
        handler._queue_event(event)
        
        # Should have a pending event
        assert str(event.file_path) in handler._pending_events
        assert str(event.file_path) in handler._debounce_tasks


class TestFileWatchConfig:
    """Test file watch configuration."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = FileWatchConfig()
        
        assert config.watch_directory == Path("data/trade_plans")
        assert config.debounce_delay == 0.5
        assert config.enable_notifications is True
        assert config.auto_start is False
        
    def test_custom_config(self):
        """Test custom configuration values."""
        custom_dir = Path("/custom/path")
        config = FileWatchConfig(
            watch_directory=custom_dir,
            debounce_delay=1.0,
            enable_notifications=False,
            auto_start=True
        )
        
        assert config.watch_directory == custom_dir
        assert config.debounce_delay == 1.0
        assert config.enable_notifications is False
        assert config.auto_start is True
        
    def test_from_settings(self):
        """Test creating config from settings dictionary."""
        settings = {
            "watch_directory": "/test/path",
            "debounce_delay": 2.0,
            "enable_notifications": False,
            "auto_start": True
        }
        
        config = FileWatchConfig.from_settings(settings)
        
        assert config.watch_directory == Path("/test/path")
        assert config.debounce_delay == 2.0
        assert config.enable_notifications is False
        assert config.auto_start is True


class TestFileWatcher:
    """Test the main file watcher class."""
    
    @pytest.fixture
    def temp_watch_dir(self):
        """Create temporary directory for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            watch_dir = Path(temp_dir) / "trade_plans"
            watch_dir.mkdir()
            yield watch_dir
    
    @pytest.fixture
    def mock_validation_callback(self):
        """Create mock validation callback."""
        return Mock()
    
    def test_initialization(self, temp_watch_dir):
        """Test file watcher initialization."""
        watcher = FileWatcher(temp_watch_dir)
        
        assert watcher.watch_directory == temp_watch_dir
        assert watcher.debounce_delay == 0.5
        assert watcher.events_processed == 0
        assert watcher.validation_errors == 0
        assert watcher.last_validation_time is None
        
    def test_start_creates_directory_if_missing(self):
        """Test that start() creates watch directory if it doesn't exist."""
        non_existent_dir = Path("/tmp/test_auto_trader_nonexistent")
        
        # Ensure directory doesn't exist
        if non_existent_dir.exists():
            non_existent_dir.rmdir()
        
        watcher = FileWatcher(non_existent_dir)
        
        try:
            result = watcher.start()
            assert result is True
            assert non_existent_dir.exists()
        finally:
            watcher.stop()
            if non_existent_dir.exists():
                non_existent_dir.rmdir()
                
    def test_start_stop_lifecycle(self, temp_watch_dir):
        """Test start/stop lifecycle."""
        watcher = FileWatcher(temp_watch_dir)
        
        # Should start successfully
        assert watcher.start() is True
        assert watcher.observer is not None
        assert watcher.observer.is_alive()
        
        # Stop should clean up
        watcher.stop()
        assert not watcher.observer.is_alive()
        
    def test_file_validation(self, temp_watch_dir):
        """Test file validation functionality."""
        # Create a valid YAML file
        test_file = temp_watch_dir / "test_plan.yaml"
        plan_data = {
            "plan_id": "TEST_001",
            "symbol": "AAPL",
            "entry_level": 150.00,
            "stop_loss": 145.00,
            "take_profit": 160.00,
            "position_size": 100,
            "entry_function": {
                "type": "close_above",
                "timeframe": "15min"
            },
            "risk_category": "normal",
            "status": "awaiting_entry"
        }
        
        with open(test_file, 'w') as f:
            yaml.dump(plan_data, f)
        
        watcher = FileWatcher(temp_watch_dir)
        
        # Test validation
        with patch.object(watcher.validation_engine, 'validate_file') as mock_validate:
            from auto_trader.models.validation_engine import ValidationResult
            mock_validate.return_value = ValidationResult(
                is_valid=True,
                errors=[],
                warnings=[],
                plan_ids={'TEST_001'}
            )
            
            watcher._validate_file(test_file)
            mock_validate.assert_called_once_with(test_file)
    
    def test_file_deletion_handling(self, temp_watch_dir):
        """Test file deletion handling."""
        test_file = temp_watch_dir / "deleted_plan.yaml"
        
        watcher = FileWatcher(temp_watch_dir)
        
        # Mock the trade plan loader
        with patch.object(watcher.trade_plan_loader, 'clear_cache_for_file') as mock_clear:
            watcher._handle_file_deletion(test_file)
            mock_clear.assert_called_once_with(test_file)
    
    def test_event_handling(self, temp_watch_dir, mock_validation_callback):
        """Test file event handling."""
        watcher = FileWatcher(
            temp_watch_dir, 
            validation_callback=mock_validation_callback
        )
        
        test_file = temp_watch_dir / "event_test.yaml"
        
        # Test CREATE event
        create_event = FileWatchEvent(
            FileWatchEventType.CREATED,
            test_file,
            time.time()
        )
        
        with patch.object(watcher, '_validate_file') as mock_validate:
            watcher._handle_file_event(create_event)
            mock_validate.assert_called_once_with(test_file)
            mock_validation_callback.assert_called_once_with(test_file, FileWatchEventType.CREATED)
        
        # Reset mocks
        mock_validation_callback.reset_mock()
        
        # Test DELETE event
        delete_event = FileWatchEvent(
            FileWatchEventType.DELETED,
            test_file,
            time.time()
        )
        
        with patch.object(watcher, '_handle_file_deletion') as mock_delete:
            watcher._handle_file_event(delete_event)
            mock_delete.assert_called_once_with(test_file)
            mock_validation_callback.assert_called_once_with(test_file, FileWatchEventType.DELETED)
    
    def test_statistics(self, temp_watch_dir):
        """Test statistics collection."""
        watcher = FileWatcher(temp_watch_dir, debounce_delay=1.0)
        
        stats = watcher.get_stats()
        
        expected_stats = {
            "watch_directory": str(temp_watch_dir),
            "events_processed": 0,
            "validation_errors": 0,
            "last_validation_time": None,
            "is_running": False,
            "debounce_delay": 1.0,
        }
        
        assert stats == expected_stats
        
        # Test after processing events
        watcher.events_processed = 5
        watcher.validation_errors = 1
        watcher.last_validation_time = 1234567890.0
        
        stats = watcher.get_stats()
        assert stats["events_processed"] == 5
        assert stats["validation_errors"] == 1
        assert stats["last_validation_time"] == 1234567890.0
    
    def test_force_validation(self, temp_watch_dir):
        """Test force validation of all files."""
        # Create test files
        valid_file = temp_watch_dir / "valid_plan.yaml"
        template_file = temp_watch_dir / "template_plan.yaml"  # Should be skipped
        
        plan_data = {"plan_id": "TEST_001", "symbol": "AAPL"}
        
        for file_path in [valid_file, template_file]:
            with open(file_path, 'w') as f:
                yaml.dump(plan_data, f)
        
        watcher = FileWatcher(temp_watch_dir)
        
        with patch.object(watcher, '_validate_file') as mock_validate:
            watcher.force_validation()
            
            # Should only validate the non-template file
            mock_validate.assert_called_once_with(valid_file)
    
    def test_valid_plan_file_detection(self, temp_watch_dir):
        """Test detection of valid plan files vs templates/examples."""
        watcher = FileWatcher(temp_watch_dir)
        
        # Valid plan files
        assert watcher._is_valid_plan_file(Path("regular_plan.yaml")) is True
        assert watcher._is_valid_plan_file(Path("AAPL_20250815_001.yaml")) is True
        
        # Invalid files (should be excluded)
        assert watcher._is_valid_plan_file(Path("template_plan.yaml")) is False
        assert watcher._is_valid_plan_file(Path("example_plan.yaml")) is False
        assert watcher._is_valid_plan_file(Path(".hidden_plan.yaml")) is False
        assert watcher._is_valid_plan_file(Path("plan.yaml.tmp")) is False
        assert watcher._is_valid_plan_file(Path("plan.yaml.bak")) is False


class TestFileWatchEvent:
    """Test file watch event data structure."""
    
    def test_event_creation(self):
        """Test creating file watch events."""
        timestamp = time.time()
        file_path = Path("test.yaml")
        
        event = FileWatchEvent(
            FileWatchEventType.MODIFIED,
            file_path,
            timestamp
        )
        
        assert event.event_type == FileWatchEventType.MODIFIED
        assert event.file_path == file_path
        assert event.timestamp == timestamp
        
    def test_event_types(self):
        """Test all event types are available."""
        assert FileWatchEventType.CREATED.value == "created"
        assert FileWatchEventType.MODIFIED.value == "modified"
        assert FileWatchEventType.DELETED.value == "deleted"