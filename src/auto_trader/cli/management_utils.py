"""Plan management utility functions for trade plan operations."""

from __future__ import annotations

import shutil
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from ..logging_config import get_logger
from ..models import TradePlan, TradePlanLoader, TradePlanStatus, ValidationEngine
from ..risk_management import RiskManager
from ..risk_management.portfolio_tracker import PortfolioTracker

console = Console()
logger = get_logger("management_utils", "cli")


class PlanManagementError(Exception):
    """Base exception for plan management operations."""
    pass


class BackupCreationError(PlanManagementError):
    """Raised when plan backup creation fails."""
    pass


class PlanUpdateError(PlanManagementError):
    """Raised when plan update operation fails."""
    pass


def create_plan_backup(plan_path: Path, backup_dir: Path) -> Path:
    """
    Create timestamped backup of trade plan before modification.
    
    Args:
        plan_path: Path to original plan file
        backup_dir: Directory to store backup
        
    Returns:
        Path to created backup file
        
    Raises:
        BackupCreationError: If backup creation fails
    """
    try:
        # Ensure backup directory exists
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Create timestamped backup filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{plan_path.stem}.backup.{timestamp}.yaml"
        backup_path = backup_dir / backup_filename
        
        # Copy original file to backup location
        shutil.copy2(plan_path, backup_path)
        
        logger.info(
            "Plan backup created",
            original=str(plan_path),
            backup=str(backup_path),
        )
        
        return backup_path
        
    except Exception as e:
        error_msg = f"Failed to create backup for {plan_path.name}: {e}"
        logger.error("Backup creation failed", error=str(e), plan_path=str(plan_path))
        raise BackupCreationError(error_msg) from e


def get_portfolio_risk_summary(
    risk_manager: RiskManager,
    plans: List[TradePlan],
) -> Dict[str, Any]:
    """
    Calculate comprehensive portfolio risk summary for display.
    
    Args:
        risk_manager: Configured risk manager instance
        plans: List of all trade plans
        
    Returns:
        Dictionary with portfolio risk metrics
    """
    current_risk = risk_manager.portfolio_tracker.get_current_portfolio_risk()
    portfolio_limit = PortfolioTracker.MAX_PORTFOLIO_RISK  # Portfolio risk limit from config
    
    # Calculate total risk from all plans
    total_plan_risk = Decimal("0.0")
    plan_risks = {}
    
    for plan in plans:
        if plan.status in [TradePlanStatus.AWAITING_ENTRY, TradePlanStatus.POSITION_OPEN]:
            validation_result = risk_manager.validate_trade_plan(plan)
            if validation_result.passed and validation_result.position_size_result:
                plan_risk = validation_result.position_size_result.risk_amount_percent
                total_plan_risk += plan_risk
                plan_risks[plan.plan_id] = {
                    "risk_percent": plan_risk,
                    "position_size": validation_result.position_size_result.position_size,
                    "dollar_risk": validation_result.position_size_result.risk_amount_dollars,
                }
    
    remaining_capacity = max(Decimal("0"), portfolio_limit - current_risk)
    capacity_percent = (remaining_capacity / portfolio_limit) * 100
    
    return {
        "current_risk_percent": current_risk,
        "portfolio_limit_percent": portfolio_limit,
        "remaining_capacity_percent": remaining_capacity,
        "capacity_utilization_percent": capacity_percent,
        "total_plan_risk_percent": total_plan_risk,
        "plan_risks": plan_risks,
        "exceeds_limit": current_risk > portfolio_limit,
        "near_limit": current_risk > (portfolio_limit * Decimal("0.8")),  # 80% warning threshold
    }


def format_risk_indicator(risk_percent: Decimal, limit: Decimal) -> str:
    """
    Create color-coded risk level indicator with emoji.
    
    Args:
        risk_percent: Current risk percentage
        limit: Maximum risk limit
        
    Returns:
        Formatted risk indicator with color and emoji
    """
    if risk_percent > limit:
        return f"🔴 {risk_percent:.1f}%"
    elif risk_percent > (limit * Decimal("0.8")):
        return f"🟡 {risk_percent:.1f}%"
    else:
        return f"🟢 {risk_percent:.1f}%"


