# Auto-Trader Configuration Guide

## Configuration Hierarchy

The Auto-Trader system uses a three-tier configuration hierarchy, with clear separation of concerns:

```
1. Environment Variables (.env) - HIGHEST PRIORITY
   └── Deployment-specific settings and secrets
   
2. System Configuration (config.yaml)
   └── Application behavior and limits
   
3. User Preferences (user_config.yaml)
   └── Trading preferences and defaults
```

## File Purposes and Contents

### 1. `.env` - Environment Variables (Deployment-Specific)

**Purpose:** Contains deployment-specific settings that vary between environments (development, paper trading, live trading) and secrets that should never be committed to version control.

**What belongs here:**
- ✅ IBKR connection details (host, port, client_id)
- ✅ API keys and secrets (Discord webhook, future APIs)
- ✅ Environment-specific overrides
- ✅ Non-standard file paths

**What DOESN'T belong here:**
- ❌ Application behavior settings (use config.yaml)
- ❌ Trading parameters (use user_config.yaml)
- ❌ Risk limits (use config.yaml)

**Example:**
```bash
# Connection settings (vary per deployment)
IBKR_HOST=127.0.0.1       # Local TWS/Gateway
IBKR_PORT=7497            # Paper trading port
IBKR_CLIENT_ID=1          # Unique client identifier

# Secrets (never commit these!)
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/xxx/yyy

# Optional overrides
SIMULATION_MODE=true      # Forces simulation regardless of config.yaml
DEBUG=true               # Enables debug logging
```

### 2. `config.yaml` - System Configuration

**Purpose:** Defines how the application behaves, including risk limits, trading rules, and system-wide settings. These settings are the same across deployments unless explicitly overridden.

**What belongs here:**
- ✅ IBKR behavior settings (timeout, reconnect attempts)
- ✅ Risk management limits
- ✅ Trading system rules
- ✅ Logging configuration
- ✅ Default operational parameters

**What DOESN'T belong here:**
- ❌ Connection details (use .env)
- ❌ Secrets or API keys (use .env)
- ❌ User-specific preferences (use user_config.yaml)

**Example:**
```yaml
ibkr:
  timeout: 30                    # How long to wait for connection
  reconnect_attempts: 5          # Max reconnection attempts
  graceful_shutdown: true        # Behavior on shutdown

risk:
  max_position_percent: 10.0     # Position size limit
  daily_loss_limit_percent: 2.0  # Daily loss limit
  max_concurrent_trades: 10      # Concurrent trade limit

trading:
  simulation_mode: true          # Default mode (can be overridden by .env)
  market_hours_only: true        # Trading time restrictions
  order_timeout: 60              # Order timeout in seconds
```

### 3. `user_config.yaml` - User Preferences

**Purpose:** Contains user-specific trading preferences and defaults that customize the trading behavior for individual traders.

**What belongs here:**
- ✅ Account value for position sizing
- ✅ Default risk categories
- ✅ Preferred timeframes
- ✅ Personal trading preferences

**What DOESN'T belong here:**
- ❌ System limits (use config.yaml)
- ❌ Connection settings (use .env)
- ❌ Application behavior (use config.yaml)

**Example:**
```yaml
# Account Configuration
account_value: 10000.00
default_account_value: 10000.00
default_risk_category: "normal"  # small, normal, or large

# Trading Preferences
preferred_timeframes: 
  - "15min"
  - "30min"
default_execution_function: "close_above"

# Position Preferences
default_position_size_override: null
use_fractional_shares: false

# Environment (informational only)
environment: "paper"  # Placeholder – not enforced yet
```

## Configuration Priority and Overrides

### Override Hierarchy

When the same setting appears in multiple places, the priority is:

1. **Environment Variable** (highest priority)
2. **Config YAML file**
3. **Default value in code** (lowest priority)

### Specific Override Examples

#### Simulation Mode
```
Priority Order:
1. SIMULATION_MODE environment variable (.env)
2. trading.simulation_mode in config.yaml
3. Default value: true (in code)
```

#### Debug Logging
```
Priority Order:
1. DEBUG environment variable (.env)
2. logging.level in config.yaml
3. Default value: INFO (in code)
```

