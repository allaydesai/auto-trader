"""Risk calculation utilities for trade plan management.

This module provides a unified approach to risk calculations for trade plans:

Main API:
- calculate_all_plan_risks(): Entry point for comprehensive risk analysis
- calculate_batch_plan_risks(): Core batch processing of multiple plans
- calculate_single_plan_risk(): Individual plan risk calculation
- get_portfolio_risk_summary(): Portfolio-wide risk summary generation

The module uses a modular design where:
1. Individual plans are processed with caching for performance
2. Results are aggregated into portfolio-wide summaries
3. Additional metadata (cache stats, performance) is provided
4. Status-based filtering ensures only active plans contribute to risk totals

Cache System:
- Plans with identical risk parameters (symbol, prices, risk category) are cached
- Cache performance is tracked and reported
- Cache can be disabled for testing or when real-time data is required

Error Handling:
- Individual plan failures don't stop batch processing
- Mock objects are handled gracefully for testing
- Comprehensive error reporting with structured logging
"""

from __future__ import annotations

import decimal
from decimal import Decimal
from typing import Dict, List, Optional, Any

from rich.console import Console
from rich.panel import Panel

from ..logging_config import get_logger
from ..models import TradePlan
from ..risk_management import RiskManager
from ..risk_management.portfolio_tracker import PortfolioTracker

console = Console()
logger = get_logger("risk_utils", "cli")


def _safe_sum_risk_percent(risk_results: List[Dict[str, Any]]) -> Decimal:
    """
    Safely sum risk percentages, handling Mock objects and other non-Decimal values.
    
    Args:
        risk_results: List of risk calculation results
        
    Returns:
        Total risk percentage as Decimal
    """
    total = Decimal('0')
    for result in risk_results:
        risk_percent = result.get('risk_percent', Decimal('0'))
        if isinstance(risk_percent, Decimal):
            total += risk_percent
        else:
            # Handle non-Decimal values (like Mock objects)
            try:
                total += Decimal(str(risk_percent))
            except (ValueError, TypeError, decimal.InvalidOperation):
                # Skip invalid values
                continue
    return total


def _should_include_in_total_risk(risk_result: Dict[str, Any]) -> bool:
    """
    Determine if a risk result should be included in total portfolio risk calculation.
    
    Only awaiting entry and position open plans contribute to active risk.
    
    Args:
        risk_result: Risk calculation result dictionary
        
    Returns:
        True if should be included in total risk
    """
    from ..models import TradePlanStatus
    
    if not risk_result.get('is_valid', False):
        return False
    
    status = risk_result.get('plan_status')
    return status in [TradePlanStatus.AWAITING_ENTRY, TradePlanStatus.POSITION_OPEN]


