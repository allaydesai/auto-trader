# Auto-Trader

Personal automated trading system designed to execute discretionary trades with time-based triggers to avoid institutional stop-hunting algorithms.

## Features

### Core Trading System
- **Complete Trade Lifecycle Management**: Automatic management from entry to exit with systematic execution
- **Trade Plan Management**: YAML-based trade plan definitions with comprehensive validation  
- **Candle-Close Execution**: Uses time-based triggers instead of simple price levels to filter market noise
- **Risk Management**: Built-in position sizing, daily loss limits, and portfolio risk validation
- **State Machine**: Robust trade plan status tracking (awaiting_entry → position_open → completed)
- **Position Tracking**: Real-time position state management with P&L calculations

### Execution Engine
- **Execution Function Framework**: Pluggable execution functions with registry system
- **Core Functions**: close_above, close_below, trailing_stop with <1 second accuracy
- **Signal Processing**: Entry/exit signal handling with risk validation integration
- **Order Management**: Bracket order placement (entry + stop-loss + take-profit)
- **Market Data Integration**: Real-time bar data processing with IBKR connectivity

### Risk & Portfolio Management  
- **Automated Position Sizing**: Calculate position sizes based on 1%, 2%, or 3% risk categories
- **Portfolio Risk Tracking**: Real-time portfolio exposure monitoring and limits
- **Risk Registry**: Active position tracking with automatic cleanup on exits
- **Pre-trade Validation**: Risk checks before order submission with limit enforcement

### Integrations & Notifications
- **IBKR Integration**: Direct connection to Interactive Brokers for market data and execution
- **Discord Notifications**: Real-time trade alerts and status updates with rich formatting  
- **Simulation Mode**: Complete paper trading environment for strategy testing
- **State Persistence**: Position state recovery and backup management across restarts

### User Interface & Management
- **Interactive CLI Wizard**: Step-by-step trade plan creation with real-time validation
- **Enhanced Plan Management**: Comprehensive commands for plan listing, validation, modification, and archiving
- **Modular CLI Interface**: Rich command-line tools organized into focused modules
- **Live Monitoring**: Real-time dashboard with optimized file watching
- **Template System**: Pre-built trade plan templates for quick strategy creation

### Development & Quality
- **Comprehensive Testing**: 300+ tests with 87% code coverage across all components
- **Performance Optimizations**: AsyncIO improvements with <1 second execution latency
- **Structured Logging**: Comprehensive audit trail with separate log files for different components
- **Error Handling**: Robust error recovery with circuit breaker patterns and graceful degradation

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

Copy the example configuration files and customize them:

```bash
# Copy example files
cp .env.example .env
cp config.yaml.example config.yaml
cp user_config.yaml.example user_config.yaml

# Edit with your settings
# IMPORTANT: Update .env with your IBKR connection details and Discord webhook
```

Alternatively, run the interactive setup wizard:

```bash
uv run python -m auto_trader.cli.commands setup
```

This will create the necessary configuration files:
- `.env` - Environment variables and secrets (connection details, API keys)
- `config.yaml` - System configuration (behavior settings, risk limits)
- `user_config.yaml` - Trading preferences (account value, risk categories)

### 3. Configuration

#### Environment Variables (`.env`)

```bash
# IBKR Connection (deployment-specific)
IBKR_HOST=127.0.0.1        # TWS/Gateway host
IBKR_PORT=7497             # 7497=TWS Paper, 7496=TWS Live, 4002=Gateway Paper, 4001=Gateway Live
IBKR_CLIENT_ID=1           # Must be unique per connection

# Secrets (never commit!)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_URL

# Optional Overrides (these override config.yaml if set)
# SIMULATION_MODE=true     # Forces simulation mode
# DEBUG=true              # Enables debug logging
```

#### System Configuration (`config.yaml`)

```yaml
# IBKR Behavior (not connection details - those are in .env)
ibkr:
  timeout: 30                    # Connection timeout in seconds
  reconnect_attempts: 5          # Max reconnection attempts
  graceful_shutdown: true        # Close positions on shutdown

# Risk Management
risk:
  max_position_percent: 10.0     # Max 10% of account per position
  daily_loss_limit_percent: 2.0  # Stop trading at 2% daily loss
  max_open_positions: 5          # Maximum concurrent positions
  max_concurrent_trades: 10      # Maximum trades processing simultaneously
  max_portfolio_risk_percent: 10.0 # Maximum total portfolio risk

# Trading Settings
trading:
  simulation_mode: true          # Default mode (can be overridden by .env)
  market_hours_only: true        # Only trade during market hours
  default_timeframe: "15min"     # Default execution timeframe
  order_timeout: 60              # Order timeout in seconds
```

