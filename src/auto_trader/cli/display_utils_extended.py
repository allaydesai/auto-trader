"""Extended display utilities for trade plan management operations."""

from __future__ import annotations

from decimal import Decimal
from typing import Dict, List, Optional, Any

from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from ..models import TradePlan, TradePlanStatus

console = Console()


def format_plan_status(status: TradePlanStatus) -> str:
    """
    Format plan status with consistent emoji indicators.
    
    Args:
        status: Plan status to format
        
    Returns:
        Formatted status string with emoji
    """
    status_formats = {
        TradePlanStatus.AWAITING_ENTRY: "✅ awaiting_entry",
        TradePlanStatus.POSITION_OPEN: "🔄 position_open",
        TradePlanStatus.COMPLETED: "🎯 completed",
        TradePlanStatus.CANCELLED: "❌ cancelled",
        TradePlanStatus.ERROR: "⚠️ error"
    }
    return status_formats.get(status, f"❓ {status.value if hasattr(status, 'value') else status}")


def create_plans_listing_table(plans: List[TradePlan], risk_results: List[Dict[str, Any]],
                              verbose: bool = False, show_risk: bool = True) -> Table:
    """
    Create Rich table for plan listings with risk integration.
    
    Args:
        plans: List of trade plans to display
        risk_results: Risk calculation results for plans
        verbose: Whether to show verbose details
        show_risk: Whether to include risk columns
        
    Returns:
        Rich Table formatted for plan display
    """
    table = Table()
    
    # Add columns based on verbose mode
    table.add_column("Plan ID", style="bold")
    table.add_column("Symbol", justify="center")
    table.add_column("Status", justify="center")
    
    if show_risk:
        table.add_column("Risk %", justify="right")
        table.add_column("Position Size", justify="right")
    
    if verbose:
        table.add_column("Entry Level", justify="right")
        table.add_column("Stop Loss", justify="right")
        table.add_column("Take Profit", justify="right")
        table.add_column("Risk Category")
    
    # Create risk lookup for efficiency
    risk_lookup = {r['plan_id']: r for r in risk_results} if risk_results else {}
    
    for plan in plans:
        row_data = [
            plan.plan_id,
            plan.symbol,
            format_plan_status(plan.status)
        ]
        
        if show_risk:
            risk_data = risk_lookup.get(plan.plan_id, {})
            
            if 'error' in risk_data:
                row_data.extend(["❌ Error", "Invalid"])
            elif risk_data.get('validation_result'):
                risk_percent = risk_data['risk_percent']
                position_size = risk_data['position_size']
                
                # Format risk with color coding
                if risk_percent <= Decimal('2.0'):
                    risk_display = f"🟢 {risk_percent:.1f}%"
                elif risk_percent <= Decimal('3.0'):
                    risk_display = f"🟡 {risk_percent:.1f}%"
                else:
                    risk_display = f"🔴 {risk_percent:.1f}%"
                
                row_data.extend([
                    risk_display,
                    f"{position_size} shares"
                ])
            else:
                row_data.extend(["⚠️ Unknown", "Pending"])
        
        if verbose:
            row_data.extend([
                f"${plan.entry_level:.2f}",
                f"${plan.stop_loss:.2f}",
                f"${plan.take_profit:.2f}",
                plan.risk_category.value if hasattr(plan, 'risk_category') and hasattr(plan.risk_category, 'value') else (str(plan.risk_category) if hasattr(plan, 'risk_category') else "medium")
            ])
        
        table.add_row(*row_data)
    
    return table


