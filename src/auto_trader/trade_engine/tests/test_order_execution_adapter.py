"""Tests for order execution adapter."""

import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, UTC
from decimal import Decimal

from auto_trader.models.execution import ExecutionSignal, ExecutionContext, PositionState
from auto_trader.models.enums import ExecutionAction, Timeframe, OrderSide
from auto_trader.models.trade_plan import RiskCategory
from auto_trader.models.order import OrderRequest, OrderResult
from auto_trader.models.market_data import BarData
from auto_trader.trade_engine.order_execution_adapter import ExecutionOrderAdapter
from auto_trader.integrations.ibkr_client.order_execution_manager import OrderExecutionManager


@pytest.fixture
def mock_order_execution_manager():
    """Create mock order execution manager."""
    manager = Mock(spec=OrderExecutionManager)
    manager.place_market_order = AsyncMock(return_value=OrderResult(
        success=True,
        order_id="TEST123",
        trade_plan_id="test_plan",
        order_status="Submitted",
        symbol="AAPL",
        side="BUY",
        quantity=100,
        order_type="MKT",
    ))
    manager.place_stop_order = AsyncMock(return_value=OrderResult(
        success=True,
        order_id="STOP123",
        trade_plan_id="test_plan",
        order_status="Submitted",
        symbol="AAPL",
        side="SELL",
        quantity=100,
        order_type="STP",
    ))
    return manager


@pytest.fixture
def order_adapter(mock_order_execution_manager):
    """Create order execution adapter."""
    return ExecutionOrderAdapter(
        order_execution_manager=mock_order_execution_manager,
        default_risk_category=RiskCategory.NORMAL,
    )


@pytest.fixture
def sample_bar():
    """Create sample bar data."""
    return BarData(
        symbol="AAPL",
        timestamp=datetime.now(UTC),
        open_price=Decimal("180.00"),
        high_price=Decimal("182.00"),
        low_price=Decimal("179.50"),
        close_price=Decimal("181.50"),
        volume=1000000,
        bar_size="1min",
    )


@pytest.fixture
def sample_context(sample_bar):
    """Create sample execution context."""
    return ExecutionContext(
        symbol="AAPL",
        timeframe=Timeframe.ONE_MIN,
        current_bar=sample_bar,
        historical_bars=[sample_bar] * 20,
        trade_plan_params={},
        position_state=None,
        account_balance=Decimal("10000"),
        timestamp=datetime.now(UTC),
    )


@pytest.fixture
def sample_position():
    """Create sample position state."""
    return PositionState(
        symbol="AAPL",
        quantity=100,
        entry_price=Decimal("180.00"),
        current_price=Decimal("181.50"),
        stop_loss=Decimal("178.00"),
        take_profit=Decimal("185.00"),
        opened_at=datetime.now(UTC),
    )


