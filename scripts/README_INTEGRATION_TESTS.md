# IBKR Market Data Integration Tests

This directory contains integration tests for the IBKR market data subscription system implemented in Story 2.2.

## Overview

The integration tests validate the market data system against the actual IBKR API using a paper trading account. These tests complement the comprehensive unit tests (63 tests with ~95% coverage) by testing real-world connectivity and data flow.

## Test Coverage

### What These Tests Validate

✅ **IBKR Connection & Authentication**
- Paper trading account connection
- Account type detection
- Connection status monitoring

✅ **Historical Data Fetching**  
- Multiple timeframes (1min, 5min, 15min)
- Data quality validation (OHLC consistency)
- Gap detection in historical sequences
- Startup context establishment

✅ **Real-time Market Data Subscriptions**
- Dynamic symbol subscription/unsubscription
- Multiple timeframe support
- Bar reception and processing
- Subscription state management

✅ **Data Quality & Caching**
- Stale data detection (>2x bar size)
- Memory management and cleanup
- Thread-safe cache operations
- Performance monitoring

✅ **Error Handling & Recovery**
- Invalid symbol handling
- Connection failure recovery
- Subscription error management
- Graceful degradation

## Prerequisites

### 1. IBKR Account Setup
- **Paper Trading Account**: Always use paper trading for integration tests
- **TWS or IB Gateway**: Must be running and configured
- **API Enabled**: Ensure API access is enabled in TWS/Gateway settings

### 2. Configuration
Required configuration files:
- `config.yaml` - System configuration
- `.env` - Environment variables with IBKR settings
- `user_config.yaml` - User preferences

Example IBKR settings in `.env`:
```bash
IBKR_HOST=127.0.0.1
IBKR_PORT=7497          # Paper trading port
IBKR_CLIENT_ID=1
IBKR_TIMEOUT=30
```

### 3. Market Hours
- **Best Results**: During US market hours (9:30 AM - 4:00 PM ET)
- **Historical Data**: Available anytime
- **Real-time Data**: Limited outside market hours

## Running Tests

### Option 1: Automated Runner (Recommended)
```bash
# Run setup validation and tests
./scripts/run_integration_tests.sh

# Just run setup checks
./scripts/run_integration_tests.sh setup

# Just run tests (skip setup)
SYMBOLS=AAPL DURATION=30 ./scripts/run_integration_tests.sh test
```

### Option 2: Manual Execution

**Step 1: Validate Environment**
```bash
python scripts/setup_integration_test_env.py
```

**Step 2: Run Integration Tests**
```bash
# Basic test with default symbols (AAPL, MSFT)
python scripts/test_ibkr_market_data_integration.py

# Custom symbols and duration
python scripts/test_ibkr_market_data_integration.py --symbols AAPL,GOOGL,TSLA --duration 120

# Verbose logging for debugging
python scripts/test_ibkr_market_data_integration.py --verbose
```

## Test Parameters

| Parameter | Description | Default | Example |
|-----------|-------------|---------|---------|
| `--symbols` | Comma-separated symbols to test | `AAPL,MSFT` | `AAPL,GOOGL,TSLA` |
| `--duration` | Real-time data collection time (seconds) | `60` | `120` |
| `--verbose` | Enable debug logging | `false` | `--verbose` |

## Understanding Test Results

### Success Criteria
- ✅ **All Checks Green**: System is working correctly
- 📊 **Bars Received > 0**: During market hours, should receive real-time data
- 🔍 **No Critical Errors**: Connection and subscription errors indicate issues

### Common Issues & Solutions

**❌ Connection Failed**
- Ensure TWS/IB Gateway is running
- Check port configuration (7497 for TWS paper trading)
- Verify API access is enabled

**❌ No Real-time Data** 
- Normal outside market hours
- Check symbol validity
- Verify market data permissions

**❌ Historical Data Errors**
- Check internet connectivity  
- Verify IBKR account has data permissions
- Some symbols may not have data for requested timeframes

## Test Architecture

```
Integration Test Flow:
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Environment     │───▶│ IBKR Connection  │───▶│ Market Data     │
│ Validation      │    │ & Authentication │    │ Operations      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                                                        │
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│ Results         │◀───│ Error Handling   │◀───│ Data Quality    │
│ & Reporting     │    │ & Recovery       │    │ Validation      │
└─────────────────┘    └──────────────────┘    └─────────────────┘
```

## Files

| File | Purpose |
|------|---------|
| `test_ibkr_market_data_integration.py` | Main integration test suite |
| `setup_integration_test_env.py` | Environment validation and setup |
| `run_integration_tests.sh` | Automated test runner script |
| `README_INTEGRATION_TESTS.md` | This documentation |

## Integration with CI/CD

These tests are designed for manual execution during development and before releases. They require:
- Live IBKR paper trading connection
- Market hours for optimal results
- Manual verification of results

**Not suitable for automated CI/CD** due to external dependencies and timing requirements.

## Safety Notes

⚠️ **Always Use Paper Trading**
- Integration tests should never run against live trading accounts
- Paper trading ports: 7497 (TWS), 4002 (IB Gateway)
- Verify account type in test output

⚠️ **Rate Limiting**
- IBKR has API rate limits (50 messages/second)
- Tests are designed to respect these limits
- Avoid running multiple test instances simultaneously

⚠️ **Market Data Costs**
- Paper accounts typically have free delayed data
- Real-time data may require market data subscriptions
- Historical data is usually included

## Troubleshooting

### Common Setup Issues

**"Failed to connect to IBKR"**
1. Verify TWS/IB Gateway is running
2. Check port configuration in settings
3. Enable API access in TWS settings
4. Verify client ID is unique

**"No historical data returned"**
1. Check internet connectivity
2. Verify symbol exists and is active
3. Check IBKR account permissions
4. Try different time duration (e.g., "2 D" instead of "1 D")

**"Permission denied" errors**
1. Ensure scripts are executable: `chmod +x scripts/*.py`
2. Check Python/UV environment setup
3. Verify project dependencies are installed

### Getting Help

1. **Check Setup**: Run `setup_integration_test_env.py` first
2. **Enable Verbose Logging**: Use `--verbose` flag for detailed output  
3. **Review IBKR Logs**: Check TWS/Gateway logs for API messages
4. **Test Individual Components**: Use unit tests to isolate issues

## Next Steps

After successful integration testing:

1. **Story 2.2 Completion**: Mark remaining tasks as complete
2. **Main Application Integration**: Connect to auto-trader main entry point
3. **Trade Engine Integration**: Hook up with execution functions
4. **End-to-End Testing**: Test complete trading workflow

---

*For questions about these integration tests, refer to Story 2.2 documentation or the development team.*