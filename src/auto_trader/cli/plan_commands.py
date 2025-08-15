"""Trade plan management CLI commands for Auto-Trader application."""

from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel

from ..logging_config import get_logger
from ..models import (
    TradePlanLoader,
    TemplateManager,
    TradePlanStatus,
)
from .display_utils import (
    display_plans_summary,
    display_plans_table,
    display_stats_summary,
)
from .file_utils import get_plan_data_interactive
from .error_utils import (
    handle_validation_plan_failure,
    handle_generic_error,
)
from .plan_utils import (
    show_available_templates,
    get_template_choice,
    create_plan_output_file,
    show_plan_creation_success,
)
from .watch_utils import start_file_watching


console = Console()
logger = get_logger("cli", "cli")


@click.command()
@click.option(
    "--plans-dir",
    type=click.Path(exists=True, path_type=Path),
    help="Directory containing trade plan YAML files",
)
@click.option("--verbose", "-v", is_flag=True, help="Show detailed validation results")
@click.option("--watch", "-w", is_flag=True, help="Watch for file changes and validate automatically")
def validate_plans(plans_dir: Optional[Path], verbose: bool, watch: bool) -> None:
    """Validate all trade plan YAML files in the plans directory."""
    logger.info("Trade plan validation started")
    
    try:
        # Use custom directory or default
        loader = TradePlanLoader(plans_dir) if plans_dir else TradePlanLoader()
        
        console.print(
            Panel(
                f"[blue]Validating trade plans in: {loader.plans_directory}[/blue]",
                title="Trade Plan Validation",
                border_style="blue",
            )
        )
        
        # Load and validate all plans
        plans = loader.load_all_plans(validate=True)
        
        # Get validation report
        report = loader.get_validation_report()
        
        if plans:
            console.print(
                Panel(
                    f"[green]✓ Successfully loaded {len(plans)} trade plan(s)[/green]",
                    title="Validation Result",
                    border_style="green",
                )
            )
            
            if verbose:
                display_plans_summary(loader)
                console.print("\n" + report)
                
        else:
            handle_validation_plan_failure(loader, plans_dir, verbose)
        
        # Enable file watching if requested
        if watch:
            start_file_watching(loader.plans_directory, verbose)
            
        logger.info("Trade plan validation completed", plan_count=len(plans))
        
    except Exception as e:
        handle_generic_error("trade plan validation", e)


