"""Tests for connection manager implementation."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from auto_trader.integrations.ibkr_client.circuit_breaker import CircuitBreakerError


class TestConnectionManager:
    """Test suite for ConnectionManager."""

    @pytest.mark.asyncio
    async def test_connect_success(self, connection_manager):
        """Test successful connection through manager."""
        # Act
        await connection_manager.connect()
        
        # Assert
        connection_manager._circuit_breaker.call_with_circuit_breaker.assert_called_once()
        connection_manager._client.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_connect_circuit_breaker_error(self, connection_manager):
        """Test connection blocked by circuit breaker."""
        # Arrange
        connection_manager._circuit_breaker.call_with_circuit_breaker.side_effect = (
            CircuitBreakerError("Circuit breaker is open")
        )
        
        # Act & Assert
        with pytest.raises(CircuitBreakerError):
            await connection_manager.connect()

    @pytest.mark.asyncio
    async def test_connect_connection_error(self, connection_manager):
        """Test connection error handling."""
        # Arrange
        connection_manager._circuit_breaker.call_with_circuit_breaker.side_effect = (
            Exception("Connection failed")
        )
        
        # Act & Assert
        with pytest.raises(Exception, match="Connection failed"):
            await connection_manager.connect()

    @pytest.mark.asyncio
    async def test_disconnect(self, connection_manager):
        """Test graceful disconnection."""
        # Create a real async task that we can control
        async def dummy_task():
            await asyncio.sleep(1)  # This will be cancelled
        
        # Start the task and assign it
        mock_task = asyncio.create_task(dummy_task())
        connection_manager._reconnection_task = mock_task
        
        # Ensure client.disconnect is properly mocked as async
        connection_manager._client.disconnect = AsyncMock()
        
        # Act
        await connection_manager.disconnect()
        
        # Assert
        assert mock_task.cancelled()  # Task should be cancelled
        connection_manager._client.disconnect.assert_called_once()

    def test_is_connected_true(self, connection_manager):
        """Test is_connected when client is connected."""
        # Arrange
        connection_manager._client.is_connected.return_value = True
        
        # Act & Assert
        assert connection_manager.is_connected() is True

    def test_is_connected_false(self, connection_manager):
        """Test is_connected when client is disconnected."""
        # Arrange
        connection_manager._client.is_connected.return_value = False
        
        # Act & Assert
        assert connection_manager.is_connected() is False

    def test_get_connection_status(self, connection_manager):
        """Test getting connection status."""
        # Arrange
        mock_status = Mock()
        connection_manager._client.get_connection_status.return_value = mock_status
        
        # Act
        status = connection_manager.get_connection_status()
        
        # Assert
        assert status == mock_status

    def test_get_circuit_breaker_state(self, connection_manager):
        """Test getting circuit breaker state."""
        # Arrange
        mock_state = Mock()
        connection_manager._circuit_breaker.get_state.return_value = mock_state
        
        # Act
        state = connection_manager.get_circuit_breaker_state()
        
        # Assert
        assert state == mock_state

    @pytest.mark.asyncio
    async def test_health_check(self, connection_manager):
        """Test comprehensive health check."""
        # Arrange
        mock_connection_status = Mock()
        mock_connection_status.state.value = "connected"
        mock_connection_status.last_connected = None
        mock_connection_status.reconnect_attempts = 0
        mock_connection_status.account_type = "DU123456"
        mock_connection_status.is_paper_account = True
        
        mock_circuit_state = Mock()
        mock_circuit_state.state.value = "closed"
        mock_circuit_state.failure_count = 0
        mock_circuit_state.last_failure_time = None
        
        connection_manager._client.is_connected.return_value = True
        connection_manager._client.get_connection_status.return_value = mock_connection_status
        connection_manager._circuit_breaker.get_state.return_value = mock_circuit_state
        
        # Act
        health = await connection_manager.health_check()
        
        # Assert
        assert health["connected"] is True
        assert health["connection_state"] == "connected"
        assert health["account_type"] == "DU123456"
        assert health["is_paper_account"] is True
        assert health["circuit_breaker_state"] == "closed"
        assert health["circuit_failure_count"] == 0

    def test_setup_signal_handlers(self, connection_manager):
        """Test signal handler registration."""
        with patch('signal.signal') as mock_signal:
            # Act
            connection_manager.setup_signal_handlers()
            
            # Assert
            assert mock_signal.call_count == 2  # SIGTERM and SIGINT

    def test_setup_signal_handlers_error(self, connection_manager):
        """Test signal handler registration error."""
        with patch('signal.signal', side_effect=ValueError("Not main thread")):
            # Act - should not raise exception
            connection_manager.setup_signal_handlers()

    @pytest.mark.asyncio
    async def test_graceful_shutdown_with_position_closure(self, connection_manager):
        """Test graceful shutdown with position closure."""
        # Arrange
        connection_manager._client.is_connected.return_value = True
        # Use the original method for this test
        connection_manager.graceful_shutdown = connection_manager._original_graceful_shutdown
        
        # Act
        await connection_manager.graceful_shutdown()
        
        # Assert
        connection_manager._client.disconnect.assert_called_once()
        assert connection_manager._shutdown_initiated is True

    @pytest.mark.asyncio
    async def test_graceful_shutdown_already_initiated(self, connection_manager):
        """Test graceful shutdown when already initiated."""
        # Arrange
        connection_manager._shutdown_initiated = True
        
        # Act
        await connection_manager.graceful_shutdown()
        
        # Assert
        connection_manager._client.disconnect.assert_not_called()

    @pytest.mark.asyncio
    async def test_graceful_shutdown_with_error(self, connection_manager):
        """Test graceful shutdown with error."""
        # Arrange
        connection_manager._client.disconnect.side_effect = Exception("Disconnect failed")
        # Use the original method for this test
        connection_manager.graceful_shutdown = connection_manager._original_graceful_shutdown
        
        # Act - should not raise exception
        await connection_manager.graceful_shutdown()
        
        # Assert
        assert connection_manager._shutdown_initiated is True

    @pytest.mark.asyncio
    async def test_monitor_connection_reconnect_success(self, connection_manager):
        """Test connection monitoring with successful reconnection."""
        # Setup connection states - always disconnected to trigger reconnection
        connection_manager._client.is_connected.return_value = False
        
        # Mock the circuit breaker to track calls
        connection_manager._circuit_breaker.call_with_circuit_breaker.return_value = None
        
        # Start monitoring - it should check connection immediately and try to reconnect
        monitor_task = asyncio.create_task(connection_manager._monitor_connection())
        
        # Give it time to run the first iteration and detect disconnection
        await asyncio.sleep(6)  # Wait longer than the 5-second check interval
        
        # Stop monitoring gracefully
        connection_manager._shutdown_initiated = True
        
        # Wait for monitoring to complete
        await monitor_task
        
        # Assert - circuit breaker should have been called for reconnection attempt
        connection_manager._circuit_breaker.call_with_circuit_breaker.assert_called()

    @pytest.mark.asyncio
    async def test_monitor_connection_circuit_breaker_open(self, connection_manager):
        """Test connection monitoring when circuit breaker is open."""
        # Setup - always disconnected to trigger reconnection attempts
        connection_manager._client.is_connected.return_value = False
        
        # Make circuit breaker raise error to simulate circuit breaker being open
        connection_manager._circuit_breaker.call_with_circuit_breaker.side_effect = (
            CircuitBreakerError("Circuit breaker is open")
        )
        
        # Start monitoring - should try to reconnect and hit circuit breaker
        monitor_task = asyncio.create_task(connection_manager._monitor_connection())
        
        # Give it time to run first check and hit circuit breaker (which breaks the loop)
        await asyncio.sleep(6)  # Wait longer than the 5-second check interval
        
        # Wait for monitoring to complete (should exit due to circuit breaker)
        await monitor_task
        
        # Assert circuit breaker was called
        connection_manager._circuit_breaker.call_with_circuit_breaker.assert_called()

    @pytest.mark.asyncio
    async def test_monitor_connection_cancelled(self, connection_manager):
        """Test connection monitoring handles cancellation gracefully."""
        # Mock to keep connection active and prevent shutdown
        connection_manager._client.is_connected.return_value = True
        connection_manager._shutdown_initiated = False
        
        # Start monitoring
        monitor_task = asyncio.create_task(connection_manager._monitor_connection())
        
        # Give it a moment to start the monitoring loop
        await asyncio.sleep(0.01)
        
        # Cancel the task
        monitor_task.cancel()
        
        # Wait for task to complete - it should handle cancellation gracefully
        await monitor_task
        
        # Verify the task completed (either cancelled or finished gracefully)
        assert monitor_task.done()
        # The monitoring function catches CancelledError and logs it, so task won't be "cancelled"
        # but will be completed - this is the intended behavior

    @pytest.mark.asyncio
    async def test_close_open_positions_placeholder(self, connection_manager):
        """Test position closure placeholder."""
        # Act - should not raise exception
        await connection_manager._close_open_positions()
        
        # Assert - just verify it completes without error
        # This is a placeholder method for future implementation

    def test_signal_handler_first_call(self, connection_manager):
        """Test signal handler on first call."""
        with patch('asyncio.create_task') as mock_create_task, \
             patch('asyncio.get_event_loop') as mock_get_loop:
            
            mock_loop = Mock()
            mock_loop.is_running.return_value = True
            mock_get_loop.return_value = mock_loop
            
            # Act
            connection_manager._signal_handler(15, None)  # SIGTERM
            
            # Assert
            assert connection_manager._shutdown_initiated is True
            mock_create_task.assert_called_once()

    def test_signal_handler_already_initiated(self, connection_manager):
        """Test signal handler when shutdown already initiated."""
        # Arrange
        connection_manager._shutdown_initiated = True
        
        with patch('asyncio.create_task') as mock_create_task, \
             patch.object(connection_manager, 'graceful_shutdown', new_callable=AsyncMock) as mock_graceful:
            # Act
            connection_manager._signal_handler(15, None)
            
            # Assert
            mock_create_task.assert_not_called()

    @pytest.mark.asyncio
    async def test_start_connection_monitoring(self, connection_manager):
        """Test starting connection monitoring."""
        # Act
        connection_manager._start_connection_monitoring()
        
        # Assert
        assert connection_manager._reconnection_task is not None
        assert not connection_manager._reconnection_task.done()
        
        # Cleanup
        connection_manager._reconnection_task.cancel()
        try:
            await connection_manager._reconnection_task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_start_connection_monitoring_already_running(self, connection_manager):
        """Test starting monitoring when already running."""
        # Arrange
        existing_task = asyncio.create_task(asyncio.sleep(1))
        connection_manager._reconnection_task = existing_task
        
        # Act
        connection_manager._start_connection_monitoring()
        
        # Assert - should keep existing task
        assert connection_manager._reconnection_task is existing_task
        
        # Cleanup
        existing_task.cancel()
        try:
            await existing_task
        except asyncio.CancelledError:
            pass