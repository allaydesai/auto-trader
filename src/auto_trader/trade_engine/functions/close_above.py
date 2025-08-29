"""Close above threshold execution function."""

from decimal import Decimal
from typing import Any, Dict, Set
from statistics import mean

from loguru import logger

from auto_trader.models.execution import ExecutionContext, ExecutionSignal
from auto_trader.models.enums import ExecutionAction
from auto_trader.trade_engine.execution_functions import (
    ExecutionFunctionBase,
    ValidationMixin,
)


class CloseAboveFunction(ExecutionFunctionBase, ValidationMixin):
    """Execution function that triggers when price closes above a threshold.

    This function monitors for price closes above a specified threshold level,
    commonly used for breakout entries or resistance level breaks.
    """

    @property
    def required_parameters(self) -> Set[str]:
        """Get required parameter names."""
        return {"threshold_price"}

    @property
    def description(self) -> str:
        """Get function description."""
        return "Triggers entry when price closes above threshold level"

    def validate_parameters(self, params: Dict[str, Any]) -> bool:
        """Validate function parameters.

        Args:
            params: Parameters to validate

        Returns:
            True if valid
        """
        # Check required threshold_price
        if not self.validate_price_parameter(params, "threshold_price"):
            logger.error("Invalid or missing threshold_price parameter")
            return False

        # Optional min_volume parameter
        if "min_volume" in params:
            if not self.validate_integer_parameter(params, "min_volume", min_value=0):
                logger.error("Invalid min_volume parameter")
                return False

        # Optional confirmation_bars parameter (number of bars above threshold)
        if "confirmation_bars" in params:
            if not self.validate_integer_parameter(
                params, "confirmation_bars", min_value=1, max_value=10
            ):
                logger.error("Invalid confirmation_bars parameter")
                return False

        return True

    async def evaluate(self, context: ExecutionContext) -> ExecutionSignal:
        """Evaluate if price has closed above threshold.

        Args:
            context: Execution context with market data

        Returns:
            Execution signal with decision
        """
        # Check if we have sufficient data
        if not self.check_sufficient_data(context):
            return ExecutionSignal.no_action("Insufficient historical data")

        # Check if already in position
        if context.has_position:
            return ExecutionSignal.no_action("Already in position")

        # Get parameters
        threshold = Decimal(str(self.get_parameter("threshold_price")))
        min_volume = self.get_parameter("min_volume", 0)
        confirmation_bars = self.get_parameter("confirmation_bars", 1)

        current_bar = context.current_bar

        # Check volume requirement
        if min_volume > 0 and current_bar.volume < min_volume:
            return ExecutionSignal.no_action(
                f"Volume {current_bar.volume:,} below minimum {min_volume:,}"
            )

        # Check if we need multiple confirmation bars
        if confirmation_bars > 1:
            # Check last N bars all closed above threshold
            recent_bars = context.historical_bars[-confirmation_bars:]
            if len(recent_bars) < confirmation_bars:
                return ExecutionSignal.no_action("Insufficient bars for confirmation")

            all_above = all(bar.close_price > threshold for bar in recent_bars)

            if not all_above:
                closes_above = sum(
                    1 for bar in recent_bars if bar.close_price > threshold
                )
                return ExecutionSignal.no_action(
                    f"Only {closes_above}/{confirmation_bars} bars closed above "
                    f"{self.format_price(threshold)}"
                )

        # Check if current bar closed above threshold
        if current_bar.close_price <= threshold:
            return ExecutionSignal.no_action(
                f"Close {self.format_price(current_bar.close_price)} "
                f"not above threshold {self.format_price(threshold)}"
            )

        # Calculate confidence based on various factors
        confidence = self._calculate_confidence(context, threshold)

        # Generate reasoning
        price_above_pct = (
            (current_bar.close_price - threshold) / threshold * Decimal("100")
        )
        reasoning = (
            f"Price closed at {self.format_price(current_bar.close_price)} "
            f"({price_above_pct:.2f}% above threshold {self.format_price(threshold)})"
        )

        # Add volume context to reasoning if available
        if len(context.historical_bars) >= 20:
            avg_volume = mean(bar.volume for bar in context.historical_bars[-20:])
            volume_ratio = current_bar.volume / avg_volume if avg_volume > 0 else 1.0
            reasoning += f" with {volume_ratio:.1f}x average volume"

        return ExecutionSignal(
            action=ExecutionAction.ENTER_LONG,
            confidence=confidence,
            reasoning=reasoning,
            metadata={
                "threshold": float(threshold),
                "close_price": float(current_bar.close_price),
                "volume": current_bar.volume,
                "price_above_pct": float(price_above_pct),
            },
        )

    def _calculate_confidence(
        self, context: ExecutionContext, threshold: Decimal
    ) -> float:
        """Calculate confidence score for the signal.

        Args:
            context: Execution context
            threshold: Threshold price

        Returns:
            Confidence score between 0 and 1
        """
        current_bar = context.current_bar
        base_confidence = 0.6  # Base confidence for threshold break

        # Factor 1: Distance above threshold (up to 0.1 boost)
        price_above_pct = float((current_bar.close_price - threshold) / threshold)
        distance_boost = min(0.1, price_above_pct * 10)  # Cap at 0.1

        # Factor 2: Volume compared to average (up to 0.2 boost)
        volume_boost = 0.0
        if len(context.historical_bars) >= 20:
            avg_volume = mean(bar.volume for bar in context.historical_bars[-20:])
            if avg_volume > 0:
                volume_ratio = current_bar.volume / avg_volume
                volume_boost = min(0.2, (volume_ratio - 1) * 0.1)

        # Factor 3: Momentum leading up to break (up to 0.1 boost)
        momentum_boost = 0.0
        if len(context.historical_bars) >= 5:
            recent_momentum = self.calculate_momentum(context.historical_bars[-5:])
            if recent_momentum > 0:
                momentum_boost = min(0.1, float(recent_momentum) / 100)

        # Calculate final confidence
        confidence = base_confidence + distance_boost + volume_boost + momentum_boost

        # Cap at 1.0
        return min(1.0, confidence)
