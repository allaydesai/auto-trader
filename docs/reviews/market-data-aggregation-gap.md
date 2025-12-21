# Gap Report: Real-Time Market Data Aggregation

**Date:** 2025-12-21
**Reporter:** AI Coding Assistant
**Scope:** `src/auto_trader/integrations/ibkr_client/`
**Current Status:** Critical Gap Identified

---

## Executive Summary

A deep dive into the IBKR market data pipeline has revealed a critical architectural flaw: **the system lacks an aggregation layer for real-time bars.** While the system allows users to specify timeframes like "1min", "5min", or "15min", it currently processes every symbol using a raw 5-second stream, mislabelling these 5-second "pulses" as full candles.

**Severity:** Critical (Impacts Signal Accuracy & Indicator Math)

---

## Technical Details

### 1. IBKR API Limitation
The `SubscriptionManager` utilizes the `ib_async` method `reqRealTimeBars()`:

```python
# src/auto_trader/integrations/ibkr_client/subscription_manager.py:158
return self._ib.reqRealTimeBars(
    contract,
    5,  # HARDCODED: IB KR API only supports 5-second real-time bars
    "TRADES",
    False,
)
```
Interactive Brokers only provides real-time bar updates in fixed 5-second increments. To support any other timeframe, the client application *must* implement its own aggregation logic.

### 2. Mislabelling in Ingestion
In `MarketDataManager._on_bar_update`, the system receives these 5-second bars but passes them to the `BarConverter` along with the *requested* `bar_size` label:

```python
# src/auto_trader/integrations/ibkr_client/market_data_manager.py:136
bar_data = self._bar_converter.convert_ib_bar_to_bar_data(
    bars, symbol, bar_size # bar_size is "5min", but bars contains 5s of data
)
```

The resulting `BarData` object is then cached and distributed as if it were a completed candle for the requested timeframe.

---

## Business & Functional Impact

### 1. Mathematical Inaccuracy
Any technical indicator (RSI, Moving Averages, etc.) calculated by the `ExecutionFunctions` will be fundamentally incorrect. They are effectively being calculated on a "noisy" 5-second timeframe rather than the intended trend timeframe.

### 2. Evaluation Frequency Error
The `TradeOrchestrator` evaluates entry and exit conditions every time a bar is received. Currently, this means strategies are being evaluated **every 5 seconds**, regardless of their configured timeframe. This leads to premature exits and entries based on micro-volatility (noise) rather than confirmed candle closes.

### 3. Indicator "Flicker"
Signals may trigger and then disappear within the actual 5-minute window because the system is making decisions based on 5-second snapshots.

---

## Proposed Remediation

A `BarAggregator` service must be implemented to sit between the `SubscriptionManager` and the `MarketDataCache`.

1.  **Buffer State**: Maintain a running OHLCV state for every `(symbol, bar_size)` pair.
2.  **Aggregation Logic**: 
    *   **Open**: Price of the first 5s bar in the period.
    *   **High**: Max price across all 5s bars in the period.
    *   **Low**: Min price across all 5s bars in the period.
    *   **Close**: Price of the most recent 5s bar.
    *   **Volume**: Sum of volumes across all 5s bars.
3.  **Emission Trigger**: Only update the `MarketDataCache` and notify subscribers when the 5-second bar's timestamp crosses a timeframe boundary (e.g., at 10:00:00, 10:05:00).

---

## Conclusion

The current "multi-timeframe" support is an illusion; the system is currently a "5-second scalper" regardless of configuration. Fixing this is prerequisite for reliable live trading.

