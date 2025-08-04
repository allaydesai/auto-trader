"""Auto-Trader main entry point with proper error handling and initialization."""

import asyncio
import signal
import sys
from pathlib import Path
from typing import Optional

from config import Settings, ConfigLoader
from auto_trader.logging_config import LoggerConfig, get_logger, set_service_context


class AutoTraderApp:
    """Main application class with dependency injection and lifecycle management."""
    
    def __init__(self, settings: Optional[Settings] = None):
        """Initialize application with configuration."""
        self.settings = settings or Settings()
        self.config_loader = ConfigLoader(self.settings)
        self.logger = get_logger("main", "system")
        self._shutdown_event = asyncio.Event()
        self._running = False
        
    async def initialize(self) -> None:
        """Initialize all application components."""
        set_service_context("main", "initialize")
        
        try:
            # Configure logging first
            log_config = LoggerConfig(
                logs_dir=self.settings.logs_dir,
                log_level="DEBUG" if self.settings.debug else "INFO"
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
                log_level=system_config.logging.level
            )
            
            # TODO: Initialize modules when implemented
            # await self._initialize_trade_engine()
            # await self._initialize_ibkr_client()
            # await self._initialize_risk_manager()
            # await self._initialize_discord_notifier()
            
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
                # TODO: Shutdown modules when implemented
                # await self._shutdown_trade_engine()
                # await self._shutdown_ibkr_client()
                # await self._shutdown_risk_manager()
                # await self._shutdown_discord_notifier()
                
                self.logger.info("Application shutdown completed")
                
            except Exception as e:
                self.logger.error("Error during shutdown", error=str(e))
                raise
    
    async def _run_main_loop(self) -> None:
        """Main application event loop."""
        set_service_context("main", "run_main_loop")
        
        try:
            while self._running:
                # TODO: Implement main trading logic when modules are ready
                # await self._process_trade_signals()
                # await self._update_positions()
                # await self._check_risk_limits()
                
                # For now, just wait for shutdown signal
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