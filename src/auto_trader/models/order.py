# Order models for trade execution
from decimal import Decimal
from datetime import datetime, UTC
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict, field_validator, computed_field

from .enums import (
    OrderType, 
    OrderSide, 
    OrderStatus, 
    OrderAction,
    BracketOrderType,
    TimeInForce
)
from .trade_plan import RiskCategory


class Order(BaseModel):
    """Core order representation with IBKR integration."""
    
    # Core order identification
    order_id: Optional[str] = Field(None, description="IBKR order ID")
    parent_order_id: Optional[str] = Field(None, description="Parent order ID for bracket orders")
    trade_plan_id: str = Field(..., description="Associated trade plan ID")
    
    # Contract details
    symbol: str = Field(..., min_length=1, max_length=10, description="Trading symbol")
    exchange: str = Field(default="SMART", description="Exchange routing")
    currency: str = Field(default="USD", description="Contract currency")
    
    # Order parameters
    side: OrderSide = Field(..., description="Buy or Sell")
    order_type: OrderType = Field(..., description="Order type")
    quantity: int = Field(..., gt=0, description="Order quantity")
    
    # Price parameters (optional based on order type)
    price: Optional[Decimal] = Field(None, gt=0, decimal_places=4, description="Limit price")
    stop_price: Optional[Decimal] = Field(None, gt=0, decimal_places=4, description="Stop price")
    trail_amount: Optional[Decimal] = Field(None, gt=0, decimal_places=4, description="Trailing amount")
    trail_percent: Optional[Decimal] = Field(None, gt=0, le=100, decimal_places=2, description="Trailing percent")
    
    # Order configuration
    time_in_force: TimeInForce = Field(default=TimeInForce.DAY, description="Time in force")
    transmit: bool = Field(default=True, description="Transmit order immediately")
    
    # Status tracking
    status: OrderStatus = Field(default=OrderStatus.PENDING, description="Current order status")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    submitted_at: Optional[datetime] = Field(None, description="When order was submitted to IBKR")
    filled_at: Optional[datetime] = Field(None, description="When order was filled")
    
    # Fill information
    filled_quantity: int = Field(default=0, ge=0, description="Filled quantity")
    average_fill_price: Optional[Decimal] = Field(None, decimal_places=4, description="Average fill price")
    
    # Commission and fees
    commission: Optional[Decimal] = Field(None, decimal_places=4, description="Order commission")
    
    # Error handling
    error_message: Optional[str] = Field(None, description="Error message if order failed")
    
    model_config = ConfigDict(
        validate_assignment=True,
        str_strip_whitespace=True,
        use_enum_values=True,
        frozen=False  # Allow status updates
    )
    
    @computed_field
    def remaining_quantity(self) -> int:
        """Calculate remaining quantity from total and filled."""
        return max(0, self.quantity - self.filled_quantity)


class OrderRequest(BaseModel):
    """Request model for order placement with risk calculation."""
    
    # Trade plan association
    trade_plan_id: str = Field(..., description="Associated trade plan ID")
    
    # Contract details
    symbol: str = Field(..., min_length=1, max_length=10, description="Trading symbol")
    exchange: str = Field(default="SMART", description="Exchange routing")
    currency: str = Field(default="USD", description="Contract currency")
    
    # Order details
    side: OrderSide = Field(..., description="Buy or Sell")
    order_type: OrderType = Field(..., description="Order type")
    
    # Price levels for risk calculation
    entry_price: Decimal = Field(..., gt=0, decimal_places=4, description="Entry price")
    stop_loss_price: Decimal = Field(..., gt=0, decimal_places=4, description="Stop loss price")
    take_profit_price: Decimal = Field(..., gt=0, decimal_places=4, description="Take profit price")
    
    # Risk management
    risk_category: RiskCategory = Field(..., description="Risk level for position sizing")
    calculated_position_size: Optional[int] = Field(None, gt=0, description="Calculated position size")
    
    # Order configuration
    time_in_force: TimeInForce = Field(default=TimeInForce.DAY, description="Time in force")
    
    model_config = ConfigDict(
        validate_assignment=True,
        str_strip_whitespace=True,
        use_enum_values=True
    )


