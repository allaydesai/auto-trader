"""Market data models for real-time and historical bar data."""

from datetime import datetime, timedelta, UTC
from decimal import Decimal
from typing import Dict, List, Optional, Literal
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic import ConfigDict
from loguru import logger


# Supported bar sizes mapping to ib-async format
BAR_SIZE_MAPPING = {
    "1min": "1 min",
    "5min": "5 mins",
    "15min": "15 mins",
    "30min": "30 mins",
    "1hour": "1 hour",
    "4hour": "4 hours",
    "1day": "1 day"
}

# Bar size to seconds for stale data detection
BAR_SIZE_SECONDS = {
    "1min": 60,
    "5min": 300,
    "15min": 900,
    "30min": 1800,
    "1hour": 3600,
    "4hour": 14400,
    "1day": 86400
}

BarSizeType = Literal["1min", "5min", "15min", "30min", "1hour", "4hour", "1day"]


class BarData(BaseModel):
    """Represents a single OHLCV bar with comprehensive validation."""
    
    symbol: str = Field(..., min_length=1, max_length=10, description="Trading symbol")
    timestamp: datetime = Field(..., description="Bar close time in UTC")
    open_price: Decimal = Field(..., gt=0, decimal_places=4, description="Opening price")
    high_price: Decimal = Field(..., gt=0, decimal_places=4, description="High price")
    low_price: Decimal = Field(..., gt=0, decimal_places=4, description="Low price")
    close_price: Decimal = Field(..., gt=0, decimal_places=4, description="Closing price")
    volume: int = Field(..., ge=0, description="Trading volume")
    bar_size: BarSizeType = Field(..., description="Bar timeframe")
    
    model_config = ConfigDict(
        validate_assignment=True,
        str_strip_whitespace=True,
        use_enum_values=True,
        arbitrary_types_allowed=True
    )
    
    @field_validator('timestamp')
    @classmethod
    def validate_utc_timezone(cls, v: datetime) -> datetime:
        """Ensure timestamp is timezone-aware and in UTC."""
        if v.tzinfo is None:
            raise ValueError("Timestamp must be timezone-aware")
        if v.tzinfo != UTC:
            return v.astimezone(UTC)
        return v
    
    @model_validator(mode='after')
    def validate_ohlc_consistency(self) -> 'BarData':
        """Validate OHLC relationships."""
        # High must be >= max(open, close)
        max_price = max(self.open_price, self.close_price)
        if self.high_price < max_price:
            raise ValueError(
                f"High price {self.high_price} must be >= max(open {self.open_price}, "
                f"close {self.close_price})"
            )
        
        # Low must be <= min(open, close)
        min_price = min(self.open_price, self.close_price)
        if self.low_price > min_price:
            raise ValueError(
                f"Low price {self.low_price} must be <= min(open {self.open_price}, "
                f"close {self.close_price})"
            )
        
        # High must be >= Low
        if self.high_price < self.low_price:
            raise ValueError(
                f"High price {self.high_price} must be >= low price {self.low_price}"
            )
        
        return self
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for serialization."""
        return {
            "symbol": self.symbol,
            "timestamp": self.timestamp.isoformat(),
            "open": f"{self.open_price:.2f}",
            "high": f"{self.high_price:.2f}",
            "low": f"{self.low_price:.2f}",
            "close": f"{self.close_price:.2f}",
            "volume": self.volume,
            "bar_size": self.bar_size
        }


class MarketData(BaseModel):
    """Market data container with quality validation."""
    
    bars: Dict[str, List[BarData]] = Field(
        default_factory=dict,
        description="Bars indexed by 'symbol:bar_size' key"
    )
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="Last update timestamp"
    )
    
    model_config = ConfigDict(
        validate_assignment=True,
        arbitrary_types_allowed=True
    )
    
    def add_bar(self, bar: BarData) -> None:
        """Add a new bar to the container."""
        key = f"{bar.symbol}:{bar.bar_size}"
        if key not in self.bars:
            self.bars[key] = []
        
        # Insert in chronological order
        self.bars[key].append(bar)
        self.bars[key].sort(key=lambda x: x.timestamp)
        
        self.last_updated = datetime.now(UTC)
        
        logger.debug(
            "Bar added",
            symbol=bar.symbol,
            bar_size=bar.bar_size,
            timestamp=bar.timestamp.isoformat(),
            close=str(bar.close_price)
        )
    
    def get_latest_bar(
        self, 
        symbol: str, 
        bar_size: BarSizeType
    ) -> Optional[BarData]:
        """Get the most recent bar for a symbol and timeframe."""
        key = f"{symbol}:{bar_size}"
        if key in self.bars and self.bars[key]:
            return self.bars[key][-1]
        return None
    
    def get_bars(
        self, 
        symbol: str, 
        bar_size: BarSizeType,
        limit: Optional[int] = None
    ) -> List[BarData]:
        """Get bars for a symbol and timeframe."""
        key = f"{symbol}:{bar_size}"
        bars = self.bars.get(key, [])
        
        if limit and limit > 0:
            return bars[-limit:]
        return bars
    
    def is_stale(
        self, 
        symbol: str,
        bar_size: BarSizeType, 
        max_age_multiplier: int = 2
    ) -> bool:
        """Check if data is stale (older than max_age_multiplier * bar_size)."""
        latest_bar = self.get_latest_bar(symbol, bar_size)
        if not latest_bar:
            return True
        
        bar_seconds = BAR_SIZE_SECONDS.get(bar_size, 300)
        max_age_seconds = bar_seconds * max_age_multiplier
        
        now = datetime.now(UTC)
        age = now - latest_bar.timestamp
        
        is_stale = age.total_seconds() > max_age_seconds
        
        if is_stale:
            logger.warning(
                "Stale data detected",
                symbol=symbol,
                bar_size=bar_size,
                data_age_seconds=age.total_seconds(),
                max_age_seconds=max_age_seconds,
                last_bar_time=latest_bar.timestamp.isoformat()
            )
        
        return is_stale
    
    def remove_old_bars(self, max_age_hours: int = 24) -> int:
        """Remove bars older than specified hours."""
        cutoff = datetime.now(UTC) - timedelta(hours=max_age_hours)
        removed_count = 0
        
        for key in list(self.bars.keys()):
            original_count = len(self.bars[key])
            self.bars[key] = [
                bar for bar in self.bars[key] 
                if bar.timestamp > cutoff
            ]
            removed_count += original_count - len(self.bars[key])
            
            # Remove empty keys
            if not self.bars[key]:
                del self.bars[key]
        
        if removed_count > 0:
            logger.info(
                "Old bars removed",
                removed_count=removed_count,
                max_age_hours=max_age_hours
            )
        
        return removed_count
    
    def get_symbol_count(self) -> int:
        """Get count of unique symbols with data."""
        symbols = set()
        for key in self.bars.keys():
            symbol, _ = key.split(":")
            symbols.add(symbol)
        return len(symbols)
    
    def get_total_bar_count(self) -> int:
        """Get total count of bars across all symbols and timeframes."""
        return sum(len(bars) for bars in self.bars.values())


# Custom exceptions for market data
class MarketDataError(Exception):
    """Base exception for market data errors."""
    pass


class StaleDataError(MarketDataError):
    """Data is too old for reliable trading decisions."""
    def __init__(self, symbol: str, bar_size: str, age_seconds: float):
        self.symbol = symbol
        self.bar_size = bar_size
        self.age_seconds = age_seconds
        super().__init__(
            f"Stale data for {symbol} {bar_size}: "
            f"age {age_seconds:.1f}s exceeds limit"
        )


class DataQualityError(MarketDataError):
    """Market data failed quality validation."""
    def __init__(self, message: str, bar_data: Optional[Dict] = None):
        self.bar_data = bar_data
        super().__init__(message)


class SubscriptionError(MarketDataError):
    """Market data subscription failed."""
    def __init__(self, symbol: str, bar_size: str, error: str):
        self.symbol = symbol
        self.bar_size = bar_size
        super().__init__(f"Subscription failed for {symbol} {bar_size}: {error}")