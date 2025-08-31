"""Core exit processor implementation."""

from typing import Dict, Any
from datetime import datetime, UTC
from decimal import Decimal

from loguru import logger

from auto_trader.models.execution import ExecutionSignal, ExecutionContext
from auto_trader.models.enums import ExecutionAction
from auto_trader.models.order import OrderResult
from auto_trader.models.trade_plan import TradePlan
from auto_trader.trade_engine.position_state_manager import PositionStateManager
from auto_trader.trade_engine.position_entry import PositionEntry
from auto_trader.trade_engine.order_builders import ExitProcessingResult
from auto_trader.integrations.ibkr_client.order_execution_manager import OrderExecutionManager
from auto_trader.risk_management.risk_manager import RiskManager

from .validation import ExitSignalValidator
from .order_management import OrderCancellationManager, ExitOrderManager
from .position_cleanup import PositionCleanupManager


class ExitProcessor:
    """Processes exit signals for open positions.
    
    Handles exit signal evaluation, order cancellation, position cleanup,
    and risk registry management for completed trades.
    """
    
    def __init__(
        self,
        position_manager: PositionStateManager,
        order_execution_manager: OrderExecutionManager,
        risk_manager: RiskManager,
    ):
        """Initialize exit processor.
        
        Args:
            position_manager: Position state management
            order_execution_manager: Order execution system
            risk_manager: Risk management system
        """
        self.position_manager = position_manager
        self.order_execution_manager = order_execution_manager
        self.risk_manager = risk_manager
        
        # Initialize sub-components
        self.validator = ExitSignalValidator()
        self.order_cancellation_manager = OrderCancellationManager(order_execution_manager)
        self.exit_order_manager = ExitOrderManager(order_execution_manager)
        self.cleanup_manager = PositionCleanupManager(position_manager, risk_manager)
        
        # Processing statistics
        self.processing_stats = {
            "exit_signals_processed": 0,
            "positions_closed": 0,
            "stop_modifications": 0,
            "orders_cancelled": 0,
            "processing_errors": 0,
            "last_processed_at": None,
        }

    async def process_exit_signal(
        self,
        signal: ExecutionSignal,
        context: ExecutionContext,
        trade_plan: TradePlan,
        function_name: str,
    ) -> ExitProcessingResult:
        """Process an exit execution signal with comprehensive position management.
        
        Args:
            signal: Exit execution signal with confidence and reasoning
            context: Execution context with market data and position information
            trade_plan: Trade plan containing exit parameters
            function_name: Name of the execution function that generated the signal
            
        Returns:
            ExitProcessingResult with success status and action details
        """
        try:
            logger.info(
                f"Processing exit signal for plan {trade_plan.plan_id}",
                action=signal.action.value,
                confidence=signal.confidence,
                function=function_name,
            )
            
            self.processing_stats["exit_signals_processed"] += 1
            
            # Get associated position
            position = self.position_manager.get_position_by_plan_id(trade_plan.plan_id)
            
            # Validate signal and state
            validation_result = self.validator.validate_exit_signal(signal, trade_plan, position)
            if not validation_result.success:
                return validation_result
            
            # Process based on signal action
            if signal.action == ExecutionAction.EXIT:
                return await self._process_position_exit(
                    signal, context, trade_plan, position, function_name
                )
            elif signal.action == ExecutionAction.MODIFY_STOP:
                return await self._process_stop_modification(
                    signal, context, trade_plan, position, function_name
                )
            
        except Exception as e:
            self.processing_stats["processing_errors"] += 1
            logger.error(
                f"Error processing exit signal for plan {trade_plan.plan_id}: {e}",
                exc_info=True,
            )
            return ExitProcessingResult(
                success=False,
                action_taken="processing_error",
                error_message=str(e),
                plan_id=trade_plan.plan_id,
            )
    
    async def _process_position_exit(
        self,
        signal: ExecutionSignal,
        context: ExecutionContext,
        trade_plan: TradePlan,
        position: PositionEntry,
        function_name: str,
    ) -> ExitProcessingResult:
        """Process position exit signal.
        
        Args:
            signal: Exit signal
            context: Execution context
            trade_plan: Trade plan
            position: Position to exit
            function_name: Function name generating signal
            
        Returns:
            ExitProcessingResult with processing outcome
        """
        try:
            logger.info(
                f"Processing position exit for plan {trade_plan.plan_id}",
                position_id=position.position_id,
                function=function_name,
            )
            
            # Cancel existing orders for the symbol
            cancelled_orders = await self.order_cancellation_manager.cancel_symbol_orders(
                trade_plan.symbol, position, self.processing_stats
            )
            
            # Create and execute exit order
            exit_order_request = self.exit_order_manager.create_exit_order_request(
                signal, context, trade_plan, position
            )
            
            order_result = await self.exit_order_manager.execute_exit_order(exit_order_request)
            
            if order_result.success:
                # Handle the fill if immediate
                if order_result.filled_quantity > 0:
                    await self.cleanup_manager.handle_exit_fill(
                        position, order_result, trade_plan, self.processing_stats
                    )
                
                self.processing_stats["last_processed_at"] = datetime.now(UTC)
                
                return ExitProcessingResult(
                    success=True,
                    action_taken="exit_order_placed",
                    order_id=order_result.order_id,
                    cancelled_order_ids=cancelled_orders,
                    position_id=position.position_id,
                    plan_id=trade_plan.plan_id,
                    realized_pnl=getattr(order_result, "realized_pnl", None),
                    position_closed=(order_result.filled_quantity == position.quantity),
                )
            else:
                logger.error(
                    f"Failed to place exit order for plan {trade_plan.plan_id}: "
                    f"{order_result.error_message}"
                )
                return ExitProcessingResult(
                    success=False,
                    action_taken="exit_order_failed",
                    error_message=order_result.error_message,
                    position_id=position.position_id,
                    plan_id=trade_plan.plan_id,
                )
                
        except Exception as e:
            logger.error(f"Error processing position exit: {e}", exc_info=True)
            return ExitProcessingResult(
                success=False,
                action_taken="exit_processing_error",
                error_message=str(e),
                position_id=position.position_id,
                plan_id=trade_plan.plan_id,
            )
    
    async def _process_stop_modification(
        self,
        signal: ExecutionSignal,
        context: ExecutionContext,
        trade_plan: TradePlan,
        position: PositionEntry,
        function_name: str,
    ) -> ExitProcessingResult:
        """Process stop order modification signal.
        
        Args:
            signal: Stop modification signal
            context: Execution context
            trade_plan: Trade plan
            position: Position with stop to modify
            function_name: Function name generating signal
            
        Returns:
            ExitProcessingResult with modification outcome
        """
        try:
            logger.info(
                f"Processing stop modification for plan {trade_plan.plan_id}",
                position_id=position.position_id,
                function=function_name,
            )
            
            # Extract new stop price from signal metadata
            new_stop_price = Decimal(str(signal.metadata.get("stop_price", "0")))
            if new_stop_price <= 0:
                return ExitProcessingResult(
                    success=False,
                    action_taken="invalid_stop_price",
                    error_message="Invalid stop price in signal metadata",
                    position_id=position.position_id,
                    plan_id=trade_plan.plan_id,
                )
            
            # Create stop modification order
            stop_order_request = self.exit_order_manager.create_stop_order_request(
                trade_plan, position, new_stop_price
            )
            
            order_result = await self.exit_order_manager.execute_stop_modification(stop_order_request)
            
            if order_result.success:
                self.processing_stats["stop_modifications"] += 1
                self.processing_stats["last_processed_at"] = datetime.now(UTC)
                
                return ExitProcessingResult(
                    success=True,
                    action_taken="stop_modified",
                    order_id=order_result.order_id,
                    position_id=position.position_id,
                    plan_id=trade_plan.plan_id,
                    stop_price=new_stop_price,
                )
            else:
                logger.error(
                    f"Failed to modify stop for plan {trade_plan.plan_id}: "
                    f"{order_result.error_message}"
                )
                return ExitProcessingResult(
                    success=False,
                    action_taken="stop_modification_failed",
                    error_message=order_result.error_message,
                    position_id=position.position_id,
                    plan_id=trade_plan.plan_id,
                )
                
        except Exception as e:
            logger.error(f"Error processing stop modification: {e}", exc_info=True)
            return ExitProcessingResult(
                success=False,
                action_taken="stop_modification_error",
                error_message=str(e),
                position_id=position.position_id,
                plan_id=trade_plan.plan_id,
            )
    
    async def handle_order_fill_event(self, order_result: OrderResult) -> None:
        """Handle incoming order fill events for exit orders.
        
        Args:
            order_result: Order fill result
        """
        await self.cleanup_manager.handle_order_fill_event(
            order_result, self.processing_stats
        )
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """Get processing statistics.
        
        Returns:
            Dictionary with processing statistics
        """
        return self.processing_stats.copy()
    
    def reset_statistics(self) -> None:
        """Reset processing statistics."""
        self.processing_stats = {
            "exit_signals_processed": 0,
            "positions_closed": 0,
            "stop_modifications": 0,
            "orders_cancelled": 0,
            "processing_errors": 0,
            "last_processed_at": None,
        }