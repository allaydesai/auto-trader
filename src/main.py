"""Auto-Trader main entry point with proper error handling and initialization."""

import asyncio
import signal
import sys
from typing import Optional

from pathlib import Path
from decimal import Decimal

from config import Settings, ConfigLoader
from auto_trader.logging_config import LoggerConfig, get_logger, set_service_context
from auto_trader.trade_engine.main_application import (
    TradingApplication,
    ApplicationConfig,
)
from auto_trader.integrations.discord_notifier import DiscordNotifier
from auto_trader.utils.file_watcher import FileWatcher


class AutoTraderApp:
    """Main application class with dependency injection and lifecycle management."""

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize application with configuration."""
        self.settings = settings or Settings()
        self.config_loader = ConfigLoader(self.settings)
        self.logger = get_logger("main", "system")
        self._shutdown_event = asyncio.Event()
        self._running = False

        # Core components
        self.trading_app: Optional[TradingApplication] = None
        self.discord_notifier: Optional[DiscordNotifier] = None
        self.file_watcher: Optional[FileWatcher] = None
        self._file_watch_task: Optional[asyncio.Task] = None

    async def initialize(self) -> None:
        """Initialize all application components."""
        set_service_context("main", "initialize")

        try:
            # Configure logging first
            log_config = LoggerConfig(
                logs_dir=self.settings.logs_dir,
                log_level="DEBUG" if self.settings.debug else "INFO",
            )
            log_config.configure_logging()

            self.logger.info("Auto-Trader application starting", version="0.1.0")

            # Validate configuration
            config_issues = self.config_loader.validate_configuration()
            if config_issues:
                for issue in config_issues:
                    self.logger.error("Configuration issue", issue=issue)
                raise ValueError(f"Configuration validation failed: {config_issues}")

            # Load configurations
            system_config = self.config_loader.system_config
            user_preferences = self.config_loader.user_preferences

            self.logger.info(
                "Configuration loaded successfully",
                simulation_mode=system_config.trading.simulation_mode,
                risk_category=user_preferences.default_risk_category,
                log_level=system_config.logging.level,
            )

            # Initialize trading application
            await self._initialize_trade_engine(system_config, user_preferences)

            # Initialize Discord notifier if webhook URL is configured
            await self._initialize_discord_notifier(system_config)

            # Initialize file watcher for hot-reload
            await self._initialize_file_watcher()

            self.logger.info("Application initialization completed")

        except Exception as e:
            self.logger.critical("Application initialization failed", error=str(e))
            raise

    async def start(self) -> None:
        """Start the application and all services."""
        set_service_context("main", "start")

        try:
            await self.initialize()

            # Setup signal handlers for graceful shutdown
            self._setup_signal_handlers()

            self._running = True
            self.logger.info("Auto-Trader application started successfully")

            # Main application loop
            await self._run_main_loop()

        except Exception as e:
            self.logger.critical("Application startup failed", error=str(e))
            raise

    async def shutdown(self) -> None:
        """Graceful shutdown of all services."""
        set_service_context("main", "shutdown")

        # Mark as not running and set shutdown event regardless of current state
        was_running = self._running
        self._running = False
        self._shutdown_event.set()

        if was_running:
            self.logger.info("Initiating graceful shutdown")

            try:
                # Shutdown modules in reverse order
                await self._shutdown_file_watcher()
                await self._shutdown_discord_notifier()
                await self._shutdown_trade_engine()

                self.logger.info("Application shutdown completed")

            except Exception as e:
                self.logger.error("Error during shutdown", error=str(e))
                raise

    async def _run_main_loop(self) -> None:
        """Main application event loop."""
        set_service_context("main", "run_main_loop")

        try:
            while self._running:
                # Check if trading app is still running
                if self.trading_app and self.trading_app.is_running:
                    # The trading app runs its own event loop
                    # We just monitor for shutdown signal
                    pass

                # Wait for shutdown signal or check interval
                try:
                    await asyncio.wait_for(self._shutdown_event.wait(), timeout=1.0)
                    break
                except asyncio.TimeoutError:
                    continue

        except Exception as e:
            self.logger.error("Error in main loop", error=str(e))
            raise

    def _setup_signal_handlers(self) -> None:
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(signum: int, frame) -> None:
            self.logger.info(f"Received signal {signum}, initiating shutdown")
            asyncio.create_task(self.shutdown())

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

    async def _initialize_trade_engine(self, system_config, user_preferences) -> None:
        """Initialize the trade engine with configuration."""
        set_service_context("main", "initialize_trade_engine")

        try:
            # Build application configuration from settings
            # Simulation mode: environment variable overrides config.yaml
            simulation_mode = (
                self.settings.simulation_mode
                if self.settings.simulation_mode is not None
                else system_config.trading.simulation_mode
            )

            # Get account value - prefer new field, fallback to legacy field
            account_val = (
                user_preferences.account_value
                or user_preferences.default_account_value
                or Decimal("10000")
            )

            app_config = ApplicationConfig(
                trade_plans_directory=str(self.settings.plans_directory),
                state_directory=str(self.settings.state_directory),
                simulation_mode=simulation_mode,
                max_concurrent_trades=system_config.risk.max_concurrent_trades,
                enable_risk_validation=True,
                enable_position_tracking=True,
                account_value=float(account_val),
                max_portfolio_risk_percent=float(
                    system_config.risk.max_portfolio_risk_percent
                ),
                signal_timeout_seconds=30,
                state_save_interval_seconds=60,
                ibkr_host=self.settings.ibkr_host,
                ibkr_port=self.settings.ibkr_port,
                ibkr_client_id=self.settings.ibkr_client_id,
            )

            # Create and initialize trading application
            self.trading_app = TradingApplication(config=app_config)
            await self.trading_app.initialize()

            # Start the trading application
            await self.trading_app.start()

            self.logger.info(
                "Trade engine initialized",
                simulation_mode=app_config.simulation_mode,
                account_value=app_config.account_value,
            )

        except Exception as e:
            self.logger.error(f"Failed to initialize trade engine: {e}")
            raise

    async def _shutdown_trade_engine(self) -> None:
        """Shutdown the trade engine gracefully."""
        set_service_context("main", "shutdown_trade_engine")

        if self.trading_app:
            try:
                await self.trading_app.stop()
                self.logger.info("Trade engine shutdown completed")
            except Exception as e:
                self.logger.error(f"Error shutting down trade engine: {e}")

    async def _initialize_discord_notifier(self, system_config) -> None:
        """Initialize Discord webhook notifier."""
        set_service_context("main", "initialize_discord_notifier")

        try:
            webhook_url = self.settings.discord_webhook_url
            if webhook_url and webhook_url != "":
                # Use the same simulation_mode that was determined for trade engine
                simulation_mode = (
                    self.settings.simulation_mode
                    if self.settings.simulation_mode is not None
                    else system_config.trading.simulation_mode
                )
                self.discord_notifier = DiscordNotifier(
                    webhook_url=webhook_url, simulation_mode=simulation_mode
                )

                # Connect notifier to trade engine's order event system
                if self.trading_app and self.trading_app.order_execution_manager:
                    # The order execution manager will handle Discord notifications
                    # through its event system
                    pass

                self.logger.info("Discord notifier initialized")
            else:
                self.logger.warning(
                    "Discord webhook URL not configured, notifications disabled"
                )

        except Exception as e:
            self.logger.error(f"Failed to initialize Discord notifier: {e}")
            # Non-critical, continue without notifications

    async def _shutdown_discord_notifier(self) -> None:
        """Shutdown Discord notifier."""
        set_service_context("main", "shutdown_discord_notifier")

        if self.discord_notifier:
            try:
                # Close HTTP client
                if hasattr(self.discord_notifier, "_client"):
                    await self.discord_notifier._client.aclose()
                self.logger.info("Discord notifier shutdown completed")
            except Exception as e:
                self.logger.error(f"Error shutting down Discord notifier: {e}")

    async def _initialize_file_watcher(self) -> None:
        """Initialize file watcher for trade plan hot-reload."""
        set_service_context("main", "initialize_file_watcher")

        try:
            # Create file watcher for trade plans directory
            plans_dir = Path(self.settings.plans_directory)
            if not plans_dir.exists():
                plans_dir.mkdir(parents=True, exist_ok=True)
                self.logger.info(f"Created trade plans directory: {plans_dir}")

            # Define callback for file changes
            def on_file_change(file_path: Path, event_type):
                """Handle file change events."""
                try:
                    self.logger.info(f"Trade plan file {event_type.value}: {file_path}")

                    # Reload plans in the trade engine if it's running
                    if self.trading_app and self.trading_app.trade_orchestrator:
                        # Schedule plan reload in the event loop
                        asyncio.create_task(self._reload_trade_plans(file_path))

                except Exception as e:
                    self.logger.error(f"Error handling file change: {e}")

            # Initialize file watcher
            self.file_watcher = FileWatcher(
                watch_directory=plans_dir,
                validation_callback=on_file_change,
                debounce_delay=1.0,  # Wait 1 second after changes before reloading
            )

            # Start file watcher in background
            self._file_watch_task = asyncio.create_task(self._run_file_watcher())

            self.logger.info(f"File watcher initialized for: {plans_dir}")

        except Exception as e:
            self.logger.error(f"Failed to initialize file watcher: {e}")
            # Non-critical, continue without hot-reload

    async def _shutdown_file_watcher(self) -> None:
        """Shutdown file watcher."""
        set_service_context("main", "shutdown_file_watcher")

        if self._file_watch_task:
            try:
                self._file_watch_task.cancel()
                try:
                    await self._file_watch_task
                except asyncio.CancelledError:
                    pass

                if self.file_watcher:
                    self.file_watcher.stop()

                self.logger.info("File watcher shutdown completed")
            except Exception as e:
                self.logger.error(f"Error shutting down file watcher: {e}")

    async def _run_file_watcher(self) -> None:
        """Run file watcher in background."""
        try:
            if self.file_watcher:
                self.file_watcher.start()

                # Keep running until shutdown
                while self._running:
                    await asyncio.sleep(1.0)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"File watcher error: {e}")

    async def _reload_trade_plans(self, file_path: Path) -> None:
        """Reload trade plans after file change."""
        try:
            if self.trading_app and self.trading_app.trade_plan_loader:
                # Reload all plans
                await asyncio.to_thread(self.trading_app.trade_plan_loader.reload_plans)

                # Notify orchestrator of plan changes
                if self.trading_app.trade_orchestrator:
                    # The orchestrator will pick up new plans on next cycle
                    self.logger.info(
                        f"Trade plans reloaded after change to: {file_path}"
                    )

        except Exception as e:
            self.logger.error(f"Failed to reload trade plans: {e}")


async def main() -> int:
    """Main entry point with error handling."""
    app = None

    try:
        # Load settings from environment
        settings = Settings()

        # Create and start application
        app = AutoTraderApp(settings)
        await app.start()

        return 0

    except KeyboardInterrupt:
        if app:
            await app.shutdown()
        return 0

    except Exception as e:
        # Fallback logging in case logger isn't configured
        print(f"CRITICAL: Application failed to start: {e}", file=sys.stderr)
        return 1

    finally:
        if app and app._running:
            await app.shutdown()


if __name__ == "__main__":
    """Entry point when run as script."""
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        sys.exit(1)
