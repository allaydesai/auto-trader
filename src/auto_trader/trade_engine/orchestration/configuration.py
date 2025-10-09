"""Configuration management for trade orchestration."""

from typing import Optional
from dataclasses import dataclass


@dataclass
class OrchestrationConfig:
    """Configuration for trade orchestration behavior."""
    
    # Risk management settings
    enable_risk_validation: bool = True
    max_concurrent_trades: int = 10
    
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
        if self.config.max_concurrent_trades <= 0:
            return False
            
        if self.config.signal_timeout_seconds <= 0:
            return False
            
        if self.config.state_save_interval_seconds <= 0:
            return False
            
        return True
    
    def get_signal_processor_config(self) -> dict:
        """Get configuration for signal processor.

        Returns:
            Signal processor configuration dictionary
        """
        return {
            "enable_risk_validation": self.config.enable_risk_validation,
            "minimum_confidence_threshold": self.config.minimum_confidence_threshold,
            "enable_signal_filtering": True,  # Default value
        }
    
    def get_performance_config(self) -> dict:
        """Get performance monitoring configuration.
        
        Returns:
            Performance configuration dictionary
        """
        return {
            "max_latency_ms": 1000,  # Default 1 second
            "enable_tracking": True,  # Default enabled
            "detailed_logging": False,  # Default disabled
        }
    
    def get_event_config(self) -> dict:
        """Get event management configuration.
        
        Returns:
            Event configuration dictionary
        """
        return {
            "max_history": 1000,  # Default max events
            "enable_persistence": True,  # Default enabled
        }