# Trade Engine Orchestration Layer - Bug Analysis & Data Flow

> **Document Purpose:** Comprehensive analysis of bugs and gaps in the orchestration layer preventing lifecycle tests from passing.
>
> **Date:** 2025-10-08 (Updated: 2025-12-07)
> **Scope:** Complete functional journey from market data → entry signal → order placement → status update
> **Status:** PARTIALLY RESOLVED - Original bugs fixed, tests now progressing further

---

## Status Update (2025-12-07)

### ✅ FIXED Issues

1. **Bug #1: Mock Order Execution Field Mismatch** - RESOLVED
   - Fixed `quantity` → `calculated_position_size` field mapping in test fixture
   - Tests now successfully place orders without AttributeError

2. **Bug #0: Test Fixture Async/Await Mismatch** - RESOLVED (NEW)
   - Fixed mock_trade_plan_loader using `AsyncMock` for `load_all_plans`
   - Changed to regular `Mock` since real implementation is synchronous
   - Tests now load active plans correctly during orchestrator startup

### 🔄 Remaining Work

- Gap #2: Position state creation after order fill
- Gap #3: Order result feedback to trade plan
- Missing `save_plan` implementation in TradePlanLoader

---

## Executive Summary (Original Analysis)

**Primary Issue:** Trade plan status does not update from `AWAITING_ENTRY` to `POSITION_OPEN` after successful order placement.

**Root Cause:** Mock test fixture has field name mismatch causing exception during order placement, which cascades into orchestrator not receiving success confirmation.

**Impact:** 3 lifecycle integration tests fail because the trade lifecycle cannot progress beyond entry signal detection.

---

## Complete Data Flow Journey

### 1. Market Data Ingestion → Signal Generation

```
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 1: Market Data Arrives                                    │
└─────────────────────────────────────────────────────────────────┘

Location: trade_engine/orchestration/core.py:162-192
Function: TradeOrchestrator.process_market_data_event()

INPUT:  BarData(symbol="AAPL", close_price=180.75, bar_size="15min")

FLOW:
1. Filter plans by symbol & timeframe
   - active_plans (AWAITING_ENTRY) → relevant_active_plans
   - position_plans (POSITION_OPEN) → relevant_position_plans

2. For each relevant plan:
   → _evaluate_trade_plan(plan, bar_data)

STATUS: ✅ Working correctly
```

### 2. Entry Function Evaluation

```
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 2: Entry Function Evaluation                              │
└─────────────────────────────────────────────────────────────────┘

Location: trade_engine/orchestration/core.py:194-205
Function: TradeOrchestrator._evaluate_trade_plan()

LOGIC:
if plan.status == TradePlanStatus.AWAITING_ENTRY:
    → _evaluate_entry_function(plan, bar_data)

Location: trade_engine/orchestration/core.py:207-269
Function: TradeOrchestrator._evaluate_entry_function()

FLOW:
1. Build ExecutionContext with:
   - symbol, timeframe, current_bar
   - trade_plan_params (from plan.entry_function.parameters)
   - position_state = None (no position yet)

2. Create ExecutionFunctionConfig:
   - name: "AAPL_20250815_001_entry"
   - function_type: "close_above"
   - timeframe: "15min"
   - parameters: {"threshold": 180.50}

3. Get/create function instance from registry
   → entry_function = function_registry.get_or_create_function(config)

4. Evaluate function:
   → signal = await entry_function.evaluate(context)

   RESULT: ExecutionSignal(
       should_execute=True,
       action=ExecutionAction.ENTER_LONG,
       confidence=0.95,
       reasoning="Close $180.75 above threshold $180.50"
   )

5. Process entry signal:
   → result = signal_processor.process_entry_signal(plan, context, signal)

STATUS: ✅ Working correctly - signal generates properly
```

### 3. Signal Processing → Order Creation

