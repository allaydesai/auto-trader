#!/bin/bash
# Script to run the complete lifecycle integration test

echo "=================================================="
echo "Running Complete Lifecycle Integration Test"
echo "=================================================="
echo ""
echo "This test validates the complete trade lifecycle:"
echo "  1. Load plan with split exit functions"
echo "  2. Trigger entry signal"
echo "  3. Open position"
echo "  4. Trigger exit signal (stop_loss or take_profit)"
echo "  5. Close position"
echo ""
echo "Expected: ALL TESTS PASS ✅"
echo "  - Entry functions evaluated correctly"
echo "  - Exit functions (stop_loss + take_profit) evaluated"
echo "  - Complete lifecycle works end-to-end"
echo ""
echo "=================================================="
echo ""

# Run the test with verbose output
PYTHONPATH=src uv run pytest \
    src/auto_trader/trade_engine/tests/test_complete_lifecycle_integration.py \
    -v -s \
    --tb=short

echo ""
echo "=================================================="
echo "Test Results Analysis"
echo "=================================================="

