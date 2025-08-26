"""Tests for market data models."""

import pytest
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from pydantic import ValidationError

from auto_trader.models.market_data import (
    BarData, MarketData, StaleDataError, DataQualityError,
    BAR_SIZE_MAPPING, BAR_SIZE_SECONDS
)


class TestBarData:
    """Test BarData model validation and functionality."""
    
    def test_valid_bar_creation(self):
        """Test creating a valid bar."""
        bar = BarData(
            symbol="AAPL",
            timestamp=datetime.now(UTC),
            open_price=Decimal("180.50"),
            high_price=Decimal("181.00"),
            low_price=Decimal("180.00"),
            close_price=Decimal("180.75"),
            volume=1000000,
            bar_size="5min"
        )
        
        assert bar.symbol == "AAPL"
        assert bar.open_price == Decimal("180.50")
        assert bar.high_price == Decimal("181.00")
        assert bar.low_price == Decimal("180.00")
        assert bar.close_price == Decimal("180.75")
        assert bar.volume == 1000000
        assert bar.bar_size == "5min"
    
    def test_timezone_enforcement(self):
        """Test that timestamps are converted to UTC."""
        # Create with non-UTC timezone
        import pytz
        eastern = pytz.timezone('US/Eastern')
        eastern_time = datetime.now(eastern)
        
        bar = BarData(
            symbol="AAPL",
            timestamp=eastern_time,
            open_price=Decimal("180.50"),
            high_price=Decimal("181.00"),
            low_price=Decimal("180.00"),
            close_price=Decimal("180.75"),
            volume=1000,
            bar_size="1min"
        )
        
        assert bar.timestamp.tzinfo == UTC
    
    def test_timezone_naive_rejection(self):
        """Test that timezone-naive timestamps are rejected."""
        with pytest.raises(ValidationError, match="Timestamp must be timezone-aware"):
            BarData(
                symbol="AAPL",
                timestamp=datetime.now(),  # No timezone
                open_price=Decimal("180.50"),
                high_price=Decimal("181.00"),
                low_price=Decimal("180.00"),
                close_price=Decimal("180.75"),
                volume=1000,
                bar_size="1min"
            )
    
    def test_ohlc_validation_high_low(self):
        """Test OHLC consistency validation for high/low."""
        # High < Low should fail (but also must be >= max(open, close))
        with pytest.raises(ValidationError, match="High price.*must be >= max"):
            BarData(
                symbol="AAPL",
                timestamp=datetime.now(UTC),
                open_price=Decimal("180.50"),
                high_price=Decimal("179.00"),  # Lower than low AND lower than open/close
                low_price=Decimal("180.00"),
                close_price=Decimal("180.75"),
                volume=1000,
                bar_size="5min"
            )
    
    def test_ohlc_validation_high_range(self):
        """Test that high must be >= max(open, close)."""
        # High < close should fail
        with pytest.raises(ValidationError, match="High price.*must be >= max"):
            BarData(
                symbol="AAPL",
                timestamp=datetime.now(UTC),
                open_price=Decimal("180.50"),
                high_price=Decimal("180.60"),  # Lower than close
                low_price=Decimal("180.00"),
                close_price=Decimal("180.75"),
                volume=1000,
                bar_size="5min"
            )
    
    def test_ohlc_validation_low_range(self):
        """Test that low must be <= min(open, close)."""
        # Low > open should fail
        with pytest.raises(ValidationError, match="Low price.*must be <= min"):
            BarData(
                symbol="AAPL",
                timestamp=datetime.now(UTC),
                open_price=Decimal("180.50"),
                high_price=Decimal("181.00"),
                low_price=Decimal("180.60"),  # Higher than open
                close_price=Decimal("180.75"),
                volume=1000,
                bar_size="5min"
            )
    
    def test_negative_price_rejection(self):
        """Test that negative prices are rejected."""
        with pytest.raises(ValidationError, match="greater than 0"):
            BarData(
                symbol="AAPL",
                timestamp=datetime.now(UTC),
                open_price=Decimal("-180.50"),
                high_price=Decimal("181.00"),
                low_price=Decimal("180.00"),
                close_price=Decimal("180.75"),
                volume=1000,
                bar_size="5min"
            )
    
    def test_negative_volume_rejection(self):
        """Test that negative volume is rejected."""
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            BarData(
                symbol="AAPL",
                timestamp=datetime.now(UTC),
                open_price=Decimal("180.50"),
                high_price=Decimal("181.00"),
                low_price=Decimal("180.00"),
                close_price=Decimal("180.75"),
                volume=-1000,
                bar_size="5min"
            )
    
    def test_invalid_bar_size_rejection(self):
        """Test that invalid bar sizes are rejected."""
        with pytest.raises(ValidationError):
            BarData(
                symbol="AAPL",
                timestamp=datetime.now(UTC),
                open_price=Decimal("180.50"),
                high_price=Decimal("181.00"),
                low_price=Decimal("180.00"),
                close_price=Decimal("180.75"),
                volume=1000,
                bar_size="invalid"
            )
    
    def test_all_bar_sizes(self):
        """Test all supported bar sizes."""
        for bar_size in BAR_SIZE_MAPPING.keys():
            bar = BarData(
                symbol="AAPL",
                timestamp=datetime.now(UTC),
                open_price=Decimal("180.50"),
                high_price=Decimal("181.00"),
                low_price=Decimal("180.00"),
                close_price=Decimal("180.75"),
                volume=1000,
                bar_size=bar_size
            )
            assert bar.bar_size == bar_size
    
    def test_to_dict_serialization(self):
        """Test dictionary serialization."""
        bar = BarData(
            symbol="AAPL",
            timestamp=datetime.now(UTC),
            open_price=Decimal("180.50"),
            high_price=Decimal("181.00"),
            low_price=Decimal("180.00"),
            close_price=Decimal("180.75"),
            volume=1000,
            bar_size="5min"
        )
        
        data = bar.to_dict()
        assert data["symbol"] == "AAPL"
        assert data["open"] == "180.50"
        assert data["high"] == "181.00"
        assert data["low"] == "180.00"
        assert data["close"] == "180.75"
        assert data["volume"] == 1000
        assert data["bar_size"] == "5min"
        assert "timestamp" in data


