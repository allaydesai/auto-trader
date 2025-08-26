"""Plan management utility functions for trade plan operations."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Any
import yaml

from rich.console import Console

from ..logging_config import get_logger
from ..models import TradePlan

# Import from split utility modules
from .risk_utils import (
    RiskCalculationCache,
    calculate_single_plan_risk,
    calculate_batch_plan_risks,
    get_portfolio_risk_summary,
    format_risk_indicator,
    create_portfolio_summary_panel
)
from .backup_utils import (
    BackupCreationError,
    BackupVerificationError,
    create_plan_backup,
    verify_backup,
    cleanup_old_backups,
    get_backup_info
)
from .archive_utils import (
    ArchiveError,
    organize_plans_for_archive,
    create_archive_preview_table,
    perform_plan_archiving,
    get_archive_statistics,
    restore_plan_from_archive
)
from .validation_utils import (
    ValidationError,
    validate_single_file,
    validate_all_plans,
    check_portfolio_risk_compliance,
    create_validation_summary_table,
    create_validation_details_table,
    format_validation_guidance
)
from .display_utils_extended import (
    format_plan_status,
    create_plans_listing_table,
    create_plan_update_preview_table,
    display_plan_risk_impact,
    create_statistics_overview_table,
    display_plan_insights,
    display_guidance_footer
)

console = Console()
logger = get_logger("management_utils", "cli")


class PlanManagementError(Exception):
    """Base exception for plan management operations."""
    pass


class PlanUpdateError(PlanManagementError):
    """Raised when plan update operations fail."""
    pass


class PlanLoadingError(PlanManagementError):
    """Raised when plan loading fails."""
    pass


class FileSystemError(PlanManagementError):
    """Raised when file system operations fail."""
    pass


class RiskCalculationError(PlanManagementError):
    """Raised when risk calculations fail."""
    pass


def _sort_plans_by_criteria(plans: List[TradePlan], sort_by: str, 
                           risk_results: Optional[List[Dict[str, Any]]] = None) -> List[TradePlan]:
    """
    Sort plans by the specified criteria.
    
    Args:
        plans: List of plans to sort
        sort_by: Sort criteria ('risk', 'date', 'symbol')
        risk_results: Optional risk results for risk-based sorting
        
    Returns:
        Sorted list of plans
    """
    if sort_by == "risk" and risk_results:
        # Create risk lookup
        risk_lookup = {r['plan_id']: r.get('risk_percent', Decimal('0')) 
                      for r in risk_results}
        return sorted(plans, key=lambda p: risk_lookup.get(p.plan_id, Decimal('0')), reverse=True)
    elif sort_by == "date":
        return sorted(plans, key=lambda p: p.plan_id, reverse=True)  # plan_id contains date
    elif sort_by == "symbol":
        return sorted(plans, key=lambda p: p.symbol)
    else:
        return plans


def _display_plan_listing_guidance(verbose: bool, status: Optional[str]) -> None:
    """
    Display helpful guidance for plan listing commands.
    
    Args:
        verbose: Whether verbose mode is active
        status: Status filter being used
    """
    guidance = []
    
    if not verbose:
        guidance.append("💡 Use --verbose for detailed information")
    
    if not status:
        guidance.append("🔍 Use --status to filter by plan status")
    
    guidance.append("📊 Use --sort-by to change ordering")
    
    if guidance:
        console.print("\n" + "\n".join(guidance), style="dim")


def process_plan_field_updates(plan: TradePlan, entry_level: Optional[float], 
                              stop_loss: Optional[float], take_profit: Optional[float],
                              risk_category: Optional[str]) -> Dict[str, Any]:
    """
    Process and validate plan field updates.
    
    Args:
        plan: Original plan object
        entry_level: New entry level (optional)
        stop_loss: New stop loss (optional) 
        take_profit: New take profit (optional)
        risk_category: New risk category (optional)
        
    Returns:
        Dictionary of validated updates
        
    Raises:
        PlanUpdateError: If validation fails
    """
    updates = {}
    
    # Process price field updates
    if entry_level is not None:
        if entry_level <= 0:
            raise PlanUpdateError("Entry level must be positive")
        updates['entry_level'] = Decimal(str(entry_level))
    
    if stop_loss is not None:
        if stop_loss <= 0:
            raise PlanUpdateError("Stop loss must be positive")
        updates['stop_loss'] = Decimal(str(stop_loss))
    
    if take_profit is not None:
        if take_profit <= 0:
            raise PlanUpdateError("Take profit must be positive")
        updates['take_profit'] = Decimal(str(take_profit))
    
    if risk_category is not None:
        valid_categories = ['small', 'normal', 'large']
        if risk_category.lower() not in valid_categories:
            raise PlanUpdateError(f"Risk category must be one of: {', '.join(valid_categories)}")
        updates['risk_category'] = risk_category.lower()
    
    # Validate that entry_level != stop_loss if both are being updated
    final_entry = updates.get('entry_level', plan.entry_level)
    final_stop = updates.get('stop_loss', plan.stop_loss)
    
    if final_entry == final_stop:
        raise PlanUpdateError("Entry level cannot equal stop loss")
    
    return updates


def _create_and_validate_updated_plan(plan: TradePlan, updates: Dict[str, Any]) -> TradePlan:
    """
    Create updated plan object and validate it.
    
    Args:
        plan: Original plan object
        updates: Dictionary of field updates
        
    Returns:
        Updated and validated plan object
        
    Raises:
        PlanUpdateError: If updated plan is invalid
    """
    # Create updated plan data
    plan_data = plan.model_dump()
    plan_data.update(updates)
    
    try:
        # Create new plan object with validation
        updated_plan = TradePlan(**plan_data)
        return updated_plan
        
    except Exception as e:
        raise PlanUpdateError(f"Updated plan validation failed: {e}")


def _display_update_preview_and_confirmation(plan_id: str, plan: TradePlan, updates: Dict[str, Any], 
                                           original_validation, updated_validation) -> bool:
    """
    Display update preview and get user confirmation.
    
    Args:
        plan_id: Plan ID being updated
        plan: Original plan object
        updates: Dictionary of field updates
        original_validation: Original risk validation
        updated_validation: Updated risk validation
        
    Returns:
        True if user confirms the update
    """
    # Display warning header
    console.print("⚠️ PLAN MODIFICATION WARNING", style="bold yellow")
    console.print()
    
    # Display update preview table
    preview_table = create_plan_update_preview_table(plan_id, plan, updates)
    console.print(preview_table)
    console.print()
    
    # Display risk impact if available
    if original_validation and updated_validation:
        display_plan_risk_impact(original_validation, updated_validation)
    
    # Display backup information
    timestamp = "YYYYMMDD_HHMMSS"  # Will be actual timestamp in implementation
    console.print(f"💾 Backup will be created: {plan_id}.backup.{timestamp}.yaml")
    console.print()
    
    # Get user confirmation
    response = console.input("Continue with modification? [y/N]: ")
    return response.lower() in ['y', 'yes']


def _perform_plan_update(plan_id: str, updated_plan: TradePlan, plans_dir: Path, 
                        backup_dir: Path) -> Path:
    """
    Perform the actual plan file update with backup.
    
    Args:
        plan_id: Plan ID being updated
        updated_plan: Updated plan object
        plans_dir: Directory containing plan files
        backup_dir: Directory for backups
        
    Returns:
        Path to created backup file
        
    Raises:
        PlanUpdateError: If update operation fails
    """
    plan_file = plans_dir / f"{plan_id}.yaml"
    
    if not plan_file.exists():
        raise PlanUpdateError(f"Plan file not found: {plan_file}")
    
    try:
        # Create backup first
        backup_path = create_plan_backup(plan_file, backup_dir)
        
    except BackupCreationError as e:
        raise FileSystemError(f"Failed to create backup before update: {e}")
    
    try:
        # Verify backup integrity
        verify_backup(plan_file, backup_path)
        
    except BackupVerificationError as e:
        # Clean up failed backup
        if backup_path.exists():
            try:
                backup_path.unlink()
            except Exception:
                pass
        raise FileSystemError(f"Backup verification failed, update cancelled: {e}")
    
    try:
        # Write updated plan
        with plan_file.open('w', encoding='utf-8') as f:
            # Convert Decimal to float for YAML compatibility
            plan_data = updated_plan.model_dump(mode='json')
            yaml.dump(plan_data, f, default_flow_style=False)
        
        logger.info(f"Updated plan {plan_id} successfully")
        return backup_path
        
    except (IOError, OSError, PermissionError) as e:
        raise FileSystemError(f"Failed to write updated plan file: {e}")


def _display_update_success(plan_id: str, updated_validation, backup_path: Path) -> None:
    """
    Display success message after plan update.
    
    Args:
        plan_id: Plan ID that was updated
        updated_validation: Updated risk validation result
        backup_path: Path to created backup file
    """
    console.print(f"✅ Plan {plan_id} updated successfully", style="bold green")
    
    if updated_validation and updated_validation.passed:
        console.print(f"📊 Position size recalculated: {updated_validation.position_size} shares")
    
    console.print(f"💾 Backup saved: {backup_path}")