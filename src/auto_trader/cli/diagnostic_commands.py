"""Diagnostic and troubleshooting CLI commands for Auto-Trader application."""

import click
from rich.console import Console
from rich.panel import Panel

from ..logging_config import get_logger
from .diagnostic_utils import (
    check_configuration,
    check_trade_plans,
    check_permissions,
    display_diagnostic_summary,
    export_debug_information,
)
from .error_utils import handle_generic_error


console = Console()
logger = get_logger("cli", "cli")


@click.command()
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