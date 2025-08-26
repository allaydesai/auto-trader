"""Trade plan management CLI commands for enhanced plan operations."""

import shutil
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Optional

import click
from rich.console import Console

from ..logging_config import get_logger
from ..models import TradePlanLoader, TradePlanStatus, ValidationEngine
from ..risk_management import RiskManager
from config import ConfigLoader, Settings
from .error_utils import handle_generic_error
from .command_helpers import (
    _get_risk_manager,
    _load_and_filter_plans,
    _display_plans_listing_output,
    _log_plans_listing_completion,
    _setup_update_directories,
    _load_and_validate_plan_for_update,
    _prepare_plan_update_data,
    _log_plan_update_completion,
    _setup_archive_directories,
    _get_archivable_plans,
    _display_archive_preview,
    _get_archive_confirmation,
    _display_archive_success,
    _calculate_plan_statistics,
    _display_statistics_output,
    _log_statistics_completion,
    handle_command_errors
)
from .management_utils import (
    PlanManagementError,
    PlanLoadingError,
    FileSystemError,
    RiskCalculationError,
    PlanUpdateError,
    _sort_plans_by_criteria,
    _display_plan_listing_guidance,
    process_plan_field_updates,
    _create_and_validate_updated_plan,
    _display_update_preview_and_confirmation,
    _perform_plan_update,
    _display_update_success,
)
from .backup_utils import (
    create_plan_backup,
    verify_backup,
    BackupCreationError,
    BackupVerificationError,
)
from .risk_utils import (
    calculate_all_plan_risks,
    get_portfolio_risk_summary,
    create_portfolio_summary_panel,
)
from .display_utils_extended import (
    create_plans_listing_table as create_plans_table,
    create_plan_update_preview_table,
    display_plan_risk_impact,
    create_statistics_overview_table as create_plan_statistics_tables,
    display_plan_insights,
)
from .archive_utils import (
    organize_plans_for_archive,
    create_archive_preview_table,
    perform_plan_archiving,
)
from .validation_utils import (
    validate_all_plans as validate_plans_comprehensive,
    _display_validation_results,
    _display_validation_file_details,
    _display_validation_guidance,
    ValidationError,
)

console = Console()
logger = get_logger("management_commands", "cli")




@click.command()
@click.option(
    "--plans-dir",
    type=click.Path(exists=True, path_type=Path),
    help="Directory containing trade plan YAML files",
)
@click.option(
    "--status",
    type=click.Choice([s.value for s in TradePlanStatus]),
    help="Filter plans by status (awaiting_entry, position_open, etc.)",
)
@click.option(
    "--sort-by", 
    type=click.Choice(["risk", "date", "symbol"]),
    default="date",
    help="Sort plans by criteria (risk, date, symbol)",
)
@click.option("--verbose", "-v", is_flag=True, help="Show detailed plan information")
def list_plans_enhanced(
    plans_dir: Optional[Path], 
    status: Optional[str], 
    sort_by: str, 
    verbose: bool
) -> None:
    """Enhanced plan listing with risk management integration and UX compliance."""
    logger.info("Enhanced plan listing started", status_filter=status, sort_by=sort_by)
    
    try:
        # Use default plans directory if not specified
        if plans_dir is None:
            plans_dir = Path("data/trade_plans")
        
        # Initialize components and load plans
        loader = TradePlanLoader(plans_dir)
        risk_manager = _get_risk_manager()
        plans = _load_and_filter_plans(loader, status)
        
        if not plans:
            console.print("[yellow]No trade plans found.[/yellow]")
            return
        
        # Pre-calculate all risk data and sort plans
        risk_results = calculate_all_plan_risks(plans, risk_manager)
        plan_risk_data = risk_results["plan_risk_data"]
        portfolio_data = risk_results["portfolio_summary"]
        # Convert dict to list for sorting function compatibility
        risk_data_list = list(plan_risk_data.values()) if isinstance(plan_risk_data, dict) else plan_risk_data
        plans = _sort_plans_by_criteria(plans, sort_by, risk_data_list)
        
        # Display results and log completion
        _display_plans_listing_output(plans, plan_risk_data, portfolio_data, verbose, status)
        _log_plans_listing_completion(plans, portfolio_data, risk_results)
        
    except (IOError, OSError, PermissionError) as e:
        console.print(f"[red]File system error: {e}[/red]")
        logger.error("Enhanced plan listing failed - file system error", error=str(e))
        raise click.ClickException("Failed to access plan files")
    except PlanLoadingError as e:
        console.print(f"[red]Plan loading error: {e}[/red]")
        logger.error("Enhanced plan listing failed - plan loading", error=str(e))
        raise click.ClickException("Failed to load trade plans")
    except RiskCalculationError as e:
        console.print(f"[red]Risk calculation error: {e}[/red]")
        logger.error("Enhanced plan listing failed - risk calculation", error=str(e))
        raise click.ClickException("Failed to calculate plan risks")
    except PlanManagementError as e:
        console.print(f"[red]Plan management error: {e}[/red]")
        logger.error("Enhanced plan listing failed - management error", error=str(e))
        raise click.ClickException("Plan listing operation failed")


