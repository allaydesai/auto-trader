"""Exit signal validation logic."""

from auto_trader.models.execution import ExecutionSignal
from auto_trader.models.enums import ExecutionAction
from auto_trader.models.trade_plan import TradePlan, TradePlanStatus
from auto_trader.trade_engine.position_entry import PositionEntry
from auto_trader.trade_engine.order_builders import ExitProcessingResult


class ExitSignalValidator:
    """Validates exit signals before processing."""
    
    @staticmethod
    def validate_exit_signal(
        signal: ExecutionSignal,
        trade_plan: TradePlan,
        position: PositionEntry,
    ) -> ExitProcessingResult:
        """Validate exit signal and associated state.
        
        Args:
            signal: Exit signal to validate
            trade_plan: Associated trade plan
            position: Associated position (can be None)
            
        Returns:
            ExitProcessingResult with validation status
        """
        # Validate signal action
        if signal.action not in [ExecutionAction.EXIT, ExecutionAction.MODIFY_STOP]:
            return ExitProcessingResult(
                success=False,
                action_taken="invalid_exit_action",
                error_message=f"Invalid exit action: {signal.action}",
                plan_id=trade_plan.plan_id,
            )
        
        # Check if position exists
        if not position:
            return ExitProcessingResult(
                success=False,
                action_taken="no_position_found",
                error_message=f"No position found for plan {trade_plan.plan_id}",
                plan_id=trade_plan.plan_id,
            )
        
        # Check if position is already closed
        if position.is_closed:
            return ExitProcessingResult(
                success=False,
                action_taken="position_already_closed",
                error_message=f"Position {position.position_id} already closed",
                position_id=position.position_id,
                plan_id=trade_plan.plan_id,
            )
        
        # Validate trade plan status
        if trade_plan.status != TradePlanStatus.POSITION_OPEN:
            return ExitProcessingResult(
                success=False,
                action_taken="invalid_plan_status",
                error_message=f"Plan {trade_plan.plan_id} not in position_open status: {trade_plan.status}",
                position_id=position.position_id,
                plan_id=trade_plan.plan_id,
            )
        
        # All validations passed
        return ExitProcessingResult(
            success=True,
            action_taken="validation_passed",
            position_id=position.position_id,
            plan_id=trade_plan.plan_id,
        )