"""Subscription management utilities for IBKR market data."""

from typing import Dict, List, Set, Callable, Any

from ib_async import IB, Stock, Contract
from loguru import logger

from auto_trader.models.market_data import (
    BarSizeType, BAR_SIZE_MAPPING,
    SubscriptionError
)


class SubscriptionManager:
    """
    Manages IBKR market data subscriptions and contract handling.
    
    Handles creation, validation, and lifecycle of market data subscriptions
    including contract qualification and callback registration.
    """
    
    def __init__(self, ib_client: IB):
        """
        Initialize subscription manager.
        
        Args:
            ib_client: Connected IB client instance
        """
        self._ib = ib_client
        self._subscriptions: Dict[str, Any] = {}  # key: "symbol:bar_size" -> subscription
        self._contracts: Dict[str, Contract] = {}  # symbol -> Contract
        self._active_symbols: Set[str] = set()
        self._subscription_errors = 0
    
    async def create_subscription(
        self, 
        symbol: str, 
        bar_size: BarSizeType, 
        callback: Callable
    ) -> bool:
        """
        Create a single market data subscription.
        
        Args:
            symbol: Trading symbol
            bar_size: Bar timeframe
            callback: Callback for bar updates
            
        Returns:
            True if subscription successful, False otherwise
        """
        key = f"{symbol}:{bar_size}"
        
        try:
            if key in self._subscriptions:
                logger.debug(f"Already subscribed to {key}")
                return True
            
            # Validate bar size
            ib_bar_size = BAR_SIZE_MAPPING.get(bar_size)
            if not ib_bar_size:
                raise SubscriptionError(
                    symbol, bar_size,
                    f"Unsupported bar size: {bar_size}"
                )
            
            # Get or create contract
            contract = await self._get_or_create_contract(symbol)
            
            # Create subscription
            subscription = self._create_ib_subscription(contract)
            
            # Register callback
            subscription.updateEvent += callback
            
            # Track subscription
            self._subscriptions[key] = subscription
            self._active_symbols.add(symbol)
            
            logger.info(
                "Market data subscription created",
                symbol=symbol,
                bar_size=bar_size,
                key=key
            )
            
            return True
            
        except Exception as e:
            self._subscription_errors += 1
            
            logger.error(
                "Market data subscription failed",
                symbol=symbol,
                bar_size=bar_size,
                error=str(e)
            )
            
            return False
    
    async def remove_subscriptions_for_symbols(self, symbols: List[str]) -> None:
        """
        Remove all subscriptions for specified symbols.
        
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
            if symbol in self._contracts:
                del self._contracts[symbol]
    
    async def _get_or_create_contract(self, symbol: str) -> Contract:
        """
        Get existing contract or create and qualify new one.
        
        Args:
            symbol: Trading symbol
            
        Returns:
            Qualified contract
        """
        if symbol not in self._contracts:
            contract = Stock(symbol, "SMART", "USD")
            await self._ib.qualifyContractsAsync(contract)
            self._contracts[symbol] = contract
        
        return self._contracts[symbol]
    
    def _create_ib_subscription(self, contract: Contract) -> Any:
        """
        Create IBKR real-time bar subscription.
        
        Args:
            contract: Qualified contract
            
        Returns:
            IB subscription object
        """
        return self._ib.reqRealTimeBars(
            contract,
            5,  # 5 seconds for real-time bars
            "TRADES",
            False
        )
    
    def get_active_subscriptions(self) -> Dict[str, List[str]]:
        """
        Get currently active subscriptions grouped by symbol.
        
        Returns:
            Dictionary mapping symbols to list of subscribed bar sizes
        """
        subscriptions: Dict[str, List[str]] = {}
        
        for key in self._subscriptions.keys():
            symbol, bar_size = key.split(":")
            if symbol not in subscriptions:
                subscriptions[symbol] = []
            subscriptions[symbol].append(bar_size)
        
        return subscriptions
    
    def get_active_symbols(self) -> Set[str]:
        """Get set of currently active symbols."""
        return self._active_symbols.copy()
    
    def get_subscription_count(self) -> int:
        """Get total number of active subscriptions."""
        return len(self._subscriptions)
    
    def get_stats(self) -> Dict[str, int]:
        """Get subscription manager statistics."""
        return {
            "active_subscriptions": len(self._subscriptions),
            "active_symbols": len(self._active_symbols),
            "subscription_errors": self._subscription_errors
        }
    
    async def cleanup(self) -> None:
        """Clean up all subscriptions."""
        symbols_to_remove = list(self._active_symbols)
        if symbols_to_remove:
            await self.remove_subscriptions_for_symbols(symbols_to_remove)