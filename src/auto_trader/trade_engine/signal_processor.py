"""Signal processing for trade lifecycle management."""

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
        
        # Performance metrics
        self.processing_stats = {
            "signals_processed": 0,
            "signals_executed": 0,
            "signals_rejected": 0,
            "risk_failures": 0,
            "processing_errors": 0,
        }
        
        logger.info("SignalProcessor initialized")
    
    async def process_entry_signal(
        self,
        signal: ExecutionSignal,
        context: ExecutionContext,
        trade_plan: TradePlan,
        function_name: str,
    ) -> SignalProcessingResult:
        """Process an entry execution signal.
        
        Args:
            signal: Execution signal to process
            context: Execution context
            trade_plan: Associated trade plan
            function_name: Name of generating function
            
        Returns:
            Signal processing result
        """
        start_time = datetime.now(UTC)
        
        try:
            logger.info(
                f"Processing entry signal for plan {trade_plan.plan_id}",
                action=signal.action.value,
                confidence=signal.confidence,
                function=function_name,
            )
            
            # Update statistics
            self.processing_stats["signals_processed"] += 1
            
            # Validate signal quality
            quality_check = self._validate_signal_quality(signal, trade_plan)
            if not quality_check.success:
                self.processing_stats["signals_rejected"] += 1
                return quality_check
            
            # Check for duplicate signals
            if self.config.enable_duplicate_detection:
                duplicate_check = self._check_duplicate_signal(
                    signal, trade_plan, function_name
                )
                if not duplicate_check.success:
                    self.processing_stats["signals_rejected"] += 1
                    return duplicate_check
            
            # Validate trade plan status
            if trade_plan.status != TradePlanStatus.AWAITING_ENTRY:
                return SignalProcessingResult(
                    success=False,
                    action_taken="rejected_invalid_status",
                    error_message=f"Plan {trade_plan.plan_id} not in awaiting_entry status: {trade_plan.status}",
                    plan_id=trade_plan.plan_id,
                )
            
            # Perform risk validation
            if self.config.enable_risk_validation:
                risk_result = await self._validate_risk(signal, trade_plan)
                if not risk_result.success:
                    self.processing_stats["risk_failures"] += 1
                    return risk_result
            
            # Process the signal based on action
            if signal.action == ExecutionAction.ENTER_LONG:
                return await self._process_long_entry(
                    signal, context, trade_plan, function_name
                )
            elif signal.action == ExecutionAction.ENTER_SHORT:
                return await self._process_short_entry(
                    signal, context, trade_plan, function_name
                )
            else:
                return SignalProcessingResult(
                    success=False,
                    action_taken="unsupported_action",
                    error_message=f"Entry signal processor does not support action: {signal.action}",
                    plan_id=trade_plan.plan_id,
                )
                
        except Exception as e:
            self.processing_stats["processing_errors"] += 1
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
        
        finally:
            processing_time = (datetime.now(UTC) - start_time).total_seconds()
            if processing_time > self.config.max_processing_time_seconds:
                logger.warning(
                    f"Signal processing took {processing_time:.2f}s, "
                    f"exceeding threshold of {self.config.max_processing_time_seconds}s"
                )
    
    async def _process_long_entry(
        self,
        signal: ExecutionSignal,
        context: ExecutionContext,
        trade_plan: TradePlan,
        function_name: str,
    ) -> SignalProcessingResult:
        """Process long entry signal.
        
        Args:
            signal: Execution signal
            context: Execution context  
            trade_plan: Trade plan
            function_name: Function name
            
        Returns:
            Processing result
        """
        try:
            # Create signal data for execution adapter
            signal_data = self._create_signal_data(
                signal, context, trade_plan, function_name, OrderSide.BUY
            )
            
            # Execute through adapter
            order_result = await self.execution_adapter.handle_execution_signal(signal_data)
            
            if order_result and order_result.success:
                self.processing_stats["signals_executed"] += 1
                
                # Record signal for duplicate detection
                self._record_signal(signal, trade_plan, function_name)
                
                logger.info(
                    f"Long entry executed for plan {trade_plan.plan_id}",
                    order_id=order_result.order_id,
                )
                
                return SignalProcessingResult(
                    success=True,
                    action_taken="long_entry_executed",
                    order_result=order_result,
                    risk_check_passed=True,
                    signal_confidence=signal.confidence,
                    plan_id=trade_plan.plan_id,
                )
            else:
                error_msg = order_result.error_message if order_result else "Unknown execution error"
                return SignalProcessingResult(
                    success=False,
                    action_taken="execution_failed",
                    error_message=error_msg,
                    order_result=order_result,
                    risk_check_passed=True,
                    signal_confidence=signal.confidence,
                    plan_id=trade_plan.plan_id,
                )
                
        except Exception as e:
            logger.error(f"Error processing long entry: {e}")
            return SignalProcessingResult(
                success=False,
                action_taken="processing_error",
                error_message=str(e),
                plan_id=trade_plan.plan_id,
            )
    
    async def _process_short_entry(
        self,
        signal: ExecutionSignal,
        context: ExecutionContext,
        trade_plan: TradePlan,
        function_name: str,
    ) -> SignalProcessingResult:
        """Process short entry signal.
        
        Args:
            signal: Execution signal
            context: Execution context
            trade_plan: Trade plan
            function_name: Function name
            
        Returns:
            Processing result
        """
        try:
            # Create signal data for execution adapter
            signal_data = self._create_signal_data(
                signal, context, trade_plan, function_name, OrderSide.SELL
            )
            
            # Execute through adapter
            order_result = await self.execution_adapter.handle_execution_signal(signal_data)
            
            if order_result and order_result.success:
                self.processing_stats["signals_executed"] += 1
                
                # Record signal for duplicate detection
                self._record_signal(signal, trade_plan, function_name)
                
                logger.info(
                    f"Short entry executed for plan {trade_plan.plan_id}",
                    order_id=order_result.order_id,
                )
                
                return SignalProcessingResult(
                    success=True,
                    action_taken="short_entry_executed",
                    order_result=order_result,
                    risk_check_passed=True,
                    signal_confidence=signal.confidence,
                    plan_id=trade_plan.plan_id,
                )
            else:
                error_msg = order_result.error_message if order_result else "Unknown execution error"
                return SignalProcessingResult(
                    success=False,
                    action_taken="execution_failed",
                    error_message=error_msg,
                    order_result=order_result,
                    risk_check_passed=True,
                    signal_confidence=signal.confidence,
                    plan_id=trade_plan.plan_id,
                )
                
        except Exception as e:
            logger.error(f"Error processing short entry: {e}")
            return SignalProcessingResult(
                success=False,
                action_taken="processing_error",
                error_message=str(e),
                plan_id=trade_plan.plan_id,
            )
    
    def _validate_signal_quality(
        self, signal: ExecutionSignal, trade_plan: TradePlan
    ) -> SignalProcessingResult:
        """Validate signal quality and filtering criteria.
        
        Args:
            signal: Execution signal
            trade_plan: Trade plan
            
        Returns:
            Validation result
        """
        # Use validator for quality checks
        if not self.validator.validate_signal_quality(signal, trade_plan):
            return SignalProcessingResult(
                success=False,
                action_taken="rejected_quality_check",
                error_message=f"Signal quality validation failed",
                signal_confidence=signal.confidence,
                plan_id=trade_plan.plan_id,
            )
        
        # Check signal action validity for entry
        if signal.action not in [ExecutionAction.ENTER_LONG, ExecutionAction.ENTER_SHORT]:
            return SignalProcessingResult(
                success=False,
                action_taken="rejected_invalid_action",
                error_message=f"Signal action {signal.action} not valid for entry processing",
                signal_confidence=signal.confidence,
                plan_id=trade_plan.plan_id,
            )
        
        return SignalProcessingResult(
            success=True,
            action_taken="quality_check_passed",
            signal_confidence=signal.confidence,
            plan_id=trade_plan.plan_id,
        )
    
    def _check_duplicate_signal(
        self, signal: ExecutionSignal, trade_plan: TradePlan, function_name: str
    ) -> SignalProcessingResult:
        """Check for duplicate signals within time window.
        
        Args:
            signal: Execution signal
            trade_plan: Trade plan
            function_name: Function name
            
        Returns:
            Duplicate check result
        """
        # Use validator for duplicate checks
        if self.validator.check_duplicate_signal(signal, trade_plan):
            return SignalProcessingResult(
                success=False,
                action_taken="rejected_duplicate",
                error_message="Duplicate signal detected within time window",
                signal_confidence=signal.confidence,
                plan_id=trade_plan.plan_id,
            )
        
        return SignalProcessingResult(
            success=True,
            action_taken="duplicate_check_passed",
            signal_confidence=signal.confidence,
            plan_id=trade_plan.plan_id,
        )
    
    async def _validate_risk(
        self, signal: ExecutionSignal, trade_plan: TradePlan
    ) -> SignalProcessingResult:
        """Validate signal against risk management rules.
        
        Args:
            signal: Execution signal
            trade_plan: Trade plan
            
        Returns:
            Risk validation result
        """
        try:
            # Validate trade plan through risk manager
            risk_result = self.risk_manager.validate_trade_plan(trade_plan)
            
            if not risk_result.is_valid:
                error_message = "; ".join(risk_result.errors)
                
                logger.warning(
                    f"Risk validation failed for plan {trade_plan.plan_id}",
                    errors=risk_result.errors,
                )
                
                return SignalProcessingResult(
                    success=False,
                    action_taken="rejected_risk_validation",
                    error_message=f"Risk validation failed: {error_message}",
                    risk_check_passed=False,
                    signal_confidence=signal.confidence,
                    plan_id=trade_plan.plan_id,
                )
            
            return SignalProcessingResult(
                success=True,
                action_taken="risk_validation_passed",
                risk_check_passed=True,
                signal_confidence=signal.confidence,
                plan_id=trade_plan.plan_id,
            )
            
        except Exception as e:
            logger.error(f"Error during risk validation: {e}")
            return SignalProcessingResult(
                success=False,
                action_taken="risk_validation_error",
                error_message=f"Risk validation error: {str(e)}",
                risk_check_passed=False,
                signal_confidence=signal.confidence,
                plan_id=trade_plan.plan_id,
            )
    
    def _create_signal_data(
        self,
        signal: ExecutionSignal,
        context: ExecutionContext,
        trade_plan: TradePlan,
        function_name: str,
        order_side: OrderSide,
    ) -> Dict[str, Any]:
        """Create signal data for execution adapter.
        
        Args:
            signal: Execution signal
            context: Execution context
            trade_plan: Trade plan
            function_name: Function name
            order_side: Order side
            
        Returns:
            Signal data dictionary
        """
        return {
            "function_name": function_name,
            "symbol": trade_plan.symbol,
            "timeframe": context.timeframe,
            "signal": signal,
            "context": context,
            "timestamp": datetime.now(UTC),
            "plan_id": trade_plan.plan_id,
            "order_side": order_side,
            "trade_plan": trade_plan,
        }
    
    def _record_signal(
        self, signal: ExecutionSignal, trade_plan: TradePlan, function_name: str
    ) -> None:
        """Record signal for duplicate detection.
        
        Args:
            signal: Execution signal
            trade_plan: Trade plan
            function_name: Function name
        """
        self.validator.record_signal(signal, trade_plan)
    
    def get_processing_statistics(self) -> Dict[str, Any]:
        """Get signal processing statistics.
        
        Returns:
            Dictionary with processing statistics
        """
        total_signals = self.processing_stats["signals_processed"]
        execution_rate = (
            self.processing_stats["signals_executed"] / total_signals * 100
            if total_signals > 0 else 0
        )
        
        stats = {
            "total_processed": total_signals,
            "executed": self.processing_stats["signals_executed"],
            "rejected": self.processing_stats["signals_rejected"],
            "risk_failures": self.processing_stats["risk_failures"],
            "processing_errors": self.processing_stats["processing_errors"],
            "execution_rate_percent": round(execution_rate, 2),
            "config": {
                "risk_validation_enabled": self.config.enable_risk_validation,
                "minimum_confidence": self.config.minimum_confidence_threshold,
                "signal_filtering_enabled": self.config.enable_signal_filtering,
                "duplicate_detection_enabled": self.config.enable_duplicate_detection,
            },
        }
        
        # Add validator statistics
        stats["validator"] = self.validator.get_validation_statistics()
        return stats
    
    def reset_statistics(self) -> None:
        """Reset processing statistics."""
        self.processing_stats = {
            "signals_processed": 0,
            "signals_executed": 0,
            "signals_rejected": 0,
            "risk_failures": 0,
            "processing_errors": 0,
        }
        
        logger.info("Signal processing statistics reset")
    
    def clear_recent_signals(self) -> None:
        """Clear recent signals cache."""
        self.validator.clear_recent_signals()
        logger.info("Recent signals cache cleared")