# Auto-Trader Product Requirements Document (PRD)

## Goals and Background Context

### Goals
- Automate discretionary trading strategy execution with dynamic, time-based entry/exit logic to avoid institutional stop-hunting algorithms
- Achieve consistent trade execution within 1 second of signal generation across multiple timeframes (1 minute to 1 week)
- Eliminate emotional trading decisions and human execution delays through systematic automation
- Provide complete trade lifecycle visibility through real-time UI monitoring and Discord notifications
- Maintain comprehensive trade history for strategy analysis and refinement
- Support both live trading and simulation modes for testing and alert-only operation
- Deliver a working MVP within 4 weeks that handles the complete trade lifecycle from entry to exit

### Background Context
This PRD defines a personal automated trading system designed to address the fundamental challenges faced by retail traders in algorithm-dominated markets. Traditional retail trading platforms rely on simple price-level triggers that institutional algorithms easily exploit through stop-hunting strategies. By implementing time-based execution functions that trigger on candle closes rather than instantaneous price crosses, this system provides a more robust approach to trade execution that filters market noise and reduces vulnerability to algorithmic manipulation.

The system leverages established financial infrastructure (Interactive Brokers for execution, Financial Modeling Prep for market data, TA-lib for technical indicators) while maintaining complete user control over execution logic. As a single-user system built for the developer/trader, it eliminates multi-user complexity while focusing on modular architecture that supports custom execution functions and comprehensive trade management across multiple timeframes.

### Change Log
| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2025-08-03 | 1.0 | Initial PRD creation based on Project Brief | John (PM) |

## Requirements

### Functional (MVP - 4 Week Scope)
- FR1: The system shall load trade plans from YAML files containing entry/exit levels, stop-loss levels, and execution function selection with timeframe metadata
- FR2: The system shall connect to Interactive Brokers API for both market data and trade execution
- FR3: The system shall implement three pre-built execution functions: close above level, close below level, and trailing stop (all with configurable timeframes)
- FR4: The system shall execute risk management checks (position size, daily loss limits) before placing any orders
- FR5: The system shall send Discord notifications for each trade event (entry, exit, stop-loss)
- FR6: The system shall support a simulation mode toggle that processes all logic without placing broker orders
- FR7: The system shall append all executed trades to a history file with timestamp, symbol, action, price, and P&L
- FR8: The system shall persist and recover position state across restarts to support multi-day swing trades

### Future Functional Requirements (Post-MVP)
- Future FR1: Add Financial Modeling Prep as secondary data source with failover logic
- Future FR2: Implement custom execution function builder with TA-lib integration
- Future FR3: Create web-based monitoring UI for trade plan status
- Future FR4: Add daily trade summary generation and Discord posting
- Future FR5: Scale to support 100+ simultaneous trade plans
- Future FR6: Implement advanced risk management features (correlation, portfolio heat)

### Non Functional (MVP)
- NFR1: Trade execution latency shall not exceed 1 second from signal generation to order submission
- NFR2: The system shall run on both Windows and Linux desktop environments
- NFR3: The system shall handle IBKR connection drops with automatic reconnection attempts
- NFR4: API credentials shall be stored in environment variables or encrypted config file
- NFR5: The system shall operate within Interactive Brokers API rate limits
- NFR6: Critical execution paths (risk checks, order placement) shall have unit test coverage

### Future Non-Functional Requirements (Post-MVP)
- Future NFR1: Achieve 95% uptime during market hours
- Future NFR2: Scale to process tick data for 100+ symbols without lag
- Future NFR3: Implement comprehensive test coverage across all modules
- Future NFR4: Add performance monitoring and alerting

## User Interface Design Goals
*Note: Skipped for MVP - Discord serves as the primary interface with CLI for control*

## Technical Assumptions

### Repository Structure: Monorepo
A single repository containing all components (execution engine, IBKR integration, Discord client) to simplify development and deployment for a single-user system.

### Service Architecture
**Monolithic application with modular components:**
- Single Python process managing all functionality
- Clear module separation: trade_engine, ibkr_client, discord_notifier, risk_manager
- Shared in-memory state for low-latency execution
- File-based persistence for simplicity (YAML configs, JSON state, CSV trade history)

### Testing Requirements
**Focused testing on critical paths only:**
- Unit tests for risk management calculations
- Unit tests for execution function logic
- Integration tests for IBKR order placement (using paper trading account)
- Manual testing checklist for end-to-end flows

