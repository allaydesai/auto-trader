"""Tests for CLI watch utilities."""

import time
from pathlib import Path
from unittest.mock import patch, Mock, MagicMock

import pytest

from ..watch_utils import start_file_watching
from ...utils import FileWatchEventType


class TestWatchUtils:
    """Test watch utility functions."""

    def test_start_file_watching_success(self, tmp_path):
        """Test successful file watching startup."""
        watch_dir = tmp_path / "plans"
        watch_dir.mkdir()
        
        with patch('auto_trader.cli.watch_utils.FileWatcher') as mock_watcher_class, \
             patch('auto_trader.cli.watch_utils.console') as mock_console, \
             patch('time.sleep', side_effect=KeyboardInterrupt):  # Simulate Ctrl+C
            
            # Setup mock watcher
            mock_watcher = Mock()
            mock_watcher.start.return_value = True
            mock_watcher.stop.return_value = None
            mock_watcher.get_stats.return_value = {
                'events_processed': 5,
                'validation_errors': 0,
                'watch_duration': 'Active'
            }
            mock_watcher_class.return_value = mock_watcher
            
            # This should handle KeyboardInterrupt gracefully
            start_file_watching(watch_dir, verbose=True)
            
            # Verify watcher was created and started
            mock_watcher_class.assert_called_once()
            mock_watcher.start.assert_called_once()
            mock_watcher.stop.assert_called_once()
            
            # Verify console output
            assert mock_console.print.call_count >= 2  # Start message and statistics
    
    def test_start_file_watching_failure(self, tmp_path):
        """Test file watching startup failure."""
        watch_dir = tmp_path / "plans"
        
        with patch('auto_trader.cli.watch_utils.FileWatcher') as mock_watcher_class, \
             patch('auto_trader.cli.watch_utils.console') as mock_console:
            
            # Setup mock watcher that fails to start
            mock_watcher = Mock()
            mock_watcher.start.return_value = False
            mock_watcher_class.return_value = mock_watcher
            
            start_file_watching(watch_dir, verbose=False)
            
            # Verify failure was handled
            mock_watcher.start.assert_called_once()
            # Should print failure message
            assert any("❌" in str(call) for call in mock_console.print.call_args_list)
    
    def test_validation_callback_created_file(self, tmp_path):
        """Test validation callback handles file creation events."""
        watch_dir = tmp_path / "plans"
        
        with patch('auto_trader.cli.watch_utils.FileWatcher') as mock_watcher_class, \
             patch('auto_trader.cli.watch_utils.console') as mock_console, \
             patch('time.sleep', side_effect=KeyboardInterrupt):
            
            mock_watcher = Mock()
            mock_watcher.start.return_value = True
            mock_watcher.get_stats.return_value = {'events_processed': 1, 'validation_errors': 0}
            
            # Capture the callback function
            captured_callback = None
            def capture_callback(*args, **kwargs):
                nonlocal captured_callback
                captured_callback = kwargs.get('validation_callback') or args[1]  # Get callback parameter
                return mock_watcher
            
            mock_watcher_class.side_effect = capture_callback
            
            try:
                start_file_watching(watch_dir, verbose=True)
            except KeyboardInterrupt:
                pass
            
            # Test the callback function if captured
            if captured_callback:
                test_path = Path("test_plan.yaml")
                captured_callback(test_path, FileWatchEventType.CREATED)
                
                # Should have printed creation message
                assert any("✅" in str(call) for call in mock_console.print.call_args_list)
    
    def test_validation_callback_modified_file(self, tmp_path):
        """Test validation callback handles file modification events."""
        watch_dir = tmp_path / "plans"
        
        with patch('auto_trader.cli.watch_utils.FileWatcher') as mock_watcher_class, \
             patch('auto_trader.cli.watch_utils.console') as mock_console, \
             patch('time.sleep', side_effect=KeyboardInterrupt):
            
            mock_watcher = Mock()
            mock_watcher.start.return_value = True
            mock_watcher.get_stats.return_value = {'events_processed': 1, 'validation_errors': 0}
            
            # Capture the callback function
            captured_callback = None
            def capture_callback(*args, **kwargs):
                nonlocal captured_callback
                captured_callback = kwargs.get('validation_callback') or args[1]
                return mock_watcher
            
            mock_watcher_class.side_effect = capture_callback
            
            try:
                start_file_watching(watch_dir, verbose=True)
            except KeyboardInterrupt:
                pass
            
            # Test the callback function if captured
            if captured_callback:
                test_path = Path("test_plan.yaml")
                captured_callback(test_path, FileWatchEventType.MODIFIED)
                
                # Should have printed modification message
                assert any("🔄" in str(call) for call in mock_console.print.call_args_list)
    
    def test_validation_callback_deleted_file(self, tmp_path):
        """Test validation callback handles file deletion events."""
        watch_dir = tmp_path / "plans"
        
        with patch('auto_trader.cli.watch_utils.FileWatcher') as mock_watcher_class, \
             patch('auto_trader.cli.watch_utils.console') as mock_console, \
             patch('time.sleep', side_effect=KeyboardInterrupt):
            
            mock_watcher = Mock()
            mock_watcher.start.return_value = True
            mock_watcher.get_stats.return_value = {'events_processed': 1, 'validation_errors': 0}
            
            # Capture the callback function
            captured_callback = None
            def capture_callback(*args, **kwargs):
                nonlocal captured_callback
                captured_callback = kwargs.get('validation_callback') or args[1]
                return mock_watcher
            
            mock_watcher_class.side_effect = capture_callback
            
            try:
                start_file_watching(watch_dir, verbose=False)  # Test non-verbose mode
            except KeyboardInterrupt:
                pass
            
            # Test the callback function if captured
            if captured_callback:
                test_path = Path("test_plan.yaml")
                captured_callback(test_path, FileWatchEventType.DELETED)
                
                # Should have printed deletion message
                assert any("🗑️" in str(call) for call in mock_console.print.call_args_list)