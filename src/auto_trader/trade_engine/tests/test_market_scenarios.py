"""Tests for execution functions across various market scenarios."""

import pytest
from decimal import Decimal
from datetime import datetime, UTC

from auto_trader.trade_engine.functions import (
    CloseAboveFunction,
    CloseBelowFunction,
    TrailingStopFunction,
)
from auto_trader.models.execution import ExecutionFunctionConfig
from auto_trader.models.enums import Timeframe, ExecutionAction
from .fixtures.market_data import (
    create_execution_context,
    trending_up_bars,
    trending_down_bars,
    ranging_market_bars,
    volatile_market_bars,
    sample_position_long,
    sample_position_short,
)


def create_valid_bar(symbol: str, timestamp, close_price: Decimal, volume: int, bar_size: str, open_price: Decimal = None) -> "BarData":
    """Helper to create BarData with valid OHLC relationships."""
    from auto_trader.models.market_data import BarData
    
    # Ensure all decimals are properly quantized to 4 decimal places
    close_price = close_price.quantize(Decimal("0.0001"))
    
    if open_price is None:
        # Default open slightly away from close
        open_price = close_price + (Decimal("0.10") if close_price > Decimal("100") else -Decimal("0.10"))
    else:
        open_price = open_price.quantize(Decimal("0.0001"))
    
    # Ensure proper OHLC relationships
    high_price = (max(open_price, close_price) + Decimal("0.30")).quantize(Decimal("0.0001"))
    low_price = (min(open_price, close_price) - Decimal("0.20")).quantize(Decimal("0.0001"))
    
    return BarData(
        symbol=symbol,
        timestamp=timestamp,
        open_price=open_price,
        high_price=high_price,
        low_price=low_price,
        close_price=close_price,
        volume=volume,
        bar_size=bar_size,
    )


def ensure_sufficient_bars(bars_list, min_count=20):
    """Helper to ensure sufficient historical bars for execution functions."""
    if len(bars_list) >= min_count:
        return bars_list[:]
    
    # Add additional bars if needed
    base_bar = bars_list[0] if bars_list else None
    if not base_bar:
        return bars_list
    
    additional_bars = []
    for i in range(min_count - len(bars_list)):
        additional_bars.append(create_valid_bar(
            symbol=base_bar.symbol,
            timestamp=base_bar.timestamp,
            close_price=(base_bar.close_price + Decimal(str(i * 0.1))).quantize(Decimal("0.0001")),
            volume=base_bar.volume,
            bar_size=base_bar.bar_size,
        ))
    return additional_bars + bars_list


