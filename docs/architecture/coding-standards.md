# Coding Standards

## Core Standards
- **Languages & Runtimes:** Python 3.11.8 exclusively
- **Style & Linting:** ruff with 100 char line limit, format on save
- **Test Organization:** Tests in `tests/` subdirectory next to code

## Naming Conventions
| Element | Convention | Example |
|---------|------------|---------|
| Variables/Functions | snake_case | `calculate_position_size` |
| Classes | PascalCase | `TradePlan` |
| Constants | UPPER_SNAKE_CASE | `MAX_POSITIONS` |
| Private | _leading_underscore | `_internal_state` |

## Critical Rules
- **Always use pydantic models:** Never pass raw dicts between functions
- **No print statements:** Use logger exclusively for all output
- **Type hints required:** All functions must have complete type annotations
- **UTC everywhere:** All timestamps in UTC, convert at display layer only
- **Decimal for money:** Never use float for prices or monetary values
- **Repository pattern:** All external data access through repository interfaces
