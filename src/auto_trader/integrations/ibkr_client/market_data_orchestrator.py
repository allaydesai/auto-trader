"""Market data subscription orchestration for IBKR integration."""

from typing import Dict, List, Set, Optional
from loguru import logger

from auto_trader.models.market_data import BarSizeType
from auto_trader.models.market_data_cache import MarketDataCache
from .subscription_manager import SubscriptionManager


class MarketDataOrchestrator:
    """
    Orchestrates high-level market data subscription workflows.
    
    Handles coordination between subscription manager and cache,
    manages subscription lifecycle, and provides business logic
    for subscription operations.
    """
    
    def __init__(self, subscription_manager: SubscriptionManager, cache: MarketDataCache):
        """
        Initialize market data orchestrator.
        
        Args:
            subscription_manager: Subscription management component
            cache: Market data cache component
        """
        self._subscription_manager = subscription_manager
        self._cache = cache
    
    async def orchestrate_subscriptions(
        self,
        symbols: List[str],
        bar_sizes: List[BarSizeType],
        callback_factory
    ) -> Dict[str, bool]:
        """
        Orchestrate subscription creation for multiple symbols and timeframes.
        
        Args:
            symbols: List of trading symbols
            bar_sizes: List of bar sizes to subscribe to
            callback_factory: Function to create callbacks for each symbol/bar_size
            
        Returns:
            Dictionary mapping symbol:bar_size to success status
        """
        results = {}
        
        for symbol in symbols:
            symbol_results = await self._subscribe_symbol_to_all_timeframes(
                symbol, bar_sizes, callback_factory
            )
            results.update(symbol_results)
        
        return results
    
    async def _subscribe_symbol_to_all_timeframes(
        self,
        symbol: str,
        bar_sizes: List[BarSizeType],
        callback_factory
    ) -> Dict[str, bool]:
        """
        Subscribe a single symbol to all specified timeframes.
        
        Args:
            symbol: Trading symbol
            bar_sizes: List of bar sizes
            callback_factory: Function to create callbacks
            
        Returns:
            Dictionary mapping symbol:bar_size keys to success status
        """
        results = {}
        
        for bar_size in bar_sizes:
            key = f"{symbol}:{bar_size}"
            callback = callback_factory(symbol, bar_size)
            
            success = await self._subscription_manager.create_subscription(
                symbol, bar_size, callback
            )
            
            results[key] = success
            
            # Update cache only on successful subscription
            if success:
                self._cache.add_subscription(symbol)
                logger.debug(f"Added cache subscription for {symbol}")
        
        return results
    
    async def orchestrate_symbol_sync(
        self, 
        required_symbols: Set[str], 
        callback_factory,
        default_bar_sizes: List[BarSizeType] = None
    ) -> None:
        """
        Orchestrate synchronization of subscriptions with required symbols.
        
        Args:
            required_symbols: Set of symbols that should be subscribed
            callback_factory: Function to create callbacks for new subscriptions
            default_bar_sizes: Bar sizes to use for new subscriptions
        """
        if default_bar_sizes is None:
            default_bar_sizes = ["5min"]
            
        current_symbols = self._subscription_manager.get_active_symbols()
        
        # Calculate changes needed
        symbols_to_add = required_symbols - current_symbols
        symbols_to_remove = current_symbols - required_symbols
        
        # Execute changes
        await self._handle_symbol_additions(symbols_to_add, callback_factory, default_bar_sizes)
        await self._handle_symbol_removals(symbols_to_remove)
    
    async def _handle_symbol_additions(
        self, 
        symbols_to_add: Set[str], 
        callback_factory,
        bar_sizes: List[BarSizeType]
    ) -> None:
        """
        Handle adding new symbol subscriptions.
        
        Args:
            symbols_to_add: Set of symbols to add
            callback_factory: Function to create callbacks
            bar_sizes: Bar sizes to subscribe to
        """
        if not symbols_to_add:
            return
            
        logger.info(
            "Adding new market data subscriptions",
            symbols=list(symbols_to_add)
        )
        
        # Actually create the subscriptions
        await self.orchestrate_subscriptions(
            list(symbols_to_add), bar_sizes, callback_factory
        )
    
    async def _handle_symbol_removals(self, symbols_to_remove: Set[str]) -> None:
        """
        Handle removing symbol subscriptions.
        
        Args:
            symbols_to_remove: Set of symbols to remove
        """
        if not symbols_to_remove:
            return
            
        logger.info(
            "Removing unused market data subscriptions",
            symbols=list(symbols_to_remove)
        )
        
        await self._subscription_manager.remove_subscriptions_for_symbols(
            list(symbols_to_remove)
        )
        
        # Clean up cache
        for symbol in symbols_to_remove:
            self._cache.remove_subscription(symbol)
    
    async def orchestrate_cleanup(self) -> None:
        """
        Orchestrate cleanup of all subscriptions and resources.
        """
        logger.info("Orchestrating market data cleanup")
        
        # Clean up subscription manager
        await self._subscription_manager.cleanup()
        
        # Clear cache
        self._cache.clear_cache()
        
        logger.info("Market data orchestration cleanup complete")
    
    def get_orchestration_stats(self) -> Dict[str, any]:
        """
        Get orchestration statistics combining all components.
        
        Returns:
            Dictionary of orchestration statistics
        """
        subscription_stats = self._subscription_manager.get_stats()
        cache_stats = self._cache.get_memory_usage()
        
        return {
            "orchestration_active": True,
            **subscription_stats,
            "cache_stats": cache_stats
        }