def create_plan_update_preview_table(plan_id: str, plan: TradePlan, 
                                    updates: Dict[str, Any]) -> Table:
    """
    Create table showing plan update preview.
    
    Args:
        plan_id: ID of plan being updated
        plan: Current plan object
        updates: Dictionary of field updates
        
    Returns:
        Rich Table showing before/after values
    """
    table = Table(title=f"Plan Update Preview: {plan_id}")
    table.add_column("Field", style="bold")
    table.add_column("Current Value", justify="right")
    table.add_column("New Value", justify="right", style="green")
    
    # Field display mapping
    field_formatters = {
        'entry_level': lambda x: f"${x:.2f}",
        'stop_loss': lambda x: f"${x:.2f}",
        'take_profit': lambda x: f"${x:.2f}",
        'risk_category': lambda x: x.value if hasattr(x, 'value') else str(x),
        'position_size': lambda x: f"{x} shares"
    }
    
    field_names = {
        'entry_level': 'Entry Level',
        'stop_loss': 'Stop Loss',
        'take_profit': 'Take Profit',
        'risk_category': 'Risk Category',
        'position_size': 'Position Size'
    }
    
    for field_key, new_value in updates.items():
        if hasattr(plan, field_key):
            current_value = getattr(plan, field_key)
            
            formatter = field_formatters.get(field_key, str)
            field_display = field_names.get(field_key, field_key.replace('_', ' ').title())
            
            table.add_row(
                field_display,
                formatter(current_value),
                formatter(new_value)
            )
    
    return table


def display_plan_risk_impact(original_validation, updated_validation) -> None:
    """
    Display risk impact comparison for plan updates.
    
    Args:
        original_validation: Original risk validation result
        updated_validation: Updated risk validation result
    """
    if not original_validation or not updated_validation:
        console.print("⚠️ Risk impact calculation unavailable", style="yellow")
        return
    
    # Calculate changes
    position_change = updated_validation.position_size - original_validation.position_size
    risk_change = updated_validation.risk_percent - original_validation.risk_percent
    
    # Format changes with indicators
    if position_change > 0:
        position_indicator = f"📈 +{position_change}"
    elif position_change < 0:
        position_indicator = f"📉 {position_change}"
    else:
        position_indicator = "➡️ No change"
    
    if risk_change > 0:
        risk_indicator = f"📈 +{risk_change:.2f}%"
        risk_style = "red"
    elif risk_change < 0:
        risk_indicator = f"📉 {risk_change:.2f}%"
        risk_style = "green"
    else:
        risk_indicator = "➡️ No change"
        risk_style = "dim"
    
    # Create impact panel
    content = f"""Position Size: {original_validation.position_size} → {updated_validation.position_size} shares ({position_indicator})
Risk Amount: ${original_validation.risk_amount:.2f} → ${updated_validation.risk_amount:.2f}
Portfolio Risk: {original_validation.risk_percent:.2f}% → {updated_validation.risk_percent:.2f}% ({risk_indicator})"""
    
    panel = Panel(
        content,
        title="🛡️ Risk Impact Analysis",
        border_style=risk_style
    )
    
    console.print(panel)


