"""Risk management orchestrator with trade plan integration."""

from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Optional

from ..logging_config import get_logger
from ..models import TradePlan
from .portfolio_tracker import PortfolioTracker
from .position_sizer import PositionSizer
from .risk_models import (
    DailyLossLimitExceededError,
    InvalidPositionSizeError,
    RiskCheck,
    RiskValidationResult,
)

logger = get_logger("risk_manager", "risk")


class RiskManager:
    """Orchestrate position sizing and portfolio risk management."""
    
    def __init__(
        self,
        account_value: Decimal,
        daily_loss_limit: Optional[Decimal] = None,
        state_file: Optional[Path] = None,
    ) -> None:
        """
        Initialize risk manager.
        
        Args:
            account_value: Total account balance for calculations
            daily_loss_limit: Maximum daily loss allowed (defaults to $500)
            state_file: Path to position registry state file
        """
        self.account_value = account_value
        self.daily_loss_limit = daily_loss_limit if daily_loss_limit is not None else Decimal("500.00")
        
        # Initialize components
        self.position_sizer = PositionSizer()
        self.portfolio_tracker = PortfolioTracker(
            state_file=state_file,
            account_value=account_value,
        )
        
        # Track daily losses
        self._daily_losses: Decimal = Decimal("0.00")
        self._last_reset_date = datetime.utcnow().date()
        
        logger.info(
            "RiskManager initialized",
            account_value=float(account_value),
            daily_loss_limit=float(self.daily_loss_limit),
            existing_positions=self.portfolio_tracker.get_position_count(),
            portfolio_risk=float(self.portfolio_tracker.get_current_portfolio_risk()),
        )
    
    def validate_trade_plan(self, trade_plan: TradePlan) -> RiskValidationResult:
        """
        Complete risk validation for a trade plan (AC 10, 11, 13).
        
        Args:
            trade_plan: Trade plan to validate
            
        Returns:
            RiskValidationResult with comprehensive validation details
        """
        errors = []
        warnings = []
        
        logger.info(
            "Validating trade plan",
            plan_id=trade_plan.plan_id,
            symbol=trade_plan.symbol,
            risk_category=trade_plan.risk_category,
        )
        
        # Validate account value (AC 20)
        if self.account_value <= 0:
            errors.append("Invalid account value for risk calculations")
            return self._create_failed_result(errors, "Invalid account value")
        
        # Calculate position size
        position_result = None
        try:
            position_result = self.position_sizer.calculate_position_size(
                account_value=self.account_value,
                risk_category=trade_plan.risk_category,
                entry_price=trade_plan.entry_level,
                stop_loss=trade_plan.stop_loss,
            )
            
            logger.debug(
                "Position size calculated",
                plan_id=trade_plan.plan_id,
                position_size=position_result.position_size,
                dollar_risk=float(position_result.dollar_risk),
            )
            
        except InvalidPositionSizeError as e:
            errors.append(str(e))
            return self._create_failed_result(errors, str(e))
        
        # Check portfolio risk limit (AC 7, 12, 19)
        portfolio_check = self._check_portfolio_risk_limit(position_result.dollar_risk)
        
        if not portfolio_check.passed:
            errors.append(portfolio_check.reason or "Portfolio risk limit exceeded")
        
        # Check daily loss limit (AC 24)
        daily_loss_check = self._check_daily_loss_limit()
        if not daily_loss_check:
            errors.append(
                f"Daily loss limit exceeded: ${self._daily_losses:.2f} >= "
                f"${self.daily_loss_limit:.2f}"
            )
            warnings.append("Consider waiting until tomorrow to trade")
        
        # Create comprehensive result
        result = RiskValidationResult(
            is_valid=len(errors) == 0,
            position_size_result=position_result if len(errors) == 0 else None,
            portfolio_risk_check=portfolio_check,
            errors=errors,
            warnings=warnings,
        )
        
        # Enhanced audit logging for risk decisions
        audit_data = {
            "plan_id": trade_plan.plan_id,
            "symbol": trade_plan.symbol,
            "is_valid": result.is_valid,
            "error_count": result.error_count,
            "warning_count": result.warning_count,
            "account_value": float(self.account_value),
            "entry_price": float(trade_plan.entry_level),
            "stop_loss": float(trade_plan.stop_loss),
            "risk_category": trade_plan.risk_category,
        }
        
        if position_result:
            audit_data.update({
                "position_size": position_result.position_size,
                "dollar_risk": float(position_result.dollar_risk),
                "risk_percentage": float(position_result.portfolio_risk_percentage),
            })
        
        audit_data.update({
            "portfolio_risk_current": float(portfolio_check.current_risk),
            "portfolio_risk_new": float(portfolio_check.new_trade_risk),
            "portfolio_risk_total": float(portfolio_check.total_risk),
            "portfolio_risk_limit": float(portfolio_check.limit),
            "portfolio_check_passed": portfolio_check.passed,
        })
        
        if result.errors:
            audit_data["rejection_reasons"] = result.errors
            
        if result.warnings:
            audit_data["warnings"] = result.warnings
            
        logger.info(
            "AUDIT: Trade plan validation decision",
            **audit_data
        )
        
        return result
    
    def calculate_position_size_for_plan(self, trade_plan: TradePlan) -> int:
        """
        Calculate position size for a trade plan.
        
        Args:
            trade_plan: Trade plan to calculate position size for
            
        Returns:
            Position size in shares
            
        Raises:
            InvalidPositionSizeError: If calculation fails
        """
        result = self.position_sizer.calculate_position_size(
            account_value=self.account_value,
            risk_category=trade_plan.risk_category,
            entry_price=trade_plan.entry_level,
            stop_loss=trade_plan.stop_loss,
        )
        
        return result.position_size
    
    def check_portfolio_risk_limit(self, new_trade_dollar_risk: Decimal) -> RiskCheck:
        """
        Check if new trade would exceed portfolio risk limit.
        
        Args:
            new_trade_dollar_risk: Dollar risk amount of new trade
            
        Returns:
            RiskCheck with validation result
        """
        return self._check_portfolio_risk_limit(new_trade_dollar_risk)
    
    def get_current_portfolio_risk(self) -> Decimal:
        """Get current portfolio risk percentage."""
        return self.portfolio_tracker.get_current_portfolio_risk()
    
    def get_available_risk_capacity(self) -> tuple[Decimal, Decimal]:
        """
        Get available risk capacity.
        
        Returns:
            Tuple of (percentage_capacity, dollar_capacity)
        """
        return self.portfolio_tracker.get_available_risk_capacity()
    
    def add_position_to_tracking(
        self,
        position_id: str,
        symbol: str,
        risk_amount: Decimal,
        plan_id: str,
    ) -> None:
        """
        Add position to risk tracking registry.
        
        Args:
            position_id: Unique position identifier
            symbol: Trading symbol
            risk_amount: Risk amount in dollars
            plan_id: Trade plan identifier
        """
        self.portfolio_tracker.add_position(position_id, symbol, risk_amount, plan_id)
        
        logger.info(
            "Position added to risk tracking",
            position_id=position_id,
            symbol=symbol,
            risk_amount=float(risk_amount),
            plan_id=plan_id,
            new_portfolio_risk=float(self.get_current_portfolio_risk()),
        )
    
    def remove_position_from_tracking(self, position_id: str) -> bool:
        """
        Remove position from risk tracking registry.
        
        Args:
            position_id: Position identifier to remove
            
        Returns:
            True if position was removed, False if not found
        """
        result = self.portfolio_tracker.remove_position(position_id)
        
        if result:
            logger.info(
                "Position removed from risk tracking",
                position_id=position_id,
                new_portfolio_risk=float(self.get_current_portfolio_risk()),
            )
        
        return result
    
    def record_daily_loss(self, loss_amount: Decimal) -> None:
        """
        Record a daily loss and check against limits.
        
        Args:
            loss_amount: Loss amount to record (positive value)
            
        Raises:
            DailyLossLimitExceededError: If adding loss exceeds daily limit
        """
        self._reset_daily_losses_if_needed()
        
        new_total = self._daily_losses + loss_amount
        
        # Check if limit exceeded
        logger.debug(
            "Checking daily loss limit",
            new_total=float(new_total),
            limit=float(self.daily_loss_limit),
            would_exceed=new_total > self.daily_loss_limit,
        )
        
        if new_total > self.daily_loss_limit:
            raise DailyLossLimitExceededError(
                current_loss=new_total,
                limit=self.daily_loss_limit,
            )
        
        self._daily_losses = new_total
        
        logger.warning(
            "Daily loss recorded",
            loss_amount=float(loss_amount),
            total_daily_losses=float(self._daily_losses),
            daily_limit=float(self.daily_loss_limit),
            remaining_limit=float(self.daily_loss_limit - self._daily_losses),
        )
    
    def get_portfolio_summary(self) -> dict:
        """Get comprehensive risk management summary."""
        portfolio_summary = self.portfolio_tracker.get_portfolio_summary()
        
        # Add risk manager specific data
        portfolio_summary.update({
            "daily_loss_limit": float(self.daily_loss_limit),
            "daily_losses": float(self._daily_losses),
            "daily_loss_remaining": float(self.daily_loss_limit - self._daily_losses),
            "daily_loss_percentage": float(
                (self._daily_losses / self.daily_loss_limit) * Decimal("100")
                if self.daily_loss_limit > 0 else Decimal("0")
            ),
        })
        
        return portfolio_summary
    
    def update_account_value(self, new_account_value: Decimal) -> None:
        """
        Update account value for all calculations.
        
        Args:
            new_account_value: New account balance
        """
        old_value = self.account_value
        self.account_value = new_account_value
        self.portfolio_tracker.set_account_value(new_account_value)
        
        logger.info(
            "Account value updated",
            old_value=float(old_value),
            new_value=float(new_account_value),
            portfolio_risk=float(self.get_current_portfolio_risk()),
        )
    
    def clear_all_positions(self) -> int:
        """
        Clear all positions from tracking.
        
        Returns:
            Number of positions cleared
        """
        count = self.portfolio_tracker.clear_all_positions()
        
        logger.warning(
            "All positions cleared from risk tracking",
            cleared_count=count,
        )
        
        return count
    
    def _check_portfolio_risk_limit(self, new_trade_dollar_risk: Decimal) -> RiskCheck:
        """Check portfolio risk limit for new trade."""
        can_trade, message = self.portfolio_tracker.check_new_trade_risk(
            new_trade_dollar_risk
        )
        
        current_risk = self.portfolio_tracker.get_current_portfolio_risk()
        new_risk_percent = (
            (new_trade_dollar_risk / self.account_value) * Decimal("100")
            if self.account_value > 0 else Decimal("0")
        )
        
        return RiskCheck(
            passed=can_trade,
            reason=message if not can_trade else None,
            current_risk=current_risk,
            new_trade_risk=new_risk_percent,
            total_risk=current_risk + new_risk_percent,
            limit=self.portfolio_tracker.MAX_PORTFOLIO_RISK,
        )
    
    def _check_daily_loss_limit(self) -> bool:
        """Check if daily loss limit would be exceeded."""
        self._reset_daily_losses_if_needed()
        return self._daily_losses < self.daily_loss_limit
    
    def _reset_daily_losses_if_needed(self) -> None:
        """Reset daily losses if it's a new day."""
        current_date = datetime.utcnow().date()
        
        if current_date > self._last_reset_date:
            old_losses = self._daily_losses
            self._daily_losses = Decimal("0.00")
            self._last_reset_date = current_date
            
            logger.info(
                "Daily losses reset for new day",
                previous_losses=float(old_losses),
                reset_date=current_date.isoformat(),
            )
    
    def _create_failed_result(self, errors: list[str], reason: str) -> RiskValidationResult:
        """Create a failed risk validation result."""
        return RiskValidationResult(
            is_valid=False,
            portfolio_risk_check=RiskCheck(
                passed=False,
                reason=reason,
                current_risk=self.portfolio_tracker.get_current_portfolio_risk(),
                new_trade_risk=Decimal("0"),
                limit=self.portfolio_tracker.MAX_PORTFOLIO_RISK,
            ),
            errors=errors,
        )