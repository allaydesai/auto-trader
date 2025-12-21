"""Comprehensive tests for SimulatedOrderExecution class."""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from decimal import Decimal

from auto_trader.order_execution.simulated_execution import SimulatedOrderExecution
from auto_trader.models.order import Order, OrderResult, BracketOrder, OrderModification
from auto_trader.models.enums import OrderStatus, OrderSide, OrderType


@pytest.fixture
def mock_engine():
    """Provide a mock OrderSimulationEngine for testing."""
    with patch(
        "auto_trader.order_execution.simulated_execution.OrderSimulationEngine"
    ) as mock:
        engine_instance = Mock()
        mock.return_value = engine_instance
        yield engine_instance


@pytest.fixture
def simulated_execution(mock_engine):
    """Provide a SimulatedOrderExecution instance with mocked engine."""
    return SimulatedOrderExecution()


@pytest.fixture
def sample_order():
    """Provide a sample order for testing."""
    return Order(
        order_id="TEST_001",
        trade_plan_id="PLAN_001",
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=100,
        status=OrderStatus.PENDING,
    )


@pytest.fixture
def sample_bracket_order():
    """Provide a sample bracket order for testing."""
    parent = Order(
        order_id="PARENT_001",
        trade_plan_id="PLAN_001",
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        quantity=100,
        transmit=False,
    )
    stop_loss = Order(
        order_id="SL_001",
        parent_order_id="PARENT_001",
        trade_plan_id="PLAN_001",
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.STOP,
        quantity=100,
        stop_price=Decimal("180.00"),
        transmit=False,
    )
    take_profit = Order(
        order_id="TP_001",
        parent_order_id="PARENT_001",
        trade_plan_id="PLAN_001",
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=100,
        price=Decimal("200.00"),
        transmit=True,
    )
    return BracketOrder(
        bracket_id="BRACKET_001",
        trade_plan_id="PLAN_001",
        parent_order=parent,
        stop_loss_order=stop_loss,
        take_profit_order=take_profit,
    )


@pytest.fixture
def sample_order_modification():
    """Provide a sample order modification for testing."""
    return OrderModification(
        order_id="TEST_001",
        new_quantity=150,
        reason="Increased position size based on volatility",
    )


class TestSimulatedOrderExecutionInit:
    """Test initialization of SimulatedOrderExecution."""

    def test_init_creates_engine(self, mock_engine):
        """Test that __init__ initializes OrderSimulationEngine."""
        execution = SimulatedOrderExecution()

        assert execution._engine == mock_engine

    def test_init_creates_empty_orders_dict(self, mock_engine):
        """Test that __init__ initializes empty orders dictionary."""
        execution = SimulatedOrderExecution()

        assert execution._orders == {}
        assert isinstance(execution._orders, dict)

    def test_init_creates_stats_dict_with_correct_keys(self, mock_engine):
        """Test that __init__ initializes stats dict with all required keys."""
        execution = SimulatedOrderExecution()

        expected_keys = {
            "orders_placed",
            "orders_filled",
            "orders_cancelled",
            "orders_modified",
            "is_simulation",
        }
        assert set(execution._stats.keys()) == expected_keys

    def test_init_sets_stats_counters_to_zero(self, mock_engine):
        """Test that __init__ sets all counters to zero."""
        execution = SimulatedOrderExecution()

        assert execution._stats["orders_placed"] == 0
        assert execution._stats["orders_filled"] == 0
        assert execution._stats["orders_cancelled"] == 0
        assert execution._stats["orders_modified"] == 0

    def test_init_sets_is_simulation_to_true(self, mock_engine):
        """Test that __init__ sets is_simulation flag to True."""
        execution = SimulatedOrderExecution()

        assert execution._stats["is_simulation"] is True


