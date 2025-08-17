"""Integration tests for file_utils interactive functions."""

import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from decimal import Decimal

import pytest

from auto_trader.cli.file_utils import (
    get_plan_data_interactive,
    export_performance_csv,
    export_trade_history_csv,
)


class TestGetPlanDataInteractive:
    """Test get_plan_data_interactive function."""

    @patch("datetime.datetime")
    @patch("auto_trader.cli.file_utils.click.prompt")
    @patch("auto_trader.cli.file_utils.Prompt.ask")
    @patch("auto_trader.cli.file_utils.console")
    def test_get_plan_data_interactive_default_values(
        self, mock_console, mock_prompt_ask, mock_click_prompt, mock_datetime
    ):
        """Test interactive plan data collection with default values."""
        # Mock datetime
        mock_datetime.now.return_value.strftime.return_value = "20240101"

        # Mock user inputs
        mock_prompt_ask.side_effect = [
            "AAPL",  # symbol
            "AAPL_20240101_001",  # plan_id (default)
            "normal",  # risk_category (default)
        ]
        
        mock_click_prompt.side_effect = [
            "150.50",  # entry_level
            "148.00",  # stop_loss
            "155.00",  # take_profit
            "150.50",  # threshold (default)
        ]

        result = get_plan_data_interactive()

        # Verify return data
        assert result["plan_id"] == "AAPL_20240101_001"
        assert result["symbol"] == "AAPL"
        assert result["entry_level"] == Decimal("150.50")
        assert result["stop_loss"] == Decimal("148.00")
        assert result["take_profit"] == Decimal("155.00")
        assert result["risk_category"] == "normal"
        assert result["threshold"] == Decimal("150.50")

        # Verify console was used to show prompts
        mock_console.print.assert_called()

    @patch("datetime.datetime")
    @patch("auto_trader.cli.file_utils.click.prompt")
    @patch("auto_trader.cli.file_utils.Prompt.ask")
    @patch("auto_trader.cli.file_utils.console")
    def test_get_plan_data_interactive_custom_values(
        self, mock_console, mock_prompt_ask, mock_click_prompt, mock_datetime
    ):
        """Test interactive plan data collection with custom values."""
        # Mock datetime
        mock_datetime.now.return_value.strftime.return_value = "20240201"

        # Mock user inputs with custom values
        mock_prompt_ask.side_effect = [
            "TSLA",  # symbol
            "TSLA_CUSTOM_001",  # custom plan_id
            "large",  # large risk category
        ]
        
        mock_click_prompt.side_effect = [
            "250.75",  # entry_level
            "240.00",  # stop_loss
            "270.00",  # take_profit
            "252.00",  # custom threshold
        ]

        result = get_plan_data_interactive()

        # Verify custom values
        assert result["plan_id"] == "TSLA_CUSTOM_001"
        assert result["symbol"] == "TSLA"
        assert result["entry_level"] == Decimal("250.75")
        assert result["stop_loss"] == Decimal("240.00")
        assert result["take_profit"] == Decimal("270.00")
        assert result["risk_category"] == "large"
        assert result["threshold"] == Decimal("252.00")

    @patch("datetime.datetime")
    @patch("auto_trader.cli.file_utils.click.prompt")
    @patch("auto_trader.cli.file_utils.Prompt.ask")
    @patch("auto_trader.cli.file_utils.console")
    def test_get_plan_data_interactive_symbol_uppercase(
        self, mock_console, mock_prompt_ask, mock_click_prompt, mock_datetime
    ):
        """Test that symbol is converted to uppercase."""
        mock_datetime.now.return_value.strftime.return_value = "20240101"

        mock_prompt_ask.side_effect = [
            "msft",  # lowercase symbol
            "MSFT_20240101_001",
            "small",
        ]
        
        mock_click_prompt.side_effect = ["100.00", "95.00", "110.00", "100.50"]

        result = get_plan_data_interactive()

        # Symbol should be uppercase
        assert result["symbol"] == "MSFT"

    @patch("datetime.datetime")
    @patch("auto_trader.cli.file_utils.click.prompt")
    @patch("auto_trader.cli.file_utils.Prompt.ask")
    @patch("auto_trader.cli.file_utils.console")
    def test_get_plan_data_interactive_decimal_precision(
        self, mock_console, mock_prompt_ask, mock_click_prompt, mock_datetime
    ):
        """Test decimal precision handling."""
        mock_datetime.now.return_value.strftime.return_value = "20240101"

        mock_prompt_ask.side_effect = ["GOOGL", "GOOGL_20240101_001", "normal"]
        
        # Test various decimal formats
        mock_click_prompt.side_effect = [
            "2500.1234",  # 4 decimal places
            "2490.50",    # 2 decimal places
            "2550.0",     # 1 decimal place
            "2501.123",   # 3 decimal places
        ]

        result = get_plan_data_interactive()

        # Verify decimal precision is maintained
        assert result["entry_level"] == Decimal("2500.1234")
        assert result["stop_loss"] == Decimal("2490.50")
        assert result["take_profit"] == Decimal("2550.0")
        assert result["threshold"] == Decimal("2501.123")

    @patch("datetime.datetime")
    @patch("auto_trader.cli.file_utils.click.prompt")
    @patch("auto_trader.cli.file_utils.Prompt.ask")
    @patch("auto_trader.cli.file_utils.console")
    def test_get_plan_data_interactive_all_risk_categories(
        self, mock_console, mock_prompt_ask, mock_click_prompt, mock_datetime
    ):
        """Test all valid risk categories."""
        mock_datetime.now.return_value.strftime.return_value = "20240101"

        for risk_category in ["small", "normal", "large"]:
            mock_prompt_ask.side_effect = [
                "TEST",
                f"TEST_{risk_category}_001",
                risk_category,
            ]
            
            mock_click_prompt.side_effect = ["100.00", "95.00", "105.00", "100.00"]

            result = get_plan_data_interactive()
            assert result["risk_category"] == risk_category

    @patch("datetime.datetime")
    @patch("auto_trader.cli.file_utils.click.prompt")
    @patch("auto_trader.cli.file_utils.Prompt.ask")
    @patch("auto_trader.cli.file_utils.console")
    def test_get_plan_data_interactive_plan_id_generation(
        self, mock_console, mock_prompt_ask, mock_click_prompt, mock_datetime
    ):
        """Test plan ID suggestion generation."""
        mock_datetime.now.return_value.strftime.return_value = "20241225"

        mock_prompt_ask.side_effect = [
            "AMZN",
            "AMZN_20241225_001",  # Should get suggested plan ID
            "normal",
        ]
        
        mock_click_prompt.side_effect = ["3000.00", "2950.00", "3100.00", "3000.00"]

        result = get_plan_data_interactive()

        # Verify suggested plan ID format was used
        assert result["plan_id"] == "AMZN_20241225_001"
        
        # Verify Prompt.ask was called with the suggested default
        plan_id_call = mock_prompt_ask.call_args_list[1]
        assert plan_id_call[0] == ("Plan ID",)
        assert plan_id_call[1]["default"] == "AMZN_20241225_001"


