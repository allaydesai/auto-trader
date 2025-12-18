"""Comprehensive tests for file-based data feed."""

import asyncio
from datetime import datetime, UTC
from decimal import Decimal

import pytest

from auto_trader.data_feed.file_feed import (
    FileDataFeed,
    PlaybackMode,
    ColumnMapping,
)
from auto_trader.models.market_data import BarData


class TestPlaybackMode:
    """Test PlaybackMode enum values."""

    def test_playback_mode_values(self):
        """Test all playback mode enum values."""
        assert PlaybackMode.INSTANT.value == "instant"
        assert PlaybackMode.SEQUENTIAL.value == "sequential"
        assert PlaybackMode.REAL_TIME.value == "real_time"


class TestColumnMapping:
    """Test ColumnMapping dataclass."""

    def test_column_mapping_default_values(self):
        """Test default column names are set correctly."""
        mapping = ColumnMapping()
        assert mapping.timestamp == "timestamp"
        assert mapping.symbol == "symbol"
        assert mapping.open == "open"
        assert mapping.high == "high"
        assert mapping.low == "low"
        assert mapping.close == "close"
        assert mapping.volume == "volume"
        assert mapping.bar_size == "bar_size"
        assert mapping.default_symbol is None
        assert mapping.default_bar_size is None

    def test_column_mapping_custom_values(self):
        """Test custom column names can be specified."""
        mapping = ColumnMapping(
            timestamp="Date",
            symbol="Ticker",
            open="Open",
            high="High",
            low="Low",
            close="Close",
            volume="Volume",
            default_symbol="AAPL",
            default_bar_size="1min",
        )
        assert mapping.timestamp == "Date"
        assert mapping.symbol == "Ticker"
        assert mapping.open == "Open"
        assert mapping.high == "High"
        assert mapping.low == "Low"
        assert mapping.close == "Close"
        assert mapping.volume == "Volume"
        assert mapping.default_symbol == "AAPL"
        assert mapping.default_bar_size == "1min"

    def test_column_mapping_for_standard_ohlcv(self):
        """Test for_standard_ohlcv factory method creates correct mapping."""
        mapping = ColumnMapping.for_standard_ohlcv("AAPL", "5min", "Date")

        assert mapping.timestamp == "Date"
        assert mapping.open == "Open"
        assert mapping.high == "High"
        assert mapping.low == "Low"
        assert mapping.close == "Close"
        assert mapping.volume == "Volume"
        assert mapping.default_symbol == "AAPL"
        assert mapping.default_bar_size == "5min"

    def test_column_mapping_for_standard_ohlcv_defaults(self):
        """Test for_standard_ohlcv uses correct default values."""
        mapping = ColumnMapping.for_standard_ohlcv("TSLA")

        assert mapping.timestamp == "Date"
        assert mapping.default_symbol == "TSLA"
        assert mapping.default_bar_size == "1min"


class TestFileDataFeedInitialization:
    """Test FileDataFeed initialization."""

    def test_init_file_errors(self, tmp_path):
        """Test initialization errors for missing and unsupported files."""
        with pytest.raises(FileNotFoundError, match="Data file not found"):
            FileDataFeed("nonexistent_file.csv")
        unsupported_file = tmp_path / "data.txt"
        unsupported_file.write_text("some data")
        with pytest.raises(ValueError, match="Unsupported file format: .txt"):
            FileDataFeed(str(unsupported_file))

    def test_init_with_various_formats(
        self, sample_csv_file, sample_yaml_file, sample_json_file
    ):
        """Test successful initialization with CSV, YAML, and JSON files."""
        for file_path in [sample_csv_file, sample_yaml_file, sample_json_file]:
            feed = FileDataFeed(str(file_path))
            assert feed.is_running is False
            assert len(feed.get_loaded_bars()) > 0

    def test_init_with_custom_column_mapping(self, yahoo_finance_csv_file):
        """Test initialization with custom column mapping."""
        mapping = ColumnMapping.for_standard_ohlcv("AAPL", "1min")
        feed = FileDataFeed(str(yahoo_finance_csv_file), column_mapping=mapping)

        bars = feed.get_loaded_bars()
        assert len(bars) > 0
        assert all(bar.symbol == "AAPL" for bar in bars)
        assert all(bar.bar_size == "1min" for bar in bars)