class TestPlaceMarketOrder:
    """Test place_market_order method."""

    @pytest.mark.asyncio
    async def test_place_market_order_calls_engine(
        self, simulated_execution, mock_engine, sample_order
    ):
        """Test that place_market_order delegates to engine."""
        mock_result = OrderResult(
            success=True,
            order_id="TEST_001",
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.FILLED,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )
        mock_engine.place_market_order = AsyncMock(return_value=mock_result)

        await simulated_execution.place_market_order(sample_order)

        mock_engine.place_market_order.assert_called_once_with(sample_order)

    @pytest.mark.asyncio
    async def test_place_market_order_returns_engine_result(
        self, simulated_execution, mock_engine, sample_order
    ):
        """Test that place_market_order returns engine result."""
        mock_result = OrderResult(
            success=True,
            order_id="TEST_001",
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.FILLED,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )
        mock_engine.place_market_order = AsyncMock(return_value=mock_result)

        result = await simulated_execution.place_market_order(sample_order)

        assert result == mock_result

    @pytest.mark.asyncio
    async def test_place_market_order_tracks_successful_order(
        self, simulated_execution, mock_engine, sample_order
    ):
        """Test that place_market_order tracks order when successful."""
        mock_result = OrderResult(
            success=True,
            order_id="TEST_001",
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.SUBMITTED,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )
        mock_engine.place_market_order = AsyncMock(return_value=mock_result)

        await simulated_execution.place_market_order(sample_order)

        assert "TEST_001" in simulated_execution._orders
        assert simulated_execution._orders["TEST_001"] == sample_order

    @pytest.mark.asyncio
    async def test_place_market_order_increments_placed_stat(
        self, simulated_execution, mock_engine, sample_order
    ):
        """Test that place_market_order increments orders_placed counter."""
        mock_result = OrderResult(
            success=True,
            order_id="TEST_001",
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.SUBMITTED,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )
        mock_engine.place_market_order = AsyncMock(return_value=mock_result)

        await simulated_execution.place_market_order(sample_order)

        assert simulated_execution._stats["orders_placed"] == 1

    @pytest.mark.asyncio
    async def test_place_market_order_increments_filled_stat_when_filled(
        self, simulated_execution, mock_engine, sample_order
    ):
        """Test that place_market_order increments filled counter when filled."""
        mock_result = OrderResult(
            success=True,
            order_id="TEST_001",
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.FILLED,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )
        mock_engine.place_market_order = AsyncMock(return_value=mock_result)

        await simulated_execution.place_market_order(sample_order)

        assert simulated_execution._stats["orders_filled"] == 1

    @pytest.mark.asyncio
    async def test_place_market_order_does_not_increment_filled_when_submitted(
        self, simulated_execution, mock_engine, sample_order
    ):
        """Test that place_market_order does not increment filled when submitted."""
        mock_result = OrderResult(
            success=True,
            order_id="TEST_001",
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.SUBMITTED,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )
        mock_engine.place_market_order = AsyncMock(return_value=mock_result)

        await simulated_execution.place_market_order(sample_order)

        assert simulated_execution._stats["orders_filled"] == 0

    @pytest.mark.asyncio
    async def test_place_market_order_does_not_track_failed_order(
        self, simulated_execution, mock_engine, sample_order
    ):
        """Test that place_market_order does not track order when failed."""
        mock_result = OrderResult(
            success=False,
            order_id=None,
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.REJECTED,
            error_message="Insufficient margin",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )
        mock_engine.place_market_order = AsyncMock(return_value=mock_result)

        await simulated_execution.place_market_order(sample_order)

        assert len(simulated_execution._orders) == 0

    @pytest.mark.asyncio
    async def test_place_market_order_does_not_increment_stats_when_failed(
        self, simulated_execution, mock_engine, sample_order
    ):
        """Test that place_market_order does not increment stats when failed."""
        mock_result = OrderResult(
            success=False,
            order_id=None,
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.REJECTED,
            error_message="Insufficient margin",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )
        mock_engine.place_market_order = AsyncMock(return_value=mock_result)

        await simulated_execution.place_market_order(sample_order)

        assert simulated_execution._stats["orders_placed"] == 0
        assert simulated_execution._stats["orders_filled"] == 0


