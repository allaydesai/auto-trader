"""Tests for TradeLifecycleManager."""

import pytest
from decimal import Decimal
from datetime import datetime, UTC
from unittest.mock import Mock

from auto_trader.models.trade_plan import TradePlan, TradePlanStatus, RiskCategory, ExecutionFunction
from auto_trader.models.order import OrderResult, OrderStatus
from auto_trader.models.enums import OrderSide
from auto_trader.trade_engine.lifecycle_manager import (
    TradeLifecycleManager,
    TradeLifecycleState,
    StateTransitionError,
)


@pytest.fixture
def lifecycle_manager():
    """Create a fresh lifecycle manager."""
    return TradeLifecycleManager()


@pytest.fixture
def sample_trade_plan():
    """Create a sample trade plan for testing."""
    return TradePlan(
        plan_id="TEST_001",
        symbol="AAPL",
        entry_level=Decimal("180.50"),
        stop_loss=Decimal("178.00"),
        take_profit=Decimal("185.00"),
        risk_category=RiskCategory.NORMAL,
        entry_function=ExecutionFunction(
            function_type="close_above",
            timeframe="15min",
            parameters={"threshold": "180.50"},
        ),
        stop_loss_function=ExecutionFunction(
            function_type="close_below",
            timeframe="15min",
            parameters={"threshold": "178.00"},
        ),
        take_profit_function=ExecutionFunction(
            function_type="close_above",
            timeframe="15min",
            parameters={"threshold": "185.00"},
        ),
        status=TradePlanStatus.AWAITING_ENTRY,
    )


@pytest.fixture
def successful_order_result():
    """Create a successful order result."""
    return OrderResult(
        success=True,
        order_id="ORDER_001",
        trade_plan_id="TEST_001",
        order_status=OrderStatus.FILLED,
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=100,
        filled_quantity=100,
        average_fill_price=Decimal("180.75"),
        order_type="MKT",
    )


def create_test_trade_plan(plan_id: str, symbol: str = "AAPL", status: TradePlanStatus = TradePlanStatus.AWAITING_ENTRY):
    """Helper function to create test trade plans with all required fields."""
    return TradePlan(
        plan_id=plan_id,
        symbol=symbol,
        entry_level=Decimal("180.00"),
        stop_loss=Decimal("178.00"),
        take_profit=Decimal("185.00"),
        risk_category=RiskCategory.NORMAL,
        entry_function=ExecutionFunction(
            function_type="close_above",
            timeframe="15min",
            parameters={"threshold": "180.00"},
        ),
        stop_loss_function=ExecutionFunction(
            function_type="close_below",
            timeframe="15min",
            parameters={"threshold": "178.00"},
        ),
        take_profit_function=ExecutionFunction(
            function_type="close_above",
            timeframe="15min",
            parameters={"threshold": "185.00"},
        ),
        status=status,
    )


class TestTradeLifecycleState:
    """Test TradeLifecycleState class."""
    
    def test_create_lifecycle_state(self, sample_trade_plan):
        """Test creating a new lifecycle state."""
        state = TradeLifecycleState(sample_trade_plan)
        
        assert state.plan == sample_trade_plan
        assert state.entry_order_id is None
        assert state.exit_order_id is None
        assert state.position_quantity == 0
        assert state.entry_price is None
        assert not state.has_position
        assert not state.is_long
        assert not state.is_short
        assert state.created_at is not None
        assert state.updated_at is not None
    
    def test_update_state_with_long_position(self, sample_trade_plan):
        """Test updating state with long position."""
        state = TradeLifecycleState(sample_trade_plan)
        
        state.update(
            entry_order_id="ORDER_001",
            position_quantity=100,
            entry_price=Decimal("180.75"),
        )
        
        assert state.entry_order_id == "ORDER_001"
        assert state.position_quantity == 100
        assert state.entry_price == Decimal("180.75")
        assert state.has_position
        assert state.is_long
        assert not state.is_short
    
    def test_update_state_with_short_position(self, sample_trade_plan):
        """Test updating state with short position."""
        state = TradeLifecycleState(sample_trade_plan)
        
        state.update(
            entry_order_id="ORDER_002",
            position_quantity=-50,
            entry_price=Decimal("179.25"),
        )
        
        assert state.entry_order_id == "ORDER_002"
        assert state.position_quantity == -50
        assert state.entry_price == Decimal("179.25")
        assert state.has_position
        assert not state.is_long
        assert state.is_short
    
    def test_close_position(self, sample_trade_plan):
        """Test closing a position."""
        state = TradeLifecycleState(sample_trade_plan)
        
        # Open position
        state.update(position_quantity=100)
        assert state.has_position
        
        # Close position
        state.update(
            exit_order_id="ORDER_EXIT",
            position_quantity=0,
        )
        
        assert state.exit_order_id == "ORDER_EXIT"
        assert state.position_quantity == 0
        assert not state.has_position
        assert not state.is_long
        assert not state.is_short


