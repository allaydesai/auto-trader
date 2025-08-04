# Cross-Interface Consistency

## Information Architecture

### **Consistent Identifiers**
Use the same plan_id format across all interfaces:
- Discord: "🟢 **AAPL_20250803_001** LONG entry"
- Config file: `plan_id: "AAPL_20250803_001"`  
- Terminal: "✅ Plan AAPL_20250803_001 loaded successfully"

### **Unified Status Language**
Same status terms across all interfaces:
- `awaiting_entry` (not "pending", "waiting", "active")
- `position_open` (not "filled", "in trade", "live")
- `position_closed` (not "completed", "finished", "done")

### **Consistent Timing Format**
All timestamps in human-readable format:
- Discord: "14:23:45" (time only for today's events)
- Logs: "2025-08-03 14:23:45.123" (full timestamp)
- Config: "2025-08-03T14:23:45Z" (ISO format for parsing)

## Data Flow Transparency

### **State Change Notifications**
When config changes, notify across all interfaces:

```bash