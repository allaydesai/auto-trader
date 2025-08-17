"""Risk management CLI commands for Auto-Trader application."""

from decimal import Decimal
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..logging_config import get_logger
from ..risk_management import RiskManager, InvalidPositionSizeError
from .wizard_constants import RISK_CATEGORY_CHOICES, RISK_CATEGORY_HELP_TEXT
from .error_utils import handle_generic_error
from config import ConfigLoader

console = Console()
logger = get_logger("cli", "cli")


@click.command("calculate-position-size")
@click.option(
    "--symbol",
    required=True,
    help="Trading symbol (e.g., AAPL, MSFT)",
)
@click.option(
    "--entry",
    type=float,
    required=True,
    help="Entry price for the trade",
)
@click.option(
    "--stop",
    type=float,
    required=True,
    help="Stop loss price for the trade",
)
@click.option(
    "--risk",
    type=click.Choice(RISK_CATEGORY_CHOICES, case_sensitive=False),
    default="normal",
    help=RISK_CATEGORY_HELP_TEXT,
)
@click.option(
    "--account-value",
    type=float,
    help="Account value for calculations (overrides config)",
)
@click.option(
    "--state-file",
    type=click.Path(path_type=Path),
    help="Portfolio state file path (defaults to config)",
)
def calculate_position_size(
    symbol: str,
    entry: float,
    stop: float,
    risk: str,
    account_value: Optional[float],
    state_file: Optional[Path],
) -> None:
    """Calculate position size based on risk parameters.
    
    Examples:
        auto-trader calculate-position-size --symbol AAPL --entry 180.50 --stop 178.00 --risk normal
        auto-trader calculate-position-size --symbol MSFT --entry 420.00 --stop 400.00 --risk large --account-value 25000
    """
    try:
        logger.info("Position size calculation started", symbol=symbol, entry=entry, stop=stop, risk=risk)
        
        # Load configuration if account value not provided
        if account_value is None:
            config_loader = ConfigLoader()
            account_value = float(config_loader.user_preferences.default_account_value)
        
        # Convert to Decimal for calculations
        account_decimal = Decimal(str(account_value))
        entry_decimal = Decimal(str(entry))
        stop_decimal = Decimal(str(stop))
        
        # Determine state file path
        if state_file is None:
            state_file = Path("data/state/portfolio_registry.json")
        
        # Create risk manager
        risk_manager = RiskManager(
            account_value=account_decimal,
            state_file=state_file,
        )
        
        # Calculate position size
        result = risk_manager.position_sizer.calculate_position_size(
            account_value=account_decimal,
            risk_category=risk,
            entry_price=entry_decimal,
            stop_loss=stop_decimal,
        )
        
        # Check portfolio risk limit
        portfolio_check = risk_manager.check_portfolio_risk_limit(result.dollar_risk)
        
        # Display results
        _display_position_size_result(
            symbol=symbol,
            entry=entry,
            stop=stop,
            risk=risk,
            account_value=account_value,
            result=result,
            portfolio_check=portfolio_check,
            risk_manager=risk_manager,
        )
        
        logger.info(
            "Position size calculation completed",
            symbol=symbol,
            position_size=result.position_size,
            dollar_risk=float(result.dollar_risk),
            portfolio_risk=float(result.portfolio_risk_percentage),
        )
        
    except InvalidPositionSizeError as e:
        logger.error("Position size calculation failed", error=str(e))
        console.print("\n❌ [bold red]Calculation Failed[/bold red]")
        console.print(f"🔧 [yellow]{str(e)}[/yellow]")
        console.print("💡 [dim]Check your entry and stop loss prices[/dim]")
        
    except Exception as e:
        handle_generic_error(e, "calculating position size")


@click.command("portfolio-risk-summary")
@click.option(
    "--state-file",
    type=click.Path(path_type=Path),
    help="Portfolio state file path (defaults to config)",
)
@click.option(
    "--account-value",
    type=float,
    help="Account value for calculations (overrides config)",
)
def portfolio_risk_summary(
    state_file: Optional[Path],
    account_value: Optional[float],
) -> None:
    """Display current portfolio risk summary and position details."""
    try:
        logger.info("Portfolio risk summary requested")
        
        # Load configuration if account value not provided
        if account_value is None:
            config_loader = ConfigLoader()
            account_value = float(config_loader.user_preferences.default_account_value)
        
        # Convert to Decimal
        account_decimal = Decimal(str(account_value))
        
        # Determine state file path
        if state_file is None:
            state_file = Path("data/state/portfolio_registry.json")
        
        # Create risk manager
        risk_manager = RiskManager(
            account_value=account_decimal,
            state_file=state_file,
        )
        
        # Get portfolio summary
        summary = risk_manager.get_portfolio_summary()
        
        # Display results
        _display_portfolio_summary(summary, account_value)
        
        logger.info(
            "Portfolio risk summary displayed",
            position_count=summary["position_count"],
            portfolio_risk=summary["current_risk_percentage"],
            daily_losses=summary["daily_losses"],
        )
        
    except Exception as e:
        handle_generic_error(e, "displaying portfolio risk summary")


