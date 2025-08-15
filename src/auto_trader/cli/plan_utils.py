"""Plan creation utilities for CLI commands."""

from pathlib import Path
from typing import Dict, Any, TYPE_CHECKING

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt

from ..models import TemplateManager

if TYPE_CHECKING:
    from ..models import TradePlan


console = Console()


def show_available_templates(template_manager: TemplateManager) -> Dict[str, Any]:
    """Show available templates and return template list."""
    templates = template_manager.list_available_templates()
    
    if not templates:
        console.print(
            Panel(
                "[red]No templates found! Please check your templates directory.[/red]",
                title="Error",
                border_style="red",
            )
        )
        return {}
    
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
    
    return {"templates": templates, "template_names": template_names}


def get_template_choice(template_names: list) -> str:
    """Get user's template choice and return selected template name."""
    template_choice = Prompt.ask(
        "\nSelect template", 
        choices=[str(i) for i in range(1, len(template_names) + 1)]
    )
    template_name = template_names[int(template_choice) - 1]
    
    console.print(f"\n[green]Selected template: {template_name}[/green]")
    return template_name


def create_plan_output_file(plan_data: Dict[str, Any], output_dir_param: Path | None = None) -> Path:
    """Create output directory and file path for the plan."""
    
    output_dir = Path("data/trade_plans") if not output_dir_param else output_dir_param
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / f"{plan_data['plan_id']}.yaml"
    
    return output_file


def show_plan_creation_success(trade_plan: "TradePlan", output_file: Path) -> None:
    """Show success message for plan creation."""
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