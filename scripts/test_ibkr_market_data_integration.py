#!/usr/bin/env python3
"""
IBKR Market Data Integration Tests

Tests the market data subscription system against actual IBKR paper trading account.
This script validates real-time subscriptions, historical data fetching, and data quality.

Usage:
    python scripts/test_ibkr_market_data_integration.py [--symbols AAPL,MSFT] [--duration 60]

Requirements:
    - IBKR paper trading account running (TWS or IB Gateway)
    - Valid connection settings in config files
    - Market hours for live data (or extended hours data available)
"""

import asyncio
import sys
import argparse
from pathlib import Path
from datetime import datetime, UTC
from typing import List, Set
from decimal import Decimal

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from auto_trader.integrations.ibkr_client.client import IBKRClient
from auto_trader.integrations.ibkr_client.market_data_manager import MarketDataManager
from auto_trader.integrations.ibkr_client.historical_data_fetcher import HistoricalDataFetcher
from auto_trader.models.market_data_cache import MarketDataCache
from auto_trader.models.market_data import BarData
from config import Settings
from loguru import logger


class IntegrationTestResults:
    """Track integration test results."""
    
    def __init__(self):
        self.tests_run = 0
        self.tests_passed = 0
        self.tests_failed = 0
        self.errors = []
        self.bars_received = 0
        self.symbols_tested = set()
    
    def add_result(self, test_name: str, passed: bool, error: str = None):
        """Add test result."""
        self.tests_run += 1
        if passed:
            self.tests_passed += 1
            logger.info(f"✅ {test_name}")
        else:
            self.tests_failed += 1
            self.errors.append(f"{test_name}: {error}")
            logger.error(f"❌ {test_name}: {error}")
    
    def print_summary(self):
        """Print test summary."""
        print("\n" + "="*60)
        print("INTEGRATION TEST SUMMARY")
        print("="*60)
        print(f"Tests Run:    {self.tests_run}")
        print(f"Passed:       {self.tests_passed}")
        print(f"Failed:       {self.tests_failed}")
        print(f"Success Rate: {(self.tests_passed/self.tests_run*100):.1f}%" if self.tests_run > 0 else "0%")
        print(f"Bars Received: {self.bars_received}")
        print(f"Symbols Tested: {', '.join(sorted(self.symbols_tested))}")
        
        if self.errors:
            print(f"\nERRORS:")
            for error in self.errors:
                print(f"  - {error}")


