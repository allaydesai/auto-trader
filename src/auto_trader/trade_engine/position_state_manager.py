"""Position state management for trade lifecycle tracking."""

from typing import Dict, Optional, List, Any
from datetime import datetime, UTC, timedelta
from decimal import Decimal
from pathlib import Path
import json

from loguru import logger
from pydantic import BaseModel, Field

from auto_trader.models.trade_plan import TradePlan, TradePlanStatus
from auto_trader.models.order import Order, OrderResult
from auto_trader.models.enums import OrderSide, OrderStatus


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
            self.remaining_quantity += quantity_filled  # quantity_filled should be negative
        else:
            self.remaining_quantity += quantity_filled  # quantity_filled should be positive for short cover
        
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
            "side": self.side.value,
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
            "close_timestamp": self.close_timestamp.isoformat() if self.close_timestamp else None,
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
            position.exit_fills.append({
                "order_id": fill_data["order_id"],
                "quantity": fill_data["quantity"],
                "price": Decimal(fill_data["price"]),
                "timestamp": datetime.fromisoformat(fill_data["timestamp"]),
            })
        
        return position


class PositionStateManager:
    """Manages position state and tracking throughout trade lifecycles.
    
    Links trade plans to actual positions, tracks position changes through
    order fills, and maintains position state persistence.
    """
    
    def __init__(
        self,
        state_file_path: Optional[Path] = None,
        backup_retention_count: int = 10,
        auto_save_interval_seconds: int = 60,
    ):
        """Initialize position state manager.
        
        Args:
            state_file_path: Path to state persistence file
            backup_retention_count: Number of backup files to retain
            auto_save_interval_seconds: Automatic save interval
        """
        self.state_file_path = state_file_path or Path("data/state/positions.json")
        self.backup_retention_count = backup_retention_count
        self.auto_save_interval_seconds = auto_save_interval_seconds
        
        # Position tracking
        self.positions: Dict[str, PositionEntry] = {}  # position_id -> PositionEntry
        self.plan_to_position: Dict[str, str] = {}     # plan_id -> position_id
        self.order_to_position: Dict[str, str] = {}    # order_id -> position_id
        self.symbol_positions: Dict[str, List[str]] = {}  # symbol -> [position_ids]
        
        # Position counters for generating unique IDs
        self.position_counter = 0
        
        # Load existing state
        self._load_state()
        
        logger.info(
            f"PositionStateManager initialized with {len(self.positions)} positions"
        )
    
    async def create_position_from_fill(
        self,
        trade_plan: TradePlan,
        order_result: OrderResult,
        fill_price: Optional[Decimal] = None,
        fill_quantity: Optional[int] = None,
    ) -> str:
        """Create new position from order fill.
        
        Args:
            trade_plan: Associated trade plan
            order_result: Order execution result
            fill_price: Actual fill price (uses average_fill_price if None)
            fill_quantity: Actual fill quantity (uses filled_quantity if None)
            
        Returns:
            Created position ID
        """
        # Generate unique position ID
        position_id = self._generate_position_id(trade_plan.symbol)
        
        # Determine fill details
        actual_fill_price = fill_price or order_result.average_fill_price
        actual_fill_quantity = fill_quantity or order_result.filled_quantity
        
        if not actual_fill_price or not actual_fill_quantity:
            raise ValueError(
                f"Cannot create position: missing fill price ({actual_fill_price}) "
                f"or quantity ({actual_fill_quantity})"
            )
        
        # Create position entry
        position = PositionEntry(
            position_id=position_id,
            plan_id=trade_plan.plan_id,
            symbol=trade_plan.symbol,
            order_id=order_result.order_id,
            quantity=actual_fill_quantity,
            entry_price=actual_fill_price,
            side=order_result.side,
            metadata={
                "risk_category": trade_plan.risk_category.value,
                "entry_function": trade_plan.entry_function.function_type,
                "plan_entry_level": str(trade_plan.entry_level),
                "plan_stop_loss": str(trade_plan.stop_loss),
                "plan_take_profit": str(trade_plan.take_profit),
            },
        )
        
        # Add to tracking
        self.positions[position_id] = position
        self.plan_to_position[trade_plan.plan_id] = position_id
        self.order_to_position[order_result.order_id] = position_id
        
        # Add to symbol tracking
        if trade_plan.symbol not in self.symbol_positions:
            self.symbol_positions[trade_plan.symbol] = []
        self.symbol_positions[trade_plan.symbol].append(position_id)
        
        # Save state
        await self._save_state()
        
        logger.info(
            f"Created position {position_id} for plan {trade_plan.plan_id}",
            symbol=trade_plan.symbol,
            quantity=actual_fill_quantity,
            price=float(actual_fill_price),
            side=order_result.side.value,
        )
        
        return position_id
    
    async def record_exit_fill(
        self,
        position_id: str,
        exit_order_id: str,
        fill_quantity: int,
        fill_price: Decimal,
        timestamp: Optional[datetime] = None,
    ) -> bool:
        """Record exit fill for a position.
        
        Args:
            position_id: Position ID
            exit_order_id: Exit order ID
            fill_quantity: Quantity filled (negative for position reduction)
            fill_price: Fill price
            timestamp: Fill timestamp
            
        Returns:
            True if position fully closed, False otherwise
        """
        position = self.positions.get(position_id)
        if not position:
            logger.error(f"Position {position_id} not found for exit fill")
            return False
        
        # Record the fill
        position.record_exit_fill(exit_order_id, fill_quantity, fill_price, timestamp)
        
        # Track exit order
        self.order_to_position[exit_order_id] = position_id
        
        # Save state
        await self._save_state()
        
        logger.info(
            f"Recorded exit fill for position {position_id}",
            order_id=exit_order_id,
            quantity=fill_quantity,
            price=float(fill_price),
            position_closed=position.is_closed,
        )
        
        return position.is_closed
    
    def get_position_by_id(self, position_id: str) -> Optional[PositionEntry]:
        """Get position by ID.
        
        Args:
            position_id: Position ID
            
        Returns:
            PositionEntry if found, None otherwise
        """
        return self.positions.get(position_id)
    
    def get_position_by_plan_id(self, plan_id: str) -> Optional[PositionEntry]:
        """Get position associated with trade plan.
        
        Args:
            plan_id: Trade plan ID
            
        Returns:
            PositionEntry if found, None otherwise
        """
        position_id = self.plan_to_position.get(plan_id)
        return self.positions.get(position_id) if position_id else None
    
    def get_position_by_order_id(self, order_id: str) -> Optional[PositionEntry]:
        """Get position associated with order.
        
        Args:
            order_id: Order ID (entry or exit)
            
        Returns:
            PositionEntry if found, None otherwise
        """
        position_id = self.order_to_position.get(order_id)
        return self.positions.get(position_id) if position_id else None
    
    def get_positions_by_symbol(self, symbol: str) -> List[PositionEntry]:
        """Get all positions for a symbol.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            List of PositionEntry objects
        """
        position_ids = self.symbol_positions.get(symbol, [])
        return [self.positions[pid] for pid in position_ids if pid in self.positions]
    
    def get_open_positions(self) -> List[PositionEntry]:
        """Get all open positions.
        
        Returns:
            List of open PositionEntry objects
        """
        return [pos for pos in self.positions.values() if not pos.is_closed]
    
    def get_closed_positions(self) -> List[PositionEntry]:
        """Get all closed positions.
        
        Returns:
            List of closed PositionEntry objects
        """
        return [pos for pos in self.positions.values() if pos.is_closed]
    
    async def close_position(
        self,
        position_id: str,
        close_reason: str = "manual_close",
        timestamp: Optional[datetime] = None,
    ) -> bool:
        """Manually close a position.
        
        Args:
            position_id: Position ID to close
            close_reason: Reason for closure
            timestamp: Close timestamp
            
        Returns:
            True if successfully closed
        """
        position = self.positions.get(position_id)
        if not position:
            logger.error(f"Position {position_id} not found for closure")
            return False
        
        if position.is_closed:
            logger.warning(f"Position {position_id} already closed")
            return True
        
        # Force close the position
        position.remaining_quantity = 0
        position.is_closed = True
        position.close_timestamp = timestamp or datetime.now(UTC)
        position.metadata["close_reason"] = close_reason
        
        # Save state
        await self._save_state()
        
        logger.info(f"Manually closed position {position_id}", reason=close_reason)
        return True
    
    def get_position_summary(self) -> Dict[str, Any]:
        """Get summary of all positions.
        
        Returns:
            Position summary statistics
        """
        open_positions = self.get_open_positions()
        closed_positions = self.get_closed_positions()
        
        # Calculate P&L for closed positions
        total_realized_pnl = sum(pos.calculate_realized_pnl() for pos in closed_positions)
        
        # Group by symbol
        symbol_summary = {}
        for symbol in self.symbol_positions:
            positions = self.get_positions_by_symbol(symbol)
            open_count = sum(1 for pos in positions if not pos.is_closed)
            closed_count = sum(1 for pos in positions if pos.is_closed)
            
            symbol_summary[symbol] = {
                "total_positions": len(positions),
                "open_positions": open_count,
                "closed_positions": closed_count,
            }
        
        return {
            "total_positions": len(self.positions),
            "open_positions": len(open_positions),
            "closed_positions": len(closed_positions),
            "total_realized_pnl": float(total_realized_pnl),
            "symbols_traded": len(self.symbol_positions),
            "symbol_breakdown": symbol_summary,
        }
    
    def _generate_position_id(self, symbol: str) -> str:
        """Generate unique position ID.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Unique position ID
        """
        self.position_counter += 1
        timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        return f"POS_{symbol}_{timestamp}_{self.position_counter:04d}"
    
    async def _save_state(self) -> None:
        """Save position state to file."""
        try:
            # Ensure directory exists
            self.state_file_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Create backup if file exists
            if self.state_file_path.exists():
                backup_path = Path(
                    str(self.state_file_path) + f".bak.{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}"
                )
                self.state_file_path.rename(backup_path)
                
                # Clean up old backups
                self._cleanup_old_backups()
            
            # Prepare state data
            state_data = {
                "positions": {
                    pid: pos.to_dict() for pid, pos in self.positions.items()
                },
                "plan_to_position": self.plan_to_position,
                "order_to_position": self.order_to_position,
                "symbol_positions": self.symbol_positions,
                "position_counter": self.position_counter,
                "last_saved": datetime.now(UTC).isoformat(),
            }
            
            # Write state file atomically
            temp_file = Path(str(self.state_file_path) + ".tmp")
            with temp_file.open("w") as f:
                json.dump(state_data, f, indent=2, default=str)
            
            temp_file.rename(self.state_file_path)
            
            logger.debug(f"Position state saved to {self.state_file_path}")
            
        except Exception as e:
            logger.error(f"Failed to save position state: {e}")
            raise
    
    def _load_state(self) -> None:
        """Load position state from file."""
        if not self.state_file_path.exists():
            logger.info("No existing position state file found")
            return
        
        try:
            with self.state_file_path.open("r") as f:
                state_data = json.load(f)
            
            # Load positions
            self.positions = {}
            for pid, pos_data in state_data.get("positions", {}).items():
                self.positions[pid] = PositionEntry.from_dict(pos_data)
            
            # Load mappings
            self.plan_to_position = state_data.get("plan_to_position", {})
            self.order_to_position = state_data.get("order_to_position", {})
            self.symbol_positions = state_data.get("symbol_positions", {})
            self.position_counter = state_data.get("position_counter", 0)
            
            logger.info(
                f"Loaded {len(self.positions)} positions from state file",
                last_saved=state_data.get("last_saved"),
            )
            
        except Exception as e:
            logger.error(f"Failed to load position state: {e}")
            # Don't raise - start with empty state instead
    
    def _cleanup_old_backups(self) -> None:
        """Clean up old backup files."""
        try:
            backup_files = list(self.state_file_path.parent.glob(f"{self.state_file_path.name}.bak.*"))
            backup_files.sort(key=lambda x: x.stat().st_mtime, reverse=True)
            
            # Remove excess backups
            for backup_file in backup_files[self.backup_retention_count:]:
                backup_file.unlink()
                logger.debug(f"Removed old backup: {backup_file}")
                
        except Exception as e:
            logger.warning(f"Error cleaning up backups: {e}")
    
    async def cleanup_closed_positions(self, days_to_keep: int = 30) -> int:
        """Clean up old closed positions.
        
        Args:
            days_to_keep: Number of days to keep closed positions
            
        Returns:
            Number of positions cleaned up
        """
        cutoff_time = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        cutoff_time = cutoff_time - timedelta(days=days_to_keep)
        
        positions_to_remove = []
        
        for position_id, position in self.positions.items():
            if position.is_closed and position.close_timestamp:
                if position.close_timestamp < cutoff_time:
                    positions_to_remove.append(position_id)
        
        # Remove old positions
        removed_count = 0
        for position_id in positions_to_remove:
            position = self.positions[position_id]
            
            # Remove from all mappings
            if position.plan_id in self.plan_to_position:
                del self.plan_to_position[position.plan_id]
            
            # Remove from order mappings
            orders_to_remove = [position.order_id] + position.exit_order_ids
            for order_id in orders_to_remove:
                if order_id in self.order_to_position:
                    del self.order_to_position[order_id]
            
            # Remove from symbol positions
            if position.symbol in self.symbol_positions:
                if position_id in self.symbol_positions[position.symbol]:
                    self.symbol_positions[position.symbol].remove(position_id)
                if not self.symbol_positions[position.symbol]:
                    del self.symbol_positions[position.symbol]
            
            # Remove position itself
            del self.positions[position_id]
            removed_count += 1
        
        if removed_count > 0:
            await self._save_state()
            logger.info(f"Cleaned up {removed_count} old closed positions")
        
        return removed_count