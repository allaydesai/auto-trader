"""IBKR order execution adapter using ib-async."""

from decimal import Decimal
from datetime import datetime, UTC
from typing import Dict, Callable, Optional

from ib_async import IB, Stock, MarketOrder, LimitOrder, StopOrder, Trade
from ib_async import OrderStatus as IBOrderStatus

from ...logging_config import get_logger
from ...models.order import Order, OrderResult, BracketOrder, OrderModification
from ...models.enums import OrderType, OrderStatus
from .client import IBKRClient, IBKRError

logger = get_logger("ibkr_order_adapter", "trades")


class IBKROrderAdapter:
    """
    Handles real order execution through IBKR using ib-async.
    
    Provides integration with Interactive Brokers for live order placement,
    modification, cancellation, and status tracking.
    """
    
    def __init__(self, ibkr_client: IBKRClient) -> None:
        """Initialize IBKR adapter."""
        self.ibkr_client = ibkr_client
        self._order_trades: Dict[str, Trade] = {}  # Track ib-async Trade objects
        self._status_update_callback: Optional[Callable] = None
        
        logger.info("IBKROrderAdapter initialized")
    
    async def setup_event_handlers(self, status_callback: Callable) -> None:
        """Setup ib-async event handlers for order tracking."""
        self._status_update_callback = status_callback
        
        # Get IB connection from client
        if hasattr(self.ibkr_client, '_ib') and self.ibkr_client._ib:
            ib = self.ibkr_client._ib
            
            # Set up order status event handler (only if not a mock)
            if hasattr(ib, 'orderStatusEvent') and not hasattr(ib.orderStatusEvent, '_mock_name'):
                ib.orderStatusEvent += self._on_order_status_update
                ib.execDetailsEvent += self._on_execution_update
                logger.debug("IBKR event handlers configured")
            else:
                logger.debug("Skipping event handler setup for mock object")
    
    async def place_market_order(self, order: Order) -> OrderResult:
        """Execute real market order through IBKR."""
        try:
            ib = self.ibkr_client._ib
            
            # Create and qualify contract
            contract = Stock(order.symbol, 'SMART', order.currency)
            await ib.qualifyContractsAsync(contract)
            
            # Create market order
            ib_order: MarketOrder = MarketOrder(
                action=order.side.value if hasattr(order.side, 'value') else str(order.side),
                totalQuantity=order.quantity
            )
            ib_order.tif = order.time_in_force.value if hasattr(order.time_in_force, 'value') else str(order.time_in_force)
            
            # Place order with IBKR
            trade = ib.placeOrder(contract, ib_order)
            order.order_id = str(trade.order.orderId)
            order.status = self._map_ibkr_status(trade.orderStatus.status)
            order.submitted_at = datetime.now(UTC)
            
            # Track the trade object
            self._order_trades[order.order_id] = trade
            
            logger.info(
                "Market order placed with IBKR",
                order_id=order.order_id,
                symbol=order.symbol,
                ibkr_status=trade.orderStatus.status,
            )
            
            return OrderResult(
                success=True,
                order_id=order.order_id,
                trade_plan_id=order.trade_plan_id,
                order_status=order.status,
                error_message=None,
                error_code=None,
                processing_time_ms=None,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                order_type=order.order_type,
            )
            
        except Exception as e:
            logger.error("IBKR market order execution failed", error=str(e))
            return self._create_ibkr_error_result(order, str(e))
    
    async def place_bracket_order(self, bracket: BracketOrder) -> OrderResult:
        """Execute real bracket order through IBKR."""
        try:
            ib = self.ibkr_client._ib
            
            # Create and qualify contract
            contract = Stock(bracket.parent_order.symbol, 'SMART', bracket.parent_order.currency)
            await ib.qualifyContractsAsync(contract)
            
            # Get next order IDs for the bracket
            parent_id = ib.client.getReqId()
            stop_id = ib.client.getReqId()  
            profit_id = ib.client.getReqId()
            
            # Create parent order
            action = bracket.parent_order.side.value if hasattr(bracket.parent_order.side, 'value') else str(bracket.parent_order.side)
            if bracket.parent_order.order_type == OrderType.MARKET:
                parent_ib_order = MarketOrder(
                    action=action,
                    totalQuantity=bracket.parent_order.quantity
                )
            else:
                parent_ib_order = LimitOrder(
                    action=action,
                    totalQuantity=bracket.parent_order.quantity,
                    lmtPrice=float(bracket.parent_order.price) if bracket.parent_order.price else 0.0
                )
            
            # Configure parent order for bracket
            parent_ib_order.orderId = parent_id
            parent_ib_order.transmit = False
            
            # Create stop loss order (child)
            stop_action = bracket.stop_loss_order.side.value if hasattr(bracket.stop_loss_order.side, 'value') else str(bracket.stop_loss_order.side)
            stop_ib_order = StopOrder(
                action=stop_action,
                totalQuantity=bracket.stop_loss_order.quantity,
                stopPrice=float(bracket.stop_loss_order.stop_price) if bracket.stop_loss_order.stop_price else 0.0
            )
            stop_ib_order.orderId = stop_id
            stop_ib_order.parentId = parent_id
            stop_ib_order.transmit = False
            
            # Create take profit order (child)
            profit_action = bracket.take_profit_order.side.value if hasattr(bracket.take_profit_order.side, 'value') else str(bracket.take_profit_order.side)
            profit_ib_order = LimitOrder(
                action=profit_action,
                totalQuantity=bracket.take_profit_order.quantity,
                lmtPrice=float(bracket.take_profit_order.price) if bracket.take_profit_order.price else 0.0
            )
            profit_ib_order.orderId = profit_id
            profit_ib_order.parentId = parent_id
            profit_ib_order.transmit = True  # Transmit all orders when this is placed
            
            # Place orders in sequence
            parent_trade = ib.placeOrder(contract, parent_ib_order)
            stop_trade = ib.placeOrder(contract, stop_ib_order)
            profit_trade = ib.placeOrder(contract, profit_ib_order)
            
            # Update order objects with IDs and status
            bracket.parent_order.order_id = str(parent_id)
            bracket.stop_loss_order.order_id = str(stop_id)
            bracket.take_profit_order.order_id = str(profit_id)
            
            bracket.parent_order.status = self._map_ibkr_status(parent_trade.orderStatus.status)
            bracket.stop_loss_order.status = self._map_ibkr_status(stop_trade.orderStatus.status)
            bracket.take_profit_order.status = self._map_ibkr_status(profit_trade.orderStatus.status)
            
            bracket.all_orders_submitted = True
            
            # Track trade objects
            self._order_trades[bracket.parent_order.order_id] = parent_trade
            self._order_trades[bracket.stop_loss_order.order_id] = stop_trade
            self._order_trades[bracket.take_profit_order.order_id] = profit_trade
            
            logger.info(
                "Bracket order placed with IBKR",
                parent_id=bracket.parent_order.order_id,
                stop_id=bracket.stop_loss_order.order_id,
                profit_id=bracket.take_profit_order.order_id,
                symbol=bracket.parent_order.symbol,
            )
            
            return OrderResult(
                success=True,
                order_id=bracket.parent_order.order_id,
                trade_plan_id=bracket.trade_plan_id,
                order_status=bracket.parent_order.status,
                error_message=None,
                error_code=None,
                processing_time_ms=None,
                symbol=bracket.parent_order.symbol,
                side=bracket.parent_order.side,
                quantity=bracket.parent_order.quantity,
                order_type=bracket.parent_order.order_type,
            )
            
        except Exception as e:
            logger.error("IBKR bracket order execution failed", error=str(e))
            return self._create_ibkr_error_result(bracket.parent_order, str(e))
    
    async def modify_order(self, order: Order, modification: OrderModification) -> OrderResult:
        """Execute real order modification through IBKR."""
        try:
            if order.order_id not in self._order_trades:
                raise IBKRError(f"Trade object not found for order {order.order_id}")
            
            ib = self.ibkr_client._ib
            trade = self._order_trades[order.order_id]
            
            # Clone the existing order for modification
            modified_order = trade.order
            
            # Apply modifications
            if modification.new_price and hasattr(modified_order, 'lmtPrice'):
                modified_order.lmtPrice = float(modification.new_price)
                order.price = modification.new_price
                
            if modification.new_stop_price and hasattr(modified_order, 'stopPrice'):
                modified_order.stopPrice = float(modification.new_stop_price)
                order.stop_price = modification.new_stop_price
                    
            if modification.new_quantity:
                modified_order.totalQuantity = modification.new_quantity
                order.quantity = modification.new_quantity
            
            # Send modification to IBKR
            ib.placeOrder(trade.contract, modified_order)
            
            logger.info(
                "Order modification sent to IBKR",
                order_id=order.order_id,
                new_price=float(modification.new_price) if modification.new_price else None,
                new_quantity=modification.new_quantity,
            )
            
            return OrderResult(
                success=True,
                order_id=order.order_id,
                trade_plan_id=order.trade_plan_id,
                order_status=order.status,
                error_message=None,
                error_code=None,
                processing_time_ms=None,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                order_type=order.order_type,
            )
            
        except Exception as e:
            logger.error("IBKR order modification failed", error=str(e))
            return self._create_ibkr_error_result(order, str(e))
    
    async def cancel_order(self, order: Order) -> OrderResult:
        """Execute real order cancellation through IBKR."""
        try:
            if order.order_id not in self._order_trades:
                raise IBKRError(f"Trade object not found for order {order.order_id}")
            
            ib = self.ibkr_client._ib
            trade = self._order_trades[order.order_id]
            
            # Cancel the order
            ib.cancelOrder(trade.order)
            
            # Wait for cancellation confirmation
            import asyncio
            await asyncio.sleep(0.5)
            
            order.status = OrderStatus.CANCELLED
            
            logger.info(
                "Order cancellation sent to IBKR",
                order_id=order.order_id,
                symbol=order.symbol,
            )
            
            return OrderResult(
                success=True,
                order_id=order.order_id,
                trade_plan_id=order.trade_plan_id,
                order_status=order.status,
                error_message=None,
                error_code=None,
                processing_time_ms=None,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                order_type=order.order_type,
            )
            
        except Exception as e:
            logger.error("IBKR order cancellation failed", error=str(e))
            return self._create_ibkr_error_result(order, str(e))
    
    def _on_order_status_update(self, trade: Trade) -> None:
        """Handle order status updates from ib-async."""
        try:
            order_id = str(trade.order.orderId)
            old_status = OrderStatus.PENDING  # Default, should be tracked better
            new_status = self._map_ibkr_status(trade.orderStatus.status)
            
            logger.info(
                "Order status updated from IBKR",
                order_id=order_id,
                new_status=new_status,
                filled_quantity=int(trade.orderStatus.filled),
            )
            
            # Notify the execution manager
            if self._status_update_callback:
                self._status_update_callback(order_id, old_status, new_status)
                
        except Exception as e:
            logger.error("Order status update handler error", error=str(e))
    
    def _on_execution_update(self, trade: Trade, fill: object) -> None:
        """Handle execution updates from ib-async."""
        try:
            order_id = str(trade.order.orderId)
            
            logger.info(
                "Order execution update from IBKR",
                order_id=order_id,
                fill_price=fill.execution.price,
                fill_shares=fill.execution.shares,
                commission=fill.commissionReport.commission if fill.commissionReport else None,
            )
            
        except Exception as e:
            logger.error("Execution update handler error", error=str(e))
    
    def _map_ibkr_status(self, ibkr_status: str) -> OrderStatus:
        """Map IBKR order status to internal OrderStatus."""
        status_mapping = {
            "PendingSubmit": OrderStatus.PENDING,
            "PendingCancel": OrderStatus.PENDING,
            "PreSubmitted": OrderStatus.SUBMITTED,
            "Submitted": OrderStatus.SUBMITTED,
            "Cancelled": OrderStatus.CANCELLED,
            "Filled": OrderStatus.FILLED,
            "Inactive": OrderStatus.REJECTED,
        }
        return status_mapping.get(ibkr_status, OrderStatus.PENDING)
    
    def _create_ibkr_error_result(self, order: Order, error_msg: str) -> OrderResult:
        """Create error result for IBKR execution failures."""
        return OrderResult(
            success=False,
            order_id=order.order_id,
            trade_plan_id=order.trade_plan_id,
            order_status=OrderStatus.REJECTED,
            error_message=f"IBKR execution failed: {error_msg}",
            error_code=None,
            processing_time_ms=None,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            order_type=order.order_type,
        )