@click.command()
@click.option(
    "--plans-dir",
    type=click.Path(exists=True, path_type=Path),
    help="Directory containing trade plan YAML files",
)
@click.option("--status", help="Filter by status (awaiting_entry, position_open, completed)")
@click.option("--symbol", help="Filter by symbol")  
@click.option("--risk-category", help="Filter by risk category (small, normal, large)")
@click.option("--sort-by", default="plan_id", type=click.Choice(["plan_id", "symbol", "status", "created_at"]), help="Sort plans by field")
@click.option("--sort-desc", is_flag=True, help="Sort in descending order")
@click.option("--limit", type=int, help="Limit number of results")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed plan information")
@click.option("--quiet", "-q", is_flag=True, help="Minimal output")
@click.option("--debug", is_flag=True, help="Debug level output")
def list_plans(
    plans_dir: Optional[Path], 
    status: Optional[str], 
    symbol: Optional[str],
    risk_category: Optional[str],
    sort_by: str,
    sort_desc: bool,
    limit: Optional[int],
    verbose: bool,
    quiet: bool,
    debug: bool
) -> None:
    """List all loaded trade plans with optional filtering."""
    logger.info("List trade plans started")
    
    try:
        # Use custom directory or default
        loader = TradePlanLoader(plans_dir) if plans_dir else TradePlanLoader()
        
        # Load all plans
        plans = loader.load_all_plans(validate=True)
        
        if not plans:
            console.print(
                Panel(
                    "[yellow]No trade plans found[/yellow]",
                    title="Trade Plans",
                    border_style="yellow",
                )
            )
            return
        
        # Apply filters
        filtered_plans = list(plans.values())
        
        if status:
            try:
                status_enum = TradePlanStatus(status)
                filtered_plans = [p for p in filtered_plans if p.status == status_enum]
            except ValueError:
                console.print(f"[red]❌ Invalid status: {status}[/red]")
                return
                
        if symbol:
            filtered_plans = [p for p in filtered_plans if p.symbol.upper() == symbol.upper()]
            
        if risk_category:
            filtered_plans = [p for p in filtered_plans if p.risk_category == risk_category]
        
        # Apply sorting
        reverse = sort_desc
        if sort_by == "plan_id":
            filtered_plans.sort(key=lambda p: p.plan_id, reverse=reverse)
        elif sort_by == "symbol":
            filtered_plans.sort(key=lambda p: p.symbol, reverse=reverse) 
        elif sort_by == "status":
            filtered_plans.sort(key=lambda p: p.status.value, reverse=reverse)
        elif sort_by == "created_at":
            filtered_plans.sort(key=lambda p: p.created_at, reverse=reverse)
        
        # Apply limit
        if limit and limit > 0:
            filtered_plans = filtered_plans[:limit]
        
        # Display results
        if not filtered_plans:
            if not quiet:
                console.print(
                    Panel(
                        "[yellow]⚠️  No plans found matching filters[/yellow]",
                        title="Filtered Results",
                        border_style="yellow",
                    )
                )
            return
        
        # Display with UX-compliant formatting
        if not quiet:
            # Show header with status-at-a-glance information
            filter_info = []
            if status:
                filter_info.append(f"status={status}")
            if symbol:
                filter_info.append(f"symbol={symbol}")  
            if risk_category:
                filter_info.append(f"risk={risk_category}")
            if limit:
                filter_info.append(f"limit={limit}")
                
            filter_str = f" ({', '.join(filter_info)})" if filter_info else ""
            
            console.print(
                Panel(
                    f"[blue]📈 TRADE PLANS - {len(filtered_plans)} plan(s) found{filter_str}[/blue]",
                    title="Trade Plans",
                    border_style="blue",
                )
            )
        
        # Display plans table with verbosity control
        if debug:
            display_plans_table(filtered_plans, verbose=True)
            console.print(f"\n[dim]🔍 Debug: Sort by {sort_by}, desc={sort_desc}[/dim]")
        elif verbose:
            display_plans_table(filtered_plans, verbose=True)
        elif not quiet:
            display_plans_table(filtered_plans, verbose=False)
        
        # Show statistics (unless quiet mode)
        if not quiet:
            stats = loader.get_stats()
            display_stats_summary(stats)
        
        logger.info("List trade plans completed", filtered_count=len(filtered_plans))
        
    except Exception as e:
        handle_generic_error("listing plans", e)


@click.command()
@click.option("--output-dir", type=click.Path(path_type=Path), help="Output directory for created plan")
def create_plan() -> None:
    """Interactive wizard to create a new trade plan from template."""
    logger.info("Create trade plan wizard started")
    
    try:
        # Initialize template manager
        template_manager = TemplateManager()
        
        # Show available templates
        template_info = show_available_templates(template_manager)
        if not template_info:
            return
        
        # Get template choice
        template_name = get_template_choice(template_info["template_names"])
        
        # Get plan data interactively
        plan_data = get_plan_data_interactive()
        
        # Create output file path
        output_dir_param = click.get_current_context().params.get("output_dir")
        output_file = create_plan_output_file(plan_data, output_dir_param)
        
        # Create the plan
        trade_plan = template_manager.create_plan_from_template(
            template_name, 
            plan_data, 
            output_file
        )
        
        # Show success message
        show_plan_creation_success(trade_plan, output_file)
        
        logger.info("Trade plan created successfully", plan_id=trade_plan.plan_id)
        
    except Exception as e:
        handle_generic_error("creating plan", e)