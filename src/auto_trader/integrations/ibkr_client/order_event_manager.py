"""Order event management and Discord notification integration."""

import uuid
from typing import List, Callable, Optional, Any, Dict
from decimal import Decimal

from ...logging_config import get_logger
from ...models.order import Order, OrderEvent, OrderModification, BracketOrder
from ...models.enums import OrderStatus

logger = get_logger("order_event_manager", "trades")


class OrderEventManager:
    """
    Manages order events and notifications.
    
    Handles event emission, Discord notifications, and custom event handlers
    for order lifecycle management.
    """
    
    def __init__(self, discord_notifier: Optional[object] = None) -> None:
        """Initialize event manager with optional Discord integration."""
        self._event_handlers: List[Callable[[OrderEvent], None]] = []
        self._discord_handler = None
        
        # Setup Discord notifications if provided
        if discord_notifier:
            try:
                from ...integrations.discord_notifier import DiscordOrderEventHandler
                self._discord_handler = DiscordOrderEventHandler(discord_notifier)
                self.add_handler(self._discord_handler.handle_order_event)
                logger.info("Discord notifications enabled for order events")
            except ImportError as e:
                logger.warning("Discord notifier integration failed", error=str(e))
        
        logger.info("OrderEventManager initialized")
    
    def add_handler(self, handler: Callable[[OrderEvent], None]) -> None:
        """Add order event handler."""
        self._event_handlers.append(handler)
        logger.debug("Event handler added", handler=handler.__name__)
        
    def remove_handler(self, handler: Callable[[OrderEvent], None]) -> None:
        """Remove order event handler."""
        if handler in self._event_handlers:
            self._event_handlers.remove(handler)
            logger.debug("Event handler removed", handler=handler.__name__)
    
    async def emit_order_submitted(self, order: Order, risk_validation: Any) -> None:
        """Emit order submitted event."""
        event_data = {
            "order": order.model_dump(),
            "risk_amount": getattr(risk_validation.position_size_result, 'dollar_risk', None) if risk_validation else None,
            "portfolio_risk": getattr(risk_validation, 'portfolio_risk_percent', None) if risk_validation else None,
        }
        
        await self._emit_event(order, "order_submitted", event_data)
    
    async def emit_bracket_order_placed(self, bracket: BracketOrder, risk_validation: Any) -> None:
        """Emit bracket order placed event."""
        event_data = {
            "order": bracket.parent_order.model_dump(),
            "stop_loss_price": float(bracket.stop_loss_order.stop_price) if bracket.stop_loss_order.stop_price else None,
            "take_profit_price": float(bracket.take_profit_order.price) if bracket.take_profit_order.price else None,
            "risk_amount": getattr(risk_validation.position_size_result, 'dollar_risk', None) if risk_validation else None,
        }
        
        await self._emit_event(bracket.parent_order, "bracket_order_placed", event_data)
    
    async def emit_order_modified(self, order: Order, modification: OrderModification) -> None:
        """Emit order modified event."""
        event_data = {"modification": modification.model_dump()}
        await self._emit_event(order, "order_modified", event_data)
    
    async def emit_order_cancelled(self, order: Order) -> None:
        """Emit order cancelled event."""
        event_data = {"order": order.model_dump(), "reason": "Manual"}
        await self._emit_event(order, "order_cancelled", event_data)
    
    async def emit_order_rejected(self, order: Order, rejection_reasons: List[str]) -> None:
        """Emit order rejected event."""
        event_data = {
            "order": order.model_dump(),
            "reason": "; ".join(rejection_reasons)
        }
        await self._emit_event(order, "order_rejected", event_data)
    
    async def emit_status_update(self, order: Order, old_status: OrderStatus, new_status: OrderStatus) -> None:
        """Emit order status update event."""
        event_data = {
            "old_status": old_status.value,
            "new_status": new_status.value,
            "filled_quantity": order.filled_quantity,
        }
        
        event = OrderEvent(
            event_id=f"EVT_{uuid.uuid4().hex[:8].upper()}",
            order_id=order.order_id or "unknown",
            trade_plan_id=order.trade_plan_id,
            event_type="status_update",
            old_status=old_status,
            new_status=new_status,
            event_data=event_data,
            fill_quantity=order.filled_quantity if new_status == OrderStatus.FILLED else None,
            fill_price=order.average_fill_price if new_status == OrderStatus.FILLED else None,
            error_message=None,
            error_code=None,
        )
        
        await self._process_event(event)
    
    async def emit_order_filled(self, order: Order, fill_price: Decimal, fill_shares: int, commission: Optional[Decimal] = None) -> None:
        """Emit order filled event."""
        event_data = {
            "order": order.model_dump(),
            "fill_price": float(fill_price),
            "fill_shares": fill_shares,
            "commission": float(commission) if commission else None,
            "entry_price": None,  # TODO: Add logic for entry price tracking
        }
        
        event = OrderEvent(
            event_id=f"EVT_{uuid.uuid4().hex[:8].upper()}",
            order_id=order.order_id or "unknown",
            trade_plan_id=order.trade_plan_id,
            event_type="order_filled",
            old_status=OrderStatus.SUBMITTED,  # Assume previous status
            new_status=OrderStatus.FILLED,
            event_data=event_data,
            fill_quantity=fill_shares,
            fill_price=fill_price,
            error_message=None,
            error_code=None,
        )
        
        await self._process_event(event)
    
    async def _emit_event(self, order: Order, event_type: str, event_data: Dict[str, Any]) -> None:
        """Internal method to emit order events."""
        event = OrderEvent(
            event_id=f"EVT_{uuid.uuid4().hex[:8].upper()}",
            order_id=order.order_id or "unknown",
            trade_plan_id=order.trade_plan_id,
            event_type=event_type,
            old_status=None,
            new_status=order.status,
            event_data=event_data,
            fill_quantity=None,
            fill_price=None,
            error_message=None,
            error_code=None,
        )
        
        await self._process_event(event)
    
    async def _process_event(self, event: OrderEvent) -> None:
        """Process event through all registered handlers."""
        logger.debug(
            "Processing order event",
            event_type=event.event_type,
            order_id=event.order_id,
            trade_plan_id=event.trade_plan_id,
        )
        
        for handler in self._event_handlers:
            try:
                # Call handler (may be sync or async)
                if hasattr(handler, '__call__'):
                    handler(event)
                else:
                    logger.warning("Invalid event handler", handler=str(handler))
                    
            except Exception as e:
                logger.error(
                    "Order event handler failed",
                    handler=handler.__name__ if hasattr(handler, '__name__') else str(handler),
                    error=str(e),
                    event_type=event.event_type,
                    order_id=event.order_id,
                )