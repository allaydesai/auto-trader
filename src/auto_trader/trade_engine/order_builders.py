"""Order builders for exit processing and trade execution."""

from typing import Dict, Any
from decimal import Decimal
from datetime import datetime, UTC

from loguru import logger

from auto_trader.models.trade_plan import TradePlan
from auto_trader.models.execution import ExecutionSignal
from auto_trader.models.enums import OrderSide
from auto_trader.trade_engine.position_entry import PositionEntry


class ExitProcessingResult:
    """Result of exit signal processing operation."""

    def __init__(
        self,
        success: bool,
        action_taken: str,
        position_closed: bool = False,
        order_result=None,
        orders_cancelled=None,
        error_message=None,
        position_id=None,
        plan_id=None,
    ):
        """Initialize exit processing result.

        Args:
            success: Whether processing was successful
            action_taken: Description of action taken
            position_closed: Whether position was fully closed
            order_result: Exit order result if applicable
            orders_cancelled: List of cancelled order IDs
            error_message: Error message if processing failed
            position_id: Associated position ID
            plan_id: Associated trade plan ID
        """
        self.success = success
        self.action_taken = action_taken
        self.position_closed = position_closed
        self.order_result = order_result
        self.orders_cancelled = orders_cancelled or []
        self.error_message = error_message
        self.position_id = position_id
        self.plan_id = plan_id
        self.timestamp = datetime.now(UTC)

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for logging/serialization.

        Returns:
            Result data as dictionary
        """
        return {
            "success": self.success,
            "action_taken": self.action_taken,
            "position_closed": self.position_closed,
            "order_result": self.order_result.to_dict()
            if hasattr(self.order_result, "to_dict")
            else None,
            "orders_cancelled": self.orders_cancelled,
            "error_message": self.error_message,
            "position_id": self.position_id,
            "plan_id": self.plan_id,
            "timestamp": self.timestamp.isoformat(),
        }


class ExitOrderBuilder:
    """Builds exit orders for different exit scenarios."""

    @staticmethod
    def create_exit_order_request(
        signal: ExecutionSignal,
        trade_plan: TradePlan,
        position: PositionEntry,
        metadata: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Create exit order request from signal and position.

        Args:
            signal: Exit signal
            trade_plan: Trade plan
            position: Position to exit
            metadata: Additional order metadata

        Returns:
            Order request for exit
        """
        # Determine exit side (opposite of entry)
        exit_side = OrderSide.SELL if position.is_long else OrderSide.BUY

        # Use remaining quantity for exit
        exit_quantity = abs(position.remaining_quantity)

        # Build metadata
        order_metadata = {
            "exit_reason": signal.reasoning,
            "function_name": metadata.get("function_name", "unknown")
            if metadata
            else "unknown",
            "position_id": position.position_id,
            "signal_confidence": signal.confidence,
            "exit_type": "market_exit",
        }

        if metadata:
            order_metadata.update(metadata)

        # Create order request
        order_request = {
            "symbol": trade_plan.symbol,
            "side": exit_side,
            "quantity": exit_quantity,
            "order_type": "MKT",
            "trade_plan_id": trade_plan.plan_id,
            "metadata": order_metadata,
        }

        logger.debug(f"Created exit order request for position {position.position_id}")

        return order_request

    @staticmethod
    def create_stop_order_request(
        trade_plan: TradePlan,
        position: PositionEntry,
        stop_price: Decimal,
        metadata: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Create stop order request for trailing stop or adjusted stop.

        Args:
            trade_plan: Trade plan
            position: Position
            stop_price: New stop price
            metadata: Additional order metadata

        Returns:
            Stop order request
        """
        # Determine stop side (opposite of entry)
        stop_side = OrderSide.SELL if position.is_long else OrderSide.BUY

        # Build metadata
        order_metadata = {
            "order_purpose": "stop_loss",
            "position_id": position.position_id,
            "original_stop": str(trade_plan.stop_loss),
            "new_stop": str(stop_price),
            "stop_type": "trailing_stop",
        }

        if metadata:
            order_metadata.update(metadata)

        # Create stop order request
        order_request = {
            "symbol": trade_plan.symbol,
            "side": stop_side,
            "quantity": abs(position.remaining_quantity),
            "order_type": "STP",
            "stop_price": stop_price,
            "trade_plan_id": trade_plan.plan_id,
            "metadata": order_metadata,
        }

        logger.debug(
            f"Created stop order request for position {position.position_id}",
            original_stop=float(trade_plan.stop_loss),
            new_stop=float(stop_price),
        )

        return order_request

    @staticmethod
    def create_bracket_exit_orders(
        trade_plan: TradePlan,
        position: PositionEntry,
        stop_price: Decimal = None,
        target_price: Decimal = None,
        metadata: Dict[str, Any] = None,
    ) -> Dict[str, Dict[str, Any]]:
        """Create bracket exit orders (stop loss and take profit).

        Args:
            trade_plan: Trade plan
            position: Position
            stop_price: Stop loss price (uses plan default if None)
            target_price: Take profit price (uses plan default if None)
            metadata: Additional order metadata

        Returns:
            Dictionary with 'stop_order' and 'target_order' requests
        """
        # Use plan defaults if not provided
        stop_price = stop_price or trade_plan.stop_loss
        target_price = target_price or trade_plan.take_profit

        # Determine order sides
        if position.is_long:
            stop_side = OrderSide.SELL
            target_side = OrderSide.SELL
        else:
            stop_side = OrderSide.BUY
            target_side = OrderSide.BUY

        # Common metadata
        base_metadata = {
            "position_id": position.position_id,
            "bracket_order": True,
        }

        if metadata:
            base_metadata.update(metadata)

        # Create stop loss order
        stop_metadata = base_metadata.copy()
        stop_metadata.update(
            {
                "order_purpose": "stop_loss",
                "stop_price": str(stop_price),
            }
        )

        stop_order = {
            "symbol": trade_plan.symbol,
            "side": stop_side,
            "quantity": abs(position.remaining_quantity),
            "order_type": "STP",
            "stop_price": stop_price,
            "trade_plan_id": trade_plan.plan_id,
            "metadata": stop_metadata,
        }

        # Create take profit order
        target_metadata = base_metadata.copy()
        target_metadata.update(
            {
                "order_purpose": "take_profit",
                "limit_price": str(target_price),
            }
        )

        target_order = {
            "symbol": trade_plan.symbol,
            "side": target_side,
            "quantity": abs(position.remaining_quantity),
            "order_type": "LMT",
            "limit_price": target_price,
            "trade_plan_id": trade_plan.plan_id,
            "metadata": target_metadata,
        }

        logger.debug(
            f"Created bracket exit orders for position {position.position_id}",
            stop_price=float(stop_price),
            target_price=float(target_price),
        )

        return {
            "stop_order": stop_order,
            "target_order": target_order,
        }

    @staticmethod
    def validate_exit_order_request(
        order_request: Dict[str, Any],
        position: PositionEntry,
    ) -> bool:
        """Validate exit order request against position.

        Args:
            order_request: Order request to validate
            position: Position being exited

        Returns:
            True if request is valid
        """
        try:
            # Check required fields
            required_fields = ["symbol", "side", "quantity", "order_type"]
            for field in required_fields:
                if field not in order_request:
                    logger.error(f"Missing required field in exit order: {field}")
                    return False

            # Check symbol matches position
            if order_request["symbol"] != position.symbol:
                logger.error("Order symbol does not match position symbol")
                return False

            # Check quantity doesn't exceed position
            order_quantity = order_request["quantity"]
            if order_quantity > abs(position.remaining_quantity):
                logger.error(
                    f"Exit quantity {order_quantity} exceeds position {position.remaining_quantity}"
                )
                return False

            # Check side is opposite of position
            order_side = order_request["side"]
            expected_side = OrderSide.SELL if position.is_long else OrderSide.BUY

            if order_side != expected_side:
                logger.error(f"Exit side {order_side} incorrect for position side")
                return False

            logger.debug(
                f"Exit order request validation passed for position {position.position_id}"
            )
            return True

        except Exception as e:
            logger.error(f"Error validating exit order request: {e}")
            return False
