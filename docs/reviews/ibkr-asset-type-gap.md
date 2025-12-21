# Gap Report: IBKR Multi-Asset Support

**Date:** 2025-12-21
**Reporter:** AI Coding Assistant
**Scope:** `src/auto_trader/integrations/ibkr_client/`
**Current Status:** Identified (Limited to US Equities)

---

## Executive Summary

A review of the IBKR integration layer has identified a significant architectural gap: the system is currently hardcoded to support only **US Equities** via the **SMART** exchange. There is no existing infrastructure to handle other asset types (FX, Futures, Crypto, Options) or specified exchanges/currencies.

**Severity:** Medium (Functional Limitation)

---

## Identified Gaps

### 1. Hardcoded Contract Types in Integration Layer
Multiple components instantiate `ib_async.Stock` directly instead of using a polymorphic contract factory.

*   **Market Data:** `src/auto_trader/integrations/ibkr_client/subscription_manager.py`
    ```python
    # Line 142
    contract = Stock(symbol, "SMART", "USD")
    ```
*   **Order Execution:** `src/auto_trader/integrations/ibkr_client/ibkr_order_adapter.py`
    ```python
    # Line 56 & 112
    contract = Stock(order.symbol, "SMART", order.currency)
    ```
*   **Historical Data:** `src/auto_trader/integrations/ibkr_client/historical_data_fetcher.py`
    ```python
    # Line 105
    contract = Stock(symbol, "SMART", "USD")
    ```

### 2. Missing Metadata in Data Models
The core models do not currently store the necessary metadata to support multi-asset routing.

*   **`TradePlan` (`src/auto_trader/models/trade_plan.py`):** Lacks `asset_type`, `exchange`, and `currency` fields.
*   **`BarData` (`src/auto_trader/models/market_data.py`):** Lacks asset metadata, making it difficult to differentiate between symbols that might exist across different asset classes (e.g., "AAPL" as stock vs a hypothetical future).

### 3. Restrictive Symbol Validation
The `TradePlan` model implements a strict regex for symbols that may exclude valid non-equity formats (e.g., FX pairs with dots like `EUR.USD` or complex Futures strings).

```python
# src/auto_trader/models/trade_plan.py:163
if not re.match(r"^[A-Z]{1,10}$", v):
    # Fails for "EUR.USD" or "ESU4"
```

---

## Technical Debt Impact

*   **FX Support:** Impossible without `Forex` contract type and `IDEALPRO` exchange.
*   **Futures Support:** Impossible without `Future` contract type, expiration dates, and specific exchanges (CME, ICE, etc.).
*   **International Markets:** Hardcoded `USD` currency prevents trading on non-US exchanges.

---

## Proposed Remediation (Future Work)

1.  **Model Enhancement:**
    *   Add `asset_type` (Enum: STOCK, FOREX, FUTURE, CRYPTO, etc.) to `TradePlan`.
    *   Add `exchange` and `currency` fields (with defaults to "SMART" and "USD").
2.  **Contract Factory:**
    *   Implement a centralized `ContractFactory` that generates the correct `ib_async` contract object based on `TradePlan` metadata.
3.  **Refactor Integrations:**
    *   Replace all direct `Stock()` calls with the `ContractFactory`.
4.  **Validation Update:**
    *   Relax `TradePlan.symbol` validation to allow dots and numbers as required by other asset classes.

---

## Conclusion

While current support for US Equities is sufficient for immediate needs, the hardcoded nature of the integration layer will require significant refactoring to support any other asset class or market.

