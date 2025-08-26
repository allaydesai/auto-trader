"""Historical market data fetching for startup context and analysis."""

from datetime import datetime, timedelta, UTC
from decimal import Decimal
from typing import List, Dict, Optional, Tuple, Any

from ib_async import IB, Stock, Contract, BarData as IBBarData
from loguru import logger

from auto_trader.models.market_data import (
    BarData, BarSizeType, BAR_SIZE_MAPPING,
    MarketDataError
)
from auto_trader.models.trade_plan import TradePlan


class HistoricalDataFetcher:
    """
    Fetches historical market data for startup context establishment.
    
    Provides historical bar fetching, gap detection, and position
    calculation relative to trade plan levels.
    """
    
    def __init__(self, ib_client: IB):
        """
        Initialize historical data fetcher.
        
        Args:
            ib_client: Connected IB client instance
        """
        self._ib = ib_client
        self._contracts: Dict[str, Contract] = {}
        
        # Statistics
        self._stats = {
            "bars_fetched": 0,
            "fetch_errors": 0,
            "gaps_detected": 0
        }
        
        logger.info("HistoricalDataFetcher initialized")
    
    async def fetch_startup_context(
        self,
        symbols: List[str],
        bar_size: BarSizeType = "5min",
        duration: str = "1 D"
    ) -> Dict[str, List[BarData]]:
        """
        Fetch historical context for system startup.
        
        Args:
            symbols: List of trading symbols
            bar_size: Bar timeframe
            duration: Historical duration (IB format: "1 D", "1 W", etc.)
            
        Returns:
            Dictionary mapping symbols to historical bars
        """
        context_data = {}
        
        for symbol in symbols:
            try:
                bars = await self.fetch_historical_bars(
                    symbol, bar_size, duration
                )
                context_data[symbol] = bars
                
                logger.info(
                    "Startup context fetched",
                    symbol=symbol,
                    bar_count=len(bars),
                    oldest_bar=bars[0].timestamp.isoformat() if bars else None,
                    latest_bar=bars[-1].timestamp.isoformat() if bars else None
                )
                
            except Exception as e:
                self._stats["fetch_errors"] += 1
                logger.error(
                    "Failed to fetch startup context",
                    symbol=symbol,
                    error=str(e)
                )
                context_data[symbol] = []
        
        return context_data
    
    async def fetch_historical_bars(
        self,
        symbol: str,
        bar_size: BarSizeType,
        duration: str = "1 D",
        end_datetime: Optional[datetime] = None
    ) -> List[BarData]:
        """
        Fetch historical bars for a symbol.
        
        Args:
            symbol: Trading symbol
            bar_size: Bar timeframe
            duration: Historical duration (e.g., "1 D", "2 W", "1 M")
            end_datetime: End time for historical data (defaults to now)
            
        Returns:
            List of historical bars in chronological order
            
        Raises:
            MarketDataError: If fetch fails
        """
        try:
            # Get or create contract
            if symbol not in self._contracts:
                contract = Stock(symbol, "SMART", "USD")
                await self._ib.qualifyContractsAsync(contract)
                self._contracts[symbol] = contract
            
            # Convert bar size to IB format
            ib_bar_size = BAR_SIZE_MAPPING.get(bar_size)
            if not ib_bar_size:
                raise MarketDataError(f"Unsupported bar size: {bar_size}")
            
            # Fetch historical data
            ib_bars = await self._ib.reqHistoricalDataAsync(
                self._contracts[symbol],
                endDateTime=end_datetime or "",
                durationStr=duration,
                barSizeSetting=ib_bar_size,
                whatToShow="TRADES",
                useRTH=True,  # Regular trading hours only
                formatDate=2,  # UTC timestamps
                keepUpToDate=False
            )
            
            if not ib_bars:
                logger.warning(
                    "No historical data returned",
                    symbol=symbol,
                    bar_size=bar_size,
                    duration=duration
                )
                return []
            
            # Convert IB bars to our format
            bars = []
            for ib_bar in ib_bars:
                bar = BarData(
                    symbol=symbol,
                    timestamp=ib_bar.date if isinstance(ib_bar.date, datetime) 
                              else datetime.fromisoformat(str(ib_bar.date)).replace(tzinfo=UTC),
                    open_price=Decimal(str(ib_bar.open)),
                    high_price=Decimal(str(ib_bar.high)),
                    low_price=Decimal(str(ib_bar.low)),
                    close_price=Decimal(str(ib_bar.close)),
                    volume=int(ib_bar.volume),
                    bar_size=bar_size
                )
                bars.append(bar)
            
            self._stats["bars_fetched"] += len(bars)
            
            logger.debug(
                "Historical bars fetched",
                symbol=symbol,
                bar_size=bar_size,
                bar_count=len(bars)
            )
            
            return bars
            
        except Exception as e:
            self._stats["fetch_errors"] += 1
            raise MarketDataError(
                f"Failed to fetch historical data for {symbol}: {str(e)}"
            )
    
    def detect_data_gaps(
        self,
        bars: List[BarData],
        bar_size: BarSizeType
    ) -> List[Tuple[datetime, datetime]]:
        """
        Detect gaps in historical bar sequence.
        
        Args:
            bars: List of bars to check
            bar_size: Expected bar timeframe
            
        Returns:
            List of gap tuples (gap_start, gap_end)
        """
        if len(bars) < 2:
            return []
        
        gaps = []
        
        # Determine expected time delta based on bar size
        expected_deltas = {
            "1min": timedelta(minutes=1),
            "5min": timedelta(minutes=5),
            "15min": timedelta(minutes=15),
            "30min": timedelta(minutes=30),
            "1hour": timedelta(hours=1),
            "4hour": timedelta(hours=4),
            "1day": timedelta(days=1)
        }
        
        expected_delta = expected_deltas.get(bar_size)
        if not expected_delta:
            return []
        
        # Allow for market hours gaps (weekends, overnight)
        # Gap is significant if > 2x expected delta during market hours
        max_gap = expected_delta * 2
        
        for i in range(1, len(bars)):
            time_diff = bars[i].timestamp - bars[i-1].timestamp
            
            # Check for significant gaps during market hours
            if self._is_market_hours_gap(bars[i-1].timestamp, bars[i].timestamp):
                if time_diff > max_gap:
                    gaps.append((bars[i-1].timestamp, bars[i].timestamp))
                    self._stats["gaps_detected"] += 1
        
        if gaps:
            logger.warning(
                "Data gaps detected",
                gap_count=len(gaps),
                symbol=bars[0].symbol if bars else None
            )
        
        return gaps
    
    def calculate_position_vs_levels(
        self,
        bars: List[BarData],
        plan: TradePlan
    ) -> Dict[str, Any]:
        """
        Calculate current market position relative to trade plan levels.
        
        Args:
            bars: Historical bars for analysis
            plan: Trade plan with entry/stop/target levels
            
        Returns:
            Dictionary with position analysis
        """
        if not bars:
            return {
                "current_price": None,
                "vs_entry": None,
                "vs_stop": None,
                "vs_target": None,
                "position_status": "no_data"
            }
        
        current_price = bars[-1].close_price
        
        # Calculate distances to key levels
        vs_entry = ((current_price - plan.entry_level) / plan.entry_level * 100)
        vs_stop = ((current_price - plan.stop_loss) / plan.stop_loss * 100)
        vs_target = ((plan.take_profit - current_price) / current_price * 100)
        
        # Determine position status (infer long/short from stop loss position)
        is_long = plan.stop_loss < plan.entry_level
        
        if is_long:
            if current_price < plan.stop_loss:
                position_status = "below_stop"
            elif current_price < plan.entry_level:
                position_status = "below_entry"
            elif current_price < plan.take_profit:
                position_status = "between_entry_target"
            else:
                position_status = "above_target"
        else:  # short
            if current_price > plan.stop_loss:
                position_status = "above_stop"
            elif current_price > plan.entry_level:
                position_status = "above_entry"
            elif current_price > plan.take_profit:
                position_status = "between_entry_target"
            else:
                position_status = "below_target"
        
        result = {
            "current_price": float(current_price),
            "vs_entry": round(float(vs_entry), 2),
            "vs_stop": round(float(vs_stop), 2),
            "vs_target": round(float(vs_target), 2),
            "position_status": position_status,
            "entry_level": float(plan.entry_level),
            "stop_loss": float(plan.stop_loss),
            "take_profit": float(plan.take_profit)
        }
        
        logger.debug(
            "Position calculated vs plan levels",
            plan_id=plan.plan_id,
            symbol=plan.symbol,
            position_status=position_status,
            current_price=float(current_price)
        )
        
        return result
    
    def _is_market_hours_gap(
        self,
        start: datetime,
        end: datetime
    ) -> bool:
        """
        Check if time period is during market hours.
        
        Args:
            start: Start timestamp
            end: End timestamp
            
        Returns:
            True if period is during market hours
        """
        # Simple check for weekdays
        # More sophisticated logic would check actual market hours
        if start.weekday() >= 5 or end.weekday() >= 5:  # Weekend
            return False
        
        # Check if times are during market hours (9:30 AM - 4:00 PM ET)
        # This is simplified - production would need proper timezone handling
        market_open = 9.5  # 9:30 AM
        market_close = 16  # 4:00 PM
        
        start_hour = start.hour + start.minute / 60
        end_hour = end.hour + end.minute / 60
        
        return (market_open <= start_hour <= market_close and
                market_open <= end_hour <= market_close)
    
    def get_stats(self) -> Dict[str, int]:
        """Get fetcher statistics."""
        return self._stats.copy()
    
    async def fetch_bars_for_plans(
        self,
        plans: List[TradePlan],
        bar_size: BarSizeType = "5min",
        duration: str = "1 D"
    ) -> Dict[str, Dict[str, Any]]:
        """
        Fetch historical data and calculate positions for trade plans.
        
        Args:
            plans: List of trade plans
            bar_size: Bar timeframe
            duration: Historical duration
            
        Returns:
            Dictionary with symbol -> position analysis
        """
        results = {}
        
        # Get unique symbols
        symbols = list(set(plan.symbol for plan in plans))
        
        # Fetch historical data
        historical_data = await self.fetch_startup_context(
            symbols, bar_size, duration
        )
        
        # Calculate positions for each plan
        for plan in plans:
            bars = historical_data.get(plan.symbol, [])
            position = self.calculate_position_vs_levels(bars, plan)
            
            if plan.symbol not in results:
                results[plan.symbol] = {
                    "bars": bars,
                    "positions": {}
                }
            
            results[plan.symbol]["positions"][plan.plan_id] = position
        
        return results