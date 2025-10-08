# Integration Gaps and Recommended Fixes

## Critical Gap 1: Open Positions Not Evaluated

### Problem
When a position opens, the trade plan moves from `active_plans` to `position_plans`, but the market data processing only checks `active_plans`. This means **exit functions are never evaluated**.

### Location
`src/auto_trader/trade_engine/orchestration/core.py:148-184`

### Current Buggy Code
```python
async def process_market_data_event(self, bar_data: BarData) -> None:
    """Process incoming market data and evaluate relevant trade plans."""
    if not self.is_running:
        return
    
    symbol = bar_data.symbol
    timeframe = bar_data.timeframe
    
    # BUG: Only checks active_plans!
    relevant_plans = self.coordinator.filter_plans_for_symbol(
        self.active_plans, symbol
    )
    
    if not relevant_plans:
        return  # Exit early, never evaluates position_plans!
    
    # Process each relevant plan
    for plan in relevant_plans:
        await self._evaluate_trade_plan(plan, bar_data)
```

### Recommended Fix
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
    
    # Process ALL relevant plans (both active and positions)
    for plan in all_relevant_plans:
        try:
            await self._evaluate_trade_plan(plan, bar_data)
            self.statistics.record_plan_processed(plan.plan_id)
        except Exception as e:
            logger.error(f"Error evaluating plan {plan.plan_id}: {e}")
            await self._handle_plan_error(plan, str(e))
```

### Impact
- **Critical**: Without this fix, exits will never trigger
- Stop losses won't execute
- Take profits won't execute
- Trailing stops won't work

---

## Potential Gap 2: Function Instantiation from Plans

### Problem
Trade plans have `entry_function` and `exit_function` configurations, but it's unclear if these are being converted to actual function instances.

### What Should Happen
```python
# When plan is loaded:
plan = TradePlan(...)

# Create entry function from plan config
entry_config = ExecutionFunctionConfig(
    name=f"{plan.plan_id}_entry",
    function_type=plan.entry_function.function_type,
    timeframe=plan.entry_function.timeframe,
    parameters=plan.entry_function.parameters,
    enabled=True
)
entry_function = await function_registry.create_function(entry_config)

# Create exit function from plan config
exit_config = ExecutionFunctionConfig(
    name=f"{plan.plan_id}_exit",
    function_type=plan.exit_function.function_type,
    timeframe=plan.exit_function.timeframe,
    parameters=plan.exit_function.parameters,
    enabled=True
)
exit_function = await function_registry.create_function(exit_config)
```

### Where This Should Be
In `TradeOrchestrator.start()` or when plans are loaded:

```python
async def start(self) -> None:
    """Initialize orchestrator and start trade lifecycle management."""
    logger.info("Starting TradeOrchestrator")
    
    # Load all active trade plans
    self.active_plans = await self.coordinator.load_active_trade_plans()
    
    # CREATE EXECUTION FUNCTIONS FROM PLANS
    for plan in self.active_plans.values():
        await self._register_plan_functions(plan)
    
    self.is_running = True

async def _register_plan_functions(self, plan: TradePlan) -> None:
    """Create and register execution functions for a trade plan."""
    
    # Create entry function
    entry_config = ExecutionFunctionConfig(
        name=f"{plan.plan_id}_entry",
        function_type=plan.entry_function.function_type,
        timeframe=plan.entry_function.timeframe,
        parameters=plan.entry_function.parameters,
        enabled=True,
        lookback_bars=50
    )
    await self.function_registry.create_function(entry_config)
    
    # Create exit function
    exit_config = ExecutionFunctionConfig(
        name=f"{plan.plan_id}_exit",
        function_type=plan.exit_function.function_type,
        timeframe=plan.exit_function.timeframe,
        parameters=plan.exit_function.parameters,
        enabled=True,
        lookback_bars=50
    )
    await self.function_registry.create_function(exit_config)
