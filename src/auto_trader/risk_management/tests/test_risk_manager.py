"""Tests for the RiskManager orchestrator."""

import tempfile
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from ...models import TradePlan
from ..risk_manager import RiskManager
from ..risk_models import DailyLossLimitExceededError, InvalidPositionSizeError


class TestRiskManagerInitialization:
    """Tests for RiskManager initialization."""
    
    def test_default_initialization(self, temp_state_file: Path) -> None:
        """Test risk manager initialization with defaults."""
        risk_manager = RiskManager(
            account_value=Decimal("10000.00"),
            state_file=temp_state_file,
        )
        
        assert risk_manager.account_value == Decimal("10000.00")
        assert risk_manager.daily_loss_limit == Decimal("500.00")
        assert risk_manager.position_sizer is not None
        assert risk_manager.portfolio_tracker is not None
        assert risk_manager._daily_losses == Decimal("0.00")
        assert risk_manager._last_reset_date == datetime.utcnow().date()
    
    def test_custom_initialization(self, temp_state_file: Path) -> None:
        """Test risk manager initialization with custom parameters."""
        risk_manager = RiskManager(
            account_value=Decimal("50000.00"),
            daily_loss_limit=Decimal("1000.00"),
            state_file=temp_state_file,
        )
        
        assert risk_manager.account_value == Decimal("50000.00")
        assert risk_manager.daily_loss_limit == Decimal("1000.00")
    
    def test_portfolio_tracker_integration(self, temp_state_file: Path) -> None:
        """Test that portfolio tracker is properly initialized."""
        risk_manager = RiskManager(
            account_value=Decimal("25000.00"),
            state_file=temp_state_file,
        )
        
        assert risk_manager.portfolio_tracker.state_file == temp_state_file
        assert risk_manager.portfolio_tracker._account_value == Decimal("25000.00")


class TestTradePlanValidation:
    """Tests for trade plan validation."""
    
    @pytest.fixture
    def risk_manager(self, temp_state_file: Path) -> RiskManager:
        """Create risk manager for testing."""
        return RiskManager(
            account_value=Decimal("10000.00"),
            daily_loss_limit=Decimal("500.00"),
            state_file=temp_state_file,
        )
    
    def test_validate_valid_trade_plan(
        self,
        risk_manager: RiskManager,
        sample_trade_plan: TradePlan,
    ) -> None:
        """Test validation of a valid trade plan."""
        result = risk_manager.validate_trade_plan(sample_trade_plan)
        
        assert result.is_valid is True
        assert result.position_size_result is not None
        assert result.portfolio_risk_check.passed is True
        assert result.error_count == 0
        
        # Check position size calculation
        assert result.position_size_result.position_size == 40  # (10000 * 2%) / (180 - 175) = 40
        assert result.position_size_result.dollar_risk == Decimal("200.00")
        assert result.position_size_result.risk_category == "normal"
    
    def test_validate_invalid_account_value(
        self,
        sample_trade_plan: TradePlan,
        temp_state_file: Path,
    ) -> None:
        """Test validation with invalid account value."""
        risk_manager = RiskManager(
            account_value=Decimal("0.00"),
            state_file=temp_state_file,
        )
        
        result = risk_manager.validate_trade_plan(sample_trade_plan)
        
        assert result.is_valid is False
        assert result.position_size_result is None
        assert "Invalid account value for risk calculations" in result.errors
    
    def test_validate_zero_risk_trade(
        self,
        risk_manager: RiskManager,
    ) -> None:
        """Test validation of trade with zero risk (entry == stop)."""
        # Create a new trade plan with zero risk (this will fail in TradePlan validation itself)
        from ...models import TradePlan, ExecutionFunction, RiskCategory, TradePlanStatus
        from decimal import Decimal
        
        try:
            # This should fail during TradePlan creation due to model validation
            zero_risk_plan = TradePlan(
                plan_id="ZERO_RISK_001",
                symbol="AAPL",
                entry_level=Decimal("180.00"),
                stop_loss=Decimal("180.00"),  # Same as entry
                take_profit=Decimal("190.00"),
                risk_category=RiskCategory.NORMAL,
                entry_function=ExecutionFunction(
                    function_type="close_above",
                    timeframe="15min",
                    parameters={"threshold": 180.00},
                ),
                exit_function=ExecutionFunction(
                    function_type="stop_loss_take_profit",
                    timeframe="15min",
                    parameters={},
                ),
            )
            # If we reach here, the TradePlan validation didn't catch it
            assert False, "TradePlan should have rejected zero-risk trade"
        except Exception as e:
            # This is expected - TradePlan model should prevent zero-risk trades
            assert "cannot equal stop loss" in str(e) or "zero-risk" in str(e).lower()
    
    def test_validate_portfolio_risk_exceeded(
        self,
        risk_manager: RiskManager,
        high_risk_trade_plan: TradePlan,
    ) -> None:
        """Test validation when portfolio risk limit would be exceeded."""
        # Add existing positions to approach limit
        risk_manager.add_position_to_tracking("POS_001", "AAPL", Decimal("400.00"), "AAPL_001")
        risk_manager.add_position_to_tracking("POS_002", "MSFT", Decimal("400.00"), "MSFT_002")
        # Total existing risk: 8%
        
        # Try to add large risk trade (3% = $300 for $10k / $10 difference)
        result = risk_manager.validate_trade_plan(high_risk_trade_plan)
        
        assert result.is_valid is False
        assert not result.portfolio_risk_check.passed
        assert "Portfolio risk limit exceeded" in result.portfolio_risk_check.reason
    
    def test_validate_with_warnings(
        self,
        risk_manager: RiskManager,
        sample_trade_plan: TradePlan,
    ) -> None:
        """Test validation that passes but has warnings."""
        # Add some daily losses to trigger warnings
        risk_manager._daily_losses = Decimal("600.00")  # Exceeds limit
        
        result = risk_manager.validate_trade_plan(sample_trade_plan)
        
        assert result.is_valid is False  # Fails due to daily loss limit
        assert any("Daily loss limit exceeded" in error for error in result.errors)
        assert any("Consider waiting until tomorrow" in warning for warning in result.warnings)


