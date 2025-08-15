"""Tests for config_commands module."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import yaml
from click.testing import CliRunner

from auto_trader.cli.config_commands import validate_config, setup


class TestValidateConfig:
    """Test validate-config command."""

    def test_validate_config_success(self):
        """Test successful configuration validation."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Create valid config files
            config_file = temp_path / "config.yaml"
            config_data = {"risk": {"min_account_balance": 1000}}
            with open(config_file, "w") as f:
                yaml.dump(config_data, f)

            user_config_file = temp_path / "user_config.yaml"
            user_config_data = {"default_account_value": 10000}
            with open(user_config_file, "w") as f:
                yaml.dump(user_config_data, f)

            # Mock dependencies
            with patch("auto_trader.cli.config_commands.Settings") as mock_settings, \
                 patch("auto_trader.cli.config_commands.ConfigLoader") as mock_loader_class:
                
                mock_settings_instance = MagicMock()
                mock_settings.return_value = mock_settings_instance
                
                mock_loader = MagicMock()
                mock_loader.validate_configuration.return_value = []
                mock_loader.system_config.trading.simulation_mode = True
                mock_loader_class.return_value = mock_loader

                result = runner.invoke(validate_config, [
                    "--config-file", str(config_file),
                    "--user-config-file", str(user_config_file)
                ])

                assert result.exit_code == 0
                assert "Configuration validation passed" in result.output

    def test_validate_config_failure(self):
        """Test configuration validation with errors."""
        runner = CliRunner()

        with patch("auto_trader.cli.config_commands.Settings") as mock_settings, \
             patch("auto_trader.cli.config_commands.ConfigLoader") as mock_loader_class:
            
            mock_settings_instance = MagicMock()
            mock_settings.return_value = mock_settings_instance
            
            mock_loader = MagicMock()
            mock_loader.validate_configuration.return_value = ["Test error"]
            mock_loader_class.return_value = mock_loader

            result = runner.invoke(validate_config)

            assert result.exit_code == 0  # Command runs but validation fails
            # The actual error display is handled by error_utils

    def test_validate_config_verbose(self):
        """Test verbose configuration validation."""
        runner = CliRunner()

        with patch("auto_trader.cli.config_commands.Settings") as mock_settings, \
             patch("auto_trader.cli.config_commands.ConfigLoader") as mock_loader_class, \
             patch("auto_trader.cli.config_commands.display_config_summary") as mock_display:
            
            mock_settings_instance = MagicMock()
            mock_settings.return_value = mock_settings_instance
            
            mock_loader = MagicMock()
            mock_loader.validate_configuration.return_value = []
            mock_loader.system_config.trading.simulation_mode = True
            mock_loader_class.return_value = mock_loader

            result = runner.invoke(validate_config, ["--verbose"])

            assert result.exit_code == 0
            mock_display.assert_called_once()

    def test_validate_config_exception_handling(self):
        """Test exception handling in validate_config."""
        runner = CliRunner()

        with patch("auto_trader.cli.config_commands.Settings", side_effect=Exception("Test error")):
            result = runner.invoke(validate_config)
            assert result.exit_code == 0  # Error handling prevents crash


class TestSetup:
    """Test setup command."""

    def test_setup_success(self):
        """Test successful setup wizard."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            with patch("auto_trader.cli.config_commands.check_existing_files", return_value=True), \
                 patch("auto_trader.cli.config_commands.create_env_file") as mock_env, \
                 patch("auto_trader.cli.config_commands.create_config_file") as mock_config, \
                 patch("auto_trader.cli.config_commands.create_user_config_file") as mock_user:

                result = runner.invoke(setup, ["--output-dir", str(temp_path), "--force"])

                assert result.exit_code == 0
                assert "Setup completed successfully" in result.output
                mock_env.assert_called_once()
                mock_config.assert_called_once()
                mock_user.assert_called_once()

    def test_setup_existing_files_no_force(self):
        """Test setup with existing files and no force flag."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            with patch("auto_trader.cli.config_commands.check_existing_files", return_value=False):
                result = runner.invoke(setup, ["--output-dir", str(temp_path)])

                assert result.exit_code == 0
                # Command should exit early when check_existing_files returns False

    def test_setup_file_creation_error(self):
        """Test setup with file creation errors."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            with patch("auto_trader.cli.config_commands.check_existing_files", return_value=True), \
                 patch("auto_trader.cli.config_commands.create_env_file", side_effect=OSError("Permission denied")):

                result = runner.invoke(setup, ["--output-dir", str(temp_path), "--force"])

                assert result.exit_code == 0
                # Error handling should prevent crash

    def test_setup_exception_handling(self):
        """Test exception handling in setup."""
        runner = CliRunner()

        with patch("auto_trader.cli.config_commands.check_existing_files", side_effect=Exception("Test error")):
            result = runner.invoke(setup)
            assert result.exit_code == 0  # Error handling prevents crash