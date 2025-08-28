"""Execution function framework base classes and utilities."""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING
from decimal import Decimal

from loguru import logger

from auto_trader.models.execution import (
    ExecutionContext,
    ExecutionSignal,
    ExecutionFunctionConfig,
)

if TYPE_CHECKING:
    from auto_trader.models.market_data import BarData


class ExecutionFunctionBase(ABC):
    """Abstract base class for all execution functions.

    Execution functions evaluate market conditions and generate trading signals
    based on their specific logic and parameters.
    """

    def __init__(self, config: ExecutionFunctionConfig):
        """Initialize execution function with configuration.

        Args:
            config: Function configuration including parameters
        """
        self.config = config
        self.name = config.name
        self.timeframe = config.timeframe
        self.parameters = config.parameters
        self.enabled = config.enabled
        self.lookback_bars = config.lookback_bars

        # Validate parameters on initialization
        if not self.validate_parameters(self.parameters):
            raise ValueError(f"Invalid parameters for {self.__class__.__name__}")

        logger.info(
            f"Initialized {self.__class__.__name__} '{self.name}' "
            f"for {self.timeframe.value}"
        )

    @abstractmethod
    async def evaluate(self, context: ExecutionContext) -> ExecutionSignal:
        """Evaluate market conditions and return execution signal.

        Args:
            context: Execution context with market data and position state

        Returns:
            ExecutionSignal with action, confidence, and reasoning
        """
        pass

    @abstractmethod
    def validate_parameters(self, params: Dict[str, Any]) -> bool:
        """Validate function-specific parameters.

        Args:
            params: Parameters to validate

        Returns:
            True if parameters are valid, False otherwise
        """
        pass

    @property
    @abstractmethod
    def required_parameters(self) -> Set[str]:
        """Get set of required parameter names.

        Returns:
            Set of parameter names that must be provided
        """
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Get human-readable description of function.

        Returns:
            Description of what this function does
        """
        pass

    @property
    def is_enabled(self) -> bool:
        """Check if function is enabled."""
        return self.enabled

    def get_parameter(self, key: str, default: Any = None) -> Any:
        """Get parameter value with optional default.

        Args:
            key: Parameter key
            default: Default value if key not found

        Returns:
            Parameter value or default
        """
        return self.parameters.get(key, default)

    def check_sufficient_data(self, context: ExecutionContext) -> bool:
        """Check if there's sufficient historical data for evaluation.

        Args:
            context: Execution context with historical bars

        Returns:
            True if sufficient data available
        """
        available_bars = len(context.historical_bars)
        if available_bars < self.lookback_bars:
            logger.warning(
                f"{self.name}: Insufficient historical data "
                f"(need {self.lookback_bars}, have {available_bars})"
            )
            return False
        return True

    def calculate_confidence_from_volume(
        self, current_volume: int, avg_volume: float, base_confidence: float = 0.5
    ) -> float:
        """Calculate confidence adjustment based on volume.

        Higher volume relative to average increases confidence.

        Args:
            current_volume: Current bar volume
            avg_volume: Average volume over lookback period
            base_confidence: Base confidence level

        Returns:
            Adjusted confidence between 0 and 1
        """
        if avg_volume == 0:
            return base_confidence

        volume_ratio = current_volume / avg_volume

        # Adjust confidence based on volume
        # Higher volume = higher confidence (up to 20% boost)
        volume_adjustment = min(0.2, (volume_ratio - 1) * 0.1)

        return max(0, min(1, base_confidence + volume_adjustment))

    def calculate_momentum(self, bars: List["BarData"]) -> Decimal:
        """Calculate price momentum over given bars.

        Args:
            bars: List of historical bars

        Returns:
            Momentum as percentage change
        """
        if len(bars) < 2:
            return Decimal("0")

        first_close = bars[0].close_price
        last_close = bars[-1].close_price

        if first_close == 0:
            return Decimal("0")

        momentum = ((last_close - first_close) / first_close) * Decimal("100")
        return momentum

    def format_price(self, price: Decimal) -> str:
        """Format price for display.

        Args:
            price: Price to format

        Returns:
            Formatted price string
        """
        return f"${price:.4f}"

    def __str__(self) -> str:
        """String representation of function."""
        return f"{self.__class__.__name__}({self.name}, {self.timeframe.value})"

    def __repr__(self) -> str:
        """Detailed representation of function."""
        return (
            f"{self.__class__.__name__}("
            f"name={self.name}, "
            f"timeframe={self.timeframe.value}, "
            f"enabled={self.enabled}, "
            f"parameters={self.parameters})"
        )


class ValidationMixin:
    """Mixin class for common parameter validation methods."""

    @staticmethod
    def validate_price_parameter(params: Dict[str, Any], key: str) -> bool:
        """Validate a price parameter.

        Args:
            params: Parameters dictionary
            key: Parameter key to validate

        Returns:
            True if valid price parameter
        """
        if key not in params:
            return False

        try:
            price = Decimal(str(params[key]))
            return price > 0
        except (ValueError, TypeError):
            return False

    @staticmethod
    def validate_percentage_parameter(params: Dict[str, Any], key: str) -> bool:
        """Validate a percentage parameter.

        Args:
            params: Parameters dictionary
            key: Parameter key to validate

        Returns:
            True if valid percentage (0-100)
        """
        if key not in params:
            return False

        try:
            percentage = float(params[key])
            return 0 <= percentage <= 100
        except (ValueError, TypeError):
            return False

    @staticmethod
    def validate_integer_parameter(
        params: Dict[str, Any],
        key: str,
        min_value: Optional[int] = None,
        max_value: Optional[int] = None,
    ) -> bool:
        """Validate an integer parameter with optional bounds.

        Args:
            params: Parameters dictionary
            key: Parameter key to validate
            min_value: Minimum allowed value
            max_value: Maximum allowed value

        Returns:
            True if valid integer within bounds
        """
        if key not in params:
            return False

        try:
            value = int(params[key])

            if min_value is not None and value < min_value:
                return False
            if max_value is not None and value > max_value:
                return False

            return True
        except (ValueError, TypeError):
            return False
