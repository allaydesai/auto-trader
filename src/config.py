"""Configuration management with pydantic Settings."""

from decimal import Decimal
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
import yaml


class IBKRConfig(BaseModel):
    """Interactive Brokers configuration."""

    host: str = Field(default="127.0.0.1", description="IBKR TWS/Gateway host")
    port: int = Field(
        default=7497, ge=1024, le=65535, description="IBKR TWS/Gateway port"
    )
    client_id: int = Field(default=1, ge=1, le=999, description="IBKR client ID")
    timeout: int = Field(
        default=30, ge=5, le=300, description="Connection timeout in seconds"
    )
    reconnect_attempts: int = Field(
        default=5, ge=1, le=10, description="Maximum reconnection attempts"
    )
    graceful_shutdown: bool = Field(
        default=True, description="Close positions on shutdown"
    )


class RiskConfig(BaseModel):
    """Risk management configuration."""

    max_position_percent: float = Field(
        default=10.0, ge=0.1, le=50.0, description="Max position size as % of account"
    )
    daily_loss_limit_percent: float = Field(
        default=2.0, ge=0.1, le=10.0, description="Daily loss limit as % of account"
    )
    max_open_positions: int = Field(
        default=5, ge=1, le=20, description="Maximum number of open positions"
    )
    min_account_balance: Decimal = Field(
        default=Decimal("1000"), ge=0, description="Minimum account balance required"
    )


class TradingConfig(BaseModel):
    """Trading system configuration."""

    simulation_mode: bool = Field(default=True, description="Enable simulation mode")
    market_hours_only: bool = Field(
        default=True, description="Trade only during market hours"
    )
    default_timeframe: str = Field(
        default="15min", description="Default execution timeframe"
    )
    order_timeout: int = Field(
        default=60, ge=10, le=300, description="Order timeout in seconds"
    )


class LoggingConfig(BaseModel):
    """Logging configuration."""

    level: str = Field(default="INFO", pattern="^(DEBUG|INFO|WARNING|ERROR|CRITICAL)$")
    rotation: str = Field(default="1 day", description="Log rotation frequency")
    retention: str = Field(default="30 days", description="Log retention period")
    format: str = Field(
        default="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line} | {message}",
        description="Log format string",
    )


class SystemConfig(BaseModel):
    """System-wide configuration from config.yaml."""

    ibkr: IBKRConfig = Field(default_factory=IBKRConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    trading: TradingConfig = Field(default_factory=TradingConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)


class UserPreferences(BaseModel):
    """User-specific preferences from user_config.yaml."""

    # Account and Risk Configuration  
    account_value: Decimal = Field(
        default=Decimal("10000"),
        ge=1000,
        description="Total account balance for position sizing calculations",
    )
    default_risk_category: str = Field(
        default="normal", 
        pattern="^(small|normal|large)$",
        description="Default risk level for new trade plans"
    )
    
    # Trading Preferences
    preferred_timeframes: list[str] = Field(
        default=["15min", "30min"], 
        description="Default timeframes for execution functions"
    )
    default_entry_function: str = Field(
        default="close_above",
        description="Preferred entry execution function type"
    )
    default_exit_function: str = Field(
        default="take_profit_stop_loss",
        description="Preferred exit execution function type"
    )
    
    # Environment Configuration
    environment: str = Field(
        default="paper",
        pattern="^(paper|live)$", 
        description="Trading environment preference"
    )
    
    # Legacy Support (maintained for backward compatibility)
    default_account_value: Optional[Decimal] = Field(
        default=None,
        description="DEPRECATED: Use account_value instead",
    )
    default_execution_functions: dict[str, str] = Field(
        default_factory=lambda: {"long": "close_above", "short": "close_below"},
        description="DEPRECATED: Use default_entry_function instead",
    )
    
    @field_validator('preferred_timeframes')
    @classmethod 
    def validate_timeframes(cls, v):
        """Validate timeframe formats."""
        valid_timeframes = ['1min', '5min', '15min', '30min', '1h', '2h', '4h', '1d']
        for timeframe in v:
            if timeframe not in valid_timeframes:
                raise ValueError(f"Invalid timeframe '{timeframe}'. Must be one of: {valid_timeframes}")
        return v


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # IBKR Credentials
    ibkr_host: str = Field(default="127.0.0.1")
    ibkr_port: int = Field(default=7497)
    ibkr_client_id: int = Field(default=1)

    # Discord Integration
    discord_webhook_url: Optional[str] = Field(
        None, description="Discord webhook URL for notifications"
    )

    # System Settings
    simulation_mode: bool = Field(default=True, description="Enable simulation mode")
    debug: bool = Field(default=False, description="Enable debug logging")

    # File Paths
    config_file: Path = Field(
        default=Path("config.yaml"), description="System config file path"
    )
    user_config_file: Path = Field(
        default=Path("user_config.yaml"), description="User preferences file path"
    )
    logs_dir: Path = Field(default=Path("logs"), description="Logs directory path")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        validate_assignment=True,
        str_strip_whitespace=True,
        extra="ignore",
    )

    @field_validator("logs_dir", "config_file", "user_config_file")
    @classmethod
    def validate_paths(cls, v: Path) -> Path:
        """Ensure paths are absolute."""
        if not v.is_absolute():
            return Path.cwd() / v
        return v