class TestExportFunctions:
    """Test export utility functions."""

    @patch("auto_trader.cli.file_utils.console")
    def test_export_performance_csv_daily(self, mock_console):
        """Test exporting daily performance CSV."""
        export_performance_csv("daily", "20240101")

        # Should print success message
        mock_console.print.assert_any_call(
            "[green]✓ Performance summary exported to performance_summary_daily_20240101.csv[/green]"
        )
        
        # Should print placeholder note
        mock_console.print.assert_any_call(
            "[yellow]Note: This is a placeholder. Real implementation would create actual CSV file.[/yellow]"
        )

    @patch("auto_trader.cli.file_utils.console")
    def test_export_performance_csv_weekly(self, mock_console):
        """Test exporting weekly performance CSV."""
        export_performance_csv("weekly", "20240107")

        mock_console.print.assert_any_call(
            "[green]✓ Performance summary exported to performance_summary_weekly_20240107.csv[/green]"
        )

    @patch("auto_trader.cli.file_utils.console")
    def test_export_performance_csv_monthly(self, mock_console):
        """Test exporting monthly performance CSV."""
        export_performance_csv("monthly", "20240131")

        mock_console.print.assert_any_call(
            "[green]✓ Performance summary exported to performance_summary_monthly_20240131.csv[/green]"
        )

    @patch("auto_trader.cli.file_utils.console")
    def test_export_trade_history_csv_no_symbol(self, mock_console):
        """Test exporting trade history without symbol filter."""
        export_trade_history_csv(None, 30)

        # Should export all trades for 30 days
        mock_console.print.assert_any_call(
            "[green]✓ Trade history exported to trade_history_30days.csv[/green]"
        )
        
        mock_console.print.assert_any_call(
            "[yellow]Note: This is a placeholder. Real implementation would create actual CSV file.[/yellow]"
        )

    @patch("auto_trader.cli.file_utils.console")
    def test_export_trade_history_csv_with_symbol(self, mock_console):
        """Test exporting trade history with symbol filter."""
        export_trade_history_csv("AAPL", 7)

        # Should export AAPL trades for 7 days
        mock_console.print.assert_any_call(
            "[green]✓ Trade history exported to trade_history_7days_AAPL.csv[/green]"
        )

    @patch("auto_trader.cli.file_utils.console")
    def test_export_trade_history_csv_different_periods(self, mock_console):
        """Test exporting trade history with different time periods."""
        test_cases = [
            ("TSLA", 1, "trade_history_1days_TSLA.csv"),
            ("MSFT", 90, "trade_history_90days_MSFT.csv"),
            (None, 365, "trade_history_365days.csv"),
        ]

        for symbol, days, expected_filename in test_cases:
            mock_console.reset_mock()
            export_trade_history_csv(symbol, days)

            mock_console.print.assert_any_call(
                f"[green]✓ Trade history exported to {expected_filename}[/green]"
            )