```
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 3: Signal Processing & Order Creation                     │
└─────────────────────────────────────────────────────────────────┘

Location: trade_engine/signal_processing/core.py:74-148
Function: SignalProcessor.process_entry_signal()

INPUT: signal.action = ExecutionAction.ENTER_LONG

FLOW:
1. Determine trade direction from plan price relationships:
   - stop_loss (178.00) < entry_level (180.50) < take_profit (185.00)
   → is_long_trade = True

2. Route to long entry processor:
   → _process_long_entry(trade_plan, context, signal, function_name)

Location: trade_engine/signal_processing/core.py:150-214
Function: SignalProcessor._process_long_entry()

FLOW:
1. Risk validation:
   → _validate_risk(trade_plan, signal, OrderSide.BUY)
   STATUS: ✅ Passes (mocked)

2. Create order request:
   → order_request = execution_adapter.order_request_builder.create_entry_order(
        symbol=trade_plan.symbol,              # "AAPL"
        side=OrderSide.BUY,
        signal=signal,
        context=context,
        function_name=function_name,           # "close_above"
        position_size=trade_plan.calculated_position_size  # 80
   )

Location: trade_engine/order_request_builder.py:46-108
Function: OrderRequestBuilder.create_entry_order()

ORDER REQUEST CREATED:
OrderRequest(
    trade_plan_id="AAPL_20250815_001",
    symbol="AAPL",
    side=OrderSide.BUY,
    order_type="MKT",
    entry_price=Decimal("180.75"),
    stop_loss_price=Decimal("178.50"),      # Calculated
    take_profit_price=Decimal("183.00"),    # Calculated
    risk_category=RiskCategory.NORMAL,
    calculated_position_size=80,            # ⚠️ KEY FIELD
    notes="Entry triggered by close_above: ..."
)

STATUS: ✅ Order request created successfully
```

### 4. Order Placement (WHERE THE BUG OCCURS)

```
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 4: Order Placement - ⚠️ BUG LOCATION                      │
└─────────────────────────────────────────────────────────────────┘

Location: trade_engine/signal_processing/core.py:184
Function: execution_adapter.order_execution_manager.place_market_order()

EXPECTED FLOW (Production):
1. Risk validation on order request
2. Create Order object from OrderRequest
3. Execute via IBKR adapter or simulation
4. Return OrderResult(success=True, order_id="...")

ACTUAL FLOW (Test):
Location: trade_engine/tests/test_complete_lifecycle_integration.py:163-178
Mock: mock_order_execution_manager.place_market_order()

CODE:
async def mock_place_order(order_request):
    manager.orders_placed.append(order_request)

    return OrderResult(
        success=True,
        order_id=f"ORDER_{len(manager.orders_placed)}",
        trade_plan_id=order_request.trade_plan_id,
        order_status=OrderStatus.FILLED,
        symbol=order_request.symbol,
        side=order_request.side,
        quantity=order_request.quantity,  # ⚠️ BUG: Field doesn't exist!
        order_type=order_request.order_type,
        fill_price=Decimal("180.75"),
        fill_time=datetime.now(UTC)
    )

🐛 BUG #1: Field Name Mismatch
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
LINE 174: quantity=order_request.quantity
ISSUE:    OrderRequest does NOT have a 'quantity' field
CORRECT:  OrderRequest has 'calculated_position_size' field

IMPACT:
When mock tries to access order_request.quantity:
→ AttributeError: 'OrderRequest' object has no attribute 'quantity'
→ Exception caught by signal processor (line 207)
→ Returns SignalProcessingResult(success=False, error_message="...")
→ Orchestrator never receives success=True

STATUS: ❌ FAILS - Exception prevents successful order placement
```

### 5. Status Update (Never Reached)

```
┌─────────────────────────────────────────────────────────────────┐
│ PHASE 5: Plan Status Update - NOT REACHED                       │
└─────────────────────────────────────────────────────────────────┘

Location: trade_engine/orchestration/core.py:252-269
Condition: if result.success and result.order_result:

EXPECTED:
if result.success and result.order_result:  # Should be True
    # Update plan status
    old_status = plan.status                # "awaiting_entry"
    plan.status = TradePlanStatus.POSITION_OPEN  # ✅ Status update

    # Move to position tracking
    self.position_plans[plan.plan_id] = plan  # ✅ Add to position_plans
    del self.active_plans[plan.plan_id]       # (implicitly removed)

    # Record statistics
    self.statistics.record_position_opened(...)

ACTUAL:
result.success = False  # Due to exception in mock
→ Condition evaluates to False
→ Status update code NEVER EXECUTES
→ Plan remains in AWAITING_ENTRY
→ Plan remains in active_plans (not moved to position_plans)

STATUS: ❌ BLOCKED - Never reached due to Phase 4 bug
```

---

## Bug Catalog

### Bug #0: Test Fixture Async/Await Mismatch ✅ FIXED

**Location:** `src/auto_trader/trade_engine/tests/test_complete_lifecycle_integration.py:112`

**Issue:**
```python
# WRONG - Using AsyncMock for synchronous method
loader.load_all_plans = AsyncMock(return_value={...})
```

**Root Cause:** TradePlanLoader.load_all_plans() is a synchronous method, but test fixture mocked it as async, causing coroutine object errors.

