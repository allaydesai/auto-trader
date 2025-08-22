"""Tests for diagnostic_commands module."""

from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from auto_trader.cli.diagnostic_commands import doctor


class TestDoctor:
    """Test doctor command."""

    def test_doctor_all_checks(self):
        """Test doctor command with all checks enabled."""
        runner = CliRunner()

        with patch("auto_trader.cli.diagnostic_commands.check_configuration") as mock_config, \
             patch("auto_trader.cli.diagnostic_commands.check_trade_plans") as mock_plans, \
             patch("auto_trader.cli.diagnostic_commands.check_permissions") as mock_perms, \
             patch("auto_trader.cli.diagnostic_commands.display_diagnostic_summary") as mock_summary:

            # Mock diagnostic results
            mock_config.return_value = [{"check": "config", "status": "pass"}]
            mock_plans.return_value = [{"check": "plans", "status": "pass"}]
            mock_perms.return_value = [{"check": "permissions", "status": "pass"}]

            result = runner.invoke(doctor)

            assert result.exit_code == 0
            assert "Health Check" in result.output
            assert "Checking configuration" in result.output
            assert "Checking trade plans" in result.output
            assert "Checking permissions" in result.output

            mock_config.assert_called_once()
            mock_plans.assert_called_once()
            mock_perms.assert_called_once()
            mock_summary.assert_called_once()

    def test_doctor_config_only(self):
        """Test doctor command with only config checks."""
        runner = CliRunner()

        with patch("auto_trader.cli.diagnostic_commands.check_configuration") as mock_config, \
             patch("auto_trader.cli.diagnostic_commands.check_trade_plans") as mock_plans, \
             patch("auto_trader.cli.diagnostic_commands.check_permissions") as mock_perms, \
             patch("auto_trader.cli.diagnostic_commands.display_diagnostic_summary") as mock_summary:

            mock_config.return_value = [{"check": "config", "status": "pass"}]

            result = runner.invoke(doctor, ["--config"])

            assert result.exit_code == 0
            assert "Checking configuration" in result.output

            mock_config.assert_called_once()
            mock_plans.assert_not_called()
            mock_perms.assert_not_called()
            mock_summary.assert_called_once()

    def test_doctor_plans_only(self):
        """Test doctor command with only plans checks."""
        runner = CliRunner()

        with patch("auto_trader.cli.diagnostic_commands.check_configuration") as mock_config, \
             patch("auto_trader.cli.diagnostic_commands.check_trade_plans") as mock_plans, \
             patch("auto_trader.cli.diagnostic_commands.check_permissions") as mock_perms, \
             patch("auto_trader.cli.diagnostic_commands.display_diagnostic_summary") as mock_summary:

            mock_plans.return_value = [{"check": "plans", "status": "pass"}]

            result = runner.invoke(doctor, ["--plans"])

            assert result.exit_code == 0
            assert "Checking trade plans" in result.output

            mock_config.assert_not_called()
            mock_plans.assert_called_once()
            mock_perms.assert_not_called()
            mock_summary.assert_called_once()

    def test_doctor_permissions_only(self):
        """Test doctor command with only permissions checks."""
        runner = CliRunner()

        with patch("auto_trader.cli.diagnostic_commands.check_configuration") as mock_config, \
             patch("auto_trader.cli.diagnostic_commands.check_trade_plans") as mock_plans, \
             patch("auto_trader.cli.diagnostic_commands.check_permissions") as mock_perms, \
             patch("auto_trader.cli.diagnostic_commands.display_diagnostic_summary") as mock_summary:

            mock_perms.return_value = [{"check": "permissions", "status": "pass"}]

            result = runner.invoke(doctor, ["--permissions"])

            assert result.exit_code == 0
            assert "Checking permissions" in result.output

            mock_config.assert_not_called()
            mock_plans.assert_not_called()
            mock_perms.assert_called_once()
            mock_summary.assert_called_once()

    def test_doctor_with_export_debug(self):
        """Test doctor command with debug export."""
        runner = CliRunner()

        with patch("auto_trader.cli.diagnostic_commands.check_configuration") as mock_config, \
             patch("auto_trader.cli.diagnostic_commands.check_trade_plans") as mock_plans, \
             patch("auto_trader.cli.diagnostic_commands.check_permissions") as mock_perms, \
             patch("auto_trader.cli.diagnostic_commands.display_diagnostic_summary") as mock_summary, \
             patch("auto_trader.cli.diagnostic_commands.export_debug_information") as mock_export:

            mock_config.return_value = [{"check": "config", "status": "pass"}]
            mock_plans.return_value = [{"check": "plans", "status": "pass"}]
            mock_perms.return_value = [{"check": "permissions", "status": "pass"}]

            result = runner.invoke(doctor, ["--export-debug"])

            assert result.exit_code == 0
            mock_export.assert_called_once()

    def test_doctor_mixed_flags(self):
        """Test doctor command with mixed check flags."""
        runner = CliRunner()

        with patch("auto_trader.cli.diagnostic_commands.check_configuration") as mock_config, \
             patch("auto_trader.cli.diagnostic_commands.check_trade_plans") as mock_plans, \
             patch("auto_trader.cli.diagnostic_commands.check_permissions") as mock_perms, \
             patch("auto_trader.cli.diagnostic_commands.display_diagnostic_summary") as mock_summary:

            mock_config.return_value = [{"check": "config", "status": "pass"}]
            mock_plans.return_value = [{"check": "plans", "status": "pass"}]

            result = runner.invoke(doctor, ["--config", "--plans"])

            assert result.exit_code == 0
            assert "Checking configuration" in result.output
            assert "Checking trade plans" in result.output

            mock_config.assert_called_once()
            mock_plans.assert_called_once()
            mock_perms.assert_not_called()
            mock_summary.assert_called_once()

    def test_doctor_exception_handling(self):
        """Test exception handling in doctor command."""
        runner = CliRunner()

        with patch("auto_trader.cli.diagnostic_commands.check_configuration", side_effect=Exception("Test error")):
            result = runner.invoke(doctor)
            assert result.exit_code == 1  # Error handler calls sys.exit(1)
            assert "Error during diagnostic checks" in result.output