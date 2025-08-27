"""Market data subscription management for IBKR integration."""

import asyncio
from datetime import UTC
from typing import Dict, List, Set, Optional, Callable, Any
from decimal import Decimal

from ib_async import IB, Stock, RealTimeBar, Contract
from loguru import logger

from auto_trader.models.market_data import (
    BarData, BarSizeType, BAR_SIZE_MAPPING,
    SubscriptionError
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
        self._callback = callback  # Kept for backward compatibility
        
        # Track active subscriptions
        self._subscriptions: Dict[str, Any] = {}  # key: "symbol:bar_size" -> subscription
        self._contracts: Dict[str, Contract] = {}  # symbol -> Contract
        self._active_symbols: Set[str] = set()
        
        # Market data distribution system
        self._subscribers: Dict[str, Callable[[BarData], None]] = {}  # subscriber_id -> callback
        self._execution_engine_callbacks: List[Callable[[BarData], None]] = []  # For execution engine integration
        
        # Statistics
        self._stats = {
            "bars_received": 0,
            "subscription_errors": 0,
            "data_quality_errors": 0,
            "distribution_errors": 0
        }
        
        logger.info("MarketDataManager initialized")
    
    def add_subscriber(self, subscriber_id: str, callback: Callable[[BarData], None]) -> None:
        """
        Add a subscriber to receive market data updates.
        
        Args:
            subscriber_id: Unique identifier for the subscriber
            callback: Function to call with BarData updates
        """
        self._subscribers[subscriber_id] = callback
        logger.info(
            "Market data subscriber added",
            subscriber_id=subscriber_id,
            total_subscribers=len(self._subscribers)
        )
    
    def remove_subscriber(self, subscriber_id: str) -> bool:
        """
        Remove a subscriber from market data updates.
        
        Args:
            subscriber_id: Unique identifier for the subscriber
            
        Returns:
            True if subscriber was found and removed, False otherwise
        """
        if subscriber_id in self._subscribers:
            del self._subscribers[subscriber_id]
            logger.info(
                "Market data subscriber removed",
                subscriber_id=subscriber_id,
                total_subscribers=len(self._subscribers)
            )
            return True
        return False
    
    def add_execution_engine_callback(self, callback: Callable[[BarData], None]) -> None:
        """
        Add an execution engine callback for market data updates.
        
        Args:
            callback: Function to call with BarData updates
        """
        self._execution_engine_callbacks.append(callback)
        logger.info(
            "Execution engine callback added",
            total_callbacks=len(self._execution_engine_callbacks)
        )
    
    def remove_execution_engine_callback(self, callback: Callable[[BarData], None]) -> bool:
        """
        Remove an execution engine callback.
        
        Args:
            callback: Function to remove
            
        Returns:
            True if callback was found and removed, False otherwise
        """
        try:
            self._execution_engine_callbacks.remove(callback)
            logger.info(
                "Execution engine callback removed",
                total_callbacks=len(self._execution_engine_callbacks)
            )
            return True
        except ValueError:
            return False
    
    async def _distribute_bar_data(self, bar_data: BarData) -> None:
        """
        Distribute bar data to all subscribers and execution engines.
        
        Args:
            bar_data: Bar data to distribute
        """
        distribution_count = 0
        errors = 0
        
        # Distribute to regular subscribers
        for subscriber_id, callback in self._subscribers.items():
            try:
                callback(bar_data)
                distribution_count += 1
            except Exception as e:
                errors += 1
                logger.error(
                    "Error in market data subscriber callback",
                    subscriber_id=subscriber_id,
                    error=str(e),
                    symbol=bar_data.symbol,
                    bar_size=bar_data.bar_size
                )
        
        # Distribute to execution engine callbacks
        for callback in self._execution_engine_callbacks:
            try:
                callback(bar_data)
                distribution_count += 1
            except Exception as e:
                errors += 1
                logger.error(
                    "Error in execution engine callback",
                    error=str(e),
                    symbol=bar_data.symbol,
                    bar_size=bar_data.bar_size
                )
        
        # Update statistics
        self._stats["distribution_errors"] += errors
        
        if distribution_count > 0:
            logger.debug(
                "Market data distributed",
                symbol=bar_data.symbol,
                bar_size=bar_data.bar_size,
                distributed_to=distribution_count,
                errors=errors
            )
    
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
                    
                    # Register callback with proper closure
                    def create_callback(s, bs):
                        return lambda bars: asyncio.create_task(self._on_bar_update(bars, s, bs))
                    
                    subscription.updateEvent += create_callback(symbol, bar_size)
                    
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
                logger.debug("No bars data provided", symbol=symbol, bar_size=bar_size)
                return
            
            # Convert IB bar to our BarData model
            latest_bar = bars[-1] if isinstance(bars, list) else bars
            
            # Handle timestamp - bars.time is already a datetime object
            timestamp = latest_bar.time
            if timestamp.tzinfo is None:
                # If no timezone info, assume UTC
                timestamp = timestamp.replace(tzinfo=UTC)
            elif timestamp.tzinfo != UTC:
                # Convert to UTC if different timezone
                timestamp = timestamp.astimezone(UTC)
            
            bar_data = BarData(
                symbol=symbol,
                timestamp=timestamp,
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
            
            # Distribute to all subscribers via new distribution system
            await self._distribute_bar_data(bar_data)
            
            # Call legacy callback if provided (for backward compatibility)
            if self._callback:
                try:
                    self._callback(bar_data)
                except Exception as e:
                    logger.error(
                        "Legacy callback error in market data handler",
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
            error_details = f"Error processing bar update - {type(e).__name__}: {str(e)}"
            if bars:
                error_details += f" | bars_type: {type(bars).__name__}"
                error_details += f" | bars_data: {str(bars)[:200]}..."  # Limit to first 200 chars
            else:
                error_details += " | bars_data: None"
            
            logger.error(
                error_details,
                symbol=symbol,
                bar_size=bar_size
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
            "distribution_errors": self._stats["distribution_errors"],
            "subscribers_count": len(self._subscribers),
            "execution_callbacks_count": len(self._execution_engine_callbacks),
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