"""In-memory cache for market data with automatic cleanup and memory management."""

import asyncio
from datetime import datetime, UTC
from typing import Dict, List, Optional, Set, Any
from threading import RLock
from loguru import logger

from auto_trader.models.market_data import (
    BarData, MarketData, BarSizeType, StaleDataError
)


class MarketDataCache:
    """Thread-safe in-memory cache for market data with memory management."""
    
    def __init__(
        self, 
        max_bars_per_symbol: int = 1000,
        cleanup_interval_hours: int = 24,
        stale_data_multiplier: int = 2
    ):
        """Initialize market data cache.
        
        Args:
            max_bars_per_symbol: Maximum bars to keep per symbol/timeframe
            cleanup_interval_hours: Hours to retain intraday bars
            stale_data_multiplier: Multiplier for stale data detection
        """
        self._cache = MarketData()
        self._lock = RLock()
        self._subscriptions: Set[str] = set()
        self.max_bars_per_symbol = max_bars_per_symbol
        self.cleanup_interval_hours = cleanup_interval_hours
        self.stale_data_multiplier = stale_data_multiplier
        
        # Track cache statistics
        self._stats = {
            "bars_added": 0,
            "bars_removed": 0,
            "cache_hits": 0,
            "cache_misses": 0,
            "stale_data_detected": 0
        }
        
        logger.info(
            "MarketDataCache initialized",
            max_bars_per_symbol=max_bars_per_symbol,
            cleanup_interval_hours=cleanup_interval_hours
        )
    
    async def update_bar(self, bar: BarData) -> None:
        """Update cache with new bar data.
        
        Args:
            bar: New bar data to add to cache
        """
        with self._lock:
            key = f"{bar.symbol}:{bar.bar_size}"
            
            # Add bar to cache
            self._cache.add_bar(bar)
            self._stats["bars_added"] += 1
            
            # Enforce max bars limit
            if key in self._cache.bars:
                excess = len(self._cache.bars[key]) - self.max_bars_per_symbol
                if excess > 0:
                    self._cache.bars[key] = self._cache.bars[key][-self.max_bars_per_symbol:]
                    self._stats["bars_removed"] += excess
                    
                    logger.debug(
                        "Trimmed excess bars",
                        symbol=bar.symbol,
                        bar_size=bar.bar_size,
                        removed=excess
                    )
    
    def get_latest_bar(
        self, 
        symbol: str, 
        bar_size: BarSizeType,
        check_stale: bool = True
    ) -> Optional[BarData]:
        """Retrieve latest bar for symbol and timeframe.
        
        Args:
            symbol: Trading symbol
            bar_size: Bar timeframe
            check_stale: Whether to check for stale data
            
        Returns:
            Latest bar or None if not found
            
        Raises:
            StaleDataError: If data is stale and check_stale=True
        """
        with self._lock:
            if check_stale and self.is_data_stale(symbol, bar_size):
                self._stats["stale_data_detected"] += 1
                latest_bar = self._cache.get_latest_bar(symbol, bar_size)
                if latest_bar:
                    age = (datetime.now(UTC) - latest_bar.timestamp).total_seconds()
                    raise StaleDataError(symbol, bar_size, age)
                return None
            
            bar = self._cache.get_latest_bar(symbol, bar_size)
            if bar:
                self._stats["cache_hits"] += 1
            else:
                self._stats["cache_misses"] += 1
            
            return bar
    
    def get_bars(
        self,
        symbol: str,
        bar_size: BarSizeType,
        limit: Optional[int] = None
    ) -> List[BarData]:
        """Get historical bars for symbol and timeframe.
        
        Args:
            symbol: Trading symbol
            bar_size: Bar timeframe
            limit: Maximum number of bars to return
            
        Returns:
            List of bars in chronological order
        """
        with self._lock:
            bars = self._cache.get_bars(symbol, bar_size, limit)
            if bars:
                self._stats["cache_hits"] += 1
            else:
                self._stats["cache_misses"] += 1
            return bars
    
    def is_data_stale(self, symbol: str, bar_size: BarSizeType) -> bool:
        """Check if cached data is stale.
        
        Args:
            symbol: Trading symbol
            bar_size: Bar timeframe
            
        Returns:
            True if data is stale or missing
        """
        with self._lock:
            return self._cache.is_stale(
                symbol, 
                bar_size, 
                self.stale_data_multiplier
            )
    
    async def populate_historical(
        self, 
        symbol: str,
        bars: List[BarData]
    ) -> None:
        """Populate cache with historical bars.
        
        Args:
            symbol: Trading symbol
            bars: Historical bars to add
        """
        with self._lock:
            for bar in bars:
                await self.update_bar(bar)
            
            logger.info(
                "Historical data populated",
                symbol=symbol,
                bar_count=len(bars)
            )
    
    async def cleanup_old_data(self) -> int:
        """Remove stale data to manage memory usage.
        
        Returns:
            Number of bars removed
        """
        with self._lock:
            removed = self._cache.remove_old_bars(self.cleanup_interval_hours)
            self._stats["bars_removed"] += removed
            
            if removed > 0:
                logger.info(
                    "Cache cleanup completed",
                    bars_removed=removed,
                    total_bars=self._cache.get_total_bar_count()
                )
            
            return removed
    
    def add_subscription(self, symbol: str) -> None:
        """Track active subscription.
        
        Args:
            symbol: Symbol being subscribed to
        """
        with self._lock:
            self._subscriptions.add(symbol)
            logger.debug("Subscription added", symbol=symbol)
    
    def remove_subscription(self, symbol: str) -> None:
        """Remove subscription tracking.
        
        Args:
            symbol: Symbol to unsubscribe
        """
        with self._lock:
            self._subscriptions.discard(symbol)
            
            # Clear cache data for unsubscribed symbol
            keys_to_remove = [
                key for key in self._cache.bars.keys()
                if key.startswith(f"{symbol}:")
            ]
            
            for key in keys_to_remove:
                bars_removed = len(self._cache.bars[key])
                del self._cache.bars[key]
                self._stats["bars_removed"] += bars_removed
            
            logger.debug(
                "Subscription removed",
                symbol=symbol,
                cache_cleared=len(keys_to_remove) > 0
            )
    
    def get_active_subscriptions(self) -> Set[str]:
        """Get set of actively subscribed symbols.
        
        Returns:
            Set of symbol names
        """
        with self._lock:
            return self._subscriptions.copy()
    
    def get_memory_usage(self) -> Dict[str, Any]:
        """Get cache memory usage statistics.
        
        Returns:
            Dictionary with memory usage metrics
        """
        with self._lock:
            total_bars = self._cache.get_total_bar_count()
            symbol_count = self._cache.get_symbol_count()
            
            # Estimate memory usage (rough calculation)
            # Each bar ~200 bytes (including Python object overhead)
            estimated_memory_bytes = total_bars * 200
            estimated_memory_mb = round(estimated_memory_bytes / (1024.0 * 1024.0), 4)
            
            return {
                "total_bars": total_bars,
                "symbol_count": symbol_count,
                "subscription_count": len(self._subscriptions),
                "estimated_memory_mb": estimated_memory_mb,
                "cache_stats": self._stats.copy(),
                "last_updated": self._cache.last_updated.isoformat()
            }
    
    def clear_cache(self) -> None:
        """Clear all cached data."""
        with self._lock:
            bars_removed = self._cache.get_total_bar_count()
            self._cache = MarketData()
            self._stats["bars_removed"] += bars_removed
            
            logger.info(
                "Cache cleared",
                bars_removed=bars_removed
            )
    
    def get_cache_summary(self) -> Dict[str, Any]:
        """Get summary of cache contents.
        
        Returns:
            Summary dictionary with cache metrics
        """
        with self._lock:
            summary = {
                "symbols": {},
                "total_bars": 0,
                "oldest_bar": None,
                "newest_bar": None
            }
            
            for key, bars in self._cache.bars.items():
                if bars:
                    symbol, bar_size = key.split(":")
                    if symbol not in summary["symbols"]:
                        summary["symbols"][symbol] = {}
                    
                    summary["symbols"][symbol][bar_size] = {
                        "bar_count": len(bars),
                        "oldest": bars[0].timestamp.isoformat(),
                        "newest": bars[-1].timestamp.isoformat()
                    }
                    
                    summary["total_bars"] += len(bars)
                    
                    # Track overall oldest/newest
                    if not summary["oldest_bar"] or bars[0].timestamp < datetime.fromisoformat(summary["oldest_bar"]):
                        summary["oldest_bar"] = bars[0].timestamp.isoformat()
                    if not summary["newest_bar"] or bars[-1].timestamp > datetime.fromisoformat(summary["newest_bar"]):
                        summary["newest_bar"] = bars[-1].timestamp.isoformat()
            
            return summary