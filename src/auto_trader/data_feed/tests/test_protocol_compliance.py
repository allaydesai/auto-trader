"""Comprehensive tests for DataFeedProvider protocol compliance.

Tests verify that FileDataFeed and IBKRDataFeed correctly implement
the DataFeedProvider protocol with runtime type checking.
"""

import asyncio
import pytest
from pathlib import Path
from typing import Callable, List, Dict
from unittest.mock import Mock, AsyncMock, patch

from auto_trader.data_feed.protocol import DataFeedProvider
from auto_trader.data_feed.file_feed import FileDataFeed, PlaybackMode
from auto_trader.data_feed.ibkr_feed import IBKRDataFeed
from auto_trader.models.market_data import BarData, BarSizeType


@pytest.fixture
def temp_csv_file(tmp_path: Path) -> Path:
    """Create temporary CSV file with valid bar data."""
    csv_file = tmp_path / "test_data.csv"
    csv_file.write_text(
        "timestamp,symbol,open,high,low,close,volume,bar_size\n"
        "2024-01-01T09:30:00Z,SPY,450.00,451.00,449.50,450.75,1000000,5min\n"
        "2024-01-01T09:35:00Z,SPY,450.75,451.50,450.25,451.00,1200000,5min\n"
    )
    return csv_file


@pytest.fixture
def mock_ib_client() -> Mock:
    """Provide mock IB client for IBKR feed testing."""
    mock = Mock()
    mock.isConnected.return_value = True
    return mock


@pytest.fixture
def mock_market_data_manager() -> Mock:
    """Provide mock MarketDataManager for IBKR feed testing."""
    mock = Mock()
    mock.add_subscriber = Mock()
    mock.remove_subscriber = Mock(return_value=True)
    mock.subscribe_symbols = AsyncMock(return_value={"SPY:5min": True})
    mock.cleanup = AsyncMock()
    return mock


# Protocol runtime_checkable tests


def test_protocol_is_runtime_checkable():
    """Test DataFeedProvider is runtime_checkable with isinstance."""
    import inspect

    assert inspect.isclass(DataFeedProvider)

    class TestImpl:
        def add_subscriber(
            self, subscriber_id: str, callback: Callable[[BarData], None]
        ) -> None:
            pass

        def remove_subscriber(self, subscriber_id: str) -> bool:
            return True

        async def start(self) -> None:
            pass

        async def stop(self) -> None:
            pass

        async def subscribe_symbols(
            self, symbols: List[str], bar_sizes: List[BarSizeType]
        ) -> Dict[str, bool]:
            return {}

    assert isinstance(TestImpl(), DataFeedProvider)


def test_protocol_isinstance_check_with_valid_implementation():
    """Test isinstance works with complete protocol implementation."""

    class ValidImpl:
        def add_subscriber(
            self, subscriber_id: str, callback: Callable[[BarData], None]
        ) -> None:
            pass

        def remove_subscriber(self, subscriber_id: str) -> bool:
            return True

        async def start(self) -> None:
            pass

        async def stop(self) -> None:
            pass

        async def subscribe_symbols(
            self, symbols: List[str], bar_sizes: List[BarSizeType]
        ) -> Dict[str, bool]:
            return {}

    assert isinstance(ValidImpl(), DataFeedProvider)


def test_protocol_isinstance_check_with_invalid_implementation():
    """Test isinstance fails with incomplete protocol implementation."""

    class InvalidImpl:
        def add_subscriber(
            self, subscriber_id: str, callback: Callable[[BarData], None]
        ) -> None:
            pass

    assert not isinstance(InvalidImpl(), DataFeedProvider)


def test_non_implementing_class_fails_isinstance_check():
    """Test class without protocol methods fails isinstance."""

    class NonImpl:
        def some_other_method(self) -> None:
            pass

    assert not isinstance(NonImpl(), DataFeedProvider)


def test_partially_implementing_class_fails_isinstance_check():
    """Test class with partial protocol implementation fails isinstance."""

    class PartialImpl:
        def add_subscriber(
            self, subscriber_id: str, callback: Callable[[BarData], None]
        ) -> None:
            pass

        def remove_subscriber(self, subscriber_id: str) -> bool:
            return True

    assert not isinstance(PartialImpl(), DataFeedProvider)


def test_protocol_documentation_example_works():
    """Test the protocol docstring example works correctly."""

    class MyFeed:
        def add_subscriber(self, id: str, cb: Callable) -> None:
            pass

        def remove_subscriber(self, id: str) -> bool:
            return True

        async def start(self) -> None:
            pass

        async def stop(self) -> None:
            pass

        async def subscribe_symbols(self, symbols, sizes) -> dict:
            return {}

    assert isinstance(MyFeed(), DataFeedProvider)


# FileDataFeed protocol compliance tests


def test_file_feed_implements_protocol(temp_csv_file: Path):
    """Test FileDataFeed implements DataFeedProvider protocol."""
    feed = FileDataFeed(str(temp_csv_file))
    assert isinstance(feed, DataFeedProvider)


