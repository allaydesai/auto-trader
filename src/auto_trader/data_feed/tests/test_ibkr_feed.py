"""Comprehensive tests for IBKRDataFeed class.

Tests cover initialization, subscriber management, lifecycle operations,
delegation to MarketDataManager, and statistics retrieval.
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, UTC
from decimal import Decimal
from typing import List

from auto_trader.data_feed.ibkr_feed import IBKRDataFeed
from auto_trader.models.market_data import BarData, BarSizeType


@pytest.fixture
def mock_ib_client():
    """Mock IB client instance for testing.

    Returns:
        Mock IB client with basic connection attributes.
    """
    mock_ib = Mock()
    mock_ib.isConnected = Mock(return_value=True)
    mock_ib.disconnect = Mock()
    return mock_ib


@pytest.fixture
def mock_market_data_manager():
    """Mock MarketDataManager for testing delegation.

    Returns:
        Mock MarketDataManager with all required methods.
    """
    mock_manager = Mock()
    mock_manager.add_subscriber = Mock()
    mock_manager.remove_subscriber = Mock(return_value=True)
    mock_manager.subscribe_symbols = AsyncMock(return_value={"SPY:5min": True})
    mock_manager.cleanup = AsyncMock()
    mock_manager.get_stats = Mock(
        return_value={
            "total_bars_received": 100,
            "active_subscriptions": 2,
        }
    )
    mock_manager.get_active_subscriptions = Mock(
        return_value={
            "SPY": ["5min", "15min"],
        }
    )
    mock_manager.get_subscription_count = Mock(return_value=2)
    return mock_manager


@pytest.fixture
def sample_bar_data():
    """Sample BarData for testing callbacks.

    Returns:
        BarData instance with realistic values.
    """
    return BarData(
        symbol="SPY",
        timestamp=datetime.now(UTC),
        open_price=Decimal("450.00"),
        high_price=Decimal("451.50"),
        low_price=Decimal("449.75"),
        close_price=Decimal("450.75"),
        volume=1000000,
        bar_size="5min",
    )


@pytest.fixture
def ibkr_feed(mock_ib_client, mock_market_data_manager):
    """IBKRDataFeed instance with mocked dependencies.

    Args:
        mock_ib_client: Mocked IB client.
        mock_market_data_manager: Mocked MarketDataManager.

    Returns:
        IBKRDataFeed instance ready for testing.
    """
    with patch(
        "auto_trader.data_feed.ibkr_feed.MarketDataManager",
        return_value=mock_market_data_manager,
    ):
        feed = IBKRDataFeed(mock_ib_client)
        return feed


class TestIBKRDataFeedInitialization:
    """Test IBKRDataFeed initialization."""

    def test_ibkr_feed_initializes_with_ib_client(self, mock_ib_client):
        """Test that feed initializes with IB client."""
        with patch("auto_trader.data_feed.ibkr_feed.MarketDataManager") as mock_mgr:
            feed = IBKRDataFeed(mock_ib_client)

            assert feed._ib_client is mock_ib_client
            assert not feed.is_running
            mock_mgr.assert_called_once_with(ib_client=mock_ib_client, cache=None)

    def test_ibkr_feed_initializes_with_cache(self, mock_ib_client):
        """Test that feed initializes with optional cache."""
        mock_cache = Mock()
        with patch("auto_trader.data_feed.ibkr_feed.MarketDataManager") as mock_mgr:
            IBKRDataFeed(mock_ib_client, cache=mock_cache)

            mock_mgr.assert_called_once_with(ib_client=mock_ib_client, cache=mock_cache)

    def test_ibkr_feed_initial_is_running_state_is_false(self, ibkr_feed):
        """Test that feed starts with is_running as False."""
        assert ibkr_feed.is_running is False


class TestIBKRDataFeedSubscriberManagement:
    """Test subscriber add/remove operations."""

    def test_add_subscriber_delegates_to_manager(
        self, ibkr_feed, mock_market_data_manager
    ):
        """Test that add_subscriber delegates to MarketDataManager."""
        callback = Mock()
        subscriber_id = "test_orchestrator"

        ibkr_feed.add_subscriber(subscriber_id, callback)

        mock_market_data_manager.add_subscriber.assert_called_once_with(
            subscriber_id, callback
        )

    def test_remove_subscriber_delegates_to_manager(
        self, ibkr_feed, mock_market_data_manager
    ):
        """Test that remove_subscriber delegates to MarketDataManager."""
        subscriber_id = "test_orchestrator"

        result = ibkr_feed.remove_subscriber(subscriber_id)

        mock_market_data_manager.remove_subscriber.assert_called_once_with(
            subscriber_id
        )
        assert result is True

    def test_remove_subscriber_returns_manager_result(
        self, ibkr_feed, mock_market_data_manager
    ):
        """Test that remove_subscriber returns manager's result."""
        mock_market_data_manager.remove_subscriber.return_value = False

        result = ibkr_feed.remove_subscriber("nonexistent")

        assert result is False


