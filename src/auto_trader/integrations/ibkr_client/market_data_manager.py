"""Market data subscription management for IBKR integration."""

import asyncio
from typing import Dict, List, Set, Optional, Callable

from ib_async import IB, RealTimeBar
from loguru import logger

from auto_trader.models.market_data import BarData, BarSizeType
from auto_trader.models.market_data_cache import MarketDataCache
from .market_data_distribution import MarketDataDistributor
from .subscription_manager import SubscriptionManager
from .bar_converter import BarConverter


class MarketDataManager:
    """
    Manages real-time market data subscriptions and distribution.
    
    Coordinates subscription management, bar data conversion, and distribution
    using specialized helper components for clean separation of concerns.
    """
    
    def __init__(
        self,
        ib_client: IB,
        cache: Optional[MarketDataCache] = None
    ):
        """
        Initialize market data manager.
        
        Args:
            ib_client: Connected IB client instance
            cache: Optional market data cache
        """
        self._ib = ib_client
        self._cache = cache or MarketDataCache()
        
        # Initialize helper components
        self._distributor = MarketDataDistributor()
        self._subscription_manager = SubscriptionManager(ib_client)
        self._bar_converter = BarConverter()
        
        # Statistics
        self._bars_received = 0
        
        logger.info("MarketDataManager initialized")
    
    # Delegate subscription management to distributor
    def add_subscriber(self, subscriber_id: str, callback: Callable[[BarData], None]) -> None:
        """Add a subscriber to receive market data updates."""
        self._distributor.add_subscriber(subscriber_id, callback)
    
    def remove_subscriber(self, subscriber_id: str) -> bool:
        """Remove a subscriber from market data updates."""
        return self._distributor.remove_subscriber(subscriber_id)
    
    
    async def subscribe_symbols(
        self,
        symbols: List[str],
        bar_sizes: Optional[List[BarSizeType]] = None
    ) -> Dict[str, bool]:
        """
        Subscribe to real-time bars for multiple symbols.
        
        Args:
            symbols: List of trading symbols
            bar_sizes: Optional list of bar sizes, defaults to ["5min"]
            
        Returns:
            Dictionary mapping symbol:bar_size to success status
        """
        if not bar_sizes:
            bar_sizes = ["5min"]
        
        results = {}
        
        for symbol in symbols:
            for bar_size in bar_sizes:
                key = f"{symbol}:{bar_size}"
                callback = self._create_bar_callback(symbol, bar_size)
                success = await self._subscription_manager.create_subscription(
                    symbol, bar_size, callback
                )
                results[key] = success
                if success:
                    self._cache.add_subscription(symbol)
        
        return results
    
    def _create_bar_callback(self, symbol: str, bar_size: BarSizeType) -> Callable[[any], any]:
        """
        Create callback for bar updates.
        
        Args:
            symbol: Trading symbol
            bar_size: Bar timeframe
            
        Returns:
            Callback function for bar updates
        """
        async def handle_bar(bars):
            await self._on_bar_update(bars, symbol, bar_size)
        
        return lambda bars: asyncio.create_task(handle_bar(bars))
    
    async def unsubscribe_symbols(self, symbols: List[str]) -> None:
        """
        Unsubscribe from market data for specified symbols.
        
        Args:
            symbols: List of symbols to unsubscribe
        """
        await self._subscription_manager.remove_subscriptions_for_symbols(symbols)
        
        # Clean up cache
        for symbol in symbols:
            self._cache.remove_subscription(symbol)
    
    async def sync_with_active_plans(
        self,
        required_symbols: Set[str]
    ) -> None:
        """
        Sync subscriptions with currently required symbols.
        
        Args:
            required_symbols: Set of symbols that should be subscribed
        """
        current_symbols = self._subscription_manager.get_active_symbols()
        
        # Add new subscriptions
        new_symbols = required_symbols - current_symbols
        if new_symbols:
            logger.info(
                "Adding new market data subscriptions",
                symbols=list(new_symbols)
            )
            await self.subscribe_symbols(list(new_symbols))
        
        # Remove unused subscriptions
        unused_symbols = current_symbols - required_symbols
        if unused_symbols:
            logger.info(
                "Removing unused market data subscriptions",
                symbols=list(unused_symbols)
            )
            await self.unsubscribe_symbols(list(unused_symbols))
    
    async def _on_bar_update(
        self,
        bars: RealTimeBar,
        symbol: str,
        bar_size: BarSizeType
    ) -> None:
        """
        Handle real-time bar updates from IB.
        
        Args:
            bars: Real-time bar data from IB
            symbol: Trading symbol
            bar_size: Bar timeframe
        """
        try:
            if not bars:
                logger.debug("No bars data provided", symbol=symbol, bar_size=bar_size)
                return
            
            # Convert IB bar to our BarData model
            bar_data = self._bar_converter.convert_ib_bar_to_bar_data(bars, symbol, bar_size)
            
            # Update cache and statistics
            await self._cache.update_bar(bar_data)
            self._bars_received += 1
            
            # Distribute to all subscribers
            await self._distributor.distribute_bar_data(bar_data)
            
            logger.debug(
                "Bar update processed",
                symbol=symbol,
                bar_size=bar_size,
                close=str(bar_data.close_price),
                volume=bar_data.volume
            )
            
        except Exception as e:
            self._bar_converter.handle_bar_processing_error(e, bars, symbol, bar_size)
    
    def get_active_subscriptions(self) -> Dict[str, List[str]]:
        """Get currently active subscriptions grouped by symbol."""
        return self._subscription_manager.get_active_subscriptions()
    
    def get_subscription_count(self) -> int:
        """Get total number of active subscriptions."""
        return self._subscription_manager.get_subscription_count()
    
    def get_stats(self) -> Dict[str, any]:
        """Get market data manager statistics."""
        stats = {
            "bars_received": self._bars_received,
            "cache_stats": self._cache.get_memory_usage()
        }
        
        # Merge stats from components
        stats.update(self._subscription_manager.get_stats())
        stats.update(self._distributor.get_stats())
        stats.update(self._bar_converter.get_stats())
        
        return stats
    
    async def cleanup(self) -> None:
        """Clean up all subscriptions and resources."""
        logger.info("Cleaning up market data subscriptions")
        
        # Clean up subscription manager
        await self._subscription_manager.cleanup()
        
        # Clear cache
        self._cache.clear_cache()
        
        logger.info(
            "Market data cleanup complete",
            bars_received=self._bars_received
        )