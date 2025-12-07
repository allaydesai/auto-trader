"""Trade statistics and reporting utilities for orchestrator."""

from typing import Dict, List, Any
from decimal import Decimal

from loguru import logger

from auto_trader.models.trade_plan import TradePlan
from auto_trader.models.order import OrderResult
from auto_trader.trade_engine.position_entry import PositionEntry


class TradeStatisticsCalculator:
    """Utility class for calculating trade and orchestrator statistics."""

    @staticmethod
    def calculate_dollar_risk(plan: TradePlan, order_result: OrderResult) -> Decimal:
        """Calculate dollar risk for a position.

        Args:
            plan: Trade plan
            order_result: Order result

        Returns:
            Dollar risk amount
        """
        entry_price = order_result.average_fill_price
        stop_price = plan.stop_loss
        quantity = order_result.filled_quantity

        return abs((entry_price - stop_price) * quantity)

    @staticmethod
    def get_orchestrator_status_summary(
        is_running: bool,
        active_plans: Dict[str, TradePlan],
        position_plans: Dict[str, str],
        position_manager,
        config,
        signal_processor=None,
        exit_processor=None,
        lifecycle_manager=None,
    ) -> Dict[str, Any]:
        """Get comprehensive orchestrator status summary.

        Args:
            is_running: Whether orchestrator is running
            active_plans: Active trade plans
            position_plans: Position plan mappings
            position_manager: Position state manager
            config: Orchestration configuration
            signal_processor: Signal processor (optional)
            exit_processor: Exit processor (optional)
            lifecycle_manager: Lifecycle manager (optional)

        Returns:
            Dictionary with status information
        """
        # Base status information
        status = {
            "is_running": is_running,
            "active_plans_count": len(active_plans),
            "position_plans_count": len(position_plans),
            "open_positions_count": len(position_manager.get_open_positions()),
            "total_positions": len(position_manager.positions),
            "config": {
                "max_concurrent_trades": config.max_concurrent_trades,
                "risk_validation_enabled": config.enable_risk_validation,
                "position_tracking_enabled": config.enable_position_tracking,
            },
        }

        # Add processor statistics if available
        processors = {}

        if signal_processor:
            try:
                processors["signal_processor_stats"] = (
                    signal_processor.get_processing_statistics()
                )
            except Exception as e:
                logger.warning(f"Error getting signal processor stats: {e}")
                processors["signal_processor_stats"] = {"error": str(e)}

        if exit_processor:
            try:
                processors["exit_processor_stats"] = (
                    exit_processor.get_processing_statistics()
                )
            except Exception as e:
                logger.warning(f"Error getting exit processor stats: {e}")
                processors["exit_processor_stats"] = {"error": str(e)}

        if lifecycle_manager:
            try:
                processors["lifecycle_manager_stats"] = (
                    lifecycle_manager.get_lifecycle_statistics()
                )
            except Exception as e:
                logger.warning(f"Error getting lifecycle manager stats: {e}")
                processors["lifecycle_manager_stats"] = {"error": str(e)}

        # Position manager summary
        try:
            processors["position_manager_summary"] = (
                position_manager.get_position_summary()
            )
        except Exception as e:
            logger.warning(f"Error getting position manager summary: {e}")
            processors["position_manager_summary"] = {"error": str(e)}

        if processors:
            status["processors"] = processors

        return status

    @staticmethod
    def calculate_portfolio_risk_metrics(
        positions: List[PositionEntry], active_plans: Dict[str, TradePlan]
    ) -> Dict[str, Any]:
        """Calculate portfolio-wide risk metrics.

        Args:
            positions: List of positions
            active_plans: Active trade plans

        Returns:
            Dictionary with risk metrics
        """
        open_positions = [pos for pos in positions if not pos.is_closed]

        # Calculate total exposure
        total_exposure = sum(pos.dollar_value for pos in open_positions)

        # Calculate total risk (sum of potential losses)
        total_risk = Decimal("0")
        for pos in open_positions:
            plan = active_plans.get(pos.plan_id)
            if plan:
                risk_per_share = abs(pos.entry_price - plan.stop_loss)
                position_risk = risk_per_share * abs(pos.remaining_quantity)
                total_risk += position_risk

        # Risk-to-exposure ratio
        risk_ratio = float(total_risk / total_exposure) if total_exposure > 0 else 0

        # Position concentration (largest position as % of total)
        if open_positions:
            largest_position = max(pos.dollar_value for pos in open_positions)
            concentration = (
                float(largest_position / total_exposure) if total_exposure > 0 else 0
            )
        else:
            concentration = 0

        # Symbol diversification
        symbols = set(pos.symbol for pos in open_positions)

        return {
            "total_exposure": float(total_exposure),
            "total_risk": float(total_risk),
            "risk_to_exposure_ratio": risk_ratio,
            "position_concentration": concentration,
            "symbols_count": len(symbols),
            "average_position_size": float(total_exposure / len(open_positions))
            if open_positions
            else 0,
            "largest_position": float(max(pos.dollar_value for pos in open_positions))
            if open_positions
            else 0,
        }

    @staticmethod
    def get_plan_execution_summary(
        active_plans: Dict[str, TradePlan], position_plans: Dict[str, str]
    ) -> Dict[str, Any]:
        """Get summary of plan execution status.

        Args:
            active_plans: Active trade plans
            position_plans: Position plan mappings

        Returns:
            Dictionary with plan execution summary
        """
        # Categorize plans by status
        awaiting_entry = []
        position_open = []

        for plan_id, plan in active_plans.items():
            if plan_id in position_plans:
                position_open.append(plan_id)
            else:
                awaiting_entry.append(plan_id)

        # Group by symbol
        symbol_breakdown = {}
        for plan in active_plans.values():
            symbol = plan.symbol
            if symbol not in symbol_breakdown:
                symbol_breakdown[symbol] = {
                    "total_plans": 0,
                    "awaiting_entry": 0,
                    "position_open": 0,
                }

            symbol_breakdown[symbol]["total_plans"] += 1

            if plan.plan_id in position_plans:
                symbol_breakdown[symbol]["position_open"] += 1
            else:
                symbol_breakdown[symbol]["awaiting_entry"] += 1

        return {
            "total_active_plans": len(active_plans),
            "awaiting_entry_count": len(awaiting_entry),
            "position_open_count": len(position_open),
            "symbols_with_plans": len(symbol_breakdown),
            "symbol_breakdown": symbol_breakdown,
            "awaiting_entry_plans": awaiting_entry,
            "position_open_plans": position_open,
        }
