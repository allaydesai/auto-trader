"""Integration tests for Discord notifications with OrderExecutionManager."""

import pytest
import asyncio
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock, AsyncMock, patch

from auto_trader.models.order import OrderRequest
from auto_trader.models.enums import OrderSide, OrderType
from auto_trader.models.trade_plan import RiskCategory
from auto_trader.integrations.ibkr_client import OrderExecutionManager
from auto_trader.integrations.ibkr_client.client import IBKRClient
from auto_trader.integrations.discord_notifier import DiscordNotifier
from auto_trader.risk_management import OrderRiskValidator


@pytest.fixture
def temp_state_dir():
    """Temporary directory for state files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def mock_discord_notifier():
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
def mock_ibkr_client():
    """Mock IBKR client."""
    client = MagicMock(spec=IBKRClient)
    client.is_connected.return_value = True
    
    # Mock IB connection
    mock_ib = MagicMock()
    client._ib = mock_ib
    
    return client


@pytest.fixture
def mock_risk_validator():
    """Mock risk validator."""
    validator = MagicMock(spec=OrderRiskValidator)
    return validator


@pytest.fixture
async def order_manager_with_discord(
    mock_ibkr_client,
    mock_risk_validator, 
    temp_state_dir,
    mock_discord_notifier
):
    """Order execution manager with Discord integration."""
    manager = OrderExecutionManager(
        ibkr_client=mock_ibkr_client,
        risk_validator=mock_risk_validator,
        simulation_mode=True,
        state_dir=temp_state_dir,
        discord_notifier=mock_discord_notifier
    )
    
    yield manager
    
    # Cleanup
    await manager.stop_state_management()


@pytest.fixture
def sample_order_request():
    """Sample order request."""
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


class TestDiscordIntegration:
    """Integration tests for Discord notifications."""
    
    @pytest.mark.asyncio
    async def test_order_manager_initialization_with_discord(
        self, 
        mock_ibkr_client,
        mock_risk_validator,
        temp_state_dir,
        mock_discord_notifier
    ):
        """Test that OrderExecutionManager properly initializes Discord integration."""
        manager = OrderExecutionManager(
            ibkr_client=mock_ibkr_client,
            risk_validator=mock_risk_validator,
            simulation_mode=True,
            state_dir=temp_state_dir,
            discord_notifier=mock_discord_notifier
        )
        
        # Should have Discord handler registered
        assert manager._discord_handler is not None
        assert len(manager._event_handlers) > 0
        
        await manager.stop_state_management()
    
    @pytest.mark.asyncio
    async def test_order_manager_initialization_without_discord(
        self,
        mock_ibkr_client,
        mock_risk_validator,
        temp_state_dir
    ):
        """Test that OrderExecutionManager works without Discord notifier."""
        manager = OrderExecutionManager(
            ibkr_client=mock_ibkr_client,
            risk_validator=mock_risk_validator,
            simulation_mode=True,
            state_dir=temp_state_dir,
            discord_notifier=None
        )
        
        # Should not have Discord handler
        assert manager._discord_handler is None
        
        await manager.stop_state_management()
    
    @pytest.mark.asyncio
    async def test_market_order_triggers_discord_notification(
        self,
        order_manager_with_discord,
        mock_discord_notifier,
        mock_risk_validator,
        sample_order_request
    ):
        """Test that placing market order triggers Discord notification."""
        # Setup successful risk validation
        mock_validation = MagicMock()
        mock_validation.is_valid = True
        mock_validation.position_size_result.dollar_risk = Decimal("240.00")
        mock_risk_validator.validate_order_request.return_value = mock_validation
        
        # Place order
        result = await order_manager_with_discord.place_market_order(sample_order_request)
        
        # Wait for async notification
        await asyncio.sleep(0.1)
        
        # Verify order was placed successfully
        assert result.success
        
        # Verify Discord notification was sent
        mock_discord_notifier.send_order_submitted.assert_called_once()
        
        # Verify notification parameters
        call_args = mock_discord_notifier.send_order_submitted.call_args
        order = call_args.kwargs['order']
        assert order.symbol == "AAPL"
        assert order.side == OrderSide.BUY
        assert order.quantity == 100
        assert call_args.kwargs['risk_amount'] == Decimal("240.00")
    
    @pytest.mark.asyncio
    async def test_order_rejection_triggers_discord_notification(
        self,
        order_manager_with_discord,
        mock_discord_notifier,
        mock_risk_validator,
        sample_order_request
    ):
        """Test that order rejection triggers Discord notification."""
        # Setup failed risk validation
        mock_validation = MagicMock()
        mock_validation.is_valid = False
        mock_validation.errors = ["Insufficient buying power", "Position size too large"]
        mock_risk_validator.validate_order_request.return_value = mock_validation
        mock_risk_validator.create_order_rejection_result.return_value = MagicMock(success=False)
        
        # Place order (should be rejected)
        result = await order_manager_with_discord.place_market_order(sample_order_request)
        
        # Wait for async notification
        await asyncio.sleep(0.1)
        
        # Verify order was rejected
        assert not result.success
        
        # Verify Discord rejection notification was sent
        mock_discord_notifier.send_order_rejected.assert_called_once()
        
        # Verify rejection parameters
        call_args = mock_discord_notifier.send_order_rejected.call_args
        assert "Insufficient buying power; Position size too large" in call_args.kwargs['reason']
    
    @pytest.mark.asyncio
    async def test_bracket_order_triggers_discord_notification(
        self,
        order_manager_with_discord,
        mock_discord_notifier,
        mock_risk_validator,
        sample_order_request
    ):
        """Test that placing bracket order triggers Discord notification."""
        # Setup successful risk validation
        mock_validation = MagicMock()
        mock_validation.is_valid = True
        mock_validation.position_size_result.dollar_risk = Decimal("250.00")
        mock_risk_validator.validate_order_request.return_value = mock_validation
        
        # Place bracket order
        result = await order_manager_with_discord.place_bracket_order(
            entry_request=sample_order_request,
            stop_loss_price=Decimal("178.00"),
            take_profit_price=Decimal("185.00")
        )
        
        # Wait for async notification
        await asyncio.sleep(0.1)
        
        # Verify bracket order was placed successfully
        assert result.success
        
        # Verify Discord bracket notification was sent
        mock_discord_notifier.send_bracket_order_placed.assert_called_once()
        
        # Verify bracket notification parameters
        call_args = mock_discord_notifier.send_bracket_order_placed.call_args
        assert call_args.kwargs['stop_loss_price'] == Decimal("178.00")
        assert call_args.kwargs['take_profit_price'] == Decimal("185.00")
        assert call_args.kwargs['risk_amount'] == Decimal("250.00")
    
    @pytest.mark.asyncio
    async def test_order_cancellation_triggers_discord_notification(
        self,
        order_manager_with_discord,
        mock_discord_notifier,
        mock_risk_validator,
        sample_order_request
    ):
        """Test that order cancellation triggers Discord notification."""
        # First place an order
        mock_validation = MagicMock()
        mock_validation.is_valid = True
        mock_validation.position_size_result.dollar_risk = Decimal("240.00")
        mock_risk_validator.validate_order_request.return_value = mock_validation
        
        result = await order_manager_with_discord.place_market_order(sample_order_request)
        assert result.success
        
        order_id = result.order_id
        
        # Reset mock to clear previous calls
        mock_discord_notifier.reset_mock()
        
        # Cancel the order
        cancel_result = await order_manager_with_discord.cancel_order(order_id)
        
        # Wait for async notification
        await asyncio.sleep(0.1)
        
        # Verify cancellation was successful
        assert cancel_result.success
        
        # Verify Discord cancellation notification was sent
        mock_discord_notifier.send_order_cancelled.assert_called_once()
        
        # Verify cancellation parameters
        call_args = mock_discord_notifier.send_order_cancelled.call_args
        order = call_args.kwargs['order']
        assert order.order_id == order_id
        assert call_args.kwargs['reason'] == "Manual"
    
    @pytest.mark.asyncio
    async def test_discord_integration_with_import_error(
        self,
        mock_ibkr_client,
        mock_risk_validator,
        temp_state_dir,
        mock_discord_notifier
    ):
        """Test Discord integration handling when import fails."""
        with patch('builtins.__import__', side_effect=ImportError("Discord notifier not available")):
            manager = OrderExecutionManager(
                ibkr_client=mock_ibkr_client,
                risk_validator=mock_risk_validator,
                simulation_mode=True,
                state_dir=temp_state_dir,
                discord_notifier=mock_discord_notifier
            )
            
            # Should handle import error gracefully
            assert manager._discord_handler is None
            
            await manager.stop_state_management()
    
    @pytest.mark.asyncio
    async def test_multiple_event_handlers_with_discord(
        self,
        order_manager_with_discord,
        mock_discord_notifier,
        mock_risk_validator,
        sample_order_request
    ):
        """Test that Discord works alongside other event handlers."""
        # Add custom event handler
        custom_handler_called = False
        
        def custom_handler(event):
            nonlocal custom_handler_called
            custom_handler_called = True
        
        order_manager_with_discord.add_event_handler(custom_handler)
        
        # Setup and place order
        mock_validation = MagicMock()
        mock_validation.is_valid = True
        mock_validation.position_size_result.dollar_risk = Decimal("240.00")
        mock_risk_validator.validate_order_request.return_value = mock_validation
        
        result = await order_manager_with_discord.place_market_order(sample_order_request)
        
        # Wait for async notifications
        await asyncio.sleep(0.1)
        
        # Both handlers should be called
        assert result.success
        assert custom_handler_called
        mock_discord_notifier.send_order_submitted.assert_called_once()