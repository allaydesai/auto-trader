"""Configuration-related CLI commands for Auto-Trader application."""

from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.panel import Panel

from config import Settings, ConfigLoader
from ..logging_config import get_logger
from .display_utils import display_config_summary
from .file_utils import (
    create_env_file,
    create_config_file,
    create_user_config_file,
)
from .error_utils import (
    handle_config_validation_failure,
    handle_file_permission_error,
    handle_generic_error,
    show_safety_warning,
    check_existing_files,
)


console = Console()
logger = get_logger("cli", "cli")


@click.command()
@click.option(
    "--config-file",
    type=click.Path(exists=True, path_type=Path),
    help="Path to config.yaml file",
)
@click.option(
    "--user-config-file",
    type=click.Path(exists=True, path_type=Path),
    help="Path to user_config.yaml file",
)
@click.option("--verbose", "-v", is_flag=True, help="Verbose output")
def validate_config(
    config_file: Optional[Path], user_config_file: Optional[Path], verbose: bool
) -> None:
    """Validate configuration files and environment variables."""
    logger.info("Configuration validation started")

    try:
        # Override settings if custom paths provided
        settings = Settings()
        if config_file:
            settings.config_file = config_file
        if user_config_file:
            settings.user_config_file = user_config_file

        config_loader = ConfigLoader(settings)

        # Validate configuration
        issues = config_loader.validate_configuration()

        if not issues:
            console.print(
                Panel(
                    "[green]✓ Configuration validation passed![/green]",
                    title="Validation Result",
                    border_style="green",
                )
            )

            # Show safety warning if not in simulation mode
            show_safety_warning(config_loader.system_config.trading.simulation_mode)

            if verbose:
                display_config_summary(config_loader)

            logger.info("Configuration validation passed")

        else:
            handle_config_validation_failure(issues, verbose)

    except Exception as e:
        handle_generic_error("configuration validation", e)


@click.command()
@click.option(
    "--output-dir",
    type=click.Path(path_type=Path),
    default=Path.cwd(),
    help="Output directory for configuration files",
)
@click.option("--force", is_flag=True, help="Overwrite existing files")
def setup(output_dir: Path, force: bool) -> None:
    """Interactive setup wizard for first-time configuration."""
    logger.info("Setup wizard started", output_dir=str(output_dir))

    console.print(
        Panel(
            "[bold blue]Auto-Trader Setup Wizard[/bold blue]\n"
            "This wizard will help you create the necessary configuration files.",
            title="Welcome",
            border_style="blue",
        )
    )

    try:
        # Ensure output directory exists
        output_dir.mkdir(parents=True, exist_ok=True)

        # Check for existing files
        if not check_existing_files(output_dir, force):
            return

        # Create configuration files
        env_file = output_dir / ".env"
        config_file = output_dir / "config.yaml"
        user_config_file = output_dir / "user_config.yaml"
        
        try:
            create_env_file(env_file)
            create_config_file(config_file)
            create_user_config_file(user_config_file)
        except (OSError, IOError) as e:
            handle_file_permission_error(output_dir, "file creation", e)
            return

        console.print(
            Panel(
                "[green]✓ Setup completed successfully![/green]\n\n"
                "[bold]Next steps:[/bold]\n"
                "1. Edit .env file with your actual credentials\n"
                "2. Customize config.yaml for your trading preferences\n"
                "3. Adjust user_config.yaml for your risk profile\n"
                "4. Run 'auto-trader validate-config' to verify setup",
                title="Setup Complete",
                border_style="green",
            )
        )

        logger.info("Setup wizard completed successfully")

    except Exception as e:
        handle_generic_error("setup wizard", e)