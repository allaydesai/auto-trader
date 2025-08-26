"""Shared fixtures for IBKR client testing."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch
from pathlib import Path
import tempfile

import pytest
from ib_async import IB

import sys
sys.path.insert(0, str(Path(__file__).parents[5] / "src"))

from auto_trader.integrations.ibkr_client.client import IBKRClient
from auto_trader.integrations.ibkr_client.circuit_breaker import CircuitBreaker
from auto_trader.integrations.ibkr_client.connection_manager import ConnectionManager


@pytest.fixture
def mock_settings():
    """Mock settings for testing."""
    with patch('config.Settings') as mock_settings:
        settings = Mock()
        settings.ibkr_host = "127.0.0.1"
        settings.ibkr_port = 7497
        settings.ibkr_client_id = 1
        settings.discord_webhook_url = "https://discord.com/api/webhooks/test"
        settings.simulation_mode = True
        settings.debug = False
        mock_settings.return_value = settings
        yield settings


@pytest.fixture
def mock_config_loader():
    """Mock configuration loader."""
    with patch('config.ConfigLoader') as mock_loader_class:
        loader = Mock()
        
        # Mock IBKR config
        ibkr_config = Mock()
        ibkr_config.host = "127.0.0.1"
        ibkr_config.port = 7497
        ibkr_config.client_id = 1
        ibkr_config.timeout = 30
        ibkr_config.reconnect_attempts = 5
        ibkr_config.graceful_shutdown = True
        
        system_config = Mock()
        system_config.ibkr = ibkr_config
        
        mock_loader_class.return_value = loader
        loader.system_config = system_config
        loader.load_system_config.return_value = system_config
        
        yield mock_loader_class


@pytest.fixture
def mock_ib():
    """Mock ib-async IB client."""
    with patch('auto_trader.integrations.ibkr_client.client.IB') as mock_ib_class:
        mock_ib = Mock(spec=IB)
        mock_ib.connectAsync = AsyncMock()
        mock_ib.disconnect = Mock()
        mock_ib.isConnected = Mock(return_value=False)
        mock_ib.accountSummaryAsync = AsyncMock()
        mock_ib.managedAccounts = Mock(return_value=["DU123456"])
        
        # Event attributes - need to support += operator
        mock_ib.connectedEvent = Mock()
        mock_ib.connectedEvent.__iadd__ = Mock(return_value=mock_ib.connectedEvent)
        mock_ib.disconnectedEvent = Mock()
        mock_ib.disconnectedEvent.__iadd__ = Mock(return_value=mock_ib.disconnectedEvent)
        mock_ib.errorEvent = Mock()
        mock_ib.errorEvent.__iadd__ = Mock(return_value=mock_ib.errorEvent)
        
        mock_ib_class.return_value = mock_ib
        yield mock_ib


@pytest.fixture
def ibkr_client(mock_settings, mock_config_loader, mock_ib):
    """IBKRClient with mocked dependencies."""
    with patch('auto_trader.integrations.ibkr_client.client.ConfigLoader', mock_config_loader):
        client = IBKRClient(mock_settings)
        client._ib = mock_ib
        yield client


@pytest.fixture 
def temp_state_dir():
    """Temporary directory for state files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def circuit_breaker(temp_state_dir):
    """CircuitBreaker with temporary state file."""
    state_file = temp_state_dir / "circuit_breaker_test.json"
    breaker = CircuitBreaker(
        failure_threshold=3,
        reset_timeout=60,
        state_file=state_file
    )
    yield breaker


@pytest.fixture
async def cleanup_tasks():
    """Fixture to track and cleanup tasks."""
    tasks = []
    yield tasks
    for task in tasks:
        if not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass


@pytest.fixture
def connection_manager(mock_settings, temp_state_dir, mock_config_loader):
    """ConnectionManager with mocked dependencies."""
    with patch('auto_trader.integrations.ibkr_client.connection_manager.IBKRClient') as mock_client_class, \
         patch('auto_trader.integrations.ibkr_client.connection_manager.CircuitBreaker') as mock_breaker_class:
        
        # Setup mock client
        mock_client = Mock()
        mock_client.connect = AsyncMock()
        mock_client.disconnect = AsyncMock() 
        mock_client.is_connected = Mock(return_value=False)
        mock_client.get_connection_status = Mock()
        mock_client._config_loader = Mock()
        mock_client._config_loader.system_config.ibkr.graceful_shutdown = True
        mock_client_class.return_value = mock_client
        
        # Setup mock circuit breaker
        mock_breaker = Mock()
        mock_breaker.call_with_circuit_breaker = AsyncMock(
            side_effect=lambda func, *args, **kwargs: func(*args, **kwargs)
        )
        mock_breaker.get_state = Mock()
        mock_breaker_class.return_value = mock_breaker
        
        manager = ConnectionManager(mock_settings, temp_state_dir)
        manager._client = mock_client
        manager._circuit_breaker = mock_breaker
        
        yield manager


@pytest.fixture
def mock_account_summary():
    """Mock account summary response."""
    account_info = Mock()
    account_info.account = "DU123456"  # Paper account
    return [account_info]


@pytest.fixture
def mock_live_account_summary():
    """Mock live account summary response."""
    account_info = Mock()
    account_info.account = "U123456"  # Live account
    return [account_info]