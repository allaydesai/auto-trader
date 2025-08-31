"""Lifecycle state validation and consistency checking."""

from typing import List, Dict, Optional
from loguru import logger

from auto_trader.models.trade_plan import TradePlan, TradePlanStatus
from .state import TradeLifecycleState, StateTransitionError


class LifecycleValidator:
    """Validates lifecycle state transitions and consistency."""
    
    def __init__(self):
        """Initialize lifecycle validator."""
        self._validation_cache: Dict[str, bool] = {}
        
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
        # Handle both string and enum values
        current_val = current_status.value if hasattr(current_status, 'value') else current_status
        target_val = target_status.value if hasattr(target_status, 'value') else target_status
        cache_key = f"{current_val}_{target_val}"
        
        if cache_key in self._validation_cache:
            return self._validation_cache[cache_key]
        
        # Define allowed transitions
        allowed_transitions = {
            TradePlanStatus.AWAITING_ENTRY: [
                TradePlanStatus.POSITION_OPEN,
                TradePlanStatus.CANCELLED,
                TradePlanStatus.ERROR,
            ],
            TradePlanStatus.POSITION_OPEN: [
                TradePlanStatus.COMPLETED,
                TradePlanStatus.ERROR,
                TradePlanStatus.CANCELLED,
            ],
            TradePlanStatus.COMPLETED: [],  # Terminal state
            TradePlanStatus.CANCELLED: [],  # Terminal state
            TradePlanStatus.ERROR: [
                TradePlanStatus.AWAITING_ENTRY,  # Allow retry after error
                TradePlanStatus.CANCELLED,
            ],
        }
        
        # Convert to enum for allowed transitions lookup
        if isinstance(current_status, str):
            # Try to find matching enum
            for status_enum in TradePlanStatus:
                if status_enum.value == current_status:
                    current_status = status_enum
                    break
                    
        if isinstance(target_status, str):
            # Try to find matching enum 
            for status_enum in TradePlanStatus:
                if status_enum.value == target_status:
                    target_status = status_enum
                    break
        
        is_valid = target_status in allowed_transitions.get(current_status, [])
        self._validation_cache[cache_key] = is_valid
        
        return is_valid
    
    def validate_state_consistency(self, states: Dict[str, TradeLifecycleState]) -> List[str]:
        """Validate consistency of all lifecycle states.
        
        Args:
            states: Dictionary of lifecycle states by plan_id
            
        Returns:
            List of validation error messages
        """
        validation_errors = []
        
        for plan_id, state in states.items():
            errors = self._validate_single_state(plan_id, state)
            validation_errors.extend(errors)
            
        return validation_errors
    
    def _validate_single_state(self, plan_id: str, state: TradeLifecycleState) -> List[str]:
        """Validate a single lifecycle state.
        
        Args:
            plan_id: Plan identifier
            state: Lifecycle state to validate
            
        Returns:
            List of validation errors for this state
        """
        errors = []
        plan = state.plan
        
        # Validate status consistency
        if plan.status == TradePlanStatus.POSITION_OPEN and not state.has_position:
            errors.append(
                f"Plan {plan_id} marked as POSITION_OPEN but has no position quantity"
            )
        
        if plan.status == TradePlanStatus.AWAITING_ENTRY and state.has_position:
            errors.append(
                f"Plan {plan_id} marked as AWAITING_ENTRY but has position quantity {state.position_quantity}"
            )
        
        # Validate entry price consistency
        if state.has_position and state.entry_price is None:
            errors.append(
                f"Plan {plan_id} has position but no entry price recorded"
            )
        
        # Validate order ID consistency
        if plan.status == TradePlanStatus.POSITION_OPEN and not state.entry_order_id:
            errors.append(
                f"Plan {plan_id} in POSITION_OPEN status but no entry order ID"
            )
        
        # Validate position quantity signs
        if state.position_quantity < 0 and not state.is_short:
            errors.append(
                f"Plan {plan_id} has negative quantity but is_short is False"
            )
        
        if state.position_quantity > 0 and not state.is_long:
            errors.append(
                f"Plan {plan_id} has positive quantity but is_long is False"
            )
        
        return errors
    
    def invalidate_cache(self) -> None:
        """Invalidate validation cache."""
        self._validation_cache.clear()
        logger.debug("Validation cache invalidated")