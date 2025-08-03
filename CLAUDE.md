# Auto-Trader AI Agent Context

> **Context Document for AI Agents implementing the Auto-Trader system**  
> Read this document completely before starting any implementation tasks.

## Project Overview

**Auto-Trader** is a personal automated trading system designed to execute discretionary trades with time-based triggers to avoid institutional stop-hunting algorithms. Built as a backend-only Python monolith with Discord as the UI interface.

**Core Problem Solved:** Retail traders lose money to institutional algorithms that exploit simple price-level triggers. This system uses candle-close based execution functions to filter noise and avoid manipulation.

**MVP Timeline:** 4 weeks  
**Single User System:** Built for the developer/trader only  
**Architecture:** Python monolith with modular components  

## Core Development Philosophy

### KISS (Keep It Simple, Stupid)
- Choose straightforward solutions over complex ones
- Simple solutions are easier to understand, maintain, and debug
- No premature optimization or over-engineering

### YAGNI (You Aren't Gonna Need It)
- Implement features only when needed, not when anticipated
- Avoid speculation-driven development
- Focus on MVP requirements only

### Design Principles
- **Dependency Inversion:** High-level modules depend on abstractions
- **Open/Closed:** Open for extension, closed for modification
- **Single Responsibility:** Each function/class has one clear purpose
- **Fail Fast:** Check errors early, raise exceptions immediately

## File and Code Structure Requirements

### Strict Limits
- **Files:** Maximum 500 lines of code
- **Functions:** Maximum 50 lines with single responsibility
- **Classes:** Maximum 100 lines representing single concept
- **Line Length:** Maximum 100 characters (ruff enforced)

### Vertical Slice Architecture
```
src/auto_trader/
    __init__.py
    main.py                    # Entry point, max 100 lines
    
    models/                    # Pydantic models
        __init__.py
        trade_plan.py
        position.py
        market_data.py
        tests/
            test_trade_plan.py
            test_position.py
    
    trade_engine/             # Core execution logic
        __init__.py
        engine.py
        execution_functions.py
        tests/
            test_engine.py
            test_execution_functions.py
    
    integrations/            # External services
        ibkr_client/
            __init__.py
            client.py
            circuit_breaker.py
            tests/
                test_client.py
        discord_notifier/
            __init__.py
            notifier.py
            tests/
                test_notifier.py
```

## Technology Stack (DEFINITIVE)

### Core Technologies
- **Python:** 3.11.8 (exact version)
- **Package Manager:** UV 0.5.0+ (NEVER update pyproject.toml directly)
- **Async Runtime:** asyncio (stdlib)
- **Data Processing:** pandas 2.2.0, numpy 1.26.0
- **Data Validation:** pydantic 2.9.0 (v2 syntax only)
- **Logging:** loguru 0.7.2 (NOT stdlib logging)
- **HTTP Client:** httpx 0.27.0 (for Discord webhooks)
- **Scheduling:** APScheduler 3.10.4

### Financial Integrations
- **IBKR Integration:** ib-async 1.0.0+ (NOT ib_insync)
- **Market Data:** IBKR only for MVP (FMP deferred to post-MVP)

### Development Tools
- **Testing:** pytest 8.3.0 + pytest-asyncio 0.24.0
- **Linting:** ruff 0.7.0 (replaces black, flake8, isort)
- **Type Checking:** mypy 1.11.0
- **Time Zones:** pytz 2024.1

## Data Models and Validation

### Pydantic V2 Requirements
```python
from pydantic import BaseModel, Field
from decimal import Decimal
from datetime import datetime
from typing import Optional

class TradePlan(BaseModel):
    """Represents a complete trading strategy for a single symbol."""
    plan_id: str = Field(..., description="Unique identifier")
    symbol: str = Field(..., min_length=1, max_length=10)
    entry_level: Decimal = Field(..., gt=0, decimal_places=4)
    stop_loss: Decimal = Field(..., gt=0, decimal_places=4)
    take_profit: Decimal = Field(..., gt=0, decimal_places=4)
    position_size: int = Field(..., gt=0)
    
    model_config = ConfigDict(
        validate_assignment=True,
        str_strip_whitespace=True,
        use_enum_values=True
    )
```