def format_plan_status(status: TradePlanStatus) -> str:
    """
    Format plan status with appropriate emoji indicator.
    
    Args:
        status: Plan status enum value
        
    Returns:
        Formatted status string with emoji
    """
    status_map = {
        TradePlanStatus.AWAITING_ENTRY: "✅ awaiting_entry",
        TradePlanStatus.POSITION_OPEN: "🔄 position_open",
        TradePlanStatus.COMPLETED: "✅ completed",
        TradePlanStatus.CANCELLED: "⏹️ cancelled",
        TradePlanStatus.ERROR: "❌ error",
    }
    return status_map.get(status, f"❓ {status}")


def create_plans_table(
    plans: List[TradePlan],
    risk_manager: RiskManager,
    show_verbose: bool = False,
) -> Table:
    """
    Create Rich table for plan display with risk integration.
    
    Args:
        plans: List of trade plans to display
        risk_manager: Risk manager for calculations
        show_verbose: Whether to show verbose details
        
    Returns:
        Rich Table object for display
    """
    table = Table(title="📊 TRADE PLANS", show_header=True, header_style="bold blue")
    
    # Define columns based on verbosity
    table.add_column("Plan ID", style="cyan", width=17)
    table.add_column("Symbol", style="white", width=8)
    table.add_column("Status", style="white", width=15)
    table.add_column("Risk %", style="white", width=10)
    table.add_column("Position Size", style="white", width=13)
    
    if show_verbose:
        table.add_column("Entry", style="green", width=8)
        table.add_column("Stop", style="red", width=8)
        table.add_column("Target", style="blue", width=8)
        table.add_column("R:R", style="yellow", width=6)
    
    # Add rows for each plan
    for plan in plans:
        # Calculate risk and position size
        validation_result = risk_manager.validate_trade_plan(plan)
        
        if validation_result.passed and validation_result.position_size_result:
            risk_percent = validation_result.position_size_result.risk_amount_percent
            position_size = validation_result.position_size_result.position_size
            risk_indicator = format_risk_indicator(risk_percent, PortfolioTracker.MAX_PORTFOLIO_RISK)
            size_display = f"{position_size} shares"
        else:
            risk_indicator = "❌ Invalid"
            size_display = "N/A"
        
        # Basic columns
        row_data = [
            plan.plan_id,
            plan.symbol,
            format_plan_status(plan.status),
            risk_indicator,
            size_display,
        ]
        
        # Add verbose columns if requested
        if show_verbose:
            # Calculate risk-reward ratio
            risk_amount = abs(plan.entry_level - plan.stop_loss)
            reward_amount = abs(plan.take_profit - plan.entry_level)
            rr_ratio = reward_amount / risk_amount if risk_amount > 0 else Decimal("0")
            
            row_data.extend([
                f"${plan.entry_level:.2f}",
                f"${plan.stop_loss:.2f}",
                f"${plan.take_profit:.2f}",
                f"{rr_ratio:.1f}:1",
            ])
        
        table.add_row(*row_data)
    
    return table


