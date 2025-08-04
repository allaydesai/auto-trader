# Epic 3: Trade Execution Engine

Implement execution functions, time-based triggers, and complete trade lifecycle from entry to exit. This epic contains the core value proposition of the system.

## Story 3.1: Execution Function Framework

As a trader,
I want a framework for execution functions that trigger on candle closes,
so that I can avoid stop-hunting algorithms.

### Acceptance Criteria
1: Function registry maps function names to implementations
2: Functions receive: current bar data, trade plan parameters, position state
3: Functions return: action (none, enter, exit) with confidence score
4: Bar close detection accurate within 1 second of actual close time
5: Multiple timeframes monitored simultaneously for same symbol
6: Execution decisions logged with reasoning for audit trail

## Story 3.2: Core Execution Functions

As a trader,
I want three proven execution functions available,
so that I can implement my most common trading strategies.

### Acceptance Criteria
1: "close_above" function triggers when price closes above specified level
2: "close_below" function triggers when price closes below specified level  
3: "trailing_stop" function maintains stop distance from highest/lowest close
4: All functions respect timeframe parameter (only evaluate on specified bar size)
5: Functions handle edge cases (gaps, limit up/down, missing data)
6: Unit tests verify function behavior across market scenarios

## Story 3.3: Trade Lifecycle Management

As a trader,
I want automatic management of my trades from entry to exit,
so that I can rely on systematic execution.

### Acceptance Criteria
1: Entry function monitored while position is flat
2: Upon entry trigger, position size calculated using risk management module
3: Risk checks performed before order submission (portfolio limit validation)
4: After successful risk validation and fill, stop-loss and take-profit orders placed immediately
5: Position added to risk registry with calculated risk amount upon fill
6: Exit functions (stop/target) monitored while position is open
7: Position state tracked: awaiting_entry, position_open, position_closed
8: Exit fills cancel any remaining orders for that symbol and remove position from risk registry

## Story 3.4: Simulation Mode

As a trader,
I want to test my system without risking real money,
so that I can validate behavior before live trading.

### Acceptance Criteria
1: Simulation mode flag in config.yaml disables all IBKR order submissions
2: Simulated fills use current market price with configurable slippage
3: Simulated positions tracked identically to real positions
4: All Discord notifications sent with "[SIMULATION]" prefix
5: Trade history includes simulation flag for easy filtering
6: Simulated P&L calculated using market prices