@click.command()
@click.option(
    "--plans-dir",
    type=click.Path(exists=True, path_type=Path),
    help="Directory containing trade plan YAML files",
)
@click.option(
    "--file",
    type=click.Path(exists=True, path_type=Path),
    help="Validate single file instead of all files",
)
@click.option("--verbose", "-v", is_flag=True, help="Show detailed validation results")
def validate_config(
    plans_dir: Optional[Path], 
    file: Optional[Path], 
    verbose: bool
) -> None:
    """Comprehensive validation of trade plan configuration with UX compliance."""
    logger.info("Comprehensive validation started", single_file=str(file) if file else None)
    
    try:
        # Use default plans directory if not specified
        if plans_dir is None:
            plans_dir = Path("data/trade_plans")
        
        # Initialize components and perform validation
        validation_engine = ValidationEngine()
        risk_manager = _get_risk_manager()
        
        results = validate_plans_comprehensive(
            plans_dir=plans_dir,
            validation_engine=validation_engine,
            risk_manager=risk_manager,
            single_file=file,
        )
        
        # Display validation results using utility functions
        _display_validation_results(results, verbose)
        _display_validation_file_details(results["file_results"], verbose)
        _display_validation_guidance(results["file_results"], results["portfolio_risk_passed"])
        
        logger.info(
            "Comprehensive validation completed",
            files_checked=results["files_checked"],
            syntax_passed=results["syntax_passed"],
            logic_passed=results["business_logic_passed"],
            portfolio_passed=results["portfolio_risk_passed"],
        )
        
    except (IOError, OSError, PermissionError) as e:
        console.print(f"[red]File system error: {e}[/red]")
        logger.error("Comprehensive validation failed - file system error", error=str(e))
        raise click.ClickException("Failed to access validation files")
    except ValidationError as e:
        console.print(f"[red]Validation error: {e}[/red]")
        logger.error("Comprehensive validation failed - validation error", error=str(e))
        raise click.ClickException("Validation operation failed")
    except RiskCalculationError as e:
        console.print(f"[red]Risk calculation error: {e}[/red]")
        logger.error("Comprehensive validation failed - risk calculation", error=str(e))
        raise click.ClickException("Failed to calculate portfolio risks")
    except PlanManagementError as e:
        console.print(f"[red]Plan management error: {e}[/red]")
        logger.error("Comprehensive validation failed - management error", error=str(e))
        raise click.ClickException("Validation operation failed")