def create_portfolio_summary_panel(portfolio_data: Dict[str, Any]) -> Panel:
    """
    Create Rich panel displaying portfolio risk summary.
    
    Args:
        portfolio_data: Portfolio metrics from get_portfolio_risk_summary()
        
    Returns:
        Rich Panel with portfolio overview
    """
    current_risk = portfolio_data["current_risk_percent"]
    limit = portfolio_data["portfolio_limit_percent"]
    remaining = portfolio_data["remaining_capacity_percent"]
    capacity_pct = portfolio_data["capacity_utilization_percent"]
    
    # Create risk indicator
    risk_indicator = format_risk_indicator(current_risk, limit)
    
    # Build summary text
    summary_lines = [
        f"🛡️  PORTFOLIO RISK: {risk_indicator} / {limit:.1f}% limit",
        f"📈 Capacity: {capacity_pct:.0f}% utilized ({remaining:.1f}% remaining)",
    ]
    
    # Add warning if near or over limit
    if portfolio_data["exceeds_limit"]:
        summary_lines.append("🚨 CRITICAL: Portfolio risk exceeds limit!")
    elif portfolio_data["near_limit"]:
        summary_lines.append("⚠️  WARNING: Approaching portfolio risk limit")
    
    summary_text = "\n".join(summary_lines)
    
    # Choose panel style based on risk level
    if portfolio_data["exceeds_limit"]:
        border_style = "red"
    elif portfolio_data["near_limit"]:
        border_style = "yellow"
    else:
        border_style = "green"
    
    return Panel(
        summary_text,
        title="Portfolio Risk Summary",
        border_style=border_style,
        padding=(0, 1),
    )


def validate_plans_comprehensive(
    plans_dir: Path,
    validation_engine: ValidationEngine,
    risk_manager: RiskManager,
    single_file: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Perform comprehensive validation of trade plans.
    
    Args:
        plans_dir: Directory containing trade plan files
        validation_engine: Validation engine instance
        risk_manager: Risk manager for portfolio validation
        single_file: Optional single file to validate
        
    Returns:
        Comprehensive validation results dictionary
    """
    results = {
        "files_checked": 0,
        "syntax_passed": 0,
        "business_logic_passed": 0,
        "portfolio_risk_passed": True,
        "file_results": {},
        "portfolio_risk_percent": Decimal("0.0"),
        "portfolio_limit_exceeded": False,
        "errors": [],
        "warnings": [],
    }
    
    # Determine files to validate
    if single_file:
        files_to_check = [single_file]
    else:
        files_to_check = list(plans_dir.glob("*.yaml")) + list(plans_dir.glob("*.yml"))
    
    results["files_checked"] = len(files_to_check)
    
    # Validate each file
    valid_plans = []
    for file_path in files_to_check:
        file_result = {
            "syntax_valid": False,
            "business_logic_valid": False,
            "errors": [],
            "warnings": [],
        }
        
        try:
            # YAML syntax validation
            validation_result = validation_engine.validate_file(file_path)
            
            if validation_result.is_valid:
                file_result["syntax_valid"] = True
                results["syntax_passed"] += 1
                
                # Load plan for business logic validation
                loader = TradePlanLoader(plans_dir)
                plan = loader.load_plan_from_file(file_path)
                
                if plan:
                    # Business logic validation via risk manager
                    risk_validation = risk_manager.validate_trade_plan(plan)
                    
                    if risk_validation.passed:
                        file_result["business_logic_valid"] = True
                        results["business_logic_passed"] += 1
                        valid_plans.append(plan)
                    else:
                        file_result["errors"].extend(risk_validation.errors)
                        file_result["warnings"].extend(risk_validation.warnings)
                        
            else:
                file_result["errors"] = validation_result.errors
                
        except Exception as e:
            file_result["errors"].append(f"Validation error: {e}")
            logger.error("Plan validation failed", file=str(file_path), error=str(e))
        
        results["file_results"][file_path.name] = file_result
    
    # Portfolio risk validation
    if valid_plans:
        portfolio_summary = get_portfolio_risk_summary(risk_manager, valid_plans)
        results["portfolio_risk_percent"] = portfolio_summary["total_plan_risk_percent"]
        results["portfolio_limit_exceeded"] = portfolio_summary["exceeds_limit"]
        results["portfolio_risk_passed"] = not portfolio_summary["exceeds_limit"]
    
    logger.info(
        "Plan validation completed",
        files_checked=results["files_checked"],
        syntax_passed=results["syntax_passed"],
        business_logic_passed=results["business_logic_passed"],
        portfolio_risk_passed=results["portfolio_risk_passed"],
    )
    
    return results