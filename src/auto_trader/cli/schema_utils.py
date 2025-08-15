"""Schema documentation and display utilities."""

from typing import Dict, Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def display_schema_console(schema: dict) -> None:
    """Display schema in console-friendly format."""
    console.print(
        Panel(
            "[blue]Trade Plan Schema Documentation[/blue]\n"
            "Complete schema for trade plan YAML files",
            title="Schema",
            border_style="blue",
        )
    )
    
    properties = schema.get("properties", {})
    required_fields = set(schema.get("required", []))
    
    # Create schema table
    table = Table(title="Trade Plan Fields")
    table.add_column("Field", style="cyan", width=20)
    table.add_column("Type", style="yellow", width=15) 
    table.add_column("Required", style="red", width=10)
    table.add_column("Description", style="white", width=40)
    
    for field_name, field_info in properties.items():
        field_type = field_info.get("type", "unknown")
        if field_type == "object" and "properties" in field_info:
            field_type = "object"
        elif field_type == "array" and "items" in field_info:
            items_type = field_info["items"].get("type", "unknown")
            field_type = f"array[{items_type}]"
            
        is_required = "✓" if field_name in required_fields else ""
        description = field_info.get("description", "No description")[:50] + "..." if len(field_info.get("description", "")) > 50 else field_info.get("description", "")
        
        table.add_row(field_name, field_type, is_required, description)
    
    console.print(table)
    
    # Show examples section
    console.print(
        Panel(
            "[green]Examples:[/green]\n"
            "• Basic plan: auto-trader create-plan\n"
            "• View templates: auto-trader list-templates\n"
            "• Field help: auto-trader show-schema --field plan_id\n"
            "• JSON format: auto-trader show-schema --format json",
            title="Usage Examples",
            border_style="green",
        )
    )