"""Comprehensive tests for provider_factory module.

Tests SimulationContext dataclass and factory functions for creating
data feed and order execution providers in simulation and live modes.
"""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from auto_trader.data_feed import FileDataFeed, IBKRDataFeed, PlaybackMode
from auto_trader.order_execution import SimulatedOrderExecution
from auto_trader.simulation.provider_factory import (
    SimulationContext,
    create_data_feed_provider,
    create_order_execution_provider,
)


# ==============================================================================
# Test Fixtures
# ==============================================================================


@pytest.fixture
def valid_csv_content():
    """Provide valid CSV content for FileDataFeed."""
    return (
        "timestamp,symbol,bar_size,open,high,low,close,volume\n"
        "2024-01-01 10:00:00,AAPL,5min,100.0,101.0,99.0,100.5,1000\n"
    )


# ==============================================================================
# SimulationContext Tests
# ==============================================================================


def test_simulation_context_default_values():
    """Test SimulationContext initializes with correct default values."""
    context = SimulationContext()

    assert context.enabled is True
    assert context.data_file is None
    assert context.playback_mode == "instant"
    assert context.speed_multiplier == 1.0


def test_simulation_context_custom_values():
    """Test SimulationContext accepts custom values."""
    context = SimulationContext(
        enabled=False,
        data_file="/path/to/data.csv",
        playback_mode="sequential",
        speed_multiplier=2.5,
    )

    assert context.enabled is False
    assert context.data_file == "/path/to/data.csv"
    assert context.playback_mode == "sequential"
    assert context.speed_multiplier == 2.5


def test_simulation_context_get_playback_mode_instant():
    """Test get_playback_mode returns INSTANT for 'instant' string."""
    context = SimulationContext(playback_mode="instant")

    result = context.get_playback_mode()

    assert result == PlaybackMode.INSTANT


def test_simulation_context_get_playback_mode_sequential():
    """Test get_playback_mode returns SEQUENTIAL for 'sequential' string."""
    context = SimulationContext(playback_mode="sequential")

    result = context.get_playback_mode()

    assert result == PlaybackMode.SEQUENTIAL


def test_simulation_context_get_playback_mode_real_time():
    """Test get_playback_mode returns REAL_TIME for 'real_time' string."""
    context = SimulationContext(playback_mode="real_time")

    result = context.get_playback_mode()

    assert result == PlaybackMode.REAL_TIME


def test_simulation_context_get_playback_mode_invalid_defaults_to_instant():
    """Test get_playback_mode defaults to INSTANT for invalid mode with warning."""
    context = SimulationContext(playback_mode="invalid_mode")

    # Should default to INSTANT even with invalid mode
    result = context.get_playback_mode()

    assert result == PlaybackMode.INSTANT


# ==============================================================================
# create_data_feed_provider Tests - Simulation Mode
# ==============================================================================


@patch("auto_trader.simulation.provider_factory.set_simulation_mode")
def test_create_data_feed_provider_simulation_mode_with_valid_file(
    mock_set_simulation, tmp_path, valid_csv_content
):
    """Test create_data_feed_provider returns FileDataFeed in simulation mode."""
    # Create temporary data file with required columns
    data_file = tmp_path / "test_data.csv"
    data_file.write_text(valid_csv_content)

    context = SimulationContext(
        enabled=True,
        data_file=str(data_file),
        playback_mode="sequential",
        speed_multiplier=2.0,
    )

    provider = create_data_feed_provider(context)

    assert isinstance(provider, FileDataFeed)
    assert provider._file_path == Path(data_file)
    assert provider._playback_mode == PlaybackMode.SEQUENTIAL
    assert provider._speed_multiplier == 2.0
    mock_set_simulation.assert_called_once_with(True)


@patch("auto_trader.simulation.provider_factory.set_simulation_mode")
def test_create_data_feed_provider_simulation_mode_without_data_file_raises_error(
    mock_set_simulation,
):
    """Test create_data_feed_provider raises ValueError when data_file is None."""
    context = SimulationContext(enabled=True, data_file=None)

    with pytest.raises(ValueError) as exc_info:
        create_data_feed_provider(context)

    assert "Simulation mode requires a data file" in str(exc_info.value)
    assert "Set simulation.data_file in config" in str(exc_info.value)
    mock_set_simulation.assert_called_once_with(True)


@patch("auto_trader.simulation.provider_factory.set_simulation_mode")
def test_create_data_feed_provider_simulation_mode_with_nonexistent_file_raises_error(
    mock_set_simulation,
):
    """Test create_data_feed_provider raises ValueError for non-existent file."""
    context = SimulationContext(
        enabled=True, data_file="/path/to/nonexistent/file.csv"
    )

    with pytest.raises(ValueError) as exc_info:
        create_data_feed_provider(context)

    assert "Simulation data file not found" in str(exc_info.value)
    assert "/path/to/nonexistent/file.csv" in str(exc_info.value)
    mock_set_simulation.assert_called_once_with(True)