### Additional Technical Assumptions and Requests
- **Language:** Python 3.10+ (for IBKR API compatibility and financial ecosystem)
- **IBKR Integration:** Using ib_insync library for cleaner async API handling
- **Data Storage:** Local files only - YAML for configs, JSON for state, CSV for trade history
- **Discord Integration:** Discord.py or simple webhook POST requests
- **Scheduling:** Python's asyncio for event loops and APScheduler for time-based events
- **Configuration:** Environment variables for secrets, YAML files for trade plans
- **Deployment:** Simple Python virtual environment with requirements.txt
- **Process Management:** systemd service (Linux) or Task Scheduler (Windows)
- **Logging:** Python's built-in logging to rotating file handlers
- **Time Handling:** All timestamps in UTC to avoid timezone issues
- **Market Hours:** Hardcoded US equity market hours initially

## Epic List

**Epic 1: Foundation & Trade Plan Management** - Establish project infrastructure, configuration system, and trade plan loading with basic risk management framework

**Epic 2: IBKR Integration & Market Data** - Connect to Interactive Brokers for real-time data consumption and order execution with connection management

**Epic 3: Trade Execution Engine** - Implement execution functions, time-based triggers, and complete trade lifecycle from entry to exit

**Epic 4: Notifications & Persistence** - Add Discord notifications, trade history logging, and state persistence for multi-day positions

## Epic 1: Foundation & Trade Plan Management

Establish project infrastructure, configuration system, and trade plan loading with basic risk management framework. This epic delivers the foundational components needed for all subsequent functionality while also providing immediate value through trade plan management.

### Story 1.1: Project Setup and Configuration

As a trader,
I want the application to load configuration from environment variables and files,
so that I can securely manage API credentials and system settings.

#### Acceptance Criteria
1: Project structure created with modules for trade_engine, ibkr_client, discord_notifier, and risk_manager
2: Configuration loader reads from .env file for secrets (IBKR credentials, Discord webhook)
3: System configuration (risk limits, market hours) loads from config.yaml
4: Logging configured with rotating file handlers outputting to logs/ directory
5: Main entry point (main.py) initializes all modules with proper error handling
6: README.md documents environment setup and configuration options

### Story 1.2: Trade Plan Schema and Loader

As a trader,
I want to define my trade plans in YAML files,
so that I can easily create and modify trading strategies without code changes.

#### Acceptance Criteria
1: YAML schema defined supporting: symbol, entry_level, stop_loss, take_profit, position_size
2: Execution function specification includes: function_name, timeframe, parameters
3: Trade plan loader validates YAML structure and reports clear errors for invalid plans
4: Support for multiple trade plans in a single file or across multiple files
5: Example trade plan files provided demonstrating all three execution functions
6: Plans loaded into memory with unique identifiers for tracking

### Story 1.3: Risk Management Framework

As a trader,
I want risk checks performed before any trade execution,
so that I protect my capital from excessive losses.

#### Acceptance Criteria
1: Risk manager validates position size against account balance (via config max_position_percent)
2: Daily loss limit enforced across all trades (configurable in config.yaml)
3: Maximum positions limit enforced (configurable in config.yaml)
4: Risk checks return clear pass/fail with reason for any rejection
5: Risk calculations account for existing positions when evaluating new trades
6: Unit tests verify all risk scenarios including edge cases

## Epic 2: IBKR Integration & Market Data

Connect to Interactive Brokers for real-time data consumption and order execution with connection management. This epic establishes the critical broker connection that enables all trading functionality.

### Story 2.1: IBKR Connection Management

As a trader,
I want reliable connection to Interactive Brokers,
so that I can receive market data and execute trades without interruption.

#### Acceptance Criteria
1: Connect to IBKR using ib_insync library with configurable host/port
2: Automatic reconnection on disconnect with exponential backoff (max 5 attempts)
3: Connection status logged and available for health checks
4: Graceful shutdown handling to close positions if configured
5: Paper trading vs live account detected and logged prominently
6: Connection errors result in Discord notification

### Story 2.2: Market Data Subscription

As a trader,
I want to receive real-time price data for my trading symbols,
so that my execution functions can trigger on accurate market conditions.

#### Acceptance Criteria
1: Subscribe to real-time bars for all symbols in active trade plans
2: Support bar sizes: 1min, 5min, 15min, 30min, 1hour, 4hour, 1day
3: Historical data fetched on startup to establish current position relative to levels
4: Market data cached in memory with timestamp for each bar
5: Data quality checks ensure no stale data used for execution (>2x bar size)
6: Subscription management handles adding/removing symbols dynamically

