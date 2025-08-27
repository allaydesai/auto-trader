#!/bin/bash
#
# IBKR Market Data Integration Test Runner
#
# This script helps run the integration tests with proper setup and validation.
#
# Usage:
#   ./scripts/run_integration_tests.sh [setup|test|all]
#

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo -e "${BLUE}IBKR Market Data Integration Test Runner${NC}"
echo "========================================"

# Function to run setup
run_setup() {
    echo -e "\n${YELLOW}Running setup and environment checks...${NC}"
    cd "$PROJECT_ROOT"
    uv run python scripts/setup_integration_test_env.py
}

# Function to run tests
run_tests() {
    echo -e "\n${YELLOW}Running integration tests...${NC}"
    cd "$PROJECT_ROOT"
    
    # Default test parameters
    SYMBOLS="${SYMBOLS:-AAPL,MSFT}"
    DURATION="${DURATION:-60}"
    VERBOSE="${VERBOSE:-}"
    
    echo "Test parameters:"
    echo "  Symbols: $SYMBOLS"
    echo "  Duration: ${DURATION}s"
    echo "  Verbose: ${VERBOSE:-false}"
    
    # Build command
    CMD="uv run python scripts/test_ibkr_market_data_integration.py --symbols $SYMBOLS --duration $DURATION"
    if [ "$VERBOSE" = "true" ]; then
        CMD="$CMD --verbose"
    fi
    
    echo -e "\nExecuting: ${CMD}"
    echo ""
    
    eval $CMD
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [setup|test|all]"
    echo ""
    echo "Commands:"
    echo "  setup  - Run environment setup and validation checks"
    echo "  test   - Run integration tests (assumes setup is complete)"
    echo "  all    - Run both setup and tests (default)"
    echo ""
    echo "Environment Variables:"
    echo "  SYMBOLS  - Comma-separated symbols to test (default: AAPL,MSFT)"
    echo "  DURATION - Test duration in seconds (default: 60)"
    echo "  VERBOSE  - Enable verbose logging (true/false, default: false)"
    echo ""
    echo "Examples:"
    echo "  $0 setup"
    echo "  SYMBOLS=AAPL DURATION=30 VERBOSE=true $0 test"
    echo "  $0 all"
}

# Main logic
case "${1:-all}" in
    "setup")
        run_setup
        ;;
    "test")
        run_tests
        ;;
    "all")
        run_setup
        echo -e "\n${YELLOW}Press Enter to continue with tests, or Ctrl+C to exit...${NC}"
        read -r
        run_tests
        ;;
    "help"|"-h"|"--help")
        show_usage
        ;;
    *)
        echo -e "${RED}Error: Unknown command '$1'${NC}"
        show_usage
        exit 1
        ;;
esac

echo -e "\n${GREEN}Integration test runner completed.${NC}"