"""Test suite for Discord notifier."""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from auto_trader.models.order import Order, OrderRequest
from auto_trader.models.enums import OrderSide, OrderType, OrderStatus, TimeInForce
from auto_trader.integrations.discord_notifier import DiscordNotifier


@pytest.fixture
def webhook_url():
    """Test webhook URL."""
    return "https://discord.com/api/webhooks/test/webhook"


@pytest.fixture
def notifier(webhook_url):
    """Discord notifier instance."""
    return DiscordNotifier(webhook_url=webhook_url, simulation_mode=False)


@pytest.fixture 
def sim_notifier(webhook_url):
    """Discord notifier in simulation mode."""
    return DiscordNotifier(webhook_url=webhook_url, simulation_mode=True)


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
        filled_quantity=100,
        average_fill_price=Decimal("180.52"),
        time_in_force=TimeInForce.DAY,
    )


@pytest.fixture
def sample_order_request():
    """Sample order request for testing."""
    from auto_trader.models.trade_plan import RiskCategory
    return OrderRequest(
        trade_plan_id="AAPL_20250827_001", 
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        entry_price=Decimal("180.50"),
        stop_loss_price=Decimal("178.00"),
        take_profit_price=Decimal("185.00"),
        risk_category=RiskCategory.NORMAL,
        calculated_position_size=100,
        time_in_force="DAY"
    )


