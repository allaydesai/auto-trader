"""Order request builder for creating validated order requests from execution signals."""

from decimal import Decimal
from datetime import datetime, UTC
from typing import Optional, Dict, Any

from loguru import logger

from auto_trader.models.execution import ExecutionSignal, ExecutionContext
from auto_trader.models.order import OrderRequest
from auto_trader.models.enums import OrderSide
from auto_trader.models.trade_plan import RiskCategory


class OrderRequestBuilder:
    """Builds order requests from execution signals and context.
    
    Handles conversion of execution signals into properly formatted
    order requests with appropriate risk management parameters.
    """
    
    def __init__(
        self,
        default_risk_category: RiskCategory = RiskCategory.NORMAL,
        default_stop_loss_percent: float = 0.05,  # 5%
        default_take_profit_percent: float = 0.10,  # 10%
    ):
        """Initialize order request builder.
        
        Args:
            default_risk_category: Default risk category for position sizing
            default_stop_loss_percent: Default stop loss percentage
            default_take_profit_percent: Default take profit percentage
        """
        self.default_risk_category = default_risk_category
        self.default_stop_loss_percent = default_stop_loss_percent
        self.default_take_profit_percent = default_take_profit_percent
        
        logger.info(
            "OrderRequestBuilder initialized",
            default_risk=default_risk_category.value,
            default_stop=default_stop_loss_percent,
            default_target=default_take_profit_percent,
        )
    
    def create_entry_order(
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
            plan_id = self._generate_plan_id(function_name, symbol)
            entry_decimal = Decimal(str(entry_price))
            
            # Calculate stop loss and take profit
            stop_loss_price = self._calculate_stop_loss(entry_decimal, side)
            take_profit_price = self._calculate_take_profit(entry_decimal, side)
            
            order_request = OrderRequest(
                trade_plan_id=plan_id,
                symbol=symbol,
                side=side,
                order_type="MKT",  # Market order for immediate execution
                entry_price=entry_decimal,
                stop_loss_price=stop_loss_price,
                take_profit_price=take_profit_price,
                risk_category=risk_category,
                notes=f"Entry triggered by {function_name}: {signal.reasoning}",
            )
            
            logger.debug(
                f"Created entry order request",
                symbol=symbol,
                side=side.value,
                entry_price=float(entry_decimal),
                risk_category=risk_category.value,
            )
            
            return order_request
            
        except Exception as e:
            logger.error(f"Error creating entry order request: {e}")
            return None
    
    def create_exit_order(
        self,
        signal: ExecutionSignal,
        context: ExecutionContext,
        function_name: str,
    ) -> Optional[OrderRequest]:
        """Create order request for exit signals.
        
        Args:
            signal: Execution signal
            context: Execution context
            function_name: Name of generating function
            
        Returns:
            OrderRequest or None if cannot create
        """
        if not context.has_position:
            logger.warning("Cannot create exit order - no position exists")
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
                stop_loss_price=(position.current_price * Decimal("0.95")).quantize(Decimal('0.0001')),
                take_profit_price=(position.current_price * Decimal("1.05")).quantize(Decimal('0.0001')),
                risk_category=self.default_risk_category,
                calculated_position_size=abs(position.quantity),  # Exit the entire position
                notes=f"Exit triggered by {function_name}: {signal.reasoning}",
            )
            
            logger.debug(
                f"Created exit order request",
                symbol=context.symbol,
                side=side.value,
                quantity=abs(position.quantity),
            )
            
            return order_request
            
        except Exception as e:
            logger.error(f"Error creating exit order request: {e}")
            return None
    
    def create_stop_modification(
        self,
        signal: ExecutionSignal,
        context: ExecutionContext,
        function_name: str,
    ) -> Optional[OrderRequest]:
        """Create order request for stop loss modifications.
        
        Args:
            signal: Execution signal
            context: Execution context
            function_name: Name of generating function
            
        Returns:
            OrderRequest or None if cannot create
        """
        if not context.has_position:
            logger.warning("Cannot modify stop - no position exists")
            return None
        
        try:
            # Extract new stop level from signal metadata
            new_stop_level = signal.metadata.get("new_stop_level")
            if not new_stop_level:
                logger.error("Modify stop signal missing new_stop_level in metadata")
                return None
            
            position = context.position_state
            
            # Create modified stop order request
            plan_id = f"STOP_{function_name}_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
            stop_level = Decimal(str(new_stop_level))
            
            order_request = OrderRequest(
                trade_plan_id=plan_id,
                symbol=context.symbol,
                side=OrderSide.SELL if position.is_long else OrderSide.BUY,
                order_type="STP",  # Stop order
                entry_price=position.current_price,
                stop_loss_price=stop_level,
                take_profit_price=position.take_profit or (
                    position.current_price * Decimal("1.10")
                ).quantize(Decimal('0.0001')),
                risk_category=self.default_risk_category,
                notes=f"Stop modified by {function_name}: {signal.reasoning}",
            )
            
            logger.debug(
                f"Created stop modification order request",
                symbol=context.symbol,
                new_stop=float(stop_level),
            )
            
            return order_request
            
        except Exception as e:
            logger.error(f"Error creating stop modification order request: {e}")
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
    
    def _calculate_stop_loss(self, entry_price: Decimal, side: OrderSide) -> Decimal:
        """Calculate stop loss price based on entry price and side.
        
        Args:
            entry_price: Entry price
            side: Order side
            
        Returns:
            Stop loss price
        """
        if side == OrderSide.BUY:
            # Long position - stop below entry
            multiplier = Decimal(str(1 - self.default_stop_loss_percent))
        else:
            # Short position - stop above entry
            multiplier = Decimal(str(1 + self.default_stop_loss_percent))
        
        return (entry_price * multiplier).quantize(Decimal('0.0001'))
    
    def _calculate_take_profit(self, entry_price: Decimal, side: OrderSide) -> Decimal:
        """Calculate take profit price based on entry price and side.
        
        Args:
            entry_price: Entry price
            side: Order side
            
        Returns:
            Take profit price
        """
        if side == OrderSide.BUY:
            # Long position - target above entry
            multiplier = Decimal(str(1 + self.default_take_profit_percent))
        else:
            # Short position - target below entry
            multiplier = Decimal(str(1 - self.default_take_profit_percent))
        
        return (entry_price * multiplier).quantize(Decimal('0.0001'))
    
    def _generate_plan_id(self, function_name: str, symbol: str) -> str:
        """Generate unique plan ID for order.
        
        Args:
            function_name: Name of execution function
            symbol: Trading symbol
            
        Returns:
            Unique plan ID
        """
        timestamp = datetime.now(UTC).strftime('%Y%m%d_%H%M%S')
        return f"{function_name}_{symbol}_{timestamp}"