class TestIBKRDataFeedLifecycle:
    """Test async lifecycle methods (start/stop)."""

    @pytest.mark.asyncio
    async def test_start_sets_is_running_to_true(self, ibkr_feed):
        """Test that start() sets is_running to True."""
        await ibkr_feed.start()

        assert ibkr_feed.is_running is True

    @pytest.mark.asyncio
    async def test_stop_calls_manager_cleanup(
        self, ibkr_feed, mock_market_data_manager
    ):
        """Test that stop() delegates cleanup to MarketDataManager."""
        await ibkr_feed.start()
        await ibkr_feed.stop()

        mock_market_data_manager.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_sets_is_running_to_false(self, ibkr_feed):
        """Test that stop() sets is_running to False."""
        await ibkr_feed.start()
        await ibkr_feed.stop()

        assert ibkr_feed.is_running is False

    @pytest.mark.asyncio
    async def test_stop_without_start_handles_gracefully(
        self, ibkr_feed, mock_market_data_manager
    ):
        """Test that stop() works even if start() was never called."""
        await ibkr_feed.stop()

        mock_market_data_manager.cleanup.assert_called_once()
        assert ibkr_feed.is_running is False


class TestIBKRDataFeedSubscription:
    """Test symbol subscription operations."""

    @pytest.mark.asyncio
    async def test_subscribe_symbols_delegates_to_manager(
        self, ibkr_feed, mock_market_data_manager
    ):
        """Test that subscribe_symbols delegates to MarketDataManager."""
        symbols = ["SPY", "QQQ"]
        bar_sizes: List[BarSizeType] = ["5min", "15min"]

        await ibkr_feed.subscribe_symbols(symbols, bar_sizes)

        mock_market_data_manager.subscribe_symbols.assert_called_once_with(
            symbols, bar_sizes
        )

    @pytest.mark.asyncio
    async def test_subscribe_symbols_returns_manager_result(
        self, ibkr_feed, mock_market_data_manager
    ):
        """Test that subscribe_symbols returns manager's result dictionary."""
        expected_result = {
            "SPY:5min": True,
            "SPY:15min": True,
            "QQQ:5min": False,
        }
        mock_market_data_manager.subscribe_symbols.return_value = expected_result

        result = await ibkr_feed.subscribe_symbols(["SPY", "QQQ"], ["5min", "15min"])

        assert result == expected_result

    @pytest.mark.asyncio
    async def test_subscribe_symbols_with_empty_lists(
        self, ibkr_feed, mock_market_data_manager
    ):
        """Test that subscribe_symbols handles empty lists."""
        mock_market_data_manager.subscribe_symbols.return_value = {}

        result = await ibkr_feed.subscribe_symbols([], [])

        assert result == {}


