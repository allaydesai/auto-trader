"""Factory functions for creating data feed and order execution providers."""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from loguru import logger

from auto_trader.data_feed import (
    DataFeedProvider,
    FileDataFeed,
    IBKRDataFeed,
    PlaybackMode,
)
from auto_trader.logging_config import set_simulation_mode
from auto_trader.order_execution import (
    OrderExecutionProvider,
    SimulatedOrderExecution,
)


@dataclass
class SimulationContext:
    """Context for simulation mode configuration.

    Attributes:
        enabled: Whether simulation mode is enabled.
        data_file: Path to simulation data file (CSV/YAML/JSON).
        playback_mode: Playback mode for file data (instant, sequential, real_time).
        speed_multiplier: Speed multiplier for playback.
    """

    enabled: bool = True
    data_file: Optional[str] = None
    playback_mode: str = "instant"
    speed_multiplier: float = 1.0

    def get_playback_mode(self) -> PlaybackMode:
        """Convert string playback mode to PlaybackMode enum."""
        mode_map = {
            "instant": PlaybackMode.INSTANT,
            "sequential": PlaybackMode.SEQUENTIAL,
            "real_time": PlaybackMode.REAL_TIME,
        }
        if self.playback_mode not in mode_map:
            logger.warning(
                f"Unknown playback mode '{self.playback_mode}', defaulting to 'instant'. "
                f"Valid modes: {list(mode_map.keys())}"
            )
            return PlaybackMode.INSTANT
        return mode_map[self.playback_mode]


def create_data_feed_provider(
    simulation_context: SimulationContext,
    ib_client: Optional[object] = None,
) -> DataFeedProvider:
    """Create appropriate data feed provider based on simulation context.

    Args:
        simulation_context: Simulation configuration context.
        ib_client: IB client instance for live mode.

    Returns:
        DataFeedProvider implementation (FileDataFeed or IBKRDataFeed).

    Raises:
        ValueError: If simulation mode is enabled but no data file is specified,
                   or if live mode is requested but no ib_client provided.
    """
    # Set simulation mode for logging indicators
    set_simulation_mode(simulation_context.enabled)

    if simulation_context.enabled:
        if not simulation_context.data_file:
            raise ValueError(
                "Simulation mode requires a data file. "
                "Set simulation.data_file in config."
            )

        file_path = Path(simulation_context.data_file)
        if not file_path.exists():
            raise ValueError(f"Simulation data file not found: {file_path}")

        return FileDataFeed(
            file_path=str(file_path),
            playback_mode=simulation_context.get_playback_mode(),
            speed_multiplier=simulation_context.speed_multiplier,
        )
    else:
        if ib_client is None:
            raise ValueError(
                "Live mode requires an IB client instance. "
                "Provide ib_client parameter."
            )

        return IBKRDataFeed(ib_client=ib_client)


def create_order_execution_provider(
    simulation_context: SimulationContext,
) -> OrderExecutionProvider:
    """Create appropriate order execution provider based on simulation context.

    Args:
        simulation_context: Simulation configuration context.

    Returns:
        OrderExecutionProvider implementation (SimulatedOrderExecution for simulation,
        or the caller should use existing OrderExecutionManager for live mode).

    Note:
        For live mode, this returns SimulatedOrderExecution as a placeholder.
        The actual live execution should use the existing OrderExecutionManager
        which handles both modes internally. This factory is primarily for
        the simulation path.
    """
    if simulation_context.enabled:
        return SimulatedOrderExecution()
    else:
        # For live mode, return SimulatedOrderExecution as a fallback
        # The actual live execution is handled by OrderExecutionManager
        # which has its own simulation_mode flag
        return SimulatedOrderExecution()