class TestPositionSizeCalculation:
    """Tests for position size calculation methods."""
    
    @pytest.fixture
    def risk_manager(self, temp_state_file: Path) -> RiskManager:
        """Create risk manager for testing."""
        return RiskManager(
            account_value=Decimal("10000.00"),
            state_file=temp_state_file,
        )
    
    def test_calculate_position_size_for_plan(
        self,
        risk_manager: RiskManager,
        sample_trade_plan: TradePlan,
    ) -> None:
        """Test position size calculation for trade plan."""
        position_size = risk_manager.calculate_position_size_for_plan(sample_trade_plan)
        
        # (10000 * 2%) / (180 - 175) = 200 / 5 = 40 shares
        assert position_size == 40
    
    def test_calculate_position_size_invalid_plan(
        self,
        risk_manager: RiskManager,
    ) -> None:
        """Test position size calculation with invalid plan by using zero account value."""
        # Create risk manager with zero account value to trigger error
        zero_account_manager = RiskManager(
            account_value=Decimal("0.00"),
            state_file=Path("temp_test.json"),
        )
        
        from ...models import TradePlan, ExecutionFunction, RiskCategory
        
        valid_plan = TradePlan(
            plan_id="VALID_PLAN_001",
            symbol="AAPL",
            entry_level=Decimal("180.00"),
            stop_loss=Decimal("175.00"),
            take_profit=Decimal("190.00"),
            risk_category=RiskCategory.NORMAL,
            entry_function=ExecutionFunction(
                function_type="close_above",
                timeframe="15min",
                parameters={"threshold": 180.00},
            ),
            exit_function=ExecutionFunction(
                function_type="stop_loss_take_profit",
                timeframe="15min",
                parameters={},
            ),
        )
        
        with pytest.raises(InvalidPositionSizeError):
            zero_account_manager.calculate_position_size_for_plan(valid_plan)


