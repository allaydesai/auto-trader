"""Tests for market data cache functionality."""

import pytest
import asyncio
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

from auto_trader.models.market_data import BarData, StaleDataError
from auto_trader.models.market_data_cache import MarketDataCache


@pytest.fixture
def sample_bar():
    """Create a sample bar for testing."""
    return BarData(
        symbol="AAPL",
        timestamp=datetime.now(UTC),
        open_price=Decimal("180.50"),
        high_price=Decimal("181.00"),
        low_price=Decimal("180.00"),
        close_price=Decimal("180.75"),
        volume=1000000,
        bar_size="5min"
    )


@pytest.fixture
def cache():
    """Create a market data cache instance."""
    return MarketDataCache(
        max_bars_per_symbol=100,
        cleanup_interval_hours=24,
        stale_data_multiplier=2
    )


class TestMarketDataCache:
    """Test MarketDataCache functionality."""
    
    @pytest.mark.asyncio
    async def test_update_bar(self, cache, sample_bar):
        """Test updating cache with new bar."""
        await cache.update_bar(sample_bar)
        
        latest = cache.get_latest_bar("AAPL", "5min", check_stale=False)
        assert latest == sample_bar
        assert cache._stats["bars_added"] == 1
    
    @pytest.mark.asyncio
    async def test_max_bars_enforcement(self, cache):
        """Test that max bars limit is enforced."""
        cache.max_bars_per_symbol = 5
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
            await cache.update_bar(bar)
        
        # Should only have 5 bars
        bars = cache.get_bars("AAPL", "5min")
        assert len(bars) == 5
        assert cache._stats["bars_added"] == 10
        assert cache._stats["bars_removed"] == 5
    
    def test_get_latest_bar_with_stale_check(self, cache):
        """Test getting latest bar with stale data check."""
        # Add an old bar
        old_bar = BarData(
            symbol="AAPL",
            timestamp=datetime.now(UTC) - timedelta(minutes=15),
            open_price=Decimal("180.50"),
            high_price=Decimal("181.00"),
            low_price=Decimal("180.00"),
            close_price=Decimal("180.75"),
            volume=1000,
            bar_size="5min"
        )
        
        # Manually add to cache to bypass async
        cache._cache.add_bar(old_bar)
        
        # Should raise StaleDataError
        with pytest.raises(StaleDataError) as exc_info:
            cache.get_latest_bar("AAPL", "5min", check_stale=True)
        
        assert exc_info.value.symbol == "AAPL"
        assert exc_info.value.bar_size == "5min"
        assert cache._stats["stale_data_detected"] == 1
    
    def test_get_latest_bar_without_stale_check(self, cache):
        """Test getting latest bar without stale check."""
        # Add an old bar
        old_bar = BarData(
            symbol="AAPL",
            timestamp=datetime.now(UTC) - timedelta(minutes=15),
            open_price=Decimal("180.50"),
            high_price=Decimal("181.00"),
            low_price=Decimal("180.00"),
            close_price=Decimal("180.75"),
            volume=1000,
            bar_size="5min"
        )
        
        cache._cache.add_bar(old_bar)
        
        # Should return bar without error
        latest = cache.get_latest_bar("AAPL", "5min", check_stale=False)
        assert latest == old_bar
        assert cache._stats["cache_hits"] == 1
    
    def test_cache_miss(self, cache):
        """Test cache miss statistics."""
        result = cache.get_latest_bar("NONEXISTENT", "5min", check_stale=False)
        assert result is None
        assert cache._stats["cache_misses"] == 1
    
    def test_get_bars_with_limit(self, cache):
        """Test getting bars with limit."""
        now = datetime.now(UTC)
        
        # Add multiple bars
        for i in range(10):
            bar = BarData(
                symbol="MSFT",
                timestamp=now - timedelta(minutes=i*5),
                open_price=Decimal("350.00"),
                high_price=Decimal("351.00"),
                low_price=Decimal("349.00"),
                close_price=Decimal("350.50"),
                volume=5000,
                bar_size="5min"
            )
            cache._cache.add_bar(bar)
        
        # Get limited bars
        bars = cache.get_bars("MSFT", "5min", limit=3)
        assert len(bars) == 3
        
        # Verify they are the most recent
        all_bars = cache.get_bars("MSFT", "5min")
        assert bars == all_bars[-3:]
    
    @pytest.mark.asyncio
    async def test_populate_historical(self, cache):
        """Test populating cache with historical data."""
        now = datetime.now(UTC)
        
        historical_bars = []
        for i in range(5):
            bar = BarData(
                symbol="GOOGL",
                timestamp=now - timedelta(minutes=i*5),
                open_price=Decimal("2800.00"),
                high_price=Decimal("2810.00"),
                low_price=Decimal("2790.00"),
                close_price=Decimal("2805.00"),
                volume=10000,
                bar_size="5min"
            )
            historical_bars.append(bar)
        
        await cache.populate_historical("GOOGL", historical_bars)
        
        bars = cache.get_bars("GOOGL", "5min")
        assert len(bars) == 5
        assert cache._stats["bars_added"] == 5
    
    @pytest.mark.asyncio
    async def test_cleanup_old_data(self, cache):
        """Test cleaning up old data."""
        now = datetime.now(UTC)
        
        # Add recent and old bars
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
        
        await cache.update_bar(recent_bar)
        await cache.update_bar(old_bar)
        
        removed = await cache.cleanup_old_data()
        
        assert removed == 1
        bars = cache.get_bars("AAPL", "5min")
        assert len(bars) == 1
        assert bars[0] == recent_bar
    
    def test_subscription_management(self, cache):
        """Test subscription tracking."""
        cache.add_subscription("AAPL")
        cache.add_subscription("MSFT")
        
        subscriptions = cache.get_active_subscriptions()
        assert "AAPL" in subscriptions
        assert "MSFT" in subscriptions
        assert len(subscriptions) == 2
        
        cache.remove_subscription("AAPL")
        subscriptions = cache.get_active_subscriptions()
        assert "AAPL" not in subscriptions
        assert "MSFT" in subscriptions
        assert len(subscriptions) == 1
    
    def test_remove_subscription_clears_data(self, cache):
        """Test that removing subscription clears associated data."""
        # Add bars for a symbol
        bar1 = BarData(
            symbol="AAPL",
            timestamp=datetime.now(UTC),
            open_price=Decimal("180.50"),
            high_price=Decimal("181.00"),
            low_price=Decimal("180.00"),
            close_price=Decimal("180.75"),
            volume=1000,
            bar_size="5min"
        )
        
        bar2 = BarData(
            symbol="AAPL",
            timestamp=datetime.now(UTC),
            open_price=Decimal("180.50"),
            high_price=Decimal("181.00"),
            low_price=Decimal("180.00"),
            close_price=Decimal("180.75"),
            volume=1000,
            bar_size="1min"
        )
        
        cache._cache.add_bar(bar1)
        cache._cache.add_bar(bar2)
        
        assert "AAPL:5min" in cache._cache.bars
        assert "AAPL:1min" in cache._cache.bars
        
        # Remove subscription
        cache.add_subscription("AAPL")
        cache.remove_subscription("AAPL")
        
        assert "AAPL:5min" not in cache._cache.bars
        assert "AAPL:1min" not in cache._cache.bars
    
    def test_memory_usage_stats(self, cache):
        """Test memory usage statistics."""
        now = datetime.now(UTC)
        
        # Add bars for multiple symbols
        symbols = ["AAPL", "MSFT"]
        for symbol in symbols:
            for i in range(5):
                bar = BarData(
                    symbol=symbol,
                    timestamp=now - timedelta(minutes=i*5),
                    open_price=Decimal("100.00"),
                    high_price=Decimal("101.00"),
                    low_price=Decimal("99.00"),
                    close_price=Decimal("100.50"),
                    volume=1000,
                    bar_size="5min"
                )
                cache._cache.add_bar(bar)
        
        cache.add_subscription("AAPL")
        cache.add_subscription("MSFT")
        
        usage = cache.get_memory_usage()
        
        assert usage["total_bars"] == 10
        assert usage["symbol_count"] == 2
        assert usage["subscription_count"] == 2
        assert "estimated_memory_mb" in usage
        assert usage["estimated_memory_mb"] > 0
        assert "cache_stats" in usage
    
    def test_clear_cache(self, cache):
        """Test clearing entire cache."""
        # Add some data
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
        
        cache._cache.add_bar(bar)
        assert cache._cache.get_total_bar_count() == 1
        
        cache.clear_cache()
        
        assert cache._cache.get_total_bar_count() == 0
        assert cache.get_latest_bar("AAPL", "5min", check_stale=False) is None
    
    def test_cache_summary(self, cache):
        """Test getting cache summary."""
        now = datetime.now(UTC)
        
        # Add bars for different symbols and timeframes
        for symbol in ["AAPL", "MSFT"]:
            for bar_size in ["1min", "5min"]:
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
                    cache._cache.add_bar(bar)
        
        summary = cache.get_cache_summary()
        
        assert summary["total_bars"] == 12
        assert len(summary["symbols"]) == 2
        assert "AAPL" in summary["symbols"]
        assert "MSFT" in summary["symbols"]
        assert "1min" in summary["symbols"]["AAPL"]
        assert "5min" in summary["symbols"]["AAPL"]
        assert summary["symbols"]["AAPL"]["1min"]["bar_count"] == 3
        assert "oldest_bar" in summary
        assert "newest_bar" in summary
    
    def test_thread_safety(self, cache):
        """Test that cache operations are thread-safe."""
        import threading
        
        def add_bars():
            for i in range(10):
                bar = BarData(
                    symbol="TEST",
                    timestamp=datetime.now(UTC),
                    open_price=Decimal("100.00"),
                    high_price=Decimal("101.00"),
                    low_price=Decimal("99.00"),
                    close_price=Decimal("100.50"),
                    volume=1000,
                    bar_size="1min"
                )
                cache._cache.add_bar(bar)
        
        # Run multiple threads
        threads = []
        for _ in range(5):
            t = threading.Thread(target=add_bars)
            threads.append(t)
            t.start()
        
        for t in threads:
            t.join()
        
        # Should have all bars without corruption
        assert cache._cache.get_total_bar_count() == 50