class TestFileDataFeedSubscriberManagement:
    """Test subscriber add/remove functionality."""

    def test_add_subscribers(self, sample_csv_file):
        """Test adding single and multiple subscribers."""
        feed = FileDataFeed(str(sample_csv_file))
        feed.add_subscriber("test_1", lambda bar: None)
        assert feed.get_stats()["subscribers_count"] == 1
        feed.add_subscriber("test_2", lambda bar: None)
        assert feed.get_stats()["subscribers_count"] == 2

    def test_remove_subscriber(self, sample_csv_file):
        """Test removing existing and non-existent subscribers."""
        feed = FileDataFeed(str(sample_csv_file))
        feed.add_subscriber("test", lambda bar: None)
        assert feed.remove_subscriber("test") is True
        assert feed.get_stats()["subscribers_count"] == 0
        assert feed.remove_subscriber("nonexistent") is False


class TestFileDataFeedPlayback:
    """Test async playback functionality."""

    @pytest.mark.asyncio
    async def test_start_sets_running_flag(self, sample_csv_file):
        """Test start() sets is_running flag correctly."""
        feed = FileDataFeed(str(sample_csv_file))
        received_bars = []

        def callback(bar: BarData):
            received_bars.append(bar)

        feed.add_subscriber("test", callback)

        task = asyncio.create_task(feed.start())
        await asyncio.sleep(0.1)
        await feed.stop()
        await task

        assert feed.is_running is False
        assert len(received_bars) > 0

    @pytest.mark.asyncio
    async def test_stop_interrupts_playback(self, sample_csv_file):
        """Test stop() interrupts playback correctly."""
        feed = FileDataFeed(
            str(sample_csv_file),
            playback_mode=PlaybackMode.SEQUENTIAL,
            speed_multiplier=0.1,
        )
        received_bars = []

        def callback(bar: BarData):
            received_bars.append(bar)

        feed.add_subscriber("test", callback)

        task = asyncio.create_task(feed.start())
        await asyncio.sleep(0.05)
        await feed.stop()
        await task

        stats = feed.get_stats()
        assert stats["bars_delivered"] < stats["bars_loaded"]

    @pytest.mark.asyncio
    async def test_playback_instant_delivers_all_bars(self, sample_csv_file):
        """Test INSTANT mode delivers all bars without delay."""
        feed = FileDataFeed(str(sample_csv_file), playback_mode=PlaybackMode.INSTANT)
        received_bars = []

        def callback(bar: BarData):
            received_bars.append(bar)

        feed.add_subscriber("test", callback)
        await feed.start()

        assert len(received_bars) == len(feed.get_loaded_bars())

    @pytest.mark.asyncio
    async def test_playback_sequential_respects_timing(self, sample_csv_file):
        """Test SEQUENTIAL mode introduces delays between bars."""
        feed = FileDataFeed(
            str(sample_csv_file),
            playback_mode=PlaybackMode.SEQUENTIAL,
            speed_multiplier=100.0,
        )
        received_bars = []
        timestamps = []

        def callback(bar: BarData):
            received_bars.append(bar)
            timestamps.append(datetime.now(UTC))

        feed.add_subscriber("test", callback)
        start_time = datetime.now(UTC)
        await feed.start()
        end_time = datetime.now(UTC)

        duration = (end_time - start_time).total_seconds()
        assert duration > 0.0
        assert len(received_bars) == len(feed.get_loaded_bars())

    @pytest.mark.asyncio
    async def test_playback_delivers_to_all_subscribers(self, sample_csv_file):
        """Test playback delivers bars to all subscribers."""
        feed = FileDataFeed(str(sample_csv_file))
        received_bars_1 = []
        received_bars_2 = []

        def callback1(bar: BarData):
            received_bars_1.append(bar)

        def callback2(bar: BarData):
            received_bars_2.append(bar)

        feed.add_subscriber("subscriber_1", callback1)
        feed.add_subscriber("subscriber_2", callback2)
        await feed.start()

        assert len(received_bars_1) == len(feed.get_loaded_bars())
        assert len(received_bars_2) == len(feed.get_loaded_bars())
        assert received_bars_1 == received_bars_2