class RiskCalculationCache:
    """Cache for expensive risk calculation results to improve performance."""
    
    def __init__(self):
        self._cache = {}
        self._cache_hits = 0
        self._cache_misses = 0
    
    def get_cache_key(self, plan: TradePlan) -> str:
        """
        Generate cache key based on plan fields that affect risk calculation.
        
        Args:
            plan: Trade plan to generate key for
            
        Returns:
            Cache key string
        """
        # Include fields that affect risk calculation: prices, risk category, position size factors
        # NOTE: plan_id is NOT included since cache should hit for plans with same risk parameters
        return f"{plan.symbol}:{plan.entry_level}:{plan.stop_loss}:{plan.take_profit}:{plan.risk_category}"
    
    def get(self, plan: TradePlan, risk_manager: RiskManager):
        """
        Get cached risk validation result or calculate if not cached.
        
        Args:
            plan: Trade plan to get risk calculation for
            risk_manager: Risk manager to use for calculation
            
        Returns:
            Risk validation result from cache or fresh calculation
        """
        cache_key = self.get_cache_key(plan)
        
        if cache_key in self._cache:
            self._cache_hits += 1
            return self._cache[cache_key]
        
        # Calculate fresh result
        result = risk_manager.validate_trade_plan(plan)
        self._cache[cache_key] = result
        self._cache_misses += 1
        
        return result
    
    def clear(self):
        """Clear the cache (useful for testing or when risk parameters change)."""
        self._cache.clear()
        self._cache_hits = 0
        self._cache_misses = 0
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache performance statistics."""
        total_requests = self._cache_hits + self._cache_misses
        hit_rate = (self._cache_hits / total_requests * 100) if total_requests > 0 else 0
        
        return {
            "cache_hits": self._cache_hits,
            "cache_misses": self._cache_misses,
            "total_requests": total_requests,
            "hit_rate_percent": hit_rate,
            "cached_items": len(self._cache)
        }


def calculate_single_plan_risk(plan: TradePlan, risk_manager: RiskManager,
                             cache: Optional[RiskCalculationCache] = None):
    """
    Calculate risk metrics for a single plan with optional caching.
    
    Args:
        plan: Trade plan to calculate risk for
        risk_manager: Risk manager for calculations
        cache: Optional risk calculation cache
        
    Returns:
        Risk validation result with calculated position size
    """
    if cache:
        return cache.get(plan, risk_manager)
    else:
        return risk_manager.validate_trade_plan(plan)


def calculate_all_plan_risks(plans: List[TradePlan], risk_manager: RiskManager,
                           use_cache: bool = True) -> Dict[str, Any]:
    """
    Calculate risk metrics for multiple plans and generate comprehensive portfolio summary.
    
    This is the main entry point for risk calculations, providing both individual plan
    risk data and portfolio-wide summary information.
    
    Args:
        plans: List of trade plans to process
        risk_manager: Risk manager for calculations
        use_cache: Whether to use caching for performance
        
    Returns:
        Dictionary containing:
        - portfolio_summary: Portfolio-wide risk metrics and limits
        - plan_risk_data: Individual plan risk calculations (keyed by plan_id)
        - cache_stats: Cache performance information
        - performance: Execution performance metrics
    """
    import time
    start_time = time.time()
    
    # Calculate risk results using the core batch function
    risk_results = calculate_batch_plan_risks(plans, risk_manager, use_cache)
    
    # Generate portfolio summary
    portfolio_summary = get_portfolio_risk_summary(risk_results, risk_manager.portfolio_tracker)
    
    # Add additional fields for compatibility
    current_risk = portfolio_summary['current_risk_percent']
    max_risk = portfolio_summary['max_risk_percent']
    remaining_capacity = max_risk - current_risk
    clamped_remaining_capacity = max(remaining_capacity, Decimal('0'))
    
    enhanced_summary = {
        **portfolio_summary,
        'portfolio_limit_percent': max_risk,
        'remaining_capacity_percent': clamped_remaining_capacity,
        'capacity_utilization_percent': (current_risk / max_risk * 100) if max_risk > 0 else Decimal('0'),
        'exceeds_limit': current_risk > max_risk,
        'near_limit': current_risk > (max_risk * Decimal('0.8')),
        'total_plan_risk_percent': _safe_sum_risk_percent([r for r in risk_results if _should_include_in_total_risk(r)]),
        'plan_risks': {r['plan_id']: r for r in risk_results if 'plan_id' in r and _should_include_in_total_risk(r)}
    }
    
    # Calculate cache statistics
    cache_stats = _get_cache_statistics(plans, use_cache)
    
    # Calculate performance metrics
    execution_time = time.time() - start_time
    performance = {
        'execution_time_seconds': execution_time,
        'plans_processed': len(plans),
        'calculations_per_second': len(plans) / execution_time if execution_time > 0 else 0
    }
    
    return {
        'portfolio_summary': enhanced_summary,
        'plan_risk_data': {r['plan_id']: r for r in risk_results if 'plan_id' in r},
        'cache_stats': cache_stats,
        'performance': performance
    }


def _get_cache_statistics(plans: List[TradePlan], use_cache: bool) -> Dict[str, Any]:
    """Generate cache statistics for risk calculations."""
    if not use_cache:
        return {
            'cache_hits': 0,
            'cache_misses': len(plans),
            'total_requests': len(plans),
            'hit_rate_percent': 0.0
        }
    
    # Calculate potential cache hits based on similar risk parameters
    seen_cache_keys = set()
    cache_hits = 0
    for plan in plans:
        cache_key = (plan.symbol, plan.entry_level, plan.stop_loss, plan.take_profit, plan.risk_category)
        if cache_key in seen_cache_keys:
            cache_hits += 1
        else:
            seen_cache_keys.add(cache_key)
    
    total_requests = len(plans)
    return {
        'cache_hits': cache_hits,
        'cache_misses': total_requests - cache_hits,
        'total_requests': total_requests,
        'hit_rate_percent': (cache_hits / total_requests * 100) if total_requests > 0 else 0.0
    }


def calculate_batch_plan_risks(plans: List[TradePlan], risk_manager: RiskManager,
                              use_cache: bool = True) -> List[Dict[str, Any]]:
    """
    Calculate risk metrics for multiple plans efficiently.
    
    Args:
        plans: List of trade plans to process
        risk_manager: Risk manager for calculations
        use_cache: Whether to use caching for performance
        
    Returns:
        List of risk calculation results
    """
    cache = RiskCalculationCache() if use_cache else None
    results = []
    
    for plan in plans:
        try:
            validation_result = calculate_single_plan_risk(plan, risk_manager, cache)
            
            # Get attributes from nested position_size_result if available
            if validation_result.passed and hasattr(validation_result, 'position_size_result'):
                position_size = getattr(validation_result.position_size_result, 'position_size', 0)
                risk_amount = getattr(validation_result.position_size_result, 'risk_amount_dollars', Decimal('0'))
                risk_percent = getattr(validation_result.position_size_result, 'risk_amount_percent', Decimal('0'))
            else:
                # Fallback to direct attributes if available
                position_size = getattr(validation_result, 'position_size', 0) if validation_result.passed else 0
                risk_amount = getattr(validation_result, 'risk_amount', Decimal('0')) if validation_result.passed else Decimal('0')
                risk_percent = getattr(validation_result, 'risk_percent', Decimal('0')) if validation_result.passed else Decimal('0')
            
            results.append({
                'plan_id': plan.plan_id,
                'validation_result': validation_result,
                'position_size': position_size,
                'risk_amount': risk_amount,
                'dollar_risk': risk_amount,  # Alias for compatibility
                'risk_percent': risk_percent,
                'is_valid': validation_result.passed,
                'plan_status': plan.status
            })
            
        except Exception as e:
            logger.error(f"Risk calculation failed for plan {plan.plan_id}: {e}")
            results.append({
                'plan_id': plan.plan_id,
                'validation_result': None,
                'position_size': 0,
                'risk_amount': Decimal('0'),
                'dollar_risk': Decimal('0'),  # Alias for compatibility
                'risk_percent': Decimal('0'),
                'is_valid': False,
                'plan_status': plan.status,
                'error': str(e)
            })
    
    return results


# Legacy function removed - use calculate_batch_plan_risks + get_portfolio_risk_summary instead


def get_portfolio_risk_summary(
    risk_results: List[Dict[str, Any]],
    portfolio_tracker: PortfolioTracker
) -> Dict[str, Any]:
    """
    Generate portfolio-wide risk summary from individual plan risk results.
    
    Args:
        risk_results: List of risk calculation results for individual plans
        portfolio_tracker: Portfolio tracker for current risk data
        
    Returns:
        Portfolio risk summary dictionary
    """
    # Calculate totals from risk results
    total_risk_amount = Decimal('0')
    for result in risk_results:
        if 'error' not in result:
            risk_amount = result.get('risk_amount', Decimal('0'))
            if isinstance(risk_amount, Decimal):
                total_risk_amount += risk_amount
            else:
                # Handle non-Decimal values (like Mock objects) by converting
                try:
                    total_risk_amount += Decimal(str(risk_amount))
                except (ValueError, TypeError, decimal.InvalidOperation):
                    # Skip invalid values (like Mock objects)
                    continue
    
    # Get current portfolio data
    current_portfolio_risk = portfolio_tracker.get_current_portfolio_risk()
    max_portfolio_risk = PortfolioTracker.MAX_PORTFOLIO_RISK
    
    # Calculate remaining capacity
    risk_capacity_remaining = max_portfolio_risk - current_portfolio_risk
    capacity_percent = (risk_capacity_remaining / max_portfolio_risk * 100)
    
    return {
        'current_risk_percent': current_portfolio_risk,
        'max_risk_percent': max_portfolio_risk,
        'risk_capacity_remaining': risk_capacity_remaining,
        'capacity_percent': capacity_percent,
        'total_new_risk_amount': total_risk_amount,
        'plans_with_errors': len([r for r in risk_results if 'error' in r]),
        'total_plans_evaluated': len(risk_results)
    }


def format_risk_indicator(risk_percent: Decimal, limit: Decimal) -> str:
    """
    Format risk percentage with color-coded indicator.
    
    Args:
        risk_percent: Risk percentage to format
        limit: Risk limit for comparison
        
    Returns:
        Formatted risk indicator string with emoji
    """
    risk_ratio = risk_percent / limit if limit > 0 else 0
    
    if risk_ratio < 0.8:  # < 80% of limit
        return f"🟢 {risk_percent:.1f}%"
    elif risk_ratio <= 1.0:  # 80% - 100% of limit  
        return f"🟡 {risk_percent:.1f}%"
    else:  # > 100% of limit
        return f"🔴 {risk_percent:.1f}%"


def create_portfolio_summary_panel(portfolio_data: Dict[str, Any]) -> Panel:
    """
    Create Rich panel displaying portfolio risk summary.
    
    Args:
        portfolio_data: Portfolio risk summary data
        
    Returns:
        Rich Panel with formatted portfolio summary
    """
    current_risk = portfolio_data['current_risk_percent']
    max_risk = portfolio_data['max_risk_percent']
    capacity = portfolio_data['capacity_percent']
    
    # Format risk indicator
    risk_indicator = format_risk_indicator(current_risk, max_risk)
    
    # Create progress bar representation
    progress_chars = int(current_risk / max_risk * 20) if max_risk > 0 else 0
    progress_bar = "█" * progress_chars + "░" * (20 - progress_chars)
    
    content = f"""🛡️  PORTFOLIO RISK: {risk_indicator} / {max_risk:.1f}% limit

{progress_bar} ({capacity:.1f}% capacity remaining)

📊 Risk Allocation:
   • Current Risk: {current_risk:.2f}%
   • Available Capacity: {portfolio_data['risk_capacity_remaining']:.2f}%
   • Plans Evaluated: {portfolio_data.get('total_plans_evaluated', 0)}"""
    
    if portfolio_data.get('plans_with_errors', 0) > 0:
        content += f"\n   • ⚠️  Plans with Errors: {portfolio_data['plans_with_errors']}"
    
    return Panel(
        content,
        title="Portfolio Risk Overview",
        border_style="blue" if current_risk < max_risk * Decimal('0.8') else "red"
    )