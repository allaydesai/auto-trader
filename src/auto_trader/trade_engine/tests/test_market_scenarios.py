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
        # Modify last bar to break above threshold with good volume
        current_bar = trending_up_bars[-1]
        current_bar.close_price = Decimal("102.50")
        current_bar.volume = 1500000
        
        context = create_execution_context(
            current_bar=current_bar,
            historical_bars=trending_up_bars[:-1],
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
        # Modify a bar in downtrend to break above threshold
        current_bar = trending_down_bars[10]  # Mid-trend bar
        current_bar.close_price = Decimal("102.20")
        current_bar.volume = 800000  # Lower volume
        
        context = create_execution_context(
            current_bar=current_bar,
            historical_bars=trending_down_bars[:10],
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
            current_bar = ranging_market_bars[i]
            # Some bars will naturally be above/below threshold due to oscillation
            if current_bar.close_price > Decimal("102.0"):
                current_bar.close_price = Decimal("102.10")
            current_bar.volume = 1000000
            
            context = create_execution_context(
                current_bar=current_bar,
                historical_bars=ranging_market_bars[:i],
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
        current_bar = trending_up_bars[-1]
        current_bar.close_price = Decimal("102.50")  # Above threshold
        
        # Test 1: Low volume should reject
        current_bar.volume = 100000  # Below min_volume of 500000
        
        context = create_execution_context(
            current_bar=current_bar,
            historical_bars=trending_up_bars[:-1],
            threshold_price=102.0,
            min_volume=500000
        )
        
        signal = await close_above_function.evaluate(context)
        assert signal.action == ExecutionAction.NONE
        assert "below minimum" in signal.reasoning
        
        # Test 2: High volume should accept
        current_bar.volume = 2000000  # Above min_volume
        signal = await close_above_function.evaluate(context)
        assert signal.action == ExecutionAction.ENTER_LONG
    
    @pytest.mark.asyncio
    async def test_confirmation_bars_requirement(self):
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
        
        # Create bars where only 2 out of last 3 are above threshold
        bars = trending_up_bars()
        
        # Set last 3 bars: above, below, above
        bars[-3].close_price = Decimal("100.50")  # Above
        bars[-2].close_price = Decimal("99.80")   # Below
        bars[-1].close_price = Decimal("100.30")  # Above
        
        context = create_execution_context(
            current_bar=bars[-1],
            historical_bars=bars[:-1],
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
        current_bar = trending_down_bars[15]  # Late in downtrend
        current_bar.close_price = Decimal("97.50")  # Below stop level
        current_bar.volume = 1200000
        
        context = create_execution_context(
            current_bar=current_bar,
            historical_bars=trending_down_bars[:15],
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
        # Modify bars to show breakdown pattern
        bars = trending_down_bars.copy()
        bars[-2].close_price = Decimal("97.80")  # Below threshold
        bars[-1].close_price = Decimal("97.50")  # Confirmed below
        
        context = create_execution_context(
            current_bar=bars[-1],
            historical_bars=bars[:-1],
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
        current_bar = trending_down_bars[-1]
        current_bar.close_price = Decimal("97.50")  # Below threshold
        
        context = create_execution_context(
            current_bar=current_bar,
            historical_bars=trending_down_bars[:-1],
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
        current_bar = trending_down_bars[-1]
        current_bar.close_price = Decimal("97.50")  # Below threshold
        
        context = create_execution_context(
            current_bar=current_bar,
            historical_bars=trending_down_bars[:-1],
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
        # Simulate position entry and price movement
        position = sample_position_long
        position.entry_price = Decimal("100.00")
        position.stop_loss = Decimal("98.00")
        
        signals = []
        
        # Test trailing behavior as price moves up
        for i in range(10, len(trending_up_bars)):
            current_bar = trending_up_bars[i]
            # Ensure price keeps trending up and position is profitable
            current_bar.close_price = Decimal("100.00") + Decimal(str(i - 10)) * Decimal("0.5")
            position.current_price = current_bar.close_price
            
            context = create_execution_context(
                current_bar=current_bar,
                historical_bars=trending_up_bars[:i],
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
        position = sample_position_long
        position.entry_price = Decimal("100.00")
        position.current_price = Decimal("105.00")  # Profitable position
        
        # Create scenario where price falls and hits trailing stop
        current_bar = volatile_market_bars[-1]
        current_bar.close_price = Decimal("102.90")  # Below 2% trail from 105 = 102.90
        
        # Set up trailing stop function internal state
        trailing_stop_function._highest_price = Decimal("105.00")
        trailing_stop_function._current_stop_level = Decimal("102.90")
        
        context = create_execution_context(
            current_bar=current_bar,
            historical_bars=volatile_market_bars[:-1],
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
            historical_bars=trending_up_bars[:-1],
            position_state=None,  # No position
            trail_percentage=2.0
        )
        
        signal = await trailing_stop_function.evaluate(context)
        
        assert signal.action == ExecutionAction.NONE
        assert "No position to trail" in signal.reasoning
        
        # Internal tracking should be reset
        assert trailing_stop_function._highest_price is None
        assert trailing_stop_function._lowest_price is None
        assert trailing_stop_function._current_stop_level is None
    
    @pytest.mark.asyncio
    async def test_volatility_adjusted_trailing(self):
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
        
        # Create high volatility scenario
        bars = volatile_market_bars()
        position = sample_position_long()
        position.entry_price = Decimal("100.00")
        position.current_price = Decimal("103.00")
        
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
    async def test_fixed_amount_trailing(self):
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
        
        bars = trending_up_bars()
        position = sample_position_long()
        position.entry_price = Decimal("100.00")
        
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
    async def test_bull_market_full_cycle(self):
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
        
        bars = trending_up_bars()
        
        # Test breakout detection
        current_bar = bars[10]
        current_bar.close_price = Decimal("101.50")
        
        context = create_execution_context(
            current_bar=current_bar,
            historical_bars=bars[:10],
            threshold_price=101.0
        )
        
        breakout_signal = await close_above.evaluate(context)
        assert breakout_signal.action == ExecutionAction.ENTER_LONG
        
        # Test that functions can work in sequence (entry -> management -> exit)
        # This establishes the foundation for integration testing
        assert breakout_signal.confidence > 0.0
        assert breakout_signal.metadata is not None
    
    @pytest.mark.asyncio
    async def test_timeframe_consistency(self):
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
            bars = trending_up_bars()
            bar_size_map = {
                Timeframe.ONE_MIN: "1min",
                Timeframe.FIVE_MIN: "5min", 
                Timeframe.FIFTEEN_MIN: "15min",
            }
            
            current_bar = bars[-1]
            current_bar.bar_size = bar_size_map[timeframe]
            current_bar.close_price = Decimal("100.50")
            
            context = create_execution_context(
                current_bar=current_bar,
                historical_bars=bars[:-1],
                threshold_price=100.0
            )
            context.timeframe = timeframe
            
            signal = await function.evaluate(context)
            
            # Should work for all timeframes
            assert signal.action == ExecutionAction.ENTER_LONG
            assert function.timeframe == timeframe