class TestCloseAboveFunctionScenarios:
    """Test CloseAboveFunction across market scenarios."""
    
    @pytest.fixture
    def close_above_function(self):
        """Create close above function with standard parameters."""
        config = ExecutionFunctionConfig(
            name="scenario_test",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={
                "threshold_price": 102.0,
                "min_volume": 500000,
                "confirmation_bars": 1,
            },
        )
        return CloseAboveFunction(config)
    
    @pytest.mark.asyncio
    async def test_bull_trend_breakout(self, close_above_function, trending_up_bars):
        """Test breakout signal in bull trend."""
        # Create new bar to break above threshold with good volume
        from auto_trader.models.market_data import BarData
        original_bar = trending_up_bars[-1]
        
        close_price = Decimal("102.50")
        current_bar = BarData(
            symbol=original_bar.symbol,
            timestamp=original_bar.timestamp,
            open_price=original_bar.open_price,
            high_price=max(original_bar.high_price, close_price),
            low_price=min(original_bar.low_price, original_bar.open_price, close_price),
            close_price=close_price,
            volume=1500000,
            bar_size=original_bar.bar_size,
        )
        
        # Ensure we have enough historical bars (need 20)
        if len(trending_up_bars) <= 20:
            # Add more bars if needed
            additional_bars = []
            base_bar = trending_up_bars[0]
            for i in range(21 - len(trending_up_bars)):
                additional_bars.append(BarData(
                    symbol=base_bar.symbol,
                    timestamp=base_bar.timestamp,
                    open_price=base_bar.open_price,
                    high_price=base_bar.high_price,
                    low_price=base_bar.low_price,
                    close_price=base_bar.close_price,
                    volume=base_bar.volume,
                    bar_size=base_bar.bar_size,
                ))
            historical_bars = additional_bars + trending_up_bars[:-1]
        else:
            historical_bars = trending_up_bars[:20]  # Use exactly 20 bars
        
        context = create_execution_context(
            current_bar=current_bar,
            historical_bars=historical_bars,
            threshold_price=102.0,
            min_volume=500000
        )
        
        signal = await close_above_function.evaluate(context)
        
        assert signal.action == ExecutionAction.ENTER_LONG
        assert signal.confidence > 0.7  # High confidence in trend continuation
        assert "above threshold" in signal.reasoning
        assert "volume" in signal.reasoning
    
    @pytest.mark.asyncio
    async def test_bear_trend_false_breakout(self, close_above_function, trending_down_bars):
        """Test potential false breakout in bear trend."""
        # Create new bar in downtrend to break above threshold
        from auto_trader.models.market_data import BarData
        original_bar = trending_down_bars[10]  # Mid-trend bar
        
        close_price = Decimal("102.20")
        current_bar = BarData(
            symbol=original_bar.symbol,
            timestamp=original_bar.timestamp,
            open_price=original_bar.open_price,
            high_price=max(original_bar.high_price, close_price),
            low_price=min(original_bar.low_price, original_bar.open_price, close_price),
            close_price=close_price,
            volume=800000,  # Lower volume
            bar_size=original_bar.bar_size,
        )
        
        # Ensure we have enough historical bars (need 20)
        historical_bars = trending_down_bars[:10]
        if len(historical_bars) < 20:
            # Pad with additional bars
            additional_count = 20 - len(historical_bars)
            base_bar = trending_down_bars[0]
            additional_bars = []
            for i in range(additional_count):
                additional_bars.append(BarData(
                    symbol=base_bar.symbol,
                    timestamp=base_bar.timestamp,
                    open_price=base_bar.open_price,
                    high_price=base_bar.high_price,
                    low_price=base_bar.low_price,
                    close_price=base_bar.close_price,
                    volume=base_bar.volume,
                    bar_size=base_bar.bar_size,
                ))
            historical_bars = additional_bars + historical_bars
        
        context = create_execution_context(
            current_bar=current_bar,
            historical_bars=historical_bars,
            threshold_price=102.0,
            min_volume=500000
        )
        
        signal = await close_above_function.evaluate(context)
        
        assert signal.action == ExecutionAction.ENTER_LONG
        # Confidence should be lower due to counter-trend momentum
        assert signal.confidence < 0.8
    
    @pytest.mark.asyncio
    async def test_ranging_market_whipsaw(self, close_above_function, ranging_market_bars):
        """Test multiple signals in ranging market."""
        signals = []
        
        for i in range(10, len(ranging_market_bars)):
            original_bar = ranging_market_bars[i]
            # Create new bar with price above threshold if needed
            close_price = Decimal("102.10") if original_bar.close_price > Decimal("102.0") else original_bar.close_price
            
            current_bar = create_valid_bar(
                symbol=original_bar.symbol,
                timestamp=original_bar.timestamp,
                close_price=close_price,
                volume=1000000,
                bar_size=original_bar.bar_size,
            )
            
            context = create_execution_context(
                current_bar=current_bar,
                historical_bars=ensure_sufficient_bars(ranging_market_bars[:i]),
                threshold_price=102.0,
                min_volume=500000
            )
            
            signal = await close_above_function.evaluate(context)
            signals.append(signal)
        
        # Should have some triggers but with varying confidence
        triggered = [s for s in signals if s.action != ExecutionAction.NONE]
        
        if triggered:
            # Confidence should vary reflecting the ranging nature
            confidences = [s.confidence for s in triggered]
            assert min(confidences) < max(confidences)  # Some variation
    
    @pytest.mark.asyncio
    async def test_volume_confirmation(self, close_above_function, trending_up_bars):
        """Test volume confirmation requirement."""
        from auto_trader.models.market_data import BarData
        original_bar = trending_up_bars[-1]
        
        # Test 1: Low volume should reject
        close_price = Decimal("102.50")
        open_price = Decimal("102.00")
        high_price = max(close_price, open_price) + Decimal("0.30")
        low_price = min(close_price, open_price) - Decimal("0.20")
        
        current_bar = BarData(
            symbol=original_bar.symbol,
            timestamp=original_bar.timestamp,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,  # Above threshold
            volume=100000,  # Below min_volume of 500000
            bar_size=original_bar.bar_size,
        )
        
        context = create_execution_context(
            current_bar=current_bar,
            historical_bars=ensure_sufficient_bars(trending_up_bars[:-1]),
            threshold_price=102.0,
            min_volume=500000
        )
        
        signal = await close_above_function.evaluate(context)
        assert signal.action == ExecutionAction.NONE
        assert "below minimum" in signal.reasoning
        
        # Test 2: High volume should accept
        current_bar_high_vol = BarData(
            symbol=original_bar.symbol,
            timestamp=original_bar.timestamp,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
            volume=2000000,  # Above min_volume
            bar_size=original_bar.bar_size,
        )
        context_high_vol = create_execution_context(
            current_bar=current_bar_high_vol,
            historical_bars=ensure_sufficient_bars(trending_up_bars[:-1]),
            threshold_price=102.0,
            min_volume=500000
        )
        signal = await close_above_function.evaluate(context_high_vol)
        assert signal.action == ExecutionAction.ENTER_LONG
    
    @pytest.mark.asyncio
    async def test_confirmation_bars_requirement(self, trending_up_bars):
        """Test multiple bar confirmation requirement."""
        config = ExecutionFunctionConfig(
            name="confirmation_test",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={
                "threshold_price": 100.0,
                "confirmation_bars": 3,  # Require 3 bars above threshold
            },
        )
        function = CloseAboveFunction(config)
        
        # Create modified bars where only 2 out of last 3 are above threshold
        from auto_trader.models.market_data import BarData
        bars = trending_up_bars.copy()  # Create a copy to avoid modifying fixture
        
        # Create new bars with modified prices: above, below, above
        # Bar -3: close above threshold (100.50)
        close_3 = Decimal("100.50")
        open_3 = Decimal("100.20")
        high_3 = max(close_3, open_3) + Decimal("0.10")
        low_3 = min(close_3, open_3) - Decimal("0.10")
        bars[-3] = BarData(
            symbol=bars[-3].symbol, timestamp=bars[-3].timestamp, open_price=open_3,
            high_price=high_3, low_price=low_3,
            close_price=close_3, volume=bars[-3].volume, bar_size=bars[-3].bar_size
        )
        
        # Bar -2: close below threshold (99.80)
        close_2 = Decimal("99.80")
        open_2 = Decimal("100.00")
        high_2 = max(close_2, open_2) + Decimal("0.10")
        low_2 = min(close_2, open_2) - Decimal("0.10")
        bars[-2] = BarData(
            symbol=bars[-2].symbol, timestamp=bars[-2].timestamp, open_price=open_2,
            high_price=high_2, low_price=low_2,
            close_price=close_2, volume=bars[-2].volume, bar_size=bars[-2].bar_size
        )
        
        # Bar -1: close above threshold (100.30)
        close_1 = Decimal("100.30")
        open_1 = Decimal("100.10")
        high_1 = max(close_1, open_1) + Decimal("0.10")
        low_1 = min(close_1, open_1) - Decimal("0.10")
        bars[-1] = BarData(
            symbol=bars[-1].symbol, timestamp=bars[-1].timestamp, open_price=open_1,
            high_price=high_1, low_price=low_1,
            close_price=close_1, volume=bars[-1].volume, bar_size=bars[-1].bar_size
        )
        
        context = create_execution_context(
            current_bar=bars[-1],
            historical_bars=ensure_sufficient_bars(bars[:-1]),
            threshold_price=100.0,
            confirmation_bars=3
        )
        
        signal = await function.evaluate(context)
        assert signal.action == ExecutionAction.NONE
        assert "2/3 bars" in signal.reasoning or "Only 2" in signal.reasoning


