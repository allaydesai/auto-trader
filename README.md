# Auto-Trader

Personal automated trading system designed to execute discretionary trades with time-based triggers to avoid institutional stop-hunting algorithms.

## Features

- **Trade Plan Management**: YAML-based trade plan definitions with comprehensive validation
- **Candle-Close Execution**: Uses time-based triggers instead of simple price levels to filter market noise
- **Risk Management**: Built-in position sizing and daily loss limits
- **Discord Notifications**: Real-time trade alerts and status updates
- **Simulation Mode**: Test strategies without real money
- **IBKR Integration**: Direct connection to Interactive Brokers for execution
- **Interactive CLI Wizard**: Step-by-step trade plan creation with real-time validation and risk management
- **Modular CLI Interface**: Rich command-line tools organized into focused modules
- **Live Monitoring**: Real-time dashboard with optimized file watching
- **Performance Optimizations**: AsyncIO improvements for reliable file monitoring
- **Comprehensive Testing**: 179+ tests with 87% code coverage
- **Template System**: Pre-built trade plan templates for quick strategy creation
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

### 4. Create Trade Plans

Create your first trade plan using the interactive wizard:

```bash
# Interactive wizard with real-time validation and risk management
uv run python -m auto_trader.cli.commands create-plan

# Quick creation with CLI shortcuts
uv run python -m auto_trader.cli.commands create-plan --symbol AAPL --entry 180.50 --stop 178.00 --target 185.00 --risk normal

# Create from templates (alternative method)
uv run python -m auto_trader.cli.commands create-plan-template

# List available templates
uv run python -m auto_trader.cli.commands list-templates --verbose
```

### 5. Validation

Verify your configuration and trade plans:

```bash
# Validate system configuration
uv run python -m auto_trader.cli.commands validate-config --verbose

# Validate all trade plans
uv run python -m auto_trader.cli.commands validate-plans --verbose

# List loaded trade plans
uv run python -m auto_trader.cli.commands list-plans --verbose
```

### 6. Monitoring

Monitor your trading system:

```bash
# Start live monitoring dashboard
uv run python -m auto_trader.cli.commands monitor

# View performance summary
uv run python -m auto_trader.cli.commands summary --period week

# Check trade history
uv run python -m auto_trader.cli.commands history --symbol AAPL --days 7
```

### 7. Running the Application

```bash
# Start the trading system
uv run python -m auto_trader.main
```

## Project Structure

```
auto-trader/
├── src/
│   ├── config.py                    # Configuration management
│   ├── main.py                      # Application entry point
│   └── auto_trader/
│       ├── models/                  # Pydantic data models & validation
│       │   ├── trade_plan.py        # Trade plan schema & validation
│       │   ├── validation_engine.py # YAML validation engine
│       │   ├── error_reporting.py   # Enhanced error reporting
│       │   ├── template_manager.py  # Template management
│       │   └── plan_loader.py       # Plan loading & management
│       ├── trade_engine/            # Core execution logic
│       ├── integrations/            # External service integrations
│       │   ├── ibkr_client/         # Interactive Brokers API
│       │   └── discord_notifier/    # Discord notifications
│       ├── risk_management/         # Risk validation
│       ├── persistence/             # State management
│       ├── utils/                   # Utility modules
│       │   ├── file_watcher.py      # File monitoring with AsyncIO optimizations
│       │   └── tests/               # Utility tests
│       └── cli/                     # Modular command-line interface
│           ├── commands.py          # Main CLI entry point (refactored)
│           ├── config_commands.py   # Configuration management commands
│           ├── plan_commands.py     # Trade plan management commands
│           ├── wizard_utils.py      # Interactive wizard utilities
│           ├── template_commands.py # Template-related commands
│           ├── schema_commands.py   # Schema validation commands
│           ├── monitor_commands.py  # Monitoring and analysis commands
│           ├── diagnostic_commands.py # System diagnostic commands
│           ├── help_commands.py     # Help system commands
│           ├── display_utils.py     # Display & formatting utilities
│           ├── file_utils.py        # File creation utilities
│           ├── error_utils.py       # Error handling utilities
│           ├── plan_utils.py        # Plan creation utilities
│           ├── diagnostic_utils.py  # Diagnostic utility functions
│           ├── schema_utils.py      # Schema utility functions
│           ├── watch_utils.py       # File watching utilities
│           └── tests/               # Comprehensive CLI test suite
├── data/
│   └── trade_plans/
│       ├── templates/               # YAML plan templates
│       │   ├── close_above.yaml     # Close above execution template
│       │   ├── close_below.yaml     # Close below execution template
│       │   └── trailing_stop.yaml   # Trailing stop template
│       └── *.yaml                   # Your trade plan files
├── logs/                            # Application logs
├── config.yaml                      # System configuration
├── user_config.yaml                 # User preferences
└── .env                            # Environment variables
```

