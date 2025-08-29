"""Historical market data storage and management for execution framework."""

import asyncio
from typing import Dict, List
from collections import defaultdict

from loguru import logger

from auto_trader.models.market_data import BarData
from auto_trader.models.enums import Timeframe


class HistoricalDataManager:
    """Manages historical bar data storage and retrieval.
    
    Provides thread-safe storage and retrieval of historical market data
    with automatic size management and multi-timeframe support.
    """
    
    def __init__(
        self,
        max_historical_bars: int = 1000,
        min_bars_for_execution: int = 20,
    ):
        """Initialize historical data manager.
        
        Args:
            max_historical_bars: Maximum bars to keep per symbol/timeframe
            min_bars_for_execution: Minimum bars needed for function evaluation
        """
        self.max_historical_bars = max_historical_bars
        self.min_bars_for_execution = min_bars_for_execution
        
        # Track monitored symbols and their historical data
        self.historical_data: Dict[str, Dict[Timeframe, List[BarData]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self.historical_data_lock = asyncio.Lock()
        
        logger.info(
            "HistoricalDataManager initialized",
            max_bars=max_historical_bars,
            min_bars=min_bars_for_execution,
        )
    
    async def update_data(self, bar: BarData, timeframe: Timeframe) -> None:
        """Update historical data storage with new bar.
        
        Args:
            bar: New bar to add
            timeframe: Timeframe of the bar
        """
        async with self.historical_data_lock:
            symbol = bar.symbol
            
            # Add the bar
            bars = self.historical_data[symbol][timeframe]
            bars.append(bar)
            
            # Maintain size limit
            if len(bars) > self.max_historical_bars:
                bars[:] = bars[-self.max_historical_bars:]
                
                logger.debug(
                    f"Trimmed historical data for {symbol} {timeframe.value}",
                    kept_bars=len(bars),
                )
    
    async def store_one_minute_for_all_timeframes(
        self,
        bar: BarData,
        monitored_timeframes: Dict[str, List[str]],
    ) -> None:
        """Store 1-minute bar for all monitored timeframes of the symbol.
        
        This ensures that longer timeframes have sufficient 1-minute data for aggregation.
        
        Args:
            bar: 1-minute bar to store
            monitored_timeframes: Dictionary mapping symbols to timeframe strings
        """
        async with self.historical_data_lock:
            symbol = bar.symbol
            
            # Get monitored timeframes for this symbol
            symbol_timeframes = monitored_timeframes.get(symbol, [])
            
            # Map from timeframe mapping
            timeframe_mapping = {
                "1min": Timeframe.ONE_MIN,
                "5min": Timeframe.FIVE_MIN,
                "15min": Timeframe.FIFTEEN_MIN,
                "30min": Timeframe.THIRTY_MIN,
                "1hour": Timeframe.ONE_HOUR,
                "4hour": Timeframe.FOUR_HOUR,
                "1day": Timeframe.ONE_DAY,
            }
            
            for timeframe_str in symbol_timeframes:
                # Convert string back to enum
                if timeframe_str in timeframe_mapping:
                    tf_enum = timeframe_mapping[timeframe_str]
                    
                    # Store the 1-minute bar for this timeframe
                    bars = self.historical_data[symbol][tf_enum]
                    bars.append(bar)
                    
                    # Maintain size limit
                    if len(bars) > self.max_historical_bars:
                        bars.pop(0)
    
    async def get_historical_bars(self, symbol: str, timeframe: Timeframe) -> List[BarData]:
        """Get historical bars for a symbol/timeframe.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            
        Returns:
            List of historical bars (most recent last)
        """
        async with self.historical_data_lock:
            return self.historical_data[symbol][timeframe].copy()
    
    async def has_sufficient_data(self, symbol: str, timeframe: Timeframe) -> bool:
        """Check if symbol/timeframe has sufficient data for execution.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe
            
        Returns:
            True if sufficient data available
        """
        async with self.historical_data_lock:
            bars = self.historical_data[symbol][timeframe]
            return len(bars) >= self.min_bars_for_execution
    
    async def initialize_storage(self, symbol: str, timeframe: Timeframe) -> None:
        """Initialize storage for a symbol/timeframe combination.
        
        Args:
            symbol: Trading symbol
            timeframe: Timeframe to initialize
        """
        async with self.historical_data_lock:
            # This will create the nested structure if it doesn't exist
            _ = self.historical_data[symbol][timeframe]
        
        logger.debug(f"Initialized storage for {symbol} {timeframe.value}")
    
    async def cleanup_storage(self, symbol: str, timeframe: Timeframe = None) -> None:
        """Clean up historical data storage.
        
        Args:
            symbol: Symbol to clean up
            timeframe: Specific timeframe or None for all timeframes
        """
        async with self.historical_data_lock:
            if timeframe and symbol in self.historical_data:
                if timeframe in self.historical_data[symbol]:
                    del self.historical_data[symbol][timeframe]
                    
                # Remove symbol if no timeframes left
                if not self.historical_data[symbol]:
                    del self.historical_data[symbol]
            elif symbol in self.historical_data:
                del self.historical_data[symbol]
        
        logger.debug(f"Cleaned up storage for {symbol}")
    
    async def get_stats(self) -> Dict[str, int]:
        """Get historical data statistics.
        
        Returns:
            Dictionary with storage statistics
        """
        async with self.historical_data_lock:
            total_bars = sum(
                len(timeframe_bars)
                for symbol_data in self.historical_data.values()
                for timeframe_bars in symbol_data.values()
            )
            
            total_combinations = sum(
                len(timeframes) for timeframes in self.historical_data.values()
            )
        
        return {
            "monitored_symbols": len(self.historical_data),
            "monitored_combinations": total_combinations,
            "total_historical_bars": total_bars,
            "max_bars_per_combination": self.max_historical_bars,
            "min_bars_for_execution": self.min_bars_for_execution,
        }