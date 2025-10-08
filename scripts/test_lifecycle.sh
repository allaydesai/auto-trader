#!/bin/bash
# Script to run the complete lifecycle integration test

echo "=================================================="
echo "Running Complete Lifecycle Integration Test"
echo "=================================================="
echo ""
echo "This test will validate the complete trade lifecycle:"
echo "  1. Load plan with entry/exit functions"
echo "  2. Trigger entry signal"
echo "  3. Open position"
echo "  4. Trigger exit signal"
echo "  5. Close position"
echo ""
echo "Expected: TEST WILL FAIL due to Gap #1"
echo "  - Exit functions are never evaluated"
echo "  - position_plans not in evaluation loop"
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