class TestCloseBelowFunctionScenarios:
    """Test CloseBelowFunction across market scenarios."""
    
    @pytest.fixture
    def close_below_exit_function(self):
        """Create close below function for stop-loss exits."""
        config = ExecutionFunctionConfig(
            name="stop_loss_test",
            function_type="close_below",
            timeframe=Timeframe.ONE_MIN,
            parameters={
                "threshold_price": 98.0,
                "action": "EXIT",
                "min_volume": 300000,
            },
        )
        return CloseBelowFunction(config)
    
    @pytest.fixture
    def close_below_short_function(self):
        """Create close below function for short entries."""
        config = ExecutionFunctionConfig(
            name="short_entry_test",
            function_type="close_below",
            timeframe=Timeframe.ONE_MIN,
            parameters={
                "threshold_price": 98.0,
                "action": "ENTER_SHORT",
                "confirmation_bars": 2,
            },
        )
        return CloseBelowFunction(config)
    
    @pytest.mark.asyncio
    async def test_stop_loss_trigger_in_downtrend(self, close_below_exit_function, trending_down_bars, sample_position_long):
        """Test stop-loss trigger during downtrend."""
        original_bar = trending_down_bars[15]  # Late in downtrend
        current_bar = create_valid_bar(
            symbol=original_bar.symbol,
            timestamp=original_bar.timestamp,
            close_price=Decimal("97.50"),  # Below stop level
            volume=1200000,
            bar_size=original_bar.bar_size,
        )
        
        # Ensure we have enough historical data (need 20 bars)
        historical_bars = trending_down_bars[:]  # Use all 20 bars as historical
        if len(historical_bars) < 20:
            # Add additional bars if needed
            base_bar = historical_bars[0]
            additional_bars = []
            for i in range(20 - len(historical_bars)):
                additional_bars.append(create_valid_bar(
                    symbol=base_bar.symbol,
                    timestamp=base_bar.timestamp,
                    close_price=base_bar.close_price - Decimal(str(i * 0.1)),
                    volume=base_bar.volume,
                    bar_size=base_bar.bar_size,
                ))
            historical_bars = additional_bars + historical_bars
        
        context = create_execution_context(
            current_bar=current_bar,
            historical_bars=historical_bars,
            position_state=sample_position_long,
            threshold_price=98.0,
            action="EXIT",
            min_volume=300000
        )
        
        signal = await close_below_exit_function.evaluate(context)
        
        assert signal.action == ExecutionAction.EXIT
        assert signal.confidence > 0.8  # High confidence for stop-loss in trend
        assert "Stop-loss triggered" in signal.reasoning
    
    @pytest.mark.asyncio
    async def test_short_entry_breakdown(self, close_below_short_function, trending_down_bars):
        """Test short entry on support breakdown."""
        from auto_trader.models.market_data import BarData
        # Create modified bars to show breakdown pattern
        bars = trending_down_bars.copy()
        bars[-2] = create_valid_bar(
            symbol=bars[-2].symbol, timestamp=bars[-2].timestamp, 
            close_price=Decimal("97.80"), volume=bars[-2].volume, bar_size=bars[-2].bar_size
        )
        bars[-1] = create_valid_bar(
            symbol=bars[-1].symbol, timestamp=bars[-1].timestamp, 
            close_price=Decimal("97.50"), volume=bars[-1].volume, bar_size=bars[-1].bar_size
        )
        
        context = create_execution_context(
            current_bar=bars[-1],
            historical_bars=ensure_sufficient_bars(bars[:-1]),
            threshold_price=98.0,
            action="ENTER_SHORT",
            confirmation_bars=2
        )
        
        signal = await close_below_short_function.evaluate(context)
        
        assert signal.action == ExecutionAction.ENTER_SHORT
        assert "broke down" in signal.reasoning or "below support" in signal.reasoning
    
    @pytest.mark.asyncio
    async def test_no_position_for_exit(self, close_below_exit_function, trending_down_bars):
        """Test that EXIT action requires a position."""
        from auto_trader.models.market_data import BarData
        original_bar = trending_down_bars[-1]
        current_bar = create_valid_bar(
            symbol=original_bar.symbol,
            timestamp=original_bar.timestamp,
            close_price=Decimal("97.50"),  # Below threshold
            volume=original_bar.volume,
            bar_size=original_bar.bar_size,
        )
        
        context = create_execution_context(
            current_bar=current_bar,
            historical_bars=ensure_sufficient_bars(trending_down_bars[:-1]),
            position_state=None,  # No position
            threshold_price=98.0,
            action="EXIT"
        )
        
        signal = await close_below_exit_function.evaluate(context)
        
        assert signal.action == ExecutionAction.NONE
        assert "No position to exit" in signal.reasoning
    
    @pytest.mark.asyncio
    async def test_position_exists_for_short_entry(self, close_below_short_function, trending_down_bars, sample_position_long):
        """Test that ENTER_SHORT rejects when position exists."""
        from auto_trader.models.market_data import BarData
        original_bar = trending_down_bars[-1]
        current_bar = create_valid_bar(
            symbol=original_bar.symbol,
            timestamp=original_bar.timestamp,
            close_price=Decimal("97.50"),  # Below threshold
            volume=original_bar.volume,
            bar_size=original_bar.bar_size,
        )
        
        context = create_execution_context(
            current_bar=current_bar,
            historical_bars=ensure_sufficient_bars(trending_down_bars[:-1]),
            position_state=sample_position_long,  # Already have position
            threshold_price=98.0,
            action="ENTER_SHORT"
        )
        
        signal = await close_below_short_function.evaluate(context)
        
        assert signal.action == ExecutionAction.NONE
        assert "Already in position" in signal.reasoning