### Critical Rules
- **Always use Decimal for money:** Never float for prices/P&L
- **UTC timestamps everywhere:** Convert at display layer only
- **Type hints required:** All functions must have complete annotations
- **Entity-specific IDs:** trade_id, position_id, plan_id (not generic id)

## Package Management with UV

### Essential Commands
```bash
# NEVER edit pyproject.toml directly - ALWAYS use UV commands

# Add dependency
uv add ib-async pandas pydantic loguru

# Add dev dependency  
uv add --dev pytest ruff mypy

# Remove package
uv remove package-name

# Run commands
uv run pytest
uv run ruff check .
uv run ruff format .
uv run mypy src/
```

## Code Style and Conventions

### Python Style (Enforced by Ruff)
- **Strings:** Double quotes always
- **Line Length:** 100 characters maximum
- **Trailing Commas:** Required in multi-line structures
- **Import Order:** Ruff handles automatically

### Naming Conventions
- **Variables/Functions:** snake_case
- **Classes:** PascalCase  
- **Constants:** UPPER_SNAKE_CASE
- **Private:** _leading_underscore
- **Files:** snake_case.py

### Google-Style Docstrings Required
```python
def calculate_position_size(
    account_balance: Decimal,
    risk_percent: float,
    entry_price: Decimal,
    stop_price: Decimal
) -> int:
    """
    Calculate position size based on risk management rules.
    
    Args:
        account_balance: Total account balance
        risk_percent: Maximum risk percentage (0-100)
        entry_price: Planned entry price
        stop_price: Stop loss price
        
    Returns:
        Number of shares/contracts to trade
        
    Raises:
        ValueError: If risk_percent is outside 0-100 range
        ValueError: If stop_price equals entry_price
        
    Example:
        >>> calculate_position_size(Decimal("10000"), 2.0, Decimal("100"), Decimal("95"))
        40
    """
```

## Architecture Patterns and Components

### Key Design Patterns
- **Repository Pattern:** Abstract data access (trade plans, state)
- **Strategy Pattern:** Pluggable execution functions
- **Observer Pattern:** WebSocket market data subscriptions
- **Circuit Breaker:** IBKR connection resilience
- **Event-Driven:** Market data events trigger execution

### Core Components

#### 1. Trade Engine (trade_engine/)
**Responsibility:** Core orchestration of trade execution logic
```python
class TradeEngine:
    async def start(self) -> None:
        """Initialize engine and start processing."""
        
    async def evaluate_trade_plans(self) -> None:
        """Check all plans for signals."""
        
    async def on_market_data(self, data: MarketData) -> None:
        """Handle incoming price data."""
```

#### 2. IBKR Client (integrations/ibkr_client/)
**Responsibility:** All Interactive Brokers interactions
```python
class IBKRClient:
    async def connect(self) -> None:
        """Establish IBKR connection with circuit breaker."""
        
    async def place_order(self, order: Order) -> str:
        """Submit order and return order ID."""
```

#### 3. Risk Manager (risk_management/)
**Responsibility:** Pre-trade risk validation
```python
class RiskManager:
    def check_position_size(self, symbol: str, quantity: int) -> RiskCheck:
        """Validate position size against account balance."""
        
    def check_daily_loss_limit(self) -> RiskCheck:
        """Ensure daily loss limit not exceeded."""
```

## Data Persistence Strategy

### File-Based Storage (MVP)
- **Trade Plans:** YAML files (human-editable)
- **Position State:** JSON files (with versioned backups)
- **Trade History:** CSV files (monthly rotation)
- **Configuration:** config.yaml + .env for secrets

### File Schemas
```yaml
# trade_plans/active_plans.yaml
plans:
  - plan_id: "AAPL_20250803_001"
    symbol: "AAPL"
    entry_level: 180.50
    stop_loss: 178.00
    take_profit: 185.00
    position_size: 100
    entry_function:
      type: "close_above"
      timeframe: "15min"
    status: "awaiting_entry"
```

## Error Handling and Logging

### Custom Exception Hierarchy
```python
class AutoTraderError(Exception):
    """Base exception for all auto-trader errors."""
    pass

class RiskLimitExceeded(AutoTraderError):
    """Raised when risk limits are violated."""
    def __init__(self, limit_type: str, current: Decimal, max_allowed: Decimal):
        self.limit_type = limit_type
        self.current = current  
        self.max_allowed = max_allowed
        super().__init__(f"{limit_type}: {current} exceeds limit {max_allowed}")
```

