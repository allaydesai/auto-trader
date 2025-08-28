"""Core order execution manager interface."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Callable

from ...logging_config import get_logger
from ...models.order import (
    Order,
    OrderRequest,
    OrderResult,
    BracketOrder,
    OrderEvent,
    OrderModification,
)
from ...models.enums import OrderStatus, OrderType
from ...risk_management import OrderRiskValidator
from .client import IBKRClient, IBKRError
from .state_manager import OrderStateManager
from .order_simulation_engine import OrderSimulationEngine  
from .ibkr_order_adapter import IBKROrderAdapter
from .order_event_manager import OrderEventManager

logger = get_logger("order_execution_manager", "trades")


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
    Core order execution manager that coordinates all order operations.
    
    Provides a unified interface for order placement, modification, cancellation,
    and status tracking with risk management integration.
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
        
        # State persistence
        if state_dir is None:
            state_dir = Path("data/orders")
        self.state_manager = OrderStateManager(state_dir)
        
        # Initialize execution engines
        self.simulation_engine = OrderSimulationEngine()
        self.ibkr_adapter = IBKROrderAdapter(ibkr_client) if not simulation_mode else None
        
        # Event management
        self.event_manager = OrderEventManager(discord_notifier)
        
        # Expose event handlers and discord handler for backward compatibility
        self._event_handlers = self.event_manager._event_handlers
        self._discord_handler = self.event_manager._discord_handler
        
        logger.info(
            "OrderExecutionManager initialized",
            simulation_mode=simulation_mode,
            state_dir=str(state_dir),
        )
    
    def add_event_handler(self, handler: Callable[[OrderEvent], None]) -> None:
        """Add order event handler for notifications."""
        self.event_manager.add_handler(handler)
        
    def remove_event_handler(self, handler: Callable[[OrderEvent], None]) -> None:
        """Remove order event handler."""
        self.event_manager.remove_handler(handler)
    
    async def start_state_management(self) -> None:
        """Start state management and setup event handlers."""
        await self._recover_orders()
        await self.state_manager.start_periodic_backup()
        
        # Setup IBKR event handlers if not in simulation mode
        if not self.simulation_mode and self.ibkr_adapter:
            await self.ibkr_adapter.setup_event_handlers(self._on_order_status_update)
        
        logger.info("State management started")
    
    async def stop_state_management(self) -> None:
        """Stop state management and save current state."""
        await self._save_state("shutdown")
        await self.state_manager.stop_periodic_backup()
        logger.info("State management stopped")
    
    async def place_market_order(self, order_request: OrderRequest) -> OrderResult:
        """Place market order with risk validation."""
        try:
            logger.info(
                "Market order placement initiated",
                trade_plan_id=order_request.trade_plan_id,
                symbol=order_request.symbol,
                side=order_request.side,
            )
            
            # Risk validation
            risk_validation = await self.risk_validator.validate_order_request(order_request)
            if not risk_validation.is_valid:
                return await self._handle_risk_rejection(order_request, risk_validation)
            
            # Create order object
            order = self._create_order_from_request(order_request, OrderType.MARKET)
            
            # Execute order
            if self.simulation_mode:
                result = await self.simulation_engine.place_market_order(order)
            else:
                if self.ibkr_adapter is None:
                    raise OrderExecutionError("IBKR adapter not available in live mode")
                result = await self.ibkr_adapter.place_market_order(order)
            
            if result.success and result.order_id:
                self._active_orders[result.order_id] = order
                await self.event_manager.emit_order_submitted(order, risk_validation)
                asyncio.create_task(self._save_state("order_placed"))
            
            return result
            
        except Exception as e:
            logger.error("Market order placement failed", error=str(e))
            return self._create_error_result(order_request, str(e))
    
    async def place_bracket_order(
        self, 
        entry_request: OrderRequest,
        stop_loss_price: Decimal,
        take_profit_price: Decimal,
    ) -> OrderResult:
        """Place bracket order (entry + stop loss + take profit)."""
        try:
            # Risk validation
            risk_validation = await self.risk_validator.validate_order_request(entry_request)
            if not risk_validation.is_valid:
                return await self._handle_risk_rejection(entry_request, risk_validation)
            
            # Create bracket order
            bracket = await self._create_bracket_order(entry_request, stop_loss_price, take_profit_price)
            
            # Execute bracket order
            if self.simulation_mode:
                result = await self.simulation_engine.place_bracket_order(bracket)
            else:
                if self.ibkr_adapter is None:
                    raise OrderExecutionError("IBKR adapter not available in live mode")
                result = await self.ibkr_adapter.place_bracket_order(bracket)
            
            if result.success and result.order_id:
                # Track all orders
                if bracket.parent_order.order_id:
                    self._active_orders[bracket.parent_order.order_id] = bracket.parent_order
                if bracket.stop_loss_order.order_id:
                    self._active_orders[bracket.stop_loss_order.order_id] = bracket.stop_loss_order
                if bracket.take_profit_order.order_id:
                    self._active_orders[bracket.take_profit_order.order_id] = bracket.take_profit_order
                
                await self.event_manager.emit_bracket_order_placed(bracket, risk_validation)
                asyncio.create_task(self._save_state("bracket_order_placed"))
            
            return result
            
        except Exception as e:
            logger.error("Bracket order placement failed", error=str(e))
            return self._create_error_result(entry_request, str(e))
    
    async def modify_order(self, modification: OrderModification) -> OrderResult:
        """Modify existing order."""
        try:
            if modification.order_id not in self._active_orders:
                raise OrderNotFoundError(f"Order {modification.order_id} not found")
            
            order = self._active_orders[modification.order_id]
            
            if self.simulation_mode:
                result = await self.simulation_engine.modify_order(order, modification)
            else:
                if self.ibkr_adapter is None:
                    raise OrderExecutionError("IBKR adapter not available in live mode")
                result = await self.ibkr_adapter.modify_order(order, modification)
            
            if result.success:
                await self.event_manager.emit_order_modified(order, modification)
            
            return result
            
        except Exception as e:
            logger.error("Order modification failed", error=str(e))
            return self._create_error_result_for_order(
                self._active_orders.get(modification.order_id), str(e)
            )
    
    async def cancel_order(self, order_id: str) -> OrderResult:
        """Cancel existing order."""
        try:
            if order_id not in self._active_orders:
                raise OrderNotFoundError(f"Order {order_id} not found")
            
            order = self._active_orders[order_id]
            
            if self.simulation_mode:
                result = await self.simulation_engine.cancel_order(order)
            else:
                if self.ibkr_adapter is None:
                    raise OrderExecutionError("IBKR adapter not available in live mode")
                result = await self.ibkr_adapter.cancel_order(order)
            
            if result.success:
                del self._active_orders[order_id]
                await self.event_manager.emit_order_cancelled(order)
                asyncio.create_task(self._save_state("order_cancelled"))
            
            return result
            
        except Exception as e:
            logger.error("Order cancellation failed", error=str(e))
            return self._create_error_result_for_order(
                self._active_orders.get(order_id), str(e)
            )
    
    async def get_order_status(self, order_id: str) -> Optional[Order]:
        """Get current order status."""
        return self._active_orders.get(order_id)
    
    async def get_active_orders(self) -> List[Order]:
        """Get all active orders."""
        return list(self._active_orders.values())
    
    # Helper methods
    async def _recover_orders(self) -> None:
        """Recover orders from persistent storage."""
        try:
            recovered_orders = await self.state_manager.load_state()
            if not recovered_orders:
                return
            
            # Filter active orders only
            completed_statuses = {OrderStatus.FILLED, OrderStatus.CANCELLED, OrderStatus.REJECTED}
            active_orders = {
                order_id: order
                for order_id, order in recovered_orders.items()
                if order.status not in completed_statuses
            }
            
            self._active_orders.update(active_orders)
            
            logger.info(
                "Orders recovered",
                total=len(recovered_orders),
                active=len(active_orders),
            )
            
        except Exception as e:
            logger.error("Failed to recover orders", error=str(e))
    
    async def _save_state(self, reason: str = "periodic") -> None:
        """Save current order state."""
        try:
            await self.state_manager.save_state(self._active_orders)
            logger.debug("Order state saved", reason=reason)
        except Exception as e:
            logger.error("Failed to save order state", error=str(e))
    
    def _create_order_from_request(self, request: OrderRequest, order_type: OrderType) -> Order:
        """Create Order object from OrderRequest."""
        return Order(
            order_id=None,
            parent_order_id=None,
            trade_plan_id=request.trade_plan_id,
            symbol=request.symbol,
            exchange=request.exchange,
            currency=request.currency,
            side=request.side,
            order_type=order_type,
            quantity=request.calculated_position_size or 0,
            price=request.entry_price if order_type == OrderType.LIMIT else None,
            stop_price=None,
            trail_amount=None,
            trail_percent=None,
            time_in_force=request.time_in_force,
            submitted_at=None,
            filled_at=None,
            average_fill_price=None,
            commission=None,
            error_message=None,
        )
    
    async def _create_bracket_order(
        self, request: OrderRequest, stop_loss_price: Decimal, take_profit_price: Decimal
    ) -> BracketOrder:
        """Create bracket order from request."""
        import uuid
        from ...models.enums import OrderType, OrderSide, TimeInForce
        
        bracket_id = f"BRACKET_{uuid.uuid4().hex[:8].upper()}"
        
        parent_order = self._create_order_from_request(request, request.order_type)
        parent_order.parent_order_id = bracket_id
        
        # Create child orders
        child_side = OrderSide.SELL if parent_order.side == OrderSide.BUY else OrderSide.BUY
        
        stop_loss_order = Order(
            order_id=None,
            parent_order_id=bracket_id,
            trade_plan_id=parent_order.trade_plan_id,
            symbol=parent_order.symbol,
            exchange=parent_order.exchange,
            currency=parent_order.currency,
            side=child_side,
            order_type=OrderType.STOP,
            quantity=parent_order.quantity,
            price=None,
            stop_price=stop_loss_price,
            trail_amount=None,
            trail_percent=None,
            time_in_force=TimeInForce.GTC,
            transmit=False,
            submitted_at=None,
            filled_at=None,
            average_fill_price=None,
            commission=None,
            error_message=None,
        )
        
        take_profit_order = Order(
            order_id=None,
            parent_order_id=bracket_id,
            trade_plan_id=parent_order.trade_plan_id,
            symbol=parent_order.symbol,
            exchange=parent_order.exchange,
            currency=parent_order.currency,
            side=child_side,
            order_type=OrderType.LIMIT,
            quantity=parent_order.quantity,
            price=take_profit_price,
            stop_price=None,
            trail_amount=None,
            trail_percent=None,
            time_in_force=TimeInForce.GTC,
            transmit=False,
            submitted_at=None,
            filled_at=None,
            average_fill_price=None,
            commission=None,
            error_message=None,
        )
        
        return BracketOrder(
            bracket_id=bracket_id,
            trade_plan_id=request.trade_plan_id,
            parent_order=parent_order,
            stop_loss_order=stop_loss_order,
            take_profit_order=take_profit_order,
        )
    
    async def _handle_risk_rejection(self, request: OrderRequest, risk_validation) -> OrderResult:
        """Handle risk validation rejection."""
        from ...models.enums import OrderType
        
        temp_order = self._create_order_from_request(request, OrderType.MARKET)
        temp_order.status = OrderStatus.REJECTED
        
        await self.event_manager.emit_order_rejected(temp_order, risk_validation.errors)
        
        return self.risk_validator.create_order_rejection_result(request, risk_validation)
    
    def _create_error_result(self, request: OrderRequest, error_msg: str) -> OrderResult:
        """Create error result for OrderRequest."""
        from ...models.enums import OrderType
        
        return OrderResult(
            success=False,
            order_id=None,
            trade_plan_id=request.trade_plan_id,
            order_status=OrderStatus.REJECTED,
            error_message=f"Order placement failed: {error_msg}",
            error_code=None,
            processing_time_ms=None,
            symbol=request.symbol,
            side=request.side,
            quantity=request.calculated_position_size or 0,
            order_type=OrderType.MARKET,
        )
    
    def _create_error_result_for_order(self, order: Optional[Order], error_msg: str) -> OrderResult:
        """Create error result for existing Order."""
        from ...models.enums import OrderSide, OrderType
        
        return OrderResult(
            success=False,
            order_id=None,
            trade_plan_id=order.trade_plan_id if order else "unknown",
            order_status=OrderStatus.REJECTED,
            error_message=error_msg,
            error_code=None,
            processing_time_ms=None,
            symbol=order.symbol if order else "unknown",
            side=order.side if order else OrderSide.BUY,
            quantity=0,
            order_type=order.order_type if order else OrderType.MARKET,
        )
    
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
    
    def _create_child_order(
        self, 
        parent: Order, 
        order_type: OrderType, 
        price: Decimal,
        order_tag: str
    ) -> Order:
        """Create child order for bracket orders."""
        from ...models.enums import OrderSide, TimeInForce
        
        # Determine side (opposite of parent for exit orders)
        child_side = OrderSide.SELL if parent.side == OrderSide.BUY else OrderSide.BUY
        
        return Order(
            order_id=None,
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
            trail_amount=None,
            trail_percent=None,
            time_in_force=TimeInForce.GTC,
            transmit=False,
            submitted_at=None,
            filled_at=None,
            average_fill_price=None,
            commission=None,
            error_message=None,
        )
    
    def _on_order_status_update(self, order_id: str, old_status: OrderStatus, new_status: OrderStatus) -> None:
        """Handle order status updates from IBKR."""
        if order_id in self._active_orders:
            order = self._active_orders[order_id]
            order.status = new_status
            
            asyncio.create_task(
                self.event_manager.emit_status_update(order, old_status, new_status)
            )