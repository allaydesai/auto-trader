"""
Complete Trade Lifecycle Integration Test

This test validates the COMPLETE trade lifecycle:
1. Load trade plan with entry and exit functions
2. Evaluate plan on each market data bar
3. Trigger entry signal → place order → open position
4. Continue evaluating exit function for open position
5. Trigger exit signal → close position → complete plan

This test will EXPOSE the current integration gaps:
- Gap #1: Exit functions not evaluated (position_plans not in evaluation loop)
- Gap #2: Function instantiation from plan configs
- Gap #3: Timeframe matching

After fixing the gaps, this test should PASS.
"""

import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime, UTC
from decimal import Decimal

from auto_trader.models.trade_plan import (
    TradePlan,
    TradePlanStatus,
    RiskCategory,
    ExecutionFunction as PlanExecutionFunction,
)
from auto_trader.models.plan_loader import TradePlanLoader
from auto_trader.models.market_data import BarData
from auto_trader.models.enums import Timeframe, OrderStatus
from auto_trader.models.order import OrderResult
from auto_trader.trade_engine.trade_orchestrator import (
    TradeOrchestrator,
    TradeOrchestrationConfig,
)
from auto_trader.trade_engine.function_registry import ExecutionFunctionRegistry
from auto_trader.trade_engine.functions import CloseAboveFunction, CloseBelowFunction
from auto_trader.integrations.ibkr_client.order_execution_manager import (
    OrderExecutionManager,
)
from auto_trader.risk_management.risk_manager import RiskManager
from auto_trader.risk_management.order_risk_validator import OrderRiskValidator


# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def sample_trade_plan():
    """Create a sample trade plan with entry and exit functions."""
    return TradePlan(
        plan_id="AAPL_20250815_001",
        symbol="AAPL",
        entry_level=Decimal("180.50"),
        stop_loss=Decimal("178.00"),
        take_profit=Decimal("185.00"),
        risk_category=RiskCategory.NORMAL,
        # Entry function: trigger when price closes above 180.50 on 15min bar
        entry_function=PlanExecutionFunction(
            function_type="close_above",
            timeframe="15min",
            parameters={"threshold": 180.50},
            last_evaluated=None,
        ),
        # Stop loss function: trigger when price closes below 178.00 on 15min bar
        stop_loss_function=PlanExecutionFunction(
            function_type="close_below",
            timeframe="15min",
            parameters={"threshold": 178.00},
            last_evaluated=None,
        ),
        # Take profit function: trigger when price closes above 185.00 on 15min bar
        take_profit_function=PlanExecutionFunction(
            function_type="close_above",
            timeframe="15min",
            parameters={"threshold": 185.00},
            last_evaluated=None,
        ),
        status=TradePlanStatus.AWAITING_ENTRY,
        calculated_position_size=80,
        dollar_risk=Decimal("200.00"),
    )


@pytest.fixture
async def function_registry():
    """Create and initialize function registry."""
    registry = ExecutionFunctionRegistry()
    await registry.clear_all()

    # Register the execution function types
    await registry.register("close_above", CloseAboveFunction)
    await registry.register("close_below", CloseBelowFunction)

    yield registry

    await registry.clear_all()


@pytest.fixture
def mock_trade_plan_loader(sample_trade_plan):
    """Create mock trade plan loader."""
    loader = Mock(spec=TradePlanLoader)
    # load_all_plans is synchronous in the real implementation
    loader.load_all_plans = Mock(
        return_value={sample_trade_plan.plan_id: sample_trade_plan}
    )
    loader.get_plan = Mock(return_value=sample_trade_plan)
    # save_plan doesn't exist yet in TradePlanLoader - mocking for future implementation
    loader.save_plan = AsyncMock()
    loader.reload_plans = Mock()
    return loader