#### User Preferences (`user_config.yaml`)

```yaml
# Account Settings
account_value: 10000            # Account balance for calculations
default_account_value: 10000    # Default for position sizing
default_risk_category: "normal"  # small (1%), normal (2%), or large (3%)

# Trading Preferences
preferred_timeframes:
  - "15min"
  - "30min"

default_execution_function: "close_above"  # Default entry function
use_fractional_shares: false              # Allow fractional share trading
```

**Note:** See [Configuration Guide](docs/configuration-guide.md) for detailed explanation of the configuration hierarchy and which settings belong in each file.

### 4. Validate Configuration

Before creating trade plans, verify your configuration is correct:

```bash
# Check all configuration sources
uv run python run_auto_trader.py --check-config
```

### 5. Create Trade Plans

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

### 6. Validation

Verify your configuration and trade plans:

```bash
# Validate system configuration
uv run python -m auto_trader.cli.commands validate-config --verbose

# Validate all trade plans
uv run python -m auto_trader.cli.commands validate-plans --verbose

# List loaded trade plans
uv run python -m auto_trader.cli.commands list-plans --verbose
```

### 7. Monitoring

Monitor your trading system:

```bash
# Start live monitoring dashboard
uv run python -m auto_trader.cli.commands monitor

# View performance summary
uv run python -m auto_trader.cli.commands summary --period week

# Check trade history
uv run python -m auto_trader.cli.commands history --symbol AAPL --days 7
```

### 8. Running the Complete Trading System

The Auto-Trader now features a fully integrated automated trading system with complete trade lifecycle management.

#### Start the Trading System

```bash
# Production startup script with all integrations
uv run python run_auto_trader.py

# Run with configuration check first
uv run python run_auto_trader.py --check-config

# Run in simulation mode (default)
uv run python run_auto_trader.py

# Run with debug logging
uv run python run_auto_trader.py --debug

# Run in live trading mode (requires confirmation)
uv run python run_auto_trader.py --live
```

#### Production Deployment

**Linux (systemd):**
```bash
# Install service file
sudo cp scripts/auto-trader.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable auto-trader
sudo systemctl start auto-trader

# Check status
sudo systemctl status auto-trader
journalctl -u auto-trader -f  # Follow logs
```

**Windows:**
```batch
# Using batch script
scripts\run_auto_trader.bat

# Using PowerShell
powershell -ExecutionPolicy Bypass -File scripts\run_auto_trader.ps1
```

#### What the Trading System Does

When you start the trading system, it will:

1. **Initialize Components**: 
   - Load configuration from `.env`, `config.yaml`, and `user_config.yaml`
   - Initialize trade engine, risk manager, and IBKR client
   - Setup Discord notifications and file watcher

2. **Load Trade Plans**: Automatically load all trade plans from `data/trade_plans/`
   - **Hot-reload enabled**: Changes to YAML files are automatically detected

3. **Connect to IBKR**: Establish connection to Interactive Brokers
   - Uses connection settings from `.env` (host, port, client_id)
   - Implements circuit breaker for connection resilience

4. **Monitor Entry Conditions**: Continuously evaluate execution functions
   - Real-time market data processing
   - Candle-close based triggers to avoid stop-hunting

5. **Process Entry Signals**: When entry conditions are met:
   - Validate risk limits and portfolio exposure
   - Calculate position size based on your risk category
   - Submit bracket orders (entry + stop-loss + take-profit)
   - Add position to risk registry upon fill confirmation

6. **Monitor Exit Conditions**: Track open positions for exit signals  

7. **Process Exit Signals**: When exit conditions are met:
   - Cancel remaining orders for the symbol
   - Remove position from risk registry
   - Update trade plan status to completed

8. **Send Notifications**: Discord alerts for all trade events
   - Rich formatted messages with trade details
   - [SIM] prefix in simulation mode

9. **Persist State**: Automatic state persistence
   - Position state saved for recovery across restarts
   - Atomic writes with backup recovery

