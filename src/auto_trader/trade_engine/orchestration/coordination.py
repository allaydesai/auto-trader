"""Component coordination logic for trade orchestration."""

from typing import Dict, List, Optional
from datetime import datetime, UTC
from loguru import logger

from auto_trader.models.trade_plan import TradePlan, TradePlanStatus
from auto_trader.models.market_data import BarData
from auto_trader.models.plan_loader import TradePlanLoader


class ComponentCoordinator:
    """Coordinates between orchestration components."""
    
    def __init__(self, trade_plan_loader: TradePlanLoader):
        """Initialize component coordinator.
        
        Args:
            trade_plan_loader: Trade plan loader
        """
        self.trade_plan_loader = trade_plan_loader
        
    async def load_active_trade_plans(self) -> Dict[str, TradePlan]:
        """Load all active trade plans from storage.

        Returns:
            Dictionary of active trade plans by plan_id
        """
        try:
            all_plans = self.trade_plan_loader.load_all_plans()
            
            # Filter for active plans
            active_plans = {
                plan_id: plan 
                for plan_id, plan in all_plans.items()
                if plan.status in [
                    TradePlanStatus.AWAITING_ENTRY,
                    TradePlanStatus.POSITION_OPEN
                ]
            }
            
            logger.info(f"Loaded {len(active_plans)} active trade plans")
            return active_plans
            
        except Exception as e:
            logger.error(f"Error loading active trade plans: {e}")
            return {}
    
    def filter_plans_for_symbol(
        self, plans: Dict[str, TradePlan], symbol: str
    ) -> List[TradePlan]:
        """Filter plans for a specific symbol.
        
        Args:
            plans: All available plans
            symbol: Target symbol
            
        Returns:
            List of plans for the symbol
        """
        return [
            plan for plan in plans.values()
            if plan.symbol == symbol
        ]
    
    def categorize_plans_by_status(
        self, plans: Dict[str, TradePlan]
    ) -> Dict[TradePlanStatus, List[TradePlan]]:
        """Categorize plans by their status.
        
        Args:
            plans: All plans to categorize
            
        Returns:
            Dictionary mapping status to plan lists
        """
        categorized = {}
        
        for plan in plans.values():
            if plan.status not in categorized:
                categorized[plan.status] = []
            categorized[plan.status].append(plan)
            
        return categorized
    
    async def persist_state(self, plans: Dict[str, TradePlan]) -> None:
        """Persist current state of trade plans.
        
        Args:
            plans: Plans to persist
        """
        try:
            for plan in plans.values():
                await self.trade_plan_loader.save_plan(plan)
            
            logger.debug(f"Persisted state for {len(plans)} plans")
            
        except Exception as e:
            logger.error(f"Error persisting state: {e}")


class MarketDataRouter:
    """Routes market data to appropriate processing functions."""
    
    def __init__(self):
        """Initialize market data router."""
        self.symbol_subscribers: Dict[str, List] = {}
        
    def register_symbol_subscriber(self, symbol: str, subscriber) -> None:
        """Register a subscriber for symbol updates.
        
        Args:
            symbol: Trading symbol
            subscriber: Object to receive updates
        """
        if symbol not in self.symbol_subscribers:
            self.symbol_subscribers[symbol] = []
        
        self.symbol_subscribers[symbol].append(subscriber)
        logger.debug(f"Registered subscriber for {symbol}")
        
    def route_market_data(self, bar_data: BarData) -> List:
        """Route market data to registered subscribers.
        
        Args:
            bar_data: Market data bar
            
        Returns:
            List of subscribers that received the data
        """
        symbol = bar_data.symbol
        
        if symbol in self.symbol_subscribers:
            subscribers = self.symbol_subscribers[symbol]
            logger.debug(f"Routing {symbol} data to {len(subscribers)} subscribers")
            return subscribers
        
        return []
    
    def get_subscription_stats(self) -> Dict[str, int]:
        """Get subscription statistics.
        
        Returns:
            Dictionary mapping symbols to subscriber counts
        """
        return {
            symbol: len(subscribers)
            for symbol, subscribers in self.symbol_subscribers.items()
        }


class PlanStatusTracker:
    """Tracks and manages plan status transitions."""
    
    def __init__(self):
        """Initialize plan status tracker."""
        self.status_history: Dict[str, List[Dict]] = {}
        
    def record_status_change(
        self,
        plan_id: str,
        old_status: TradePlanStatus,
        new_status: TradePlanStatus,
        context: Optional[str] = None
    ) -> None:
        """Record a plan status change.

        Args:
            plan_id: Plan identifier
            old_status: Previous status (can be enum or string due to use_enum_values)
            new_status: New status (can be enum or string due to use_enum_values)
            context: Optional context for the change
        """
        if plan_id not in self.status_history:
            self.status_history[plan_id] = []

        # Handle both enum and string values (use_enum_values=True in TradePlan)
        old_status_value = old_status.value if hasattr(old_status, 'value') else old_status
        new_status_value = new_status.value if hasattr(new_status, 'value') else new_status

        self.status_history[plan_id].append({
            "old_status": old_status_value,
            "new_status": new_status_value,
            "context": context,
            "timestamp": datetime.now(UTC).isoformat(),
        })

        logger.debug(
            f"Plan {plan_id} status change: {old_status_value} -> {new_status_value}"
        )
    
    def get_plan_history(self, plan_id: str) -> List[Dict]:
        """Get status history for a plan.
        
        Args:
            plan_id: Plan identifier
            
        Returns:
            List of status change records
        """
        return self.status_history.get(plan_id, [])
    
    def clear_plan_history(self, plan_id: str) -> None:
        """Clear history for a plan.
        
        Args:
            plan_id: Plan identifier
        """
        if plan_id in self.status_history:
            del self.status_history[plan_id]
            logger.debug(f"Cleared history for plan {plan_id}")