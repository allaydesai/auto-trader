"""Core trade orchestration implementation."""

from typing import Dict, Optional, Any
from decimal import Decimal
from datetime import datetime, time, UTC
from zoneinfo import ZoneInfo

from loguru import logger

from auto_trader.models.trade_plan import TradePlan, TradePlanStatus
from auto_trader.models.plan_loader import TradePlanLoader
from auto_trader.models.execution import ExecutionContext, PositionState
from auto_trader.models.enums import ExecutionAction, Timeframe
from auto_trader.models.order import OrderResult
from auto_trader.models.market_data import BarData
from auto_trader.trade_engine.function_registry import ExecutionFunctionRegistry
from auto_trader.trade_engine.order_execution_adapter import ExecutionOrderAdapter
from auto_trader.trade_engine.signal_processor import (
    SignalProcessor,
    SignalProcessorConfig,
)
from auto_trader.trade_engine.position_state_manager import PositionStateManager
from auto_trader.trade_engine.exit_processor import ExitProcessor
from auto_trader.trade_engine.lifecycle_manager import TradeLifecycleManager
from auto_trader.trade_engine.lifecycle_events import (
    TradeOrchestrationConfig,
    LifecycleEventManager,
)
from auto_trader.integrations.ibkr_client.order_execution_manager import (
    OrderExecutionManager,
)
from auto_trader.risk_management.risk_manager import RiskManager

