"""Backup and verification utilities for trade plan management."""

from __future__ import annotations

import shutil
import yaml
from datetime import datetime
from pathlib import Path

from ..logging_config import get_logger

logger = get_logger("backup_utils", "cli")


class BackupCreationError(Exception):
    """Raised when plan backup creation fails."""
    pass


class BackupVerificationError(Exception):
    """Raised when plan backup verification fails."""
    pass


def create_plan_backup(plan_path: Path, backup_dir: Path) -> Path:
    """
    Create a timestamped backup of a trade plan file.
    
    Args:
        plan_path: Path to the original plan file
        backup_dir: Directory to store backups
        
    Returns:
        Path to the created backup file
        
    Raises:
        BackupCreationError: If backup creation fails
    """
    if not plan_path.exists():
        raise BackupCreationError(f"Original plan file not found: {plan_path}")
    
    try:
        # Create backup directory if it doesn't exist
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate timestamped backup filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{plan_path.stem}.backup.{timestamp}.yaml"
        backup_path = backup_dir / backup_filename
        
        # Copy the file
        shutil.copy2(plan_path, backup_path)
        logger.info(f"Created backup: {backup_path}")
        
        return backup_path
        
    except (IOError, OSError, PermissionError) as e:
        raise BackupCreationError(f"Failed to create backup: {e}")
    except shutil.SameFileError as e:
        raise BackupCreationError(f"Failed to create backup: {e}")


def verify_backup(original_path: Path, backup_path: Path) -> bool:
    """
    Verify backup integrity by comparing size and validating YAML format.
    
    Args:
        original_path: Path to original file
        backup_path: Path to backup file
        
    Returns:
        True if backup is valid
        
    Raises:
        BackupVerificationError: If verification fails
    """
    # Check if both files exist
    if not original_path.exists():
        raise BackupVerificationError(f"Original file not found: {original_path}")
    
    if not backup_path.exists():
        raise BackupVerificationError(f"Backup file does not exist: {backup_path}")
    
    try:
        # Compare file sizes
        original_size = original_path.stat().st_size
        backup_size = backup_path.stat().st_size
        
        if original_size != backup_size:
            logger.error(f"Size mismatch: original={original_size}, backup={backup_size}")
            raise BackupVerificationError(f"Backup size mismatch: original={original_size}, backup={backup_size}")
        
        # Validate backup YAML format
        with backup_path.open('r', encoding='utf-8') as f:
            content = f.read().strip()
            if not content:
                raise BackupVerificationError("Backup file is empty")
            
            # Parse YAML
            f.seek(0)
            yaml.safe_load(f)
        
        logger.info(f"Backup verification successful: {backup_path}")
        return True
        
    except yaml.YAMLError as e:
        error_msg = f"Backup contains invalid YAML: {e}"
        logger.error(error_msg)
        
        # Clean up invalid backup
        try:
            backup_path.unlink()
            logger.info(f"Removed invalid backup: {backup_path}")
        except Exception as cleanup_error:
            logger.error(f"Failed to remove invalid backup: {cleanup_error}")
        
        raise BackupVerificationError(error_msg)
        
    except (IOError, OSError, PermissionError) as e:
        error_msg = f"Backup verification I/O error: {e}"
        logger.error(error_msg)
        raise BackupVerificationError(error_msg)


def cleanup_old_backups(backup_dir: Path, retention_days: int = 30) -> int:
    """
    Clean up backup files older than retention period.
    
    Args:
        backup_dir: Directory containing backup files
        retention_days: Number of days to retain backups
        
    Returns:
        Number of files cleaned up
    """
    if not backup_dir.exists():
        return 0
    
    cutoff_time = datetime.now().timestamp() - (retention_days * 24 * 3600)
    cleaned_count = 0
    
    try:
        for backup_file in backup_dir.glob("*.backup.*.yaml"):
            if backup_file.stat().st_mtime < cutoff_time:
                backup_file.unlink()
                logger.info(f"Cleaned up old backup: {backup_file}")
                cleaned_count += 1
                
    except Exception as e:
        logger.error(f"Error during backup cleanup: {e}")
    
    return cleaned_count


def get_backup_info(backup_path: Path) -> dict:
    """
    Get information about a backup file.
    
    Args:
        backup_path: Path to backup file
        
    Returns:
        Dictionary with backup information
    """
    if not backup_path.exists():
        return {"exists": False}
    
    stat = backup_path.stat()
    
    return {
        "exists": True,
        "size": stat.st_size,
        "created": datetime.fromtimestamp(stat.st_ctime),
        "modified": datetime.fromtimestamp(stat.st_mtime),
        "name": backup_path.name
    }