"""Order simulation engine for testing and development."""

import asyncio
import uuid
from decimal import Decimal
from datetime import datetime, UTC

from ...logging_config import get_logger
from ...models.order import Order, OrderResult, BracketOrder, OrderModification
from ...models.enums import OrderType, OrderStatus

logger = get_logger("order_simulation_engine", "trades")


class OrderSimulationEngine:
    """
    Handles order simulation for testing and development.
    
    Provides realistic order execution simulation without connecting to IBKR,
    including market fills, status tracking, and timing delays.
    """
    
    def __init__(self) -> None:
        """Initialize the simulation engine."""
        logger.info("OrderSimulationEngine initialized")
    
    async def place_market_order(self, order: Order) -> OrderResult:
        """Simulate market order placement."""
        try:
            # Simulate order ID and initial status
            order.order_id = f"SIM_{uuid.uuid4().hex[:8].upper()}"
            order.status = OrderStatus.SUBMITTED
            order.submitted_at = datetime.now(UTC)
            
            logger.info(
                "Simulating market order placement",
                order_id=order.order_id,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
            )
            
            # Simulate network delay
            await asyncio.sleep(0.1)
            
            # Simulate immediate fill for market orders
            order.status = OrderStatus.FILLED
            order.filled_at = datetime.now(UTC)
            order.filled_quantity = order.quantity
            order.average_fill_price = order.price or Decimal("100.00")  # Mock price
            
            logger.info(
                "Market order simulation completed",
                order_id=order.order_id,
                filled_price=float(order.average_fill_price),
                filled_quantity=order.filled_quantity,
            )
            
            return OrderResult(
                success=True,
                order_id=order.order_id,
                trade_plan_id=order.trade_plan_id,
                order_status=order.status,
                error_message=None,
                error_code=None,
                processing_time_ms=100,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                order_type=order.order_type,
            )
            
        except Exception as e:
            logger.error("Market order simulation failed", error=str(e))
            return self._create_simulation_error_result(order, str(e))
    
    async def place_bracket_order(self, bracket: BracketOrder) -> OrderResult:
        """Simulate bracket order placement."""
        try:
            # Simulate parent order
            parent_result = await self.place_market_order(bracket.parent_order)
            
            if parent_result.success:
                # Simulate child orders
                bracket.stop_loss_order.order_id = f"SIM_{uuid.uuid4().hex[:8].upper()}"
                bracket.take_profit_order.order_id = f"SIM_{uuid.uuid4().hex[:8].upper()}"
                
                bracket.stop_loss_order.status = OrderStatus.SUBMITTED
                bracket.take_profit_order.status = OrderStatus.SUBMITTED
                bracket.stop_loss_order.submitted_at = datetime.now(UTC)
                bracket.take_profit_order.submitted_at = datetime.now(UTC)
                
                bracket.all_orders_submitted = True
                
                logger.info(
                    "Bracket order simulation completed",
                    parent_id=bracket.parent_order.order_id,
                    stop_id=bracket.stop_loss_order.order_id,
                    profit_id=bracket.take_profit_order.order_id,
                )
            
            return parent_result
            
        except Exception as e:
            logger.error("Bracket order simulation failed", error=str(e))
            return self._create_simulation_error_result(bracket.parent_order, str(e))
    
    async def modify_order(self, order: Order, modification: OrderModification) -> OrderResult:
        """Simulate order modification."""
        try:
            logger.info(
                "Simulating order modification",
                order_id=modification.order_id,
                reason=modification.reason,
            )
            
            # Apply modifications to order
            if modification.new_price:
                order.price = modification.new_price
            if modification.new_stop_price:
                order.stop_price = modification.new_stop_price
            if modification.new_quantity:
                order.quantity = modification.new_quantity
            if modification.new_trail_amount:
                order.trail_amount = modification.new_trail_amount
            if modification.new_trail_percent:
                order.trail_percent = modification.new_trail_percent
            
            # Simulate processing delay
            await asyncio.sleep(0.05)
            
            logger.info(
                "Order modification simulation completed",
                order_id=order.order_id,
                new_price=float(order.price) if order.price else None,
                new_quantity=order.quantity,
            )
            
            return OrderResult(
                success=True,
                order_id=order.order_id,
                trade_plan_id=order.trade_plan_id,
                order_status=order.status,
                error_message=None,
                error_code=None,
                processing_time_ms=50,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                order_type=order.order_type,
            )
            
        except Exception as e:
            logger.error("Order modification simulation failed", error=str(e))
            return self._create_simulation_error_result(order, str(e))
    
    async def cancel_order(self, order: Order) -> OrderResult:
        """Simulate order cancellation."""
        try:
            logger.info("Simulating order cancellation", order_id=order.order_id)
            
            # Simulate processing delay
            await asyncio.sleep(0.05)
            
            # Update order status
            order.status = OrderStatus.CANCELLED
            
            logger.info(
                "Order cancellation simulation completed",
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
                processing_time_ms=50,
                symbol=order.symbol,
                side=order.side,
                quantity=order.quantity,
                order_type=order.order_type,
            )
            
        except Exception as e:
            logger.error("Order cancellation simulation failed", error=str(e))
            return self._create_simulation_error_result(order, str(e))
    
    def _create_simulation_error_result(self, order: Order, error_msg: str) -> OrderResult:
        """Create error result for simulation failures."""
        return OrderResult(
            success=False,
            order_id=order.order_id,
            trade_plan_id=order.trade_plan_id,
            order_status=OrderStatus.REJECTED,
            error_message=f"Simulation error: {error_msg}",
            error_code=9999,  # Generic simulation error code
            processing_time_ms=0,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
            order_type=order.order_type,
        )