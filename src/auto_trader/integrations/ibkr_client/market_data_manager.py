"""Market data subscription management for IBKR integration."""

import asyncio
from datetime import datetime, UTC
from typing import Dict, List, Set, Optional, Callable, Any
from decimal import Decimal

from ib_async import IB, Stock, BarDataList, RealTimeBar, Contract
from loguru import logger

from auto_trader.models.market_data import (
    BarData, MarketData, BarSizeType, BAR_SIZE_MAPPING,
    SubscriptionError, DataQualityError
)
from auto_trader.models.market_data_cache import MarketDataCache


class MarketDataManager:
    """
    Manages real-time market data subscriptions and distribution.
    
    Provides subscription management for multiple symbols and timeframes,
    handles real-time bar updates, and distributes data to consumers.
    """
    
    def __init__(
        self,
        ib_client: IB,
        cache: Optional[MarketDataCache] = None,
        callback: Optional[Callable[[BarData], None]] = None
    ):
        """
        Initialize market data manager.
        
        Args:
            ib_client: Connected IB client instance
            cache: Optional market data cache
            callback: Optional callback for bar updates
        """
        self._ib = ib_client
        self._cache = cache or MarketDataCache()
        self._callback = callback
        
        # Track active subscriptions
        self._subscriptions: Dict[str, Any] = {}  # key: "symbol:bar_size" -> subscription
        self._contracts: Dict[str, Contract] = {}  # symbol -> Contract
        self._active_symbols: Set[str] = set()
        
        # Statistics
        self._stats = {
            "bars_received": 0,
            "subscription_errors": 0,
            "data_quality_errors": 0
        }
        
        logger.info("MarketDataManager initialized")
    
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
                
                try:
                    if key in self._subscriptions:
                        logger.debug(f"Already subscribed to {key}")
                        results[key] = True
                        continue
                    
                    # Convert bar size to IB format
                    ib_bar_size = BAR_SIZE_MAPPING.get(bar_size)
                    if not ib_bar_size:
                        raise SubscriptionError(
                            symbol, bar_size,
                            f"Unsupported bar size: {bar_size}"
                        )
                    
                    # Get or create contract
                    if symbol not in self._contracts:
                        contract = Stock(symbol, "SMART", "USD")
                        await self._ib.qualifyContractsAsync(contract)
                        self._contracts[symbol] = contract
                    
                    # Subscribe to real-time bars
                    subscription = self._ib.reqRealTimeBars(
                        self._contracts[symbol],
                        5,  # 5 seconds for real-time bars
                        "TRADES",
                        False
                    )
                    
                    # Register callback
                    subscription.updateEvent += lambda bars, symbol=symbol, bar_size=bar_size: \
                        asyncio.create_task(self._on_bar_update(bars, symbol, bar_size))
                    
                    self._subscriptions[key] = subscription
                    self._active_symbols.add(symbol)
                    self._cache.add_subscription(symbol)
                    
                    results[key] = True
                    
                    logger.info(
                        "Market data subscription started",
                        symbol=symbol,
                        bar_size=bar_size,
                        key=key
                    )
                    
                except Exception as e:
                    self._stats["subscription_errors"] += 1
                    results[key] = False
                    
                    logger.error(
                        "Market data subscription failed",
                        symbol=symbol,
                        bar_size=bar_size,
                        error=str(e)
                    )
        
        return results
    
    async def unsubscribe_symbols(self, symbols: List[str]) -> None:
        """
        Unsubscribe from market data for specified symbols.
        
        Args:
            symbols: List of symbols to unsubscribe
        """
        for symbol in symbols:
            # Find all subscriptions for this symbol
            keys_to_remove = [
                key for key in self._subscriptions.keys()
                if key.startswith(f"{symbol}:")
            ]
            
            for key in keys_to_remove:
                try:
                    subscription = self._subscriptions[key]
                    self._ib.cancelRealTimeBars(subscription)
                    del self._subscriptions[key]
                    
                    logger.info(
                        "Market data subscription cancelled",
                        key=key
                    )
                    
                except Exception as e:
                    logger.error(
                        "Error cancelling subscription",
                        key=key,
                        error=str(e)
                    )
            
            # Clean up symbol tracking
            self._active_symbols.discard(symbol)
            self._cache.remove_subscription(symbol)
            if symbol in self._contracts:
                del self._contracts[symbol]
    
    async def sync_with_active_plans(
        self,
        required_symbols: Set[str]
    ) -> None:
        """
        Sync subscriptions with currently required symbols.
        
        Args:
            required_symbols: Set of symbols that should be subscribed
        """
        current_symbols = self._active_symbols.copy()
        
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
                return
            
            # Convert IB bar to our BarData model
            latest_bar = bars[-1] if isinstance(bars, list) else bars
            
            bar_data = BarData(
                symbol=symbol,
                timestamp=datetime.fromtimestamp(latest_bar.time, UTC),
                open_price=Decimal(str(latest_bar.open_)),
                high_price=Decimal(str(latest_bar.high)),
                low_price=Decimal(str(latest_bar.low)),
                close_price=Decimal(str(latest_bar.close)),
                volume=int(latest_bar.volume),
                bar_size=bar_size
            )
            
            # Update cache
            await self._cache.update_bar(bar_data)
            self._stats["bars_received"] += 1
            
            # Call external callback if provided
            if self._callback:
                try:
                    self._callback(bar_data)
                except Exception as e:
                    logger.error(
                        "Callback error in market data handler",
                        error=str(e)
                    )
            
            logger.debug(
                "Bar update processed",
                symbol=symbol,
                bar_size=bar_size,
                close=str(bar_data.close_price),
                volume=bar_data.volume
            )
            
        except Exception as e:
            self._stats["data_quality_errors"] += 1
            logger.error(
                "Error processing bar update",
                symbol=symbol,
                bar_size=bar_size,
                error=str(e)
            )
    
    def get_active_subscriptions(self) -> Dict[str, List[str]]:
        """
        Get currently active subscriptions grouped by symbol.
        
        Returns:
            Dictionary mapping symbols to list of subscribed bar sizes
        """
        subscriptions = {}
        
        for key in self._subscriptions.keys():
            symbol, bar_size = key.split(":")
            if symbol not in subscriptions:
                subscriptions[symbol] = []
            subscriptions[symbol].append(bar_size)
        
        return subscriptions
    
    def get_subscription_count(self) -> int:
        """Get total number of active subscriptions."""
        return len(self._subscriptions)
    
    def get_stats(self) -> Dict[str, Any]:
        """Get market data manager statistics."""
        return {
            "active_subscriptions": len(self._subscriptions),
            "active_symbols": len(self._active_symbols),
            "bars_received": self._stats["bars_received"],
            "subscription_errors": self._stats["subscription_errors"],
            "data_quality_errors": self._stats["data_quality_errors"],
            "cache_stats": self._cache.get_memory_usage()
        }
    
    async def cleanup(self) -> None:
        """Clean up all subscriptions and resources."""
        logger.info("Cleaning up market data subscriptions")
        
        # Cancel all subscriptions
        symbols_to_remove = list(self._active_symbols)
        if symbols_to_remove:
            await self.unsubscribe_symbols(symbols_to_remove)
        
        # Clear cache
        self._cache.clear_cache()
        
        logger.info(
            "Market data cleanup complete",
            bars_received=self._stats["bars_received"]
        )