class TestExecutionOrderAdapter:
    """Test the execution order adapter."""

    def test_initialization(self, order_adapter, mock_order_execution_manager):
        """Test adapter initialization."""
        assert order_adapter.order_execution_manager == mock_order_execution_manager
        assert order_adapter.default_risk_category == RiskCategory.NORMAL
        assert order_adapter.execution_orders == {}

    @pytest.mark.asyncio
    async def test_handle_enter_long_signal(self, order_adapter, sample_context):
        """Test handling of enter long signal."""
        signal = ExecutionSignal(
            action=ExecutionAction.ENTER_LONG,
            confidence=0.8,
            reasoning="Strong bullish signal",
            metadata={"close_price": 181.50},
        )
        
        signal_data = {
            "function_name": "close_above_test",
            "symbol": "AAPL",
            "timeframe": Timeframe.ONE_MIN,
            "signal": signal,
            "context": sample_context,
            "timestamp": datetime.now(UTC),
        }
        
        result = await order_adapter.handle_execution_signal(signal_data)
        
        assert result is not None
        assert result.success is True
        assert result.order_id == "TEST123"
        
        # Should have placed market order
        order_adapter.order_execution_manager.place_market_order.assert_called_once()
        
        # Check order request
        call_args = order_adapter.order_execution_manager.place_market_order.call_args[0][0]
        assert call_args.symbol == "AAPL"
        assert call_args.side == OrderSide.BUY
        assert call_args.order_type == "MKT"
        assert call_args.risk_category == RiskCategory.LARGE  # High confidence

    @pytest.mark.asyncio
    async def test_handle_enter_short_signal(self, order_adapter, sample_context):
        """Test handling of enter short signal."""
        signal = ExecutionSignal(
            action=ExecutionAction.ENTER_SHORT,
            confidence=0.6,
            reasoning="Bearish signal",
            metadata={"close_price": 181.50},
        )
        
        signal_data = {
            "function_name": "close_below_test",
            "symbol": "AAPL",
            "timeframe": Timeframe.ONE_MIN,
            "signal": signal,
            "context": sample_context,
            "timestamp": datetime.now(UTC),
        }
        
        result = await order_adapter.handle_execution_signal(signal_data)
        
        assert result is not None
        assert result.success is True
        
        # Should have placed market order
        order_adapter.order_execution_manager.place_market_order.assert_called_once()
        
        # Check order request
        call_args = order_adapter.order_execution_manager.place_market_order.call_args[0][0]
        assert call_args.symbol == "AAPL"
        assert call_args.side == OrderSide.SELL
        assert call_args.risk_category == RiskCategory.NORMAL  # Medium confidence

    @pytest.mark.asyncio
    async def test_handle_exit_signal_with_position(self, order_adapter, sample_context, sample_position):
        """Test handling of exit signal with open position."""
        # Update context with position
        context_with_position = ExecutionContext(
            symbol=sample_context.symbol,
            timeframe=sample_context.timeframe,
            current_bar=sample_context.current_bar,
            historical_bars=sample_context.historical_bars,
            trade_plan_params=sample_context.trade_plan_params,
            position_state=sample_position,
            account_balance=sample_context.account_balance,
            timestamp=sample_context.timestamp,
        )
        
        signal = ExecutionSignal(
            action=ExecutionAction.EXIT,
            confidence=1.0,
            reasoning="Stop loss triggered",
        )
        
        signal_data = {
            "function_name": "trailing_stop_test",
            "symbol": "AAPL",
            "timeframe": Timeframe.ONE_MIN,
            "signal": signal,
            "context": context_with_position,
            "timestamp": datetime.now(UTC),
        }
        
        result = await order_adapter.handle_execution_signal(signal_data)
        
        assert result is not None
        assert result.success is True
        
        # Should have placed market order
        order_adapter.order_execution_manager.place_market_order.assert_called_once()
        
        # Check order request - should be opposite side of position
        call_args = order_adapter.order_execution_manager.place_market_order.call_args[0][0]
        assert call_args.symbol == "AAPL"
        assert call_args.side == OrderSide.SELL  # Opposite of long position
        assert call_args.quantity == 100  # Same as position size

    @pytest.mark.asyncio
    async def test_handle_exit_signal_no_position(self, order_adapter, sample_context):
        """Test handling of exit signal without position."""
        signal = ExecutionSignal(
            action=ExecutionAction.EXIT,
            confidence=1.0,
            reasoning="Stop loss triggered",
        )
        
        signal_data = {
            "function_name": "trailing_stop_test",
            "symbol": "AAPL",
            "timeframe": Timeframe.ONE_MIN,
            "signal": signal,
            "context": sample_context,  # No position
            "timestamp": datetime.now(UTC),
        }
        
        result = await order_adapter.handle_execution_signal(signal_data)
        
        # Should return None (no order placed)
        assert result is None
        order_adapter.order_execution_manager.place_market_order.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_modify_stop_signal(self, order_adapter, sample_context, sample_position):
        """Test handling of modify stop signal."""
        context_with_position = ExecutionContext(
            symbol=sample_context.symbol,
            timeframe=sample_context.timeframe,
            current_bar=sample_context.current_bar,
            historical_bars=sample_context.historical_bars,
            trade_plan_params=sample_context.trade_plan_params,
            position_state=sample_position,
            account_balance=sample_context.account_balance,
            timestamp=sample_context.timestamp,
        )
        
        signal = ExecutionSignal(
            action=ExecutionAction.MODIFY_STOP,
            confidence=1.0,
            reasoning="Trailing stop adjustment",
            metadata={"new_stop_level": 179.50},
        )
        
        signal_data = {
            "function_name": "trailing_stop_test",
            "symbol": "AAPL",
            "timeframe": Timeframe.ONE_MIN,
            "signal": signal,
            "context": context_with_position,
            "timestamp": datetime.now(UTC),
        }
        
        result = await order_adapter.handle_execution_signal(signal_data)
        
        assert result is not None
        assert result.success is True
        
        # Should have placed stop order
        order_adapter.order_execution_manager.place_stop_order.assert_called_once()
        
        # Check order request
        call_args = order_adapter.order_execution_manager.place_stop_order.call_args[0][0]
        assert call_args.symbol == "AAPL"
        assert call_args.side == OrderSide.SELL  # Opposite of long position
        assert call_args.stop_price == Decimal("179.50")

    @pytest.mark.asyncio
    async def test_handle_no_action_signal(self, order_adapter, sample_context):
        """Test handling of no action signal."""
        signal = ExecutionSignal(
            action=ExecutionAction.NONE,
            confidence=0.3,
            reasoning="No clear signal",
        )
        
        signal_data = {
            "function_name": "test_function",
            "symbol": "AAPL",
            "timeframe": Timeframe.ONE_MIN,
            "signal": signal,
            "context": sample_context,
            "timestamp": datetime.now(UTC),
        }
        
        result = await order_adapter.handle_execution_signal(signal_data)
        
        # Should return None (no order placed)
        assert result is None
        order_adapter.order_execution_manager.place_market_order.assert_not_called()

    def test_confidence_to_risk_category_mapping(self, order_adapter):
        """Test confidence to risk category mapping."""
        # High confidence
        risk_cat = order_adapter._map_confidence_to_risk_category(0.9)
        assert risk_cat == RiskCategory.LARGE
        
        # Medium confidence
        risk_cat = order_adapter._map_confidence_to_risk_category(0.7)
        assert risk_cat == RiskCategory.NORMAL
        
        # Low confidence
        risk_cat = order_adapter._map_confidence_to_risk_category(0.4)
        assert risk_cat == RiskCategory.SMALL

    def test_generate_execution_id(self, order_adapter, sample_context):
        """Test execution ID generation."""
        execution_id = order_adapter._generate_execution_id("test_function", sample_context)
        
        assert "test_function" in execution_id
        assert "AAPL" in execution_id
        assert "1min" in execution_id
        # Should contain timestamp
        assert len(execution_id.split("_")) == 4

    @pytest.mark.asyncio
    async def test_order_tracking(self, order_adapter, sample_context):
        """Test that orders are tracked properly."""
        signal = ExecutionSignal(
            action=ExecutionAction.ENTER_LONG,
            confidence=0.8,
            reasoning="Test signal",
            metadata={"close_price": 181.50},
        )
        
        signal_data = {
            "function_name": "test_function",
            "symbol": "AAPL",
            "timeframe": Timeframe.ONE_MIN,
            "signal": signal,
            "context": sample_context,
            "timestamp": datetime.now(UTC),
        }
        
        result = await order_adapter.handle_execution_signal(signal_data)
        
        assert result.success is True
        
        # Should track the order
        execution_orders = order_adapter.get_execution_orders()
        assert len(execution_orders) == 1
        assert "TEST123" in execution_orders.values()

    @pytest.mark.asyncio
    async def test_error_handling(self, order_adapter, sample_context, mock_order_execution_manager):
        """Test error handling during order placement."""
        # Mock order manager to raise exception
        mock_order_execution_manager.place_market_order.side_effect = Exception("Test error")
        
        signal = ExecutionSignal(
            action=ExecutionAction.ENTER_LONG,
            confidence=0.8,
            reasoning="Test signal",
            metadata={"close_price": 181.50},
        )
        
        signal_data = {
            "function_name": "test_function",
            "symbol": "AAPL",
            "timeframe": Timeframe.ONE_MIN,
            "signal": signal,
            "context": sample_context,
            "timestamp": datetime.now(UTC),
        }
        
        result = await order_adapter.handle_execution_signal(signal_data)
        
        # Should return error result
        assert result is not None
        assert result.success is False
        assert "Test error" in result.error_message

    def test_get_stats(self, order_adapter):
        """Test statistics gathering."""
        # Add some tracked order
        order_adapter.execution_orders["test_id"] = "order_123"
        
        stats = order_adapter.get_stats()
        
        assert "tracked_orders" in stats
        assert "default_risk_category" in stats
        assert "config" in stats
        assert stats["tracked_orders"] == 1
        assert stats["default_risk_category"] == "NORMAL"