#### Trade Plan Status Flow

Your trade plans will automatically transition through these states:
- `awaiting_entry` → Entry function monitored, waiting for signal
- `position_open` → Position active, exit functions monitored  
- `completed` → Position closed successfully
- `cancelled` → Plan cancelled before execution
- `error` → Error occurred during execution

#### Monitoring Your Trading System

```bash
# Monitor system status and active trades
uv run python -m auto_trader.cli.commands monitor

# Check trade plan status
uv run python -m auto_trader.cli.commands list-plans --verbose

# View trade history and performance
uv run python -m auto_trader.cli.commands summary --period week

# Check system health
uv run python -m auto_trader.cli.commands doctor
```

#### Important Configuration Notes

**Configuration Hierarchy:**
1. **Environment variables (.env)** - Highest priority, overrides all
2. **System configuration (config.yaml)** - Application behavior
3. **User preferences (user_config.yaml)** - Trading preferences

**Key Settings:**
- IBKR connection details (host, port, client_id) MUST be in `.env`
- `SIMULATION_MODE` in `.env` overrides `trading.simulation_mode` in config.yaml
- Risk limits and trading behavior in `config.yaml`
- Account value and preferences in `user_config.yaml`

See [Configuration Guide](docs/configuration-guide.md) for complete details.

## Project Structure

```
auto-trader/
├── src/
│   ├── config.py                    # Configuration management
│   ├── main.py                      # Application entry point
│   └── auto_trader/
│       ├── models/                  # Pydantic data models & validation
│       │   ├── trade_plan.py        # Trade plan schema & validation
│       │   ├── market_data.py       # Market data models
│       │   ├── market_data_cache.py # Market data caching system
│       │   ├── validation_engine.py # YAML validation engine
│       │   ├── error_reporting.py   # Enhanced error reporting
│       │   ├── template_manager.py  # Template management
│       │   └── plan_loader.py       # Plan loading & management
│       ├── trade_engine/            # Complete trade lifecycle management
│       │   ├── trade_orchestrator.py        # Main trade lifecycle coordinator
│       │   ├── lifecycle_manager.py         # State transition management
│       │   ├── signal_processor.py          # Entry signal processing with risk validation
│       │   ├── exit_processor.py            # Exit signal processing and cleanup
│       │   ├── position_state_manager.py    # Position tracking and persistence
│       │   ├── main_application.py          # Main application entry point
│       │   ├── execution_functions.py       # Execution function base classes
│       │   ├── function_registry.py         # Execution function registry
│       │   ├── bar_close_detector.py        # Bar close detection with <1s accuracy
│       │   ├── execution_logger.py          # Comprehensive execution logging
│       │   ├── execution_metrics.py         # Performance metrics tracking
│       │   ├── functions/                   # Core execution functions
│       │   │   ├── close_above.py           # Close above execution function
│       │   │   ├── close_below.py           # Close below execution function
│       │   │   └── trailing_stop.py         # Trailing stop execution function
│       │   └── tests/                       # Comprehensive test suite (50+ tests)
│       ├── integrations/            # External service integrations
│       │   ├── ibkr_client/         # Interactive Brokers integration
│       │   │   ├── client.py        # Main IBKR client
│       │   │   ├── connection_manager.py    # Connection management with circuit breaker
│       │   │   ├── market_data_manager.py   # Real-time market data handling
│       │   │   ├── order_execution_manager.py # Order execution and fill tracking
│       │   │   ├── state_manager.py         # State persistence with backup rotation
│       │   │   ├── order_manager.py         # Order lifecycle management
│       │   │   ├── circuit_breaker.py       # Connection resilience
│       │   │   └── tests/                   # Integration tests
│       │   └── discord_notifier/    # Discord notifications
│       │       ├── notifier.py      # Rich notification formatting
│       │       ├── order_event_handler.py   # Order event notifications
│       │       └── tests/           # Notification tests
│       ├── risk_management/         # Comprehensive risk management
│       │   ├── risk_manager.py      # Main risk validation
│       │   ├── position_sizer.py    # Automated position sizing
│       │   ├── portfolio_tracker.py # Portfolio exposure tracking
│       │   ├── risk_models.py       # Risk calculation models
│       │   ├── backup_manager.py    # Risk state backup management
│       │   └── tests/               # Risk management tests
│       ├── utils/                   # Utility modules
│       │   ├── file_watcher.py      # File monitoring with AsyncIO optimizations
│       │   └── tests/               # Utility tests
│       └── cli/                     # Modular command-line interface
│           ├── commands.py          # Main CLI entry point (refactored)
│           ├── config_commands.py   # Configuration management commands
│           ├── plan_commands.py     # Trade plan creation and validation
│           ├── management_commands.py # Enhanced plan management commands
│           ├── risk_commands.py     # Risk management commands
│           ├── wizard_utils.py      # Interactive wizard utilities
│           ├── template_commands.py # Template-related commands
│           ├── schema_commands.py   # Schema validation commands
│           ├── monitor_commands.py  # Live monitoring and analysis commands
│           ├── diagnostic_commands.py # System diagnostic commands
│           ├── help_commands.py     # Help system commands
│           ├── display_utils.py     # Display & formatting utilities
│           ├── file_utils.py        # File creation utilities
│           ├── plan_utils.py        # Plan creation utilities
│           └── tests/               # Comprehensive CLI test suite (200+ tests)
├── data/
│   └── trade_plans/
│       ├── templates/               # YAML plan templates
│       │   ├── close_above.yaml     # Close above execution template
│       │   ├── close_below.yaml     # Close below execution template
│       │   └── trailing_stop.yaml   # Trailing stop template
│       ├── backups/                 # Timestamped plan backups
│       ├── archive/                 # Organized archived plans
│       │   ├── YYYY/MM/completed/   # Completed plans by date
│       │   └── YYYY/MM/cancelled/   # Cancelled plans by date
│       └── *.yaml                   # Your trade plan files
├── logs/                            # Application logs
│   ├── system.log                   # General application events
│   ├── trades.log                   # Trading execution logs
│   ├── risk.log                     # Risk management events
│   ├── cli.log                      # CLI command logs
│   └── execution.log                # Detailed execution function logs
├── state/                           # Persistent state storage
│   ├── positions/                   # Position state files
│   ├── backups/                     # State backup files
│   └── risk_registry/               # Risk registry persistence
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
stop_loss_function:
  function_type: "close_below"
  timeframe: "1min"
  parameters:
    threshold: 178.00
take_profit_function:
  function_type: "close_above"
  timeframe: "1min"
  parameters:
    threshold: 185.00
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

#### Basic Plan Listing
```bash
# List all loaded plans
uv run python -m auto_trader.cli.commands list-plans

