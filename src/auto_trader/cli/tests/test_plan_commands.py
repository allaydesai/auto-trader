"""Tests for plan_commands module."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from decimal import Decimal

from click.testing import CliRunner

from auto_trader.cli.plan_commands import validate_plans, list_plans, create_plan, create_plan_interactive
from auto_trader.models import TradePlanStatus, RiskCategory


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

        with patch("auto_trader.cli.plan_commands.TradePlanLoader") as mock_loader_class, \
             patch("auto_trader.cli.plan_commands.display_plans_table") as mock_display, \
             patch("auto_trader.cli.plan_commands.display_stats_summary") as mock_stats:
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

        with patch("auto_trader.cli.plan_commands.TradePlanLoader") as mock_loader_class, \
             patch("auto_trader.cli.plan_commands.display_plans_table") as mock_display, \
             patch("auto_trader.cli.plan_commands.display_stats_summary") as mock_stats:
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
             patch("auto_trader.cli.plan_commands.display_plans_table") as mock_display, \
             patch("auto_trader.cli.plan_commands.display_stats_summary") as mock_stats:
            
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
            assert result.exit_code == 1  # Error handling calls sys.exit(1)
            assert "Error during creating plan" in result.output


class TestCreatePlanInteractive:
    """Test create-plan interactive wizard command."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()
    
    def create_mock_config_loader(self):
        """Create mock config loader."""
        mock_config = MagicMock()
        mock_config.user_preferences.account_value = Decimal("10000")
        return mock_config
    
    def create_mock_risk_manager(self):
        """Create mock risk manager."""
        mock_risk_manager = MagicMock()
        mock_risk_manager.account_value = Decimal("10000")
        
        # Mock portfolio summary
        mock_risk_manager.get_portfolio_summary.return_value = {
            "account_value": 10000.0,
            "current_portfolio_risk": 2.5,
            "available_risk_capacity_percent": 7.5,
            "position_count": 2,
        }
        
        # Mock position size calculation
        mock_position_result = MagicMock()
        mock_position_result.position_size = 100
        mock_position_result.dollar_risk = Decimal("250.00")
        mock_position_result.portfolio_risk_percentage = Decimal("2.5")
        mock_risk_manager.position_sizer.calculate_position_size.return_value = mock_position_result
        
        # Mock portfolio risk check
        mock_portfolio_check = MagicMock()
        mock_portfolio_check.passed = True
        mock_portfolio_check.current_risk = Decimal("2.5")
        mock_portfolio_check.new_trade_risk = Decimal("2.5")
        mock_portfolio_check.total_risk = Decimal("5.0")
        mock_portfolio_check.limit = Decimal("10.0")
        mock_risk_manager.check_portfolio_risk_limit.return_value = mock_portfolio_check
        
        return mock_risk_manager
    
    def test_create_plan_interactive_success(self):
        """Test successful interactive plan creation."""
        with patch("config.ConfigLoader") as mock_config_class, \
             patch("auto_trader.risk_management.RiskManager") as mock_risk_class, \
             patch("auto_trader.cli.wizard_utils.Prompt.ask") as mock_prompt, \
             patch("auto_trader.cli.wizard_preview.TradePlanPreview.show_preview") as mock_preview, \
             patch("auto_trader.cli.wizard_plan_utils.save_plan_to_yaml") as mock_save:
            
            # Setup mocks
            mock_config_class.return_value = self.create_mock_config_loader()
            mock_risk_class.return_value = self.create_mock_risk_manager()
            
            # Mock user inputs for complete wizard flow
            mock_prompt.side_effect = [
                "AAPL",  # symbol
                "180.50",  # entry
                "178.00",  # stop
                "normal",  # risk category  
                "185.00",  # take profit
                "close_above",  # entry function
                "15min",  # entry timeframe
                "stop_loss_take_profit",  # exit function
                "15min",  # exit timeframe
            ]
            
            mock_preview.return_value = True  # User confirms
            mock_save.return_value = Path("data/trade_plans/AAPL_20250817_001.yaml")
            
            result = self.runner.invoke(create_plan_interactive)
            
            assert result.exit_code == 0
            assert "TRADE PLAN CREATED SUCCESSFULLY" in result.output
            mock_save.assert_called_once()
    
    def test_create_plan_interactive_with_cli_shortcuts(self):
        """Test interactive plan creation with CLI shortcuts."""
        with patch("config.ConfigLoader") as mock_config_class, \
             patch("auto_trader.risk_management.RiskManager") as mock_risk_class, \
             patch("auto_trader.cli.wizard_utils.Prompt.ask") as mock_prompt, \
             patch("auto_trader.cli.wizard_preview.TradePlanPreview.show_preview") as mock_preview, \
             patch("auto_trader.cli.wizard_plan_utils.save_plan_to_yaml") as mock_save:
            
            # Setup mocks
            mock_config_class.return_value = self.create_mock_config_loader()
            mock_risk_class.return_value = self.create_mock_risk_manager()
            
            # Only need prompts for fields not provided via CLI
            mock_prompt.side_effect = [
                "185.00",  # take profit (not provided via CLI)
                "close_above",  # entry function
                "15min",  # entry timeframe
                "stop_loss_take_profit",  # exit function
                "15min",  # exit timeframe
            ]
            
            mock_preview.return_value = True
            mock_save.return_value = Path("data/trade_plans/MSFT_20250817_001.yaml")
            
            result = self.runner.invoke(create_plan_interactive, [
                "--symbol", "MSFT",
                "--entry", "150.25",
                "--stop", "148.00",
                "--risk", "normal"
            ])
            
            assert result.exit_code == 0
            assert "TRADE PLAN CREATED SUCCESSFULLY" in result.output
    
    def test_create_plan_interactive_user_cancellation(self):
        """Test user cancelling during preview."""
        with patch("config.ConfigLoader") as mock_config_class, \
             patch("auto_trader.risk_management.RiskManager") as mock_risk_class, \
             patch("auto_trader.cli.wizard_utils.Prompt.ask") as mock_prompt, \
             patch("auto_trader.cli.wizard_preview.TradePlanPreview.show_preview") as mock_preview:
            
            # Setup mocks
            mock_config_class.return_value = self.create_mock_config_loader()
            mock_risk_class.return_value = self.create_mock_risk_manager()
            
            mock_prompt.side_effect = [
                "AAPL", "180.50", "178.00", "normal", "185.00",
                "close_above", "15min", "stop_loss_take_profit", "15min"
            ]
            
            mock_preview.return_value = False  # User cancels
            
            result = self.runner.invoke(create_plan_interactive)
            
            assert result.exit_code == 0
            assert "Plan creation cancelled" in result.output
    
    def test_create_plan_interactive_portfolio_risk_exceeded(self):
        """Test wizard handling when portfolio risk limit is exceeded."""
        with patch("config.ConfigLoader") as mock_config_class, \
             patch("auto_trader.risk_management.RiskManager") as mock_risk_class, \
             patch("auto_trader.cli.wizard_utils.Prompt.ask") as mock_prompt, \
             patch("auto_trader.cli.wizard_utils.Confirm.ask") as mock_confirm:
            
            # Setup config loader
            mock_config_class.return_value = self.create_mock_config_loader()
            
            # Setup risk manager with risk limit exceeded
            mock_risk_manager = self.create_mock_risk_manager()
            
            # Mock portfolio check - FAIL
            mock_portfolio_check = MagicMock()
            mock_portfolio_check.passed = False
            mock_portfolio_check.current_risk = Decimal("5.0")
            mock_portfolio_check.new_trade_risk = Decimal("8.0")
            mock_portfolio_check.total_risk = Decimal("13.0")
            mock_portfolio_check.limit = Decimal("10.0")
            mock_risk_manager.check_portfolio_risk_limit.return_value = mock_portfolio_check
            
            mock_risk_class.return_value = mock_risk_manager
            
            mock_prompt.side_effect = [
                "AAPL", "180.50", "178.00", "large"  # Large risk category triggers limit
            ]
            
            mock_confirm.return_value = False  # User doesn't want to continue
            
            result = self.runner.invoke(create_plan_interactive)
            
            assert result.exit_code == 1  # Error handling calls sys.exit(1)
            assert "Error during interactive plan creation" in result.output
    
    def test_create_plan_interactive_keyboard_interrupt(self):
        """Test handling of keyboard interrupt during wizard."""
        with patch("config.ConfigLoader") as mock_config_class, \
             patch("auto_trader.risk_management.RiskManager") as mock_risk_class, \
             patch("auto_trader.cli.wizard_utils.WizardFieldCollector.collect_symbol", side_effect=KeyboardInterrupt):
            
            mock_config_class.return_value = self.create_mock_config_loader()
            mock_risk_class.return_value = self.create_mock_risk_manager()
            
            result = self.runner.invoke(create_plan_interactive)
            
            assert result.exit_code == 0
            assert "Wizard cancelled by user" in result.output
    
    def test_create_plan_interactive_exception_handling(self):
        """Test exception handling in interactive wizard."""
        with patch("config.ConfigLoader", side_effect=Exception("Config error")):
            result = self.runner.invoke(create_plan_interactive)
            
            assert result.exit_code == 1  # Error handling calls sys.exit(1)
            assert "Error during interactive plan creation" in result.output
    
    def test_create_plan_interactive_output_directory(self):
        """Test interactive plan creation with custom output directory."""
        with patch("config.ConfigLoader") as mock_config_class, \
             patch("auto_trader.risk_management.RiskManager") as mock_risk_class, \
             patch("auto_trader.cli.wizard_utils.Prompt.ask") as mock_prompt, \
             patch("auto_trader.cli.wizard_preview.TradePlanPreview.show_preview") as mock_preview, \
             patch("auto_trader.cli.wizard_plan_utils.save_plan_to_yaml") as mock_save:
            
            # Setup mocks
            mock_config_class.return_value = self.create_mock_config_loader()
            mock_risk_class.return_value = self.create_mock_risk_manager()
            
            mock_prompt.side_effect = [
                "AAPL", "180.50", "178.00", "normal", "185.00",
                "close_above", "15min", "stop_loss_take_profit", "15min"
            ]
            
            mock_preview.return_value = True
            mock_save.return_value = Path("custom/plans/AAPL_20250817_001.yaml")
            
            result = self.runner.invoke(create_plan_interactive, [
                "--output-dir", "custom/plans"
            ])
            
            assert result.exit_code == 0
            # Verify save_plan_to_yaml was called with custom output directory
            mock_save.assert_called_once()
            call_args = mock_save.call_args
            assert str(call_args[0][1]) == "custom/plans"  # output_dir parameter
    
    def test_create_plan_interactive_all_cli_shortcuts(self):
        """Test interactive wizard with all possible CLI shortcuts."""
        with patch("config.ConfigLoader") as mock_config_class, \
             patch("auto_trader.risk_management.RiskManager") as mock_risk_class, \
             patch("auto_trader.cli.wizard_utils.Prompt.ask") as mock_prompt, \
             patch("auto_trader.cli.wizard_preview.TradePlanPreview.show_preview") as mock_preview, \
             patch("auto_trader.cli.wizard_plan_utils.save_plan_to_yaml") as mock_save:
            
            # Setup mocks
            mock_config_class.return_value = self.create_mock_config_loader()
            mock_risk_class.return_value = self.create_mock_risk_manager()
            
            # Only need prompts for execution functions
            mock_prompt.side_effect = [
                "close_above",  # entry function
                "15min",  # entry timeframe
                "stop_loss_take_profit",  # exit function
                "15min",  # exit timeframe
            ]
            
            mock_preview.return_value = True
            mock_save.return_value = Path("data/trade_plans/TSLA_20250817_001.yaml")
            
            result = self.runner.invoke(create_plan_interactive, [
                "--symbol", "TSLA",
                "--entry", "250.00",
                "--stop", "245.00", 
                "--target", "260.00",
                "--risk", "small"
            ])
            
            assert result.exit_code == 0
            assert "TRADE PLAN CREATED SUCCESSFULLY" in result.output
    
    def test_create_plan_interactive_full_integration(self):
        """Integration test for complete CLI command execution including file creation."""
        import tempfile
        import yaml
        from pathlib import Path
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            with patch("config.ConfigLoader") as mock_config_class, \
                 patch("auto_trader.risk_management.RiskManager") as mock_risk_class, \
                 patch("auto_trader.cli.wizard_utils.Prompt.ask") as mock_prompt, \
                 patch("auto_trader.cli.wizard_preview.TradePlanPreview.show_preview") as mock_preview, \
                 patch("auto_trader.cli.wizard_plan_utils.datetime") as mock_datetime:
                
                # Setup mocks
                mock_config_class.return_value = self.create_mock_config_loader()
                mock_risk_class.return_value = self.create_mock_risk_manager()
                
                # Mock datetime to get predictable plan ID
                mock_datetime.utcnow.return_value = MagicMock()
                mock_datetime.utcnow.return_value.strftime.return_value = "20250817"
                
                # Mock user inputs
                mock_prompt.side_effect = [
                    "TSLA",  # symbol
                    "250.00",  # entry level
                    "245.00",  # stop loss
                    "normal",  # risk category (will be selected from choices)
                    "260.00",  # take profit
                    "close_above",  # entry function
                    "15min",  # entry timeframe
                    "stop_loss_take_profit",  # exit function
                    "15min",  # exit timeframe
                ]
                
                mock_preview.return_value = True  # User confirms
                
                # Execute command with output directory
                result = self.runner.invoke(create_plan_interactive, [
                    "--output-dir", str(temp_path)
                ])
                
                # Verify CLI execution succeeded
                assert result.exit_code == 0
                assert "TRADE PLAN CREATED SUCCESSFULLY" in result.output
                assert "TSLA" in result.output
                
                # Verify actual file was created
                expected_file = temp_path / "TSLA_20250817_001.yaml"
                assert expected_file.exists(), f"Expected file {expected_file} was not created"
                
                # Verify file contents by reading the raw text
                with open(expected_file, 'r') as f:
                    file_content = f.read()
                
                # Verify YAML structure and content by checking text content
                assert "plan_id: TSLA_20250817_001" in file_content
                assert "symbol: TSLA" in file_content
                assert "entry_level:" in file_content
                assert "stop_loss:" in file_content
                assert "take_profit:" in file_content
                assert "risk_category: normal" in file_content
                
                # Verify execution functions structure
                assert "entry_function:" in file_content
                assert "function_type: close_above" in file_content
                assert "timeframe: 15min" in file_content
                
                assert "exit_function:" in file_content
                assert "function_type: stop_loss_take_profit" in file_content
                
                # The file was successfully created by save_plan_to_yaml which validates via TradePlan
                # so we know the structure is correct and loadable
    
    def test_create_plan_interactive_duplicate_plan_id_handling(self):
        """Test handling of duplicate plan IDs during creation."""
        import tempfile
        from pathlib import Path
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create existing plan file to simulate duplicate
            existing_file = temp_path / "AAPL_20250817_001.yaml"
            existing_file.touch()
            
            with patch("config.ConfigLoader") as mock_config_class, \
                 patch("auto_trader.risk_management.RiskManager") as mock_risk_class, \
                 patch("auto_trader.cli.wizard_utils.Prompt.ask") as mock_prompt, \
                 patch("auto_trader.cli.wizard_preview.TradePlanPreview.show_preview") as mock_preview, \
                 patch("auto_trader.cli.wizard_plan_utils.datetime") as mock_datetime:
                
                # Setup mocks
                mock_config_class.return_value = self.create_mock_config_loader()
                mock_risk_class.return_value = self.create_mock_risk_manager()
                
                # Mock datetime to get predictable plan ID
                mock_datetime.utcnow.return_value = MagicMock()
                mock_datetime.utcnow.return_value.strftime.return_value = "20250817"
                
                # Mock user inputs
                mock_prompt.side_effect = [
                    "AAPL",  # symbol
                    "180.50",  # entry level
                    "178.00",  # stop loss
                    "normal",  # risk category
                    "185.00",  # take profit
                    "close_above",  # entry function
                    "15min",  # entry timeframe
                    "stop_loss_take_profit",  # exit function
                    "15min",  # exit timeframe
                ]
                
                mock_preview.return_value = True  # User confirms
                
                # Execute command - should automatically handle duplicate by using _002
                result = self.runner.invoke(create_plan_interactive, [
                    "--output-dir", str(temp_path)
                ])
                
                # Verify CLI execution succeeded
                assert result.exit_code == 0
                assert "TRADE PLAN CREATED SUCCESSFULLY" in result.output
                
                # Verify the new file was created with incremented ID
                expected_file = temp_path / "AAPL_20250817_002.yaml"
                assert expected_file.exists(), f"Expected file {expected_file} was not created"
                
                # Verify the plan ID in the output reflects the incremented value
                assert "AAPL_20250817_002" in result.output