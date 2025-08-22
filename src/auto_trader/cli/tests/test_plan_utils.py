"""Tests for plan_utils module."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from auto_trader.cli.plan_utils import (
    show_available_templates,
    get_template_choice,
    create_plan_output_file,
    show_plan_creation_success,
)


class TestShowAvailableTemplates:
    """Test show_available_templates function."""

    def test_show_available_templates_success(self):
        """Test showing available templates successfully."""
        # Create mock template manager
        mock_template_manager = MagicMock()
        mock_templates = {
            "close_above": {"name": "close_above", "type": "entry"},
            "close_below": {"name": "close_below", "type": "entry"}
        }
        mock_template_manager.list_available_templates.return_value = mock_templates
        mock_template_manager.get_template_documentation.side_effect = [
            {"description": "Enter position when price closes above threshold"},
            {"description": "Enter position when price closes below threshold"}
        ]

        with patch("auto_trader.cli.plan_utils.console") as mock_console:
            result = show_available_templates(mock_template_manager)

            # Verify return value
            assert result["templates"] == mock_templates
            assert result["template_names"] == ["close_above", "close_below"]

            # Verify console calls
            assert mock_console.print.call_count >= 3  # Welcome panel + template list
            
            # Check that template documentation was fetched
            mock_template_manager.get_template_documentation.assert_any_call("close_above")
            mock_template_manager.get_template_documentation.assert_any_call("close_below")

    def test_show_available_templates_no_templates(self):
        """Test when no templates are available."""
        mock_template_manager = MagicMock()
        mock_template_manager.list_available_templates.return_value = {}

        with patch("auto_trader.cli.plan_utils.console") as mock_console:
            result = show_available_templates(mock_template_manager)

            # Should return empty dict
            assert result == {}

            # Should show error message
            mock_console.print.assert_called_once()
            # Verify error panel was shown (just check that print was called with a Panel)
            call_args = mock_console.print.call_args[0][0]
            assert hasattr(call_args, 'renderable')  # Rich Panel has this attribute

    def test_show_available_templates_with_missing_description(self):
        """Test templates with missing descriptions."""
        mock_template_manager = MagicMock()
        mock_templates = {"test_template": {"name": "test_template"}}
        mock_template_manager.list_available_templates.return_value = mock_templates
        mock_template_manager.get_template_documentation.return_value = {}  # No description

        with patch("auto_trader.cli.plan_utils.console") as mock_console:
            result = show_available_templates(mock_template_manager)

            assert result["templates"] == mock_templates
            assert result["template_names"] == ["test_template"]

            # Should handle missing description gracefully
            mock_console.print.assert_called()


class TestGetTemplateChoice:
    """Test get_template_choice function."""

    def test_get_template_choice_valid_selection(self):
        """Test valid template selection."""
        template_names = ["close_above", "close_below", "trailing_stop"]

        with patch("auto_trader.cli.plan_utils.Prompt.ask") as mock_prompt, \
             patch("auto_trader.cli.plan_utils.console") as mock_console:
            
            mock_prompt.return_value = "2"  # Select second template

            result = get_template_choice(template_names)

            assert result == "close_below"
            mock_prompt.assert_called_once_with(
                "\nSelect template",
                choices=["1", "2", "3"]
            )
            mock_console.print.assert_called_once()

    def test_get_template_choice_first_template(self):
        """Test selecting first template."""
        template_names = ["close_above"]

        with patch("auto_trader.cli.plan_utils.Prompt.ask") as mock_prompt, \
             patch("auto_trader.cli.plan_utils.console") as mock_console:
            
            mock_prompt.return_value = "1"

            result = get_template_choice(template_names)

            assert result == "close_above"
            mock_prompt.assert_called_once_with(
                "\nSelect template",
                choices=["1"]
            )

    def test_get_template_choice_last_template(self):
        """Test selecting last template."""
        template_names = ["template1", "template2", "template3"]

        with patch("auto_trader.cli.plan_utils.Prompt.ask") as mock_prompt, \
             patch("auto_trader.cli.plan_utils.console") as mock_console:
            
            mock_prompt.return_value = "3"

            result = get_template_choice(template_names)

            assert result == "template3"


class TestCreatePlanOutputFile:
    """Test create_plan_output_file function."""

    def test_create_plan_output_file_default_directory(self):
        """Test creating output file with default directory."""
        plan_data = {"plan_id": "AAPL_20240101_001"}

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("auto_trader.cli.plan_utils.Path") as mock_path_class:
                # Mock the default path creation
                default_path = Path(temp_dir) / "data" / "trade_plans"
                mock_path_class.return_value = default_path

                result = create_plan_output_file(plan_data, None)

                # Should create the directory structure
                expected_file = default_path / "AAPL_20240101_001.yaml"
                assert str(result).endswith("AAPL_20240101_001.yaml")

    def test_create_plan_output_file_custom_directory(self):
        """Test creating output file with custom directory."""
        plan_data = {"plan_id": "MSFT_20240101_001"}

        with tempfile.TemporaryDirectory() as temp_dir:
            custom_dir = Path(temp_dir) / "custom_plans"
            
            result = create_plan_output_file(plan_data, custom_dir)

            # Should use custom directory
            expected_file = custom_dir / "MSFT_20240101_001.yaml"
            assert result == expected_file
            
            # Directory should be created
            assert custom_dir.exists()

    def test_create_plan_output_file_existing_directory(self):
        """Test creating output file when directory already exists."""
        plan_data = {"plan_id": "GOOGL_20240101_001"}

        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "existing_plans"
            output_dir.mkdir(parents=True, exist_ok=True)
            
            result = create_plan_output_file(plan_data, output_dir)

            expected_file = output_dir / "GOOGL_20240101_001.yaml"
            assert result == expected_file


class TestShowPlanCreationSuccess:
    """Test show_plan_creation_success function."""

    def test_show_plan_creation_success(self):
        """Test showing plan creation success message."""
        # Create mock trade plan
        mock_trade_plan = MagicMock()
        mock_trade_plan.plan_id = "AAPL_20240101_001"
        mock_trade_plan.symbol = "AAPL"
        mock_trade_plan.entry_level = 150.50
        mock_trade_plan.risk_category = "normal"

        output_file = Path("/tmp/AAPL_20240101_001.yaml")

        with patch("auto_trader.cli.plan_utils.console") as mock_console:
            show_plan_creation_success(mock_trade_plan, output_file)

            # Should call console.print once with a Panel
            mock_console.print.assert_called_once()
            
            # Verify the content includes plan details (check that a Panel was printed)
            call_args = mock_console.print.call_args[0][0]
            assert hasattr(call_args, 'renderable')  # Rich Panel has this attribute
            # The actual content verification would require Rich rendering,
            # but we can verify the function was called with proper parameters

    def test_show_plan_creation_success_different_values(self):
        """Test success message with different plan values."""
        mock_trade_plan = MagicMock()
        mock_trade_plan.plan_id = "TSLA_20240101_002"
        mock_trade_plan.symbol = "TSLA"
        mock_trade_plan.entry_level = 250.75
        mock_trade_plan.risk_category = "large"

        output_file = Path("/custom/path/TSLA_20240101_002.yaml")

        with patch("auto_trader.cli.plan_utils.console") as mock_console:
            show_plan_creation_success(mock_trade_plan, output_file)

            mock_console.print.assert_called_once()
            call_args = mock_console.print.call_args[0][0]
            assert hasattr(call_args, 'renderable')  # Rich Panel has this attribute