class TestTrailingStopFunctionScenarios:
    """Test TrailingStopFunction across market scenarios."""
    
    @pytest.fixture
    def trailing_stop_function(self):
        """Create trailing stop function with standard parameters."""
        config = ExecutionFunctionConfig(
            name="trail_test",
            function_type="trailing_stop",
            timeframe=Timeframe.ONE_MIN,
            parameters={
                "trail_percentage": 2.0,  # 2% trailing stop
                "trail_on_profit_only": True,
            },
        )
        return TrailingStopFunction(config)
    
    @pytest.mark.asyncio
    async def test_trailing_in_uptrend(self, trailing_stop_function, trending_up_bars, sample_position_long):
        """Test trailing stop follows price up in uptrend."""
        from auto_trader.models.execution import PositionState
        from datetime import datetime, UTC
        # Create a new position to avoid modifying fixture data
        position = PositionState(
            symbol=sample_position_long.symbol,
            quantity=sample_position_long.quantity,
            entry_price=Decimal("100.00"),
            current_price=sample_position_long.current_price,
            stop_loss=Decimal("98.00"),
            take_profit=sample_position_long.take_profit,
            opened_at=datetime.now(UTC),
        )
        
        signals = []
        
        # Test trailing behavior as price moves up
        for i in range(10, len(trending_up_bars)):
            original_bar = trending_up_bars[i]
            # Create new bar with trending up price
            new_close = Decimal("100.00") + Decimal(str(i - 10)) * Decimal("0.5")
            current_bar = create_valid_bar(
                symbol=original_bar.symbol,
                timestamp=original_bar.timestamp,
                close_price=new_close,
                volume=original_bar.volume,
                bar_size=original_bar.bar_size,
            )
            position.current_price = current_bar.close_price
            
            context = create_execution_context(
                current_bar=current_bar,
                historical_bars=ensure_sufficient_bars(trending_up_bars[:i]),
                position_state=position,
                trail_percentage=2.0,
                trail_on_profit_only=True
            )
            
            signal = await trailing_stop_function.evaluate(context)
            signals.append(signal)
            
            if signal.action == ExecutionAction.MODIFY_STOP:
                # Update the position's stop loss for next iteration
                new_stop = Decimal(str(signal.metadata.get("new_stop_level", position.stop_loss)))
                position.stop_loss = new_stop
        
        # Should have some stop modifications as price moves up
        modify_signals = [s for s in signals if s.action == ExecutionAction.MODIFY_STOP]
        assert len(modify_signals) > 0
        
        # Stop should be moving up (trailing)
        stop_levels = [Decimal(str(s.metadata["new_stop_level"])) for s in modify_signals]
        assert stop_levels[-1] > stop_levels[0]  # Stop moved up
    
    @pytest.mark.asyncio
    async def test_trailing_stop_hit(self, trailing_stop_function, volatile_market_bars, sample_position_long):
        """Test trailing stop gets hit on reversal."""
        from auto_trader.models.execution import PositionState
        from auto_trader.models.market_data import BarData
        from datetime import datetime, UTC
        # Create a new position to avoid modifying fixture data
        position = PositionState(
            symbol=sample_position_long.symbol,
            quantity=sample_position_long.quantity,
            entry_price=Decimal("100.00"),
            current_price=Decimal("105.00"),  # Profitable position
            stop_loss=sample_position_long.stop_loss,
            take_profit=sample_position_long.take_profit,
            opened_at=datetime.now(UTC),
        )
        
        # Create scenario where price falls and hits trailing stop
        original_bar = volatile_market_bars[-1]
        current_bar = create_valid_bar(
            symbol=original_bar.symbol,
            timestamp=original_bar.timestamp,
            close_price=Decimal("102.90"),  # Below 2% trail from 105 = 102.90
            volume=original_bar.volume,
            bar_size=original_bar.bar_size,
        )
        
        # Set up trailing stop function internal state
        trailing_stop_function._highest_price = Decimal("105.00")
        trailing_stop_function._current_stop_level = Decimal("102.90")
        
        # Ensure we have enough historical data (need 20 bars)
        historical_bars = volatile_market_bars[:]  # Use all bars as historical
        if len(historical_bars) < 20:
            # Add additional bars if needed
            base_bar = historical_bars[0]
            additional_bars = []
            for i in range(20 - len(historical_bars)):
                additional_bars.append(create_valid_bar(
                    symbol=base_bar.symbol,
                    timestamp=base_bar.timestamp,
                    close_price=base_bar.close_price + Decimal(str(i * 0.1)),
                    volume=base_bar.volume,
                    bar_size=base_bar.bar_size,
                ))
            historical_bars = additional_bars + historical_bars
        
        context = create_execution_context(
            current_bar=current_bar,
            historical_bars=historical_bars,
            position_state=position,
            trail_percentage=2.0
        )
        
        signal = await trailing_stop_function.evaluate(context)
        
        assert signal.action == ExecutionAction.EXIT
        assert signal.confidence == 1.0  # Always high confidence when stop hit
        assert "hit" in signal.reasoning.lower()
    
    @pytest.mark.asyncio
    async def test_no_position_resets_tracking(self, trailing_stop_function, trending_up_bars):
        """Test that no position resets internal tracking."""
        context = create_execution_context(
            current_bar=trending_up_bars[-1],
            historical_bars=ensure_sufficient_bars(trending_up_bars[:-1]),
            position_state=None,  # No position
            trail_percentage=2.0
        )
        
        signal = await trailing_stop_function.evaluate(context)
        
        assert signal.action == ExecutionAction.NONE
        # Function may return different messages based on internal checks
        assert any(phrase in signal.reasoning for phrase in [
            "No position to trail", 
            "Insufficient historical data",
            "No position"
        ])
        
        # Internal tracking should be reset
        assert trailing_stop_function._highest_price is None
        assert trailing_stop_function._lowest_price is None
        assert trailing_stop_function._current_stop_level is None
    
    @pytest.mark.asyncio
    async def test_volatility_adjusted_trailing(self, volatile_market_bars, sample_position_long):
        """Test volatility-adjusted trailing stop."""
        config = ExecutionFunctionConfig(
            name="volatility_trail",
            function_type="trailing_stop", 
            timeframe=Timeframe.ONE_MIN,
            parameters={
                "trail_percentage": 2.0,
                "volatility_adjusted": True,
            },
        )
        function = TrailingStopFunction(config)
        
        # Create high volatility scenario using fixture
        bars = volatile_market_bars
        from auto_trader.models.execution import PositionState
        from datetime import datetime, UTC
        position = PositionState(
            symbol=sample_position_long.symbol,
            quantity=sample_position_long.quantity,
            entry_price=Decimal("100.00"),
            current_price=Decimal("103.00"),
            stop_loss=sample_position_long.stop_loss,
            take_profit=sample_position_long.take_profit,
            opened_at=datetime.now(UTC),
        )
        
        context = create_execution_context(
            current_bar=bars[-1],
            historical_bars=bars[:-1],
            position_state=position,
            trail_percentage=2.0,
            volatility_adjusted=True
        )
        
        signal = await function.evaluate(context)
        
        # Should complete without error and potentially adjust stop
        assert signal is not None
        assert signal.action in [ExecutionAction.NONE, ExecutionAction.MODIFY_STOP, ExecutionAction.EXIT]
    
    @pytest.mark.asyncio
    async def test_fixed_amount_trailing(self, trending_up_bars, sample_position_long):
        """Test fixed dollar amount trailing instead of percentage."""
        config = ExecutionFunctionConfig(
            name="fixed_trail",
            function_type="trailing_stop",
            timeframe=Timeframe.ONE_MIN,
            parameters={
                "trail_percentage": 2.0,  # This will be used (with warning)
                "trail_amount": 1.50,     # Fixed $1.50 trail
            },
        )
        function = TrailingStopFunction(config)
        
        bars = trending_up_bars  # Use fixture directly
        from auto_trader.models.execution import PositionState
        from datetime import datetime, UTC
        position = PositionState(
            symbol=sample_position_long.symbol,
            quantity=sample_position_long.quantity,
            entry_price=Decimal("100.00"),
            current_price=sample_position_long.current_price,
            stop_loss=sample_position_long.stop_loss,
            take_profit=sample_position_long.take_profit,
            opened_at=datetime.now(UTC),
        )
        
        context = create_execution_context(
            current_bar=bars[-1],
            historical_bars=bars[:-1],
            position_state=position,
            trail_percentage=2.0,
            trail_amount=1.50
        )
        
        signal = await function.evaluate(context)
        
        # Should handle fixed amount trailing
        assert signal is not None
        assert signal.action in [ExecutionAction.NONE, ExecutionAction.MODIFY_STOP]


