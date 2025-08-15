"""Error handling utilities for CLI commands."""

import sys
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel

from ..logging_config import get_logger

if TYPE_CHECKING:
    from ..models import TradePlanLoader


console = Console()
logger = get_logger("cli", "cli")


def handle_config_validation_failure(issues: List[str], verbose: bool) -> None:
    """Handle configuration validation failure with enhanced error reporting."""
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


def handle_file_permission_error(file_path: Path, operation: str, error: Exception) -> None:
    """Handle file permission errors with enhanced context."""
    console.print(
        Panel(
            f"[red]File Permission Error[/red]\n\n"
            f"[bold]Operation:[/bold] {operation}\n"
            f"[bold]File:[/bold] {file_path}\n"
            f"[bold]Error:[/bold] {error}\n\n"
            f"[bold]Possible Solutions:[/bold]\n"
            f"• Check file/directory permissions\n"
            f"• Ensure the directory exists and is writable\n"
            f"• Verify you have sufficient privileges\n"
            f"• Check if file is in use by another process",
            title="Permission Error",
            border_style="red",
        )
    )
    
    logger.error(
        "File permission error", 
        file_path=str(file_path), 
        operation=operation, 
        error=str(error),
        error_type=type(error).__name__
    )


def handle_validation_plan_failure(
    loader: "TradePlanLoader", 
    plans_dir: Optional[Path], 
    verbose: bool
) -> None:
    """Handle trade plan validation failure with progressive error disclosure."""
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
        console.print("\n" + validation_report)


def handle_generic_error(operation: str, error: Exception) -> None:
    """Handle generic errors with proper logging and exit."""
    console.print(f"[red]Error during {operation}: {error}[/red]")
    logger.error(f"{operation} error", error=str(error), error_type=type(error).__name__)
    sys.exit(1)


def show_safety_warning(simulation_mode: bool) -> None:
    """Show safety warning if not in simulation mode."""
    if not simulation_mode:
        console.print(
            Panel(
                "[bold red]⚠ LIVE TRADING MODE DETECTED[/bold red]\n\n"
                "[yellow]This configuration will trade with REAL MONEY.[/yellow]\n"
                "Ensure thorough testing in simulation mode before enabling live trading.",
                title="Trading Mode Warning",
                border_style="red",
            )
        )


def check_existing_files(
    output_dir: Path, 
    force: bool
) -> bool:
    """Check for existing configuration files and handle conflicts."""
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
        return False
    
    return True