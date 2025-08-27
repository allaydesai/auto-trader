"""Tests for market data manager."""

import pytest
import asyncio
from datetime import datetime, UTC
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch, call

from auto_trader.integrations.ibkr_client.market_data_manager import MarketDataManager
from auto_trader.models.market_data import BarData, SubscriptionError
from auto_trader.models.market_data_cache import MarketDataCache


@pytest.fixture
def mock_ib_client():
    """Create a mock IB client."""
    mock = MagicMock()
    mock.qualifyContractsAsync = AsyncMock()
    mock.reqRealTimeBars = MagicMock()
    mock.cancelRealTimeBars = MagicMock()
    return mock


@pytest.fixture
def mock_cache():
    """Create a mock market data cache."""
    cache = MagicMock(spec=MarketDataCache)
    cache.update_bar = AsyncMock()
    cache.add_subscription = MagicMock()
    cache.remove_subscription = MagicMock()
    cache.clear_cache = MagicMock()
    cache.get_memory_usage = MagicMock(return_value={
        "total_bars": 100,
        "estimated_memory_mb": 0.1
    })
    return cache


@pytest.fixture
def manager(mock_ib_client, mock_cache):
    """Create a market data manager instance."""
    return MarketDataManager(mock_ib_client, mock_cache)


class TestMarketDataManager:
    """Test market data manager functionality."""
    
    @pytest.mark.asyncio
    async def test_subscribe_symbols_success(self, manager, mock_ib_client):
        """Test successful subscription to symbols."""
        symbols = ["AAPL", "MSFT"]
        bar_sizes = ["5min"]
        
        # Mock subscription object
        mock_subscription = MagicMock()
        mock_subscription.updateEvent = MagicMock()
        mock_ib_client.reqRealTimeBars.return_value = mock_subscription
        
        results = await manager.subscribe_symbols(symbols, bar_sizes)
        
        assert results["AAPL:5min"] is True
        assert results["MSFT:5min"] is True
        assert mock_ib_client.qualifyContractsAsync.call_count == 2
        assert mock_ib_client.reqRealTimeBars.call_count == 2
        assert manager.get_subscription_count() == 2
    
    @pytest.mark.asyncio
    async def test_subscribe_symbols_with_multiple_timeframes(self, manager, mock_ib_client):
        """Test subscribing to multiple timeframes."""
        symbols = ["AAPL"]
        bar_sizes = ["1min", "5min", "15min"]
        
        mock_subscription = MagicMock()
        mock_subscription.updateEvent = MagicMock()
        mock_ib_client.reqRealTimeBars.return_value = mock_subscription
        
        results = await manager.subscribe_symbols(symbols, bar_sizes)
        
        assert results["AAPL:1min"] is True
        assert results["AAPL:5min"] is True
        assert results["AAPL:15min"] is True
        assert manager.get_subscription_count() == 3
    
    @pytest.mark.asyncio
    async def test_subscribe_existing_symbol(self, manager, mock_ib_client):
        """Test subscribing to an already subscribed symbol."""
        symbol = ["AAPL"]
        
        mock_subscription = MagicMock()
        mock_subscription.updateEvent = MagicMock()
        mock_ib_client.reqRealTimeBars.return_value = mock_subscription
        
        # First subscription
        await manager.subscribe_symbols(symbol, ["5min"])
        
        # Second subscription to same symbol
        results = await manager.subscribe_symbols(symbol, ["5min"])
        
        assert results["AAPL:5min"] is True
        # Should only call reqRealTimeBars once
        assert mock_ib_client.reqRealTimeBars.call_count == 1
    
    @pytest.mark.asyncio
    async def test_subscribe_invalid_bar_size(self, manager):
        """Test subscription with invalid bar size."""
        results = await manager.subscribe_symbols(["AAPL"], ["invalid"])
        
        assert results["AAPL:invalid"] is False
        assert manager.get_subscription_count() == 0
    
    @pytest.mark.asyncio
    async def test_unsubscribe_symbols(self, manager, mock_ib_client):
        """Test unsubscribing from symbols."""
        # Setup subscriptions
        mock_subscription = MagicMock()
        mock_subscription.updateEvent = MagicMock()
        mock_ib_client.reqRealTimeBars.return_value = mock_subscription
        
        await manager.subscribe_symbols(["AAPL", "MSFT"], ["5min"])
        assert manager.get_subscription_count() == 2
        
        # Unsubscribe from one symbol
        await manager.unsubscribe_symbols(["AAPL"])
        
        assert manager.get_subscription_count() == 1
        assert mock_ib_client.cancelRealTimeBars.call_count == 1
    
    @pytest.mark.asyncio
    async def test_sync_with_active_plans(self, manager, mock_ib_client):
        """Test syncing subscriptions with active plans."""
        mock_subscription = MagicMock()
        mock_subscription.updateEvent = MagicMock()
        mock_ib_client.reqRealTimeBars.return_value = mock_subscription
        
        # Initial subscriptions
        await manager.subscribe_symbols(["AAPL", "MSFT"], ["5min"])
        
        # Sync with new required symbols
        required_symbols = {"AAPL", "GOOGL"}  # Remove MSFT, add GOOGL
        await manager.sync_with_active_plans(required_symbols)
        
        active_subs = manager.get_active_subscriptions()
        assert "AAPL" in active_subs
        assert "GOOGL" in active_subs
        assert "MSFT" not in active_subs
    
    @pytest.mark.asyncio
    async def test_bar_update_processing(self, manager, mock_cache):
        """Test processing of bar updates."""
        # Create mock bar data
        mock_bar = MagicMock()
        mock_bar.time = datetime.now(UTC)  # Use datetime object, not timestamp
        mock_bar.open_ = 180.50
        mock_bar.high = 181.00
        mock_bar.low = 180.00
        mock_bar.close = 180.75
        mock_bar.volume = 1000000
        
        await manager._on_bar_update(mock_bar, "AAPL", "5min")
        
        # Verify cache was updated
        assert mock_cache.update_bar.called
        call_args = mock_cache.update_bar.call_args[0][0]
        assert isinstance(call_args, BarData)
        assert call_args.symbol == "AAPL"
        assert call_args.close_price == Decimal("180.75")
    
    @pytest.mark.asyncio
    async def test_bar_update_with_callback(self, mock_ib_client, mock_cache):
        """Test bar update with external callback."""
        callback_called = False
        received_bar = None
        
        def test_callback(bar: BarData):
            nonlocal callback_called, received_bar
            callback_called = True
            received_bar = bar
        
        manager = MarketDataManager(mock_ib_client, mock_cache, test_callback)
        
        mock_bar = MagicMock()
        mock_bar.time = datetime.now(UTC)  # Use datetime object, not timestamp
        mock_bar.open_ = 180.50
        mock_bar.high = 181.00
        mock_bar.low = 180.00
        mock_bar.close = 180.75
        mock_bar.volume = 1000000
        
        await manager._on_bar_update(mock_bar, "AAPL", "5min")
        
        assert callback_called
        assert received_bar.symbol == "AAPL"
        assert received_bar.bar_size == "5min"
    
    def test_get_active_subscriptions(self, manager, mock_ib_client):
        """Test getting active subscriptions grouped by symbol."""
        # Setup mock subscriptions
        manager._subscriptions = {
            "AAPL:1min": MagicMock(),
            "AAPL:5min": MagicMock(),
            "MSFT:5min": MagicMock()
        }
        
        active = manager.get_active_subscriptions()
        
        assert "AAPL" in active
        assert "MSFT" in active
        assert "1min" in active["AAPL"]
        assert "5min" in active["AAPL"]
        assert "5min" in active["MSFT"]
    
    def test_get_stats(self, manager, mock_cache):
        """Test getting manager statistics."""
        manager._stats["bars_received"] = 100
        manager._stats["subscription_errors"] = 2
        
        stats = manager.get_stats()
        
        assert stats["bars_received"] == 100
        assert stats["subscription_errors"] == 2
        assert "cache_stats" in stats
        assert stats["cache_stats"]["total_bars"] == 100
    
    @pytest.mark.asyncio
    async def test_cleanup(self, manager, mock_ib_client, mock_cache):
        """Test cleanup of all subscriptions."""
        mock_subscription = MagicMock()
        mock_subscription.updateEvent = MagicMock()
        mock_ib_client.reqRealTimeBars.return_value = mock_subscription
        
        await manager.subscribe_symbols(["AAPL", "MSFT"], ["5min"])
        assert manager.get_subscription_count() == 2
        
        await manager.cleanup()
        
        assert manager.get_subscription_count() == 0
        assert mock_cache.clear_cache.called
    
    @pytest.mark.asyncio
    async def test_error_handling_in_subscription(self, mock_ib_client, mock_cache):
        """Test error handling during subscription."""
        # Create a new manager with error in qualifyContractsAsync
        mock_ib_client.qualifyContractsAsync.side_effect = Exception("Connection error")
        manager = MarketDataManager(mock_ib_client, mock_cache)
        
        results = await manager.subscribe_symbols(["AAPL"], ["5min"])
        
        assert results["AAPL:5min"] is False
        assert manager._stats["subscription_errors"] == 1
    
    @pytest.mark.asyncio
    async def test_error_handling_in_bar_update(self, manager, mock_cache):
        """Test error handling during bar update processing."""
        # Invalid bar data that will cause an error
        invalid_bar = MagicMock()
        invalid_bar.time = "invalid"  # Should be timestamp
        
        await manager._on_bar_update(invalid_bar, "AAPL", "5min")
        
        assert manager._stats["data_quality_errors"] == 1
    
    @pytest.mark.asyncio
    async def test_empty_bar_update(self, manager):
        """Test handling of empty bar updates."""
        await manager._on_bar_update(None, "AAPL", "5min")
        
        # Should return without error
        assert manager._stats["bars_received"] == 0
        assert manager._stats["data_quality_errors"] == 0

    def test_add_remove_subscriber(self, manager):
        """Test adding and removing market data subscribers."""
        callback_called = []
        
        def test_callback(bar_data):
            callback_called.append(bar_data)
        
        # Add subscriber
        manager.add_subscriber("test_subscriber", test_callback)
        assert len(manager._subscribers) == 1
        assert "test_subscriber" in manager._subscribers
        
        # Remove subscriber
        removed = manager.remove_subscriber("test_subscriber")
        assert removed is True
        assert len(manager._subscribers) == 0
        
        # Try to remove non-existent subscriber
        removed = manager.remove_subscriber("non_existent")
        assert removed is False
    
    def test_add_remove_execution_engine_callback(self, manager):
        """Test adding and removing execution engine callbacks."""
        callback_called = []
        
        def test_callback(bar_data):
            callback_called.append(bar_data)
        
        # Add execution engine callback
        manager.add_execution_engine_callback(test_callback)
        assert len(manager._execution_engine_callbacks) == 1
        
        # Remove execution engine callback
        removed = manager.remove_execution_engine_callback(test_callback)
        assert removed is True
        assert len(manager._execution_engine_callbacks) == 0
        
        # Try to remove non-existent callback
        def other_callback(bar_data):
            pass
        removed = manager.remove_execution_engine_callback(other_callback)
        assert removed is False

    @pytest.mark.asyncio
    async def test_distribution_system(self, manager, mock_cache):
        """Test market data distribution to subscribers and execution engines."""
        subscriber_calls = []
        execution_calls = []
        
        def subscriber_callback(bar_data):
            subscriber_calls.append(bar_data)
        
        def execution_callback(bar_data):
            execution_calls.append(bar_data)
        
        # Add subscribers
        manager.add_subscriber("subscriber1", subscriber_callback)
        manager.add_execution_engine_callback(execution_callback)
        
        # Create mock bar data
        mock_bar = MagicMock()
        mock_bar.time = datetime.now(UTC)
        mock_bar.open_ = 100.0
        mock_bar.high = 101.0
        mock_bar.low = 99.0
        mock_bar.close = 100.5
        mock_bar.volume = 1000.0
        
        # Process bar update
        await manager._on_bar_update(mock_bar, "AAPL", "5min")
        
        # Verify distribution
        assert len(subscriber_calls) == 1
        assert len(execution_calls) == 1
        assert subscriber_calls[0].symbol == "AAPL"
        assert execution_calls[0].symbol == "AAPL"
        
        # Check statistics
        stats = manager.get_stats()
        assert stats["subscribers_count"] == 1
        assert stats["execution_callbacks_count"] == 1
        assert stats["distribution_errors"] == 0

    @pytest.mark.asyncio
    async def test_distribution_error_handling(self, manager, mock_cache):
        """Test error handling in distribution system."""
        def failing_callback(bar_data):
            raise Exception("Callback error")
        
        # Add failing subscriber and execution callback
        manager.add_subscriber("failing_subscriber", failing_callback)
        manager.add_execution_engine_callback(failing_callback)
        
        # Create mock bar data
        mock_bar = MagicMock()
        mock_bar.time = datetime.now(UTC)
        mock_bar.open_ = 100.0
        mock_bar.high = 101.0
        mock_bar.low = 99.0
        mock_bar.close = 100.5
        mock_bar.volume = 1000.0
        
        # Process bar update
        await manager._on_bar_update(mock_bar, "AAPL", "5min")
        
        # Check that errors were tracked
        stats = manager.get_stats()
        assert stats["distribution_errors"] == 2  # One for subscriber, one for execution callback