@click.command()
@click.argument("plan_id", type=str)
@click.option(
    "--entry-level",
    type=float,
    help="Update entry level price",
)
@click.option(
    "--stop-loss",
    type=float,
    help="Update stop loss price",
)
@click.option(
    "--take-profit",
    type=float,
    help="Update take profit price",
)
@click.option(
    "--risk-category",
    type=click.Choice(["small", "normal", "large"]),
    help="Update risk category",
)
@click.option(
    "--plans-dir",
    type=click.Path(exists=True, path_type=Path),
    help="Directory containing trade plan YAML files",
)
@click.option("--backup-dir", type=click.Path(path_type=Path), help="Backup directory")
@click.option("--force", is_flag=True, help="Skip confirmation prompts")
def update_plan(
    plan_id: str,
    entry_level: Optional[float],
    stop_loss: Optional[float], 
    take_profit: Optional[float],
    risk_category: Optional[str],
    plans_dir: Optional[Path],
    backup_dir: Optional[Path],
    force: bool,
) -> None:
    """Update trade plan fields with automatic recalculation and backup."""
    logger.info("Plan update started", plan_id=plan_id, force=force)
    
    try:
        # Setup directories and initialize components
        plans_dir, backup_dir = _setup_update_directories(plans_dir, backup_dir)
        loader = TradePlanLoader(plans_dir)
        risk_manager = _get_risk_manager()
        
        # Load and validate plan exists
        plan = _load_and_validate_plan_for_update(plan_id, loader)
        if not plan:
            return
        
        # Process updates and prepare data
        updates = process_plan_field_updates(plan, entry_level, stop_loss, take_profit, risk_category)
        
        if not updates:
            console.print("[yellow]No fields specified for update.[/yellow]")
            return
            
        updated_plan, original_validation, updated_validation = _prepare_plan_update_data(plan, updates, risk_manager)
        
        # Display preview and get confirmation (skip if force flag)
        if not force:
            should_proceed = _display_update_preview_and_confirmation(
                plan_id, plan, updates, original_validation, updated_validation
            )
            if not should_proceed:
                return
        
        # Perform update and display success
        backup_path = _perform_plan_update(plan_id, updated_plan, plans_dir, backup_dir)
        _display_update_success(plan_id, updated_validation, backup_path)
        _log_plan_update_completion(plan_id, updates, backup_path)
        
    except (IOError, OSError, PermissionError) as e:
        console.print(f"[red]File system error: {e}[/red]")
        logger.error("Plan update failed - file system error", plan_id=plan_id, error=str(e))
        raise click.ClickException("Failed to access plan files")
    except PlanLoadingError as e:
        console.print(f"[red]Plan loading error: {e}[/red]")
        logger.error("Plan update failed - plan loading", plan_id=plan_id, error=str(e))
        raise click.ClickException("Failed to load plan")
    except BackupCreationError as e:
        console.print(f"[red]Backup creation error: {e}[/red]")
        logger.error("Plan update failed - backup creation", plan_id=plan_id, error=str(e))
        raise click.ClickException("Failed to create backup before plan update")
    except BackupVerificationError as e:
        console.print(f"[red]Backup verification error: {e}[/red]")
        logger.error("Plan update failed - backup verification", plan_id=plan_id, error=str(e))
        raise click.ClickException("Backup verification failed, plan update cancelled")
    except RiskCalculationError as e:
        console.print(f"[red]Risk calculation error: {e}[/red]")
        logger.error("Plan update failed - risk calculation", plan_id=plan_id, error=str(e))
        raise click.ClickException("Failed to calculate plan risks")
    except PlanManagementError as e:
        console.print(f"[red]Plan management error: {e}[/red]")
        logger.error("Plan update failed - management error", plan_id=plan_id, error=str(e))
        raise click.ClickException("Plan update operation failed")


