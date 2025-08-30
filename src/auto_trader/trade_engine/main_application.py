"""Main application entry point for trade lifecycle management."""

import asyncio
from typing import Optional, Dict, Any
from datetime import datetime, UTC
from pathlib import Path

from loguru import logger
from pydantic import BaseModel

from auto_trader.models.plan_loader import TradePlanLoader
from auto_trader.trade_engine.function_registry import ExecutionFunctionRegistry
from auto_trader.trade_engine.trade_orchestrator import TradeOrchestrator, TradeOrchestrationConfig
from auto_trader.integrations.ibkr_client.order_execution_manager import OrderExecutionManager
from auto_trader.risk_management.risk_manager import RiskManager


class ApplicationConfig(BaseModel):
    """Configuration for the main trading application."""
    
    # Data paths
    trade_plans_directory: str = "data/trade_plans"
    state_directory: str = "data/state"
    
    # Trading configuration
    simulation_mode: bool = True
    max_concurrent_trades: int = 10
    enable_risk_validation: bool = True
    enable_position_tracking: bool = True
    
    # Risk management
    account_value: float = 10000.0
    max_portfolio_risk_percent: float = 10.0
    
    # Performance settings
    signal_timeout_seconds: int = 30
    state_save_interval_seconds: int = 60
    
    # IBKR settings (for future use)
    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 7497
    ibkr_client_id: int = 1


