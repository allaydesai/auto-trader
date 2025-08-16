"""Tests for risk_commands module."""

import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch, MagicMock

from click.testing import CliRunner

from auto_trader.cli.risk_commands import calculate_position_size, portfolio_risk_summary
from auto_trader.risk_management import (
    PositionSizeResult,
    RiskCheck,
    InvalidPositionSizeError,
)


class TestCalculatePositionSize:
    """Test calculate-position-size command."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_calculate_position_size_success(self):
        """Test successful position size calculation."""
        # Mock position size result
        mock_result = PositionSizeResult(
            position_size=40,
            dollar_risk=Decimal("200.00"),
            validation_status=True,
            portfolio_risk_percentage=Decimal("2.0"),
            risk_category="normal",
            account_value=Decimal("10000.00"),
        )

        # Mock risk check
        mock_risk_check = RiskCheck(
            passed=True,
            current_risk=Decimal("0.0"),
            new_trade_risk=Decimal("2.0"),
            total_risk=Decimal("2.0"),
            limit=Decimal("10.0"),
        )

        with patch("auto_trader.cli.risk_commands.RiskManager") as mock_risk_manager_class:
            mock_risk_manager = MagicMock()
            mock_risk_manager.position_sizer.calculate_position_size.return_value = mock_result
            mock_risk_manager.check_portfolio_risk_limit.return_value = mock_risk_check
            mock_risk_manager.position_sizer.get_risk_percentage.return_value = 2.0
            mock_risk_manager_class.return_value = mock_risk_manager

            result = self.runner.invoke(calculate_position_size, [
                "--symbol", "AAPL",
                "--entry", "180.50",
                "--stop", "178.00",
                "--risk", "normal",
                "--account-value", "10000"
            ])

            assert result.exit_code == 0
            assert "Position Size Calculated" in result.output
            assert "40 shares" in result.output
            assert "$200" in result.output

    def test_calculate_position_size_with_portfolio_risk_warning(self):
        """Test position size calculation with portfolio risk warning."""
        # Mock position size result
        mock_result = PositionSizeResult(
            position_size=40,
            dollar_risk=Decimal("200.00"),
            validation_status=True,
            portfolio_risk_percentage=Decimal("2.0"),
            risk_category="normal",
            account_value=Decimal("10000.00"),
        )

        # Mock risk check that fails
        mock_risk_check = RiskCheck(
            passed=False,
            reason="Portfolio risk limit exceeded: 11.0% exceeds limit of 10.0%",
            current_risk=Decimal("9.0"),
            new_trade_risk=Decimal("2.0"),
            total_risk=Decimal("11.0"),
            limit=Decimal("10.0"),
        )

        with patch("auto_trader.cli.risk_commands.RiskManager") as mock_risk_manager_class:
            mock_risk_manager = MagicMock()
            mock_risk_manager.position_sizer.calculate_position_size.return_value = mock_result
            mock_risk_manager.check_portfolio_risk_limit.return_value = mock_risk_check
            mock_risk_manager.position_sizer.get_risk_percentage.return_value = 2.0
            mock_risk_manager_class.return_value = mock_risk_manager

            result = self.runner.invoke(calculate_position_size, [
                "--symbol", "AAPL",
                "--entry", "180.50",
                "--stop", "178.00",
                "--risk", "normal",
                "--account-value", "10000"
            ])

            assert result.exit_code == 0
            assert "Trade Blocked - Portfolio Risk Exceeded" in result.output
            assert "Portfolio risk limit exceeded" in result.output

    def test_calculate_position_size_invalid_calculation(self):
        """Test position size calculation with invalid parameters."""
        with patch("auto_trader.cli.risk_commands.RiskManager") as mock_risk_manager_class:
            mock_risk_manager = MagicMock()
            mock_risk_manager.position_sizer.calculate_position_size.side_effect = InvalidPositionSizeError(
                "Entry price cannot equal stop loss price"
            )
            mock_risk_manager_class.return_value = mock_risk_manager

            result = self.runner.invoke(calculate_position_size, [
                "--symbol", "AAPL",
                "--entry", "180.00",
                "--stop", "180.00",  # Same as entry
                "--risk", "normal",
                "--account-value", "10000"
            ])

            assert result.exit_code == 0
            assert "Calculation Failed" in result.output
            assert "Entry price cannot equal stop loss price" in result.output

    def test_calculate_position_size_missing_required_params(self):
        """Test command with missing required parameters."""
        result = self.runner.invoke(calculate_position_size, [
            "--symbol", "AAPL",
            "--entry", "180.50"
            # Missing --stop parameter
        ])

        assert result.exit_code != 0
        assert "Missing option" in result.output

    def test_calculate_position_size_with_custom_state_file(self):
        """Test position size calculation with custom state file."""
        mock_result = PositionSizeResult(
            position_size=40,
            dollar_risk=Decimal("200.00"),
            validation_status=True,
            portfolio_risk_percentage=Decimal("2.0"),
            risk_category="normal",
            account_value=Decimal("10000.00"),
        )

        mock_risk_check = RiskCheck(
            passed=True,
            current_risk=Decimal("0.0"),
            new_trade_risk=Decimal("2.0"),
            total_risk=Decimal("2.0"),
            limit=Decimal("10.0"),
        )

        with tempfile.NamedTemporaryFile(suffix=".json") as temp_file:
            temp_path = Path(temp_file.name)

            with patch("auto_trader.cli.risk_commands.RiskManager") as mock_risk_manager_class:
                mock_risk_manager = MagicMock()
                mock_risk_manager.position_sizer.calculate_position_size.return_value = mock_result
                mock_risk_manager.check_portfolio_risk_limit.return_value = mock_risk_check
                mock_risk_manager.position_sizer.get_risk_percentage.return_value = 2.0
                mock_risk_manager_class.return_value = mock_risk_manager

                result = self.runner.invoke(calculate_position_size, [
                    "--symbol", "AAPL",
                    "--entry", "180.50",
                    "--stop", "178.00",
                    "--risk", "normal",
                    "--account-value", "10000",
                    "--state-file", str(temp_path)
                ])

                assert result.exit_code == 0
                # Verify state file was passed to RiskManager
                mock_risk_manager_class.assert_called_once()
                call_args = mock_risk_manager_class.call_args
                assert call_args[1]["state_file"] == temp_path


class TestPortfolioRiskSummary:
    """Test portfolio-risk-summary command."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_portfolio_risk_summary_empty_portfolio(self):
        """Test portfolio risk summary with empty portfolio."""
        mock_summary = {
            "account_value": 10000.0,
            "position_count": 0,
            "total_dollar_risk": 0.0,
            "current_risk_percentage": 0.0,
            "risk_limit": 10.0,
            "remaining_capacity_percent": 10.0,
            "remaining_capacity_dollars": 1000.0,
            "daily_loss_limit": 500.0,
            "daily_losses": 0.0,
            "daily_loss_remaining": 500.0,
            "daily_loss_percentage": 0.0,
            "positions": [],
        }

        with patch("auto_trader.cli.risk_commands.RiskManager") as mock_risk_manager_class:
            mock_risk_manager = MagicMock()
            mock_risk_manager.get_portfolio_summary.return_value = mock_summary
            mock_risk_manager_class.return_value = mock_risk_manager

            result = self.runner.invoke(portfolio_risk_summary, [
                "--account-value", "10000"
            ])

            assert result.exit_code == 0
            assert "Portfolio Risk Summary" in result.output
            assert "Account Value:" in result.output
            assert "$10,000.00" in result.output
            assert "No open positions" in result.output
            assert "Portfolio is risk-free" in result.output

    def test_portfolio_risk_summary_with_positions(self):
        """Test portfolio risk summary with open positions."""
        mock_summary = {
            "account_value": 10000.0,
            "position_count": 2,
            "total_dollar_risk": 500.0,
            "current_risk_percentage": 5.0,
            "risk_limit": 10.0,
            "remaining_capacity_percent": 5.0,
            "remaining_capacity_dollars": 500.0,
            "daily_loss_limit": 500.0,
            "daily_losses": 150.0,
            "daily_loss_remaining": 350.0,
            "daily_loss_percentage": 30.0,
            "positions": [
                {
                    "position_id": "POS_001",
                    "symbol": "AAPL",
                    "risk_amount": 200.0,
                    "plan_id": "AAPL_001",
                },
                {
                    "position_id": "POS_002",
                    "symbol": "MSFT",
                    "risk_amount": 300.0,
                    "plan_id": "MSFT_001",
                },
            ],
        }

        with patch("auto_trader.cli.risk_commands.RiskManager") as mock_risk_manager_class:
            mock_risk_manager = MagicMock()
            mock_risk_manager.get_portfolio_summary.return_value = mock_summary
            mock_risk_manager_class.return_value = mock_risk_manager

            result = self.runner.invoke(portfolio_risk_summary, [
                "--account-value", "10000"
            ])

            assert result.exit_code == 0
            assert "Portfolio Risk Summary" in result.output
            assert "Open Positions (2)" in result.output
            assert "POS_001" in result.output
            assert "AAPL" in result.output
            assert "$200.00" in result.output
            assert "Portfolio risk is moderate (5.0%)" in result.output

    def test_portfolio_risk_summary_high_risk(self):
        """Test portfolio risk summary with high risk portfolio."""
        mock_summary = {
            "account_value": 10000.0,
            "position_count": 1,
            "total_dollar_risk": 900.0,
            "current_risk_percentage": 9.0,
            "risk_limit": 10.0,
            "remaining_capacity_percent": 1.0,
            "remaining_capacity_dollars": 100.0,
            "daily_loss_limit": 500.0,
            "daily_losses": 0.0,
            "daily_loss_remaining": 500.0,
            "daily_loss_percentage": 0.0,
            "positions": [
                {
                    "position_id": "POS_001",
                    "symbol": "AAPL",
                    "risk_amount": 900.0,
                    "plan_id": "AAPL_001",
                },
            ],
        }

        with patch("auto_trader.cli.risk_commands.RiskManager") as mock_risk_manager_class:
            mock_risk_manager = MagicMock()
            mock_risk_manager.get_portfolio_summary.return_value = mock_summary
            mock_risk_manager_class.return_value = mock_risk_manager

            result = self.runner.invoke(portfolio_risk_summary, [
                "--account-value", "10000"
            ])

            assert result.exit_code == 0
            assert "Portfolio risk is high (9.0%)" in result.output

    def test_portfolio_risk_summary_with_custom_state_file(self):
        """Test portfolio risk summary with custom state file."""
        mock_summary = {
            "account_value": 10000.0,
            "position_count": 0,
            "total_dollar_risk": 0.0,
            "current_risk_percentage": 0.0,
            "risk_limit": 10.0,
            "remaining_capacity_percent": 10.0,
            "remaining_capacity_dollars": 1000.0,
            "daily_loss_limit": 500.0,
            "daily_losses": 0.0,
            "daily_loss_remaining": 500.0,
            "daily_loss_percentage": 0.0,
            "positions": [],
        }

        with tempfile.NamedTemporaryFile(suffix=".json") as temp_file:
            temp_path = Path(temp_file.name)

            with patch("auto_trader.cli.risk_commands.RiskManager") as mock_risk_manager_class:
                mock_risk_manager = MagicMock()
                mock_risk_manager.get_portfolio_summary.return_value = mock_summary
                mock_risk_manager_class.return_value = mock_risk_manager

                result = self.runner.invoke(portfolio_risk_summary, [
                    "--account-value", "10000",
                    "--state-file", str(temp_path)
                ])

                assert result.exit_code == 0
                # Verify state file was passed to RiskManager
                mock_risk_manager_class.assert_called_once()
                call_args = mock_risk_manager_class.call_args
                assert call_args[1]["state_file"] == temp_path


class TestErrorHandling:
    """Test error handling in risk commands."""

    def setup_method(self):
        """Set up test fixtures."""
        self.runner = CliRunner()

    def test_calculate_position_size_generic_error(self):
        """Test generic error handling in calculate-position-size."""
        with patch("auto_trader.cli.risk_commands.RiskManager") as mock_risk_manager_class:
            mock_risk_manager_class.side_effect = Exception("Unexpected error")

            result = self.runner.invoke(calculate_position_size, [
                "--symbol", "AAPL",
                "--entry", "180.50",
                "--stop", "178.00",
                "--risk", "normal",
                "--account-value", "10000"
            ])

            assert result.exit_code == 1
            # Should handle error gracefully and exit with error code

    def test_portfolio_risk_summary_generic_error(self):
        """Test generic error handling in portfolio-risk-summary."""
        with patch("auto_trader.cli.risk_commands.RiskManager") as mock_risk_manager_class:
            mock_risk_manager_class.side_effect = Exception("Unexpected error")

            result = self.runner.invoke(portfolio_risk_summary, [
                "--account-value", "10000"
            ])

            assert result.exit_code == 1
            # Should handle error gracefully and exit with error code