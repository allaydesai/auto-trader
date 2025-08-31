"""Core trade orchestration implementation."""

from typing import Dict, List, Optional, Callable, Any
from datetime import datetime, UTC
from decimal import Decimal

from loguru import logger

from auto_trader.models.trade_plan import TradePlan, TradePlanStatus
from auto_trader.models.plan_loader import TradePlanLoader
from auto_trader.models.execution import ExecutionSignal, ExecutionContext
from auto_trader.models.enums import ExecutionAction
from auto_trader.models.order import OrderResult
from auto_trader.models.market_data import BarData
from auto_trader.trade_engine.function_registry import ExecutionFunctionRegistry
from auto_trader.trade_engine.order_execution_adapter import ExecutionOrderAdapter
from auto_trader.trade_engine.signal_processor import SignalProcessor, SignalProcessorConfig
from auto_trader.trade_engine.position_state_manager import PositionStateManager
from auto_trader.trade_engine.exit_processor import ExitProcessor
from auto_trader.trade_engine.lifecycle_manager import TradeLifecycleManager
from auto_trader.trade_engine.lifecycle_events import (
    TradeLifecycleEvent,
    TradeOrchestrationConfig,
    LifecycleEventManager
)
from auto_trader.integrations.ibkr_client.order_execution_manager import OrderExecutionManager
from auto_trader.risk_management.risk_manager import RiskManager

from .configuration import ConfigurationManager, OrchestrationConfig
from .statistics import OrchestrationStatistics, StatusReporter
from .coordination import ComponentCoordinator, MarketDataRouter, PlanStatusTracker


