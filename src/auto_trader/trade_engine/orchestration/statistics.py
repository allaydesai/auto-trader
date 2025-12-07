"""Statistics collection and reporting for trade orchestration."""

from typing import Dict, Any, List, Optional
from datetime import datetime, UTC
from decimal import Decimal

from auto_trader.models.trade_plan import TradePlan
from auto_trader.models.order import OrderResult


class OrchestrationStatistics:
    """Collects and manages orchestration statistics."""

    def __init__(self):
        """Initialize statistics collector."""
        self.stats = {
            "plans_processed": 0,
            "signals_generated": 0,
            "orders_placed": 0,
            "positions_opened": 0,
            "positions_closed": 0,
            "total_realized_pnl": Decimal("0"),
            "total_dollar_risk": Decimal("0"),
            "processing_errors": 0,
            "last_reset": datetime.now(UTC),
            "start_time": datetime.now(UTC),
        }
        self.plan_history: List[Dict[str, Any]] = []

    def record_plan_processed(self, plan_id: str) -> None:
        """Record a plan being processed.

        Args:
            plan_id: Plan identifier
        """
        self.stats["plans_processed"] += 1
        self.plan_history.append(
            {
                "plan_id": plan_id,
                "action": "processed",
                "timestamp": datetime.now(UTC),
            }
        )

    def record_signal_generated(self, plan_id: str, signal_action: str) -> None:
        """Record a signal being generated.

        Args:
            plan_id: Plan identifier
            signal_action: Signal action type
        """
        self.stats["signals_generated"] += 1
        self.plan_history.append(
            {
                "plan_id": plan_id,
                "action": "signal_generated",
                "signal_action": signal_action,
                "timestamp": datetime.now(UTC),
            }
        )

    def record_order_placed(self, plan_id: str, order_id: str) -> None:
        """Record an order being placed.

        Args:
            plan_id: Plan identifier
            order_id: Order identifier
        """
        self.stats["orders_placed"] += 1
        self.plan_history.append(
            {
                "plan_id": plan_id,
                "action": "order_placed",
                "order_id": order_id,
                "timestamp": datetime.now(UTC),
            }
        )

    def record_position_opened(
        self, plan_id: str, order_result: OrderResult, dollar_risk: Decimal
    ) -> None:
        """Record a position being opened.

        Args:
            plan_id: Plan identifier
            order_result: Order execution result
            dollar_risk: Dollar risk amount
        """
        self.stats["positions_opened"] += 1
        self.stats["total_dollar_risk"] += dollar_risk
        self.plan_history.append(
            {
                "plan_id": plan_id,
                "action": "position_opened",
                "order_id": order_result.order_id,
                "fill_price": order_result.average_fill_price,
                "quantity": order_result.filled_quantity,
                "dollar_risk": dollar_risk,
                "timestamp": datetime.now(UTC),
            }
        )

    def record_position_closed(
        self, plan_id: str, order_result: OrderResult, realized_pnl: Optional[Decimal]
    ) -> None:
        """Record a position being closed.

        Args:
            plan_id: Plan identifier
            order_result: Order execution result
            realized_pnl: Realized P&L if available
        """
        self.stats["positions_closed"] += 1
        if realized_pnl:
            self.stats["total_realized_pnl"] += realized_pnl

        self.plan_history.append(
            {
                "plan_id": plan_id,
                "action": "position_closed",
                "order_id": order_result.order_id,
                "fill_price": order_result.average_fill_price,
                "quantity": order_result.filled_quantity,
                "realized_pnl": realized_pnl,
                "timestamp": datetime.now(UTC),
            }
        )

    def record_processing_error(self, plan_id: str, error_message: str) -> None:
        """Record a processing error.

        Args:
            plan_id: Plan identifier
            error_message: Error message
        """
        self.stats["processing_errors"] += 1
        self.plan_history.append(
            {
                "plan_id": plan_id,
                "action": "processing_error",
                "error": error_message,
                "timestamp": datetime.now(UTC),
            }
        )

    def get_summary(self) -> Dict[str, Any]:
        """Get statistics summary.

        Returns:
            Statistics summary dictionary
        """
        runtime = datetime.now(UTC) - self.stats["start_time"]

        return {
            "runtime_seconds": runtime.total_seconds(),
            "plans_processed": self.stats["plans_processed"],
            "signals_generated": self.stats["signals_generated"],
            "orders_placed": self.stats["orders_placed"],
            "positions_opened": self.stats["positions_opened"],
            "positions_closed": self.stats["positions_closed"],
            "total_realized_pnl": float(self.stats["total_realized_pnl"]),
            "total_dollar_risk": float(self.stats["total_dollar_risk"]),
            "processing_errors": self.stats["processing_errors"],
            "success_rate": self._calculate_success_rate(),
            "avg_processing_time": self._calculate_avg_processing_time(),
        }

    def _calculate_success_rate(self) -> float:
        """Calculate success rate based on errors vs total operations."""
        total_operations = (
            self.stats["plans_processed"]
            + self.stats["signals_generated"]
            + self.stats["orders_placed"]
        )
        if total_operations == 0:
            return 1.0

        success_operations = total_operations - self.stats["processing_errors"]
        return success_operations / total_operations

    def _calculate_avg_processing_time(self) -> float:
        """Calculate average processing time (placeholder)."""
        # This would need actual timing measurements
        return 0.5  # Placeholder: 500ms average

    def reset_statistics(self) -> None:
        """Reset all statistics."""
        self.stats = {
            "plans_processed": 0,
            "signals_generated": 0,
            "orders_placed": 0,
            "positions_opened": 0,
            "positions_closed": 0,
            "total_realized_pnl": Decimal("0"),
            "total_dollar_risk": Decimal("0"),
            "processing_errors": 0,
            "last_reset": datetime.now(UTC),
            "start_time": datetime.now(UTC),
        }
        self.plan_history.clear()


class StatusReporter:
    """Generates status reports for orchestration."""

    def __init__(self, statistics: OrchestrationStatistics):
        """Initialize status reporter.

        Args:
            statistics: Statistics collector
        """
        self.statistics = statistics

    def get_orchestrator_status(
        self,
        is_running: bool,
        active_plans: Dict[str, TradePlan],
        position_plans: Dict[str, TradePlan],
        additional_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate comprehensive orchestrator status.

        Args:
            is_running: Whether orchestrator is running
            active_plans: Active trade plans
            position_plans: Plans with open positions
            additional_data: Additional status data

        Returns:
            Comprehensive status dictionary
        """
        status = {
            "is_running": is_running,
            "active_plans_count": len(active_plans),
            "position_plans_count": len(position_plans),
            "statistics": self.statistics.get_summary(),
            "timestamp": datetime.now(UTC).isoformat(),
        }

        if additional_data:
            status.update(additional_data)

        return status
