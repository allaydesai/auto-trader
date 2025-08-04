# Requirements

## Functional (MVP - 4 Week Scope)
- FR1: The system shall load trade plans from YAML files containing entry/exit levels, stop-loss levels, and execution function selection with timeframe metadata
- FR2: The system shall provide dual trade plan creation methods: manual YAML editing with validation and interactive CLI wizard
- FR3: The system shall connect to Interactive Brokers API for both market data and trade execution
- FR4: The system shall implement three pre-built execution functions: close above level, close below level, and trailing stop (all with configurable timeframes)
- FR5: The system shall calculate position sizes automatically using risk percentage (1%, 2%, 3%) and block trades exceeding 10% total portfolio risk
- FR6: The system shall send Discord notifications for each trade event (entry, exit, stop-loss)
- FR7: The system shall support a simulation mode toggle that processes all logic without placing broker orders
- FR8: The system shall append all executed trades to a history file with timestamp, symbol, action, price, and P&L
- FR9: The system shall persist and recover position state across restarts to support multi-day swing trades

## Future Functional Requirements (Post-MVP)
- Future FR1: Add Financial Modeling Prep as secondary data source with failover logic
- Future FR2: Implement custom execution function builder with TA-lib integration
- Future FR3: Create web-based monitoring UI for trade plan status
- Future FR4: Add daily trade summary generation and Discord posting
- Future FR5: Scale to support 100+ simultaneous trade plans
- Future FR6: Implement advanced risk management features (correlation, portfolio heat)

## Non Functional (MVP)
- NFR1: Trade execution latency shall not exceed 1 second from signal generation to order submission
- NFR2: The system shall run on both Windows and Linux desktop environments
- NFR3: The system shall handle IBKR connection drops with automatic reconnection attempts
- NFR4: API credentials shall be stored in environment variables or encrypted config file
- NFR5: The system shall operate within Interactive Brokers API rate limits
- NFR6: Critical execution paths (risk checks, order placement) shall have unit test coverage

## Future Non-Functional Requirements (Post-MVP)
- Future NFR1: Achieve 95% uptime during market hours
- Future NFR2: Scale to process tick data for 100+ symbols without lag
- Future NFR3: Implement comprehensive test coverage across all modules
- Future NFR4: Add performance monitoring and alerting
