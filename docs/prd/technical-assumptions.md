# Technical Assumptions

## Repository Structure: Monorepo
A single repository containing all components (execution engine, IBKR integration, Discord client) to simplify development and deployment for a single-user system.

## Service Architecture
**Monolithic application with modular components:**
- Single Python process managing all functionality
- Clear module separation: trade_engine, ibkr_client, discord_notifier, risk_manager
- Shared in-memory state for low-latency execution
- File-based persistence for simplicity (YAML configs, JSON state, CSV trade history)

## Testing Requirements
**Focused testing on critical paths only:**
- Unit tests for risk management calculations
- Unit tests for execution function logic
- Integration tests for IBKR order placement (using paper trading account)
- Manual testing checklist for end-to-end flows

## Additional Technical Assumptions and Requests
- **Language:** Python 3.10+ (for IBKR API compatibility and financial ecosystem)
- **IBKR Integration:** Using ib_async library for cleaner async API handling
- **Data Storage:** Local files only - YAML for configs, JSON for state, CSV for trade history
- **Discord Integration:** Discord.py or simple webhook POST requests
- **Scheduling:** Python's asyncio for event loops and APScheduler for time-based events
- **Configuration:** Environment variables for secrets, YAML files for trade plans
- **Deployment:** Simple Python virtual environment with requirements.txt
- **Process Management:** systemd service (Linux) or Task Scheduler (Windows)
- **Logging:** Python's built-in logging to rotating file handlers
- **Time Handling:** All timestamps in UTC to avoid timezone issues
- **Market Hours:** Hardcoded US equity market hours initially
