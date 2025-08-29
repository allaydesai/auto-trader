"""Order execution integration adapter for execution function framework."""

from typing import Dict, Any, Optional
from datetime import datetime, UTC

from loguru import logger

from auto_trader.models.execution import ExecutionSignal
from auto_trader.models.enums import ExecutionAction
from auto_trader.models.order import OrderResult
from auto_trader.models.trade_plan import RiskCategory
from auto_trader.integrations.ibkr_client.order_execution_manager import (
    OrderExecutionManager,
)
from auto_trader.trade_engine.circuit_breaker import CircuitBreakerManager
from auto_trader.trade_engine.order_request_builder import OrderRequestBuilder
from auto_trader.trade_engine.signal_handler import SignalHandler


class ExecutionOrderAdapter:
    """Adapter connecting execution signals to order execution system.
    
    Converts execution function signals into order requests and manages
    the integration between the execution framework and order system.
    Uses composition pattern for maintainability and separation of concerns.
    """
    
    def __init__(
        self,
        order_execution_manager: OrderExecutionManager,
        default_risk_category: RiskCategory = RiskCategory.NORMAL,
    ):
        """Initialize execution order adapter.
        
        Args:
            order_execution_manager: Order execution manager from Story 2.3
            default_risk_category: Default risk category for position sizing
        """
        # Initialize components using composition pattern
        self.circuit_breaker = CircuitBreakerManager(
            max_consecutive_failures=5,
            reset_timeout=0.05,  # Fast reset for testing
            enabled=True,
        )
        
        self.order_request_builder = OrderRequestBuilder(
            default_risk_category=default_risk_category,
        )
        
        self.signal_handler = SignalHandler(
            order_execution_manager=order_execution_manager,
            order_request_builder=self.order_request_builder,
            circuit_breaker=self.circuit_breaker,
        )
        
        # Configuration for adapter
        self.config = {
            "default_risk_category": default_risk_category,
            "order_timeout_seconds": 300,  # 5 minutes
            "max_retry_attempts": 3,
            "circuit_breaker_enabled": True,
        }
        
        logger.info("ExecutionOrderAdapter initialized with composition pattern")
    
    # Backward compatibility properties for tests
    @property
    def order_execution_manager(self):
        """Access order execution manager for backward compatibility."""
        return self.signal_handler.order_execution_manager
    
    @order_execution_manager.setter
    def order_execution_manager(self, value):
        """Set order execution manager for backward compatibility."""
        self.signal_handler.order_execution_manager = value
    
    @property
    def default_risk_category(self):
        """Access default risk category for backward compatibility."""
        return self.config["default_risk_category"]
    
    @property
    def execution_orders(self):
        """Access execution orders for backward compatibility."""
        return self.signal_handler.execution_orders
    
    @property
    def consecutive_failures(self):
        """Access circuit breaker failures for backward compatibility."""
        return self.circuit_breaker.consecutive_failures
    
    @property
    def max_consecutive_failures(self):
        """Access max consecutive failures for backward compatibility."""
        return self.circuit_breaker.max_consecutive_failures
    
    @property
    def circuit_breaker_open(self):
        """Access circuit breaker state for backward compatibility."""
        return self.circuit_breaker.circuit_breaker_open
    
    async def handle_execution_signal(self, signal_data: Dict[str, Any]) -> Optional[OrderResult]:
        """Handle execution signal and convert to order if appropriate.
        
        Args:
            signal_data: Signal data from execution framework containing:
                - function_name: Name of execution function
                - symbol: Trading symbol
                - timeframe: Execution timeframe
                - signal: ExecutionSignal object
                - context: ExecutionContext object
                - timestamp: Signal generation time
                
        Returns:
            OrderResult if order was placed, None if no order needed
        """
        try:
            # Check circuit breaker state
            if self.config.get("circuit_breaker_enabled", True):
                self.circuit_breaker.check_state()
                
            signal = signal_data["signal"]
            context = signal_data["context"]
            function_name = signal_data["function_name"]
            
            logger.info(
                f"Processing execution signal from {function_name}",
                action=signal.action.value,
                confidence=signal.confidence,
                symbol=context.symbol,
            )
            
            # Route based on signal action using signal handler
            result = None
            if signal.action == ExecutionAction.ENTER_LONG:
                result = await self.signal_handler.handle_entry_long(signal, context, function_name)
            elif signal.action == ExecutionAction.ENTER_SHORT:
                result = await self.signal_handler.handle_entry_short(signal, context, function_name)
            elif signal.action == ExecutionAction.EXIT:
                result = await self.signal_handler.handle_exit(signal, context, function_name)
            elif signal.action == ExecutionAction.MODIFY_STOP:
                result = await self.signal_handler.handle_modify_stop(signal, context, function_name)
            else:
                # No action needed
                return None
            
            # Track success/failure for circuit breaker
            if result and result.success:
                self.circuit_breaker.record_success()
            elif result and not result.success:
                self.circuit_breaker.record_failure()
                
            return result
                
        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(
                f"Error handling execution signal: {e}",
                signal_data=signal_data,
                exc_info=True,
            )
            raise  # Re-raise for circuit breaker to detect
    
    
    
    
    
    
    
    
    def get_execution_orders(self) -> Dict[str, str]:
        """Get mapping of execution IDs to order IDs.
        
        Returns:
            Dictionary mapping execution IDs to order IDs
        """
        return self.signal_handler.get_execution_orders()
    
    def get_stats(self) -> Dict[str, Any]:
        """Get adapter statistics.
        
        Returns:
            Dictionary with adapter statistics
        """
        execution_orders = self.signal_handler.get_execution_orders()
        return {
            "tracked_orders": len(execution_orders),
            "default_risk_category": self.config["default_risk_category"].value,
            "config": self.config,
            "circuit_breaker_state": self.circuit_breaker.get_stats(),
        }
    
    def reset_circuit_breaker(self) -> None:
        """Reset circuit breaker state for testing or manual recovery.
        
        This method allows manual reset of the circuit breaker state,
        useful for testing scenarios or administrative reset.
        """
        self.circuit_breaker.reset()
    
    # Backward compatibility helper methods for tests
    def _map_confidence_to_risk_category(self, confidence: float):
        """Map confidence to risk category for test compatibility."""
        return self.order_request_builder._map_confidence_to_risk_category(confidence)
    
    def _generate_execution_id(self, function_name: str, context):
        """Generate execution ID for test compatibility."""
        return self.signal_handler._generate_execution_id(function_name, context)
    
    
        
