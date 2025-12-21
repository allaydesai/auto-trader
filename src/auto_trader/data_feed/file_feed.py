"""File-based data feed for simulation mode.

This module provides the FileDataFeed class that reads market data from
CSV, YAML, or JSON files and delivers it to subscribers as BarData objects,
simulating live market data flow.
"""

import asyncio
import csv
import json
from dataclasses import dataclass, field
from datetime import datetime, UTC
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Callable, List, Dict, Any, Optional

import yaml
from loguru import logger

from auto_trader.models.market_data import BarData, BarSizeType


class PlaybackMode(Enum):
    """Playback mode for file data feed."""

    INSTANT = "instant"  # Deliver all bars immediately
    SEQUENTIAL = "sequential"  # Deliver with delays between bars
    REAL_TIME = "real_time"  # Simulate real-time delivery based on timestamps


@dataclass
class ColumnMapping:
    """Configuration for mapping CSV/file columns to BarData fields.

    Supports flexible column name mapping for various data file formats.
    Column names are matched case-insensitively.

    Attributes:
        timestamp: Column name for timestamp (default: "timestamp").
        symbol: Column name for symbol (default: "symbol").
        open: Column name for open price (default: "open").
        high: Column name for high price (default: "high").
        low: Column name for low price (default: "low").
        close: Column name for close price (default: "close").
        volume: Column name for volume (default: "volume").
        bar_size: Column name for bar size (default: "bar_size").
        default_symbol: Default symbol when column is missing.
        default_bar_size: Default bar size when column is missing.

    Example:
        >>> # For files with "Date" instead of "timestamp"
        >>> mapping = ColumnMapping(timestamp="Date", default_symbol="AAPL")
        >>> feed = FileDataFeed("data.csv", column_mapping=mapping)
    """

    timestamp: str = "timestamp"
    symbol: str = "symbol"
    open: str = "open"
    high: str = "high"
    low: str = "low"
    close: str = "close"
    volume: str = "volume"
    bar_size: str = "bar_size"

    # Default values for columns that might be missing
    default_symbol: Optional[str] = None
    default_bar_size: Optional[BarSizeType] = None

    @classmethod
    def for_standard_ohlcv(
        cls,
        symbol: str,
        bar_size: BarSizeType = "1min",
        timestamp_column: str = "Date",
    ) -> "ColumnMapping":
        """Create mapping for standard OHLCV files with Date column.

        Common format from data providers like Yahoo Finance, Alpha Vantage, etc.
        Expects columns: Date, Open, High, Low, Close, Volume

        Args:
            symbol: The symbol to assign to all bars.
            bar_size: The bar size to assign to all bars.
            timestamp_column: The timestamp column name (default: "Date").

        Returns:
            ColumnMapping configured for standard OHLCV format.
        """
        return cls(
            timestamp=timestamp_column,
            symbol="symbol",  # Will use default since column won't exist
            open="Open",
            high="High",
            low="Low",
            close="Close",
            volume="Volume",
            bar_size="bar_size",  # Will use default since column won't exist
            default_symbol=symbol,
            default_bar_size=bar_size,
        )