class TestTradeLifecycleManager:
    """Test TradeLifecycleManager class."""
    
    def test_create_lifecycle_state(self, lifecycle_manager, sample_trade_plan):
        """Test creating a new lifecycle state."""
        state = lifecycle_manager.create_lifecycle_state(sample_trade_plan)
        
        assert isinstance(state, TradeLifecycleState)
        assert state.plan == sample_trade_plan
        assert sample_trade_plan.plan_id in lifecycle_manager.states
        
    def test_create_duplicate_state_raises_error(self, lifecycle_manager, sample_trade_plan):
        """Test that creating duplicate state raises error."""
        lifecycle_manager.create_lifecycle_state(sample_trade_plan)
        
        with pytest.raises(ValueError, match="already exists"):
            lifecycle_manager.create_lifecycle_state(sample_trade_plan)
    
    def test_get_lifecycle_state(self, lifecycle_manager, sample_trade_plan):
        """Test getting lifecycle state."""
        created_state = lifecycle_manager.create_lifecycle_state(sample_trade_plan)
        retrieved_state = lifecycle_manager.get_lifecycle_state(sample_trade_plan.plan_id)
        
        assert retrieved_state == created_state
        
    def test_get_nonexistent_state(self, lifecycle_manager):
        """Test getting nonexistent state returns None."""
        state = lifecycle_manager.get_lifecycle_state("NONEXISTENT")
        assert state is None
    
    def test_remove_lifecycle_state(self, lifecycle_manager, sample_trade_plan):
        """Test removing lifecycle state."""
        lifecycle_manager.create_lifecycle_state(sample_trade_plan)
        
        result = lifecycle_manager.remove_lifecycle_state(sample_trade_plan.plan_id)
        assert result is True
        assert sample_trade_plan.plan_id not in lifecycle_manager.states
        
    def test_remove_nonexistent_state(self, lifecycle_manager):
        """Test removing nonexistent state returns False."""
        result = lifecycle_manager.remove_lifecycle_state("NONEXISTENT")
        assert result is False
    
    def test_valid_transitions(self, lifecycle_manager):
        """Test valid state transitions."""
        # Test all valid transitions
        valid_cases = [
            (TradePlanStatus.AWAITING_ENTRY, TradePlanStatus.POSITION_OPEN),
            (TradePlanStatus.AWAITING_ENTRY, TradePlanStatus.CANCELLED),
            (TradePlanStatus.AWAITING_ENTRY, TradePlanStatus.ERROR),
            (TradePlanStatus.POSITION_OPEN, TradePlanStatus.COMPLETED),
            (TradePlanStatus.POSITION_OPEN, TradePlanStatus.CANCELLED),
            (TradePlanStatus.POSITION_OPEN, TradePlanStatus.ERROR),
            (TradePlanStatus.ERROR, TradePlanStatus.AWAITING_ENTRY),
            (TradePlanStatus.ERROR, TradePlanStatus.CANCELLED),
        ]
        
        for current, new in valid_cases:
            assert lifecycle_manager.validate_transition(current, new) is True
    
    def test_invalid_transitions(self, lifecycle_manager):
        """Test invalid state transitions."""
        invalid_cases = [
            (TradePlanStatus.COMPLETED, TradePlanStatus.AWAITING_ENTRY),
            (TradePlanStatus.COMPLETED, TradePlanStatus.POSITION_OPEN),
            (TradePlanStatus.CANCELLED, TradePlanStatus.AWAITING_ENTRY),
            (TradePlanStatus.CANCELLED, TradePlanStatus.POSITION_OPEN),
            (TradePlanStatus.AWAITING_ENTRY, TradePlanStatus.COMPLETED),
        ]
        
        for current, new in invalid_cases:
            assert lifecycle_manager.validate_transition(current, new) is False


