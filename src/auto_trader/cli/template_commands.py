"""Template management CLI commands for Auto-Trader application."""

from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..logging_config import get_logger
from ..models import TemplateManager
from .error_utils import handle_generic_error


console = Console()
logger = get_logger("cli", "cli")


@click.command()
@click.option("--verbose", "-v", is_flag=True, help="Show detailed template information")
def list_templates(verbose: bool) -> None:
    """List all available trade plan templates."""
    logger.info("List templates started")
    
    try:
        template_manager = TemplateManager()
        templates = template_manager.list_available_templates()
        
        if not templates:
            console.print(
                Panel(
                    "[yellow]No templates found[/yellow]",
                    title="Templates",
                    border_style="yellow",
                )
            )
            return
        
        console.print(
            Panel(
                f"[blue]Found {len(templates)} template(s)[/blue]",
                title="Available Templates",
                border_style="blue",
            )
        )
        
        # Create templates table
        table = Table(title="Trade Plan Templates")
        table.add_column("Name", style="cyan")
        table.add_column("Description", style="white")
        if verbose:
            table.add_column("Required Fields", style="yellow")
            table.add_column("Use Cases", style="green")
        
        for name in templates:
            doc_info = template_manager.get_template_documentation(name)
            description = doc_info.get("description", "No description")
            
            if verbose:
                required_count = len(doc_info.get("required_fields", []))
                use_cases_count = len(doc_info.get("use_cases", []))
                table.add_row(
                    name, 
                    description,
                    str(required_count),
                    str(use_cases_count)
                )
            else:
                table.add_row(name, description)
        
        console.print(table)
        
        if verbose:
            # Show template summary
            summary = template_manager.get_template_summary()
            console.print("\n[bold]Template Validation Results:[/bold]")
            for name, is_valid in summary["validation_results"].items():
                status = "[green]✓[/green]" if is_valid else "[red]✗[/red]"
                console.print(f"  {status} {name}")
        
        logger.info("List templates completed", template_count=len(templates))
        
    except Exception as e:
        handle_generic_error("listing templates", e)