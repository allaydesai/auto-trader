# Project Brief: Auto-Trader

## Executive Summary

Auto-Trader is a personal automated trade execution system designed to implement discretionary trading strategies with dynamic entry/exit logic. The system addresses the challenges retail traders face from institutional algorithmic trading by using customizable time-based execution functions rather than simple price-level triggers. Built for a single user (the developer/trader), it integrates with Interactive Brokers for trade execution and Financial Modeling Prep for market data, providing automated trade management with comprehensive Discord notifications and trade history tracking.

## Problem Statement

### Current State and Pain Points
As a retail trader operating in markets dominated by institutional algorithms, I face several critical challenges:
- **Algorithmic Stop Hunting**: Large institutions use algorithms to trigger stop-loss and take-profit orders placed at obvious price levels, causing premature exits and suboptimal entries
- **Execution Inconsistency**: Manual discretionary trading suffers from:
  - Emotional decision-making affecting execution quality
  - Inability to monitor multiple timeframes simultaneously
  - Missed opportunities due to human limitations in 24/7 market monitoring
  - Inconsistent fill prices due to manual order placement delays

### Impact of the Problem
- **Financial Impact**: Poor execution timing and stop hunting result in reduced profitability and increased losses
- **Time Impact**: Constant market monitoring required for multi-timeframe analysis is unsustainable
- **Quality Impact**: Human factors introduce variability in trade execution that undermines strategy performance

### Why Existing Solutions Fall Short
- Most retail trading platforms only offer simple price-level triggers that are easily exploited by institutional algorithms
- Existing automation tools lack the flexibility to implement custom, time-based execution logic
- Commercial solutions don't provide the transparency and control needed for personal trading strategies

### Urgency
In today's algorithm-dominated markets, retail traders need sophisticated execution tools to remain competitive. Manual execution is no longer viable for implementing complex, multi-timeframe strategies consistently.

## Proposed Solution

### Core Concept
A modular, personal auto-trading system that executes trades based on user-defined functions incorporating time-based criteria (candle closes) across multiple timeframes. The system monitors positions continuously, manages entries/exits/stops dynamically, and provides real-time notifications while maintaining complete trade history.

### Key Differentiators
- **Dynamic Function-Based Execution**: Unlike simple price triggers, uses customizable functions that can incorporate multiple indicators and timeframes
- **Time-Based Filtering**: Executes based on candle closes at user-specified timeframes (1 minute to 1 week) to filter market noise
- **Modular Architecture**: Extensible system allowing custom execution functions and indicator integration
- **Simulation Mode**: Can run without broker connection for testing and alert-only operation
- **Comprehensive Observability**: Real-time UI monitoring and Discord notifications for complete trade lifecycle visibility

### Why This Solution Will Succeed
- **Tailored for Personal Use**: Eliminates unnecessary complexity of multi-user systems
- **Anti-Algorithm Design**: Time-based execution functions are harder for algorithms to exploit than simple price levels
- **Full Control**: Complete transparency and control over execution logic
- **Proven Components**: Leverages established APIs (IBKR, FMP) and libraries (TA-lib)

## Target Users

### Primary User Segment: Retail Discretionary Trader (Self)
- **Profile**: Experienced retail trader with programming skills transitioning from manual to automated execution
- **Current Workflow**: 
  - Manual trade planning with predetermined entry/exit levels
  - Discretionary execution based on price action and multiple timeframe analysis
  - Manual position monitoring and order management
- **Specific Needs**:
  - Consistent execution of predefined trade plans
  - Protection from algorithmic stop hunting
  - Multi-timeframe analysis capability
  - Trade execution quality and repeatability
  - Historical trade tracking for strategy refinement
- **Goals**:
  - Automate discretionary strategy execution
  - Improve trade timing and fill prices
  - Maintain trading discipline through systematic execution
  - Free up time from constant market monitoring

## Goals & Success Metrics

### Business Objectives
- Launch functional auto-trading system within 4 weeks
- Successfully execute 100% of planned trades according to defined functions
- Achieve 95%+ uptime during market hours after deployment
- Reduce manual intervention in trade execution by 90%

### User Success Metrics
- Trade execution occurs within 1 second of signal generation
- All trades executed according to predefined plan without emotional interference
- Complete trade history maintained with 100% accuracy
- Real-time notification delivery to Discord within 5 seconds of trade events

### Key Performance Indicators (KPIs)
- **System Reliability**: Uptime percentage during market hours (target: >95%)
- **Execution Accuracy**: Percentage of trades executed correctly per trade plan (target: 100%)
- **Notification Latency**: Time from trade event to Discord notification (target: <5 seconds)
- **Fill Quality**: Slippage from signal price to execution price (target: minimize within market conditions)

## MVP Scope

### Core Features (Must Have)
- **Trade Plan Management:** Load and persist trade plans from editable storage with entry/exit levels and execution functions
- **Multi-Timeframe Execution Engine:** Support candle-based execution from 1 minute to 1 week timeframes
- **Function Library:** Pre-built execution functions including close above/below levels and trailing stops
- **IBKR Integration:** Full trading API integration for order placement and position management
- **FMP Data Integration:** Real-time and historical data feed for all required timeframes
- **Position Monitoring UI:** Simple interface showing active trade plans and their current status
- **Discord Notifications:** Real-time alerts for trade execution and daily summaries
- **Trade History:** Persistent storage of all trade plans and execution history
- **Simulation Mode:** Ability to run without broker connection for testing/alerts only

