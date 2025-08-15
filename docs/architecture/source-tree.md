# Source Tree

## Implementation Status
- ✅ **Implemented** (Stories 1.1, 1.2): Core models, validation, CLI, templates
- ⏸️ **Planned**: Trade engine, IBKR integration, risk management, notifications
- 🧪 **Testing**: 134 tests currently passing (88% coverage)

```plaintext
auto-trader/
├── src/
│   ├── __init__.py
│   ├── main.py                    # Entry point, max 100 lines
│   ├── config.py                  # ✅ Settings with pydantic validation
│   └── auto_trader/
│       ├── __init__.py
│       ├── logging_config.py      # ✅ Loguru configuration
│       ├── models/               # ✅ Pydantic models & validation
│       │   ├── __init__.py        # ✅ Model exports
│       │   ├── trade_plan.py      # ✅ TradePlan & ExecutionFunction
│       │   ├── validation_engine.py # ✅ YAML validation engine
│       │   ├── error_reporting.py # ✅ Enhanced error reporting
│       │   ├── template_manager.py # ✅ Template system
│       │   ├── plan_loader.py     # ✅ Plan loading & management
│       │   ├── position.py        # ⏸️ Position model (future)
│       │   ├── risk_models.py     # ⏸️ Risk management models
│       │   ├── market_data.py     # ⏸️ Market data models
│       │   └── tests/            # ✅ Comprehensive test suite
│       │       ├── conftest.py    # ✅ Test fixtures
│       │       ├── test_trade_plan.py    # ✅ 21 tests
│       │       ├── test_validation_engine.py # ✅ 21 tests
│       │       ├── test_error_reporting.py   # ✅ 47 tests
│       │       ├── test_template_manager.py  # ✅ 19 tests
│       │       ├── test_plan_loader.py       # ✅ 19 tests
│       │       └── test_config.py            # ✅ 22 tests
│       ├── cli/                 # ✅ Rich CLI interface (refactored)
│       │   ├── __init__.py
│       │   ├── commands.py      # ✅ Main CLI commands (549 lines)
│       │   ├── display_utils.py # ✅ Display & formatting utilities
│       │   ├── file_utils.py    # ✅ File creation utilities
│       │   ├── error_utils.py   # ✅ Error handling utilities
│       │   ├── plan_utils.py    # ✅ Plan creation utilities
│       │   └── tests/          # ✅ CLI tests
│       │       └── test_commands.py
│       ├── trade_engine/         # Core execution logic
│       │   ├── __init__.py
│       │   ├── engine.py
│       │   ├── execution_functions.py
│       │   └── tests/
│       │       ├── test_engine.py
│       │       └── test_execution_functions.py
│       ├── integrations/        # External services
│       │   ├── __init__.py
│       │   ├── ibkr_client/
│       │   │   ├── __init__.py
│       │   │   ├── client.py
│       │   │   ├── circuit_breaker.py
│       │   │   └── tests/
│       │   │       └── test_client.py
│       │   └── discord_notifier/
│       │       ├── __init__.py
│       │       ├── notifier.py
│       │       └── tests/
│       │           └── test_notifier.py
│       ├── risk_management/     # Enhanced risk system
│       │   ├── __init__.py
│       │   ├── risk_manager.py  # Core risk management
│       │   ├── position_sizer.py # Automated position sizing
│       │   ├── portfolio_tracker.py # Portfolio risk tracking
│       │   └── tests/
│       │       ├── test_risk_manager.py
│       │       ├── test_position_sizer.py
│       │       └── test_portfolio_tracker.py
│       └── persistence/         # State management
│           ├── __init__.py
│           ├── state_manager.py
│           ├── trade_history.py
│           └── tests/
│               └── test_state_manager.py
├── data/                       # ✅ Runtime data files
│   ├── trade_plans/           # ✅ YAML trade plans
│   │   ├── *.yaml             # ✅ User trade plan files
│   │   └── templates/         # ✅ Plan templates with inline docs
│   │       ├── close_above.yaml   # ✅ Close above execution template
│   │       ├── close_below.yaml   # ✅ Close below execution template  
│   │       └── trailing_stop.yaml # ✅ Trailing stop template
│   ├── state/                 # JSON position state
│   └── history/               # CSV trade history
├── logs/                      # Enhanced logging structure
│   ├── trades.log            # Trade execution logs
│   ├── risk.log              # Risk management logs
│   ├── system.log            # System events
│   └── cli.log               # CLI wizard interactions
├── scripts/                   # Utility scripts
│   ├── setup_environment.py
│   ├── validate_config.py
│   └── create_plan_templates.py
├── tests/                     # Integration tests
│   ├── conftest.py
│   └── integration/
├── .env.example              # Environment template
├── config.yaml.example       # Config template
├── user_config.yaml.example  # User preferences template
├── pyproject.toml           # UV/project config
├── uv.lock                  # Locked dependencies
├── README.md
└── CLAUDE.md                # AI context
```
