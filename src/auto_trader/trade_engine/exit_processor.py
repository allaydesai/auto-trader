"""Exit signal processing for open positions (compatibility module).

This module provides backward compatibility while delegating to the
modular exit_processor package structure.
"""

# Import main class for backward compatibility
from .exit_processor.core import ExitProcessor

# Re-export for existing imports
__all__ = ["ExitProcessor"]
