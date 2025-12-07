"""Trade lifecycle state management."""

from typing import Optional
from datetime import datetime, UTC
from decimal import Decimal

from auto_trader.models.trade_plan import TradePlan


class StateTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    pass


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
        """Update lifecycle state fields.

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

    def __repr__(self) -> str:
        """String representation of lifecycle state."""
        return (
            f"TradeLifecycleState(plan_id='{self.plan.plan_id}', "
            f"status={self.plan.status}, quantity={self.position_quantity}, "
            f"entry_price={self.entry_price})"
        )
