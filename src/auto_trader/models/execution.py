"""Execution function framework models."""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, TYPE_CHECKING

from pydantic import BaseModel, Field, ConfigDict, computed_field

from auto_trader.models.enums import ConfidenceLevel, ExecutionAction, Timeframe

if TYPE_CHECKING:
    from auto_trader.models.market_data import BarData


@dataclass(frozen=True)
class ExecutionContext:
    """Immutable context for execution function evaluation.

    Contains all data needed for an execution function to make a decision.
    """

    symbol: str
    timeframe: Timeframe
    current_bar: "BarData"  # Forward reference to avoid circular import
    historical_bars: List["BarData"]
    trade_plan_params: Dict[str, Any]
    position_state: Optional["PositionState"]
    account_balance: Decimal
    timestamp: datetime

    def get_param(self, key: str, default: Any = None) -> Any:
        """Get a parameter from trade plan params with optional default."""
        return self.trade_plan_params.get(key, default)

    @property
    def has_position(self) -> bool:
        """Check if there's an open position."""
        return self.position_state is not None and self.position_state.quantity > 0


@dataclass(frozen=True)
class ExecutionSignal:
    """Signal returned by execution functions.

    Represents the decision made by an execution function including
    the action to take, confidence level, and reasoning.
    """

    action: ExecutionAction
    confidence: float  # 0.0 to 1.0
    reasoning: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def confidence_level(self) -> ConfidenceLevel:
        """Convert numeric confidence to categorical level."""
        if self.confidence <= 0.33:
            return ConfidenceLevel.LOW
        elif self.confidence <= 0.66:
            return ConfidenceLevel.MEDIUM
        else:
            return ConfidenceLevel.HIGH

    @property
    def should_execute(self) -> bool:
        """Check if signal should trigger execution."""
        return self.action != ExecutionAction.NONE and self.confidence > 0.5

    @classmethod
    def no_action(cls, reasoning: str = "No conditions met") -> "ExecutionSignal":
        """Create a no-action signal."""
        return cls(
            action=ExecutionAction.NONE,
            confidence=0.0,
            reasoning=reasoning,
            metadata={},
        )


class BarCloseEvent(BaseModel):
    """Event emitted when a bar closes.

    Used to trigger execution function evaluation at precise bar boundaries.
    """

    model_config = ConfigDict(validate_assignment=True, str_strip_whitespace=True)

    symbol: str = Field(..., min_length=1, max_length=10, description="Trading symbol")
    timeframe: Timeframe = Field(..., description="Bar timeframe")
    close_time: datetime = Field(..., description="Exact time of bar close")
    bar_data: "BarData" = Field(..., description="The completed bar data")
    next_close_time: datetime = Field(..., description="Expected next bar close time")

    @computed_field
    @property
    def event_id(self) -> str:
        """Generate unique event ID."""
        timestamp_str = self.close_time.strftime("%Y%m%d_%H%M%S")
        return f"{self.symbol}_{self.timeframe.value}_{timestamp_str}"


class ExecutionLogEntry(BaseModel):
    """Structured log entry for execution decisions.

    Provides comprehensive audit trail of all execution evaluations.
    """

    model_config = ConfigDict(validate_assignment=True, str_strip_whitespace=True)

    timestamp: datetime = Field(..., description="When evaluation occurred")
    function_name: str = Field(..., description="Execution function name")
    symbol: str = Field(..., min_length=1, max_length=10)
    timeframe: Timeframe = Field(..., description="Evaluation timeframe")
    signal: ExecutionSignal = Field(..., description="Resulting signal")
    duration_ms: float = Field(
        ..., gt=0, description="Evaluation duration in milliseconds"
    )
    context_snapshot: Dict[str, Any] = Field(
        default_factory=dict, description="Context data snapshot"
    )
    error: Optional[str] = Field(None, description="Error message if evaluation failed")

    @computed_field
    @property
    def log_level(self) -> str:
        """Determine log level based on signal and error."""
        if self.error:
            return "ERROR"
        elif self.signal.should_execute:
            return "WARNING"  # Important events that trigger actions
        else:
            return "INFO"

    @computed_field
    @property
    def summary(self) -> str:
        """Generate human-readable summary."""
        if self.error:
            return f"[ERROR] {self.function_name} failed: {self.error}"

        action_str = self.signal.action.value
        confidence_str = f"{self.signal.confidence:.1%}"
        return f"{self.function_name}: {action_str} ({confidence_str}) - {self.signal.reasoning}"


class PositionState(BaseModel):
    """Current position state for execution context.

    Represents the current open position if any.
    """

    model_config = ConfigDict(validate_assignment=True, use_enum_values=True)

    symbol: str = Field(..., min_length=1, max_length=10)
    quantity: int = Field(
        ..., description="Position size (positive=long, negative=short)"
    )
    entry_price: Decimal = Field(..., gt=0, decimal_places=4)
    current_price: Decimal = Field(..., gt=0, decimal_places=4)
    stop_loss: Optional[Decimal] = Field(None, gt=0, decimal_places=4)
    take_profit: Optional[Decimal] = Field(None, gt=0, decimal_places=4)
    opened_at: datetime = Field(...)

    @computed_field
    @property
    def is_long(self) -> bool:
        """Check if position is long."""
        return self.quantity > 0

    @computed_field
    @property
    def is_short(self) -> bool:
        """Check if position is short."""
        return self.quantity < 0

    @computed_field
    @property
    def unrealized_pnl(self) -> Decimal:
        """Calculate unrealized P&L."""
        if self.quantity == 0:
            return Decimal("0")

        if self.is_long:
            return (self.current_price - self.entry_price) * Decimal(
                str(abs(self.quantity))
            )
        else:
            return (self.entry_price - self.current_price) * Decimal(
                str(abs(self.quantity))
            )

    @computed_field
    @property
    def unrealized_pnl_percent(self) -> Decimal:
        """Calculate unrealized P&L percentage."""
        if self.quantity == 0:
            return Decimal("0")

        if self.is_long:
            return (
                (self.current_price - self.entry_price) / self.entry_price
            ) * Decimal("100")
        else:
            return (
                (self.entry_price - self.current_price) / self.entry_price
            ) * Decimal("100")


class ExecutionFunctionConfig(BaseModel):
    """Configuration for an execution function instance.

    Used to configure and validate execution function parameters.
    """

    model_config = ConfigDict(validate_assignment=True, str_strip_whitespace=True)

    name: str = Field(..., min_length=1, description="Function name")
    function_type: str = Field(..., description="Type of execution function")
    timeframe: Timeframe = Field(..., description="Timeframe to monitor")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Function-specific parameters"
    )
    enabled: bool = Field(True, description="Whether function is active")
    lookback_bars: int = Field(
        20, ge=1, le=1000, description="Number of historical bars needed"
    )

    def get_param(self, key: str, default: Any = None) -> Any:
        """Get a parameter with optional default."""
        return self.parameters.get(key, default)


# Resolve forward references after all models are defined
def _rebuild_models():
    """Rebuild models with forward references."""
    try:
        from auto_trader.models.market_data import BarData
        BarCloseEvent.model_rebuild()
    except ImportError:
        # BarData not available yet, will be rebuilt later
        pass

_rebuild_models()