class TradeOrchestrator:
    """Main trade orchestration engine managing complete trade lifecycles.
    
    Coordinates between execution functions, risk management, and order execution
    to manage complete trade lifecycles from entry signal to exit.
    """
    
    def __init__(
        self,
        trade_plan_loader: TradePlanLoader,
        function_registry: ExecutionFunctionRegistry,
        order_execution_manager: OrderExecutionManager,
        risk_manager: RiskManager,
        config: Optional[TradeOrchestrationConfig] = None,
    ):
        """Initialize trade orchestrator.
        
        Args:
            trade_plan_loader: Trade plan loading system
            function_registry: Execution function registry
            order_execution_manager: Order execution system
            risk_manager: Risk management system
            config: Orchestrator configuration
        """
        # Core dependencies
        self.trade_plan_loader = trade_plan_loader
        self.function_registry = function_registry
        self.order_execution_manager = order_execution_manager
        self.risk_manager = risk_manager
        
        # Configuration management
        self.config_manager = ConfigurationManager(config)
        if not self.config_manager.validate_configuration():
            raise ValueError("Invalid orchestration configuration")
        self.config = self.config_manager.config
        
        # Statistics and reporting
        self.statistics = OrchestrationStatistics()
        self.status_reporter = StatusReporter(self.statistics)
        
        # Component coordination
        self.coordinator = ComponentCoordinator(trade_plan_loader)
        self.data_router = MarketDataRouter()
        self.status_tracker = PlanStatusTracker()
        
        # Initialize core processors
        self._initialize_processors()
        
        # State tracking
        self.active_plans: Dict[str, TradePlan] = {}
        self.position_plans: Dict[str, TradePlan] = {}
        self.is_running = False
        
        logger.info("TradeOrchestrator initialized with integrated processors")
        
    def _initialize_processors(self) -> None:
        """Initialize core processing components."""
        # Position and lifecycle management
        self.position_manager = PositionStateManager()
        self.lifecycle_manager = TradeLifecycleManager()
        
        # Signal processing
        signal_config = SignalProcessorConfig(**self.config_manager.get_signal_processor_config())
        self.signal_processor = SignalProcessor(
            function_registry=self.function_registry,
            risk_manager=self.risk_manager,
            config=signal_config,
        )
        
        # Exit processing
        self.exit_processor = ExitProcessor(
            position_manager=self.position_manager,
            order_execution_manager=self.order_execution_manager,
            risk_manager=self.risk_manager,
        )
        
        # Event management
        self.event_manager = LifecycleEventManager(self.config)
    
    async def start(self) -> None:
        """Initialize orchestrator and start trade lifecycle management."""
        try:
            logger.info("Starting TradeOrchestrator")
            
            # Load all active trade plans
            self.active_plans = await self.coordinator.load_active_trade_plans()
            
            # Initialize execution function registry if needed
            if not self.function_registry._functions:
                await self.function_registry.initialize()
            
            self.is_running = True
            logger.info(
                f"TradeOrchestrator started with {len(self.active_plans)} active plans"
            )
            
        except Exception as e:
            logger.error(f"Failed to start TradeOrchestrator: {e}")
            raise
    
    async def stop(self) -> None:
        """Gracefully stop the trade orchestrator."""
        logger.info("Stopping TradeOrchestrator")
        self.is_running = False
        
        # Save final state
        await self.coordinator.persist_state(self.active_plans)
        
        logger.info("TradeOrchestrator stopped")
    
    async def process_market_data_event(self, bar_data: BarData) -> None:
        """Process incoming market data and evaluate relevant trade plans.
        
        Args:
            bar_data: Market data bar for evaluation
        """
        if not self.is_running:
            return
        
        symbol = bar_data.symbol
        timeframe = bar_data.timeframe
        
        # Find relevant trade plans for this symbol
        relevant_plans = self.coordinator.filter_plans_for_symbol(
            self.active_plans, symbol
        )
        
        if not relevant_plans:
            return
        
        logger.debug(
            f"Processing market data for {len(relevant_plans)} plans",
            symbol=symbol,
            timeframe=timeframe.value,
        )
        
        # Process each relevant plan
        for plan in relevant_plans:
            try:
                await self._evaluate_trade_plan(plan, bar_data)
                self.statistics.record_plan_processed(plan.plan_id)
            except Exception as e:
                logger.error(
                    f"Error evaluating plan {plan.plan_id}: {e}",
                    exc_info=True,
                )
                await self._handle_plan_error(plan, str(e))
    
    async def _evaluate_trade_plan(self, plan: TradePlan, bar_data: BarData) -> None:
        """Evaluate a trade plan against market data.
        
        Args:
            plan: Trade plan to evaluate
            bar_data: Market data for evaluation
        """
        # Determine which functions to evaluate based on plan status
        if plan.status == TradePlanStatus.AWAITING_ENTRY:
            await self._evaluate_entry_function(plan, bar_data)
        elif plan.status == TradePlanStatus.POSITION_OPEN:
            await self._evaluate_exit_functions(plan, bar_data)
    
    async def _evaluate_entry_function(self, plan: TradePlan, bar_data: BarData) -> None:
        """Evaluate entry function for a trade plan.
        
        Args:
            plan: Trade plan in awaiting_entry status
            bar_data: Market data for evaluation
        """
        try:
            context = ExecutionContext(
                symbol=plan.symbol,
                current_bar=bar_data,
                has_position=False,
            )
            
            # Process entry signal
            result = await self.signal_processor.process_entry_signal(
                plan, context, plan.entry_function.function_type
            )
            
            if result.success and result.order_result:
                self.statistics.record_signal_generated(plan.plan_id, "ENTRY")
                self.statistics.record_order_placed(plan.plan_id, result.order_result.order_id)
                
                # Update plan status and tracking
                old_status = plan.status
                plan.status = TradePlanStatus.POSITION_OPEN
                self.status_tracker.record_status_change(
                    plan.plan_id, old_status, plan.status, "entry_filled"
                )
                
                # Move to position tracking
                self.position_plans[plan.plan_id] = plan
                
                # Record position opened
                dollar_risk = self._calculate_dollar_risk(plan, result.order_result)
                self.statistics.record_position_opened(
                    plan.plan_id, result.order_result, dollar_risk
                )
                
        except Exception as e:
            logger.error(f"Error evaluating entry function for plan {plan.plan_id}: {e}")
            await self._handle_plan_error(plan, str(e))
    
    async def _evaluate_exit_functions(self, plan: TradePlan, bar_data: BarData) -> None:
        """Evaluate exit functions for an open position.
        
        Args:
            plan: Trade plan with open position
            bar_data: Market data for evaluation
        """
        try:
            # Get position state
            position = self.position_manager.get_position_by_plan_id(plan.plan_id)
            if not position:
                logger.warning(f"No position found for plan {plan.plan_id}")
                return
            
            context = ExecutionContext(
                symbol=plan.symbol,
                current_bar=bar_data,
                has_position=True,
                position_entry_price=position.average_entry_price,
                current_quantity=position.quantity,
            )
            
            # Evaluate exit function
            function = self.function_registry.get_function(plan.exit_function.function_type)
            signal = await function.evaluate(context)
            
            if signal and signal.action in [ExecutionAction.EXIT, ExecutionAction.MODIFY_STOP]:
                # Process exit signal
                exit_result = await self.exit_processor.process_exit_signal(
                    signal, context, plan, plan.exit_function.function_type
                )
                
                if exit_result.success:
                    self.statistics.record_signal_generated(plan.plan_id, signal.action.value)
                    
                    if exit_result.position_closed:
                        # Position fully closed
                        old_status = plan.status
                        plan.status = TradePlanStatus.COMPLETED
                        self.status_tracker.record_status_change(
                            plan.plan_id, old_status, plan.status, "exit_filled"
                        )
                        
                        # Remove from active tracking
                        if plan.plan_id in self.position_plans:
                            del self.position_plans[plan.plan_id]
                        
                        # Record position closed
                        if exit_result.order_result:
                            self.statistics.record_position_closed(
                                plan.plan_id, exit_result.order_result, exit_result.realized_pnl
                            )
                
        except Exception as e:
            logger.error(f"Error evaluating exit functions for plan {plan.plan_id}: {e}")
            await self._handle_plan_error(plan, str(e))
    
    async def _handle_plan_error(self, plan: TradePlan, error_message: str) -> None:
        """Handle plan processing error.
        
        Args:
            plan: Trade plan with error
            error_message: Error description
        """
        self.statistics.record_processing_error(plan.plan_id, error_message)
        
        # Update plan status to error
        old_status = plan.status
        plan.status = TradePlanStatus.ERROR
        self.status_tracker.record_status_change(
            plan.plan_id, old_status, plan.status, f"error: {error_message}"
        )
    
    def get_orchestrator_status(self) -> Dict[str, Any]:
        """Get comprehensive orchestrator status.
        
        Returns:
            Dictionary with status information
        """
        return self.status_reporter.get_orchestrator_status(
            is_running=self.is_running,
            active_plans=self.active_plans,
            position_plans=self.position_plans,
            additional_data={
                "function_registry_loaded": bool(self.function_registry._functions),
                "subscription_stats": self.data_router.get_subscription_stats(),
            }
        )
    
    def _calculate_dollar_risk(self, plan: TradePlan, order_result: OrderResult) -> Decimal:
        """Calculate dollar risk for a position.
        
        Args:
            plan: Trade plan
            order_result: Order result
            
        Returns:
            Dollar risk amount
        """
        entry_price = order_result.average_fill_price
        stop_price = plan.stop_loss
        quantity = order_result.filled_quantity
        
        return abs(entry_price - stop_price) * quantity
    
    # Testing and compatibility methods
    async def add_trade_plan(self, trade_plan: TradePlan) -> None:
        """Add a trade plan for testing purposes."""
        await self.trade_plan_loader.save_plan(trade_plan)
        self.active_plans = await self.coordinator.load_active_trade_plans()
    
    async def get_trade_plan(self, plan_id: str) -> Optional[TradePlan]:
        """Get trade plan by ID for testing purposes."""
        return await self.trade_plan_loader.load_plan(plan_id)
    
    async def process_market_data(self, bar_data: BarData) -> None:
        """Process market data event for testing purposes."""
        await self.process_market_data_event(bar_data)