from .configuration import ConfigurationManager
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
        market_hours_only: bool = True,
        order_timeout_seconds: int = 300,
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
        self.market_hours_only = market_hours_only
        self.order_timeout_seconds = order_timeout_seconds

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
        self._eastern_tz = ZoneInfo("America/New_York")

        # Initialize execution adapter
        self.execution_adapter = ExecutionOrderAdapter(
            order_execution_manager=self.order_execution_manager,
            order_timeout_seconds=self.order_timeout_seconds,
        )

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
        signal_config = SignalProcessorConfig(
            **self.config_manager.get_signal_processor_config()
        )
        self.signal_processor = SignalProcessor(
            execution_adapter=self.execution_adapter,
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
            loaded_plans = await self.coordinator.load_active_trade_plans()

            # Split plans into awaiting entry and open positions
            self.active_plans = {
                pid: p
                for pid, p in loaded_plans.items()
                if p.status == TradePlanStatus.AWAITING_ENTRY
            }
            self.position_plans = {
                pid: p
                for pid, p in loaded_plans.items()
                if p.status == TradePlanStatus.POSITION_OPEN
            }

            # Function registry is already initialized in constructor
            # No additional initialization needed

            self.is_running = True
            logger.info(
                f"TradeOrchestrator started with {len(self.active_plans)} awaiting entry "
                f"and {len(self.position_plans)} open positions"
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

        if self.market_hours_only and not self._is_market_open(bar_data.timestamp):
            logger.debug(
                "Skipping market data outside market hours",
                symbol=bar_data.symbol,
                timestamp=bar_data.timestamp.isoformat(),
            )
            return

        symbol = bar_data.symbol
        bar_size = bar_data.bar_size

        # FIX Gap #1: Check BOTH active_plans AND position_plans
        relevant_active_plans = self.coordinator.filter_plans_for_symbol(
            self.active_plans, symbol
        )

        relevant_position_plans = self.coordinator.filter_plans_for_symbol(
            self.position_plans, symbol
        )

        # Combine both lists
        all_relevant_plans = list(relevant_active_plans) + list(relevant_position_plans)

        if not all_relevant_plans:
            return

        logger.debug(
            f"Processing {len(relevant_active_plans)} awaiting entry, "
            f"{len(relevant_position_plans)} open positions",
            symbol=symbol,
            bar_size=bar_size,
        )

        # Process ALL relevant plans (both active and positions)
        for plan in all_relevant_plans:
            try:
                await self._evaluate_trade_plan(plan, bar_data)
                self.statistics.record_plan_processed(plan.plan_id)
            except Exception as e:
                logger.error(
                    f"Error evaluating plan {plan.plan_id}: {e}",
                    exc_info=True,
                )
                await self._handle_plan_error(plan, str(e))

    def _is_market_open(self, timestamp: Optional[datetime]) -> bool:
        """Check if timestamp falls within regular US market hours."""
        ts = timestamp or datetime.now(UTC)
        eastern_time = ts.astimezone(self._eastern_tz)

        # Weekends closed
        if eastern_time.weekday() >= 5:
            return False

        market_open = time(hour=9, minute=30)
        market_close = time(hour=16, minute=0)
        current_time = eastern_time.time()
        return market_open <= current_time <= market_close

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

    async def _evaluate_entry_function(
        self, plan: TradePlan, bar_data: BarData
    ) -> None:
        """Evaluate entry function for a trade plan.

        Args:
            plan: Trade plan in awaiting_entry status
            bar_data: Market data for evaluation
        """
        try:
            # Build execution context with all required parameters
            context = ExecutionContext(
                symbol=plan.symbol,
                timeframe=Timeframe(bar_data.bar_size),
                current_bar=bar_data,
                historical_bars=[],  # TODO: Get from market data manager
                trade_plan_params=plan.entry_function.parameters,
                position_state=None,  # No position yet for entry
                account_balance=self.risk_manager.account_value,
                timestamp=bar_data.timestamp,
            )

            # Get or create execution function instance from plan config
            from auto_trader.models.execution import ExecutionFunctionConfig

            entry_config = ExecutionFunctionConfig(
                name=f"{plan.plan_id}_entry",
                function_type=plan.entry_function.function_type,
                timeframe=Timeframe(plan.entry_function.timeframe),
                parameters=plan.entry_function.parameters,
                enabled=True,
                lookback_bars=0,  # TODO: Implement historical data manager
            )

            entry_function = await self.function_registry.get_or_create_function(
                entry_config
            )
            signal = await entry_function.evaluate(context)

            # Only process if signal should execute
            if not signal or not signal.should_execute:
                logger.debug(
                    f"No entry signal for plan {plan.plan_id}: {signal.reasoning if signal else 'No signal'}"
                )
                return

            # Process entry signal
            result = await self.signal_processor.process_entry_signal(
                plan, context, plan.entry_function.function_type, signal=signal
            )

            if result.success and result.order_result:
                self.statistics.record_signal_generated(plan.plan_id, "ENTRY")
                order_id = result.order_result.order_id or "unknown"
                self.statistics.record_order_placed(plan.plan_id, order_id)

                # Update plan status and tracking
                old_status = plan.status
                plan.status = TradePlanStatus.POSITION_OPEN
                self.status_tracker.record_status_change(
                    plan.plan_id, old_status, plan.status, "entry_filled"
                )

                # Move to position tracking
                self.position_plans[plan.plan_id] = plan
                if plan.plan_id in self.active_plans:
                    del self.active_plans[plan.plan_id]

                # Create position entry in position manager
                await self.position_manager.create_position_from_fill(
                    trade_plan=plan, order_result=result.order_result
                )

                # Record position opened
                dollar_risk = self._calculate_dollar_risk(plan, result.order_result)
                self.statistics.record_position_opened(
                    plan.plan_id, result.order_result, dollar_risk
                )

        except Exception as e:
            logger.error(
                f"Error evaluating entry function for plan {plan.plan_id}: {e}"
            )
            await self._handle_plan_error(plan, str(e))

    async def _evaluate_exit_functions(
        self, plan: TradePlan, bar_data: BarData
    ) -> None:
        """Evaluate exit functions for an open position.

        Evaluates both stop loss and take profit exit functions.
        First function to trigger will close the position.

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

            # Evaluate both stop loss and take profit functions
            exit_functions = [
                ("stop_loss", plan.stop_loss_function),
                ("take_profit", plan.take_profit_function),
            ]

            for exit_type, exit_func in exit_functions:
                # Convert PositionEntry to PositionState for ExecutionContext
                position_state = PositionState(
                    symbol=position.symbol,
                    quantity=position.quantity,
                    entry_price=position.entry_price,
                    current_price=bar_data.close_price,
                    stop_loss=plan.stop_loss,
                    take_profit=plan.take_profit,
                    opened_at=position.timestamp,
                )

                # Build execution context for this exit function
                context = ExecutionContext(
                    symbol=plan.symbol,
                    timeframe=Timeframe(bar_data.bar_size),
                    current_bar=bar_data,
                    historical_bars=[],  # TODO: Get from market data manager
                    trade_plan_params=exit_func.parameters,
                    position_state=position_state,
                    account_balance=self.risk_manager.account_value,
                    timestamp=bar_data.timestamp,
                )

                # Get or create exit function instance from plan config
                from auto_trader.models.execution import ExecutionFunctionConfig

                exit_config = ExecutionFunctionConfig(
                    name=f"{plan.plan_id}_{exit_type}",
                    function_type=exit_func.function_type,
                    timeframe=Timeframe(exit_func.timeframe),
                    parameters=exit_func.parameters,
                    enabled=True,
                    lookback_bars=0,  # TODO: Implement historical data manager
                )

                exit_function = await self.function_registry.get_or_create_function(
                    exit_config
                )
                signal = await exit_function.evaluate(context)

                if signal and signal.action in [
                    ExecutionAction.EXIT,
                    ExecutionAction.MODIFY_STOP,
                ]:
                    logger.info(
                        f"Exit signal triggered: {exit_type}",
                        plan_id=plan.plan_id,
                        exit_type=exit_type,
                        action=signal.action.value,
                    )

                    # Process exit signal
                    exit_result = await self.exit_processor.process_exit_signal(
                        signal, context, plan, exit_func.function_type
                    )

                    logger.debug(
                        f"Exit result for {plan.plan_id}: success={exit_result.success}, "
                        f"position_closed={getattr(exit_result, 'position_closed', None)}"
                    )

                    if exit_result.success:
                        self.statistics.record_signal_generated(
                            plan.plan_id, signal.action.value
                        )

                        if exit_result.position_closed:
                            # Position fully closed
                            old_status = plan.status
                            plan.status = TradePlanStatus.COMPLETED
                            self.status_tracker.record_status_change(
                                plan.plan_id,
                                old_status,
                                plan.status,
                                f"{exit_type}_exit_filled",
                            )

                            # Remove from active tracking
                            if plan.plan_id in self.position_plans:
                                del self.position_plans[plan.plan_id]

                            # Record position closed
                            if exit_result.order_result:
                                realized_pnl = getattr(
                                    exit_result.order_result, "realized_pnl", None
                                )
                                self.statistics.record_position_closed(
                                    plan.plan_id, exit_result.order_result, realized_pnl
                                )

                            # Exit early - position is closed, don't evaluate other exit
                            return

        except Exception as e:
            logger.error(
                f"Error evaluating exit functions for plan {plan.plan_id}: {e}"
            )
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
            },
        )

    def get_status_summary(self) -> Dict[str, Any]:
        """Get status summary for application statistics.

        Returns:
            Dictionary with orchestrator status and processor statistics
        """
        base_status = self.get_orchestrator_status()

        # Add processor statistics if available
        processors = {}

        # Add signal processor stats
        if hasattr(self, "signal_processor") and hasattr(
            self.signal_processor, "get_stats"
        ):
            processors["signal_processor_stats"] = self.signal_processor.get_stats()
        else:
            processors["signal_processor_stats"] = {"total_processed": 0}

        # Add exit processor stats
        if hasattr(self, "exit_processor") and hasattr(
            self.exit_processor, "get_stats"
        ):
            processors["exit_processor_stats"] = self.exit_processor.get_stats()
        else:
            processors["exit_processor_stats"] = {"positions_closed": 0}

        base_status["processors"] = processors
        return base_status

    def _calculate_dollar_risk(
        self, plan: TradePlan, order_result: OrderResult
    ) -> Decimal:
        """Calculate dollar risk for a position.

        Args:
            plan: Trade plan
            order_result: Order result

        Returns:
            Dollar risk amount
        """
        entry_price = order_result.average_fill_price or Decimal("0")
        stop_price = plan.stop_loss
        quantity = order_result.filled_quantity

        return abs(entry_price - stop_price) * quantity

    # Testing and compatibility methods
    async def add_trade_plan(self, trade_plan: TradePlan) -> None:
        """Add a trade plan for testing purposes."""
        self.trade_plan_loader.save_plan(trade_plan)
        loaded_plans = await self.coordinator.load_active_trade_plans()
        self.active_plans = {
            pid: p
            for pid, p in loaded_plans.items()
            if p.status == TradePlanStatus.AWAITING_ENTRY
        }
        self.position_plans = {
            pid: p
            for pid, p in loaded_plans.items()
            if p.status == TradePlanStatus.POSITION_OPEN
        }

    def get_trade_plan(self, plan_id: str) -> Optional[TradePlan]:
        """Get trade plan by ID for testing purposes."""
        return self.trade_plan_loader.load_plan(plan_id)

    async def process_market_data(self, bar_data: BarData) -> None:
        """Process market data event for testing purposes."""
        await self.process_market_data_event(bar_data)
