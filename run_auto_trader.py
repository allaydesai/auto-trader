#!/usr/bin/env python3
"""
Auto-Trader Production Startup Script

This script provides a unified entry point for running the Auto-Trader system
in production mode with proper error handling and graceful shutdown.
"""

import asyncio
import sys
import signal
import argparse
from pathlib import Path
from typing import Optional
from decimal import Decimal

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import Settings, ConfigLoader
from auto_trader.logging_config import LoggerConfig, get_logger


def setup_argument_parser() -> argparse.ArgumentParser:
    """Setup command line argument parser."""
    parser = argparse.ArgumentParser(
        description="Auto-Trader: Automated Trading System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run in simulation mode (default)
  python run_auto_trader.py
  
  # Run in live trading mode
  python run_auto_trader.py --live
  
  # Run with custom config file
  python run_auto_trader.py --config /path/to/config.yaml
  
  # Run with debug logging
  python run_auto_trader.py --debug
  
  # Check configuration without starting
  python run_auto_trader.py --check-config
""",
    )

    parser.add_argument(
        "--live",
        action="store_true",
        help="Run in live trading mode (default: simulation)",
    )

    parser.add_argument(
        "--config", type=Path, help="Path to configuration file (default: config.yaml)"
    )

    parser.add_argument("--debug", action="store_true", help="Enable debug logging")

    parser.add_argument(
        "--check-config", action="store_true", help="Validate configuration and exit"
    )

    parser.add_argument(
        "--no-discord", action="store_true", help="Disable Discord notifications"
    )

    parser.add_argument(
        "--no-file-watch",
        action="store_true",
        help="Disable file watching for trade plan updates",
    )

    parser.add_argument("--version", action="version", version="Auto-Trader v0.1.0")

    return parser


async def check_configuration(settings: Settings) -> bool:
    """
    Check and validate configuration.

    Args:
        settings: Application settings

    Returns:
        True if configuration is valid, False otherwise
    """
    logger = get_logger("startup", "system")

    try:
        config_loader = ConfigLoader(settings)
        issues = config_loader.validate_configuration()

        if issues:
            logger.error("Configuration validation failed:")
            for issue in issues:
                logger.error(f"  - {issue}")
            return False

        system_config = config_loader.system_config
        user_preferences = config_loader.user_preferences

        logger.info("Configuration validation successful:")
        logger.info(f"  - Simulation Mode: {system_config.trading.simulation_mode}")
        account_val = (
            user_preferences.account_value
            or user_preferences.default_account_value
            or Decimal("10000")
        )
        logger.info(f"  - Account Value: ${account_val:,.2f}")
        logger.info(f"  - Default Risk: {user_preferences.default_risk_category}")
        logger.info(f"  - Plans Directory: {settings.plans_directory}")
        logger.info(f"  - State Directory: {settings.state_directory}")

        # Check directories exist
        for dir_path in [
            settings.plans_directory,
            settings.state_directory,
            settings.logs_dir,
        ]:
            dir_path = Path(dir_path)
            if not dir_path.exists():
                logger.info(f"Creating directory: {dir_path}")
                dir_path.mkdir(parents=True, exist_ok=True)

        # Check IBKR connectivity settings
        if not system_config.trading.simulation_mode:
            logger.info("IBKR Connection Settings:")
            logger.info(f"  - Host: {settings.ibkr_host}")
            logger.info(f"  - Port: {settings.ibkr_port}")
            logger.info(f"  - Client ID: {settings.ibkr_client_id}")

            if not settings.ibkr_host or settings.ibkr_port == 0:
                logger.error("IBKR connection settings missing for live trading!")
                return False

        # Check Discord webhook if enabled
        if settings.discord_webhook_url and not settings.discord_webhook_url.startswith(
            "https://discord.com/api/webhooks/"
        ):
            logger.warning("Discord webhook URL appears invalid")

        return True

    except Exception as e:
        logger.error(f"Configuration check failed: {e}")
        return False


async def run_auto_trader(args: argparse.Namespace) -> int:
    """
    Main entry point for running the Auto-Trader system.

    Args:
        args: Command line arguments

    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    # Load settings
    settings = Settings()

    # Override settings from command line
    if args.config:
        settings.config_file = str(args.config)
    if args.debug:
        settings.debug = True
    if args.no_discord:
        settings.discord_webhook_url = ""

    # Setup logging
    log_config = LoggerConfig(
        logs_dir=settings.logs_dir,
        log_level="DEBUG" if settings.debug else "INFO",
    )
    log_config.configure_logging()

    logger = get_logger("startup", "system")

    logger.info("=" * 60)
    logger.info("Auto-Trader System Starting")
    logger.info("=" * 60)

    # Check configuration
    if not await check_configuration(settings):
        logger.error("Configuration check failed. Please fix the issues and try again.")
        return 1

    if args.check_config:
        logger.info("Configuration check completed successfully.")
        return 0

    # Import main application after configuration check
    from src.main import AutoTraderApp

    app: Optional[AutoTraderApp] = None

    try:
        # Override simulation mode if live trading requested
        if args.live:
            logger.warning("=" * 60)
            logger.warning("LIVE TRADING MODE ENABLED")
            logger.warning("Real money trades will be executed!")
            logger.warning("=" * 60)

            # Get user confirmation
            response = input("Type 'YES' to confirm live trading mode: ")
            if response != "YES":
                logger.info("Live trading cancelled by user")
                return 0

            # Update config to disable simulation
            config_loader = ConfigLoader(settings)
            config_loader.system_config.trading.simulation_mode = False

        # Create application instance
        app = AutoTraderApp(settings)

        # Disable components if requested
        if args.no_file_watch:
            logger.info("File watching disabled by command line flag")
            app._enable_file_watch = False

        # Setup signal handlers for graceful shutdown
        def signal_handler(sig, frame):
            logger.info(f"Received signal {sig}, initiating shutdown...")
            if app:
                asyncio.create_task(app.shutdown())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Start the application
        logger.info("Starting Auto-Trader application...")
        await app.start()

        logger.info("Auto-Trader shutdown completed successfully")
        return 0

    except KeyboardInterrupt:
        logger.info("Shutdown requested by user (Ctrl+C)")
        if app:
            await app.shutdown()
        return 0

    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
        if app:
            try:
                await app.shutdown()
            except Exception:
                pass
        return 1


def main():
    """Main entry point."""
    # Parse command line arguments
    parser = setup_argument_parser()
    args = parser.parse_args()

    # Run the application
    try:
        exit_code = asyncio.run(run_auto_trader(args))
        sys.exit(exit_code)
    except Exception as e:
        print(f"FATAL: Failed to start Auto-Trader: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