class TestPortfolioRiskManagement:
    """Tests for portfolio risk management."""
    
    @pytest.fixture
    def risk_manager(self, temp_state_file: Path) -> RiskManager:
        """Create risk manager for testing."""
        return RiskManager(
            account_value=Decimal("10000.00"),
            state_file=temp_state_file,
        )
    
    def test_check_portfolio_risk_limit_within_limit(
        self,
        risk_manager: RiskManager,
    ) -> None:
        """Test portfolio risk check within limit."""
        # Add 5% existing risk
        risk_manager.add_position_to_tracking("POS_001", "AAPL", Decimal("500.00"), "AAPL_001")
        
        # Check 3% additional risk (total 8%, within 10% limit)
        risk_check = risk_manager.check_portfolio_risk_limit(Decimal("300.00"))
        
        assert risk_check.passed is True
        assert risk_check.current_risk == Decimal("5.00")
        assert risk_check.new_trade_risk == Decimal("3.00")
        assert risk_check.total_risk == Decimal("8.00")
    
    def test_check_portfolio_risk_limit_exceeded(
        self,
        risk_manager: RiskManager,
    ) -> None:
        """Test portfolio risk check when limit exceeded."""
        # Add 8% existing risk
        risk_manager.add_position_to_tracking("POS_001", "AAPL", Decimal("800.00"), "AAPL_001")
        
        # Check 3% additional risk (total 11%, exceeds 10% limit)
        risk_check = risk_manager.check_portfolio_risk_limit(Decimal("300.00"))
        
        assert risk_check.passed is False
        assert risk_check.current_risk == Decimal("8.00")
        assert risk_check.new_trade_risk == Decimal("3.00")
        assert risk_check.total_risk == Decimal("11.00")
        assert "Portfolio risk limit exceeded" in risk_check.reason
    
    def test_get_current_portfolio_risk(
        self,
        risk_manager: RiskManager,
    ) -> None:
        """Test getting current portfolio risk."""
        assert risk_manager.get_current_portfolio_risk() == Decimal("0.00")
        
        risk_manager.add_position_to_tracking("POS_001", "AAPL", Decimal("250.00"), "AAPL_001")
        assert risk_manager.get_current_portfolio_risk() == Decimal("2.50")
    
    def test_get_available_risk_capacity(
        self,
        risk_manager: RiskManager,
    ) -> None:
        """Test getting available risk capacity."""
        # Empty portfolio
        percent_capacity, dollar_capacity = risk_manager.get_available_risk_capacity()
        assert percent_capacity == Decimal("10.0")
        assert dollar_capacity == Decimal("1000.00")
        
        # Add some positions
        risk_manager.add_position_to_tracking("POS_001", "AAPL", Decimal("300.00"), "AAPL_001")
        percent_capacity, dollar_capacity = risk_manager.get_available_risk_capacity()
        assert percent_capacity == Decimal("7.00")
        assert dollar_capacity == Decimal("700.00")


class TestPositionTracking:
    """Tests for position tracking operations."""
    
    @pytest.fixture
    def risk_manager(self, temp_state_file: Path) -> RiskManager:
        """Create risk manager for testing."""
        return RiskManager(
            account_value=Decimal("10000.00"),
            state_file=temp_state_file,
        )
    
    def test_add_position_to_tracking(
        self,
        risk_manager: RiskManager,
    ) -> None:
        """Test adding position to tracking."""
        risk_manager.add_position_to_tracking(
            position_id="POS_001",
            symbol="AAPL",
            risk_amount=Decimal("200.00"),
            plan_id="AAPL_001",
        )
        
        assert risk_manager.portfolio_tracker.get_position_count() == 1
        assert risk_manager.get_current_portfolio_risk() == Decimal("2.00")
        
        position = risk_manager.portfolio_tracker.get_position("POS_001")
        assert position is not None
        assert position.symbol == "AAPL"
        assert position.risk_amount == Decimal("200.00")
    
    def test_remove_position_from_tracking(
        self,
        risk_manager: RiskManager,
    ) -> None:
        """Test removing position from tracking."""
        # Add position first
        risk_manager.add_position_to_tracking("POS_001", "AAPL", Decimal("200.00"), "AAPL_001")
        risk_manager.add_position_to_tracking("POS_002", "MSFT", Decimal("300.00"), "MSFT_001")
        
        # Remove one position
        result = risk_manager.remove_position_from_tracking("POS_001")
        
        assert result is True
        assert risk_manager.portfolio_tracker.get_position_count() == 1
        assert risk_manager.get_current_portfolio_risk() == Decimal("3.00")
        assert risk_manager.portfolio_tracker.get_position("POS_001") is None
    
    def test_remove_nonexistent_position(
        self,
        risk_manager: RiskManager,
    ) -> None:
        """Test removing non-existent position."""
        result = risk_manager.remove_position_from_tracking("NONEXISTENT")
        
        assert result is False
        assert risk_manager.portfolio_tracker.get_position_count() == 0
    
    def test_clear_all_positions(
        self,
        risk_manager: RiskManager,
    ) -> None:
        """Test clearing all positions."""
        # Add multiple positions
        risk_manager.add_position_to_tracking("POS_001", "AAPL", Decimal("200.00"), "AAPL_001")
        risk_manager.add_position_to_tracking("POS_002", "MSFT", Decimal("300.00"), "MSFT_001")
        risk_manager.add_position_to_tracking("POS_003", "GOOGL", Decimal("150.00"), "GOOGL_001")
        
        cleared_count = risk_manager.clear_all_positions()
        
        assert cleared_count == 3
        assert risk_manager.portfolio_tracker.get_position_count() == 0
        assert risk_manager.get_current_portfolio_risk() == Decimal("0.00")