## Trade Plan Management

The Auto-Trader uses YAML-based trade plans with comprehensive validation and template support.

### Creating Trade Plans

#### Using Interactive Wizard (Recommended)

```bash
# Interactive wizard with real-time validation and risk management
uv run python -m auto_trader.cli.commands create-plan

# Quick creation with CLI shortcuts
uv run python -m auto_trader.cli.commands create-plan --symbol AAPL --entry 180.50 --stop 178.00 --target 185.00 --risk normal

# All available shortcuts
uv run python -m auto_trader.cli.commands create-plan --symbol MSFT --entry 150.25 --stop 148.00 --target 155.00 --risk small --output-dir custom/path
```

#### Using Templates (Alternative)

```bash
# Interactive plan creation from templates
uv run python -m auto_trader.cli.commands create-plan-template

# View available templates
uv run python -m auto_trader.cli.commands list-templates --verbose
```

#### Manual YAML Creation

Create files in `data/trade_plans/` directory:

```yaml
# data/trade_plans/AAPL_20250815_001.yaml
plan_id: "AAPL_20250815_001"
symbol: "AAPL"
entry_level: 180.50
stop_loss: 178.00
take_profit: 185.00
risk_category: "normal"  # small (1%), normal (2%), large (3%)
entry_function:
  function_type: "close_above"
  timeframe: "15min"
  parameters:
    threshold: 180.50
exit_function:
  function_type: "stop_loss_take_profit"
  timeframe: "1min"
  parameters: {}
status: "awaiting_entry"
```

### Trade Plan Validation

```bash
# Validate all trade plans
uv run python -m auto_trader.cli.commands validate-plans --verbose

# Validate specific directory
uv run python -m auto_trader.cli.commands validate-plans --plans-dir /path/to/plans
```

### Managing Trade Plans

```bash
# List all loaded plans
uv run python -m auto_trader.cli.commands list-plans

# Filter by status
uv run python -m auto_trader.cli.commands list-plans --status awaiting_entry

# Filter by symbol
uv run python -m auto_trader.cli.commands list-plans --symbol AAPL --verbose
```

### Execution Functions

| Function Type | Description | Parameters |
|---------------|-------------|------------|
| `close_above` | Execute when price closes above threshold | `threshold`: Price level |
| `close_below` | Execute when price closes below threshold | `threshold`: Price level |
| `trailing_stop` | Dynamic stop loss that trails price | `trail_percent`: Trailing percentage |

### Risk Categories

| Category | Risk Percentage | Use Case |
|----------|----------------|----------|
| `small` | 1% | Conservative positions |
| `normal` | 2% | Standard positions |
| `large` | 3% | High-conviction trades |

### Plan Statuses

| Status | Description |
|--------|-------------|
| `awaiting_entry` | Waiting for entry conditions |
| `position_open` | Active position, monitoring exit |
| `completed` | Position closed successfully |
| `cancelled` | Plan cancelled before execution |
| `error` | Error occurred during execution |

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

The Auto-Trader provides a comprehensive, modular CLI interface organized into focused command groups for better maintainability.

### Configuration Commands

