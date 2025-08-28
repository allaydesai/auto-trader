"""Order risk validation for trade execution."""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, Any, Optional

from ..logging_config import get_logger
from ..models.order import OrderRequest, OrderResult
from ..models.enums import OrderStatus
from ..models.trade_plan import RiskCategory
from .position_sizer import PositionSizer
from .portfolio_tracker import PortfolioTracker
from .risk_models import (
    RiskValidationResult,
    PositionSizeResult,
    RiskManagementError,
    PortfolioRiskExceededError,
    InvalidPositionSizeError,
    DailyLossLimitExceededError,
)

logger = get_logger("order_risk_validator", "risk")


class OrderRiskValidator:
    """Validate order requests against risk management rules."""
    
    # Portfolio risk limit (10% maximum total risk)
    MAX_PORTFOLIO_RISK_PERCENT = Decimal("10.0")
    
    def __init__(
        self, 
        position_sizer: PositionSizer,
        portfolio_tracker: PortfolioTracker,
        account_value: Optional[Decimal] = None
    ) -> None:
        """
        Initialize order risk validator.
        
        Args:
            position_sizer: Position sizing calculator
            portfolio_tracker: Portfolio risk tracking
            account_value: Current account value (if None, will be fetched)
        """
        self.position_sizer = position_sizer
        self.portfolio_tracker = portfolio_tracker
        self._account_value = account_value
        
        logger.debug("OrderRiskValidator initialized")
    
    async def validate_order_request(self, order_request: OrderRequest) -> RiskValidationResult:
        """
        Validate order request against all risk management rules.
        
        Args:
            order_request: Order placement request to validate
            
        Returns:
            RiskValidationResult with validation status and details
            
        Raises:
            RiskManagementError: If validation fails due to risk violations
        """
        try:
            logger.info(
                "Validating order request",
                trade_plan_id=order_request.trade_plan_id,
                symbol=order_request.symbol,
                risk_category=order_request.risk_category,
            )
            
            # Get current account value
            account_value = await self._get_account_value()
            
            # Step 1: Calculate position size
            position_size_result = self._calculate_position_size(
                order_request, account_value
            )
            
            # Step 2: Check portfolio risk limit
            await self._validate_portfolio_risk_limit(
                position_size_result.dollar_risk
            )
            
            # Step 3: Check available capital
            await self._validate_available_capital(
                order_request, position_size_result, account_value
            )
            
            # Step 4: Check daily loss limit
            await self._validate_daily_loss_limit()
            
            # Update order request with calculated position size
            order_request.calculated_position_size = position_size_result.position_size
            
            logger.info(
                "Order request validation successful",
                trade_plan_id=order_request.trade_plan_id,
                calculated_position_size=position_size_result.position_size,
                dollar_risk=float(position_size_result.dollar_risk),
            )
            
            from .risk_models import RiskCheck
            
            portfolio_risk_check = RiskCheck(
                passed=True,
                reason=None,
                current_risk=await self._get_current_portfolio_risk(),
                new_trade_risk=position_size_result.portfolio_risk_percentage,
                total_risk=(await self._get_current_portfolio_risk()) + position_size_result.portfolio_risk_percentage,
                limit=self.MAX_PORTFOLIO_RISK_PERCENT,
            )
            
            return RiskValidationResult(
                is_valid=True,
                position_size_result=position_size_result,
                portfolio_risk_check=portfolio_risk_check,
                errors=[],
                warnings=[],
            )
            
        except RiskManagementError as e:
            logger.error(
                "Order request validation failed",
                trade_plan_id=order_request.trade_plan_id,
                error=str(e),
                error_type=type(e).__name__,
            )
            
            from .risk_models import RiskCheck
            
            portfolio_risk_check = RiskCheck(
                passed=False,
                reason=str(e),
                current_risk=Decimal("0.0"),
                new_trade_risk=Decimal("0.0"),
                total_risk=Decimal("0.0"),
                limit=self.MAX_PORTFOLIO_RISK_PERCENT,
            )
            
            return RiskValidationResult(
                is_valid=False,
                position_size_result=None,
                portfolio_risk_check=portfolio_risk_check,
                errors=[str(e)],
                warnings=[],
            )
    
    def _calculate_position_size(
        self, order_request: OrderRequest, account_value: Decimal
    ) -> PositionSizeResult:
        """Calculate position size for the order request."""
        try:
            # RiskCategory enum values are already converted to strings by Pydantic
            risk_category_str = order_request.risk_category.lower()
            
            return self.position_sizer.calculate_position_size(
                account_value=account_value,
                risk_category=risk_category_str,
                entry_price=order_request.entry_price,
                stop_loss=order_request.stop_loss_price,
            )
            
        except InvalidPositionSizeError as e:
            logger.error(
                "Position size calculation failed",
                trade_plan_id=order_request.trade_plan_id,
                error=str(e),
            )
            raise
    
    async def _validate_portfolio_risk_limit(self, new_trade_risk: Decimal) -> None:
        """Validate that adding this trade doesn't exceed portfolio risk limit."""
        try:
            portfolio_state = await self.portfolio_tracker.get_current_state()
            
            # Calculate total risk including new trade
            total_risk = portfolio_state.total_risk_percentage + (
                (new_trade_risk / await self._get_account_value()) * Decimal("100")
            )
            
            if total_risk > self.MAX_PORTFOLIO_RISK_PERCENT:
                new_trade_risk_percent = (new_trade_risk / await self._get_account_value()) * Decimal('100')
                raise PortfolioRiskExceededError(
                    current_risk=portfolio_state.total_risk_percentage,
                    new_risk=new_trade_risk_percent,
                    limit=self.MAX_PORTFOLIO_RISK_PERCENT,
                )
                
            logger.debug(
                "Portfolio risk check passed",
                current_risk=float(portfolio_state.total_risk_percentage),
                new_trade_risk=float((new_trade_risk / await self._get_account_value()) * Decimal("100")),
                total_risk=float(total_risk),
                limit=float(self.MAX_PORTFOLIO_RISK_PERCENT),
            )
            
        except Exception as e:
            if isinstance(e, PortfolioRiskExceededError):
                raise
            logger.error("Portfolio risk validation error", error=str(e))
            raise RiskManagementError(f"Portfolio risk validation failed: {e}")
    
    async def _validate_available_capital(
        self, 
        order_request: OrderRequest, 
        position_size_result: PositionSizeResult,
        account_value: Decimal
    ) -> None:
        """Validate sufficient capital is available for the trade."""
        try:
            # Calculate required capital (position value + some buffer for commissions)
            position_value = Decimal(str(position_size_result.position_size)) * order_request.entry_price
            required_capital = position_value * Decimal("1.02")  # 2% buffer for commissions/slippage
            
            # Get available buying power (simplified: use 50% of account value)
            # In real implementation, this would query IBKR for actual buying power
            available_capital = account_value * Decimal("0.5")
            
            if required_capital > available_capital:
                raise InvalidPositionSizeError(
                    reason=f"Insufficient capital: required ${required_capital:.2f}, "
                           f"available ${available_capital:.2f}",
                    entry_price=order_request.entry_price,
                    stop_price=order_request.stop_loss_price,
                )
                
            logger.debug(
                "Capital availability check passed",
                required_capital=float(required_capital),
                available_capital=float(available_capital),
                position_size=position_size_result.position_size,
            )
            
        except InvalidPositionSizeError:
            raise
        except Exception as e:
            logger.error("Capital validation error", error=str(e))
            raise RiskManagementError(f"Capital validation failed: {e}")
    
    async def _validate_daily_loss_limit(self) -> None:
        """Validate that daily loss limit has not been exceeded."""
        try:
            # For now, daily loss limit validation is simplified
            # In real implementation, this would:
            # 1. Check daily P&L from account data
            # 2. Compare against configured daily loss limit
            # 3. Block new positions if limit exceeded
            
            # Placeholder implementation - always passes for MVP
            logger.debug("Daily loss limit check passed (simplified implementation)")
            
        except Exception as e:
            logger.error("Daily loss limit validation error", error=str(e))
            raise RiskManagementError(f"Daily loss limit validation failed: {e}")
    
    async def _get_account_value(self) -> Decimal:
        """Get current account value."""
        if self._account_value is not None:
            return self._account_value
            
        # In real implementation, this would query IBKR for current account value
        # For now, return a placeholder value
        return Decimal("100000.00")  # $100k default
    
    async def _get_current_portfolio_risk(self) -> Decimal:
        """Get current portfolio risk percentage."""
        try:
            portfolio_state = await self.portfolio_tracker.get_current_state()
            return portfolio_state.total_risk_percentage
        except Exception as e:
            logger.warning(f"Could not get current portfolio risk: {e}")
            return Decimal("0.0")
    
    def create_order_rejection_result(
        self, 
        order_request: OrderRequest, 
        validation_result: RiskValidationResult
    ) -> OrderResult:
        """Create order rejection result from failed validation."""
        # Get first error message if any
        error_message = validation_result.errors[0] if validation_result.errors else "Unknown validation error"
        
        return OrderResult(
            success=False,
            trade_plan_id=order_request.trade_plan_id,
            order_status=OrderStatus.REJECTED,
            error_message=f"Risk validation failed: {error_message}",
            error_code=None,
            symbol=order_request.symbol,
            side=order_request.side,
            quantity=0,  # No quantity since order was rejected
            order_type=order_request.order_type,
        )