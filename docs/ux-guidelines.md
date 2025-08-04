# Auto-Trader UX Guidelines for Headless MVP

## Overview

The Auto-Trader system operates without a traditional GUI, instead leveraging a **tri-interface approach**: Discord for notifications and monitoring, configuration files for plan management, and terminal for system control. This document provides UX principles and guidelines for creating an intuitive experience across these three touchpoints.

## Core UX Philosophy

### 1. **Clarity Through Constraints**
- **Principle**: Limited interfaces demand exceptional clarity in each interaction
- **Application**: Every Discord message, config file, and terminal output must be immediately understandable
- **Rationale**: With no visual UI to fall back on, text-based interfaces must be self-documenting

### 2. **Fail-Safe-by-Design**
- **Principle**: System should be nearly impossible to misconfigure dangerously
- **Application**: Config validation with clear error messages, simulation mode defaults, risk limit enforcement
- **Rationale**: Trading with real money requires bulletproof UX that prevents costly mistakes

### 3. **Progressive Disclosure**
- **Principle**: Show essential information first, details on demand
- **Application**: Discord notifications start with key facts, terminal logs offer varying verbosity levels
- **Rationale**: Trader needs quick decision-making information, not data overload

## Interface-Specific Guidelines

## Discord Interface (Primary Monitoring & Alerts)

### Notification Hierarchy & Visual Language

#### **Critical Alerts (🚨 Red Zone)**
Use for system failures and risk violations that require immediate attention:

```
🚨 **CRITICAL: SYSTEM OFFLINE**
Connection to IBKR lost at 14:23:45
Auto-reconnect failed (attempt 3/5)
Active positions: AAPL (+100), MSFT (-50)
Manual intervention required
```

#### **Trade Execution (🟢/🔴 Action Zone)**
Primary notifications for trade events using consistent emoji language:

```
🟢 **ENTRY EXECUTED**
**AAPL** | LONG 98 @ $180.45
**Function:** close_above_15min
**Stop:** $178.00 | **Target:** $185.00
**Risk:** $196 (2.0% account) | **Portfolio Risk:** 6.2%
```

```
🔴 **EXIT: STOP LOSS**
**AAPL** | SOLD 100 @ $177.95
**P&L:** -$250 (-1.39%)
**Duration:** 2h 34m
**Reason:** trailing_stop triggered
```

#### **Status Updates (ℹ️ Info Zone)**
System health and plan status updates:

```
ℹ️ **DAILY SUMMARY - 2025-08-03**
**Trades:** 3 executed | 2 wins | 1 loss
**P&L:** +$425 (+2.1% account)
**Active Plans:** 5 awaiting entry | 2 positions open
```

### Message Structure Standards

#### **Scannable Format**
- **Bold key information** that needs immediate recognition
- Use consistent field ordering: Symbol → Action → Price → Context
- One key fact per line for mobile readability
- Include context for decision-making (timeframe, function used)

#### **Actionable Information**
Every notification should answer: "What happened?" and "What do I need to do?"

```
❌ Poor: "Trade executed for AAPL"
✅ Good: "🟢 AAPL LONG 98 shares @ $180.45 | Risk: $196 (2.0%) | Portfolio: 6.2%"
```

#### **Consistent Emoji Language**
- 🟢 Entry/Profit exits
- 🔴 Stop loss/Loss exits  
- 🟡 Warnings (risk approaching limits)
- 🚨 Critical failures requiring action
- ℹ️ System status and summaries
- ⚙️ Configuration changes
- 🛡️ Risk management notifications
- 📊 Position sizing and portfolio updates

## Configuration Files (Plan Management)

### YAML Design Principles

#### **Self-Documenting Structure**
Configuration files must be readable by the trader without referring to documentation:

```yaml
# Active Trade Plans - Auto-Trader System
# Format: [SYMBOL]_[DATE]_[SEQUENCE]

plans:
  - plan_id: "AAPL_20250803_001"
    symbol: "AAPL"
    
    # Entry/Exit Levels (always use 2+ decimal places)
    entry_level: 180.50    # Trigger level for position entry
    stop_loss: 178.00      # Maximum loss exit
    take_profit: 185.00    # Profit target exit
    risk_category: "normal" # Risk level: small (1%), normal (2%), large (3%)
    
    # Execution Logic
    entry_function:
      type: "close_above"   # Options: close_above, close_below, trailing_stop
      timeframe: "15min"    # Bar size: 1min, 5min, 15min, 30min, 1hour, 4hour, 1day
      
    # Current Status (auto-updated by system)
    status: "awaiting_entry"  # awaiting_entry, position_open, position_closed
    created_at: "2025-08-03T09:30:00Z"
    
    # Position sizing calculated automatically by risk management module
    # Formula: Position Size = (Account Value × Risk %) ÷ |Entry Price - Stop Loss Price|
```

