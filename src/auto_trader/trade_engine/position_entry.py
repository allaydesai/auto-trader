"""Position entry model for individual trade positions."""

from typing import Dict, List, Optional, Any
from datetime import datetime, UTC
from decimal import Decimal

from loguru import logger

from auto_trader.models.enums import OrderSide


class PositionEntry:
    """Represents a position entry with associated trade plan information."""

    def __init__(
        self,
        position_id: str,
        plan_id: str,
        symbol: str,
        order_id: str,
        quantity: int,
        entry_price: Decimal,
        side: OrderSide,
        timestamp: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Initialize position entry.

        Args:
            position_id: Unique position identifier
            plan_id: Associated trade plan ID
            symbol: Trading symbol
            order_id: Entry order ID
            quantity: Position quantity (signed: positive=long, negative=short)
            entry_price: Entry price
            side: Order side (BUY/SELL)
            timestamp: Position creation timestamp
            metadata: Additional position metadata
        """
        self.position_id = position_id
        self.plan_id = plan_id
        self.symbol = symbol
        self.order_id = order_id
        self.quantity = quantity
        self.entry_price = entry_price
        self.side = side
        self.timestamp = timestamp or datetime.now(UTC)
        self.metadata = metadata or {}

        # Derived properties
        self.is_long = side == OrderSide.BUY
        self.is_short = side == OrderSide.SELL
        self.dollar_value = abs(quantity) * entry_price

        # Exit tracking
        self.exit_order_ids: List[str] = []
        self.exit_fills: List[Dict[str, Any]] = []
        self.remaining_quantity = quantity
        self.is_closed = False
        self.close_timestamp: Optional[datetime] = None

        logger.debug(f"Created position entry {position_id} for plan {plan_id}")

    def add_exit_order(self, order_id: str) -> None:
        """Add exit order to position tracking.

        Args:
            order_id: Exit order ID
        """
        if order_id not in self.exit_order_ids:
            self.exit_order_ids.append(order_id)
            logger.debug(f"Added exit order {order_id} to position {self.position_id}")

    def record_exit_fill(
        self,
        order_id: str,
        quantity_filled: int,
        fill_price: Decimal,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """Record an exit fill against this position.

        Args:
            order_id: Exit order ID
            quantity_filled: Quantity filled (should be negative for position reduction)
            fill_price: Fill price
            timestamp: Fill timestamp
        """
        fill_record = {
            "order_id": order_id,
            "quantity": quantity_filled,
            "price": fill_price,
            "timestamp": timestamp or datetime.now(UTC),
        }

        self.exit_fills.append(fill_record)

        # Update remaining quantity
        if self.is_long:
            self.remaining_quantity += (
                quantity_filled  # quantity_filled should be negative
            )
        else:
            self.remaining_quantity += (
                quantity_filled  # quantity_filled should be positive for short cover
            )

        # Check if position is fully closed
        if abs(self.remaining_quantity) < 0.001:  # Account for floating point precision
            self.remaining_quantity = 0
            self.is_closed = True
            self.close_timestamp = timestamp or datetime.now(UTC)

            logger.info(
                f"Position {self.position_id} fully closed",
                fills=len(self.exit_fills),
                close_time=self.close_timestamp,
            )
        else:
            logger.debug(
                f"Partial fill for position {self.position_id}",
                remaining=self.remaining_quantity,
                fill_quantity=quantity_filled,
            )

    def calculate_unrealized_pnl(self, current_price: Decimal) -> Decimal:
        """Calculate unrealized P&L for open portion of position.

        Args:
            current_price: Current market price

        Returns:
            Unrealized P&L amount
        """
        if self.is_closed:
            return Decimal("0")

        if self.is_long:
            return (current_price - self.entry_price) * abs(self.remaining_quantity)
        else:
            return (self.entry_price - current_price) * abs(self.remaining_quantity)

    def calculate_realized_pnl(self) -> Decimal:
        """Calculate realized P&L from all exit fills.

        Returns:
            Realized P&L amount
        """
        if not self.exit_fills:
            return Decimal("0")

        total_pnl = Decimal("0")

        for fill in self.exit_fills:
            fill_quantity = abs(fill["quantity"])

            if self.is_long:
                pnl = (fill["price"] - self.entry_price) * fill_quantity
            else:
                pnl = (self.entry_price - fill["price"]) * fill_quantity

            total_pnl += pnl

        return total_pnl

    def to_dict(self) -> Dict[str, Any]:
        """Convert position to dictionary for serialization.

        Returns:
            Position data as dictionary
        """
        return {
            "position_id": self.position_id,
            "plan_id": self.plan_id,
            "symbol": self.symbol,
            "order_id": self.order_id,
            "quantity": int(self.quantity),
            "entry_price": str(self.entry_price),
            "side": self.side.value if hasattr(self.side, "value") else self.side,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "exit_order_ids": self.exit_order_ids,
            "exit_fills": [
                {
                    "order_id": fill["order_id"],
                    "quantity": int(fill["quantity"]),
                    "price": str(fill["price"]),
                    "timestamp": fill["timestamp"].isoformat(),
                }
                for fill in self.exit_fills
            ],
            "remaining_quantity": int(self.remaining_quantity),
            "is_closed": self.is_closed,
            "close_timestamp": self.close_timestamp.isoformat()
            if self.close_timestamp
            else None,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PositionEntry":
        """Create position entry from dictionary data.

        Args:
            data: Position data dictionary

        Returns:
            PositionEntry instance
        """
        # Create position entry
        position = cls(
            position_id=data["position_id"],
            plan_id=data["plan_id"],
            symbol=data["symbol"],
            order_id=data["order_id"],
            quantity=data["quantity"],
            entry_price=Decimal(data["entry_price"]),
            side=OrderSide(data["side"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            metadata=data.get("metadata", {}),
        )

        # Restore exit tracking data
        position.exit_order_ids = data.get("exit_order_ids", [])
        position.remaining_quantity = data.get("remaining_quantity", data["quantity"])
        position.is_closed = data.get("is_closed", False)

        if data.get("close_timestamp"):
            position.close_timestamp = datetime.fromisoformat(data["close_timestamp"])

        # Restore exit fills
        position.exit_fills = []
        for fill_data in data.get("exit_fills", []):
            position.exit_fills.append(
                {
                    "order_id": fill_data["order_id"],
                    "quantity": fill_data["quantity"],
                    "price": Decimal(fill_data["price"]),
                    "timestamp": datetime.fromisoformat(fill_data["timestamp"]),
                }
            )

        return position