```

Then in evaluation:
```python
async def _evaluate_entry_function(self, plan: TradePlan, bar_data: BarData):
    # Get the instantiated function by name
    function = self.function_registry.get_function(f"{plan.plan_id}_entry")
    if not function:
        logger.error(f"Entry function not found for {plan.plan_id}")
        return
    
    # Evaluate
    signal = await function.evaluate(context)
```

---

## Potential Gap 3: Timeframe Matching

### Problem
Need to ensure that functions are only evaluated when bars match their timeframe.

### Recommendation
Add timeframe validation in evaluation:

```python
async def _evaluate_entry_function(self, plan: TradePlan, bar_data: BarData):
    """Evaluate entry function for a trade plan."""
    
    # VALIDATE TIMEFRAME MATCH
    if bar_data.timeframe.value != plan.entry_function.timeframe:
        logger.debug(
            f"Skipping entry evaluation: bar timeframe {bar_data.timeframe.value} "
            f"doesn't match function timeframe {plan.entry_function.timeframe}"
        )
        return
    
    # Continue with evaluation...
```

---

## Testing Recommendations

### Test Case 1: Complete Lifecycle
```python
@pytest.mark.asyncio
async def test_complete_trade_lifecycle():
    """Test entry → position → exit flow."""
    
    # 1. Create plan with entry and exit functions
    plan = create_test_plan(
        symbol="AAPL",
        entry_function={"function_type": "close_above", "timeframe": "15min"},
        exit_function={"function_type": "close_below", "timeframe": "15min"}
    )
    
    # 2. Load plan into orchestrator
    orchestrator.active_plans[plan.plan_id] = plan
    
    # 3. Send bar that triggers entry
    entry_bar = create_bar("AAPL", close_price=180.75, timeframe="15min")
    await orchestrator.process_market_data_event(entry_bar)
    
    # Verify: Plan moved to position_plans
    assert plan.plan_id in orchestrator.position_plans
    assert plan.plan_id not in orchestrator.active_plans
    assert plan.status == TradePlanStatus.POSITION_OPEN
    
    # 4. Send bar that triggers exit
    exit_bar = create_bar("AAPL", close_price=177.50, timeframe="15min")
    await orchestrator.process_market_data_event(exit_bar)
    
    # Verify: Plan completed and removed
    assert plan.plan_id not in orchestrator.position_plans
    assert plan.status == TradePlanStatus.COMPLETED
```

### Test Case 2: Multiple Timeframes
```python
@pytest.mark.asyncio
async def test_multiple_timeframes():
    """Test plans with different timeframes."""
    
    # Plan 1: 15min entry, 1min exit
    plan1 = create_test_plan(
        symbol="AAPL",
        entry_timeframe="15min",
        exit_timeframe="1min"
    )
    
    # Send 1min bar - should NOT trigger entry
    bar_1min = create_bar("AAPL", timeframe="1min")
    await orchestrator.process_market_data_event(bar_1min)
    assert plan1.status == TradePlanStatus.AWAITING_ENTRY
    
    # Send 15min bar - SHOULD trigger entry
    bar_15min = create_bar("AAPL", timeframe="15min")
    await orchestrator.process_market_data_event(bar_15min)
    assert plan1.status == TradePlanStatus.POSITION_OPEN
    
    # Send 1min bar - SHOULD trigger exit now
    bar_1min_exit = create_bar("AAPL", timeframe="1min", close_price=177.00)
    await orchestrator.process_market_data_event(bar_1min_exit)
    assert plan1.status == TradePlanStatus.COMPLETED
```

---

## Summary

### Critical Fixes Needed
1. ✅ **Fix Gap 1**: Evaluate both active_plans AND position_plans

### Verification Needed
2. ❓ **Check Gap 2**: Are functions created from plan configs?
3. ❓ **Check Gap 3**: Is timeframe matching validated?

### Testing Required
4. 📝 **Test complete lifecycle**: Entry → Position → Exit
5. 📝 **Test multiple timeframes**: Different entry/exit timeframes
6. 📝 **Test concurrent plans**: Multiple plans for same symbol