class TestPlaceBracketOrder:
    """Test place_bracket_order method."""

    @pytest.mark.asyncio
    async def test_place_bracket_order_calls_engine(
        self, simulated_execution, mock_engine, sample_bracket_order
    ):
        """Test that place_bracket_order delegates to engine."""
        mock_result = OrderResult(
            success=True,
            order_id="PARENT_001",
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.FILLED,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )
        mock_engine.place_bracket_order = AsyncMock(return_value=mock_result)

        await simulated_execution.place_bracket_order(sample_bracket_order)

        mock_engine.place_bracket_order.assert_called_once_with(sample_bracket_order)

    @pytest.mark.asyncio
    async def test_place_bracket_order_returns_engine_result(
        self, simulated_execution, mock_engine, sample_bracket_order
    ):
        """Test that place_bracket_order returns engine result."""
        mock_result = OrderResult(
            success=True,
            order_id="PARENT_001",
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.FILLED,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )
        mock_engine.place_bracket_order = AsyncMock(return_value=mock_result)

        result = await simulated_execution.place_bracket_order(sample_bracket_order)

        assert result == mock_result

    @pytest.mark.asyncio
    async def test_place_bracket_order_tracks_all_three_orders(
        self, simulated_execution, mock_engine, sample_bracket_order
    ):
        """Test that place_bracket_order tracks parent, SL, and TP orders."""
        mock_result = OrderResult(
            success=True,
            order_id="PARENT_001",
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.SUBMITTED,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )
        mock_engine.place_bracket_order = AsyncMock(return_value=mock_result)

        await simulated_execution.place_bracket_order(sample_bracket_order)

        assert "PARENT_001" in simulated_execution._orders
        assert "SL_001" in simulated_execution._orders
        assert "TP_001" in simulated_execution._orders

    @pytest.mark.asyncio
    async def test_place_bracket_order_increments_placed_by_three(
        self, simulated_execution, mock_engine, sample_bracket_order
    ):
        """Test that place_bracket_order increments orders_placed by 3."""
        mock_result = OrderResult(
            success=True,
            order_id="PARENT_001",
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.SUBMITTED,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )
        mock_engine.place_bracket_order = AsyncMock(return_value=mock_result)

        await simulated_execution.place_bracket_order(sample_bracket_order)

        assert simulated_execution._stats["orders_placed"] == 3

    @pytest.mark.asyncio
    async def test_place_bracket_order_increments_filled_when_filled(
        self, simulated_execution, mock_engine, sample_bracket_order
    ):
        """Test that place_bracket_order increments filled counter when filled."""
        mock_result = OrderResult(
            success=True,
            order_id="PARENT_001",
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.FILLED,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )
        mock_engine.place_bracket_order = AsyncMock(return_value=mock_result)

        await simulated_execution.place_bracket_order(sample_bracket_order)

        assert simulated_execution._stats["orders_filled"] == 1

    @pytest.mark.asyncio
    async def test_place_bracket_order_does_not_track_failed_order(
        self, simulated_execution, mock_engine, sample_bracket_order
    ):
        """Test that place_bracket_order does not track orders when failed."""
        mock_result = OrderResult(
            success=False,
            order_id=None,
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.REJECTED,
            error_message="Bracket order rejected",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )
        mock_engine.place_bracket_order = AsyncMock(return_value=mock_result)

        await simulated_execution.place_bracket_order(sample_bracket_order)

        assert len(simulated_execution._orders) == 0

    @pytest.mark.asyncio
    async def test_place_bracket_order_does_not_increment_stats_when_failed(
        self, simulated_execution, mock_engine, sample_bracket_order
    ):
        """Test that place_bracket_order does not increment stats when failed."""
        mock_result = OrderResult(
            success=False,
            order_id=None,
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.REJECTED,
            error_message="Bracket order rejected",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )
        mock_engine.place_bracket_order = AsyncMock(return_value=mock_result)

        await simulated_execution.place_bracket_order(sample_bracket_order)

        assert simulated_execution._stats["orders_placed"] == 0
        assert simulated_execution._stats["orders_filled"] == 0


