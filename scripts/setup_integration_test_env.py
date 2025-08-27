#!/usr/bin/env python3
"""
Setup Integration Test Environment

Helps configure the environment for IBKR market data integration testing.
Validates configuration, checks TWS/IB Gateway connection, and provides guidance.

Usage:
    python scripts/setup_integration_test_env.py
"""

import sys
import asyncio
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from auto_trader.integrations.ibkr_client.client import IBKRClient
from config import Settings, ConfigLoader
from loguru import logger


class IntegrationTestSetup:
    """Setup and validation for integration testing."""
    
    def __init__(self):
        self.settings = Settings()
        self.config_loader = ConfigLoader(self.settings)
        self.checks_passed = 0
        self.checks_total = 0
    
    def check(self, name: str, condition: bool, message: str = "", fix_hint: str = ""):
        """Run a check and report results."""
        self.checks_total += 1
        
        if condition:
            self.checks_passed += 1
            logger.info(f"✅ {name}")
            if message:
                logger.info(f"   {message}")
        else:
            logger.error(f"❌ {name}")
            if message:
                logger.error(f"   {message}")
            if fix_hint:
                logger.info(f"   💡 Fix: {fix_hint}")
    
    def check_configuration(self):
        """Check configuration files and settings."""
        logger.info("Checking configuration...")
        
        # Check if config files exist
        config_files = [
            Path("config.yaml"),
            Path(".env"),
            Path("user_config.yaml")
        ]
        
        for config_file in config_files:
            exists = config_file.exists()
            self.check(
                f"Config file: {config_file.name}",
                exists,
                f"Found at: {config_file.absolute()}" if exists else "File not found",
                f"Create {config_file.name} from {config_file.name}.example"
            )
        
        # Check IBKR settings (environment variables override config.yaml)
        try:
            # Use the actual settings that will be used by IBKRClient
            host = self.settings.ibkr_host
            port = self.settings.ibkr_port  
            client_id = self.settings.ibkr_client_id
            
            self.check(
                "IBKR Host configured",
                bool(host),
                f"Host: {host}",
                "Set IBKR_HOST in .env or config.yaml"
            )
            
            self.check(
                "IBKR Port configured", 
                port > 0,
                f"Port: {port}",
                "Set IBKR_PORT in .env or config.yaml"
            )
            
            self.check(
                "IBKR Client ID configured",
                client_id > 0,
                f"Client ID: {client_id}",
                "Set IBKR_CLIENT_ID in .env or config.yaml"
            )
            
            # Check for paper trading (safer for integration tests)
            paper_trading_ports = [7497, 4002]  # Common paper trading ports
            is_paper = port in paper_trading_ports
            
            self.check(
                "Paper Trading Port",
                is_paper,
                f"Using {'paper' if is_paper else 'live'} trading port {port}",
                "Use port 7497 (TWS paper) or 4002 (Gateway paper) for safe testing"
            )
            
        except Exception as e:
            self.check("IBKR Configuration", False, str(e), "Check config file syntax")
    
    async def check_ibkr_connection(self):
        """Test IBKR connection."""
        logger.info("Testing IBKR connection...")
        
        try:
            client = IBKRClient(self.settings)
            
            # Attempt connection with timeout
            logger.info("Attempting to connect to IBKR...")
            await asyncio.wait_for(client.connect(), timeout=10.0)
            
            if client.is_connected():
                status = client.get_connection_status()
                
                self.check(
                    "IBKR Connection",
                    True,
                    f"Connected to {status.account_type or 'unknown'} account",
                    ""
                )
                
                self.check(
                    "Account Type Detection",
                    status.account_type is not None,
                    f"Account type: {status.account_type}",
                    ""
                )
                
                # Check if it's paper account
                is_paper = status.is_paper_account
                self.check(
                    "Paper Account Verification",
                    is_paper,
                    "Using paper trading account" if is_paper else "Using LIVE account",
                    "Switch to paper trading for safe integration testing"
                )
                
                await client.disconnect()
                
            else:
                self.check(
                    "IBKR Connection",
                    False,
                    "Failed to establish connection",
                    "Ensure TWS/IB Gateway is running and configured correctly"
                )
                
        except asyncio.TimeoutError:
            self.check(
                "IBKR Connection",
                False,
                "Connection timeout after 10 seconds",
                "Check if TWS/IB Gateway is running on correct port"
            )
        except Exception as e:
            self.check(
                "IBKR Connection",
                False,
                f"Connection error: {str(e)}",
                "Verify TWS/IB Gateway settings and network connectivity"
            )
    
    def check_dependencies(self):
        """Check required dependencies."""
        logger.info("Checking dependencies...")
        
        required_packages = [
            ("ib_async", "ib-async"),
            ("loguru", "loguru"),
            ("pydantic", "pydantic"),
            ("pandas", "pandas")
        ]
        
        for package, pip_name in required_packages:
            try:
                __import__(package)
                self.check(f"Package: {pip_name}", True, "Installed")
            except ImportError:
                self.check(
                    f"Package: {pip_name}",
                    False,
                    "Not installed",
                    f"Run: uv add {pip_name}"
                )
    
    def check_market_hours(self):
        """Check if currently in market hours (for better testing)."""
        now = datetime.now()
        
        # Simple US market hours check (9:30 AM - 4:00 PM ET, Mon-Fri)
        is_weekday = now.weekday() < 5
        hour = now.hour
        
        # Rough approximation - doesn't handle timezone properly
        likely_market_hours = is_weekday and 9 <= hour <= 16
        
        self.check(
            "Market Hours (approximate)",
            True,  # Always pass since this is informational
            f"{'Likely' if likely_market_hours else 'Likely not'} in market hours",
            "Real-time data testing works best during market hours"
        )
    
    def provide_usage_guidance(self):
        """Provide guidance on running integration tests."""
        logger.info("\n" + "="*60)
        logger.info("INTEGRATION TEST USAGE GUIDANCE")
        logger.info("="*60)
        
        if self.checks_passed == self.checks_total:
            logger.info("✅ All checks passed! Ready for integration testing.")
            logger.info("")
            logger.info("Run integration tests with:")
            logger.info("  python scripts/test_ibkr_market_data_integration.py")
            logger.info("")
            logger.info("Options:")
            logger.info("  --symbols AAPL,MSFT,GOOGL  # Test specific symbols")
            logger.info("  --duration 120              # Run for 2 minutes")
            logger.info("  --verbose                   # Enable debug logging")
            logger.info("")
            logger.info("Example:")
            logger.info("  python scripts/test_ibkr_market_data_integration.py --symbols AAPL --duration 30 --verbose")
        else:
            logger.warning(f"⚠️  {self.checks_total - self.checks_passed} checks failed!")
            logger.info("Fix the issues above before running integration tests.")
        
        logger.info("\nIMPORTANT NOTES:")
        logger.info("• Always use paper trading for integration testing")
        logger.info("• Tests work best during market hours for real-time data")
        logger.info("• Historical data tests work anytime")
        logger.info("• Ensure TWS/IB Gateway is running before testing")
    
    async def run_all_checks(self):
        """Run all setup checks."""
        logger.info("IBKR Market Data Integration Test Setup")
        logger.info("="*60)
        
        self.check_dependencies()
        self.check_configuration()
        await self.check_ibkr_connection()
        self.check_market_hours()
        
        success_rate = (self.checks_passed / self.checks_total * 100) if self.checks_total > 0 else 0
        
        logger.info(f"\nChecks completed: {self.checks_passed}/{self.checks_total} passed ({success_rate:.1f}%)")
        
        self.provide_usage_guidance()


async def main():
    """Main entry point."""
    # Configure logging
    logger.remove()
    logger.add(
        sys.stdout,
        level="INFO",
        format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}"
    )
    
    setup = IntegrationTestSetup()
    await setup.run_all_checks()


if __name__ == "__main__":
    asyncio.run(main())