"""Core signal processing implementation."""

from typing import Dict, Any, Optional
from datetime import datetime, UTC

from loguru import logger

from auto_trader.models.execution import ExecutionSignal, ExecutionContext
from auto_trader.models.enums import ExecutionAction, OrderSide
from auto_trader.models.order import OrderResult
from auto_trader.models.trade_plan import TradePlan, TradePlanStatus
from auto_trader.trade_engine.order_execution_adapter import ExecutionOrderAdapter
from auto_trader.trade_engine.signal_validation import (
    SignalProcessingResult,
    SignalProcessorConfig,
    SignalValidator
)
from auto_trader.risk_management.risk_manager import RiskManager

from .statistics import SignalStatisticsManager


class SignalProcessor:
    """Processes execution signals with risk validation and order coordination.
    
    Responsible for taking execution signals from the execution functions and
    coordinating their processing through risk management and order execution.
    """
    
    def __init__(
        self,
        execution_adapter: ExecutionOrderAdapter,
        risk_manager: RiskManager,
        config: Optional[SignalProcessorConfig] = None,
    ):
        """Initialize signal processor.
        
        Args:
            execution_adapter: Order execution adapter
            risk_manager: Risk management system
            config: Processor configuration
        """
        self.execution_adapter = execution_adapter
        self.risk_manager = risk_manager
        self.config = config or SignalProcessorConfig()
        
        # Signal validation
        self.validator = SignalValidator(self.config)
        
        # Statistics management
        self.stats_manager = SignalStatisticsManager(self.config, self.validator)
        
        logger.info("SignalProcessor initialized")
    
    async def process_entry_signal(
        self,
        trade_plan: TradePlan,
        context: ExecutionContext,
        function_name: str,
        signal: Optional[ExecutionSignal] = None,
    ) -> SignalProcessingResult:
        """Process an entry execution signal with comprehensive validation and execution.
        
        Args:
            trade_plan: Trade plan requiring entry signal processing
            context: Execution context with current market data and position state
            function_name: Name of the execution function that generated the signal
            signal: Optional pre-generated execution signal
            
        Returns:
            SignalProcessingResult with execution status and order details
        """
        try:
            logger.info(
                f"Processing entry signal for plan {trade_plan.plan_id}",
                function=function_name,
                symbol=trade_plan.symbol,
            )
            
            self.stats_manager.record_signal_processed()
            
            # Validate plan status
            if trade_plan.status != TradePlanStatus.AWAITING_ENTRY:
                self.stats_manager.record_signal_rejected()
                return SignalProcessingResult(
                    success=False,
                    action_taken="invalid_plan_status",
                    error_message=f"Plan {trade_plan.plan_id} not awaiting entry",
                    plan_id=trade_plan.plan_id,
                )
            
            # Use provided signal or evaluate function
            if not signal:
                # Would evaluate execution function here if signal not provided
                logger.warning("No signal provided and function evaluation not implemented")
                return SignalProcessingResult(
                    success=False,
                    action_taken="no_signal_provided",
                    error_message="Signal required for processing",
                    plan_id=trade_plan.plan_id,
                )
            
            # Validate signal quality
            if not self._validate_signal_quality(signal, trade_plan):
                self.stats_manager.record_signal_rejected()
                return SignalProcessingResult(
                    success=False,
                    action_taken="signal_quality_failed",
                    error_message="Signal did not meet quality thresholds",
                    plan_id=trade_plan.plan_id,
                )
            
            # Check for duplicate signals
            if self._check_duplicate_signal(signal, trade_plan):
                self.stats_manager.record_signal_rejected()
                return SignalProcessingResult(
                    success=False,
                    action_taken="duplicate_signal",
                    error_message="Duplicate signal detected",
                    plan_id=trade_plan.plan_id,
                )
            
            # Process based on signal action
            if signal.action == ExecutionAction.ENTER_LONG:
                return await self._process_long_entry(trade_plan, context, signal, function_name)
            elif signal.action == ExecutionAction.ENTER_SHORT:
                return await self._process_short_entry(trade_plan, context, signal, function_name)
            else:
                self.stats_manager.record_signal_rejected()
                return SignalProcessingResult(
                    success=False,
                    action_taken="invalid_signal_action",
                    error_message=f"Invalid entry action: {signal.action}",
                    plan_id=trade_plan.plan_id,
                )
                
        except Exception as e:
            self.stats_manager.record_processing_error()
            logger.error(
                f"Error processing entry signal for plan {trade_plan.plan_id}: {e}",
                exc_info=True,
            )
            return SignalProcessingResult(
                success=False,
                action_taken="processing_error",
                error_message=str(e),
                plan_id=trade_plan.plan_id,
            )
    
    async def _process_long_entry(
        self,
        trade_plan: TradePlan,
        context: ExecutionContext,
        signal: ExecutionSignal,
        function_name: str,
    ) -> SignalProcessingResult:
        """Process long entry signal with risk validation and order placement."""
        try:
            logger.info(
                f"Processing long entry for plan {trade_plan.plan_id}",
                function=function_name,
            )
            
            # Risk validation
            if not await self._validate_risk(trade_plan, signal, OrderSide.BUY):
                self.stats_manager.record_risk_failure()
                return SignalProcessingResult(
                    success=False,
                    action_taken="risk_validation_failed",
                    error_message="Risk validation failed for long entry",
                    plan_id=trade_plan.plan_id,
                )
            
            # Create order request
            order_request = self.execution_adapter.order_request_builder.create_entry_order(
                symbol=trade_plan.symbol,
                side=OrderSide.BUY,
                signal=signal,
                context=context,
                function_name=function_name,
                position_size=trade_plan.calculated_position_size,
            )
            
            # Execute order
            order_result = await self.execution_adapter.order_execution_manager.place_market_order(order_request)
            
            if order_result.success:
                self.stats_manager.record_signal_executed()
                self._record_signal(signal, trade_plan)
                
                return SignalProcessingResult(
                    success=True,
                    action_taken="long_entry_placed",
                    order_result=order_result,
                    plan_id=trade_plan.plan_id,
                )
            else:
                self.stats_manager.record_signal_rejected()
                return SignalProcessingResult(
                    success=False,
                    action_taken="order_placement_failed",
                    error_message=order_result.error_message,
                    plan_id=trade_plan.plan_id,
                )
                
        except Exception as e:
            logger.error(f"Error processing long entry: {e}", exc_info=True)
            return SignalProcessingResult(
                success=False,
                action_taken="long_entry_error",
                error_message=str(e),
                plan_id=trade_plan.plan_id,
            )
    
    async def _process_short_entry(
        self,
        trade_plan: TradePlan,
        context: ExecutionContext,
        signal: ExecutionSignal,
        function_name: str,
    ) -> SignalProcessingResult:
        """Process short entry signal with risk validation and order placement."""
        try:
            logger.info(
                f"Processing short entry for plan {trade_plan.plan_id}",
                function=function_name,
            )
            
            # Risk validation
            if not await self._validate_risk(trade_plan, signal, OrderSide.SELL):
                self.stats_manager.record_risk_failure()
                return SignalProcessingResult(
                    success=False,
                    action_taken="risk_validation_failed",
                    error_message="Risk validation failed for short entry",
                    plan_id=trade_plan.plan_id,
                )
            
            # Create order request
            order_request = self.execution_adapter.order_request_builder.create_entry_order(
                symbol=trade_plan.symbol,
                side=OrderSide.SELL,
                signal=signal,
                context=context,
                function_name=function_name,
                position_size=trade_plan.calculated_position_size,
            )
            
            # Execute order
            order_result = await self.execution_adapter.order_execution_manager.place_market_order(order_request)
            
            if order_result.success:
                self.stats_manager.record_signal_executed()
                self._record_signal(signal, trade_plan)
                
                return SignalProcessingResult(
                    success=True,
                    action_taken="short_entry_placed",
                    order_result=order_result,
                    plan_id=trade_plan.plan_id,
                )
            else:
                self.stats_manager.record_signal_rejected()
                return SignalProcessingResult(
                    success=False,
                    action_taken="order_placement_failed",
                    error_message=order_result.error_message,
                    plan_id=trade_plan.plan_id,
                )
                
        except Exception as e:
            logger.error(f"Error processing short entry: {e}", exc_info=True)
            return SignalProcessingResult(
                success=False,
                action_taken="short_entry_error",
                error_message=str(e),
                plan_id=trade_plan.plan_id,
            )
    
    def _validate_signal_quality(self, signal: ExecutionSignal, trade_plan: TradePlan) -> bool:
        """Validate signal meets quality thresholds."""
        return self.validator.validate_signal_quality(signal, trade_plan)
    
    def _check_duplicate_signal(self, signal: ExecutionSignal, trade_plan: TradePlan) -> bool:
        """Check if signal is a duplicate."""
        return self.validator.check_duplicate_signal(signal, trade_plan)
    
    async def _validate_risk(
        self, trade_plan: TradePlan, signal: ExecutionSignal, order_side: OrderSide
    ) -> bool:
        """Validate risk for signal processing."""
        # For now, return True - risk validation will be handled by the risk manager
        # during order placement
        return True
    
    def _create_signal_data(self, signal: ExecutionSignal, function_name: str) -> Dict[str, Any]:
        """Create signal data record."""
        return {
            "action": signal.action.value,
            "confidence": signal.confidence,
            "reasoning": signal.reasoning,
            "function": function_name,
            "timestamp": datetime.now(UTC).isoformat(),
            "metadata": signal.metadata,
        }
    
    def _record_signal(self, signal: ExecutionSignal, trade_plan: TradePlan) -> None:
        """Record signal for tracking and duplicate detection."""
        self.validator.record_signal(signal, trade_plan)
    
    # Statistics methods delegating to statistics manager
    def get_processing_statistics(self) -> Dict[str, Any]:
        """Get signal processing statistics."""
        return self.stats_manager.get_processing_statistics()
    
    def reset_statistics(self) -> None:
        """Reset processing statistics."""
        self.stats_manager.reset_statistics()
    
    def clear_recent_signals(self) -> None:
        """Clear recent signals cache."""
        self.stats_manager.clear_recent_signals()