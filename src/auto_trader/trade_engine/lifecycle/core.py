"""Core trade lifecycle management implementation."""

from typing import Dict, List, Optional
from decimal import Decimal
from loguru import logger

from auto_trader.models.trade_plan import TradePlan, TradePlanStatus
from auto_trader.models.order import OrderResult

from .state import TradeLifecycleState
from .validation import LifecycleValidator
from .transitions import StateTransitionManager


class TradeLifecycleManager:
    """Manages trade lifecycle states and transitions."""

    def __init__(self):
        """Initialize lifecycle manager."""
        self.states: Dict[str, TradeLifecycleState] = {}

        # Initialize components
        self.validator = LifecycleValidator()
        self.transition_manager = StateTransitionManager(self.validator)

        logger.info("TradeLifecycleManager initialized")

    def create_lifecycle_state(self, plan: TradePlan) -> TradeLifecycleState:
        """Create a new lifecycle state for a trade plan.

        Args:
            plan: Trade plan to create state for

        Returns:
            New lifecycle state

        Raises:
            ValueError: If state already exists for plan
        """
        if plan.plan_id in self.states:
            raise ValueError(f"Lifecycle state already exists for plan {plan.plan_id}")

        state = TradeLifecycleState(plan=plan)
        self.states[plan.plan_id] = state

        # Invalidate validation cache
        self.validator.invalidate_cache()

        logger.info(f"Created lifecycle state for plan {plan.plan_id}")
        return state

    def get_lifecycle_state(self, plan_id: str) -> Optional[TradeLifecycleState]:
        """Get lifecycle state for a plan.

        Args:
            plan_id: Plan identifier

        Returns:
            Lifecycle state if found
        """
        return self.states.get(plan_id)

    def remove_lifecycle_state(self, plan_id: str) -> bool:
        """Remove lifecycle state for a plan.

        Args:
            plan_id: Plan identifier

        Returns:
            True if state was removed
        """
        if plan_id in self.states:
            del self.states[plan_id]
            self.validator.invalidate_cache()
            logger.info(f"Removed lifecycle state for plan {plan_id}")
            return True
        return False

    def validate_transition(
        self,
        current_status: TradePlanStatus,
        target_status: TradePlanStatus,
    ) -> bool:
        """Validate if a status transition is allowed.

        Args:
            current_status: Current plan status
            target_status: Desired target status

        Returns:
            True if transition is valid
        """
        return self.validator.validate_transition(current_status, target_status)

    # Transition methods delegating to StateTransitionManager
    async def transition_to_position_open(
        self, plan_id: str, order_result: OrderResult
    ) -> None:
        """Transition plan to position open status."""
        state = self.get_lifecycle_state(plan_id)
        if not state:
            raise ValueError(f"No lifecycle state found for plan {plan_id}")

        await self.transition_manager.transition_to_position_open(state, order_result)
        self.validator.invalidate_cache()

    async def transition_to_completed(
        self,
        plan_id: str,
        order_result: OrderResult,
        realized_pnl: Optional[Decimal] = None,
    ) -> None:
        """Transition plan to completed status."""
        state = self.get_lifecycle_state(plan_id)
        if not state:
            raise ValueError(f"No lifecycle state found for plan {plan_id}")

        await self.transition_manager.transition_to_completed(
            state, order_result, realized_pnl
        )
        self.validator.invalidate_cache()

    async def transition_to_error(
        self,
        plan_id: str,
        error_message: str,
        error_context: Optional[str] = None,
    ) -> None:
        """Transition plan to error status."""
        state = self.get_lifecycle_state(plan_id)
        if not state:
            raise ValueError(f"No lifecycle state found for plan {plan_id}")

        await self.transition_manager.transition_to_error(
            state, error_message, error_context
        )
        self.validator.invalidate_cache()

    async def transition_to_cancelled(
        self, plan_id: str, cancellation_reason: str
    ) -> None:
        """Transition plan to cancelled status."""
        state = self.get_lifecycle_state(plan_id)
        if not state:
            raise ValueError(f"No lifecycle state found for plan {plan_id}")

        await self.transition_manager.transition_to_cancelled(
            state, cancellation_reason
        )
        self.validator.invalidate_cache()

    # Query and reporting methods
    def get_plans_by_status(self, status: TradePlanStatus) -> List[TradePlan]:
        """Get all plans with specified status.

        Args:
            status: Target status

        Returns:
            List of plans with the status
        """
        return [
            state.plan for state in self.states.values() if state.plan.status == status
        ]

    def get_open_positions(self) -> List[TradeLifecycleState]:
        """Get all states with open positions.

        Returns:
            List of states with positions
        """
        return [state for state in self.states.values() if state.has_position]

    def get_position_summary(self) -> Dict[str, int]:
        """Get summary of net position quantities by symbol.

        Returns:
            Dictionary mapping symbol to net position quantity
        """
        summary = {}
        for state in self.states.values():
            if state.has_position:
                symbol = state.plan.symbol
                summary[symbol] = summary.get(symbol, 0) + state.position_quantity
        return summary

    def get_lifecycle_statistics(self) -> Dict[str, int]:
        """Get lifecycle management statistics.

        Returns:
            Dictionary with various statistics
        """
        total_states = len(self.states)
        open_positions = len(self.get_open_positions())

        status_counts = {}
        for status in TradePlanStatus:
            count = len(self.get_plans_by_status(status))
            status_counts[status.value] = count

        return {
            "total_states": total_states,
            "open_positions": open_positions,
            **status_counts,
        }

    def validate_state_consistency(self) -> List[str]:
        """Validate consistency of all lifecycle states.

        Returns:
            List of validation error messages
        """
        return self.validator.validate_state_consistency(self.states)

    def cleanup_terminal_states(self) -> int:
        """Remove states for plans in terminal status.

        Returns:
            Number of states removed
        """
        terminal_statuses = {TradePlanStatus.COMPLETED, TradePlanStatus.CANCELLED}

        to_remove = [
            plan_id
            for plan_id, state in self.states.items()
            if state.plan.status in terminal_statuses
        ]

        removed_count = 0
        for plan_id in to_remove:
            if self.remove_lifecycle_state(plan_id):
                removed_count += 1

        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} terminal lifecycle states")

        return removed_count
