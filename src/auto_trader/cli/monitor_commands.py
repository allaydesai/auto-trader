"""Monitoring and analysis CLI commands for Auto-Trader application."""

import time
from pathlib import Path
from typing import Optional
from datetime import datetime

import click
from rich.console import Console
from rich.panel import Panel
from rich.live import Live

from ..logging_config import get_logger
from ..models import TradePlanLoader
from .display_utils import (
    display_performance_summary,
    display_trade_history,
    generate_monitor_layout,
)
from .file_utils import export_performance_csv, export_trade_history_csv
from .error_utils import handle_generic_error


console = Console()
logger = get_logger("cli", "cli")


@click.command()
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


@click.command()
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


@click.command()
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