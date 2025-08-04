# Epic 1: Foundation & Trade Plan Management

Establish project infrastructure, configuration system, and trade plan loading with basic risk management framework. This epic delivers the foundational components needed for all subsequent functionality while also providing immediate value through trade plan management.

## Story 1.1: Project Setup and Configuration

As a trader,
I want the application to load configuration from environment variables and files,
so that I can securely manage API credentials and system settings.

### Acceptance Criteria

**Core Configuration Structure**
1: Project structure created with modules for trade_engine, ibkr_client, discord_notifier, and risk_manager
2: Configuration loader reads from .env file for secrets (IBKR credentials, Discord webhook)
3: System configuration (risk limits, market hours) loads from config.yaml
4: Logging configured with rotating file handlers outputting to logs/ directory
5: Main entry point (main.py) initializes all modules with proper error handling

**User Configuration Management**
6: Create user_config.yaml for trader-specific preferences and defaults
7: Include fields: default_account_value, default_risk_category, preferred_timeframes
8: Support default execution function preferences for different trade types
9: Enable per-environment configs (separate settings for paper vs live trading)
10: Provide config validation command: `auto-trader validate-config`

**Documentation and Setup**
11: README.md documents environment setup and configuration options
12: Include configuration examples and recommended default values
13: Provide setup wizard: `auto-trader setup` for first-time configuration

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

## Story 1.3: Automated Position Sizing & Risk Management

As a trader,
I want automated position sizing based on risk percentage and portfolio limits,
so that I maintain consistent risk management across all trades.

### Acceptance Criteria

**Core Position Calculation (Critical)**
1: Implement position sizing formula: Position Size = (Account Value × Risk %) ÷ |Entry Price - Stop Loss Price|
2: Support three predefined risk levels: Small (1%), Normal (2%), Large (3%)
3: Validate Entry Price ≠ Stop Loss Price before calculation
4: Round calculated position size to whole shares
5: Return position size in shares, dollar risk amount, and validation status

**Portfolio Risk Protection**
6: Track total portfolio risk percentage across all open positions
7: Block new trades if (Current Risk + New Trade Risk) > 10% portfolio limit
8: Display current total portfolio risk percentage in risk calculations
9: Maintain in-memory registry of open positions with their risk amounts

**Risk Calculation Interface**
10: Accept inputs: account value, entry price, stop loss price, risk category
11: Return outputs: position size (shares), dollar risk, total portfolio risk %, trade status
12: Provide clear error message: "Portfolio risk limit exceeded" when blocking trades
13: Prevent position size calculation when portfolio limit would be exceeded

**Position State Management**
14: Add position to risk registry when trade opens (with calculated risk amount)
15: Remove position from risk registry when trade closes
16: Recalculate total portfolio risk when positions change
17: Persist position risk data across system restarts

**Essential Validations**
18: Reject calculations where entry price equals stop loss price
19: Reject trades that would exceed 10% total portfolio risk
20: Validate account value is positive and realistic
21: Unit tests verify all risk scenarios including edge cases and boundary conditions

## Story 1.4: Trade Plan Creation Interfaces

As a trader,
I want multiple ways to create trade plans efficiently,
so that I can choose the method that best fits my workflow and experience level.

### Acceptance Criteria

**Manual YAML Editing Support**
1: Provide trade plan templates in templates/ directory for copy-paste creation
2: Include comprehensive inline documentation and examples in templates
3: Implement real-time validation command: `auto-trader validate-plans`
4: Show validation results with specific file, line, and field information
5: Support hot-reload: automatically detect and validate YAML file changes
6: Provide schema documentation with all valid values and examples

**Interactive CLI Creation Wizard**
7: Implement command: `auto-trader create-plan` to launch interactive wizard
8: Prompt for each required field with current value display and validation
9: Show acceptable values for each field (e.g., "risk_category [small/normal/large]:")
10: Validate each input immediately and request correction if invalid
11: Calculate and display estimated position size during creation process
12: Allow plan preview before final save to YAML file

**Common Configuration Management**
13: Create system config file for trader-specific defaults (account_value, default_risk_category)
14: Allow setting default execution function and timeframe preferences
15: Support environment-specific configs (paper trading vs live account settings)
16: Enable config override via CLI: `auto-trader create-plan --risk normal --timeframe 15min`

**User Experience Enhancements**
17: Provide plan templates for common strategies: "breakout", "pullback", "swing_trade"
18: Show recently created plans for quick duplication and modification
19: Enable plan editing: `auto-trader edit-plan PLAN_ID` to modify existing plans
20: Implement plan status command: `auto-trader list-plans` showing all plans with status
21: Support plan deletion with confirmation: `auto-trader delete-plan PLAN_ID`

**Validation Integration**
22: Both creation methods use same validation engine for consistency
23: Show estimated portfolio risk impact during plan creation
24: Warn if new plan would exceed portfolio risk limits when activated
25: Unit tests verify both creation methods produce identical, valid YAML output
