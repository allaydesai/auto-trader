"""Risk management data models with comprehensive validation."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class PositionSizeResult(BaseModel):
    """Result of position size calculation with validation."""
    
    model_config = ConfigDict(
        frozen=True,
        validate_assignment=True,
        str_strip_whitespace=True,
    )
    
    position_size: int = Field(
        ...,
        gt=0,
        description="Calculated position size in shares",
    )
    dollar_risk: Decimal = Field(
        ...,
        ge=0,
        decimal_places=2,
        description="Risk amount in dollars",
    )
    validation_status: bool = Field(
        ...,
        description="Whether calculation is valid",
    )
    portfolio_risk_percentage: Decimal = Field(
        ...,
        ge=0,
        decimal_places=2,
        description="Risk percentage for this trade",
    )
    risk_category: str = Field(
        ...,
        description="Risk category used (small/normal/large)",
    )
    account_value: Decimal = Field(
        ...,
        gt=0,
        decimal_places=2,
        description="Account value used in calculation",
    )


class RiskCheck(BaseModel):
    """Risk validation result with detailed information."""
    
    model_config = ConfigDict(
        frozen=True,
        validate_assignment=True,
        str_strip_whitespace=True,
    )
    
    passed: bool = Field(
        ...,
        description="Whether risk check passed",
    )
    reason: Optional[str] = Field(
        None,
        description="Reason for failure if applicable",
    )
    current_risk: Decimal = Field(
        ...,
        ge=0,
        decimal_places=2,
        description="Current portfolio risk percentage",
    )
    new_trade_risk: Decimal = Field(
        ...,
        ge=0,
        decimal_places=2,
        description="Risk percentage of new trade",
    )
    total_risk: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        decimal_places=2,
        description="Combined risk percentage",
    )
    limit: Decimal = Field(
        default=Decimal("10.0"),
        gt=0,
        decimal_places=1,
        description="Risk limit percentage",
    )
    
    def __post_init__(self) -> None:
        """Calculate total risk after initialization."""
        if self.total_risk == Decimal("0"):
            object.__setattr__(
                self, 
                "total_risk", 
                self.current_risk + self.new_trade_risk
            )


class PositionRiskEntry(BaseModel):
    """Single position risk tracking entry."""
    
    model_config = ConfigDict(
        validate_assignment=True,
        str_strip_whitespace=True,
    )
    
    position_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique position identifier",
    )
    symbol: str = Field(
        ...,
        min_length=1,
        max_length=10,
        description="Trading symbol",
    )
    risk_amount: Decimal = Field(
        ...,
        ge=0,
        decimal_places=2,
        description="Risk amount in dollars",
    )
    plan_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Trade plan identifier",
    )
    entry_time: datetime = Field(
        default_factory=lambda: datetime.utcnow(),
        description="Position entry timestamp (UTC)",
    )


class PortfolioRiskState(BaseModel):
    """Complete portfolio risk snapshot for persistence."""
    
    model_config = ConfigDict(
        validate_assignment=True,
        str_strip_whitespace=True,
    )
    
    positions: List[PositionRiskEntry] = Field(
        default_factory=list,
        description="List of open positions with risk",
    )
    total_risk_percentage: Decimal = Field(
        default=Decimal("0"),
        ge=0,
        decimal_places=2,
        description="Current total portfolio risk percentage",
    )
    account_value: Decimal = Field(
        ...,
        ge=0,
        decimal_places=2,
        description="Account value used for calculations",
    )
    last_updated: datetime = Field(
        default_factory=lambda: datetime.utcnow(),
        description="Last state update timestamp (UTC)",
    )
    
    @property
    def position_count(self) -> int:
        """Number of open positions."""
        return len(self.positions)
    
    @property
    def total_dollar_risk(self) -> Decimal:
        """Total dollar risk across all positions."""
        return sum(pos.risk_amount for pos in self.positions)


class RiskValidationResult(BaseModel):
    """Comprehensive risk validation result."""
    
    model_config = ConfigDict(
        validate_assignment=True,
        str_strip_whitespace=True,
    )
    
    is_valid: bool = Field(
        ...,
        description="Overall validation status",
    )
    position_size_result: Optional[PositionSizeResult] = Field(
        None,
        description="Position sizing calculation result",
    )
    portfolio_risk_check: RiskCheck = Field(
        ...,
        description="Portfolio risk validation result",
    )
    errors: List[str] = Field(
        default_factory=list,
        description="List of validation errors",
    )
    warnings: List[str] = Field(
        default_factory=list,
        description="List of non-blocking warnings",
    )
    
    @property
    def error_count(self) -> int:
        """Number of validation errors."""
        return len(self.errors)
    
    @property
    def warning_count(self) -> int:
        """Number of warnings."""
        return len(self.warnings)
    
    def get_error_summary(self) -> str:
        """Get formatted summary of all errors."""
        if not self.errors:
            return "No validation errors"
            
        lines = [f"Found {self.error_count} validation error(s):"]
        for i, error in enumerate(self.errors, 1):
            lines.append(f"{i}. {error}")
        
        return "\n".join(lines)
    
    def get_warning_summary(self) -> str:
        """Get formatted summary of all warnings."""
        if not self.warnings:
            return "No warnings"
            
        lines = [f"Found {self.warning_count} warning(s):"]
        for i, warning in enumerate(self.warnings, 1):
            lines.append(f"{i}. {warning}")
        
        return "\n".join(lines)


class RiskManagementError(Exception):
    """Base exception for risk management errors."""
    
    def __init__(
        self, 
        message: str, 
        error_code: Optional[str] = None,
        context: Optional[dict] = None,
    ) -> None:
        """Initialize risk management error with context."""
        self.message = message
        self.error_code = error_code
        self.context = context or {}
        super().__init__(message)


class PortfolioRiskExceededError(RiskManagementError):
    """Raised when portfolio risk limits are exceeded."""
    
    def __init__(
        self, 
        current_risk: Decimal, 
        new_risk: Decimal, 
        limit: Decimal,
    ) -> None:
        """Initialize portfolio risk exceeded error."""
        self.current_risk = current_risk
        self.new_risk = new_risk
        self.limit = limit
        self.total_risk = current_risk + new_risk
        
        message = (
            f"Portfolio risk limit exceeded: {self.total_risk:.2f}% "
            f"(current: {current_risk:.2f}% + new: {new_risk:.2f}%) "
            f"exceeds limit of {limit:.2f}%"
        )
        
        context = {
            "current_risk": float(current_risk),
            "new_risk": float(new_risk),
            "total_risk": float(self.total_risk),
            "limit": float(limit),
        }
        
        super().__init__(message, "RISK_001", context)


class InvalidPositionSizeError(RiskManagementError):
    """Raised when position size calculation is invalid."""
    
    def __init__(
        self, 
        reason: str, 
        entry_price: Optional[Decimal] = None,
        stop_price: Optional[Decimal] = None,
    ) -> None:
        """Initialize invalid position size error."""
        self.reason = reason
        self.entry_price = entry_price
        self.stop_price = stop_price
        
        context = {}
        if entry_price is not None:
            context["entry_price"] = float(entry_price)
        if stop_price is not None:
            context["stop_price"] = float(stop_price)
            
        super().__init__(reason, "RISK_002", context)


class DailyLossLimitExceededError(RiskManagementError):
    """Raised when daily loss limit is exceeded."""
    
    def __init__(
        self, 
        current_loss: Decimal, 
        limit: Decimal,
    ) -> None:
        """Initialize daily loss limit exceeded error."""
        self.current_loss = current_loss
        self.limit = limit
        
        message = (
            f"Daily loss limit exceeded: ${current_loss:.2f} "
            f"exceeds limit of ${limit:.2f}"
        )
        
        context = {
            "current_loss": float(current_loss),
            "limit": float(limit),
        }
        
        super().__init__(message, "RISK_003", context)