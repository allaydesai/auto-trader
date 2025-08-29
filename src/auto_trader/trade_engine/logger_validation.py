"""Validation mixin for execution logger configuration."""

from typing import Optional
from pathlib import Path

from loguru import logger


class LoggerValidationMixin:
    """Mixin class for execution logger parameter validation."""

    @staticmethod
    def validate_log_directory(log_dir: Optional[Path]) -> bool:
        """Validate log directory parameter.

        Args:
            log_dir: Directory path to validate

        Returns:
            True if valid directory parameter
        """
        if log_dir is None:
            return True  # Allow None for default behavior
        
        if not isinstance(log_dir, Path):
            try:
                Path(log_dir)
                return True
            except (TypeError, ValueError):
                logger.error(f"Invalid log directory type: {type(log_dir)}")
                return False
        
        return True

    @staticmethod
    def validate_memory_settings(
        max_memory_entries: int,
        max_entries_per_file: int,
        max_log_files: int
    ) -> bool:
        """Validate memory and file limit settings.

        Args:
            max_memory_entries: Maximum entries in memory
            max_entries_per_file: Maximum entries per log file
            max_log_files: Maximum number of log files

        Returns:
            True if all settings are valid
        """
        if not isinstance(max_memory_entries, int) or max_memory_entries <= 0:
            logger.error(f"Invalid max_memory_entries: {max_memory_entries}")
            return False

        if not isinstance(max_entries_per_file, int) or max_entries_per_file <= 0:
            logger.error(f"Invalid max_entries_per_file: {max_entries_per_file}")
            return False

        if not isinstance(max_log_files, int) or max_log_files <= 0:
            logger.error(f"Invalid max_log_files: {max_log_files}")
            return False

        # Ensure reasonable limits
        if max_memory_entries > 100000:
            logger.warning(f"High memory entries limit: {max_memory_entries}")

        if max_entries_per_file > 10000:
            logger.warning(f"High entries per file limit: {max_entries_per_file}")

        return True

    @staticmethod
    def validate_file_logging_settings(
        enable_file_logging: bool,
        log_dir: Optional[Path]
    ) -> bool:
        """Validate file logging configuration.

        Args:
            enable_file_logging: Whether file logging is enabled
            log_dir: Log directory path

        Returns:
            True if configuration is valid
        """
        if not isinstance(enable_file_logging, bool):
            logger.error(f"Invalid enable_file_logging type: {type(enable_file_logging)}")
            return False

        if enable_file_logging and log_dir is None:
            logger.warning("File logging enabled but no log directory specified")
            # This is okay - we'll use default

        return True

    @staticmethod
    def ensure_log_directory_exists(log_dir: Path) -> bool:
        """Ensure log directory exists and is writable.

        Args:
            log_dir: Directory to check/create

        Returns:
            True if directory exists and is writable
        """
        try:
            log_dir.mkdir(parents=True, exist_ok=True)
            
            # Test write permission by creating a temporary file
            test_file = log_dir / ".write_test"
            test_file.touch()
            test_file.unlink()
            
            return True
            
        except (OSError, PermissionError) as e:
            logger.error(f"Cannot access log directory {log_dir}: {e}")
            return False