"""Plan management utility functions for trade plan operations."""

from __future__ import annotations

import shutil
import yaml
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from ..logging_config import get_logger
from ..models import TradePlan, TradePlanLoader, TradePlanStatus, ValidationEngine
from ..risk_management import RiskManager
from ..risk_management.portfolio_tracker import PortfolioTracker

console = Console()
logger = get_logger("management_utils", "cli")


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


class PlanManagementError(Exception):
    """Base exception for plan management operations."""
    pass


class BackupCreationError(PlanManagementError):
    """Raised when plan backup creation fails."""
    pass


class BackupVerificationError(PlanManagementError):
    """Raised when backup verification fails."""
    pass


class PlanUpdateError(PlanManagementError):
    """Raised when plan update operation fails."""
    pass


class PlanLoadingError(PlanManagementError):
    """Raised when plan loading fails."""
    pass


class ValidationError(PlanManagementError):
    """Raised when plan validation fails."""
    pass


class FileSystemError(PlanManagementError):
    """Raised when file system operations fail."""
    pass


class RiskCalculationError(PlanManagementError):
    """Raised when risk calculations fail."""
    pass


def create_plan_backup(plan_path: Path, backup_dir: Path) -> Path:
    """
    Create timestamped backup of trade plan before modification.
    
    Args:
        plan_path: Path to original plan file
        backup_dir: Directory to store backup
        
    Returns:
        Path to created backup file
        
    Raises:
        BackupCreationError: If backup creation fails
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"{plan_path.stem}.backup.{timestamp}.yaml"
    backup_path = backup_dir / backup_filename
    
    try:
        backup_dir.mkdir(parents=True, exist_ok=True)
    except (OSError, PermissionError) as e:
        raise BackupCreationError(f"Failed to create backup directory {backup_dir}: {e}") from e
    
    try:
        shutil.copy2(plan_path, backup_path)
    except (OSError, PermissionError, shutil.SameFileError) as e:
        raise BackupCreationError(f"Failed to copy plan file to backup: {e}") from e
    
    logger.info("Plan backup created", source=str(plan_path), backup=str(backup_path))
    return backup_path


def verify_backup(original_path: Path, backup_path: Path) -> bool:
    """
    Verify backup integrity by comparing file content and metadata.
    
    Args:
        original_path: Path to original plan file
        backup_path: Path to backup file
        
    Returns:
        True if backup is valid
        
    Raises:
        BackupVerificationError: If backup verification fails
    """
    try:
        if not backup_path.exists():
            raise BackupVerificationError(f"Backup file does not exist: {backup_path}")
        
        if not backup_path.is_file():
            raise BackupVerificationError(f"Backup path is not a file: {backup_path}")
        
        # Compare file sizes
        original_size = original_path.stat().st_size
        backup_size = backup_path.stat().st_size
        
        if original_size != backup_size:
            raise BackupVerificationError(
                f"Backup size mismatch: original={original_size}, backup={backup_size}"
            )
        
        # Verify backup contains valid YAML content
        try:
            with open(backup_path, 'r') as f:
                backup_content = f.read()
            
            if not backup_content.strip():
                raise BackupVerificationError("Backup file is empty")
                
            # Basic YAML format check
            yaml.safe_load(backup_content)
            
        except yaml.YAMLError as e:
            raise BackupVerificationError(f"Backup contains invalid YAML: {e}") from e
        except IOError as e:
            raise BackupVerificationError(f"Cannot read backup file: {e}") from e
        
        logger.info("Backup verification passed", backup=str(backup_path))
        return True
        
    except (OSError, PermissionError) as e:
        raise BackupVerificationError(f"Cannot access backup file: {e}") from e


def _sort_plans_by_criteria(plans: List[TradePlan], sort_by: str, 
                           plan_risk_data: Optional[Dict[str, Any]] = None) -> List[TradePlan]:
    """
    Sort plans by specified criteria using pre-calculated risk data.
    
    Args:
        plans: List of trade plans to sort
        sort_by: Sort criteria ('risk', 'symbol', 'date')
        plan_risk_data: Pre-calculated risk data from calculate_all_plan_risks()
        
    Returns:
        Sorted list of trade plans
    """
    if sort_by == "risk" and plan_risk_data:
        # Use pre-calculated risk data for efficient sorting
        def get_risk(plan):
            risk_data = plan_risk_data.get(plan.plan_id, {})
            return risk_data.get("risk_percent", Decimal("0"))
        return sorted(plans, key=get_risk, reverse=True)
    elif sort_by == "symbol":
        return sorted(plans, key=lambda p: p.symbol)
    else:  # date (default)
        return sorted(plans, key=lambda p: p.plan_id, reverse=True)


def _display_plan_listing_guidance(verbose: bool, status: Optional[str]) -> None:
    """
    Display next-step guidance for plan listing command.
    
    Args:
        verbose: Whether verbose mode is enabled
        status: Current status filter
    """
    console.print()
    if not verbose:
        console.print("💡 Use --verbose for detailed information")
    if not status:
        console.print("💡 Use --status to filter plans by status")
    console.print("💡 Use validate-config to check plan health")


def process_plan_field_updates(plan: TradePlan, entry_level: Optional[float], stop_loss: Optional[float], 
                             take_profit: Optional[float], risk_category: Optional[str]) -> Dict[str, Any]:
    """
    Process and validate field updates for a trade plan.
    
    Args:
        plan: Original trade plan
        entry_level: New entry level (if provided)
        stop_loss: New stop loss (if provided)  
        take_profit: New take profit (if provided)
        risk_category: New risk category (if provided)
        
    Returns:
        Dictionary of field updates
        
    Raises:
        PlanUpdateError: If no valid updates provided
    """
    updates = {}
    if entry_level is not None:
        updates["entry_level"] = Decimal(str(entry_level))
    if stop_loss is not None:
        updates["stop_loss"] = Decimal(str(stop_loss))
    if take_profit is not None:
        updates["take_profit"] = Decimal(str(take_profit))
    if risk_category is not None:
        from ..models.trade_plan import RiskCategory
        updates["risk_category"] = RiskCategory(risk_category)
    
    if not updates:
        raise PlanUpdateError("No fields specified for update")
    
    return updates


def create_plan_update_preview_table(plan_id: str, plan: TradePlan, updates: Dict[str, Any]) -> Table:
    """
    Create Rich table showing plan update preview.
    
    Args:
        plan_id: Plan identifier
        plan: Original plan
        updates: Dictionary of field updates
        
    Returns:
        Rich table for display
    """
    preview_table = Table(title=f"📋 Plan Update Preview: {plan_id}")
    preview_table.add_column("Field", style="cyan")
    preview_table.add_column("Before", style="white")
    preview_table.add_column("After", style="yellow")
    
    for field, new_value in updates.items():
        old_value = getattr(plan, field)
        preview_table.add_row(
            field.replace("_", " ").title(),
            str(old_value),
            str(new_value),
        )
    
    return preview_table


def display_plan_risk_impact(original_validation, updated_validation) -> None:
    """
    Display risk impact of plan update.
    
    Args:
        original_validation: Risk validation result for original plan
        updated_validation: Risk validation result for updated plan
    """
    console.print("🛡️  Risk Impact:")
    if original_validation.passed and updated_validation.passed:
        orig_size = original_validation.position_size_result.position_size
        new_size = updated_validation.position_size_result.position_size
        orig_risk = original_validation.position_size_result.risk_amount_dollars
        new_risk = updated_validation.position_size_result.risk_amount_dollars
        
        console.print(f"   Position Size: {orig_size} → {new_size} shares")
        console.print(f"   Dollar Risk: ${orig_risk:.2f} → ${new_risk:.2f}")
        console.print("   Portfolio impact calculated after update")
    else:
        console.print("   ❌ Risk calculation failed - plan may have validation errors")


def organize_plans_for_archive(plans: List[TradePlan]) -> Dict[str, List[TradePlan]]:
    """
    Organize plans by archive path structure.
    
    Args:
        plans: List of plans to archive
        
    Returns:
        Dictionary mapping archive paths to plan lists
    """
    from collections import defaultdict
    archive_groups = defaultdict(list)
    
    for plan in plans:
        try:
            # Extract date from plan_id (format: SYMBOL_YYYYMMDD_NNN)
            date_part = plan.plan_id.split('_')[1]  # YYYYMMDD
            year = date_part[:4]
            month = date_part[4:6]
            archive_groups[f"{year}/{month}/{plan.status.value}"].append(plan)
        except (IndexError, ValueError):
            # Fallback for non-standard plan IDs
            current_date = datetime.now()
            fallback_path = f"{current_date.year}/{current_date.month:02d}/unknown_date"
            archive_groups[fallback_path].append(plan)
    
    return dict(archive_groups)


def create_archive_preview_table(archive_groups: Dict[str, List[TradePlan]]) -> tuple[Table, int]:
    """
    Create preview table for archive operations.
    
    Args:
        archive_groups: Dictionary mapping archive paths to plan lists
        
    Returns:
        Tuple of (Rich table, total plan count)
    """
    preview_table = Table(title="Plans to Archive")
    preview_table.add_column("Plan ID", style="cyan")
    preview_table.add_column("Status", style="white")
    preview_table.add_column("Archive Path", style="yellow")
    
    total_plans = 0
    for archive_path, plans in archive_groups.items():
        for plan in plans:
            preview_table.add_row(
                plan.plan_id,
                plan.status.value,
                archive_path,
            )
            total_plans += 1
    
    return preview_table, total_plans


def perform_plan_archiving(archive_groups: Dict[str, List[TradePlan]], 
                          plans_dir: Path, archive_dir: Path) -> int:
    """
    Perform actual plan archiving operation.
    
    Args:
        archive_groups: Dictionary mapping archive paths to plan lists
        plans_dir: Source plans directory
        archive_dir: Destination archive directory
        
    Returns:
        Number of successfully archived plans
    """
    archived_count = 0
    for archive_path, plans in archive_groups.items():
        # Create archive directory structure
        full_archive_path = archive_dir / archive_path
        full_archive_path.mkdir(parents=True, exist_ok=True)
        
        for plan in plans:
            source_file = plans_dir / f"{plan.plan_id}.yaml"
            dest_file = full_archive_path / f"{plan.plan_id}.yaml"
            
            if source_file.exists():
                # Move file to archive
                shutil.move(str(source_file), str(dest_file))
                archived_count += 1
                logger.debug(
                    "Plan archived",
                    plan_id=plan.plan_id,
                    source=str(source_file),
                    dest=str(dest_file),
                )
    
    return archived_count


def create_plan_statistics_tables(status_counts, symbol_counts, risk_counts, total_plans):
    """
    Create all statistics tables for plan analysis.
    
    Args:
        status_counts: Counter of plan statuses
        symbol_counts: Counter of plan symbols
        risk_counts: Counter of risk categories
        total_plans: Total number of plans
        
    Returns:
        Tuple of (status_table, symbol_table, risk_table)
    """
    # Plan Status Distribution
    status_table = Table(title="📈 Plan Status Distribution", show_header=True)
    status_table.add_column("Status", style="cyan", width=15)
    status_table.add_column("Count", style="white", width=8)
    status_table.add_column("Percentage", style="green", width=12)
    
    for status, count in status_counts.most_common():
        percentage = (count / total_plans) * 100
        formatted_status = status.replace('_', ' ').title()
        status_table.add_row(
            formatted_status,
            str(count),
            f"{percentage:.1f}%",
        )
    
    # Symbol Diversity Analysis
    symbol_table = Table(title="🎯 Symbol Diversity", show_header=True)
    symbol_table.add_column("Symbol", style="cyan", width=10)
    symbol_table.add_column("Plans", style="white", width=8)
    symbol_table.add_column("Portfolio %", style="yellow", width=12)
    
    for symbol, count in symbol_counts.most_common(10):  # Top 10 symbols
        percentage = (count / total_plans) * 100
        symbol_table.add_row(
            symbol,
            str(count),
            f"{percentage:.1f}%",
        )
    
    # Risk Category Distribution
    risk_table = Table(title="🛡️ Risk Category Distribution", show_header=True)
    risk_table.add_column("Risk Category", style="cyan", width=15)
    risk_table.add_column("Count", style="white", width=8)
    risk_table.add_column("Portfolio Impact", style="red", width=15)
    
    for risk_cat, count in risk_counts.most_common():
        percentage = (count / total_plans) * 100
        formatted_risk = risk_cat.replace('_', ' ').title()
        risk_table.add_row(
            formatted_risk,
            str(count),
            f"{percentage:.1f}%",
        )
    
    return status_table, symbol_table, risk_table


def display_plan_insights(total_plans: int, symbol_counts, portfolio_data: Dict[str, Any]) -> None:
    """
    Display key insights about plan portfolio.
    
    Args:
        total_plans: Total number of plans
        symbol_counts: Counter of symbols
        portfolio_data: Portfolio risk data
    """
    console.print("💡 KEY INSIGHTS:")
    console.print(f"   • Total Plans: {total_plans}")
    console.print(f"   • Unique Symbols: {len(symbol_counts)}")
    
    if symbol_counts:
        most_active = symbol_counts.most_common(1)[0]
        console.print(f"   • Most Active Symbol: {most_active[0]} ({most_active[1]} plans)")
    
    console.print(f"   • Portfolio Diversification: {len(symbol_counts)} symbols")
    
    if portfolio_data["exceeds_limit"]:
        console.print("   🚨 ALERT: Portfolio risk exceeds 10% limit!")
    elif portfolio_data["near_limit"]:
        console.print("   ⚠️  WARNING: Portfolio risk approaching limit")
    else:
        console.print("   ✅ Portfolio risk within safe limits")


def calculate_all_plan_risks(plans: List[TradePlan], risk_manager: RiskManager, 
                           use_cache: bool = True) -> Dict[str, Any]:
    """
    Pre-calculate risk validation results for all plans in a single pass.
    
    This function eliminates redundant risk calculations by computing all risk data once
    and returning it in a structured format for use by sorting, portfolio summary,
    and table creation functions.
    
    Args:
        plans: List of trade plans to calculate risks for
        risk_manager: Risk manager for calculations
        use_cache: Whether to use caching (default True)
        
    Returns:
        Dictionary containing all risk calculation results
    """
    import time
    start_time = time.time()
    
    # Initialize cache if using caching
    cache = RiskCalculationCache() if use_cache else None
    
    # Pre-calculate all risk validations
    plan_risk_data = {}
    active_plan_risks = {}
    total_plan_risk = Decimal("0.0")
    
    for plan in plans:
        # Get risk validation result (cached or fresh)
        if cache:
            validation_result = cache.get(plan, risk_manager)
        else:
            validation_result = risk_manager.validate_trade_plan(plan)
        
        # Store comprehensive risk data for this plan
        plan_risk_data[plan.plan_id] = {
            "plan": plan,
            "validation_result": validation_result,
            "risk_percent": Decimal("0"),
            "position_size": 0,
            "dollar_risk": Decimal("0"),
            "is_valid": validation_result.passed,
        }
        
        # Calculate risk metrics if validation passed
        if validation_result.passed and validation_result.position_size_result:
            risk_percent = validation_result.position_size_result.risk_amount_percent
            position_size = validation_result.position_size_result.position_size
            dollar_risk = validation_result.position_size_result.risk_amount_dollars
            
            plan_risk_data[plan.plan_id].update({
                "risk_percent": risk_percent,
                "position_size": position_size,
                "dollar_risk": dollar_risk,
            })
            
            # Track active plan risks for portfolio summary
            # NOTE: total_plan_risk is sum of individual plan risks, which may differ
            # from actual portfolio risk if positions are partially executed
            if plan.status in [TradePlanStatus.AWAITING_ENTRY, TradePlanStatus.POSITION_OPEN]:
                total_plan_risk += risk_percent
                active_plan_risks[plan.plan_id] = {
                    "risk_percent": risk_percent,
                    "position_size": position_size,
                    "dollar_risk": dollar_risk,
                }
    
    # Calculate portfolio summary data using ACTUAL portfolio risk from tracker
    current_risk = risk_manager.portfolio_tracker.get_current_portfolio_risk()
    portfolio_limit = PortfolioTracker.MAX_PORTFOLIO_RISK
    remaining_capacity = max(Decimal("0"), portfolio_limit - current_risk)
    utilization_percent = (current_risk / portfolio_limit) * 100
    
    # Calculate execution time
    execution_time = time.time() - start_time
    
    # Compile complete results
    results = {
        "plan_risk_data": plan_risk_data,  # Individual plan risk data
        "portfolio_summary": {
            "current_risk_percent": current_risk,
            "portfolio_limit_percent": portfolio_limit,
            "remaining_capacity_percent": remaining_capacity,
            "capacity_utilization_percent": utilization_percent,
            "total_plan_risk_percent": total_plan_risk,
            "plan_risks": active_plan_risks,
            "exceeds_limit": current_risk > portfolio_limit,
            "near_limit": current_risk > (portfolio_limit * Decimal("0.8")),
        },
        "cache_stats": cache.get_stats() if cache else None,
        "performance": {
            "execution_time_seconds": execution_time,
            "plans_processed": len(plans),
            "calculations_per_second": len(plans) / execution_time if execution_time > 0 else 0
        }
    }
    
    if cache:
        logger.debug("Risk calculation performance", 
                    execution_time=execution_time,
                    plans_processed=len(plans),
                    **cache.get_stats())
    
    return results


def get_portfolio_risk_summary(
    risk_manager: RiskManager,
    plans: List[TradePlan],
) -> Dict[str, Any]:
    """
    Calculate comprehensive portfolio risk summary for display.
    
    Args:
        risk_manager: Configured risk manager instance
        plans: List of all trade plans
        
    Returns:
        Dictionary with portfolio risk metrics
    """
    current_risk = risk_manager.portfolio_tracker.get_current_portfolio_risk()
    portfolio_limit = PortfolioTracker.MAX_PORTFOLIO_RISK  # Portfolio risk limit from config
    
    # Calculate total risk from all plans
    total_plan_risk = Decimal("0.0")
    plan_risks = {}
    
    for plan in plans:
        if plan.status in [TradePlanStatus.AWAITING_ENTRY, TradePlanStatus.POSITION_OPEN]:
            validation_result = risk_manager.validate_trade_plan(plan)
            if validation_result.passed and validation_result.position_size_result:
                plan_risk = validation_result.position_size_result.risk_amount_percent
                total_plan_risk += plan_risk
                plan_risks[plan.plan_id] = {
                    "risk_percent": plan_risk,
                    "position_size": validation_result.position_size_result.position_size,
                    "dollar_risk": validation_result.position_size_result.risk_amount_dollars,
                }
    
    remaining_capacity = max(Decimal("0"), portfolio_limit - current_risk)
    utilization_percent = (current_risk / portfolio_limit) * 100
    
    return {
        "current_risk_percent": current_risk,
        "portfolio_limit_percent": portfolio_limit,
        "remaining_capacity_percent": remaining_capacity,
        "capacity_utilization_percent": utilization_percent,
        "total_plan_risk_percent": total_plan_risk,
        "plan_risks": plan_risks,
        "exceeds_limit": current_risk > portfolio_limit,
        "near_limit": current_risk > (portfolio_limit * Decimal("0.8")),  # 80% warning threshold
    }


def format_risk_indicator(risk_percent: Decimal, limit: Decimal) -> str:
    """
    Create color-coded risk level indicator with emoji.
    
    Args:
        risk_percent: Current risk percentage
        limit: Maximum risk limit
        
    Returns:
        Formatted risk indicator with color and emoji
    """
    if risk_percent > limit:
        return f"🔴 {risk_percent:.1f}%"
    elif risk_percent > (limit * Decimal("0.8")):
        return f"🟡 {risk_percent:.1f}%"
    else:
        return f"🟢 {risk_percent:.1f}%"


def format_plan_status(status: TradePlanStatus) -> str:
    """
    Format plan status with appropriate emoji indicator.
    
    Args:
        status: Plan status enum value
        
    Returns:
        Formatted status string with emoji
    """
    status_map = {
        TradePlanStatus.AWAITING_ENTRY: "✅ awaiting_entry",
        TradePlanStatus.POSITION_OPEN: "🔄 position_open",
        TradePlanStatus.COMPLETED: "✅ completed",
        TradePlanStatus.CANCELLED: "⏹️ cancelled",
        TradePlanStatus.ERROR: "❌ error",
    }
    return status_map.get(status, f"❓ {status}")


def create_plans_table(
    plans: List[TradePlan],
    plan_risk_data: Optional[Dict[str, Any]] = None,
    show_verbose: bool = False,
) -> Table:
    """
    Create Rich table for plan display with pre-calculated risk data.
    
    Args:
        plans: List of trade plans to display
        plan_risk_data: Pre-calculated risk data from calculate_all_plan_risks()
        show_verbose: Whether to show verbose details
        
    Returns:
        Rich Table object for display
    """
    table = Table(title="📊 TRADE PLANS", show_header=True, header_style="bold blue")
    
    # Define columns based on verbosity
    table.add_column("Plan ID", style="cyan", width=17)
    table.add_column("Symbol", style="white", width=8)
    table.add_column("Status", style="white", width=15)
    table.add_column("Risk %", style="white", width=10)
    table.add_column("Position Size", style="white", width=13)
    
    if show_verbose:
        table.add_column("Entry", style="green", width=8)
        table.add_column("Stop", style="red", width=8)
        table.add_column("Target", style="blue", width=8)
        table.add_column("R:R", style="yellow", width=6)
    
    # Add rows for each plan
    for plan in plans:
        # Use pre-calculated risk data if available
        if plan_risk_data and plan.plan_id in plan_risk_data:
            risk_data = plan_risk_data[plan.plan_id]
            if risk_data["is_valid"]:
                risk_percent = risk_data["risk_percent"]
                position_size = risk_data["position_size"]
                risk_indicator = format_risk_indicator(risk_percent, PortfolioTracker.MAX_PORTFOLIO_RISK)
                size_display = f"{position_size} shares"
            else:
                risk_indicator = "❌ Invalid"
                size_display = "N/A"
        else:
            # Fallback for backward compatibility (should not happen in normal flow)
            risk_indicator = "❓ No Data"
            size_display = "N/A"
        
        # Basic columns
        row_data = [
            plan.plan_id,
            plan.symbol,
            format_plan_status(plan.status),
            risk_indicator,
            size_display,
        ]
        
        # Add verbose columns if requested
        if show_verbose:
            # Calculate risk-reward ratio
            risk_amount = abs(plan.entry_level - plan.stop_loss)
            reward_amount = abs(plan.take_profit - plan.entry_level)
            rr_ratio = reward_amount / risk_amount if risk_amount > 0 else Decimal("0")
            
            row_data.extend([
                f"${plan.entry_level:.2f}",
                f"${plan.stop_loss:.2f}",
                f"${plan.take_profit:.2f}",
                f"{rr_ratio:.1f}:1",
            ])
        
        table.add_row(*row_data)
    
    return table


def create_portfolio_summary_panel(portfolio_data: Dict[str, Any]) -> Panel:
    """
    Create Rich panel displaying portfolio risk summary.
    
    Args:
        portfolio_data: Portfolio metrics from get_portfolio_risk_summary()
        
    Returns:
        Rich Panel with portfolio overview
    """
    current_risk = portfolio_data["current_risk_percent"]
    limit = portfolio_data["portfolio_limit_percent"]
    remaining = portfolio_data["remaining_capacity_percent"]
    capacity_pct = portfolio_data["capacity_utilization_percent"]
    
    # Create risk indicator
    risk_indicator = format_risk_indicator(current_risk, limit)
    
    # Build summary text
    summary_lines = [
        f"🛡️  PORTFOLIO RISK: {risk_indicator} / {limit:.1f}% limit",
        f"📈 Capacity: {capacity_pct:.0f}% utilized ({remaining:.1f}% remaining)",
    ]
    
    # Add warning if near or over limit
    if portfolio_data["exceeds_limit"]:
        summary_lines.append("🚨 CRITICAL: Portfolio risk exceeds limit!")
    elif portfolio_data["near_limit"]:
        summary_lines.append("⚠️  WARNING: Approaching portfolio risk limit")
    
    summary_text = "\n".join(summary_lines)
    
    # Choose panel style based on risk level
    if portfolio_data["exceeds_limit"]:
        border_style = "red"
    elif portfolio_data["near_limit"]:
        border_style = "yellow"
    else:
        border_style = "green"
    
    return Panel(
        summary_text,
        title="Portfolio Risk Summary",
        border_style=border_style,
        padding=(0, 1),
    )


def validate_plans_comprehensive(
    plans_dir: Path,
    validation_engine: ValidationEngine,
    risk_manager: RiskManager,
    single_file: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Perform comprehensive validation of trade plans.
    
    Args:
        plans_dir: Directory containing trade plan files
        validation_engine: Validation engine instance
        risk_manager: Risk manager for portfolio validation
        single_file: Optional single file to validate
        
    Returns:
        Comprehensive validation results dictionary
    """
    results = {
        "files_checked": 0,
        "syntax_passed": 0,
        "business_logic_passed": 0,
        "portfolio_risk_passed": True,
        "file_results": {},
        "portfolio_risk_percent": Decimal("0.0"),
        "portfolio_limit_exceeded": False,
        "errors": [],
        "warnings": [],
    }
    
    # Determine files to validate
    if single_file:
        files_to_check = [single_file]
    else:
        files_to_check = list(plans_dir.glob("*.yaml")) + list(plans_dir.glob("*.yml"))
    
    results["files_checked"] = len(files_to_check)
    
    # Validate each file
    valid_plans = []
    for file_path in files_to_check:
        file_result = {
            "syntax_valid": False,
            "business_logic_valid": False,
            "errors": [],
            "warnings": [],
        }
        
        try:
            # YAML syntax validation
            validation_result = validation_engine.validate_file(file_path)
            
            if validation_result.is_valid:
                file_result["syntax_valid"] = True
                results["syntax_passed"] += 1
                
                # Load plan for business logic validation
                loader = TradePlanLoader(plans_dir)
                plan = loader.load_plan_from_file(file_path)
                
                if plan:
                    # Business logic validation via risk manager
                    risk_validation = risk_manager.validate_trade_plan(plan)
                    
                    if risk_validation.passed:
                        file_result["business_logic_valid"] = True
                        results["business_logic_passed"] += 1
                        valid_plans.append(plan)
                    else:
                        file_result["errors"].extend(risk_validation.errors)
                        file_result["warnings"].extend(risk_validation.warnings)
                        
            else:
                file_result["errors"] = validation_result.errors
                
        except (IOError, OSError, PermissionError) as e:
            file_result["errors"].append(f"File access error: {e}")
            logger.error("Plan validation failed - file access", file=str(file_path), error=str(e))
        except (yaml.YAMLError, UnicodeDecodeError) as e:
            file_result["errors"].append(f"File format error: {e}")
            logger.error("Plan validation failed - format error", file=str(file_path), error=str(e))
        except ValueError as e:
            file_result["errors"].append(f"Validation error: {e}")
            logger.error("Plan validation failed - validation error", file=str(file_path), error=str(e))
        
        results["file_results"][file_path.name] = file_result
    
    # Portfolio risk validation
    if valid_plans:
        portfolio_summary = get_portfolio_risk_summary(risk_manager, valid_plans)
        results["portfolio_risk_percent"] = portfolio_summary["total_plan_risk_percent"]
        results["portfolio_limit_exceeded"] = portfolio_summary["exceeds_limit"]
        results["portfolio_risk_passed"] = not portfolio_summary["exceeds_limit"]
    
    logger.info(
        "Plan validation completed",
        files_checked=results["files_checked"],
        syntax_passed=results["syntax_passed"],
        business_logic_passed=results["business_logic_passed"],
        portfolio_risk_passed=results["portfolio_risk_passed"],
    )
    
    return results