class TestModifyOrder:
    """Test modify_order method."""

    @pytest.mark.asyncio
    async def test_modify_order_calls_engine(
        self, simulated_execution, mock_engine, sample_order, sample_order_modification
    ):
        """Test that modify_order delegates to engine."""
        mock_result = OrderResult(
            success=True,
            order_id="TEST_001",
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.SUBMITTED,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=150,
            order_type=OrderType.MARKET,
        )
        mock_engine.modify_order = AsyncMock(return_value=mock_result)

        await simulated_execution.modify_order(sample_order, sample_order_modification)

        mock_engine.modify_order.assert_called_once_with(
            sample_order, sample_order_modification
        )

    @pytest.mark.asyncio
    async def test_modify_order_returns_engine_result(
        self, simulated_execution, mock_engine, sample_order, sample_order_modification
    ):
        """Test that modify_order returns engine result."""
        mock_result = OrderResult(
            success=True,
            order_id="TEST_001",
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.SUBMITTED,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=150,
            order_type=OrderType.MARKET,
        )
        mock_engine.modify_order = AsyncMock(return_value=mock_result)

        result = await simulated_execution.modify_order(
            sample_order, sample_order_modification
        )

        assert result == mock_result

    @pytest.mark.asyncio
    async def test_modify_order_increments_modified_stat(
        self, simulated_execution, mock_engine, sample_order, sample_order_modification
    ):
        """Test that modify_order increments orders_modified counter."""
        mock_result = OrderResult(
            success=True,
            order_id="TEST_001",
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.SUBMITTED,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=150,
            order_type=OrderType.MARKET,
        )
        mock_engine.modify_order = AsyncMock(return_value=mock_result)

        await simulated_execution.modify_order(sample_order, sample_order_modification)

        assert simulated_execution._stats["orders_modified"] == 1

    @pytest.mark.asyncio
    async def test_modify_order_updates_tracked_order(
        self, simulated_execution, mock_engine, sample_order, sample_order_modification
    ):
        """Test that modify_order updates order in tracking dict."""
        # First place the order
        simulated_execution._orders["TEST_001"] = sample_order

        mock_result = OrderResult(
            success=True,
            order_id="TEST_001",
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.SUBMITTED,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=150,
            order_type=OrderType.MARKET,
        )
        mock_engine.modify_order = AsyncMock(return_value=mock_result)

        await simulated_execution.modify_order(sample_order, sample_order_modification)

        assert simulated_execution._orders["TEST_001"] == sample_order

    @pytest.mark.asyncio
    async def test_modify_order_does_not_increment_stat_when_failed(
        self, simulated_execution, mock_engine, sample_order, sample_order_modification
    ):
        """Test that modify_order does not increment stat when failed."""
        mock_result = OrderResult(
            success=False,
            order_id="TEST_001",
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.SUBMITTED,
            error_message="Modification rejected",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )
        mock_engine.modify_order = AsyncMock(return_value=mock_result)

        await simulated_execution.modify_order(sample_order, sample_order_modification)

        assert simulated_execution._stats["orders_modified"] == 0

    @pytest.mark.asyncio
    async def test_modify_order_handles_untracked_order(
        self, simulated_execution, mock_engine, sample_order, sample_order_modification
    ):
        """Test that modify_order handles order not in tracking dict."""
        mock_result = OrderResult(
            success=True,
            order_id="TEST_001",
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.SUBMITTED,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=150,
            order_type=OrderType.MARKET,
        )
        mock_engine.modify_order = AsyncMock(return_value=mock_result)

        await simulated_execution.modify_order(sample_order, sample_order_modification)

        # Should not crash, stat should still increment
        assert simulated_execution._stats["orders_modified"] == 1


