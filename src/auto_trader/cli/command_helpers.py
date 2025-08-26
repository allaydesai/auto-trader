"""Common helper functions for management commands."""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Dict, List, Optional, Any

import click
from rich.console import Console

from ..logging_config import get_logger
from ..models import TradePlan, TradePlanLoader, TradePlanStatus
from ..risk_management import RiskManager
from config import ConfigLoader
from .management_utils import (
    PlanLoadingError, RiskCalculationError, BackupCreationError, 
    BackupVerificationError, FileSystemError, ArchiveError, 
    ValidationError, PlanManagementError,
    _display_plan_listing_guidance, process_plan_field_updates,
    _create_and_validate_updated_plan, _perform_plan_update,
    _display_update_success
)
from .risk_utils import create_portfolio_summary_panel, get_portfolio_risk_summary
from .display_utils_extended import create_plans_listing_table, create_statistics_overview_table, display_plan_insights
from .archive_utils import organize_plans_for_archive, create_archive_preview_table, perform_plan_archiving

console = Console()
logger = get_logger("command_helpers", "cli")


def _get_risk_manager() -> RiskManager:
    """Get properly configured risk manager from user preferences."""
    from config import Settings
    settings = Settings()
    config_loader = ConfigLoader(settings)
    user_prefs = config_loader.load_user_preferences()
    return RiskManager(account_value=user_prefs.account_value)


def _load_and_filter_plans(loader: TradePlanLoader, status: Optional[str]) -> List[TradePlan]:
    """Load and filter plans by status."""
    # Always load all plans first to ensure _loaded_plans is populated
    plans_dict = loader.load_all_plans()
    
    if status:
        # Now filter by status from the loaded plans
        return loader.get_plans_by_status(TradePlanStatus(status))
    else:
        return list(plans_dict.values())


def _display_plans_listing_output(plans: List[TradePlan], plan_risk_data: Dict[str, Dict], 
                                 portfolio_data: Dict, verbose: bool, status: Optional[str]) -> None:
    """Display the formatted plans listing output."""
    portfolio_panel = create_portfolio_summary_panel(portfolio_data)
    console.print(portfolio_panel)
    console.print()
    
    # Convert dict to list for table creation compatibility
    risk_data_list = list(plan_risk_data.values()) if isinstance(plan_risk_data, dict) else plan_risk_data
    plans_table = create_plans_listing_table(plans, risk_data_list, verbose=verbose)
    console.print(plans_table)
    _display_plan_listing_guidance(verbose, status)


def _log_plans_listing_completion(plans: List[TradePlan], portfolio_data: Dict, 
                                 risk_results: Dict) -> None:
    """Log completion of plans listing operation."""
    logger.info(
        "Enhanced plan listing completed",
        plans_count=len(plans),
        portfolio_risk=float(portfolio_data["current_risk_percent"]),
        cache_stats=risk_results.get("cache_stats"),
    )


def _setup_update_directories(plans_dir: Optional[Path], backup_dir: Optional[Path]) -> tuple[Path, Path]:
    """Setup default directories for plan updates."""
    if plans_dir is None:
        plans_dir = Path("data/trade_plans")
    if backup_dir is None:
        backup_dir = Path("data/trade_plans/backups")
    return plans_dir, backup_dir


def _load_and_validate_plan_for_update(plan_id: str, loader: TradePlanLoader) -> Optional[TradePlan]:
    """Load and validate that plan exists for update."""
    # Load all plans first to ensure _loaded_plans is populated
    loader.load_all_plans()
    
    plan = loader.get_plan(plan_id)
    if not plan:
        console.print(f"[red]Error: Plan '{plan_id}' not found.[/red]")
        return None
    return plan


def _prepare_plan_update_data(plan: TradePlan, updates: Dict, risk_manager: RiskManager) -> tuple:
    """Prepare update data including validations and risk calculations."""
    updated_plan = _create_and_validate_updated_plan(plan, updates)
    original_validation = risk_manager.validate_trade_plan(plan)
    updated_validation = risk_manager.validate_trade_plan(updated_plan)
    return updated_plan, original_validation, updated_validation


def _log_plan_update_completion(plan_id: str, updates: Dict, backup_path: Path) -> None:
    """Log successful completion of plan update."""
    logger.info("Plan update completed", plan_id=plan_id, 
                updates=list(updates.keys()), backup_path=str(backup_path))


def _setup_archive_directories(plans_dir: Optional[Path], archive_dir: Optional[Path]) -> tuple[Path, Path]:
    """Setup default directories for plan archiving."""
    if plans_dir is None:
        plans_dir = Path("data/trade_plans")
    if archive_dir is None:
        archive_dir = Path("data/trade_plans/archive")
    return plans_dir, archive_dir


