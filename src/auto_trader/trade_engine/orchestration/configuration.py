"""Configuration management for trade orchestration."""

from typing import Optional
from dataclasses import dataclass


@dataclass
class OrchestrationConfig:
    """Configuration for trade orchestration behavior."""
    
    # Risk management settings
    enable_risk_validation: bool = True
    max_concurrent_positions: int = 10
    
    # Signal processing settings
    signal_confidence_threshold: float = 0.7
    enable_signal_filtering: bool = True
    
    # Performance settings
    max_processing_latency_ms: int = 1000
    batch_processing_enabled: bool = False
    
    # Monitoring settings
    enable_performance_tracking: bool = True
    log_detailed_metrics: bool = False
    
    # Event management settings
    max_event_history: int = 1000
    enable_event_persistence: bool = True


class ConfigurationManager:
    """Manages orchestration configuration and validation."""
    
    def __init__(self, config: Optional[OrchestrationConfig] = None):
        """Initialize configuration manager.
        
        Args:
            config: Orchestration configuration
        """
        self.config = config or OrchestrationConfig()
        
    def validate_configuration(self) -> bool:
        """Validate configuration settings.
        
        Returns:
            True if configuration is valid
        """
        if self.config.max_concurrent_positions <= 0:
            return False
            
        if not (0.0 <= self.config.signal_confidence_threshold <= 1.0):
            return False
            
        if self.config.max_processing_latency_ms <= 0:
            return False
            
        if self.config.max_event_history <= 0:
            return False
            
        return True
    
    def get_signal_processor_config(self) -> dict:
        """Get configuration for signal processor.
        
        Returns:
            Signal processor configuration dictionary
        """
        return {
            "enable_risk_validation": self.config.enable_risk_validation,
            "confidence_threshold": self.config.signal_confidence_threshold,
            "enable_filtering": self.config.enable_signal_filtering,
        }
    
    def get_performance_config(self) -> dict:
        """Get performance monitoring configuration.
        
        Returns:
            Performance configuration dictionary
        """
        return {
            "max_latency_ms": self.config.max_processing_latency_ms,
            "enable_tracking": self.config.enable_performance_tracking,
            "detailed_logging": self.config.log_detailed_metrics,
        }
    
    def get_event_config(self) -> dict:
        """Get event management configuration.
        
        Returns:
            Event configuration dictionary
        """
        return {
            "max_history": self.config.max_event_history,
            "enable_persistence": self.config.enable_event_persistence,
        }