@pytest.fixture
def mock_risk_manager():
    """Create mock risk manager."""
    risk_manager = Mock(spec=RiskManager)
    risk_manager.account_value = Decimal("10000")

    # Mock position sizer
    risk_manager.position_sizer = Mock()
    risk_manager.position_sizer.calculate_position_size = Mock(
        return_value=Mock(
            position_size=80,
            dollar_risk=Decimal("200.00"),
            portfolio_risk_percentage=Decimal("2.0"),
        )
    )

    # Mock portfolio tracker
    risk_manager.portfolio_tracker = Mock()
    risk_manager.portfolio_tracker.add_position = Mock()
    risk_manager.portfolio_tracker.remove_position = Mock()
    risk_manager.portfolio_tracker.get_current_portfolio_risk = Mock(
        return_value=Decimal("0.0")
    )

    # Mock remove_position method for cleanup
    risk_manager.remove_position = AsyncMock()

    # Mock validation
    risk_manager.validate_trade_plan = Mock(
        return_value=Mock(
            is_valid=True,
            passed=True,
            position_size_result=Mock(position_size=80, dollar_risk=Decimal("200.00")),
            errors=[],
        )
    )

    return risk_manager


@pytest.fixture
def mock_order_execution_manager():
    """Create mock order execution manager."""
    manager = Mock(spec=OrderExecutionManager)

    # Track orders placed
    manager.orders_placed = []

    async def mock_place_order(order_request):
        """Mock order placement that tracks calls."""
        manager.orders_placed.append(order_request)

        # Handle both dict and object order requests
        if isinstance(order_request, dict):
            trade_plan_id = order_request.get("trade_plan_id")
            symbol = order_request.get("symbol")
            side = order_request.get("side")
            quantity = order_request.get(
                "quantity", order_request.get("calculated_position_size")
            )
            order_type = order_request.get("order_type", "MKT")
        else:
            trade_plan_id = order_request.trade_plan_id
            symbol = order_request.symbol
            side = order_request.side
            quantity = order_request.calculated_position_size
            order_type = order_request.order_type

        return OrderResult(
            success=True,
            order_id=f"ORDER_{len(manager.orders_placed)}",
            trade_plan_id=trade_plan_id,
            order_status=OrderStatus.FILLED,
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            filled_quantity=quantity,
            average_fill_price=Decimal("180.75"),
        )

    manager.place_market_order = AsyncMock(side_effect=mock_place_order)
    manager.place_bracket_order = AsyncMock(side_effect=mock_place_order)
    manager.place_order = AsyncMock(side_effect=mock_place_order)

    return manager


@pytest.fixture
async def orchestrator(
    mock_trade_plan_loader,
    function_registry,
    mock_order_execution_manager,
    mock_risk_manager,
):
    """Create trade orchestrator with all dependencies."""

    # Create order risk validator
    order_risk_validator = Mock(spec=OrderRiskValidator)
    order_risk_validator.validate_order_request = AsyncMock(
        return_value=Mock(is_valid=True, errors=[])
    )

    # Patch the order execution manager to include risk validator
    mock_order_execution_manager.risk_validator = order_risk_validator

    config = TradeOrchestrationConfig(
        max_concurrent_trades=10,
        signal_timeout_seconds=30,
        state_save_interval_seconds=60,
        enable_position_tracking=True,
        enable_risk_validation=True,
        minimum_confidence_threshold=0.5,  # Lower threshold for testing
    )

    orchestrator = TradeOrchestrator(
        trade_plan_loader=mock_trade_plan_loader,
        function_registry=function_registry,
        order_execution_manager=mock_order_execution_manager,
        risk_manager=mock_risk_manager,
        config=config,
        market_hours_only=False,  # Disable for testing
    )

    return orchestrator


# ============================================================================
# Helper Functions
# ============================================================================


def create_bar(
    symbol: str = "AAPL",
    close_price: float = 180.00,
    timeframe: str = "15min",
    timestamp: datetime = None,
) -> BarData:
    """Create a market data bar for testing."""
    return BarData(
        symbol=symbol,
        timestamp=timestamp or datetime.now(UTC),
        open_price=Decimal(str(close_price - 0.50)),
        high_price=Decimal(str(close_price + 0.50)),
        low_price=Decimal(str(close_price - 0.50)),
        close_price=Decimal(str(close_price)),
        volume=100000,
        bar_size=timeframe,
        timeframe=Timeframe(timeframe)
        if hasattr(Timeframe, timeframe.upper().replace("MIN", "_MIN"))
        else Timeframe.FIFTEEN_MIN,
    )


# ============================================================================
# Integration Tests
# ============================================================================