@patch("auto_trader.simulation.provider_factory.set_simulation_mode")
def test_create_data_feed_provider_simulation_mode_uses_playback_mode(
    mock_set_simulation, tmp_path, valid_csv_content
):
    """Test create_data_feed_provider correctly passes playback mode."""
    data_file = tmp_path / "test_data.csv"
    data_file.write_text(valid_csv_content)

    context = SimulationContext(
        enabled=True, data_file=str(data_file), playback_mode="real_time"
    )

    provider = create_data_feed_provider(context)

    assert isinstance(provider, FileDataFeed)
    assert provider._playback_mode == PlaybackMode.REAL_TIME


@patch("auto_trader.simulation.provider_factory.set_simulation_mode")
def test_create_data_feed_provider_simulation_mode_with_instant_playback(
    mock_set_simulation, tmp_path, valid_csv_content
):
    """Test create_data_feed_provider with instant playback mode."""
    data_file = tmp_path / "test_data.csv"
    data_file.write_text(valid_csv_content)

    context = SimulationContext(
        enabled=True, data_file=str(data_file), playback_mode="instant"
    )

    provider = create_data_feed_provider(context)

    assert isinstance(provider, FileDataFeed)
    assert provider._playback_mode == PlaybackMode.INSTANT


# ==============================================================================
# create_data_feed_provider Tests - Live Mode
# ==============================================================================


@patch("auto_trader.simulation.provider_factory.set_simulation_mode")
def test_create_data_feed_provider_live_mode_with_ib_client_returns_ibkr_feed(
    mock_set_simulation,
):
    """Test create_data_feed_provider returns IBKRDataFeed in live mode."""
    mock_ib_client = Mock()
    context = SimulationContext(enabled=False)

    provider = create_data_feed_provider(context, ib_client=mock_ib_client)

    assert isinstance(provider, IBKRDataFeed)
    assert provider._ib_client is mock_ib_client
    mock_set_simulation.assert_called_once_with(False)


@patch("auto_trader.simulation.provider_factory.set_simulation_mode")
def test_create_data_feed_provider_live_mode_without_ib_client_raises_error(
    mock_set_simulation,
):
    """Test create_data_feed_provider raises ValueError when ib_client is None."""
    context = SimulationContext(enabled=False)

    with pytest.raises(ValueError) as exc_info:
        create_data_feed_provider(context, ib_client=None)

    assert "Live mode requires an IB client instance" in str(exc_info.value)
    assert "Provide ib_client parameter" in str(exc_info.value)
    mock_set_simulation.assert_called_once_with(False)


# ==============================================================================
# create_order_execution_provider Tests
# ==============================================================================


def test_create_order_execution_provider_simulation_mode_returns_simulated():
    """Test create_order_execution_provider returns SimulatedOrderExecution."""
    context = SimulationContext(enabled=True)

    provider = create_order_execution_provider(context)

    assert isinstance(provider, SimulatedOrderExecution)


def test_create_order_execution_provider_live_mode_raises_not_implemented():
    """Test create_order_execution_provider raises NotImplementedError for live mode."""
    context = SimulationContext(enabled=False)

    with pytest.raises(NotImplementedError) as exc_info:
        create_order_execution_provider(context)

    assert "Live order execution not implemented in factory" in str(exc_info.value)
    assert "Use OrderExecutionManager for live trading" in str(exc_info.value)


# ==============================================================================
# Integration Tests
# ==============================================================================


@patch("auto_trader.simulation.provider_factory.set_simulation_mode")
def test_create_providers_simulation_mode_integration(
    mock_set_simulation, tmp_path, valid_csv_content
):
    """Test creating both providers in simulation mode works together."""
    data_file = tmp_path / "integration_test.csv"
    data_file.write_text(valid_csv_content)

    context = SimulationContext(enabled=True, data_file=str(data_file))

    data_feed = create_data_feed_provider(context)
    order_execution = create_order_execution_provider(context)

    assert isinstance(data_feed, FileDataFeed)
    assert isinstance(order_execution, SimulatedOrderExecution)
    mock_set_simulation.assert_called_once_with(True)


@patch("auto_trader.simulation.provider_factory.set_simulation_mode")
def test_create_providers_live_mode_data_feed_only(mock_set_simulation):
    """Test creating data feed in live mode with IB client."""
    mock_ib_client = Mock()
    context = SimulationContext(enabled=False)

    data_feed = create_data_feed_provider(context, ib_client=mock_ib_client)

    assert isinstance(data_feed, IBKRDataFeed)
    # Order execution should raise NotImplementedError in live mode
    with pytest.raises(NotImplementedError):
        create_order_execution_provider(context)
    mock_set_simulation.assert_called_once_with(False)


@patch("auto_trader.simulation.provider_factory.set_simulation_mode")
def test_create_data_feed_provider_with_custom_speed_multiplier(
    mock_set_simulation, tmp_path, valid_csv_content
):
    """Test create_data_feed_provider passes custom speed multiplier."""
    data_file = tmp_path / "speed_test.csv"
    data_file.write_text(valid_csv_content)

    context = SimulationContext(
        enabled=True, data_file=str(data_file), speed_multiplier=5.0
    )

    provider = create_data_feed_provider(context)

    assert isinstance(provider, FileDataFeed)
    assert provider._speed_multiplier == 5.0