class TestIBKRDataFeedStatistics:
    """Test statistics and subscription queries."""

    def test_get_stats_includes_manager_stats(
        self, ibkr_feed, mock_market_data_manager
    ):
        """Test that get_stats includes MarketDataManager stats."""
        stats = ibkr_feed.get_stats()

        assert stats["total_bars_received"] == 100
        assert stats["active_subscriptions"] == 2

    def test_get_stats_adds_is_running_field(self, ibkr_feed):
        """Test that get_stats adds is_running status."""
        stats = ibkr_feed.get_stats()

        assert "is_running" in stats
        assert stats["is_running"] is False

    def test_get_stats_adds_feed_type_field(self, ibkr_feed):
        """Test that get_stats identifies feed type as ibkr."""
        stats = ibkr_feed.get_stats()

        assert stats["feed_type"] == "ibkr"

    @pytest.mark.asyncio
    async def test_get_stats_reflects_running_state_after_start(self, ibkr_feed):
        """Test that get_stats reflects is_running state after start()."""
        await ibkr_feed.start()
        stats = ibkr_feed.get_stats()

        assert stats["is_running"] is True

    def test_get_active_subscriptions_delegates_to_manager(
        self, ibkr_feed, mock_market_data_manager
    ):
        """Test that get_active_subscriptions delegates to manager."""
        result = ibkr_feed.get_active_subscriptions()

        mock_market_data_manager.get_active_subscriptions.assert_called_once()
        assert result == {"SPY": ["5min", "15min"]}

    def test_get_subscription_count_delegates_to_manager(
        self, ibkr_feed, mock_market_data_manager
    ):
        """Test that get_subscription_count delegates to manager."""
        result = ibkr_feed.get_subscription_count()

        mock_market_data_manager.get_subscription_count.assert_called_once()
        assert result == 2

    def test_get_subscription_count_returns_zero_initially(self):
        """Test that subscription count is zero for new feed."""
        mock_ib = Mock()
        with patch("auto_trader.data_feed.ibkr_feed.MarketDataManager") as mock_mgr:
            mock_manager = Mock()
            mock_manager.get_subscription_count = Mock(return_value=0)
            mock_mgr.return_value = mock_manager

            feed = IBKRDataFeed(mock_ib)
            assert feed.get_subscription_count() == 0


class TestIBKRDataFeedIntegration:
    """Integration-style tests for complete workflows."""

    @pytest.mark.asyncio
    async def test_complete_lifecycle_workflow(
        self, ibkr_feed, mock_market_data_manager
    ):
        """Test complete workflow: start, subscribe, get stats, stop."""
        # Start feed
        await ibkr_feed.start()
        assert ibkr_feed.is_running is True

        # Subscribe to symbols
        result = await ibkr_feed.subscribe_symbols(["SPY"], ["5min"])
        assert result == {"SPY:5min": True}

        # Check stats
        stats = ibkr_feed.get_stats()
        assert stats["is_running"] is True
        assert stats["feed_type"] == "ibkr"

        # Stop feed
        await ibkr_feed.stop()
        assert ibkr_feed.is_running is False
        mock_market_data_manager.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_subscriber_workflow_with_callback(
        self, ibkr_feed, mock_market_data_manager, sample_bar_data
    ):
        """Test workflow with subscriber registration and callback."""
        callback = Mock()
        subscriber_id = "test_engine"

        # Add subscriber
        ibkr_feed.add_subscriber(subscriber_id, callback)
        mock_market_data_manager.add_subscriber.assert_called_once_with(
            subscriber_id, callback
        )

        # Verify subscriber can be removed
        result = ibkr_feed.remove_subscriber(subscriber_id)
        assert result is True
        mock_market_data_manager.remove_subscriber.assert_called_once_with(
            subscriber_id
        )

    def test_get_stats_combines_manager_and_feed_info(
        self, ibkr_feed, mock_market_data_manager
    ):
        """Test that get_stats properly combines manager stats with feed info."""
        mock_market_data_manager.get_stats.return_value = {
            "total_bars_received": 250,
            "active_subscriptions": 5,
            "subscription_details": {"SPY": ["1min", "5min"]},
        }

        stats = ibkr_feed.get_stats()

        # Should have manager stats
        assert stats["total_bars_received"] == 250
        assert stats["active_subscriptions"] == 5
        assert "subscription_details" in stats

        # Should have feed-specific additions
        assert stats["is_running"] is False
        assert stats["feed_type"] == "ibkr"
