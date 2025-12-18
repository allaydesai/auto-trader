"""IBKR-based data feed implementation.

This module provides the IBKRDataFeed class that wraps the existing
MarketDataManager to implement the DataFeedProvider protocol.
This enables the system to use IBKR for live market data while
maintaining interface compatibility with simulation feeds.
"""

from typing import Callable, List, Dict, Any

from loguru import logger
from ib_async import IB

from auto_trader.models.market_data import BarData, BarSizeType
from auto_trader.models.market_data_cache import MarketDataCache
from auto_trader.integrations.ibkr_client.market_data_manager import MarketDataManager


class IBKRDataFeed:
    """IBKR-based data feed implementing DataFeedProvider protocol.

    This class wraps the existing MarketDataManager to provide a consistent
    interface for market data feeds. It delegates all operations to the
    underlying MarketDataManager while adding protocol compliance.

    The wrapper ensures zero behavioral changes for live trading mode -
    all calls are passed directly to MarketDataManager without modification.

    Args:
        ib_client: Connected IB client instance.
        cache: Optional market data cache for bar storage.

    Example:
        >>> ib = IB()
        >>> await ib.connectAsync("127.0.0.1", 7497, clientId=1)
        >>> feed = IBKRDataFeed(ib)
        >>> feed.add_subscriber("orchestrator", process_bar)
        >>> await feed.start()
        >>> await feed.subscribe_symbols(["SPY"], ["5min"])
    """

    def __init__(self, ib_client: IB, cache: MarketDataCache | None = None) -> None:
        """Initialize IBKR data feed.

        Args:
            ib_client: Connected IB client instance.
            cache: Optional market data cache.
        """
        self._ib_client = ib_client
        self._manager = MarketDataManager(ib_client=ib_client, cache=cache)
        self._is_running = False

        logger.info("IBKRDataFeed initialized")

    @property
    def is_running(self) -> bool:
        """Check if the feed is currently running."""
        return self._is_running

    def add_subscriber(
        self, subscriber_id: str, callback: Callable[[BarData], None]
    ) -> None:
        """Register a callback to receive BarData updates.

        Delegates directly to MarketDataManager without modification.

        Args:
            subscriber_id: Unique identifier for the subscriber.
            callback: Function to call with each BarData update.
        """
        self._manager.add_subscriber(subscriber_id, callback)

    def remove_subscriber(self, subscriber_id: str) -> bool:
        """Unregister a subscriber from receiving updates.

        Delegates directly to MarketDataManager without modification.

        Args:
            subscriber_id: The identifier used when registering.

        Returns:
            True if subscriber was found and removed, False otherwise.
        """
        return self._manager.remove_subscriber(subscriber_id)

    async def start(self) -> None:
        """Start feeding data to subscribers.

        For IBKR, the feed is ready immediately after initialization
        since the IB client is already connected. This method sets the
        is_running flag but does not initiate data streaming.

        Note:
            Actual data streaming begins when subscribe_symbols() is called.
            This method exists to satisfy the DataFeedProvider protocol and
            maintain consistency with FileDataFeed behavior.
        """
        logger.info("Starting IBKRDataFeed")
        self._is_running = True
        logger.info("IBKRDataFeed started")

    async def stop(self) -> None:
        """Stop feeding data and clean up resources.

        Delegates cleanup to MarketDataManager.
        """
        logger.info("Stopping IBKRDataFeed")
        await self._manager.cleanup()
        self._is_running = False
        logger.info("IBKRDataFeed stopped")

    async def subscribe_symbols(
        self, symbols: List[str], bar_sizes: List[BarSizeType]
    ) -> Dict[str, bool]:
        """Subscribe to specific symbols and timeframes.

        Delegates directly to MarketDataManager without modification.

        Args:
            symbols: List of trading symbols.
            bar_sizes: List of bar timeframes.

        Returns:
            Dictionary mapping "symbol:bar_size" keys to success status.
        """
        return await self._manager.subscribe_symbols(symbols, bar_sizes)

    def get_stats(self) -> Dict[str, Any]:
        """Get data feed statistics.

        Returns:
            Dictionary with feed statistics including running state
            and underlying manager statistics.
        """
        stats = self._manager.get_stats()
        stats["is_running"] = self._is_running
        stats["feed_type"] = "ibkr"
        return stats

    def get_active_subscriptions(self) -> Dict[str, List[str]]:
        """Get currently active subscriptions grouped by symbol.

        Returns:
            Dictionary mapping symbols to their subscribed bar sizes.
        """
        return self._manager.get_active_subscriptions()

    def get_subscription_count(self) -> int:
        """Get total number of active subscriptions.

        Returns:
            Number of active symbol/bar_size subscriptions.
        """
        return self._manager.get_subscription_count()