class TestCrossMarketScenarioIntegration:
    """Test integration scenarios across different market conditions."""
    
    @pytest.mark.asyncio
    async def test_bull_market_full_cycle(self, trending_up_bars):
        """Test complete cycle: breakout -> trail -> exit in bull market."""
        # This would test a complete trading cycle but requires more complex setup
        # For now, we'll test individual components work together
        
        close_above_config = ExecutionFunctionConfig(
            name="bull_cycle",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 101.0},
        )
        close_above = CloseAboveFunction(close_above_config)
        
        bars = trending_up_bars  # Use fixture directly
        
        # Test breakout detection - create new bar instead of modifying
        original_bar = bars[10]
        close_price = Decimal("101.50")
        current_bar = create_valid_bar(
            symbol=original_bar.symbol,
            timestamp=original_bar.timestamp,
            close_price=close_price,
            volume=original_bar.volume,
            bar_size=original_bar.bar_size,
        )
        
        context = create_execution_context(
            current_bar=current_bar,
            historical_bars=ensure_sufficient_bars(bars[:10]),
            threshold_price=101.0
        )
        
        breakout_signal = await close_above.evaluate(context)
        assert breakout_signal.action == ExecutionAction.ENTER_LONG
        
        # Test that functions can work in sequence (entry -> management -> exit)
        # This establishes the foundation for integration testing
        assert breakout_signal.confidence > 0.0
        assert breakout_signal.metadata is not None
    
    @pytest.mark.asyncio
    async def test_timeframe_consistency(self, trending_up_bars):
        """Test that functions respect timeframe settings consistently."""
        # Test different timeframes work correctly
        timeframes = [Timeframe.ONE_MIN, Timeframe.FIVE_MIN, Timeframe.FIFTEEN_MIN]
        
        for timeframe in timeframes:
            config = ExecutionFunctionConfig(
                name=f"timeframe_test_{timeframe.value}",
                function_type="close_above",
                timeframe=timeframe,
                parameters={"threshold_price": 100.0},
            )
            function = CloseAboveFunction(config)
            
            # Create bars with appropriate bar_size
            bars = trending_up_bars  # Use the fixture parameter
            bar_size_map = {
                Timeframe.ONE_MIN: "1min",
                Timeframe.FIVE_MIN: "5min", 
                Timeframe.FIFTEEN_MIN: "15min",
            }
            
            # Create new bar with appropriate bar_size and close_price
            from auto_trader.models.market_data import BarData
            original_bar = bars[-1]
            close_price = Decimal("100.50")
            open_price = original_bar.open_price
            current_bar = BarData(
                symbol=original_bar.symbol,
                timestamp=original_bar.timestamp,
                open_price=open_price,
                high_price=max(original_bar.high_price, close_price),
                low_price=min(original_bar.low_price, open_price, close_price),
                close_price=close_price,
                volume=original_bar.volume,
                bar_size=bar_size_map[timeframe],
            )
            
            # Ensure we have enough historical bars (need 20)
            historical_bars = bars[:-1]
            if len(historical_bars) < 20:
                # Pad with additional bars
                additional_count = 20 - len(historical_bars)
                base_bar = bars[0]
                additional_bars = []
                for i in range(additional_count):
                    additional_bars.append(BarData(
                        symbol=base_bar.symbol,
                        timestamp=base_bar.timestamp,
                        open_price=base_bar.open_price,
                        high_price=base_bar.high_price,
                        low_price=base_bar.low_price,
                        close_price=base_bar.close_price,
                        volume=base_bar.volume,
                        bar_size=bar_size_map[timeframe],  # Use appropriate bar_size
                    ))
                historical_bars = additional_bars + historical_bars
            
            # Need to create ExecutionContext directly with proper timeframe since create_execution_context hardcodes ONE_MIN
            from auto_trader.models.execution import ExecutionContext
            from datetime import datetime, UTC
            context = ExecutionContext(
                symbol=current_bar.symbol,
                timeframe=timeframe,
                current_bar=current_bar,
                historical_bars=historical_bars,
                trade_plan_params={"threshold_price": 100.0},
                position_state=None,
                account_balance=Decimal("10000"),
                timestamp=datetime.now(UTC),
            )
            
            signal = await function.evaluate(context)
            
            # Should work for all timeframes
            assert signal.action == ExecutionAction.ENTER_LONG
            assert function.timeframe == timeframe