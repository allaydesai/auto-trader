"""Tests for configuration management."""

import tempfile
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

from auto_trader import (
    Settings,
    ConfigLoader,
    SystemConfig,
    UserPreferences,
    IBKRConfig,
    RiskConfig,
    TradingConfig,
    LoggingConfig
)


class TestSettings:
    """Test settings loading from environment variables."""
    
    def test_default_settings(self):
        """Test settings with default values."""
        settings = Settings(
            discord_webhook_url="https://discord.com/api/webhooks/test"
        )
        
        assert settings.ibkr_host == "127.0.0.1"
        assert settings.ibkr_port == 7497
        assert settings.ibkr_client_id == 1
        assert settings.simulation_mode is True
        assert settings.debug is False
        assert settings.config_file == Path("config.yaml").resolve()
        assert settings.user_config_file == Path("user_config.yaml").resolve()
        assert settings.logs_dir == Path("logs").resolve()
    
    def test_settings_from_env(self, monkeypatch):
        """Test settings loaded from environment variables."""
        monkeypatch.setenv("IBKR_HOST", "192.168.1.100")
        monkeypatch.setenv("IBKR_PORT", "7496")
        monkeypatch.setenv("IBKR_CLIENT_ID", "2")
        monkeypatch.setenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/custom")
        monkeypatch.setenv("SIMULATION_MODE", "false")
        monkeypatch.setenv("DEBUG", "true")
        
        settings = Settings()
        
        assert settings.ibkr_host == "192.168.1.100"
        assert settings.ibkr_port == 7496
        assert settings.ibkr_client_id == 2
        assert settings.discord_webhook_url == "https://discord.com/api/webhooks/custom"
        assert settings.simulation_mode is False
        assert settings.debug is True
    
    def test_path_validation(self):
        """Test path validation for relative paths."""
        settings = Settings(
            discord_webhook_url="https://discord.com/api/webhooks/test",
            config_file=Path("custom_config.yaml"),
            logs_dir=Path("custom_logs")
        )
        
        # Paths should be converted to absolute
        assert settings.config_file.is_absolute()
        assert settings.logs_dir.is_absolute()


class TestSystemConfig:
    """Test system configuration models."""
    
    def test_default_system_config(self):
        """Test system config with default values."""
        config = SystemConfig()
        
        assert config.ibkr.host == "127.0.0.1"
        assert config.ibkr.port == 7497
        assert config.risk.max_position_percent == 10.0
        assert config.trading.simulation_mode is True
        assert config.logging.level == "INFO"
    
    def test_custom_system_config(self):
        """Test system config with custom values."""
        config_data = {
            "ibkr": {"host": "192.168.1.100", "port": 7496},
            "risk": {"max_position_percent": 5.0, "daily_loss_limit_percent": 1.0},
            "trading": {"simulation_mode": False, "default_timeframe": "5min"},
            "logging": {"level": "DEBUG", "rotation": "6 hours"}
        }
        
        config = SystemConfig(**config_data)
        
        assert config.ibkr.host == "192.168.1.100"
        assert config.ibkr.port == 7496
        assert config.risk.max_position_percent == 5.0
        assert config.risk.daily_loss_limit_percent == 1.0
        assert config.trading.simulation_mode is False
        assert config.trading.default_timeframe == "5min"
        assert config.logging.level == "DEBUG"
        assert config.logging.rotation == "6 hours"
    
    def test_risk_config_validation(self):
        """Test risk configuration validation."""
        # Valid configuration
        risk_config = RiskConfig(
            max_position_percent=15.0,
            daily_loss_limit_percent=3.0,
            max_open_positions=10,
            min_account_balance=Decimal("5000")
        )
        assert risk_config.max_position_percent == 15.0
        
        # Test validation ranges
        with pytest.raises(ValueError):
            RiskConfig(max_position_percent=0.05)  # Below minimum
        
        with pytest.raises(ValueError):
            RiskConfig(max_position_percent=60.0)  # Above maximum
        
        with pytest.raises(ValueError):
            RiskConfig(daily_loss_limit_percent=0.05)  # Below minimum
        
        with pytest.raises(ValueError):
            RiskConfig(max_open_positions=0)  # Below minimum


