# Error Handling Strategy

## General Approach
- **Error Model:** Fail fast with specific exceptions, recover where possible
- **Exception Hierarchy:** Custom exceptions inherit from AutoTraderError base
- **Error Propagation:** Bubble to main loop, log, notify, continue operation

## Logging Standards
- **Library:** loguru 0.7.2
- **Format:** JSON structured logs with timestamp, level, module, message, context
- **Levels:** DEBUG (dev only), INFO (normal), WARNING (issues), ERROR (failures)
- **Required Context:**
  - Correlation ID: UUID per trade plan evaluation
  - Service Context: module.function name
  - Trade Context: plan_id, symbol, action
  - Risk Context: portfolio_risk_percent, position_risk_amount
  - User Context: Not applicable (single user system)

**Enhanced Logging Categories:**
- **Risk Management Logs:** All position sizing calculations, portfolio risk updates, limit violations
- **CLI Wizard Logs:** User interaction flows, validation errors, plan creation steps
- **Cross-Interface Logs:** State changes propagated across Discord/Terminal/Config
- **Performance Logs:** Execution latency, WebSocket reconnection timing

**Progressive Verbosity Levels:**
- **Standard:** Essential trade events, errors, risk violations
- **Detailed (--verbose):** Risk calculations, validation steps, state changes
- **Debug (--debug):** All function calls, WebSocket events, configuration loads

**Log Rotation and Retention:**
- Daily rotation with 30-day retention
- Separate log files by category: trades.log, risk.log, system.log, cli.log
- Structured format for easy parsing and analysis

## Error Handling Patterns

### External API Errors
- **Retry Policy:** Exponential backoff, max 5 attempts
- **Circuit Breaker:** After 5 failures, wait 5 minutes before retry
- **Timeout Configuration:** 30s for HTTP, 60s for IBKR connection
- **Error Translation:** Map IBKR errors to internal exception types

### Business Logic Errors  
- **Custom Exceptions:** InsufficientFundsError, InvalidTradePlanError, RiskLimitExceeded
- **User-Facing Errors:** Sent to Discord with actionable message
- **Error Codes:** Simple string codes (RISK_001, EXEC_002)

### Data Consistency
- **Transaction Strategy:** Write-through cache with file persistence
- **Compensation Logic:** Rollback in-memory state on write failure
- **Idempotency:** Order IDs prevent duplicate submissions