class OrderResult(BaseModel):
    """Result of order execution with status and error information."""
    
    success: bool = Field(..., description="Order placement success")
    order_id: Optional[str] = Field(None, description="IBKR order ID if successful")
    trade_plan_id: str = Field(..., description="Associated trade plan ID")
    
    # Status information
    order_status: OrderStatus = Field(..., description="Current order status")
    error_message: Optional[str] = Field(None, description="Error details if failed")
    error_code: Optional[int] = Field(None, description="IBKR error code if applicable")
    
    # Timing
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    processing_time_ms: Optional[int] = Field(None, description="Processing time in milliseconds")
    
    # Order details for confirmation
    symbol: str = Field(..., description="Trading symbol")
    side: OrderSide = Field(..., description="Order side")
    quantity: int = Field(..., ge=0, description="Order quantity")
    order_type: OrderType = Field(..., description="Order type")
    
    model_config = ConfigDict(
        validate_assignment=True,
        str_strip_whitespace=True,
        use_enum_values=True
    )


class BracketOrder(BaseModel):
    """Container for bracket order components (parent + stop loss + take profit)."""
    
    # Order identification
    bracket_id: str = Field(..., description="Unique bracket order ID")
    trade_plan_id: str = Field(..., description="Associated trade plan ID")
    
    # Component orders
    parent_order: Order = Field(..., description="Main entry order")
    stop_loss_order: Order = Field(..., description="Stop loss order")
    take_profit_order: Order = Field(..., description="Take profit order")
    
    # Bracket configuration
    bracket_type: BracketOrderType = Field(default=BracketOrderType.PARENT, description="Bracket type")
    transmit_parent: bool = Field(default=False, description="Transmit parent order first")
    
    # Status tracking
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    all_orders_submitted: bool = Field(default=False, description="All orders submitted to IBKR")
    
    model_config = ConfigDict(
        validate_assignment=True,
        str_strip_whitespace=True,
        use_enum_values=True
    )


class OrderEvent(BaseModel):
    """Event-sourced order status change for audit trail."""
    
    event_id: str = Field(..., description="Unique event ID")
    order_id: str = Field(..., description="Associated order ID")
    trade_plan_id: str = Field(..., description="Associated trade plan ID")
    
    # Event details
    event_type: str = Field(..., description="Event type (status_change, fill, error, etc.)")
    old_status: Optional[OrderStatus] = Field(None, description="Previous order status")
    new_status: OrderStatus = Field(..., description="New order status")
    
    # Event data
    event_data: Dict[str, Any] = Field(default_factory=dict, description="Additional event data")
    
    # Fill details (if applicable)
    fill_quantity: Optional[int] = Field(None, description="Quantity filled in this event")
    fill_price: Optional[Decimal] = Field(None, decimal_places=4, description="Fill price")
    
    # Timing
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    # Error information
    error_message: Optional[str] = Field(None, description="Error message if applicable")
    error_code: Optional[int] = Field(None, description="IBKR error code if applicable")
    
    model_config = ConfigDict(
        validate_assignment=True,
        str_strip_whitespace=True,
        use_enum_values=True
    )


class OrderModification(BaseModel):
    """Model for order modification requests."""
    
    order_id: str = Field(..., description="Order ID to modify")
    
    # Modifiable fields
    new_quantity: Optional[int] = Field(None, gt=0, description="New order quantity")
    new_price: Optional[Decimal] = Field(None, gt=0, decimal_places=4, description="New limit price")
    new_stop_price: Optional[Decimal] = Field(None, gt=0, decimal_places=4, description="New stop price")
    new_trail_amount: Optional[Decimal] = Field(None, gt=0, decimal_places=4, description="New trailing amount")
    new_trail_percent: Optional[Decimal] = Field(None, gt=0, le=100, decimal_places=2, description="New trailing percent")
    
    # Modification metadata
    reason: str = Field(..., description="Reason for modification")
    requested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    
    model_config = ConfigDict(
        validate_assignment=True,
        str_strip_whitespace=True,
        use_enum_values=True
    )