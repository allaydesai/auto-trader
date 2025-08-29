"""Tests for edge case detection and handling in execution functions."""

import pytest
from decimal import Decimal
from datetime import datetime, UTC

from auto_trader.trade_engine.edge_case_detector import EdgeCaseDetector, EdgeCaseResult
from auto_trader.trade_engine.functions import (
    CloseAboveFunction,
    CloseBelowFunction,
    TrailingStopFunction,
)
from auto_trader.models.execution import ExecutionFunctionConfig
from auto_trader.models.enums import Timeframe, ExecutionAction
from .fixtures.market_data import (
    create_execution_context,
    gap_up_scenario,
    gap_down_scenario,
    limit_up_scenario,
    invalid_data_bars,
    low_volume_bars,
    volatile_market_bars,
    trending_up_bars,
    trending_down_bars,
    ranging_market_bars,
    sample_position_long,
)


class TestEdgeCaseDetector:
    """Test the EdgeCaseDetector utility class."""
    
    def test_detector_initialization(self):
        """Test detector initializes with default parameters."""
        detector = EdgeCaseDetector()
        assert detector.gap_threshold_percent == Decimal("2.0")
        assert detector.limit_move_percent == Decimal("10.0")
        assert detector.volume_spike_threshold == 5.0
        assert detector.min_volume_threshold == 1000
    
    def test_detector_custom_parameters(self):
        """Test detector accepts custom parameters."""
        detector = EdgeCaseDetector(
            gap_threshold_percent=1.5,
            limit_move_percent=15.0,
            volume_spike_threshold=3.0,
            min_volume_threshold=500,
        )
        assert detector.gap_threshold_percent == Decimal("1.5")
        assert detector.limit_move_percent == Decimal("15.0")
        assert detector.volume_spike_threshold == 3.0
        assert detector.min_volume_threshold == 500
    
    def test_data_quality_check_valid_data(self, trending_up_bars):
        """Test data quality check passes for valid data."""
        detector = EdgeCaseDetector()
        current_bar = trending_up_bars[-1]
        
        result = detector.check_data_quality(current_bar)
        
        assert not result.has_edge_case
        assert result.case_type == "none"
        assert result.recommended_action == "continue"
    
    def test_data_quality_check_invalid_ohlc(self, invalid_data_bars):
        """Test data quality check detects invalid OHLC relationships."""
        detector = EdgeCaseDetector()
        invalid_bar = invalid_data_bars[1]  # Has high < low
        
        result = detector.check_data_quality(invalid_bar)
        
        assert result.has_edge_case
        assert result.case_type == "invalid_ohlc"
        assert result.severity == "high"
        assert result.recommended_action == "skip_evaluation"
    
    def test_data_quality_check_low_volume(self, low_volume_bars):
        """Test data quality check detects low volume."""
        detector = EdgeCaseDetector(min_volume_threshold=1000)
        current_bar = low_volume_bars[0]  # Has volume = 100
        
        result = detector.check_data_quality(current_bar)
        
        assert result.has_edge_case
        assert result.case_type == "low_volume"
        assert result.severity == "low"
        assert result.recommended_action == "reduce_confidence"
    
    def test_gap_detection_up(self, gap_up_scenario):
        """Test gap up detection."""
        detector = EdgeCaseDetector(gap_threshold_percent=2.0)
        previous_bar = gap_up_scenario[0]
        current_bar = gap_up_scenario[1]
        
        result = detector.detect_gap(current_bar, previous_bar)
        
        assert result.has_edge_case
        assert result.case_type == "gap_up"
        assert "2.3" in result.description or "2.2" in result.description  # ~2.3% gap
        assert result.severity == "medium"
    
    def test_gap_detection_down(self, gap_down_scenario):
        """Test gap down detection."""
        detector = EdgeCaseDetector(gap_threshold_percent=2.0)
        previous_bar = gap_down_scenario[0]
        current_bar = gap_down_scenario[1]
        
        result = detector.detect_gap(current_bar, previous_bar)
        
        assert result.has_edge_case
        assert result.case_type == "gap_down"
        assert result.severity == "medium"
    
    def test_limit_move_detection(self, limit_up_scenario):
        """Test limit up move detection."""
        detector = EdgeCaseDetector(limit_move_percent=10.0)
        current_bar = limit_up_scenario[-1]  # The limit up bar
        historical_bars = limit_up_scenario[:-1]
        
        result = detector.detect_limit_move(current_bar, historical_bars)
        
        assert result.has_edge_case
        assert result.case_type == "limit_up"
        assert result.severity == "high"
        assert "15" in result.description  # ~15% move
    
    def test_volume_spike_detection(self, volatile_market_bars):
        """Test volume spike detection."""
        detector = EdgeCaseDetector(volume_spike_threshold=3.0)
        
        # Find a bar with high volume relative to others
        current_bar = None
        for bar in volatile_market_bars:
            if bar.volume > 1000000:  # High volume bar
                current_bar = bar
                break
        
        assert current_bar is not None
        
        # Use bars with normal volume as historical context
        historical_bars = [bar for bar in volatile_market_bars if bar.volume <= 700000][:20]
        
        if len(historical_bars) >= 20:
            result = detector.detect_volume_anomaly(current_bar, historical_bars)
            
            if result.has_edge_case:
                assert result.case_type == "volume_spike"
                assert result.severity in ["medium", "high"]
    
    def test_confidence_adjustment_calculation(self):
        """Test confidence adjustment calculation."""
        detector = EdgeCaseDetector()
        
        # No edge cases should return 1.0
        edge_cases = []
        adjustment = detector.get_confidence_adjustment(edge_cases)
        assert adjustment == 1.0
        
        # Skip evaluation case should return 0.0
        edge_cases = [EdgeCaseResult(
            has_edge_case=True,
            case_type="invalid_ohlc",
            severity="high",
            description="Test",
            recommended_action="skip_evaluation"
        )]
        adjustment = detector.get_confidence_adjustment(edge_cases)
        assert adjustment == 0.0
        
        # Reduce confidence case should return < 1.0
        edge_cases = [EdgeCaseResult(
            has_edge_case=True,
            case_type="low_volume",
            severity="medium",
            description="Test",
            recommended_action="reduce_confidence"
        )]
        adjustment = detector.get_confidence_adjustment(edge_cases)
        assert 0.0 < adjustment < 1.0
    
    def test_should_skip_evaluation(self):
        """Test should skip evaluation logic."""
        detector = EdgeCaseDetector()
        
        # No skip action should return False
        edge_cases = [EdgeCaseResult(
            has_edge_case=True,
            case_type="gap_up",
            severity="medium",
            description="Test",
            recommended_action="adjust_confidence"
        )]
        assert not detector.should_skip_evaluation(edge_cases)
        
        # Skip action should return True
        edge_cases = [EdgeCaseResult(
            has_edge_case=True,
            case_type="invalid_ohlc",
            severity="high",
            description="Test",
            recommended_action="skip_evaluation"
        )]
        assert detector.should_skip_evaluation(edge_cases)


