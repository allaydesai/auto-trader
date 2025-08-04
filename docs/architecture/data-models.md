# Data Models

## TradePlan
**Purpose:** Represents a complete trading strategy for a single symbol including entry/exit logic

**Key Attributes:**
- plan_id: str - Unique identifier for the plan
- symbol: str - Trading symbol (e.g., "AAPL")
- entry_level: Decimal - Price level for entry
- stop_loss: Decimal - Stop loss price
- take_profit: Decimal - Target price
- risk_category: str - Risk level: "small" (1%), "normal" (2%), "large" (3%)
- entry_function: ExecutionFunction - Entry trigger logic
- exit_function: ExecutionFunction - Exit trigger logic
- status: TradePlanStatus - Current state (awaiting_entry, position_open, completed)
- calculated_position_size: int - Dynamically calculated based on risk management
- dollar_risk: Decimal - Calculated risk amount in dollars

**Relationships:**
- Contains ExecutionFunction configurations
- Tracked by Position when active
- Generates TradeHistory records

## ExecutionFunction
**Purpose:** Configuration for time-based execution logic

**Key Attributes:**
- function_type: str - Type identifier (close_above, close_below, trailing_stop)
- timeframe: str - Candle size (1min, 5min, 15min, etc.)
- parameters: dict - Function-specific parameters
- last_evaluated: datetime - Last evaluation timestamp

**Relationships:**
- Embedded in TradePlan for entry/exit logic
- Evaluated by ExecutionEngine

## Position
**Purpose:** Represents an active trading position

**Key Attributes:**
- position_id: str - Unique identifier
- symbol: str - Trading symbol
- entry_price: Decimal - Actual fill price
- quantity: int - Filled quantity
- entry_time: datetime - Position open timestamp
- stop_order_id: str - IBKR stop order ID
- target_order_id: str - IBKR target order ID
- pnl: Decimal - Current P&L

**Relationships:**
- References original TradePlan
- Tracked in PositionState for persistence

## TradeHistory
**Purpose:** Immutable record of completed trades

**Key Attributes:**
- trade_id: str - Unique identifier
- symbol: str - Trading symbol
- side: str - BUY/SELL
- entry_price: Decimal - Entry fill price
- exit_price: Decimal - Exit fill price
- quantity: int - Trade size
- pnl: Decimal - Realized P&L
- fees: Decimal - Transaction costs
- entry_time: datetime - Entry timestamp
- exit_time: datetime - Exit timestamp
- exit_reason: str - stop_loss/take_profit/manual

**Relationships:**
- Generated from completed Positions
- Appended to CSV history file
