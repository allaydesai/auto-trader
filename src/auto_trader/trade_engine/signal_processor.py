"""Signal processing for trade lifecycle management (compatibility module).

This module provides backward compatibility while delegating to the 
modular signal_processing package structure.
"""

# Import main class for backward compatibility
from .signal_processing.core import SignalProcessor

# Import configuration from signal_validation module
from .signal_validation import SignalProcessorConfig

# Re-export for existing imports
__all__ = ["SignalProcessor", "SignalProcessorConfig"]