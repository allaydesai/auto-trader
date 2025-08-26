"""Tests for IBKR client implementation."""

import pytest
from unittest.mock import patch

from auto_trader.integrations.ibkr_client.client import (
    ConnectionState,
    IBKRConnectionError,
    IBKRTimeoutError,
    IBKRAuthenticationError
)


class TestIBKRClient:
    """Test suite for IBKRClient."""

    @pytest.mark.asyncio
    async def test_connect_success(self, ibkr_client, mock_ib, mock_account_summary):
        """Test successful IBKR connection establishment."""
        # Arrange
        mock_ib.connectAsync.return_value = None
        mock_ib.isConnected.return_value = True
        mock_ib.accountSummaryAsync.return_value = mock_account_summary
        
        # Act
        await ibkr_client.connect()
        
        # Assert
        assert ibkr_client.is_connected()
        assert ibkr_client._connection_status.state == ConnectionState.CONNECTED
        assert ibkr_client._connection_status.account_type == "DU123456"
        assert ibkr_client._connection_status.is_paper_account is True
        mock_ib.connectAsync.assert_called_once_with(
            host="127.0.0.1",
            port=7497,
            clientId=1,
            timeout=30
        )

    @pytest.mark.asyncio
    async def test_connect_already_connected(self, ibkr_client, mock_ib):
        """Test connection when already connected."""
        # Arrange
        mock_ib.isConnected.return_value = True
        ibkr_client._connection_status.state = ConnectionState.CONNECTED
        
        # Act
        await ibkr_client.connect()
        
        # Assert
        mock_ib.connectAsync.assert_not_called()

    @pytest.mark.asyncio
    async def test_connect_timeout_error(self, ibkr_client, mock_ib):
        """Test connection timeout handling."""
        # Arrange
        mock_ib.connectAsync.side_effect = Exception("Connection timeout")
        
        # Act & Assert
        with pytest.raises(IBKRTimeoutError, match="Connection timeout"):
            await ibkr_client.connect()
        
        assert ibkr_client._connection_status.state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_connect_authentication_error(self, ibkr_client, mock_ib):
        """Test authentication error handling."""
        # Arrange
        mock_ib.connectAsync.side_effect = Exception("Authentication failed")
        
        # Act & Assert
        with pytest.raises(IBKRAuthenticationError, match="Authentication failed"):
            await ibkr_client.connect()

    @pytest.mark.asyncio  
    async def test_connect_general_error(self, ibkr_client, mock_ib):
        """Test general connection error handling."""
        # Arrange
        mock_ib.connectAsync.side_effect = Exception("Network error")
        
        # Act & Assert
        with pytest.raises(IBKRConnectionError, match="Connection failed"):
            await ibkr_client.connect()

    @pytest.mark.asyncio
    async def test_disconnect_success(self, ibkr_client, mock_ib):
        """Test successful disconnection."""
        # Arrange
        mock_ib.isConnected.return_value = True
        ibkr_client._connection_status.state = ConnectionState.CONNECTED
        
        # Act
        await ibkr_client.disconnect()
        
        # Assert
        mock_ib.disconnect.assert_called_once()
        assert ibkr_client._connection_status.state == ConnectionState.DISCONNECTED

    @pytest.mark.asyncio
    async def test_disconnect_already_disconnected(self, ibkr_client, mock_ib):
        """Test disconnection when already disconnected."""
        # Arrange
        mock_ib.isConnected.return_value = False
        
        # Act
        await ibkr_client.disconnect()
        
        # Assert
        mock_ib.disconnect.assert_not_called()

    def test_is_connected_true(self, ibkr_client, mock_ib):
        """Test is_connected when connected."""
        # Arrange
        mock_ib.isConnected.return_value = True
        ibkr_client._connection_status.state = ConnectionState.CONNECTED
        
        # Act & Assert
        assert ibkr_client.is_connected() is True

    def test_is_connected_false(self, ibkr_client, mock_ib):
        """Test is_connected when disconnected."""
        # Arrange
        mock_ib.isConnected.return_value = False
        ibkr_client._connection_status.state = ConnectionState.DISCONNECTED
        
        # Act & Assert
        assert ibkr_client.is_connected() is False

    def test_get_connection_status(self, ibkr_client):
        """Test getting connection status."""
        # Arrange
        ibkr_client._connection_status.account_type = "DU123456"
        ibkr_client._connection_status.is_paper_account = True
        
        # Act
        status = ibkr_client.get_connection_status()
        
        # Assert
        assert status.account_type == "DU123456"
        assert status.is_paper_account is True

    @pytest.mark.asyncio
    async def test_detect_account_type_paper(self, ibkr_client, mock_ib, mock_account_summary):
        """Test paper account detection."""
        # Arrange
        mock_ib.accountSummaryAsync.return_value = mock_account_summary
        
        # Act
        account_id, is_paper = await ibkr_client._detect_account_type()
        
        # Assert
        assert account_id == "DU123456"
        assert is_paper is True

    @pytest.mark.asyncio
    async def test_detect_account_type_live(self, ibkr_client, mock_ib, mock_live_account_summary):
        """Test live account detection."""
        # Arrange
        mock_ib.accountSummaryAsync.return_value = mock_live_account_summary
        
        # Act
        account_id, is_paper = await ibkr_client._detect_account_type()
        
        # Assert
        assert account_id == "U123456"
        assert is_paper is False

    @pytest.mark.asyncio
    async def test_detect_account_type_fallback(self, ibkr_client, mock_ib):
        """Test account detection fallback to managedAccounts."""
        # Arrange
        mock_ib.accountSummaryAsync.return_value = []
        mock_ib.managedAccounts.return_value = ["DU789012"]
        
        # Act
        account_id, is_paper = await ibkr_client._detect_account_type()
        
        # Assert
        assert account_id == "DU789012"
        assert is_paper is True

    @pytest.mark.asyncio
    async def test_detect_account_type_error(self, ibkr_client, mock_ib):
        """Test account detection error handling."""
        # Arrange
        mock_ib.accountSummaryAsync.side_effect = Exception("API error")
        mock_ib.managedAccounts.return_value = []
        
        # Act
        account_id, is_paper = await ibkr_client._detect_account_type()
        
        # Assert
        assert account_id == "UNKNOWN"
        assert is_paper is True  # Default to paper for safety

    def test_log_account_type_warning_paper(self, ibkr_client):
        """Test paper account logging."""
        with patch('auto_trader.integrations.ibkr_client.client.logger') as mock_logger:
            # Act
            ibkr_client._log_account_type_warning("DU123456", True)
            
            # Assert
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert "PAPER TRADING ACCOUNT DETECTED" in call_args[0][0]

    def test_log_account_type_warning_live(self, ibkr_client):
        """Test live account logging."""
        with patch('auto_trader.integrations.ibkr_client.client.logger') as mock_logger:
            # Act
            ibkr_client._log_account_type_warning("U123456", False)
            
            # Assert
            mock_logger.critical.assert_called_once()
            call_args = mock_logger.critical.call_args
            assert "LIVE TRADING ACCOUNT DETECTED" in call_args[0][0]

    def test_on_connected_event(self, ibkr_client):
        """Test connected event handler."""
        with patch('auto_trader.integrations.ibkr_client.client.logger') as mock_logger:
            # Act
            ibkr_client._on_connected()
            
            # Assert
            mock_logger.debug.assert_called_once_with("IBKR connection event: connected")

    def test_on_disconnected_event(self, ibkr_client):
        """Test disconnected event handler."""
        with patch('auto_trader.integrations.ibkr_client.client.logger') as mock_logger:
            # Arrange
            ibkr_client._connection_status.state = ConnectionState.CONNECTED
            
            # Act
            ibkr_client._on_disconnected()
            
            # Assert
            mock_logger.warning.assert_called_once_with("IBKR connection event: disconnected")
            assert ibkr_client._connection_status.state == ConnectionState.DISCONNECTED

    def test_on_disconnected_event_during_shutdown(self, ibkr_client):
        """Test disconnected event handler during shutdown."""
        # Arrange
        ibkr_client._connection_status.state = ConnectionState.SHUTDOWN
        
        # Act
        ibkr_client._on_disconnected()
        
        # Assert - state should remain SHUTDOWN
        assert ibkr_client._connection_status.state == ConnectionState.SHUTDOWN

    def test_on_error_event_info(self, ibkr_client):
        """Test error event handler for informational messages."""
        with patch('auto_trader.integrations.ibkr_client.client.logger') as mock_logger:
            # Act
            ibkr_client._on_error(1, 2104, "Market data farm connection is OK")
            
            # Assert
            mock_logger.debug.assert_called_once()

    def test_on_error_event_warning(self, ibkr_client):
        """Test error event handler for warnings."""
        with patch('auto_trader.integrations.ibkr_client.client.logger') as mock_logger:
            # Act
            ibkr_client._on_error(1, 2100, "API client has been unsubscribed")
            
            # Assert
            mock_logger.warning.assert_called_once()

    def test_on_error_event_error(self, ibkr_client):
        """Test error event handler for actual errors."""
        with patch('auto_trader.integrations.ibkr_client.client.logger') as mock_logger:
            # Act
            ibkr_client._on_error(1, 502, "Couldn't connect to TWS")
            
            # Assert
            mock_logger.error.assert_called_once()