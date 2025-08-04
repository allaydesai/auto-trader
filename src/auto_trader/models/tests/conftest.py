"""Shared pytest fixtures for model tests."""

import tempfile
from decimal import Decimal
from pathlib import Path

import pytest
import yaml

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from config import Settings, SystemConfig, UserPreferences


@pytest.fixture
def sample_settings():
    """Provide sample settings for testing."""
    return Settings(
        discord_webhook_url="https://discord.com/api/webhooks/test_webhook",
        ibkr_host="127.0.0.1",
        ibkr_port=7497,
        ibkr_client_id=1,
        simulation_mode=True,
        debug=False
    )


@pytest.fixture
def sample_system_config():
    """Provide sample system configuration for testing."""
    return SystemConfig()


@pytest.fixture
def sample_user_preferences():
    """Provide sample user preferences for testing."""
    return UserPreferences(
        default_account_value=Decimal("10000"),
        default_risk_category="conservative",
        preferred_timeframes=["15min", "1hour"],
        default_execution_functions={"long": "close_above", "short": "close_below"}
    )


@pytest.fixture
def temp_config_directory():
    """Create a temporary directory with sample config files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create .env file
        env_file = temp_path / ".env"
        env_content = """IBKR_HOST=127.0.0.1
IBKR_PORT=7497
IBKR_CLIENT_ID=1
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/test
SIMULATION_MODE=true
DEBUG=false"""
        env_file.write_text(env_content)
        
        # Create config.yaml
        config_file = temp_path / "config.yaml"
        system_config = {
            "ibkr": {
                "host": "127.0.0.1",
                "port": 7497,
                "client_id": 1,
                "timeout": 30
            },
            "risk": {
                "max_position_percent": 10.0,
                "daily_loss_limit_percent": 2.0,
                "max_open_positions": 5,
                "min_account_balance": 1000
            },
            "trading": {
                "simulation_mode": True,
                "market_hours_only": True,
                "default_timeframe": "15min",
                "order_timeout": 60
            },
            "logging": {
                "level": "INFO",
                "rotation": "1 day",
                "retention": "30 days",
                "format": "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line} | {message}"
            }
        }
        with open(config_file, 'w') as f:
            yaml.dump(system_config, f)
        
        # Create user_config.yaml
        user_config_file = temp_path / "user_config.yaml"
        user_config = {
            "default_account_value": 10000,
            "default_risk_category": "conservative",
            "preferred_timeframes": ["15min", "1hour"],
            "default_execution_functions": {
                "long": "close_above",
                "short": "close_below"
            }
        }
        with open(user_config_file, 'w') as f:
            yaml.dump(user_config, f)
        
        yield temp_path, env_file, config_file, user_config_file


@pytest.fixture
def invalid_yaml_config():
    """Create a temporary directory with invalid YAML config."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create invalid YAML file
        config_file = temp_path / "config.yaml"
        config_file.write_text("invalid: yaml: [unclosed bracket")
        
        yield temp_path, config_file


@pytest.fixture
def missing_required_config():
    """Create config with missing required fields."""
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create config with missing Discord webhook
        env_file = temp_path / ".env"
        env_content = """IBKR_HOST=127.0.0.1
IBKR_PORT=7497
IBKR_CLIENT_ID=1
# DISCORD_WEBHOOK_URL is missing
SIMULATION_MODE=true"""
        env_file.write_text(env_content)
        
        yield temp_path, env_file