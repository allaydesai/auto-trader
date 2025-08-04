# Epic 2: IBKR Integration & Market Data

Connect to Interactive Brokers for real-time data consumption and order execution with connection management. This epic establishes the critical broker connection that enables all trading functionality.

## Story 2.1: IBKR Connection Management

As a trader,
I want reliable connection to Interactive Brokers,
so that I can receive market data and execute trades without interruption.

### Acceptance Criteria
1: Connect to IBKR using ib_insync library with configurable host/port
2: Automatic reconnection on disconnect with exponential backoff (max 5 attempts)
3: Connection status logged and available for health checks
4: Graceful shutdown handling to close positions if configured
5: Paper trading vs live account detected and logged prominently
6: Connection errors result in Discord notification

## Story 2.2: Market Data Subscription

As a trader,
I want to receive real-time price data for my trading symbols,
so that my execution functions can trigger on accurate market conditions.

### Acceptance Criteria
1: Subscribe to real-time bars for all symbols in active trade plans
2: Support bar sizes: 1min, 5min, 15min, 30min, 1hour, 4hour, 1day
3: Historical data fetched on startup to establish current position relative to levels
4: Market data cached in memory with timestamp for each bar
5: Data quality checks ensure no stale data used for execution (>2x bar size)
6: Subscription management handles adding/removing symbols dynamically

## Story 2.3: Order Execution Interface

As a trader,
I want to place and manage orders through IBKR,
so that my trades execute in the market.

### Acceptance Criteria
1: Calculate position size using risk management module before placing orders
2: Place market orders for trade plan entries with calculated position size
3: Place stop-loss orders immediately after entry fill confirmation
4: Place take-profit orders immediately after entry fill confirmation
5: Modify existing orders (for trailing stops) without creating duplicates
6: Order status tracked and logged (submitted, filled, cancelled, rejected)
7: Failed orders trigger Discord notification with error details
8: Risk limit violations prevent order placement and trigger error notifications
