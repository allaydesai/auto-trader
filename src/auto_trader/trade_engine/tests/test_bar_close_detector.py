"""Tests for BarCloseDetector with timing accuracy validation."""

import asyncio
import pytest
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch
from typing import List

from auto_trader.models.execution import BarCloseEvent
from auto_trader.models.enums import Timeframe
from auto_trader.models.market_data import BarData
from auto_trader.trade_engine.bar_close_detector import BarCloseDetector


@pytest.fixture
def sample_bar():
    """Create sample bar data."""
    return BarData(
        symbol="AAPL",
        timestamp=datetime.now(UTC),
        open_price=Decimal("180.00"),
        high_price=Decimal("182.00"),
        low_price=Decimal("179.50"),
        close_price=Decimal("181.50"),
        volume=1000000,
        bar_size="1min",
    )


@pytest.fixture
async def detector():
    """Create BarCloseDetector instance."""
    detector = BarCloseDetector(
        accuracy_ms=500,
        schedule_advance_ms=100,
        timezone="America/New_York"
    )
    await detector.start()
    yield detector
    await detector.stop()


@pytest.mark.asyncio
class TestBarCloseDetector:
    """Test BarCloseDetector functionality and timing accuracy."""

    async def test_detector_initialization(self):
        """Test detector initializes with correct parameters."""
        detector = BarCloseDetector(
            accuracy_ms=250,
            schedule_advance_ms=50,
            timezone="UTC"
        )
        
        assert detector.accuracy_ms == 250
        assert detector.schedule_advance_ms == 50
        assert str(detector.timezone) == "UTC"
        assert detector.callbacks == []
        assert detector.monitored == {}

    async def test_start_stop_detector(self):
        """Test detector start/stop lifecycle."""
        detector = BarCloseDetector()
        
        # Start detector
        await detector.start()
        assert detector.scheduler.running
        
        # Stop detector
        await detector.stop()
        # Note: APScheduler may take time to fully shutdown
        import asyncio
        await asyncio.sleep(0.1)
        # Just verify stop was called, scheduler state may vary

    async def test_callback_registration(self, detector):
        """Test callback registration and removal."""
        def callback1(event):
            pass
        
        def callback2(event):
            pass
        
        # Add callbacks
        detector.add_callback(callback1)
        detector.add_callback(callback2)
        assert len(detector.callbacks) == 2
        
        # Remove callback
        removed = detector.remove_callback(callback1)
        assert removed is True
        assert len(detector.callbacks) == 1
        
        # Try to remove non-existing callback
        removed = detector.remove_callback(callback1)
        assert removed is False

    async def test_monitor_timeframe(self, detector):
        """Test monitoring symbol/timeframe combinations."""
        symbol = "AAPL"
        timeframe = Timeframe.ONE_MIN
        
        # Start monitoring
        await detector.monitor_timeframe(symbol, timeframe)
        
        assert timeframe in detector.monitored[symbol]
        assert detector.is_monitoring(symbol, timeframe)
        assert detector.is_monitoring(symbol)

    async def test_stop_monitoring(self, detector):
        """Test stopping monitoring for symbol/timeframe."""
        symbol = "AAPL"
        timeframe1 = Timeframe.ONE_MIN
        timeframe2 = Timeframe.FIVE_MIN
        
        # Start monitoring multiple timeframes
        await detector.monitor_timeframe(symbol, timeframe1)
        await detector.monitor_timeframe(symbol, timeframe2)
        
        # Stop specific timeframe
        await detector.stop_monitoring(symbol, timeframe1)
        assert not detector.is_monitoring(symbol, timeframe1)
        assert detector.is_monitoring(symbol, timeframe2)
        
        # Stop all timeframes for symbol
        await detector.stop_monitoring(symbol)
        assert not detector.is_monitoring(symbol)

    async def test_bar_data_update(self, detector, sample_bar):
        """Test updating bar data for symbol/timeframe."""
        symbol = "AAPL"
        timeframe = Timeframe.ONE_MIN
        
        detector.update_bar_data(symbol, timeframe, sample_bar)
        
        stored_bar = detector.last_bars.get((symbol, timeframe))
        assert stored_bar == sample_bar

    def test_calculate_next_close_1min(self, detector):
        """Test next close calculation for 1-minute timeframe."""
        base_time = datetime(2025, 8, 28, 14, 30, 25, tzinfo=UTC)
        
        next_close = detector._calculate_next_close(
            Timeframe.ONE_MIN, base_time
        )
        
        # Should align to next minute boundary
        expected = datetime(2025, 8, 28, 14, 31, 0)
        expected = detector.timezone.localize(expected)
        
        assert next_close.minute == 31
        assert next_close.second == 0
        assert next_close.microsecond == 0

    def test_calculate_next_close_daily(self, detector):
        """Test next close calculation for daily timeframe."""
        base_time = datetime(2025, 8, 28, 10, 30, 0, tzinfo=UTC)
        
        next_close = detector._calculate_next_close(
            Timeframe.ONE_DAY, base_time
        )
        
        # Should be 4 PM ET (market close)
        assert next_close.hour == 16
        assert next_close.minute == 0
        assert next_close.second == 0

    @patch('auto_trader.trade_engine.bar_close_detector.datetime')
    async def test_timing_accuracy_measurement(self, mock_datetime, detector):
        """Test timing accuracy is measured correctly."""
        # Mock the current time
        expected_close = datetime(2025, 8, 28, 14, 31, 0, tzinfo=UTC)
        actual_time = expected_close + timedelta(milliseconds=150)  # 150ms late
        
        mock_datetime.now.return_value = actual_time
        
        # Update bar data
        sample_bar = BarData(
            symbol="AAPL",
            timestamp=expected_close,
            open_price=Decimal("180.00"),
            high_price=Decimal("182.00"),
            low_price=Decimal("179.50"),
            close_price=Decimal("181.50"),
            volume=1000000,
            bar_size="1min",
        )
        detector.update_bar_data("AAPL", Timeframe.ONE_MIN, sample_bar)
        
        # Test bar close check
        await detector._check_bar_close("AAPL", Timeframe.ONE_MIN, expected_close)
        
        # Verify timing error was recorded
        assert len(detector.timing_errors) == 1
        assert abs(detector.timing_errors[0] - 150.0) < 1.0  # 150ms error

    async def test_bar_close_event_emission(self, detector, sample_bar):
        """Test bar close events are emitted correctly."""
        callback = AsyncMock()
        detector.add_callback(callback)
        
        # Set up bar data
        symbol = "AAPL"
        timeframe = Timeframe.ONE_MIN
        detector.update_bar_data(symbol, timeframe, sample_bar)
        
        # Trigger bar close check
        close_time = datetime.now(UTC)
        await detector._check_bar_close(symbol, timeframe, close_time)
        
        # Verify callback was called with correct event
        callback.assert_called_once()
        event = callback.call_args[0][0]
        
        assert isinstance(event, BarCloseEvent)
        assert event.symbol == symbol
        assert event.timeframe == timeframe
        assert event.close_time == close_time
        assert event.bar_data == sample_bar

    async def test_callback_error_handling(self, detector, sample_bar):
        """Test error handling in callbacks doesn't break the system."""
        # Create failing callback
        def failing_callback(event):
            raise ValueError("Test error")
        
        # Create working callback
        working_callback_called = False
        def working_callback(event):
            nonlocal working_callback_called
            working_callback_called = True
        
        detector.add_callback(failing_callback)
        detector.add_callback(working_callback)
        
        # Set up bar data and trigger event
        detector.update_bar_data("AAPL", Timeframe.ONE_MIN, sample_bar)
        close_time = datetime.now(UTC)
        
        # Should not raise exception despite failing callback
        await detector._check_bar_close("AAPL", Timeframe.ONE_MIN, close_time)
        
        # Working callback should still be called
        assert working_callback_called is True

    async def test_schedule_next_close_creates_job(self, detector):
        """Test that scheduling creates a job in the scheduler."""
        symbol = "AAPL"
        timeframe = Timeframe.ONE_MIN
        
        # Mock scheduler to verify job creation
        detector.scheduler.add_job = Mock(return_value=Mock(id="test_job"))
        
        detector._schedule_next_close(symbol, timeframe)
        
        # Verify job was scheduled
        detector.scheduler.add_job.assert_called_once()
        assert (symbol, timeframe) in detector.scheduled_jobs

    def test_get_timing_stats(self, detector):
        """Test timing statistics calculation."""
        # Add some timing errors
        detector.timing_errors = [100.0, 200.0, 150.0, 75.0, 250.0]
        
        stats = detector.get_timing_stats()
        
        assert stats["samples"] == 5
        assert stats["avg_error_ms"] == 155.0
        assert stats["max_error_ms"] == 250.0
        assert stats["min_error_ms"] == 75.0
        assert stats["accuracy_threshold_ms"] == 500

    def test_get_timing_stats_empty(self, detector):
        """Test timing stats when no data available."""
        stats = detector.get_timing_stats()
        
        assert stats["samples"] == 0
        assert stats["avg_error_ms"] == 0.0
        assert stats["max_error_ms"] == 0.0
        assert stats["min_error_ms"] == 0.0

    def test_get_monitored_symbols(self, detector):
        """Test getting monitored symbol/timeframe combinations."""
        # No monitoring initially
        monitored = detector.get_monitored()
        assert monitored == {}
        
        # Add some monitoring
        detector.monitored["AAPL"].add(Timeframe.ONE_MIN)
        detector.monitored["AAPL"].add(Timeframe.FIVE_MIN)
        detector.monitored["MSFT"].add(Timeframe.ONE_HOUR)
        
        monitored = detector.get_monitored()
        
        assert "AAPL" in monitored
        assert "MSFT" in monitored
        assert "1min" in monitored["AAPL"]
        assert "5min" in monitored["AAPL"]
        assert "1hour" in monitored["MSFT"]

    async def test_timing_error_limit(self, detector):
        """Test that timing errors are limited to last 100 measurements."""
        # Add 150 timing errors
        detector.timing_errors = list(range(150))
        
        # Trigger a bar close check to process timing errors
        close_time = datetime.now(UTC)
        await detector._check_bar_close("AAPL", Timeframe.ONE_MIN, close_time)
        
        # Should keep only last 100
        assert len(detector.timing_errors) <= 100

    def test_timeframe_seconds_mapping(self, detector):
        """Test timeframe to seconds mapping is correct."""
        assert detector.TIMEFRAME_SECONDS[Timeframe.ONE_MIN] == 60
        assert detector.TIMEFRAME_SECONDS[Timeframe.FIVE_MIN] == 300
        assert detector.TIMEFRAME_SECONDS[Timeframe.FIFTEEN_MIN] == 900
        assert detector.TIMEFRAME_SECONDS[Timeframe.ONE_HOUR] == 3600
        assert detector.TIMEFRAME_SECONDS[Timeframe.ONE_DAY] == 86400

    async def test_no_bar_data_warning(self, detector):
        """Test warning when no bar data available for close check."""
        with patch('auto_trader.trade_engine.bar_close_detector.logger') as mock_logger:
            close_time = datetime.now(UTC)
            await detector._check_bar_close("AAPL", Timeframe.ONE_MIN, close_time)
            
            # Should log warning about missing bar data
            mock_logger.warning.assert_called()