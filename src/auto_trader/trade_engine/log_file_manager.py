"""File management for execution logger operations."""

from datetime import datetime
from pathlib import Path

from loguru import logger

from auto_trader.models.execution import ExecutionLogEntry


class LogFileManager:
    """Manages log file operations for execution logger.
    
    Handles file writing, rotation, and path management
    to keep execution history organized and manageable.
    """

    def __init__(
        self,
        log_dir: Path,
        max_entries_per_file: int = 1000,
        max_log_files: int = 10,
    ):
        """Initialize log file manager.

        Args:
            log_dir: Directory for log files
            max_entries_per_file: Maximum entries per file before rotation
            max_log_files: Maximum number of log files to keep
        """
        self.log_dir = log_dir
        self.max_entries_per_file = max_entries_per_file
        self.max_log_files = max_log_files
        self.current_file_entries = 0
        
        # Initialize current log file
        self.current_log_file = self.get_current_log_path()

    def write_entry(self, entry: ExecutionLogEntry) -> bool:
        """Write log entry to current file.

        Args:
            entry: Log entry to write

        Returns:
            True if write successful, False otherwise
        """
        try:
            # Check if we need to rotate log file
            if self.should_rotate():
                self.rotate_log_file()
                self.current_file_entries = 0

            # Write as JSON line
            with open(self.current_log_file, "a") as f:
                json_data = entry.model_dump_json()
                f.write(json_data + "\n")
                self.current_file_entries += 1
                
            return True

        except Exception as e:
            logger.error(f"Failed to write execution log to file: {e}")
            return False

    def should_rotate(self) -> bool:
        """Check if log file should be rotated.

        Returns:
            True if rotation needed
        """
        if not hasattr(self, "current_log_file") or not self.current_log_file:
            return True

        # Rotate if file has reached maximum entries
        if self.current_file_entries >= self.max_entries_per_file:
            return True

        # Rotate daily
        current_date = datetime.now().strftime("%Y%m%d")
        
        try:
            # Extract date from filename (format: execution_YYYYMMDD.jsonl)
            file_date = self.current_log_file.stem.split("_")[1]
            return current_date != file_date
        except (IndexError, ValueError):
            # If we can't parse the date, rotate to be safe
            return True

    def rotate_log_file(self) -> None:
        """Rotate to a new log file."""
        if self.current_file_entries >= self.max_entries_per_file:
            # Generate a unique filename with timestamp for rotation
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            base_name = f"execution_{timestamp}.jsonl"
            self.current_log_file = self.log_dir / base_name
        else:
            # Use standard date-based naming
            self.current_log_file = self.get_current_log_path()

        logger.info(f"Rotated to new log file: {self.current_log_file}")
        
        # Clean up old files if needed
        self._cleanup_old_files()

    def get_current_log_path(self) -> Path:
        """Get current log file path.

        Returns:
            Path to current log file
        """
        date_str = datetime.now().strftime("%Y%m%d")
        return self.log_dir / f"execution_{date_str}.jsonl"

    def get_log_files(self) -> list[Path]:
        """Get list of all log files in directory.

        Returns:
            List of log file paths, sorted by modification time
        """
        try:
            log_files = list(self.log_dir.glob("execution_*.jsonl"))
            return sorted(log_files, key=lambda f: f.stat().st_mtime)
        except OSError as e:
            logger.error(f"Failed to list log files: {e}")
            return []

    def get_file_entry_count(self, file_path: Path) -> int:
        """Get number of entries in a log file.

        Args:
            file_path: Path to log file

        Returns:
            Number of entries in file
        """
        try:
            with open(file_path, "r") as f:
                return sum(1 for _ in f)
        except (OSError, IOError):
            return 0

    def _cleanup_old_files(self) -> None:
        """Remove old log files if exceeding max_log_files limit."""
        log_files = self.get_log_files()
        
        if len(log_files) <= self.max_log_files:
            return

        # Remove oldest files
        files_to_remove = log_files[:-self.max_log_files]
        
        for file_path in files_to_remove:
            try:
                file_path.unlink()
                logger.info(f"Removed old log file: {file_path}")
            except OSError as e:
                logger.error(f"Failed to remove old log file {file_path}: {e}")

    def get_total_entries(self) -> int:
        """Get total number of entries across all log files.

        Returns:
            Total entry count
        """
        total = 0
        for file_path in self.get_log_files():
            total += self.get_file_entry_count(file_path)
        return total

    def reset_current_file_counter(self) -> None:
        """Reset the current file entry counter."""
        self.current_file_entries = 0