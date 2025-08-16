"""Portfolio risk tracking with state persistence."""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, Optional, Tuple

from ..logging_config import get_logger
from .backup_manager import BackupManager
from .risk_models import (
    PortfolioRiskState,
    PositionRiskEntry,
    PortfolioRiskExceededError,
)

logger = get_logger("portfolio_tracker", "risk")


class PortfolioTracker:
    """Track and persist portfolio risk across positions."""
    
    MAX_PORTFOLIO_RISK = Decimal("10.0")  # 10% limit (AC 7, 19)
    
    def __init__(
        self, 
        state_file: Optional[Path] = None,
        account_value: Optional[Decimal] = None,
    ) -> None:
        """
        Initialize portfolio tracker.
        
        Args:
            state_file: Path to JSON state file for persistence
            account_value: Total account value for risk calculations
        """
        self.state_file = state_file or Path("data/state/position_registry.json")
        self._positions: Dict[str, PositionRiskEntry] = {}
        self._account_value = account_value or Decimal("0")
        self._backup_manager = BackupManager(self.state_file)
        
        # Load existing state if file exists
        self._load_state()
        
        logger.debug(
            "PortfolioTracker initialized",
            state_file=str(self.state_file),
            account_value=float(self._account_value),
            existing_positions=len(self._positions),
        )
    
    def set_account_value(self, account_value: Decimal) -> None:
        """Set the account value for risk calculations."""
        self._account_value = account_value
        logger.info("Account value updated", account_value=float(account_value))
    
    def add_position(
        self, 
        position_id: str, 
        symbol: str, 
        risk_amount: Decimal, 
        plan_id: str,
    ) -> None:
        """
        Add position to risk registry (AC 14).
        
        Args:
            position_id: Unique position identifier
            symbol: Trading symbol
            risk_amount: Risk amount in dollars
            plan_id: Trade plan identifier
        """
        entry = PositionRiskEntry(
            position_id=position_id,
            symbol=symbol,
            risk_amount=risk_amount,
            plan_id=plan_id,
        )
        
        self._positions[position_id] = entry
        self._persist_state()
        
        current_risk = self.get_current_portfolio_risk()
        logger.info(
            "Position added to registry",
            position_id=position_id,
            symbol=symbol,
            risk_amount=float(risk_amount),
            plan_id=plan_id,
            total_positions=len(self._positions),
            portfolio_risk=float(current_risk),
        )
        
        # Enhanced audit logging for position tracking
        logger.info(
            "AUDIT: Position tracking - Add",
            action="add_position",
            position_id=position_id,
            symbol=symbol,
            risk_amount_dollars=float(risk_amount),
            plan_id=plan_id,
            account_value=float(self._account_value),
            portfolio_risk_before=float(current_risk - (risk_amount / self._account_value * Decimal("100")) if self._account_value > 0 else Decimal("0")),
            portfolio_risk_after=float(current_risk),
            total_positions_count=len(self._positions),
            risk_capacity_remaining=float(self.MAX_PORTFOLIO_RISK - current_risk),
        )
    
    def remove_position(self, position_id: str) -> bool:
        """
        Remove position from registry (AC 15).
        
        Args:
            position_id: Position identifier to remove
            
        Returns:
            True if position was removed, False if not found
        """
        if position_id in self._positions:
            removed = self._positions.pop(position_id)
            risk_before = self.get_current_portfolio_risk() + (removed.risk_amount / self._account_value * Decimal("100") if self._account_value > 0 else Decimal("0"))
            self._persist_state()
            
            current_risk = self.get_current_portfolio_risk()
            logger.info(
                "Position removed from registry",
                position_id=position_id,
                symbol=removed.symbol,
                risk_amount=float(removed.risk_amount),
                remaining_positions=len(self._positions),
                portfolio_risk=float(current_risk),
            )
            
            # Enhanced audit logging for position removal
            logger.info(
                "AUDIT: Position tracking - Remove",
                action="remove_position",
                position_id=position_id,
                symbol=removed.symbol,
                risk_amount_dollars=float(removed.risk_amount),
                plan_id=removed.plan_id,
                account_value=float(self._account_value),
                portfolio_risk_before=float(risk_before),
                portfolio_risk_after=float(current_risk),
                risk_reduction=float(removed.risk_amount / self._account_value * Decimal("100") if self._account_value > 0 else Decimal("0")),
                remaining_positions_count=len(self._positions),
                risk_capacity_freed=float(removed.risk_amount / self._account_value * Decimal("100") if self._account_value > 0 else Decimal("0")),
            )
            return True
        else:
            logger.warning(
                "Attempted to remove non-existent position",
                position_id=position_id,
            )
            return False
    
    def get_current_portfolio_risk(self) -> Decimal:
        """
        Calculate total portfolio risk percentage (AC 6, 8, 16).
        
        Returns:
            Portfolio risk as percentage (0-100)
        """
        if self._account_value <= 0:
            return Decimal("0")
        
        total_risk_dollars = sum(pos.risk_amount for pos in self._positions.values())
        risk_percentage = (total_risk_dollars / self._account_value) * Decimal("100")
        
        return risk_percentage.quantize(Decimal("0.01"))
    
    def get_total_dollar_risk(self) -> Decimal:
        """Get total dollar risk across all positions."""
        return sum(pos.risk_amount for pos in self._positions.values())
    
    def get_position_count(self) -> int:
        """Get number of open positions."""
        return len(self._positions)
    
    def get_position(self, position_id: str) -> Optional[PositionRiskEntry]:
        """Get position entry by ID."""
        return self._positions.get(position_id)
    
    def get_all_positions(self) -> Dict[str, PositionRiskEntry]:
        """Get all position entries."""
        return self._positions.copy()
    
    def get_positions_by_symbol(self, symbol: str) -> Dict[str, PositionRiskEntry]:
        """Get all positions for a specific symbol."""
        return {
            pos_id: entry 
            for pos_id, entry in self._positions.items() 
            if entry.symbol == symbol
        }
    
    def check_new_trade_risk(self, new_risk_amount: Decimal) -> Tuple[bool, str]:
        """
        Check if new trade would exceed portfolio limit (AC 7, 12, 19).
        
        Args:
            new_risk_amount: Dollar risk amount of new trade
            
        Returns:
            Tuple of (can_trade, reason_if_blocked)
        """
        if self._account_value <= 0:
            return False, "Invalid account value for risk calculation"
        
        current_risk = self.get_current_portfolio_risk()
        new_risk_percent = (new_risk_amount / self._account_value) * Decimal("100")
        total_risk = current_risk + new_risk_percent
        
        if total_risk > self.MAX_PORTFOLIO_RISK:
            message = (
                f"Portfolio risk limit exceeded: {total_risk:.2f}% "
                f"(current: {current_risk:.2f}% + new: {new_risk_percent:.2f}%) "
                f"exceeds limit of {self.MAX_PORTFOLIO_RISK:.1f}%"
            )
            
            logger.warning(
                "Portfolio risk limit exceeded",
                current_risk=float(current_risk),
                new_risk=float(new_risk_percent),
                total_risk=float(total_risk),
                limit=float(self.MAX_PORTFOLIO_RISK),
                new_risk_dollars=float(new_risk_amount),
            )
            
            return False, message
        
        return True, ""
    
    def validate_new_trade_risk(self, new_risk_amount: Decimal) -> None:
        """
        Validate new trade risk and raise exception if exceeded.
        
        Args:
            new_risk_amount: Dollar risk amount of new trade
            
        Raises:
            PortfolioRiskExceededError: If portfolio risk limit exceeded
        """
        can_trade, message = self.check_new_trade_risk(new_risk_amount)
        
        if not can_trade:
            current_risk = self.get_current_portfolio_risk()
            new_risk_percent = (new_risk_amount / self._account_value) * Decimal("100")
            
            raise PortfolioRiskExceededError(
                current_risk=current_risk,
                new_risk=new_risk_percent,
                limit=self.MAX_PORTFOLIO_RISK,
            )
    
    def get_available_risk_capacity(self) -> Tuple[Decimal, Decimal]:
        """
        Get remaining risk capacity.
        
        Returns:
            Tuple of (percentage_capacity, dollar_capacity)
        """
        current_risk = self.get_current_portfolio_risk()
        remaining_percent = self.MAX_PORTFOLIO_RISK - current_risk
        remaining_dollars = (remaining_percent / Decimal("100")) * self._account_value
        
        return remaining_percent, remaining_dollars
    
    def get_portfolio_summary(self) -> Dict:
        """Get comprehensive portfolio risk summary."""
        current_risk = self.get_current_portfolio_risk()
        remaining_percent, remaining_dollars = self.get_available_risk_capacity()
        
        return {
            "account_value": float(self._account_value),
            "position_count": self.get_position_count(),
            "total_dollar_risk": float(self.get_total_dollar_risk()),
            "current_risk_percentage": float(current_risk),
            "risk_limit": float(self.MAX_PORTFOLIO_RISK),
            "remaining_capacity_percent": float(remaining_percent),
            "remaining_capacity_dollars": float(remaining_dollars),
            "positions": [
                {
                    "position_id": entry.position_id,
                    "symbol": entry.symbol,
                    "risk_amount": float(entry.risk_amount),
                    "plan_id": entry.plan_id,
                    "entry_time": entry.entry_time.isoformat(),
                }
                for entry in self._positions.values()
            ],
        }
    
    def _load_state(self) -> None:
        """Load position registry from file (AC 17)."""
        if not self.state_file.exists():
            logger.debug("No existing state file found, starting with empty portfolio")
            return
        
        try:
            with open(self.state_file, "r") as f:
                data = json.load(f)
            
            state = PortfolioRiskState(**data)
            
            # Restore positions
            self._positions = {
                pos.position_id: pos for pos in state.positions
            }
            
            # Update account value if provided in state and not already set
            if hasattr(state, "account_value") and state.account_value >= 0:
                if self._account_value == Decimal("0"):  # Only update if not explicitly set
                    self._account_value = state.account_value
            
            logger.info(
                "Position registry loaded from file",
                file_path=str(self.state_file),
                position_count=len(self._positions),
                account_value=float(self._account_value),
                portfolio_risk=float(self.get_current_portfolio_risk()),
            )
            
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse state file JSON",
                file_path=str(self.state_file),
                error=str(e),
            )
        except Exception as e:
            logger.error(
                "Failed to load position registry",
                file_path=str(self.state_file),
                error=str(e),
            )
    
    def _persist_state(self) -> None:
        """Save position registry to file with atomic write (AC 17)."""
        try:
            # Ensure directory exists
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Create automated backup before state changes
            if self.state_file.exists():
                self._backup_manager.create_automated_backup()
            
            # Create portfolio state
            state = PortfolioRiskState(
                positions=list(self._positions.values()),
                total_risk_percentage=self.get_current_portfolio_risk(),
                account_value=self._account_value,
                last_updated=datetime.utcnow(),
            )
            
            # Atomic write using temporary file
            temp_file = self.state_file.with_suffix(".tmp")
            
            with open(temp_file, "w") as f:
                json.dump(
                    state.model_dump(mode="json"), 
                    f, 
                    indent=2, 
                    default=str,
                )
            
            # Atomically replace the original file
            temp_file.replace(self.state_file)
            
            logger.debug(
                "Position registry persisted",
                file_path=str(self.state_file),
                position_count=len(self._positions),
                total_risk=float(state.total_risk_percentage),
            )
            
        except Exception as e:
            logger.error(
                "Failed to persist position registry",
                file_path=str(self.state_file),
                error=str(e),
            )
            raise
    
    def create_backup(self, backup_path: Optional[Path] = None) -> Path:
        """
        Create a backup of the current state.
        
        Args:
            backup_path: Optional custom backup path
            
        Returns:
            Path to created backup file
        """
        return self._backup_manager.create_backup(backup_path)
    
    def clear_all_positions(self) -> int:
        """
        Clear all positions from registry.
        
        Returns:
            Number of positions cleared
        """
        count = len(self._positions)
        self._positions.clear()
        self._persist_state()
        
        logger.warning(
            "All positions cleared from registry",
            cleared_count=count,
        )
        
        return count