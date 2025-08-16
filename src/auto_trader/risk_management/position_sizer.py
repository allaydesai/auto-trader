"""Position sizing calculations based on risk management rules."""

from __future__ import annotations

from decimal import Decimal, ROUND_DOWN
from typing import Dict

from ..logging_config import get_logger
from .risk_models import PositionSizeResult, InvalidPositionSizeError

logger = get_logger("position_sizer", "risk")


class PositionSizer:
    """Calculate position sizes based on account risk management."""
    
    # Risk percentages for each category (AC 2)
    RISK_PERCENTAGES: Dict[str, Decimal] = {
        "small": Decimal("1.0"),   # 1%
        "normal": Decimal("2.0"),  # 2% 
        "large": Decimal("3.0"),   # 3%
    }
    
    def __init__(self) -> None:
        """Initialize position sizer."""
        logger.debug("PositionSizer initialized")
    
    def calculate_position_size(
        self,
        account_value: Decimal,
        risk_category: str,
        entry_price: Decimal,
        stop_loss: Decimal,
    ) -> PositionSizeResult:
        """
        Calculate position size using risk management formula.
        
        Formula: Position Size = (Account Value × Risk %) ÷ |Entry Price - Stop Loss|
        
        Args:
            account_value: Total account balance
            risk_category: Risk level (small/normal/large)
            entry_price: Planned entry price
            stop_loss: Stop loss price
            
        Returns:
            PositionSizeResult with calculated size and validation
            
        Raises:
            InvalidPositionSizeError: If calculation parameters are invalid
            
        Example:
            >>> sizer = PositionSizer()
            >>> result = sizer.calculate_position_size(
            ...     Decimal("10000"), "normal", Decimal("100"), Decimal("95")
            ... )
            >>> result.position_size
            40
        """
        # Validate inputs
        self._validate_inputs(account_value, risk_category, entry_price, stop_loss)
        
        # Get risk percentage for category (AC 2)
        risk_percent = self.RISK_PERCENTAGES[risk_category.lower()]
        
        # Calculate dollar risk amount (AC 5)
        dollar_risk = self._calculate_dollar_risk(account_value, risk_percent)
        
        # Calculate price difference (risk per share)
        price_difference = self._calculate_price_difference(entry_price, stop_loss)
        
        # Calculate raw position size (AC 1)
        raw_position_size = dollar_risk / price_difference
        
        # Round to whole shares (AC 4)
        position_size = self._round_to_shares(raw_position_size)
        
        # Log calculation details
        logger.info(
            "Position size calculated",
            account_value=float(account_value),
            risk_category=risk_category,
            risk_percent=float(risk_percent),
            entry_price=float(entry_price),
            stop_loss=float(stop_loss),
            price_difference=float(price_difference),
            dollar_risk=float(dollar_risk),
            raw_position_size=float(raw_position_size),
            final_position_size=position_size,
        )
        
        return PositionSizeResult(
            position_size=position_size,
            dollar_risk=dollar_risk,
            validation_status=True,
            portfolio_risk_percentage=risk_percent,
            risk_category=risk_category,
            account_value=account_value,
        )
    
    def _validate_inputs(
        self,
        account_value: Decimal,
        risk_category: str,
        entry_price: Decimal,
        stop_loss: Decimal,
    ) -> None:
        """Validate calculation inputs (AC 3, 18, 20)."""
        # Validate account value (AC 20)
        if account_value <= 0:
            raise InvalidPositionSizeError(
                "Account value must be positive",
                entry_price=entry_price,
                stop_price=stop_loss,
            )
        
        # Validate risk category (AC 2)
        if risk_category.lower() not in self.RISK_PERCENTAGES:
            valid_categories = ", ".join(self.RISK_PERCENTAGES.keys())
            raise InvalidPositionSizeError(
                f"Invalid risk category '{risk_category}'. "
                f"Must be one of: {valid_categories}"
            )
        
        # Validate prices are positive
        if entry_price <= 0:
            raise InvalidPositionSizeError(
                "Entry price must be positive",
                entry_price=entry_price,
                stop_price=stop_loss,
            )
        
        if stop_loss <= 0:
            raise InvalidPositionSizeError(
                "Stop loss price must be positive",
                entry_price=entry_price,
                stop_price=stop_loss,
            )
        
        # Prevent zero-risk trades (AC 3, 18)
        if entry_price == stop_loss:
            raise InvalidPositionSizeError(
                f"Entry price ({entry_price}) cannot equal stop loss "
                f"({stop_loss}). This creates zero-risk trades.",
                entry_price=entry_price,
                stop_price=stop_loss,
            )
    
    def _calculate_dollar_risk(
        self, 
        account_value: Decimal, 
        risk_percent: Decimal,
    ) -> Decimal:
        """Calculate dollar risk amount from percentage."""
        dollar_risk = account_value * (risk_percent / Decimal("100"))
        return dollar_risk.quantize(Decimal("0.01"))  # Round to cents
    
    def _calculate_price_difference(
        self, 
        entry_price: Decimal, 
        stop_loss: Decimal,
    ) -> Decimal:
        """Calculate absolute price difference for risk calculation."""
        return abs(entry_price - stop_loss)
    
    def _round_to_shares(self, raw_position_size: Decimal) -> int:
        """Round position size to whole shares (AC 4)."""
        # Round down to ensure we don't exceed risk limits
        rounded_size = int(raw_position_size.quantize(Decimal("1"), ROUND_DOWN))
        
        # Ensure minimum 1 share for valid trades
        return max(1, rounded_size)
    
    def get_risk_percentage(self, risk_category: str) -> Decimal:
        """Get risk percentage for a given category."""
        if risk_category.lower() not in self.RISK_PERCENTAGES:
            valid_categories = ", ".join(self.RISK_PERCENTAGES.keys())
            raise InvalidPositionSizeError(
                f"Invalid risk category '{risk_category}'. "
                f"Must be one of: {valid_categories}"
            )
        
        return self.RISK_PERCENTAGES[risk_category.lower()]
    
    def get_supported_risk_categories(self) -> list[str]:
        """Get list of supported risk categories."""
        return list(self.RISK_PERCENTAGES.keys())
    
    def calculate_max_position_size(
        self,
        account_value: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal,
    ) -> int:
        """Calculate maximum position size using largest risk category."""
        result = self.calculate_position_size(
            account_value=account_value,
            risk_category="large",
            entry_price=entry_price,
            stop_loss=stop_loss,
        )
        return result.position_size
    
    def preview_position_sizes(
        self,
        account_value: Decimal,
        entry_price: Decimal,
        stop_loss: Decimal,
    ) -> Dict[str, PositionSizeResult]:
        """Preview position sizes for all risk categories."""
        results = {}
        
        for category in self.RISK_PERCENTAGES:
            try:
                result = self.calculate_position_size(
                    account_value=account_value,
                    risk_category=category,
                    entry_price=entry_price,
                    stop_loss=stop_loss,
                )
                results[category] = result
            except InvalidPositionSizeError as e:
                logger.warning(
                    "Failed to calculate position size for category",
                    category=category,
                    error=str(e),
                )
                
        return results