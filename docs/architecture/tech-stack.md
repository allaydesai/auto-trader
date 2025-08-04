# Tech Stack

This is the DEFINITIVE technology selection for the project. All components MUST use these exact versions and libraries.

## Cloud Infrastructure
- **Provider:** N/A - Local deployment only for MVP
- **Key Services:** Local file system for persistence
- **Deployment Regions:** User's local machine (Windows/Linux)

## Technology Stack Table

| Category | Technology | Version | Purpose | Rationale |
|----------|------------|---------|---------|-----------|
| **Language** | Python | 3.11.8 | Primary development language | Modern features, excellent async support, financial ecosystem |
| **Package Manager** | UV | 0.5.0+ | Fast dependency management | Blazing fast, replaces pip/poetry/virtualenv |
| **Async Runtime** | asyncio | stdlib | Concurrent I/O operations | Built-in, mature, perfect for event-driven systems |
| **IBKR Integration** | ib-async | 1.0.0+ | Interactive Brokers API | Modern async wrapper, cleaner than ib_insync |
| **Market Data** | fmp-sdk | 1.0.0+ | Financial Modeling Prep API | Official SDK, well-maintained |
| **Data Processing** | pandas | 2.2.0 | Time series manipulation | Industry standard for financial data |
| **Data Validation** | pydantic | 2.9.0 | Settings and model validation | Type safety, automatic validation |
| **Numerical** | numpy | 1.26.0 | Numerical computations | Required by pandas, efficient arrays |
| **Scheduling** | APScheduler | 3.10.4 | Time-based event scheduling | Reliable, supports async, perfect for candle events |
| **HTTP Client** | httpx | 0.27.0 | Discord webhooks | Modern async HTTP, replaces requests |
| **Logging** | loguru | 0.7.2 | Structured logging | Superior to stdlib logging, rotation built-in |
| **Configuration** | pydantic-settings | 2.4.0 | Environment config | Type-safe settings with .env support |
| **Testing** | pytest | 8.3.0 | Test framework | De facto Python standard |
| **Testing - Async** | pytest-asyncio | 0.24.0 | Async test support | Required for async code testing |
| **Linting** | ruff | 0.7.0 | Fast Python linter | Replaces flake8/isort/black, blazing fast |
| **Type Checking** | mypy | 1.11.0 | Static type checking | Catches errors before runtime |
| **Time Zones** | pytz | 2024.1 | Timezone handling | Market hours calculations |
| **CLI Enhancement** | rich | 13.7.0 | Enhanced terminal output | Improved CLI wizard experience |
| **CLI Framework** | click | 8.1.7 | Command-line interface | CLI wizard and commands |
