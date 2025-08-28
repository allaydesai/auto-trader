# Execution Function Framework Architecture

## Overview

The Execution Function Framework is a critical component of the Auto-Trader system that bridges market data, trade plans, and order execution. It implements a plugin-based, event-driven architecture designed to trigger trading decisions on precise candle closes, avoiding stop-hunting algorithms employed by institutional traders.

## Core Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   Market Data System (Story 2.2)            │
│                     (BarData, MarketDataCache)              │
└────────────────────┬────────────────────────────────────────┘
                     │ Bar Close Events
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              Bar Close Detection System                      │
│         (Multi-timeframe, <1sec accuracy)                   │
└────────────────────┬────────────────────────────────────────┘
                     │ BarCloseEvent
                     ▼
┌─────────────────────────────────────────────────────────────┐
│           Execution Function Framework                       │
│  ┌──────────────────────────────────────────────────────┐  │
│  │         Function Registry & Plugin System             │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │      ExecutionContext (Bar Data + Plan + State)      │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │    ExecutionSignal (Action + Confidence + Reason)    │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────────┘
                     │ Execution Decisions
                     ▼
┌─────────────────────────────────────────────────────────────┐
│          Order Execution System (Story 2.3)                 │
│              (Risk Validation + Order Placement)            │
└─────────────────────────────────────────────────────────────┘
```

## Design Principles

### 1. Plugin Architecture
- Functions are self-contained plugins registered at runtime
- Easy to add new execution functions without modifying core framework
- Each function encapsulates its own logic and parameters

### 2. Event-Driven Processing
- React to bar close events rather than polling
- Asynchronous processing for scalability
- Decoupled components communicating via events

### 3. Immutable Context
- Pass immutable context objects to functions
- Prevents side effects and ensures thread safety
- Clear data flow through the system

### 4. Comprehensive Audit Trail
- Every execution decision logged with full reasoning
- Performance metrics captured for analysis
- Structured logging for easy querying

### 5. Testability First
- Easy to mock and test components in isolation
- Dependency injection for external systems
- Comprehensive test coverage requirements

### 6. Performance Optimized
- Microsecond-level timing accuracy for bar closes
- Efficient memory usage with bounded caches
- Concurrent execution for multiple symbols/timeframes

## Core Components

### ExecutionFunctionBase
Abstract base class defining the interface for all execution functions:
```python
class ExecutionFunctionBase(ABC):
    """Base class for all execution functions"""
    
    @abstractmethod
    async def evaluate(self, context: ExecutionContext) -> ExecutionSignal:
        """Evaluate conditions and return execution signal"""
        pass
    
    @abstractmethod
    def validate_parameters(self, params: Dict[str, Any]) -> bool:
        """Validate function-specific parameters"""
        pass
    
    @property
    @abstractmethod
    def required_lookback(self) -> int:
        """Number of historical bars required"""
        pass
```

### ExecutionFunctionRegistry
Plugin registry system for dynamic function registration:
```python
class ExecutionFunctionRegistry:
    """Registry for execution function plugins"""
    
    def register(self, name: str, function_class: Type[ExecutionFunctionBase]):
        """Register a new execution function"""
        
    def get_function(self, name: str, params: Dict) -> ExecutionFunctionBase:
        """Instantiate and return configured function"""
        
    def list_functions(self) -> List[str]:
        """List all registered function names"""
```

### BarCloseDetector
High-precision bar close detection system:
```python
class BarCloseDetector:
    """Detect bar closes with <1 second accuracy"""
    
    def __init__(self):
        self.scheduler = APScheduler()  # For precise timing
        self.timeframe_monitors = {}    # Per-timeframe monitoring
        
    async def monitor_timeframe(self, symbol: str, timeframe: str):
        """Monitor specific timeframe for bar closes"""
        
    async def on_bar_close(self, callback: Callable):
        """Register callback for bar close events"""
```

### ExecutionContext
Immutable context object containing all data needed for execution decisions:
```python
@dataclass(frozen=True)
class ExecutionContext:
    """Immutable context for execution function evaluation"""
    
    symbol: str
    timeframe: str
    current_bar: BarData
    historical_bars: List[BarData]
    trade_plan_params: Dict[str, Any]
    position_state: Optional[PositionState]
    account_info: AccountInfo
    timestamp: datetime
```

### ExecutionSignal
Result of execution function evaluation:
```python
@dataclass(frozen=True)
class ExecutionSignal:
    """Signal returned by execution functions"""
    
    action: ExecutionAction  # NONE, ENTER_LONG, ENTER_SHORT, EXIT
    confidence: float        # 0.0 to 1.0
    reasoning: str          # Human-readable explanation
    metadata: Dict[str, Any]  # Function-specific data
```

### ExecutionLogger
Structured logging system for audit trail:
```python
class ExecutionLogger:
    """Structured logging for all execution decisions"""
    
    def log_evaluation(self, 
                      function: str,
                      context: ExecutionContext,
                      signal: ExecutionSignal,
                      duration_ms: float):
        """Log execution evaluation with full context"""
        
    def log_error(self, function: str, error: Exception):
        """Log execution errors"""
        
    def query_logs(self, filters: Dict) -> List[ExecutionLogEntry]:
        """Query historical execution logs"""