class TestStateTransitions:
    """Test state transition methods."""
    
    @pytest.mark.asyncio
    async def test_transition_to_position_open(
        self, lifecycle_manager, sample_trade_plan, successful_order_result
    ):
        """Test transitioning to position_open status."""
        # Create initial state
        lifecycle_manager.create_lifecycle_state(sample_trade_plan)
        
        # Transition to position open
        successful_order_result.filled_quantity = 100
        successful_order_result.average_fill_price = Decimal("180.75")
        await lifecycle_manager.transition_to_position_open(
            sample_trade_plan.plan_id,
            successful_order_result,
        )
        state = lifecycle_manager.get_lifecycle_state(sample_trade_plan.plan_id)
        
        assert sample_trade_plan.status == TradePlanStatus.POSITION_OPEN
        assert state.entry_order_id == "ORDER_001"
        assert state.position_quantity == 100
        assert state.entry_price == Decimal("180.75")
        assert state.has_position
        assert state.is_long
    
    @pytest.mark.asyncio
    async def test_transition_to_position_open_invalid(
        self, lifecycle_manager, successful_order_result
    ):
        """Test invalid transition to position_open."""
        # Create plan already in position_open state
        plan = create_test_trade_plan("TEST_002", status=TradePlanStatus.POSITION_OPEN)
        
        lifecycle_manager.create_lifecycle_state(plan)
        
        with pytest.raises(StateTransitionError):
            await lifecycle_manager.transition_to_position_open(
                plan.plan_id, successful_order_result
            )
    
    @pytest.mark.asyncio
    async def test_transition_to_completed(
        self, lifecycle_manager, sample_trade_plan, successful_order_result
    ):
        """Test transitioning to completed status."""
        # Set up plan in position_open state
        sample_trade_plan.status = TradePlanStatus.POSITION_OPEN
        state = lifecycle_manager.create_lifecycle_state(sample_trade_plan)
        state.update(
            entry_order_id="ORDER_001",
            position_quantity=100,
            entry_price=Decimal("180.75"),
        )
        
        # Create exit order result
        exit_result = OrderResult(
            success=True,
            order_id="ORDER_EXIT",
            trade_plan_id="TEST_001",
            order_status=OrderStatus.FILLED,
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=100,
            filled_quantity=100,
            average_fill_price=Decimal("185.25"),
            order_type="MKT",
        )
        
        # Transition to completed
        await lifecycle_manager.transition_to_completed(
            sample_trade_plan.plan_id, exit_result, Decimal("185.25")
        )
        final_state = lifecycle_manager.get_lifecycle_state(sample_trade_plan.plan_id)
        
        assert sample_trade_plan.status == TradePlanStatus.COMPLETED
        assert final_state.exit_order_id == "ORDER_EXIT"
        assert final_state.position_quantity == 0
        assert not final_state.has_position
    
    @pytest.mark.asyncio
    async def test_transition_to_completed_invalid(self, lifecycle_manager, sample_trade_plan):
        """Test invalid transition to completed."""
        # Plan still in awaiting_entry state
        exit_result = Mock()
        
        lifecycle_manager.create_lifecycle_state(sample_trade_plan)
        
        with pytest.raises(StateTransitionError):
            await lifecycle_manager.transition_to_completed(
                sample_trade_plan.plan_id, exit_result, Decimal("185.00")
            )
    
    @pytest.mark.asyncio
    async def test_transition_to_completed_no_state(self, lifecycle_manager):
        """Test transition to completed with no existing state."""
        plan = create_test_trade_plan("TEST_NO_STATE", status=TradePlanStatus.POSITION_OPEN)
        exit_result = Mock()
        
        with pytest.raises(ValueError, match="No lifecycle state found"):
            await lifecycle_manager.transition_to_completed(
                plan.plan_id, exit_result, Decimal("185.00")
            )
    
    @pytest.mark.asyncio
    async def test_transition_to_error(self, lifecycle_manager, sample_trade_plan):
        """Test transitioning to error status."""
        lifecycle_manager.create_lifecycle_state(sample_trade_plan)
        
        await lifecycle_manager.transition_to_error(
            sample_trade_plan.plan_id, "Test error"
        )
        state = lifecycle_manager.get_lifecycle_state(sample_trade_plan.plan_id)
        
        assert sample_trade_plan.status == TradePlanStatus.ERROR
        assert state.plan.status == TradePlanStatus.ERROR
    
    @pytest.mark.asyncio
    async def test_transition_to_cancelled(self, lifecycle_manager, sample_trade_plan):
        """Test transitioning to cancelled status."""
        lifecycle_manager.create_lifecycle_state(sample_trade_plan)
        
        await lifecycle_manager.transition_to_cancelled(
            sample_trade_plan.plan_id, "User requested"
        )
        state = lifecycle_manager.get_lifecycle_state(sample_trade_plan.plan_id)
        
        assert sample_trade_plan.status == TradePlanStatus.CANCELLED
        assert state.plan.status == TradePlanStatus.CANCELLED
    
    @pytest.mark.asyncio
    async def test_transition_to_cancelled_invalid(self, lifecycle_manager):
        """Test invalid transition to cancelled."""
        # Create completed plan
        plan = create_test_trade_plan("TEST_COMPLETED", status=TradePlanStatus.COMPLETED)
        
        lifecycle_manager.create_lifecycle_state(plan)
        
        with pytest.raises(StateTransitionError):
            await lifecycle_manager.transition_to_cancelled(plan.plan_id, "Invalid")


