"""CLI commands for Auto-Trader application."""

import time
from pathlib import Path
from typing import Optional, List
from datetime import datetime

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.live import Live

from config import Settings, ConfigLoader
from ..logging_config import get_logger
from ..models import (
    TradePlanLoader,
    TemplateManager,
    TradePlanStatus,
)
from ..utils import FileWatcher, FileWatchEventType
from .display_utils import (
    display_config_summary,
    display_plans_summary,
    display_plans_table,
    display_stats_summary,
    display_performance_summary,
    display_trade_history,
    generate_monitor_layout,
)
from .file_utils import (
    create_env_file,
    create_config_file,
    create_user_config_file,
    get_plan_data_interactive,
    export_performance_csv,
    export_trade_history_csv,
)
from .error_utils import (
    handle_config_validation_failure,
    handle_file_permission_error,
    handle_validation_plan_failure,
    handle_generic_error,
    show_safety_warning,
    check_existing_files,
)
from .plan_utils import (
    show_available_templates,
    get_template_choice,
    create_plan_output_file,
    show_plan_creation_success,
)
from .diagnostic_utils import (
    check_configuration,
    check_trade_plans,
    check_permissions,
    display_diagnostic_summary,
    export_debug_information,
)
from .schema_utils import (
    display_schema_console,
)
from .watch_utils import (
    start_file_watching,
)


console = Console()
logger = get_logger("cli", "cli")


@click.group()
@click.version_option(version="0.1.0", prog_name="auto-trader")
def cli() -> None:
    """Auto-Trader: Personal Automated Trading System."""
    pass


@cli.command()
@click.option(
    "--config-file",
    type=click.Path(exists=True, path_type=Path),
    help="Path to config.yaml file",
)
@click.option(
    "--user-config-file",
    type=click.Path(exists=True, path_type=Path),
    help="Path to user_config.yaml file",
)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def validate_config(
    config_file: Optional[Path], user_config_file: Optional[Path], verbose: bool
) -> None:
    """Validate configuration files and environment variables."""
    logger.info("Configuration validation started")

    try:
        # Override settings if custom paths provided
        settings = Settings()
        if config_file:
            settings.config_file = config_file
        if user_config_file:
            settings.user_config_file = user_config_file

        config_loader = ConfigLoader(settings)

        # Validate configuration
        issues = config_loader.validate_configuration()

        if not issues:
            console.print(
                Panel(
                    "[green]✓ Configuration validation passed![/green]",
                    title="Validation Result",
                    border_style="green",
                )
            )

            # Show safety warning if not in simulation mode
            show_safety_warning(config_loader.system_config.trading.simulation_mode)

            if verbose:
                display_config_summary(config_loader)

            logger.info("Configuration validation passed")

        else:
            handle_config_validation_failure(issues, verbose)

    except Exception as e:
        handle_generic_error("configuration validation", e)


@cli.command()
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=Path.cwd(),
    help="Output directory for configuration files",
)
@click.option("--force", is_flag=True, help="Overwrite existing files")
def setup(output_dir: Path, force: bool) -> None:
    """Interactive setup wizard for first-time configuration."""
    logger.info("Setup wizard started", output_dir=str(output_dir))

    console.print(
        Panel(
            "[bold blue]Auto-Trader Setup Wizard[/bold blue]\n"
            "This wizard will help you create the necessary configuration files.",
            title="Welcome",
            border_style="blue",
        )
    )

    try:
        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        # Check for existing files
        if not check_existing_files(output_dir, force):
            return

        # Create configuration files
        env_file = output_dir / ".env"
        config_file = output_dir / "config.yaml"
        user_config_file = output_dir / "user_config.yaml"
        
        try:
            create_env_file(env_file)
            create_config_file(config_file)
            create_user_config_file(user_config_file)
        except (OSError, IOError) as e:
            handle_file_permission_error(output_dir, "file creation", e)
            return

        console.print(
            Panel(
                "[green]✓ Setup completed successfully![/green]\n\n"
                "[bold]Next steps:[/bold]\n"
                "1. Edit .env file with your actual credentials\n"
                "2. Customize config.yaml for your trading preferences\n"
                "3. Adjust user_config.yaml for your risk profile\n"
                "4. Run 'auto-trader validate-config' to verify setup",
                title="Setup Complete",
                border_style="green",
            )
        )

        logger.info("Setup wizard completed successfully")

    except Exception as e:
        handle_generic_error("setup wizard", e)


@cli.command()
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


@cli.command()
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


@cli.command()
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