class TestExecutionFunctionsWithEdgeCases:
    """Test execution functions handle edge cases correctly."""
    
    @pytest.fixture
    def close_above_function(self):
        """Create close above function for testing."""
        config = ExecutionFunctionConfig(
            name="test_close_above",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 101.0},
        )
        return CloseAboveFunction(config)
    
    @pytest.fixture
    def close_below_function(self):
        """Create close below function for testing."""
        config = ExecutionFunctionConfig(
            name="test_close_below",
            function_type="close_below", 
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 99.0, "action": "EXIT"},
        )
        return CloseBelowFunction(config)
    
    @pytest.mark.asyncio
    async def test_close_above_skips_invalid_data(self, close_above_function, invalid_data_bars):
        """Test close above function skips evaluation for invalid data."""
        current_bar = invalid_data_bars[1]  # Invalid bar
        historical_bars = invalid_data_bars[:1]
        
        context = create_execution_context(
            current_bar=current_bar,
            historical_bars=historical_bars,
            threshold_price=101.0
        )
        
        signal = await close_above_function.evaluate(context)
        
        assert signal.action == ExecutionAction.NONE
        assert "edge case" in signal.reasoning
    
    @pytest.mark.asyncio
    async def test_close_above_adjusts_confidence_for_gaps(self, close_above_function, gap_up_scenario):
        """Test close above function adjusts confidence for gap scenarios."""
        gap_bars = gap_up_scenario()  # Call the fixture function
        current_bar = gap_bars[1]  # Gap up bar above threshold
        historical_bars = gap_bars[:1]
        
        context = create_execution_context(
            current_bar=current_bar,
            historical_bars=historical_bars,
            threshold_price=101.0
        )
        
        signal = await close_above_function.evaluate(context)
        
        # Should still trigger but with adjusted confidence
        assert signal.action == ExecutionAction.ENTER_LONG
        # Confidence might be reduced due to gap, but function should still work
        assert 0.0 < signal.confidence <= 1.0
    
    @pytest.mark.asyncio
    async def test_close_below_handles_gap_down(self, close_below_function, gap_down_scenario):
        """Test close below function handles gap down scenarios."""
        gap_bars = gap_down_scenario()  # Call the fixture function
        current_bar = gap_bars[1]  # Gap down bar below threshold
        historical_bars = gap_bars[:1]
        
        # Set up context with position for EXIT action
        position = sample_position_long()
        
        context = create_execution_context(
            current_bar=current_bar,
            historical_bars=historical_bars,
            position_state=position,
            threshold_price=99.0,
            action="EXIT"
        )
        
        signal = await close_below_function.evaluate(context)
        
        # Should trigger exit with adjusted confidence
        assert signal.action == ExecutionAction.EXIT
        assert 0.0 < signal.confidence <= 1.0
    
    @pytest.mark.asyncio
    async def test_functions_handle_low_volume(self, close_above_function, low_volume_bars):
        """Test functions handle low volume scenarios."""
        # Create a new bar instead of modifying immutable one
        original_bar = low_volume_bars[-1]
        from auto_trader.models.market_data import BarData
        
        current_bar = BarData(
            symbol=original_bar.symbol,
            timestamp=original_bar.timestamp,
            open_price=Decimal("101.00"),
            high_price=Decimal("101.60"),  # Ensure high >= close
            low_price=Decimal("100.80"),
            close_price=Decimal("101.50"),  # Above threshold
            volume=original_bar.volume,  # Keep low volume
            bar_size=original_bar.bar_size,
        )
        historical_bars = low_volume_bars[:-1]
        
        context = create_execution_context(
            current_bar=current_bar,
            historical_bars=historical_bars,
            threshold_price=101.0
        )
        
        signal = await close_above_function.evaluate(context)
        
        # Should trigger but with reduced confidence due to low volume
        assert signal.action == ExecutionAction.ENTER_LONG
        # Confidence should be reduced from the edge case adjustment
        assert signal.confidence < 1.0
    
    @pytest.mark.asyncio
    async def test_distance_validation_parameters(self, close_above_function):
        """Test new distance validation parameters work correctly."""
        # Test with valid close above function config
        config = ExecutionFunctionConfig(
            name="test_distance",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={
                "threshold_price": 100.0,
                "min_distance_percent": 1.0,  # Require at least 1% above
                "max_distance_percent": 5.0,  # Don't trigger if more than 5% above
            },
        )
        function = CloseAboveFunction(config)
        
        # Test case 1: Price barely above threshold (should fail min_distance)
        bars = trending_up_bars()
        original_bar = bars[-1]
        from auto_trader.models.market_data import BarData
        
        current_bar = BarData(
            symbol=original_bar.symbol,
            timestamp=original_bar.timestamp,
            open_price=Decimal("100.40"),
            high_price=Decimal("100.60"),
            low_price=Decimal("100.30"),
            close_price=Decimal("100.50"),  # Only 0.5% above
            volume=original_bar.volume,
            bar_size=original_bar.bar_size,
        )
        
        context = create_execution_context(
            current_bar=current_bar,
            historical_bars=bars[:-1],
            threshold_price=100.0,
            min_distance_percent=1.0,
            max_distance_percent=5.0
        )
        
        signal = await function.evaluate(context)
        assert signal.action == ExecutionAction.NONE
        assert "minimum required" in signal.reasoning
        
        # Test case 2: Price way above threshold (should fail max_distance) 
        current_bar_2 = BarData(
            symbol=original_bar.symbol,
            timestamp=original_bar.timestamp,
            open_price=Decimal("105.50"),
            high_price=Decimal("106.20"),
            low_price=Decimal("105.30"),
            close_price=Decimal("106.00"),  # 6% above
            volume=original_bar.volume,
            bar_size=original_bar.bar_size,
        )
        context_2 = create_execution_context(
            current_bar=current_bar_2,
            historical_bars=bars[:-1],
            threshold_price=100.0,
            min_distance_percent=1.0,
            max_distance_percent=5.0
        )
        signal = await function.evaluate(context_2)
        assert signal.action == ExecutionAction.NONE
        assert "exceeds maximum allowed" in signal.reasoning
        
        # Test case 3: Price in sweet spot (should trigger)
        current_bar_3 = BarData(
            symbol=original_bar.symbol,
            timestamp=original_bar.timestamp,
            open_price=Decimal("102.50"),
            high_price=Decimal("103.20"),
            low_price=Decimal("102.30"),
            close_price=Decimal("103.00"),  # 3% above
            volume=original_bar.volume,
            bar_size=original_bar.bar_size,
        )
        context_3 = create_execution_context(
            current_bar=current_bar_3,
            historical_bars=bars[:-1],
            threshold_price=100.0,
            min_distance_percent=1.0,
            max_distance_percent=5.0
        )
        signal = await function.evaluate(context_3)
        assert signal.action == ExecutionAction.ENTER_LONG