class TestUserPreferences:
    """Test user preferences model."""
    
    def test_default_user_preferences(self):
        """Test user preferences with default values."""
        prefs = UserPreferences()
        
        assert prefs.default_account_value == Decimal("10000")
        assert prefs.default_risk_category == "conservative"
        assert prefs.preferred_timeframes == ["15min", "1hour"]
        assert prefs.default_execution_functions == {"long": "close_above", "short": "close_below"}
    
    def test_custom_user_preferences(self):
        """Test user preferences with custom values."""
        prefs_data = {
            "default_account_value": 50000,
            "default_risk_category": "aggressive",
            "preferred_timeframes": ["5min", "30min"],
            "default_execution_functions": {"long": "trailing_stop", "short": "trailing_stop"}
        }
        
        prefs = UserPreferences(**prefs_data)
        
        assert prefs.default_account_value == Decimal("50000")
        assert prefs.default_risk_category == "aggressive"
        assert prefs.preferred_timeframes == ["5min", "30min"]
        assert prefs.default_execution_functions["long"] == "trailing_stop"
    
    def test_risk_category_validation(self):
        """Test risk category validation."""
        # Valid categories
        for category in ["conservative", "moderate", "aggressive"]:
            prefs = UserPreferences(default_risk_category=category)
            assert prefs.default_risk_category == category
        
        # Invalid category
        with pytest.raises(ValueError):
            UserPreferences(default_risk_category="invalid")


