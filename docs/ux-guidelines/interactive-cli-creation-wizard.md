# Interactive CLI Creation Wizard

## Guided Trade Plan Creation

The CLI wizard provides a step-by-step interface for creating trade plans with real-time validation and risk calculation. This interface bridges the gap between manual YAML editing and user-friendly plan creation.

### **Wizard Flow Design**

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

### **Field-by-Field Prompts with Validation**

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

### **Plan Preview & Confirmation**

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

### **Error Handling & Recovery**

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

### **Advanced Features**

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

### **Integration with Risk Management**

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
