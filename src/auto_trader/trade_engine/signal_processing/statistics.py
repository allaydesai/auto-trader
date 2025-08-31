"""Statistics tracking for signal processing."""

from typing import Dict, Any
from loguru import logger

from auto_trader.trade_engine.signal_validation import SignalValidator, SignalProcessorConfig


class SignalStatisticsManager:
    """Manages statistics for signal processing operations."""
    
    def __init__(self, config: SignalProcessorConfig, validator: SignalValidator):
        """Initialize statistics manager.
        
        Args:
            config: Signal processor configuration
            validator: Signal validator instance
        """
        self.config = config
        self.validator = validator
        self.processing_stats = {
            "signals_processed": 0,
            "signals_executed": 0,
            "signals_rejected": 0,
            "risk_failures": 0,
            "processing_errors": 0,
        }
    
    def record_signal_processed(self) -> None:
        """Record a signal being processed."""
        self.processing_stats["signals_processed"] += 1
    
    def record_signal_executed(self) -> None:
        """Record a signal being executed."""
        self.processing_stats["signals_executed"] += 1
    
    def record_signal_rejected(self) -> None:
        """Record a signal being rejected."""
        self.processing_stats["signals_rejected"] += 1
    
    def record_risk_failure(self) -> None:
        """Record a risk validation failure."""
        self.processing_stats["risk_failures"] += 1
    
    def record_processing_error(self) -> None:
        """Record a processing error."""
        self.processing_stats["processing_errors"] += 1
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """Get signal processing statistics.
        
        Returns:
            Dictionary with processing statistics
        """
        total_signals = self.processing_stats["signals_processed"]
        execution_rate = (
            self.processing_stats["signals_executed"] / total_signals * 100
            if total_signals > 0 else 0
        )
        
        stats = {
            "total_processed": total_signals,
            "executed": self.processing_stats["signals_executed"],
            "rejected": self.processing_stats["signals_rejected"],
            "risk_failures": self.processing_stats["risk_failures"],
            "processing_errors": self.processing_stats["processing_errors"],
            "execution_rate_percent": round(execution_rate, 2),
            "config": {
                "risk_validation_enabled": self.config.enable_risk_validation,
                "minimum_confidence": self.config.minimum_confidence_threshold,
                "signal_filtering_enabled": self.config.enable_signal_filtering,
                "duplicate_detection_enabled": self.config.enable_duplicate_detection,
            },
        }
        
        # Add validator statistics
        stats["validator"] = self.validator.get_validation_statistics()
        return stats
    
    def reset_statistics(self) -> None:
        """Reset processing statistics."""
        self.processing_stats = {
            "signals_processed": 0,
            "signals_executed": 0,
            "signals_rejected": 0,
            "risk_failures": 0,
            "processing_errors": 0,
        }
        
        logger.info("Signal processing statistics reset")
    
    def clear_recent_signals(self) -> None:
        """Clear recent signals cache."""
        self.validator.clear_recent_signals()
        logger.info("Recent signals cache cleared")