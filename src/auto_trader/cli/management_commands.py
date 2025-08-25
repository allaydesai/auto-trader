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
from config import get_config_loader
from .error_utils import handle_generic_error
from .management_utils import (
    create_plan_backup,
    create_plans_table,
    create_portfolio_summary_panel,
    get_portfolio_risk_summary,
    PlanManagementError,
    PlanLoadingError,
    ValidationError,
    FileSystemError,
    RiskCalculationError,
    BackupCreationError,
    BackupVerificationError,
    validate_plans_comprehensive,
    verify_backup,
    _sort_plans_by_criteria,
    _display_plan_listing_guidance,
    process_plan_field_updates,
    create_plan_update_preview_table,
    display_plan_risk_impact,
    organize_plans_for_archive,
    create_archive_preview_table,
    perform_plan_archiving,
    create_plan_statistics_tables,
    display_plan_insights,
    _display_validation_results,
    _display_validation_file_details,
    _display_validation_guidance,
    _create_and_validate_updated_plan,
    _display_update_preview_and_confirmation,
    _perform_plan_update,
    _display_update_success,
    calculate_all_plan_risks,
)

console = Console()
logger = get_logger("management_commands", "cli")


def _get_risk_manager() -> RiskManager:
    """Get properly configured risk manager from user preferences."""
    config_loader = get_config_loader()
    user_prefs = config_loader.load_user_preferences()
    return RiskManager(account_value=user_prefs.account_value)


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
        
        # Initialize components
        loader = TradePlanLoader(plans_dir)
        risk_manager = _get_risk_manager()
        
        # Load and filter plans
        if status:
            plans = loader.get_plans_by_status(TradePlanStatus(status))
        else:
            plans_dict = loader.load_all_plans()
            plans = list(plans_dict.values())
        
        if not plans:
            console.print("[yellow]No trade plans found.[/yellow]")
            return
        
        # Pre-calculate all risk data in single pass for performance
        risk_results = calculate_all_plan_risks(plans, risk_manager)
        plan_risk_data = risk_results["plan_risk_data"]
        portfolio_data = risk_results["portfolio_summary"]
        
        # Sort plans using pre-calculated risk data
        plans = _sort_plans_by_criteria(plans, sort_by, plan_risk_data)
        
        # Display portfolio summary and plans table using cached data
        portfolio_panel = create_portfolio_summary_panel(portfolio_data)
        console.print(portfolio_panel)
        console.print()
        
        plans_table = create_plans_table(plans, plan_risk_data, show_verbose=verbose)
        console.print(plans_table)
        _display_plan_listing_guidance(verbose, status)
        
        logger.info(
            "Enhanced plan listing completed",
            plans_count=len(plans),
            portfolio_risk=float(portfolio_data["current_risk_percent"]),
            cache_stats=risk_results.get("cache_stats"),
        )
        
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
        # Use default directories if not specified  
        if plans_dir is None:
            plans_dir = Path("data/trade_plans")
        if backup_dir is None:
            backup_dir = Path("data/trade_plans/backups")
            
        # Initialize components and load plan
        loader = TradePlanLoader(plans_dir)
        risk_manager = _get_risk_manager()
        
        plan = loader.get_plan_by_id(plan_id)
        if not plan:
            console.print(f"[red]Error: Plan '{plan_id}' not found.[/red]")
            return
        
        # Process field updates and create validated updated plan
        updates = process_plan_field_updates(plan, entry_level, stop_loss, take_profit, risk_category)
        updated_plan = _create_and_validate_updated_plan(plan, updates)
        
        # Calculate risk impact for preview
        original_validation = risk_manager.validate_trade_plan(plan)
        updated_validation = risk_manager.validate_trade_plan(updated_plan)
        
        # Display preview and get confirmation
        should_proceed = _display_update_preview_and_confirmation(
            plan_id, plan, updates, original_validation, updated_validation, backup_dir, force
        )
        if not should_proceed:
            return
        
        # Perform update and display success
        backup_path = _perform_plan_update(plan_id, updated_plan, plans_dir, backup_dir)
        _display_update_success(plan_id, updated_validation, backup_path)
        
        logger.info(
            "Plan update completed",
            plan_id=plan_id,
            updates=list(updates.keys()),
            backup_path=str(backup_path),
        )
        
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
        # Use default directories if not specified
        if plans_dir is None:
            plans_dir = Path("data/trade_plans")
        if archive_dir is None:
            archive_dir = Path("data/trade_plans/archive")
        
        # Get archivable plans
        loader = TradePlanLoader(plans_dir)
        archivable_statuses = [TradePlanStatus.COMPLETED, TradePlanStatus.CANCELLED]
        archivable_plans = []
        
        for status in archivable_statuses:
            plans = loader.get_plans_by_status(status)
            archivable_plans.extend(plans)
        
        if not archivable_plans:
            console.print("[yellow]No plans found for archiving.[/yellow]")
            return
        
        # Organize plans for archiving and create preview
        archive_groups = organize_plans_for_archive(archivable_plans)
        
        console.print("📁 PLAN ARCHIVE PREVIEW")
        console.print()
        
        preview_table, total_plans = create_archive_preview_table(archive_groups)
        console.print(preview_table)
        console.print(f"\n📊 Total plans to archive: {total_plans}")
        
        if dry_run:
            console.print("\n💡 This was a dry run. Use --force to perform actual archiving.")
            return
        
        # Get confirmation and perform archiving
        if not force:
            console.print()
            confirm = click.confirm(f"Archive {total_plans} plans to {archive_dir}?", default=False)
            if not confirm:
                console.print("[yellow]Plan archiving cancelled.[/yellow]")
                return
        
        archived_count = perform_plan_archiving(archive_groups, plans_dir, archive_dir)
        
        # Display success summary
        console.print(f"\n✅ Successfully archived {archived_count} plans")
        console.print(f"📁 Archive location: {archive_dir}")
        
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
        # Use default directory if not specified
        if plans_dir is None:
            plans_dir = Path("data/trade_plans")
        
        # Initialize components and load plans
        loader = TradePlanLoader(plans_dir)
        risk_manager = _get_risk_manager()
        
        all_plans_dict = loader.load_all_plans()
        all_plans = list(all_plans_dict.values())
        
        if not all_plans:
            console.print("[yellow]No trade plans found for analysis.[/yellow]")
            return
        
        # Calculate statistics
        from collections import Counter
        status_counts = Counter(plan.status for plan in all_plans)
        symbol_counts = Counter(plan.symbol for plan in all_plans)
        risk_counts = Counter(plan.risk_category for plan in all_plans)
        
        # Pre-calculate all risk data in single pass for performance
        risk_results = calculate_all_plan_risks(all_plans, risk_manager)
        portfolio_data = risk_results["portfolio_summary"]
        
        # Display header and portfolio summary
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        console.print(f"📊 PLAN STATISTICS - {timestamp}")
        console.print()
        
        portfolio_panel = create_portfolio_summary_panel(portfolio_data)
        console.print(portfolio_panel)
        console.print()
        
        # Create and display statistics tables
        total_plans = len(all_plans)
        status_table, symbol_table, risk_table = create_plan_statistics_tables(
            status_counts, symbol_counts, risk_counts, total_plans
        )
        
        console.print(status_table)
        console.print()
        console.print(symbol_table)
        console.print()
        console.print(risk_table)
        console.print()
        # Display insights
        display_plan_insights(total_plans, symbol_counts, portfolio_data)
        
        logger.info(
            "Plan statistics completed",
            total_plans=total_plans,
            unique_symbols=len(symbol_counts),
            portfolio_risk=float(portfolio_data["current_risk_percent"]),
            cache_stats=risk_results.get("cache_stats"),
        )
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