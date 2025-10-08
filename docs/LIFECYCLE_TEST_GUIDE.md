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

## Expected Results (BEFORE Fix)

### Test: `test_complete_lifecycle_entry_to_exit`

**What should happen**:
```
Phase 1: Plan loaded ✓
Phase 2: Bar below threshold → No entry ✓
Phase 3: Bar above threshold → Entry triggered ✓
Phase 4: Bar above stop → No exit ✓
Phase 5: Bar below stop → Exit triggered ❌ FAILS HERE
```

**Why it fails**:
```
AssertionError: ❌ GAP #1 DETECTED: Expected COMPLETED, got POSITION_OPEN.
This means exit function was never evaluated because position_plans
are not included in process_market_data_event()!
```

**The problem**:
- After entry, plan moves from `active_plans` to `position_plans`
- `process_market_data_event()` only checks `active_plans`
- Exit function is **never evaluated**

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
  - Plan status: position_open  ← STILL OPEN!
  - In active_plans: False
  - In position_plans: True
  - Orders placed: 0  ← NO EXIT ORDER!

FAILED: Expected COMPLETED, got position_open
```

## The Fix

### Location
`src/auto_trader/trade_engine/orchestration/core.py:148-184`

### Change Required

**Before (Buggy)**:
```python
async def process_market_data_event(self, bar_data: BarData) -> None:
    """Process incoming market data and evaluate relevant trade plans."""
    if not self.is_running:
        return
    
    symbol = bar_data.symbol
    
    # BUG: Only checks active_plans!
    relevant_plans = self.coordinator.filter_plans_for_symbol(
        self.active_plans, symbol
    )
    
    if not relevant_plans:
        return  # Never evaluates position_plans!
    
    for plan in relevant_plans:
        await self._evaluate_trade_plan(plan, bar_data)
```

**After (Fixed)**:
```python
async def process_market_data_event(self, bar_data: BarData) -> None:
    """Process incoming market data and evaluate relevant trade plans."""
    if not self.is_running:
        return
    
    symbol = bar_data.symbol
    timeframe = bar_data.timeframe
    
    # FIX: Check BOTH active_plans AND position_plans
    relevant_active_plans = self.coordinator.filter_plans_for_symbol(
        self.active_plans, symbol
    )
    
    relevant_position_plans = self.coordinator.filter_plans_for_symbol(
        self.position_plans, symbol
    )
    
    # Combine both lists
    all_relevant_plans = list(relevant_active_plans) + list(relevant_position_plans)
    
    if not all_relevant_plans:
        return
    
    logger.debug(
        f"Processing {len(relevant_active_plans)} awaiting entry, "
        f"{len(relevant_position_plans)} open positions",
        symbol=symbol,
        timeframe=timeframe.value,
    )
    
    # Process ALL relevant plans
    for plan in all_relevant_plans:
        try:
            await self._evaluate_trade_plan(plan, bar_data)
            self.statistics.record_plan_processed(plan.plan_id)
        except Exception as e:
            logger.error(f"Error evaluating plan {plan.plan_id}: {e}")
            await self._handle_plan_error(plan, str(e))
```

## Expected Results (AFTER Fix)

### Test: `test_complete_lifecycle_entry_to_exit`

**What should happen**:
```
Phase 1: Plan loaded ✓
Phase 2: Bar below threshold → No entry ✓
Phase 3: Bar above threshold → Entry triggered ✓
Phase 4: Bar above stop → No exit ✓
Phase 5: Bar below stop → Exit triggered ✓ NOW PASSES!
```

**Output**:
```
==================================================
PHASE 5: Sending bar BELOW stop loss (EXIT SIGNAL)
==================================================
Bar: AAPL @ 177.50 (15min)
Stop loss threshold: 178.00
Expected: EXIT signal triggered

After processing exit bar:
  - Plan status: completed  ← FIXED!
  - In active_plans: False
  - In position_plans: False  ← REMOVED!
  - Orders placed: 1  ← EXIT ORDER PLACED!

==================================================
✅ TEST PASSED: Complete lifecycle works!
==================================================
```

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

### Step 1: Run Test (Confirm Gaps)
```bash
scripts/test_lifecycle.bat
```

**Expected**: Test FAILS at Phase 5, confirming Gap #1

### Step 2: Implement Fix
Edit `src/auto_trader/trade_engine/orchestration/core.py` as shown above

### Step 3: Run Test (Validate Fix)
```bash
scripts/test_lifecycle.bat
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
    
    exit_function={
        "function_type": "close_below",
        "timeframe": "15min",
        "parameters": {"threshold": 178.00}
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

## Next Steps

1. **Run test** to confirm gaps
2. **Implement fix** for Gap #1
3. **Re-run test** to validate
4. **Check for Gaps #2 and #3** (function instantiation, timeframe matching)
5. **Implement additional fixes** if needed
6. **Run full test suite** to ensure no regressions

---

**Status**: Ready to run
**Expected Result**: Test will FAIL, exposing Gap #1
**After Fix**: Test will PASS, confirming lifecycle works

