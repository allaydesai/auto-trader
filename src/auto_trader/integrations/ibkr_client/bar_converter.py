"""Bar data conversion utilities for IBKR market data."""

from datetime import UTC
from decimal import Decimal
from typing import Any

from ib_async import RealTimeBar
from loguru import logger

from auto_trader.models.market_data import BarData, BarSizeType


class BarConverter:
    """
    Handles conversion of IBKR bar data to BarData model.
    
    Provides utilities for converting real-time bars from IB format
    to standardized BarData models with proper timestamp normalization.
    """
    
    def __init__(self) -> None:
        """Initialize bar converter."""
        self._data_quality_errors = 0
    
    def convert_ib_bar_to_bar_data(
        self, 
        bars: RealTimeBar, 
        symbol: str, 
        bar_size: BarSizeType
    ) -> BarData:
        """
        Convert IB real-time bar to BarData model.
        
        Args:
            bars: Real-time bar data from IB
            symbol: Trading symbol
            bar_size: Bar timeframe
            
        Returns:
            Converted BarData instance
        """
        latest_bar = bars[-1] if isinstance(bars, list) else bars
        
        # Process timestamp to UTC
        timestamp = self._normalize_timestamp(latest_bar.time)
        
        return BarData(
            symbol=symbol,
            timestamp=timestamp,
            open_price=Decimal(str(latest_bar.open_)),
            high_price=Decimal(str(latest_bar.high)),
            low_price=Decimal(str(latest_bar.low)),
            close_price=Decimal(str(latest_bar.close)),
            volume=int(latest_bar.volume),
            bar_size=bar_size
        )
    
    def _normalize_timestamp(self, timestamp: Any) -> Any:
        """
        Normalize timestamp to UTC.
        
        Args:
            timestamp: Timestamp from IB
            
        Returns:
            UTC timestamp
        """
        if timestamp.tzinfo is None:
            # If no timezone info, assume UTC
            return timestamp.replace(tzinfo=UTC)
        elif timestamp.tzinfo != UTC:
            # Convert to UTC if different timezone
            return timestamp.astimezone(UTC)
        return timestamp
    
    def handle_bar_processing_error(
        self, 
        error: Exception, 
        bars: RealTimeBar, 
        symbol: str, 
        bar_size: BarSizeType
    ) -> None:
        """
        Handle errors in bar processing.
        
        Args:
            error: Exception that occurred
            bars: Bar data that caused error
            symbol: Trading symbol
            bar_size: Bar timeframe
        """
        self._data_quality_errors += 1
        error_details = f"Error processing bar update - {type(error).__name__}: {str(error)}"
        
        if bars:
            error_details += f" | bars_type: {type(bars).__name__}"
            error_details += f" | bars_data: {str(bars)[:200]}..."  # Limit to first 200 chars
        else:
            error_details += " | bars_data: None"
        
        logger.error(
            error_details,
            symbol=symbol,
            bar_size=bar_size
        )
    
    def get_stats(self) -> dict:
        """Get bar converter statistics."""
        return {
            "data_quality_errors": self._data_quality_errors
        }