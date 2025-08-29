"""Execution decision logging system for comprehensive audit trail."""

from datetime import datetime, timedelta, UTC
from typing import Dict, List, Any, Optional
from pathlib import Path
from collections import deque
from threading import Lock

from loguru import logger

from auto_trader.models.execution import (
    ExecutionContext,
    ExecutionSignal,
    ExecutionLogEntry,
)
from auto_trader.models.enums import ExecutionAction, Timeframe
from auto_trader.trade_engine.logger_validation import LoggerValidationMixin
from auto_trader.trade_engine.execution_metrics import ExecutionMetricsCalculator
from auto_trader.trade_engine.log_file_manager import LogFileManager


class ExecutionLogger(LoggerValidationMixin):
    """Structured logging system for all execution decisions.

    Provides comprehensive audit trail with querying capabilities
    and performance metrics tracking using composition pattern.
    """

    def __init__(
        self,
        log_dir: Optional[Path] = None,
        log_directory: Optional[Path] = None,
        max_memory_entries: int = 10000,
        enable_file_logging: bool = True,
        max_entries_per_file: int = 1000,
        max_log_files: int = 10,
    ):
        """Initialize execution logger.

        Args:
            log_dir: Directory for log files (default: logs/execution)
            log_directory: Alternative parameter name for log_dir (backward compatibility)
            max_memory_entries: Maximum entries to keep in memory
            enable_file_logging: Whether to write logs to files
            max_entries_per_file: Maximum entries per log file before rotation
            max_log_files: Maximum number of log files to keep
        """
        # Validate parameters using mixin
        self._validate_init_parameters(
            log_dir, log_directory, max_memory_entries, enable_file_logging,
            max_entries_per_file, max_log_files
        )

        # Support both parameter names for backward compatibility
        self.log_dir = log_directory or log_dir or Path("logs/execution")
        self.log_directory = self.log_dir  # Alias for test compatibility
        self.max_memory_entries = max_memory_entries
        self.enable_file_logging = enable_file_logging

        # In-memory log storage for fast querying
        self.entries: deque = deque(maxlen=max_memory_entries)
        self.lock = Lock()
        self.current_entries = 0  # Track count for test compatibility

        # Initialize component classes
        self.metrics_calculator = ExecutionMetricsCalculator()
        
        # Initialize file manager if file logging enabled
        self.file_manager = None
        if self.enable_file_logging:
            if self.ensure_log_directory_exists(self.log_dir):
                self.file_manager = LogFileManager(
                    self.log_dir, max_entries_per_file, max_log_files
                )
                logger.info(f"ExecutionLogger file logging to: {self.log_dir}")
            else:
                logger.warning("File logging disabled due to directory issues")
                self.enable_file_logging = False

        logger.info(
            f"ExecutionLogger initialized (memory capacity: {max_memory_entries})"
        )

    @property
    def current_log_file(self) -> Optional[Path]:
        """Get current log file path for backward compatibility."""
        if self.file_manager:
            return self.file_manager.current_log_file
        return None

    @property
    def current_file_entries(self) -> int:
        """Get current file entry count for backward compatibility."""
        if self.file_manager:
            return self.file_manager.current_file_entries
        return 0

    def _get_log_file_path(self) -> Optional[Path]:
        """Get log file path for backward compatibility."""
        if self.file_manager:
            return self.file_manager.get_current_log_path()
        return None

    @property
    def max_entries_per_file(self) -> int:
        """Get max entries per file for backward compatibility."""
        if self.file_manager:
            return self.file_manager.max_entries_per_file
        return 1000

    @max_entries_per_file.setter
    def max_entries_per_file(self, value: int) -> None:
        """Set max entries per file for backward compatibility."""
        if self.file_manager:
            self.file_manager.max_entries_per_file = value

    @property
    def max_log_files(self) -> int:
        """Get max log files for backward compatibility."""
        if self.file_manager:
            return self.file_manager.max_log_files
        return 10

    @max_log_files.setter
    def max_log_files(self, value: int) -> None:
        """Set max log files for backward compatibility."""
        if self.file_manager:
            self.file_manager.max_log_files = value

    def _validate_init_parameters(
        self,
        log_dir: Optional[Path],
        log_directory: Optional[Path],
        max_memory_entries: int,
        enable_file_logging: bool,
        max_entries_per_file: int,
        max_log_files: int,
    ) -> None:
        """Validate initialization parameters using mixin methods."""
        # Use log_directory or log_dir (backward compatibility)
        target_log_dir = log_directory or log_dir
        
        if not self.validate_log_directory(target_log_dir):
            raise ValueError(f"Invalid log directory: {target_log_dir}")
        
        if not self.validate_memory_settings(
            max_memory_entries, max_entries_per_file, max_log_files
        ):
            raise ValueError("Invalid memory or file limit settings")
        
        if not self.validate_file_logging_settings(enable_file_logging, target_log_dir):
            raise ValueError("Invalid file logging configuration")

    def log_evaluation(
        self,
        function_name: str,
        context: ExecutionContext,
        signal: ExecutionSignal,
        duration_ms: float,
        error: Optional[str] = None,
    ) -> None:
        """Log an execution function evaluation.

        Args:
            function_name: Name of execution function
            context: Execution context used
            signal: Resulting signal
            duration_ms: Evaluation duration in milliseconds
            error: Error message if evaluation failed
        """
        # Create context snapshot (subset of data to avoid huge logs)
        context_snapshot = self._create_context_snapshot(context)

        # Create log entry
        entry = ExecutionLogEntry(
            timestamp=datetime.now(UTC),
            function_name=function_name,
            symbol=context.symbol,
            timeframe=context.timeframe,
            signal=signal,
            duration_ms=duration_ms,
            context_snapshot=context_snapshot,
            error=error,
        )

        # Store in memory and update metrics
        with self.lock:
            self.entries.append(entry)
            self.current_entries += 1
            self.metrics_calculator.update(entry)

        # Write to file if enabled
        if self.enable_file_logging and self.file_manager:
            self.file_manager.write_entry(entry)

        # Log to standard logger based on importance
        self._log_to_standard(entry)

    def log_error(
        self,
        function_name: str,
        symbol: str,
        timeframe: Timeframe,
        error: Exception,
        context: Optional[ExecutionContext] = None,
    ) -> None:
        """Log an execution error.

        Args:
            function_name: Function that failed
            symbol: Trading symbol
            timeframe: Timeframe being evaluated
            error: Exception that occurred
            context: Execution context if available
        """
        error_msg = f"{error.__class__.__name__}: {str(error)}"

        # Create minimal entry for error
        entry = ExecutionLogEntry(
            timestamp=datetime.now(UTC),
            function_name=function_name,
            symbol=symbol,
            timeframe=timeframe,
            signal=ExecutionSignal.no_action("Error occurred"),
            duration_ms=0.1,  # Minimum valid duration for error cases
            context_snapshot=self._create_context_snapshot(context) if context else {},
            error=error_msg,
        )

        with self.lock:
            self.entries.append(entry)
            self.current_entries += 1
            self.metrics_calculator.update(entry)

        if self.enable_file_logging and self.file_manager:
            self.file_manager.write_entry(entry)

        logger.error(f"Execution error in {function_name}: {error_msg}")

    def query_logs(
        self, 
        filters: Optional[Dict[str, Any]] = None, 
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[ExecutionLogEntry]:
        """Query historical execution logs.

        Args:
            filters: Optional filters to apply
            limit: Maximum entries to return

        Returns:
            List of matching log entries
        """
        with self.lock:
            entries_list = list(self.entries)

        # Apply filters
        filtered = entries_list
        
        # Apply dictionary filters if provided
        if filters:
            if "symbol" in filters:
                filtered = [e for e in filtered if e.symbol == filters["symbol"]]

            if "timeframe" in filters:
                filtered = [e for e in filtered if e.timeframe == filters["timeframe"]]

            if "function_name" in filters:
                filtered = [
                    e for e in filtered if e.function_name == filters["function_name"]
                ]

            if "action" in filters:
                action = filters["action"]
                if isinstance(action, str):
                    action = ExecutionAction(action)
                filtered = [e for e in filtered if e.signal.action == action]

            if "has_error" in filters:
                if filters["has_error"]:
                    filtered = [e for e in filtered if e.error is not None]
                else:
                    filtered = [e for e in filtered if e.error is None]

            if "min_confidence" in filters:
                min_conf = filters["min_confidence"]
                filtered = [e for e in filtered if e.signal.confidence >= min_conf]

            if "since" in filters:
                since = filters["since"]
                if not isinstance(since, datetime):
                    since = datetime.fromisoformat(since)
                filtered = [e for e in filtered if e.timestamp >= since]

        # Apply start_time and end_time filters if provided
        if start_time:
            filtered = [e for e in filtered if e.timestamp >= start_time]
        if end_time:
            filtered = [e for e in filtered if e.timestamp <= end_time]

        return filtered[-limit:]

    def get_recent_signals(
        self, symbol: Optional[str] = None, minutes: int = 60
    ) -> List[ExecutionLogEntry]:
        """Get recent signals that triggered actions.

        Args:
            symbol: Optional symbol filter
            minutes: How far back to look

        Returns:
            List of recent signal entries
        """
        since = datetime.now(UTC) - timedelta(minutes=minutes)

        filters = {
            "since": since,
            "min_confidence": 0.5,  # Only meaningful signals
        }

        if symbol:
            filters["symbol"] = symbol

        entries = self.query_logs(filters, limit=1000)

        # Filter for actual actions (not NONE)
        return [e for e in entries if e.signal.action != ExecutionAction.NONE]

    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics.

        Returns:
            Dictionary of performance metrics
        """
        return self.metrics_calculator.get_summary()

    def get_function_stats(self, function_name: str) -> Dict[str, Any]:
        """Get statistics for a specific function.

        Args:
            function_name: Function to get stats for

        Returns:
            Dictionary of function statistics
        """
        entries = self.query_logs({"function_name": function_name}, limit=10000)
        return self.metrics_calculator.get_function_statistics(function_name, entries)

    def clear_old_entries(self, days: int = 7) -> int:
        """Clear entries older than specified days.

        Args:
            days: Number of days to keep

        Returns:
            Number of entries removed
        """
        cutoff = datetime.now(UTC) - timedelta(days=days)

        with self.lock:
            original_count = len(self.entries)
            self.entries = deque(
                (e for e in self.entries if e.timestamp >= cutoff),
                maxlen=self.max_memory_entries,
            )
            removed = original_count - len(self.entries)

        if removed > 0:
            logger.info(
                f"Cleared {removed} execution log entries older than {days} days"
            )

        return removed

    async def log_execution_decision(self, entry: ExecutionLogEntry) -> None:
        """Log an execution decision entry.
        
        Args:
            entry: Pre-built execution log entry
        """
        # Store in memory
        with self.lock:
            self.entries.append(entry)
            self.current_entries += 1
            self.metrics_calculator.update(entry)

        # Write to file if enabled
        if self.enable_file_logging and self.file_manager:
            self.file_manager.write_entry(entry)

        # Log to standard logger based on importance
        self._log_to_standard(entry)

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics (alias for get_metrics)."""
        return self.metrics_calculator.get_performance_summary()

    def get_function_statistics(self, function_name: Optional[str] = None) -> Dict[str, Any]:
        """Get statistics for all functions or a specific function."""
        if function_name:
            return self.get_function_stats(function_name)
        
        # Get stats for all functions
        with self.lock:
            entries_list = list(self.entries)
        
        return self.metrics_calculator.get_all_function_statistics(entries_list)

    def get_audit_trail(self, symbol: Optional[str] = None) -> List[ExecutionLogEntry]:
        """Get audit trail for symbol or all symbols."""
        filters = {}
        if symbol:
            filters["symbol"] = symbol
        
        return self.query_logs(filters, limit=10000)

    def _create_context_snapshot(
        self, context: Optional[ExecutionContext]
    ) -> Dict[str, Any]:
        """Create a lightweight snapshot of execution context.

        Args:
            context: Execution context to snapshot

        Returns:
            Dictionary with key context data
        """
        if not context:
            return {}

        snapshot = {
            "symbol": context.symbol,
            "timeframe": context.timeframe.value,
            "timestamp": context.timestamp.isoformat(),
            "current_bar": {
                "close": float(context.current_bar.close_price),
                "volume": context.current_bar.volume,
                "timestamp": context.current_bar.timestamp.isoformat(),
            }
            if context.current_bar
            else None,
            "has_position": context.has_position,
            "trade_plan_params": context.trade_plan_params,
        }

        if context.position_state:
            snapshot["position"] = {
                "quantity": context.position_state.quantity,
                "entry_price": float(context.position_state.entry_price),
                "pnl_percent": float(context.position_state.unrealized_pnl_percent),
            }

        return snapshot

    def _log_to_standard(self, entry: ExecutionLogEntry) -> None:
        """Log to standard logger based on importance.

        Args:
            entry: Log entry
        """
        if entry.error:
            logger.error(entry.summary)
        elif entry.signal.should_execute:
            logger.warning(entry.summary)
        else:
            logger.debug(entry.summary)

