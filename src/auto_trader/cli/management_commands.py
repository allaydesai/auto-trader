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
    validate_plans_comprehensive,
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
        
        # Sort plans
        if sort_by == "risk":
            # Sort by risk (requires calculation, expensive)
            def get_risk(plan):
                result = risk_manager.validate_trade_plan(plan)
                if result.passed and result.position_size_result:
                    return result.position_size_result.risk_amount_percent
                return Decimal("0")
            plans.sort(key=get_risk, reverse=True)
        elif sort_by == "symbol":
            plans.sort(key=lambda p: p.symbol)
        else:  # date (default)
            plans.sort(key=lambda p: p.plan_id, reverse=True)
        
        # Get portfolio risk summary
        portfolio_data = get_portfolio_risk_summary(risk_manager, plans)
        
        # Display portfolio summary panel
        portfolio_panel = create_portfolio_summary_panel(portfolio_data)
        console.print(portfolio_panel)
        console.print()
        
        # Display plans table
        plans_table = create_plans_table(plans, risk_manager, show_verbose=verbose)
        console.print(plans_table)
        
        # Display next-step guidance
        console.print()
        if not verbose:
            console.print("💡 Use --verbose for detailed information")
        if not status:
            console.print("💡 Use --status to filter plans by status")
        console.print("💡 Use validate-config to check plan health")
        
        logger.info(
            "Enhanced plan listing completed",
            plans_count=len(plans),
            portfolio_risk=float(portfolio_data["current_risk_percent"]),
        )
        
    except Exception as e:
        handle_generic_error("enhanced plan listing", e)


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
        
        # Initialize components
        validation_engine = ValidationEngine()
        risk_manager = _get_risk_manager()
        
        # Perform comprehensive validation
        results = validate_plans_comprehensive(
            plans_dir=plans_dir,
            validation_engine=validation_engine,
            risk_manager=risk_manager,
            single_file=file,
        )
        
        # Display validation header
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
        
        # Show file-specific results if verbose or there are errors
        file_results = results["file_results"]
        error_files = [f for f, r in file_results.items() if not r["syntax_valid"] or not r["business_logic_valid"]]
        
        if error_files or verbose:
            from rich.table import Table
            
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
        
        # Display next-step guidance
        console.print("💡 Use --verbose for detailed error information")
        if error_files:
            console.print("🔧 Review and fix errors in failing files")
        if not portfolio_passed:
            console.print("⚠️  Reduce plan risk amounts to stay within 10% limit")
        
        logger.info(
            "Comprehensive validation completed",
            files_checked=files_checked,
            syntax_passed=syntax_passed,
            logic_passed=logic_passed,
            portfolio_passed=portfolio_passed,
        )
        
    except Exception as e:
        handle_generic_error("comprehensive validation", e)


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
            
        # Initialize components
        loader = TradePlanLoader(plans_dir)
        risk_manager = _get_risk_manager()
        
        # Load existing plan
        plan = loader.get_plan_by_id(plan_id)
        if not plan:
            console.print(f"[red]Error: Plan '{plan_id}' not found.[/red]")
            return
        
        # Determine what fields to update
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
            console.print("[yellow]No fields specified for update. Use --help to see available options.[/yellow]")
            return
        
        # Create updated plan for validation
        updated_plan_data = plan.model_dump()
        updated_plan_data.update(updates)
        
        # Validate updated plan
        from ..models.trade_plan import TradePlan
        try:
            updated_plan = TradePlan(**updated_plan_data)
        except Exception as e:
            console.print(f"[red]Error: Invalid field values - {e}[/red]")
            return
        
        # Calculate risk impact
        original_validation = risk_manager.validate_trade_plan(plan)
        updated_validation = risk_manager.validate_trade_plan(updated_plan)
        
        # Display modification preview
        console.print("⚠️  PLAN MODIFICATION WARNING")
        console.print()
        
        from rich.table import Table
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
        
        console.print(preview_table)
        console.print()
        
        # Show risk impact
        console.print("🛡️  Risk Impact:")
        if original_validation.passed and updated_validation.passed:
            orig_size = original_validation.position_size_result.position_size
            new_size = updated_validation.position_size_result.position_size
            orig_risk = original_validation.position_size_result.risk_amount_dollars
            new_risk = updated_validation.position_size_result.risk_amount_dollars
            
            console.print(f"   Position Size: {orig_size} → {new_size} shares")
            console.print(f"   Dollar Risk: ${orig_risk:.2f} → ${new_risk:.2f}")
            
            # Portfolio impact would require recalculating entire portfolio
            console.print("   Portfolio impact calculated after update")
        else:
            console.print("   ❌ Risk calculation failed - plan may have validation errors")
        
        console.print()
        console.print(f"💾 Backup will be created in: {backup_dir}")
        
        # Get confirmation unless forced
        if not force:
            console.print()
            confirm = click.confirm("Continue with modification?", default=False)
            if not confirm:
                console.print("[yellow]Plan update cancelled.[/yellow]")
                return
        
        # Create backup
        plan_file_path = plans_dir / f"{plan_id}.yaml"
        backup_path = create_plan_backup(plan_file_path, backup_dir)
        
        # Update plan file
        import yaml
        with open(plan_file_path, 'w') as f:
            yaml.dump(updated_plan.model_dump(mode='python'), f, default_flow_style=False)
        
        # Success message
        console.print()
        console.print(f"✅ Plan {plan_id} updated successfully")
        if updated_validation.passed:
            console.print(f"📊 Position size recalculated: {updated_validation.position_size_result.position_size} shares")
        console.print(f"💾 Backup saved: {backup_path}")
        
        logger.info(
            "Plan update completed",
            plan_id=plan_id,
            updates=list(updates.keys()),
            backup_path=str(backup_path),
        )
        
    except PlanManagementError as e:
        console.print(f"[red]Plan management error: {e}[/red]")
    except Exception as e:
        handle_generic_error("plan update", e)


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
        
        # Initialize loader
        loader = TradePlanLoader(plans_dir)
        
        # Get completed and cancelled plans
        archivable_statuses = [TradePlanStatus.COMPLETED, TradePlanStatus.CANCELLED]
        archivable_plans = []
        
        for status in archivable_statuses:
            plans = loader.get_plans_by_status(status)
            archivable_plans.extend(plans)
        
        if not archivable_plans:
            console.print("[yellow]No plans found for archiving.[/yellow]")
            return
        
        # Organize plans by status and date for archive structure
        from collections import defaultdict
        archive_groups = defaultdict(list)
        
        for plan in archivable_plans:
            # Extract date from plan_id (format: SYMBOL_YYYYMMDD_NNN)
            try:
                date_part = plan.plan_id.split('_')[1]  # YYYYMMDD
                year = date_part[:4]
                month = date_part[4:6]
                archive_groups[f"{year}/{month}/{plan.status.value}"].append(plan)
            except (IndexError, ValueError):
                # Fallback for non-standard plan IDs
                current_date = datetime.now()
                fallback_path = f"{current_date.year}/{current_date.month:02d}/unknown_date"
                archive_groups[fallback_path].append(plan)
        
        # Display archive preview
        console.print("📁 PLAN ARCHIVE PREVIEW")
        console.print()
        
        from rich.table import Table
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
        
        console.print(preview_table)
        console.print(f"\n📊 Total plans to archive: {total_plans}")
        
        if dry_run:
            console.print("\n💡 This was a dry run. Use --force to perform actual archiving.")
            return
        
        # Get confirmation unless forced
        if not force:
            console.print()
            confirm = click.confirm(f"Archive {total_plans} plans to {archive_dir}?", default=False)
            if not confirm:
                console.print("[yellow]Plan archiving cancelled.[/yellow]")
                return
        
        # Perform archiving
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
        
        # Success summary
        console.print(f"\n✅ Successfully archived {archived_count} plans")
        console.print(f"📁 Archive location: {archive_dir}")
        
        logger.info(
            "Plan archiving completed",
            archived_count=archived_count,
            archive_dir=str(archive_dir),
        )
        
    except Exception as e:
        handle_generic_error("plan archiving", e)


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
        
        # Initialize components
        loader = TradePlanLoader(plans_dir)
        risk_manager = _get_risk_manager()
        
        # Load all plans
        all_plans_dict = loader.load_all_plans()
        all_plans = list(all_plans_dict.values())
        
        if not all_plans:
            console.print("[yellow]No trade plans found for analysis.[/yellow]")
            return
        
        # Calculate statistics
        status_counts = Counter(plan.status for plan in all_plans)
        symbol_counts = Counter(plan.symbol for plan in all_plans)
        risk_counts = Counter(plan.risk_category for plan in all_plans)
        
        # Portfolio risk analysis
        portfolio_data = get_portfolio_risk_summary(risk_manager, all_plans)
        
        # Display timestamp header
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        console.print(f"📊 PLAN STATISTICS - {timestamp}")
        console.print()
        
        # Portfolio Risk Summary
        portfolio_panel = create_portfolio_summary_panel(portfolio_data)
        console.print(portfolio_panel)
        console.print()
        
        # Plan Status Distribution
        from rich.table import Table
        
        status_table = Table(title="📈 Plan Status Distribution", show_header=True)
        status_table.add_column("Status", style="cyan", width=15)
        status_table.add_column("Count", style="white", width=8)
        status_table.add_column("Percentage", style="green", width=12)
        
        total_plans = len(all_plans)
        for status, count in status_counts.most_common():
            percentage = (count / total_plans) * 100
            formatted_status = status.replace('_', ' ').title()
            status_table.add_row(
                formatted_status,
                str(count),
                f"{percentage:.1f}%",
            )
        
        console.print(status_table)
        console.print()
        
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
        
        console.print(symbol_table)
        console.print()
        
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
        
        console.print(risk_table)
        console.print()
        
        # Summary insights
        console.print("💡 KEY INSIGHTS:")
        console.print(f"   • Total Plans: {total_plans}")
        console.print(f"   • Unique Symbols: {len(symbol_counts)}")
        console.print(f"   • Most Active Symbol: {symbol_counts.most_common(1)[0][0]} ({symbol_counts.most_common(1)[0][1]} plans)")
        console.print(f"   • Portfolio Diversification: {len(symbol_counts)} symbols")
        
        if portfolio_data["exceeds_limit"]:
            console.print("   🚨 ALERT: Portfolio risk exceeds 10% limit!")
        elif portfolio_data["near_limit"]:
            console.print("   ⚠️  WARNING: Portfolio risk approaching limit")
        else:
            console.print("   ✅ Portfolio risk within safe limits")
        
        logger.info(
            "Plan statistics completed",
            total_plans=total_plans,
            unique_symbols=len(symbol_counts),
            portfolio_risk=float(portfolio_data["current_risk_percent"]),
        )
        
    except Exception as e:
        handle_generic_error("plan statistics", e)