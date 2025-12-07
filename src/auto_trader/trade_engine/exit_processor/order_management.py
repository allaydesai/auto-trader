"""Order management for exit processing."""

from typing import List, Dict, Any
from decimal import Decimal
from loguru import logger

from auto_trader.models.execution import ExecutionSignal, ExecutionContext
from auto_trader.models.trade_plan import TradePlan
from auto_trader.models.order import OrderResult
from auto_trader.trade_engine.position_entry import PositionEntry
from auto_trader.trade_engine.order_builders import ExitOrderBuilder
from auto_trader.integrations.ibkr_client.order_execution_manager import (
    OrderExecutionManager,
)


class OrderCancellationManager:
    """Manages order cancellation logic."""

    def __init__(self, order_execution_manager: OrderExecutionManager):
        """Initialize order cancellation manager.

        Args:
            order_execution_manager: Order execution system
        """
        self.order_execution_manager = order_execution_manager

    async def cancel_symbol_orders(
        self, symbol: str, position: PositionEntry, processing_stats: Dict[str, Any]
    ) -> List[str]:
        """Cancel all active orders for a symbol associated with position.

        Args:
            symbol: Trading symbol
            position: Position entry
            processing_stats: Statistics tracking dictionary

        Returns:
            List of cancelled order IDs
        """
        try:
            cancelled_orders = []

            # Get all active orders for the symbol
            active_orders = await self.order_execution_manager.get_active_orders()
            symbol_orders = [
                order
                for order in active_orders
                if order.symbol == symbol and order.order_id in position.exit_order_ids
            ]

            # Cancel each order
            for order in symbol_orders:
                try:
                    cancel_result = await self.order_execution_manager.cancel_order(
                        order.order_id
                    )
                    if cancel_result.success:
                        cancelled_orders.append(order.order_id)
                        processing_stats["orders_cancelled"] += 1
                        logger.debug(
                            f"Cancelled order {order.order_id} for symbol {symbol}"
                        )
                    else:
                        logger.warning(
                            f"Failed to cancel order {order.order_id}: {cancel_result.error_message}"
                        )
                except Exception as e:
                    logger.error(f"Error cancelling order {order.order_id}: {e}")

            if cancelled_orders:
                logger.info(f"Cancelled {len(cancelled_orders)} orders for {symbol}")

            return cancelled_orders

        except Exception as e:
            logger.error(f"Error cancelling orders for {symbol}: {e}")
            return []


class ExitOrderManager:
    """Manages creation and execution of exit orders."""

    def __init__(self, order_execution_manager: OrderExecutionManager):
        """Initialize exit order manager.

        Args:
            order_execution_manager: Order execution system
        """
        self.order_execution_manager = order_execution_manager

    def create_exit_order_request(
        self,
        signal: ExecutionSignal,
        context: ExecutionContext,
        trade_plan: TradePlan,
        position: PositionEntry,
    ):
        """Create exit order request.

        Args:
            signal: Exit signal
            context: Execution context
            trade_plan: Trade plan
            position: Position to exit

        Returns:
            Order request for exit
        """
        metadata = {
            "function_name": signal.metadata.get("function_name", "unknown"),
            "exit_context": "signal_triggered",
        }
        return ExitOrderBuilder.create_exit_order_request(
            signal=signal,
            trade_plan=trade_plan,
            position=position,
            metadata=metadata,
        )

    def create_stop_order_request(
        self,
        trade_plan: TradePlan,
        position: PositionEntry,
        stop_price: Decimal,
    ):
        """Create stop order request.

        Args:
            trade_plan: Trade plan
            position: Position
            stop_price: New stop price

        Returns:
            Stop order request
        """
        metadata = {"stop_context": "trailing_stop_adjustment"}
        return ExitOrderBuilder.create_stop_order_request(
            trade_plan=trade_plan,
            position=position,
            stop_price=stop_price,
            metadata=metadata,
        )

    async def execute_exit_order(self, order_request) -> OrderResult:
        """Execute an exit order.

        Args:
            order_request: Exit order request

        Returns:
            OrderResult from execution
        """
        return await self.order_execution_manager.place_order(order_request)

    async def execute_stop_modification(self, order_request) -> OrderResult:
        """Execute a stop order modification.

        Args:
            order_request: Stop modification order request

        Returns:
            OrderResult from execution
        """
        return await self.order_execution_manager.modify_order(order_request)
