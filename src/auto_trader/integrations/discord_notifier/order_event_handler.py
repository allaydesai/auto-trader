"""Discord notification handler for order events."""

import asyncio
from decimal import Decimal
from typing import Dict, Optional

from loguru import logger

from auto_trader.models.order import OrderEvent, Order
from auto_trader.models.enums import OrderStatus
from .notifier import DiscordNotifier


class DiscordOrderEventHandler:
    """
    Handles order events and sends Discord notifications.
    
    Integrates with OrderExecutionManager's event system to automatically
    send Discord notifications for order lifecycle events.
    """
    
    def __init__(self, notifier: DiscordNotifier):
        """
        Initialize Discord order event handler.
        
        Args:
            notifier: Discord notifier instance
        """
        self.notifier = notifier
        self._order_cache: Dict[str, Order] = {}
        
    def handle_order_event(self, event: OrderEvent) -> None:
        """
        Handle order event and send Discord notification.
        
        Args:
            event: Order event to handle
        """
        # Run async notification in background task
        asyncio.create_task(self._handle_event_async(event))
    
    async def _handle_event_async(self, event: OrderEvent) -> None:
        """Handle order event asynchronously."""
        try:
            # Get order from event data if available
            order_data = event.event_data.get('order')
            if not order_data:
                logger.warning(
                    "No order data in event", 
                    event_id=event.event_id,
                    event_type=event.event_type
                )
                return
            
            # Convert order data dict back to Order object
            order = Order.model_validate(order_data) if isinstance(order_data, dict) else order_data
                
            # Cache order for future reference
            if order.order_id:
                self._order_cache[order.order_id] = order
            
            # Handle different event types
            if event.event_type == "order_submitted":
                await self._handle_order_submitted(order, event.event_data)
                
            elif event.event_type == "order_filled":
                await self._handle_order_filled(order, event.event_data)
                
            elif event.event_type == "order_cancelled":
                await self._handle_order_cancelled(order, event.event_data)
                
            elif event.event_type == "order_rejected":
                await self._handle_order_rejected(order, event.event_data)
                
            elif event.event_type == "bracket_order_placed":
                await self._handle_bracket_order_placed(order, event.event_data)
                
            else:
                logger.debug(
                    "Unhandled order event type",
                    event_type=event.event_type,
                    order_id=event.order_id
                )
                
        except Exception as e:
            logger.error(
                "Failed to handle Discord order event",
                event_id=event.event_id,
                event_type=event.event_type,
                error=str(e)
            )
    
    async def _handle_order_submitted(self, order: Order, event_data: dict) -> None:
        """Handle order submitted event."""
        risk_amount = event_data.get('risk_amount')
        portfolio_risk = event_data.get('portfolio_risk')
        
        await self.notifier.send_order_submitted(
            order=order,
            risk_amount=Decimal(str(risk_amount)) if risk_amount else None,
            portfolio_risk=portfolio_risk
        )
    
    async def _handle_order_filled(self, order: Order, event_data: dict) -> None:
        """Handle order filled event."""
        entry_price = event_data.get('entry_price')
        
        await self.notifier.send_order_filled(
            order=order,
            entry_price=Decimal(str(entry_price)) if entry_price else None
        )
    
    async def _handle_order_cancelled(self, order: Order, event_data: dict) -> None:
        """Handle order cancelled event."""
        reason = event_data.get('reason', 'Manual')
        
        await self.notifier.send_order_cancelled(
            order=order,
            reason=reason
        )
    
    async def _handle_order_rejected(self, order: Order, event_data: dict) -> None:
        """Handle order rejected event."""
        # Convert Order back to OrderRequest for rejected notifications
        # This is a bit of a hack but works for the notification
        from auto_trader.models.order import OrderRequest
        from auto_trader.models.trade_plan import RiskCategory
        
        order_request = OrderRequest(
            trade_plan_id=order.trade_plan_id,
            symbol=order.symbol,
            side=order.side,
            order_type=order.order_type,
            entry_price=order.price or Decimal("100.00"),
            stop_loss_price=Decimal("95.00"),  # Dummy values for rejection notification
            take_profit_price=Decimal("105.00"),  
            risk_category=RiskCategory.NORMAL,  # Dummy value
            calculated_position_size=order.quantity,
            time_in_force=order.time_in_force or "DAY"
        )
        
        reason = event_data.get('reason', 'Unknown rejection reason')
        
        await self.notifier.send_order_rejected(
            order_request=order_request,
            reason=reason
        )
    
    async def _handle_bracket_order_placed(self, order: Order, event_data: dict) -> None:
        """Handle bracket order placed event."""
        stop_loss_price = event_data.get('stop_loss_price')
        take_profit_price = event_data.get('take_profit_price') 
        risk_amount = event_data.get('risk_amount')
        
        if stop_loss_price and take_profit_price and risk_amount:
            await self.notifier.send_bracket_order_placed(
                entry_order=order,
                stop_loss_price=Decimal(str(stop_loss_price)),
                take_profit_price=Decimal(str(take_profit_price)),
                risk_amount=Decimal(str(risk_amount))
            )
    
    def get_cached_order(self, order_id: str) -> Optional[Order]:
        """Get cached order by ID."""
        return self._order_cache.get(order_id)