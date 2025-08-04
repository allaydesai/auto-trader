# Epic 4: Notifications & Persistence

Add Discord notifications, trade history logging, and state persistence for multi-day positions. This epic completes the system with observability and continuity features.

## Story 4.1: Discord Notifications

As a trader,
I want immediate Discord notifications for all trade events,
so that I can monitor my system remotely.

### Acceptance Criteria
1: Webhook URL configured via environment variable
2: Entry notifications include: symbol, side, price, position size, timestamp
3: Exit notifications include: symbol, side, price, P&L, exit reason
4: Error notifications include: error type, symbol, attempted action, timestamp
5: Notifications formatted with markdown for readability
6: Failed webhook posts logged but don't crash the system

## Story 4.2: Trade History Logging

As a trader,
I want a permanent record of all trades,
so that I can analyze my performance.

### Acceptance Criteria
1: CSV file appends one row per trade with all relevant fields
2: Fields include: timestamp, symbol, side, entry_price, exit_price, size, P&L, fees
3: Execution metadata logged: function used, timeframe, trigger level
4: Separate files for each month (trades_2024_01.csv format)
5: Trade summary calculated on each trade: win rate, average win/loss
6: History queryable by date range or symbol

## Story 4.3: State Persistence and Recovery

As a trader,
I want my positions to survive system restarts,
so that I can maintain trades across multiple days.

### Acceptance Criteria
1: Position state saved to JSON file on each state change
2: State includes: symbol, entry_price, size, stop/target orders, entry_time
3: On startup, state file loaded and positions reconciled with IBKR
4: Orphaned orders detected and cancelled if position no longer exists
5: State file backup created before each update (keeping last 5 versions)
6: Recovery process logged clearly showing what was restored