# Filter by status
uv run python -m auto_trader.cli.commands list-plans --status awaiting_entry

# Filter by symbol
uv run python -m auto_trader.cli.commands list-plans --symbol AAPL --verbose
```

#### Enhanced Plan Management (New)
```bash
# Enhanced plan listing with risk integration
uv run python -m auto_trader.cli.commands list-plans-enhanced --verbose

# Filter and sort plans with portfolio risk display
uv run python -m auto_trader.cli.commands list-plans-enhanced --status awaiting_entry --sort-by risk

# Comprehensive plan validation with portfolio risk checking
uv run python -m auto_trader.cli.commands validate-config-enhanced --verbose

# Validate single file
uv run python -m auto_trader.cli.commands validate-config-enhanced --file data/trade_plans/AAPL_001.yaml

# Update plan fields with automatic recalculation
uv run python -m auto_trader.cli.commands update-plan AAPL_20250822_001 --entry-level 181.00 --force

# Archive completed plans with organized structure
uv run python -m auto_trader.cli.commands archive-plans --dry-run

# Generate comprehensive portfolio statistics
uv run python -m auto_trader.cli.commands plan-stats
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

## Configuration

### Configuration Files

The Auto-Trader uses a three-tier configuration system:

1. **`.env`** - Deployment-specific settings and secrets
   - IBKR connection details (host, port, client_id)
   - API keys and webhooks
   - Environment overrides

2. **`config.yaml`** - System behavior and limits
   - Risk management rules
   - Trading system behavior
   - Logging configuration

3. **`user_config.yaml`** - User preferences
   - Account values
   - Default risk categories
   - Trading preferences

**Important:** IBKR connection settings (host, port, client_id) are ONLY in `.env`, not in `config.yaml`.

See [Configuration Guide](docs/configuration-guide.md) for detailed information.