def _display_position_size_result(
    symbol: str,
    entry: float,
    stop: float,
    risk: str,
    account_value: float,
    result,  # PositionSizeResult
    portfolio_check,  # RiskCheck
    risk_manager,  # RiskManager
) -> None:
    """Display position size calculation results with rich formatting."""
    
    # Title
    if portfolio_check.passed:
        title = "✅ Position Size Calculated"
        panel_style = "green"
    else:
        title = "⚠️  Position Size Calculated (Risk Warning)"
        panel_style = "yellow"
    
    # Create calculation details table
    calc_table = Table(show_header=False, box=None, padding=(0, 1))
    calc_table.add_column("Label", style="cyan")
    calc_table.add_column("Value", style="white")
    
    calc_table.add_row("📊 Account Value:", f"${account_value:,.2f}")
    # Get risk percentage from the position sizer
    risk_percentage = risk_manager.position_sizer.get_risk_percentage(risk)
    calc_table.add_row("🎯 Risk Category:", f"{risk.title()} ({risk_percentage}%)")
    calc_table.add_row("📍 Entry Price:", f"${entry:.2f}")
    calc_table.add_row("🛑 Stop Loss:", f"${stop:.2f}")
    calc_table.add_row("💰 Risk Amount:", f"${result.dollar_risk:.2f}")
    calc_table.add_row("📈 Position Size:", f"{result.position_size:,} shares")
    
    # Portfolio risk details
    risk_table = Table(show_header=False, box=None, padding=(0, 1))
    risk_table.add_column("Label", style="cyan")
    risk_table.add_column("Value", style="white")
    
    current_risk = portfolio_check.current_risk
    new_trade_risk = portfolio_check.new_trade_risk
    total_risk = portfolio_check.total_risk
    limit = portfolio_check.limit
    
    risk_table.add_row("📊 Current Portfolio Risk:", f"{current_risk:.1f}%")
    risk_table.add_row("📈 New Trade Risk:", f"{new_trade_risk:.1f}%")
    risk_table.add_row("🎯 Total Portfolio Risk:", f"{total_risk:.1f}%")
    risk_table.add_row("🔒 Risk Limit:", f"{limit:.1f}%")
    
    remaining_capacity = limit - total_risk
    if remaining_capacity >= 0:
        risk_table.add_row("💡 Remaining Capacity:", f"{remaining_capacity:.1f}%")
    
    # Display results
    console.print(Panel(title, style=panel_style))
    console.print(calc_table)
    console.print("\n[bold]Portfolio Risk Analysis:[/bold]")
    console.print(risk_table)
    
    # Risk warnings
    if not portfolio_check.passed:
        console.print("\n❌ [bold red]Trade Blocked - Portfolio Risk Exceeded[/bold red]")
        console.print(f"🔒 [yellow]{portfolio_check.reason}[/yellow]")
        console.print("🔧 [dim]Reduce position size or close existing positions[/dim]")
        console.print("📚 [dim]Help: auto-trader help risk-management[/dim]")
    elif total_risk > (limit * Decimal("0.8")):  # 80% of limit
        console.print(f"\n⚠️  [yellow]Portfolio risk approaching limit ({total_risk:.1f}% of {limit:.1f}%)[/yellow]")


def _display_portfolio_summary(summary: dict, account_value: float) -> None:
    """Display portfolio risk summary with rich formatting."""
    
    # Header
    console.print(Panel("[bold]Portfolio Risk Summary[/bold]", style="blue"))
    
    # Account overview
    overview_table = Table(title="Account Overview", show_header=False, box=None)
    overview_table.add_column("Label", style="cyan")
    overview_table.add_column("Value", style="white")
    
    overview_table.add_row("💰 Account Value:", f"${summary['account_value']:,.2f}")
    overview_table.add_row("📊 Current Risk:", f"{summary['current_risk_percentage']:.1f}%")
    overview_table.add_row("🔒 Risk Limit:", f"{summary['risk_limit']:.1f}%")
    overview_table.add_row("💡 Available Capacity:", f"{summary['remaining_capacity_percent']:.1f}%")
    overview_table.add_row("💵 Available Dollars:", f"${summary['remaining_capacity_dollars']:,.2f}")
    
    console.print(overview_table)
    
    # Daily loss tracking
    console.print("\n[bold]Daily Loss Tracking:[/bold]")
    loss_table = Table(show_header=False, box=None)
    loss_table.add_column("Label", style="cyan")
    loss_table.add_column("Value", style="white")
    
    loss_table.add_row("📉 Daily Losses:", f"${summary['daily_losses']:,.2f}")
    loss_table.add_row("🔒 Daily Limit:", f"${summary['daily_loss_limit']:,.2f}")
    loss_table.add_row("💡 Remaining:", f"${summary['daily_loss_remaining']:,.2f}")
    loss_table.add_row("📊 Usage:", f"{summary['daily_loss_percentage']:.1f}%")
    
    console.print(loss_table)
    
    # Position details
    if summary['position_count'] > 0:
        console.print(f"\n[bold]Open Positions ({summary['position_count']}):[/bold]")
        
        positions_table = Table()
        positions_table.add_column("Position ID", style="cyan")
        positions_table.add_column("Symbol", style="yellow")
        positions_table.add_column("Risk Amount", style="red")
        positions_table.add_column("Plan ID", style="blue")
        
        for position in summary['positions']:
            positions_table.add_row(
                position['position_id'],
                position['symbol'],
                f"${position['risk_amount']:,.2f}",
                position['plan_id'],
            )
        
        console.print(positions_table)
    else:
        console.print("\n💤 [dim]No open positions[/dim]")
    
    # Risk status indicators
    risk_percent = summary['current_risk_percentage']
    limit_percent = summary['risk_limit']
    
    if risk_percent == 0:
        console.print("\n🟢 [green]Portfolio is risk-free[/green]")
    elif risk_percent < (limit_percent * 0.5):
        console.print(f"\n🟢 [green]Portfolio risk is low ({risk_percent:.1f}%)[/green]")
    elif risk_percent < (limit_percent * 0.8):
        console.print(f"\n🟡 [yellow]Portfolio risk is moderate ({risk_percent:.1f}%)[/yellow]")
    else:
        console.print(f"\n🔴 [red]Portfolio risk is high ({risk_percent:.1f}%)[/red]")