```

## Data Models

### Core Models
- **ExecutionSignal**: Function return value with action and confidence
- **ExecutionContext**: Container for all execution decision inputs
- **BarCloseEvent**: Event emitted when a bar closes
- **ExecutionLogEntry**: Structured log entry for audit trail
- **ExecutionAction**: Enum for possible actions (NONE, ENTER_LONG, ENTER_SHORT, EXIT)
- **ConfidenceLevel**: Enum for confidence levels (LOW, MEDIUM, HIGH)

### Integration Models
- **BarData** (from Story 2.2): OHLCV data with timestamp
- **MarketData** (from Story 2.2): Real-time price updates
- **TradePlan** (from Epic 1): Trade plan configuration
- **PositionState**: Current position information
- **OrderRequest** (from Story 2.3): Order placement request

## Built-in Execution Functions

### CloseAboveFunction
Triggers when price closes above a threshold:
- Parameters: threshold_price, min_volume (optional)
- Timeframes: All supported
- Confidence: Based on volume and price momentum

### CloseBelowFunction  
Triggers when price closes below a threshold:
- Parameters: threshold_price, min_volume (optional)
- Timeframes: All supported
- Confidence: Based on volume and price momentum

### TrailingStopFunction
Dynamic stop-loss that trails price movement:
- Parameters: trail_percentage, activation_price
- Timeframes: Typically shorter (1min, 5min)
- Confidence: Always HIGH when triggered

## Event Flow

### 1. Market Data Reception
```
MarketDataSystem → BarData → MarketDataCache
```

### 2. Bar Close Detection
```
MarketDataCache → BarCloseDetector → BarCloseEvent
```

### 3. Execution Evaluation
```
BarCloseEvent → ExecutionContext → ExecutionFunction → ExecutionSignal
```

### 4. Order Placement Decision
```
ExecutionSignal → RiskValidation → OrderRequest → IBKRClient
```

### 5. Logging & Audit
```
All stages → ExecutionLogger → Structured Logs → Persistence
```

## Performance Requirements

### Timing Accuracy
- Bar close detection: <1 second of actual close time
- Execution evaluation: <100ms per function
- Total signal generation: <500ms from bar close to signal

### Scalability
- Support 100+ simultaneous symbol monitoring
- Handle 5+ timeframes per symbol
- Process 1000+ executions per minute

### Memory Efficiency
- Bounded historical data cache (max 1000 bars per symbol)
- Automatic cleanup of stale data
- Efficient function instance pooling

## Error Handling Strategy

### Function-Level Errors
- Graceful degradation on function failure
- Fallback to safe state (no action)
- Detailed error logging with context

### System-Level Errors
- Circuit breaker for market data failures
- Automatic recovery with exponential backoff
- State persistence for crash recovery

### Data Quality Issues
- Validation of all incoming market data
- Rejection of stale or invalid bars
- Quality metrics in execution logs

## Testing Strategy

### Unit Tests (70%)
- Individual function logic validation
- Registry system operations
- Bar close timing accuracy
- Context and signal model validation

### Integration Tests (20%)
- Market data flow end-to-end
- Multi-timeframe scenarios
- Order execution flow
- Error recovery scenarios

### Performance Tests (10%)
- Timing accuracy validation
- Concurrent execution stress tests
- Memory usage profiling
- Latency measurements

## Security Considerations

### Parameter Validation
- Strict validation of all function parameters
- Type checking and range validation
- Injection attack prevention

### Access Control
- Function registration requires authentication
- Audit trail of all modifications
- Read-only execution context

### Data Integrity
- Immutable data structures
- Cryptographic hashing of critical decisions
- Tamper-evident audit logs

## Future Enhancements

### Machine Learning Integration
- Confidence score optimization
- Pattern recognition functions
- Adaptive parameter tuning

### Advanced Functions
- Multi-indicator combinations
- Market regime detection
- Correlation-based execution

### Performance Optimizations
- GPU acceleration for complex calculations
- Distributed execution for scale
- Real-time strategy backtesting

## Configuration

### Function Registry Configuration
```yaml
execution_functions:
  close_above:
    class: CloseAboveFunction
    enabled: true
    max_instances: 10
  close_below:
    class: CloseBelowFunction
    enabled: true
    max_instances: 10
  trailing_stop:
    class: TrailingStopFunction
    enabled: true
    max_instances: 5
```

### Timing Configuration
```yaml
bar_close_detection:
  accuracy_ms: 500  # Max deviation from actual close
  schedule_advance_ms: 100  # Schedule ahead of expected close
  timezone: "America/New_York"
  market_hours_only: true
```

### Logging Configuration
```yaml
execution_logging:
  level: INFO
  structured: true
  retention_days: 30
  performance_metrics: true
  include_context: true
```

## Dependencies

### Required Systems
- Market Data System (Story 2.2)
- Order Execution System (Story 2.3)
- Risk Management System (Epic 1)
- State Persistence System

### External Libraries
- APScheduler 3.10.4: Precise scheduling
- pydantic 2.9.0: Data validation
- loguru 0.7.2: Structured logging
- asyncio: Async processing

## Implementation Checklist

- [ ] Core models and data structures
- [ ] ExecutionFunctionBase abstract class
- [ ] ExecutionFunctionRegistry implementation
- [ ] Built-in execution functions (3)
- [ ] BarCloseDetector with timing accuracy
- [ ] ExecutionLogger with audit trail
- [ ] Market data integration adapter
- [ ] Order system integration adapter
- [ ] Comprehensive unit tests
- [ ] Integration test suite
- [ ] Performance validation tests
- [ ] Documentation and examples

## References

- Story 3.1: Execution Function Framework requirements
- Story 2.2: Market Data Subscription system
- Story 2.3: Order Execution Interface
- Architecture Document: System design principles
- Coding Standards: Implementation guidelines