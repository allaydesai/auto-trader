"""Tests for plan_commands module."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from decimal import Decimal

from click.testing import CliRunner

from auto_trader.cli.plan_commands import validate_plans, list_plans, create_plan
from auto_trader.models import TradePlanStatus


class TestValidatePlans:
    """Test validate-plans command."""

    def test_validate_plans_success(self):
        """Test successful plan validation."""
        runner = CliRunner()

        with patch("auto_trader.cli.plan_commands.TradePlanLoader") as mock_loader_class:
            mock_loader = MagicMock()
            mock_loader.plans_directory = Path("data/trade_plans")
            mock_loader.load_all_plans.return_value = {"plan1": MagicMock()}
            mock_loader.get_validation_report.return_value = "All plans valid"
            mock_loader_class.return_value = mock_loader

            result = runner.invoke(validate_plans)

            assert result.exit_code == 0
            assert "Successfully loaded 1 trade plan" in result.output

    def test_validate_plans_with_custom_directory(self):
        """Test validation with custom plans directory."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("auto_trader.cli.plan_commands.TradePlanLoader") as mock_loader_class:
                mock_loader = MagicMock()
                mock_loader.plans_directory = Path(temp_dir)
                mock_loader.load_all_plans.return_value = {}
                mock_loader_class.return_value = mock_loader

                result = runner.invoke(validate_plans, ["--plans-dir", temp_dir])

                assert result.exit_code == 0
                mock_loader_class.assert_called_with(Path(temp_dir))

    def test_validate_plans_verbose(self):
        """Test verbose plan validation."""
        runner = CliRunner()

        with patch("auto_trader.cli.plan_commands.TradePlanLoader") as mock_loader_class, \
             patch("auto_trader.cli.plan_commands.display_plans_summary") as mock_display:
            
            mock_loader = MagicMock()
            mock_loader.plans_directory = Path("data/trade_plans")
            mock_loader.load_all_plans.return_value = {"plan1": MagicMock()}
            mock_loader.get_validation_report.return_value = "All plans valid"
            mock_loader_class.return_value = mock_loader

            result = runner.invoke(validate_plans, ["--verbose"])

            assert result.exit_code == 0
            mock_display.assert_called_once()

    def test_validate_plans_with_watch(self):
        """Test plan validation with file watching."""
        runner = CliRunner()

        with patch("auto_trader.cli.plan_commands.TradePlanLoader") as mock_loader_class, \
             patch("auto_trader.cli.plan_commands.start_file_watching") as mock_watch:
            
            mock_loader = MagicMock()
            mock_loader.plans_directory = Path("data/trade_plans")
            mock_loader.load_all_plans.return_value = {"plan1": MagicMock()}
            mock_loader.get_validation_report.return_value = "All plans valid"
            mock_loader_class.return_value = mock_loader

            result = runner.invoke(validate_plans, ["--watch"])

            assert result.exit_code == 0
            mock_watch.assert_called_once()

    def test_validate_plans_failure(self):
        """Test plan validation with no plans found."""
        runner = CliRunner()

        with patch("auto_trader.cli.plan_commands.TradePlanLoader") as mock_loader_class:
            mock_loader = MagicMock()
            mock_loader.plans_directory = Path("data/trade_plans")
            mock_loader.load_all_plans.return_value = {}
            mock_loader_class.return_value = mock_loader

            result = runner.invoke(validate_plans)

            assert result.exit_code == 0  # Command completes but handles failure