class FileDataFeed:
    """File-based data feed implementing DataFeedProvider protocol.

    Reads OHLCV data from files (CSV, YAML, JSON) and distributes as
    BarData objects to subscribers, simulating live market data flow.

    Args:
        file_path: Path to the data file.
        playback_mode: How to deliver bars (instant, sequential, real_time).
        speed_multiplier: Speed factor for sequential/real_time modes.
            1.0 = real time, 10.0 = 10x faster, 0.1 = 10x slower.
        column_mapping: Optional column name mapping for non-standard files.

    Example:
        >>> # Standard format
        >>> feed = FileDataFeed("data/simulation/scenario.csv")
        >>> feed.add_subscriber("orchestrator", process_bar)
        >>> await feed.start()

        >>> # Custom format (e.g., Yahoo Finance style)
        >>> mapping = ColumnMapping.for_standard_ohlcv("AAPL", "1min")
        >>> feed = FileDataFeed("aapl_data.csv", column_mapping=mapping)
    """

    def __init__(
        self,
        file_path: str,
        playback_mode: PlaybackMode = PlaybackMode.INSTANT,
        speed_multiplier: float = 1.0,
        column_mapping: Optional[ColumnMapping] = None,
    ) -> None:
        """Initialize file data feed.

        Args:
            file_path: Path to the data file.
            playback_mode: How to deliver bars.
            speed_multiplier: Speed factor for playback.
            column_mapping: Optional column name mapping configuration.

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError: If the file format is unsupported.
        """
        self._file_path = Path(file_path)
        self._playback_mode = playback_mode
        self._speed_multiplier = speed_multiplier
        self._column_mapping = column_mapping or ColumnMapping()

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
            column_mapping_used=column_mapping is not None,
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

    def _get_column_value(
        self, bar_dict: Dict[str, Any], column_name: str, default: Any = None
    ) -> Any:
        """Get a value from bar_dict using case-insensitive column matching.

        Args:
            bar_dict: Dictionary with bar data fields.
            column_name: The column name to look for.
            default: Default value if column not found.

        Returns:
            The column value or default.
        """
        # First try exact match
        if column_name in bar_dict:
            return bar_dict[column_name]

        # Try case-insensitive match
        column_lower = column_name.lower()
        for key, value in bar_dict.items():
            if key.lower() == column_lower:
                return value

        return default

    def _parse_bar_dict(self, bar_dict: Dict[str, Any]) -> BarData:
        """Parse a dictionary into a BarData object.

        Uses column mapping to handle various file formats.
        Column names are matched case-insensitively.

        Args:
            bar_dict: Dictionary with bar data fields.

        Returns:
            Validated BarData object.

        Raises:
            ValueError: If required fields are missing or validation fails.
        """
        mapping = self._column_mapping

        # Parse timestamp
        timestamp_str = self._get_column_value(bar_dict, mapping.timestamp, "")
        if not timestamp_str:
            raise ValueError(
                f"Missing timestamp column. Expected '{mapping.timestamp}', "
                f"available columns: {list(bar_dict.keys())}"
            )

        if isinstance(timestamp_str, str):
            # Handle ISO format with Z suffix
            timestamp_str = timestamp_str.replace("Z", "+00:00")
            # Handle space-separated datetime (e.g., "2006-01-03 00:00:00")
            if " " in timestamp_str and "T" not in timestamp_str:
                timestamp_str = timestamp_str.replace(" ", "T")
            timestamp = datetime.fromisoformat(timestamp_str)
        else:
            timestamp = timestamp_str

        # Ensure UTC
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)

        # Get symbol (use default if column missing)
        symbol = self._get_column_value(bar_dict, mapping.symbol)
        if symbol is None:
            if mapping.default_symbol:
                symbol = mapping.default_symbol
            else:
                raise ValueError(
                    f"Missing symbol column '{mapping.symbol}' and no default_symbol set. "
                    f"Available columns: {list(bar_dict.keys())}"
                )

        # Get bar_size (use default if column missing)
        bar_size = self._get_column_value(bar_dict, mapping.bar_size)
        if bar_size is None:
            if mapping.default_bar_size:
                bar_size = mapping.default_bar_size
            else:
                raise ValueError(
                    f"Missing bar_size column '{mapping.bar_size}' and no default_bar_size set. "
                    f"Available columns: {list(bar_dict.keys())}"
                )

        # Get OHLCV values
        open_val = self._get_column_value(bar_dict, mapping.open)
        high_val = self._get_column_value(bar_dict, mapping.high)
        low_val = self._get_column_value(bar_dict, mapping.low)
        close_val = self._get_column_value(bar_dict, mapping.close)
        volume_val = self._get_column_value(bar_dict, mapping.volume, 0)

        # Validate required OHLC values exist
        for name, val in [
            ("open", open_val),
            ("high", high_val),
            ("low", low_val),
            ("close", close_val),
        ]:
            if val is None:
                raise ValueError(
                    f"Missing {name} column '{getattr(mapping, name)}'. "
                    f"Available columns: {list(bar_dict.keys())}"
                )

        # Round prices to 4 decimal places to comply with BarData validation
        # Many data sources have excessive precision (e.g., Yahoo Finance)
        def round_price(val: Any) -> Decimal:
            return Decimal(str(val)).quantize(Decimal("0.0001"))

        # Create BarData (Pydantic validates OHLC consistency)
        return BarData(
            symbol=symbol,
            timestamp=timestamp,
            open_price=round_price(open_val),
            high_price=round_price(high_val),
            low_price=round_price(low_val),
            close_price=round_price(close_val),
            volume=int(float(volume_val)),  # Handle float volumes like "807234400.0"
            bar_size=bar_size,
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
