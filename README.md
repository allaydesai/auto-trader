# Auto-Trader

Personal automated trading system designed to execute discretionary trades with time-based triggers to avoid institutional stop-hunting algorithms.

## Features

- **Candle-Close Execution**: Uses time-based triggers instead of simple price levels to filter market noise
- **Risk Management**: Built-in position sizing and daily loss limits
- **Discord Notifications**: Real-time trade alerts and status updates
- **Simulation Mode**: Test strategies without real money
- **IBKR Integration**: Direct connection to Interactive Brokers for execution
- **Structured Logging**: Comprehensive audit trail with separate log files

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone <repository-url>
cd auto-trader

# Install dependencies with UV
uv sync
```

### 2. Initial Setup

Run the interactive setup wizard:

```bash
uv run python -m auto_trader.cli.commands setup
```

This will create the necessary configuration files:
- `.env` - Environment variables and secrets
- `config.yaml` - System configuration
- `user_config.yaml` - Trading preferences

### 3. Configuration

#### Environment Variables (`.env`)

```bash
# Interactive Brokers
IBKR_HOST=127.0.0.1
IBKR_PORT=7497
IBKR_CLIENT_ID=1

# Discord Integration
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_URL

# System Settings
SIMULATION_MODE=true
DEBUG=false
```

#### System Configuration (`config.yaml`)

```yaml
# Risk Management
risk:
  max_position_percent: 10.0  # Max 10% of account per position
  daily_loss_limit_percent: 2.0  # Stop trading at 2% daily loss
  max_open_positions: 5

# Trading Settings
trading:
  simulation_mode: true  # Set to false for live trading
  market_hours_only: true
  default_timeframe: "15min"
```

#### User Preferences (`user_config.yaml`)

```yaml
# Account Settings
default_account_value: 10000
default_risk_category: "conservative"

# Preferred Settings
preferred_timeframes:
  - "15min"
  - "1hour"

default_execution_functions:
  long: "close_above"
  short: "close_below"
```

### 4. Validation

Verify your configuration:

```bash
uv run python -m auto_trader.cli.commands validate-config --verbose
```

### 5. Running the Application

```bash
# Start the trading system
uv run python -m src.main
```

## Project Structure

```
auto-trader/
├── src/
│   ├── config.py                    # Configuration management
│   ├── main.py                      # Application entry point
│   └── auto_trader/
│       ├── models/                  # Pydantic data models
│       ├── trade_engine/            # Core execution logic
│       ├── integrations/            # External service integrations
│       │   ├── ibkr_client/         # Interactive Brokers API
│       │   └── discord_notifier/    # Discord notifications
│       ├── risk_management/         # Risk validation
│       ├── persistence/             # State management
│       └── cli/                     # Command-line interface
├── logs/                            # Application logs
├── config.yaml                      # System configuration
├── user_config.yaml                 # User preferences
└── .env                            # Environment variables
```

## Configuration Options

### Risk Management

| Setting | Description | Default | Range |
|---------|-------------|---------|--------|
| `max_position_percent` | Maximum position size as % of account | 10.0 | 0.1-50.0 |
| `daily_loss_limit_percent` | Daily loss limit as % of account | 2.0 | 0.1-10.0 |
| `max_open_positions` | Maximum concurrent positions | 5 | 1-20 |
| `min_account_balance` | Minimum account balance required | 1000 | >0 |

### Trading Settings

| Setting | Description | Default | Options |
|---------|-------------|---------|---------|
| `simulation_mode` | Enable paper trading | true | true/false |
| `market_hours_only` | Trade only during market hours | true | true/false |
| `default_timeframe` | Default execution timeframe | "15min" | "1min", "5min", "15min", "1hour" |
| `order_timeout` | Order timeout in seconds | 60 | 10-300 |

### Logging Configuration

| Setting | Description | Default |
|---------|-------------|---------|
| `level` | Log level | "INFO" |
| `rotation` | Log rotation frequency | "1 day" |
| `retention` | Log retention period | "30 days" |

## CLI Commands

### Setup Wizard

```bash
uv run python -m auto_trader.cli.commands setup [--output-dir DIR] [--force]
```

Creates configuration files interactively.

### Configuration Validation

```bash
uv run python -m auto_trader.cli.commands validate-config [--verbose]
```

Validates all configuration files and environment variables.

### Help System

```bash
uv run python -m auto_trader.cli.commands help-system
```

Displays detailed help information.

## Development

### Testing

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test file
uv run pytest src/auto_trader/models/tests/test_config.py
```

### Code Quality

```bash
# Format code
uv run ruff format .

# Check linting
uv run ruff check .

# Type checking
uv run mypy src/
```

### Dependencies

Never edit `pyproject.toml` directly. Always use UV commands:

```bash
# Add dependency
uv add package-name

# Add development dependency
uv add --dev package-name

# Remove dependency
uv remove package-name
```

## Security

- **Never commit secrets**: Use `.env` files (git ignored)
- **Environment isolation**: Separate configs for development/production
- **Credential rotation**: Regularly rotate API keys and webhooks
- **Audit logging**: All trading activities are logged with timestamps

## Troubleshooting

### Common Issues

1. **Configuration validation fails**
   - Check `.env` file exists and has correct values
   - Verify YAML syntax in config files
   - Ensure Discord webhook URL is valid

2. **IBKR connection fails**
   - Verify TWS/Gateway is running
   - Check host/port settings match TWS configuration
   - Ensure client ID is unique

3. **Logging issues**
   - Check `logs/` directory permissions
   - Verify disk space for log files
   - Review log level settings

### Log Files

- `logs/system.log` - General application events
- `logs/trades.log` - All trading activity
- `logs/risk.log` - Risk management events
- `logs/cli.log` - Command-line interface events

## License

This project is for personal use only. Not licensed for commercial distribution.

## Support

For issues and questions, please check:
1. Configuration validation output
2. Application logs in `logs/` directory
3. This README and example configuration files