def _display_validation_results(results: Dict[str, Any], verbose: bool) -> None:
    """
    Display validation results with Rich formatting.
    
    Args:
        results: Validation results dictionary
        verbose: Whether to show verbose details
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    console.print(f"🔍 PLAN VALIDATION - {timestamp}")
    console.print()
    
    # Display validation summary
    files_checked = results["files_checked"]
    syntax_passed = results["syntax_passed"]
    logic_passed = results["business_logic_passed"]
    portfolio_passed = results["portfolio_risk_passed"]
    
    console.print(f"✅ Checking {files_checked} trade plan files...")
    console.print(f"✅ YAML syntax validation: {syntax_passed}/{files_checked} passed")
    
    if logic_passed == files_checked:
        console.print(f"✅ Business logic validation: {logic_passed}/{files_checked} passed")
    else:
        console.print(f"⚠️  Business logic validation: {logic_passed}/{files_checked} passed")
    
    if portfolio_passed:
        console.print("✅ Portfolio risk validation: PASSED")
    else:
        console.print("❌ Portfolio risk validation: FAILED")
        console.print(f"🚨 CRITICAL: Total portfolio risk would be {results['portfolio_risk_percent']:.1f}% (exceeds 10% limit)")
    
    console.print()


def _display_validation_file_details(file_results: Dict[str, Dict], verbose: bool) -> None:
    """
    Display file-specific validation details.
    
    Args:
        file_results: Dictionary of file validation results
        verbose: Whether to show verbose details
    """
    from rich.table import Table
    
    error_files = [f for f, r in file_results.items() if not r["syntax_valid"] or not r["business_logic_valid"]]
    
    if error_files or verbose:
        results_table = Table(title="📋 VALIDATION DETAILS")
        results_table.add_column("File", style="cyan")
        results_table.add_column("Status", style="white")
        results_table.add_column("Issues", style="white")
        
        for filename, file_result in file_results.items():
            if not file_result["syntax_valid"]:
                status = "❌ SYNTAX ERROR"
                issues = "; ".join(file_result["errors"][:2])  # Show first 2 errors
            elif not file_result["business_logic_valid"]:
                status = "❌ LOGIC ERROR"
                issues = "; ".join(file_result["errors"][:2])
            elif verbose:
                status = "✅ PASSED"
                issues = "No issues"
            else:
                continue  # Skip passed files if not verbose
            
            results_table.add_row(filename, status, issues)
        
        if results_table.rows:
            console.print(results_table)
            console.print()


def _display_validation_guidance(file_results: Dict[str, Dict], portfolio_passed: bool) -> None:
    """
    Display validation guidance and next steps.
    
    Args:
        file_results: Dictionary of file validation results
        portfolio_passed: Whether portfolio risk validation passed
    """
    error_files = [f for f, r in file_results.items() if not r["syntax_valid"] or not r["business_logic_valid"]]
    
    console.print("💡 Use --verbose for detailed error information")
    if error_files:
        console.print("🔧 Review and fix errors in failing files")
    if not portfolio_passed:
        console.print("⚠️  Reduce plan risk amounts to stay within 10% limit")


def _create_and_validate_updated_plan(plan: TradePlan, updates: Dict[str, Any]) -> TradePlan:
    """
    Create and validate an updated plan.
    
    Args:
        plan: Original trade plan
        updates: Dictionary of field updates
        
    Returns:
        Updated and validated trade plan
        
    Raises:
        PlanUpdateError: If plan validation fails
    """
    updated_plan_data = plan.model_dump()
    updated_plan_data.update(updates)
    
    from ..models.trade_plan import TradePlan
    try:
        return TradePlan(**updated_plan_data)
    except (ValueError, TypeError) as e:
        raise PlanUpdateError(f"Invalid field values: {e}") from e
    except Exception as e:
        raise PlanUpdateError(f"Unexpected error creating updated plan: {e}") from e


def _display_update_preview_and_confirmation(plan_id: str, plan: TradePlan, updates: Dict[str, Any], 
                                           original_validation, updated_validation, backup_dir: Path, force: bool) -> bool:
    """
    Display update preview and get user confirmation.
    
    Args:
        plan_id: Plan identifier
        plan: Original plan
        updates: Field updates
        original_validation: Original risk validation result
        updated_validation: Updated risk validation result  
        backup_dir: Backup directory path
        force: Whether to skip confirmation
        
    Returns:
        True if should proceed with update, False otherwise
    """
    console.print("⚠️  PLAN MODIFICATION WARNING")
    console.print()
    
    preview_table = create_plan_update_preview_table(plan_id, plan, updates)
    console.print(preview_table)
    console.print()
    
    display_plan_risk_impact(original_validation, updated_validation)
    console.print()
    console.print(f"💾 Backup will be created in: {backup_dir}")
    
    # Get confirmation unless forced
    if not force:
        import click
        console.print()
        confirm = click.confirm("Continue with modification?", default=False)
        if not confirm:
            console.print("[yellow]Plan update cancelled.[/yellow]")
            return False
    
    return True


def _perform_plan_update(plan_id: str, updated_plan: TradePlan, plans_dir: Path, backup_dir: Path) -> Path:
    """
    Perform the actual plan file update with backup verification.
    
    Args:
        plan_id: Plan identifier
        updated_plan: Updated plan to save
        plans_dir: Plans directory
        backup_dir: Backup directory
        
    Returns:
        Path to created backup file
        
    Raises:
        BackupVerificationError: If backup verification fails
        FileSystemError: If file operations fail
    """
    plan_file_path = plans_dir / f"{plan_id}.yaml"
    
    # Create backup first
    try:
        backup_path = create_plan_backup(plan_file_path, backup_dir)
    except BackupCreationError as e:
        raise FileSystemError(f"Failed to create backup before update: {e}") from e
    
    # Verify backup integrity before proceeding
    try:
        verify_backup(plan_file_path, backup_path)
        logger.info("Backup verification passed, proceeding with plan update", 
                   plan_id=plan_id, backup=str(backup_path))
    except BackupVerificationError as e:
        # Cleanup failed backup if verification fails
        try:
            backup_path.unlink()
        except OSError:
            pass  # Ignore cleanup failures
        raise FileSystemError(f"Backup verification failed, update cancelled: {e}") from e
    
    # Proceed with file update only after successful backup verification
    try:
        with open(plan_file_path, 'w') as f:
            yaml.dump(updated_plan.model_dump(mode='python'), f, default_flow_style=False)
    except (IOError, OSError, PermissionError, yaml.YAMLError) as e:
        raise FileSystemError(f"Failed to write updated plan file: {e}") from e
    
    logger.info("Plan update completed successfully", 
               plan_id=plan_id, backup=str(backup_path))
    return backup_path


def _display_update_success(plan_id: str, updated_validation, backup_path: Path) -> None:
    """
    Display success message for plan update.
    
    Args:
        plan_id: Plan identifier
        updated_validation: Updated risk validation result
        backup_path: Path to backup file
    """
    console.print()
    console.print(f"✅ Plan {plan_id} updated successfully")
    if updated_validation.passed:
        console.print(f"📊 Position size recalculated: {updated_validation.position_size_result.position_size} shares")
    console.print(f"💾 Backup saved: {backup_path}")