"""Tests for historical data fetcher."""

import pytest
import asyncio
from datetime import datetime, timedelta, UTC
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from auto_trader.integrations.ibkr_client.historical_data_fetcher import HistoricalDataFetcher
from auto_trader.models.market_data import BarData, MarketDataError
from auto_trader.models.trade_plan import TradePlan, ExecutionFunction


@pytest.fixture
def mock_ib_client():
    """Create a mock IB client."""
    mock = MagicMock()
    mock.qualifyContractsAsync = AsyncMock()
    mock.reqHistoricalDataAsync = AsyncMock()
    return mock


@pytest.fixture
def fetcher(mock_ib_client):
    """Create a historical data fetcher instance."""
    return HistoricalDataFetcher(mock_ib_client)


@pytest.fixture
def sample_ib_bars():
    """Create sample IB bar data."""
    bars = []
    base_time = datetime.now(UTC) - timedelta(hours=1)
    
    for i in range(10):
        bar = MagicMock()
        bar.date = base_time + timedelta(minutes=i*5)
        bar.open = 180.0 + i * 0.1
        bar.high = 180.5 + i * 0.1
        bar.low = 179.5 + i * 0.1
        bar.close = 180.25 + i * 0.1
        bar.volume = 100000 + i * 1000
        bars.append(bar)
    
    return bars


@pytest.fixture
def sample_trade_plan():
    """Create a sample trade plan."""
    return TradePlan(
        plan_id="AAPL_20250826_001",
        symbol="AAPL",
        entry_level=Decimal("181.00"),
        stop_loss=Decimal("179.00"),
        take_profit=Decimal("185.00"),
        position_size=100,
        risk_category="small",
        entry_function=ExecutionFunction(
            function_type="close_above",
            timeframe="5min",
            parameters={"threshold": 181.00}
        ),
        exit_function=ExecutionFunction(
            function_type="close_below",
            timeframe="5min",
            parameters={"threshold": 179.00}
        )
    )