### Configuration Options

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

# Enhanced plan management (new commands)
uv run python -m auto_trader.cli.commands list-plans-enhanced [--status STATUS] [--sort-by risk|date|symbol] [--verbose]

# Comprehensive validation with portfolio risk checking
uv run python -m auto_trader.cli.commands validate-config-enhanced [--file FILE] [--verbose]

# Update plan fields with automatic recalculation and backup
uv run python -m auto_trader.cli.commands update-plan PLAN_ID [--entry-level PRICE] [--stop-loss PRICE] [--take-profit PRICE] [--risk-category CATEGORY] [--force]

# Archive completed plans with organized structure
uv run python -m auto_trader.cli.commands archive-plans [--dry-run] [--force]

# Generate portfolio statistics and analysis
uv run python -m auto_trader.cli.commands plan-stats
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

## Trade Lifecycle Management (NEW)

The Auto-Trader now includes a complete trade lifecycle management system that automates your entire trading workflow from entry to exit.

### Key Features

- **Automatic Entry Execution**: Monitors your trade plans and executes entries when conditions are met
- **Risk-Validated Execution**: All trades undergo comprehensive risk checks before execution
- **Position State Tracking**: Real-time position monitoring with P&L calculations
- **Automatic Exit Handling**: Monitors exit conditions and closes positions systematically
- **State Persistence**: Maintains position state across system restarts
- **Performance Metrics**: Tracks execution latency and system performance

### How It Works

1. **Create Trade Plans**: Use the CLI wizard or manually create YAML trade plans
2. **Start the System**: Run the main application to begin trade lifecycle management
3. **Automatic Monitoring**: System continuously evaluates execution functions
4. **Signal Processing**: Entry/exit signals trigger risk validation and order submission
5. **Position Tracking**: Active positions are monitored with real-time state updates
6. **Completion Handling**: Positions are automatically closed and removed from tracking

### Trade Plan Configuration

Your trade plans now support advanced execution functions:

```yaml
plan_id: "AAPL_20250831_001"
symbol: "AAPL"
entry_level: 180.50
stop_loss: 178.00
take_profit: 185.00
risk_category: "normal"

# Entry execution function
entry_function:
  function_type: "close_above"
  timeframe: "15min"
  parameters:
    threshold: 180.50

# Stop loss exit function
stop_loss_function:
  function_type: "close_below"
  timeframe: "1min"
  parameters:
    threshold: 178.00

# Take profit exit function
take_profit_function:
  function_type: "close_above"
  timeframe: "1min"
  parameters:
    threshold: 185.00

status: "awaiting_entry"
```

### Available Execution Functions

| Function Type | Usage | Parameters | Description |
|---------------|-------|------------|-------------|
| `close_above` | Entry | `threshold`: Price level | Execute when price closes above threshold |
| `close_below` | Entry | `threshold`: Price level | Execute when price closes below threshold |
| `trailing_stop` | Entry/Exit | `trail_percent`: Trail % | Dynamic stop that follows price |
| `stop_loss_take_profit` | Exit | None | Handles both stop loss and take profit |

### Position State Management

The system maintains comprehensive position state:

- **Entry Information**: Fill price, quantity, timestamp
- **P&L Tracking**: Real-time profit/loss calculations
- **Risk Metrics**: Position size, risk amount, portfolio impact
- **Order Status**: Active orders and fill confirmations
- **State Persistence**: Automatic backup and recovery

### Performance Monitoring

```bash
# Check execution performance
uv run python -m auto_trader.cli.commands summary --verbose

# View detailed position states
uv run python -m auto_trader.cli.commands list-plans --status position_open

# Monitor system health
uv run python -m auto_trader.cli.commands doctor --export-debug
```

## Recent Improvements

### Fully Integrated Main Application (v4.0.0) 🚀
**MAJOR RELEASE**: Complete integration of all components into unified application:

- **Main Application Integration**: Connected AutoTraderApp with TradingApplication for seamless operation
- **File Watcher Integration**: Automatic hot-reload of trade plans when YAML files change
- **Production Startup Scripts**: 
  - Python entry point with CLI arguments (`run_auto_trader.py`)
  - Linux systemd service file for production deployment
  - Windows batch and PowerShell scripts
