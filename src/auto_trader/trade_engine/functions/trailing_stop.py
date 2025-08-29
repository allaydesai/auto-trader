"""Trailing stop execution function."""

from decimal import Decimal
from typing import Any, Dict, Set, Optional, TYPE_CHECKING

from loguru import logger

from auto_trader.models.execution import ExecutionContext, ExecutionSignal
from auto_trader.models.enums import ExecutionAction
from auto_trader.trade_engine.execution_functions import (
    ExecutionFunctionBase,
    ValidationMixin,
)

if TYPE_CHECKING:
    from auto_trader.models.market_data import BarData
    from auto_trader.models.execution import PositionState


class TrailingStopFunction(ExecutionFunctionBase, ValidationMixin):
    """Execution function that implements a trailing stop-loss.

    This function dynamically adjusts the stop level as price moves favorably,
    locking in profits while allowing the position to run.
    """

    def __init__(self, config):
        """Initialize with tracking of highest/lowest prices."""
        super().__init__(config)
        self._highest_price: Optional[Decimal] = None
        self._lowest_price: Optional[Decimal] = None
        self._current_stop_level: Optional[Decimal] = None

    @property
    def required_parameters(self) -> Set[str]:
        """Get required parameter names."""
        return {"trail_percentage"}

    @property
    def description(self) -> str:
        """Get function description."""
        return "Dynamic stop-loss that trails price movement to lock in profits"

    def validate_parameters(self, params: Dict[str, Any]) -> bool:
        """Validate function parameters.

        Args:
            params: Parameters to validate

        Returns:
            True if valid
        """
        # Check required trail_percentage
        if not self.validate_percentage_parameter(params, "trail_percentage"):
            logger.error("Invalid or missing trail_percentage parameter")
            return False

        # Optional activation_price (price must reach this before trailing starts)
        if "activation_price" in params:
            if not self.validate_price_parameter(params, "activation_price"):
                logger.error("Invalid activation_price parameter")
                return False

        # Optional initial_stop (starting stop level)
        if "initial_stop" in params:
            if not self.validate_price_parameter(params, "initial_stop"):
                logger.error("Invalid initial_stop parameter")
                return False

        # Optional trail_on_profit_only (only trail when position is profitable)
        if "trail_on_profit_only" in params:
            if not isinstance(params["trail_on_profit_only"], bool):
                logger.error("trail_on_profit_only must be boolean")
                return False

        return True

    async def evaluate(self, context: ExecutionContext) -> ExecutionSignal:
        """Evaluate trailing stop conditions.

        Args:
            context: Execution context with market data

        Returns:
            Execution signal with decision
        """
        # Check if we have sufficient data
        if not self.check_sufficient_data(context):
            return ExecutionSignal.no_action("Insufficient historical data")

        # Must have an open position for trailing stop
        if not context.has_position:
            # Reset tracking variables
            self._reset_tracking()
            return ExecutionSignal.no_action("No position to trail")

        position = context.position_state
        current_bar = context.current_bar

        # Get parameters
        trail_pct = Decimal(str(self.get_parameter("trail_percentage"))) / Decimal(
            "100"
        )
        activation_price = self.get_parameter("activation_price")
        initial_stop = self.get_parameter("initial_stop")
        trail_on_profit_only = self.get_parameter("trail_on_profit_only", False)

        # Check if trailing is activated (if activation price is set)
        if activation_price:
            activation = Decimal(str(activation_price))
            if position.is_long and current_bar.high_price < activation:
                return ExecutionSignal.no_action(
                    f"Trailing not activated (need price > {self.format_price(activation)})"
                )
            elif position.is_short and current_bar.low_price > activation:
                return ExecutionSignal.no_action(
                    f"Trailing not activated (need price < {self.format_price(activation)})"
                )

        # Check if we should only trail on profit
        if trail_on_profit_only and position.unrealized_pnl <= 0:
            return ExecutionSignal.no_action(
                "Position not profitable, trailing disabled"
            )

        # Update highest/lowest prices
        self._update_extremes(current_bar, position)

        # Calculate trailing stop level
        new_stop_level = self._calculate_stop_level(position, trail_pct, initial_stop)

        # Check if stop has been hit
        stop_hit = False
        if position.is_long:
            stop_hit = current_bar.close_price <= new_stop_level
        else:  # Short position
            stop_hit = current_bar.close_price >= new_stop_level

        # Update current stop level
        self._current_stop_level = new_stop_level

        if not stop_hit:
            # Check if stop needs adjustment (for order modification)
            if self._should_modify_stop(position, new_stop_level):
                return ExecutionSignal(
                    action=ExecutionAction.MODIFY_STOP,
                    confidence=1.0,  # Always high confidence for stop modifications
                    reasoning=f"Adjusting trailing stop to {self.format_price(new_stop_level)}",
                    metadata={
                        "new_stop_level": float(new_stop_level),
                        "highest_price": float(self._highest_price)
                        if self._highest_price
                        else None,
                        "lowest_price": float(self._lowest_price)
                        if self._lowest_price
                        else None,
                        "trail_percentage": float(trail_pct * 100),
                    },
                )

            return ExecutionSignal.no_action(
                f"Trailing stop at {self.format_price(new_stop_level)}, "
                f"current price {self.format_price(current_bar.close_price)}"
            )

        # Stop has been hit - generate exit signal
        pnl_pct = position.unrealized_pnl_percent
        reasoning = self._generate_exit_reasoning(position, new_stop_level, pnl_pct)

        return ExecutionSignal(
            action=ExecutionAction.EXIT,
            confidence=1.0,  # Always high confidence when stop is hit
            reasoning=reasoning,
            metadata={
                "stop_level": float(new_stop_level),
                "exit_price": float(current_bar.close_price),
                "pnl_percent": float(pnl_pct),
                "highest_price": float(self._highest_price)
                if self._highest_price
                else None,
                "lowest_price": float(self._lowest_price)
                if self._lowest_price
                else None,
            },
        )

    def _update_extremes(self, bar: "BarData", position: "PositionState") -> None:
        """Update highest/lowest price tracking.

        Args:
            bar: Current bar data
            position: Current position state
        """
        if position.is_long:
            # Track highest price for long positions
            if self._highest_price is None:
                self._highest_price = bar.high_price
            else:
                self._highest_price = max(self._highest_price, bar.high_price)
        else:
            # Track lowest price for short positions
            if self._lowest_price is None:
                self._lowest_price = bar.low_price
            else:
                self._lowest_price = min(self._lowest_price, bar.low_price)

    def _calculate_stop_level(
        self, position: "PositionState", trail_pct: Decimal, initial_stop: Optional[Any]
    ) -> Decimal:
        """Calculate current trailing stop level.

        Args:
            position: Current position
            trail_pct: Trail percentage (as decimal, e.g., 0.02 for 2%)
            initial_stop: Optional initial stop level

        Returns:
            Current stop level
        """
        if position.is_long:
            if self._highest_price is None:
                # Use initial stop or calculate from entry
                if initial_stop:
                    return Decimal(str(initial_stop))
                return position.entry_price * (Decimal("1") - trail_pct)

            # Trail from highest price
            new_stop = self._highest_price * (Decimal("1") - trail_pct)

            # Never lower the stop (ratchet effect)
            if self._current_stop_level:
                new_stop = max(new_stop, self._current_stop_level)

            return new_stop

        else:  # Short position
            if self._lowest_price is None:
                # Use initial stop or calculate from entry
                if initial_stop:
                    return Decimal(str(initial_stop))
                return position.entry_price * (Decimal("1") + trail_pct)

            # Trail from lowest price
            new_stop = self._lowest_price * (Decimal("1") + trail_pct)

            # Never raise the stop for shorts (ratchet effect)
            if self._current_stop_level:
                new_stop = min(new_stop, self._current_stop_level)

            return new_stop

    def _should_modify_stop(self, position: "PositionState", new_stop: Decimal) -> bool:
        """Check if stop level should be modified.

        Args:
            position: Current position
            new_stop: New stop level

        Returns:
            True if stop should be modified
        """
        if not position.stop_loss:
            return True  # No stop set yet

        # Only modify if stop has moved favorably by at least 0.1%
        min_move = Decimal("0.001")

        if position.is_long:
            # For longs, only raise the stop
            return new_stop > position.stop_loss * (Decimal("1") + min_move)
        else:
            # For shorts, only lower the stop
            return new_stop < position.stop_loss * (Decimal("1") - min_move)

    def _generate_exit_reasoning(
        self, position: "PositionState", stop_level: Decimal, pnl_pct: Decimal
    ) -> str:
        """Generate exit reasoning message.

        Args:
            position: Position being exited
            stop_level: Stop level that was hit
            pnl_pct: P&L percentage

        Returns:
            Reasoning string
        """
        if pnl_pct > 0:
            return (
                f"Trailing stop hit at {self.format_price(stop_level)} "
                f"locking in {pnl_pct:.2f}% profit"
            )
        else:
            return (
                f"Trailing stop hit at {self.format_price(stop_level)} "
                f"limiting loss to {abs(pnl_pct):.2f}%"
            )

    def _reset_tracking(self) -> None:
        """Reset tracking variables when no position."""
        self._highest_price = None
        self._lowest_price = None
        self._current_stop_level = None