def create_statistics_overview_table(status_counts: Dict[str, int], 
                                    symbol_counts: Dict[str, int],
                                    risk_counts: Dict[str, int],
                                    total_plans: int) -> Table:
    """
    Create overview statistics table.
    
    Args:
        status_counts: Count of plans by status
        symbol_counts: Count of plans by symbol
        risk_counts: Count of plans by risk category
        total_plans: Total number of plans
        
    Returns:
        Rich Table with statistics overview
    """
    table = Table(title=f"📊 Plan Statistics Overview ({total_plans} total plans)")
    table.add_column("Category", style="bold")
    table.add_column("Count", justify="right")
    table.add_column("Percentage", justify="right")
    
    # Add status statistics
    table.add_section()
    for status, count in status_counts.items():
        percentage = (count / total_plans * 100) if total_plans > 0 else 0
        status_display = format_plan_status(TradePlanStatus(status)).split(' ', 1)[0]  # Get emoji only
        table.add_row(f"{status_display} {status.replace('_', ' ').title()}", 
                     str(count), f"{percentage:.1f}%")
    
    # Add top symbols
    if symbol_counts:
        table.add_section()
        top_symbols = sorted(symbol_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        for symbol, count in top_symbols:
            percentage = (count / total_plans * 100) if total_plans > 0 else 0
            table.add_row(f"📈 {symbol}", str(count), f"{percentage:.1f}%")
    
    # Add risk distribution
    if risk_counts:
        table.add_section()
        for risk_category, count in risk_counts.items():
            percentage = (count / total_plans * 100) if total_plans > 0 else 0
            risk_emoji = {"low": "🟢", "medium": "🟡", "high": "🔴"}.get(risk_category, "❓")
            table.add_row(f"{risk_emoji} {risk_category.title()} Risk", 
                         str(count), f"{percentage:.1f}%")
    
    return table


def display_plan_insights(total_plans: int, symbol_counts: Dict[str, int],
                         portfolio_data: Dict[str, Any]) -> None:
    """
    Display portfolio insights and recommendations.
    
    Args:
        total_plans: Total number of plans
        symbol_counts: Count of plans by symbol
        portfolio_data: Portfolio risk data
    """
    insights = []
    
    # Diversification analysis
    unique_symbols = len(symbol_counts)
    if total_plans > 0:
        avg_plans_per_symbol = total_plans / unique_symbols if unique_symbols > 0 else 0
        
        if unique_symbols == 1:
            insights.append("⚠️ Single symbol concentration - consider diversification")
        elif avg_plans_per_symbol > 3:
            insights.append("📊 High concentration in few symbols - review balance")
        else:
            insights.append("✅ Good symbol diversification")
    
    # Risk utilization analysis
    current_risk = portfolio_data.get('current_risk_percent', 0)
    max_risk = portfolio_data.get('max_risk_percent', 10)
    
    risk_utilization = (current_risk / max_risk * 100) if max_risk > 0 else 0
    
    if risk_utilization < 30:
        insights.append(f"📈 Conservative risk utilization ({risk_utilization:.1f}%) - room for growth")
    elif risk_utilization > 90:
        insights.append(f"⚠️ High risk utilization ({risk_utilization:.1f}%) - approaching limit")
    else:
        insights.append(f"✅ Balanced risk utilization ({risk_utilization:.1f}%)")
    
    # Portfolio health
    plans_with_errors = portfolio_data.get('plans_with_errors', 0)
    if plans_with_errors > 0:
        insights.append(f"🔧 {plans_with_errors} plan(s) need attention - check validation")
    
    if insights:
        content = "\n".join([f"• {insight}" for insight in insights])
        panel = Panel(
            content,
            title="💡 Portfolio Insights",
            border_style="blue"
        )
        console.print(panel)


def display_guidance_footer(command_context: str, verbose: bool = False) -> None:
    """
    Display contextual guidance footer for commands.
    
    Args:
        command_context: Context identifier for the command
        verbose: Whether verbose mode is active
    """
    guidance_map = {
        "list_plans": [
            "💡 Use --verbose for detailed information",
            "🔍 Use --status to filter by plan status", 
            "📊 Use --sort-by to change ordering"
        ],
        "validate_config": [
            "💡 Use --verbose for detailed error information",
            "🔧 Use --file FILENAME to validate specific plan",
            "📋 Fix validation errors before activating plans"
        ],
        "update_plan": [
            "💾 Backup created automatically before updates",
            "🔄 Position size recalculated after price changes",
            "⚠️ Updates require confirmation for safety"
        ],
        "archive_plans": [
            "📁 Plans organized by status and date",
            "🔒 Archive operation is reversible",
            "📊 Use plan-stats to review before archiving"
        ]
    }
    
    guidance = guidance_map.get(command_context, [])
    
    if not verbose and guidance:
        console.print("\n" + "\n".join(guidance), style="dim")
    elif verbose:
        console.print("\n💡 Verbose mode active - showing all available details", style="dim")