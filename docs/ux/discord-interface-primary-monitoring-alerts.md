# Discord Interface (Primary Monitoring & Alerts)

## Notification Hierarchy & Visual Language

### **Critical Alerts (🚨 Red Zone)**
Use for system failures and risk violations that require immediate attention:

```
🚨 **CRITICAL: SYSTEM OFFLINE**
Connection to IBKR lost at 14:23:45
Auto-reconnect failed (attempt 3/5)
Active positions: AAPL (+100), MSFT (-50)
Manual intervention required
```

### **Trade Execution (🟢/🔴 Action Zone)**
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

### **Status Updates (ℹ️ Info Zone)**
System health and plan status updates:

```
ℹ️ **DAILY SUMMARY - 2025-08-03**
**Trades:** 3 executed | 2 wins | 1 loss
**P&L:** +$425 (+2.1% account)
**Active Plans:** 5 awaiting entry | 2 positions open
```

## Message Structure Standards

### **Scannable Format**
- **Bold key information** that needs immediate recognition
- Use consistent field ordering: Symbol → Action → Price → Context
- One key fact per line for mobile readability
- Include context for decision-making (timeframe, function used)

### **Actionable Information**
Every notification should answer: "What happened?" and "What do I need to do?"

```
❌ Poor: "Trade executed for AAPL"
✅ Good: "🟢 AAPL LONG 98 shares @ $180.45 | Risk: $196 (2.0%) | Portfolio: 6.2%"
```

### **Consistent Emoji Language**
- 🟢 Entry/Profit exits
- 🔴 Stop loss/Loss exits  
- 🟡 Warnings (risk approaching limits)
- 🚨 Critical failures requiring action
- ℹ️ System status and summaries
- ⚙️ Configuration changes
- 🛡️ Risk management notifications
- 📊 Position sizing and portfolio updates
