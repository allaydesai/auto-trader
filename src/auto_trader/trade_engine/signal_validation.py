"""Signal validation and configuration for signal processing."""

from typing import Dict, Optional, Any
from datetime import datetime, UTC, timedelta

from loguru import logger

from auto_trader.models.execution import ExecutionSignal
from auto_trader.models.trade_plan import TradePlan
from auto_trader.models.order import OrderResult


class SignalProcessingResult:
    """Result of signal processing operation."""
    
    def __init__(
        self,
        success: bool,
        action_taken: str,
        order_result: Optional[OrderResult] = None,
        error_message: Optional[str] = None,
        risk_check_passed: Optional[bool] = None,
        signal_confidence: Optional[float] = None,
        plan_id: Optional[str] = None,
    ):
        """Initialize signal processing result.
        
        Args:
            success: Whether processing was successful
            action_taken: Description of action taken
            order_result: Order execution result if applicable
            error_message: Error message if processing failed
            risk_check_passed: Whether risk validation passed
            signal_confidence: Confidence level of the signal
            plan_id: Associated trade plan ID
        """
        self.success = success
        self.action_taken = action_taken
        self.order_result = order_result
        self.error_message = error_message
        self.risk_check_passed = risk_check_passed
        self.signal_confidence = signal_confidence
        self.plan_id = plan_id
        self.timestamp = datetime.now(UTC)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for logging/serialization.
        
        Returns:
            Result data as dictionary
        """
        return {
            "success": self.success,
            "action_taken": self.action_taken,
            "order_result": self.order_result.to_dict() if hasattr(self.order_result, 'to_dict') else None,
            "error_message": self.error_message,
            "risk_check_passed": self.risk_check_passed,
            "signal_confidence": self.signal_confidence,
            "plan_id": self.plan_id,
            "timestamp": self.timestamp.isoformat(),
        }


class SignalProcessorConfig:
    """Configuration for signal processor."""
    
    def __init__(
        self,
        enable_risk_validation: bool = True,
        minimum_confidence_threshold: float = 0.5,
        max_processing_time_seconds: int = 30,
        enable_signal_filtering: bool = True,
        enable_duplicate_detection: bool = True,
        duplicate_signal_window_seconds: int = 60,
    ):
        """Initialize signal processor config.
        
        Args:
            enable_risk_validation: Enable risk management validation
            minimum_confidence_threshold: Minimum signal confidence to process
            max_processing_time_seconds: Maximum processing time per signal
            enable_signal_filtering: Enable signal quality filtering
            enable_duplicate_detection: Enable duplicate signal detection
            duplicate_signal_window_seconds: Time window for duplicate detection
        """
        self.enable_risk_validation = enable_risk_validation
        self.minimum_confidence_threshold = minimum_confidence_threshold
        self.max_processing_time_seconds = max_processing_time_seconds
        self.enable_signal_filtering = enable_signal_filtering
        self.enable_duplicate_detection = enable_duplicate_detection
        self.duplicate_signal_window_seconds = duplicate_signal_window_seconds
        
        # Validate configuration
        self._validate_config()
    
    def _validate_config(self) -> None:
        """Validate configuration parameters."""
        if not 0 <= self.minimum_confidence_threshold <= 1:
            raise ValueError("minimum_confidence_threshold must be between 0 and 1")
        
        if self.max_processing_time_seconds <= 0:
            raise ValueError("max_processing_time_seconds must be positive")
        
        if self.duplicate_signal_window_seconds <= 0:
            raise ValueError("duplicate_signal_window_seconds must be positive")
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert configuration to dictionary.
        
        Returns:
            Configuration data as dictionary
        """
        return {
            "enable_risk_validation": self.enable_risk_validation,
            "minimum_confidence_threshold": self.minimum_confidence_threshold,
            "max_processing_time_seconds": self.max_processing_time_seconds,
            "enable_signal_filtering": self.enable_signal_filtering,
            "enable_duplicate_detection": self.enable_duplicate_detection,
            "duplicate_signal_window_seconds": self.duplicate_signal_window_seconds,
        }


