"""Tests for help_commands module."""

from click.testing import CliRunner

from auto_trader.cli.help_commands import help_system


class TestHelpSystem:
    """Test help-system command."""

    def test_help_system_display(self):
        """Test help system displays all sections."""
        runner = CliRunner()

        result = runner.invoke(help_system)

        assert result.exit_code == 0
        
        # Verify all main sections are present
        assert "Auto-Trader Help System" in result.output
        assert "Configuration Commands:" in result.output
        assert "Trade Plan Commands:" in result.output
        assert "Monitoring & Analysis:" in result.output
        assert "Configuration Files:" in result.output
        assert "Trade Plan Files:" in result.output
        assert "Example Usage:" in result.output

        # Verify specific commands are mentioned
        assert "validate-config" in result.output
        assert "setup" in result.output
        assert "validate-plans" in result.output
        assert "list-plans" in result.output
        assert "create-plan" in result.output
        assert "list-templates" in result.output
        assert "monitor" in result.output
        assert "summary" in result.output
        assert "history" in result.output

        # Verify file types are mentioned
        assert ".env" in result.output
        assert "config.yaml" in result.output
        assert "user_config.yaml" in result.output

        # Verify examples are included
        assert "auto-trader setup" in result.output
        assert "auto-trader validate-config --verbose" in result.output
        assert "auto-trader list-plans --status awaiting_entry" in result.output