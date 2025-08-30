"""Trade lifecycle state management and validation."""

from typing import Dict, Optional, List, Tuple
from datetime import datetime, UTC
from decimal import Decimal

from loguru import logger

from auto_trader.models.trade_plan import TradePlan, TradePlanStatus
from auto_trader.models.order import Order, OrderResult
from auto_trader.models.execution import ExecutionSignal
from auto_trader.models.enums import ExecutionAction, OrderSide


class TradeLifecycleState:
    """Represents the state of a trade throughout its lifecycle."""
    
    def __init__(
        self,
        plan: TradePlan,
        entry_order_id: Optional[str] = None,
        exit_order_id: Optional[str] = None,
        position_quantity: int = 0,
        entry_price: Optional[Decimal] = None,
        created_at: Optional[datetime] = None,
    ):
        """Initialize trade lifecycle state.
        
        Args:
            plan: Associated trade plan
            entry_order_id: ID of entry order
            exit_order_id: ID of exit order
            position_quantity: Current position quantity
            entry_price: Actual entry price
            created_at: State creation timestamp
        """
        self.plan = plan
        self.entry_order_id = entry_order_id
        self.exit_order_id = exit_order_id
        self.position_quantity = position_quantity
        self.entry_price = entry_price
        self.created_at = created_at or datetime.now(UTC)
        self.updated_at = datetime.now(UTC)
        
        # Derived properties
        self.is_long = position_quantity > 0
        self.is_short = position_quantity < 0
        self.has_position = position_quantity != 0
        
    def update(
        self,
        entry_order_id: Optional[str] = None,
        exit_order_id: Optional[str] = None,
        position_quantity: Optional[int] = None,
        entry_price: Optional[Decimal] = None,
    ) -> None:
        """Update lifecycle state.
        
        Args:
            entry_order_id: New entry order ID
            exit_order_id: New exit order ID
            position_quantity: New position quantity
            entry_price: New entry price
        """
        if entry_order_id is not None:
            self.entry_order_id = entry_order_id
        if exit_order_id is not None:
            self.exit_order_id = exit_order_id
        if position_quantity is not None:
            self.position_quantity = position_quantity
            self.is_long = position_quantity > 0
            self.is_short = position_quantity < 0
            self.has_position = position_quantity != 0
        if entry_price is not None:
            self.entry_price = entry_price
            
        self.updated_at = datetime.now(UTC)


class StateTransitionError(Exception):
    """Exception raised when invalid state transition is attempted."""
    pass


