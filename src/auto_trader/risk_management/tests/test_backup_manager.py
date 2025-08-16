"""Tests for BackupManager class."""

import json
import pytest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch, mock_open

from auto_trader.risk_management.backup_manager import BackupManager


class TestBackupManagerInitialization:
    """Test BackupManager initialization."""
    
    def test_init_with_state_file(self, tmp_path):
        """Test initialization with state file."""
        state_file = tmp_path / "test_state.json"
        backup_manager = BackupManager(state_file)
        
        assert backup_manager.state_file == state_file


class TestBackupCreation:
    """Test backup creation functionality."""
    
    def test_create_backup_success(self, tmp_path):
        """Test successful backup creation."""
        state_file = tmp_path / "state.json"
        state_file.write_text('{"test": "data"}')
        
        backup_manager = BackupManager(state_file)
        backup_path = backup_manager.create_backup()
        
        assert backup_path.exists()
        assert backup_path.read_text() == '{"test": "data"}'
        assert backup_path.name.startswith("state.backup_")
        assert backup_path.name.endswith(".json")
    
    def test_create_backup_custom_path(self, tmp_path):
        """Test backup creation with custom path."""
        state_file = tmp_path / "state.json"
        state_file.write_text('{"test": "data"}')
        custom_backup = tmp_path / "custom_backup.json"
        
        backup_manager = BackupManager(state_file)
        backup_path = backup_manager.create_backup(custom_backup)
        
        assert backup_path == custom_backup
        assert backup_path.exists()
        assert backup_path.read_text() == '{"test": "data"}'
    
    def test_create_backup_no_state_file(self, tmp_path):
        """Test backup creation when state file doesn't exist."""
        state_file = tmp_path / "nonexistent.json"
        backup_manager = BackupManager(state_file)
        backup_path = backup_manager.create_backup()
        
        # Backup path should be generated but file shouldn't exist
        assert backup_path.name.startswith("nonexistent.backup_")
        assert not backup_path.exists()
    
    def test_create_backup_error_handling(self, tmp_path):
        """Test backup creation error handling."""
        state_file = tmp_path / "state.json"
        state_file.write_text('{"test": "data"}')
        
        # Create backup path in non-existent directory
        invalid_backup = Path("/nonexistent/dir/backup.json")
        
        backup_manager = BackupManager(state_file)
        
        with pytest.raises(Exception):
            backup_manager.create_backup(invalid_backup)


class TestAutomatedBackup:
    """Test automated backup functionality."""
    
    def test_create_automated_backup_success(self, tmp_path):
        """Test successful automated backup creation."""
        state_file = tmp_path / "state.json"
        state_file.write_text('{"test": "data"}')
        
        backup_manager = BackupManager(state_file)
        backup_manager.create_automated_backup()
        
        # Find the created backup
        backup_files = list(tmp_path.glob("state.backup_*.json"))
        assert len(backup_files) == 1
        assert backup_files[0].read_text() == '{"test": "data"}'
    
    def test_create_automated_backup_no_state_file(self, tmp_path):
        """Test automated backup when state file doesn't exist."""
        state_file = tmp_path / "nonexistent.json"
        backup_manager = BackupManager(state_file)
        
        # Should not raise exception
        backup_manager.create_automated_backup()
        
        backup_files = list(tmp_path.glob("*.backup_*.json"))
        assert len(backup_files) == 0
    
    @patch('auto_trader.risk_management.backup_manager.shutil.copy2')
    def test_create_automated_backup_with_rotation(self, mock_copy, tmp_path):
        """Test automated backup calls rotation."""
        state_file = tmp_path / "state.json"
        state_file.write_text('{"test": "data"}')
        
        backup_manager = BackupManager(state_file)
        
        with patch.object(backup_manager, 'rotate_backups') as mock_rotate:
            backup_manager.create_automated_backup()
            mock_rotate.assert_called_once()
    
    def test_create_automated_backup_error_no_exception(self, tmp_path):
        """Test automated backup handles errors gracefully."""
        state_file = tmp_path / "state.json"
        state_file.write_text('{"test": "data"}')
        
        backup_manager = BackupManager(state_file)
        
        with patch('auto_trader.risk_management.backup_manager.shutil.copy2', side_effect=Exception("Test error")):
            # Should not raise exception
            backup_manager.create_automated_backup()
            
        # Should complete without raising exception
        assert True