def _get_archivable_plans(loader: TradePlanLoader) -> List[TradePlan]:
    """Get all plans eligible for archiving."""
    # Load all plans first to ensure _loaded_plans is populated
    loader.load_all_plans()
    
    archivable_statuses = [TradePlanStatus.COMPLETED, TradePlanStatus.CANCELLED]
    archivable_plans = []
    for status in archivable_statuses:
        plans = loader.get_plans_by_status(status)
        archivable_plans.extend(plans)
    return archivable_plans


def _display_archive_preview(archive_groups: Dict, dry_run: bool) -> tuple[int, bool]:
    """Display archive preview and get confirmation if needed."""
    console.print("📁 PLAN ARCHIVE PREVIEW")
    console.print()
    preview_table, total_plans = create_archive_preview_table(archive_groups)
    console.print(preview_table)
    console.print(f"\n📊 Total plans to archive: {total_plans}")
    if dry_run:
        console.print("\n💡 This was a dry run. Use --force to perform actual archiving.")
        return total_plans, False
    return total_plans, True


def _get_archive_confirmation(total_plans: int, archive_dir: Path, force: bool) -> bool:
    """Get user confirmation for archiving operation."""
    if force:
        return True
    console.print()
    confirm = click.confirm(f"Archive {total_plans} plans to {archive_dir}?", default=False)
    if not confirm:
        console.print("[yellow]Plan archiving cancelled.[/yellow]")
        return False
    return True


def _display_archive_success(archived_count: int, archive_dir: Path) -> None:
    """Display success message after archiving."""
    console.print(f"\n✅ Successfully archived {archived_count} plans")
    console.print(f"📁 Archive location: {archive_dir}")


def _calculate_plan_statistics(all_plans: List[TradePlan]) -> tuple:
    """Calculate plan statistics from all plans."""
    status_counts = Counter(plan.status for plan in all_plans)
    symbol_counts = Counter(plan.symbol for plan in all_plans)
    risk_counts = Counter(plan.risk_category for plan in all_plans)
    return status_counts, symbol_counts, risk_counts


def _display_statistics_output(portfolio_data: Dict, status_counts, symbol_counts, 
                              risk_counts, total_plans: int) -> None:
    """Display formatted statistics output."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    console.print(f"📊 PLAN STATISTICS - {timestamp}")
    console.print()
    
    portfolio_panel = create_portfolio_summary_panel(portfolio_data)
    console.print(portfolio_panel)
    console.print()
    
    status_table = create_statistics_overview_table(status_counts, symbol_counts, risk_counts, total_plans)
    console.print(status_table)
    console.print()
    
    display_plan_insights(total_plans, symbol_counts, portfolio_data)


def _log_statistics_completion(total_plans: int, symbol_counts, portfolio_data: Dict, 
                              risk_results: Dict) -> None:
    """Log completion of statistics operation."""
    logger.info(
        "Plan statistics completed",
        total_plans=total_plans,
        unique_symbols=len(symbol_counts),
        portfolio_risk=float(portfolio_data["current_risk_percent"]),
        cache_stats=risk_results.get("cache_stats"),
    )


def handle_command_errors(operation_name: str, extra_context: str = ""):
    """Decorator for common error handling in management commands."""
    def error_handler(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except (IOError, OSError, PermissionError) as e:
                console.print(f"[red]File system error: {e}[/red]")
                logger.error(f"{operation_name} failed - file system error{extra_context}", error=str(e))
                raise click.ClickException("Failed to access files")
            except PlanLoadingError as e:
                console.print(f"[red]Plan loading error: {e}[/red]")
                logger.error(f"{operation_name} failed - plan loading{extra_context}", error=str(e))
                raise click.ClickException("Failed to load trade plans")
            except (BackupCreationError, BackupVerificationError) as e:
                console.print(f"[red]Backup operation error: {e}[/red]")
                logger.error(f"{operation_name} failed - backup operation{extra_context}", error=str(e))
                raise click.ClickException("Backup operation failed")
            except RiskCalculationError as e:
                console.print(f"[red]Risk calculation error: {e}[/red]")
                logger.error(f"{operation_name} failed - risk calculation{extra_context}", error=str(e))
                raise click.ClickException("Failed to calculate risks")
            except (FileSystemError, ArchiveError, ValidationError, PlanManagementError) as e:
                console.print(f"[red]Operation error: {e}[/red]")
                logger.error(f"{operation_name} failed - operation error{extra_context}", error=str(e))
                raise click.ClickException(f"{operation_name} operation failed")
        return wrapper
    return error_handler