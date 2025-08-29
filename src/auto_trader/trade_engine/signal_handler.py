"""Signal processing logic for different execution actions."""

from typing import Optional, Dict, Any
from datetime import datetime, UTC

from loguru import logger

from auto_trader.models.execution import ExecutionSignal, ExecutionContext
from auto_trader.models.enums import ExecutionAction, OrderSide
from auto_trader.models.order import OrderResult
from auto_trader.integrations.ibkr_client.order_execution_manager import (
    OrderExecutionManager,
)
from auto_trader.trade_engine.order_request_builder import OrderRequestBuilder
from auto_trader.trade_engine.circuit_breaker import CircuitBreakerManager


class SignalHandler:
    """Handles processing of different execution signal types.
    
    Processes entry, exit, and modification signals by routing them
    to appropriate order execution methods.
    """
    
    def __init__(
        self,
        order_execution_manager: OrderExecutionManager,
        order_request_builder: OrderRequestBuilder,
        circuit_breaker: CircuitBreakerManager,
    ):
        """Initialize signal handler.
        
        Args:
            order_execution_manager: Order execution manager
            order_request_builder: Builder for order requests
            circuit_breaker: Circuit breaker manager
        """
        self.order_execution_manager = order_execution_manager
        self.order_request_builder = order_request_builder
        self.circuit_breaker = circuit_breaker
        
        # Track execution function generated orders
        self.execution_orders: Dict[str, str] = {}  # execution_id -> order_id
        
        logger.info("SignalHandler initialized")
    
    async def handle_entry_long(
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
            order_request = self.order_request_builder.create_entry_order(
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
            return self._create_error_result(
                error=str(e),
                symbol=context.symbol,
                side=OrderSide.BUY,
            )
    
    async def handle_entry_short(
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
            order_request = self.order_request_builder.create_entry_order(
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
            return self._create_error_result(
                error=str(e),
                symbol=context.symbol,
                side=OrderSide.SELL,
            )
    
    async def handle_exit(
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
            # Create exit order request
            order_request = self.order_request_builder.create_exit_order(
                signal=signal,
                context=context,
                function_name=function_name,
            )
            
            if not order_request:
                return None
            
            # Place the order
            result = await self.order_execution_manager.place_market_order(order_request)
            
            if result.success:
                position = context.position_state
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
            position = context.position_state
            side = OrderSide.SELL if position and position.is_long else OrderSide.BUY
            return self._create_error_result(
                error=str(e),
                symbol=context.symbol,
                side=side,
            )
    
    async def handle_modify_stop(
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
            # Create stop modification order request
            order_request = self.order_request_builder.create_stop_modification(
                signal=signal,
                context=context,
                function_name=function_name,
            )
            
            if not order_request:
                return None
            
            # Place the modified stop order
            result = await self.order_execution_manager.place_stop_order(order_request)
            
            if result.success:
                new_stop_level = signal.metadata.get("new_stop_level")
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
            position = context.position_state
            side = OrderSide.SELL if position and position.is_long else OrderSide.BUY
            return self._create_error_result(
                error=str(e),
                symbol=context.symbol,
                side=side,
                order_type="STP",
            )
    
    def get_execution_orders(self) -> Dict[str, str]:
        """Get mapping of execution IDs to order IDs.
        
        Returns:
            Dictionary mapping execution IDs to order IDs
        """
        return self.execution_orders.copy()
    
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
    
    def _create_error_result(
        self,
        error: str,
        symbol: str,
        side: OrderSide,
        order_type: str = "MKT",
    ) -> OrderResult:
        """Create error OrderResult.
        
        Args:
            error: Error message
            symbol: Trading symbol
            side: Order side
            order_type: Order type
            
        Returns:
            OrderResult indicating failure
        """
        return OrderResult(
            success=False,
            error_message=error,
            trade_plan_id="unknown",
            order_status="Rejected",
            symbol=symbol,
            side=side,
            quantity=0,
            order_type=order_type,
        )