### Out of Scope for MVP
- Options trading support
- Cryptocurrency trading
- Multi-user functionality
- Advanced UI features beyond basic monitoring
- Mobile application
- Cloud deployment (local only)
- Backtesting engine
- Strategy optimization tools

### MVP Success Criteria
The MVP is successful when it can reliably execute a complete trade lifecycle: loading a trade plan, monitoring for entry conditions across multiple timeframes, executing the entry, managing the position with stop-loss and take-profit functions, and recording the complete trade history with Discord notifications at each step.

## Post-MVP Vision

### Phase 2 Features
- **Advanced Execution Functions:** More complex entry/exit logic incorporating multiple indicators
- **Enhanced Risk Management:** Portfolio-level risk controls and position correlation analysis
- **Performance Analytics:** Detailed trade statistics and strategy performance metrics
- **Strategy Templates:** Reusable trade plan templates for common setups
- **Market Regime Detection:** Adaptive execution based on market conditions

### Long-term Vision
Within 1-2 years, evolve the system into a comprehensive personal trading platform that handles all aspects of systematic trading, including strategy development, backtesting, optimization, and execution. Potentially extend to options trading and additional asset classes while maintaining the single-user focus.

### Expansion Opportunities
- **Cloud Deployment:** Move from local to cloud infrastructure for 24/7 reliability
- **Machine Learning Integration:** Incorporate ML for execution timing optimization
- **Additional Brokers:** Support for multiple broker APIs beyond IBKR
- **Alternative Data Sources:** Integration with premium data providers
- **Advanced Analytics:** Real-time strategy performance dashboard

## Technical Considerations

### Platform Requirements
- **Target Platforms:** Windows and Linux desktop environments
- **Browser/OS Support:** Modern web browser for UI (Chrome, Firefox, Edge)
- **Performance Requirements:** 
  - Sub-second execution latency
  - Handle 100+ simultaneous position monitors
  - Process tick data for multiple symbols without lag

### Technology Preferences
- **Frontend:** React or Vue.js for monitoring UI
- **Backend:** Python (for TA-lib compatibility and financial library ecosystem) or Node.js
- **Database:** PostgreSQL for trade history, Redis for real-time state
- **Hosting/Infrastructure:** Local deployment on dedicated machine

### Architecture Considerations
- **Repository Structure:** Monorepo with clear separation of concerns (engine, UI, integrations)
- **Service Architecture:** Modular design with separate services for data feed, execution engine, and UI
- **Integration Requirements:** 
  - IBKR TWS API or IB Gateway
  - FMP REST and WebSocket APIs
  - Discord webhook API
- **Security/Compliance:** 
  - Encrypted storage for API credentials
  - Secure local network deployment
  - Audit trail for all trade decisions

## Constraints & Assumptions

### Constraints
- **Budget:** Personal project with minimal external costs beyond API subscriptions
- **Timeline:** 4-week development window for MVP
- **Resources:** Single developer/user
- **Technical:** Must work within IBKR API rate limits and connection requirements

### Key Assumptions
- IBKR and FMP APIs will remain stable and accessible
- Local deployment environment will have reliable internet connectivity
- Market data quality from FMP is sufficient for execution decisions
- Single-user design eliminates need for complex permissions/auth systems
- WebSocket connections can be maintained reliably for real-time data

## Risks & Open Questions

### Key Risks
- **API Reliability:** Broker or data provider API outages could prevent trade execution
- **WebSocket Stability:** Connection drops could miss critical market events
- **Execution Timing:** Network latency might impact time-sensitive executions
- **Data Quality:** FMP data accuracy/timeliness compared to direct exchange feeds

### Open Questions
- What is the optimal architecture for managing WebSocket connections reliably?
- How to handle partial fills and order modifications in execution logic?
- What's the best approach for persisting state between system restarts?
- How to implement efficient multi-timeframe candle aggregation?

### Areas Needing Further Research
- IBKR API connection management best practices
- WebSocket reconnection strategies and error handling
- Optimal database schema for time-series trade data
- Performance implications of real-time indicator calculations

## Appendices

### A. Research Summary
Further research needed on:
- IBKR TWS API documentation and example implementations
- FMP WebSocket API capabilities and limitations
- TA-lib Python wrapper performance characteristics
- Discord webhook rate limits and best practices

### C. References
- [IBKR API Documentation](https://interactivebrokers.github.io/)
- [Financial Modeling Prep API](https://financialmodelingprep.com/developer/docs)
- [TA-Lib Documentation](https://mrjbq7.github.io/ta-lib/)
- Discord Webhook Documentation

## Next Steps

### Immediate Actions
1. Set up development environment with Python/Node.js and required dependencies
2. Obtain and configure IBKR paper trading account for testing
3. Register for FMP API access and test data endpoints
4. Create detailed technical architecture document
5. Set up project repository with initial structure
6. Design database schema for trade plans and history
7. Prototype WebSocket connection management
8. Define JSON/YAML format for trade plan configuration

### PM Handoff
This Project Brief provides the full context for Auto-Trader. Please start in 'PRD Generation Mode', review the brief thoroughly to work with the user to create the PRD section by section as the template indicates, asking for any necessary clarification or suggesting improvements.