#### IBKR Connection
```
Always from environment:
- IBKR_HOST (.env only)
- IBKR_PORT (.env only)  
- IBKR_CLIENT_ID (.env only)

From config.yaml:
- ibkr.timeout
- ibkr.reconnect_attempts
- ibkr.graceful_shutdown
```

## How Settings Are Used

### In Main Application (`src/main.py`)

```python
# IBKR connection uses environment variables
app_config = ApplicationConfig(
    ibkr_host=self.settings.ibkr_host,        # From .env
    ibkr_port=self.settings.ibkr_port,        # From .env
    ibkr_client_id=self.settings.ibkr_client_id, # From .env
    ...
)

# Simulation mode checks environment override first
simulation_mode = (
    self.settings.simulation_mode  # From .env if set
    if self.settings.simulation_mode is not None
    else system_config.trading.simulation_mode  # Otherwise from config.yaml
)
```

### In IBKR Client (`src/auto_trader/integrations/ibkr_client/client.py`)

```python
# Connection parameters from environment
host = self._settings.ibkr_host        # From .env
port = self._settings.ibkr_port        # From .env
client_id = self._settings.ibkr_client_id  # From .env

# Behavior settings from config.yaml
timeout = self._config_loader.system_config.ibkr.timeout
reconnect_attempts = self._config_loader.system_config.ibkr.reconnect_attempts
```

## Best Practices

### 1. Never Commit Secrets
- Always use `.env` for sensitive data
- Keep `.env` in `.gitignore`
- Provide `.env.example` with dummy values

### 2. Use the Right File
- **Deployment varies?** → Use `.env`
- **Behavior setting?** → Use `config.yaml`
- **User preference?** → Use `user_config.yaml`

### 3. Environment-Specific Deployments

**Development:**
```bash
IBKR_HOST=127.0.0.1
IBKR_PORT=7497  # Paper trading
SIMULATION_MODE=true
DEBUG=true
```

**Paper Trading:**
```bash
IBKR_HOST=127.0.0.1
IBKR_PORT=7497  # Paper trading
# Don't set SIMULATION_MODE, use config.yaml default
DEBUG=false
```

**Live Trading:**
```bash
IBKR_HOST=127.0.0.1
IBKR_PORT=7496  # Live trading port
# Don't set SIMULATION_MODE, config.yaml should have false
DEBUG=false
```

### 4. Configuration Validation

Always validate configuration before starting:
```bash
# Check configuration without starting
uv run python run_auto_trader.py --check-config
```

## Common Configuration Scenarios

### Scenario 1: Local Development
```bash
# .env
IBKR_HOST=127.0.0.1
IBKR_PORT=7497
DEBUG=true
SIMULATION_MODE=true  # Force simulation during development
```

### Scenario 2: Remote TWS Connection
```bash
# .env
IBKR_HOST=192.168.1.100  # Remote machine IP
IBKR_PORT=7497
IBKR_CLIENT_ID=2  # Different ID if multiple connections
```

### Scenario 3: Production with Strict Limits
```yaml
# config.yaml
risk:
  max_position_percent: 5.0      # Stricter position limit
  daily_loss_limit_percent: 1.0  # Tighter daily loss
  max_concurrent_trades: 3       # Fewer concurrent trades
```

### Scenario 4: Different Account Sizes
```yaml
# user_config.yaml
account_value: 25000.00  # Larger account
default_risk_category: "small"  # But more conservative
```

## Troubleshooting

### Issue: Settings not taking effect
**Solution:** Check override hierarchy - environment variables override YAML files

### Issue: Connection settings in config.yaml ignored
**Solution:** IBKR connection settings (host, port, client_id) only come from .env

### Issue: Can't connect to IBKR
**Solution:** Verify IBKR_HOST, IBKR_PORT, and IBKR_CLIENT_ID in .env match your TWS/Gateway setup

### Issue: Wrong simulation mode
**Solution:** Check if SIMULATION_MODE is set in .env (overrides config.yaml)

## Summary

The three-tier configuration system provides:
- **Security**: Secrets stay in .env (never committed)
- **Flexibility**: Environment-specific overrides
- **Clarity**: Clear separation of concerns
- **Maintainability**: Settings in appropriate files

Remember: 
- `.env` = WHERE and HOW to connect
- `config.yaml` = WHAT the system can do  
- `user_config.yaml` = WHO is trading and their preferences