"""CLI commands for Auto-Trader application."""

import sys
import time
import asyncio
from pathlib import Path
from typing import Optional
from datetime import datetime

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from rich.live import Live
from rich.layout import Layout
from rich.text import Text

from config import Settings, ConfigLoader
from ..logging_config import get_logger
from ..models import (
    TradePlanLoader,
    TemplateManager,
    TradePlanStatus,
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
            if not config_loader.system_config.trading.simulation_mode:
                console.print(
                    Panel(
                        "[bold red]⚠ LIVE TRADING MODE DETECTED[/bold red]\n\n"
                        "[yellow]This configuration will trade with REAL MONEY.[/yellow]\n"
                        "Ensure thorough testing in simulation mode before enabling live trading.",
                        title="Trading Mode Warning",
                        border_style="red",
                    )
                )

            if verbose:
                _display_config_summary(config_loader)

            logger.info("Configuration validation passed")

        else:
            console.print(
                Panel(
                    "[red]✗ Configuration validation failed![/red]",
                    title="Validation Result",
                    border_style="red",
                )
            )

            console.print("\n[bold red]Configuration Issues Found:[/bold red]")
            
            # Show first 3 issues by default (progressive disclosure)
            critical_issues = issues[:3]
            remaining_issues = issues[3:]
            
            for i, issue in enumerate(critical_issues, 1):
                console.print(f"  {i}. {issue}")
            
            if remaining_issues:
                console.print(f"\n[dim]... and {len(remaining_issues)} more issue(s)[/dim]")
                if verbose:
                    console.print("\n[bold]Additional Issues:[/bold]")
                    for i, issue in enumerate(remaining_issues, len(critical_issues) + 1):
                        console.print(f"  {i}. {issue}")
                else:
                    console.print("[dim]Use --verbose to see all issues[/dim]")
            
            # Add helpful next steps
            console.print(
                Panel(
                    "[bold]Quick Fixes:[/bold]\n"
                    "• Run 'auto-trader setup' to regenerate configuration files\n"
                    "• Check .env file for missing variables\n"
                    "• Ensure DISCORD_WEBHOOK_URL is set correctly",
                    title="Suggested Actions",
                    border_style="yellow"
                )
            )

            logger.error("Configuration validation failed", issues=issues)
            sys.exit(1)

    except Exception as e:
        console.print(f"[red]Error during validation: {e}[/red]")
        logger.error("Configuration validation error", error=str(e))
        sys.exit(1)


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
        env_file = output_dir / ".env"
        config_file = output_dir / "config.yaml"
        user_config_file = output_dir / "user_config.yaml"

        existing_files = [
            f for f in [env_file, config_file, user_config_file] if f.exists()
        ]

        if existing_files and not force:
            console.print(
                "\n[yellow]Warning: The following files already exist:[/yellow]"
            )
            for f in existing_files:
                console.print(f"  • {f}")
            console.print("\nUse --force to overwrite existing files.")
            return

        # Create configuration files
        _create_env_file(env_file)
        _create_config_file(config_file)
        _create_user_config_file(user_config_file)

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
        console.print(f"[red]Setup failed: {e}[/red]")
        logger.error("Setup wizard failed", error=str(e))
        sys.exit(1)


@cli.command()
@click.option(
    "--plans-dir",
    type=click.Path(exists=True, path_type=Path),
    help="Directory containing trade plan YAML files",
)
@click.option("--verbose", "-v", is_flag=True, help="Show detailed validation results")
def validate_plans(plans_dir: Optional[Path], verbose: bool) -> None:
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
                _display_plans_summary(loader)
                console.print("\n" + report)
                
        else:
            console.print(
                Panel(
                    "[yellow]⚠ No valid trade plans found[/yellow]",
                    title="Validation Result", 
                    border_style="yellow",
                )
            )
            
            # Enhanced error reporting with progressive disclosure
            validation_report = loader.get_validation_report()
            if "Error" in validation_report and not verbose:
                console.print(
                    Panel(
                        "[bold]Common Issues:[/bold]\n"
                        "• Check YAML syntax (indentation, colons, quotes)\n"
                        "• Verify required fields: plan_id, symbol, entry_level, stop_loss, take_profit\n"
                        "• Ensure risk_category is one of: small, normal, large\n"
                        "• Use --verbose to see detailed validation errors",
                        title="Quick Help",
                        border_style="yellow"
                    )
                )
            
            if verbose:
                console.print("\n" + report)
        
        logger.info("Trade plan validation completed", plan_count=len(plans))
        
    except Exception as e:
        console.print(f"[red]Error during validation: {e}[/red]")
        logger.error("Trade plan validation error", error=str(e))
        sys.exit(1)


@cli.command()
@click.option(
    "--plans-dir",
    type=click.Path(exists=True, path_type=Path),
    help="Directory containing trade plan YAML files",
)
@click.option("--status", help="Filter by status (awaiting_entry, position_open, completed)")
@click.option("--symbol", help="Filter by symbol")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed plan information")
def list_plans(plans_dir: Optional[Path], status: Optional[str], symbol: Optional[str], verbose: bool) -> None:
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
                console.print(f"[red]Invalid status: {status}[/red]")
                return
                
        if symbol:
            filtered_plans = [p for p in filtered_plans if p.symbol.upper() == symbol.upper()]
        
        # Display results
        if not filtered_plans:
            console.print(
                Panel(
                    "[yellow]No plans found matching filters[/yellow]",
                    title="Filtered Results",
                    border_style="yellow",
                )
            )
            return
        
        _display_plans_table(filtered_plans, verbose)
        
        # Show statistics
        stats = loader.get_stats()
        _display_stats_summary(stats)
        
        logger.info("List trade plans completed", filtered_count=len(filtered_plans))
        
    except Exception as e:
        console.print(f"[red]Error listing plans: {e}[/red]")
        logger.error("List trade plans error", error=str(e))
        sys.exit(1)


@cli.command()
@click.option("--output-dir", type=click.Path(path_type=Path), help="Output directory for created plan")
def create_plan() -> None:
    """Interactive wizard to create a new trade plan from template."""
    logger.info("Create trade plan wizard started")
    
    try:
        # Initialize template manager
        template_manager = TemplateManager()
        templates = template_manager.list_available_templates()
        
        if not templates:
            console.print(
                Panel(
                    "[red]No templates found! Please check your templates directory.[/red]",
                    title="Error",
                    border_style="red",
                )
            )
            return
        
        console.print(
            Panel(
                "[bold blue]Trade Plan Creation Wizard[/bold blue]\n"
                "This wizard will help you create a new trade plan.",
                title="Create Trade Plan",
                border_style="blue",
            )
        )
        
        # Show available templates
        console.print("\n[bold]Available Templates:[/bold]")
        template_names = list(templates.keys())
        for i, name in enumerate(template_names, 1):
            doc_info = template_manager.get_template_documentation(name)
            description = doc_info.get("description", "No description")
            console.print(f"  {i}. [cyan]{name}[/cyan] - {description}")
        
        # Get template choice
        template_choice = Prompt.ask(
            "\nSelect template", 
            choices=[str(i) for i in range(1, len(template_names) + 1)]
        )
        template_name = template_names[int(template_choice) - 1]
        
        console.print(f"\n[green]Selected template: {template_name}[/green]")
        
        # Get plan data interactively
        plan_data = _get_plan_data_interactive()
        
        # Create output file path
        output_dir = Path("data/trade_plans") if not click.get_current_context().params.get("output_dir") else click.get_current_context().params["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / f"{plan_data['plan_id']}.yaml"
        
        # Create the plan
        trade_plan = template_manager.create_plan_from_template(
            template_name, 
            plan_data, 
            output_file
        )
        
        console.print(
            Panel(
                f"[green]✓ Trade plan created successfully![/green]\n\n"
                f"[bold]Plan ID:[/bold] {trade_plan.plan_id}\n"
                f"[bold]Symbol:[/bold] {trade_plan.symbol}\n"
                f"[bold]Entry Level:[/bold] ${trade_plan.entry_level}\n"
                f"[bold]Risk Category:[/bold] {trade_plan.risk_category}\n"
                f"[bold]File:[/bold] {output_file}",
                title="Plan Created",
                border_style="green",
            )
        )
        
        logger.info("Trade plan created successfully", plan_id=trade_plan.plan_id)
        
    except Exception as e:
        console.print(f"[red]Error creating plan: {e}[/red]")
        logger.error("Create trade plan error", error=str(e))
        sys.exit(1)


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
        console.print(f"[red]Error listing templates: {e}[/red]")
        logger.error("List templates error", error=str(e))
        sys.exit(1)


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
        
        with Live(_generate_monitor_layout(loader), refresh_per_second=1/refresh_rate, screen=True) as live:
            try:
                while True:
                    live.update(_generate_monitor_layout(loader))
                    time.sleep(refresh_rate)
            except KeyboardInterrupt:
                console.print("\n[yellow]Monitor stopped by user[/yellow]")
                
    except Exception as e:
        console.print(f"[red]Monitor error: {e}[/red]")
        logger.error("Live monitor error", error=str(e))
        sys.exit(1)


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
            _display_performance_summary(period, current_date)
        else:
            _export_performance_csv(period, current_date)
            
        logger.info("Performance summary completed", period=period, format=output_format)
        
    except Exception as e:
        console.print(f"[red]Error generating summary: {e}[/red]")
        logger.error("Performance summary error", error=str(e))
        sys.exit(1)


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
            _display_trade_history(symbol, days)
        else:
            _export_trade_history_csv(symbol, days)
            
        logger.info("Trade history completed", symbol=symbol, days=days, format=output_format)
        
    except Exception as e:
        console.print(f"[red]Error loading history: {e}[/red]")
        logger.error("Trade history error", error=str(e))
        sys.exit(1)


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


def _display_config_summary(config_loader: ConfigLoader) -> None:
    """Display configuration summary in verbose mode."""
    system_config = config_loader.system_config
    user_preferences = config_loader.user_preferences

    # System Configuration Table
    system_table = Table(title="System Configuration")
    system_table.add_column("Setting", style="cyan")
    system_table.add_column("Value", style="white")

    system_table.add_row("Simulation Mode", str(system_config.trading.simulation_mode))
    system_table.add_row(
        "Market Hours Only", str(system_config.trading.market_hours_only)
    )
    system_table.add_row("Default Timeframe", system_config.trading.default_timeframe)
    system_table.add_row(
        "Max Position %", f"{system_config.risk.max_position_percent}%"
    )
    system_table.add_row(
        "Daily Loss Limit %", f"{system_config.risk.daily_loss_limit_percent}%"
    )
    system_table.add_row(
        "Max Open Positions", str(system_config.risk.max_open_positions)
    )
    system_table.add_row("Log Level", system_config.logging.level)

    # User Preferences Table
    user_table = Table(title="User Preferences")
    user_table.add_column("Setting", style="cyan")
    user_table.add_column("Value", style="white")

    user_table.add_row(
        "Default Account Value", f"${user_preferences.default_account_value:,}"
    )
    user_table.add_row("Risk Category", user_preferences.default_risk_category)
    user_table.add_row(
        "Preferred Timeframes", ", ".join(user_preferences.preferred_timeframes)
    )

    console.print("\n")
    console.print(system_table)
    console.print("\n")
    console.print(user_table)


def _create_env_file(path: Path) -> None:
    """Create .env file with interactive prompts."""
    console.print("\n[bold]Environment Configuration:[/bold]")

    # Safety warning about simulation mode
    console.print(
        Panel(
            "[bold red]SAFETY NOTICE[/bold red]\n\n"
            "[yellow]This system trades with REAL MONEY when simulation mode is disabled.[/yellow]\n"
            "For your safety, simulation mode is REQUIRED for new installations.\n"
            "Only disable simulation mode after thorough testing and validation.",
            title="Trading Safety",
            border_style="red",
        )
    )

    # Get Discord webhook URL
    webhook_url = click.prompt(
        "Discord webhook URL",
        type=str,
        default="https://discord.com/api/webhooks/YOUR_WEBHOOK_URL_HERE",
    )

    # Get IBKR settings
    ibkr_host = click.prompt("IBKR Host", default="127.0.0.1")
    ibkr_port = click.prompt("IBKR Port", default=7497, type=int)
    ibkr_client_id = click.prompt("IBKR Client ID", default=1, type=int)

    # Force simulation mode for safety
    console.print("\n[bold yellow]Simulation mode is ENABLED by default for safety.[/bold yellow]")
    simulation_mode = True
    debug = click.confirm("Enable debug logging?", default=False)

    env_content = f"""# Auto-Trader Environment Configuration
# Generated by setup wizard

# Interactive Brokers Configuration
IBKR_HOST={ibkr_host}
IBKR_PORT={ibkr_port}
IBKR_CLIENT_ID={ibkr_client_id}

# Discord Integration
DISCORD_WEBHOOK_URL={webhook_url}

# System Settings
SIMULATION_MODE={str(simulation_mode).lower()}
DEBUG={str(debug).lower()}

# File Paths (optional - defaults will be used if not set)
CONFIG_FILE=config.yaml
USER_CONFIG_FILE=user_config.yaml
LOGS_DIR=logs
"""

    path.write_text(env_content)
    console.print(f"[green]✓ Created {path}[/green]")


def _create_config_file(path: Path) -> None:
    """Create config.yaml with default values."""
    config_content = """# Auto-Trader System Configuration
# Generated by setup wizard

# Interactive Brokers Configuration
ibkr:
  host: "127.0.0.1"
  port: 7497
  client_id: 1
  timeout: 30

# Risk Management Configuration  
risk:
  max_position_percent: 10.0
  daily_loss_limit_percent: 2.0
  max_open_positions: 5
  min_account_balance: 1000

# Trading System Configuration
trading:
  simulation_mode: true
  market_hours_only: true
  default_timeframe: "15min"
  order_timeout: 60

# Logging Configuration
logging:
  level: "INFO"
  rotation: "1 day"
  retention: "30 days"
  format: "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {name}:{function}:{line} | {message}"
"""

    path.write_text(config_content)
    console.print(f"[green]✓ Created {path}[/green]")


def _create_user_config_file(path: Path) -> None:
    """Create user_config.yaml with interactive prompts."""
    console.print("\n[bold]User Preferences:[/bold]")

    # Get user preferences
    account_value = click.prompt("Default account value", default=10000, type=int)

    risk_category = click.prompt(
        "Risk category",
        type=click.Choice(["conservative", "moderate", "aggressive"]),
        default="conservative",
    )

    user_config_content = f"""# Auto-Trader User Preferences Configuration
# Generated by setup wizard

# Account Configuration
default_account_value: {account_value}

# Risk Profile
default_risk_category: "{risk_category}"

# Trading Preferences
preferred_timeframes:
  - "15min"
  - "1hour"

# Default Execution Functions by Trade Type
default_execution_functions:
  long: "close_above"
  short: "close_below"
"""

    path.write_text(user_config_content)
    console.print(f"[green]✓ Created {path}[/green]")


def _display_plans_summary(loader: TradePlanLoader) -> None:
    """Display summary of loaded plans."""
    stats = loader.get_stats()
    
    console.print("\n[bold]Plans Summary:[/bold]")
    console.print(f"  Total Plans: {stats['total_plans']}")
    console.print(f"  Files Loaded: {stats['files_loaded']}")
    
    if stats['by_status']:
        console.print("\n[bold]By Status:[/bold]")
        for status, count in stats['by_status'].items():
            console.print(f"  {status}: {count}")
    
    if stats['by_symbol']:
        console.print("\n[bold]By Symbol:[/bold]")
        for symbol, count in stats['by_symbol'].items():
            console.print(f"  {symbol}: {count}")


def _display_plans_table(plans: list, verbose: bool) -> None:
    """Display plans in a formatted table."""
    table = Table(title="Trade Plans")
    table.add_column("Plan ID", style="cyan")
    table.add_column("Symbol", style="yellow")
    table.add_column("Status", style="white")
    table.add_column("Entry", style="green")
    table.add_column("Stop", style="red")
    table.add_column("Target", style="green")
    table.add_column("Risk", style="white")
    
    if verbose:
        table.add_column("Entry Function", style="blue")
        table.add_column("Timeframe", style="blue")
    
    for plan in plans:
        status_color = {
            "awaiting_entry": "[yellow]",
            "position_open": "[green]",
            "completed": "[blue]",
            "cancelled": "[red]",
            "error": "[red]"
        }.get(str(plan.status), "[white]")
        
        row = [
            plan.plan_id,
            plan.symbol,
            f"{status_color}{plan.status}[/]",
            f"${plan.entry_level}",
            f"${plan.stop_loss}",
            f"${plan.take_profit}",
            str(plan.risk_category),
        ]
        
        if verbose:
            row.extend([
                plan.entry_function.function_type,
                plan.entry_function.timeframe,
            ])
        
        table.add_row(*row)
    
    console.print(table)


def _display_stats_summary(stats: dict) -> None:
    """Display statistics summary."""
    stats_table = Table(title="Statistics")
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", style="white")
    
    stats_table.add_row("Total Plans", str(stats["total_plans"]))
    stats_table.add_row("Files Loaded", str(stats["files_loaded"]))
    
    console.print("\n")
    console.print(stats_table)


def _generate_monitor_layout(loader: TradePlanLoader) -> Layout:
    """Generate the live monitor layout."""
    try:
        # Load current plans
        plans = loader.load_all_plans(validate=False)
        stats = loader.get_stats()
        
        # Create layout
        layout = Layout()
        layout.split_column(
            Layout(name="header", size=6),
            Layout(name="body"),
            Layout(name="footer", size=3)
        )
        
        # Header with system status
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S EST")
        header_content = Panel(
            f"[bold]AUTO-TRADER LIVE MONITOR - {current_time}[/bold]\n\n"
            "🔌 IBKR: [red]Disconnected[/red] | Discord: [yellow]Unknown[/yellow] | Mode: [green]SIMULATION[/green]\n"
            "🛡️  Portfolio Risk: [green]0.0% / 10.0%[/green] | Available: [blue]$10,000[/blue]",
            title="System Status",
            border_style="blue"
        )
        layout["header"].update(header_content)
        
        # Body with active plans monitoring
        if plans:
            active_plans = [p for p in plans.values() if p.status.value in ["awaiting_entry", "position_open"]]
            
            if active_plans:
                monitoring_table = Table(title="Active Plan Monitoring")
                monitoring_table.add_column("Symbol", style="cyan")
                monitoring_table.add_column("Timeframe", style="white")
                monitoring_table.add_column("Last Price", style="yellow")
                monitoring_table.add_column("Entry Target", style="green")
                monitoring_table.add_column("Status", style="white")
                monitoring_table.add_column("Risk", style="red")
                
                for plan in active_plans[:5]:  # Show max 5 active plans
                    status_icon = "↗️" if plan.status.value == "awaiting_entry" else "✅"
                    monitoring_table.add_row(
                        plan.symbol,
                        plan.entry_function.timeframe,
                        f"${float(plan.entry_level):.2f}",  # Placeholder - real system would have live prices
                        f"${float(plan.entry_level):.2f}",
                        f"{status_icon} {plan.status.value}",
                        plan.risk_category
                    )
                
                body_content = monitoring_table
            else:
                body_content = Panel(
                    "[yellow]No active plans to monitor[/yellow]\n\n"
                    f"Total plans loaded: {stats['total_plans']}\n"
                    f"Files processed: {stats['files_loaded']}",
                    title="Plan Status"
                )
        else:
            body_content = Panel(
                "[red]No trade plans loaded[/red]\n\n"
                "Use 'auto-trader list-plans' to check for available plans",
                title="No Plans Found"
            )
        
        layout["body"].update(body_content)
        
        # Footer with controls
        footer_content = Panel(
            "[dim]Press Ctrl+C to quit | Refresh rate: 5s | Last update: " + current_time + "[/dim]",
            border_style="dim"
        )
        layout["footer"].update(footer_content)
        
        return layout
        
    except Exception as e:
        # Return error layout
        error_layout = Layout()
        error_layout.update(Panel(f"[red]Monitor Error: {e}[/red]", border_style="red"))
        return error_layout


def _display_performance_summary(period: str, current_date: str) -> None:
    """Display performance summary in console format."""
    # Placeholder data - real implementation would calculate from trade history
    summary_table = Table(title=f"{period.title()} Performance Summary - {current_date}")
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="white")
    
    summary_table.add_row("📊 Period", f"{period.title()} ending {current_date}")
    summary_table.add_row("💰 Total P&L", "[green]+$1,247 (+6.2%)[/green]")
    summary_table.add_row("📈 Trades Executed", "23")
    summary_table.add_row("🎯 Win Rate", "[green]65% (15W / 8L)[/green]")
    summary_table.add_row("🏆 Best Trade", "[green]AAPL +$485[/green]")
    summary_table.add_row("📉 Worst Trade", "[red]TSLA -$145[/red]")
    summary_table.add_row("⏱️ Avg Hold Time", "4h 23m")
    summary_table.add_row("🔧 Top Function", "close_above_15min (70% win rate)")
    
    console.print(summary_table)
    
    console.print(
        Panel(
            "[yellow]This is placeholder data. Real implementation would analyze trade history files.[/yellow]",
            title="Note",
            border_style="yellow"
        )
    )


def _export_performance_csv(period: str, current_date: str) -> None:
    """Export performance summary to CSV."""
    csv_filename = f"performance_summary_{period}_{current_date}.csv"
    console.print(f"[green]✓ Performance summary exported to {csv_filename}[/green]")
    console.print("[yellow]Note: This is a placeholder. Real implementation would create actual CSV file.[/yellow]")


def _display_trade_history(symbol: Optional[str], days: int) -> None:
    """Display trade history in console format."""
    history_table = Table(title=f"Trade History - Last {days} Days")
    history_table.add_column("Date", style="white")
    history_table.add_column("Symbol", style="cyan")
    history_table.add_column("Action", style="white")
    history_table.add_column("Price", style="yellow")
    history_table.add_column("Quantity", style="white")
    history_table.add_column("P&L", style="white")
    history_table.add_column("Function", style="blue")
    
    # Placeholder data - real implementation would load from CSV files
    sample_trades = [
        ("2025-08-15", "AAPL", "entry", "$180.45", "100", "$0.00", "close_above"),
        ("2025-08-15", "AAPL", "exit", "$185.25", "100", "[green]+$480.00[/green]", "take_profit"),
        ("2025-08-14", "MSFT", "entry", "$415.20", "50", "$0.00", "close_above"),
        ("2025-08-14", "MSFT", "exit", "$412.80", "50", "[red]-$120.00[/red]", "stop_loss"),
    ]
    
    for trade in sample_trades:
        if symbol is None or symbol.upper() in trade[1]:
            history_table.add_row(*trade)
    
    console.print(history_table)
    
    console.print(
        Panel(
            "[yellow]This is placeholder data. Real implementation would load from CSV trade history files.[/yellow]",
            title="Note",
            border_style="yellow"
        )
    )


def _export_trade_history_csv(symbol: Optional[str], days: int) -> None:
    """Export trade history to CSV."""
    filter_suffix = f"_{symbol}" if symbol else ""
    csv_filename = f"trade_history_{days}days{filter_suffix}.csv"
    console.print(f"[green]✓ Trade history exported to {csv_filename}[/green]")
    console.print("[yellow]Note: This is a placeholder. Real implementation would create actual CSV file.[/yellow]")


def _get_plan_data_interactive() -> dict:
    """Get plan data from user through interactive prompts."""
    console.print("\n[bold]Plan Information:[/bold]")
    
    # Get basic plan info
    symbol = Prompt.ask("Trading symbol (e.g., AAPL)", default="AAPL").upper()
    
    # Generate plan ID suggestion
    from datetime import datetime
    date_str = datetime.now().strftime("%Y%m%d")
    suggested_plan_id = f"{symbol}_{date_str}_001"
    
    plan_id = Prompt.ask("Plan ID", default=suggested_plan_id)
    
    # Get price levels
    entry_level = click.prompt("Entry level", type=float)
    stop_loss = click.prompt("Stop loss", type=float)
    take_profit = click.prompt("Take profit", type=float)
    
    # Get risk category
    risk_category = Prompt.ask(
        "Risk category",
        choices=["small", "normal", "large"],
        default="normal"
    )
    
    # Get execution function details
    console.print("\n[bold]Entry Function:[/bold]")
    threshold = click.prompt("Entry threshold", type=float, default=entry_level)
    
    return {
        "plan_id": plan_id,
        "symbol": symbol,
        "entry_level": entry_level,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "risk_category": risk_category,
        "threshold": threshold,
    }


if __name__ == "__main__":
    cli()
