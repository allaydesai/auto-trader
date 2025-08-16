"""Display utilities for CLI commands."""

from typing import Optional
from datetime import datetime

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.layout import Layout

from config import ConfigLoader
from ..models import TradePlanLoader


console = Console()


def display_config_summary(config_loader: ConfigLoader) -> None:
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


def display_plans_summary(loader: TradePlanLoader) -> None:
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


def display_plans_table(plans: list, verbose: bool, show_risk_info: bool = False) -> None:
    """Display plans in a formatted table with optional risk information."""
    table = Table(title="Trade Plans")
    table.add_column("Plan ID", style="cyan")
    table.add_column("Symbol", style="yellow")
    table.add_column("Status", style="white")
    table.add_column("Entry", style="green")
    table.add_column("Stop", style="red")
    table.add_column("Target", style="green")
    table.add_column("Risk", style="white")
    
    if show_risk_info:
        table.add_column("Position Size", style="magenta")
        table.add_column("$ Risk", style="red")
    
    if verbose:
        table.add_column("Entry Function", style="blue")
        table.add_column("Timeframe", style="blue")
    
    # Initialize risk manager if needed
    risk_manager = None
    if show_risk_info:
        try:
            from decimal import Decimal
            from pathlib import Path
            from ..risk_management import RiskManager
            
            # Use default account value for now - can be enhanced later to read from config
            account_value = Decimal("10000.00")
            state_file = Path("data/state/portfolio_registry.json")
            
            risk_manager = RiskManager(
                account_value=account_value,
                state_file=state_file,
            )
        except Exception:
            # If risk calculation fails, continue without it
            show_risk_info = False
    
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
        
        # Add risk information if requested
        if show_risk_info and risk_manager:
            try:
                result = risk_manager.position_sizer.calculate_position_size(
                    account_value=risk_manager.account_value,
                    risk_category=plan.risk_category,
                    entry_price=plan.entry_level,
                    stop_loss=plan.stop_loss,
                )
                row.extend([
                    f"{result.position_size:,}",
                    f"${result.dollar_risk:.0f}",
                ])
            except Exception:
                # If calculation fails for this plan, show N/A
                row.extend(["N/A", "N/A"])
        
        if verbose:
            row.extend([
                plan.entry_function.function_type,
                plan.entry_function.timeframe,
            ])
        
        table.add_row(*row)
    
    console.print(table)


def display_stats_summary(stats: dict) -> None:
    """Display statistics summary."""
    stats_table = Table(title="Statistics")
    stats_table.add_column("Metric", style="cyan")
    stats_table.add_column("Value", style="white")
    
    stats_table.add_row("Total Plans", str(stats["total_plans"]))
    stats_table.add_row("Files Loaded", str(stats["files_loaded"]))
    
    console.print("\n")
    console.print(stats_table)


def display_performance_summary(period: str, current_date: str) -> None:
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


def display_trade_history(symbol: Optional[str], days: int) -> None:
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


def generate_monitor_layout(loader: TradePlanLoader) -> Layout:
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
                        f"${plan.entry_level:.2f}",  # Placeholder - real system would have live prices
                        f"${plan.entry_level:.2f}",
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