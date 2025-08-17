"""Interactive wizard utilities for trade plan creation with real-time validation."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from ..logging_config import get_logger
from ..models import (
    ExecutionFunction,
    RiskCategory,
    ValidationEngine,
)
from ..risk_management import RiskManager
from .field_validator import WizardFieldValidator
from config import ConfigLoader

logger = get_logger("wizard", "cli")
console = Console()


class WizardFieldCollector:
    """Collect and validate trade plan fields interactively."""
    
    def __init__(self, config_loader: ConfigLoader, risk_manager: RiskManager) -> None:
        """
        Initialize field collector with validation and risk management.
        
        Args:
            config_loader: Configuration loader for default values
            risk_manager: Risk manager for position sizing calculations
        """
        self.config_loader = config_loader
        self.risk_manager = risk_manager
        self.validation_engine = ValidationEngine()
        self.field_validator = WizardFieldValidator()
        self.console = Console()
        
        # Track collected values for validation
        self.collected_data: Dict[str, Any] = {}
        
        logger.info("WizardFieldCollector initialized")
    
    def collect_symbol(self, initial_value: Optional[str] = None) -> str:
        """
        Collect and validate trading symbol.
        
        Args:
            initial_value: Pre-populated value from CLI shortcut
            
        Returns:
            Validated trading symbol
        """
        while True:
            if initial_value:
                symbol = initial_value.upper()
                self.console.print(f"[cyan]Symbol (from CLI):[/cyan] {symbol}")
                initial_value = None  # Only use once
            else:
                symbol = Prompt.ask(
                    "[cyan]Trading symbol[/cyan] [dim](1-10 uppercase chars)[/dim]"
                ).upper()
            
            # Validate symbol using field validator
            validation_result = self.field_validator.validate_symbol(symbol)
            if validation_result["is_valid"]:
                self.collected_data["symbol"] = symbol
                logger.info("Symbol collected", symbol=symbol)
                return symbol
            else:
                self.console.print(
                    f"[red]❌ {validation_result['error']}[/red]"
                )
    
    def collect_entry_level(self, initial_value: Optional[str] = None) -> Decimal:
        """
        Collect and validate entry price level.
        
        Args:
            initial_value: Pre-populated value from CLI shortcut
            
        Returns:
            Validated entry price as Decimal
        """
        while True:
            if initial_value:
                entry_str = initial_value
                self.console.print(f"[cyan]Entry level (from CLI):[/cyan] {entry_str}")
                initial_value = None  # Only use once
            else:
                entry_str = Prompt.ask(
                    "[cyan]Entry level[/cyan] [dim](positive price, max 4 decimals)[/dim]"
                )
            
            try:
                entry_level = Decimal(entry_str)
                
                # Validate using field validator
                validation_result = self.field_validator.validate_entry_level(entry_level)
                if validation_result["is_valid"]:
                    self.collected_data["entry_level"] = entry_level
                    logger.info("Entry level collected", entry_level=float(entry_level))
                    return entry_level
                else:
                    self.console.print(
                        f"[red]❌ {validation_result['error']}[/red]"
                    )
                    continue
                
            except InvalidOperation:
                self.console.print("[red]❌ Invalid number format.[/red]")
    
    def collect_stop_loss(
        self, 
        entry_level: Decimal,
        initial_value: Optional[str] = None
    ) -> Decimal:
        """
        Collect and validate stop loss level.
        
        Args:
            entry_level: Entry price for validation
            initial_value: Pre-populated value from CLI shortcut
            
        Returns:
            Validated stop loss as Decimal
        """
        while True:
            if initial_value:
                stop_str = initial_value
                self.console.print(f"[cyan]Stop loss (from CLI):[/cyan] {stop_str}")
                initial_value = None  # Only use once
            else:
                stop_str = Prompt.ask(
                    "[cyan]Stop loss[/cyan] [dim](must differ from entry)[/dim]"
                )
            
            try:
                stop_loss = Decimal(stop_str)
                
                # Validate using field validator (includes business rules)
                validation_result = self.field_validator.validate_stop_loss(stop_loss, entry_level)
                if not validation_result["is_valid"]:
                    self.console.print(
                        f"[red]❌ {validation_result['error']}[/red]"
                    )
                    continue
                
                # Calculate and display stop distance
                stop_distance = abs((stop_loss - entry_level) / entry_level) * 100
                self.console.print(
                    f"[yellow]📊 Stop distance: {stop_distance:.2f}%[/yellow]"
                )
                
                self.collected_data["stop_loss"] = stop_loss
                logger.info(
                    "Stop loss collected", 
                    stop_loss=float(stop_loss),
                    stop_distance_percent=float(stop_distance)
                )
                return stop_loss
                
            except InvalidOperation:
                self.console.print("[red]❌ Invalid number format.[/red]")
    
    def collect_risk_category(
        self, 
        initial_value: Optional[str] = None
    ) -> RiskCategory:
        """
        Collect and validate risk category.
        
        Args:
            initial_value: Pre-populated value from CLI shortcut
            
        Returns:
            Selected risk category
        """
        risk_options = {
            "small": "Small (1% risk)",
            "normal": "Normal (2% risk)", 
            "large": "Large (3% risk)"
        }
        
        if initial_value and initial_value.lower() in risk_options:
            category = RiskCategory(initial_value.lower())
            self.console.print(
                f"[cyan]Risk category (from CLI):[/cyan] {risk_options[category.value]}"
            )
        else:
            # Show options
            self.console.print("\n[bold]Risk Categories:[/bold]")
            for key, desc in risk_options.items():
                self.console.print(f"  [cyan]{key}[/cyan]: {desc}")
            
            while True:
                choice = Prompt.ask(
                    "\n[cyan]Risk category[/cyan]",
                    choices=list(risk_options.keys()),
                    default="normal"
                )
                category = RiskCategory(choice)
                break
        
        self.collected_data["risk_category"] = category
        logger.info("Risk category collected", risk_category=category.value)
        return category
    
    def calculate_and_display_position_size(
        self,
        entry_level: Decimal,
        stop_loss: Decimal,
        risk_category: RiskCategory
    ) -> Tuple[int, Decimal]:
        """
        Calculate position size and display risk information.
        
        Args:
            entry_level: Entry price
            stop_loss: Stop loss price  
            risk_category: Selected risk category
            
        Returns:
            Tuple of (position_size, dollar_risk)
        """
        try:
            # Calculate position size using risk manager
            position_result = self.risk_manager.position_sizer.calculate_position_size(
                account_value=self.risk_manager.account_value,
                risk_category=risk_category,
                entry_price=entry_level,
                stop_loss=stop_loss
            )
            
            # Check portfolio risk limit
            portfolio_check = self.risk_manager.check_portfolio_risk_limit(
                position_result.dollar_risk
            )
            
            # Display calculation results
            self.console.print("\n[bold]💰 Position Sizing Results:[/bold]")
            table = Table(show_header=False, box=None)
            table.add_column("Metric", style="cyan")
            table.add_column("Value", style="white")
            
            table.add_row("Position Size", f"{position_result.position_size:,} shares")
            table.add_row("Dollar Risk", f"${position_result.dollar_risk:.2f}")
            table.add_row("Risk Percentage", f"{position_result.portfolio_risk_percentage:.2f}%")
            
            self.console.print(table)
            
            # Display portfolio risk status
            self._display_portfolio_risk_status(portfolio_check)
            
            # Check if portfolio limit exceeded
            if not portfolio_check.passed:
                self.console.print(
                    Panel(
                        f"[red]❌ PORTFOLIO RISK LIMIT EXCEEDED[/red]\n\n"
                        f"Current portfolio risk: {portfolio_check.current_risk:.2f}%\n"
                        f"New trade risk: {portfolio_check.new_trade_risk:.2f}%\n"
                        f"Total would be: {portfolio_check.total_risk:.2f}%\n"
                        f"Maximum allowed: {portfolio_check.limit:.2f}%\n\n"
                        f"[yellow]Suggestion: Reduce position size or close existing positions[/yellow]",
                        title="Risk Limit Check",
                        border_style="red"
                    )
                )
                
                if not Confirm.ask("Continue anyway? (NOT RECOMMENDED)"):
                    raise ValueError("Portfolio risk limit exceeded - plan creation cancelled")
            
            logger.info(
                "Position size calculated",
                position_size=position_result.position_size,
                dollar_risk=float(position_result.dollar_risk),
                portfolio_risk_percent=float(position_result.portfolio_risk_percentage),
                portfolio_check_passed=portfolio_check.passed
            )
            
            return position_result.position_size, position_result.dollar_risk
            
        except Exception as e:
            self.console.print(f"[red]❌ Error calculating position size: {e}[/red]")
            logger.error("Position size calculation failed", error=str(e))
            raise
    
    def collect_take_profit(self, initial_value: Optional[str] = None) -> Decimal:
        """
        Collect and validate take profit level.
        
        Args:
            initial_value: Pre-populated value from CLI shortcut
            
        Returns:
            Validated take profit as Decimal
        """
        while True:
            if initial_value:
                target_str = initial_value
                self.console.print(f"[cyan]Take profit (from CLI):[/cyan] {target_str}")
                initial_value = None  # Only use once
            else:
                target_str = Prompt.ask(
                    "[cyan]Take profit target[/cyan] [dim](positive price)[/dim]"
                )
            
            try:
                take_profit = Decimal(target_str)
                
                # Validate using field validator
                validation_result = self.field_validator.validate_take_profit(take_profit)
                if not validation_result["is_valid"]:
                    self.console.print(
                        f"[red]❌ {validation_result['error']}[/red]"
                    )
                    continue
                
                # Calculate R:R ratio if we have entry and stop
                if "entry_level" in self.collected_data and "stop_loss" in self.collected_data:
                    entry = self.collected_data["entry_level"]
                    stop = self.collected_data["stop_loss"]
                    
                    risk_amount = abs(entry - stop)
                    reward_amount = abs(take_profit - entry)
                    
                    if risk_amount > 0:
                        rr_ratio = reward_amount / risk_amount
                        self.console.print(
                            f"[yellow]📊 Risk:Reward ratio: 1:{rr_ratio:.2f}[/yellow]"
                        )
                
                self.collected_data["take_profit"] = take_profit
                logger.info("Take profit collected", take_profit=float(take_profit))
                return take_profit
                
            except InvalidOperation:
                self.console.print("[red]❌ Invalid number format.[/red]")
    
    def collect_execution_functions(self) -> Tuple[ExecutionFunction, ExecutionFunction]:
        """
        Collect entry and exit execution functions.
        
        Returns:
            Tuple of (entry_function, exit_function)
        """
        # Default timeframes from config
        timeframes = ["1min", "5min", "15min", "30min", "60min"]
        default_timeframe = "15min"
        
        self.console.print("\n[bold]⚙️  Execution Functions:[/bold]")
        
        # Entry function
        self.console.print("\n[cyan]Entry Function:[/cyan]")
        entry_type = Prompt.ask(
            "Entry trigger",
            choices=["close_above", "close_below"],
            default="close_above"
        )
        
        entry_timeframe = Prompt.ask(
            "Entry timeframe",
            choices=timeframes,
            default=default_timeframe
        )
        
        entry_function = ExecutionFunction(
            function_type=entry_type,
            timeframe=entry_timeframe,
            parameters={"threshold": self.collected_data.get("entry_level", Decimal("0"))}
        )
        
        # Exit function
        self.console.print("\n[cyan]Exit Function:[/cyan]")
        exit_type = Prompt.ask(
            "Exit trigger",
            choices=["stop_loss_take_profit", "trailing_stop"],
            default="stop_loss_take_profit"
        )
        
        exit_timeframe = Prompt.ask(
            "Exit timeframe",
            choices=timeframes,
            default=default_timeframe
        )
        
        exit_function = ExecutionFunction(
            function_type=exit_type,
            timeframe=exit_timeframe,
            parameters={}
        )
        
        logger.info(
            "Execution functions collected",
            entry_type=entry_type,
            entry_timeframe=entry_timeframe,
            exit_type=exit_type,
            exit_timeframe=exit_timeframe
        )
        
        return entry_function, exit_function
    
    
    def _display_portfolio_risk_status(self, portfolio_check: Any) -> None:
        """Display current portfolio risk status."""
        self.console.print("\n[bold]📊 Portfolio Risk Status:[/bold]")
        
        status_table = Table(show_header=False, box=None)
        status_table.add_column("Metric", style="cyan")
        status_table.add_column("Value", style="white")
        
        status_table.add_row("Current Portfolio Risk", f"{portfolio_check.current_risk:.2f}%")
        status_table.add_row("New Trade Risk", f"{portfolio_check.new_trade_risk:.2f}%")
        status_table.add_row("Total Risk", f"{portfolio_check.total_risk:.2f}%")
        status_table.add_row("Risk Limit", f"{portfolio_check.limit:.2f}%")
        
        # Add status indicator
        if portfolio_check.passed:
            status_table.add_row("Status", "[green]✓ Within limits[/green]")
        else:
            status_table.add_row("Status", "[red]❌ Exceeds limit[/red]")
        
        self.console.print(status_table)


# Extracted to separate modules to maintain file size limits