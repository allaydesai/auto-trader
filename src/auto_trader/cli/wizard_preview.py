"""Trade plan preview and modification utilities."""

from typing import Any, Dict

from rich.console import Console
from rich.prompt import Prompt
from rich.table import Table


class TradePlanPreview:
    """Display and manage trade plan preview with modification support."""

    def __init__(self, console: Console) -> None:
        """Initialize preview manager."""
        self.console = console

    def show_preview(self, plan_data: Dict[str, Any]) -> bool:
        """
        Show plan preview and allow modifications.

        Args:
            plan_data: Complete plan data dictionary

        Returns:
            True if user confirms, False if cancelled
        """
        while True:
            self._display_plan_preview(plan_data)

            choice = Prompt.ask(
                "\n[cyan]Options[/cyan]",
                choices=["confirm", "cancel"],
                default="confirm",
            )

            if choice == "confirm":
                return True
            elif choice == "cancel":
                return False

    def _display_plan_preview(self, plan_data: Dict[str, Any]) -> None:
        """Display formatted plan preview."""
        preview_table = Table(title="📋 Trade Plan Preview")
        preview_table.add_column("Field", style="cyan")
        preview_table.add_column("Value", style="white")

        preview_table.add_row("Plan ID", plan_data.get("plan_id", ""))
        preview_table.add_row("Symbol", plan_data.get("symbol", ""))
        preview_table.add_row("Entry Level", f"${plan_data.get('entry_level', 0)}")
        preview_table.add_row("Stop Loss", f"${plan_data.get('stop_loss', 0)}")
        preview_table.add_row("Take Profit", f"${plan_data.get('take_profit', 0)}")
        preview_table.add_row("Risk Category", plan_data.get("risk_category", ""))

        if "calculated_position_size" in plan_data:
            preview_table.add_row(
                "Position Size", f"{plan_data['calculated_position_size']:,} shares"
            )

        if "dollar_risk" in plan_data:
            preview_table.add_row("Dollar Risk", f"${plan_data['dollar_risk']:.2f}")

        # Show execution functions
        entry_func = plan_data.get("entry_function", {})
        if entry_func:
            preview_table.add_row(
                "Entry Function", f"{entry_func.function_type} ({entry_func.timeframe})"
            )

        stop_loss_func = plan_data.get("stop_loss_function", {})
        if stop_loss_func:
            preview_table.add_row(
                "Stop Loss Function",
                f"{stop_loss_func.function_type} ({stop_loss_func.timeframe})",
            )

        take_profit_func = plan_data.get("take_profit_function", {})
        if take_profit_func:
            preview_table.add_row(
                "Take Profit Function",
                f"{take_profit_func.function_type} ({take_profit_func.timeframe})",
            )

        self.console.print("\n")
        self.console.print(preview_table)