class TestFileDataFeedSubscribeSymbols:
    """Test symbol and bar size filtering."""

    @pytest.mark.asyncio
    async def test_subscribe_symbols_filters_correctly(self, multi_symbol_csv_file):
        """Test subscribe_symbols filters bars by symbol and bar size."""
        feed = FileDataFeed(str(multi_symbol_csv_file))
        received_bars = []

        def callback(bar: BarData):
            received_bars.append(bar)

        feed.add_subscriber("test", callback)
        result = await feed.subscribe_symbols(["AAPL"], ["5min"])
        await feed.start()

        assert all(bar.symbol == "AAPL" for bar in received_bars)
        assert all(bar.bar_size == "5min" for bar in received_bars)

    @pytest.mark.asyncio
    async def test_subscribe_symbols_returns_availability(self, multi_symbol_csv_file):
        """Test subscribe_symbols returns correct availability status."""
        feed = FileDataFeed(str(multi_symbol_csv_file))

        result = await feed.subscribe_symbols(
            ["AAPL", "TSLA", "GOOG"], ["5min", "15min"]
        )

        assert "AAPL:5min" in result
        assert "TSLA:5min" in result
        assert isinstance(result["AAPL:5min"], bool)

    @pytest.mark.asyncio
    async def test_subscribe_symbols_no_filter_delivers_all(self, sample_csv_file):
        """Test that no subscription delivers all bars."""
        feed = FileDataFeed(str(sample_csv_file))
        received_bars = []

        def callback(bar: BarData):
            received_bars.append(bar)

        feed.add_subscriber("test", callback)
        await feed.start()

        assert len(received_bars) == len(feed.get_loaded_bars())


class TestFileDataFeedLoadingMethods:
    """Test file loading for different formats."""

    def test_load_from_various_formats(
        self, sample_csv_file, sample_yaml_file, sample_json_file
    ):
        """Test loading from CSV, YAML, and JSON formats."""
        for file_path in [sample_csv_file, sample_yaml_file, sample_json_file]:
            feed = FileDataFeed(str(file_path))
            bars = feed.get_loaded_bars()
            assert len(bars) > 0
            assert all(isinstance(bar, BarData) for bar in bars)

    def test_load_sorts_bars_chronologically(self, unsorted_csv_file):
        """Test that loaded bars are sorted by timestamp."""
        feed = FileDataFeed(str(unsorted_csv_file))
        bars = feed.get_loaded_bars()

        timestamps = [bar.timestamp for bar in bars]
        assert timestamps == sorted(timestamps)


class TestFileDataFeedParseBarDict:
    """Test _parse_bar_dict with various column mappings."""

    def test_parse_bar_dict_with_standard_columns(self, sample_csv_file):
        """Test parsing with standard column names."""
        feed = FileDataFeed(str(sample_csv_file))
        bars = feed.get_loaded_bars()

        assert len(bars) > 0
        assert bars[0].symbol == "AAPL"
        assert bars[0].open_price > Decimal("0")

    def test_parse_bar_dict_with_custom_mapping(self, yahoo_finance_csv_file):
        """Test parsing with custom column mapping."""
        mapping = ColumnMapping.for_standard_ohlcv("MSFT", "15min")
        feed = FileDataFeed(str(yahoo_finance_csv_file), column_mapping=mapping)
        bars = feed.get_loaded_bars()

        assert all(bar.symbol == "MSFT" for bar in bars)
        assert all(bar.bar_size == "15min" for bar in bars)

    def test_parse_bar_dict_missing_timestamp_raises_error(
        self, missing_timestamp_csv_file
    ):
        """Test parsing raises error when timestamp column is missing."""
        with pytest.raises(ValueError, match="Missing timestamp column"):
            FileDataFeed(str(missing_timestamp_csv_file))

    def test_parse_bar_dict_missing_symbol_without_default_raises_error(
        self, missing_symbol_csv_file
    ):
        """Test parsing raises error when symbol column missing without default."""
        with pytest.raises(ValueError, match="Missing symbol column"):
            FileDataFeed(str(missing_symbol_csv_file))

    def test_parse_bar_dict_missing_ohlc_raises_error(self, missing_ohlc_csv_file):
        """Test parsing raises error when OHLC columns are missing."""
        with pytest.raises(ValueError, match="Missing"):
            FileDataFeed(str(missing_ohlc_csv_file))

    def test_parse_bar_dict_case_insensitive_columns(self, case_insensitive_csv_file):
        """Test parsing handles case-insensitive column names."""
        mapping = ColumnMapping.for_standard_ohlcv("AAPL", "1min")
        feed = FileDataFeed(str(case_insensitive_csv_file), column_mapping=mapping)
        bars = feed.get_loaded_bars()

        assert len(bars) > 0
        assert all(bar.symbol == "AAPL" for bar in bars)


