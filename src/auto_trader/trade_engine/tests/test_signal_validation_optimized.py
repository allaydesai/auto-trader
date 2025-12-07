"""Tests for optimized signal validation performance."""

import pytest
from datetime import datetime, UTC, timedelta
from collections import OrderedDict

from auto_trader.trade_engine.signal_validation import (
    SignalValidator,
    SignalProcessorConfig,
)
from auto_trader.models.execution import ExecutionSignal, ExecutionAction
from auto_trader.models.trade_plan import (
    TradePlan,
    TradePlanStatus,
    RiskCategory,
    ExecutionFunction,
)
from decimal import Decimal


def create_test_signal(
    action: ExecutionAction = ExecutionAction.ENTER_LONG, confidence: float = 0.8
) -> ExecutionSignal:
    """Create a test execution signal."""
    return ExecutionSignal(
        action=action,
        confidence=confidence,
        reasoning="Test signal for optimization testing",
    )


def create_test_trade_plan(plan_id: str = "TEST_001") -> TradePlan:
    """Create a test trade plan."""
    entry_function = ExecutionFunction(
        function_type="close_above", timeframe="15min", parameters={"threshold": 150.0}
    )

    stop_loss_function = ExecutionFunction(
        function_type="close_below", timeframe="15min", parameters={"threshold": 145.0}
    )

    take_profit_function = ExecutionFunction(
        function_type="close_above", timeframe="15min", parameters={"threshold": 155.0}
    )

    return TradePlan(
        plan_id=plan_id,
        symbol="AAPL",
        entry_level=Decimal("150.00"),
        stop_loss=Decimal("145.00"),
        take_profit=Decimal("155.00"),
        position_size=100,
        risk_category=RiskCategory.NORMAL,
        status=TradePlanStatus.AWAITING_ENTRY,
        entry_function=entry_function,
        stop_loss_function=stop_loss_function,
        take_profit_function=take_profit_function,
    )


class TestSignalValidatorOptimized:
    """Test optimized signal validation with OrderedDict cleanup."""

    @pytest.fixture
    def config(self):
        """Create signal processor config."""
        return SignalProcessorConfig()

    @pytest.fixture
    def validator(self, config):
        """Create signal validator."""
        return SignalValidator(config)

    def test_uses_ordered_dict(self, validator):
        """Test that validator uses OrderedDict for efficient cleanup."""
        assert isinstance(validator.recent_signals, OrderedDict)

    def test_efficient_signal_cleanup(self, validator):
        """Test that old signals are cleaned up efficiently using OrderedDict."""
        plan = create_test_trade_plan()
        signal = create_test_signal()

        # Add old signals that should be cleaned up
        old_time = datetime.now(UTC) - timedelta(seconds=300)  # 5 minutes ago
        for i in range(10):
            key = f"old_signal_{i}"
            validator.recent_signals[key] = old_time

        # Add a recent signal that should remain
        recent_time = datetime.now(UTC) - timedelta(seconds=30)  # 30 seconds ago
        validator.recent_signals["recent_signal"] = recent_time

        assert len(validator.recent_signals) == 11

        # Check for duplicate (this triggers cleanup)
        validator.check_duplicate_signal(signal, plan)

        # Old signals should be cleaned up, recent signal should remain
        # Plus the new signal we just processed
        remaining_keys = list(validator.recent_signals.keys())
        assert "recent_signal" in remaining_keys
        assert len([k for k in remaining_keys if k.startswith("old_signal")]) == 0

    def test_signal_cleanup_preserves_order(self, validator):
        """Test that OrderedDict preserves insertion order for cleanup."""
        plan = create_test_trade_plan()
        signal = create_test_signal()

        # Add signals in specific order
        times = []
        for i in range(5):
            key = f"signal_{i}"
            time_offset = datetime.now(UTC) - timedelta(
                seconds=400 - i * 50
            )  # Oldest to newest
            validator.recent_signals[key] = time_offset
            times.append(time_offset)

        # Trigger cleanup
        validator.check_duplicate_signal(signal, plan)

        # Check that cleanup happened from oldest first (FIFO)
        remaining_times = list(validator.recent_signals.values())
        # The newest signals should remain (those within the 300 second window)
        assert all(
            time >= datetime.now(UTC) - timedelta(seconds=300)
            for time in remaining_times[:-1]
        )  # Exclude the just-added signal

    def test_duplicate_detection_after_cleanup(self, validator):
        """Test duplicate detection works correctly after cleanup."""
        plan = create_test_trade_plan()
        signal = create_test_signal()

        # Add old duplicate signal
        old_time = datetime.now(UTC) - timedelta(seconds=300)
        signal_key = f"{plan.plan_id}_{signal.action.value}_{signal.confidence:.2f}"
        validator.recent_signals[signal_key] = old_time

        # Should not be duplicate after cleanup
        is_duplicate_1 = validator.check_duplicate_signal(signal, plan)
        assert not is_duplicate_1

        # Immediate retry should be duplicate
        is_duplicate_2 = validator.check_duplicate_signal(signal, plan)
        assert is_duplicate_2
