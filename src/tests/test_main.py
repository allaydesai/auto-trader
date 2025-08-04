"""Tests for main application entry point."""

import asyncio
import signal
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from main import AutoTraderApp, main
from config import Settings


class TestAutoTraderApp:
    """Test AutoTraderApp class."""
    
    @pytest.fixture
    def mock_settings(self):
        """Provide mock settings for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            settings = Settings(
                discord_webhook_url="https://discord.com/api/webhooks/test",
                logs_dir=temp_path / "logs",
                config_file=temp_path / "config.yaml",
                user_config_file=temp_path / "user_config.yaml"
            )
            yield settings
    
    def test_app_initialization(self, mock_settings):
        """Test application initialization."""
        app = AutoTraderApp(mock_settings)
        
        assert app.settings == mock_settings
        assert app.config_loader is not None
        assert app.logger is not None
        assert app._running is False
        assert not app._shutdown_event.is_set()
    
    def test_app_initialization_default_settings(self):
        """Test application initialization with default settings."""
        with patch('main.Settings') as mock_settings_class:
            mock_settings = MagicMock()
            mock_settings_class.return_value = mock_settings
            
            app = AutoTraderApp()
            
            assert app.settings == mock_settings
            mock_settings_class.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initialize_success(self, mock_settings):
        """Test successful application initialization."""
        app = AutoTraderApp(mock_settings)
        
        with patch('main.LoggerConfig') as mock_log_config_class, \
             patch.object(app.config_loader, 'validate_configuration') as mock_validate, \
             patch.object(app.config_loader, 'load_system_config') as mock_system_config, \
             patch.object(app.config_loader, 'load_user_preferences') as mock_user_prefs:
            
            mock_log_config = MagicMock()
            mock_log_config_class.return_value = mock_log_config
            mock_validate.return_value = []  # No validation issues
            
            # Create mock objects with proper structure
            mock_system = MagicMock()
            mock_system.trading.simulation_mode = True
            mock_system.logging.level = "INFO"
            mock_system_config.return_value = mock_system
            
            mock_user = MagicMock()
            mock_user.default_risk_category = "conservative"
            mock_user_prefs.return_value = mock_user
            
            await app.initialize()
            
            mock_log_config.configure_logging.assert_called_once()
            mock_validate.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_initialize_validation_failure(self, mock_settings):
        """Test initialization with configuration validation failure."""
        app = AutoTraderApp(mock_settings)
        
        with patch('main.LoggerConfig'), \
             patch.object(app.config_loader, 'validate_configuration') as mock_validate:
            
            mock_validate.return_value = ["Configuration error"]
            
            with pytest.raises(ValueError, match="Configuration validation failed"):
                await app.initialize()
    
    @pytest.mark.asyncio
    async def test_initialize_exception_handling(self, mock_settings):
        """Test initialization exception handling."""
        app = AutoTraderApp(mock_settings)
        
        with patch('main.LoggerConfig') as mock_log_config_class:
            mock_log_config_class.side_effect = Exception("Logging setup failed")
            
            with pytest.raises(Exception, match="Logging setup failed"):
                await app.initialize()
    
    @pytest.mark.asyncio
    async def test_start_success(self, mock_settings):
        """Test successful application start."""
        app = AutoTraderApp(mock_settings)
        
        with patch.object(app, 'initialize') as mock_init, \
             patch.object(app, '_setup_signal_handlers') as mock_signal, \
             patch.object(app, '_run_main_loop') as mock_main_loop:
            
            mock_main_loop.return_value = None
            
            await app.start()
            
            mock_init.assert_called_once()
            mock_signal.assert_called_once()
            mock_main_loop.assert_called_once()
            assert app._running is True
    
    @pytest.mark.asyncio
    async def test_start_initialization_failure(self, mock_settings):
        """Test start with initialization failure."""
        app = AutoTraderApp(mock_settings)
        
        with patch.object(app, 'initialize') as mock_init:
            mock_init.side_effect = Exception("Init failed")
            
            with pytest.raises(Exception, match="Init failed"):
                await app.start()
    
    @pytest.mark.asyncio
    async def test_shutdown(self, mock_settings):
        """Test application shutdown."""
        app = AutoTraderApp(mock_settings)
        app._running = True
        
        await app.shutdown()
        
        assert app._running is False
        assert app._shutdown_event.is_set()
    
    @pytest.mark.asyncio
    async def test_shutdown_not_running(self, mock_settings):
        """Test shutdown when application is not running."""
        app = AutoTraderApp(mock_settings)
        
        # Should complete without error
        await app.shutdown()
        
        assert app._running is False
    
    @pytest.mark.asyncio
    async def test_run_main_loop_shutdown_signal(self, mock_settings):
        """Test main loop with shutdown signal."""
        app = AutoTraderApp(mock_settings)
        app._running = True
        
        # Simulate shutdown signal
        async def trigger_shutdown():
            await asyncio.sleep(0.1)
            app._shutdown_event.set()
        
        # Run both tasks concurrently
        await asyncio.gather(
            app._run_main_loop(),
            trigger_shutdown()
        )
        
        # Should exit cleanly
    
    @pytest.mark.asyncio
    async def test_run_main_loop_exception(self, mock_settings):
        """Test main loop exception handling."""
        app = AutoTraderApp(mock_settings)
        app._running = True
        
        with patch('asyncio.wait_for') as mock_wait:
            mock_wait.side_effect = Exception("Main loop error")
            
            with pytest.raises(Exception, match="Main loop error"):
                await app._run_main_loop()
    
    def test_setup_signal_handlers(self, mock_settings):
        """Test signal handlers setup."""
        app = AutoTraderApp(mock_settings)
        
        with patch('signal.signal') as mock_signal:
            app._setup_signal_handlers()
            
            # Should set up handlers for SIGINT and SIGTERM
            assert mock_signal.call_count == 2
            calls = mock_signal.call_args_list
            assert calls[0][0][0] == signal.SIGINT
            assert calls[1][0][0] == signal.SIGTERM


class TestMainFunction:
    """Test main entry point function."""
    
    @pytest.mark.asyncio
    async def test_main_success(self):
        """Test successful main execution."""
        with patch('main.Settings') as mock_settings_class, \
             patch('main.AutoTraderApp') as mock_app_class:
            
            mock_settings = MagicMock()
            mock_settings_class.return_value = mock_settings
            
            mock_app = AsyncMock()
            mock_app_class.return_value = mock_app
            
            result = await main()
            
            assert result == 0
            mock_app.start.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_main_keyboard_interrupt(self):
        """Test main with KeyboardInterrupt."""
        with patch('main.Settings'), \
             patch('main.AutoTraderApp') as mock_app_class:
            
            mock_app = AsyncMock()
            mock_app.start.side_effect = KeyboardInterrupt()
            mock_app._running = False  # Not running when KeyboardInterrupt occurs during start
            mock_app_class.return_value = mock_app
            
            result = await main()
            
            assert result == 0
            mock_app.shutdown.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_main_exception(self):
        """Test main with general exception."""
        with patch('main.Settings') as mock_settings_class:
            mock_settings_class.side_effect = Exception("Settings error")
            
            result = await main()
            
            assert result == 1
    
    @pytest.mark.asyncio
    async def test_main_with_running_app_cleanup(self):
        """Test main ensures app shutdown in finally block."""
        with patch('main.Settings'), \
             patch('main.AutoTraderApp') as mock_app_class:
            
            mock_app = AsyncMock()
            mock_app._running = True
            mock_app.start.side_effect = Exception("Start failed")
            mock_app_class.return_value = mock_app
            
            result = await main()
            
            assert result == 1
            mock_app.shutdown.assert_called_once()


class TestMainScriptExecution:
    """Test main script execution path."""
    
    def test_main_script_success(self):
        """Test successful script execution."""
        with patch('main.asyncio.run') as mock_run, \
             patch('main.sys.exit') as mock_exit:
            
            mock_run.return_value = 0
            
            # Import and execute main block
            with patch('main.__name__', '__main__'):
                exec("""
if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        sys.exit(1)
                """, {'__name__': '__main__', 'asyncio': asyncio, 'main': main, 'sys': __import__('sys')})
            
            mock_run.assert_called_once()
            mock_exit.assert_called_once_with(0)
    
    def test_main_script_exception(self):
        """Test script execution with exception."""
        with patch('main.asyncio.run') as mock_run, \
             patch('main.sys.exit') as mock_exit, \
             patch('builtins.print') as mock_print:
            
            mock_run.side_effect = Exception("Fatal error")
            
            # Import and execute main block
            with patch('main.__name__', '__main__'):
                exec("""
if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except Exception as e:
        print(f"FATAL: {e}", file=sys.stderr)
        sys.exit(1)
                """, {'__name__': '__main__', 'asyncio': asyncio, 'main': main, 'sys': __import__('sys')})
            
            mock_run.assert_called_once()
            mock_print.assert_called_once()
            mock_exit.assert_called_once_with(1)