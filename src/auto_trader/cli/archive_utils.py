"""Archive and organization utilities for trade plan management."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from rich.table import Table

from ..logging_config import get_logger
from ..models import TradePlan, TradePlanStatus

logger = get_logger("archive_utils", "cli")


class ArchiveError(Exception):
    """Base exception for archive operations."""
    pass


def organize_plans_for_archive(plans: List[TradePlan]) -> Dict[str, List[TradePlan]]:
    """
    Organize plans into archive groups by status.
    
    Args:
        plans: List of trade plans to organize
        
    Returns:
        Dictionary mapping archive categories to plans
    """
    archive_groups = {
        "completed": [],
        "cancelled": [],
        "error": []
    }
    
    archivable_statuses = {
        TradePlanStatus.COMPLETED,
        TradePlanStatus.CANCELLED,
        TradePlanStatus.ERROR
    }
    
    for plan in plans:
        if plan.status in archivable_statuses:
            # Handle both enum and string status values
            group_key = plan.status.value if hasattr(plan.status, 'value') else str(plan.status)
            if group_key in archive_groups:
                archive_groups[group_key].append(plan)
    
    # Remove empty groups
    return {k: v for k, v in archive_groups.items() if v}


def create_archive_preview_table(archive_groups: Dict[str, List[TradePlan]]) -> tuple[Table, int]:
    """
    Create table showing plans to be archived.
    
    Args:
        archive_groups: Dictionary of plans grouped by archive category
        
    Returns:
        Tuple of (Rich Table, total count)
    """
    table = Table(title="Plans to Archive")
    table.add_column("Category", style="bold")
    table.add_column("Count", justify="right")
    table.add_column("Plans", style="dim")
    
    total_plans = 0
    
    for category, plans in archive_groups.items():
        count = len(plans)
        total_plans += count
        
        # Create truncated list of plan IDs
        plan_ids = [plan.plan_id for plan in plans]
        if len(plan_ids) > 3:
            plan_display = f"{', '.join(plan_ids[:3])}, ... and {len(plan_ids) - 3} more"
        else:
            plan_display = ', '.join(plan_ids)
        
        # Add emoji for category
        category_display = {
            "completed": f"✅ {category.title()}",
            "cancelled": f"❌ {category.title()}",
            "error": f"⚠️ {category.title()}"
        }.get(category, category.title())
        
        table.add_row(category_display, str(count), plan_display)
    
    return table, total_plans


def perform_plan_archiving(archive_groups: Dict[str, List[TradePlan]], 
                          plans_dir: Path, archive_base_dir: Path) -> Dict[str, int]:
    """
    Move plans to archive directories organized by status and date.
    
    Args:
        archive_groups: Plans organized by archive category
        plans_dir: Source directory containing plan files
        archive_base_dir: Base directory for archives
        
    Returns:
        Dictionary with counts of archived plans by category
        
    Raises:
        ArchiveError: If archiving fails
    """
    results = {}
    current_date = datetime.now()
    year_month = current_date.strftime("%Y/%m")
    
    for category, plans in archive_groups.items():
        category_results = 0
        
        # Create category-specific archive directory
        archive_dir = archive_base_dir / category / year_month
        archive_dir.mkdir(parents=True, exist_ok=True)
        
        for plan in plans:
            try:
                source_path = plans_dir / f"{plan.plan_id}.yaml"
                
                if not source_path.exists():
                    logger.warning(f"Plan file not found for archiving: {source_path}")
                    continue
                
                # Create destination path
                dest_path = archive_dir / f"{plan.plan_id}.yaml"
                
                # Move the file
                shutil.move(str(source_path), str(dest_path))
                logger.info(f"Archived {plan.plan_id} to {dest_path}")
                category_results += 1
                
            except (IOError, OSError, PermissionError) as e:
                logger.error(f"Failed to archive {plan.plan_id}: {e}")
                raise ArchiveError(f"Failed to archive {plan.plan_id}: {e}")
        
        results[category] = category_results
    
    return results


def get_archive_statistics(archive_base_dir: Path) -> Dict[str, any]:
    """
    Get statistics about archived plans.
    
    Args:
        archive_base_dir: Base directory for archives
        
    Returns:
        Dictionary with archive statistics
    """
    stats = {
        "total_archived": 0,
        "by_category": {},
        "by_month": {},
        "oldest_archive": None,
        "newest_archive": None
    }
    
    if not archive_base_dir.exists():
        return stats
    
    archive_files = []
    
    # Scan all archive files
    for category_dir in archive_base_dir.iterdir():
        if not category_dir.is_dir():
            continue
            
        category_count = 0
        
        # Scan year/month subdirectories
        for year_dir in category_dir.rglob("*.yaml"):
            archive_files.append(year_dir)
            category_count += 1
            
            # Track monthly statistics
            try:
                # Extract year/month from path
                parts = year_dir.parts
                if len(parts) >= 3:
                    year_month = f"{parts[-3]}/{parts[-2]}"
                    stats["by_month"][year_month] = stats["by_month"].get(year_month, 0) + 1
            except (IndexError, ValueError):
                pass
        
        stats["by_category"][category_dir.name] = category_count
        stats["total_archived"] += category_count
    
    # Find oldest and newest archives
    if archive_files:
        archive_files.sort(key=lambda f: f.stat().st_ctime)
        stats["oldest_archive"] = datetime.fromtimestamp(archive_files[0].stat().st_ctime)
        stats["newest_archive"] = datetime.fromtimestamp(archive_files[-1].stat().st_ctime)
    
    return stats


def restore_plan_from_archive(plan_id: str, archive_base_dir: Path, 
                             plans_dir: Path) -> bool:
    """
    Restore a plan from archive back to active plans directory.
    
    Args:
        plan_id: ID of plan to restore
        archive_base_dir: Base directory for archives
        plans_dir: Active plans directory
        
    Returns:
        True if restoration was successful
        
    Raises:
        ArchiveError: If restoration fails
    """
    # Search for the plan in all archive categories
    plan_file = f"{plan_id}.yaml"
    
    for archive_file in archive_base_dir.rglob(plan_file):
        try:
            dest_path = plans_dir / plan_file
            
            if dest_path.exists():
                raise ArchiveError(f"Plan {plan_id} already exists in active directory")
            
            shutil.move(str(archive_file), str(dest_path))
            logger.info(f"Restored {plan_id} from archive to {dest_path}")
            return True
            
        except (IOError, OSError, PermissionError) as e:
            raise ArchiveError(f"Failed to restore {plan_id}: {e}")
    
    raise ArchiveError(f"Plan {plan_id} not found in archives")