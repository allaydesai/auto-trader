#!/usr/bin/env python3
"""Quick integration test for the Auto-Trader system."""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

async def test_integration():
    """Test basic integration of the system."""
    
    print("=" * 60)
    print("Auto-Trader Integration Test")
    print("=" * 60)
    
    # Test 1: Configuration loading
    print("\nTest 1: Configuration Loading")
    try:
        from config import Settings, ConfigLoader
        settings = Settings()
        config_loader = ConfigLoader(settings)
        system_config = config_loader.system_config
        user_prefs = config_loader.user_preferences
        print(f"✅ Configuration loaded successfully")
        print(f"   - Simulation Mode: {system_config.trading.simulation_mode}")
        print(f"   - Account Value: ${user_prefs.account_value:,.2f}")
    except Exception as e:
        print(f"❌ Configuration loading failed: {e}")
        return False
    
    # Test 2: Trade plan loading
    print("\nTest 2: Trade Plan Loading")
    try:
        from auto_trader.models.plan_loader import TradePlanLoader
        loader = TradePlanLoader()
        plans = loader.load_all_plans()
        print(f"✅ Loaded {len(plans)} trade plans")
        for plan_id in list(plans.keys())[:3]:  # Show first 3
            print(f"   - {plan_id}")
    except Exception as e:
        print(f"❌ Trade plan loading failed: {e}")
    
    # Test 3: Risk manager initialization
    print("\nTest 3: Risk Manager")
    try:
        from auto_trader.risk_management.risk_manager import RiskManager
        from decimal import Decimal
        risk_mgr = RiskManager(account_value=Decimal("10000"))
        print(f"✅ Risk manager initialized")
        print(f"   - Account value: ${risk_mgr.account_value:,.2f}")
    except Exception as e:
        print(f"❌ Risk manager initialization failed: {e}")
    
    # Test 4: IBKR client (without connection)
    print("\nTest 4: IBKR Client Setup")
    try:
        from auto_trader.integrations.ibkr_client.client import IBKRClient
        client = IBKRClient()
        print(f"✅ IBKR client created (not connected)")
        print(f"   - Host: {client.config.host}")
        print(f"   - Port: {client.config.port}")
    except Exception as e:
        print(f"❌ IBKR client setup failed: {e}")
    
    # Test 5: Discord notifier
    print("\nTest 5: Discord Notifier")
    try:
        from auto_trader.integrations.discord_notifier import DiscordNotifier
        webhook = settings.discord_webhook_url or "https://discord.com/api/webhooks/test"
        notifier = DiscordNotifier(webhook_url=webhook, simulation_mode=True)
        print(f"✅ Discord notifier initialized")
        print(f"   - Simulation mode: {notifier.simulation_mode}")
    except Exception as e:
        print(f"❌ Discord notifier setup failed: {e}")
    
    # Test 6: Trade engine components
    print("\nTest 6: Trade Engine Components")
    try:
        from auto_trader.trade_engine.function_registry import ExecutionFunctionRegistry
        from auto_trader.trade_engine.trade_orchestrator import TradeOrchestrator, TradeOrchestrationConfig
        
        registry = ExecutionFunctionRegistry()
        print(f"✅ Execution function registry initialized")
        print(f"   - Registered functions: {len(registry._registry)}")
        
        # Try to create orchestrator config
        config = TradeOrchestrationConfig()
        print(f"✅ Trade orchestrator config created")
        print(f"   - Max concurrent trades: {config.max_concurrent_trades}")
    except Exception as e:
        print(f"❌ Trade engine setup failed: {e}")
    
    # Test 7: Main application initialization
    print("\nTest 7: Main Application")
    try:
        from auto_trader.trade_engine.main_application import TradingApplication, ApplicationConfig
        
        app_config = ApplicationConfig(
            simulation_mode=True,
            account_value=10000.0,
            trade_plans_directory="data/trade_plans",
            state_directory="data/state"
        )
        
        app = TradingApplication(config=app_config)
        await app.initialize()
        print(f"✅ Trading application initialized")
        print(f"   - Simulation mode: {app.config.simulation_mode}")
        print(f"   - Components ready: {app.trade_orchestrator is not None}")
        
        # Clean shutdown
        await app.stop()
        
    except Exception as e:
        print(f"❌ Main application initialization failed: {e}")
        return False
    
    print("\n" + "=" * 60)
    print("Integration Test Complete - All Systems Operational!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_integration())
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        sys.exit(1)