class TestCancelOrder:
    """Test cancel_order method."""

    @pytest.mark.asyncio
    async def test_cancel_order_calls_engine(
        self, simulated_execution, mock_engine, sample_order
    ):
        """Test that cancel_order delegates to engine."""
        mock_result = OrderResult(
            success=True,
            order_id="TEST_001",
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.CANCELLED,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )
        mock_engine.cancel_order = AsyncMock(return_value=mock_result)

        await simulated_execution.cancel_order(sample_order)

        mock_engine.cancel_order.assert_called_once_with(sample_order)

    @pytest.mark.asyncio
    async def test_cancel_order_returns_engine_result(
        self, simulated_execution, mock_engine, sample_order
    ):
        """Test that cancel_order returns engine result."""
        mock_result = OrderResult(
            success=True,
            order_id="TEST_001",
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.CANCELLED,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )
        mock_engine.cancel_order = AsyncMock(return_value=mock_result)

        result = await simulated_execution.cancel_order(sample_order)

        assert result == mock_result

    @pytest.mark.asyncio
    async def test_cancel_order_increments_cancelled_stat(
        self, simulated_execution, mock_engine, sample_order
    ):
        """Test that cancel_order increments orders_cancelled counter."""
        mock_result = OrderResult(
            success=True,
            order_id="TEST_001",
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.CANCELLED,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )
        mock_engine.cancel_order = AsyncMock(return_value=mock_result)

        await simulated_execution.cancel_order(sample_order)

        assert simulated_execution._stats["orders_cancelled"] == 1

    @pytest.mark.asyncio
    async def test_cancel_order_updates_tracked_order(
        self, simulated_execution, mock_engine, sample_order
    ):
        """Test that cancel_order updates order in tracking dict."""
        # First place the order
        simulated_execution._orders["TEST_001"] = sample_order

        mock_result = OrderResult(
            success=True,
            order_id="TEST_001",
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.CANCELLED,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )
        mock_engine.cancel_order = AsyncMock(return_value=mock_result)

        await simulated_execution.cancel_order(sample_order)

        assert simulated_execution._orders["TEST_001"] == sample_order

    @pytest.mark.asyncio
    async def test_cancel_order_does_not_increment_stat_when_failed(
        self, simulated_execution, mock_engine, sample_order
    ):
        """Test that cancel_order does not increment stat when failed."""
        mock_result = OrderResult(
            success=False,
            order_id="TEST_001",
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.SUBMITTED,
            error_message="Cancellation rejected",
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )
        mock_engine.cancel_order = AsyncMock(return_value=mock_result)

        await simulated_execution.cancel_order(sample_order)

        assert simulated_execution._stats["orders_cancelled"] == 0

    @pytest.mark.asyncio
    async def test_cancel_order_handles_untracked_order(
        self, simulated_execution, mock_engine, sample_order
    ):
        """Test that cancel_order handles order not in tracking dict."""
        mock_result = OrderResult(
            success=True,
            order_id="TEST_001",
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.CANCELLED,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )
        mock_engine.cancel_order = AsyncMock(return_value=mock_result)

        await simulated_execution.cancel_order(sample_order)

        # Should not crash, stat should still increment
        assert simulated_execution._stats["orders_cancelled"] == 1


class TestGetOrderStatus:
    """Test get_order_status method."""

    @pytest.mark.asyncio
    async def test_get_order_status_returns_tracked_order(
        self, simulated_execution, sample_order
    ):
        """Test that get_order_status returns order from tracking dict."""
        simulated_execution._orders["TEST_001"] = sample_order

        result = await simulated_execution.get_order_status("TEST_001")

        assert result == sample_order

    @pytest.mark.asyncio
    async def test_get_order_status_returns_none_for_unknown_order(
        self, simulated_execution
    ):
        """Test that get_order_status returns None for unknown order ID."""
        result = await simulated_execution.get_order_status("UNKNOWN_ID")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_order_status_does_not_call_engine(
        self, simulated_execution, mock_engine, sample_order
    ):
        """Test that get_order_status does not call engine."""
        simulated_execution._orders["TEST_001"] = sample_order

        await simulated_execution.get_order_status("TEST_001")

        # Verify no methods were called on the engine
        assert not mock_engine.method_calls