@cli.command()
@click.option("--format", "output_format", default="console", type=click.Choice(["console", "json", "yaml"]), help="Output format")
@click.option("--field", help="Show documentation for specific field")
def show_schema(output_format: str, field: Optional[str]) -> None:
    """Show trade plan schema documentation with examples."""
    logger.info("Schema documentation requested")
    
    try:
        from ..models.trade_plan import TradePlan
        
        # Get model schema information
        schema = TradePlan.model_json_schema()
        
        if field:
            # Show specific field documentation
            if field in schema.get("properties", {}):
                field_info = schema["properties"][field]
                console.print(
                    Panel(
                        f"[blue]Field: {field}[/blue]\n"
                        f"Type: {field_info.get('type', 'unknown')}\n"
                        f"Description: {field_info.get('description', 'No description')}\n"
                        f"Required: {'Yes' if field in schema.get('required', []) else 'No'}",
                        title=f"Schema - {field}",
                        border_style="blue",
                    )
                )
            else:
                console.print(f"[red]❌ Field '{field}' not found in schema[/red]")
                return
        else:
            # Show complete schema
            if output_format == "console":
                display_schema_console(schema)
            elif output_format == "json":
                import json
                console.print(json.dumps(schema, indent=2))
            elif output_format == "yaml":
                import yaml
                console.print(yaml.dump(schema, default_flow_style=False))
                
        logger.info("Schema documentation completed", field=field, format=output_format)
        
    except Exception as e:
        handle_generic_error("schema documentation", e)


@cli.command()
@click.option("--verbose", "-v", is_flag=True, help="Show detailed template information")
def list_templates(verbose: bool) -> None:
    """List all available trade plan templates."""
    logger.info("List templates started")
    
    try:
        template_manager = TemplateManager()
        templates = template_manager.list_available_templates()
        
        if not templates:
            console.print(
                Panel(
                    "[yellow]No templates found[/yellow]",
                    title="Templates",
                    border_style="yellow",
                )
            )
            return
        
        console.print(
            Panel(
                f"[blue]Found {len(templates)} template(s)[/blue]",
                title="Available Templates",
                border_style="blue",
            )
        )
        
        # Create templates table
        table = Table(title="Trade Plan Templates")
        table.add_column("Name", style="cyan")
        table.add_column("Description", style="white")
        if verbose:
            table.add_column("Required Fields", style="yellow")
            table.add_column("Use Cases", style="green")
        
        for name in templates:
            doc_info = template_manager.get_template_documentation(name)
            description = doc_info.get("description", "No description")
            
            if verbose:
                required_count = len(doc_info.get("required_fields", []))
                use_cases_count = len(doc_info.get("use_cases", []))
                table.add_row(
                    name, 
                    description,
                    str(required_count),
                    str(use_cases_count)
                )
            else:
                table.add_row(name, description)
        
        console.print(table)
        
        if verbose:
            # Show template summary
            summary = template_manager.get_template_summary()
            console.print("\n[bold]Template Validation Results:[/bold]")
            for name, is_valid in summary["validation_results"].items():
                status = "[green]✓[/green]" if is_valid else "[red]✗[/red]"
                console.print(f"  {status} {name}")
        
        logger.info("List templates completed", template_count=len(templates))
        
    except Exception as e:
        handle_generic_error("listing templates", e)


@cli.command()
@click.option(
    "--plans-dir",
    type=click.Path(exists=True, path_type=Path),
    help="Directory containing trade plan YAML files",
)
@click.option("--refresh-rate", default=5, help="Refresh rate in seconds")
def monitor(plans_dir: Optional[Path], refresh_rate: int) -> None:
    """Live system monitor dashboard showing real-time status."""
    logger.info("Live system monitor started")
    
    try:
        # Initialize loader
        loader = TradePlanLoader(plans_dir) if plans_dir else TradePlanLoader()
        
        console.print(
            Panel(
                "[bold blue]Starting Auto-Trader Live Monitor[/bold blue]\n"
                "Press 'Ctrl+C' to exit",
                title="Live Monitor",
                border_style="blue",
            )
        )
        
        with Live(generate_monitor_layout(loader), refresh_per_second=1/refresh_rate, screen=True) as live:
            try:
                while True:
                    live.update(generate_monitor_layout(loader))
                    time.sleep(refresh_rate)
            except KeyboardInterrupt:
                console.print("\n[yellow]Monitor stopped by user[/yellow]")
                
    except Exception as e:
        handle_generic_error("live monitor", e)


@cli.command()
@click.option("--period", default="week", type=click.Choice(["day", "week", "month"]), help="Summary period")
@click.option("--format", "output_format", default="console", type=click.Choice(["console", "csv"]), help="Output format")
def summary(period: str, output_format: str) -> None:
    """Generate performance summary for the specified period."""
    logger.info("Performance summary started", period=period)
    
    try:
        console.print(
            Panel(
                f"[blue]Generating {period} performance summary...[/blue]",
                title="Performance Summary",
                border_style="blue",
            )
        )
        
        # This is a placeholder implementation - in real system would analyze trade history
        current_date = datetime.now().strftime("%Y-%m-%d")
        
        if output_format == "console":
            display_performance_summary(period, current_date)
        else:
            export_performance_csv(period, current_date)
            
        logger.info("Performance summary completed", period=period, format=output_format)
        
    except Exception as e:
        handle_generic_error("generating summary", e)


