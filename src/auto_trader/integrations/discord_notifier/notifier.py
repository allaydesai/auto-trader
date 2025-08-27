"""Discord webhook notification service for order events."""

import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Optional

import httpx
from loguru import logger

from auto_trader.models.order import Order, OrderRequest, OrderResult
from auto_trader.models.enums import OrderSide, OrderStatus


class DiscordNotifier:
    """
    Sends order execution notifications to Discord via webhook.
    
    Features:
    - Rich formatted messages with consistent emoji language
    - Order entry/exit notifications with P&L calculation
    - Risk information display
    - Error handling with retry mechanism
    """
    
    def __init__(self, webhook_url: str, simulation_mode: bool = False):
        """
        Initialize Discord notifier.
        
        Args:
            webhook_url: Discord webhook URL for notifications
            simulation_mode: If True, prefix all messages with [SIM] 
        """
        self.webhook_url = webhook_url
        self.simulation_mode = simulation_mode
        self._client = httpx.AsyncClient(timeout=10.0)
        
        logger.info(
            "Discord notifier initialized", 
            simulation_mode=simulation_mode,
            has_webhook=bool(webhook_url)
        )
    
    async def send_order_submitted(
        self, 
        order: Order,
        risk_amount: Optional[Decimal] = None,
        portfolio_risk: Optional[float] = None
    ) -> None:
        """
        Send notification when order is submitted to IBKR.
        
        Args:
            order: The submitted order
            risk_amount: Dollar amount at risk
            portfolio_risk: Current portfolio risk percentage
        """
        prefix = "[SIM] " if self.simulation_mode else ""
        
        side_emoji = "📈" if order.side == OrderSide.BUY else "📉"
        action = "LONG" if order.side == OrderSide.BUY else "SHORT"
        
        message = f"""
{side_emoji} **{prefix}ORDER SUBMITTED**
**{order.symbol}** | {action} {order.quantity} @ ${order.price}
**Type:** {order.order_type}
**Plan ID:** {order.trade_plan_id}
        """.strip()
        
        if risk_amount:
            message += f"\n**Risk:** ${risk_amount}"
            
        if portfolio_risk:
            message += f" | **Portfolio Risk:** {portfolio_risk:.1f}%"
        
        await self._send_webhook_message(message)
    
    async def send_order_filled(
        self,
        order: Order,
        entry_price: Optional[Decimal] = None
    ) -> None:
        """
        Send notification when order is filled.
        
        Args:
            order: The filled order
            entry_price: Entry price for P&L calculation (for exits)
        """
        prefix = "[SIM] " if self.simulation_mode else ""
        
        # Determine if this is entry or exit
        is_entry = entry_price is None
        
        if is_entry:
            emoji = "🟢"
            action_text = "ENTRY EXECUTED"
            side_text = "LONG" if order.side == OrderSide.BUY else "SHORT"
            
            message = f"""
{emoji} **{prefix}{action_text}**
**{order.symbol}** | {side_text} {order.filled_quantity} @ ${order.average_fill_price}
**Order ID:** {order.order_id}
**Time:** {datetime.now(timezone.utc).strftime('%H:%M:%S')}
            """.strip()
        else:
            # Calculate P&L for exit
            if order.side == OrderSide.SELL:
                pnl = (order.average_fill_price - entry_price) * order.filled_quantity
            else:
                pnl = (entry_price - order.average_fill_price) * order.filled_quantity
            
            pnl_percent = (pnl / (entry_price * order.filled_quantity)) * 100
            
            emoji = "🟢" if pnl >= 0 else "🔴"
            exit_reason = "TAKE PROFIT" if pnl >= 0 else "STOP LOSS"
            
            message = f"""
{emoji} **{prefix}EXIT: {exit_reason}**
**{order.symbol}** | SOLD {order.filled_quantity} @ ${order.average_fill_price}
**P&L:** ${pnl:.2f} ({pnl_percent:+.1f}%)
**Entry:** ${entry_price} | **Exit:** ${order.average_fill_price}
**Time:** {datetime.now(timezone.utc).strftime('%H:%M:%S')}
            """.strip()
        
        await self._send_webhook_message(message)
    
    async def send_order_cancelled(self, order: Order, reason: str = "Manual") -> None:
        """
        Send notification when order is cancelled.
        
        Args:
            order: The cancelled order
            reason: Cancellation reason
        """
        prefix = "[SIM] " if self.simulation_mode else ""
        
        message = f"""
🟡 **{prefix}ORDER CANCELLED**
**{order.symbol}** | {order.side} {order.quantity} @ ${order.price}
**Reason:** {reason}
**Order ID:** {order.order_id}
        """.strip()
        
        await self._send_webhook_message(message)
    
    async def send_order_rejected(
        self, 
        order_request: OrderRequest, 
        reason: str
    ) -> None:
        """
        Send notification when order is rejected.
        
        Args:
            order_request: The rejected order request
            reason: Rejection reason
        """
        prefix = "[SIM] " if self.simulation_mode else ""
        
        message = f"""
🚨 **{prefix}ORDER REJECTED**
**{order_request.symbol}** | {order_request.side} {order_request.calculated_position_size or 0}
**Reason:** {reason}
**Plan ID:** {order_request.trade_plan_id}
        """.strip()
        
        await self._send_webhook_message(message)
    
    async def send_bracket_order_placed(
        self,
        entry_order: Order,
        stop_loss_price: Decimal,
        take_profit_price: Decimal,
        risk_amount: Decimal
    ) -> None:
        """
        Send notification when bracket order is placed.
        
        Args:
            entry_order: The entry order
            stop_loss_price: Stop loss price
            take_profit_price: Take profit price  
            risk_amount: Dollar amount at risk
        """
        prefix = "[SIM] " if self.simulation_mode else ""
        
        side_text = "LONG" if entry_order.side == OrderSide.BUY else "SHORT"
        
        message = f"""
🛡️ **{prefix}BRACKET ORDER PLACED**
**{entry_order.symbol}** | {side_text} {entry_order.quantity} @ ${entry_order.price}
**Stop Loss:** ${stop_loss_price}
**Take Profit:** ${take_profit_price}
**Risk:** ${risk_amount:.2f}
**Order ID:** {entry_order.order_id}
        """.strip()
        
        await self._send_webhook_message(message)
    
    async def send_system_alert(self, alert_type: str, message: str) -> None:
        """
        Send system alert notification.
        
        Args:
            alert_type: Type of alert (ERROR, WARNING, INFO)
            message: Alert message
        """
        prefix = "[SIM] " if self.simulation_mode else ""
        
        emoji_map = {
            "ERROR": "🚨",
            "WARNING": "🟡", 
            "INFO": "ℹ️"
        }
        
        emoji = emoji_map.get(alert_type, "ℹ️")
        
        formatted_message = f"""
{emoji} **{prefix}SYSTEM {alert_type}**
{message}
**Time:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}
        """.strip()
        
        await self._send_webhook_message(formatted_message)
    
    async def _send_webhook_message(self, message: str) -> None:
        """
        Send message to Discord webhook with error handling.
        
        Args:
            message: Message to send
        """
        if not self.webhook_url:
            logger.warning("Discord webhook URL not configured, skipping notification")
            return
            
        payload = {
            "content": message,
            "username": "Auto-Trader Bot",
        }
        
        try:
            response = await self._client.post(self.webhook_url, json=payload)
            response.raise_for_status()
            
            logger.debug("Discord notification sent successfully")
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                # Rate limited, wait and retry once
                logger.warning("Discord rate limited, retrying in 2 seconds")
                await asyncio.sleep(2)
                try:
                    retry_response = await self._client.post(self.webhook_url, json=payload)
                    retry_response.raise_for_status()
                    logger.debug("Discord notification sent on retry")
                except Exception as retry_error:
                    logger.error("Discord notification failed on retry", error=str(retry_error))
            else:
                logger.error(
                    "Discord webhook request failed", 
                    status_code=e.response.status_code,
                    response=e.response.text
                )
        except Exception as e:
            logger.error("Failed to send Discord notification", error=str(e))
    
    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.aclose()