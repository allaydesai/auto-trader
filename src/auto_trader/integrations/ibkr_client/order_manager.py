"""
Order execution manager for IBKR integration using ib-async.

This module provides the main OrderExecutionManager class which coordinates
order placement, modification, cancellation, and status tracking with 
risk management integration and comprehensive error handling.

The implementation uses a modular architecture with separate engines for
simulation and live execution, centralized event management, and persistent
state tracking.
"""

# Re-export the main OrderExecutionManager and related classes
from .order_execution_manager import (
    OrderExecutionManager,
    OrderExecutionError,
    OrderNotFoundError,
    OrderAlreadyExistsError,
)

__all__ = [
    "OrderExecutionManager",
    "OrderExecutionError", 
    "OrderNotFoundError",
    "OrderAlreadyExistsError",
]