class TradeLifecycleManager:
    """Manages trade plan lifecycle states and transitions.
    
    Handles state machine logic for trade plans, ensuring valid transitions
    and maintaining state consistency throughout the trade lifecycle.
    """
    
    def __init__(self):
        """Initialize lifecycle manager."""
        # Track lifecycle states by plan ID
        self.lifecycle_states: Dict[str, TradeLifecycleState] = {}
        
        # Valid state transitions
        self.valid_transitions = {
            TradePlanStatus.AWAITING_ENTRY: [
                TradePlanStatus.POSITION_OPEN,
                TradePlanStatus.CANCELLED,
                TradePlanStatus.ERROR,
            ],
            TradePlanStatus.POSITION_OPEN: [
                TradePlanStatus.COMPLETED,
                TradePlanStatus.CANCELLED,
                TradePlanStatus.ERROR,
            ],
            TradePlanStatus.COMPLETED: [],  # Terminal state
            TradePlanStatus.CANCELLED: [],  # Terminal state
            TradePlanStatus.ERROR: [
                TradePlanStatus.AWAITING_ENTRY,  # Recovery possible
                TradePlanStatus.CANCELLED,
            ],
        }
        
        logger.info("TradeLifecycleManager initialized")
    
    def create_lifecycle_state(self, plan: TradePlan) -> TradeLifecycleState:
        """Create new lifecycle state for a trade plan.
        
        Args:
            plan: Trade plan to create state for
            
        Returns:
            Created lifecycle state
            
        Raises:
            ValueError: If state already exists for plan
        """
        if plan.plan_id in self.lifecycle_states:
            raise ValueError(f"Lifecycle state already exists for plan {plan.plan_id}")
        
        state = TradeLifecycleState(plan)
        self.lifecycle_states[plan.plan_id] = state
        
        logger.debug(f"Created lifecycle state for plan {plan.plan_id}")
        return state
    
    def get_lifecycle_state(self, plan_id: str) -> Optional[TradeLifecycleState]:
        """Get lifecycle state for a plan.
        
        Args:
            plan_id: Trade plan ID
            
        Returns:
            Lifecycle state if exists, None otherwise
        """
        return self.lifecycle_states.get(plan_id)
    
    def remove_lifecycle_state(self, plan_id: str) -> bool:
        """Remove lifecycle state for completed/cancelled plans.
        
        Args:
            plan_id: Trade plan ID
            
        Returns:
            True if state was removed, False if not found
        """
        if plan_id in self.lifecycle_states:
            del self.lifecycle_states[plan_id]
            logger.debug(f"Removed lifecycle state for plan {plan_id}")
            return True
        return False
    
    def validate_transition(
        self, current_status: TradePlanStatus, new_status: TradePlanStatus
    ) -> bool:
        """Validate if status transition is allowed.
        
        Args:
            current_status: Current plan status
            new_status: Proposed new status
            
        Returns:
            True if transition is valid
        """
        valid_next_states = self.valid_transitions.get(current_status, [])
        return new_status in valid_next_states
    
    async def transition_to_position_open(
        self,
        plan: TradePlan,
        entry_order_result: OrderResult,
        position_quantity: int,
        entry_price: Decimal,
    ) -> TradeLifecycleState:
        """Transition plan from awaiting_entry to position_open.
        
        Args:
            plan: Trade plan
            entry_order_result: Successful entry order result
            position_quantity: Actual position quantity
            entry_price: Actual entry price
            
        Returns:
            Updated lifecycle state
            
        Raises:
            StateTransitionError: If transition is invalid
        """
        if not self.validate_transition(plan.status, TradePlanStatus.POSITION_OPEN):
            raise StateTransitionError(
                f"Invalid transition: {plan.status} -> {TradePlanStatus.POSITION_OPEN}"
            )
        
        # Get or create lifecycle state
        state = self.lifecycle_states.get(plan.plan_id)
        if not state:
            state = self.create_lifecycle_state(plan)
        
        # Update state with entry information
        state.update(
            entry_order_id=entry_order_result.order_id,
            position_quantity=position_quantity,
            entry_price=entry_price,
        )
        
        # Update plan status
        plan.status = TradePlanStatus.POSITION_OPEN
        
        logger.info(
            f"Plan {plan.plan_id} transitioned to POSITION_OPEN",
            entry_price=float(entry_price),
            quantity=position_quantity,
            order_id=entry_order_result.order_id,
        )
        
        return state
    
    async def transition_to_completed(
        self,
        plan: TradePlan,
        exit_order_result: OrderResult,
        exit_price: Optional[Decimal] = None,
    ) -> TradeLifecycleState:
        """Transition plan from position_open to completed.
        
        Args:
            plan: Trade plan
            exit_order_result: Successful exit order result
            exit_price: Actual exit price
            
        Returns:
            Final lifecycle state
            
        Raises:
            StateTransitionError: If transition is invalid
        """
        if not self.validate_transition(plan.status, TradePlanStatus.COMPLETED):
            raise StateTransitionError(
                f"Invalid transition: {plan.status} -> {TradePlanStatus.COMPLETED}"
            )
        
        state = self.lifecycle_states.get(plan.plan_id)
        if not state:
            raise StateTransitionError(f"No lifecycle state found for plan {plan.plan_id}")
        
        # Update state with exit information
        state.update(
            exit_order_id=exit_order_result.order_id,
            position_quantity=0,  # Position closed
        )
        
        # Update plan status
        plan.status = TradePlanStatus.COMPLETED
        
        # Calculate P&L if both prices available
        pnl = None
        if state.entry_price and exit_price:
            if state.is_long:
                pnl = (exit_price - state.entry_price) * abs(state.position_quantity)
            else:
                pnl = (state.entry_price - exit_price) * abs(state.position_quantity)
        
        logger.info(
            f"Plan {plan.plan_id} completed successfully",
            exit_price=float(exit_price) if exit_price else None,
            pnl=float(pnl) if pnl else None,
            order_id=exit_order_result.order_id,
        )
        
        return state
    
    async def transition_to_error(
        self, plan: TradePlan, error_reason: str
    ) -> TradeLifecycleState:
        """Transition plan to error state.
        
        Args:
            plan: Trade plan
            error_reason: Description of error
            
        Returns:
            Updated lifecycle state
        """
        if not self.validate_transition(plan.status, TradePlanStatus.ERROR):
            # Log warning but allow error transitions from any state
            logger.warning(
                f"Unusual error transition: {plan.status.value} -> ERROR",
                plan_id=plan.plan_id,
                error=error_reason,
            )
        
        # Get or create lifecycle state
        state = self.lifecycle_states.get(plan.plan_id)
        if not state:
            state = self.create_lifecycle_state(plan)
        
        # Update plan status
        old_status = plan.status
        plan.status = TradePlanStatus.ERROR
        
        logger.error(
            f"Plan {plan.plan_id} transitioned to ERROR state",
            old_status=old_status,
            error=error_reason,
        )
        
        return state
    
    async def transition_to_cancelled(
        self, plan: TradePlan, cancel_reason: str
    ) -> TradeLifecycleState:
        """Transition plan to cancelled state.
        
        Args:
            plan: Trade plan
            cancel_reason: Reason for cancellation
            
        Returns:
            Updated lifecycle state
            
        Raises:
            StateTransitionError: If transition is invalid
        """
        if not self.validate_transition(plan.status, TradePlanStatus.CANCELLED):
            raise StateTransitionError(
                f"Invalid transition: {plan.status} -> {TradePlanStatus.CANCELLED}"
            )
        
        # Get or create lifecycle state
        state = self.lifecycle_states.get(plan.plan_id)
        if not state:
            state = self.create_lifecycle_state(plan)
        
        # Update plan status
        old_status = plan.status
        plan.status = TradePlanStatus.CANCELLED
        
        logger.info(
            f"Plan {plan.plan_id} cancelled",
            old_status=old_status,
            reason=cancel_reason,
        )
        
        return state
    
    def get_plans_by_status(self, status: TradePlanStatus) -> List[TradePlan]:
        """Get all plans with specified status.
        
        Args:
            status: Status to filter by
            
        Returns:
            List of plans with the specified status
        """
        return [
            state.plan
            for state in self.lifecycle_states.values()
            if state.plan.status == status
        ]
    
    def get_open_positions(self) -> List[TradeLifecycleState]:
        """Get all lifecycle states with open positions.
        
        Returns:
            List of states with open positions
        """
        return [
            state
            for state in self.lifecycle_states.values()
            if state.has_position
        ]
    
    def get_position_summary(self) -> Dict[str, int]:
        """Get summary of current positions by symbol.
        
        Returns:
            Dictionary mapping symbol to net position quantity
        """
        position_summary: Dict[str, int] = {}
        
        for state in self.lifecycle_states.values():
            if state.has_position:
                symbol = state.plan.symbol
                position_summary[symbol] = position_summary.get(symbol, 0) + state.position_quantity
        
        return position_summary
    
    def get_lifecycle_statistics(self) -> Dict[str, int]:
        """Get statistics about lifecycle states.
        
        Returns:
            Dictionary with counts by status and other metrics
        """
        stats = {
            "total_states": len(self.lifecycle_states),
            "awaiting_entry": 0,
            "position_open": 0,
            "completed": 0,
            "cancelled": 0,
            "error": 0,
            "open_positions": 0,
        }
        
        for state in self.lifecycle_states.values():
            status_key = state.plan.status.lower()
            if status_key in stats:
                stats[status_key] += 1
            
            if state.has_position:
                stats["open_positions"] += 1
        
        return stats
    
    def validate_state_consistency(self) -> List[str]:
        """Validate consistency of all lifecycle states.
        
        Returns:
            List of consistency errors found
        """
        errors = []
        
        for plan_id, state in self.lifecycle_states.items():
            # Check plan status matches expected state
            plan_status = state.plan.status
            
            if plan_status == TradePlanStatus.AWAITING_ENTRY:
                if state.has_position:
                    errors.append(f"Plan {plan_id}: AWAITING_ENTRY but has position")
                if state.entry_order_id:
                    errors.append(f"Plan {plan_id}: AWAITING_ENTRY but has entry order")
            
            elif plan_status == TradePlanStatus.POSITION_OPEN:
                if not state.has_position:
                    errors.append(f"Plan {plan_id}: POSITION_OPEN but no position")
                if not state.entry_order_id:
                    errors.append(f"Plan {plan_id}: POSITION_OPEN but no entry order ID")
            
            elif plan_status in [TradePlanStatus.COMPLETED, TradePlanStatus.CANCELLED]:
                if state.has_position:
                    errors.append(f"Plan {plan_id}: {plan_status.value} but still has position")
        
        return errors
    
    def cleanup_terminal_states(self) -> int:
        """Remove lifecycle states for completed and cancelled plans.
        
        Returns:
            Number of states removed
        """
        terminal_statuses = [TradePlanStatus.COMPLETED, TradePlanStatus.CANCELLED]
        to_remove = []
        
        for plan_id, state in self.lifecycle_states.items():
            if state.plan.status in terminal_statuses:
                to_remove.append(plan_id)
        
        for plan_id in to_remove:
            self.remove_lifecycle_state(plan_id)
        
        if to_remove:
            logger.info(f"Cleaned up {len(to_remove)} terminal lifecycle states")
        
        return len(to_remove)