#### **Validation-Friendly Design**
Structure that prevents common errors:

```yaml
# ❌ Error-Prone
entry: 180.5
stop: 178
target: 185
position_size: 100

# ✅ Clear and Validated
entry_level: 180.50     # Must be > 0, max 4 decimal places
stop_loss: 178.00       # Must be != entry_level  
take_profit: 185.00     # Must be != entry_level
risk_category: "normal" # Must be: small, normal, or large
```

#### **Visual Grouping**
Use whitespace and comments to create visual sections:

```yaml
plans:
  # === ACTIVE SWING TRADES ===
  - plan_id: "AAPL_swing_001"
    # ... swing trade config
    
  # === DAY TRADING SETUPS ===  
  - plan_id: "TSLA_day_001"
    # ... day trade config
```

### File Organization Standards

#### **Predictable File Structure**
```
config/
├── active_plans.yaml      # Current trade plans  
├── user_config.yaml       # User preferences and defaults
├── system_config.yaml     # System-wide settings
└── templates/
    ├── breakout.yaml      # Breakout strategy template
    ├── pullback.yaml      # Pullback strategy template
    └── swing_trade.yaml   # Swing trade template
```

#### **Template System**
Provide copy-paste templates to reduce configuration errors:

```yaml
# templates/basic_entry.yaml
# Copy this template and modify for new trades

plan_template:
  plan_id: "SYMBOL_DATE_001"    # ← Update this
  symbol: "SYMBOL"              # ← Update this  
  entry_level: 0.00             # ← Set your entry
  stop_loss: 0.00               # ← Set your stop
  take_profit: 0.00             # ← Set your target
  risk_category: "normal"       # ← Choose: small (1%), normal (2%), large (3%)
  entry_function:
    type: "close_above"         # ← Choose function type
    timeframe: "15min"          # ← Choose timeframe
```

## Terminal Interface (System Control)

### Command Line UX Principles

#### **Immediate Feedback**
Every command should provide clear, immediate feedback about what happened:

```bash
$ auto-trader start --simulation
✅ Auto-Trader starting in SIMULATION mode
📊 Loaded 5 trade plans from config/active_plans.yaml
🔌 Connecting to IBKR (paper trading account)...
✅ Connected to IBKR successfully  
🤖 Discord notifications enabled
⚡ System ready - monitoring 3 symbols across 2 timeframes

Press Ctrl+C to stop gracefully
```

#### **Status-At-A-Glance**  
Provide immediate system overview:

```bash
$ auto-trader status
📊 AUTO-TRADER STATUS - 2025-08-03 14:30:15

🔌 CONNECTIONS:
   IBKR: ✅ Connected (Paper Trading)
   Discord: ✅ Webhook active

📈 ACTIVE PLANS: 5 total
   Awaiting Entry: 3 (AAPL, MSFT, GOOGL)
   Position Open: 2 (TSLA +100, NVDA -50)

🛡️  RISK MANAGEMENT:
   Portfolio Risk: 6.2% / 10.0% limit
   Account Value: $10,000
   Risk Capacity: $380 remaining
   
💰 TODAY'S PERFORMANCE:
   Trades: 4 executed | P&L: +$325 | Win Rate: 75%
   
⚠️  ALERTS: None
```

#### **Progressive Verbosity**
Support different detail levels based on user needs:

```bash
# Quick status
$ auto-trader status

# Detailed view  
$ auto-trader status --detailed

# Full debug info
$ auto-trader status --verbose
```

### Error Handling & Recovery

#### **Actionable Error Messages**
Every error should tell the user exactly what to do:

```bash
❌ ERROR: Invalid trade plan configuration
📁 File: config/active_plans.yaml
📍 Line 15: entry_level must be greater than 0
🔧 Fix: Change 'entry_level: -180.50' to 'entry_level: 180.50'

$ auto-trader validate-config
```

#### **Graceful Degradation**
Show what's working when parts fail:

```bash
⚠️  WARNING: Discord webhook unreachable
✅ IBKR connection active - trades will still execute
📝 Notifications logged to: logs/notifications.log
🔧 Fix webhook URL in .env file

Continue? [y/N]
```

## Interactive CLI Creation Wizard

