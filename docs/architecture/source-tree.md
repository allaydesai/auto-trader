# Source Tree

```plaintext
auto-trader/
├── src/
│   ├── __init__.py
│   ├── main.py                    # Entry point, max 100 lines
│   ├── config.py                  # Settings with pydantic
│   └── auto_trader/
│       ├── __init__.py
│       ├── models/               # Pydantic models
│       │   ├── __init__.py
│       │   ├── trade_plan.py
│       │   ├── position.py
│       │   ├── risk_models.py    # Risk management models
│       │   └── market_data.py
│       ├── cli/                 # Interactive CLI components
│       │   ├── __init__.py
│       │   ├── wizard.py        # Trade plan creation wizard
│       │   ├── commands.py      # CLI command handlers
│       │   ├── validators.py    # Input validation
│       │   └── tests/
│       │       ├── test_wizard.py
│       │       └── test_validators.py
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
├── data/                       # Runtime data files
│   ├── trade_plans/           # YAML trade plans
│   │   ├── active_plans.yaml  # Current trade plans
│   │   └── templates/         # Plan templates
│   │       ├── breakout.yaml
│   │       ├── pullback.yaml
│   │       └── swing_trade.yaml
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
