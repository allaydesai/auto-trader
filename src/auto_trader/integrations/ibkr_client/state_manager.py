"""Order state persistence and recovery management."""

import asyncio
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger
from pydantic import BaseModel, ConfigDict

from auto_trader.models.order import Order, OrderStatus


class OrderStateSnapshot(BaseModel):
    """Snapshot of order state for persistence."""
    
    timestamp: datetime
    active_orders: Dict[str, dict]  # order_id -> serialized Order
    metadata: Dict[str, str] = {}


class OrderStateManager:
    """
    Manages persistent storage and recovery of order state.
    
    Features:
    - JSON-based storage with atomic writes
    - Automatic backups with rotation
    - Recovery mechanism for system restarts
    - Integration with OrderExecutionManager
    """
    
    def __init__(
        self,
        state_dir: Path,
        max_backups: int = 10,
        backup_interval: int = 300,  # 5 minutes
    ):
        """
        Initialize order state manager.
        
        Args:
            state_dir: Directory for state files
            max_backups: Maximum number of backup files to retain
            backup_interval: Backup interval in seconds
        """
        self.state_dir = Path(state_dir)
        self.max_backups = max_backups
        self.backup_interval = backup_interval
        
        # File paths
        self.state_file = self.state_dir / "order_state.json"
        self.backup_dir = self.state_dir / "backups"
        self.temp_file = self.state_dir / "order_state.tmp"
        
        # Create directories
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        
        # State tracking
        self._last_backup = datetime.now(timezone.utc)
        self._backup_task: Optional[asyncio.Task] = None
        
        logger.info(
            "OrderStateManager initialized",
            state_file=str(self.state_file),
            max_backups=max_backups,
            backup_interval=backup_interval,
        )
    
    async def save_state(self, active_orders: Dict[str, Order]) -> None:
        """
        Save current order state to persistent storage.
        
        Args:
            active_orders: Dictionary of active orders by order_id
        """
        try:
            # Create snapshot
            serialized_orders = {}
            for order_id, order in active_orders.items():
                try:
                    serialized_orders[order_id] = order.model_dump()
                except Exception as e:
                    logger.error(
                        "Failed to serialize order",
                        order_id=order_id,
                        error=str(e),
                    )
                    continue
            
            snapshot = OrderStateSnapshot(
                timestamp=datetime.now(timezone.utc),
                active_orders=serialized_orders,
                metadata={
                    "total_orders": str(len(active_orders)),
                    "save_reason": "periodic_save",
                },
            )
            
            # Atomic write (write to temp file, then rename)
            with open(self.temp_file, 'w') as f:
                json.dump(snapshot.model_dump(), f, indent=2, default=str)
            
            # Atomic rename
            shutil.move(str(self.temp_file), str(self.state_file))
            
            logger.debug(
                "Order state saved",
                active_orders=len(active_orders),
                file=str(self.state_file),
            )
            
            # Check if backup is needed
            await self._maybe_create_backup()
            
        except Exception as e:
            logger.error("Failed to save order state", error=str(e))
            # Clean up temp file if it exists
            if self.temp_file.exists():
                self.temp_file.unlink()
    
    async def load_state(self) -> Dict[str, Order]:
        """
        Load order state from persistent storage.
        
        Returns:
            Dictionary of active orders by order_id
            
        Raises:
            FileNotFoundError: If state file doesn't exist
            ValueError: If state file is corrupted
        """
        try:
            if not self.state_file.exists():
                logger.info("No existing state file found")
                return {}
            
            with open(self.state_file, 'r') as f:
                data = json.load(f)
            
            snapshot = OrderStateSnapshot(**data)
            
            # Deserialize orders
            active_orders = {}
            for order_id, order_data in snapshot.active_orders.items():
                try:
                    order = Order(**order_data)
                    active_orders[order_id] = order
                except Exception as e:
                    logger.error(
                        "Failed to deserialize order",
                        order_id=order_id,
                        error=str(e),
                    )
                    continue
            
            logger.info(
                "Order state loaded",
                total_orders=len(active_orders),
                snapshot_age=(datetime.now(timezone.utc) - snapshot.timestamp).total_seconds(),
            )
            
            return active_orders
            
        except Exception as e:
            logger.error("Failed to load order state", error=str(e))
            
            # Try to load from most recent backup
            return await self._load_from_backup()
    
    async def clear_state(self) -> None:
        """Clear all persisted state (for testing/reset)."""
        try:
            if self.state_file.exists():
                self.state_file.unlink()
                logger.info("Order state file cleared")
        except Exception as e:
            logger.error("Failed to clear state file", error=str(e))
    
    async def create_backup(self, reason: str = "manual") -> str:
        """
        Create a backup of the current state.
        
        Args:
            reason: Reason for creating backup
            
        Returns:
            Path to created backup file
        """
        if not self.state_file.exists():
            logger.warning("No state file to backup")
            return ""
        
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        backup_file = self.backup_dir / f"order_state_{timestamp}_{reason}.json"
        
        try:
            shutil.copy2(str(self.state_file), str(backup_file))
            
            logger.info(
                "State backup created",
                backup_file=str(backup_file),
                reason=reason,
            )
            
            # Clean up old backups
            await self._cleanup_old_backups()
            
            return str(backup_file)
            
        except Exception as e:
            logger.error("Failed to create backup", error=str(e))
            return ""
    
    async def start_periodic_backup(self) -> None:
        """Start periodic backup task."""
        if self._backup_task and not self._backup_task.done():
            logger.warning("Periodic backup already running")
            return
        
        self._backup_task = asyncio.create_task(self._periodic_backup_loop())
        logger.info("Periodic backup started", interval=self.backup_interval)
    
    async def stop_periodic_backup(self) -> None:
        """Stop periodic backup task."""
        if self._backup_task and not self._backup_task.done():
            self._backup_task.cancel()
            try:
                await self._backup_task
            except asyncio.CancelledError:
                pass
            logger.info("Periodic backup stopped")
    
    async def _maybe_create_backup(self) -> None:
        """Create backup if enough time has passed."""
        now = datetime.now(timezone.utc)
        time_since_backup = (now - self._last_backup).total_seconds()
        
        if time_since_backup >= self.backup_interval:
            await self.create_backup("periodic")
            self._last_backup = now
    
    async def _load_from_backup(self) -> Dict[str, Order]:
        """Try to load state from most recent backup."""
        try:
            backup_files = list(self.backup_dir.glob("order_state_*.json"))
            if not backup_files:
                logger.warning("No backup files found")
                return {}
            
            # Sort by modification time (most recent first)
            backup_files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
            
            most_recent = backup_files[0]
            logger.info("Loading from backup", backup_file=str(most_recent))
            
            with open(most_recent, 'r') as f:
                data = json.load(f)
            
            snapshot = OrderStateSnapshot(**data)
            
            # Deserialize orders
            active_orders = {}
            for order_id, order_data in snapshot.active_orders.items():
                try:
                    order = Order(**order_data)
                    active_orders[order_id] = order
                except Exception as e:
                    logger.error(
                        "Failed to deserialize order from backup",
                        order_id=order_id,
                        error=str(e),
                    )
                    continue
            
            logger.info(
                "State loaded from backup",
                backup_file=str(most_recent),
                total_orders=len(active_orders),
            )
            
            return active_orders
            
        except Exception as e:
            logger.error("Failed to load from backup", error=str(e))
            return {}
    
    async def _periodic_backup_loop(self) -> None:
        """Periodic backup loop."""
        try:
            while True:
                await asyncio.sleep(self.backup_interval)
                if self.state_file.exists():
                    await self.create_backup("periodic")
                    self._last_backup = datetime.now(timezone.utc)
        except asyncio.CancelledError:
            logger.debug("Periodic backup loop cancelled")
        except Exception as e:
            logger.error("Periodic backup loop error", error=str(e))
    
    async def _cleanup_old_backups(self) -> None:
        """Clean up old backup files beyond max_backups limit."""
        try:
            backup_files = list(self.backup_dir.glob("order_state_*.json"))
            if len(backup_files) <= self.max_backups:
                return
            
            # Sort by modification time (oldest first)
            backup_files.sort(key=lambda f: f.stat().st_mtime)
            
            # Remove oldest files beyond limit
            files_to_remove = backup_files[:len(backup_files) - self.max_backups]
            for file_to_remove in files_to_remove:
                file_to_remove.unlink()
                logger.debug("Removed old backup", file=str(file_to_remove))
            
            logger.info(
                "Cleaned up old backups",
                removed=len(files_to_remove),
                remaining=len(backup_files) - len(files_to_remove),
            )
            
        except Exception as e:
            logger.error("Failed to cleanup old backups", error=str(e))