"""Metrics calculation for execution function performance tracking."""

import asyncio
from typing import Dict, List, Any

from auto_trader.models.execution import ExecutionLogEntry
from auto_trader.models.enums import ExecutionAction


class ExecutionMetricsCalculator:
    """Calculator for execution function performance metrics.
    
    Tracks evaluations, signals, errors, and timing statistics
    for performance monitoring and optimization.
    """

    def __init__(self):
        """Initialize metrics calculator."""
        self.metrics = {
            "total_evaluations": 0,
            "successful_evaluations": 0,
            "failed_evaluations": 0,
            "actions_triggered": 0,
            "avg_duration_ms": 0.0,
            "max_duration_ms": 0.0,
            "min_duration_ms": float("inf"),
        }
        self.lock = asyncio.Lock()  # Use asyncio.Lock for async-safe synchronization

    async def update(self, entry: ExecutionLogEntry) -> None:
        """Update metrics with new log entry.

        Args:
            entry: Log entry to process
        """
        async with self.lock:
            self.metrics["total_evaluations"] += 1

            if entry.error:
                self.metrics["failed_evaluations"] += 1
            else:
                self.metrics["successful_evaluations"] += 1

                if entry.signal.action != ExecutionAction.NONE:
                    self.metrics["actions_triggered"] += 1

            if entry.duration_ms > 0:
                self._update_duration_metrics(entry.duration_ms)

    async def get_summary(self) -> Dict[str, Any]:
        """Get summary of all metrics.

        Returns:
            Dictionary of performance metrics
        """
        async with self.lock:
            return self.metrics.copy()

    def get_function_statistics(
        self, 
        function_name: str, 
        entries: List[ExecutionLogEntry]
    ) -> Dict[str, Any]:
        """Get statistics for a specific function.

        Args:
            function_name: Function to get stats for
            entries: List of log entries for this function

        Returns:
            Dictionary of function statistics
        """
        if not entries:
            return {
                "function": function_name,
                "evaluations": 0,
                "signals": 0,
                "errors": 0,
                "avg_duration_ms": 0.0,
                "max_duration_ms": 0.0,
                "min_duration_ms": 0.0,
                "signal_rate": 0.0,
                "error_rate": 0.0,
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

    async def get_performance_summary(self) -> Dict[str, Any]:
        """Get performance metrics summary (alias for get_summary)."""
        return await self.get_summary()

    def get_all_function_statistics(
        self, 
        entries: List[ExecutionLogEntry]
    ) -> Dict[str, Any]:
        """Get statistics for all functions from entries.

        Args:
            entries: List of all log entries

        Returns:
            Dictionary with statistics for each function
        """
        if not entries:
            return {}

        # Group entries by function name
        function_entries = {}
        for entry in entries:
            if entry.function_name not in function_entries:
                function_entries[entry.function_name] = []
            function_entries[entry.function_name].append(entry)

        # Calculate statistics for each function
        stats = {}
        for function_name, func_entries in function_entries.items():
            stats[function_name] = self.get_function_statistics(
                function_name, func_entries
            )

        return stats

    async def calculate_success_rate(self) -> float:
        """Calculate overall success rate.

        Returns:
            Success rate as percentage (0-100)
        """
        async with self.lock:
            total = self.metrics["total_evaluations"]
            if total == 0:
                return 0.0
            
            successful = self.metrics["successful_evaluations"]
            return (successful / total) * 100.0

    async def calculate_signal_rate(self) -> float:
        """Calculate rate of actions triggered.

        Returns:
            Signal rate as percentage (0-100)
        """
        async with self.lock:
            total = self.metrics["total_evaluations"]
            if total == 0:
                return 0.0
            
            actions = self.metrics["actions_triggered"]
            return (actions / total) * 100.0

    async def reset(self) -> None:
        """Reset all metrics to initial state."""
        async with self.lock:
            self.metrics = {
                "total_evaluations": 0,
                "successful_evaluations": 0,
                "failed_evaluations": 0,
                "actions_triggered": 0,
                "avg_duration_ms": 0.0,
                "max_duration_ms": 0.0,
                "min_duration_ms": float("inf"),
            }

    def _update_duration_metrics(self, duration_ms: float) -> None:
        """Update duration-related metrics.

        Args:
            duration_ms: Duration in milliseconds
        """
        self.metrics["max_duration_ms"] = max(
            self.metrics["max_duration_ms"], duration_ms
        )
        self.metrics["min_duration_ms"] = min(
            self.metrics["min_duration_ms"], duration_ms
        )

        # Update average based on total evaluations (including failed ones)
        total_duration = self.metrics["avg_duration_ms"] * (
            self.metrics["total_evaluations"] - 1
        )
        total_duration += duration_ms
        self.metrics["avg_duration_ms"] = (
            total_duration / self.metrics["total_evaluations"]
        )

