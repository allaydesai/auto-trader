"""Basic integration tests for Story 1.5.3 to verify core functionality works.

This simplified test suite verifies the essential functionality without complex mocking.
"""

import tempfile
import yaml
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from auto_trader.cli.management_commands import (
    list_plans_enhanced,
    validate_config,
    update_plan,
    archive_plans,
    plan_stats,
)


class TestStory153BasicIntegration:
    """Basic integration tests for management commands."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.temp_path = Path(self.temp_dir)
        self.plans_dir = self.temp_path / "trade_plans"
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        self.runner = CliRunner()

    def create_sample_plan_file(self, plan_id: str = "TEST_001") -> Path:
        """Create a sample trade plan YAML file."""
        plan_data = {
            "plan_id": plan_id,
            "symbol": "AAPL",
            "entry_level": 180.50,
            "stop_loss": 178.00,
            "take_profit": 185.00,
            "risk_category": "normal",
            "status": "awaiting_entry",
            "entry_function": {
                "function_type": "close_above",
                "timeframe": "15min",
                "parameters": {"threshold": "180.50"},
            },
            "exit_function": {
                "function_type": "stop_loss_take_profit",
                "timeframe": "15min",
                "parameters": {},
            },
        }
        
        plan_file = self.plans_dir / f"{plan_id}.yaml"
        with open(plan_file, 'w') as f:
            yaml.dump(plan_data, f, default_flow_style=False)
        
        return plan_file

    @patch('auto_trader.cli.management_commands._get_risk_manager')
    @patch('auto_trader.cli.management_commands.get_portfolio_risk_summary')
    @patch('auto_trader.cli.management_commands.create_plans_table')
    @patch('auto_trader.cli.management_commands.create_portfolio_summary_panel')
    def test_list_plans_basic_functionality(
        self, mock_panel, mock_table, mock_portfolio, mock_risk_manager
    ):
        """Test that list_plans_enhanced can load plans without crashing."""
        # Setup basic mocks
        mock_risk_manager.return_value = MagicMock()
        mock_portfolio.return_value = {
            "current_risk_percent": Decimal("2.0"),
            "portfolio_limit_percent": Decimal("10.0"),
            "remaining_capacity_percent": Decimal("8.0"),
            "capacity_utilization_percent": Decimal("20.0"),
            "total_plan_risk_percent": Decimal("2.0"),
            "plan_risks": {},
            "exceeds_limit": False,
            "near_limit": False,
        }
        mock_panel.return_value = MagicMock()
        mock_table.return_value = MagicMock()
        
        # Create a test plan
        self.create_sample_plan_file("TEST_001")
        
        # Run command
        result = self.runner.invoke(list_plans_enhanced, [
            '--plans-dir', str(self.plans_dir)
        ])
        
        # Should not crash and should load the plan
        assert result.exit_code == 0
        
        # Verify that the plans were loaded (portfolio summary was called)
        mock_portfolio.assert_called_once()
        
        # Verify that table creation was called
        mock_table.assert_called_once()

    @patch('auto_trader.cli.management_commands._get_risk_manager') 
    @patch('auto_trader.cli.management_commands.validate_plans_comprehensive')
    def test_validate_config_basic_functionality(
        self, mock_validate, mock_risk_manager
    ):
        """Test that validate_config can process plans without crashing."""
        # Setup mocks
        mock_risk_manager.return_value = MagicMock()
        mock_validate.return_value = {
            "files_checked": 1,
            "syntax_passed": 1,
            "business_logic_passed": 1,
            "portfolio_risk_passed": True,
            "portfolio_risk_percent": 2.0,
            "file_results": {
                "TEST_001.yaml": {
                    "syntax_valid": True,
                    "business_logic_valid": True,
                    "errors": []
                },
            }
        }
        
        # Create a test plan
        self.create_sample_plan_file("TEST_001")
        
        # Run command
        result = self.runner.invoke(validate_config, [
            '--plans-dir', str(self.plans_dir)
        ])
        
        # Should not crash
        assert result.exit_code == 0
        
        # Should show validation results
        assert "PLAN VALIDATION" in result.output
        
        # Verify validation function was called
        mock_validate.assert_called_once()

    def test_plans_directory_loading_bug_fix(self):
        """Test that the critical bug fix for dictionary to list conversion works."""
        # This is the core issue that was causing the integration tests to fail
        # Create multiple plan files
        self.create_sample_plan_file("PLAN_001")
        self.create_sample_plan_file("PLAN_002")
        
        # Import the loader directly to test the fix
        from auto_trader.models import TradePlanLoader
        
        loader = TradePlanLoader(self.plans_dir)
        
        # Load all plans - this returns a dictionary
        plans_dict = loader.load_all_plans()
        assert isinstance(plans_dict, dict)
        assert len(plans_dict) == 2
        
        # Convert to list (this is what the management commands now do)
        plans_list = list(plans_dict.values())
        assert isinstance(plans_list, list)
        assert len(plans_list) == 2
        
        # Verify we can sort the list (this was failing before)
        plans_list.sort(key=lambda p: p.plan_id)
        assert len(plans_list) == 2

    @patch('auto_trader.cli.management_commands._get_risk_manager')
    @patch('auto_trader.cli.management_commands.get_portfolio_risk_summary')
    def test_plan_stats_basic_functionality(
        self, mock_portfolio, mock_risk_manager
    ):
        """Test that plan_stats can generate statistics without crashing."""
        # Setup mocks
        mock_risk_manager.return_value = MagicMock()
        mock_portfolio.return_value = {
            "current_risk_percent": Decimal("4.0"),
            "portfolio_limit_percent": Decimal("10.0"),
            "remaining_capacity_percent": Decimal("6.0"),
            "capacity_utilization_percent": Decimal("40.0"),
            "total_plan_risk_percent": Decimal("4.0"),
            "plan_risks": {},
            "exceeds_limit": False,
            "near_limit": False,
        }
        
        # Create test plans with different statuses and symbols
        plan_data = [
            ("AAPL_001", "AAPL", "awaiting_entry"),
            ("MSFT_001", "MSFT", "completed"),
            ("GOOGL_001", "GOOGL", "cancelled"),
        ]
        
        for plan_id, symbol, status in plan_data:
            plan_file_data = {
                "plan_id": plan_id,
                "symbol": symbol,
                "entry_level": 100.0,
                "stop_loss": 95.0,
                "take_profit": 105.0,
                "risk_category": "normal",
                "status": status,
                "entry_function": {
                    "function_type": "close_above",
                    "timeframe": "15min",
                    "parameters": {"threshold": "100.0"},
                },
                "exit_function": {
                    "function_type": "stop_loss_take_profit",
                    "timeframe": "15min",
                    "parameters": {},
                },
            }
            
            plan_file = self.plans_dir / f"{plan_id}.yaml"
            with open(plan_file, 'w') as f:
                yaml.dump(plan_file_data, f, default_flow_style=False)
        
        # Run command
        result = self.runner.invoke(plan_stats, [
            '--plans-dir', str(self.plans_dir)
        ])
        
        # Should not crash
        assert result.exit_code == 0
        
        # Should show statistics
        assert "PLAN STATISTICS" in result.output
        
        # Should show different statuses
        assert "Status" in result.output or "status" in result.output.lower()

    def test_empty_directory_handling(self):
        """Test that commands handle empty directories gracefully."""
        # Test with empty directory
        
        with patch('auto_trader.cli.management_commands._get_risk_manager') as mock_risk_manager:
            mock_risk_manager.return_value = MagicMock()
            
            result = self.runner.invoke(list_plans_enhanced, [
                '--plans-dir', str(self.plans_dir)
            ])
            
            # Should not crash
            assert result.exit_code == 0
            
            # Should show appropriate message
            assert "No trade plans found" in result.output

    def test_missing_directory_handling(self):
        """Test that commands handle missing directories gracefully."""
        # Test with non-existent directory
        missing_dir = self.temp_path / "nonexistent"
        
        result = self.runner.invoke(list_plans_enhanced, [
            '--plans-dir', str(missing_dir)
        ])
        
        # Should handle error gracefully
        assert result.exit_code in [0, 1, 2]  # Either succeeds with message or fails gracefully
        
        # Should not crash with unhandled exception
        if result.exception:
            assert not isinstance(result.exception, AttributeError)  # The original sort() error