"""Tests for trade plan management CLI commands."""

import tempfile
import yaml
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
from click.testing import CliRunner
from rich.console import Console

from ..management_commands import (
    list_plans_enhanced,
    validate_config,
    update_plan,
    archive_plans,
    plan_stats,
)
from ...models import TradePlan, TradePlanStatus, RiskCategory


@pytest.fixture
def cli_runner():
    """Provide Click CLI runner for testing."""
    return CliRunner()


@pytest.fixture
def temp_dir():
    """Provide temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_plan_data():
    """Provide sample plan data for testing."""
    return {
        "plan_id": "AAPL_20250822_001",
        "symbol": "AAPL",
        "entry_level": 180.50,
        "stop_loss": 178.00,
        "take_profit": 185.00,
        "risk_category": "normal",
        "status": "awaiting_entry",
        "entry_function": {
            "function_type": "close_above",
            "timeframe": "15min",
            "parameters": {"threshold": "180.50"}
        },
        "exit_function": {
            "function_type": "stop_loss_take_profit",
            "timeframe": "1min",
            "parameters": {}
        },
    }


@pytest.fixture
def mock_risk_manager():
    """Provide mock risk manager for testing."""
    mock_rm = Mock()
    
    # Mock validation result
    mock_validation = Mock()
    mock_validation.passed = True
    mock_validation.position_size_result = Mock()
    mock_validation.position_size_result.position_size = 100
    mock_validation.position_size_result.risk_amount_percent = Decimal("2.1")
    mock_validation.position_size_result.risk_amount_dollars = Decimal("250.00")
    
    mock_rm.validate_trade_plan.return_value = mock_validation
    mock_rm.portfolio_tracker.get_current_portfolio_risk.return_value = Decimal("5.2")
    
    return mock_rm


class TestListPlansEnhanced:
    """Test enhanced plan listing command."""
    
    @patch('auto_trader.cli.management_commands.RiskManager')
    @patch('auto_trader.cli.management_commands.TradePlanLoader')
    @patch('auto_trader.cli.management_commands.get_portfolio_risk_summary')
    @patch('auto_trader.cli.management_commands.create_plans_table')
    @patch('auto_trader.cli.management_commands.create_portfolio_summary_panel')
    def test_list_plans_enhanced_success(
        self,
        mock_panel,
        mock_table,
        mock_risk_summary,
        mock_loader_class,
        mock_rm_class,
        cli_runner,
        temp_dir,
        mock_risk_manager,
    ):
        """Test successful enhanced plan listing."""
        # Setup mocks
        mock_loader = Mock()
        mock_plan = Mock()
        mock_plan.plan_id = "AAPL_20250822_001"
        mock_plan.symbol = "AAPL"
        mock_loader.load_all_plans.return_value = {"AAPL_20250822_001": mock_plan}
        mock_loader_class.return_value = mock_loader
        
        mock_rm_class.return_value = mock_risk_manager
        mock_risk_summary.return_value = {"current_risk_percent": Decimal("5.2")}
        mock_panel.return_value = Mock()
        mock_table.return_value = Mock()
        
        # Run command
        result = cli_runner.invoke(list_plans_enhanced, ["--plans-dir", str(temp_dir)])
        
        # Verify success
        assert result.exit_code == 0
        mock_loader.load_all_plans.assert_called_once()
        mock_risk_summary.assert_called_once()
    
    @patch('auto_trader.cli.management_commands.TradePlanLoader')
    def test_list_plans_enhanced_no_plans(self, mock_loader_class, cli_runner, temp_dir, mock_risk_manager):
        """Test enhanced listing with no plans found."""
        mock_loader = Mock()
        mock_loader.load_all_plans.return_value = {}
        mock_loader_class.return_value = mock_loader
        
        result = cli_runner.invoke(list_plans_enhanced, ["--plans-dir", str(temp_dir)])
        
        assert result.exit_code == 0
        assert "No trade plans found" in result.output
    
    @patch('auto_trader.cli.management_commands.TradePlanLoader')
    def test_list_plans_enhanced_with_status_filter(
        self,
        mock_loader_class,
        cli_runner,
        temp_dir,
        mock_risk_manager,
    ):
        """Test enhanced listing with status filter."""
        mock_loader = Mock()
        mock_loader.get_plans_by_status.return_value = []
        mock_loader_class.return_value = mock_loader
        
        result = cli_runner.invoke(
            list_plans_enhanced,
            ["--plans-dir", str(temp_dir), "--status", "awaiting_entry"]
        )
        
        # Should call get_plans_by_status instead of load_all_plans
        mock_loader.get_plans_by_status.assert_called_once()
        mock_loader.load_all_plans.assert_not_called()
    
    @patch('auto_trader.cli.management_commands.TradePlanLoader')
    @patch('auto_trader.cli.management_commands.get_portfolio_risk_summary')
    @patch('auto_trader.cli.management_commands.create_plans_table')
    @patch('auto_trader.cli.management_commands.create_portfolio_summary_panel')
    def test_list_plans_enhanced_verbose_mode(
        self,
        mock_panel,
        mock_table,
        mock_risk_summary,
        mock_loader_class,
        cli_runner,
        temp_dir,
        mock_risk_manager,
    ):
        """Test enhanced listing in verbose mode."""
        mock_loader = Mock()
        mock_plan = Mock()
        mock_loader.load_all_plans.return_value = {"TEST_001": mock_plan}
        mock_loader_class.return_value = mock_loader
        
        mock_risk_summary.return_value = {"current_risk_percent": Decimal("5.2")}
        
        result = cli_runner.invoke(
            list_plans_enhanced,
            ["--plans-dir", str(temp_dir), "--verbose"]
        )
        
        # Verify verbose flag passed to table creation
        mock_table.assert_called_once()
        args, kwargs = mock_table.call_args
        assert kwargs.get('show_verbose') == True


class TestValidateConfig:
    """Test comprehensive validation command."""
    
    @patch('auto_trader.cli.management_commands.validate_plans_comprehensive')
    @patch('auto_trader.cli.management_commands.ValidationEngine')
    def test_validate_config_success(
        self,
        mock_validation_engine_class,
        mock_validate_comprehensive,
        cli_runner,
        temp_dir,
        mock_risk_manager,
    ):
        """Test successful configuration validation."""
        # Setup mock results
        mock_results = {
            "files_checked": 3,
            "syntax_passed": 3,
            "business_logic_passed": 3,
            "portfolio_risk_passed": True,
            "file_results": {},
            "portfolio_risk_percent": Decimal("6.5"),
        }
        mock_validate_comprehensive.return_value = mock_results
        
        result = cli_runner.invoke(validate_config, ["--plans-dir", str(temp_dir)])
        
        assert result.exit_code == 0
        assert "3 trade plan files" in result.output
        assert "3/3 passed" in result.output
        mock_validate_comprehensive.assert_called_once()
    
    @patch('auto_trader.cli.management_commands.validate_plans_comprehensive')
    @patch('auto_trader.cli.management_commands.ValidationEngine')
    def test_validate_config_with_errors(
        self,
        mock_validation_engine_class,
        mock_validate_comprehensive,
        cli_runner,
        temp_dir,
        mock_risk_manager,
    ):
        """Test validation with errors."""
        mock_results = {
            "files_checked": 2,
            "syntax_passed": 1,
            "business_logic_passed": 1,
            "portfolio_risk_passed": False,
            "file_results": {
                "bad_plan.yaml": {
                    "syntax_valid": False,
                    "business_logic_valid": False,
                    "errors": ["Invalid YAML syntax", "Missing required field"],
                }
            },
            "portfolio_risk_percent": Decimal("11.2"),
        }
        mock_validate_comprehensive.return_value = mock_results
        
        result = cli_runner.invoke(validate_config, ["--plans-dir", str(temp_dir)])
        
        assert result.exit_code == 0
        assert "FAILED" in result.output
        assert "11.2%" in result.output
    
    @patch('auto_trader.cli.management_commands.validate_plans_comprehensive')
    @patch('auto_trader.cli.management_commands.ValidationEngine')
    def test_validate_config_single_file(
        self,
        mock_validation_engine_class,
        mock_validate_comprehensive,
        cli_runner,
        temp_dir,
        mock_risk_manager,
    ):
        """Test validation of single file."""
        # Create test file
        test_file = temp_dir / "test_plan.yaml"
        test_file.write_text("test: content")
        
        mock_results = {
            "files_checked": 1,
            "syntax_passed": 1,
            "business_logic_passed": 1,
            "portfolio_risk_passed": True,
            "file_results": {},
        }
        mock_validate_comprehensive.return_value = mock_results
        
        result = cli_runner.invoke(
            validate_config,
            ["--plans-dir", str(temp_dir), "--file", str(test_file)]
        )
        
        assert result.exit_code == 0
        # Verify single file passed to validation
        mock_validate_comprehensive.assert_called_once()
        args, kwargs = mock_validate_comprehensive.call_args
        assert kwargs["single_file"] == test_file


class TestUpdatePlan:
    """Test plan update command."""
    
    def create_plan_file(self, temp_dir, sample_plan_data):
        """Helper to create a plan file."""
        plan_file = temp_dir / f"{sample_plan_data['plan_id']}.yaml"
        with open(plan_file, 'w') as f:
            yaml.dump(sample_plan_data, f)
        return plan_file
    
    @patch('auto_trader.cli.management_commands._get_risk_manager')
    @patch('auto_trader.cli.management_commands.TradePlanLoader')
    @patch('auto_trader.cli.management_commands.create_plan_backup')
    def test_update_plan_success(
        self,
        mock_backup,
        mock_loader_class,
        mock_get_risk_manager,
        cli_runner,
        temp_dir,
        sample_plan_data,
        mock_risk_manager,
    ):
        """Test successful plan update."""
        # Create plan file
        plan_file = self.create_plan_file(temp_dir, sample_plan_data)
        
        # Setup mocks
        mock_loader = Mock()
        mock_plan = Mock()
        mock_plan.plan_id = sample_plan_data["plan_id"]
        mock_plan.model_dump.return_value = sample_plan_data
        mock_loader.get_plan_by_id.return_value = mock_plan
        mock_loader_class.return_value = mock_loader
        
        mock_backup.return_value = temp_dir / "backup_file.yaml"
        mock_get_risk_manager.return_value = mock_risk_manager
        
        # Run command with force flag to skip confirmation
        result = cli_runner.invoke(
            update_plan,
            [
                sample_plan_data["plan_id"],
                "--entry-level", "181.00",
                "--plans-dir", str(temp_dir),
                "--force"
            ]
        )
        
        assert result.exit_code == 0
        assert "updated successfully" in result.output
        mock_backup.assert_called_once()
    
    @patch('auto_trader.cli.management_commands.TradePlanLoader')
    def test_update_plan_not_found(
        self,
        mock_loader_class,
        cli_runner,
        temp_dir,
        mock_risk_manager,
    ):
        """Test update of non-existent plan."""
        mock_loader = Mock()
        mock_loader.get_plan_by_id.return_value = None
        mock_loader_class.return_value = mock_loader
        
        result = cli_runner.invoke(
            update_plan,
            ["NONEXISTENT_001", "--entry-level", "100.00", "--plans-dir", str(temp_dir)]
        )
        
        assert result.exit_code == 0
        assert "not found" in result.output
    
    @patch('auto_trader.cli.management_commands.TradePlanLoader')
    def test_update_plan_no_fields(
        self,
        mock_loader_class,
        cli_runner,
        temp_dir,
        mock_risk_manager,
    ):
        """Test update with no fields specified."""
        result = cli_runner.invoke(
            update_plan,
            ["AAPL_20250822_001", "--plans-dir", str(temp_dir)]
        )
        
        assert result.exit_code == 0
        assert "No fields specified" in result.output


class TestArchivePlans:
    """Test plan archiving command."""
    
    @patch('auto_trader.cli.management_commands.TradePlanLoader')
    def test_archive_plans_dry_run(
        self,
        mock_loader_class,
        cli_runner,
        temp_dir,
    ):
        """Test plan archiving in dry run mode."""
        # Setup mock plans
        mock_loader = Mock()
        mock_plan = Mock()
        mock_plan.plan_id = "AAPL_20250822_001"
        mock_plan.status = TradePlanStatus.COMPLETED
        mock_loader.get_plans_by_status.return_value = [mock_plan]
        mock_loader_class.return_value = mock_loader
        
        result = cli_runner.invoke(
            archive_plans,
            ["--plans-dir", str(temp_dir), "--dry-run"]
        )
        
        assert result.exit_code == 0
        assert "dry run" in result.output
        assert "AAPL_20250822_001" in result.output
    
    @patch('auto_trader.cli.management_commands.TradePlanLoader')
    def test_archive_plans_no_plans(
        self,
        mock_loader_class,
        cli_runner,
        temp_dir,
    ):
        """Test archiving when no plans are archivable."""
        mock_loader = Mock()
        mock_loader.get_plans_by_status.return_value = []
        mock_loader_class.return_value = mock_loader
        
        result = cli_runner.invoke(
            archive_plans,
            ["--plans-dir", str(temp_dir)]
        )
        
        assert result.exit_code == 0
        assert "No plans found for archiving" in result.output
    
    @patch('auto_trader.cli.management_commands.TradePlanLoader')
    @patch('builtins.open')
    @patch('shutil.move')
    def test_archive_plans_success(
        self,
        mock_move,
        mock_open,
        mock_loader_class,
        cli_runner,
        temp_dir,
    ):
        """Test successful plan archiving."""
        # Setup mock plans
        mock_loader = Mock()
        mock_plan = Mock()
        mock_plan.plan_id = "AAPL_20250822_001"
        mock_plan.status = TradePlanStatus.COMPLETED
        mock_loader.get_plans_by_status.return_value = [mock_plan]
        mock_loader_class.return_value = mock_loader
        
        # Mock file operations
        mock_source_file = Mock()
        mock_source_file.exists.return_value = True
        
        with patch('pathlib.Path.exists', return_value=True):
            result = cli_runner.invoke(
                archive_plans,
                ["--plans-dir", str(temp_dir), "--force"]
            )
        
        assert result.exit_code == 0


class TestPlanStats:
    """Test plan statistics command."""
    
    @patch('auto_trader.cli.management_commands._get_risk_manager')
    @patch('auto_trader.cli.management_commands.TradePlanLoader')
    @patch('auto_trader.cli.management_commands.get_portfolio_risk_summary')
    def test_plan_stats_success(
        self,
        mock_risk_summary,
        mock_loader_class,
        mock_get_risk_manager,
        cli_runner,
        temp_dir,
        mock_risk_manager,
    ):
        """Test successful plan statistics generation."""
        # Setup mock plans
        mock_loader = Mock()
        mock_plan1 = Mock()
        mock_plan1.status = TradePlanStatus.AWAITING_ENTRY
        mock_plan1.symbol = "AAPL"
        mock_plan1.risk_category = RiskCategory.NORMAL
        
        mock_plan2 = Mock()
        mock_plan2.status = TradePlanStatus.COMPLETED
        mock_plan2.symbol = "MSFT"
        mock_plan2.risk_category = RiskCategory.SMALL
        
        mock_loader.load_all_plans.return_value = {"PLAN1": mock_plan1, "PLAN2": mock_plan2}
        mock_loader_class.return_value = mock_loader
        
        mock_risk_summary.return_value = {
            "current_risk_percent": Decimal("6.2"),
            "portfolio_limit_percent": Decimal("10.0"),
            "remaining_capacity_percent": Decimal("3.8"),
            "capacity_utilization_percent": Decimal("62.0"),
            "total_plan_risk_percent": Decimal("4.5"),
            "plan_risks": {},
            "exceeds_limit": False,
            "near_limit": False,
        }
        
        mock_get_risk_manager.return_value = mock_risk_manager
        
        result = cli_runner.invoke(plan_stats, ["--plans-dir", str(temp_dir)])
        
        assert result.exit_code == 0
        assert "PLAN STATISTICS" in result.output
        assert "Total Plans: 2" in result.output
        assert "Unique Symbols: 2" in result.output
    
    @patch('auto_trader.cli.management_commands.TradePlanLoader')
    def test_plan_stats_no_plans(
        self,
        mock_loader_class,
        cli_runner,
        temp_dir,
        mock_risk_manager,
    ):
        """Test statistics with no plans."""
        mock_loader = Mock()
        mock_loader.load_all_plans.return_value = {}
        mock_loader_class.return_value = mock_loader
        
        result = cli_runner.invoke(plan_stats, ["--plans-dir", str(temp_dir)])
        
        assert result.exit_code == 0
        assert "No trade plans found" in result.output


class TestErrorHandling:
    """Test error handling in management commands."""
    
    @patch('auto_trader.cli.management_commands.TradePlanLoader')
    def test_list_plans_enhanced_error_handling(
        self,
        mock_loader_class,
        cli_runner,
        temp_dir,
    ):
        """Test error handling in list plans enhanced."""
        mock_loader_class.side_effect = Exception("Loader error")
        
        result = cli_runner.invoke(list_plans_enhanced, ["--plans-dir", str(temp_dir)])
        
        assert result.exit_code == 1  # Should handle error gracefully and exit with error code
    
    @patch('auto_trader.cli.management_commands.ValidationEngine')
    def test_validate_config_error_handling(
        self,
        mock_validation_engine_class,
        cli_runner,
        temp_dir,
    ):
        """Test error handling in validate config."""
        mock_validation_engine_class.side_effect = Exception("Validation error")
        
        result = cli_runner.invoke(validate_config, ["--plans-dir", str(temp_dir)])
        
        assert result.exit_code == 1  # Should handle error gracefully and exit with error code


@pytest.mark.integration
class TestIntegrationScenarios:
    """Integration tests for management commands."""
    
    def test_end_to_end_plan_management_workflow(self, cli_runner, temp_dir, sample_plan_data):
        """Test complete plan management workflow."""
        # This would be a comprehensive integration test
        # covering creation, listing, validation, update, and archiving
        # Currently skipped due to complexity of mocking all dependencies
        pass