@click.command()
@click.option(
    "--plans-dir",
    type=click.Path(exists=True, path_type=Path),
    help="Directory containing trade plan YAML files",
)
@click.option(
    "--archive-dir",
    type=click.Path(path_type=Path),
    help="Archive directory (defaults to data/trade_plans/archive)",
)
@click.option("--dry-run", is_flag=True, help="Show what would be archived without moving files")
@click.option("--force", is_flag=True, help="Skip confirmation prompts")
def archive_plans(
    plans_dir: Optional[Path],
    archive_dir: Optional[Path],
    dry_run: bool,
    force: bool,
) -> None:
    """Archive completed and cancelled trade plans with fail-safe organization."""
    logger.info("Plan archiving started", dry_run=dry_run, force=force)
    
    try:
        # Setup directories and load archivable plans
        plans_dir, archive_dir = _setup_archive_directories(plans_dir, archive_dir)
        loader = TradePlanLoader(plans_dir)
        archivable_plans = _get_archivable_plans(loader)
        
        if not archivable_plans:
            console.print("[yellow]No plans found for archiving.[/yellow]")
            return
        
        # Organize plans and display preview
        archive_groups = organize_plans_for_archive(archivable_plans)
        total_plans, should_continue = _display_archive_preview(archive_groups, dry_run)
        
        if not should_continue:  # dry run completed
            return
        
        # Get confirmation and perform archiving
        if not _get_archive_confirmation(total_plans, archive_dir, force):
            return
        
        archived_count = perform_plan_archiving(archive_groups, plans_dir, archive_dir)
        _display_archive_success(archived_count, archive_dir)
        
        logger.info(
            "Plan archiving completed",
            archived_count=archived_count,
            archive_dir=str(archive_dir),
        )
        
    except (IOError, OSError, PermissionError) as e:
        console.print(f"[red]File system error: {e}[/red]")
        logger.error("Plan archiving failed - file system error", error=str(e))
        raise click.ClickException("Failed to access archiving files")
    except PlanLoadingError as e:
        console.print(f"[red]Plan loading error: {e}[/red]")
        logger.error("Plan archiving failed - plan loading", error=str(e))
        raise click.ClickException("Failed to load plans for archiving")
    except FileSystemError as e:
        console.print(f"[red]Archive operation error: {e}[/red]")
        logger.error("Plan archiving failed - file system operation", error=str(e))
        raise click.ClickException("Failed to perform archiving operation")
    except PlanManagementError as e:
        console.print(f"[red]Plan management error: {e}[/red]")
        logger.error("Plan archiving failed - management error", error=str(e))
        raise click.ClickException("Archiving operation failed")


@click.command()
@click.option(
    "--plans-dir",
    type=click.Path(exists=True, path_type=Path),
    help="Directory containing trade plan YAML files",
)
def plan_stats(plans_dir: Optional[Path]) -> None:
    """Display comprehensive plan summary statistics and portfolio analysis."""
    logger.info("Plan statistics generation started")
    
    try:
        # Setup directory and load plans
        if plans_dir is None:
            plans_dir = Path("data/trade_plans")
        
        loader = TradePlanLoader(plans_dir)
        risk_manager = _get_risk_manager()
        
        all_plans_dict = loader.load_all_plans()
        all_plans = list(all_plans_dict.values())
        
        if not all_plans:
            console.print("[yellow]No trade plans found for analysis.[/yellow]")
            return
        
        # Calculate statistics and risk data
        status_counts, symbol_counts, risk_counts = _calculate_plan_statistics(all_plans)
        risk_results = calculate_all_plan_risks(all_plans, risk_manager)
        portfolio_data = risk_results["portfolio_summary"]
        
        # Display output and log completion
        total_plans = len(all_plans)
        _display_statistics_output(portfolio_data, status_counts, symbol_counts, risk_counts, total_plans)
        _log_statistics_completion(total_plans, symbol_counts, portfolio_data, risk_results)
        
    except (IOError, OSError, PermissionError) as e:
        console.print(f"[red]File system error: {e}[/red]")
        logger.error("Plan statistics failed - file system error", error=str(e))
        raise click.ClickException("Failed to access plan files")
    except PlanLoadingError as e:
        console.print(f"[red]Plan loading error: {e}[/red]")
        logger.error("Plan statistics failed - plan loading", error=str(e))
        raise click.ClickException("Failed to load trade plans")
    except RiskCalculationError as e:
        console.print(f"[red]Risk calculation error: {e}[/red]")
        logger.error("Plan statistics failed - risk calculation", error=str(e))
        raise click.ClickException("Failed to calculate plan statistics")
    except PlanManagementError as e:
        console.print(f"[red]Plan management error: {e}[/red]")
        logger.error("Plan statistics failed - management error", error=str(e))
        raise click.ClickException("Statistics operation failed")