class TestQueryMethods:
    """Test query and summary methods."""
    
    def test_get_plans_by_status(self, lifecycle_manager):
        """Test getting plans by status."""
        # Create plans with different statuses
        plan1 = create_test_trade_plan("PLAN_1", "AAPL", TradePlanStatus.AWAITING_ENTRY)
        plan2 = create_test_trade_plan("PLAN_2", "MSFT", TradePlanStatus.POSITION_OPEN) 
        plan3 = create_test_trade_plan("PLAN_3", "GOOGL", TradePlanStatus.AWAITING_ENTRY)
        
        lifecycle_manager.create_lifecycle_state(plan1)
        lifecycle_manager.create_lifecycle_state(plan2)
        lifecycle_manager.create_lifecycle_state(plan3)
        
        awaiting_plans = lifecycle_manager.get_plans_by_status(TradePlanStatus.AWAITING_ENTRY)
        position_plans = lifecycle_manager.get_plans_by_status(TradePlanStatus.POSITION_OPEN)
        completed_plans = lifecycle_manager.get_plans_by_status(TradePlanStatus.COMPLETED)
        
        assert len(awaiting_plans) == 2
        assert len(position_plans) == 1
        assert len(completed_plans) == 0
        
        assert plan1 in awaiting_plans
        assert plan3 in awaiting_plans
        assert plan2 in position_plans
    
    def test_get_open_positions(self, lifecycle_manager):
        """Test getting open positions."""
        # Create plans with and without positions
        plan1 = create_test_trade_plan("PLAN_1", "AAPL", TradePlanStatus.AWAITING_ENTRY)
        plan2 = create_test_trade_plan("PLAN_2", "MSFT", TradePlanStatus.POSITION_OPEN)
        
        state1 = lifecycle_manager.create_lifecycle_state(plan1)
        state2 = lifecycle_manager.create_lifecycle_state(plan2)
        
        # Add position to state2
        state2.update(position_quantity=50)
        
        open_positions = lifecycle_manager.get_open_positions()
        
        assert len(open_positions) == 1
        assert open_positions[0] == state2
    
    def test_get_position_summary(self, lifecycle_manager):
        """Test getting position summary."""
        # Create multiple positions
        plan1 = create_test_trade_plan("PLAN_1", "AAPL", TradePlanStatus.POSITION_OPEN)
        plan2 = create_test_trade_plan("PLAN_2", "AAPL", TradePlanStatus.POSITION_OPEN)
        plan3 = create_test_trade_plan("PLAN_3", "MSFT", TradePlanStatus.POSITION_OPEN)
        
        state1 = lifecycle_manager.create_lifecycle_state(plan1)
        state2 = lifecycle_manager.create_lifecycle_state(plan2)
        state3 = lifecycle_manager.create_lifecycle_state(plan3)
        
        # Set positions (long and short)
        state1.update(position_quantity=100)   # AAPL +100
        state2.update(position_quantity=-50)   # AAPL -50
        state3.update(position_quantity=75)    # MSFT +75
        
        summary = lifecycle_manager.get_position_summary()
        
        assert summary["AAPL"] == 50  # 100 + (-50)
        assert summary["MSFT"] == 75
        
    def test_get_lifecycle_statistics(self, lifecycle_manager):
        """Test getting lifecycle statistics."""
        # Create plans with various statuses
        statuses = [
            TradePlanStatus.AWAITING_ENTRY,
            TradePlanStatus.AWAITING_ENTRY,
            TradePlanStatus.POSITION_OPEN,
            TradePlanStatus.COMPLETED,
            TradePlanStatus.ERROR,
        ]
        
        for i, status in enumerate(statuses):
            plan = create_test_trade_plan(f"PLAN_{i}", status=status)
            state = lifecycle_manager.create_lifecycle_state(plan)
            
            # Add position to position_open plan
            if status == TradePlanStatus.POSITION_OPEN:
                state.update(position_quantity=100)
        
        stats = lifecycle_manager.get_lifecycle_statistics()
        
        assert stats["total_states"] == 5
        assert stats["awaiting_entry"] == 2
        assert stats["position_open"] == 1
        assert stats["completed"] == 1
        assert stats["error"] == 1
        assert stats["open_positions"] == 1


