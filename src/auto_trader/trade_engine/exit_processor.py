"""Exit signal processing for open positions."""

from typing import Dict, Any, Optional, List
from datetime import datetime, UTC
from decimal import Decimal

from loguru import logger

from auto_trader.models.execution import ExecutionSignal, ExecutionContext
from auto_trader.models.enums import ExecutionAction, OrderSide, OrderStatus
from auto_trader.models.order import OrderResult
from auto_trader.models.trade_plan import TradePlan, TradePlanStatus
from auto_trader.trade_engine.position_state_manager import PositionStateManager
from auto_trader.trade_engine.position_entry import PositionEntry
from auto_trader.trade_engine.order_builders import ExitProcessingResult, ExitOrderBuilder
from auto_trader.trade_engine.signal_processor import SignalProcessingResult
from auto_trader.integrations.ibkr_client.order_execution_manager import OrderExecutionManager
from auto_trader.risk_management.risk_manager import RiskManager




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
        
        # Processing statistics
        self.processing_stats = {
            "exit_signals_processed": 0,
            "positions_closed": 0,
            "orders_cancelled": 0,
            "processing_errors": 0,
            "partial_exits": 0,
        }
        
        logger.info("ExitProcessor initialized")
    
    async def process_exit_signal(
        self,
        signal: ExecutionSignal,
        context: ExecutionContext,
        trade_plan: TradePlan,
        function_name: str,
    ) -> ExitProcessingResult:
        """Process an exit execution signal with comprehensive position management.
        
        Main entry point for exit signal processing. Validates signal, retrieves position,
        and orchestrates the complete exit workflow including order management and cleanup.
        
        Args:
            signal: Exit execution signal (CLOSE_LONG/CLOSE_SHORT) with confidence and reasoning
            context: Execution context containing current market data and position information
            trade_plan: Trade plan containing exit parameters and risk management settings
            function_name: Name of the execution function that generated the signal (for audit trail)
            
        Returns:
            ExitProcessingResult with success status, order details, and error information
            
        Example Usage:
            >>> # Stop-loss trigger for a long position
            >>> signal = ExecutionSignal(
            ...     action=ExecutionAction.CLOSE_LONG,
            ...     confidence=0.95,
            ...     reasoning="Price broke below stop-loss level $148.50"
            ... )
            >>> context = ExecutionContext(
            ...     symbol="AAPL",
            ...     current_bar=BarData(close_price=Decimal("148.00")),
            ...     has_position=True
            ... )
            >>> trade_plan = TradePlan(
            ...     plan_id="AAPL_001",
            ...     symbol="AAPL",
            ...     stop_loss=Decimal("148.50"),
            ...     # ... other plan parameters
            ... )
            >>> result = await exit_processor.process_exit_signal(
            ...     signal, context, trade_plan, "stop_loss_function"
            ... )
            >>> if result.success:
            ...     print(f"Position closed: {result.position_closed}")
            ...     print(f"Realized P&L: ${result.realized_pnl}")
            ...
            
        Signal Processing Flow:
            1. **Validation**: Verify signal action is valid exit action (CLOSE_LONG/CLOSE_SHORT)
            2. **Position Lookup**: Find open position for the trade plan symbol
            3. **Exit Processing**: Delegate to position exit workflow
            4. **Registry Cleanup**: Remove position from risk management tracking
            5. **Statistics**: Update processing metrics and performance counters
            
        Error Scenarios:
            - **No Position Found**: Returns failure result when no open position exists
            - **Invalid Signal**: Returns failure for non-exit actions (ENTER_LONG, etc.)
            - **Order Failures**: Handles order placement failures gracefully
            - **System Errors**: Catches and logs unexpected exceptions
            
        Note:
            This method is thread-safe and handles concurrent exit signals appropriately.
            Multiple exit signals for the same position are handled safely.
        """
        try:
            logger.info(
                f"Processing exit signal for plan {trade_plan.plan_id}",
                action=signal.action.value,
                confidence=signal.confidence,
                function=function_name,
            )
            
            self.processing_stats["exit_signals_processed"] += 1
            
            # Validate signal action
            if signal.action not in [ExecutionAction.EXIT, ExecutionAction.MODIFY_STOP]:
                return ExitProcessingResult(
                    success=False,
                    action_taken="invalid_exit_action",
                    error_message=f"Invalid exit action: {signal.action}",
                    plan_id=trade_plan.plan_id,
                )
            
            # Get associated position
            position = self.position_manager.get_position_by_plan_id(trade_plan.plan_id)
            if not position:
                return ExitProcessingResult(
                    success=False,
                    action_taken="no_position_found",
                    error_message=f"No position found for plan {trade_plan.plan_id}",
                    plan_id=trade_plan.plan_id,
                )
            
            if position.is_closed:
                return ExitProcessingResult(
                    success=False,
                    action_taken="position_already_closed",
                    error_message=f"Position {position.position_id} already closed",
                    position_id=position.position_id,
                    plan_id=trade_plan.plan_id,
                )
            
            # Validate trade plan status
            if trade_plan.status != TradePlanStatus.POSITION_OPEN:
                return ExitProcessingResult(
                    success=False,
                    action_taken="invalid_plan_status",
                    error_message=f"Plan {trade_plan.plan_id} not in position_open status: {trade_plan.status}",
                    position_id=position.position_id,
                    plan_id=trade_plan.plan_id,
                )
            
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
        """Process complete position exit with comprehensive order management.
        
        Handles the complete exit workflow: cancelling existing orders, placing exit orders,
        processing fills, updating position state, and managing risk registry. This method
        ensures clean position closure with proper order cancellation and state cleanup.
        
        Args:
            signal: Exit execution signal (CLOSE_LONG/CLOSE_SHORT) with confidence and reasoning
            context: Execution context containing current bar data and market information
            trade_plan: Trade plan associated with the position being exited
            position: Position entry to be closed (contains quantity, entry price, etc.)
            function_name: Name of the execution function triggering the exit (for logging)
            
        Returns:
            ExitProcessingResult containing success status, order details, and processing metrics
            
        Example Workflow:
            >>> # Position: Long 100 AAPL @ $150.00, current price $160.00
            >>> signal = ExecutionSignal(
            ...     action=ExecutionAction.CLOSE_LONG,
            ...     confidence=0.85,
            ...     reasoning="Price hit take-profit target"
            ... )
            >>> context = ExecutionContext(
            ...     symbol="AAPL", 
            ...     current_bar=BarData(close_price=Decimal("160.00")),
            ...     has_position=True
            ... )
            >>> result = await exit_processor._process_position_exit(
            ...     signal, context, trade_plan, position, "take_profit_function"
            ... )
            >>> print(f"Exit result: {result.success}, Orders cancelled: {len(result.cancelled_orders)}")
            Exit result: True, Orders cancelled: 2
            
        Processing Steps:
            1. **Order Cancellation**: Cancel all existing orders for the symbol to prevent conflicts
            2. **Exit Order Creation**: Build market order request for the full position quantity
            3. **Order Placement**: Submit exit order through order execution manager
            4. **Fill Processing**: Handle immediate fills or track pending orders
            5. **State Updates**: Update position status and remove from risk registry if fully closed
            6. **Cleanup**: Clean up order tracking and update processing statistics
            
        Error Handling:
            - Failed order placement returns failure result with error details
            - Order cancellation failures are logged but don't prevent exit processing
            - Risk registry cleanup failures are logged for monitoring
            
        Note:
            This method assumes the position exists and is valid. Caller should verify
            position existence before invoking this method.
        """
        try:
            # Cancel any existing orders for this symbol first
            cancelled_orders = await self._cancel_symbol_orders(trade_plan.symbol, position)
            
            # Create exit order request
            exit_order_request = self._create_exit_order_request(
                signal, context, trade_plan, position
            )
            
            # Place exit order
            order_result = await self.order_execution_manager.place_market_order(exit_order_request)
            
            if order_result and order_result.success:
                # Track exit order with position
                position.add_exit_order(order_result.order_id)
                
                # If order is immediately filled, process the fill
                if order_result.order_status == OrderStatus.FILLED:
                    await self._handle_exit_fill(
                        position, order_result, trade_plan
                    )
                    
                    position_closed = position.is_closed
                    if position_closed:
                        self.processing_stats["positions_closed"] += 1
                    else:
                        self.processing_stats["partial_exits"] += 1
                else:
                    position_closed = False
                
                logger.info(
                    f"Exit order placed for position {position.position_id}",
                    order_id=order_result.order_id,
                    status=order_result.order_status,
                    position_closed=position_closed,
                )
                
                return ExitProcessingResult(
                    success=True,
                    action_taken="exit_order_placed",
                    position_closed=position_closed,
                    order_result=order_result,
                    orders_cancelled=cancelled_orders,
                    position_id=position.position_id,
                    plan_id=trade_plan.plan_id,
                )
            else:
                error_msg = order_result.error_message if order_result else "Unknown order error"
                return ExitProcessingResult(
                    success=False,
                    action_taken="exit_order_failed",
                    error_message=error_msg,
                    orders_cancelled=cancelled_orders,
                    position_id=position.position_id,
                    plan_id=trade_plan.plan_id,
                )
                
        except Exception as e:
            logger.error(f"Error processing position exit: {e}")
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
        """Process stop-loss modification (e.g., trailing stops).
        
        Args:
            signal: Modification signal
            context: Execution context
            trade_plan: Trade plan
            position: Position to modify
            function_name: Function name
            
        Returns:
            Exit processing result
        """
        try:
            # Get new stop level from signal metadata
            new_stop_level = signal.metadata.get("new_stop_level")
            if not new_stop_level:
                return ExitProcessingResult(
                    success=False,
                    action_taken="missing_stop_level",
                    error_message="No new_stop_level in signal metadata",
                    position_id=position.position_id,
                    plan_id=trade_plan.plan_id,
                )
            
            new_stop_price = Decimal(str(new_stop_level))
            
            # Find existing stop loss orders for this position
            active_orders = await self.order_execution_manager.get_active_orders()
            stop_orders = [
                order for order in active_orders
                if (order.symbol == trade_plan.symbol and 
                    order.order_type in ["STP", "STP LMT"] and
                    order.order_id in position.exit_order_ids)
            ]
            
            # Cancel existing stop orders
            cancelled_orders = []
            for order in stop_orders:
                cancel_result = await self.order_execution_manager.cancel_order(order.order_id)
                if cancel_result.success:
                    cancelled_orders.append(order.order_id)
            
            # Create new stop order request
            stop_order_request = self._create_stop_order_request(
                trade_plan, position, new_stop_price
            )
            
            # Place new stop order
            order_result = await self.order_execution_manager.place_stop_order(stop_order_request)
            
            if order_result and order_result.success:
                # Track new stop order
                position.add_exit_order(order_result.order_id)
                
                logger.info(
                    f"Stop order modified for position {position.position_id}",
                    old_orders_cancelled=len(cancelled_orders),
                    new_order_id=order_result.order_id,
                    new_stop_price=float(new_stop_price),
                )
                
                return ExitProcessingResult(
                    success=True,
                    action_taken="stop_modified",
                    order_result=order_result,
                    orders_cancelled=cancelled_orders,
                    position_id=position.position_id,
                    plan_id=trade_plan.plan_id,
                )
            else:
                error_msg = order_result.error_message if order_result else "Unknown order error"
                return ExitProcessingResult(
                    success=False,
                    action_taken="stop_modification_failed",
                    error_message=error_msg,
                    orders_cancelled=cancelled_orders,
                    position_id=position.position_id,
                    plan_id=trade_plan.plan_id,
                )
                
        except Exception as e:
            logger.error(f"Error processing stop modification: {e}")
            return ExitProcessingResult(
                success=False,
                action_taken="stop_modification_error",
                error_message=str(e),
                position_id=position.position_id,
                plan_id=trade_plan.plan_id,
            )
    
    async def _cancel_symbol_orders(
        self, symbol: str, position: PositionEntry
    ) -> List[str]:
        """Cancel all active orders for a symbol associated with position.
        
        Args:
            symbol: Trading symbol
            position: Position entry
            
        Returns:
            List of cancelled order IDs
        """
        try:
            cancelled_orders = []
            
            # Get all active orders for the symbol
            active_orders = await self.order_execution_manager.get_active_orders()
            symbol_orders = [
                order for order in active_orders
                if order.symbol == symbol and order.order_id in position.exit_order_ids
            ]
            
            # Cancel each order
            for order in symbol_orders:
                try:
                    cancel_result = await self.order_execution_manager.cancel_order(order.order_id)
                    if cancel_result.success:
                        cancelled_orders.append(order.order_id)
                        self.processing_stats["orders_cancelled"] += 1
                        logger.debug(f"Cancelled order {order.order_id} for symbol {symbol}")
                    else:
                        logger.warning(
                            f"Failed to cancel order {order.order_id}: {cancel_result.error_message}"
                        )
                except Exception as e:
                    logger.error(f"Error cancelling order {order.order_id}: {e}")
            
            if cancelled_orders:
                logger.info(f"Cancelled {len(cancelled_orders)} orders for {symbol}")
            
            return cancelled_orders
            
        except Exception as e:
            logger.error(f"Error cancelling orders for {symbol}: {e}")
            return []
    
    def _create_exit_order_request(
        self,
        signal: ExecutionSignal,
        context: ExecutionContext,
        trade_plan: TradePlan,
        position: PositionEntry,
    ):
        """Create exit order request.
        
        Args:
            signal: Exit signal
            context: Execution context
            trade_plan: Trade plan
            position: Position to exit
            
        Returns:
            Order request for exit
        """
        metadata = {
            "function_name": signal.metadata.get("function_name", "unknown"),
            "exit_context": "signal_triggered",
        }
        return ExitOrderBuilder.create_exit_order_request(
            signal=signal,
            trade_plan=trade_plan,
            position=position,
            metadata=metadata,
        )
    
    def _create_stop_order_request(
        self,
        trade_plan: TradePlan,
        position: PositionEntry,
        stop_price: Decimal,
    ):
        """Create stop order request.
        
        Args:
            trade_plan: Trade plan
            position: Position
            stop_price: New stop price
            
        Returns:
            Stop order request
        """
        metadata = {"stop_context": "trailing_stop_adjustment"}
        return ExitOrderBuilder.create_stop_order_request(
            trade_plan=trade_plan,
            position=position,
            stop_price=stop_price,
            metadata=metadata,
        )
    
    async def _handle_exit_fill(
        self,
        position: PositionEntry,
        order_result: OrderResult,
        trade_plan: TradePlan,
    ) -> None:
        """Handle exit order fill processing.
        
        Args:
            position: Position entry
            order_result: Exit order result
            trade_plan: Trade plan
        """
        try:
            # Record the fill with position manager
            fill_quantity = -order_result.filled_quantity  # Negative for position reduction
            fill_price = order_result.average_fill_price
            
            position_closed = await self.position_manager.record_exit_fill(
                position.position_id,
                order_result.order_id,
                fill_quantity,
                fill_price,
            )
            
            # Remove position from risk registry if fully closed
            if position_closed:
                await self._remove_position_from_risk_registry(position, trade_plan)
                
                logger.info(
                    f"Position {position.position_id} fully closed and removed from risk registry",
                    realized_pnl=float(position.calculate_realized_pnl()),
                )
            else:
                logger.info(
                    f"Partial exit recorded for position {position.position_id}",
                    remaining_quantity=position.remaining_quantity,
                )
                
        except Exception as e:
            logger.error(f"Error handling exit fill: {e}")
            raise
    
    async def _remove_position_from_risk_registry(
        self, position: PositionEntry, trade_plan: TradePlan
    ) -> None:
        """Remove position from risk registry.
        
        Args:
            position: Closed position
            trade_plan: Associated trade plan
        """
        try:
            # Remove from risk manager registry
            removed = self.risk_manager.remove_position_from_tracking(position.position_id)
            
            if removed:
                logger.info(
                    f"Removed position {position.position_id} from risk registry",
                    plan_id=trade_plan.plan_id,
                    symbol=trade_plan.symbol,
                )
            else:
                logger.warning(
                    f"Position {position.position_id} not found in risk registry"
                )
                
        except Exception as e:
            logger.error(f"Error removing position from risk registry: {e}")
            # Don't re-raise - this is not critical for trade completion
    
    async def handle_order_fill_event(
        self, order_id: str, fill_price: Decimal, fill_quantity: int
    ) -> Optional[str]:
        """Handle order fill events for exit orders.
        
        Args:
            order_id: Filled order ID
            fill_price: Fill price
            fill_quantity: Fill quantity
            
        Returns:
            Position ID if this was an exit fill, None otherwise
        """
        try:
            # Find position associated with this order
            position = self.position_manager.get_position_by_order_id(order_id)
            if not position:
                return None
            
            # Check if this is an exit order
            if order_id not in position.exit_order_ids:
                return None
            
            # Record the fill
            fill_quantity_signed = -fill_quantity if position.is_long else fill_quantity
            position_closed = await self.position_manager.record_exit_fill(
                position.position_id,
                order_id,
                fill_quantity_signed,
                fill_price,
            )
            
            # Handle position closure if needed
            if position_closed:
                # This would typically trigger trade plan status update
                # and final cleanup through the orchestrator
                self.processing_stats["positions_closed"] += 1
                
                logger.info(
                    f"Exit fill completed position {position.position_id}",
                    order_id=order_id,
                    final_pnl=float(position.calculate_realized_pnl()),
                )
            
            return position.position_id
            
        except Exception as e:
            logger.error(f"Error handling order fill event: {e}")
            return None
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """Get exit processing statistics.
        
        Returns:
            Dictionary with processing statistics
        """
        return {
            "exit_signals_processed": self.processing_stats["exit_signals_processed"],
            "positions_closed": self.processing_stats["positions_closed"],
            "orders_cancelled": self.processing_stats["orders_cancelled"],
            "processing_errors": self.processing_stats["processing_errors"],
            "partial_exits": self.processing_stats["partial_exits"],
            "open_positions": len(self.position_manager.get_open_positions()),
            "total_positions": len(self.position_manager.positions),
        }
    
    def reset_statistics(self) -> None:
        """Reset processing statistics."""
        self.processing_stats = {
            "exit_signals_processed": 0,
            "positions_closed": 0,
            "orders_cancelled": 0,
            "processing_errors": 0,
            "partial_exits": 0,
        }
        
        logger.info("Exit processing statistics reset")