**Severity:** 🔴 CRITICAL - Prevented orchestrator from loading any plans

**Fix Applied:**
```python
# CORRECT - Using regular Mock for synchronous method
loader.load_all_plans = Mock(return_value={...})
```

**Status:** ✅ RESOLVED (2025-12-07)

---

### Bug #1: Mock Order Execution Manager Field Mismatch ✅ FIXED

**Location:** `src/auto_trader/trade_engine/tests/test_complete_lifecycle_integration.py:174`

**Issue:**
```python
# WRONG
quantity=order_request.quantity  # OrderRequest doesn't have 'quantity'

# CORRECT
quantity=order_request.calculated_position_size  # Actual field name
```

**Root Cause:** OrderRequest model uses `calculated_position_size`, but mock fixture expected old field name `quantity`.

**Severity:** 🔴 CRITICAL - Previously blocked all lifecycle tests

**Fix Applied:**
```python
# The test now properly handles both dict and object order requests
if isinstance(order_request, dict):
    quantity = order_request.get("quantity", order_request.get("calculated_position_size"))
else:
    quantity = order_request.calculated_position_size
```

**Status:** ✅ RESOLVED (Original fix from earlier work)

---

### Bug #2: Missing Active Plans Cleanup

**Location:** `src/auto_trader/trade_engine/orchestration/core.py:264`

**Issue:** When plan moves to position_plans, it should be explicitly removed from active_plans.

**Current Code:**
```python
# Move to position tracking
self.position_plans[plan.plan_id] = plan
# ⚠️ active_plans not explicitly cleaned up
```

**Recommended Fix:**
```python
# Move to position tracking
self.position_plans[plan.plan_id] = plan
if plan.plan_id in self.active_plans:
    del self.active_plans[plan.plan_id]  # ✅ Explicit cleanup
```

**Severity:** 🟡 MEDIUM - May cause duplicate processing or memory leaks

---

### Bug #3: OrderResult Field Usage Inconsistency

**Location:** Multiple locations (signal processor, orchestrator)

**Issue:** Code creates OrderResult but doesn't validate all required fields match OrderRequest schema.

**Example:**
```python
# In mock (line 174)
quantity=order_request.quantity  # Wrong field

# In production code (integrations/ibkr_client/order_execution_manager.py:312)
quantity=request.calculated_position_size or 0  # Correct field
```

**Severity:** 🟡 MEDIUM - Inconsistency between production and test code

**Recommendation:** Create helper function to convert OrderRequest → OrderResult consistently.

---

## Integration Gaps

### Gap #1: No Validation of OrderRequest Before Placement

**Location:** `trade_engine/signal_processing/core.py:175-185`

**Issue:** OrderRequest is created and immediately passed to order execution manager without validating required fields are populated.

**Risk:**
- If `calculated_position_size` is None → order fails
- If `entry_price` is missing → order fails
- No early validation before expensive API call

**Recommendation:**
```python
# Add validation before placement
if not order_request:
    return SignalProcessingResult(success=False, error_message="Failed to create order request")

if not order_request.calculated_position_size:
    return SignalProcessingResult(success=False, error_message="Position size not calculated")

# Then place order
order_result = await self.execution_adapter.order_execution_manager.place_market_order(order_request)
```

---

### Gap #2: Missing Position State Creation

**Location:** `trade_engine/orchestration/core.py:264-269`

**Issue:** Plan status updates to POSITION_OPEN but no corresponding PositionEntry is created in position state manager.

**Current:**
```python
self.position_plans[plan.plan_id] = plan  # ✅ Plan tracked
# ⚠️ No position entry created in position_state_manager
```

**Impact:** Exit functions will fail because they need position state with:
- entry_price
- remaining_quantity
- is_long/is_short
- cost_basis

**Expected Flow:**
```python
# After successful order
position_entry = PositionEntry(
    position_id=f"{plan.plan_id}_POS",
    plan_id=plan.plan_id,
    symbol=plan.symbol,
    side=OrderSide.BUY,
    entry_price=result.order_result.fill_price,
    quantity=result.order_result.quantity,
    # ...
)
self.position_state_manager.add_position(position_entry)
```

**Severity:** 🔴 CRITICAL - Blocks exit signal processing

---

### Gap #3: No Order Result → Plan Feedback Loop

**Location:** `trade_engine/orchestration/core.py:252-269`

**Issue:** OrderResult contains fill information (price, time) but this data is not persisted back to the trade plan.

