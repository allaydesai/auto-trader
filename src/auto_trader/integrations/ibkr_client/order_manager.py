"""Order execution manager for IBKR integration using ib-async."""

from __future__ import annotations

import asyncio
import uuid
from decimal import Decimal
from datetime import datetime, UTC
from pathlib import Path
from typing import Dict, List, Optional, Callable

from ib_async import IB, Stock, MarketOrder, LimitOrder, StopOrder, StopLimitOrder, Trade
from ib_async import OrderStatus as IBOrderStatus, OrderState

from ...logging_config import get_logger
from ...models.order import (
    Order,
    OrderRequest,
    OrderResult,
    BracketOrder,
    OrderEvent,
    OrderModification,
)
from ...models.enums import (
    OrderType,
    OrderSide, 
    OrderStatus,
    TimeInForce,
)
from ...risk_management import OrderRiskValidator, RiskValidationResult
from .client import IBKRClient, IBKRError
from .state_manager import OrderStateManager

logger = get_logger("order_manager", "trades")


class OrderExecutionError(IBKRError):
    """Error during order execution."""
    pass


class OrderNotFoundError(OrderExecutionError):
    """Order not found in tracking system."""
    pass


class OrderAlreadyExistsError(OrderExecutionError):
    """Order already exists in tracking system."""
    pass


