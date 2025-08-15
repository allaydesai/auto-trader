"""Trade plan data models with comprehensive validation."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field, field_validator, model_validator, ConfigDict


class TradePlanStatus(str, Enum):
    """Valid states for a trade plan."""
    
    AWAITING_ENTRY = "awaiting_entry"
    POSITION_OPEN = "position_open"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


class RiskCategory(str, Enum):
    """Risk categories with associated percentages."""
    
    SMALL = "small"    # 1%
    NORMAL = "normal"  # 2% 
    LARGE = "large"    # 3%


class ExecutionFunction(BaseModel):
    """Execution function configuration for trade entry/exit logic."""
    
    model_config = ConfigDict(
        validate_assignment=True,
        str_strip_whitespace=True,
        frozen=True,
    )
    
    function_type: str = Field(
        ...,
        description="Type identifier for execution function",
        min_length=1,
        max_length=50,
    )
    timeframe: str = Field(
        ...,
        description="Candle timeframe for evaluation",
        pattern=r"^(1|5|15|30|60|240|1440)min$|^(1|4|1440)h$|^1d$",
    )
    parameters: Dict[str, Any] = Field(
        default_factory=dict,
        description="Function-specific parameters",
    )
    last_evaluated: Optional[datetime] = Field(
        default=None,
        description="Last evaluation timestamp (UTC)",
    )
    
    @field_validator("function_type")
    @classmethod
    def validate_function_type(cls, v: str) -> str:
        """Validate function type is supported."""
        supported_functions = {
            "close_above",
            "close_below", 
            "trailing_stop",
            "stop_loss_take_profit",
        }
        if v not in supported_functions:
            raise ValueError(
                f"Unsupported function_type '{v}'. "
                f"Supported: {', '.join(sorted(supported_functions))}"
            )
        return v


class TradePlan(BaseModel):
    """Complete trading strategy with validation for a single symbol."""
    
    model_config = ConfigDict(
        validate_assignment=True,
        str_strip_whitespace=True,
        use_enum_values=True,
    )
    
    plan_id: str = Field(
        ...,
        description="Unique identifier for the plan",
        min_length=1,
        max_length=100,
        pattern=r"^[A-Z0-9_]+$",
    )
    symbol: str = Field(
        ..., 
        description="Trading symbol",
        min_length=1,
        max_length=10,
    )
    entry_level: Decimal = Field(
        ...,
        description="Price level for entry",
        gt=0,
        decimal_places=4,
    )
    stop_loss: Decimal = Field(
        ...,
        description="Stop loss price", 
        gt=0,
        decimal_places=4,
    )
    take_profit: Decimal = Field(
        ...,
        description="Target price",
        gt=0,
        decimal_places=4,
    )
    risk_category: RiskCategory = Field(
        ...,
        description="Risk level: small (1%), normal (2%), large (3%)",
    )
    entry_function: ExecutionFunction = Field(
        ...,
        description="Entry trigger logic",
    )
    exit_function: ExecutionFunction = Field(
        ...,
        description="Exit trigger logic",
    )
    status: TradePlanStatus = Field(
        default=TradePlanStatus.AWAITING_ENTRY,
        description="Current state of the plan",
    )
    calculated_position_size: Optional[int] = Field(
        default=None,
        description="Dynamically calculated position size",
        gt=0,
    )
    dollar_risk: Optional[Decimal] = Field(
        default=None,
        description="Calculated risk amount in dollars",
        ge=0,
        decimal_places=2,
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.utcnow(),
        description="Plan creation timestamp (UTC)",
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Last update timestamp (UTC)",
    )
    
    @field_validator("symbol")
    @classmethod
    def validate_symbol(cls, v: str) -> str:
        """Validate symbol format: 1-10 uppercase chars, no special chars."""
        if not re.match(r"^[A-Z]{1,10}$", v):
            raise ValueError(
                f"Invalid symbol '{v}'. "
                "Must be 1-10 uppercase letters only (e.g., 'AAPL', 'MSFT')"
            )
        return v
    
    @field_validator("entry_level", "stop_loss", "take_profit")
    @classmethod
    def validate_price_precision(cls, v: Decimal) -> Decimal:
        """Validate price has maximum 4 decimal places."""
        # Check if the decimal has more than 4 decimal places
        exponent = v.as_tuple().exponent
        if isinstance(exponent, int) and exponent < -4:
            raise ValueError(
                f"Price {v} has too many decimal places. "
                "Maximum 4 decimal places allowed (e.g., 123.4567)"
            )
        return v
    
    @model_validator(mode="after")
    def validate_price_relationships(self) -> TradePlan:
        """Validate price level relationships make sense."""
        # Prevent zero-risk trades
        if self.entry_level == self.stop_loss:
            raise ValueError(
                f"entry_level ({self.entry_level}) cannot equal stop_loss "
                f"({self.stop_loss}). This creates zero-risk trades."
            )
        
        # Determine if this is a long or short position based on take_profit vs entry
        is_long_position = self.take_profit > self.entry_level
        
        if is_long_position:
            # Long position: stop_loss < entry_level < take_profit
            if not (self.stop_loss < self.entry_level < self.take_profit):
                raise ValueError(
                    f"Invalid LONG position price relationship. "
                    f"Expected: stop_loss < entry_level < take_profit. "
                    f"Got: stop={self.stop_loss}, entry={self.entry_level}, "
                    f"target={self.take_profit}"
                )
        else:
            # Short position: take_profit < entry_level < stop_loss
            if not (self.take_profit < self.entry_level < self.stop_loss):
                raise ValueError(
                    f"Invalid SHORT position price relationship. "
                    f"Expected: take_profit < entry_level < stop_loss. "
                    f"Got: target={self.take_profit}, entry={self.entry_level}, "
                    f"stop={self.stop_loss}"
                )
        
        return self
    
    @model_validator(mode="after") 
    def validate_plan_id_format(self) -> TradePlan:
        """Validate plan_id follows expected format."""
        if not re.match(r"^[A-Z0-9_]+$", self.plan_id):
            raise ValueError(
                f"Invalid plan_id '{self.plan_id}'. "
                "Must contain only uppercase letters, numbers, and underscores "
                "(e.g., 'AAPL_20250815_001')"
            )
        return self


class TradePlanValidationError(Exception):
    """Custom exception for trade plan validation errors."""
    
    def __init__(
        self, 
        message: str, 
        field: Optional[str] = None,
        line_number: Optional[int] = None,
        suggestion: Optional[str] = None,
    ) -> None:
        """Initialize validation error with context."""
        self.message = message
        self.field = field
        self.line_number = line_number 
        self.suggestion = suggestion
        super().__init__(message)
    
    def __str__(self) -> str:
        """Format error message with context."""
        parts = []
        if self.line_number:
            parts.append(f"Line {self.line_number}")
        if self.field:
            parts.append(f"Field '{self.field}'")
        
        error_msg = self.message
        if parts:
            error_msg = f"{' - '.join(parts)}: {error_msg}"
            
        if self.suggestion:
            error_msg += f"\nFix: {self.suggestion}"
            
        return error_msg


class ValidationResult(BaseModel):
    """Result of trade plan validation."""
    
    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)
    
    is_valid: bool = Field(..., description="Whether validation passed")
    errors: list[TradePlanValidationError] = Field(
        default_factory=list,
        description="List of validation errors",
    )
    plan_id: Optional[str] = Field(
        default=None, 
        description="Plan ID if validation succeeded",
    )
    
    @property
    def error_count(self) -> int:
        """Number of validation errors."""
        return len(self.errors)
    
    def get_error_summary(self) -> str:
        """Get formatted summary of all errors."""
        if not self.errors:
            return "No validation errors"
            
        lines = [f"Found {self.error_count} validation error(s):"]
        for i, error in enumerate(self.errors, 1):
            lines.append(f"{i}. {error}")
        
        return "\n".join(lines)