### Story 2.3: Order Execution Interface

As a trader,
I want to place and manage orders through IBKR,
so that my trades execute in the market.

#### Acceptance Criteria
1: Place market orders for trade plan entries with configured position size
2: Place stop-loss orders immediately after entry fill confirmation
3: Place take-profit orders immediately after entry fill confirmation
4: Modify existing orders (for trailing stops) without creating duplicates
5: Order status tracked and logged (submitted, filled, cancelled, rejected)
6: Failed orders trigger Discord notification with error details

## Epic 3: Trade Execution Engine

Implement execution functions, time-based triggers, and complete trade lifecycle from entry to exit. This epic contains the core value proposition of the system.

### Story 3.1: Execution Function Framework

As a trader,
I want a framework for execution functions that trigger on candle closes,
so that I can avoid stop-hunting algorithms.

#### Acceptance Criteria
1: Function registry maps function names to implementations
2: Functions receive: current bar data, trade plan parameters, position state
3: Functions return: action (none, enter, exit) with confidence score
4: Bar close detection accurate within 1 second of actual close time
5: Multiple timeframes monitored simultaneously for same symbol
6: Execution decisions logged with reasoning for audit trail

### Story 3.2: Core Execution Functions

As a trader,
I want three proven execution functions available,
so that I can implement my most common trading strategies.

#### Acceptance Criteria
1: "close_above" function triggers when price closes above specified level
2: "close_below" function triggers when price closes below specified level  
3: "trailing_stop" function maintains stop distance from highest/lowest close
4: All functions respect timeframe parameter (only evaluate on specified bar size)
5: Functions handle edge cases (gaps, limit up/down, missing data)
6: Unit tests verify function behavior across market scenarios

### Story 3.3: Trade Lifecycle Management

As a trader,
I want automatic management of my trades from entry to exit,
so that I can rely on systematic execution.

#### Acceptance Criteria
1: Entry function monitored while position is flat
2: Upon entry trigger, risk checks performed before order submission
3: After fill, stop-loss and take-profit orders placed immediately
4: Exit functions (stop/target) monitored while position is open
5: Position state tracked: awaiting_entry, position_open, position_closed
6: Exit fills cancel any remaining orders for that symbol

### Story 3.4: Simulation Mode

As a trader,
I want to test my system without risking real money,
so that I can validate behavior before live trading.

#### Acceptance Criteria
1: Simulation mode flag in config.yaml disables all IBKR order submissions
2: Simulated fills use current market price with configurable slippage
3: Simulated positions tracked identically to real positions
4: All Discord notifications sent with "[SIMULATION]" prefix
5: Trade history includes simulation flag for easy filtering
6: Simulated P&L calculated using market prices

## Epic 4: Notifications & Persistence

Add Discord notifications, trade history logging, and state persistence for multi-day positions. This epic completes the system with observability and continuity features.

### Story 4.1: Discord Notifications

As a trader,
I want immediate Discord notifications for all trade events,
so that I can monitor my system remotely.

#### Acceptance Criteria
1: Webhook URL configured via environment variable
2: Entry notifications include: symbol, side, price, position size, timestamp
3: Exit notifications include: symbol, side, price, P&L, exit reason
4: Error notifications include: error type, symbol, attempted action, timestamp
5: Notifications formatted with markdown for readability
6: Failed webhook posts logged but don't crash the system

### Story 4.2: Trade History Logging

As a trader,
I want a permanent record of all trades,
so that I can analyze my performance.

#### Acceptance Criteria
1: CSV file appends one row per trade with all relevant fields
2: Fields include: timestamp, symbol, side, entry_price, exit_price, size, P&L, fees
3: Execution metadata logged: function used, timeframe, trigger level
4: Separate files for each month (trades_2024_01.csv format)
5: Trade summary calculated on each trade: win rate, average win/loss
6: History queryable by date range or symbol

### Story 4.3: State Persistence and Recovery

As a trader,
I want my positions to survive system restarts,
so that I can maintain trades across multiple days.

#### Acceptance Criteria
1: Position state saved to JSON file on each state change
2: State includes: symbol, entry_price, size, stop/target orders, entry_time
3: On startup, state file loaded and positions reconciled with IBKR
4: Orphaned orders detected and cancelled if position no longer exists
5: State file backup created before each update (keeping last 5 versions)
6: Recovery process logged clearly showing what was restored