### Logging with Loguru
```python
from loguru import logger

# Configure structured logging
logger.add(
    "logs/auto_trader_{time:YYYY-MM-DD}.log",
    rotation="1 day",
    retention="30 days",
    format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line} | {message}",
    level="INFO"
)

# Usage
logger.info("Trade executed", symbol="AAPL", price=180.75, quantity=100)
logger.error("IBKR connection failed", error=str(e), retry_count=3)
```

## Testing Requirements

### Test Organization (Next to Code)
```
trade_engine/
    engine.py
    execution_functions.py
    tests/
        test_engine.py
        test_execution_functions.py
        conftest.py  # Shared fixtures
```

### Testing Standards
- **Unit Tests:** 80% coverage minimum, 100% for risk management
- **Integration Tests:** IBKR connection, file I/O, complete workflows
- **Fixtures:** Use pytest fixtures for all setup
- **Naming:** `test_[component]_[action]_[expected_result]`

### Required Test Patterns
```python
@pytest.fixture
def sample_trade_plan():
    """Provide a sample trade plan for testing."""
    return TradePlan(
        plan_id="TEST_001",
        symbol="AAPL", 
        entry_level=Decimal("180.50"),
        stop_loss=Decimal("178.00"),
        take_profit=Decimal("185.00"),
        position_size=100
    )

def test_risk_manager_rejects_oversized_position(sample_trade_plan):
    """Test that risk manager rejects positions exceeding size limits."""
    risk_manager = RiskManager(max_position_percent=10.0)
    
    result = risk_manager.check_position_size("AAPL", 1000)
    
    assert not result.passed
    assert "position size" in result.reason.lower()
```

## Discord Integration

### Webhook Notifications
```python
class DiscordNotifier:
    async def send_trade_entry(self, trade: TradeEntry) -> None:
        """Send entry notification with markdown formatting."""
        message = f"""
🟢 **TRADE ENTRY**
**Symbol:** {trade.symbol}
**Side:** {trade.side}
**Price:** ${trade.price:.2f}
**Quantity:** {trade.quantity}
**Function:** {trade.execution_function}
**Time:** {trade.timestamp.strftime('%H:%M:%S')}
        """.strip()
        
    async def send_trade_exit(self, trade: TradeExit) -> None:
        """Send exit notification with P&L."""
        pnl_emoji = "🟢" if trade.pnl > 0 else "🔴"
        message = f"{pnl_emoji} **TRADE EXIT** | P&L: ${trade.pnl:.2f}"
```

## Security Requirements

### Secrets Management
```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    """Application settings with validation."""
    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 7497
    ibkr_client_id: int
    discord_webhook_url: str
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False
    )

# NEVER log secrets
logger.info("IBKR connected", host=settings.ibkr_host, port=settings.ibkr_port)
# DON'T: logger.info("IBKR connected", credentials=settings.ibkr_password)
```

## MVP Functional Requirements (Complete List)

1. **FR1:** Load trade plans from YAML files
2. **FR2:** Connect to IBKR for market data and execution  
3. **FR3:** Implement 3 execution functions (close_above, close_below, trailing_stop)
4. **FR4:** Execute risk management checks before orders
5. **FR5:** Send Discord notifications for trade events
6. **FR6:** Support simulation mode toggle
7. **FR7:** Append trades to history file
8. **FR8:** Persist/recover position state across restarts

## Non-Functional Requirements

- **Performance:** <1 second execution latency (signal to order)
- **Reliability:** Handle IBKR disconnections with circuit breaker
- **Platforms:** Windows and Linux desktop environments
- **Rate Limits:** Respect IBKR 50 msg/sec limit
- **Testing:** Unit test coverage for critical paths

## Critical Implementation Notes

