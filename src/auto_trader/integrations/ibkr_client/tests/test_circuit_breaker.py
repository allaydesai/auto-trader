"""Tests for circuit breaker implementation."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from auto_trader.integrations.ibkr_client.circuit_breaker import CircuitBreaker, CircuitBreakerError, CircuitState


class TestCircuitBreaker:
    """Test suite for CircuitBreaker."""

    def test_init_default_values(self, circuit_breaker):
        """Test circuit breaker initialization with defaults."""
        assert circuit_breaker._failure_threshold == 3
        assert circuit_breaker._reset_timeout == 60
        assert circuit_breaker._state.state == CircuitState.CLOSED
        assert circuit_breaker._state.failure_count == 0

    def test_calculate_backoff_delay(self, circuit_breaker):
        """Test exponential backoff delay calculation."""
        # Test exponential progression: 1, 2, 4, 8, 16
        assert circuit_breaker.calculate_backoff_delay(0) == 1
        assert circuit_breaker.calculate_backoff_delay(1) == 2
        assert circuit_breaker.calculate_backoff_delay(2) == 4
        assert circuit_breaker.calculate_backoff_delay(3) == 8
        assert circuit_breaker.calculate_backoff_delay(4) == 16
        
        # Test cap at 60 seconds
        assert circuit_breaker.calculate_backoff_delay(10) == 60

    def test_calculate_backoff_delay_custom_base(self, circuit_breaker):
        """Test backoff delay with custom base delay."""
        assert circuit_breaker.calculate_backoff_delay(0, base_delay=2) == 2
        assert circuit_breaker.calculate_backoff_delay(1, base_delay=2) == 4
        assert circuit_breaker.calculate_backoff_delay(2, base_delay=2) == 8

    @pytest.mark.asyncio
    async def test_call_with_circuit_breaker_success(self, circuit_breaker):
        """Test successful function execution through circuit breaker."""
        # Arrange
        mock_func = AsyncMock(return_value="success")
        
        # Act
        result = await circuit_breaker.call_with_circuit_breaker(mock_func, "arg1", kwarg1="kwarg1")
        
        # Assert
        assert result == "success"
        mock_func.assert_called_once_with("arg1", kwarg1="kwarg1")
        assert circuit_breaker._state.state == CircuitState.CLOSED
        assert circuit_breaker._state.failure_count == 0

    @pytest.mark.asyncio
    async def test_call_with_circuit_breaker_failure(self, circuit_breaker):
        """Test function failure handling."""
        # Arrange
        mock_func = AsyncMock(side_effect=Exception("Connection failed"))
        
        # Act & Assert
        with pytest.raises(Exception, match="Connection failed"):
            await circuit_breaker.call_with_circuit_breaker(mock_func)
        
        assert circuit_breaker._state.failure_count == 1
        assert circuit_breaker._state.state == CircuitState.CLOSED  # Not open yet

    @pytest.mark.asyncio
    async def test_call_with_circuit_breaker_opens_after_threshold(self, circuit_breaker):
        """Test circuit breaker opens after failure threshold."""
        # Arrange
        mock_func = AsyncMock(side_effect=Exception("Connection failed"))
        
        # Act - fail enough times to open circuit
        for i in range(3):
            with pytest.raises(Exception):
                await circuit_breaker.call_with_circuit_breaker(mock_func)
        
        # Assert
        assert circuit_breaker._state.state == CircuitState.OPEN
        assert circuit_breaker._state.failure_count == 3

    @pytest.mark.asyncio
    async def test_call_with_circuit_breaker_blocked_when_open(self, circuit_breaker):
        """Test circuit breaker blocks calls when open."""
        # Arrange - force circuit to open
        circuit_breaker._state.state = CircuitState.OPEN
        circuit_breaker._state.next_attempt_time = datetime.now() + timedelta(seconds=30)
        mock_func = AsyncMock()
        
        # Act & Assert
        with pytest.raises(CircuitBreakerError, match="Circuit breaker is open"):
            await circuit_breaker.call_with_circuit_breaker(mock_func)
        
        mock_func.assert_not_called()

    @pytest.mark.asyncio
    async def test_call_with_circuit_breaker_half_open_recovery(self, circuit_breaker):
        """Test circuit breaker half-open recovery."""
        # Arrange - set circuit to open with past next attempt time
        circuit_breaker._state.state = CircuitState.OPEN
        circuit_breaker._state.next_attempt_time = datetime.now() - timedelta(seconds=1)
        mock_func = AsyncMock(return_value="recovered")
        
        # Act
        result = await circuit_breaker.call_with_circuit_breaker(mock_func)
        
        # Assert
        assert result == "recovered"
        assert circuit_breaker._state.state == CircuitState.CLOSED
        assert circuit_breaker._state.failure_count == 0

    @pytest.mark.asyncio
    async def test_call_with_circuit_breaker_backoff_delay(self, circuit_breaker):
        """Test backoff delay is applied."""
        # Arrange
        mock_func = AsyncMock(return_value="success")
        circuit_breaker._state.failure_count = 2  # Should cause 2s delay
        
        start_time = datetime.now()
        
        # Act
        await circuit_breaker.call_with_circuit_breaker(mock_func)
        
        end_time = datetime.now()
        
        # Assert - should have delayed for ~2 seconds
        delay = (end_time - start_time).total_seconds()
        assert delay >= 2.0
        assert delay < 2.5  # Allow some margin

    def test_record_failure_increment(self, circuit_breaker):
        """Test failure count increments."""
        # Act
        circuit_breaker.record_failure()
        
        # Assert
        assert circuit_breaker._state.failure_count == 1
        assert circuit_breaker._state.last_failure_time is not None

    def test_record_failure_opens_circuit(self, circuit_breaker):
        """Test circuit opens after threshold failures."""
        # Arrange - simulate near threshold
        circuit_breaker._state.failure_count = 2
        
        # Act
        circuit_breaker.record_failure()
        
        # Assert
        assert circuit_breaker._state.state == CircuitState.OPEN
        assert circuit_breaker._state.failure_count == 3
        assert circuit_breaker._state.next_attempt_time is not None

    def test_record_success_resets_state(self, circuit_breaker):
        """Test success resets circuit breaker state."""
        # Arrange - simulate some failures
        circuit_breaker._state.failure_count = 2
        circuit_breaker._state.last_failure_time = datetime.now()
        
        # Act
        circuit_breaker.record_success()
        
        # Assert
        assert circuit_breaker._state.state == CircuitState.CLOSED
        assert circuit_breaker._state.failure_count == 0
        assert circuit_breaker._state.last_failure_time is None
        assert circuit_breaker._state.next_attempt_time is None

    def test_get_state(self, circuit_breaker):
        """Test getting circuit breaker state."""
        # Arrange
        circuit_breaker._state.failure_count = 1
        
        # Act
        state = circuit_breaker.get_state()
        
        # Assert
        assert state.failure_count == 1
        assert state.state == CircuitState.CLOSED

    def test_is_open_false(self, circuit_breaker):
        """Test is_open returns False when closed."""
        assert circuit_breaker.is_open() is False

    def test_is_open_true(self, circuit_breaker):
        """Test is_open returns True when open."""
        # Arrange
        circuit_breaker._state.state = CircuitState.OPEN
        
        # Act & Assert
        assert circuit_breaker.is_open() is True

    def test_should_attempt_reset_no_next_attempt_time(self, circuit_breaker):
        """Test should_attempt_reset when no next_attempt_time set."""
        # Arrange
        circuit_breaker._state.next_attempt_time = None
        
        # Act & Assert
        assert circuit_breaker._should_attempt_reset() is True

    def test_should_attempt_reset_time_passed(self, circuit_breaker):
        """Test should_attempt_reset when enough time has passed."""
        # Arrange
        circuit_breaker._state.next_attempt_time = datetime.now() - timedelta(seconds=1)
        
        # Act & Assert
        assert circuit_breaker._should_attempt_reset() is True

    def test_should_attempt_reset_time_not_passed(self, circuit_breaker):
        """Test should_attempt_reset when not enough time has passed."""
        # Arrange
        circuit_breaker._state.next_attempt_time = datetime.now() + timedelta(seconds=30)
        
        # Act & Assert
        assert circuit_breaker._should_attempt_reset() is False

    def test_time_until_next_attempt_no_time_set(self, circuit_breaker):
        """Test time_until_next_attempt when no time set."""
        # Arrange
        circuit_breaker._state.next_attempt_time = None
        
        # Act & Assert
        assert circuit_breaker._time_until_next_attempt() == 0.0

    def test_time_until_next_attempt_future_time(self, circuit_breaker):
        """Test time_until_next_attempt with future time."""
        # Arrange
        circuit_breaker._state.next_attempt_time = datetime.now() + timedelta(seconds=30)
        
        # Act
        time_left = circuit_breaker._time_until_next_attempt()
        
        # Assert
        assert 25 < time_left < 35  # Should be around 30 seconds

    def test_time_until_next_attempt_past_time(self, circuit_breaker):
        """Test time_until_next_attempt with past time."""
        # Arrange
        circuit_breaker._state.next_attempt_time = datetime.now() - timedelta(seconds=10)
        
        # Act & Assert
        assert circuit_breaker._time_until_next_attempt() == 0.0

    def test_save_and_load_state(self, circuit_breaker, temp_state_dir):
        """Test state persistence to file."""
        # Arrange
        circuit_breaker._state.failure_count = 2
        circuit_breaker._state.last_failure_time = datetime.now()
        
        # Act - save state
        circuit_breaker._save_state()
        
        # Create new instance to test loading
        new_breaker = CircuitBreaker(
            failure_threshold=3,
            state_file=circuit_breaker._state_file
        )
        
        # Assert
        assert new_breaker._state.failure_count == 2
        assert new_breaker._state.last_failure_time is not None

    def test_load_state_file_not_exists(self, temp_state_dir):
        """Test loading state when file doesn't exist."""
        # Arrange
        non_existent_file = temp_state_dir / "non_existent.json"
        
        # Act
        breaker = CircuitBreaker(state_file=non_existent_file)
        
        # Assert
        assert breaker._state.state == CircuitState.CLOSED
        assert breaker._state.failure_count == 0

    def test_load_state_invalid_json(self, temp_state_dir):
        """Test loading state with invalid JSON."""
        # Arrange
        state_file = temp_state_dir / "invalid.json"
        with open(state_file, 'w') as f:
            f.write("invalid json{")
        
        # Act
        breaker = CircuitBreaker(state_file=state_file)
        
        # Assert - should use default state
        assert breaker._state.state == CircuitState.CLOSED
        assert breaker._state.failure_count == 0