class TestFileDataFeedCalculateDelay:
    """Test delay calculation for different playback modes."""

    def test_calculate_delay_instant_returns_zero(self, sample_csv_file):
        """Test INSTANT mode returns zero delay."""
        feed = FileDataFeed(str(sample_csv_file), playback_mode=PlaybackMode.INSTANT)
        bars = feed.get_loaded_bars()

        if len(bars) >= 2:
            delay = feed._calculate_delay(bars[0], bars[1])
            assert delay == 0.0

    def test_calculate_delay_sequential_respects_multiplier(self, sample_csv_file):
        """Test SEQUENTIAL mode applies speed multiplier."""
        feed = FileDataFeed(
            str(sample_csv_file),
            playback_mode=PlaybackMode.SEQUENTIAL,
            speed_multiplier=2.0,
        )
        bars = feed.get_loaded_bars()

        if len(bars) >= 2:
            delay = feed._calculate_delay(bars[0], bars[1])
            time_diff = (bars[1].timestamp - bars[0].timestamp).total_seconds()
            expected_delay = time_diff / 2.0
            assert delay == pytest.approx(expected_delay, rel=0.01)

    def test_calculate_delay_real_time_respects_multiplier(self, sample_csv_file):
        """Test REAL_TIME mode applies speed multiplier."""
        feed = FileDataFeed(
            str(sample_csv_file),
            playback_mode=PlaybackMode.REAL_TIME,
            speed_multiplier=10.0,
        )
        bars = feed.get_loaded_bars()

        if len(bars) >= 2:
            delay = feed._calculate_delay(bars[0], bars[1])
            time_diff = (bars[1].timestamp - bars[0].timestamp).total_seconds()
            expected_delay = time_diff / 10.0
            assert delay == pytest.approx(expected_delay, rel=0.01)


class TestFileDataFeedGetStats:
    """Test get_stats method."""

    def test_get_stats_returns_correct_structure(self, sample_csv_file):
        """Test get_stats returns all required fields."""
        feed = FileDataFeed(str(sample_csv_file))
        stats = feed.get_stats()

        assert "file_path" in stats
        assert "bars_loaded" in stats
        assert "bars_delivered" in stats
        assert "is_running" in stats
        assert "playback_mode" in stats
        assert "speed_multiplier" in stats
        assert "subscribers_count" in stats
        assert "feed_type" in stats

    def test_get_stats_reflects_current_state(self, sample_csv_file):
        """Test get_stats reflects current feed state."""
        feed = FileDataFeed(str(sample_csv_file), speed_multiplier=5.0)

        def callback(bar: BarData):
            pass

        feed.add_subscriber("test", callback)
        stats = feed.get_stats()

        assert stats["bars_loaded"] == len(feed.get_loaded_bars())
        assert stats["bars_delivered"] == 0
        assert stats["is_running"] is False
        assert stats["playback_mode"] == "instant"
        assert stats["speed_multiplier"] == 5.0
        assert stats["subscribers_count"] == 1
        assert stats["feed_type"] == "file"

    @pytest.mark.asyncio
    async def test_get_stats_updates_bars_delivered(self, sample_csv_file):
        """Test get_stats updates bars_delivered after playback."""
        feed = FileDataFeed(str(sample_csv_file))

        def callback(bar: BarData):
            pass

        feed.add_subscriber("test", callback)
        await feed.start()

        stats = feed.get_stats()
        assert stats["bars_delivered"] == stats["bars_loaded"]


class TestFileDataFeedGetLoadedBars:
    """Test get_loaded_bars method."""

    def test_get_loaded_bars_returns_copy(self, sample_csv_file):
        """Test get_loaded_bars returns a copy, not the original list."""
        feed = FileDataFeed(str(sample_csv_file))
        bars1 = feed.get_loaded_bars()
        bars2 = feed.get_loaded_bars()

        assert bars1 is not bars2
        assert bars1 == bars2

    def test_get_loaded_bars_contains_valid_bars(self, sample_csv_file):
        """Test get_loaded_bars contains valid BarData objects."""
        feed = FileDataFeed(str(sample_csv_file))
        bars = feed.get_loaded_bars()

        assert all(isinstance(bar, BarData) for bar in bars)
        assert all(bar.open_price > Decimal("0") for bar in bars)
        assert all(bar.high_price >= bar.open_price for bar in bars)
        assert all(bar.low_price <= bar.close_price for bar in bars)


# Fixtures are defined in conftest.py