class TestFileUtilsIntegration:
    """Integration tests for file_utils interactive functions."""

    @patch("datetime.datetime")
    @patch("auto_trader.cli.file_utils.click.prompt")
    @patch("auto_trader.cli.file_utils.Prompt.ask")
    @patch("auto_trader.cli.file_utils.console")
    def test_complete_plan_data_flow(
        self, mock_console, mock_prompt_ask, mock_click_prompt, mock_datetime
    ):
        """Test complete plan data collection flow."""
        # Setup datetime mock
        mock_datetime.now.return_value.strftime.return_value = "20240301"

        # Setup realistic user interaction
        mock_prompt_ask.side_effect = [
            "SPY",  # ETF symbol
            "SPY_SWING_001",  # Custom plan ID
            "large",  # High risk for swing trade
        ]
        
        mock_click_prompt.side_effect = [
            "420.50",  # entry at key resistance
            "410.00",  # stop below support
            "435.00",  # target at next resistance
            "421.00",  # slightly higher threshold
        ]

        # Execute the function
        result = get_plan_data_interactive()

        # Verify complete result structure
        expected_keys = [
            "plan_id", "symbol", "entry_level", "stop_loss", 
            "take_profit", "risk_category", "threshold"
        ]
        assert all(key in result for key in expected_keys)

        # Verify realistic trading setup
        assert result["symbol"] == "SPY"
        assert result["plan_id"] == "SPY_SWING_001"
        assert result["risk_category"] == "large"
        
        # Verify price levels make sense
        assert result["entry_level"] == Decimal("420.50")
        assert result["stop_loss"] < result["entry_level"]  # Stop below entry
        assert result["take_profit"] > result["entry_level"]  # Target above entry
        assert result["threshold"] > result["entry_level"]  # Threshold above entry

        # Verify user was prompted appropriately
        mock_console.print.assert_called()  # Section headers shown
        assert len(mock_prompt_ask.call_args_list) == 3  # Symbol, plan_id, risk
        assert len(mock_click_prompt.call_args_list) == 4  # 3 prices + threshold

    def test_export_functions_error_handling(self):
        """Test export functions handle edge cases gracefully."""
        # These should not raise exceptions
        export_performance_csv("", "")
        export_performance_csv("custom_period", "20240229")  # Leap year
        
        export_trade_history_csv("", 0)
        export_trade_history_csv("VERY_LONG_SYMBOL_NAME", 9999)