### Guided Trade Plan Creation

The CLI wizard provides a step-by-step interface for creating trade plans with real-time validation and risk calculation. This interface bridges the gap between manual YAML editing and user-friendly plan creation.

#### **Wizard Flow Design**

**Initial Command & Context Setting**
```bash
$ auto-trader create-plan

🎯 AUTO-TRADER PLAN WIZARD
Creating new trade plan with guided assistance

📊 Current Portfolio Status:
   Account Value: $10,000
   Open Positions: 2 (TSLA, NVDA)
   Total Risk: 4.2% ($420)
   Available Risk: 5.8% ($580)

Let's create your trade plan step by step...
```

#### **Field-by-Field Prompts with Validation**

**Smart Symbol Input**
```bash
📈 Symbol (1-10 uppercase letters): AAPL
✅ Valid symbol: AAPL
💰 Current Price: $180.25 (market open)

📈 Symbol (1-10 uppercase letters): appl
❌ Invalid: Use uppercase letters only
📈 Symbol (1-10 uppercase letters): AAPL
✅ Valid symbol: AAPL
```

**Price Level Validation**
```bash
💲 Entry Level (current: $180.25): 180.50
✅ Entry level: $180.50

💲 Stop Loss: 185.00  
❌ Error: Stop loss ($185.00) must be BELOW entry ($180.50) for LONG position
💲 Stop Loss: 178.00
✅ Stop loss: $178.00 (1.39% stop distance)
```

**Risk Category with Live Calculation**
```bash
🛡️  Risk Category:
   [1] small  (1% risk) → ~40 shares, $100 risk
   [2] normal (2% risk) → ~80 shares, $200 risk
   [3] large  (3% risk) → ~120 shares, $300 risk

Choose risk level [1-3]: 2
✅ Risk Category: normal (2%)

📊 Calculated Position Size: 80 shares
💰 Dollar Risk: $200.00
📈 New Portfolio Risk: 6.2% (was 4.2%)
✅ Within 10% portfolio limit
```

#### **Plan Preview & Confirmation**

**Complete Plan Summary**
```bash
📋 TRADE PLAN PREVIEW:

📊 PLAN DETAILS:
   ID: AAPL_20250804_001
   Symbol: AAPL
   Entry: $180.50 (close_above, 15min)
   Stop: $178.00 (-1.39%)
   Target: $185.00 (+2.49%)
   
🛡️  RISK MANAGEMENT:
   Risk Category: normal (2%)
   Position Size: 80 shares
   Dollar Risk: $200.00
   Portfolio Risk: 6.2% (new total)
   
⚙️ EXECUTION:
   Function: close_above
   Timeframe: 15min
   Status: awaiting_entry

❓ Save this plan? [y/N]: y
✅ Plan saved to config/active_plans.yaml
📊 System will begin monitoring AAPL on next startup
```

#### **Error Handling & Recovery**

**Portfolio Risk Limit Exceeded**
```bash
🛡️  Risk Category:
   [1] small  (1% risk) → ~33 shares, $83 risk  
   [2] normal (2% risk) → ~67 shares, $167 risk
   [3] large  (3% risk) → ~100 shares, $250 risk ⚠️

Choose risk level [1-3]: 3
❌ PORTFOLIO RISK EXCEEDED
   Current Risk: 8.5%
   New Trade Risk: 2.5%
   Total Would Be: 11.0%
   Maximum Allowed: 10.0%

🔧 Suggestions:
   • Choose 'normal' risk (would be 9.2% total)
   • Close existing position to free up risk capacity
   • Reduce stop distance to lower risk per share

🛡️  Risk Category [1-2 only]: 2
✅ Risk Category: normal - Portfolio risk: 9.2% ✓
```

#### **Advanced Features**

**Quick Plan Creation with Defaults**
```bash
$ auto-trader create-plan --symbol AAPL --entry 180.50 --stop 178.00 --target 185.00

🎯 QUICK PLAN CREATION
Using defaults: risk=normal, function=close_above, timeframe=15min

📊 Calculated: 80 shares, $200 risk, 6.2% portfolio
✅ Plan AAPL_20250804_001 created and saved
```

**Plan Templates and Duplication**
```bash
$ auto-trader create-plan --template breakout

🎯 USING BREAKOUT TEMPLATE
Pre-filled: function=close_above, timeframe=15min, risk=normal

📈 Symbol: MSFT
💲 Entry Level: 420.00
💲 Stop Loss: 415.00
💲 Take Profit: 430.00

Continue with template values? [Y/n]: y
```

