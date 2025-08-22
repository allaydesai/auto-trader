"""Tests for schema_commands module."""

from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from auto_trader.cli.schema_commands import show_schema


class TestShowSchema:
    """Test show-schema command."""

    def test_show_schema_console_format(self):
        """Test schema display in console format."""
        runner = CliRunner()

        mock_schema = {
            "properties": {
                "plan_id": {
                    "type": "string",
                    "description": "Unique plan identifier"
                },
                "symbol": {
                    "type": "string", 
                    "description": "Trading symbol"
                }
            },
            "required": ["plan_id", "symbol"]
        }

        with patch("auto_trader.models.trade_plan.TradePlan") as mock_trade_plan, \
             patch("auto_trader.cli.schema_commands.display_schema_console") as mock_display:
            
            mock_trade_plan.model_json_schema.return_value = mock_schema

            result = runner.invoke(show_schema, ["--format", "console"])

            assert result.exit_code == 0
            mock_display.assert_called_once_with(mock_schema)

    def test_show_schema_json_format(self):
        """Test schema display in JSON format."""
        runner = CliRunner()

        mock_schema = {
            "properties": {
                "plan_id": {"type": "string", "description": "Test"}
            }
        }

        with patch("auto_trader.models.trade_plan.TradePlan") as mock_trade_plan:
            mock_trade_plan.model_json_schema.return_value = mock_schema

            result = runner.invoke(show_schema, ["--format", "json"])

            assert result.exit_code == 0
            assert '"plan_id"' in result.output

    def test_show_schema_yaml_format(self):
        """Test schema display in YAML format."""
        runner = CliRunner()

        mock_schema = {
            "properties": {
                "plan_id": {"type": "string", "description": "Test"}
            }
        }

        with patch("auto_trader.models.trade_plan.TradePlan") as mock_trade_plan:
            mock_trade_plan.model_json_schema.return_value = mock_schema

            result = runner.invoke(show_schema, ["--format", "yaml"])

            assert result.exit_code == 0
            assert "plan_id:" in result.output

    def test_show_schema_specific_field(self):
        """Test showing documentation for a specific field."""
        runner = CliRunner()

        mock_schema = {
            "properties": {
                "plan_id": {
                    "type": "string",
                    "description": "Unique plan identifier"
                }
            },
            "required": ["plan_id"]
        }

        with patch("auto_trader.models.trade_plan.TradePlan") as mock_trade_plan:
            mock_trade_plan.model_json_schema.return_value = mock_schema

            result = runner.invoke(show_schema, ["--field", "plan_id"])

            assert result.exit_code == 0
            assert "Field: plan_id" in result.output
            assert "Type: string" in result.output
            assert "Unique plan identifier" in result.output
            assert "Required: Yes" in result.output

    def test_show_schema_invalid_field(self):
        """Test showing documentation for a non-existent field."""
        runner = CliRunner()

        mock_schema = {
            "properties": {
                "plan_id": {"type": "string"}
            }
        }

        with patch("auto_trader.models.trade_plan.TradePlan") as mock_trade_plan:
            mock_trade_plan.model_json_schema.return_value = mock_schema

            result = runner.invoke(show_schema, ["--field", "nonexistent"])

            assert result.exit_code == 0
            assert "Field 'nonexistent' not found" in result.output

    def test_show_schema_exception_handling(self):
        """Test exception handling in show_schema."""
        runner = CliRunner()

        with patch("auto_trader.models.trade_plan.TradePlan", side_effect=Exception("Test error")):
            result = runner.invoke(show_schema)
            assert result.exit_code == 0  # Error handling prevents crash