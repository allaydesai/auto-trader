# Error Recovery & Support

## Diagnostic Information

### **Self-Diagnostic Commands**
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

### **Debug Information Export**
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
