# Monitoring & Observability UX

## Real-Time Status Dashboard (Terminal)

### **Live System Monitor**
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

## Historical Analysis UX

### **Trade History Format**
CSV structure optimized for both system parsing and human analysis:

```csv
timestamp,plan_id,symbol,action,price,quantity,pnl,function,timeframe,duration_minutes
2025-08-03T14:30:00Z,AAPL_20250803_001,AAPL,entry,180.45,100,0.00,close_above,15min,0
2025-08-03T16:45:00Z,AAPL_20250803_001,AAPL,exit,185.25,100,480.00,take_profit,15min,135
```

### **Performance Summary Generation**
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