class TestConfigLoader:
    """Test configuration loader functionality."""
    
    @pytest.fixture
    def temp_config_files(self):
        """Create temporary configuration files for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create system config file
            system_config = {
                "ibkr": {"host": "test.host", "port": 7498},
                "risk": {"max_position_percent": 8.0},
                "trading": {"simulation_mode": True},
                "logging": {"level": "DEBUG"}
            }
            config_file = temp_path / "config.yaml"
            with open(config_file, 'w') as f:
                yaml.dump(system_config, f)
            
            # Create user config file
            user_config = {
                "default_account_value": 25000,
                "default_risk_category": "moderate",
                "preferred_timeframes": ["1min", "5min"]
            }
            user_config_file = temp_path / "user_config.yaml"
            with open(user_config_file, 'w') as f:
                yaml.dump(user_config, f)
            
            # Create settings pointing to temp files
            settings = Settings(
                discord_webhook_url="https://discord.com/api/webhooks/test",
                config_file=config_file,
                user_config_file=user_config_file
            )
            
            yield settings, temp_path
    
    def test_load_system_config_from_file(self, temp_config_files):
        """Test loading system configuration from file."""
        settings, _ = temp_config_files
        loader = ConfigLoader(settings)
        
        config = loader.load_system_config()
        
        assert config.ibkr.host == "test.host"
        assert config.ibkr.port == 7498
        assert config.risk.max_position_percent == 8.0
        assert config.logging.level == "DEBUG"
    
    def test_load_user_preferences_from_file(self, temp_config_files):
        """Test loading user preferences from file."""
        settings, _ = temp_config_files
        loader = ConfigLoader(settings)
        
        prefs = loader.load_user_preferences()
        
        assert prefs.default_account_value == Decimal("25000")
        assert prefs.default_risk_category == "moderate"
        assert prefs.preferred_timeframes == ["1min", "5min"]
    
    def test_load_config_missing_files(self):
        """Test loading configuration when files don't exist."""
        settings = Settings(
            discord_webhook_url="https://discord.com/api/webhooks/test",
            config_file=Path("/nonexistent/config.yaml"),
            user_config_file=Path("/nonexistent/user_config.yaml")
        )
        loader = ConfigLoader(settings)
        
        # Should return default configurations
        config = loader.load_system_config()
        prefs = loader.load_user_preferences()
        
        assert isinstance(config, SystemConfig)
        assert isinstance(prefs, UserPreferences)
        assert config.ibkr.host == "127.0.0.1"  # Default value
        assert prefs.default_account_value == Decimal("10000")  # Default value
    
    def test_validate_configuration_success(self, temp_config_files):
        """Test successful configuration validation."""
        settings, _ = temp_config_files
        loader = ConfigLoader(settings)
        
        issues = loader.validate_configuration()
        
        assert len(issues) == 0
    
    def test_validate_configuration_missing_webhook(self):
        """Test configuration validation with missing webhook URL."""
        settings = Settings(discord_webhook_url="")  # Empty webhook URL
        loader = ConfigLoader(settings)
        
        issues = loader.validate_configuration()
        
        assert len(issues) > 0
        assert any("Discord webhook URL" in issue for issue in issues)
    
    def test_validate_configuration_account_balance_mismatch(self):
        """Test validation with account balance less than minimum."""
        # Create temporary configs with conflicting values
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # System config with high minimum balance
            system_config = {"risk": {"min_account_balance": 50000}}
            config_file = temp_path / "config.yaml"
            with open(config_file, 'w') as f:
                yaml.dump(system_config, f)
            
            # User config with low account value
            user_config = {"default_account_value": 5000}
            user_config_file = temp_path / "user_config.yaml"
            with open(user_config_file, 'w') as f:
                yaml.dump(user_config, f)
            
            settings = Settings(
                discord_webhook_url="https://discord.com/api/webhooks/test",
                config_file=config_file,
                user_config_file=user_config_file
            )
            loader = ConfigLoader(settings)
            
            issues = loader.validate_configuration()
            
            assert len(issues) > 0
            assert any("account balance" in issue.lower() for issue in issues)
    
    def test_invalid_yaml_handling(self):
        """Test handling of invalid YAML files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create invalid YAML file
            config_file = temp_path / "config.yaml"
            config_file.write_text("invalid: yaml: content: [")
            
            settings = Settings(
                discord_webhook_url="https://discord.com/api/webhooks/test",
                config_file=config_file
            )
            loader = ConfigLoader(settings)
            
            with pytest.raises(ValueError, match="Invalid YAML"):
                loader.load_system_config()


class TestIBKRConfig:
    """Test IBKR configuration model."""
    
    def test_default_ibkr_config(self):
        """Test IBKR config with default values."""
        config = IBKRConfig()
        
        assert config.host == "127.0.0.1"
        assert config.port == 7497
        assert config.client_id == 1
        assert config.timeout == 30
    
    def test_port_validation(self):
        """Test port number validation."""
        # Valid ports
        config = IBKRConfig(port=7496)
        assert config.port == 7496
        
        # Invalid ports
        with pytest.raises(ValueError):
            IBKRConfig(port=80)  # Below minimum
        
        with pytest.raises(ValueError):
            IBKRConfig(port=70000)  # Above maximum
    
    def test_client_id_validation(self):
        """Test client ID validation."""
        # Valid client IDs
        config = IBKRConfig(client_id=999)
        assert config.client_id == 999
        
        # Invalid client IDs
        with pytest.raises(ValueError):
            IBKRConfig(client_id=0)  # Below minimum
        
        with pytest.raises(ValueError):
            IBKRConfig(client_id=1000)  # Above maximum


class TestTradingConfig:
    """Test trading configuration model."""
    
    def test_default_trading_config(self):
        """Test trading config with default values."""
        config = TradingConfig()
        
        assert config.simulation_mode is True
        assert config.market_hours_only is True
        assert config.default_timeframe == "15min"
        assert config.order_timeout == 60
    
    def test_order_timeout_validation(self):
        """Test order timeout validation."""
        # Valid timeouts
        config = TradingConfig(order_timeout=120)
        assert config.order_timeout == 120
        
        # Invalid timeouts
        with pytest.raises(ValueError):
            TradingConfig(order_timeout=5)  # Below minimum
        
        with pytest.raises(ValueError):
            TradingConfig(order_timeout=400)  # Above maximum


class TestLoggingConfig:
    """Test logging configuration model."""
    
    def test_default_logging_config(self):
        """Test logging config with default values."""
        config = LoggingConfig()
        
        assert config.level == "INFO"
        assert config.rotation == "1 day"
        assert config.retention == "30 days"
        assert "{time:" in config.format
    
    def test_log_level_validation(self):
        """Test log level validation."""
        # Valid levels
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            config = LoggingConfig(level=level)
            assert config.level == level
        
        # Invalid level
        with pytest.raises(ValueError):
            LoggingConfig(level="INVALID")