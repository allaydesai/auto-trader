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


class ExecutionLogger:
    """Structured logging system for all execution decisions.

    Provides comprehensive audit trail with querying capabilities
    and performance metrics tracking.
    """

    def __init__(
        self,
        log_dir: Optional[Path] = None,
        max_memory_entries: int = 10000,
        enable_file_logging: bool = True,
    ):
        """Initialize execution logger.

        Args:
            log_dir: Directory for log files (default: logs/execution)
            max_memory_entries: Maximum entries to keep in memory
            enable_file_logging: Whether to write logs to files
        """
        self.log_dir = log_dir or Path("logs/execution")
        self.max_memory_entries = max_memory_entries
        self.enable_file_logging = enable_file_logging

        # In-memory log storage for fast querying
        self.entries: deque = deque(maxlen=max_memory_entries)
        self.lock = Lock()

        # Performance metrics
        self.metrics = {
            "total_evaluations": 0,
            "successful_evaluations": 0,
            "failed_evaluations": 0,
            "actions_triggered": 0,
            "avg_duration_ms": 0.0,
            "max_duration_ms": 0.0,
            "min_duration_ms": float("inf"),
        }

        # Create log directory if file logging enabled
        if self.enable_file_logging:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            self.current_log_file = self._get_log_file_path()
            logger.info(f"ExecutionLogger file logging to: {self.log_dir}")

        logger.info(
            f"ExecutionLogger initialized (memory capacity: {max_memory_entries})"
        )

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

        # Store in memory
        with self.lock:
            self.entries.append(entry)
            self._update_metrics(entry)

        # Write to file if enabled
        if self.enable_file_logging:
            self._write_to_file(entry)

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
            duration_ms=0.0,
            context_snapshot=self._create_context_snapshot(context) if context else {},
            error=error_msg,
        )

        with self.lock:
            self.entries.append(entry)
            self.metrics["failed_evaluations"] += 1

        if self.enable_file_logging:
            self._write_to_file(entry)

        logger.error(f"Execution error in {function_name}: {error_msg}")

    def query_logs(
        self, filters: Optional[Dict[str, Any]] = None, limit: int = 100
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

        if not filters:
            return entries_list[-limit:]

        # Apply filters
        filtered = entries_list

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
        with self.lock:
            return self.metrics.copy()

    def get_function_stats(self, function_name: str) -> Dict[str, Any]:
        """Get statistics for a specific function.

        Args:
            function_name: Function to get stats for

        Returns:
            Dictionary of function statistics
        """
        entries = self.query_logs({"function_name": function_name}, limit=10000)

        if not entries:
            return {
                "function": function_name,
                "evaluations": 0,
                "signals": 0,
                "errors": 0,
                "avg_duration_ms": 0.0,
            }

        signals = sum(1 for e in entries if e.signal.action != ExecutionAction.NONE)
        errors = sum(1 for e in entries if e.error is not None)
        durations = [e.duration_ms for e in entries if e.duration_ms > 0]

        return {
            "function": function_name,
            "evaluations": len(entries),
            "signals": signals,
            "signal_rate": signals / len(entries) if entries else 0,
            "errors": errors,
            "error_rate": errors / len(entries) if entries else 0,
            "avg_duration_ms": sum(durations) / len(durations) if durations else 0,
            "max_duration_ms": max(durations) if durations else 0,
            "min_duration_ms": min(durations) if durations else 0,
        }

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

    def _update_metrics(self, entry: ExecutionLogEntry) -> None:
        """Update performance metrics.

        Args:
            entry: Log entry to process
        """
        self.metrics["total_evaluations"] += 1

        if entry.error:
            self.metrics["failed_evaluations"] += 1
        else:
            self.metrics["successful_evaluations"] += 1

            if entry.signal.action != ExecutionAction.NONE:
                self.metrics["actions_triggered"] += 1

        if entry.duration_ms > 0:
            # Update duration metrics
            self.metrics["max_duration_ms"] = max(
                self.metrics["max_duration_ms"], entry.duration_ms
            )
            self.metrics["min_duration_ms"] = min(
                self.metrics["min_duration_ms"], entry.duration_ms
            )

            # Update average
            total_duration = self.metrics["avg_duration_ms"] * (
                self.metrics["successful_evaluations"] - 1
            )
            total_duration += entry.duration_ms
            self.metrics["avg_duration_ms"] = (
                total_duration / self.metrics["successful_evaluations"]
            )

    def _write_to_file(self, entry: ExecutionLogEntry) -> None:
        """Write log entry to file.

        Args:
            entry: Log entry to write
        """
        try:
            # Check if we need to rotate log file
            if self._should_rotate_log():
                self.current_log_file = self._get_log_file_path()

            # Write as JSON line
            with open(self.current_log_file, "a") as f:
                json_data = entry.model_dump_json()
                f.write(json_data + "\n")

        except Exception as e:
            logger.error(f"Failed to write execution log to file: {e}")

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

    def _get_log_file_path(self) -> Path:
        """Get current log file path.

        Returns:
            Path to log file
        """
        date_str = datetime.now().strftime("%Y%m%d")
        return self.log_dir / f"execution_{date_str}.jsonl"

    def _should_rotate_log(self) -> bool:
        """Check if log file should be rotated.

        Returns:
            True if rotation needed
        """
        if not hasattr(self, "current_log_file"):
            return True

        # Rotate daily
        current_date = datetime.now().strftime("%Y%m%d")
        file_date = self.current_log_file.stem.split("_")[1]

        return current_date != file_date