class TestDiscordNotifier:
    """Test cases for Discord notifier."""
    
    def test_initialization(self, webhook_url):
        """Test notifier initialization."""
        notifier = DiscordNotifier(webhook_url, simulation_mode=True)
        
        assert notifier.webhook_url == webhook_url
        assert notifier.simulation_mode is True
        assert notifier._client is not None
        
    def test_initialization_no_webhook(self):
        """Test notifier initialization without webhook."""
        notifier = DiscordNotifier("", simulation_mode=False)
        
        assert notifier.webhook_url == ""
        assert notifier.simulation_mode is False
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.post')
    async def test_send_order_submitted_buy(self, mock_post, notifier, sample_order):
        """Test order submitted notification for buy order."""
        # Setup mock response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Test with risk information
        await notifier.send_order_submitted(
            order=sample_order,
            risk_amount=Decimal("240.00"),
            portfolio_risk=5.2
        )
        
        # Verify request was made
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        
        assert args[0] == notifier.webhook_url
        payload = kwargs['json']
        assert "ORDER SUBMITTED" in payload['content']
        assert "AAPL" in payload['content']
        assert "LONG 100" in payload['content']
        assert "$240.00" in payload['content']
        assert "5.2%" in payload['content']
        assert "📈" in payload['content']
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.post')
    async def test_send_order_submitted_sell(self, mock_post, notifier):
        """Test order submitted notification for sell order."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        sell_order = Order(
            order_id="TEST_002",
            trade_plan_id="TSLA_20250827_001",
            symbol="TSLA",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=50,
            status=OrderStatus.SUBMITTED,
            price=Decimal("250.00"),
            time_in_force=TimeInForce.DAY,
        )
        
        await notifier.send_order_submitted(
            order=sell_order,
            risk_amount=Decimal("125.00")
        )
        
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        
        payload = kwargs['json']
        assert "ORDER SUBMITTED" in payload['content']
        assert "TSLA" in payload['content']
        assert "SHORT 50" in payload['content']
        assert "$125.00" in payload['content']
        assert "📉" in payload['content']
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.post')
    async def test_send_order_filled_entry(self, mock_post, notifier, sample_order):
        """Test order filled notification for entry."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        await notifier.send_order_filled(order=sample_order)
        
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        
        payload = kwargs['json']
        assert "ENTRY EXECUTED" in payload['content']
        assert "AAPL" in payload['content']
        assert "LONG 100" in payload['content']
        assert "$180.52" in payload['content']
        assert "🟢" in payload['content']
        
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.post')
    async def test_send_order_filled_exit_profit(self, mock_post, notifier, sample_order):
        """Test order filled notification for profitable exit."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Modify for exit (sell)
        sample_order.side = OrderSide.SELL
        sample_order.average_fill_price = Decimal("185.00")
        
        await notifier.send_order_filled(
            order=sample_order,
            entry_price=Decimal("180.50")
        )
        
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        
        payload = kwargs['json']
        assert "EXIT: TAKE PROFIT" in payload['content']
        assert "AAPL" in payload['content']
        assert "SOLD 100" in payload['content']
        assert "$185.00" in payload['content']
        assert "$450.00" in payload['content']  # P&L
        assert "+2.5%" in payload['content']    # P&L percentage
        assert "🟢" in payload['content']
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.post')
    async def test_send_order_filled_exit_loss(self, mock_post, notifier, sample_order):
        """Test order filled notification for losing exit."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        # Modify for exit (sell) at a loss
        sample_order.side = OrderSide.SELL
        sample_order.average_fill_price = Decimal("178.00")
        
        await notifier.send_order_filled(
            order=sample_order,
            entry_price=Decimal("180.50")
        )
        
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        
        payload = kwargs['json']
        assert "EXIT: STOP LOSS" in payload['content']
        assert "$-250.00" in payload['content']  # P&L
        assert "-1.4%" in payload['content']     # P&L percentage
        assert "🔴" in payload['content']
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.post')
    async def test_send_order_cancelled(self, mock_post, notifier, sample_order):
        """Test order cancelled notification."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        await notifier.send_order_cancelled(
            order=sample_order,
            reason="Risk limits exceeded"
        )
        
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        
        payload = kwargs['json']
        assert "ORDER CANCELLED" in payload['content']
        assert "AAPL" in payload['content']
        assert "Risk limits exceeded" in payload['content']
        assert "🟡" in payload['content']
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.post')
    async def test_send_order_rejected(self, mock_post, notifier, sample_order_request):
        """Test order rejected notification."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        await notifier.send_order_rejected(
            order_request=sample_order_request,
            reason="Insufficient buying power"
        )
        
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        
        payload = kwargs['json']
        assert "ORDER REJECTED" in payload['content']
        assert "AAPL" in payload['content']
        assert "Insufficient buying power" in payload['content']
        assert "🚨" in payload['content']
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.post')
    async def test_send_bracket_order_placed(self, mock_post, notifier, sample_order):
        """Test bracket order placed notification."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        await notifier.send_bracket_order_placed(
            entry_order=sample_order,
            stop_loss_price=Decimal("178.00"),
            take_profit_price=Decimal("185.00"),
            risk_amount=Decimal("250.00")
        )
        
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        
        payload = kwargs['json']
        assert "BRACKET ORDER PLACED" in payload['content']
        assert "AAPL" in payload['content']
        assert "LONG 100" in payload['content']
        assert "$178.00" in payload['content']  # Stop loss
        assert "$185.00" in payload['content']  # Take profit
        assert "$250.00" in payload['content']  # Risk amount
        assert "🛡️" in payload['content']
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.post')
    async def test_send_system_alert(self, mock_post, notifier):
        """Test system alert notification."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        await notifier.send_system_alert(
            alert_type="ERROR",
            message="IBKR connection lost"
        )
        
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        
        payload = kwargs['json']
        assert "SYSTEM ERROR" in payload['content']
        assert "IBKR connection lost" in payload['content']
        assert "🚨" in payload['content']
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.post')
    async def test_simulation_mode_prefix(self, mock_post, sim_notifier, sample_order):
        """Test that simulation mode adds [SIM] prefix."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response
        
        await sim_notifier.send_order_submitted(order=sample_order)
        
        mock_post.assert_called_once()
        args, kwargs = mock_post.call_args
        
        payload = kwargs['json']
        assert "[SIM]" in payload['content']
        assert "ORDER SUBMITTED" in payload['content']
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.post')
    async def test_webhook_failure_handling(self, mock_post, notifier, sample_order):
        """Test handling of webhook request failures."""
        # Mock failed response
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal Server Error"
        mock_response.raise_for_status.side_effect = Exception("HTTP 500")
        mock_post.return_value = mock_response
        
        # Should not raise exception, just log error
        await notifier.send_order_submitted(order=sample_order)
        
        mock_post.assert_called_once()
    
    @pytest.mark.asyncio
    @patch('httpx.AsyncClient.post')
    async def test_rate_limit_retry(self, mock_post, notifier, sample_order):
        """Test rate limit retry mechanism."""
        import httpx
        
        # Mock rate limited response, then success
        rate_limit_response = MagicMock()
        rate_limit_response.status_code = 429
        rate_limit_response.text = "Too Many Requests"
        
        success_response = MagicMock()
        success_response.status_code = 200
        
        # First call raises HTTPStatusError, second succeeds
        http_error = httpx.HTTPStatusError("429 Client Error", request=MagicMock(), response=rate_limit_response)
        mock_post.side_effect = [http_error, success_response]
        
        await notifier.send_order_submitted(order=sample_order)
        
        # Should be called twice (initial + retry)
        assert mock_post.call_count == 2
    
    @pytest.mark.asyncio
    async def test_no_webhook_url_handling(self, sample_order):
        """Test handling when no webhook URL is provided."""
        notifier = DiscordNotifier(webhook_url="", simulation_mode=False)
        
        # Should not raise exception, just log warning
        await notifier.send_order_submitted(order=sample_order)
    
    @pytest.mark.asyncio
    async def test_close_client(self, notifier):
        """Test closing the HTTP client."""
        with patch.object(notifier._client, 'aclose', new=AsyncMock()) as mock_close:
            await notifier.close()
            mock_close.assert_called_once()