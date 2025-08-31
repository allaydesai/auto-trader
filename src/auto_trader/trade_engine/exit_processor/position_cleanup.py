"""Position cleanup operations for exit processing."""

from typing import Dict, Any
from loguru import logger

from auto_trader.models.trade_plan import TradePlan
from auto_trader.models.order import OrderResult
from auto_trader.trade_engine.position_entry import PositionEntry
from auto_trader.trade_engine.position_state_manager import PositionStateManager
from auto_trader.risk_management.risk_manager import RiskManager


class PositionCleanupManager:
    """Manages position cleanup after exit fills."""
    
    def __init__(
        self, 
        position_manager: PositionStateManager, 
        risk_manager: RiskManager
    ):
        """Initialize position cleanup manager.
        
        Args:
            position_manager: Position state management
            risk_manager: Risk management system
        """
        self.position_manager = position_manager
        self.risk_manager = risk_manager
        
    async def handle_exit_fill(
        self,
        position: PositionEntry,
        order_result: OrderResult,
        trade_plan: TradePlan,
        processing_stats: Dict[str, Any],
    ) -> None:
        """Handle exit order fill processing.
        
        Args:
            position: Position entry
            order_result: Exit order result
            trade_plan: Trade plan
            processing_stats: Statistics tracking dictionary
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
                
                # Update trade plan status
                await self.position_manager.update_trade_plan_status(
                    trade_plan.plan_id,
                    trade_plan.status.completed
                )
                
                processing_stats["positions_closed"] += 1
                
                logger.info(
                    f"Position fully closed for {trade_plan.symbol} - "
                    f"Plan {trade_plan.plan_id} completed"
                )
                
        except Exception as e:
            logger.error(f"Error handling exit fill for {position.position_id}: {e}")
            raise
            
    async def _remove_position_from_risk_registry(
        self, position: PositionEntry, trade_plan: TradePlan
    ) -> None:
        """Remove position from risk registry.
        
        Args:
            position: Position entry
            trade_plan: Trade plan
        """
        try:
            await self.risk_manager.remove_position(
                symbol=trade_plan.symbol,
                position_id=position.position_id,
            )
            logger.debug(f"Removed position {position.position_id} from risk registry")
            
        except Exception as e:
            logger.error(
                f"Error removing position {position.position_id} from risk registry: {e}"
            )
    
    async def handle_order_fill_event(
        self,
        order_result: OrderResult,
        processing_stats: Dict[str, Any],
    ) -> None:
        """Handle incoming order fill events for exit orders.
        
        Args:
            order_result: Order fill result
            processing_stats: Statistics tracking dictionary
        """
        try:
            # Find position by order ID
            position = self.position_manager.find_position_by_order_id(
                order_result.order_id
            )
            
            if not position:
                logger.warning(f"No position found for order {order_result.order_id}")
                return
            
            # Get associated trade plan
            trade_plan = await self.position_manager.get_trade_plan(position.plan_id)
            
            if not trade_plan:
                logger.warning(f"No trade plan found for position {position.position_id}")
                return
            
            # Process the fill
            await self.handle_exit_fill(position, order_result, trade_plan, processing_stats)
            
        except Exception as e:
            logger.error(f"Error handling order fill event {order_result.order_id}: {e}")