"""Tests for LoggerValidationMixin."""

import pytest
import tempfile
from pathlib import Path

from auto_trader.trade_engine.logger_validation import LoggerValidationMixin


class TestLoggerValidationMixin:
    """Test cases for logger validation functionality."""

    def test_validate_log_directory_none(self):
        """Test that None log directory is valid."""
        assert LoggerValidationMixin.validate_log_directory(None) is True

    def test_validate_log_directory_valid_path(self):
        """Test valid Path object."""
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir)
            assert LoggerValidationMixin.validate_log_directory(path) is True

    def test_validate_log_directory_valid_string(self):
        """Test valid string path."""
        assert LoggerValidationMixin.validate_log_directory("/tmp") is True

    def test_validate_log_directory_invalid_type(self):
        """Test invalid type for log directory."""
        assert LoggerValidationMixin.validate_log_directory(123) is False
        assert LoggerValidationMixin.validate_log_directory([]) is False

    def test_validate_memory_settings_valid(self):
        """Test valid memory settings."""
        assert LoggerValidationMixin.validate_memory_settings(
            max_memory_entries=1000,
            max_entries_per_file=500,
            max_log_files=5
        ) is True

    def test_validate_memory_settings_invalid_memory_entries(self):
        """Test invalid memory entries."""
        assert LoggerValidationMixin.validate_memory_settings(
            max_memory_entries=0,
            max_entries_per_file=500,
            max_log_files=5
        ) is False

        assert LoggerValidationMixin.validate_memory_settings(
            max_memory_entries=-1,
            max_entries_per_file=500,
            max_log_files=5
        ) is False

        assert LoggerValidationMixin.validate_memory_settings(
            max_memory_entries="invalid",
            max_entries_per_file=500,
            max_log_files=5
        ) is False

    def test_validate_memory_settings_invalid_entries_per_file(self):
        """Test invalid entries per file."""
        assert LoggerValidationMixin.validate_memory_settings(
            max_memory_entries=1000,
            max_entries_per_file=0,
            max_log_files=5
        ) is False

    def test_validate_memory_settings_invalid_log_files(self):
        """Test invalid max log files."""
        assert LoggerValidationMixin.validate_memory_settings(
            max_memory_entries=1000,
            max_entries_per_file=500,
            max_log_files=0
        ) is False

    def test_validate_memory_settings_high_values_warning(self):
        """Test that high values still validate successfully."""
        # High values should still validate as True (warnings are logged but don't fail validation)
        assert LoggerValidationMixin.validate_memory_settings(
            max_memory_entries=200000,  # High value
            max_entries_per_file=20000,  # High value
            max_log_files=5
        ) is True

    def test_validate_file_logging_settings_valid(self):
        """Test valid file logging settings."""
        assert LoggerValidationMixin.validate_file_logging_settings(
            enable_file_logging=True,
            log_dir=Path("/tmp")
        ) is True

        assert LoggerValidationMixin.validate_file_logging_settings(
            enable_file_logging=False,
            log_dir=None
        ) is True

    def test_validate_file_logging_settings_invalid_type(self):
        """Test invalid enable_file_logging type."""
        assert LoggerValidationMixin.validate_file_logging_settings(
            enable_file_logging="true",  # Should be bool
            log_dir=Path("/tmp")
        ) is False

    def test_validate_file_logging_settings_enabled_no_dir_warning(self):
        """Test validation when file logging enabled but no directory."""
        # Should still validate as True (warning is logged but doesn't fail validation)
        assert LoggerValidationMixin.validate_file_logging_settings(
            enable_file_logging=True,
            log_dir=None
        ) is True

    def test_ensure_log_directory_exists_creates_dir(self):
        """Test directory creation."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_dir = Path(temp_dir) / "logs" / "execution"
            assert not test_dir.exists()
            
            result = LoggerValidationMixin.ensure_log_directory_exists(test_dir)
            
            assert result is True
            assert test_dir.exists()
            assert test_dir.is_dir()

    def test_ensure_log_directory_exists_existing_dir(self):
        """Test with existing directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_dir = Path(temp_dir)
            
            result = LoggerValidationMixin.ensure_log_directory_exists(test_dir)
            
            assert result is True

    def test_ensure_log_directory_exists_write_permission_test(self):
        """Test write permission verification."""
        with tempfile.TemporaryDirectory() as temp_dir:
            test_dir = Path(temp_dir) / "writable"
            
            result = LoggerValidationMixin.ensure_log_directory_exists(test_dir)
            
            assert result is True
            # Verify the test file was cleaned up
            assert not (test_dir / ".write_test").exists()

    def test_ensure_log_directory_exists_permission_error(self):
        """Test handling of permission errors."""
        # Try to create directory in a location without permission
        # This test might not work on all systems, so we'll mock it
        from unittest.mock import patch, Mock
        
        mock_error = PermissionError("Permission denied")
        
        with patch('pathlib.Path.mkdir', side_effect=mock_error):
            result = LoggerValidationMixin.ensure_log_directory_exists(
                Path("/root/no_permission")
            )
            
            assert result is False