"""OrderExecutionProvider protocol for order execution abstraction."""

from typing import Protocol, Optional, runtime_checkable

from auto_trader.models.order import Order, OrderResult, BracketOrder, OrderModification


@runtime_checkable
class OrderExecutionProvider(Protocol):
    """Abstract interface for order execution providers.

    Implementations must handle order placement, modification, cancellation,
    and status tracking. The system is agnostic to whether orders are executed
    live or simulated.

    This protocol enables simulation mode for testing trading logic without
    connecting to a real broker.
    """

    async def place_market_order(self, order: Order) -> OrderResult:
        """Place a market order.

        Args:
            order: The order to place.

        Returns:
            OrderResult with success status and order details.
        """
        ...

    async def place_bracket_order(self, bracket: BracketOrder) -> OrderResult:
        """Place a bracket order with parent, stop loss, and take profit.

        Args:
            bracket: The bracket order containing parent and child orders.

        Returns:
            OrderResult with success status and order details.
        """
        ...

    async def modify_order(
        self, order: Order, modification: OrderModification
    ) -> OrderResult:
        """Modify an existing order.

        Args:
            order: The order to modify.
            modification: The modifications to apply.

        Returns:
            OrderResult with success status.
        """
        ...

    async def cancel_order(self, order: Order) -> OrderResult:
        """Cancel an existing order.

        Args:
            order: The order to cancel.

        Returns:
            OrderResult with success status and cancelled state.
        """
        ...

    async def get_order_status(self, order_id: str) -> Optional[Order]:
        """Get the current status of an order.

        Args:
            order_id: The ID of the order to check.

        Returns:
            The Order if found, None otherwise.
        """
        ...