class TestBackupRotation:
    """Test backup rotation functionality."""
    
    def test_rotate_backups_no_excess(self, tmp_path):
        """Test rotation when no excess backups exist."""
        state_file = tmp_path / "state.json"
        backup_manager = BackupManager(state_file)
        
        # Create 5 backup files (less than default max of 10)
        for i in range(5):
            backup_file = tmp_path / f"state.backup_{i:08d}_000000.json"
            backup_file.write_text(f'{{"backup": {i}}}')
        
        backup_manager.rotate_backups()
        
        # All files should still exist
        backup_files = list(tmp_path.glob("state.backup_*.json"))
        assert len(backup_files) == 5
    
    def test_rotate_backups_with_excess(self, tmp_path):
        """Test rotation removes excess backup files."""
        import time
        
        state_file = tmp_path / "state.json"
        backup_manager = BackupManager(state_file)
        
        # Create 15 backup files with different timestamps (more than default max of 10)
        for i in range(15):
            backup_file = tmp_path / f"state.backup_{i:08d}_000000.json"
            backup_file.write_text(f'{{"backup": {i}}}')
            # Set different modification times to ensure proper sorting
            time.sleep(0.001)
        
        backup_manager.rotate_backups()
        
        # Should keep only 10 most recent files
        backup_files = list(tmp_path.glob("state.backup_*.json"))
        assert len(backup_files) == 10
    
    def test_rotate_backups_custom_max(self, tmp_path):
        """Test rotation with custom max backups."""
        state_file = tmp_path / "state.json"
        backup_manager = BackupManager(state_file)
        
        # Create 8 backup files
        for i in range(8):
            backup_file = tmp_path / f"state.backup_{i:08d}_000000.json"
            backup_file.write_text(f'{{"backup": {i}}}')
        
        backup_manager.rotate_backups(max_backups=5)
        
        # Should keep only 5 most recent files
        backup_files = list(tmp_path.glob("state.backup_*.json"))
        assert len(backup_files) == 5
    
    def test_rotate_backups_error_handling(self, tmp_path):
        """Test rotation error handling."""
        state_file = tmp_path / "state.json"
        backup_manager = BackupManager(state_file)
        
        # Create a backup file
        backup_file = tmp_path / "state.backup_00000001_000000.json"
        backup_file.write_text('{"test": "data"}')
        
        with patch.object(Path, 'glob', side_effect=Exception("Test error")):
            backup_manager.rotate_backups()
            
        # Should complete without raising exception
        assert True
    
    def test_rotate_backups_file_deletion_error(self, tmp_path):
        """Test rotation handles file deletion errors gracefully."""
        state_file = tmp_path / "state.json"
        backup_manager = BackupManager(state_file)
        
        # Create 12 backup files (more than default max of 10)
        for i in range(12):
            backup_file = tmp_path / f"state.backup_{i:08d}_000000.json"
            backup_file.write_text(f'{{"backup": {i}}}')
        
        with patch.object(Path, 'unlink', side_effect=Exception("Delete error")):
            backup_manager.rotate_backups()
            
        # Should complete without raising exception
        assert True


class TestBackupTimestamps:
    """Test backup timestamp generation."""
    
    def test_backup_timestamp_format(self, tmp_path):
        """Test backup files have correct timestamp format."""
        state_file = tmp_path / "state.json"
        state_file.write_text('{"test": "data"}')
        
        backup_manager = BackupManager(state_file)
        
        with patch('auto_trader.risk_management.backup_manager.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2025, 8, 16, 14, 30, 45)
            mock_datetime.strftime = datetime.strftime
            
            backup_path = backup_manager.create_backup()
            
        expected_suffix = "backup_20250816_143045.json"
        assert backup_path.name.endswith(expected_suffix)
    
    def test_automated_backup_timestamp_format(self, tmp_path):
        """Test automated backup files have correct timestamp format."""
        state_file = tmp_path / "state.json"
        state_file.write_text('{"test": "data"}')
        
        backup_manager = BackupManager(state_file)
        
        with patch('auto_trader.risk_management.backup_manager.datetime') as mock_datetime:
            mock_datetime.utcnow.return_value = datetime(2025, 8, 16, 14, 30, 45)
            mock_datetime.strftime = datetime.strftime
            
            backup_manager.create_automated_backup()
            
        backup_files = list(tmp_path.glob("state.backup_20250816_143045.json"))
        assert len(backup_files) == 1