class TestMarketScenarios:
    """Test execution functions across different market scenarios."""
    
    @pytest.mark.asyncio
    async def test_trending_market_scenarios(self, trending_up_bars, trending_down_bars):
        """Test functions in trending markets."""
        # Close above in uptrend should work well
        close_above_config = ExecutionFunctionConfig(
            name="trend_test",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 105.0},
        )
        close_above_func = CloseAboveFunction(close_above_config)
        
        current_bar = trending_up_bars[-1]
        current_bar.close_price = Decimal("105.50")  # Above threshold
        
        context = create_execution_context(
            current_bar=current_bar,
            historical_bars=trending_up_bars[:-1],
            threshold_price=105.0
        )
        
        signal = await close_above_func.evaluate(context)
        
        assert signal.action == ExecutionAction.ENTER_LONG
        assert signal.confidence > 0.6  # Should have good confidence in trend
    
    @pytest.mark.asyncio
    async def test_ranging_market_scenarios(self, ranging_market_bars):
        """Test functions in ranging/sideways markets."""
        close_above_config = ExecutionFunctionConfig(
            name="range_test",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 100.5},
        )
        close_above_func = CloseAboveFunction(close_above_config)
        
        # Test multiple bars in range
        signals = []
        for i in range(5, len(ranging_market_bars)):
            current_bar = ranging_market_bars[i]
            historical_bars = ranging_market_bars[:i]
            
            context = create_execution_context(
                current_bar=current_bar,
                historical_bars=historical_bars,
                threshold_price=100.5
            )
            
            signal = await close_above_func.evaluate(context)
            signals.append(signal)
        
        # In ranging market, should have mixed signals
        triggered_signals = [s for s in signals if s.action != ExecutionAction.NONE]
        # Some signals should trigger, but not all
        assert 0 < len(triggered_signals) < len(signals)
    
    @pytest.mark.asyncio
    async def test_volatile_market_scenarios(self, volatile_market_bars):
        """Test functions in volatile markets with gaps."""
        close_above_config = ExecutionFunctionConfig(
            name="volatile_test",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 100.0},
        )
        close_above_func = CloseAboveFunction(close_above_config)
        
        # Test each bar to see how edge cases are handled
        for i in range(5, len(volatile_market_bars)):
            current_bar = volatile_market_bars[i]
            historical_bars = volatile_market_bars[:i]
            
            context = create_execution_context(
                current_bar=current_bar,
                historical_bars=historical_bars,
                threshold_price=100.0
            )
            
            signal = await close_above_func.evaluate(context)
            
            # All evaluations should complete without error
            assert signal is not None
            assert signal.action in [ExecutionAction.NONE, ExecutionAction.ENTER_LONG]
            
            # If it triggers, confidence should reflect the volatility/gaps
            if signal.action != ExecutionAction.NONE:
                # In volatile conditions, confidence might be adjusted
                assert 0.0 < signal.confidence <= 1.0