- **Configuration Cleanup**: 
  - Removed duplicate settings between `.env` and `config.yaml`
  - Clear separation: `.env` for deployment/secrets, `config.yaml` for behavior
  - Proper override hierarchy with environment variables taking precedence
- **Comprehensive Documentation**: 
  - [Data Flow Architecture](docs/data-flow-architecture.md)
  - [Component Interaction Diagrams](docs/component-interaction-diagram.md)
  - [Configuration Guide](docs/configuration-guide.md)

### Complete Trade Lifecycle Management System (v3.3.0) 🎉
**MAJOR MILESTONE**: Full implementation of automated trade execution from entry to exit:

- **TradeOrchestrator**: Main coordination engine managing complete trade lifecycles
- **State Machine**: Robust trade plan status transitions (awaiting_entry → position_open → completed)
- **Signal Processing**: Entry signal processing with integrated risk validation and position sizing
- **Exit Processing**: Automated exit signal handling with order cancellation and position cleanup
- **Position Management**: Real-time position state tracking with P&L calculations and file persistence
- **Integration**: Seamless integration with all existing systems (risk management, order execution, execution functions)
- **Performance**: <1 second execution latency from signal to order submission
- **Testing**: 27 comprehensive unit tests for lifecycle management with 100% pass rate

### Enhanced Trade Plan Management Commands (v2.1.0)
Comprehensive trade plan management system with full risk integration:

- **Enhanced Plan Listing**: Real-time risk integration with color-coded status indicators
- **Advanced Validation**: Portfolio-wide risk checking with comprehensive error reporting
- **Safe Plan Modification**: Field updates with automatic recalculation and backup system
- **Plan Organization**: Automated archiving with date-based organizational structure
- **Portfolio Analytics**: Comprehensive statistics with risk distribution and insights
- **UX Compliance**: Progressive verbosity, fail-safe confirmations, and immediate feedback
- **Extensive Testing**: 100+ new tests covering all management functionality

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
Comprehensive testing suite with 300+ tests:

- **87% code coverage** (exceeding 80% target)
- **CLI module tests**: Full coverage of all command groups including management commands
- **Integration tests**: End-to-end workflow validation
- **Utility tests**: File watching and AsyncIO components
- **Model tests**: Pydantic validation and data models
- **Management tests**: Complete coverage of plan management functionality

## Development

### Testing

The Auto-Trader project uses **pytest** as the testing framework with comprehensive coverage requirements.

#### Quick Commands

```bash
# Run full test suite (simplest method)
uv run pytest

# Run with verbose output (shows individual test names)
uv run pytest -v

# Run with coverage reporting
uv run pytest --cov=src/auto_trader

# Run specific test file
uv run pytest src/auto_trader/cli/tests/test_wizard_utils.py -v
```

#### Comprehensive Testing Commands

```bash
# Run all tests with detailed output (300+ tests currently passing)
PYTHONPATH=src uv run pytest src/auto_trader/models/tests/ src/auto_trader/utils/tests/ src/auto_trader/tests/ src/auto_trader/cli/tests/ -v

# Run with coverage report (87% coverage achieved)
PYTHONPATH=src uv run coverage run --source=src/auto_trader -m pytest src/auto_trader/models/tests/ src/auto_trader/utils/tests/ src/auto_trader/tests/ src/auto_trader/cli/tests/
PYTHONPATH=src uv run coverage report --show-missing --sort=Cover

# Generate HTML coverage report
PYTHONPATH=src uv run coverage html --directory coverage_html
```

#### Test Categories & Organization

**By Test Module:**
```bash
# Data models and validation (32+ tests)
PYTHONPATH=src uv run pytest src/auto_trader/models/tests/ -v

# CLI commands and wizard (190+ tests)
PYTHONPATH=src uv run pytest src/auto_trader/cli/tests/ -v

# Utility functions (15+ tests)
PYTHONPATH=src uv run pytest src/auto_trader/utils/tests/ -v

# Integration tests (12+ tests)
PYTHONPATH=src uv run pytest src/auto_trader/tests/ -v
```

