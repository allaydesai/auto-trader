"""Close below threshold execution function."""

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


class CloseBelowFunction(ExecutionFunctionBase, ValidationMixin):
    """Execution function that triggers when price closes below a threshold.

    This function monitors for price closes below a specified threshold level,
    commonly used for breakdown entries, stop-loss triggers, or support breaks.
    """
    
    # Constants for confidence calculation
    _EXIT_BASE_CONFIDENCE = 0.9
    _ENTRY_BASE_CONFIDENCE = 0.6
    _MAX_DISTANCE_BOOST = 0.1
    _MAX_VOLUME_BOOST = 0.15
    _MAX_MOMENTUM_PENALTY = 0.1
    _VOLUME_LOOKBACK_BARS = 20
    _MOMENTUM_LOOKBACK_BARS = 5

    @property
    def required_parameters(self) -> Set[str]:
        """Get required parameter names."""
        return {"threshold_price"}

    @property
    def description(self) -> str:
        """Get function description."""
        return "Triggers action when price closes below threshold level"

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

        # Optional confirmation_bars parameter
        if "confirmation_bars" in params:
            if not self.validate_integer_parameter(
                params, "confirmation_bars", min_value=1, max_value=10
            ):
                logger.error("Invalid confirmation_bars parameter")
                return False

        # Optional action parameter (EXIT for stop-loss, ENTER_SHORT for short entry)
        if "action" in params:
            valid_actions = ["EXIT", "ENTER_SHORT"]
            if params["action"] not in valid_actions:
                logger.error(
                    f"Invalid action parameter. Must be one of {valid_actions}"
                )
                return False

        # Optional max_distance_percent - prevent triggering on prices too far from threshold
        if "max_distance_percent" in params:
            if not self.validate_percentage_parameter(params, "max_distance_percent"):
                logger.error("Invalid max_distance_percent parameter")
                return False

        # Optional min_distance_percent - prevent triggering on marginal breaks
        if "min_distance_percent" in params:
            if not self.validate_percentage_parameter(params, "min_distance_percent"):
                logger.error("Invalid min_distance_percent parameter")
                return False
            
            # Ensure min_distance is less than max_distance if both are set
            if "max_distance_percent" in params:
                min_dist = float(params["min_distance_percent"])
                max_dist = float(params["max_distance_percent"])
                if min_dist >= max_dist:
                    logger.error("min_distance_percent must be less than max_distance_percent")
                    return False

        return True

    async def evaluate(self, context: ExecutionContext) -> ExecutionSignal:
        """Evaluate if price has closed below threshold.

        Args:
            context: Execution context with market data

        Returns:
            Execution signal with decision
        """
        # Check if we have sufficient data
        if not self.check_sufficient_data(context):
            return ExecutionSignal.no_action("Insufficient historical data")

        # Check if this is a valid candle close for our timeframe
        if not self.is_candle_close_for_timeframe(context):
            return ExecutionSignal.no_action("Not a valid candle close for timeframe")

        # Check for edge cases first
        should_skip, confidence_adjustment = self.check_edge_cases(context)
        if should_skip:
            return ExecutionSignal.no_action("Skipping evaluation due to edge case")

        # Get parameters
        threshold = Decimal(str(self.get_parameter("threshold_price")))
        min_volume = self.get_parameter("min_volume", 0)
        confirmation_bars = self.get_parameter("confirmation_bars", 1)
        action_type = self.get_parameter("action", "EXIT")  # Default to stop-loss behavior
        min_distance_pct = self.get_parameter("min_distance_percent", 0)
        max_distance_pct = self.get_parameter("max_distance_percent", 100)

        # Determine action based on position state
        if action_type == "EXIT" and not context.has_position:
            return ExecutionSignal.no_action("No position to exit")
        elif action_type == "ENTER_SHORT" and context.has_position:
            return ExecutionSignal.no_action("Already in position")

        current_bar = context.current_bar

        # Check volume requirement
        if min_volume > 0 and current_bar.volume < min_volume:
            return ExecutionSignal.no_action(
                f"Volume {current_bar.volume:,} below minimum {min_volume:,}"
            )

        # Check if we need multiple confirmation bars
        if confirmation_bars > 1:
            # Check last N bars all closed below threshold
            recent_bars = context.historical_bars[-confirmation_bars:]
            if len(recent_bars) < confirmation_bars:
                return ExecutionSignal.no_action("Insufficient bars for confirmation")

            all_below = all(bar.close_price < threshold for bar in recent_bars)

            if not all_below:
                closes_below = sum(
                    1 for bar in recent_bars if bar.close_price < threshold
                )
                return ExecutionSignal.no_action(
                    f"Only {closes_below}/{confirmation_bars} bars closed below "
                    f"{self.format_price(threshold)}"
                )

        # Check if current bar closed below threshold
        if current_bar.close_price >= threshold:
            return ExecutionSignal.no_action(
                f"Close {self.format_price(current_bar.close_price)} "
                f"not below threshold {self.format_price(threshold)}"
            )

        # Check distance constraints
        price_below_pct = float((threshold - current_bar.close_price) / threshold * Decimal("100"))
        
        if price_below_pct < min_distance_pct:
            return ExecutionSignal.no_action(
                f"Price only {price_below_pct:.2f}% below threshold, "
                f"minimum required: {min_distance_pct}%"
            )
        
        if price_below_pct > max_distance_pct:
            return ExecutionSignal.no_action(
                f"Price {price_below_pct:.2f}% below threshold exceeds "
                f"maximum allowed: {max_distance_pct}%"
            )

        # Calculate confidence based on various factors
        base_confidence = self._calculate_confidence(context, threshold, action_type)
        
        # Apply edge case adjustments
        confidence = base_confidence * confidence_adjustment

        # Generate reasoning
        price_below_pct = (
            (threshold - current_bar.close_price) / threshold * Decimal("100")
        )

        if action_type == "EXIT":
            reasoning = (
                f"Stop-loss triggered: Price closed at "
                f"{self.format_price(current_bar.close_price)} "
                f"({price_below_pct:.2f}% below stop level "
                f"{self.format_price(threshold)})"
            )
        else:  # ENTER_SHORT
            reasoning = (
                f"Price broke down at {self.format_price(current_bar.close_price)} "
                f"({price_below_pct:.2f}% below support {self.format_price(threshold)})"
            )

        # Add volume context to reasoning if available
        if len(context.historical_bars) >= self._VOLUME_LOOKBACK_BARS:
            avg_volume = mean(bar.volume for bar in context.historical_bars[-self._VOLUME_LOOKBACK_BARS:])
            volume_ratio = current_bar.volume / avg_volume if avg_volume > 0 else 1.0
            reasoning += f" with {volume_ratio:.1f}x average volume"

        # Determine execution action
        exec_action = (
            ExecutionAction.EXIT
            if action_type == "EXIT"
            else ExecutionAction.ENTER_SHORT
        )

        return ExecutionSignal(
            action=exec_action,
            confidence=confidence,
            reasoning=reasoning,
            metadata={
                "threshold": float(threshold),
                "close_price": float(current_bar.close_price),
                "volume": current_bar.volume,
                "price_below_pct": float(price_below_pct),
                "action_type": action_type,
            },
        )

    def _calculate_confidence(
        self, context: ExecutionContext, threshold: Decimal, action_type: str
    ) -> float:
        """Calculate confidence score for the signal.

        Args:
            context: Execution context
            threshold: Threshold price
            action_type: EXIT or ENTER_SHORT

        Returns:
            Confidence score between 0 and 1
        """
        current_bar = context.current_bar

        # Higher base confidence for stop-loss exits (protect capital)
        base_confidence = self._EXIT_BASE_CONFIDENCE if action_type == "EXIT" else self._ENTRY_BASE_CONFIDENCE

        # Factor 1: Distance below threshold (boost for entries only)
        distance_boost = 0.0
        if action_type == "ENTER_SHORT":
            price_below_pct = float((threshold - current_bar.close_price) / threshold)
            distance_boost = min(self._MAX_DISTANCE_BOOST, price_below_pct * 10)

        # Factor 2: Volume compared to average
        volume_boost = 0.0
        if len(context.historical_bars) >= self._VOLUME_LOOKBACK_BARS:
            avg_volume = mean(bar.volume for bar in context.historical_bars[-self._VOLUME_LOOKBACK_BARS:])
            if avg_volume > 0:
                volume_ratio = current_bar.volume / avg_volume
                # High volume on breakdown is significant
                volume_boost = min(self._MAX_VOLUME_BOOST, (volume_ratio - 1) * 0.1)

        # Factor 3: Negative momentum penalty for false breaks
        momentum_penalty = 0.0
        if action_type == "ENTER_SHORT" and len(context.historical_bars) >= self._MOMENTUM_LOOKBACK_BARS:
            recent_momentum = self.calculate_momentum(context.historical_bars[-self._MOMENTUM_LOOKBACK_BARS:])
            # If momentum is positive despite break below, reduce confidence
            if recent_momentum > 0:
                momentum_penalty = min(self._MAX_MOMENTUM_PENALTY, float(recent_momentum) / 100)

        # Calculate final confidence
        confidence = base_confidence + distance_boost + volume_boost - momentum_penalty

        # Ensure confidence stays within bounds
        return max(0.0, min(1.0, confidence))