class TradingApplication:
    """Main trading application coordinating all components."""
    
    def __init__(self, config: Optional[ApplicationConfig] = None):
        """Initialize trading application.
        
        Args:
            config: Application configuration
        """
        self.config = config or ApplicationConfig()
        
        # Core components (to be initialized)
        self.trade_plan_loader: Optional[TradePlanLoader] = None
        self.function_registry: Optional[ExecutionFunctionRegistry] = None
        self.order_execution_manager: Optional[OrderExecutionManager] = None
        self.risk_manager: Optional[RiskManager] = None
        self.trade_orchestrator: Optional[TradeOrchestrator] = None
        
        # Application state
        self.is_running = False
        self.start_time: Optional[datetime] = None
        self.shutdown_requested = False
        
        # Statistics tracking
        self.app_stats = {
            "startup_time": None,
            "uptime_seconds": 0,
            "trades_processed": 0,
            "signals_processed": 0,
            "errors_encountered": 0,
        }
        
        logger.info(f"TradingApplication initialized with config: simulation_mode={self.config.simulation_mode}")
    
    async def initialize(self) -> None:
        """Initialize all application components."""
        try:
            logger.info("Initializing trading application components...")
            
            # Initialize trade plan loader
            self.trade_plan_loader = TradePlanLoader(
                plans_directory=Path(self.config.trade_plans_directory)
            )
            
            # Initialize execution function registry
            self.function_registry = ExecutionFunctionRegistry()
            await self.function_registry.initialize()
            
            # Initialize risk manager
            self.risk_manager = RiskManager(
                account_value=self.config.account_value,
                max_portfolio_risk_percent=self.config.max_portfolio_risk_percent,
            )
            
            # Initialize order execution manager
            self.order_execution_manager = OrderExecutionManager(
                simulation_mode=self.config.simulation_mode,
                state_dir=Path(self.config.state_directory),
            )
            
            # Initialize trade orchestrator
            orchestrator_config = TradeOrchestrationConfig(
                max_concurrent_trades=self.config.max_concurrent_trades,
                signal_timeout_seconds=self.config.signal_timeout_seconds,
                state_save_interval_seconds=self.config.state_save_interval_seconds,
                enable_position_tracking=self.config.enable_position_tracking,
                enable_risk_validation=self.config.enable_risk_validation,
            )
            
            self.trade_orchestrator = TradeOrchestrator(
                trade_plan_loader=self.trade_plan_loader,
                function_registry=self.function_registry,
                order_execution_manager=self.order_execution_manager,
                risk_manager=self.risk_manager,
                config=orchestrator_config,
            )
            
            logger.info("All application components initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize application components: {e}")
            raise
    
    async def start(self) -> None:
        """Start the trading application."""
        if self.is_running:
            logger.warning("Application is already running")
            return
        
        try:
            logger.info("Starting trading application...")
            
            # Initialize if not already done
            if not self.trade_orchestrator:
                await self.initialize()
            
            # Start the trade orchestrator
            await self.trade_orchestrator.start()
            
            # Mark as running
            self.is_running = True
            self.start_time = datetime.now(UTC)
            self.app_stats["startup_time"] = self.start_time.isoformat()
            
            logger.info("Trading application started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start trading application: {e}")
            self.is_running = False
            raise
    
    async def stop(self) -> None:
        """Stop the trading application gracefully."""
        if not self.is_running:
            logger.warning("Application is not running")
            return
        
        try:
            logger.info("Stopping trading application...")
            
            self.shutdown_requested = True
            
            # Stop the trade orchestrator
            if self.trade_orchestrator:
                await self.trade_orchestrator.stop()
            
            # Update statistics
            if self.start_time:
                uptime = datetime.now(UTC) - self.start_time
                self.app_stats["uptime_seconds"] = uptime.total_seconds()
            
            # Mark as stopped
            self.is_running = False
            
            logger.info("Trading application stopped gracefully")
            
        except Exception as e:
            logger.error(f"Error during application shutdown: {e}")
            raise
    
    async def run_forever(self) -> None:
        """Run the trading application until shutdown is requested."""
        try:
            logger.info("Running trading application in continuous mode...")
            
            # Start the application
            await self.start()
            
            # Main application loop
            while self.is_running and not self.shutdown_requested:
                try:
                    # Update statistics
                    await self._update_statistics()
                    
                    # Sleep for a short interval to avoid busy waiting
                    await asyncio.sleep(1.0)
                    
                except KeyboardInterrupt:
                    logger.info("Keyboard interrupt received, initiating shutdown...")
                    break
                except Exception as e:
                    logger.error(f"Error in main application loop: {e}")
                    self.app_stats["errors_encountered"] += 1
                    
                    # Continue running unless critical error
                    await asyncio.sleep(1.0)
            
        except Exception as e:
            logger.error(f"Critical error in application main loop: {e}")
            raise
        finally:
            # Ensure clean shutdown
            await self.stop()
    
    async def process_market_data(self, bar_data) -> None:
        """Process incoming market data through the orchestrator.
        
        Args:
            bar_data: Market data bar
        """
        if not self.is_running or not self.trade_orchestrator:
            logger.warning("Application not running, ignoring market data")
            return
        
        try:
            await self.trade_orchestrator.process_market_data_event(bar_data)
            
        except Exception as e:
            logger.error(f"Error processing market data: {e}")
            self.app_stats["errors_encountered"] += 1
    
    def get_status(self) -> Dict[str, Any]:
        """Get current application status.
        
        Returns:
            Dictionary with application status information
        """
        # Update uptime if running
        if self.is_running and self.start_time:
            uptime = datetime.now(UTC) - self.start_time
            self.app_stats["uptime_seconds"] = uptime.total_seconds()
        
        status = {
            "is_running": self.is_running,
            "simulation_mode": self.config.simulation_mode,
            "shutdown_requested": self.shutdown_requested,
            "config": self.config.dict(),
            "statistics": self.app_stats.copy(),
        }
        
        # Add orchestrator status if available
        if self.trade_orchestrator:
            status["orchestrator"] = self.trade_orchestrator.get_status_summary()
        
        return status
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics from all components.
        
        Returns:
            Dictionary with performance metrics
        """
        metrics = {
            "application": self.app_stats.copy(),
        }
        
        if self.trade_orchestrator:
            orchestrator_status = self.trade_orchestrator.get_status_summary()
            
            # Extract processor statistics
            if "processors" in orchestrator_status:
                metrics.update(orchestrator_status["processors"])
            
            # Add orchestrator metrics
            metrics["orchestrator"] = {
                "active_plans": orchestrator_status.get("active_plans_count", 0),
                "position_plans": orchestrator_status.get("position_plans_count", 0),
                "open_positions": orchestrator_status.get("open_positions_count", 0),
                "total_positions": orchestrator_status.get("total_positions", 0),
            }
        
        return metrics
    
    async def _update_statistics(self) -> None:
        """Update application statistics."""
        try:
            if self.trade_orchestrator:
                # Get statistics from orchestrator
                orchestrator_stats = self.trade_orchestrator.get_status_summary()
                
                # Update trade statistics
                if "processors" in orchestrator_stats:
                    processors = orchestrator_stats["processors"]
                    
                    if "signal_processor_stats" in processors:
                        signal_stats = processors["signal_processor_stats"]
                        self.app_stats["signals_processed"] = signal_stats.get("total_processed", 0)
                    
                    if "exit_processor_stats" in processors:
                        exit_stats = processors["exit_processor_stats"]
                        positions_closed = exit_stats.get("positions_closed", 0)
                        self.app_stats["trades_processed"] = positions_closed
                        
        except Exception as e:
            logger.debug(f"Error updating statistics: {e}")
            # Don't raise - statistics update is not critical
    
    async def reload_trade_plans(self) -> int:
        """Reload trade plans from disk.
        
        Returns:
            Number of plans loaded
        """
        if not self.trade_plan_loader:
            logger.error("Trade plan loader not initialized")
            return 0
        
        try:
            # This would reload plans - actual implementation depends on TradePlanLoader API
            logger.info("Reloading trade plans...")
            
            # For now, return 0 as placeholder
            return 0
            
        except Exception as e:
            logger.error(f"Error reloading trade plans: {e}")
            return 0


async def main():
    """Main entry point for the trading application."""
    
    # Configure logging
    logger.info("Starting Auto-Trader Application")
    
    # Create application with default config
    app = TradingApplication()
    
    try:
        # Run the application
        await app.run_forever()
        
    except KeyboardInterrupt:
        logger.info("Application interrupted by user")
    except Exception as e:
        logger.error(f"Application error: {e}")
        raise
    finally:
        logger.info("Auto-Trader Application shutdown complete")


if __name__ == "__main__":
    # Run the main application
    asyncio.run(main())