**By Specific Component:**
```bash
# Trade plan model validation
PYTHONPATH=src uv run pytest src/auto_trader/models/tests/test_trade_plan.py -v

# YAML validation engine
PYTHONPATH=src uv run pytest src/auto_trader/models/tests/test_validation_engine.py -v

# Template management system
PYTHONPATH=src uv run pytest src/auto_trader/models/tests/test_template_manager.py -v

# CLI configuration commands
PYTHONPATH=src uv run pytest src/auto_trader/cli/tests/test_config_commands.py -v

# Interactive wizard functionality
PYTHONPATH=src uv run pytest src/auto_trader/cli/tests/test_wizard_utils.py -v

# Enhanced plan management commands
PYTHONPATH=src uv run pytest src/auto_trader/cli/tests/test_management_commands.py -v

# Plan management utilities
PYTHONPATH=src uv run pytest src/auto_trader/cli/tests/test_management_utils.py -v

# File watching utilities
PYTHONPATH=src uv run pytest src/auto_trader/utils/tests/test_file_watcher.py -v

# Risk management integration
PYTHONPATH=src uv run pytest src/auto_trader/tests/test_story_1_3_integration.py -v
```

#### Test Filtering Options

```bash
# Run tests matching pattern
uv run pytest -k "wizard" -v                    # All wizard-related tests
uv run pytest -k "validation" -v                # All validation tests
uv run pytest -k "config" -v                    # All config-related tests

# Run tests by marker
uv run pytest -m "integration" -v               # Integration tests only
uv run pytest -m "unit" -v                      # Unit tests only

# Run failed tests only
uv run pytest --lf -v                           # Last failed
uv run pytest --ff -v                           # Failed first

# Stop on first failure
uv run pytest -x -v
```

#### Coverage Analysis

```bash
# Basic coverage report
uv run pytest --cov=src/auto_trader --cov-report=term

# Detailed coverage with missing lines
uv run pytest --cov=src/auto_trader --cov-report=term-missing

# HTML coverage report (opens in browser)
uv run pytest --cov=src/auto_trader --cov-report=html
open htmlcov/index.html  # View in browser

# Coverage by module
uv run pytest --cov=src/auto_trader/models --cov-report=term
uv run pytest --cov=src/auto_trader/cli --cov-report=term
```

#### Test Output & Debugging

```bash
# Extra verbose output
uv run pytest -vv

# Show local variables on failure
uv run pytest -l

# Drop into debugger on failure
uv run pytest --pdb

# Capture output (disable -s to see prints)
uv run pytest -s -v

# Quiet mode (minimal output)
uv run pytest -q
```

#### Performance Testing

```bash
# Show slowest tests
uv run pytest --durations=10

# Timeout for slow tests
uv run pytest --timeout=30

# Parallel execution (if pytest-xdist installed)
uv run pytest -n auto
```

#### Test Standards & Requirements

- **Coverage Target**: 80% minimum (currently 87%)
- **Test Types**: 70% unit tests, 20% integration tests, 10% end-to-end
- **Naming Convention**: `test_[component]_[action]_[expected_result]`
- **File Organization**: Tests located next to source code in `tests/` subdirectories
- **Fixtures**: Use pytest fixtures for setup, located in `conftest.py` files
- **Mocking**: Use `unittest.mock` for external dependencies

#### Common Test Issues & Solutions

**Import Errors:**
```bash
# Ensure PYTHONPATH is set for complex test runs
PYTHONPATH=src uv run pytest

# Or use pytest discovery from project root
uv run pytest  # Recommended approach
```

**Mock Setup Issues:**
- Risk manager tests require `position_sizer` and `portfolio_tracker` attributes
- Config loader tests need `user_preferences.account_value` attribute
- Use `Mock(spec=ClassName)` for type safety

**YAML Serialization:**
- Use `model_dump(mode='json')` for Pydantic models in YAML tests
- Decimal values require proper serialization for file tests

**Fixture Dependencies:**
- Check fixture scope (function, class, module, session)
- Ensure fixtures are properly imported in test files

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

### Testing the Integration

Run the integration test to verify all components are working:

```bash
# Test all components without starting the full system
uv run python test_integration.py
```

This will verify:
- Configuration loading from all sources
- Trade plan loading and validation
- Risk manager initialization
- IBKR client setup
- Discord notifier configuration
- Trade engine components
- Main application initialization

### Common Issues

1. **Configuration validation fails**
   - Check `.env` file exists and has correct values
   - Verify YAML syntax in config files
   - Ensure Discord webhook URL is valid
   - Run `uv run python run_auto_trader.py --check-config` to diagnose

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
