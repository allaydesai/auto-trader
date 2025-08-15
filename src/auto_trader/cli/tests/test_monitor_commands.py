"""Tests for monitor_commands module."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from auto_trader.cli.monitor_commands import monitor, summary, history


class TestMonitor:
    """Test monitor command."""

    def test_monitor_default_settings(self):
        """Test monitor with default settings."""
        runner = CliRunner()

        with patch("auto_trader.cli.monitor_commands.TradePlanLoader") as mock_loader_class, \
             patch("auto_trader.cli.monitor_commands.Live") as mock_live, \
             patch("auto_trader.cli.monitor_commands.generate_monitor_layout") as mock_layout:

            mock_loader = MagicMock()
            mock_loader_class.return_value = mock_loader
            mock_layout.return_value = MagicMock()

            # Mock Live context manager to immediately exit
            mock_live_instance = MagicMock()
            mock_live_instance.__enter__ = MagicMock(return_value=mock_live_instance)
            mock_live_instance.__exit__ = MagicMock(return_value=True)
            mock_live.return_value = mock_live_instance

            # Simulate KeyboardInterrupt to exit the loop
            with patch("auto_trader.cli.monitor_commands.time.sleep", side_effect=KeyboardInterrupt):
                result = runner.invoke(monitor)

            assert result.exit_code == 0

    def test_monitor_custom_directory(self):
        """Test monitor with custom plans directory."""
        runner = CliRunner()

        with tempfile.TemporaryDirectory() as temp_dir:
            with patch("auto_trader.cli.monitor_commands.TradePlanLoader") as mock_loader_class, \
                 patch("auto_trader.cli.monitor_commands.Live") as mock_live, \
                 patch("auto_trader.cli.monitor_commands.generate_monitor_layout") as mock_layout:

                mock_loader = MagicMock()
                mock_loader_class.return_value = mock_loader
                mock_layout.return_value = MagicMock()

                # Mock Live context manager
                mock_live_instance = MagicMock()
                mock_live_instance.__enter__ = MagicMock(return_value=mock_live_instance)
                mock_live_instance.__exit__ = MagicMock(return_value=True)
                mock_live.return_value = mock_live_instance

                with patch("auto_trader.cli.monitor_commands.time.sleep", side_effect=KeyboardInterrupt):
                    result = runner.invoke(monitor, ["--plans-dir", temp_dir])

                assert result.exit_code == 0
                mock_loader_class.assert_called_with(Path(temp_dir))

    def test_monitor_custom_refresh_rate(self):
        """Test monitor with custom refresh rate."""
        runner = CliRunner()

        with patch("auto_trader.cli.monitor_commands.TradePlanLoader") as mock_loader_class, \
             patch("auto_trader.cli.monitor_commands.Live") as mock_live, \
             patch("auto_trader.cli.monitor_commands.generate_monitor_layout") as mock_layout:

            mock_loader = MagicMock()
            mock_loader_class.return_value = mock_loader
            mock_layout.return_value = MagicMock()

            # Mock Live context manager
            mock_live_instance = MagicMock()
            mock_live_instance.__enter__ = MagicMock(return_value=mock_live_instance)  
            mock_live_instance.__exit__ = MagicMock(return_value=True)
            mock_live.return_value = mock_live_instance

            with patch("auto_trader.cli.monitor_commands.time.sleep", side_effect=KeyboardInterrupt):
                result = runner.invoke(monitor, ["--refresh-rate", "10"])

            assert result.exit_code == 0

    def test_monitor_exception_handling(self):
        """Test exception handling in monitor."""
        runner = CliRunner()

        with patch("auto_trader.cli.monitor_commands.TradePlanLoader", side_effect=Exception("Test error")):
            result = runner.invoke(monitor)
            assert result.exit_code == 0  # Error handling prevents crash


class TestSummary:
    """Test summary command."""

    def test_summary_console_format(self):
        """Test summary in console format."""
        runner = CliRunner()

        with patch("auto_trader.cli.monitor_commands.display_performance_summary") as mock_display:
            result = runner.invoke(summary, ["--period", "week", "--format", "console"])

            assert result.exit_code == 0
            assert "week performance summary" in result.output
            mock_display.assert_called_once()

    def test_summary_csv_format(self):
        """Test summary in CSV format."""
        runner = CliRunner()

        with patch("auto_trader.cli.monitor_commands.export_performance_csv") as mock_export:
            result = runner.invoke(summary, ["--period", "month", "--format", "csv"])

            assert result.exit_code == 0
            assert "month performance summary" in result.output
            mock_export.assert_called_once()

    def test_summary_different_periods(self):
        """Test summary with different time periods."""
        runner = CliRunner()

        with patch("auto_trader.cli.monitor_commands.display_performance_summary") as mock_display:
            # Test day period
            result = runner.invoke(summary, ["--period", "day"])
            assert result.exit_code == 0
            assert "day performance summary" in result.output

            # Test week period
            result = runner.invoke(summary, ["--period", "week"])
            assert result.exit_code == 0
            assert "week performance summary" in result.output

            # Test month period
            result = runner.invoke(summary, ["--period", "month"])
            assert result.exit_code == 0
            assert "month performance summary" in result.output

    def test_summary_exception_handling(self):
        """Test exception handling in summary."""
        runner = CliRunner()

        with patch("auto_trader.cli.monitor_commands.display_performance_summary", side_effect=Exception("Test error")):
            result = runner.invoke(summary)
            assert result.exit_code == 0  # Error handling prevents crash


class TestHistory:
    """Test history command."""

    def test_history_console_format(self):
        """Test history in console format."""
        runner = CliRunner()

        with patch("auto_trader.cli.monitor_commands.display_trade_history") as mock_display:
            result = runner.invoke(history, ["--days", "30", "--format", "console"])

            assert result.exit_code == 0
            assert "last 30 days" in result.output
            mock_display.assert_called_once()

    def test_history_csv_format(self):
        """Test history in CSV format."""
        runner = CliRunner()

        with patch("auto_trader.cli.monitor_commands.export_trade_history_csv") as mock_export:
            result = runner.invoke(history, ["--days", "7", "--format", "csv"])

            assert result.exit_code == 0
            assert "last 7 days" in result.output
            mock_export.assert_called_once()

    def test_history_with_symbol_filter(self):
        """Test history with symbol filtering."""
        runner = CliRunner()

        with patch("auto_trader.cli.monitor_commands.display_trade_history") as mock_display:
            result = runner.invoke(history, ["--symbol", "AAPL", "--days", "14"])

            assert result.exit_code == 0
            assert "last 14 days" in result.output
            mock_display.assert_called_with("AAPL", 14)

    def test_history_default_settings(self):
        """Test history with default settings."""
        runner = CliRunner()

        with patch("auto_trader.cli.monitor_commands.display_trade_history") as mock_display:
            result = runner.invoke(history)

            assert result.exit_code == 0
            assert "last 30 days" in result.output  # Default days
            mock_display.assert_called_with(None, 30)

    def test_history_exception_handling(self):
        """Test exception handling in history."""
        runner = CliRunner()

        with patch("auto_trader.cli.monitor_commands.display_trade_history", side_effect=Exception("Test error")):
            result = runner.invoke(history)
            assert result.exit_code == 0  # Error handling prevents crash