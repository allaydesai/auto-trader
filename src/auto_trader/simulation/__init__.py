"""Simulation mode support for auto-trader.

This module provides factory functions to create appropriate providers
based on simulation mode configuration.
"""

from .provider_factory import (
    create_data_feed_provider,
    create_order_execution_provider,
    SimulationContext,
)

__all__ = [
    "create_data_feed_provider",
    "create_order_execution_provider",
    "SimulationContext",
]
