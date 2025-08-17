"""Tests for template_commands module."""

from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from auto_trader.cli.template_commands import list_templates


class TestListTemplates:
    """Test list-templates command."""

    def test_list_templates_success(self):
        """Test successful template listing."""
        runner = CliRunner()

        with patch("auto_trader.cli.template_commands.TemplateManager") as mock_template_class:
            mock_template_manager = MagicMock()
            mock_template_class.return_value = mock_template_manager
            
            # Mock template data
            mock_template_manager.list_available_templates.return_value = ["close_above", "close_below"]
            mock_template_manager.get_template_documentation.return_value = {
                "description": "Test template description",
                "required_fields": ["field1", "field2"],
                "use_cases": ["case1", "case2"]
            }

            result = runner.invoke(list_templates)

            assert result.exit_code == 0
            assert "Found 2 template(s)" in result.output
            assert "close_above" in result.output
            assert "close_below" in result.output

    def test_list_templates_verbose(self):
        """Test verbose template listing."""
        runner = CliRunner()

        with patch("auto_trader.cli.template_commands.TemplateManager") as mock_template_class:
            mock_template_manager = MagicMock()
            mock_template_class.return_value = mock_template_manager
            
            # Mock template data
            mock_template_manager.list_available_templates.return_value = ["close_above"]
            mock_template_manager.get_template_documentation.return_value = {
                "description": "Test template description",
                "required_fields": ["field1", "field2"],
                "use_cases": ["case1", "case2"]
            }
            mock_template_manager.get_template_summary.return_value = {
                "validation_results": {"close_above": True}
            }

            result = runner.invoke(list_templates, ["--verbose"])

            assert result.exit_code == 0
            assert "Template Validation Results" in result.output
            assert "✓ close_above" in result.output

    def test_list_templates_no_templates(self):
        """Test listing when no templates exist."""
        runner = CliRunner()

        with patch("auto_trader.cli.template_commands.TemplateManager") as mock_template_class:
            mock_template_manager = MagicMock()
            mock_template_class.return_value = mock_template_manager
            mock_template_manager.list_available_templates.return_value = []

            result = runner.invoke(list_templates)

            assert result.exit_code == 0
            assert "No templates found" in result.output

    def test_list_templates_exception_handling(self):
        """Test exception handling in list_templates."""
        runner = CliRunner()

        with patch("auto_trader.cli.template_commands.TemplateManager", side_effect=Exception("Test error")):
            result = runner.invoke(list_templates)
            assert result.exit_code == 1  # Error handling calls sys.exit(1)
            assert "Error during listing templates" in result.output