class SignalValidator:
    """Utility class for validating execution signals."""
    
    def __init__(self, config: SignalProcessorConfig):
        """Initialize signal validator.
        
        Args:
            config: Signal processor configuration
        """
        self.config = config
        self.recent_signals: Dict[str, datetime] = {}
    
    def validate_signal_quality(self, signal: ExecutionSignal, trade_plan: TradePlan) -> bool:
        """Validate signal quality and confidence.
        
        Args:
            signal: Execution signal to validate
            trade_plan: Associated trade plan
            
        Returns:
            True if signal passes quality checks
        """
        if not self.config.enable_signal_filtering:
            return True
        
        # Check confidence threshold
        if signal.confidence < self.config.minimum_confidence_threshold:
            logger.debug(
                f"Signal rejected: confidence {signal.confidence:.2f} below threshold {self.config.minimum_confidence_threshold:.2f}",
                plan_id=trade_plan.plan_id,
            )
            return False
        
        # Check signal has reasoning
        if not signal.reasoning or len(signal.reasoning.strip()) == 0:
            logger.debug(f"Signal rejected: missing reasoning", plan_id=trade_plan.plan_id)
            return False
        
        # Check signal metadata
        if not signal.metadata:
            logger.debug(f"Signal rejected: missing metadata", plan_id=trade_plan.plan_id)
            return False
        
        # Additional quality checks can be added here
        # For example: check for required metadata fields, validate price levels, etc.
        
        return True
    
    def check_duplicate_signal(self, signal: ExecutionSignal, trade_plan: TradePlan) -> bool:
        """Check if signal is a duplicate of recent signals.
        
        Args:
            signal: Execution signal to check
            trade_plan: Associated trade plan
            
        Returns:
            True if signal is a duplicate
        """
        if not self.config.enable_duplicate_detection:
            return False
        
        # Create unique signal identifier
        signal_key = f"{trade_plan.plan_id}_{signal.action.value}_{signal.confidence:.2f}"
        
        current_time = datetime.now(UTC)
        cutoff_time = current_time - timedelta(seconds=self.config.duplicate_signal_window_seconds)
        
        # Clean up old signals
        self._cleanup_old_signals(cutoff_time)
        
        # Check if we've seen this signal recently
        if signal_key in self.recent_signals:
            recent_time = self.recent_signals[signal_key]
            if recent_time > cutoff_time:
                logger.debug(
                    f"Duplicate signal detected for plan {trade_plan.plan_id}",
                    action=signal.action.value,
                    confidence=signal.confidence,
                    last_seen=recent_time.isoformat(),
                )
                return True
        
        # Record this signal
        self.recent_signals[signal_key] = current_time
        return False
    
    def _cleanup_old_signals(self, cutoff_time: datetime) -> None:
        """Remove old signals from tracking.
        
        Args:
            cutoff_time: Remove signals older than this time
        """
        signals_to_remove = [
            key for key, timestamp in self.recent_signals.items()
            if timestamp <= cutoff_time
        ]
        
        for key in signals_to_remove:
            del self.recent_signals[key]
        
        if signals_to_remove:
            logger.debug(f"Cleaned up {len(signals_to_remove)} old signal records")
    
    def record_signal(self, signal: ExecutionSignal, trade_plan: TradePlan) -> None:
        """Record a signal for duplicate detection.
        
        Args:
            signal: Execution signal to record
            trade_plan: Associated trade plan
        """
        if not self.config.enable_duplicate_detection:
            return
        
        signal_key = f"{trade_plan.plan_id}_{signal.action.value}_{signal.confidence:.2f}"
        self.recent_signals[signal_key] = datetime.now(UTC)
    
    def clear_recent_signals(self) -> None:
        """Clear all recent signal records."""
        self.recent_signals.clear()
        logger.debug("Cleared all recent signal records")
    
    def get_validation_statistics(self) -> Dict[str, Any]:
        """Get validation statistics.
        
        Returns:
            Dictionary with validation statistics
        """
        return {
            "recent_signals_count": len(self.recent_signals),
            "config": self.config.to_dict(),
            "oldest_signal": min(self.recent_signals.values()).isoformat() if self.recent_signals else None,
            "newest_signal": max(self.recent_signals.values()).isoformat() if self.recent_signals else None,
        }