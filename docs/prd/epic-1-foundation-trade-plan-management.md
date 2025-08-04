# Epic 1: Core Foundation & Infrastructure

Establish project infrastructure, configuration system, logging framework, and basic trade plan management. This epic delivers the foundational components needed for all subsequent functionality, with early availability of logging infrastructure to support development and debugging across all epics.

## Story 1.1: Project Setup and Configuration

As a trader,
I want the application to load configuration from environment variables and files,
so that I can securely manage API credentials and system settings.

### Acceptance Criteria

**Core Configuration Structure**
1: Project structure created with modules for trade_engine, ibkr_client, discord_notifier, and risk_manager
2: Configuration loader reads from .env file for secrets (IBKR credentials, Discord webhook)
3: System configuration (risk limits, market hours) loads from config.yaml
4: Logging framework configured with rotating file handlers outputting to logs/ directory
5: Main entry point (main.py) initializes all modules with proper error handling

**Enhanced Logging Infrastructure (Moved from Epic 4)**
6: Implement structured logging with loguru for trades, system events, and errors
7: Create separate log files: trades.log, risk.log, system.log, cli.log
8: Configure log rotation and retention policies (daily rotation, 30-day retention)
9: Establish logging standards for all modules to use consistently
10: Include request/response logging for external API calls

**User Configuration Management**
11: Create user_config.yaml for trader-specific preferences and defaults
12: Include fields: default_account_value, default_risk_category, preferred_timeframes
13: Support default execution function preferences for different trade types
14: Enable per-environment configs (separate settings for paper vs live trading)
15: Provide config validation command: `auto-trader validate-config`

**Documentation and Setup**
16: README.md documents environment setup and configuration options
17: Include configuration examples and recommended default values
18: Provide setup wizard: `auto-trader setup` for first-time configuration

## Story 1.2: Trade Plan Schema and Validation

As a trader,
I want a robust schema and validation system for trade plans,
so that I can create error-free trading strategies with clear feedback.

### Acceptance Criteria

**Core Schema Definition**
1: YAML schema defined supporting: symbol, entry_level, stop_loss, take_profit, risk_category
2: Risk category field accepts: "small" (1%), "normal" (2%), "large" (3%)
3: Execution function specification includes: function_name, timeframe, parameters
4: Position size calculated dynamically using risk management module (not stored in YAML)
5: Support for multiple trade plans in a single file or across multiple files

**Comprehensive Validation**
6: Validate symbol format (1-10 uppercase characters, no special chars)
7: Validate price fields are positive decimals with max 4 decimal places
8: Validate entry_level ≠ stop_loss (prevent zero-risk trades)
9: Validate risk_category is one of: "small", "normal", "large"
10: Validate execution function exists and timeframe is supported
11: Validate plan_id uniqueness across all loaded plans

**Error Reporting**
12: Return specific line numbers and field names for YAML syntax errors
13: Provide actionable error messages: "Fix: Change 'risk_category: medium' to 'risk_category: normal'"
14: Show all validation errors at once (not just first error found)
15: Include example correct values in error messages

**Template and Examples**
16: Provide template YAML files for each execution function type
17: Include inline comments explaining each field and valid values
18: Plans loaded into memory with unique identifiers for tracking

## Story 1.3: Basic Trade Plan Creation

As a trader,
I want to create trade plans through manual YAML editing with validation support,
so that I can define trading strategies with immediate error feedback.

### Acceptance Criteria

**Manual YAML Editing Support**
1: Provide trade plan templates in templates/ directory for copy-paste creation
2: Include comprehensive inline documentation and examples in templates
3: Implement real-time validation command: `auto-trader validate-plans`
4: Show validation results with specific file, line, and field information
5: Support hot-reload: automatically detect and validate YAML file changes
6: Provide schema documentation with all valid values and examples

**Configuration Management**
7: Create system config file for trader-specific defaults (account_value, default_risk_category)
8: Allow setting default execution function and timeframe preferences
9: Support environment-specific configs (paper trading vs live account settings)
10: Enable basic plan status command: `auto-trader list-plans` showing loaded plans

**Validation Integration**
11: Use shared validation engine from Story 1.2 for consistency
12: Show clear error messages with actionable fix suggestions
13: Validate all plans on system startup before processing
14: Unit tests verify template-based creation produces valid YAML output

**Note**: Interactive CLI wizard, position sizing, and advanced plan management moved to Epic 1.5
