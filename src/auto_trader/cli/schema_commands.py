"""Schema documentation CLI commands for Auto-Trader application."""

from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel

from ..logging_config import get_logger
from .schema_utils import display_schema_console
from .error_utils import handle_generic_error


console = Console()
logger = get_logger("cli", "cli")


@click.command()
@click.option("--format", "output_format", default="console", type=click.Choice(["console", "json", "yaml"]), help="Output format")
@click.option("--field", help="Show documentation for specific field")
def show_schema(output_format: str, field: Optional[str]) -> None:
    """Show trade plan schema documentation with examples."""
    logger.info("Schema documentation requested")
    
    try:
        from ..models.trade_plan import TradePlan
        
        # Get model schema information
        schema = TradePlan.model_json_schema()
        
        if field:
            # Show specific field documentation
            if field in schema.get("properties", {}):
                field_info = schema["properties"][field]
                console.print(
                    Panel(
                        f"[blue]Field: {field}[/blue]\n"
                        f"Type: {field_info.get('type', 'unknown')}\n"
                        f"Description: {field_info.get('description', 'No description')}\n"
                        f"Required: {'Yes' if field in schema.get('required', []) else 'No'}",
                        title=f"Schema - {field}",
                        border_style="blue",
                    )
                )
            else:
                console.print(f"[red]❌ Field '{field}' not found in schema[/red]")
                return
        else:
            # Show complete schema
            if output_format == "console":
                display_schema_console(schema)
            elif output_format == "json":
                import json
                console.print(json.dumps(schema, indent=2))
            elif output_format == "yaml":
                import yaml
                console.print(yaml.dump(schema, default_flow_style=False))
                
        logger.info("Schema documentation completed", field=field, format=output_format)
        
    except Exception as e:
        handle_generic_error("schema documentation", e)