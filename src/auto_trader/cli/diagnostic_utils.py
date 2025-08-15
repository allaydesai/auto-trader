"""Diagnostic utilities for system health checks and troubleshooting."""

import time
from pathlib import Path
from typing import List, Dict
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from config import Settings, ConfigLoader
from ..models import TradePlanLoader
from ..logging_config import get_logger

console = Console()
logger = get_logger("cli.diagnostics", "cli")


def check_configuration() -> List[dict]:
    """Check configuration files and settings."""
    results = []
    
    try:
        settings = Settings()
        config_loader = ConfigLoader(settings)
        
        # Check environment file
        env_file = Path(".env")
        if env_file.exists():
            results.append({
                "check": "Environment file",
                "status": "✅",
                "message": f"Found {env_file}",
                "level": "success"
            })
        else:
            results.append({
                "check": "Environment file",
                "status": "⚠️",
                "message": "No .env file found - using defaults",
                "level": "warning"
            })
            
        # Check configuration validation
        issues = config_loader.validate_configuration()
        if not issues:
            results.append({
                "check": "Configuration validation",
                "status": "✅", 
                "message": "All configuration files valid",
                "level": "success"
            })
        else:
            for issue in issues:
                results.append({
                    "check": "Configuration validation",
                    "status": "❌",
                    "message": f"Issue: {issue}",
                    "level": "error"
                })
                
        # Check user config file
        if settings.user_config_file.exists():
            results.append({
                "check": "User configuration",
                "status": "✅",
                "message": f"Found {settings.user_config_file}",
                "level": "success"
            })
        else:
            results.append({
                "check": "User configuration", 
                "status": "⚠️",
                "message": "No user_config.yaml - using defaults",
                "level": "warning"
            })
            
    except Exception as e:
        results.append({
            "check": "Configuration check",
            "status": "❌",
            "message": f"Error: {e}",
            "level": "error"
        })
        
    return results


def check_trade_plans() -> List[dict]:
    """Check trade plans directory and files."""
    results = []
    
    try:
        loader = TradePlanLoader()
        
        # Check plans directory
        if loader.plans_directory.exists():
            results.append({
                "check": "Plans directory",
                "status": "✅",
                "message": f"Found {loader.plans_directory}",
                "level": "success"
            })
            
            # Count YAML files
            yaml_files = list(loader.plans_directory.glob("*.yaml")) + list(loader.plans_directory.glob("*.yml"))
            results.append({
                "check": "YAML files",
                "status": "📄",
                "message": f"Found {len(yaml_files)} YAML files",
                "level": "info"
            })
            
        else:
            results.append({
                "check": "Plans directory",
                "status": "❌",
                "message": f"Directory not found: {loader.plans_directory}",
                "level": "error"
            })
            
        # Try to load plans
        plans = loader.load_all_plans(validate=True)
        if plans:
            results.append({
                "check": "Plan loading",
                "status": "✅",
                "message": f"Loaded {len(plans)} valid plans",
                "level": "success"
            })
        else:
            results.append({
                "check": "Plan loading",
                "status": "⚠️",
                "message": "No valid plans found",
                "level": "warning"
            })
            
    except Exception as e:
        results.append({
            "check": "Trade plans check",
            "status": "❌",
            "message": f"Error: {e}",
            "level": "error"
        })
        
    return results