class TestListPlans:
    """Test list-plans command."""

    def create_mock_plan(self, plan_id="TEST_001", symbol="AAPL", status="awaiting_entry", risk_category="normal"):
        """Create a mock trade plan."""
        plan = MagicMock()
        plan.plan_id = plan_id
        plan.symbol = symbol
        plan.status = TradePlanStatus(status)
        plan.risk_category = risk_category
        plan.created_at = "2024-01-01T10:00:00"
        return plan

    def test_list_plans_success(self):
        """Test successful plan listing."""
        runner = CliRunner()

        with patch("auto_trader.cli.plan_commands.TradePlanLoader") as mock_loader_class, \
             patch("auto_trader.cli.plan_commands.display_plans_table") as mock_display, \
             patch("auto_trader.cli.plan_commands.display_stats_summary") as mock_stats:
            
            mock_plan = self.create_mock_plan()
            mock_loader = MagicMock()
            mock_loader.load_all_plans.return_value = {"plan1": mock_plan}
            mock_loader.get_stats.return_value = {}
            mock_loader_class.return_value = mock_loader

            result = runner.invoke(list_plans)

            assert result.exit_code == 0
            assert "1 plan(s) found" in result.output
            mock_display.assert_called_once()
            mock_stats.assert_called_once()

    def test_list_plans_with_filters(self):
        """Test plan listing with filters."""
        runner = CliRunner()

        with patch("auto_trader.cli.plan_commands.TradePlanLoader") as mock_loader_class:
            mock_plan1 = self.create_mock_plan("PLAN1", "AAPL", "awaiting_entry", "normal")
            mock_plan2 = self.create_mock_plan("PLAN2", "MSFT", "position_open", "small")
            
            mock_loader = MagicMock()
            mock_loader.load_all_plans.return_value = {"plan1": mock_plan1, "plan2": mock_plan2}
            mock_loader.get_stats.return_value = {}
            mock_loader_class.return_value = mock_loader

            result = runner.invoke(list_plans, [
                "--status", "awaiting_entry",
                "--symbol", "AAPL",
                "--risk-category", "normal"
            ])

            assert result.exit_code == 0

    def test_list_plans_sorting(self):
        """Test plan listing with sorting options."""
        runner = CliRunner()

        with patch("auto_trader.cli.plan_commands.TradePlanLoader") as mock_loader_class:
            mock_plan = self.create_mock_plan()
            mock_loader = MagicMock()
            mock_loader.load_all_plans.return_value = {"plan1": mock_plan}
            mock_loader.get_stats.return_value = {}
            mock_loader_class.return_value = mock_loader

            result = runner.invoke(list_plans, [
                "--sort-by", "symbol",
                "--sort-desc",
                "--limit", "10"
            ])

            assert result.exit_code == 0

    def test_list_plans_verbosity_levels(self):
        """Test different verbosity levels."""
        runner = CliRunner()

        with patch("auto_trader.cli.plan_commands.TradePlanLoader") as mock_loader_class, \
             patch("auto_trader.cli.plan_commands.display_plans_table") as mock_display:
            
            mock_plan = self.create_mock_plan()
            mock_loader = MagicMock()
            mock_loader.load_all_plans.return_value = {"plan1": mock_plan}
            mock_loader.get_stats.return_value = {}
            mock_loader_class.return_value = mock_loader

            # Test quiet mode
            result = runner.invoke(list_plans, ["--quiet"])
            assert result.exit_code == 0

            # Test verbose mode
            result = runner.invoke(list_plans, ["--verbose"])
            assert result.exit_code == 0

            # Test debug mode
            result = runner.invoke(list_plans, ["--debug"])
            assert result.exit_code == 0

    def test_list_plans_no_plans(self):
        """Test listing when no plans exist."""
        runner = CliRunner()

        with patch("auto_trader.cli.plan_commands.TradePlanLoader") as mock_loader_class:
            mock_loader = MagicMock()
            mock_loader.load_all_plans.return_value = {}
            mock_loader_class.return_value = mock_loader

            result = runner.invoke(list_plans)

            assert result.exit_code == 0
            assert "No trade plans found" in result.output

    def test_list_plans_invalid_status(self):
        """Test listing with invalid status filter."""
        runner = CliRunner()

        with patch("auto_trader.cli.plan_commands.TradePlanLoader") as mock_loader_class:
            mock_plan = self.create_mock_plan()
            mock_loader = MagicMock()
            mock_loader.load_all_plans.return_value = {"plan1": mock_plan}
            mock_loader_class.return_value = mock_loader

            result = runner.invoke(list_plans, ["--status", "invalid_status"])

            assert result.exit_code == 0
            assert "Invalid status" in result.output

    def test_list_plans_with_risk_info(self):
        """Test plan listing with risk information."""
        runner = CliRunner()

        with patch("auto_trader.cli.plan_commands.TradePlanLoader") as mock_loader_class, \
             patch("auto_trader.cli.plan_commands.display_plans_table") as mock_display, \
             patch("auto_trader.cli.plan_commands.display_stats_summary") as mock_stats:
            
            mock_plan = self.create_mock_plan()
            mock_loader = MagicMock()
            mock_loader.load_all_plans.return_value = {"plan1": mock_plan}
            mock_loader.get_stats.return_value = {}
            mock_loader_class.return_value = mock_loader

            result = runner.invoke(list_plans, ["--show-risk"])

            assert result.exit_code == 0
            # Verify that display_plans_table was called with show_risk_info=True
            mock_display.assert_called_once()
            call_args = mock_display.call_args
            assert call_args[1]["show_risk_info"] is True


class TestCreatePlan:
    """Test create-plan command."""

    def test_create_plan_success(self):
        """Test successful plan creation."""
        runner = CliRunner()

        with patch("auto_trader.cli.plan_commands.TemplateManager") as mock_template_class, \
             patch("auto_trader.cli.plan_commands.show_available_templates") as mock_show_templates, \
             patch("auto_trader.cli.plan_commands.get_template_choice") as mock_get_choice, \
             patch("auto_trader.cli.plan_commands.get_plan_data_interactive") as mock_get_data, \
             patch("auto_trader.cli.plan_commands.create_plan_output_file") as mock_create_output, \
             patch("auto_trader.cli.plan_commands.show_plan_creation_success") as mock_show_success:

            # Setup mocks
            mock_template_manager = MagicMock()
            mock_template_class.return_value = mock_template_manager
            
            mock_show_templates.return_value = {"template_names": ["close_above"]}
            mock_get_choice.return_value = "close_above"
            mock_get_data.return_value = {
                "plan_id": "TEST_001",
                "symbol": "AAPL",
                "entry_level": Decimal("150.00")
            }
            mock_create_output.return_value = Path("test_plan.yaml")
            
            mock_trade_plan = MagicMock()
            mock_trade_plan.plan_id = "TEST_001"
            mock_template_manager.create_plan_from_template.return_value = mock_trade_plan

            result = runner.invoke(create_plan)

            assert result.exit_code == 0
            mock_template_manager.create_plan_from_template.assert_called_once()
            mock_show_success.assert_called_once()

    def test_create_plan_no_templates(self):
        """Test plan creation when no templates are available."""
        runner = CliRunner()

        with patch("auto_trader.cli.plan_commands.TemplateManager") as mock_template_class, \
             patch("auto_trader.cli.plan_commands.show_available_templates") as mock_show_templates:

            mock_template_class.return_value = MagicMock()
            mock_show_templates.return_value = {}  # No templates

            result = runner.invoke(create_plan)

            assert result.exit_code == 0
            # Should exit early when no templates available

    def test_create_plan_exception_handling(self):
        """Test exception handling in create_plan."""
        runner = CliRunner()

        with patch("auto_trader.cli.plan_commands.TemplateManager", side_effect=Exception("Test error")):
            result = runner.invoke(create_plan)
            assert result.exit_code == 0  # Error handling prevents crash