@cli.command()
@click.option("--symbol", help="Filter by trading symbol")
@click.option("--days", default=30, help="Number of days to look back")
@click.option("--format", "output_format", default="console", type=click.Choice(["console", "csv"]), help="Output format")
def history(symbol: Optional[str], days: int, output_format: str) -> None:
    """Display trade history with optional filtering."""
    logger.info("Trade history requested", symbol=symbol, days=days)
    
    try:
        console.print(
            Panel(
                f"[blue]Loading trade history (last {days} days)...[/blue]",
                title="Trade History",
                border_style="blue",
            )
        )
        
        # This is a placeholder implementation - in real system would load from CSV files
        if output_format == "console":
            display_trade_history(symbol, days)
        else:
            export_trade_history_csv(symbol, days)
            
        logger.info("Trade history completed", symbol=symbol, days=days, format=output_format)
        
    except Exception as e:
        handle_generic_error("loading history", e)


@cli.command()
@click.option("--config", is_flag=True, help="Check configuration files and settings")
@click.option("--plans", is_flag=True, help="Check trade plans directory and files")
@click.option("--permissions", is_flag=True, help="Check file and directory permissions")
@click.option("--export-debug", is_flag=True, help="Export debug information to file")
def doctor(config: bool, plans: bool, permissions: bool, export_debug: bool) -> None:
    """Run diagnostic checks and provide troubleshooting information."""
    logger.info("Diagnostic checks started")
    
    try:
        console.print(
            Panel(
                "[blue]🏥 Auto-Trader Health Check[/blue]\n"
                "Running diagnostic checks...",
                title="System Diagnostics",
                border_style="blue",
            )
        )
        
        # If no specific checks specified, run all
        if not any([config, plans, permissions]):
            config = plans = permissions = True
            
        diagnostic_results = []
        
        # Configuration checks
        if config:
            console.print("[blue]🔧 Checking configuration...[/blue]")
            config_results = check_configuration()
            diagnostic_results.extend(config_results)
            
        # Plans directory checks
        if plans:
            console.print("[blue]📄 Checking trade plans...[/blue]")
            plans_results = check_trade_plans()
            diagnostic_results.extend(plans_results)
            
        # Permission checks
        if permissions:
            console.print("[blue]🔒 Checking permissions...[/blue]")
            permission_results = check_permissions()
            diagnostic_results.extend(permission_results)
            
        # Show summary
        display_diagnostic_summary(diagnostic_results)
        
        # Export debug information if requested
        if export_debug:
            export_debug_information(diagnostic_results)
            
        logger.info("Diagnostic checks completed")
        
    except Exception as e:
        handle_generic_error("diagnostic checks", e)


@cli.command()
def help_system() -> None:
    """Display detailed help information."""
    console.print(
        Panel(
            "[bold blue]Auto-Trader Help System[/bold blue]\n\n"
            "[bold]Configuration Commands:[/bold]\n"
            "• validate-config  - Validate configuration files\n"
            "• setup           - Run interactive setup wizard\n\n"
            "[bold]Trade Plan Commands:[/bold]\n"
            "• validate-plans  - Validate trade plan YAML files\n"
            "• list-plans      - List loaded trade plans with filtering\n"
            "• create-plan     - Create new trade plan from template\n"
            "• list-templates  - List available trade plan templates\n\n"
            "[bold]Monitoring & Analysis:[/bold]\n"
            "• monitor         - Live system status dashboard\n"
            "• summary         - Performance summary (day/week/month)\n"
            "• history         - Trade history with filtering\n\n"
            "[bold]Configuration Files:[/bold]\n"
            "• .env            - Environment variables and secrets\n"
            "• config.yaml     - System configuration\n"
            "• user_config.yaml - User preferences and defaults\n\n"
            "[bold]Trade Plan Files:[/bold]\n"
            "• data/trade_plans/*.yaml - Trade plan definitions\n"
            "• data/trade_plans/templates/*.yaml - Plan templates\n\n"
            "[bold]Example Usage:[/bold]\n"
            "auto-trader setup\n"
            "auto-trader validate-config --verbose\n"
            "auto-trader validate-plans --verbose\n"
            "auto-trader list-plans --status awaiting_entry\n"
            "auto-trader monitor --refresh-rate 3\n"
            "auto-trader summary --period week\n"
            "auto-trader history --symbol AAPL --days 7",
            title="Help System",
            border_style="blue",
        )
    )


# All utility functions moved to separate modules for better organization


if __name__ == "__main__":
    cli()