```bash
# Interactive setup wizard
uv run python -m auto_trader.cli.commands setup [--output-dir DIR] [--force]

# Validate system configuration  
uv run python -m auto_trader.cli.commands validate-config [--verbose]
```

### Trade Plan Commands

```bash
# Interactive wizard with real-time validation and risk management
uv run python -m auto_trader.cli.commands create-plan [--symbol SYMBOL] [--entry PRICE] [--stop PRICE] [--target PRICE] [--risk CATEGORY] [--output-dir DIR]

# Create new trade plan from template (alternative)
uv run python -m auto_trader.cli.commands create-plan-template [--output-dir DIR]

# List available templates
uv run python -m auto_trader.cli.commands list-templates [--verbose]

# Validate trade plans
uv run python -m auto_trader.cli.commands validate-plans [--plans-dir DIR] [--verbose]

# List loaded trade plans
uv run python -m auto_trader.cli.commands list-plans [--status STATUS] [--symbol SYMBOL] [--verbose]
```

### Schema & Template Commands

```bash
# Show trade plan schema documentation
uv run python -m auto_trader.cli.commands show-schema [--field FIELD]

# List template documentation
uv run python -m auto_trader.cli.commands list-templates --verbose
```

### Monitoring & Analysis Commands

```bash
# Live monitoring dashboard with optimized file watching
uv run python -m auto_trader.cli.commands monitor [--plans-dir DIR] [--refresh-rate SECONDS]

# Performance summary
uv run python -m auto_trader.cli.commands summary [--period day|week|month] [--format console|csv]

# Trade history
uv run python -m auto_trader.cli.commands history [--symbol SYMBOL] [--days DAYS] [--format console|csv]
```

### Diagnostic Commands

```bash
# System health check
uv run python -m auto_trader.cli.commands doctor [--config] [--plans] [--permissions] [--export-debug]
```

### Help System

```bash
# Comprehensive help information
uv run python -m auto_trader.cli.commands help-system

# Command-specific help
uv run python -m auto_trader.cli.commands COMMAND --help
```

## Interactive CLI Wizard

The Auto-Trader features an advanced interactive CLI wizard for creating trade plans with real-time validation and risk management integration.

### Key Features

- **Real-time Validation**: Each field is validated immediately using the TradePlan model
- **Risk Management Integration**: Live position sizing calculations and portfolio risk checks
- **Portfolio Risk Protection**: Enforces 10% maximum portfolio risk limit
- **CLI Shortcuts**: Pre-populate fields with command-line arguments
- **Rich Terminal Experience**: Colors, tables, and progress indicators
- **Error Recovery**: Clear guidance for validation errors with retry options

### Wizard Flow

1. **Portfolio Status**: Shows current risk capacity and open positions
2. **Symbol Entry**: Validates trading symbol format (1-10 uppercase chars)
3. **Entry Level**: Validates positive price with max 4 decimal places
4. **Stop Loss**: Validates stop level and calculates stop distance percentage
5. **Risk Category**: Select from small (1%), normal (2%), or large (3%)
6. **Position Sizing**: Real-time calculation with risk breakdown display
7. **Take Profit**: Validates target and shows risk:reward ratio
8. **Execution Functions**: Configure entry/exit triggers and timeframes
9. **Plan Preview**: Rich-formatted summary with modification options
10. **Save Confirmation**: YAML file generation with unique plan ID

### CLI Shortcuts

```bash
# Full wizard experience
uv run python -m auto_trader.cli.commands create-plan

# Pre-populate specific fields
uv run python -m auto_trader.cli.commands create-plan --symbol AAPL --entry 180.50

# Minimal input required
uv run python -m auto_trader.cli.commands create-plan --symbol MSFT --entry 150.25 --stop 148.00 --target 155.00 --risk normal

# Custom output location
uv run python -m auto_trader.cli.commands create-plan --output-dir custom/plans
```

### Risk Management Features

- **Portfolio Overview**: Current risk usage and available capacity
- **Real-time Calculations**: Position size updates as you enter prices
- **Risk Limit Enforcement**: Hard block at 10% portfolio risk with override option
- **Risk Breakdown**: Shows individual trade risk + current portfolio risk + new total
- **Adjustment Suggestions**: Recommendations when limits are exceeded

