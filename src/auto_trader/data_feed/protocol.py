"""Data feed provider protocol for simulation and live trading modes.

This module defines the abstract interface for market data providers.
The system is agnostic to the data source - whether live IBKR data
or file-based simulation data, the interface remains identical.
"""

from typing import Protocol, Callable, List, Dict, runtime_checkable

from auto_trader.models.market_data import BarData, BarSizeType


@runtime_checkable
class DataFeedProvider(Protocol):
    """Abstract interface for market data providers.

    Implementations must distribute BarData objects to registered
    subscribers. The system is agnostic to the data source.

    This protocol matches the public interface of MarketDataManager
    to ensure seamless substitution between live and simulated feeds.

    Methods:
        add_subscriber: Register a callback to receive BarData updates.
        remove_subscriber: Unregister a subscriber.
        start: Start feeding data to subscribers.
        stop: Stop feeding data.
        subscribe_symbols: Subscribe to specific symbols and timeframes.

    Example:
        >>> class MyFeed:
        ...     def add_subscriber(self, id: str, cb: Callable) -> None: ...
        ...     def remove_subscriber(self, id: str) -> bool: ...
        ...     async def start(self) -> None: ...
        ...     async def stop(self) -> None: ...
        ...     async def subscribe_symbols(self, symbols, sizes) -> dict: ...
        >>> isinstance(MyFeed(), DataFeedProvider)
        True
    """

    def add_subscriber(
        self, subscriber_id: str, callback: Callable[[BarData], None]
    ) -> None:
        """Register a callback to receive BarData updates.

        Args:
            subscriber_id: Unique identifier for the subscriber.
                Used for logging and to allow removal.
            callback: Function to call with each BarData update.
                The callback receives a single BarData argument.

        Note:
            If the same subscriber_id is registered twice,
            the second callback replaces the first.
        """
        ...

    def remove_subscriber(self, subscriber_id: str) -> bool:
        """Unregister a subscriber from receiving updates.

        Args:
            subscriber_id: The identifier used when registering.

        Returns:
            True if the subscriber was found and removed.
            False if no subscriber with that ID exists.
        """
        ...

    async def start(self) -> None:
        """Start feeding data to subscribers.

        For live feeds, this establishes connections and begins
        streaming data. For file-based feeds, this begins playback.

        This method is async to support connection establishment
        and other async initialization tasks.

        Raises:
            ConnectionError: If the data source cannot be reached.
        """
        ...

    async def stop(self) -> None:
        """Stop feeding data to subscribers.

        Gracefully stops the data feed. For live feeds, this
        closes connections. For file-based feeds, this stops playback.

        This method is async to support graceful shutdown.
        """
        ...

    async def subscribe_symbols(
        self, symbols: List[str], bar_sizes: List[BarSizeType]
    ) -> Dict[str, bool]:
        """Subscribe to specific symbols and timeframes.

        Args:
            symbols: List of trading symbols (e.g., ["SPY", "AAPL"]).
            bar_sizes: List of bar timeframes (e.g., ["5min", "15min"]).

        Returns:
            Dictionary mapping "symbol:bar_size" keys to success status.
            For example: {"SPY:5min": True, "AAPL:15min": False}

        Note:
            For file-based feeds, this may filter which bars are delivered
            based on the symbols in the data file.
        """
        ...
