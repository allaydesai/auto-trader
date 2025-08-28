"""Bar close detection system with high precision timing."""

import asyncio
from datetime import datetime, timedelta, UTC
from typing import Dict, List, Callable, Optional, Set, Tuple
from collections import defaultdict
import pytz

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from loguru import logger

from auto_trader.models.execution import BarCloseEvent
from auto_trader.models.enums import Timeframe
from auto_trader.models.market_data import BarData


class BarCloseDetector:
    """Detect bar closes with <1 second accuracy.

    Uses APScheduler for precise timing and manages multiple timeframes
    simultaneously for efficient monitoring.
    """

    # Mapping of timeframe to seconds
    TIMEFRAME_SECONDS = {
        Timeframe.ONE_MIN: 60,
        Timeframe.FIVE_MIN: 300,
        Timeframe.FIFTEEN_MIN: 900,
        Timeframe.THIRTY_MIN: 1800,
        Timeframe.ONE_HOUR: 3600,
        Timeframe.FOUR_HOUR: 14400,
        Timeframe.ONE_DAY: 86400,
    }

    # Market timezone (configurable)
    DEFAULT_TIMEZONE = pytz.timezone("America/New_York")

    def __init__(
        self,
        accuracy_ms: int = 500,
        schedule_advance_ms: int = 100,
        timezone: str = "America/New_York",
    ):
        """Initialize bar close detector.

        Args:
            accuracy_ms: Maximum deviation from actual close in milliseconds
            schedule_advance_ms: How early to schedule checks in milliseconds
            timezone: Market timezone for scheduling
        """
        self.accuracy_ms = accuracy_ms
        self.schedule_advance_ms = schedule_advance_ms
        self.timezone = pytz.timezone(timezone)

        # Scheduler for precise timing
        self.scheduler = AsyncIOScheduler(timezone=self.timezone)

        # Track monitored symbols and timeframes
        self.monitored: Dict[str, Set[Timeframe]] = defaultdict(set)

        # Callbacks for bar close events
        self.callbacks: List[Callable[[BarCloseEvent], None]] = []

        # Cache of last bar data per symbol/timeframe
        self.last_bars: Dict[Tuple[str, Timeframe], BarData] = {}

        # Track scheduled jobs
        self.scheduled_jobs: Dict[Tuple[str, Timeframe], str] = {}

        # Performance metrics
        self.timing_errors: List[float] = []  # Track timing accuracy

        logger.info(
            f"BarCloseDetector initialized with {accuracy_ms}ms accuracy, "
            f"timezone: {timezone}"
        )

    async def start(self) -> None:
        """Start the bar close detection system."""
        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("BarCloseDetector started")

    async def stop(self) -> None:
        """Stop the bar close detection system."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            logger.info("BarCloseDetector stopped")

    def add_callback(self, callback: Callable[[BarCloseEvent], None]) -> None:
        """Register a callback for bar close events.

        Args:
            callback: Function to call on bar close
        """
        self.callbacks.append(callback)
        logger.debug(f"Added bar close callback: {callback.__name__}")

    def remove_callback(self, callback: Callable[[BarCloseEvent], None]) -> bool:
        """Remove a registered callback.

        Args:
            callback: Callback to remove

        Returns:
            True if removed, False if not found
        """
        if callback in self.callbacks:
            self.callbacks.remove(callback)
            logger.debug(f"Removed bar close callback: {callback.__name__}")
            return True
        return False

    async def monitor_timeframe(self, symbol: str, timeframe: Timeframe) -> None:
        """Start monitoring a specific symbol/timeframe combination.

        Args:
            symbol: Trading symbol to monitor
            timeframe: Timeframe to monitor
        """
        if timeframe in self.monitored[symbol]:
            logger.warning(f"Already monitoring {symbol} {timeframe.value}")
            return

        self.monitored[symbol].add(timeframe)

        # Schedule the next bar close check
        self._schedule_next_close(symbol, timeframe)

        logger.info(f"Started monitoring {symbol} {timeframe.value} bar closes")

    async def stop_monitoring(
        self, symbol: str, timeframe: Optional[Timeframe] = None
    ) -> None:
        """Stop monitoring a symbol/timeframe.

        Args:
            symbol: Symbol to stop monitoring
            timeframe: Specific timeframe or None for all timeframes
        """
        if timeframe:
            # Stop specific timeframe
            if timeframe in self.monitored[symbol]:
                self.monitored[symbol].discard(timeframe)
                self._cancel_scheduled_job(symbol, timeframe)
                logger.info(f"Stopped monitoring {symbol} {timeframe.value}")
        else:
            # Stop all timeframes for symbol
            for tf in list(self.monitored[symbol]):
                self._cancel_scheduled_job(symbol, tf)
            del self.monitored[symbol]
            logger.info(f"Stopped monitoring all timeframes for {symbol}")

    def update_bar_data(self, symbol: str, timeframe: Timeframe, bar: BarData) -> None:
        """Update the latest bar data for a symbol/timeframe.

        Args:
            symbol: Trading symbol
            timeframe: Bar timeframe
            bar: Latest bar data
        """
        self.last_bars[(symbol, timeframe)] = bar

    def _schedule_next_close(self, symbol: str, timeframe: Timeframe) -> None:
        """Schedule the next bar close check.

        Args:
            symbol: Symbol to schedule
            timeframe: Timeframe to schedule
        """
        # Cancel existing job if any
        self._cancel_scheduled_job(symbol, timeframe)

        # Calculate next bar close time
        next_close = self._calculate_next_close(timeframe)

        # Schedule slightly before the actual close for processing time
        schedule_time = next_close - timedelta(milliseconds=self.schedule_advance_ms)

        # Create job
        job = self.scheduler.add_job(
            self._check_bar_close,
            DateTrigger(run_date=schedule_time),
            args=[symbol, timeframe, next_close],
            id=f"{symbol}_{timeframe.value}_{next_close.timestamp()}",
            misfire_grace_time=1,  # Allow 1 second grace period
        )

        self.scheduled_jobs[(symbol, timeframe)] = job.id

        logger.debug(
            f"Scheduled {symbol} {timeframe.value} bar close check at {schedule_time}"
        )

    async def _check_bar_close(
        self, symbol: str, timeframe: Timeframe, expected_close: datetime
    ) -> None:
        """Check for bar close and emit event.

        Args:
            symbol: Symbol being checked
            timeframe: Timeframe being checked
            expected_close: Expected bar close time
        """
        try:
            # Measure timing accuracy
            actual_time = datetime.now(UTC)
            timing_error_ms = abs((actual_time - expected_close).total_seconds() * 1000)
            self.timing_errors.append(timing_error_ms)

            # Keep only last 100 timing measurements
            if len(self.timing_errors) > 100:
                self.timing_errors = self.timing_errors[-100:]

            # Log if timing error exceeds accuracy threshold
            if timing_error_ms > self.accuracy_ms:
                logger.warning(
                    f"Bar close timing error: {timing_error_ms:.1f}ms for "
                    f"{symbol} {timeframe.value} (threshold: {self.accuracy_ms}ms)"
                )

            # Get the last bar data
            bar_data = self.last_bars.get((symbol, timeframe))

            if bar_data:
                # Calculate next close time
                next_close = self._calculate_next_close(timeframe, expected_close)

                # Create and emit bar close event
                event = BarCloseEvent(
                    symbol=symbol,
                    timeframe=timeframe,
                    close_time=expected_close,
                    bar_data=bar_data,
                    next_close_time=next_close,
                )

                await self._emit_event(event)
            else:
                logger.warning(f"No bar data available for {symbol} {timeframe.value}")

            # Schedule next bar close check if still monitoring
            if timeframe in self.monitored.get(symbol, set()):
                self._schedule_next_close(symbol, timeframe)

        except Exception as e:
            logger.error(
                f"Error in bar close check for {symbol} {timeframe.value}: {e}"
            )
            # Reschedule even on error
            if timeframe in self.monitored.get(symbol, set()):
                self._schedule_next_close(symbol, timeframe)

    async def _emit_event(self, event: BarCloseEvent) -> None:
        """Emit bar close event to all callbacks.

        Args:
            event: Bar close event to emit
        """
        for callback in self.callbacks:
            try:
                # Support both sync and async callbacks
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error(f"Error in bar close callback {callback.__name__}: {e}")

    def _calculate_next_close(
        self, timeframe: Timeframe, from_time: Optional[datetime] = None
    ) -> datetime:
        """Calculate the next bar close time.

        Args:
            timeframe: Timeframe to calculate for
            from_time: Reference time (default: now)

        Returns:
            Next bar close time
        """
        if from_time is None:
            from_time = datetime.now(self.timezone)
        elif from_time.tzinfo is None:
            from_time = self.timezone.localize(from_time)
        else:
            from_time = from_time.astimezone(self.timezone)

        seconds = self.TIMEFRAME_SECONDS[timeframe]

        # Calculate the next boundary
        if timeframe == Timeframe.ONE_DAY:
            # Daily bars close at market close (4 PM ET)
            next_close = from_time.replace(hour=16, minute=0, second=0, microsecond=0)
            if from_time >= next_close:
                next_close += timedelta(days=1)
        else:
            # For intraday bars, align to the timeframe boundary
            epoch = datetime(1970, 1, 1, tzinfo=pytz.UTC)
            seconds_since_epoch = (from_time - epoch).total_seconds()
            next_boundary = ((seconds_since_epoch // seconds) + 1) * seconds
            next_close = epoch + timedelta(seconds=next_boundary)
            next_close = next_close.astimezone(self.timezone)

        return next_close

    def _cancel_scheduled_job(self, symbol: str, timeframe: Timeframe) -> None:
        """Cancel a scheduled job.

        Args:
            symbol: Symbol to cancel
            timeframe: Timeframe to cancel
        """
        job_id = self.scheduled_jobs.get((symbol, timeframe))
        if job_id:
            try:
                self.scheduler.remove_job(job_id)
                del self.scheduled_jobs[(symbol, timeframe)]
                logger.debug(f"Cancelled scheduled job for {symbol} {timeframe.value}")
            except Exception as e:
                logger.warning(f"Failed to cancel job {job_id}: {e}")

    def get_timing_stats(self) -> Dict[str, float]:
        """Get timing accuracy statistics.

        Returns:
            Dictionary with timing statistics
        """
        if not self.timing_errors:
            return {
                "avg_error_ms": 0.0,
                "max_error_ms": 0.0,
                "min_error_ms": 0.0,
                "samples": 0,
            }

        return {
            "avg_error_ms": sum(self.timing_errors) / len(self.timing_errors),
            "max_error_ms": max(self.timing_errors),
            "min_error_ms": min(self.timing_errors),
            "samples": len(self.timing_errors),
            "accuracy_threshold_ms": self.accuracy_ms,
        }

    def is_monitoring(self, symbol: str, timeframe: Optional[Timeframe] = None) -> bool:
        """Check if monitoring a symbol/timeframe.

        Args:
            symbol: Symbol to check
            timeframe: Specific timeframe or None for any

        Returns:
            True if monitoring
        """
        if timeframe:
            return timeframe in self.monitored.get(symbol, set())
        return symbol in self.monitored and len(self.monitored[symbol]) > 0

    def get_monitored(self) -> Dict[str, List[str]]:
        """Get all monitored symbol/timeframe combinations.

        Returns:
            Dictionary mapping symbols to list of timeframe strings
        """
        return {
            symbol: [tf.value for tf in timeframes]
            for symbol, timeframes in self.monitored.items()
        }
