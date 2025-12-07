"""Trade lifecycle events and configuration for orchestration."""

from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, UTC

from loguru import logger

from auto_trader.models.trade_plan import TradePlanStatus


class TradeLifecycleEvent:
    """Represents a trade lifecycle transition event."""

    def __init__(
        self,
        event_type: str,
        plan_id: str,
        old_status: Optional[TradePlanStatus],
        new_status: TradePlanStatus,
        context: Optional[Dict[str, Any]] = None,
        timestamp: Optional[datetime] = None,
    ):
        """Initialize lifecycle event.

        Args:
            event_type: Type of event (status_change, entry_signal, exit_signal)
            plan_id: Trade plan ID
            old_status: Previous status
            new_status: New status
            context: Additional context data
            timestamp: Event timestamp
        """
        self.event_type = event_type
        self.plan_id = plan_id
        self.old_status = old_status
        self.new_status = new_status
        self.context = context or {}
        self.timestamp = timestamp or datetime.now(UTC)

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for serialization.

        Returns:
            Event data as dictionary
        """
        return {
            "event_type": self.event_type,
            "plan_id": self.plan_id,
            "old_status": self.old_status.value if self.old_status else None,
            "new_status": self.new_status.value,
            "context": self.context,
            "timestamp": self.timestamp.isoformat(),
        }

    def __str__(self) -> str:
        """String representation of event."""
        return (
            f"TradeLifecycleEvent({self.event_type}: {self.plan_id} "
            f"{self.old_status} -> {self.new_status})"
        )


class TradeOrchestrationConfig:
    """Configuration for trade orchestrator behavior."""

    def __init__(
        self,
        max_concurrent_trades: int = 10,
        signal_timeout_seconds: int = 300,
        state_save_interval_seconds: int = 60,
        enable_position_tracking: bool = True,
        enable_risk_validation: bool = True,
        enable_lifecycle_logging: bool = True,
        event_handler_timeout_seconds: int = 30,
        minimum_confidence_threshold: float = 0.7,
    ):
        """Initialize orchestration config.

        Args:
            max_concurrent_trades: Maximum simultaneous trades
            signal_timeout_seconds: Signal processing timeout
            state_save_interval_seconds: State persistence interval
            enable_position_tracking: Enable position state tracking
            enable_risk_validation: Enable risk management validation
            enable_lifecycle_logging: Enable detailed lifecycle logging
            event_handler_timeout_seconds: Timeout for event handlers
            minimum_confidence_threshold: Minimum signal confidence (0.0-1.0)
        """
        self.max_concurrent_trades = max_concurrent_trades
        self.signal_timeout_seconds = signal_timeout_seconds
        self.state_save_interval_seconds = state_save_interval_seconds
        self.enable_position_tracking = enable_position_tracking
        self.enable_risk_validation = enable_risk_validation
        self.enable_lifecycle_logging = enable_lifecycle_logging
        self.event_handler_timeout_seconds = event_handler_timeout_seconds
        self.minimum_confidence_threshold = minimum_confidence_threshold

        # Validate configuration
        self._validate_config()

    def _validate_config(self) -> None:
        """Validate configuration parameters."""
        if self.max_concurrent_trades <= 0:
            raise ValueError("max_concurrent_trades must be positive")

        if self.signal_timeout_seconds <= 0:
            raise ValueError("signal_timeout_seconds must be positive")

        if self.state_save_interval_seconds <= 0:
            raise ValueError("state_save_interval_seconds must be positive")

        if self.event_handler_timeout_seconds <= 0:
            raise ValueError("event_handler_timeout_seconds must be positive")

    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary.

        Returns:
            Configuration data as dictionary
        """
        return {
            "max_concurrent_trades": self.max_concurrent_trades,
            "signal_timeout_seconds": self.signal_timeout_seconds,
            "state_save_interval_seconds": self.state_save_interval_seconds,
            "enable_position_tracking": self.enable_position_tracking,
            "enable_risk_validation": self.enable_risk_validation,
            "enable_lifecycle_logging": self.enable_lifecycle_logging,
            "event_handler_timeout_seconds": self.event_handler_timeout_seconds,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TradeOrchestrationConfig":
        """Create configuration from dictionary.

        Args:
            data: Configuration data dictionary

        Returns:
            TradeOrchestrationConfig instance
        """
        return cls(
            max_concurrent_trades=data.get("max_concurrent_trades", 10),
            signal_timeout_seconds=data.get("signal_timeout_seconds", 300),
            state_save_interval_seconds=data.get("state_save_interval_seconds", 60),
            enable_position_tracking=data.get("enable_position_tracking", True),
            enable_risk_validation=data.get("enable_risk_validation", True),
            enable_lifecycle_logging=data.get("enable_lifecycle_logging", True),
            event_handler_timeout_seconds=data.get("event_handler_timeout_seconds", 30),
        )


class LifecycleEventManager:
    """Manages lifecycle event handlers and notifications."""

    def __init__(self, config: TradeOrchestrationConfig):
        """Initialize event manager.

        Args:
            config: Orchestration configuration
        """
        self.config = config
        self.event_handlers: List[Callable[[TradeLifecycleEvent], None]] = []
        self.event_history: List[TradeLifecycleEvent] = []
        self.max_history_size = 1000  # Keep last 1000 events

    def add_event_handler(self, handler: Callable[[TradeLifecycleEvent], None]) -> None:
        """Add a lifecycle event handler.

        Args:
            handler: Function to call when events occur
        """
        if handler not in self.event_handlers:
            self.event_handlers.append(handler)
            logger.debug(f"Added lifecycle event handler: {handler.__name__}")

    def remove_event_handler(
        self, handler: Callable[[TradeLifecycleEvent], None]
    ) -> None:
        """Remove a lifecycle event handler.

        Args:
            handler: Handler to remove
        """
        if handler in self.event_handlers:
            self.event_handlers.remove(handler)
            logger.debug(f"Removed lifecycle event handler: {handler.__name__}")

    def emit_event(self, event: TradeLifecycleEvent) -> None:
        """Emit a lifecycle event to all handlers.

        Args:
            event: Event to emit
        """
        # Add to history
        self.event_history.append(event)

        # Trim history if needed
        if len(self.event_history) > self.max_history_size:
            self.event_history = self.event_history[-self.max_history_size :]

        # Log the event if enabled
        if self.config.enable_lifecycle_logging:
            logger.info(f"Lifecycle event: {event}")

        # Notify handlers
        for handler in self.event_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.error(
                    f"Error in lifecycle event handler {handler.__name__}: {e}"
                )

    def get_recent_events(self, count: int = 100) -> List[TradeLifecycleEvent]:
        """Get recent lifecycle events.

        Args:
            count: Number of recent events to return

        Returns:
            List of recent events
        """
        return self.event_history[-count:]

    def get_events_for_plan(self, plan_id: str) -> List[TradeLifecycleEvent]:
        """Get all events for a specific plan.

        Args:
            plan_id: Trade plan ID

        Returns:
            List of events for the plan
        """
        return [event for event in self.event_history if event.plan_id == plan_id]

    def clear_history(self) -> None:
        """Clear event history."""
        self.event_history.clear()
        logger.debug("Cleared lifecycle event history")
