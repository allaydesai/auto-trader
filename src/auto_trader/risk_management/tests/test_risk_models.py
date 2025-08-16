"""Tests for risk management data models."""

from datetime import datetime
from decimal import Decimal

import pytest
from pydantic import ValidationError

from ..risk_models import (
    DailyLossLimitExceededError,
    InvalidPositionSizeError,
    PortfolioRiskExceededError,
    PortfolioRiskState,
    PositionRiskEntry,
    PositionSizeResult,
    RiskCheck,
    RiskManagementError,
    RiskValidationResult,
)


class TestPositionSizeResult:
    """Tests for PositionSizeResult model."""
    
    def test_valid_position_size_result(self, sample_position_size_result: PositionSizeResult) -> None:
        """Test creation of valid position size result."""
        assert sample_position_size_result.position_size == 40
        assert sample_position_size_result.dollar_risk == Decimal("200.00")
        assert sample_position_size_result.validation_status is True
        assert sample_position_size_result.portfolio_risk_percentage == Decimal("2.0")
        assert sample_position_size_result.risk_category == "normal"
        assert sample_position_size_result.account_value == Decimal("10000.00")
    
    def test_position_size_result_immutable(self, sample_position_size_result: PositionSizeResult) -> None:
        """Test that position size result is immutable."""
        with pytest.raises(ValidationError):
            sample_position_size_result.position_size = 50
    
    def test_invalid_position_size_zero(self) -> None:
        """Test validation of zero position size."""
        with pytest.raises(ValidationError, match="greater than 0"):
            PositionSizeResult(
                position_size=0,
                dollar_risk=Decimal("200.00"),
                validation_status=True,
                portfolio_risk_percentage=Decimal("2.0"),
                risk_category="normal",
                account_value=Decimal("10000.00"),
            )
    
    def test_invalid_negative_dollar_risk(self) -> None:
        """Test validation of negative dollar risk."""
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            PositionSizeResult(
                position_size=40,
                dollar_risk=Decimal("-200.00"),
                validation_status=True,
                portfolio_risk_percentage=Decimal("2.0"),
                risk_category="normal",
                account_value=Decimal("10000.00"),
            )
    
    def test_invalid_account_value_zero(self) -> None:
        """Test validation of zero account value."""
        with pytest.raises(ValidationError, match="greater than 0"):
            PositionSizeResult(
                position_size=40,
                dollar_risk=Decimal("200.00"),
                validation_status=True,
                portfolio_risk_percentage=Decimal("2.0"),
                risk_category="normal",
                account_value=Decimal("0.00"),
            )


class TestRiskCheck:
    """Tests for RiskCheck model."""
    
    def test_valid_risk_check_passed(self, sample_risk_check_passed: RiskCheck) -> None:
        """Test creation of valid passing risk check."""
        assert sample_risk_check_passed.passed is True
        assert sample_risk_check_passed.reason is None
        assert sample_risk_check_passed.current_risk == Decimal("5.0")
        assert sample_risk_check_passed.new_trade_risk == Decimal("2.0")
        assert sample_risk_check_passed.total_risk == Decimal("7.0")
        assert sample_risk_check_passed.limit == Decimal("10.0")
    
    def test_valid_risk_check_failed(self, sample_risk_check_failed: RiskCheck) -> None:
        """Test creation of valid failing risk check."""
        assert sample_risk_check_failed.passed is False
        assert sample_risk_check_failed.reason == "Portfolio risk limit exceeded"
        assert sample_risk_check_failed.current_risk == Decimal("8.5")
        assert sample_risk_check_failed.new_trade_risk == Decimal("2.0")
        assert sample_risk_check_failed.total_risk == Decimal("10.5")
        assert sample_risk_check_failed.limit == Decimal("10.0")
    
    def test_risk_check_immutable(self, sample_risk_check_passed: RiskCheck) -> None:
        """Test that risk check is immutable."""
        with pytest.raises(ValidationError):
            sample_risk_check_passed.passed = False
    
    def test_negative_risk_values(self) -> None:
        """Test validation of negative risk values."""
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            RiskCheck(
                passed=True,
                current_risk=Decimal("-5.0"),
                new_trade_risk=Decimal("2.0"),
            )


