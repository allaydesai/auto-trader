# Terminal Interface (System Control)

## Command Line UX Principles

### **Immediate Feedback**
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

### **Status-At-A-Glance**  
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

### **Progressive Verbosity**
Support different detail levels based on user needs:

```bash