class TestCompleteTradeLifecycle:
    """Test complete trade lifecycle from entry to exit."""

    @pytest.mark.asyncio
    async def test_complete_lifecycle_entry_to_exit(
        self,
        orchestrator,
        sample_trade_plan,
        mock_order_execution_manager,
        function_registry,
    ):
        """
        Test the COMPLETE lifecycle:
        1. Start with plan awaiting entry
        2. Send bar that triggers entry
        3. Verify position opens
        4. Send bar that should trigger exit
        5. Verify position closes

        This test will FAIL with current code due to Gap #1:
        Exit functions are never evaluated because position_plans
        are not included in the market data processing loop.
        """

        # ================================================================
        # SETUP: Start orchestrator and load plan
        # ================================================================
        await orchestrator.start()

        # Verify plan is in active_plans
        assert sample_trade_plan.plan_id in orchestrator.active_plans
        assert sample_trade_plan.status == TradePlanStatus.AWAITING_ENTRY

        print("\n" + "=" * 70)
        print("PHASE 1: Plan loaded, awaiting entry")
        print("=" * 70)
        print(f"Plan ID: {sample_trade_plan.plan_id}")
        print(f"Status: {sample_trade_plan.status}")
        print(
            f"Entry threshold: {sample_trade_plan.entry_function.parameters['threshold']}"
        )
        print(f"Active plans: {list(orchestrator.active_plans.keys())}")
        print(f"Position plans: {list(orchestrator.position_plans.keys())}")

        # ================================================================
        # PHASE 2: Send bar BELOW entry threshold (should NOT trigger)
        # ================================================================
        print("\n" + "=" * 70)
        print("PHASE 2: Sending bar BELOW entry threshold")
        print("=" * 70)

        bar_below = create_bar(
            symbol="AAPL",
            close_price=180.00,  # Below 180.50
            timeframe="15min",
        )

        print(f"Bar: {bar_below.symbol} @ {bar_below.close_price} (15min)")
        print("Entry threshold: 180.50")
        print("Expected: NO entry signal")

        await orchestrator.process_market_data_event(bar_below)

        # Should still be awaiting entry
        assert sample_trade_plan.status == TradePlanStatus.AWAITING_ENTRY
        assert sample_trade_plan.plan_id in orchestrator.active_plans
        assert len(mock_order_execution_manager.orders_placed) == 0

        print(f"✓ Status still: {sample_trade_plan.status}")
        print(f"✓ Orders placed: {len(mock_order_execution_manager.orders_placed)}")

        # ================================================================
        # PHASE 3: Send bar ABOVE entry threshold (SHOULD trigger entry)
        # ================================================================
        print("\n" + "=" * 70)
        print("PHASE 3: Sending bar ABOVE entry threshold (ENTRY SIGNAL)")
        print("=" * 70)

        bar_entry = create_bar(
            symbol="AAPL",
            close_price=180.75,  # Above 180.50!
            timeframe="15min",
        )

        print(f"Bar: {bar_entry.symbol} @ {bar_entry.close_price} (15min)")
        print("Entry threshold: 180.50")
        print("Expected: ENTRY signal triggered")

        await orchestrator.process_market_data_event(bar_entry)

        # Verify entry happened
        assert (
            sample_trade_plan.status == TradePlanStatus.POSITION_OPEN
        ), f"Expected POSITION_OPEN, got {sample_trade_plan.status}"

        assert (
            sample_trade_plan.plan_id in orchestrator.position_plans
        ), "Plan should be in position_plans after entry"

        assert (
            sample_trade_plan.plan_id not in orchestrator.active_plans
        ), "Plan should be removed from active_plans after entry"

        assert (
            len(mock_order_execution_manager.orders_placed) >= 1
        ), "At least one order should have been placed"

        print(f"✓ Status changed to: {sample_trade_plan.status}")
        print(
            f"✓ Plan moved to position_plans: {sample_trade_plan.plan_id in orchestrator.position_plans}"
        )
        print(f"✓ Orders placed: {len(mock_order_execution_manager.orders_placed)}")
        print(f"✓ Active plans: {list(orchestrator.active_plans.keys())}")
        print(f"✓ Position plans: {list(orchestrator.position_plans.keys())}")

        # ================================================================
        # PHASE 4: Send bar ABOVE stop loss (should NOT trigger exit)
        # ================================================================
        print("\n" + "=" * 70)
        print("PHASE 4: Sending bar ABOVE stop loss (NO EXIT)")
        print("=" * 70)

        bar_no_exit = create_bar(
            symbol="AAPL",
            close_price=179.00,  # Above 178.00 stop
            timeframe="15min",
        )

        print(f"Bar: {bar_no_exit.symbol} @ {bar_no_exit.close_price} (15min)")
        print("Stop loss threshold: 178.00")
        print("Expected: NO exit signal (still above stop)")

        orders_before = len(mock_order_execution_manager.orders_placed)

        await orchestrator.process_market_data_event(bar_no_exit)

        # Should still have open position
        assert (
            sample_trade_plan.status == TradePlanStatus.POSITION_OPEN
        ), f"Position should still be open, got {sample_trade_plan.status}"

        assert (
            sample_trade_plan.plan_id in orchestrator.position_plans
        ), "Plan should still be in position_plans"

        orders_after = len(mock_order_execution_manager.orders_placed)
        print(f"✓ Status still: {sample_trade_plan.status}")
        print(f"✓ New orders: {orders_after - orders_before}")

        # ================================================================
        # PHASE 5: Send bar BELOW stop loss (SHOULD trigger exit)
        # ================================================================
        print("\n" + "=" * 70)
        print("PHASE 5: Sending bar BELOW stop loss (EXIT SIGNAL)")
        print("=" * 70)
        print("🚨 THIS IS WHERE THE BUG WILL MANIFEST!")
        print("=" * 70)

        bar_exit = create_bar(
            symbol="AAPL",
            close_price=177.50,  # Below 178.00 stop!
            timeframe="15min",
        )

        print(f"Bar: {bar_exit.symbol} @ {bar_exit.close_price} (15min)")
        print("Stop loss threshold: 178.00")
        print("Expected: EXIT signal triggered")
        print("\nCurrent state:")
        print(f"  - Plan status: {sample_trade_plan.status}")
        print(
            f"  - In active_plans: {sample_trade_plan.plan_id in orchestrator.active_plans}"
        )
        print(
            f"  - In position_plans: {sample_trade_plan.plan_id in orchestrator.position_plans}"
        )

        orders_before_exit = len(mock_order_execution_manager.orders_placed)

        await orchestrator.process_market_data_event(bar_exit)

        orders_after_exit = len(mock_order_execution_manager.orders_placed)

        print("\nAfter processing exit bar:")
        print(f"  - Plan status: {sample_trade_plan.status}")
        print(
            f"  - In active_plans: {sample_trade_plan.plan_id in orchestrator.active_plans}"
        )
        print(
            f"  - In position_plans: {sample_trade_plan.plan_id in orchestrator.position_plans}"
        )
        print(f"  - Orders placed: {orders_after_exit - orders_before_exit}")

        # ================================================================
        # ASSERTIONS: Verify exit happened (WILL FAIL with current code)
        # ================================================================

        # This will FAIL because of Gap #1:
        # process_market_data_event() only checks active_plans, not position_plans
        # So the exit function is never evaluated!

        assert sample_trade_plan.status == TradePlanStatus.COMPLETED, (
            f"❌ GAP #1 DETECTED: Expected COMPLETED, got {sample_trade_plan.status}. "
            f"This means exit function was never evaluated because position_plans "
            f"are not included in process_market_data_event()!"
        )

        assert (
            sample_trade_plan.plan_id not in orchestrator.position_plans
        ), "❌ Plan should be removed from position_plans after exit"

        assert (
            orders_after_exit > orders_before_exit
        ), "❌ Exit order should have been placed"

        print("\n" + "=" * 70)
        print("✅ TEST PASSED: Complete lifecycle works!")
        print("=" * 70)
        print(f"Final status: {sample_trade_plan.status}")
        print(f"Total orders: {len(mock_order_execution_manager.orders_placed)}")

    @pytest.mark.asyncio
    async def test_timeframe_filtering(
        self, orchestrator, sample_trade_plan, mock_order_execution_manager
    ):
        """
        Test that functions are only evaluated on matching timeframes.

        Entry function is 15min, so:
        - 1min bar should NOT trigger evaluation
        - 5min bar should NOT trigger evaluation
        - 15min bar SHOULD trigger evaluation

        This tests Gap #3: Timeframe matching.
        """

        await orchestrator.start()

        print("\n" + "=" * 70)
        print("TEST: Timeframe Filtering")
        print("=" * 70)
        print(f"Entry function timeframe: {sample_trade_plan.entry_function.timeframe}")

        # Test 1min bar (wrong timeframe)
        print("\n--- Testing 1min bar (should be ignored) ---")
        bar_1min = create_bar("AAPL", close_price=181.00, timeframe="1min")
        await orchestrator.process_market_data_event(bar_1min)

        assert sample_trade_plan.status == TradePlanStatus.AWAITING_ENTRY
        assert len(mock_order_execution_manager.orders_placed) == 0
        print("✓ 1min bar ignored (correct)")

        # Test 5min bar (wrong timeframe)
        print("\n--- Testing 5min bar (should be ignored) ---")
        bar_5min = create_bar("AAPL", close_price=181.00, timeframe="5min")
        await orchestrator.process_market_data_event(bar_5min)

        assert sample_trade_plan.status == TradePlanStatus.AWAITING_ENTRY
        assert len(mock_order_execution_manager.orders_placed) == 0
        print("✓ 5min bar ignored (correct)")

        # Test 15min bar (correct timeframe)
        print("\n--- Testing 15min bar (should trigger) ---")
        bar_15min = create_bar("AAPL", close_price=181.00, timeframe="15min")
        await orchestrator.process_market_data_event(bar_15min)

        # This should trigger if timeframe matching works
        if sample_trade_plan.status == TradePlanStatus.POSITION_OPEN:
            print("✓ 15min bar triggered entry (correct)")
        else:
            print(
                f"❌ GAP #3: 15min bar did NOT trigger (status: {sample_trade_plan.status})"
            )
            raise AssertionError(
                f"Timeframe matching may not be working. "
                f"Expected POSITION_OPEN, got {sample_trade_plan.status}"
            )

    @pytest.mark.asyncio
    async def test_multiple_plans_same_symbol(
        self, orchestrator, sample_trade_plan, mock_order_execution_manager
    ):
        """
        Test multiple plans for the same symbol.
        Both should be evaluated on each bar.
        """

        # Create second plan for AAPL with different entry
        plan2 = TradePlan(
            plan_id="AAPL_20250815_002",
            symbol="AAPL",
            entry_level=Decimal("182.00"),
            stop_loss=Decimal("180.00"),
            take_profit=Decimal("185.00"),
            risk_category=RiskCategory.NORMAL,
            entry_function=PlanExecutionFunction(
                function_type="close_above",
                timeframe="15min",
                parameters={"threshold": 182.00},
                last_evaluated=None,
            ),
            stop_loss_function=PlanExecutionFunction(
                function_type="close_below",
                timeframe="15min",
                parameters={"threshold": 180.00},
                last_evaluated=None,
            ),
            take_profit_function=PlanExecutionFunction(
                function_type="close_above",
                timeframe="15min",
                parameters={"threshold": 185.00},
                last_evaluated=None,
            ),
            status=TradePlanStatus.AWAITING_ENTRY,
            calculated_position_size=80,
            dollar_risk=Decimal("200.00"),
        )

        orchestrator.active_plans[plan2.plan_id] = plan2

        await orchestrator.start()

        print("\n" + "=" * 70)
        print("TEST: Multiple Plans Same Symbol")
        print("=" * 70)
        print("Plan 1 entry: 180.50")
        print("Plan 2 entry: 182.00")

        # Send bar at 181.00 - should trigger plan 1 but not plan 2
        bar = create_bar("AAPL", close_price=181.00, timeframe="15min")
        await orchestrator.process_market_data_event(bar)

        print(f"\nPlan 1 status: {sample_trade_plan.status}")
        print(f"Plan 2 status: {plan2.status}")

        # Plan 1 should have triggered
        assert (
            sample_trade_plan.status == TradePlanStatus.POSITION_OPEN
        ), "Plan 1 should have triggered at 181.00"

        # Plan 2 should still be waiting
        assert (
            plan2.status == TradePlanStatus.AWAITING_ENTRY
        ), "Plan 2 should still be waiting (needs 182.00)"

        print("✓ Multiple plans evaluated correctly")


# ============================================================================
# Run Tests
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
