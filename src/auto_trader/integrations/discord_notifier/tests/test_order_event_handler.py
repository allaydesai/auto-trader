"""Test suite for Discord order event handler."""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from auto_trader.models.order import Order, OrderEvent, OrderRequest
from auto_trader.models.enums import OrderSide, OrderType, OrderStatus, TimeInForce
from auto_trader.integrations.discord_notifier import DiscordNotifier
from auto_trader.integrations.discord_notifier.order_event_handler import DiscordOrderEventHandler


@pytest.fixture
def mock_notifier():
    """Mock Discord notifier."""
    notifier = MagicMock(spec=DiscordNotifier)
    
    # Make all methods async
    notifier.send_order_submitted = AsyncMock()
    notifier.send_order_filled = AsyncMock()
    notifier.send_order_cancelled = AsyncMock()
    notifier.send_order_rejected = AsyncMock()
    notifier.send_bracket_order_placed = AsyncMock()
    
    return notifier


@pytest.fixture
def event_handler(mock_notifier):
    """Discord order event handler."""
    return DiscordOrderEventHandler(mock_notifier)


@pytest.fixture
def sample_order():
    """Sample order for testing."""
    return Order(
        order_id="TEST_001",
        trade_plan_id="AAPL_20250827_001",
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=100,
        status=OrderStatus.SUBMITTED,
        price=Decimal("180.50"),
        time_in_force=TimeInForce.DAY,
    )


