"""Order execution integration adapter for execution function framework."""

import asyncio
from decimal import Decimal
from typing import Dict, Any, Optional
from datetime import datetime, UTC

from loguru import logger

from auto_trader.models.execution import ExecutionContext, ExecutionSignal, PositionState
from auto_trader.models.enums import ExecutionAction, Timeframe
from auto_trader.models.order import OrderRequest, OrderResult, OrderModification
from auto_trader.models.enums import OrderSide
from auto_trader.models.trade_plan import RiskCategory
from auto_trader.integrations.ibkr_client.order_execution_manager import (
    OrderExecutionManager,
    OrderExecutionError,
)


class ExecutionOrderAdapter:
    """Adapter connecting execution signals to order execution system.
    
    Converts execution function signals into order requests and manages
    the integration between the execution framework and order system.
    """
    
    def __init__(
        self,
        order_execution_manager: OrderExecutionManager,
        default_risk_category: RiskCategory = RiskCategory.NORMAL,
    ):
        """Initialize execution order adapter.
        
        Args:
            order_execution_manager: Order execution manager from Story 2.3
            default_risk_category: Default risk category for position sizing
        """
        self.order_execution_manager = order_execution_manager
        self.default_risk_category = default_risk_category
        
        # Track execution function generated orders
        self.execution_orders: Dict[str, str] = {}  # execution_id -> order_id
        
        # Configuration for order generation
        self.config = {
            "default_risk_category": default_risk_category,
            "order_timeout_seconds": 300,  # 5 minutes
            "max_retry_attempts": 3,
        }
        
        logger.info("ExecutionOrderAdapter initialized")
    
    async def handle_execution_signal(self, signal_data: Dict[str, Any]) -> Optional[OrderResult]:
        """Handle execution signal and convert to order if appropriate.
        
        Args:
            signal_data: Signal data from execution framework containing:
                - function_name: Name of execution function
                - symbol: Trading symbol
                - timeframe: Execution timeframe
                - signal: ExecutionSignal object
                - context: ExecutionContext object
                - timestamp: Signal generation time
                
        Returns:
            OrderResult if order was placed, None if no order needed
        """
        try:
            signal = signal_data["signal"]
            context = signal_data["context"]
            function_name = signal_data["function_name"]
            
            logger.info(
                f"Processing execution signal from {function_name}",
                action=signal.action.value,
                confidence=signal.confidence,
                symbol=context.symbol,
            )
            
            # Route based on signal action
            if signal.action == ExecutionAction.ENTER_LONG:
                return await self._handle_entry_long(signal, context, function_name)
            elif signal.action == ExecutionAction.ENTER_SHORT:
                return await self._handle_entry_short(signal, context, function_name)
            elif signal.action == ExecutionAction.EXIT:
                return await self._handle_exit(signal, context, function_name)
            elif signal.action == ExecutionAction.MODIFY_STOP:
                return await self._handle_modify_stop(signal, context, function_name)
            else:
                # No action needed
                return None
                
        except Exception as e:
            logger.error(
                f"Error handling execution signal: {e}",
                signal_data=signal_data,
                exc_info=True,
            )
            return None
    
    async def _handle_entry_long(
        self,
        signal: ExecutionSignal,
        context: ExecutionContext,
        function_name: str,
    ) -> Optional[OrderResult]:
        """Handle long entry signal.
        
        Args:
            signal: Execution signal
            context: Execution context
            function_name: Name of generating function
            
        Returns:
            OrderResult if successful
        """
        try:
            # Create order request
            order_request = await self._create_entry_order_request(
                symbol=context.symbol,
                side=OrderSide.BUY,
                signal=signal,
                context=context,
                function_name=function_name,
            )
            
            if not order_request:
                return None
            
            # Place the order
            result = await self.order_execution_manager.place_market_order(order_request)
            
            if result.success:
                # Track the order
                execution_id = self._generate_execution_id(function_name, context)
                self.execution_orders[execution_id] = result.order_id
                
                logger.info(
                    f"Long entry order placed successfully",
                    order_id=result.order_id,
                    symbol=context.symbol,
                    function=function_name,
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Error placing long entry order: {e}")
            return OrderResult(
                success=False,
                error_message=str(e),
                trade_plan_id="unknown",
                order_status="Rejected",
                symbol=context.symbol,
                side=OrderSide.BUY,
                quantity=0,
                order_type="MKT",
            )
    
    async def _handle_entry_short(
        self,
        signal: ExecutionSignal,
        context: ExecutionContext,
        function_name: str,
    ) -> Optional[OrderResult]:
        """Handle short entry signal.
        
        Args:
            signal: Execution signal
            context: Execution context
            function_name: Name of generating function
            
        Returns:
            OrderResult if successful
        """
        try:
            # Create order request
            order_request = await self._create_entry_order_request(
                symbol=context.symbol,
                side=OrderSide.SELL,
                signal=signal,
                context=context,
                function_name=function_name,
            )
            
            if not order_request:
                return None
            
            # Place the order
            result = await self.order_execution_manager.place_market_order(order_request)
            
            if result.success:
                # Track the order
                execution_id = self._generate_execution_id(function_name, context)
                self.execution_orders[execution_id] = result.order_id
                
                logger.info(
                    f"Short entry order placed successfully",
                    order_id=result.order_id,
                    symbol=context.symbol,
                    function=function_name,
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Error placing short entry order: {e}")
            return OrderResult(
                success=False,
                error_message=str(e),
                trade_plan_id="unknown",
                order_status="Rejected",
                symbol=context.symbol,
                side=OrderSide.SELL,
                quantity=0,
                order_type="MKT",
            )
    
    async def _handle_exit(
        self,
        signal: ExecutionSignal,
        context: ExecutionContext,
        function_name: str,
    ) -> Optional[OrderResult]:
        """Handle exit signal.
        
        Args:
            signal: Execution signal
            context: Execution context
            function_name: Name of generating function
            
        Returns:
            OrderResult if successful
        """
        if not context.has_position:
            logger.warning("Exit signal received but no position exists")
            return None
        
        try:
            position = context.position_state
            
            # Determine order side (opposite of position)
            side = OrderSide.SELL if position.is_long else OrderSide.BUY
            
            # Create exit order request
            plan_id = f"EXIT_{function_name}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
            order_request = OrderRequest(
                trade_plan_id=plan_id,
                symbol=context.symbol,
                side=side,
                order_type="MKT",  # Market order for immediate exit
                entry_price=position.current_price,
                stop_loss_price=position.current_price * Decimal("0.95"),
                take_profit_price=position.current_price * Decimal("1.05"),
                risk_category=self.default_risk_category,
                calculated_position_size=abs(position.quantity),  # Exit the entire position
                notes=f"Exit triggered by {function_name}: {signal.reasoning}",
            )
            
            # Place the order
            result = await self.order_execution_manager.place_market_order(order_request)
            
            if result.success:
                logger.info(
                    f"Exit order placed successfully",
                    order_id=result.order_id,
                    symbol=context.symbol,
                    quantity=abs(position.quantity),
                    reason=signal.reasoning,
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Error placing exit order: {e}")
            return OrderResult(
                success=False,
                error_message=str(e),
                trade_plan_id="unknown",
                order_status="Rejected",
                symbol=context.symbol,
                side=OrderSide.SELL if context.position_state and context.position_state.is_long else OrderSide.BUY,
                quantity=0,
                order_type="MKT",
            )
    
    async def _handle_modify_stop(
        self,
        signal: ExecutionSignal,
        context: ExecutionContext,
        function_name: str,
    ) -> Optional[OrderResult]:
        """Handle modify stop signal.
        
        Args:
            signal: Execution signal
            context: Execution context
            function_name: Name of generating function
            
        Returns:
            OrderResult if successful
        """
        if not context.has_position:
            logger.warning("Modify stop signal received but no position exists")
            return None
        
        try:
            # Extract new stop level from signal metadata
            new_stop_level = signal.metadata.get("new_stop_level")
            if not new_stop_level:
                logger.error("Modify stop signal missing new_stop_level in metadata")
                return None
            
            position = context.position_state
            
            # Find existing stop order (this would need integration with order tracking)
            # For now, we'll create a new stop order
            plan_id = f"STOP_{function_name}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
            stop_level = Decimal(str(new_stop_level))
            order_request = OrderRequest(
                trade_plan_id=plan_id,
                symbol=context.symbol,
                side=OrderSide.SELL if position.is_long else OrderSide.BUY,
                order_type="STP",  # Stop order
                entry_price=position.current_price,
                stop_loss_price=stop_level,
                take_profit_price=position.take_profit or position.current_price * Decimal("1.10"),
                risk_category=self.default_risk_category,
                notes=f"Stop modified by {function_name}: {signal.reasoning}",
            )
            
            # Place the modified stop order
            result = await self.order_execution_manager.place_stop_order(order_request)
            
            if result.success:
                logger.info(
                    f"Stop order modified successfully",
                    order_id=result.order_id,
                    symbol=context.symbol,
                    new_stop=new_stop_level,
                    function=function_name,
                )
            
            return result
            
        except Exception as e:
            logger.error(f"Error modifying stop order: {e}")
            return OrderResult(
                success=False,
                error_message=str(e),
                trade_plan_id="unknown",
                order_status="Rejected",
                symbol=context.symbol,
                side=OrderSide.SELL if context.position_state and context.position_state.is_long else OrderSide.BUY,
                quantity=0,
                order_type="STP",
            )
    
    async def _create_entry_order_request(
        self,
        symbol: str,
        side: OrderSide,
        signal: ExecutionSignal,
        context: ExecutionContext,
        function_name: str,
    ) -> Optional[OrderRequest]:
        """Create order request for entry signals.
        
        Args:
            symbol: Trading symbol
            side: Order side (BUY/SELL)
            signal: Execution signal
            context: Execution context
            function_name: Name of generating function
            
        Returns:
            OrderRequest or None if cannot create
        """
        try:
            # Extract parameters from signal metadata
            entry_price = signal.metadata.get("close_price")
            if not entry_price:
                # Use current bar close price
                entry_price = float(context.current_bar.close_price)
            
            # Determine risk category based on signal confidence
            risk_category = self._map_confidence_to_risk_category(signal.confidence)
            
            # Create the order request
            plan_id = f"{function_name}_{symbol}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
            entry_decimal = Decimal(str(entry_price))
            order_request = OrderRequest(
                trade_plan_id=plan_id,
                symbol=symbol,
                side=side,
                order_type="MKT",  # Market order for immediate execution
                entry_price=entry_decimal,
                stop_loss_price=entry_decimal * Decimal("0.95"),  # Default 5% stop
                take_profit_price=entry_decimal * Decimal("1.10"),  # Default 10% target
                risk_category=risk_category,
                notes=f"Entry triggered by {function_name}: {signal.reasoning}",
            )
            
            return order_request
            
        except Exception as e:
            logger.error(f"Error creating entry order request: {e}")
            return None
    
    def _map_confidence_to_risk_category(self, confidence: float) -> RiskCategory:
        """Map signal confidence to risk category.
        
        Args:
            confidence: Signal confidence (0.0 to 1.0)
            
        Returns:
            Appropriate risk category
        """
        if confidence >= 0.8:
            return RiskCategory.LARGE  # High confidence = larger position
        elif confidence >= 0.6:
            return RiskCategory.NORMAL
        else:
            return RiskCategory.SMALL  # Low confidence = smaller position
    
    def _generate_execution_id(self, function_name: str, context: ExecutionContext) -> str:
        """Generate unique execution ID.
        
        Args:
            function_name: Name of execution function
            context: Execution context
            
        Returns:
            Unique execution ID
        """
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        return f"{function_name}_{context.symbol}_{context.timeframe.value}_{timestamp}"
    
    def get_execution_orders(self) -> Dict[str, str]:
        """Get mapping of execution IDs to order IDs.
        
        Returns:
            Dictionary mapping execution IDs to order IDs
        """
        return self.execution_orders.copy()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get adapter statistics.
        
        Returns:
            Dictionary with adapter statistics
        """
        return {
            "tracked_orders": len(self.execution_orders),
            "default_risk_category": self.default_risk_category.value,
            "config": self.config,
        }