"""Trade lifecycle management (compatibility module).

This module provides backward compatibility while delegating to the 
modular lifecycle package structure.
"""

# Import main classes for backward compatibility
from .lifecycle.core import TradeLifecycleManager
from .lifecycle.state import TradeLifecycleState, StateTransitionError

# Re-export for existing imports
__all__ = ["TradeLifecycleManager", "TradeLifecycleState", "StateTransitionError"]