class TestPositionRiskEntry:
    """Tests for PositionRiskEntry model."""
    
    def test_valid_position_risk_entry(self, sample_position_risk_entry: PositionRiskEntry) -> None:
        """Test creation of valid position risk entry."""
        assert sample_position_risk_entry.position_id == "TEST_POS_001"
        assert sample_position_risk_entry.symbol == "AAPL"
        assert sample_position_risk_entry.risk_amount == Decimal("200.00")
        assert sample_position_risk_entry.plan_id == "AAPL_20250815_001"
        assert isinstance(sample_position_risk_entry.entry_time, datetime)
    
    def test_position_risk_entry_default_time(self) -> None:
        """Test default entry time is set."""
        entry = PositionRiskEntry(
            position_id="TEST_POS_001",
            symbol="AAPL",
            risk_amount=Decimal("200.00"),
            plan_id="AAPL_20250815_001",
        )
        assert isinstance(entry.entry_time, datetime)
        # Should be close to current time (within 1 second)
        time_diff = abs((datetime.utcnow() - entry.entry_time).total_seconds())
        assert time_diff < 1.0
    
    def test_invalid_empty_position_id(self) -> None:
        """Test validation of empty position ID."""
        with pytest.raises(ValidationError, match="at least 1 character"):
            PositionRiskEntry(
                position_id="",
                symbol="AAPL",
                risk_amount=Decimal("200.00"),
                plan_id="AAPL_20250815_001",
            )
    
    def test_invalid_symbol_too_long(self) -> None:
        """Test validation of symbol length."""
        with pytest.raises(ValidationError, match="at most 10 characters"):
            PositionRiskEntry(
                position_id="TEST_POS_001",
                symbol="VERYLONGSYMBOL",
                risk_amount=Decimal("200.00"),
                plan_id="AAPL_20250815_001",
            )
    
    def test_invalid_negative_risk_amount(self) -> None:
        """Test validation of negative risk amount."""
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            PositionRiskEntry(
                position_id="TEST_POS_001",
                symbol="AAPL",
                risk_amount=Decimal("-200.00"),
                plan_id="AAPL_20250815_001",
            )


class TestPortfolioRiskState:
    """Tests for PortfolioRiskState model."""
    
    def test_valid_portfolio_risk_state(
        self, 
        sample_portfolio_risk_state: PortfolioRiskState,
    ) -> None:
        """Test creation of valid portfolio risk state."""
        assert len(sample_portfolio_risk_state.positions) == 1
        assert sample_portfolio_risk_state.total_risk_percentage == Decimal("2.0")
        assert sample_portfolio_risk_state.account_value == Decimal("10000.00")
        assert isinstance(sample_portfolio_risk_state.last_updated, datetime)
    
    def test_empty_portfolio_risk_state(self) -> None:
        """Test creation of empty portfolio risk state."""
        state = PortfolioRiskState(
            account_value=Decimal("10000.00"),
        )
        assert len(state.positions) == 0
        assert state.total_risk_percentage == Decimal("0")
        assert state.position_count == 0
        assert state.total_dollar_risk == Decimal("0")
    
    def test_portfolio_properties(
        self, 
        multiple_position_entries: list[PositionRiskEntry],
    ) -> None:
        """Test portfolio calculated properties."""
        state = PortfolioRiskState(
            positions=multiple_position_entries,
            total_risk_percentage=Decimal("6.5"),
            account_value=Decimal("10000.00"),
        )
        
        assert state.position_count == 3
        assert state.total_dollar_risk == Decimal("650.00")  # 200 + 300 + 150
    
    def test_portfolio_default_time(self) -> None:
        """Test default last_updated time is set."""
        state = PortfolioRiskState(
            account_value=Decimal("10000.00"),
        )
        assert isinstance(state.last_updated, datetime)
        # Should be close to current time (within 1 second)
        time_diff = abs((datetime.utcnow() - state.last_updated).total_seconds())
        assert time_diff < 1.0


