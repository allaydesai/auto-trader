# Complete Lifecycle Integration Test Guide

## Overview

We've created a comprehensive integration test to **validate the complete trade lifecycle** and **expose integration gaps**. This test will be used to:

1. **Confirm the gaps** (test will FAIL with current code)
2. **Implement fixes** for the gaps
3. **Validate fixes** (test will PASS after fixes)

## Test File

**Location**: `src/auto_trader/trade_engine/tests/test_complete_lifecycle_integration.py`

**What it tests**:
- Complete trade lifecycle from entry to exit
- Timeframe filtering for execution functions
- Multiple plans for the same symbol

## Running the Test

### Windows
```cmd
scripts\test_lifecycle.bat
```

### Linux/Mac
```bash
chmod +x scripts/test_lifecycle.sh
./scripts/test_lifecycle.sh
```

### Manual
```bash
PYTHONPATH=src uv run pytest \
    src/auto_trader/trade_engine/tests/test_complete_lifecycle_integration.py \
    -v -s --tb=short
```

## Test Status: ✅ ALL TESTS PASSING

### Test: `test_complete_lifecycle_entry_to_exit`

**What happens**:
```
Phase 1: Plan loaded ✓
Phase 2: Bar below threshold → No entry ✓
Phase 3: Bar above threshold → Entry triggered ✓
Phase 4: Bar above stop → No exit ✓
Phase 5: Bar below stop → Exit triggered ✓ PASSES!
```

**What was fixed**:
- Bug #1: Mock field name (`quantity` → `calculated_position_size`)
- Bug #2: Explicit `active_plans` cleanup when moving to `position_plans`
- Gap #2: PositionEntry creation in position_state_manager
- Multiple additional fixes for signal processing and exit handling

### Test Output Example

```
==================================================
PHASE 1: Plan loaded, awaiting entry
==================================================
Plan ID: AAPL_20250815_001
Status: awaiting_entry
Entry threshold: 180.5
Active plans: ['AAPL_20250815_001']
Position plans: []

==================================================
PHASE 3: Sending bar ABOVE entry threshold (ENTRY SIGNAL)
==================================================
Bar: AAPL @ 180.75 (15min)
Entry threshold: 180.50
Expected: ENTRY signal triggered
✓ Status changed to: position_open
✓ Plan moved to position_plans: True
✓ Orders placed: 1
✓ Active plans: []
✓ Position plans: ['AAPL_20250815_001']

==================================================
PHASE 5: Sending bar BELOW stop loss (EXIT SIGNAL)
==================================================
🚨 THIS IS WHERE THE BUG WILL MANIFEST!
==================================================
Bar: AAPL @ 177.50 (15min)
Stop loss threshold: 178.00
Expected: EXIT signal triggered

Current state:
  - Plan status: position_open
  - In active_plans: False
  - In position_plans: True

After processing exit bar:
  - Plan status: completed  ← FIXED!
  - In active_plans: False
  - In position_plans: False  ← REMOVED!
  - Orders placed: 1  ← EXIT ORDER PLACED!

======================================================================
✅ TEST PASSED: Complete lifecycle works!
======================================================================
Final status: completed
Total orders: 2
```

## Split Exit Functions

The test properly validates **split exit functions**:
- **stop_loss_function**: Separate function for stop loss exit (close_below @ 178.00)
- **take_profit_function**: Separate function for take profit exit (close_above @ 185.00)

Both functions are evaluated independently, and the first one to trigger closes the position.

## Additional Tests

### Test 2: `test_timeframe_filtering`

Validates that functions only evaluate on matching timeframes:
- 1min bar → ignored
- 5min bar → ignored
- 15min bar → evaluated

### Test 3: `test_multiple_plans_same_symbol`

Validates multiple plans for same symbol:
- Both plans evaluated on each bar
- Only matching plans trigger

## Workflow

### Run Tests
```bash
# Linux/Mac
./scripts/test_lifecycle.sh

# Windows
scripts\test_lifecycle.bat

# Manual
PYTHONPATH=src uv run pytest \
    src/auto_trader/trade_engine/tests/test_complete_lifecycle_integration.py \
    -v -s --tb=short
```

**Expected**: All tests PASS ✅

## Test Details

### Mock Components Used

1. **TradePlanLoader**: Returns sample plan
2. **FunctionRegistry**: Registers close_above and close_below
3. **OrderExecutionManager**: Tracks orders placed
4. **RiskManager**: Always validates as safe

### Sample Trade Plan

```python
TradePlan(
    plan_id="AAPL_20250815_001",
    symbol="AAPL",
    entry_level=180.50,
    stop_loss=178.00,
    take_profit=185.00,

    entry_function={
        "function_type": "close_above",
        "timeframe": "15min",
        "parameters": {"threshold": 180.50}
    },

    stop_loss_function={
        "function_type": "close_below",
        "timeframe": "15min",
        "parameters": {"threshold": 178.00}
    },

    take_profit_function={
        "function_type": "close_above",
        "timeframe": "15min",
        "parameters": {"threshold": 185.00}
    }
)
```

### Bar Sequence

1. **Bar @ 180.00** (15min) → Below entry → No action
2. **Bar @ 180.75** (15min) → Above entry → Entry triggered ✓
3. **Bar @ 179.00** (15min) → Above stop → No exit
4. **Bar @ 177.50** (15min) → Below stop → Exit triggered (FAILS without fix)

## Debugging Tips

### Enable Verbose Logging
```bash
PYTHONPATH=src uv run pytest \
    src/auto_trader/trade_engine/tests/test_complete_lifecycle_integration.py \
    -v -s -vv --log-cli-level=DEBUG
```

### Run Single Test
```bash
PYTHONPATH=src uv run pytest \
    src/auto_trader/trade_engine/tests/test_complete_lifecycle_integration.py::TestCompleteTradeLifecycle::test_complete_lifecycle_entry_to_exit \
    -v -s
```

### Check Which Plans Are Being Evaluated
Add to `process_market_data_event()`:
```python
logger.info(
    f"Processing market data for {symbol}",
    active_plans=list(self.active_plans.keys()),
    position_plans=list(self.position_plans.keys()),
    relevant_active=len(relevant_active_plans),
    relevant_positions=len(relevant_position_plans)
)
```

## Success Criteria

### All tests pass when:
1. ✅ Entry signal triggers and opens position
2. ✅ Plan moves from active_plans to position_plans
3. ✅ Exit functions are evaluated for open positions
4. ✅ Exit signal triggers and closes position
5. ✅ Plan moves to COMPLETED status
6. ✅ Exit order is placed
7. ✅ Plan is removed from position_plans

## Bugs Fixed

All issues identified in `ORCHESTRATION_BUGS_ANALYSIS.md` have been resolved:

1. **Bug #1**: Mock field name mismatch (`quantity` → `calculated_position_size`)
2. **Bug #2**: Explicit `active_plans` cleanup when moving to `position_plans`
3. **Gap #2**: PositionEntry creation in position_state_manager after successful order
4. **Signal Processing**: Fixed `_record_signal` method signature
5. **Exit Processing**: Fixed ExitProcessingResult parameter mismatches
6. **Cleanup Manager**: Removed incorrect `update_trade_plan_status` call

---

**Status**: ✅ All Tests Passing
**Test Coverage**: Complete lifecycle from entry → position open → exit → position closed
**Split Exit Functions**: Properly validated (stop_loss_function + take_profit_function)

