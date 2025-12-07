"""Lifecycle state transition operations."""

from typing import Optional
from datetime import datetime, UTC
from decimal import Decimal
from loguru import logger

from auto_trader.models.trade_plan import TradePlanStatus
from auto_trader.models.order import OrderResult
from .state import TradeLifecycleState, StateTransitionError
from .validation import LifecycleValidator


class StateTransitionManager:
    """Manages lifecycle state transitions."""

    def __init__(self, validator: LifecycleValidator):
        """Initialize transition manager.

        Args:
            validator: Lifecycle validator
        """
        self.validator = validator

    async def transition_to_position_open(
        self,
        state: TradeLifecycleState,
        order_result: OrderResult,
    ) -> None:
        """Transition a plan to position_open status.

        Args:
            state: Lifecycle state to transition
            order_result: Entry order result

        Raises:
            StateTransitionError: If transition is invalid
        """
        plan = state.plan

        if not self.validator.validate_transition(
            plan.status, TradePlanStatus.POSITION_OPEN
        ):
            raise StateTransitionError(
                f"Invalid transition from {plan.status} to POSITION_OPEN for plan {plan.plan_id}"
            )

        logger.info(
            f"Transitioning plan {plan.plan_id} to POSITION_OPEN",
            current_status=plan.status.value
            if hasattr(plan.status, "value")
            else plan.status,
            order_id=order_result.order_id,
        )

        # Update plan status
        plan.status = TradePlanStatus.POSITION_OPEN

        # Update lifecycle state
        state.update(
            entry_order_id=order_result.order_id,
            position_quantity=order_result.filled_quantity,
            entry_price=order_result.average_fill_price,
        )

        logger.info(
            f"Plan {plan.plan_id} transitioned to POSITION_OPEN",
            quantity=order_result.filled_quantity,
            entry_price=order_result.average_fill_price,
        )

    async def transition_to_completed(
        self,
        state: TradeLifecycleState,
        order_result: OrderResult,
        realized_pnl: Optional[Decimal] = None,
    ) -> None:
        """Transition a plan to completed status.

        Args:
            state: Lifecycle state to transition
            order_result: Exit order result
            realized_pnl: Realized P&L if calculated

        Raises:
            StateTransitionError: If transition is invalid
        """
        plan = state.plan

        if not self.validator.validate_transition(
            plan.status, TradePlanStatus.COMPLETED
        ):
            raise StateTransitionError(
                f"Invalid transition from {plan.status} to COMPLETED for plan {plan.plan_id}"
            )

        logger.info(
            f"Transitioning plan {plan.plan_id} to COMPLETED",
            current_status=plan.status.value
            if hasattr(plan.status, "value")
            else plan.status,
            exit_order_id=order_result.order_id,
            realized_pnl=realized_pnl,
        )

        # Update plan status
        plan.status = TradePlanStatus.COMPLETED

        # Update lifecycle state
        state.update(
            exit_order_id=order_result.order_id,
            position_quantity=0,  # Position fully closed
        )

        logger.info(
            f"Plan {plan.plan_id} completed successfully",
            realized_pnl=realized_pnl,
            exit_price=order_result.average_fill_price,
        )

    async def transition_to_error(
        self,
        state: TradeLifecycleState,
        error_message: str,
        error_context: Optional[str] = None,
    ) -> None:
        """Transition a plan to error status.

        Args:
            state: Lifecycle state to transition
            error_message: Error description
            error_context: Additional error context

        Raises:
            StateTransitionError: If transition is invalid
        """
        plan = state.plan

        if not self.validator.validate_transition(plan.status, TradePlanStatus.ERROR):
            raise StateTransitionError(
                f"Invalid transition from {plan.status} to ERROR for plan {plan.plan_id}"
            )

        logger.error(
            f"Transitioning plan {plan.plan_id} to ERROR",
            current_status=plan.status.value
            if hasattr(plan.status, "value")
            else plan.status,
            error=error_message,
            context=error_context,
        )

        # Update plan status
        plan.status = TradePlanStatus.ERROR

        # No lifecycle state updates needed for error transitions
        state.updated_at = datetime.now(UTC)

        logger.error(f"Plan {plan.plan_id} marked as ERROR: {error_message}")

    async def transition_to_cancelled(
        self,
        state: TradeLifecycleState,
        cancellation_reason: str,
    ) -> None:
        """Transition a plan to cancelled status.

        Args:
            state: Lifecycle state to transition
            cancellation_reason: Reason for cancellation

        Raises:
            StateTransitionError: If transition is invalid
        """
        plan = state.plan

        if not self.validator.validate_transition(
            plan.status, TradePlanStatus.CANCELLED
        ):
            raise StateTransitionError(
                f"Invalid transition from {plan.status} to CANCELLED for plan {plan.plan_id}"
            )

        logger.info(
            f"Transitioning plan {plan.plan_id} to CANCELLED",
            current_status=plan.status.value
            if hasattr(plan.status, "value")
            else plan.status,
            reason=cancellation_reason,
        )

        # Update plan status
        plan.status = TradePlanStatus.CANCELLED

        # Update lifecycle state
        state.updated_at = datetime.now(UTC)

        logger.info(f"Plan {plan.plan_id} cancelled: {cancellation_reason}")