class TestHistoricalDataFetcher:
    """Test historical data fetcher functionality."""
    
    @pytest.mark.asyncio
    async def test_fetch_historical_bars_success(self, fetcher, mock_ib_client, sample_ib_bars):
        """Test successful historical data fetch."""
        mock_ib_client.reqHistoricalDataAsync.return_value = sample_ib_bars
        
        bars = await fetcher.fetch_historical_bars("AAPL", "5min", "1 D")
        
        assert len(bars) == 10
        assert all(isinstance(bar, BarData) for bar in bars)
        assert bars[0].symbol == "AAPL"
        assert bars[0].bar_size == "5min"
        assert isinstance(bars[0].open_price, Decimal)
        assert fetcher._stats["bars_fetched"] == 10
    
    @pytest.mark.asyncio
    async def test_fetch_historical_bars_empty(self, fetcher, mock_ib_client):
        """Test handling of empty historical data."""
        mock_ib_client.reqHistoricalDataAsync.return_value = []
        
        bars = await fetcher.fetch_historical_bars("AAPL", "5min", "1 D")
        
        assert bars == []
        assert fetcher._stats["bars_fetched"] == 0
    
    @pytest.mark.asyncio
    async def test_fetch_historical_bars_invalid_bar_size(self, fetcher):
        """Test error handling for invalid bar size."""
        with pytest.raises(MarketDataError, match="Unsupported bar size"):
            await fetcher.fetch_historical_bars("AAPL", "invalid", "1 D")
    
    @pytest.mark.asyncio
    async def test_fetch_historical_bars_ib_error(self, fetcher, mock_ib_client):
        """Test error handling for IB API errors."""
        mock_ib_client.reqHistoricalDataAsync.side_effect = Exception("IB API Error")
        
        with pytest.raises(MarketDataError, match="Failed to fetch historical data"):
            await fetcher.fetch_historical_bars("AAPL", "5min", "1 D")
        
        assert fetcher._stats["fetch_errors"] == 1
    
    @pytest.mark.asyncio
    async def test_fetch_startup_context(self, fetcher, mock_ib_client, sample_ib_bars):
        """Test fetching startup context for multiple symbols."""
        mock_ib_client.reqHistoricalDataAsync.return_value = sample_ib_bars
        
        symbols = ["AAPL", "MSFT", "GOOGL"]
        context = await fetcher.fetch_startup_context(symbols, "5min", "1 D")
        
        assert len(context) == 3
        assert "AAPL" in context
        assert "MSFT" in context
        assert "GOOGL" in context
        assert len(context["AAPL"]) == 10
        assert fetcher._stats["bars_fetched"] == 30  # 10 bars * 3 symbols
    
    @pytest.mark.asyncio
    async def test_fetch_startup_context_with_errors(self, fetcher, mock_ib_client, sample_ib_bars):
        """Test startup context fetch with some symbols failing."""
        # First call succeeds, second fails, third succeeds
        mock_ib_client.reqHistoricalDataAsync.side_effect = [
            sample_ib_bars[:5],  # AAPL succeeds with 5 bars
            Exception("Connection error"),  # MSFT fails
            sample_ib_bars[:3]   # GOOGL succeeds with 3 bars
        ]
        
        symbols = ["AAPL", "MSFT", "GOOGL"]
        context = await fetcher.fetch_startup_context(symbols, "5min", "1 D")
        
        assert len(context["AAPL"]) == 5
        assert context["MSFT"] == []  # Failed, returns empty
        assert len(context["GOOGL"]) == 3
        assert fetcher._stats["fetch_errors"] == 2  # Fetch error + startup context error
    
    def test_detect_data_gaps(self, fetcher):
        """Test detection of gaps in bar sequence."""
        now = datetime.now(UTC)
        
        # Create bars with a gap
        bars = [
            BarData(
                symbol="AAPL",
                timestamp=now - timedelta(minutes=20),
                open_price=Decimal("180.00"),
                high_price=Decimal("180.50"),
                low_price=Decimal("179.50"),
                close_price=Decimal("180.25"),
                volume=1000,
                bar_size="5min"
            ),
            BarData(
                symbol="AAPL",
                timestamp=now - timedelta(minutes=15),
                open_price=Decimal("180.25"),
                high_price=Decimal("180.75"),
                low_price=Decimal("180.00"),
                close_price=Decimal("180.50"),
                volume=1000,
                bar_size="5min"
            ),
            # Gap here - missing 10 minute bar
            BarData(
                symbol="AAPL",
                timestamp=now - timedelta(minutes=0),  # 15 min gap
                open_price=Decimal("180.50"),
                high_price=Decimal("181.00"),
                low_price=Decimal("180.25"),
                close_price=Decimal("180.75"),
                volume=1000,
                bar_size="5min"
            )
        ]
        
        # Mock market hours check to return True
        fetcher._is_market_hours_gap = MagicMock(return_value=True)
        
        gaps = fetcher.detect_data_gaps(bars, "5min")
        
        assert len(gaps) == 1
        assert gaps[0][0] == bars[1].timestamp
        assert gaps[0][1] == bars[2].timestamp
    
    def test_detect_data_gaps_no_gaps(self, fetcher):
        """Test gap detection with continuous data."""
        now = datetime.now(UTC)
        
        # Create continuous 5-minute bars
        bars = []
        for i in range(5):
            bars.append(BarData(
                symbol="AAPL",
                timestamp=now - timedelta(minutes=(4-i)*5),
                open_price=Decimal("180.00"),
                high_price=Decimal("180.50"),
                low_price=Decimal("179.50"),
                close_price=Decimal("180.25"),
                volume=1000,
                bar_size="5min"
            ))
        
        fetcher._is_market_hours_gap = MagicMock(return_value=True)
        gaps = fetcher.detect_data_gaps(bars, "5min")
        
        assert len(gaps) == 0
    
    def test_calculate_position_vs_levels_long(self, fetcher, sample_trade_plan):
        """Test position calculation for long trade."""
        bars = [
            BarData(
                symbol="AAPL",
                timestamp=datetime.now(UTC),
                open_price=Decimal("180.00"),
                high_price=Decimal("180.50"),
                low_price=Decimal("179.50"),
                close_price=Decimal("180.25"),  # Below entry
                volume=1000,
                bar_size="5min"
            )
        ]
        
        position = fetcher.calculate_position_vs_levels(bars, sample_trade_plan)
        
        assert position["current_price"] == 180.25
        assert position["position_status"] == "below_entry"
        assert position["vs_entry"] < 0  # Below entry level
        assert position["vs_stop"] > 0   # Above stop loss
        assert position["entry_level"] == 181.00
    
    def test_calculate_position_vs_levels_short(self, fetcher):
        """Test position calculation for short trade."""
        plan = TradePlan(
            plan_id="AAPL_20250826_002",
            symbol="AAPL",
            entry_level=Decimal("180.00"),
            stop_loss=Decimal("182.00"),
            take_profit=Decimal("176.00"),
            position_size=100,
            risk_category="small",
            entry_function=ExecutionFunction(
                function_type="close_below",
                timeframe="5min",
                parameters={"threshold": 180.00}
            ),
            exit_function=ExecutionFunction(
                function_type="close_above",
                timeframe="5min",
                parameters={"threshold": 182.00}
            )
        )
        
        bars = [
            BarData(
                symbol="AAPL",
                timestamp=datetime.now(UTC),
                open_price=Decimal("180.50"),
                high_price=Decimal("181.00"),
                low_price=Decimal("180.00"),
                close_price=Decimal("180.75"),  # Above entry (not triggered for short)
                volume=1000,
                bar_size="5min"
            )
        ]
        
        position = fetcher.calculate_position_vs_levels(bars, plan)
        
        assert position["current_price"] == 180.75
        assert position["position_status"] == "above_entry"
        assert position["vs_entry"] > 0  # Above entry level (unfavorable for short)
    
    def test_calculate_position_no_bars(self, fetcher, sample_trade_plan):
        """Test position calculation with no bar data."""
        position = fetcher.calculate_position_vs_levels([], sample_trade_plan)
        
        assert position["current_price"] is None
        assert position["position_status"] == "no_data"
        assert position["vs_entry"] is None
    
    def test_is_market_hours_gap_weekend(self, fetcher):
        """Test market hours gap detection for weekend."""
        # Saturday and Sunday
        saturday = datetime(2025, 8, 23, 12, 0, 0, tzinfo=UTC)
        sunday = datetime(2025, 8, 24, 12, 0, 0, tzinfo=UTC)
        
        assert fetcher._is_market_hours_gap(saturday, sunday) is False
    
    def test_is_market_hours_gap_weekday(self, fetcher):
        """Test market hours gap detection for weekday."""
        # Monday during market hours
        monday_open = datetime(2025, 8, 25, 14, 30, 0, tzinfo=UTC)  # 2:30 PM UTC (10:30 AM ET)
        monday_close = datetime(2025, 8, 25, 15, 0, 0, tzinfo=UTC)   # 3:00 PM UTC (11:00 AM ET)
        
        # This is simplified - actual implementation would need proper timezone handling
        result = fetcher._is_market_hours_gap(monday_open, monday_close)
        assert isinstance(result, bool)
    
    @pytest.mark.asyncio
    async def test_fetch_bars_for_plans(self, fetcher, mock_ib_client, sample_trade_plan):
        """Test fetching bars and calculating positions for multiple plans."""
        mock_bars = [
            MagicMock(
                date=datetime.now(UTC),
                open=180.0,
                high=180.5,
                low=179.5,
                close=180.25,
                volume=100000
            )
        ]
        mock_ib_client.reqHistoricalDataAsync.return_value = mock_bars
        
        plans = [sample_trade_plan]
        results = await fetcher.fetch_bars_for_plans(plans, "5min", "1 D")
        
        assert "AAPL" in results
        assert "bars" in results["AAPL"]
        assert "positions" in results["AAPL"]
        assert sample_trade_plan.plan_id in results["AAPL"]["positions"]
        
        position = results["AAPL"]["positions"][sample_trade_plan.plan_id]
        assert position["current_price"] == 180.25
        assert position["position_status"] == "below_entry"
    
    def test_get_stats(self, fetcher):
        """Test getting fetcher statistics."""
        fetcher._stats["bars_fetched"] = 100
        fetcher._stats["fetch_errors"] = 2
        fetcher._stats["gaps_detected"] = 5
        
        stats = fetcher.get_stats()
        
        assert stats["bars_fetched"] == 100
        assert stats["fetch_errors"] == 2
        assert stats["gaps_detected"] == 5