class IBKRMarketDataIntegrationTests:
    """Integration tests for IBKR market data system."""
    
    def __init__(self, symbols: List[str], test_duration: int = 60):
        """Initialize integration tests.
        
        Args:
            symbols: List of symbols to test
            test_duration: How long to run real-time tests (seconds)
        """
        self.symbols = symbols
        self.test_duration = test_duration
        self.results = IntegrationTestResults()
        
        # Components to test
        self.settings = Settings()
        self.ibkr_client = IBKRClient(self.settings)
        self.cache = MarketDataCache()
        self.market_data_manager = None
        self.historical_fetcher = None
        
        # Track received data
        self.received_bars = []
        self.subscription_errors = []
    
    def bar_callback(self, bar: BarData):
        """Callback for received bars."""
        self.received_bars.append(bar)
        self.results.bars_received += 1
        self.results.symbols_tested.add(bar.symbol)
        
        logger.debug(
            f"Received bar: {bar.symbol} {bar.bar_size} "
            f"close={bar.close_price} volume={bar.volume}"
        )
    
    async def setup(self) -> bool:
        """Setup IBKR connection and components."""
        try:
            # Test IBKR connection
            logger.info("Connecting to IBKR...")
            await self.ibkr_client.connect()
            
            if not self.ibkr_client.is_connected():
                raise Exception("Failed to connect to IBKR")
            
            # Initialize components
            self.market_data_manager = MarketDataManager(
                self.ibkr_client._ib,
                self.cache
            )
            
            # Add bar callback to distributor
            self.market_data_manager.add_subscriber("integration_test", self.bar_callback)
            
            self.historical_fetcher = HistoricalDataFetcher(
                self.ibkr_client._ib
            )
            
            self.results.add_result("IBKR Connection", True)
            return True
            
        except Exception as e:
            self.results.add_result("IBKR Connection", False, str(e))
            return False
    
    async def test_connection_status(self):
        """Test IBKR connection status and account info."""
        try:
            status = self.ibkr_client.get_connection_status()
            
            # Validate connection details
            assert status.state.value == "connected", f"Not connected: {status.state}"
            assert status.account_type is not None, "Account type not detected"
            
            logger.info(f"Connected to {status.account_type} account")
            self.results.add_result("Connection Status", True)
            
        except Exception as e:
            self.results.add_result("Connection Status", False, str(e))
    
    async def test_historical_data_fetching(self):
        """Test historical data fetching for all symbols."""
        try:
            for symbol in self.symbols:
                logger.info(f"Fetching historical data for {symbol}...")
                
                # Test different timeframes
                timeframes = ["1min", "5min", "15min"]
                for timeframe in timeframes:
                    bars = await self.historical_fetcher.fetch_historical_bars(
                        symbol, timeframe, "1 D"
                    )
                    
                    assert len(bars) > 0, f"No historical bars for {symbol} {timeframe}"
                    
                    # Validate data quality
                    for bar in bars[:5]:  # Check first 5 bars
                        assert bar.symbol == symbol
                        assert bar.bar_size == timeframe
                        assert bar.open_price > 0
                        assert bar.close_price > 0
                        assert bar.high_price >= bar.low_price
                        assert bar.volume >= 0
                    
                    logger.info(f"✓ {symbol} {timeframe}: {len(bars)} bars")
            
            self.results.add_result("Historical Data Fetching", True)
            
        except Exception as e:
            self.results.add_result("Historical Data Fetching", False, str(e))
    
    async def test_startup_context(self):
        """Test startup context fetching."""
        try:
            logger.info("Testing startup context fetching...")
            
            context = await self.historical_fetcher.fetch_startup_context(
                self.symbols, "5min", "1 D"
            )
            
            # Validate context data
            for symbol in self.symbols:
                assert symbol in context, f"Missing context for {symbol}"
                bars = context[symbol]
                assert len(bars) > 0, f"No context bars for {symbol}"
                
                # Test gap detection
                if len(bars) > 1:
                    gaps = self.historical_fetcher.detect_data_gaps(bars, "5min")
                    logger.info(f"Detected {len(gaps)} gaps in {symbol} data")
            
            self.results.add_result("Startup Context", True)
            
        except Exception as e:
            self.results.add_result("Startup Context", False, str(e))
    
    async def test_real_time_subscriptions(self):
        """Test real-time market data subscriptions."""
        try:
            logger.info(f"Testing real-time subscriptions for {len(self.symbols)} symbols...")
            
            # Subscribe to multiple timeframes
            bar_sizes = ["5min"]  # Start with 5min for integration testing
            
            results = await self.market_data_manager.subscribe_symbols(
                self.symbols, bar_sizes
            )
            
            # Verify all subscriptions succeeded
            expected_subs = len(self.symbols) * len(bar_sizes)
            successful_subs = sum(1 for success in results.values() if success)
            
            assert successful_subs == expected_subs, \
                f"Only {successful_subs}/{expected_subs} subscriptions succeeded"
            
            logger.info(f"✓ All {expected_subs} subscriptions active")
            
            # Wait for data and verify reception
            logger.info(f"Waiting {self.test_duration}s for market data...")
            initial_bar_count = len(self.received_bars)
            
            await asyncio.sleep(self.test_duration)
            
            final_bar_count = len(self.received_bars)
            bars_received = final_bar_count - initial_bar_count
            
            # During market hours, we should receive some data
            # Outside market hours, this might be 0 (which is acceptable)
            logger.info(f"Received {bars_received} bars during test period")
            
            # Verify subscription status
            active_subs = self.market_data_manager.get_active_subscriptions()
            assert len(active_subs) == len(self.symbols), \
                f"Expected {len(self.symbols)} active subscriptions, got {len(active_subs)}"
            
            self.results.add_result("Real-time Subscriptions", True)
            
        except Exception as e:
            self.results.add_result("Real-time Subscriptions", False, str(e))
    
    async def test_dynamic_subscription_management(self):
        """Test adding and removing subscriptions dynamically."""
        try:
            logger.info("Testing dynamic subscription management...")
            
            # Test adding new symbols
            new_symbols = ["GOOGL"] if "GOOGL" not in self.symbols else ["TSLA"]
            
            results = await self.market_data_manager.subscribe_symbols(
                new_symbols, ["5min"]
            )
            
            assert all(results.values()), "Failed to add new subscriptions"
            
            # Test removing symbols
            await self.market_data_manager.unsubscribe_symbols(new_symbols)
            
            # Verify subscriptions were removed
            active_subs = self.market_data_manager.get_active_subscriptions()
            for symbol in new_symbols:
                assert symbol not in active_subs, f"{symbol} still in active subscriptions"
            
            self.results.add_result("Dynamic Subscription Management", True)
            
        except Exception as e:
            self.results.add_result("Dynamic Subscription Management", False, str(e))
    
    async def test_data_quality_validation(self):
        """Test data quality validation features."""
        try:
            logger.info("Testing data quality validation...")
            
            if not self.received_bars:
                # If no real-time data, create test data
                logger.warning("No real-time bars received, using test data")
                test_bar = BarData(
                    symbol="TEST",
                    timestamp=datetime.now(UTC),
                    open_price=Decimal("100.00"),
                    high_price=Decimal("101.00"),
                    low_price=Decimal("99.00"),
                    close_price=Decimal("100.50"),
                    volume=1000,
                    bar_size="5min"
                )
                await self.cache.update_bar(test_bar)
                self.received_bars = [test_bar]
            
            # Test stale data detection
            for bar in self.received_bars[:3]:  # Test first few bars
                is_stale = self.cache.is_data_stale(bar.symbol, bar.bar_size)
                logger.info(f"Stale check for {bar.symbol}: {is_stale}")
                
                # Get latest bar
                latest = self.cache.get_latest_bar(
                    bar.symbol, bar.bar_size, check_stale=False
                )
                assert latest is not None, f"No cached bar for {bar.symbol}"
            
            # Test memory usage tracking
            memory_usage = self.cache.get_memory_usage()
            assert memory_usage["total_bars"] >= 0
            assert "estimated_memory_mb" in memory_usage
            
            self.results.add_result("Data Quality Validation", True)
            
        except Exception as e:
            self.results.add_result("Data Quality Validation", False, str(e))
    
    async def test_cache_management(self):
        """Test cache management and cleanup."""
        try:
            logger.info("Testing cache management...")
            
            # Get initial cache stats
            initial_stats = self.cache.get_memory_usage()
            logger.info(f"Initial cache: {initial_stats['total_bars']} bars")
            
            # Test cleanup (won't remove recent data, but tests the mechanism)
            removed = await self.cache.cleanup_old_data()
            logger.info(f"Cache cleanup removed {removed} old bars")
            
            # Test cache summary
            summary = self.cache.get_cache_summary()
            assert "symbols" in summary
            assert "total_bars" in summary
            
            # Test subscription tracking
            subscriptions = self.cache.get_active_subscriptions()
            logger.info(f"Active subscriptions: {len(subscriptions)}")
            
            self.results.add_result("Cache Management", True)
            
        except Exception as e:
            self.results.add_result("Cache Management", False, str(e))
    
    async def test_error_handling(self):
        """Test error handling scenarios."""
        try:
            logger.info("Testing error handling...")
            
            # Test invalid symbol subscription
            invalid_results = await self.market_data_manager.subscribe_symbols(
                ["INVALID_SYMBOL_12345"], ["5min"]
            )
            
            # Should handle gracefully (may succeed but no data, or fail cleanly)
            logger.info(f"Invalid symbol subscription: {invalid_results}")
            
            # Test subscription stats for errors
            stats = self.market_data_manager.get_stats()
            logger.info(f"Manager stats: {stats}")
            
            self.results.add_result("Error Handling", True)
            
        except Exception as e:
            self.results.add_result("Error Handling", False, str(e))
    
    async def cleanup(self):
        """Cleanup resources."""
        try:
            if self.market_data_manager:
                await self.market_data_manager.cleanup()
            
            if self.ibkr_client.is_connected():
                await self.ibkr_client.disconnect()
            
            logger.info("Cleanup completed")
            
        except Exception as e:
            logger.error(f"Cleanup error: {e}")
    
    async def run_all_tests(self):
        """Run all integration tests."""
        logger.info("Starting IBKR Market Data Integration Tests")
        logger.info(f"Testing symbols: {', '.join(self.symbols)}")
        logger.info(f"Test duration: {self.test_duration}s")
        
        try:
            # Setup
            if not await self.setup():
                logger.error("Setup failed, aborting tests")
                return
            
            # Run tests in sequence
            await self.test_connection_status()
            await self.test_historical_data_fetching()
            await self.test_startup_context()
            await self.test_real_time_subscriptions()
            await self.test_dynamic_subscription_management()
            await self.test_data_quality_validation()
            await self.test_cache_management()
            await self.test_error_handling()
            
        except KeyboardInterrupt:
            logger.warning("Tests interrupted by user")
        except Exception as e:
            logger.error(f"Unexpected error during tests: {e}")
        finally:
            await self.cleanup()
            self.results.print_summary()


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="IBKR Market Data Integration Tests"
    )
    parser.add_argument(
        "--symbols",
        default="AAPL,MSFT",
        help="Comma-separated symbols to test (default: AAPL,MSFT)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duration to collect real-time data in seconds (default: 60)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    # Configure logging
    log_level = "DEBUG" if args.verbose else "INFO"
    logger.remove()
    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}"
    )
    
    # Parse symbols
    symbols = [s.strip() for s in args.symbols.split(",")]
    
    # Run tests
    tests = IBKRMarketDataIntegrationTests(symbols, args.duration)
    await tests.run_all_tests()


if __name__ == "__main__":
    asyncio.run(main())