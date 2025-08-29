"""Edge case detection utility for execution functions."""

from dataclasses import dataclass
from decimal import Decimal
from typing import List, Optional, TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from auto_trader.models.market_data import BarData


@dataclass(frozen=True)
class EdgeCaseResult:
    """Result of edge case detection."""
    
    has_edge_case: bool
    case_type: str
    severity: str  # "low", "medium", "high"
    description: str
    recommended_action: str


class EdgeCaseDetector:
    """Utility class for detecting market edge cases that affect execution functions."""
    
    def __init__(
        self,
        gap_threshold_percent: float = 2.0,
        limit_move_percent: float = 10.0,
        volume_spike_threshold: float = 5.0,
        min_volume_threshold: int = 1000,
    ):
        """Initialize edge case detector with thresholds.
        
        Args:
            gap_threshold_percent: Percentage gap to consider significant
            limit_move_percent: Daily move percentage to consider limit-like
            volume_spike_threshold: Volume spike multiplier threshold
            min_volume_threshold: Minimum volume to consider valid data
        """
        self.gap_threshold_percent = Decimal(str(gap_threshold_percent))
        self.limit_move_percent = Decimal(str(limit_move_percent))
        self.volume_spike_threshold = volume_spike_threshold
        self.min_volume_threshold = min_volume_threshold
    
    def detect_all_edge_cases(
        self,
        current_bar: "BarData",
        historical_bars: List["BarData"],
    ) -> List[EdgeCaseResult]:
        """Detect all edge cases for current bar.
        
        Args:
            current_bar: Current bar data
            historical_bars: Historical bar data for context
            
        Returns:
            List of detected edge cases
        """
        edge_cases = []
        
        # Check data quality first
        data_quality = self.check_data_quality(current_bar)
        if data_quality.has_edge_case:
            edge_cases.append(data_quality)
        
        # Check for gaps if we have previous data
        if historical_bars:
            gap_result = self.detect_gap(current_bar, historical_bars[-1])
            if gap_result.has_edge_case:
                edge_cases.append(gap_result)
        
        # Check for limit-like moves
        if historical_bars:
            limit_result = self.detect_limit_move(current_bar, historical_bars)
            if limit_result.has_edge_case:
                edge_cases.append(limit_result)
        
        # Check for volume anomalies
        if len(historical_bars) >= 20:
            volume_result = self.detect_volume_anomaly(current_bar, historical_bars)
            if volume_result.has_edge_case:
                edge_cases.append(volume_result)
        
        return edge_cases
    
    def check_data_quality(self, bar: "BarData") -> EdgeCaseResult:
        """Check for basic data quality issues.
        
        Args:
            bar: Bar data to validate
            
        Returns:
            Edge case result
        """
        # Check for null or zero prices
        if any(price <= 0 for price in [bar.open_price, bar.high_price, 
                                       bar.low_price, bar.close_price]):
            return EdgeCaseResult(
                has_edge_case=True,
                case_type="invalid_price",
                severity="high",
                description="Bar contains zero or negative prices",
                recommended_action="skip_evaluation"
            )
        
        # Check price relationships
        if bar.high_price < bar.low_price:
            return EdgeCaseResult(
                has_edge_case=True,
                case_type="invalid_ohlc",
                severity="high",
                description="High price is below low price",
                recommended_action="skip_evaluation"
            )
        
        if not (bar.low_price <= bar.open_price <= bar.high_price):
            return EdgeCaseResult(
                has_edge_case=True,
                case_type="invalid_ohlc",
                severity="high",
                description="Open price outside high-low range",
                recommended_action="skip_evaluation"
            )
        
        if not (bar.low_price <= bar.close_price <= bar.high_price):
            return EdgeCaseResult(
                has_edge_case=True,
                case_type="invalid_ohlc",
                severity="high",
                description="Close price outside high-low range",
                recommended_action="skip_evaluation"
            )
        
        # Check volume
        if bar.volume < self.min_volume_threshold:
            return EdgeCaseResult(
                has_edge_case=True,
                case_type="low_volume",
                severity="low",
                description=f"Volume {bar.volume:,} below threshold {self.min_volume_threshold:,}",
                recommended_action="reduce_confidence"
            )
        
        return EdgeCaseResult(
            has_edge_case=False,
            case_type="none",
            severity="none",
            description="Data quality checks passed",
            recommended_action="continue"
        )
    
    def detect_gap(
        self, 
        current_bar: "BarData", 
        previous_bar: "BarData"
    ) -> EdgeCaseResult:
        """Detect price gaps between bars.
        
        Args:
            current_bar: Current bar
            previous_bar: Previous bar
            
        Returns:
            Edge case result
        """
        gap_amount = abs(current_bar.open_price - previous_bar.close_price)
        gap_percent = (gap_amount / previous_bar.close_price) * Decimal("100")
        
        if gap_percent >= self.gap_threshold_percent:
            gap_direction = "up" if current_bar.open_price > previous_bar.close_price else "down"
            severity = "high" if gap_percent >= Decimal("5") else "medium"
            
            return EdgeCaseResult(
                has_edge_case=True,
                case_type=f"gap_{gap_direction}",
                severity=severity,
                description=f"Price gapped {gap_direction} {gap_percent:.2f}% from previous close",
                recommended_action="adjust_confidence" if severity == "medium" else "evaluate_carefully"
            )
        
        return EdgeCaseResult(
            has_edge_case=False,
            case_type="none",
            severity="none", 
            description="No significant gap detected",
            recommended_action="continue"
        )
    
    def detect_limit_move(
        self,
        current_bar: "BarData",
        historical_bars: List["BarData"],
    ) -> EdgeCaseResult:
        """Detect limit up/down type moves.
        
        Args:
            current_bar: Current bar
            historical_bars: Historical bars for reference
            
        Returns:
            Edge case result
        """
        if not historical_bars:
            return EdgeCaseResult(
                has_edge_case=False,
                case_type="none",
                severity="none",
                description="Insufficient data for limit move detection",
                recommended_action="continue"
            )
        
        # Use previous day's close as reference
        reference_close = historical_bars[-1].close_price
        
        # Check current bar's move from reference
        high_move = ((current_bar.high_price - reference_close) / reference_close) * Decimal("100")
        low_move = ((reference_close - current_bar.low_price) / reference_close) * Decimal("100")
        
        max_move = max(high_move, low_move)
        
        if max_move >= self.limit_move_percent:
            move_direction = "up" if high_move > low_move else "down"
            severity = "high" if max_move >= Decimal("15") else "medium"
            
            return EdgeCaseResult(
                has_edge_case=True,
                case_type=f"limit_{move_direction}",
                severity=severity,
                description=f"Large {move_direction} move of {max_move:.2f}% detected",
                recommended_action="evaluate_carefully"
            )
        
        return EdgeCaseResult(
            has_edge_case=False,
            case_type="none",
            severity="none",
            description="No limit-type move detected",
            recommended_action="continue"
        )
    
    def detect_volume_anomaly(
        self,
        current_bar: "BarData", 
        historical_bars: List["BarData"]
    ) -> EdgeCaseResult:
        """Detect volume anomalies.
        
        Args:
            current_bar: Current bar
            historical_bars: Historical bars for average calculation
            
        Returns:
            Edge case result
        """
        if len(historical_bars) < 20:
            return EdgeCaseResult(
                has_edge_case=False,
                case_type="none",
                severity="none",
                description="Insufficient data for volume analysis",
                recommended_action="continue"
            )
        
        # Calculate average volume over last 20 bars
        avg_volume = Decimal(str(sum(bar.volume for bar in historical_bars[-20:]))) / Decimal("20")
        
        if avg_volume == 0:
            return EdgeCaseResult(
                has_edge_case=True,
                case_type="zero_volume",
                severity="medium",
                description="Zero average volume detected",
                recommended_action="reduce_confidence"
            )
        
        volume_ratio = Decimal(str(current_bar.volume)) / avg_volume
        
        if volume_ratio >= Decimal(str(self.volume_spike_threshold)):
            severity = "high" if volume_ratio >= Decimal("10") else "medium"
            
            return EdgeCaseResult(
                has_edge_case=True,
                case_type="volume_spike",
                severity=severity,
                description=f"Volume spike: {volume_ratio:.1f}x average volume",
                recommended_action="increase_confidence" if severity == "medium" else "evaluate_carefully"
            )
        
        if volume_ratio <= Decimal("0.1"):  # Very low volume
            return EdgeCaseResult(
                has_edge_case=True,
                case_type="volume_dry_up",
                severity="medium",
                description=f"Very low volume: {volume_ratio:.1f}x average",
                recommended_action="reduce_confidence"
            )
        
        return EdgeCaseResult(
            has_edge_case=False,
            case_type="none",
            severity="none",
            description="Normal volume detected",
            recommended_action="continue"
        )
    
    def get_confidence_adjustment(self, edge_cases: List[EdgeCaseResult]) -> float:
        """Calculate confidence adjustment based on edge cases.
        
        Args:
            edge_cases: List of detected edge cases
            
        Returns:
            Confidence adjustment factor (0.0 to 1.0)
        """
        if not edge_cases:
            return 1.0
        
        adjustment = 1.0
        
        for case in edge_cases:
            if case.recommended_action == "skip_evaluation":
                return 0.0  # Complete confidence loss
            elif case.recommended_action == "reduce_confidence":
                if case.severity == "high":
                    adjustment *= 0.5
                elif case.severity == "medium":
                    adjustment *= 0.7
                else:
                    adjustment *= 0.9
            elif case.recommended_action == "increase_confidence":
                if case.severity == "medium":
                    adjustment *= 1.2
                    
        return min(1.0, max(0.0, adjustment))
    
    def should_skip_evaluation(self, edge_cases: List[EdgeCaseResult]) -> bool:
        """Check if evaluation should be skipped due to edge cases.
        
        Args:
            edge_cases: List of detected edge cases
            
        Returns:
            True if evaluation should be skipped
        """
        return any(case.recommended_action == "skip_evaluation" for case in edge_cases)
    
    def log_edge_cases(self, edge_cases: List[EdgeCaseResult], symbol: str) -> None:
        """Log detected edge cases.
        
        Args:
            edge_cases: List of edge cases to log
            symbol: Trading symbol
        """
        if not edge_cases:
            return
        
        for case in edge_cases:
            log_level = logger.warning if case.severity == "high" else logger.info
            log_level(
                f"Edge case detected for {symbol}: {case.case_type} - {case.description} "
                f"(severity: {case.severity}, action: {case.recommended_action})"
            )