class TestDiscordOrderEventHandler:
    """Test cases for Discord order event handler."""
    
    def test_initialization(self, mock_notifier):
        """Test event handler initialization."""
        handler = DiscordOrderEventHandler(mock_notifier)
        
        assert handler.notifier == mock_notifier
        assert handler._order_cache == {}
    
    @pytest.mark.asyncio
    async def test_handle_order_submitted_event(self, event_handler, mock_notifier, sample_order):
        """Test handling order submitted event."""
        event = OrderEvent(
            event_id="EVT_TEST_001",
            order_id="TEST_001",
            trade_plan_id="AAPL_20250827_001", 
            event_type="order_submitted",
            new_status=OrderStatus.SUBMITTED,
            event_data={
                "order": sample_order,
                "risk_amount": 240.00,
                "portfolio_risk": 5.2
            }
        )
        
        # Handle event (synchronous call)
        event_handler.handle_order_event(event)
        
        # Wait for async task to complete
        await asyncio.sleep(0.1)
        
        # Verify notifier was called correctly
        mock_notifier.send_order_submitted.assert_called_once_with(
            order=sample_order,
            risk_amount=Decimal("240.00"),
            portfolio_risk=5.2
        )
        
        # Verify order was cached
        assert event_handler._order_cache["TEST_001"] == sample_order
    
    @pytest.mark.asyncio
    async def test_handle_order_filled_event(self, event_handler, mock_notifier, sample_order):
        """Test handling order filled event."""
        event = OrderEvent(
            event_id="EVT_TEST_002",
            order_id="TEST_001",
            trade_plan_id="AAPL_20250827_001",
            event_type="order_filled",
            new_status=OrderStatus.FILLED,
            event_data={
                "order": sample_order,
                "entry_price": 178.50
            }
        )
        
        event_handler.handle_order_event(event)
        await asyncio.sleep(0.1)
        
        mock_notifier.send_order_filled.assert_called_once_with(
            order=sample_order,
            entry_price=Decimal("178.50")
        )
    
    @pytest.mark.asyncio
    async def test_handle_order_cancelled_event(self, event_handler, mock_notifier, sample_order):
        """Test handling order cancelled event."""
        event = OrderEvent(
            event_id="EVT_TEST_003",
            order_id="TEST_001",
            trade_plan_id="AAPL_20250827_001",
            event_type="order_cancelled",
            new_status=OrderStatus.CANCELLED,
            event_data={
                "order": sample_order,
                "reason": "Risk limits exceeded"
            }
        )
        
        event_handler.handle_order_event(event)
        await asyncio.sleep(0.1)
        
        mock_notifier.send_order_cancelled.assert_called_once_with(
            order=sample_order,
            reason="Risk limits exceeded"
        )
    
    @pytest.mark.asyncio
    async def test_handle_order_rejected_event(self, event_handler, mock_notifier, sample_order):
        """Test handling order rejected event."""
        event = OrderEvent(
            event_id="EVT_TEST_004",
            order_id="TEST_001", 
            trade_plan_id="AAPL_20250827_001",
            event_type="order_rejected",
            new_status=OrderStatus.REJECTED,
            event_data={
                "order": sample_order,
                "reason": "Insufficient buying power"
            }
        )
        
        event_handler.handle_order_event(event)
        await asyncio.sleep(0.1)
        
        # Should be called with OrderRequest, not Order
        args, kwargs = mock_notifier.send_order_rejected.call_args
        order_request = kwargs['order_request']
        
        assert isinstance(order_request, OrderRequest)
        assert order_request.symbol == "AAPL"
        assert order_request.side == OrderSide.BUY
        assert kwargs['reason'] == "Insufficient buying power"
    
    @pytest.mark.asyncio
    async def test_handle_bracket_order_placed_event(self, event_handler, mock_notifier, sample_order):
        """Test handling bracket order placed event."""
        event = OrderEvent(
            event_id="EVT_TEST_005",
            order_id="TEST_001",
            trade_plan_id="AAPL_20250827_001",
            event_type="bracket_order_placed",
            new_status=OrderStatus.SUBMITTED,
            event_data={
                "order": sample_order,
                "stop_loss_price": 178.00,
                "take_profit_price": 185.00,
                "risk_amount": 250.00
            }
        )
        
        event_handler.handle_order_event(event)
        await asyncio.sleep(0.1)
        
        mock_notifier.send_bracket_order_placed.assert_called_once_with(
            entry_order=sample_order,
            stop_loss_price=Decimal("178.00"),
            take_profit_price=Decimal("185.00"),
            risk_amount=Decimal("250.00")
        )
    
    @pytest.mark.asyncio
    async def test_handle_unknown_event_type(self, event_handler, mock_notifier, sample_order):
        """Test handling unknown event type."""
        event = OrderEvent(
            event_id="EVT_TEST_006",
            order_id="TEST_001",
            trade_plan_id="AAPL_20250827_001",
            event_type="unknown_event",
            new_status=OrderStatus.PENDING,
            event_data={"order": sample_order}
        )
        
        # Should not raise exception
        event_handler.handle_order_event(event)
        await asyncio.sleep(0.1)
        
        # No notifier methods should be called
        mock_notifier.send_order_submitted.assert_not_called()
        mock_notifier.send_order_filled.assert_not_called()
        mock_notifier.send_order_cancelled.assert_not_called()
        mock_notifier.send_order_rejected.assert_not_called()
        mock_notifier.send_bracket_order_placed.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_handle_event_missing_order_data(self, event_handler, mock_notifier):
        """Test handling event with missing order data."""
        event = OrderEvent(
            event_id="EVT_TEST_007",
            order_id="TEST_001",
            trade_plan_id="AAPL_20250827_001",
            event_type="order_submitted",
            new_status=OrderStatus.SUBMITTED,
            event_data={}  # Missing order
        )
        
        # Should not raise exception
        event_handler.handle_order_event(event)
        await asyncio.sleep(0.1)
        
        # Notifier should not be called
        mock_notifier.send_order_submitted.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_handle_event_with_exception(self, event_handler, mock_notifier, sample_order):
        """Test handling event when notifier raises exception."""
        # Mock notifier to raise exception
        mock_notifier.send_order_submitted.side_effect = Exception("Network error")
        
        event = OrderEvent(
            event_id="EVT_TEST_008",
            order_id="TEST_001",
            trade_plan_id="AAPL_20250827_001",
            event_type="order_submitted",
            new_status=OrderStatus.SUBMITTED,
            event_data={
                "order": sample_order,
                "risk_amount": 240.00
            }
        )
        
        # Should not raise exception (error should be logged)
        event_handler.handle_order_event(event)
        await asyncio.sleep(0.1)
        
        # Verify exception was raised in notifier
        mock_notifier.send_order_submitted.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_bracket_order_event_missing_data(self, event_handler, mock_notifier, sample_order):
        """Test bracket order event with missing price data."""
        event = OrderEvent(
            event_id="EVT_TEST_009",
            order_id="TEST_001",
            trade_plan_id="AAPL_20250827_001",
            event_type="bracket_order_placed",
            new_status=OrderStatus.SUBMITTED,
            event_data={
                "order": sample_order,
                # Missing stop_loss_price, take_profit_price, risk_amount
            }
        )
        
        event_handler.handle_order_event(event)
        await asyncio.sleep(0.1)
        
        # Should not call notifier if required data is missing
        mock_notifier.send_bracket_order_placed.assert_not_called()
    
    @pytest.mark.asyncio
    async def test_filled_event_without_entry_price(self, event_handler, mock_notifier, sample_order):
        """Test filled event without entry price (entry order)."""
        event = OrderEvent(
            event_id="EVT_TEST_010",
            order_id="TEST_001",
            trade_plan_id="AAPL_20250827_001",
            event_type="order_filled",
            new_status=OrderStatus.FILLED,
            event_data={
                "order": sample_order,
                # No entry_price - should be treated as entry
            }
        )
        
        event_handler.handle_order_event(event)
        await asyncio.sleep(0.1)
        
        mock_notifier.send_order_filled.assert_called_once_with(
            order=sample_order,
            entry_price=None
        )
    
    def test_get_cached_order(self, event_handler, sample_order):
        """Test getting cached order."""
        # Initially empty
        assert event_handler.get_cached_order("TEST_001") is None
        
        # Add to cache
        event_handler._order_cache["TEST_001"] = sample_order
        
        # Should return cached order
        cached = event_handler.get_cached_order("TEST_001")
        assert cached == sample_order
        assert cached.order_id == "TEST_001"