class TestStateValidation:
    """Test state validation and consistency checks."""
    
    def test_validate_state_consistency_valid(self, lifecycle_manager):
        """Test validation of consistent states."""
        # Create valid awaiting_entry plan
        plan1 = create_test_trade_plan("PLAN_1", "AAPL", TradePlanStatus.AWAITING_ENTRY)
        
        # Create valid position_open plan
        plan2 = create_test_trade_plan("PLAN_2", "MSFT", TradePlanStatus.POSITION_OPEN)
        
        state1 = lifecycle_manager.create_lifecycle_state(plan1)
        state2 = lifecycle_manager.create_lifecycle_state(plan2)
        
        # Set valid state for position_open plan
        state2.update(
            entry_order_id="ORDER_001",
            position_quantity=50,
            entry_price=Decimal("100.00"),
        )
        
        errors = lifecycle_manager.validate_state_consistency()
        assert len(errors) == 0
    
    def test_validate_state_consistency_invalid(self, lifecycle_manager):
        """Test validation of inconsistent states."""
        # Create inconsistent awaiting_entry plan (has position)
        plan1 = create_test_trade_plan("PLAN_1", "AAPL", TradePlanStatus.AWAITING_ENTRY)
        
        # Create inconsistent position_open plan (no position)
        plan2 = create_test_trade_plan("PLAN_2", "MSFT", TradePlanStatus.POSITION_OPEN)
        
        state1 = lifecycle_manager.create_lifecycle_state(plan1)
        state2 = lifecycle_manager.create_lifecycle_state(plan2)
        
        # Create inconsistencies
        state1.update(position_quantity=100)  # Awaiting entry but has position
        # state2 has no position but is position_open
        
        errors = lifecycle_manager.validate_state_consistency()
        
        assert len(errors) >= 2
        assert any("AWAITING_ENTRY but has position" in error for error in errors)
        assert any("POSITION_OPEN but has no position quantity" in error for error in errors)
    
    def test_cleanup_terminal_states(self, lifecycle_manager):
        """Test cleaning up terminal states."""
        # Create plans in various states
        states_to_create = [
            TradePlanStatus.AWAITING_ENTRY,
            TradePlanStatus.POSITION_OPEN,
            TradePlanStatus.COMPLETED,
            TradePlanStatus.CANCELLED,
            TradePlanStatus.ERROR,
        ]
        
        for i, status in enumerate(states_to_create):
            plan = create_test_trade_plan(f"PLAN_{i}", status=status)
            lifecycle_manager.create_lifecycle_state(plan)
        
        assert len(lifecycle_manager.states) == 5
        
        # Cleanup terminal states
        removed_count = lifecycle_manager.cleanup_terminal_states()
        
        assert removed_count == 2  # COMPLETED and CANCELLED
        assert len(lifecycle_manager.states) == 3
        
        # Verify remaining states
        remaining_statuses = {
            state.plan.status for state in lifecycle_manager.states.values()
        }
        expected_remaining = {
            TradePlanStatus.AWAITING_ENTRY,
            TradePlanStatus.POSITION_OPEN,
            TradePlanStatus.ERROR,
        }
        assert remaining_statuses == expected_remaining
    
    def test_validation_caching(self, lifecycle_manager):
        """Test that transition validation results are cached for performance."""
        # Cache should be empty initially
        assert len(lifecycle_manager.validator._validation_cache) == 0
        
        # First transition validation should populate cache
        is_valid1 = lifecycle_manager.validate_transition(
            TradePlanStatus.AWAITING_ENTRY, TradePlanStatus.POSITION_OPEN
        )
        assert is_valid1 is True
        
        # Cache should now have entries
        cache_size_after_first = len(lifecycle_manager.validator._validation_cache)
        assert cache_size_after_first > 0
        
        # Second validation should return same result from cache
        is_valid2 = lifecycle_manager.validate_transition(
            TradePlanStatus.AWAITING_ENTRY, TradePlanStatus.POSITION_OPEN
        )
        assert is_valid2 == is_valid1
        
        # Cache should have same number of entries (hit from cache)
        cache_size_after_second = len(lifecycle_manager.validator._validation_cache)
        assert cache_size_after_second == cache_size_after_first
        
        # Test different transition to add more cache entries
        is_valid3 = lifecycle_manager.validate_transition(
            TradePlanStatus.POSITION_OPEN, TradePlanStatus.COMPLETED
        )
        assert is_valid3 is True
        assert len(lifecycle_manager.validator._validation_cache) > cache_size_after_first
        
        # Invalidating cache should clear it
        lifecycle_manager.validator.invalidate_cache()
        assert len(lifecycle_manager.validator._validation_cache) == 0