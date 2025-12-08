"""File-based data feed for simulation mode.

This module provides the FileDataFeed class that reads market data from
CSV, YAML, or JSON files and delivers it to subscribers as BarData objects,
simulating live market data flow.
"""

import asyncio
import csv
import json
from datetime import datetime, UTC
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Callable, List, Dict, Any

import yaml
from loguru import logger

from auto_trader.models.market_data import BarData, BarSizeType


class PlaybackMode(Enum):
    """Playback mode for file data feed."""

    INSTANT = "instant"  # Deliver all bars immediately
    SEQUENTIAL = "sequential"  # Deliver with delays between bars
    REAL_TIME = "real_time"  # Simulate real-time delivery based on timestamps


class FileDataFeed:
    """File-based data feed implementing DataFeedProvider protocol.

    Reads OHLCV data from files (CSV, YAML, JSON) and distributes as
    BarData objects to subscribers, simulating live market data flow.

    Args:
        file_path: Path to the data file.
        playback_mode: How to deliver bars (instant, sequential, real_time).
        speed_multiplier: Speed factor for sequential/real_time modes.
            1.0 = real time, 10.0 = 10x faster, 0.1 = 10x slower.

    Example:
        >>> feed = FileDataFeed("data/simulation/scenario.csv")
        >>> feed.add_subscriber("orchestrator", process_bar)
        >>> await feed.start()
    """

    def __init__(
        self,
        file_path: str,
        playback_mode: PlaybackMode = PlaybackMode.INSTANT,
        speed_multiplier: float = 1.0,
    ) -> None:
        """Initialize file data feed.

        Args:
            file_path: Path to the data file.
            playback_mode: How to deliver bars.
            speed_multiplier: Speed factor for playback.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file format is unsupported.
        """
        self._file_path = Path(file_path)
        self._playback_mode = playback_mode
        self._speed_multiplier = speed_multiplier

        if not self._file_path.exists():
            raise FileNotFoundError(f"Data file not found: {file_path}")

        self._validate_file_format()

        self._subscribers: Dict[str, Callable[[BarData], None]] = {}
        self._subscribed_symbols: set[str] = set()
        self._subscribed_bar_sizes: set[str] = set()
        self._is_running = False
        self._stop_requested = False

        # Load bars from file
        self._bars: List[BarData] = self._load_bars_from_file()
        self._bars_delivered = 0

        logger.info(
            "FileDataFeed initialized",
            file_path=str(self._file_path),
            bars_loaded=len(self._bars),
            playback_mode=playback_mode.value,
        )

    def _validate_file_format(self) -> None:
        """Validate file has supported format."""
        suffix = self._file_path.suffix.lower()
        if suffix not in [".csv", ".yaml", ".yml", ".json"]:
            raise ValueError(f"Unsupported file format: {suffix}")

    def _load_bars_from_file(self) -> List[BarData]:
        """Load bars from file based on format."""
        suffix = self._file_path.suffix.lower()

        if suffix == ".csv":
            return self._load_from_csv()
        elif suffix in [".yaml", ".yml"]:
            return self._load_from_yaml()
        elif suffix == ".json":
            return self._load_from_json()
        else:
            raise ValueError(f"Unsupported file format: {suffix}")

    def _load_from_csv(self) -> List[BarData]:
        """Load bars from CSV file."""
        bars = []
        with open(self._file_path, newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                bar = self._parse_bar_dict(row)
                bars.append(bar)
        return sorted(bars, key=lambda b: b.timestamp)

    def _load_from_yaml(self) -> List[BarData]:
        """Load bars from YAML file."""
        with open(self._file_path) as f:
            data = yaml.safe_load(f)

        bars_data = data.get("bars", [])
        bars = [self._parse_bar_dict(bar_dict) for bar_dict in bars_data]
        return sorted(bars, key=lambda b: b.timestamp)

    def _load_from_json(self) -> List[BarData]:
        """Load bars from JSON file."""
        with open(self._file_path) as f:
            data = json.load(f)

        bars_data = data.get("bars", [])
        bars = [self._parse_bar_dict(bar_dict) for bar_dict in bars_data]
        return sorted(bars, key=lambda b: b.timestamp)

    def _parse_bar_dict(self, bar_dict: Dict[str, Any]) -> BarData:
        """Parse a dictionary into a BarData object.

        Args:
            bar_dict: Dictionary with bar data fields.

        Returns:
            Validated BarData object.

        Raises:
            ValueError: If validation fails.
        """
        # Parse timestamp
        timestamp_str = bar_dict.get("timestamp", "")
        if isinstance(timestamp_str, str):
            # Handle ISO format with Z suffix
            timestamp_str = timestamp_str.replace("Z", "+00:00")
            timestamp = datetime.fromisoformat(timestamp_str)
        else:
            timestamp = timestamp_str

        # Ensure UTC
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)

        # Create BarData (Pydantic validates OHLC consistency)
        return BarData(
            symbol=bar_dict["symbol"],
            timestamp=timestamp,
            open_price=Decimal(str(bar_dict["open"])),
            high_price=Decimal(str(bar_dict["high"])),
            low_price=Decimal(str(bar_dict["low"])),
            close_price=Decimal(str(bar_dict["close"])),
            volume=int(bar_dict["volume"]),
            bar_size=bar_dict["bar_size"],
        )

    @property
    def is_running(self) -> bool:
        """Check if the feed is currently running."""
        return self._is_running

    def get_loaded_bars(self) -> List[BarData]:
        """Get all bars loaded from the file."""
        return self._bars.copy()

    def add_subscriber(
        self, subscriber_id: str, callback: Callable[[BarData], None]
    ) -> None:
        """Register a callback to receive BarData updates.

        Args:
            subscriber_id: Unique identifier for the subscriber.
            callback: Function to call with each BarData update.
        """
        self._subscribers[subscriber_id] = callback
        logger.info(
            "Subscriber added to FileDataFeed",
            subscriber_id=subscriber_id,
            total_subscribers=len(self._subscribers),
        )

    def remove_subscriber(self, subscriber_id: str) -> bool:
        """Unregister a subscriber from receiving updates.

        Args:
            subscriber_id: The identifier used when registering.

        Returns:
            True if subscriber was found and removed, False otherwise.
        """
        if subscriber_id in self._subscribers:
            del self._subscribers[subscriber_id]
            logger.info(
                "Subscriber removed from FileDataFeed",
                subscriber_id=subscriber_id,
                total_subscribers=len(self._subscribers),
            )
            return True
        return False

    async def start(self) -> None:
        """Start feeding data to subscribers.

        Begins playback of the file data according to the playback mode.
        """
        logger.info("Starting FileDataFeed playback")
        self._is_running = True
        self._stop_requested = False
        self._bars_delivered = 0

        try:
            await self._playback_bars()
        finally:
            self._is_running = False
            logger.info(
                "FileDataFeed playback complete",
                bars_delivered=self._bars_delivered,
            )

    async def stop(self) -> None:
        """Stop feeding data to subscribers."""
        logger.info("Stopping FileDataFeed")
        self._stop_requested = True
        self._is_running = False

    async def _playback_bars(self) -> None:
        """Play back bars to subscribers according to playback mode."""
        bars_to_deliver = self._filter_bars_by_subscription()

        for i, bar in enumerate(bars_to_deliver):
            if self._stop_requested:
                logger.info("Playback stopped by request")
                break

            # Deliver bar to all subscribers
            self._deliver_bar(bar)
            self._bars_delivered += 1

            # Handle delay based on playback mode
            if (
                self._playback_mode != PlaybackMode.INSTANT
                and i < len(bars_to_deliver) - 1
            ):
                delay = self._calculate_delay(bar, bars_to_deliver[i + 1])
                if delay > 0:
                    await asyncio.sleep(delay)

    def _filter_bars_by_subscription(self) -> List[BarData]:
        """Filter bars based on subscribed symbols and bar sizes."""
        if not self._subscribed_symbols and not self._subscribed_bar_sizes:
            # No filtering - deliver all bars
            return self._bars

        filtered = []
        for bar in self._bars:
            symbol_match = (
                not self._subscribed_symbols or bar.symbol in self._subscribed_symbols
            )
            size_match = (
                not self._subscribed_bar_sizes
                or bar.bar_size in self._subscribed_bar_sizes
            )
            if symbol_match and size_match:
                filtered.append(bar)

        return filtered

    def _deliver_bar(self, bar: BarData) -> None:
        """Deliver a bar to all subscribers."""
        for subscriber_id, callback in self._subscribers.items():
            try:
                callback(bar)
            except Exception as e:
                logger.error(
                    "Error in subscriber callback",
                    subscriber_id=subscriber_id,
                    error=str(e),
                )

    def _calculate_delay(self, current_bar: BarData, next_bar: BarData) -> float:
        """Calculate delay between bars based on playback mode.

        Args:
            current_bar: The bar just delivered.
            next_bar: The next bar to deliver.

        Returns:
            Delay in seconds.
        """
        if self._playback_mode == PlaybackMode.INSTANT:
            return 0.0

        # Calculate time difference between bars
        time_diff = (next_bar.timestamp - current_bar.timestamp).total_seconds()

        if self._playback_mode == PlaybackMode.SEQUENTIAL:
            # Use time difference but apply speed multiplier
            return max(0.0, time_diff / self._speed_multiplier)
        elif self._playback_mode == PlaybackMode.REAL_TIME:
            # Real-time simulation
            return max(0.0, time_diff / self._speed_multiplier)

        return 0.0

    async def subscribe_symbols(
        self, symbols: List[str], bar_sizes: List[BarSizeType]
    ) -> Dict[str, bool]:
        """Subscribe to specific symbols and timeframes.

        For file-based feeds, this filters which bars from the file
        are delivered during playback.

        Args:
            symbols: List of trading symbols.
            bar_sizes: List of bar timeframes.

        Returns:
            Dictionary mapping "symbol:bar_size" keys to availability status.
        """
        self._subscribed_symbols = set(symbols)
        self._subscribed_bar_sizes = set(bar_sizes)

        # Check which subscriptions are available in the data
        available_keys = {f"{b.symbol}:{b.bar_size}" for b in self._bars}

        result = {}
        for symbol in symbols:
            for bar_size in bar_sizes:
                key = f"{symbol}:{bar_size}"
                result[key] = key in available_keys

        logger.info(
            "Symbol subscription updated",
            symbols=symbols,
            bar_sizes=bar_sizes,
            available=sum(1 for v in result.values() if v),
        )

        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get data feed statistics.

        Returns:
            Dictionary with feed statistics.
        """
        return {
            "file_path": str(self._file_path),
            "bars_loaded": len(self._bars),
            "bars_delivered": self._bars_delivered,
            "is_running": self._is_running,
            "playback_mode": self._playback_mode.value,
            "speed_multiplier": self._speed_multiplier,
            "subscribers_count": len(self._subscribers),
            "feed_type": "file",
        }
