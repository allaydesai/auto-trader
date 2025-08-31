"""Trade lifecycle orchestration and management (compatibility module).

This module provides backward compatibility while delegating to the 
modular orchestration package structure.
"""

# Import main class for backward compatibility
from .orchestration.core import TradeOrchestrator

# Import configuration and events from lifecycle_events module
from .lifecycle_events import TradeOrchestrationConfig, TradeLifecycleEvent

# Re-export for existing imports
__all__ = ["TradeOrchestrator", "TradeOrchestrationConfig", "TradeLifecycleEvent"]