class ConfigLoader:
    """Configuration loader with validation and error handling."""

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize configuration loader."""
        self.settings = settings or Settings()
        self._system_config: Optional[SystemConfig] = None
        self._user_preferences: Optional[UserPreferences] = None

    def load_system_config(self) -> SystemConfig:
        """Load system configuration from config.yaml."""
        if self._system_config is not None:
            return self._system_config

        try:
            if self.settings.config_file.exists():
                with open(self.settings.config_file, "r") as f:
                    config_data = yaml.safe_load(f) or {}
                self._system_config = SystemConfig(**config_data)
            else:
                self._system_config = SystemConfig()

        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {self.settings.config_file}: {e}")
        except Exception as e:
            raise ValueError(f"Failed to load system config: {e}")

        return self._system_config

    def load_user_preferences(self) -> UserPreferences:
        """Load user preferences from user_config.yaml."""
        if self._user_preferences is not None:
            return self._user_preferences

        try:
            if self.settings.user_config_file.exists():
                with open(self.settings.user_config_file, "r") as f:
                    config_data = yaml.safe_load(f) or {}
                self._user_preferences = UserPreferences(**config_data)
            else:
                self._user_preferences = UserPreferences()

        except yaml.YAMLError as e:
            raise ValueError(f"Invalid YAML in {self.settings.user_config_file}: {e}")
        except Exception as e:
            raise ValueError(f"Failed to load user preferences: {e}")

        return self._user_preferences

    def validate_configuration(self) -> list[str]:
        """Validate complete configuration and return any issues."""
        issues = []

        try:
            # Validate environment settings
            if not self.settings.discord_webhook_url:
                issues.append("Discord webhook URL is required")

            # Validate system config
            system_config = self.load_system_config()

            # Validate user preferences
            user_preferences = self.load_user_preferences()

            # Cross-validation checks
            if (
                system_config.risk.min_account_balance
                > user_preferences.account_value
            ):
                issues.append(
                    f"Minimum account balance ({system_config.risk.min_account_balance}) "
                    f"exceeds account value ({user_preferences.account_value})"
                )

        except Exception as e:
            issues.append(f"Configuration validation error: {e}")

        return issues

    @property
    def system_config(self) -> SystemConfig:
        """Get system configuration."""
        return self.load_system_config()

    @property
    def user_preferences(self) -> UserPreferences:
        """Get user preferences."""
        return self.load_user_preferences()


# Global configuration loader instance - initialized lazily to avoid validation during import
config_loader = None


def get_config_loader() -> ConfigLoader:
    """Get or create the global configuration loader."""
    global config_loader
    if config_loader is None:
        config_loader = ConfigLoader()
    return config_loader
