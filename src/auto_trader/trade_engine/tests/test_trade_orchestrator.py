"""Minimal tests for TradeOrchestrator to verify imports work."""

from auto_trader.trade_engine.trade_orchestrator import (
    TradeOrchestrator,
    TradeOrchestrationConfig,
    TradeLifecycleEvent,
)
from auto_trader.models.trade_plan import TradePlanStatus


def test_orchestration_config_creation():
    """Test that TradeOrchestrationConfig can be created."""
    config = TradeOrchestrationConfig()
    assert config.max_concurrent_trades == 10
    assert config.signal_timeout_seconds == 300


def test_lifecycle_event_creation():
    """Test that TradeLifecycleEvent can be created."""
    event = TradeLifecycleEvent(
        event_type="test_event",
        plan_id="TEST_001",
        old_status=TradePlanStatus.AWAITING_ENTRY,
        new_status=TradePlanStatus.POSITION_OPEN,
    )

    assert event.event_type == "test_event"
    assert event.plan_id == "TEST_001"
    assert event.old_status == TradePlanStatus.AWAITING_ENTRY
    assert event.new_status == TradePlanStatus.POSITION_OPEN


def test_orchestrator_import():
    """Test that TradeOrchestrator can be imported and instantiated."""
    # This test just verifies that the import works
    # We'll skip actual instantiation since it requires many dependencies
    assert TradeOrchestrator is not None