class TestRiskValidationResult:
    """Tests for RiskValidationResult model."""
    
    def test_valid_risk_validation_result(
        self,
        sample_position_size_result: PositionSizeResult,
        sample_risk_check_passed: RiskCheck,
    ) -> None:
        """Test creation of valid risk validation result."""
        result = RiskValidationResult(
            is_valid=True,
            position_size_result=sample_position_size_result,
            portfolio_risk_check=sample_risk_check_passed,
            errors=[],
            warnings=["Test warning"],
        )
        
        assert result.is_valid is True
        assert result.position_size_result == sample_position_size_result
        assert result.portfolio_risk_check == sample_risk_check_passed
        assert result.error_count == 0
        assert result.warning_count == 1
    
    def test_risk_validation_result_with_errors(
        self,
        sample_risk_check_failed: RiskCheck,
    ) -> None:
        """Test risk validation result with errors."""
        result = RiskValidationResult(
            is_valid=False,
            portfolio_risk_check=sample_risk_check_failed,
            errors=["Error 1", "Error 2"],
            warnings=[],
        )
        
        assert result.is_valid is False
        assert result.position_size_result is None
        assert result.error_count == 2
        assert result.warning_count == 0
    
    def test_error_summary(self) -> None:
        """Test error summary formatting."""
        result = RiskValidationResult(
            is_valid=False,
            portfolio_risk_check=RiskCheck(
                passed=False,
                current_risk=Decimal("0"),
                new_trade_risk=Decimal("0"),
            ),
            errors=["First error", "Second error"],
            warnings=[],
        )
        
        summary = result.get_error_summary()
        assert "Found 2 validation error(s):" in summary
        assert "1. First error" in summary
        assert "2. Second error" in summary
    
    def test_warning_summary(self) -> None:
        """Test warning summary formatting."""
        result = RiskValidationResult(
            is_valid=True,
            portfolio_risk_check=RiskCheck(
                passed=True,
                current_risk=Decimal("0"),
                new_trade_risk=Decimal("0"),
            ),
            warnings=["First warning", "Second warning"],
        )
        
        summary = result.get_warning_summary()
        assert "Found 2 warning(s):" in summary
        assert "1. First warning" in summary
        assert "2. Second warning" in summary
    
    def test_no_errors_summary(self) -> None:
        """Test summary with no errors."""
        result = RiskValidationResult(
            is_valid=True,
            portfolio_risk_check=RiskCheck(
                passed=True,
                current_risk=Decimal("0"),
                new_trade_risk=Decimal("0"),
            ),
        )
        
        assert result.get_error_summary() == "No validation errors"
        assert result.get_warning_summary() == "No warnings"


class TestRiskManagementExceptions:
    """Tests for risk management exception classes."""
    
    def test_risk_management_error_base(self) -> None:
        """Test base risk management error."""
        error = RiskManagementError(
            "Test error",
            error_code="TEST_001",
            context={"key": "value"},
        )
        
        assert str(error) == "Test error"
        assert error.error_code == "TEST_001"
        assert error.context == {"key": "value"}
    
    def test_portfolio_risk_exceeded_error(self) -> None:
        """Test portfolio risk exceeded error."""
        error = PortfolioRiskExceededError(
            current_risk=Decimal("8.5"),
            new_risk=Decimal("2.0"),
            limit=Decimal("10.0"),
        )
        
        assert error.current_risk == Decimal("8.5")
        assert error.new_risk == Decimal("2.0")
        assert error.limit == Decimal("10.0")
        assert error.total_risk == Decimal("10.5")
        assert error.error_code == "RISK_001"
        assert "Portfolio risk limit exceeded" in str(error)
        assert "10.50%" in str(error)
    
    def test_invalid_position_size_error(self) -> None:
        """Test invalid position size error."""
        error = InvalidPositionSizeError(
            "Entry price cannot equal stop loss",
            entry_price=Decimal("100.00"),
            stop_price=Decimal("100.00"),
        )
        
        assert error.reason == "Entry price cannot equal stop loss"
        assert error.entry_price == Decimal("100.00")
        assert error.stop_price == Decimal("100.00")
        assert error.error_code == "RISK_002"
        assert str(error) == "Entry price cannot equal stop loss"
    
    def test_daily_loss_limit_exceeded_error(self) -> None:
        """Test daily loss limit exceeded error."""
        error = DailyLossLimitExceededError(
            current_loss=Decimal("750.00"),
            limit=Decimal("500.00"),
        )
        
        assert error.current_loss == Decimal("750.00")
        assert error.limit == Decimal("500.00")
        assert error.error_code == "RISK_003"
        assert "$750.00" in str(error)
        assert "$500.00" in str(error)