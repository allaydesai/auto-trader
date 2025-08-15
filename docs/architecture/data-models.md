# Data Models

## Implementation Status

- ✅ **TradePlan & ExecutionFunction** (Story 1.2): Complete with pydantic validation
- ✅ **ValidationResult & ValidationError** (Story 1.2): Comprehensive error reporting models
- ✅ **TradePlanStatus** (Story 1.2): Enum for plan lifecycle states
- ✅ **Configuration Models** (Story 1.1): Settings, SystemConfig, UserPreferences with validation
- ⏸️ **Position & TradeHistory**: Awaiting trade execution implementation
- ⏸️ **MarketData**: Awaiting IBKR integration

---

## ✅ TradePlan (Implemented - Story 1.2)
**Status:** Complete with comprehensive pydantic validation  
**Purpose:** Represents a complete trading strategy for a single symbol including entry/exit logic

**Key Attributes:**
- `plan_id: str` - Unique identifier (format: SYMBOL_YYYYMMDD_NNN)
- `symbol: str` - Trading symbol (1-10 uppercase chars, validated)
- `entry_level: Decimal` - Price level for entry (4 decimal precision)
- `stop_loss: Decimal` - Stop loss price (4 decimal precision) 
- `take_profit: Decimal` - Target price (4 decimal precision)
- `risk_category: RiskCategory` - Risk level enum: small(1%), normal(2%), large(3%)
- `entry_function: ExecutionFunction` - Entry trigger logic
- `exit_function: ExecutionFunction` - Exit trigger logic
- `status: TradePlanStatus` - Current state
- `calculated_position_size: Optional[int]` - Dynamically calculated
- `dollar_risk: Optional[Decimal]` - Calculated risk amount

**Validation Rules:**
- Symbol: 1-10 uppercase characters, no special characters
- Prices: Positive decimals with max 4 decimal places
- Entry level ≠ stop loss (prevents zero-risk trades)
- Risk category validation against allowed values
- Plan ID uniqueness across all loaded plans

**Relationships:**
- Contains ExecutionFunction configurations
- Tracked by Position when active
- Generates TradeHistory records

## ✅ ExecutionFunction (Implemented - Story 1.2)
**Status:** Complete with validation  
**Purpose:** Configuration for time-based execution logic

**Key Attributes:**
- `function_type: str` - Type identifier (close_above, close_below, trailing_stop)
- `timeframe: str` - Candle size (1min, 5min, 15min, 1hour, 1day)
- `parameters: Dict[str, Any]` - Function-specific parameters
- `last_evaluated: Optional[datetime]` - Last evaluation timestamp

**Supported Functions:**
- `close_above`: Execute when price closes above threshold
- `close_below`: Execute when price closes below threshold  
- `trailing_stop`: Dynamic stop loss that trails price

**Supported Timeframes:**
- 1min, 5min, 15min, 1hour, 1day

**Relationships:**
- Embedded in TradePlan for entry/exit logic
- Evaluated by ExecutionEngine (future implementation)

## ✅ TradePlanStatus (Implemented - Story 1.2)
**Status:** Complete enum implementation  
**Purpose:** Lifecycle states for trade plan execution

**Values:**
- `awaiting_entry`: Plan loaded, waiting for entry conditions
- `position_open`: Position active, monitoring exit conditions
- `completed`: Position closed successfully
- `cancelled`: Plan cancelled before execution
- `error`: Error occurred during execution

## ✅ ValidationResult (Implemented - Story 1.2)
**Status:** Complete validation framework  
**Purpose:** Structured validation results with error aggregation

**Key Attributes:**
- `is_valid: bool` - Overall validation status
- `errors: List[ValidationError]` - List of validation errors
- `warnings: List[str]` - Non-blocking warnings
- `file_path: Optional[Path]` - Source file for context

**Methods:**
- `add_error(error: ValidationError)` - Add validation error
- `add_warning(warning: str)` - Add warning message
- `merge(other: ValidationResult)` - Combine validation results

## ✅ ValidationError (Implemented - Story 1.2) 
**Status:** Complete with line number tracking  
**Purpose:** Detailed error information with actionable messages

**Key Attributes:**
- `message: str` - Human-readable error description
- `field: Optional[str]` - Field that failed validation
- `value: Any` - Invalid value that caused error
- `line_number: Optional[int]` - YAML line number
- `suggestion: Optional[str]` - Suggested fix
- `error_code: Optional[str]` - Categorized error code

---

## ⏸️ Future Models (Awaiting Implementation)

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