def test_file_feed_add_subscriber_method(temp_csv_file: Path):
    """Test FileDataFeed add_subscriber method compliance."""
    feed = FileDataFeed(str(temp_csv_file))
    assert hasattr(feed, "add_subscriber")
    assert callable(feed.add_subscriber)

    callback = Mock()
    result = feed.add_subscriber("test_sub", callback)
    assert result is None
    assert "test_sub" in feed._subscribers
    assert feed._subscribers["test_sub"] == callback


def test_file_feed_remove_subscriber_method(temp_csv_file: Path):
    """Test FileDataFeed remove_subscriber method compliance."""
    feed = FileDataFeed(str(temp_csv_file))
    assert hasattr(feed, "remove_subscriber")
    assert callable(feed.remove_subscriber)

    callback = Mock()
    feed.add_subscriber("test_sub", callback)
    result = feed.remove_subscriber("test_sub")
    assert result is True
    assert "test_sub" not in feed._subscribers
    assert feed.remove_subscriber("nonexistent") is False


@pytest.mark.asyncio
async def test_file_feed_start_method(temp_csv_file: Path):
    """Test FileDataFeed start method compliance."""
    feed = FileDataFeed(str(temp_csv_file), playback_mode=PlaybackMode.INSTANT)
    assert hasattr(feed, "start")
    assert callable(feed.start)
    assert asyncio.iscoroutinefunction(feed.start)

    callback = Mock()
    feed.add_subscriber("test_sub", callback)
    await feed.start()
    assert callback.call_count == 2


@pytest.mark.asyncio
async def test_file_feed_stop_method(temp_csv_file: Path):
    """Test FileDataFeed stop method compliance."""
    feed = FileDataFeed(str(temp_csv_file))
    assert hasattr(feed, "stop")
    assert callable(feed.stop)
    assert asyncio.iscoroutinefunction(feed.stop)

    await feed.stop()
    assert feed._stop_requested is True


@pytest.mark.asyncio
async def test_file_feed_subscribe_symbols_method(temp_csv_file: Path):
    """Test FileDataFeed subscribe_symbols method compliance."""
    feed = FileDataFeed(str(temp_csv_file))
    assert hasattr(feed, "subscribe_symbols")
    assert callable(feed.subscribe_symbols)
    assert asyncio.iscoroutinefunction(feed.subscribe_symbols)

    result = await feed.subscribe_symbols(["SPY"], ["5min"])
    assert isinstance(result, dict)
    assert "SPY:5min" in result
    assert result["SPY:5min"] is True


# IBKRDataFeed protocol compliance tests


@patch("auto_trader.data_feed.ibkr_feed.MarketDataManager")
def test_ibkr_feed_implements_protocol(mock_mgr_cls: Mock, mock_ib_client: Mock):
    """Test IBKRDataFeed implements DataFeedProvider protocol."""
    mock_mgr_cls.return_value = Mock()
    feed = IBKRDataFeed(mock_ib_client)
    assert isinstance(feed, DataFeedProvider)


@patch("auto_trader.data_feed.ibkr_feed.MarketDataManager")
def test_ibkr_feed_add_subscriber_method(
    mock_mgr_cls: Mock, mock_ib_client: Mock, mock_market_data_manager: Mock
):
    """Test IBKRDataFeed add_subscriber method compliance."""
    mock_mgr_cls.return_value = mock_market_data_manager
    feed = IBKRDataFeed(mock_ib_client)
    assert hasattr(feed, "add_subscriber")
    assert callable(feed.add_subscriber)

    callback = Mock()
    result = feed.add_subscriber("test_sub", callback)
    assert result is None
    mock_market_data_manager.add_subscriber.assert_called_once_with("test_sub", callback)


@patch("auto_trader.data_feed.ibkr_feed.MarketDataManager")
def test_ibkr_feed_remove_subscriber_method(
    mock_mgr_cls: Mock, mock_ib_client: Mock, mock_market_data_manager: Mock
):
    """Test IBKRDataFeed remove_subscriber method compliance."""
    mock_mgr_cls.return_value = mock_market_data_manager
    feed = IBKRDataFeed(mock_ib_client)
    assert hasattr(feed, "remove_subscriber")
    assert callable(feed.remove_subscriber)

    result = feed.remove_subscriber("test_sub")
    assert result is True
    mock_market_data_manager.remove_subscriber.assert_called_once_with("test_sub")


@pytest.mark.asyncio
@patch("auto_trader.data_feed.ibkr_feed.MarketDataManager")
async def test_ibkr_feed_start_method(
    mock_mgr_cls: Mock, mock_ib_client: Mock, mock_market_data_manager: Mock
):
    """Test IBKRDataFeed start method compliance."""
    mock_mgr_cls.return_value = mock_market_data_manager
    feed = IBKRDataFeed(mock_ib_client)
    assert hasattr(feed, "start")
    assert callable(feed.start)
    assert asyncio.iscoroutinefunction(feed.start)

    await feed.start()
    assert feed.is_running is True