class TestGetStats:
    """Test get_stats method."""

    def test_get_stats_returns_stats_dict(self, simulated_execution):
        """Test that get_stats returns stats dictionary."""
        stats = simulated_execution.get_stats()

        expected_keys = {
            "orders_placed",
            "orders_filled",
            "orders_cancelled",
            "orders_modified",
            "is_simulation",
        }
        assert set(stats.keys()) == expected_keys

    def test_get_stats_returns_copy_not_reference(self, simulated_execution):
        """Test that get_stats returns copy of stats dict."""
        stats1 = simulated_execution.get_stats()
        stats2 = simulated_execution.get_stats()

        # Modify returned dict
        stats1["orders_placed"] = 999

        # Original should be unchanged
        assert stats2["orders_placed"] == 0
        assert simulated_execution._stats["orders_placed"] == 0

    def test_get_stats_reflects_current_counts(self, simulated_execution):
        """Test that get_stats reflects current counter values."""
        simulated_execution._stats["orders_placed"] = 5
        simulated_execution._stats["orders_filled"] = 3
        simulated_execution._stats["orders_cancelled"] = 1
        simulated_execution._stats["orders_modified"] = 2

        stats = simulated_execution.get_stats()

        assert stats["orders_placed"] == 5
        assert stats["orders_filled"] == 3
        assert stats["orders_cancelled"] == 1
        assert stats["orders_modified"] == 2
        assert stats["is_simulation"] is True


class TestIntegrationScenarios:
    """Test integration scenarios with multiple operations."""

    @pytest.mark.asyncio
    async def test_multiple_orders_increment_stats_correctly(
        self, simulated_execution, mock_engine
    ):
        """Test that multiple orders increment stats correctly."""
        # Setup mock
        mock_result = OrderResult(
            success=True,
            order_id="TEST_001",
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.FILLED,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )
        mock_engine.place_market_order = AsyncMock(return_value=mock_result)

        # Place three orders
        for i in range(3):
            order = Order(
                order_id=f"TEST_{i:03d}",
                trade_plan_id="PLAN_001",
                symbol="AAPL",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=100,
            )
            await simulated_execution.place_market_order(order)

        stats = simulated_execution.get_stats()
        assert stats["orders_placed"] == 3
        assert stats["orders_filled"] == 3

    @pytest.mark.asyncio
    async def test_mixed_operations_track_stats_independently(
        self, simulated_execution, mock_engine, sample_order, sample_order_modification
    ):
        """Test that different operations track stats independently."""
        # Place order
        place_result = OrderResult(
            success=True,
            order_id="TEST_001",
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.SUBMITTED,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
        )
        mock_engine.place_market_order = AsyncMock(return_value=place_result)
        await simulated_execution.place_market_order(sample_order)

        # Modify order
        modify_result = OrderResult(
            success=True,
            order_id="TEST_001",
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.SUBMITTED,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=150,
            order_type=OrderType.MARKET,
        )
        mock_engine.modify_order = AsyncMock(return_value=modify_result)
        await simulated_execution.modify_order(sample_order, sample_order_modification)

        # Cancel order
        cancel_result = OrderResult(
            success=True,
            order_id="TEST_001",
            trade_plan_id="PLAN_001",
            order_status=OrderStatus.CANCELLED,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=150,
            order_type=OrderType.MARKET,
        )
        mock_engine.cancel_order = AsyncMock(return_value=cancel_result)
        await simulated_execution.cancel_order(sample_order)

        stats = simulated_execution.get_stats()
        assert stats["orders_placed"] == 1
        assert stats["orders_filled"] == 0
        assert stats["orders_modified"] == 1
        assert stats["orders_cancelled"] == 1
