"""Trade lifecycle orchestration and management."""

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
from auto_trader.trade_engine.trade_statistics import TradeStatisticsCalculator
from auto_trader.integrations.ibkr_client.order_execution_manager import OrderExecutionManager
from auto_trader.risk_management.risk_manager import RiskManager




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
            trade_plan_loader: Trade plan loader and manager
            function_registry: Execution function registry
            order_execution_manager: Order execution manager
            risk_manager: Risk management system
            config: Orchestrator configuration
        """
        self.trade_plan_loader = trade_plan_loader
        self.function_registry = function_registry
        self.order_execution_manager = order_execution_manager
        self.risk_manager = risk_manager
        self.config = config or TradeOrchestrationConfig()
        
        # Initialize sub-managers
        self.lifecycle_manager = TradeLifecycleManager()
        self.position_manager = PositionStateManager()
        
        # Initialize processors
        signal_config = SignalProcessorConfig(
            enable_risk_validation=self.config.enable_risk_validation,
            minimum_confidence_threshold=0.6,
        )
        self.signal_processor = SignalProcessor(
            execution_adapter=ExecutionOrderAdapter(order_execution_manager),
            risk_manager=risk_manager,
            config=signal_config,
        )
        
        self.exit_processor = ExitProcessor(
            position_manager=self.position_manager,
            order_execution_manager=order_execution_manager,
            risk_manager=risk_manager,
        )
        
        # Event management
        self.event_manager = LifecycleEventManager(self.config)
        
        # State tracking
        self.active_plans: Dict[str, TradePlan] = {}
        self.position_plans: Dict[str, TradePlan] = {}
        self.is_running = False
        
        logger.info("TradeOrchestrator initialized with integrated processors")
    
    async def start(self) -> None:
        """Initialize orchestrator and start trade lifecycle management."""
        try:
            logger.info("Starting TradeOrchestrator")
            
            # Load all active trade plans
            await self._load_active_trade_plans()
            
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
        await self._persist_state()
        
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
        
        # Find relevant trade plans for this symbol/timeframe
        relevant_plans = self._get_relevant_plans(symbol, timeframe)
        
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
            # Evaluate entry function
            await self._evaluate_entry_function(plan, bar_data)
        elif plan.status == TradePlanStatus.POSITION_OPEN:
            # Evaluate exit functions (stop loss, take profit, trailing stop)
            await self._evaluate_exit_functions(plan, bar_data)
    
    async def _evaluate_entry_function(self, plan: TradePlan, bar_data: BarData) -> None:
        """Evaluate entry function for a trade plan.
        
        Args:
            plan: Trade plan in awaiting_entry status
            bar_data: Market data for evaluation
        """
        function_name = plan.entry_function.type
        function = await self.function_registry.get_function(function_name)
        
        if not function:
            logger.error(f"Entry function '{function_name}' not found for plan {plan.plan_id}")
            return
        
        # Create execution context
        execution_context = ExecutionContext(
            symbol=plan.symbol,
            timeframe=bar_data.timeframe,
            bar_data=bar_data,
            position_state=None,  # No position yet
            has_position=False,
            metadata={"plan_id": plan.plan_id, "function_type": "entry"},
        )
        
        # Evaluate the function
        signal = await function.evaluate(execution_context)
        
        if signal.action in [ExecutionAction.ENTER_LONG, ExecutionAction.ENTER_SHORT]:
            logger.info(
                f"Entry signal generated for plan {plan.plan_id}",
                action=signal.action.value,
                confidence=signal.confidence,
            )
            
            await self._handle_entry_signal(plan, signal, execution_context)
    
    async def _evaluate_exit_functions(self, plan: TradePlan, bar_data: BarData) -> None:
        """Evaluate exit functions for open position.
        
        Args:
            plan: Trade plan with open position
            bar_data: Market data for evaluation
        """
        # Get position information
        position_plan = self.position_plans.get(plan.plan_id)
        if not position_plan:
            logger.warning(f"No position found for plan {plan.plan_id}")
            return
        
        # Create execution context with position state from position manager
        position_entry = self.position_manager.get_position_by_plan_id(plan.plan_id)
        
        execution_context = ExecutionContext(
            symbol=plan.symbol,
            timeframe=bar_data.timeframe,
            bar_data=bar_data,
            position_state=position_entry,  # Actual position state from manager
            has_position=position_entry is not None,
            metadata={"plan_id": plan.plan_id, "function_type": "exit"},
        )
        
        # Evaluate exit function (handles both stop loss and take profit logic)
        if plan.exit_function:
            await self._evaluate_exit_function(
                plan, plan.exit_function.function_type, execution_context
            )
    
    async def _evaluate_exit_function(
        self, plan: TradePlan, function_name: str, execution_context: ExecutionContext
    ) -> None:
        """Evaluate a specific exit function.
        
        Args:
            plan: Trade plan
            function_name: Name of exit function to evaluate
            execution_context: Execution context
        """
        function = await self.function_registry.get_function(function_name)
        
        if not function:
            logger.error(f"Exit function '{function_name}' not found for plan {plan.plan_id}")
            return
        
        # Evaluate the function
        signal = await function.evaluate(execution_context)
        
        if signal.action == ExecutionAction.EXIT:
            logger.info(
                f"Exit signal generated for plan {plan.plan_id}",
                function=function_name,
                confidence=signal.confidence,
            )
            
            await self._handle_exit_signal(plan, signal, execution_context)
    
    async def _handle_entry_signal(
        self, plan: TradePlan, signal: ExecutionSignal, context: ExecutionContext
    ) -> None:
        """Handle entry signal by processing through signal processor.
        
        Args:
            plan: Trade plan generating the signal
            signal: Execution signal
            context: Execution context
        """
        try:
            # Process entry signal through signal processor
            processing_result = await self.signal_processor.process_entry_signal(
                signal, context, plan, plan.entry_function.function_type
            )
            
            if processing_result.success and processing_result.order_result:
                # Create position from successful order
                position_id = await self.position_manager.create_position_from_fill(
                    plan, processing_result.order_result
                )
                
                # Add to risk registry
                dollar_risk = plan.dollar_risk or self._calculate_dollar_risk(plan, processing_result.order_result)
                self.risk_manager.add_position_to_tracking(
                    position_id, plan.symbol, dollar_risk, plan.plan_id
                )
                
                # Transition plan to position_open via lifecycle manager
                await self.lifecycle_manager.transition_to_position_open(
                    plan, processing_result.order_result, 
                    processing_result.order_result.filled_quantity,
                    processing_result.order_result.average_fill_price
                )
                
                # Update tracking
                await self._handle_successful_entry(plan, processing_result.order_result)
                
            else:
                error_msg = processing_result.error_message or "Signal processing failed"
                logger.error(f"Entry processing failed for plan {plan.plan_id}: {error_msg}")
                
        except Exception as e:
            logger.error(f"Error handling entry signal for plan {plan.plan_id}: {e}")
            await self._handle_plan_error(plan, str(e))
    
    async def _handle_exit_signal(
        self, plan: TradePlan, signal: ExecutionSignal, context: ExecutionContext
    ) -> None:
        """Handle exit signal by processing through exit processor.
        
        Args:
            plan: Trade plan generating the signal
            signal: Execution signal
            context: Execution context
        """
        try:
            # Process exit signal through exit processor
            exit_result = await self.exit_processor.process_exit_signal(
                signal, context, plan, context.metadata.get("function_name", "exit")
            )
            
            if exit_result.success:
                # Handle successful exit processing
                if exit_result.position_closed:
                    # Transition plan to completed via lifecycle manager
                    await self.lifecycle_manager.transition_to_completed(
                        plan, exit_result.order_result
                    )
                    
                    # Update tracking
                    await self._handle_successful_exit(plan, exit_result.order_result)
                    
                    logger.info(
                        f"Position fully closed for plan {plan.plan_id}",
                        orders_cancelled=len(exit_result.orders_cancelled),
                    )
                else:
                    logger.info(
                        f"Partial exit or stop modification for plan {plan.plan_id}",
                        action=exit_result.action_taken,
                    )
            else:
                error_msg = exit_result.error_message or "Exit processing failed"
                logger.error(f"Exit processing failed for plan {plan.plan_id}: {error_msg}")
                
        except Exception as e:
            logger.error(f"Error handling exit signal for plan {plan.plan_id}: {e}")
            await self._handle_plan_error(plan, str(e))
    
    async def _handle_successful_entry(self, plan: TradePlan, order_result: OrderResult) -> None:
        """Handle successful entry order placement.
        
        Args:
            plan: Trade plan
            order_result: Successful order result
        """
        # Move plan to position tracking
        self.position_plans[plan.plan_id] = plan
        if plan.plan_id in self.active_plans:
            del self.active_plans[plan.plan_id]
        
        # Update plan status
        await self._update_plan_status(plan, TradePlanStatus.POSITION_OPEN)
        
        # Emit lifecycle event
        event = TradeLifecycleEvent(
            event_type="entry_filled",
            plan_id=plan.plan_id,
            old_status=TradePlanStatus.AWAITING_ENTRY,
            new_status=TradePlanStatus.POSITION_OPEN,
            context={"order_id": order_result.order_id},
        )
        await self._emit_lifecycle_event(event)
        
        logger.info(f"Plan {plan.plan_id} transitioned to POSITION_OPEN")
    
    async def _handle_successful_exit(self, plan: TradePlan, order_result: OrderResult) -> None:
        """Handle successful exit order placement.
        
        Args:
            plan: Trade plan
            order_result: Successful order result
        """
        # Clean up tracking
        if plan.plan_id in self.position_plans:
            del self.position_plans[plan.plan_id]
        
        # Update plan status
        await self._update_plan_status(plan, TradePlanStatus.COMPLETED)
        
        # Emit lifecycle event
        event = TradeLifecycleEvent(
            event_type="exit_filled",
            plan_id=plan.plan_id,
            old_status=TradePlanStatus.POSITION_OPEN,
            new_status=TradePlanStatus.COMPLETED,
            context={"order_id": order_result.order_id if order_result else None},
        )
        await self._emit_lifecycle_event(event)
        
        logger.info(f"Plan {plan.plan_id} completed successfully")
    
    async def _handle_plan_error(self, plan: TradePlan, error_message: str) -> None:
        """Handle error in trade plan processing.
        
        Args:
            plan: Trade plan with error
            error_message: Error description
        """
        await self._update_plan_status(plan, TradePlanStatus.ERROR)
        
        # Emit lifecycle event
        event = TradeLifecycleEvent(
            event_type="error",
            plan_id=plan.plan_id,
            old_status=plan.status,
            new_status=TradePlanStatus.ERROR,
            context={"error": error_message},
        )
        await self._emit_lifecycle_event(event)
        
        logger.error(f"Plan {plan.plan_id} entered ERROR state: {error_message}")
    
    async def _update_plan_status(self, plan: TradePlan, new_status: TradePlanStatus) -> None:
        """Update trade plan status and persist changes.
        
        Args:
            plan: Trade plan to update
            new_status: New status to set
        """
        old_status = plan.status
        plan.status = new_status
        
        # Persist the change
        await self.trade_plan_loader.update_plan_status(plan.plan_id, new_status)
        
        logger.debug(f"Plan {plan.plan_id} status: {old_status.value} -> {new_status.value}")
    
    async def _emit_lifecycle_event(self, event: TradeLifecycleEvent) -> None:
        """Emit lifecycle event to registered handlers.
        
        Args:
            event: Lifecycle event to emit
        """
        self.event_manager.emit_event(event)
    
    def add_lifecycle_handler(self, handler: Callable[[TradeLifecycleEvent], None]) -> None:
        """Add lifecycle event handler.
        
        Args:
            handler: Event handler function
        """
        self.event_manager.add_event_handler(handler)
    
    def remove_lifecycle_handler(self, handler: Callable[[TradeLifecycleEvent], None]) -> None:
        """Remove lifecycle event handler.
        
        Args:
            handler: Event handler function to remove
        """
        self.event_manager.remove_event_handler(handler)
    
    async def _load_active_trade_plans(self) -> None:
        """Load all active trade plans from storage."""
        try:
            # Load awaiting_entry plans
            awaiting_plans = await self.trade_plan_loader.get_plans_by_status(
                TradePlanStatus.AWAITING_ENTRY
            )
            for plan in awaiting_plans:
                self.active_plans[plan.plan_id] = plan
            
            # Load position_open plans
            position_plans = await self.trade_plan_loader.get_plans_by_status(
                TradePlanStatus.POSITION_OPEN
            )
            for plan in position_plans:
                self.position_plans[plan.plan_id] = plan
            
            logger.info(
                f"Loaded {len(self.active_plans)} awaiting_entry plans, "
                f"{len(self.position_plans)} position_open plans"
            )
            
        except Exception as e:
            logger.error(f"Failed to load trade plans: {e}")
            raise
    
    def _get_relevant_plans(self, symbol: str, timeframe) -> List[TradePlan]:
        """Get trade plans relevant to the given symbol and timeframe.
        
        Args:
            symbol: Trading symbol
            timeframe: Market data timeframe
            
        Returns:
            List of relevant trade plans
        """
        relevant_plans = []
        
        # Check awaiting_entry plans
        for plan in self.active_plans.values():
            if plan.symbol == symbol:
                # Check if timeframe matches entry function requirements
                if hasattr(plan.entry_function, 'timeframe'):
                    if plan.entry_function.timeframe == timeframe:
                        relevant_plans.append(plan)
                else:
                    # Default: include plan if symbol matches
                    relevant_plans.append(plan)
        
        # Check position_open plans
        for plan in self.position_plans.values():
            if plan.symbol == symbol:
                # Check if timeframe is relevant for exit functions
                relevant_plans.append(plan)
        
        return relevant_plans
    
    async def _persist_state(self) -> None:
        """Persist current orchestrator state."""
        # State is automatically persisted through TradePlanLoader
        # when plan statuses are updated
        pass
    
    def get_status_summary(self) -> Dict[str, Any]:
        """Get current orchestrator status summary.
        
        Returns:
            Dictionary with status information
        """
        return TradeStatisticsCalculator.get_orchestrator_status_summary(
            is_running=self.is_running,
            active_plans=self.active_plans,
            position_plans=self.position_plans,
            position_manager=self.position_manager,
            config=self.config,
            signal_processor=self.signal_processor,
            exit_processor=self.exit_processor,
            lifecycle_manager=self.lifecycle_manager,
        )
    
    def _calculate_dollar_risk(self, plan: TradePlan, order_result: OrderResult) -> Decimal:
        """Calculate dollar risk for a position.
        
        Args:
            plan: Trade plan
            order_result: Order result
            
        Returns:
            Dollar risk amount
        """
        return TradeStatisticsCalculator.calculate_dollar_risk(plan, order_result)
    
    # Convenience methods for test compatibility
    async def add_trade_plan(self, trade_plan: TradePlan) -> None:
        """Add a trade plan for testing purposes.
        
        Args:
            trade_plan: Trade plan to add
        """
        await self.trade_plan_loader.save_plan(trade_plan)
        await self._load_active_trade_plans()
    
    async def get_trade_plan(self, plan_id: str) -> Optional[TradePlan]:
        """Get trade plan by ID for testing purposes.
        
        Args:
            plan_id: Trade plan ID
            
        Returns:
            Trade plan if found
        """
        return await self.trade_plan_loader.load_plan(plan_id)
    
    async def process_market_data(self, bar_data: BarData) -> None:
        """Process market data event for testing purposes.
        
        Args:
            bar_data: Market data bar
        """
        await self.process_market_data_event(bar_data)