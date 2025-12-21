"""Simulated order execution implementation for simulation mode."""

from typing import Optional, Dict, Any

from auto_trader.integrations.ibkr_client.order_simulation_engine import (
    OrderSimulationEngine,
)
from auto_trader.models.order import Order, OrderResult, BracketOrder, OrderModification
from auto_trader.models.enums import OrderStatus


class SimulatedOrderExecution:
    """Simulated order execution provider for simulation mode.

    Wraps the existing OrderSimulationEngine and adds order tracking
    and statistics. All orders are simulated without connecting to IBKR.
    """

    def __init__(self) -> None:
        """Initialize the simulated execution provider."""
        self._engine = OrderSimulationEngine()
        self._orders: Dict[str, Order] = {}
        self._stats = {
            "orders_placed": 0,
            "orders_filled": 0,
            "orders_cancelled": 0,
            "orders_modified": 0,
            "is_simulation": True,
        }

    async def place_market_order(self, order: Order) -> OrderResult:
        """Place a simulated market order.

        Args:
            order: The order to place.

        Returns:
            OrderResult with success status and order details.
        """
        result = await self._engine.place_market_order(order)

        if result.success and result.order_id:
            self._orders[result.order_id] = order
            self._stats["orders_placed"] += 1
            if result.order_status == OrderStatus.FILLED:
                self._stats["orders_filled"] += 1

        return result

    async def place_bracket_order(self, bracket: BracketOrder) -> OrderResult:
        """Place a simulated bracket order.

        Args:
            bracket: The bracket order containing parent and child orders.

        Returns:
            OrderResult with success status and order details.
        """
        result = await self._engine.place_bracket_order(bracket)

        if result.success:
            # Track all orders in the bracket
            if bracket.parent_order.order_id:
                self._orders[bracket.parent_order.order_id] = bracket.parent_order
            if bracket.stop_loss_order.order_id:
                self._orders[bracket.stop_loss_order.order_id] = bracket.stop_loss_order
            if bracket.take_profit_order.order_id:
                self._orders[bracket.take_profit_order.order_id] = (
                    bracket.take_profit_order
                )

            self._stats["orders_placed"] += 3  # Parent + SL + TP
            if result.order_status == OrderStatus.FILLED:
                self._stats["orders_filled"] += 1

        return result

    async def modify_order(
        self, order: Order, modification: OrderModification
    ) -> OrderResult:
        """Modify a simulated order.

        Args:
            order: The order to modify.
            modification: The modifications to apply.

        Returns:
            OrderResult with success status.
        """
        result = await self._engine.modify_order(order, modification)

        if result.success:
            self._stats["orders_modified"] += 1
            # Update tracked order
            if order.order_id and order.order_id in self._orders:
                self._orders[order.order_id] = order

        return result

    async def cancel_order(self, order: Order) -> OrderResult:
        """Cancel a simulated order.

        Args:
            order: The order to cancel.

        Returns:
            OrderResult with success status and cancelled state.
        """
        result = await self._engine.cancel_order(order)

        if result.success:
            self._stats["orders_cancelled"] += 1
            # Update tracked order
            if order.order_id and order.order_id in self._orders:
                self._orders[order.order_id] = order

        return result

    async def get_order_status(self, order_id: str) -> Optional[Order]:
        """Get the current status of an order.

        Args:
            order_id: The ID of the order to check.

        Returns:
            The Order if found, None otherwise.
        """
        return self._orders.get(order_id)

    def get_stats(self) -> Dict[str, Any]:
        """Get execution statistics.

        Returns:
            Dictionary containing order statistics.
        """
        return self._stats.copy()
