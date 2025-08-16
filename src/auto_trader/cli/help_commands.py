"""Help and documentation CLI commands for Auto-Trader application."""

import click
from rich.console import Console
from rich.panel import Panel


console = Console()


@click.command()
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