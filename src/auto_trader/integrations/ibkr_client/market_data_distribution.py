"""Market data distribution system for IBKR integration."""

from typing import List, Dict, Callable
from loguru import logger

from auto_trader.models.market_data import BarData


class MarketDataDistributor:
    """
    Handles distribution of market data to subscribers.
    
    Manages subscriber registration and safe callback execution
    for both regular subscribers and execution engine callbacks.
    """
    
    def __init__(self) -> None:
        """Initialize market data distributor."""
        self._subscribers: Dict[str, Callable[[BarData], None]] = {}
        self._distribution_errors = 0
    
    def add_subscriber(self, subscriber_id: str, callback: Callable[[BarData], None]) -> None:
        """
        Add a subscriber to receive market data updates.
        
        Args:
            subscriber_id: Unique identifier for the subscriber
            callback: Function to call with BarData updates
        """
        self._subscribers[subscriber_id] = callback
        logger.info(
            "Market data subscriber added",
            subscriber_id=subscriber_id,
            total_subscribers=len(self._subscribers)
        )
    
    def remove_subscriber(self, subscriber_id: str) -> bool:
        """
        Remove a subscriber from market data updates.
        
        Args:
            subscriber_id: Unique identifier for the subscriber
            
        Returns:
            True if subscriber was found and removed, False otherwise
        """
        if subscriber_id in self._subscribers:
            del self._subscribers[subscriber_id]
            logger.info(
                "Market data subscriber removed",
                subscriber_id=subscriber_id,
                total_subscribers=len(self._subscribers)
            )
            return True
        return False
    
    
    async def distribute_bar_data(self, bar_data: BarData) -> None:
        """
        Distribute bar data to all subscribers and execution engines.
        
        Args:
            bar_data: Bar data to distribute
        """
        distribution_count = 0
        errors = 0
        
        # Distribute to all subscribers
        for subscriber_id, callback in self._subscribers.items():
            success = self._safe_callback_execution(
                callback, bar_data, subscriber_id
            )
            if success:
                distribution_count += 1
            else:
                errors += 1
        
        
        # Update statistics and log results
        self._distribution_errors += errors
        
        if distribution_count > 0:
            logger.debug(
                "Market data distributed",
                symbol=bar_data.symbol,
                bar_size=bar_data.bar_size,
                distributed_to=distribution_count,
                errors=errors
            )
    
    def _safe_callback_execution(
        self, 
        callback: Callable[[BarData], None], 
        bar_data: BarData, 
        subscriber_id: str
    ) -> bool:
        """
        Safely execute callback with error handling.
        
        Args:
            callback: Callback function to execute
            bar_data: Bar data to pass to callback
            subscriber_id: Identifier for subscriber
            
        Returns:
            True if callback executed successfully, False otherwise
        """
        try:
            callback(bar_data)
            return True
        except Exception as e:
            logger.error(
                "Error in market data subscriber callback",
                subscriber_id=subscriber_id,
                error=str(e),
                symbol=bar_data.symbol,
                bar_size=bar_data.bar_size
            )
            return False
    
    def get_stats(self) -> Dict[str, int]:
        """Get distribution statistics."""
        return {
            "distribution_errors": self._distribution_errors,
            "subscribers_count": len(self._subscribers)
        }