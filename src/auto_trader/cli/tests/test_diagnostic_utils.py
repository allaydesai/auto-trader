"""Tests for CLI diagnostic utilities."""

import tempfile
from pathlib import Path
from unittest.mock import patch, Mock

import pytest

from ..diagnostic_utils import (
    check_configuration,
    check_trade_plans,
    check_permissions,
    display_diagnostic_summary,
    export_debug_information,
)


class TestDiagnosticUtils:
    """Test diagnostic utility functions."""

    def test_check_configuration_success(self, tmp_path):
        """Test configuration check with valid config."""
        with patch('auto_trader.cli.diagnostic_utils.Settings') as mock_settings, \
             patch('auto_trader.cli.diagnostic_utils.ConfigLoader') as mock_loader, \
             patch('auto_trader.cli.diagnostic_utils.Path') as mock_path:
            
            # Setup mocks
            mock_settings.return_value.user_config_file = tmp_path / "user_config.yaml"
            mock_config_loader = Mock()
            mock_config_loader.validate_configuration.return_value = []
            mock_loader.return_value = mock_config_loader
            
            # Mock .env file exists
            mock_env = Mock()
            mock_env.exists.return_value = True
            mock_path.return_value = mock_env
            
            # Create user config file
            (tmp_path / "user_config.yaml").touch()
            
            results = check_configuration()
            
            assert len(results) >= 2
            assert any(r["check"] == "Environment file" and r["status"] == "✅" for r in results)
            assert any(r["check"] == "Configuration validation" and r["status"] == "✅" for r in results)
    
    def test_check_configuration_missing_env(self):
        """Test configuration check with missing .env file."""
        with patch('auto_trader.cli.diagnostic_utils.Settings') as mock_settings, \
             patch('auto_trader.cli.diagnostic_utils.ConfigLoader') as mock_loader, \
             patch('auto_trader.cli.diagnostic_utils.Path') as mock_path:
            
            # Setup mocks
            mock_settings.return_value.user_config_file = Path("nonexistent.yaml")
            mock_config_loader = Mock()
            mock_config_loader.validate_configuration.return_value = []
            mock_loader.return_value = mock_config_loader
            
            # Mock .env file doesn't exist
            mock_env = Mock()
            mock_env.exists.return_value = False
            mock_path.return_value = mock_env
            
            results = check_configuration()
            
            assert any(r["check"] == "Environment file" and r["status"] == "⚠️" for r in results)
    
    def test_check_configuration_validation_errors(self):
        """Test configuration check with validation errors."""
        with patch('auto_trader.cli.diagnostic_utils.Settings') as mock_settings, \
             patch('auto_trader.cli.diagnostic_utils.ConfigLoader') as mock_loader, \
             patch('auto_trader.cli.diagnostic_utils.Path') as mock_path:
            
            # Setup mocks
            mock_settings.return_value.user_config_file = Path("nonexistent.yaml")
            mock_config_loader = Mock()
            mock_config_loader.validate_configuration.return_value = ["Missing webhook URL"]
            mock_loader.return_value = mock_config_loader
            
            # Mock .env file exists
            mock_env = Mock()
            mock_env.exists.return_value = True
            mock_path.return_value = mock_env
            
            results = check_configuration()
            
            assert any(r["check"] == "Configuration validation" and r["status"] == "❌" for r in results)
    
    def test_check_trade_plans_success(self, tmp_path):
        """Test trade plans check with valid plans."""
        with patch('auto_trader.cli.diagnostic_utils.TradePlanLoader') as mock_loader:
            # Setup mock loader
            mock_instance = Mock()
            mock_plans_dir = Mock()
            mock_plans_dir.exists.return_value = True
            mock_plans_dir.glob.return_value = [tmp_path / "plan1.yaml", tmp_path / "plan2.yaml"]
            mock_instance.plans_directory = mock_plans_dir
            mock_instance.load_all_plans.return_value = {"plan1": Mock(), "plan2": Mock()}
            mock_loader.return_value = mock_instance
            
            results = check_trade_plans()
            
            assert any(r["check"] == "Plans directory" and r["status"] == "✅" for r in results)
            assert any(r["check"] == "YAML files" and r["status"] == "📄" for r in results)
            assert any(r["check"] == "Plan loading" and r["status"] == "✅" for r in results)
    
    def test_check_trade_plans_missing_directory(self):
        """Test trade plans check with missing directory."""
        with patch('auto_trader.cli.diagnostic_utils.TradePlanLoader') as mock_loader:
            # Setup mock loader
            mock_instance = Mock()
            mock_plans_dir = Mock()
            mock_plans_dir.exists.return_value = False
            mock_instance.plans_directory = mock_plans_dir
            mock_loader.return_value = mock_instance
            
            results = check_trade_plans()
            
            assert any(r["check"] == "Plans directory" and r["status"] == "❌" for r in results)
    
    def test_check_permissions_success(self, tmp_path):
        """Test permissions check with write access."""
        with patch('auto_trader.cli.diagnostic_utils.Path') as mock_path_class:
            # Mock Path.cwd() and directory checks
            mock_cwd = Mock()
            mock_cwd.is_dir.return_value = True
            mock_cwd.stat.return_value.st_mode = 0o755  # Has write permission
            mock_path_class.cwd.return_value = mock_cwd
            
            # Mock other directories
            def path_side_effect(path_str):
                mock_path = Mock()
                mock_path.exists.return_value = True
                mock_path.stat.return_value.st_mode = 0o755
                return mock_path
            
            mock_path_class.side_effect = path_side_effect
            
            results = check_permissions()
            
            assert len(results) >= 1
            assert any(r["status"] == "✅" for r in results)
    
    def test_display_diagnostic_summary_success(self, capsys):
        """Test diagnostic summary display with successful results."""
        results = [
            {"check": "Test 1", "status": "✅", "message": "Success", "level": "success"},
            {"check": "Test 2", "status": "⚠️", "message": "Warning", "level": "warning"},
        ]
        
        display_diagnostic_summary(results)
        
        # Test passes if no exceptions are raised
        # Rich output is difficult to test directly, but we ensure the function executes
        assert True
    
    def test_display_diagnostic_summary_errors(self, capsys):
        """Test diagnostic summary display with error results."""
        results = [
            {"check": "Test 1", "status": "❌", "message": "Error", "level": "error"},
            {"check": "Test 2", "status": "📄", "message": "Info", "level": "info"},
        ]
        
        display_diagnostic_summary(results)
        
        # Test passes if no exceptions are raised
        assert True
    
    def test_export_debug_information_success(self, tmp_path):
        """Test debug information export."""
        results = [
            {"check": "Test", "status": "✅", "message": "Success", "level": "success"}
        ]
        
        with patch('auto_trader.cli.diagnostic_utils.Path') as mock_path_class:
            # Mock Path.cwd()
            mock_path_class.cwd.return_value = tmp_path
            
            # Create a temporary debug file
            debug_file = tmp_path / "debug.json"
            
            with patch('builtins.open', create=True) as mock_open:
                mock_open.return_value.__enter__.return_value = Mock()
                export_debug_information(results)
                
                # Test passes if no exceptions are raised
                assert True
    
    def test_export_debug_information_failure(self):
        """Test debug information export with file error."""
        results = [
            {"check": "Test", "status": "✅", "message": "Success", "level": "success"}
        ]
        
        with patch('builtins.open', side_effect=IOError("Permission denied")):
            # Should handle the error gracefully
            export_debug_information(results)
            
            # Test passes if no exceptions are raised
            assert True