class TestMarketData:
    """Test MarketData container functionality."""
    
    def test_add_bar(self):
        """Test adding bars to market data."""
        market_data = MarketData()
        
        bar = BarData(
            symbol="AAPL",
            timestamp=datetime.now(UTC),
            open_price=Decimal("180.50"),
            high_price=Decimal("181.00"),
            low_price=Decimal("180.00"),
            close_price=Decimal("180.75"),
            volume=1000,
            bar_size="5min"
        )
        
        market_data.add_bar(bar)
        
        assert "AAPL:5min" in market_data.bars
        assert len(market_data.bars["AAPL:5min"]) == 1
        assert market_data.bars["AAPL:5min"][0] == bar
    
    def test_bars_chronological_order(self):
        """Test that bars are maintained in chronological order."""
        market_data = MarketData()
        now = datetime.now(UTC)
        
        # Add bars out of order
        bar2 = BarData(
            symbol="AAPL",
            timestamp=now,
            open_price=Decimal("181.00"),
            high_price=Decimal("181.50"),
            low_price=Decimal("180.50"),
            close_price=Decimal("181.25"),
            volume=2000,
            bar_size="5min"
        )
        
        bar1 = BarData(
            symbol="AAPL",
            timestamp=now - timedelta(minutes=5),
            open_price=Decimal("180.50"),
            high_price=Decimal("181.00"),
            low_price=Decimal("180.00"),
            close_price=Decimal("180.75"),
            volume=1000,
            bar_size="5min"
        )
        
        market_data.add_bar(bar2)
        market_data.add_bar(bar1)
        
        bars = market_data.bars["AAPL:5min"]
        assert bars[0].timestamp < bars[1].timestamp
    
    def test_get_latest_bar(self):
        """Test retrieving the latest bar."""
        market_data = MarketData()
        now = datetime.now(UTC)
        
        older_bar = BarData(
            symbol="AAPL",
            timestamp=now - timedelta(minutes=5),
            open_price=Decimal("180.50"),
            high_price=Decimal("181.00"),
            low_price=Decimal("180.00"),
            close_price=Decimal("180.75"),
            volume=1000,
            bar_size="5min"
        )
        
        newer_bar = BarData(
            symbol="AAPL",
            timestamp=now,
            open_price=Decimal("181.00"),
            high_price=Decimal("181.50"),
            low_price=Decimal("180.50"),
            close_price=Decimal("181.25"),
            volume=2000,
            bar_size="5min"
        )
        
        market_data.add_bar(older_bar)
        market_data.add_bar(newer_bar)
        
        latest = market_data.get_latest_bar("AAPL", "5min")
        assert latest == newer_bar
    
    def test_get_bars_with_limit(self):
        """Test retrieving bars with limit."""
        market_data = MarketData()
        now = datetime.now(UTC)
        
        # Add 10 bars
        for i in range(10):
            bar = BarData(
                symbol="AAPL",
                timestamp=now - timedelta(minutes=i*5),
                open_price=Decimal("180.50"),
                high_price=Decimal("181.00"),
                low_price=Decimal("180.00"),
                close_price=Decimal(f"180.{50+i}"),
                volume=1000 + i,
                bar_size="5min"
            )
            market_data.add_bar(bar)
        
        # Get last 5 bars
        bars = market_data.get_bars("AAPL", "5min", limit=5)
        assert len(bars) == 5
        
        # Verify they are the most recent 5
        all_bars = market_data.get_bars("AAPL", "5min")
        assert bars == all_bars[-5:]
    
    def test_is_stale_detection(self):
        """Test stale data detection."""
        market_data = MarketData()
        now = datetime.now(UTC)
        
        # Add a bar that's 15 minutes old
        old_bar = BarData(
            symbol="AAPL",
            timestamp=now - timedelta(minutes=15),
            open_price=Decimal("180.50"),
            high_price=Decimal("181.00"),
            low_price=Decimal("180.00"),
            close_price=Decimal("180.75"),
            volume=1000,
            bar_size="5min"
        )
        
        market_data.add_bar(old_bar)
        
        # With 2x multiplier, 5min bar is stale after 10 minutes
        assert market_data.is_stale("AAPL", "5min", max_age_multiplier=2) is True
        
        # With higher multiplier, it's not stale
        assert market_data.is_stale("AAPL", "5min", max_age_multiplier=4) is False
    
    def test_remove_old_bars(self):
        """Test removing old bars."""
        market_data = MarketData()
        now = datetime.now(UTC)
        
        # Add bars of different ages
        recent_bar = BarData(
            symbol="AAPL",
            timestamp=now - timedelta(hours=1),
            open_price=Decimal("180.50"),
            high_price=Decimal("181.00"),
            low_price=Decimal("180.00"),
            close_price=Decimal("180.75"),
            volume=1000,
            bar_size="5min"
        )
        
        old_bar = BarData(
            symbol="AAPL",
            timestamp=now - timedelta(hours=25),
            open_price=Decimal("179.50"),
            high_price=Decimal("180.00"),
            low_price=Decimal("179.00"),
            close_price=Decimal("179.75"),
            volume=2000,
            bar_size="5min"
        )
        
        market_data.add_bar(recent_bar)
        market_data.add_bar(old_bar)
        
        assert len(market_data.bars["AAPL:5min"]) == 2
        
        # Remove bars older than 24 hours
        removed = market_data.remove_old_bars(max_age_hours=24)
        
        assert removed == 1
        assert len(market_data.bars["AAPL:5min"]) == 1
        assert market_data.bars["AAPL:5min"][0] == recent_bar
    
    def test_symbol_and_bar_counting(self):
        """Test counting symbols and bars."""
        market_data = MarketData()
        now = datetime.now(UTC)
        
        # Add bars for different symbols and timeframes
        symbols = ["AAPL", "MSFT", "GOOGL"]
        bar_sizes = ["1min", "5min"]
        
        for symbol in symbols:
            for bar_size in bar_sizes:
                for i in range(3):
                    bar = BarData(
                        symbol=symbol,
                        timestamp=now - timedelta(minutes=i*5),
                        open_price=Decimal("100.00"),
                        high_price=Decimal("101.00"),
                        low_price=Decimal("99.00"),
                        close_price=Decimal("100.50"),
                        volume=1000,
                        bar_size=bar_size
                    )
                    market_data.add_bar(bar)
        
        assert market_data.get_symbol_count() == 3
        assert market_data.get_total_bar_count() == 18  # 3 symbols * 2 timeframes * 3 bars


class TestMarketDataExceptions:
    """Test custom exception classes."""
    
    def test_stale_data_error(self):
        """Test StaleDataError creation."""
        error = StaleDataError("AAPL", "5min", 1200.5)
        assert error.symbol == "AAPL"
        assert error.bar_size == "5min"
        assert error.age_seconds == 1200.5
        assert "Stale data for AAPL 5min" in str(error)
    
    def test_data_quality_error(self):
        """Test DataQualityError creation."""
        bar_data = {"symbol": "AAPL", "issue": "invalid OHLC"}
        error = DataQualityError("Invalid OHLC relationship", bar_data)
        assert error.bar_data == bar_data
        assert "Invalid OHLC relationship" in str(error)