#### **Integration with Risk Management**

**Real-Time Risk Feedback**
```bash
💲 Stop Loss: 175.00
✅ Stop loss: $175.00 (3.06% stop distance)

⚠️  RISK WARNING: 
Large stop distance increases position risk
Calculated position: 36 shares (vs 80 with tighter stop)
Consider tighter stop for larger position size?

Proceed with $175.00 stop? [y/N]: n
💲 Stop Loss: 178.00
✅ Improved: 80 shares possible with $178.00 stop
```

## Cross-Interface Consistency

### Information Architecture

#### **Consistent Identifiers**
Use the same plan_id format across all interfaces:
- Discord: "🟢 **AAPL_20250803_001** LONG entry"
- Config file: `plan_id: "AAPL_20250803_001"`  
- Terminal: "✅ Plan AAPL_20250803_001 loaded successfully"

#### **Unified Status Language**
Same status terms across all interfaces:
- `awaiting_entry` (not "pending", "waiting", "active")
- `position_open` (not "filled", "in trade", "live")
- `position_closed` (not "completed", "finished", "done")

#### **Consistent Timing Format**
All timestamps in human-readable format:
- Discord: "14:23:45" (time only for today's events)
- Logs: "2025-08-03 14:23:45.123" (full timestamp)
- Config: "2025-08-03T14:23:45Z" (ISO format for parsing)

### Data Flow Transparency

#### **State Change Notifications**
When config changes, notify across all interfaces:

```bash
# Terminal
✅ Configuration reloaded - 2 new plans added

# Discord (if major changes)
ℹ️ **CONFIG UPDATE**
Added: AAPL_20250803_002, MSFT_20250803_001
Now monitoring 7 active plans
```

#### **Error Propagation**
Configuration errors should be visible everywhere:

```bash
# Terminal
❌ AAPL_20250803_001: Invalid stop_loss (must be < entry_level for LONG)

# Discord  
🚨 **CONFIG ERROR**
AAPL_20250803_001 disabled - invalid stop loss
Check config/active_plans.yaml line 23
```

## Safety & Risk Management UX

### Fail-Safe Defaults

#### **Simulation Mode Default**
New installations should default to simulation mode:

```yaml
# system_config.yaml
simulation_mode: true  # ← Must be explicitly changed to false
```

#### **Conservative Risk Limits**
Built-in protection that requires explicit override:

```yaml
# risk_settings.yaml  
max_position_percent: 5.0    # Max 5% of account per position
daily_loss_limit: 200.00     # Stop trading after $200 daily loss
max_open_positions: 3        # Limit simultaneous positions
```

### Pre-Execution Confirmations

#### **High-Risk Action Warnings**
For actions that could cause significant loss:

```bash
⚠️  WARNING: Switching to LIVE TRADING mode
💰 Account Balance: $10,000
📊 5 active plans with total risk: $1,250
🎯 Potential loss if all stops hit: $1,250

Type 'CONFIRM LIVE TRADING' to proceed: 
```

#### **Config Validation Gates**
Prevent dangerous configurations:

```bash
❌ VALIDATION FAILED: Plan AAPL_20250803_001
🔍 Issues found:
   • Stop loss ($185.00) is ABOVE entry ($180.50) for LONG position
   • Risk category 'medium' invalid (must be: small, normal, large)
   • Plan would exceed 10% portfolio risk limit (would be 12.3%)
   
🔧 Fix these issues before starting system
💡 Suggestion: Use 'small' risk category to stay within limits
```

## Monitoring & Observability UX

### Real-Time Status Dashboard (Terminal)

#### **Live System Monitor**
When running, provide continuous status updates:

```bash
AUTO-TRADER LIVE - 2025-08-03 14:30:15 EST

🔌 IBKR: Connected | Discord: Active | Mode: SIMULATION
🛡️  Portfolio Risk: 6.2% / 10.0% | Available: $380

📊 ACTIVE MONITORING:
   AAPL 15min | Last: $180.25 | Entry @ $180.50 ↗️  (80 shares, $200 risk)
   MSFT 5min  | Last: $415.80 | Entry @ $415.00 ✅  (calculating position...)
   TSLA open  | P&L: +$125 | Stop: $245.00 | Current: $248.50 ✅
   
⏰ Next bar close: AAPL 15min in 3m 45s

[Press 'q' to quit, 's' for detailed status, 'r' for risk summary]
```

### Historical Analysis UX

#### **Trade History Format**
CSV structure optimized for both system parsing and human analysis:

```csv
timestamp,plan_id,symbol,action,price,quantity,pnl,function,timeframe,duration_minutes
2025-08-03T14:30:00Z,AAPL_20250803_001,AAPL,entry,180.45,100,0.00,close_above,15min,0
2025-08-03T16:45:00Z,AAPL_20250803_001,AAPL,exit,185.25,100,480.00,take_profit,15min,135
```

#### **Performance Summary Generation**
Automated daily/weekly summaries:

```bash
$ auto-trader summary --week

📊 WEEK SUMMARY: Jul 28 - Aug 3, 2025
💰 Total P&L: +$1,247 (+6.2% account growth)
📈 Trades: 23 executed | 15 wins | 8 losses (65% win rate)
🎯 Best performer: AAPL (+$485) | Worst: TSLA (-$145)
⏱️  Avg hold time: 4h 23m
🔧 Top function: close_above_15min (12 trades, 70% win rate)
```

## Error Recovery & Support

### Diagnostic Information

#### **Self-Diagnostic Commands**
Help users troubleshoot issues:

```bash
$ auto-trader doctor

🔍 SYSTEM HEALTH CHECK:

✅ Configuration files valid
✅ IBKR credentials configured  
❌ Discord webhook unreachable (HTTP 404)
✅ Log files writable
⚠️  Disk space: 2.1GB free (recommend >5GB)

🔧 RECOMMENDED ACTIONS:
1. Check Discord webhook URL in .env file
2. Free up disk space in logs/ directory

$ auto-trader doctor --fix-permissions
```

#### **Debug Information Export**
When seeking support, make it easy to share relevant info:

```bash
$ auto-trader export-debug

📦 Debug package created: debug_20250803_143015.zip
📁 Contents:
   • System configuration (secrets removed)
   • Last 24h of logs  
   • Active trade plans
   • System environment info

Share this file for technical support.
```

## Implementation Checklist

### Discord Interface
- [ ] Implement consistent emoji vocabulary with risk management icons
- [ ] Create notification templates for all event types including risk alerts
- [ ] Add message formatting for mobile readability
- [ ] Include portfolio risk percentage in trade notifications
- [ ] Implement notification rate limiting to prevent spam
- [ ] Create daily/weekly summary automation with risk metrics

### Configuration Files  
- [ ] Design self-documenting YAML schema with risk_category field
- [ ] Create validation with clear error messages for risk violations
- [ ] Build template system for common trade types (breakout, pullback, swing)
- [ ] Remove position_size field (calculated dynamically)
- [ ] Implement automatic backup of config changes
- [ ] Add inline documentation and examples with risk categories

### Interactive CLI Creation Wizard
- [ ] Build step-by-step plan creation with real-time validation
- [ ] Implement live position size calculation during creation
- [ ] Add portfolio risk checking and limit enforcement
- [ ] Create plan preview with complete risk analysis
- [ ] Build error recovery for risk limit violations
- [ ] Add quick plan creation with command-line options
- [ ] Implement template-based plan creation
- [ ] Add plan editing and management commands

### Risk Management Integration
- [ ] Implement automated position sizing formula
- [ ] Build portfolio risk tracking across all interfaces
- [ ] Add 10% portfolio limit enforcement
- [ ] Create risk registry for open positions
- [ ] Build position size calculation with three risk levels
- [ ] Add real-time risk feedback in CLI wizard
- [ ] Implement risk-based trade blocking

### Terminal Interface
- [ ] Create status dashboard with real-time updates and risk metrics
- [ ] Implement progressive verbosity levels
- [ ] Design actionable error message formats including risk violations
- [ ] Build self-diagnostic system
- [ ] Add graceful shutdown with position summary
- [ ] Include portfolio risk in live monitoring display
- [ ] Add risk summary command and display

### Cross-Interface Consistency
- [ ] Establish unified terminology dictionary
- [ ] Implement consistent timestamp formatting
- [ ] Create shared status update system
- [ ] Design state change notification flow
- [ ] Build configuration change propagation
- [ ] Ensure consistent risk terminology across all interfaces
- [ ] Implement unified position sizing across all creation methods

---

## Conclusion

This UX guideline transforms the headless Auto-Trader system into an intuitive, safe, and observable trading platform. By treating Discord, config files, and terminal as a unified interface ecosystem, we create a user experience that rivals traditional GUI applications while maintaining the simplicity and reliability required for automated trading.

The key is consistency, clarity, and fail-safe design - ensuring that even in the absence of traditional UI elements, the trader always knows what the system is doing and can trust it with their capital.