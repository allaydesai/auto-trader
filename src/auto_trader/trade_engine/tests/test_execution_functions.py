"""Tests for execution function framework."""

import pytest
from decimal import Decimal
from datetime import datetime, UTC

from auto_trader.models.execution import (
    ExecutionContext,
    ExecutionSignal,
    ExecutionFunctionConfig,
    PositionState,
)
from auto_trader.models.enums import ExecutionAction, Timeframe
from auto_trader.models.market_data import BarData
from auto_trader.trade_engine.execution_functions import ExecutionFunctionBase
from auto_trader.trade_engine.function_registry import ExecutionFunctionRegistry
from auto_trader.trade_engine.functions import (
    CloseAboveFunction,
    CloseBelowFunction,
    TrailingStopFunction,
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
        historical_bars=[sample_bar] * 20,  # 20 bars of history
        trade_plan_params={"threshold_price": 180.0},
        position_state=None,
        account_balance=Decimal("10000"),
        timestamp=datetime.now(UTC),
    )


class TestExecutionFunctionRegistry:
    """Test the function registry system."""

    def test_singleton_pattern(self):
        """Test that registry instances are separate (no singleton pattern)."""
        registry1 = ExecutionFunctionRegistry()
        registry2 = ExecutionFunctionRegistry()
        assert registry1 is not registry2

    @pytest.mark.asyncio
    async def test_register_function(self):
        """Test registering a function type."""
        registry = ExecutionFunctionRegistry()
        await registry.clear_all()  # Start fresh

        await registry.register("close_above", CloseAboveFunction)
        assert "close_above" in registry.list_registered_types()

    @pytest.mark.asyncio
    async def test_create_function_instance(self):
        """Test creating a function instance."""
        registry = ExecutionFunctionRegistry()
        await registry.clear_all()
        await registry.register("close_above", CloseAboveFunction)

        config = ExecutionFunctionConfig(
            name="test_function",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 180.0},
        )

        instance = await registry.create_function(config)
        assert instance is not None
        assert instance.name == "test_function"
        assert instance.timeframe == Timeframe.ONE_MIN


class TestCloseAboveFunction:
    """Test the CloseAboveFunction."""

    @pytest.mark.asyncio
    async def test_close_above_triggers(self, sample_context):
        """Test that close above triggers correctly."""
        config = ExecutionFunctionConfig(
            name="test_close_above",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 180.0},
        )

        function = CloseAboveFunction(config)
        signal = await function.evaluate(sample_context)

        assert signal.action == ExecutionAction.ENTER_LONG
        assert signal.confidence > 0.5
        assert "above threshold" in signal.reasoning

    @pytest.mark.asyncio
    async def test_close_above_no_trigger(self, sample_context):
        """Test that close above doesn't trigger below threshold."""
        config = ExecutionFunctionConfig(
            name="test_close_above",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 185.0},  # Above current price
        )

        function = CloseAboveFunction(config)
        signal = await function.evaluate(sample_context)

        assert signal.action == ExecutionAction.NONE
        assert signal.confidence == 0.0


class TestCloseBelowFunction:
    """Test the CloseBelowFunction."""

    @pytest.mark.asyncio
    async def test_close_below_triggers(self, sample_context):
        """Test that close below triggers correctly."""
        config = ExecutionFunctionConfig(
            name="test_close_below",
            function_type="close_below",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 182.0, "action": "ENTER_SHORT"},
        )

        function = CloseBelowFunction(config)
        signal = await function.evaluate(sample_context)

        assert signal.action == ExecutionAction.ENTER_SHORT
        assert signal.confidence > 0.5
        assert "below" in signal.reasoning.lower()


class TestTrailingStopFunction:
    """Test the TrailingStopFunction."""

    @pytest.mark.asyncio
    async def test_trailing_stop_no_position(self, sample_context):
        """Test trailing stop with no position."""
        config = ExecutionFunctionConfig(
            name="test_trailing",
            function_type="trailing_stop",
            timeframe=Timeframe.ONE_MIN,
            parameters={"trail_percentage": 2.0},
        )

        function = TrailingStopFunction(config)
        signal = await function.evaluate(sample_context)

        assert signal.action == ExecutionAction.NONE
        assert "No position" in signal.reasoning

    @pytest.mark.asyncio
    async def test_trailing_stop_with_position(self, sample_bar):
        """Test trailing stop with open position."""
        position = PositionState(
            symbol="AAPL",
            quantity=100,
            entry_price=Decimal("175.00"),
            current_price=Decimal("181.50"),
            stop_loss=Decimal("173.00"),
            take_profit=None,
            opened_at=datetime.now(UTC),
        )

        context = ExecutionContext(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            current_bar=sample_bar,
            historical_bars=[sample_bar] * 20,
            trade_plan_params={},
            position_state=position,
            account_balance=Decimal("10000"),
            timestamp=datetime.now(UTC),
        )

        config = ExecutionFunctionConfig(
            name="test_trailing",
            function_type="trailing_stop",
            timeframe=Timeframe.ONE_MIN,
            parameters={"trail_percentage": 2.0},
        )

        function = TrailingStopFunction(config)
        signal = await function.evaluate(context)

        # Should not exit as price is above stop
        assert signal.action in [ExecutionAction.NONE, ExecutionAction.MODIFY_STOP]