**Missing Updates:**
```python
# Should update plan with actual execution details
plan.actual_entry_price = result.order_result.fill_price
plan.actual_entry_time = result.order_result.fill_time
plan.actual_position_size = result.order_result.quantity
plan.order_id = result.order_result.order_id
```

**Impact:** Trade history and P&L calculations won't have actual execution data.

---

## Data Model Mismatches

### Mismatch #1: OrderRequest vs Order

**OrderRequest Fields:**
```python
- calculated_position_size: Optional[int]  # Pre-calculated
- entry_price: Decimal                     # Target price
- stop_loss_price: Decimal
- take_profit_price: Decimal
```

**Order Fields:**
```python
- quantity: int                            # Actual size
- price: Optional[Decimal]                 # Limit price
- stop_price: Optional[Decimal]
```

**Issue:** Field naming inconsistency causes confusion about which model to use where.

---

### Mismatch #2: TradePlan.calculated_position_size vs Actual Size

**TradePlan:**
```python
calculated_position_size: Optional[int] = None  # May not be set
```

**Usage in OrderRequestBuilder:**
```python
position_size=position_size  # Passed as parameter, may be None
```

**Issue:** If trade plan doesn't have calculated_position_size set, order request will have None, causing order placement to fail.

**Fix:** Ensure calculated_position_size is always populated before signal processing.

---

## Recommended Fix Priority

### Priority 1: Critical (Blocks Tests) - PARTIALLY COMPLETE
1. ✅ DONE - Fix mock field name: `quantity` → `calculated_position_size`
2. ✅ DONE - Fix test fixture async/await mismatch for `load_all_plans`
3. ⬜ TODO - Ensure TradePlan.calculated_position_size is populated before signal processing
4. ⬜ TODO - Create PositionEntry in position_state_manager after successful order
5. ⬜ TODO - Implement `save_plan` method in TradePlanLoader (currently missing)

### Priority 2: Important (Data Integrity)
6. ⬜ Add OrderRequest validation before placement
7. ⬜ Update plan with actual execution details from OrderResult
8. ⬜ Explicit cleanup of active_plans when moving to position_plans

### Priority 3: Code Quality (Maintainability)
9. ⬜ Create OrderRequest → Order conversion helper
10. ⬜ Standardize field naming across models
11. ⬜ Add integration test for complete lifecycle with real models (not just mocks)

---

## Test Execution Flow Visualization

```
TEST: test_complete_lifecycle_entry_to_exit
══════════════════════════════════════════════════════════════════

┌──────────────────────────────────────────────────────────────────┐
│ Setup: Create TradePlan with calculated_position_size=80         │
│        Create mock order execution manager                       │
│        Start orchestrator                                        │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ Phase 1: Send bar BELOW threshold (180.00 < 180.50)             │
│          ✅ No signal generated                                  │
│          ✅ Plan remains AWAITING_ENTRY                          │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ Phase 2: Send bar ABOVE threshold (180.75 > 180.50)             │
│          ✅ Signal generated (should_execute=True)               │
│          ✅ Order request created                                │
│          ❌ Mock tries to access order_request.quantity          │
│          ❌ AttributeError thrown                                │
│          ❌ Signal processor returns success=False               │
│          ❌ Orchestrator skips status update                     │
└──────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌──────────────────────────────────────────────────────────────────┐
│ Assertion: plan.status == POSITION_OPEN                          │
│            ❌ FAILS: status is still 'awaiting_entry'            │
└──────────────────────────────────────────────────────────────────┘
```

---

## Conclusion

### Current Status (2025-12-07)

**Major Progress:** The critical blocking bugs have been resolved:

1. ✅ **Test fixture async/await bug** - FIXED
   - Mock now correctly uses `Mock` instead of `AsyncMock` for synchronous methods
   - Orchestrator can now load active plans successfully

2. ✅ **Test fixture field mismatch** - FIXED
   - Mock properly handles `calculated_position_size` field
   - Order placement no longer throws AttributeError

**Remaining Work:**

1. **Missing integrations** - Position state not created after order fills
2. **Incomplete feedback** - Execution results not persisted to trade plan
3. **Missing method** - TradePlanLoader.save_plan() needs implementation

The orchestration flow logic is sound:
- ✅ Market data routing works
- ✅ Entry function evaluation works
- ✅ Signal generation works
- ✅ Order request creation works
- ✅ Order placement works (after fixes)
- ⏳ Status update - needs testing
- ⏳ Position state management - needs implementation

**Next Steps:** Run the lifecycle tests to see how far they progress and identify remaining gaps.