## Recent Improvements

### Interactive CLI Wizard (v2.0.0)
Complete interactive wizard implementation with comprehensive features:

- **Real-time Validation**: Field-by-field validation with immediate feedback
- **Risk Management Integration**: Live position sizing with portfolio risk protection
- **CLI Shortcuts**: Full command-line argument support for quick creation
- **Rich Terminal UX**: Enhanced user experience with colors and formatting
- **Comprehensive Testing**: 27 new test methods covering all wizard components

### CLI Modularization (v0.2.0)
The CLI interface has been refactored from a monolithic 735-line file into focused, maintainable modules:

- **config_commands.py**: Configuration management and setup commands
- **plan_commands.py**: Trade plan creation, validation, and listing (266 lines)
- **template_commands.py**: Template management and documentation
- **schema_commands.py**: Schema validation and documentation
- **monitor_commands.py**: Live monitoring and analysis commands
- **diagnostic_commands.py**: System health checks and diagnostics
- **help_commands.py**: Comprehensive help system

Each module maintains the 500-line limit while providing focused functionality.

### AsyncIO Performance Improvements
Fixed critical AsyncIO patterns in file watching system:

- Replaced deprecated `asyncio.get_event_loop()` with `asyncio.get_running_loop()`
- Improved reliability under high load scenarios
- Enhanced error handling for event loop management
- Eliminated potential deadlock conditions

### Test Coverage Expansion
Comprehensive testing suite with 179+ tests:

- **87% code coverage** (exceeding 80% target)
- **CLI module tests**: Full coverage of all command groups
- **Integration tests**: End-to-end workflow validation
- **Utility tests**: File watching and AsyncIO components
- **Model tests**: Pydantic validation and data models

## Development

### Testing

```bash
# Run all tests (179 tests currently passing)
PYTHONPATH=src uv run pytest src/auto_trader/models/tests/ src/auto_trader/utils/tests/ src/auto_trader/tests/ src/auto_trader/cli/tests/ -v

# Run with coverage report (87% coverage achieved)
PYTHONPATH=src uv run coverage run --source=src/auto_trader -m pytest src/auto_trader/models/tests/ src/auto_trader/utils/tests/ src/auto_trader/tests/ src/auto_trader/cli/tests/
PYTHONPATH=src uv run coverage report --show-missing --sort=Cover

# Run specific test modules
PYTHONPATH=src uv run pytest src/auto_trader/models/tests/test_trade_plan.py -v
PYTHONPATH=src uv run pytest src/auto_trader/models/tests/test_validation_engine.py -v
PYTHONPATH=src uv run pytest src/auto_trader/cli/tests/test_config_commands.py -v
PYTHONPATH=src uv run pytest src/auto_trader/utils/tests/test_file_watcher.py -v

# Run tests by category
PYTHONPATH=src uv run pytest src/auto_trader/models/tests/ -v        # Data models and validation
PYTHONPATH=src uv run pytest src/auto_trader/cli/tests/ -v           # CLI commands
PYTHONPATH=src uv run pytest src/auto_trader/utils/tests/ -v         # Utility functions
PYTHONPATH=src uv run pytest src/auto_trader/tests/ -v              # Integration tests

# Generate HTML coverage report
PYTHONPATH=src uv run coverage html --directory coverage_html
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

2. **Trade plan validation errors**
   - Check YAML syntax (indentation, colons, quotes)
   - Verify required fields: plan_id, symbol, entry_level, stop_loss, take_profit
   - Ensure risk_category is one of: small, normal, large
   - Validate symbol format (1-10 uppercase characters, no special chars)
   - Check price fields are positive decimals with max 4 decimal places
   - Use `validate-plans --verbose` for detailed error messages

3. **IBKR connection fails**
   - Verify TWS/Gateway is running
   - Check host/port settings match TWS configuration
   - Ensure client ID is unique

4. **Logging issues**
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
