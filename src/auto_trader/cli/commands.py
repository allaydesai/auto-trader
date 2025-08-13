"""CLI commands for Auto-Trader application."""

import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from config import Settings, ConfigLoader
from auto_trader.logging_config import get_logger


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

            console.print("\n[bold red]Issues found:[/bold red]")
            for i, issue in enumerate(issues, 1):
                console.print(f"  {i}. {issue}")

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
def help_system() -> None:
    """Display detailed help information."""
    console.print(
        Panel(
            "[bold blue]Auto-Trader Help System[/bold blue]\n\n"
            "[bold]Available Commands:[/bold]\n"
            "• validate-config  - Validate configuration files\n"
            "• setup           - Run interactive setup wizard\n"
            "• help-system     - Display this help information\n\n"
            "[bold]Configuration Files:[/bold]\n"
            "• .env            - Environment variables and secrets\n"
            "• config.yaml     - System configuration\n"
            "• user_config.yaml - User preferences and defaults\n\n"
            "[bold]Example Usage:[/bold]\n"
            "auto-trader setup\n"
            "auto-trader validate-config --verbose\n"
            "auto-trader validate-config --config-file custom_config.yaml",
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

    # Get system settings
    simulation_mode = click.confirm("Enable simulation mode?", default=True)
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


if __name__ == "__main__":
    cli()