@pytest.mark.asyncio
@patch("auto_trader.data_feed.ibkr_feed.MarketDataManager")
async def test_ibkr_feed_stop_method(
    mock_mgr_cls: Mock, mock_ib_client: Mock, mock_market_data_manager: Mock
):
    """Test IBKRDataFeed stop method compliance."""
    mock_mgr_cls.return_value = mock_market_data_manager
    feed = IBKRDataFeed(mock_ib_client)
    assert hasattr(feed, "stop")
    assert callable(feed.stop)
    assert asyncio.iscoroutinefunction(feed.stop)

    await feed.start()
    await feed.stop()
    assert feed.is_running is False
    mock_market_data_manager.cleanup.assert_called_once()


@pytest.mark.asyncio
@patch("auto_trader.data_feed.ibkr_feed.MarketDataManager")
async def test_ibkr_feed_subscribe_symbols_method(
    mock_mgr_cls: Mock, mock_ib_client: Mock, mock_market_data_manager: Mock
):
    """Test IBKRDataFeed subscribe_symbols method compliance."""
    mock_mgr_cls.return_value = mock_market_data_manager
    feed = IBKRDataFeed(mock_ib_client)
    assert hasattr(feed, "subscribe_symbols")
    assert callable(feed.subscribe_symbols)
    assert asyncio.iscoroutinefunction(feed.subscribe_symbols)

    result = await feed.subscribe_symbols(["SPY"], ["5min"])
    assert isinstance(result, dict)
    mock_market_data_manager.subscribe_symbols.assert_called_once_with(["SPY"], ["5min"])


# Method signature compatibility tests


def test_file_feed_signatures_match_protocol(temp_csv_file: Path):
    """Test FileDataFeed method signatures match protocol requirements."""
    feed = FileDataFeed(str(temp_csv_file))

    # add_subscriber: (str, Callable) -> None
    callback: Callable[[BarData], None] = Mock()
    result = feed.add_subscriber("test_id", callback)
    assert result is None

    # remove_subscriber: str -> bool
    result = feed.remove_subscriber("test_id")
    assert isinstance(result, bool)


@pytest.mark.asyncio
async def test_file_feed_async_signatures_match_protocol(temp_csv_file: Path):
    """Test FileDataFeed async method signatures match protocol."""
    feed = FileDataFeed(str(temp_csv_file))

    # subscribe_symbols: (List[str], List[BarSizeType]) -> Dict[str, bool]
    symbols: List[str] = ["SPY", "AAPL"]
    bar_sizes: List[BarSizeType] = ["5min", "15min"]
    result = await feed.subscribe_symbols(symbols, bar_sizes)
    assert isinstance(result, dict)
    for key, value in result.items():
        assert isinstance(key, str)
        assert isinstance(value, bool)


@patch("auto_trader.data_feed.ibkr_feed.MarketDataManager")
def test_ibkr_feed_signatures_match_protocol(
    mock_mgr_cls: Mock, mock_ib_client: Mock, mock_market_data_manager: Mock
):
    """Test IBKRDataFeed method signatures match protocol requirements."""
    mock_mgr_cls.return_value = mock_market_data_manager
    feed = IBKRDataFeed(mock_ib_client)

    # add_subscriber: (str, Callable) -> None
    callback: Callable[[BarData], None] = Mock()
    result = feed.add_subscriber("test_id", callback)
    assert result is None

    # remove_subscriber: str -> bool
    result = feed.remove_subscriber("test_id")
    assert isinstance(result, bool)


@pytest.mark.asyncio
@patch("auto_trader.data_feed.ibkr_feed.MarketDataManager")
async def test_ibkr_feed_async_signatures_match_protocol(
    mock_mgr_cls: Mock, mock_ib_client: Mock, mock_market_data_manager: Mock
):
    """Test IBKRDataFeed async method signatures match protocol."""
    mock_mgr_cls.return_value = mock_market_data_manager
    feed = IBKRDataFeed(mock_ib_client)

    # subscribe_symbols: (List[str], List[BarSizeType]) -> Dict[str, bool]
    symbols: List[str] = ["SPY", "AAPL"]
    bar_sizes: List[BarSizeType] = ["5min", "15min"]
    result = await feed.subscribe_symbols(symbols, bar_sizes)
    assert isinstance(result, dict)


# Integration tests


@pytest.mark.asyncio
async def test_both_implementations_interchangeable_via_protocol(temp_csv_file: Path):
    """Test both feed types work through protocol interface."""

    async def use_feed(feed: DataFeedProvider) -> None:
        callback = Mock()
        feed.add_subscriber("test", callback)
        await feed.start()
        await feed.stop()
        feed.remove_subscriber("test")

    # Test with FileDataFeed
    file_feed = FileDataFeed(str(temp_csv_file), playback_mode=PlaybackMode.INSTANT)
    await use_feed(file_feed)

    # Test with IBKRDataFeed
    with patch("auto_trader.data_feed.ibkr_feed.MarketDataManager") as mock_mgr_cls:
        mock_mgr = Mock()
        mock_mgr.cleanup = AsyncMock()
        mock_mgr_cls.return_value = mock_mgr
        ibkr_feed = IBKRDataFeed(Mock())
        await use_feed(ibkr_feed)
