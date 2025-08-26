"""CLI commands entry point for Auto-Trader application."""

import click

# Import command groups from separate modules
from .config_commands import validate_config, setup
from .plan_commands import validate_plans, list_plans, create_plan, create_plan_interactive
from .management_commands import list_plans_enhanced, validate_config as validate_config_enhanced, update_plan, archive_plans, plan_stats
from .template_commands import list_templates
from .schema_commands import show_schema
from .monitor_commands import monitor, summary, history
from .diagnostic_commands import doctor
from .help_commands import help_system
from .risk_commands import calculate_position_size, portfolio_risk_summary


@click.group()
@click.version_option(version="0.1.0", prog_name="auto-trader")
def cli() -> None:
    """Auto-Trader: Personal Automated Trading System."""
    pass


# Register all commands from the separate modules
cli.add_command(validate_config)
cli.add_command(setup)
cli.add_command(validate_plans)
cli.add_command(list_plans)
cli.add_command(create_plan)
cli.add_command(create_plan_interactive)
# New enhanced management commands
cli.add_command(list_plans_enhanced, name="list-plans-enhanced")
cli.add_command(validate_config_enhanced, name="validate-config-enhanced") 
cli.add_command(update_plan, name="update-plan")
cli.add_command(archive_plans, name="archive-plans")
cli.add_command(plan_stats, name="plan-stats")
cli.add_command(list_templates)
cli.add_command(show_schema)
cli.add_command(monitor)
cli.add_command(summary)
cli.add_command(history)
cli.add_command(doctor)
cli.add_command(help_system)
cli.add_command(calculate_position_size)
cli.add_command(portfolio_risk_summary)


if __name__ == "__main__":
    cli()