class OrderExecutionManager:
    """
    Manages order execution with IBKR using ib-async.
    
    Provides order placement, modification, cancellation, and status tracking
    with risk management integration and comprehensive error handling.
    """
    
    def __init__(
        self,
        ibkr_client: IBKRClient,
        risk_validator: OrderRiskValidator,
        simulation_mode: bool = True,
        state_dir: Optional[Path] = None,
        discord_notifier: Optional[object] = None,
    ) -> None:
        """
        Initialize order execution manager.
        
        Args:
            ibkr_client: IBKR client for market connectivity
            risk_validator: Risk validation for pre-trade checks
            simulation_mode: Whether to run in simulation mode
            state_dir: Directory for persistent state (defaults to data/orders)
            discord_notifier: Optional Discord notifier for order events
        """
        self.ibkr_client = ibkr_client
        self.risk_validator = risk_validator
        self.simulation_mode = simulation_mode
        
        # Order tracking
        self._active_orders: Dict[str, Order] = {}
        self._order_trades: Dict[str, Trade] = {}  # Map order_id to ib-async Trade objects
        self._event_handlers: List[Callable[[OrderEvent], None]] = []
        
        # Setup Discord notifications if provided
        self._discord_handler = None
        if discord_notifier:
            try:
                from auto_trader.integrations.discord_notifier import DiscordOrderEventHandler
                self._discord_handler = DiscordOrderEventHandler(discord_notifier)
                self.add_event_handler(self._discord_handler.handle_order_event)
                logger.info("Discord notifications enabled")
            except ImportError as e:
                logger.warning("Discord notifier integration failed", error=str(e))
        
        # State persistence
        if state_dir is None:
            state_dir = Path("data/orders")
        self.state_manager = OrderStateManager(state_dir)
        
        # Setup ib-async event handlers
        self._setup_event_handlers()
        
        logger.info(
            "OrderExecutionManager initialized",
            simulation_mode=simulation_mode,
            state_dir=str(state_dir),
        )
    
    def add_event_handler(self, handler: Callable[[OrderEvent], None]) -> None:
        """Add order event handler for notifications."""
        self._event_handlers.append(handler)
        
    def remove_event_handler(self, handler: Callable[[OrderEvent], None]) -> None:
        """Remove order event handler."""
        if handler in self._event_handlers:
            self._event_handlers.remove(handler)
    
    async def start_state_management(self) -> None:
        """
        Start state management (recovery and periodic persistence).
        Call this after initialization to enable state persistence.
        """
        # Load existing state if available
        await self._recover_orders()
        
        # Start periodic backups
        await self.state_manager.start_periodic_backup()
        
        logger.info("State management started")
    
    async def stop_state_management(self) -> None:
        """Stop state management and save current state."""
        # Save current state
        await self._save_state("shutdown")
        
        # Stop periodic backups
        await self.state_manager.stop_periodic_backup()
        
        logger.info("State management stopped")
    
    async def _recover_orders(self) -> None:
        """Recover orders from persistent storage."""
        try:
            recovered_orders = await self.state_manager.load_state()
            
            if not recovered_orders:
                logger.info("No orders to recover")
                return
            
            # Filter out completed orders (FILLED, CANCELLED, REJECTED)
            completed_statuses = {OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED}
            active_orders = {
                order_id: order
                for order_id, order in recovered_orders.items()
                if order.status not in completed_statuses
            }
            
            self._active_orders.update(active_orders)
            
            logger.info(
                "Orders recovered from state",
                total_recovered=len(recovered_orders),
                active_orders=len(active_orders),
                completed_orders=len(recovered_orders) - len(active_orders),
            )
            
            # If we're not in simulation mode, we'd need to sync with IBKR
            # For now, we just log the recovery
            if not self.simulation_mode:
                logger.warning(
                    "Order recovery in live mode requires manual verification",
                    recovered_orders=list(active_orders.keys()),
                )
            
        except Exception as e:
            logger.error("Failed to recover orders from state", error=str(e))
    
    async def _save_state(self, reason: str = "periodic") -> None:
        """Save current order state."""
        try:
            await self.state_manager.save_state(self._active_orders)
            logger.debug("Order state saved", reason=reason)
        except Exception as e:
            logger.error("Failed to save order state", error=str(e))
    
    async def place_market_order(self, order_request: OrderRequest) -> OrderResult:
        """
        Place market order with risk validation.
        
        Args:
            order_request: Order placement request
            
        Returns:
            OrderResult with execution status and details
        """
        try:
            logger.info(
                "Market order placement initiated",
                trade_plan_id=order_request.trade_plan_id,
                symbol=order_request.symbol,
                side=order_request.side,
            )
            
            # Step 1: Risk validation
            risk_validation = await self.risk_validator.validate_order_request(order_request)
            if not risk_validation.is_valid:
                logger.warning(
                    "Market order rejected by risk validation",
                    trade_plan_id=order_request.trade_plan_id,
                    errors=risk_validation.errors,
                )
                
                # Create temp order for rejection notification
                temp_order = self._create_order_from_request(order_request, OrderType.MARKET)
                temp_order.status = OrderStatus.REJECTED
                
                # Emit rejection event
                await self._emit_order_event(
                    temp_order, "order_rejected", {
                        "order": temp_order,
                        "reason": "; ".join(risk_validation.errors)
                    }
                )
                
                return self.risk_validator.create_order_rejection_result(
                    order_request, risk_validation
                )
            
            # Step 2: Create order object
            order = self._create_order_from_request(order_request, OrderType.MARKET)
            
            # Step 3: Execute order placement
            if self.simulation_mode:
                result = await self._simulate_order_placement(order)
            else:
                result = await self._execute_real_order(order)
            
            if result.success:
                # Step 4: Track successful order
                self._active_orders[result.order_id] = order
                await self._emit_order_event(
                    order, "order_submitted", {
                        "order": order,
                        "result": result.model_dump(),
                        "risk_amount": risk_validation.position_size_result.dollar_risk if risk_validation else None,
                        "portfolio_risk": getattr(risk_validation, 'portfolio_risk_percent', None) if risk_validation else None,
                    }
                )
                
                # Save state after successful order placement
                asyncio.create_task(self._save_state("order_placed"))
            
            logger.info(
                "Market order placement completed",
                trade_plan_id=order_request.trade_plan_id,
                success=result.success,
                order_id=result.order_id,
            )
            
            return result
            
        except Exception as e:
            logger.error(
                "Market order placement failed",
                trade_plan_id=order_request.trade_plan_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            
            return OrderResult(
                success=False,
                trade_plan_id=order_request.trade_plan_id,
                order_status=OrderStatus.REJECTED,
                error_message=f"Order placement failed: {str(e)}",
                symbol=order_request.symbol,
                side=order_request.side,
                quantity=order_request.calculated_position_size or 0,
                order_type=OrderType.MARKET,
            )
    
    async def place_bracket_order(
        self, 
        entry_request: OrderRequest,
        stop_loss_price: Decimal,
        take_profit_price: Decimal,
    ) -> OrderResult:
        """
        Place bracket order (entry + stop loss + take profit).
        
        Args:
            entry_request: Entry order request
            stop_loss_price: Stop loss price
            take_profit_price: Take profit price
            
        Returns:
            OrderResult for the parent order
        """
        try:
            logger.info(
                "Bracket order placement initiated",
                trade_plan_id=entry_request.trade_plan_id,
                symbol=entry_request.symbol,
                entry_price=float(entry_request.entry_price),
                stop_loss_price=float(stop_loss_price),
                take_profit_price=float(take_profit_price),
            )
            
            # Risk validation on entry order
            risk_validation = await self.risk_validator.validate_order_request(entry_request)
            if not risk_validation.is_valid:
                return self.risk_validator.create_order_rejection_result(
                    entry_request, risk_validation
                )
            
            # Create bracket order components
            bracket_id = f"BRACKET_{uuid.uuid4().hex[:8].upper()}"
            
            parent_order = self._create_order_from_request(entry_request, entry_request.order_type)
            parent_order.parent_order_id = bracket_id
            
            # Create child orders
            stop_loss_order = self._create_child_order(
                parent_order, OrderType.STOP, stop_loss_price, "STOP_LOSS"
            )
            
            take_profit_order = self._create_child_order(
                parent_order, OrderType.LIMIT, take_profit_price, "TAKE_PROFIT"  
            )
            
            bracket = BracketOrder(
                bracket_id=bracket_id,
                trade_plan_id=entry_request.trade_plan_id,
                parent_order=parent_order,
                stop_loss_order=stop_loss_order,
                take_profit_order=take_profit_order,
            )
            
            # Execute bracket order
            if self.simulation_mode:
                result = await self._simulate_bracket_order(bracket)
            else:
                result = await self._execute_real_bracket_order(bracket)
            
            if result.success:
                # Track all orders in bracket
                self._active_orders[parent_order.order_id] = parent_order
                self._active_orders[stop_loss_order.order_id] = stop_loss_order
                self._active_orders[take_profit_order.order_id] = take_profit_order
                
                # Emit bracket order placed event
                await self._emit_order_event(
                    parent_order, "bracket_order_placed", {
                        "order": parent_order,
                        "stop_loss_price": stop_loss_price,
                        "take_profit_price": take_profit_price,
                        "risk_amount": risk_validation.position_size_result.dollar_risk if risk_validation else None,
                    }
                )
                
                # Save state after successful bracket order placement
                asyncio.create_task(self._save_state("bracket_order_placed"))
            
            return result
            
        except Exception as e:
            logger.error(
                "Bracket order placement failed",
                trade_plan_id=entry_request.trade_plan_id,
                error=str(e),
            )
            
            return OrderResult(
                success=False,
                trade_plan_id=entry_request.trade_plan_id,
                order_status=OrderStatus.REJECTED,
                error_message=f"Bracket order placement failed: {str(e)}",
                symbol=entry_request.symbol,
                side=entry_request.side,
                quantity=entry_request.calculated_position_size or 0,
                order_type=entry_request.order_type,
            )
    
    async def modify_order(self, modification: OrderModification) -> OrderResult:
        """
        Modify existing order.
        
        Args:
            modification: Order modification request
            
        Returns:
            OrderResult with modification status
        """
        try:
            if modification.order_id not in self._active_orders:
                raise OrderNotFoundError(f"Order {modification.order_id} not found")
            
            order = self._active_orders[modification.order_id]
            
            logger.info(
                "Order modification initiated",
                order_id=modification.order_id,
                reason=modification.reason,
            )
            
            if self.simulation_mode:
                result = await self._simulate_order_modification(order, modification)
            else:
                result = await self._execute_real_order_modification(order, modification)
            
            if result.success:
                await self._emit_order_event(
                    order, "order_modified", {"modification": modification.model_dump()}
                )
            
            return result
            
        except Exception as e:
            logger.error(
                "Order modification failed",
                order_id=modification.order_id,
                error=str(e),
            )
            
            return OrderResult(
                success=False,
                trade_plan_id=order.trade_plan_id if 'order' in locals() else "unknown",
                order_status=OrderStatus.REJECTED,
                error_message=f"Order modification failed: {str(e)}",
                symbol=order.symbol if 'order' in locals() else "unknown",
                side=order.side if 'order' in locals() else OrderSide.BUY,
                quantity=0,
                order_type=order.order_type if 'order' in locals() else OrderType.MARKET,
            )
    
    async def cancel_order(self, order_id: str) -> OrderResult:
        """
        Cancel existing order.
        
        Args:
            order_id: Order ID to cancel
            
        Returns:
            OrderResult with cancellation status
        """
        try:
            if order_id not in self._active_orders:
                raise OrderNotFoundError(f"Order {order_id} not found")
            
            order = self._active_orders[order_id]
            
            logger.info("Order cancellation initiated", order_id=order_id)
            
            if self.simulation_mode:
                result = await self._simulate_order_cancellation(order)
            else:
                result = await self._execute_real_order_cancellation(order)
            
            if result.success:
                # Remove from active orders
                del self._active_orders[order_id]
                if order_id in self._order_trades:
                    del self._order_trades[order_id]
                
                await self._emit_order_event(order, "order_cancelled", {
                    "order": order,
                    "reason": "Manual"
                })
                
                # Save state after order cancellation
                asyncio.create_task(self._save_state("order_cancelled"))
            
            return result
            
        except Exception as e:
            logger.error(
                "Order cancellation failed",
                order_id=order_id,
                error=str(e),
            )
            
            order = self._active_orders.get(order_id)
            return OrderResult(
                success=False,
                trade_plan_id=order.trade_plan_id if order else "unknown",
                order_status=OrderStatus.REJECTED,
                error_message=f"Order cancellation failed: {str(e)}",
                symbol=order.symbol if order else "unknown",
                side=order.side if order else OrderSide.BUY,
                quantity=0,
                order_type=order.order_type if order else OrderType.MARKET,
            )
    
    async def get_order_status(self, order_id: str) -> Optional[Order]:
        """Get current order status."""
        return self._active_orders.get(order_id)
    
    async def get_active_orders(self) -> List[Order]:
        """Get all active orders."""
        return list(self._active_orders.values())
    
    def _create_order_from_request(self, request: OrderRequest, order_type: OrderType) -> Order:
        """Create Order object from OrderRequest."""
        return Order(
            order_id=None,  # Will be set after placement
            trade_plan_id=request.trade_plan_id,
            symbol=request.symbol,
            exchange=request.exchange,
            currency=request.currency,
            side=request.side,
            order_type=order_type,
            quantity=request.calculated_position_size or 0,
            price=request.entry_price if order_type == OrderType.LIMIT else None,
            time_in_force=request.time_in_force,
        )
    
    def _create_child_order(
        self, 
        parent: Order, 
        order_type: OrderType, 
        price: Decimal,
        order_tag: str
    ) -> Order:
        """Create child order for bracket orders."""
        # Determine side (opposite of parent for exit orders)
        child_side = OrderSide.SELL if parent.side == OrderSide.BUY else OrderSide.BUY
        
        return Order(
            order_id=None,  # Will be set after placement
            parent_order_id=parent.parent_order_id,
            trade_plan_id=parent.trade_plan_id,
            symbol=parent.symbol,
            exchange=parent.exchange,
            currency=parent.currency,
            side=child_side,
            order_type=order_type,
            quantity=parent.quantity,
            price=price if order_type == OrderType.LIMIT else None,
            stop_price=price if order_type == OrderType.STOP else None,
            time_in_force=TimeInForce.GTC,  # Child orders typically GTC
            transmit=False,  # Will be transmitted with parent
        )
    
    def _setup_event_handlers(self) -> None:
        """Setup ib-async event handlers for order tracking."""
        # Get IB connection from client when available
        if hasattr(self.ibkr_client, '_ib') and self.ibkr_client._ib:
            ib = self.ibkr_client._ib
            
            # Set up order status event handler (only if not a mock)
            if hasattr(ib, 'orderStatusEvent') and not hasattr(ib.orderStatusEvent, '_mock_name'):
                ib.orderStatusEvent += self._on_order_status_update
                ib.execDetailsEvent += self._on_execution_update
                logger.debug("ib-async event handlers configured")
            else:
                logger.debug("Skipping event handler setup for mock object")
    
    def _on_order_status_update(self, trade: Trade) -> None:
        """Handle order status updates from ib-async."""
        try:
            order_id = str(trade.order.orderId)
            
            if order_id in self._active_orders:
                order = self._active_orders[order_id]
                old_status = order.status
                new_status = self._map_ibkr_status(trade.orderStatus.status)
                
                # Update order status
                order.status = new_status
                
                # Handle fills
                if trade.orderStatus.filled > order.filled_quantity:
                    order.filled_quantity = int(trade.orderStatus.filled)
                    
                    if trade.orderStatus.avgFillPrice and trade.orderStatus.avgFillPrice > 0:
                        order.average_fill_price = Decimal(str(trade.orderStatus.avgFillPrice))
                
                # Check if order is complete
                if new_status in [OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED]:
                    if new_status == OrderStatus.FILLED:
                        order.filled_at = datetime.now(UTC)
                
                logger.info(
                    "Order status updated",
                    order_id=order_id,
                    old_status=old_status,
                    new_status=new_status,
                    filled_quantity=order.filled_quantity,
                )
                
                # Emit order event
                asyncio.create_task(self._emit_order_event(
                    order, "status_update", {
                        "old_status": old_status,
                        "new_status": new_status,
                        "filled_quantity": order.filled_quantity,
                    }
                ))
                
        except Exception as e:
            logger.error("Order status update handler error", error=str(e))
    
    def _on_execution_update(self, trade: Trade, fill) -> None:
        """Handle execution updates from ib-async."""
        try:
            order_id = str(trade.order.orderId)
            
            if order_id in self._active_orders:
                order = self._active_orders[order_id]
                
                logger.info(
                    "Order execution update",
                    order_id=order_id,
                    fill_price=fill.execution.price,
                    fill_shares=fill.execution.shares,
                    commission=fill.commissionReport.commission if fill.commissionReport else None,
                )
                
                # Update commission if available
                if fill.commissionReport and fill.commissionReport.commission:
                    order.commission = Decimal(str(fill.commissionReport.commission))
                
                # Emit fill event
                asyncio.create_task(self._emit_order_event(
                    order, "order_filled", {
                        "order": order,
                        "fill_price": fill.execution.price,
                        "fill_shares": fill.execution.shares,
                        "commission": float(order.commission) if order.commission else None,
                        "entry_price": None,  # TODO: Add logic to determine entry price for exits
                    }
                ))
                
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
    
    async def _simulate_order_placement(self, order: Order) -> OrderResult:
        """Simulate order placement for testing."""
        order.order_id = f"SIM_{uuid.uuid4().hex[:8].upper()}"
        order.status = OrderStatus.SUBMITTED
        order.submitted_at = datetime.now(UTC)
        
        # Simulate immediate fill for market orders
        if order.order_type == OrderType.MARKET:
            await asyncio.sleep(0.1)  # Simulate network delay
            order.status = OrderStatus.FILLED
            order.filled_at = datetime.now(UTC)
            order.filled_quantity = order.quantity
            order.average_fill_price = order.price or Decimal("100.00")  # Mock price
        
        return OrderResult(
            success=True,
            order_id=order.order_id,
            trade_plan_id=order.trade_plan_id,
            order_status=order.status,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            order_type=order.order_type,
        )
    
    async def _simulate_bracket_order(self, bracket: BracketOrder) -> OrderResult:
        """Simulate bracket order placement."""
        # Simulate parent order
        parent_result = await self._simulate_order_placement(bracket.parent_order)
        
        if parent_result.success:
            # Simulate child orders
            bracket.stop_loss_order.order_id = f"SIM_{uuid.uuid4().hex[:8].upper()}"
            bracket.take_profit_order.order_id = f"SIM_{uuid.uuid4().hex[:8].upper()}"
            
            bracket.stop_loss_order.status = OrderStatus.SUBMITTED
            bracket.take_profit_order.status = OrderStatus.SUBMITTED
            
            bracket.all_orders_submitted = True
        
        return parent_result
    
    async def _simulate_order_modification(self, order: Order, modification: OrderModification) -> OrderResult:
        """Simulate order modification."""
        if modification.new_price:
            order.price = modification.new_price
        if modification.new_quantity:
            order.quantity = modification.new_quantity
        
        return OrderResult(
            success=True,
            order_id=order.order_id,
            trade_plan_id=order.trade_plan_id,
            order_status=order.status,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            order_type=order.order_type,
        )
    
    async def _simulate_order_cancellation(self, order: Order) -> OrderResult:
        """Simulate order cancellation."""
        order.status = OrderStatus.CANCELLED
        
        return OrderResult(
            success=True,
            order_id=order.order_id,
            trade_plan_id=order.trade_plan_id,
            order_status=order.status,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            order_type=order.order_type,
        )
    
    async def _execute_real_order(self, order: Order) -> OrderResult:
        """Execute real order through IBKR."""
        try:
            # Get IB connection from client
            ib = self.ibkr_client._ib
            
            # Create contract
            contract = Stock(order.symbol, 'SMART', order.currency)
            await ib.qualifyContractsAsync(contract)
            
            # Create ib-async order based on type
            if order.order_type == OrderType.MARKET:
                ib_order = MarketOrder(
                    action=order.side.value,
                    totalQuantity=order.quantity
                )
            elif order.order_type == OrderType.LIMIT:
                ib_order = LimitOrder(
                    action=order.side.value,
                    totalQuantity=order.quantity,
                    lmtPrice=float(order.price)
                )
            elif order.order_type == OrderType.STOP:
                ib_order = StopOrder(
                    action=order.side.value,
                    totalQuantity=order.quantity,
                    stopPrice=float(order.stop_price)
                )
            else:
                raise OrderExecutionError(f"Unsupported order type: {order.order_type}")
            
            # Set time in force
            ib_order.tif = order.time_in_force.value
            
            # Place order with IBKR
            trade = ib.placeOrder(contract, ib_order)
            order.order_id = str(trade.order.orderId)
            order.status = self._map_ibkr_status(trade.orderStatus.status)
            order.submitted_at = datetime.now(UTC)
            
            # Track the trade object
            self._order_trades[order.order_id] = trade
            
            logger.info(
                "Order placed with IBKR",
                order_id=order.order_id,
                symbol=order.symbol,
                ibkr_status=trade.orderStatus.status,
            )
            
            return OrderResult(
                success=True,
                order_id=order.order_id,
                trade_plan_id=order.trade_plan_id,
                order_status=order.status,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                order_type=order.order_type,
            )
            
        except Exception as e:
            logger.error("IBKR order execution failed", error=str(e))
            raise OrderExecutionError(f"IBKR order execution failed: {e}")
    
    async def _execute_real_bracket_order(self, bracket: BracketOrder) -> OrderResult:
        """Execute real bracket order through IBKR."""
        try:
            # Get IB connection from client
            ib = self.ibkr_client._ib
            
            # Create contract
            contract = Stock(bracket.parent_order.symbol, 'SMART', bracket.parent_order.currency)
            await ib.qualifyContractsAsync(contract)
            
            # Get next order IDs for the bracket
            parent_id = ib.client.getReqId()
            stop_id = ib.client.getReqId()  
            profit_id = ib.client.getReqId()
            
            # Create parent order
            if bracket.parent_order.order_type == OrderType.MARKET:
                parent_ib_order = MarketOrder(
                    action=bracket.parent_order.side.value,
                    totalQuantity=bracket.parent_order.quantity
                )
            else:
                parent_ib_order = LimitOrder(
                    action=bracket.parent_order.side.value,
                    totalQuantity=bracket.parent_order.quantity,
                    lmtPrice=float(bracket.parent_order.price)
                )
            
            # Configure parent order for bracket
            parent_ib_order.orderId = parent_id
            parent_ib_order.transmit = False  # Don't transmit until all orders are ready
            
            # Create stop loss order (child)
            stop_ib_order = StopOrder(
                action=bracket.stop_loss_order.side.value,
                totalQuantity=bracket.stop_loss_order.quantity,
                stopPrice=float(bracket.stop_loss_order.stop_price)
            )
            stop_ib_order.orderId = stop_id
            stop_ib_order.parentId = parent_id
            stop_ib_order.transmit = False
            
            # Create take profit order (child)
            profit_ib_order = LimitOrder(
                action=bracket.take_profit_order.side.value,
                totalQuantity=bracket.take_profit_order.quantity,
                lmtPrice=float(bracket.take_profit_order.price)
            )
            profit_ib_order.orderId = profit_id
            profit_ib_order.parentId = parent_id
            profit_ib_order.transmit = True  # Transmit all orders when this is placed
            
            # Place orders in sequence (parent, stop, profit)
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
                symbol=bracket.parent_order.symbol,
                side=bracket.parent_order.side,
                quantity=bracket.parent_order.quantity,
                order_type=bracket.parent_order.order_type,
            )
            
        except Exception as e:
            logger.error("IBKR bracket order execution failed", error=str(e))
            raise OrderExecutionError(f"IBKR bracket order execution failed: {e}")
    
    async def _execute_real_order_modification(self, order: Order, modification: OrderModification) -> OrderResult:
        """Execute real order modification through IBKR."""
        try:
            if order.order_id not in self._order_trades:
                raise OrderNotFoundError(f"Trade object not found for order {order.order_id}")
            
            ib = self.ibkr_client._ib
            trade = self._order_trades[order.order_id]
            
            # Clone the existing order for modification
            modified_order = trade.order
            
            # Apply modifications
            if modification.new_price:
                if hasattr(modified_order, 'lmtPrice'):
                    modified_order.lmtPrice = float(modification.new_price)
                    order.price = modification.new_price
                
            if modification.new_stop_price:
                if hasattr(modified_order, 'stopPrice'):
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
                modifications=modification.model_dump(),
            )
            
            return OrderResult(
                success=True,
                order_id=order.order_id,
                trade_plan_id=order.trade_plan_id,
                order_status=order.status,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                order_type=order.order_type,
            )
            
        except Exception as e:
            logger.error("IBKR order modification failed", error=str(e))
            raise OrderExecutionError(f"IBKR order modification failed: {e}")
    
    async def _execute_real_order_cancellation(self, order: Order) -> OrderResult:
        """Execute real order cancellation through IBKR."""
        try:
            if order.order_id not in self._order_trades:
                raise OrderNotFoundError(f"Trade object not found for order {order.order_id}")
            
            ib = self.ibkr_client._ib
            trade = self._order_trades[order.order_id]
            
            # Cancel the order
            ib.cancelOrder(trade.order)
            
            # Wait for cancellation confirmation
            await asyncio.sleep(0.5)  # Give IBKR time to process
            
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
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                order_type=order.order_type,
            )
            
        except Exception as e:
            logger.error("IBKR order cancellation failed", error=str(e))
            raise OrderExecutionError(f"IBKR order cancellation failed: {e}")
    
    async def _emit_order_event(self, order: Order, event_type: str, event_data: dict) -> None:
        """Emit order event to registered handlers."""
        event = OrderEvent(
            event_id=f"EVT_{uuid.uuid4().hex[:8].upper()}",
            order_id=order.order_id or "unknown",
            trade_plan_id=order.trade_plan_id,
            event_type=event_type,
            old_status=None,  # TODO: Track previous status
            new_status=order.status,
            event_data=event_data,
        )
        
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    "Order event handler failed",
                    handler=handler.__name__,
                    error=str(e),
                )