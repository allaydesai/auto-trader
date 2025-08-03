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
**AAPL** | LONG 100 @ $180.45
**Function:** close_above_15min
**Stop:** $178.00 | **Target:** $185.00
**Risk:** $245 (2.1% account)
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
✅ Good: "🟢 AAPL LONG entry @ $180.45 | Stop @ $178.00 | Risk: 2.1%"
```

#### **Consistent Emoji Language**
- 🟢 Entry/Profit exits
- 🔴 Stop loss/Loss exits  
- 🟡 Warnings (risk approaching limits)
- 🚨 Critical failures requiring action
- ℹ️ System status and summaries
- ⚙️ Configuration changes

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
    
    # Entry/Exit Levels (always use 2 decimal places)
    entry_level: 180.50    # Trigger level for position entry
    stop_loss: 178.00      # Maximum loss exit
    take_profit: 185.00    # Profit target exit
    position_size: 100     # Number of shares
    
    # Execution Logic
    entry_function:
      type: "close_above"   # Options: close_above, close_below, trailing_stop
      timeframe: "15min"    # Bar size: 1min, 5min, 15min, 30min, 1hour, 4hour, 1day
      
    # Current Status (auto-updated by system)
    status: "awaiting_entry"  # awaiting_entry, position_open, position_closed
    created_at: "2025-08-03T09:30:00Z"
```

#### **Validation-Friendly Design**
Structure that prevents common errors:

```yaml
# ❌ Error-Prone
entry: 180.5
stop: 178
target: 185

# ✅ Clear and Validated
entry_level: 180.50  # Must be > 0, 2+ decimal places
stop_loss: 178.00    # Must be != entry_level  
take_profit: 185.00  # Must be != entry_level
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
├── risk_settings.yaml     # Risk management rules
├── system_config.yaml     # System-wide settings
└── templates/
    ├── swing_trade.yaml   # Template for swing trades
    └── day_trade.yaml     # Template for day trades
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
  position_size: 100            # ← Adjust size
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
   • Position size (1000) exceeds max position limit (500)
   
🔧 Fix these issues before starting system
```

## Monitoring & Observability UX

### Real-Time Status Dashboard (Terminal)

#### **Live System Monitor**
When running, provide continuous status updates:

```bash
AUTO-TRADER LIVE - 2025-08-03 14:30:15 EST

🔌 IBKR: Connected | Discord: Active | Mode: SIMULATION

📊 ACTIVE MONITORING:
   AAPL 15min | Last: $180.25 | Entry @ $180.50 ↗️  (need +$0.25)
   MSFT 5min  | Last: $415.80 | Entry @ $415.00 ✅  (triggered - validating)
   TSLA open  | P&L: +$125 | Stop: $245.00 | Current: $248.50 ✅
   
⏰ Next bar close: AAPL 15min in 3m 45s

[Press 'q' to quit, 's' for detailed status]
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
- [ ] Implement consistent emoji vocabulary
- [ ] Create notification templates for all event types  
- [ ] Add message formatting for mobile readability
- [ ] Implement notification rate limiting to prevent spam
- [ ] Create daily/weekly summary automation

### Configuration Files  
- [ ] Design self-documenting YAML schema
- [ ] Create validation with clear error messages
- [ ] Build template system for common trade types
- [ ] Implement automatic backup of config changes
- [ ] Add inline documentation and examples

### Terminal Interface
- [ ] Create status dashboard with real-time updates
- [ ] Implement progressive verbosity levels
- [ ] Design actionable error message formats  
- [ ] Build self-diagnostic system
- [ ] Add graceful shutdown with position summary

### Cross-Interface Consistency
- [ ] Establish unified terminology dictionary
- [ ] Implement consistent timestamp formatting
- [ ] Create shared status update system
- [ ] Design state change notification flow
- [ ] Build configuration change propagation

---

## Conclusion

This UX guideline transforms the headless Auto-Trader system into an intuitive, safe, and observable trading platform. By treating Discord, config files, and terminal as a unified interface ecosystem, we create a user experience that rivals traditional GUI applications while maintaining the simplicity and reliability required for automated trading.

The key is consistency, clarity, and fail-safe design - ensuring that even in the absence of traditional UI elements, the trader always knows what the system is doing and can trust it with their capital.