### WebSocket Event Handling
```python
# Use ib-async patterns for WebSocket management
from ib_async import IB, Stock, MarketOrder

class IBKRClient:
    def __init__(self):
        self.ib = IB()
        self.circuit_breaker = CircuitBreaker(failure_threshold=5)
        
    async def connect(self):
        """Connect with circuit breaker protection."""
        try:
            await self.ib.connectAsync(host=self.host, port=self.port)
            self.ib.disconnectedEvent += self._on_disconnect
        except Exception as e:
            self.circuit_breaker.record_failure()
            raise IBKRConnectionError(f"Connection failed: {e}")
```

### Time-Based Execution Functions
```python
class ExecutionFunction:
    """Base class for all execution functions."""
    
    def __init__(self, timeframe: str, parameters: dict):
        self.timeframe = timeframe  # "1min", "5min", "15min", etc.
        self.parameters = parameters
        
    async def evaluate(self, market_data: MarketData, position_state: PositionState) -> ExecutionSignal:
        """Evaluate if execution condition is met."""
        raise NotImplementedError

class CloseAboveFunction(ExecutionFunction):
    """Execute when price closes above threshold."""
    
    async def evaluate(self, market_data: MarketData, position_state: PositionState) -> ExecutionSignal:
        threshold = Decimal(str(self.parameters["threshold"]))
        
        # Only evaluate on candle close for specified timeframe
        if not market_data.is_candle_close(self.timeframe):
            return ExecutionSignal.NO_ACTION
            
        if market_data.close_price > threshold:
            return ExecutionSignal.ENTER_LONG
            
        return ExecutionSignal.NO_ACTION
```

## Deployment and Environment

### Local Deployment Only (MVP)
- **Development:** Paper trading account
- **Production:** Live IBKR account
- **Process Management:** systemd (Linux) / Task Scheduler (Windows)
- **No Docker/Cloud:** Keep it simple for single-user system

### Environment Files
```bash
# .env (never commit)
IBKR_HOST=127.0.0.1
IBKR_PORT=7497
IBKR_CLIENT_ID=1
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
SIMULATION_MODE=true
DEBUG=false
```

## Common Pitfalls to Avoid

1. **NEVER use float for money:** Always Decimal
2. **NEVER hardcode API credentials:** Use environment variables
3. **NEVER edit pyproject.toml directly:** Always use UV commands
4. **NEVER use print statements:** Use logger exclusively
5. **NEVER commit secrets:** Use .env files (gitignored)
6. **NEVER exceed file/function limits:** 500/50 lines respectively
7. **NEVER skip type hints:** All functions must be typed
8. **NEVER use complex patterns:** Keep it simple (KISS)

## Git Workflow

### Branch Strategy
- **main:** Production-ready code
- **feature/*:** New features
- **fix/*:** Bug fixes
- **docs/*:** Documentation updates

### Commit Messages (NEVER mention AI generation)
```
feat(engine): add trailing stop execution function

Implement trailing stop logic with configurable trail percentage
Add unit tests for various market scenarios
Update execution function registry

Closes #23
```

## Success Criteria for AI Agents

An AI agent implementation is successful when:

1. **All files under limits:** 500 lines max, functions under 50 lines
2. **Complete type annotations:** Every function properly typed
3. **Comprehensive tests:** All public methods tested with fixtures
4. **Proper error handling:** Custom exceptions with clear messages
5. **Discord notifications:** Rich formatting with trade details
6. **State persistence:** Reliable recovery across restarts
7. **IBKR integration:** Stable connection with circuit breaker
8. **Risk management:** No trades violate position/loss limits
9. **Performance:** <1 second execution latency achieved
10. **Code quality:** Passes ruff, mypy, and pytest checks

## Quick Reference Commands

```bash
# Setup
uv venv && uv sync

# Development
uv run pytest                    # Run tests
uv run ruff check .             # Check linting  
uv run ruff format .            # Format code
uv run mypy src/                # Type checking

# Add dependencies (NEVER edit pyproject.toml)
uv add pydantic loguru pandas
uv add --dev pytest ruff mypy

# Run application
uv run python -m auto_trader.main
```

## Final Reminder

This is a **personal trading system** handling **real money**. Prioritize:
1. **Reliability** over features
2. **Simplicity** over cleverness  
3. **Testing** over speed
4. **Security** over convenience

Read the complete PRD and Architecture documents before implementing any component. When in doubt, ask for clarification rather than guessing.

---

*This context document is the single source of truth for AI agents. Keep it updated as architectural decisions evolve.*