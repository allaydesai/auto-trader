"""Backup management for portfolio state persistence."""

from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional

from ..logging_config import get_logger

logger = get_logger("backup_manager", "risk")


class BackupManager:
    """Manages backup operations for portfolio state files."""
    
    def __init__(self, state_file: Path) -> None:
        """
        Initialize backup manager.
        
        Args:
            state_file: Path to the state file to manage backups for
        """
        self.state_file = state_file
        
    def create_backup(self, backup_path: Optional[Path] = None) -> Path:
        """
        Create a backup of the current state.
        
        Args:
            backup_path: Optional custom backup path
            
        Returns:
            Path to created backup file
        """
        if backup_path is None:
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_path = self.state_file.with_suffix(f".backup_{timestamp}.json")
        
        try:
            if self.state_file.exists():
                shutil.copy2(self.state_file, backup_path)
                
                logger.info(
                    "Portfolio state backup created",
                    original_file=str(self.state_file),
                    backup_file=str(backup_path),
                )
            else:
                logger.warning("No state file exists to backup")
                
        except Exception as e:
            logger.error(
                "Failed to create backup",
                backup_path=str(backup_path),
                error=str(e),
            )
            raise
        
        return backup_path
    
    def create_automated_backup(self) -> None:
        """Create automated backup with rotation."""
        try:
            # Create timestamped backup
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            backup_path = self.state_file.with_suffix(f".backup_{timestamp}.json")
            
            if self.state_file.exists():
                shutil.copy2(self.state_file, backup_path)
                
                logger.debug(
                    "Automated backup created",
                    backup_file=str(backup_path),
                )
                
                # Rotate old backups (keep last 10)
                self.rotate_backups()
                
        except Exception as e:
            logger.warning(
                "Failed to create automated backup",
                error=str(e),
            )
            # Don't raise - backup failure shouldn't stop state persistence
    
    def rotate_backups(self, max_backups: int = 10) -> None:
        """Rotate backup files, keeping only the most recent ones."""
        try:
            backup_dir = self.state_file.parent
            backup_pattern = f"{self.state_file.stem}.backup_*.json"
            
            # Find all backup files
            backup_files = list(backup_dir.glob(backup_pattern))
            
            if len(backup_files) > max_backups:
                # Sort by modification time (oldest first)
                backup_files.sort(key=lambda f: f.stat().st_mtime)
                
                # Remove excess backups
                files_to_remove = backup_files[:-max_backups]
                removed_count = 0
                
                for backup_file in files_to_remove:
                    try:
                        backup_file.unlink()
                        removed_count += 1
                    except Exception as e:
                        logger.warning(
                            "Failed to remove old backup file",
                            file_path=str(backup_file),
                            error=str(e),
                        )
                
                if removed_count > 0:
                    logger.info(
                        "Rotated backup files",
                        removed_count=removed_count,
                        remaining_backups=len(backup_files) - removed_count,
                        max_backups=max_backups,
                    )
                    
        except Exception as e:
            logger.warning(
                "Failed to rotate backup files",
                error=str(e),
            )