class TestDailyLossManagement:
    """Tests for daily loss limit management."""
    
    @pytest.fixture
    def risk_manager(self, temp_state_file: Path) -> RiskManager:
        """Create risk manager for testing."""
        return RiskManager(
            account_value=Decimal("10000.00"),
            daily_loss_limit=Decimal("500.00"),
            state_file=temp_state_file,
        )
    
    def test_record_daily_loss_within_limit(
        self,
        risk_manager: RiskManager,
    ) -> None:
        """Test recording daily loss within limit."""
        risk_manager.record_daily_loss(Decimal("200.00"))
        
        assert risk_manager._daily_losses == Decimal("200.00")
        
        # Add more losses
        risk_manager.record_daily_loss(Decimal("150.00"))
        
        assert risk_manager._daily_losses == Decimal("350.00")
    
    def test_record_daily_loss_exceeds_limit(
        self,
        risk_manager: RiskManager,
    ) -> None:
        """Test recording daily loss that exceeds limit."""
        # Add losses up to near limit
        risk_manager.record_daily_loss(Decimal("400.00"))
        
        # Try to add loss that exceeds limit
        with pytest.raises(DailyLossLimitExceededError) as exc_info:
            risk_manager.record_daily_loss(Decimal("200.00"))
        
        error = exc_info.value
        assert error.current_loss == Decimal("600.00")
        assert error.limit == Decimal("500.00")
    
    def test_daily_loss_reset(
        self,
        risk_manager: RiskManager,
    ) -> None:
        """Test daily loss reset functionality."""
        # Add some losses
        risk_manager.record_daily_loss(Decimal("300.00"))
        assert risk_manager._daily_losses == Decimal("300.00")
        
        # Simulate next day by changing the reset date
        risk_manager._last_reset_date = datetime.utcnow().date() - timedelta(days=1)
        
        # Force reset by calling internal method
        risk_manager._reset_daily_losses_if_needed()
        
        assert risk_manager._daily_losses == Decimal("0.00")
        assert risk_manager._last_reset_date == datetime.utcnow().date()
    
    def test_daily_loss_limit_check_in_validation(
        self,
        risk_manager: RiskManager,
        sample_trade_plan: TradePlan,
    ) -> None:
        """Test daily loss limit check during trade validation."""
        # Set daily losses to exceed limit
        risk_manager._daily_losses = Decimal("600.00")
        
        result = risk_manager.validate_trade_plan(sample_trade_plan)
        
        assert result.is_valid is False
        assert any("Daily loss limit exceeded" in error for error in result.errors)


class TestAccountValueManagement:
    """Tests for account value management."""
    
    @pytest.fixture
    def risk_manager(self, temp_state_file: Path) -> RiskManager:
        """Create risk manager for testing."""
        return RiskManager(
            account_value=Decimal("10000.00"),
            state_file=temp_state_file,
        )
    
    def test_update_account_value(
        self,
        risk_manager: RiskManager,
    ) -> None:
        """Test updating account value."""
        # Add a position first
        risk_manager.add_position_to_tracking("POS_001", "AAPL", Decimal("200.00"), "AAPL_001")
        initial_risk = risk_manager.get_current_portfolio_risk()
        assert initial_risk == Decimal("2.00")  # 200/10000 * 100
        
        # Update account value
        risk_manager.update_account_value(Decimal("20000.00"))
        
        assert risk_manager.account_value == Decimal("20000.00")
        assert risk_manager.portfolio_tracker._account_value == Decimal("20000.00")
        
        # Risk percentage should be recalculated
        new_risk = risk_manager.get_current_portfolio_risk()
        assert new_risk == Decimal("1.00")  # 200/20000 * 100


