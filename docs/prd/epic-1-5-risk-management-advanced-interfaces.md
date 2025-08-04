# Epic 1.5: Risk Management & Advanced Interfaces

Implement automated position sizing, portfolio risk tracking, and interactive CLI creation wizard. This epic builds upon the foundation established in Epic 1 to provide comprehensive risk management and enhanced user interfaces for trade plan creation and management.

## Story 1.5.1: Automated Position Sizing & Risk Management

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

**Logging Integration**
22: Use logging infrastructure from Epic 1 for all risk calculations and decisions
23: Log portfolio risk changes and limit violations to risk.log
24: Include risk metrics in system health logging

## Story 1.5.2: Interactive CLI Creation Wizard

As a trader,
I want an interactive CLI wizard to create trade plans with real-time validation,
so that I can efficiently create error-free plans with immediate feedback.

### Acceptance Criteria

**Core CLI Wizard Flow**
1: Implement command: `auto-trader create-plan` to launch interactive wizard
2: Prompt for each required field with current value display and validation
3: Show acceptable values for each field (e.g., "risk_category [small/normal/large]:")
4: Validate each input immediately and request correction if invalid
5: Calculate and display estimated position size during creation process using Epic 1.5.1 risk management
6: Allow plan preview before final save to YAML file

**Risk Integration**
7: Integrate with automated position sizing from Story 1.5.1 for real-time calculations
8: Display current portfolio risk and impact of new plan during creation
9: Block plan creation if it would exceed 10% portfolio risk limit
10: Show clear risk breakdown: individual trade risk + current portfolio risk
11: Provide risk-based suggestions for position size adjustments

**Enhanced User Experience**
12: Support CLI shortcuts: `auto-trader create-plan --symbol AAPL --entry 180.50`
13: Pre-populate fields from user configuration defaults
14: Allow modification of entered values before final confirmation
15: Provide clear error recovery for invalid inputs
16: Save completed plans to appropriate YAML files with proper formatting

**Validation Integration**
17: Use shared validation engine from Epic 1 Story 1.2 for consistency
18: Show validation results with specific error details
19: Unit tests verify wizard-created plans match manual YAML creation
20: Log all wizard interactions to cli.log for debugging

## Story 1.5.3: Trade Plan Management Commands

As a trader,
I want comprehensive commands to manage my trade plans,
so that I can efficiently monitor, modify, and organize my trading strategies.

### Acceptance Criteria

**Plan Status and Monitoring**
1: Implement `auto-trader list-plans` showing all plans with status, risk, and portfolio impact
2: Display plan details: symbol, entry/stop/target levels, risk category, calculated position size
3: Show current portfolio risk percentage and remaining capacity
4: Highlight plans that would exceed risk limits if activated
5: Include plan validation status and any errors

**Plan Health and Validation**
6: Implement `auto-trader validate-config` for comprehensive plan validation
7: Check all YAML files for syntax and business logic errors
8: Validate portfolio risk across all plans doesn't exceed limits
9: Report validation summary with error counts and specific issues
10: Support validation of specific plan files: `auto-trader validate-config --file plan.yaml`

**Basic Plan Modification**
11: Implement `auto-trader update-plan PLAN_ID --field value` for simple field updates
12: Support updating: entry_level, stop_loss, take_profit, risk_category
13: Recalculate position size and validate portfolio risk after updates
14: Backup original plan before modification with timestamp
15: Log all plan modifications with before/after values

**Plan Organization**
16: Support plan status filtering: `auto-trader list-plans --status awaiting_entry`
17: Enable plan sorting by risk level, creation date, or symbol
18: Implement basic plan archiving: move completed plans to archive directory
19: Provide plan summary statistics: total plans, risk distribution, symbol diversity

**Integration with Risk Management**
20: All commands integrate with position sizing and portfolio risk tracking
21: Real-time risk calculations displayed in all plan listing commands
22: Commands respect portfolio risk limits and provide clear warnings
23: Unit tests verify command accuracy and risk calculation integration

**Note**: Advanced features like plan templates, bulk operations, and plan editing UI deferred to post-MVP