def check_permissions() -> List[dict]:
    """Check file and directory permissions."""
    results = []
    
    # Check current directory permissions
    current_dir = Path.cwd()
    if current_dir.is_dir():
        results.append({
            "check": "Current directory",
            "status": "✅" if current_dir.stat().st_mode & 0o200 else "❌",
            "message": f"Write access to {current_dir}",
            "level": "success" if current_dir.stat().st_mode & 0o200 else "error"
        })
    
    # Check plans directory permissions
    plans_dir = Path("data/trade_plans")
    if plans_dir.exists():
        has_write = plans_dir.stat().st_mode & 0o200
        results.append({
            "check": "Plans directory permissions",
            "status": "✅" if has_write else "❌",
            "message": f"{'Write' if has_write else 'No write'} access to {plans_dir}",
            "level": "success" if has_write else "error"
        })
    else:
        results.append({
            "check": "Plans directory permissions",
            "status": "⚠️",
            "message": f"Plans directory does not exist: {plans_dir}",
            "level": "warning"
        })
        
    # Check logs directory
    logs_dir = Path("logs")
    if logs_dir.exists():
        has_write = logs_dir.stat().st_mode & 0o200
        results.append({
            "check": "Logs directory permissions",
            "status": "✅" if has_write else "❌",
            "message": f"{'Write' if has_write else 'No write'} access to {logs_dir}",
            "level": "success" if has_write else "error"
        })
    else:
        results.append({
            "check": "Logs directory permissions",
            "status": "⚠️",
            "message": f"Logs directory does not exist: {logs_dir}",
            "level": "warning"
        })
        
    return results


def display_diagnostic_summary(results: List[dict]) -> None:
    """Display diagnostic results summary."""
    # Count results by level
    success_count = len([r for r in results if r["level"] == "success"])
    warning_count = len([r for r in results if r["level"] == "warning"])
    error_count = len([r for r in results if r["level"] == "error"])
    info_count = len([r for r in results if r["level"] == "info"])
    
    # Create results table
    table = Table(title="Diagnostic Results")
    table.add_column("Check", style="cyan", width=25)
    table.add_column("Status", style="white", width=8)
    table.add_column("Message", style="white", width=50)
    
    for result in results:
        table.add_row(result["check"], result["status"], result["message"])
    
    console.print(table)
    
    # Show summary
    summary_color = "red" if error_count > 0 else "yellow" if warning_count > 0 else "green"
    console.print(
        Panel(
            f"[{summary_color}]Summary:[/{summary_color}]\n"
            f"✅ {success_count} successful\n"
            f"⚠️ {warning_count} warnings\n"
            f"❌ {error_count} errors\n"
            f"📄 {info_count} info",
            title="Health Check Summary",
            border_style=summary_color,
        )
    )
    
    # Show recommendations
    if error_count > 0:
        console.print(
            Panel(
                "[red]🚨 Critical Issues Found[/red]\n"
                "Please resolve errors before using the system.\n"
                "Run 'auto-trader setup' if this is first-time setup.",
                title="Recommendations",
                border_style="red",
            )
        )
    elif warning_count > 0:
        console.print(
            Panel(
                "[yellow]⚠️  Warnings Found[/yellow]\n"
                "System will work but some features may be limited.\n"
                "Consider resolving warnings for optimal experience.",
                title="Recommendations",
                border_style="yellow",
            )
        )
    else:
        console.print(
            Panel(
                "[green]✅ System Healthy[/green]\n"
                "All checks passed! Your system is ready to use.",
                title="Recommendations",
                border_style="green",
            )
        )


def export_debug_information(results: List[dict]) -> None:
    """Export debug information to file."""
    debug_file = Path(f"auto-trader-debug-{int(time.time())}.json")
    
    debug_info = {
        "timestamp": datetime.now().isoformat(),
        "diagnostic_results": results,
        "system_info": {
            "python_version": "3.11.8",  # Could get dynamically
            "platform": "linux",  # Could get dynamically
            "working_directory": str(Path.cwd()),
        },
        "environment_variables": {
            "PYTHONPATH": "src",  # Only non-sensitive env vars
        }
    }
    
    try:
        import json
        with open(debug_file, 'w') as f:
            json.dump(debug_info, f, indent=2)
            
        console.print(
            Panel(
                f"[green]Debug information exported to:[/green] {debug_file}\n"
                "[yellow]Warning:[/yellow] Review file before sharing - no secrets included",
                title="Debug Export",
                border_style="green",
            )
        )
    except Exception as e:
        console.print(f"[red]Failed to export debug info: {e}[/red]")