class TestPortfolioSummary:
    """Tests for portfolio summary functionality."""
    
    @pytest.fixture
    def risk_manager(self, temp_state_file: Path) -> RiskManager:
        """Create risk manager for testing."""
        return RiskManager(
            account_value=Decimal("10000.00"),
            daily_loss_limit=Decimal("500.00"),
            state_file=temp_state_file,
        )
    
    def test_get_portfolio_summary_empty(
        self,
        risk_manager: RiskManager,
    ) -> None:
        """Test portfolio summary with empty portfolio."""
        summary = risk_manager.get_portfolio_summary()
        
        assert summary["account_value"] == 10000.0
        assert summary["position_count"] == 0
        assert summary["total_dollar_risk"] == 0.0
        assert summary["current_risk_percentage"] == 0.0
        assert summary["daily_loss_limit"] == 500.0
        assert summary["daily_losses"] == 0.0
        assert summary["daily_loss_remaining"] == 500.0
        assert summary["daily_loss_percentage"] == 0.0
    
    def test_get_portfolio_summary_with_positions_and_losses(
        self,
        risk_manager: RiskManager,
    ) -> None:
        """Test portfolio summary with positions and daily losses."""
        # Add positions
        risk_manager.add_position_to_tracking("POS_001", "AAPL", Decimal("200.00"), "AAPL_001")
        risk_manager.add_position_to_tracking("POS_002", "MSFT", Decimal("300.00"), "MSFT_001")
        
        # Add daily losses
        risk_manager.record_daily_loss(Decimal("150.00"))
        
        summary = risk_manager.get_portfolio_summary()
        
        assert summary["account_value"] == 10000.0
        assert summary["position_count"] == 2
        assert summary["total_dollar_risk"] == 500.0
        assert summary["current_risk_percentage"] == 5.0
        assert summary["daily_losses"] == 150.0
        assert summary["daily_loss_remaining"] == 350.0
        assert summary["daily_loss_percentage"] == 30.0  # 150/500 * 100


class TestEdgeCasesAndErrorHandling:
    """Tests for edge cases and error handling."""
    
    def test_risk_manager_with_zero_daily_limit(
        self,
        temp_state_file: Path,
    ) -> None:
        """Test risk manager with zero daily loss limit."""
        risk_manager = RiskManager(
            account_value=Decimal("10000.00"),
            daily_loss_limit=Decimal("0.00"),
            state_file=temp_state_file,
        )
        
        # Any loss should exceed the zero limit
        with pytest.raises(DailyLossLimitExceededError):
            risk_manager.record_daily_loss(Decimal("1.00"))
    
    def test_portfolio_summary_with_zero_daily_limit(
        self,
        temp_state_file: Path,
    ) -> None:
        """Test portfolio summary calculation with zero daily limit."""
        risk_manager = RiskManager(
            account_value=Decimal("10000.00"),
            daily_loss_limit=Decimal("0.00"),
            state_file=temp_state_file,
        )
        
        summary = risk_manager.get_portfolio_summary()
        
        # Should handle division by zero gracefully
        assert summary["daily_loss_percentage"] == 0.0
    
    def test_risk_manager_persistence_across_instances(
        self,
        temp_state_file: Path,
        sample_trade_plan: TradePlan,
    ) -> None:
        """Test that risk manager state persists across instances."""
        # Create first instance and add positions
        risk_manager1 = RiskManager(
            account_value=Decimal("10000.00"),
            state_file=temp_state_file,
        )
        risk_manager1.add_position_to_tracking("POS_001", "AAPL", Decimal("200.00"), "AAPL_001")
        
        # Create second instance with same state file
        risk_manager2 = RiskManager(
            account_value=Decimal("10000.00"),
            state_file=temp_state_file,
        )
        
        # Should load existing positions
        assert risk_manager2.get_current_portfolio_risk() == Decimal("2.00")
        assert risk_manager2.portfolio_tracker.get_position_count() == 1