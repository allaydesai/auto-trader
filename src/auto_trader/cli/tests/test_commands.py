"""Tests for CLI commands."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import yaml
from click.testing import CliRunner

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from auto_trader.cli.commands import cli, validate_config, setup, help_system


class TestValidateConfigCommand:
    """Test validate-config command."""
    
    def test_validate_config_success(self):
        """Test successful configuration validation."""
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create valid config files
            env_file = temp_path / ".env"
            env_file.write_text("DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/test")
            
            config_file = temp_path / "config.yaml"
            config_data = {"risk": {"min_account_balance": 1000}}
            with open(config_file, 'w') as f:
                yaml.dump(config_data, f)
            
            user_config_file = temp_path / "user_config.yaml"
            user_config_data = {"default_account_value": 10000}
            with open(user_config_file, 'w') as f:
                yaml.dump(user_config_data, f)
            
            # Mock settings to use temp files
            with patch('auto_trader.cli.commands.Settings') as mock_settings:
                mock_settings_instance = MagicMock()
                mock_settings_instance.config_file = config_file
                mock_settings_instance.user_config_file = user_config_file
                mock_settings_instance.discord_webhook_url = "https://discord.com/api/webhooks/test"
                mock_settings.return_value = mock_settings_instance
                
                with patch('auto_trader.cli.commands.ConfigLoader') as mock_loader_class:
                    mock_loader = MagicMock()
                    mock_loader.validate_configuration.return_value = []
                    mock_loader_class.return_value = mock_loader
                    
                    result = runner.invoke(validate_config)
                    
                    assert result.exit_code == 0
                    assert "Configuration validation passed" in result.output
    
    def test_validate_config_failure(self):
        """Test configuration validation failure."""
        runner = CliRunner()
        
        with patch('auto_trader.cli.commands.Settings') as mock_settings:
            mock_settings_instance = MagicMock()
            mock_settings.return_value = mock_settings_instance
            
            with patch('auto_trader.cli.commands.ConfigLoader') as mock_loader_class:
                mock_loader = MagicMock()
                mock_loader.validate_configuration.return_value = [
                    "Discord webhook URL is required",
                    "Invalid risk configuration"
                ]
                mock_loader_class.return_value = mock_loader
                
                result = runner.invoke(validate_config)
                
                assert result.exit_code == 1
                assert "Configuration validation failed" in result.output
                assert "Discord webhook URL is required" in result.output
                assert "Invalid risk configuration" in result.output
    
    def test_validate_config_with_custom_files(self):
        """Test validation with custom config file paths."""
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            custom_config = temp_path / "custom_config.yaml"
            custom_user_config = temp_path / "custom_user_config.yaml"
            
            # Create empty files
            custom_config.touch()
            custom_user_config.touch()
            
            with patch('auto_trader.cli.commands.Settings') as mock_settings:
                mock_settings_instance = MagicMock()
                mock_settings.return_value = mock_settings_instance
                
                with patch('auto_trader.cli.commands.ConfigLoader') as mock_loader_class:
                    mock_loader = MagicMock()
                    mock_loader.validate_configuration.return_value = []
                    mock_loader_class.return_value = mock_loader
                    
                    result = runner.invoke(validate_config, [
                        '--config-file', str(custom_config),
                        '--user-config-file', str(custom_user_config)
                    ])
                    
                    assert result.exit_code == 0
                    # Verify custom paths were used
                    assert mock_settings_instance.config_file == custom_config
                    assert mock_settings_instance.user_config_file == custom_user_config
    
    def test_validate_config_verbose(self):
        """Test validation with verbose output."""
        runner = CliRunner()
        
        with patch('auto_trader.cli.commands.Settings'), \
             patch('auto_trader.cli.commands.ConfigLoader') as mock_loader_class, \
             patch('auto_trader.cli.commands._display_config_summary') as mock_display:
            
            mock_loader = MagicMock()
            mock_loader.validate_configuration.return_value = []
            mock_loader_class.return_value = mock_loader
            
            result = runner.invoke(validate_config, ['--verbose'])
            
            assert result.exit_code == 0
            mock_display.assert_called_once_with(mock_loader)
    
    def test_validate_config_exception_handling(self):
        """Test validation command exception handling."""
        runner = CliRunner()
        
        with patch('auto_trader.cli.commands.Settings') as mock_settings:
            mock_settings.side_effect = Exception("Configuration error")
            
            result = runner.invoke(validate_config)
            
            assert result.exit_code == 1
            assert "Error during validation" in result.output


class TestSetupCommand:
    """Test setup command."""
    
    def test_setup_success(self):
        """Test successful setup wizard."""
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Mock the interactive prompts
            with patch('auto_trader.cli.commands.click.prompt') as mock_prompt, \
                 patch('auto_trader.cli.commands.click.confirm') as mock_confirm:
                
                mock_prompt.side_effect = [
                    "https://discord.com/api/webhooks/test",  # webhook_url
                    "127.0.0.1",  # ibkr_host
                    7497,  # ibkr_port
                    1,  # ibkr_client_id
                    10000,  # account_value
                    "conservative"  # risk_category
                ]
                mock_confirm.side_effect = [True, False]  # simulation_mode, debug
                
                result = runner.invoke(setup, ['--output-dir', str(temp_path)])
                
                assert result.exit_code == 0
                assert "Setup completed successfully" in result.output
                
                # Check that files were created
                assert (temp_path / ".env").exists()
                assert (temp_path / "config.yaml").exists()
                assert (temp_path / "user_config.yaml").exists()
    
    def test_setup_existing_files_no_force(self):
        """Test setup with existing files without force flag."""
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create existing files
            (temp_path / ".env").touch()
            (temp_path / "config.yaml").touch()
            
            result = runner.invoke(setup, ['--output-dir', str(temp_path)])
            
            assert result.exit_code == 0
            assert "files already exist" in result.output
            assert "Use --force to overwrite" in result.output
    
    def test_setup_existing_files_with_force(self):
        """Test setup with existing files and force flag."""
        runner = CliRunner()
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create existing files
            (temp_path / ".env").write_text("OLD_CONTENT=true")
            (temp_path / "config.yaml").write_text("old: config")
            
            with patch('auto_trader.cli.commands.click.prompt') as mock_prompt, \
                 patch('auto_trader.cli.commands.click.confirm') as mock_confirm:
                
                mock_prompt.side_effect = [
                    "https://discord.com/api/webhooks/test",
                    "127.0.0.1", 7497, 1, 10000, "conservative"
                ]
                mock_confirm.side_effect = [True, False]
                
                result = runner.invoke(setup, [
                    '--output-dir', str(temp_path), 
                    '--force'
                ])
                
                assert result.exit_code == 0
                assert "Setup completed successfully" in result.output
                
                # Files should be overwritten
                env_content = (temp_path / ".env").read_text()
                assert "DISCORD_WEBHOOK_URL" in env_content
                assert "OLD_CONTENT" not in env_content
    
    def test_setup_exception_handling(self):
        """Test setup command exception handling."""
        runner = CliRunner()
        
        # Use invalid directory to trigger exception
        result = runner.invoke(setup, ['--output-dir', '/invalid/directory/path'])
        
        assert result.exit_code == 1
        assert "Setup failed" in result.output


class TestHelpSystemCommand:
    """Test help-system command."""
    
    def test_help_system(self):
        """Test help system command."""
        runner = CliRunner()
        
        result = runner.invoke(help_system)
        
        assert result.exit_code == 0
        assert "Auto-Trader Help System" in result.output
        assert "Available Commands" in result.output
        assert "validate-config" in result.output
        assert "setup" in result.output
        assert "help-system" in result.output
        assert "Configuration Files" in result.output
        assert "Example Usage" in result.output


class TestCLIGroup:
    """Test main CLI group."""
    
    def test_cli_version(self):
        """Test CLI version option."""
        runner = CliRunner()
        
        result = runner.invoke(cli, ['--version'])
        
        assert result.exit_code == 0
        assert "0.1.0" in result.output
    
    def test_cli_help(self):
        """Test CLI help."""
        runner = CliRunner()
        
        result = runner.invoke(cli, ['--help'])
        
        assert result.exit_code == 0
        assert "Auto-Trader" in result.output
        assert "validate-config" in result.output
        assert "setup" in result.output
        assert "help-system" in result.output


class TestHelperFunctions:
    """Test CLI helper functions."""
    
    def test_create_env_file(self):
        """Test _create_env_file function."""
        from auto_trader.cli.commands import _create_env_file
        
        with tempfile.TemporaryDirectory() as temp_dir:
            env_path = Path(temp_dir) / ".env"
            
            with patch('auto_trader.cli.commands.click.prompt') as mock_prompt, \
                 patch('auto_trader.cli.commands.click.confirm') as mock_confirm:
                
                mock_prompt.side_effect = [
                    "https://discord.com/api/webhooks/test",
                    "192.168.1.100", 7496, 2
                ]
                mock_confirm.side_effect = [False, True]  # simulation_mode, debug
                
                _create_env_file(env_path)
                
                content = env_path.read_text()
                assert "IBKR_HOST=192.168.1.100" in content
                assert "IBKR_PORT=7496" in content
                assert "IBKR_CLIENT_ID=2" in content
                assert "DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/test" in content
                assert "SIMULATION_MODE=false" in content
                assert "DEBUG=true" in content
    
    def test_create_config_file(self):
        """Test _create_config_file function."""
        from auto_trader.cli.commands import _create_config_file
        
        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "config.yaml"
            
            _create_config_file(config_path)
            
            content = config_path.read_text()
            assert "ibkr:" in content
            assert "risk:" in content
            assert "trading:" in content
            assert "logging:" in content
            
            # Verify it's valid YAML
            config_data = yaml.safe_load(content)
            assert "ibkr" in config_data
            assert "risk" in config_data
    
    def test_create_user_config_file(self):
        """Test _create_user_config_file function."""
        from auto_trader.cli.commands import _create_user_config_file
        
        with tempfile.TemporaryDirectory() as temp_dir:
            user_config_path = Path(temp_dir) / "user_config.yaml"
            
            with patch('auto_trader.cli.commands.click.prompt') as mock_prompt:
                mock_prompt.side_effect = [25000, "aggressive"]
                
                _create_user_config_file(user_config_path)
                
                content = user_config_path.read_text()
                assert "default_account_value: 25000" in content
                assert 'default_risk_category: "aggressive"' in content
                
                # Verify it's valid YAML
                config_data = yaml.safe_load(content)
                assert config_data["default_account_value"] == 25000
                assert config_data["default_risk_category"] == "aggressive"