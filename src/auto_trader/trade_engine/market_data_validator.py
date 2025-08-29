"""Market data validation for corruption detection and quality assurance."""

from dataclasses import dataclass
from datetime import datetime, UTC, timedelta
from typing import Optional

from auto_trader.models.market_data import BarData


@dataclass
class MarketDataValidationResult:
    """Result of market data validation."""
    is_valid: bool
    error_message: Optional[str] = None
    corruption_type: Optional[str] = None


class MarketDataValidator:
    """Validates market data for corruption and suspicious patterns.
    
    Performs comprehensive validation of incoming bar data to ensure
    data integrity and prevent execution on corrupted market data.
    """
    
    def __init__(
        self,
        max_reasonable_price: float = 10000.0,
        future_timestamp_tolerance_seconds: int = 1,
    ):
        """Initialize market data validator.
        
        Args:
            max_reasonable_price: Maximum reasonable price per share
            future_timestamp_tolerance_seconds: Tolerance for future timestamps
        """
        self.max_reasonable_price = max_reasonable_price
        self.future_timestamp_tolerance = timedelta(seconds=future_timestamp_tolerance_seconds)
    
    def validate(self, bar: BarData) -> MarketDataValidationResult:
        """Validate market data for corruption and suspicious patterns.
        
        Args:
            bar: Bar data to validate
            
        Returns:
            Validation result indicating if data is valid
        """
        # Check for zero or negative volume
        if bar.volume <= 0:
            return MarketDataValidationResult(
                is_valid=False,
                error_message="Invalid market data: zero or negative volume",
                corruption_type="zero_volume"
            )
        
        # Check for future timestamps
        now = datetime.now(UTC)
        if bar.timestamp > now + self.future_timestamp_tolerance:
            return MarketDataValidationResult(
                is_valid=False,
                error_message=(
                    f"Invalid market data: future timestamp {bar.timestamp} > "
                    f"{now + self.future_timestamp_tolerance}"
                ),
                corruption_type="future_timestamp"
            )
        
        # Check for negative or zero prices
        if any(price <= 0 for price in [bar.open_price, bar.high_price, bar.low_price, bar.close_price]):
            return MarketDataValidationResult(
                is_valid=False,
                error_message="Invalid market data: negative or zero price detected",
                corruption_type="negative_price"
            )
        
        # Check for invalid OHLC relationships
        if not self._validate_ohlc_relationships(bar):
            return MarketDataValidationResult(
                is_valid=False,
                error_message="Invalid market data: OHLC relationship violation",
                corruption_type="invalid_ohlc"
            )
        
        # Check for extremely high prices
        if self._has_extreme_prices(bar):
            return MarketDataValidationResult(
                is_valid=False,
                error_message=(
                    f"Invalid market data: extreme price detected (>{self.max_reasonable_price})"
                ),
                corruption_type="extreme_price"
            )
        
        # Data is valid
        return MarketDataValidationResult(is_valid=True)
    
    def _validate_ohlc_relationships(self, bar: BarData) -> bool:
        """Validate OHLC price relationships.
        
        Args:
            bar: Bar data to validate
            
        Returns:
            True if OHLC relationships are valid
        """
        return (
            bar.low_price <= bar.open_price <= bar.high_price and
            bar.low_price <= bar.close_price <= bar.high_price
        )
    
    def _has_extreme_prices(self, bar: BarData) -> bool:
        """Check for extremely high prices that may indicate corruption.
        
        Args:
            bar: Bar data to validate
            
        Returns:
            True if extreme prices detected
        """
        return any(
            float(price) > self.max_reasonable_price
            for price in [bar.open_price, bar.high_price, bar.low_price, bar.close_price]
        )