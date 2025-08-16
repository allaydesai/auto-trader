"""Tests for position sizing calculations."""

from decimal import Decimal

import pytest

from ..position_sizer import PositionSizer
from ..risk_models import InvalidPositionSizeError, PositionSizeResult


class TestPositionSizer:
    """Tests for PositionSizer class."""
    
    @pytest.fixture
    def position_sizer(self) -> PositionSizer:
        """Create a position sizer instance for testing."""
        return PositionSizer()
    
    def test_position_sizer_initialization(self, position_sizer: PositionSizer) -> None:
        """Test position sizer initialization."""
        assert isinstance(position_sizer, PositionSizer)
        assert len(position_sizer.RISK_PERCENTAGES) == 3
        assert position_sizer.RISK_PERCENTAGES["small"] == Decimal("1.0")
        assert position_sizer.RISK_PERCENTAGES["normal"] == Decimal("2.0")
        assert position_sizer.RISK_PERCENTAGES["large"] == Decimal("3.0")


class TestCalculatePositionSize:
    """Tests for calculate_position_size method."""
    
    @pytest.fixture
    def position_sizer(self) -> PositionSizer:
        """Create a position sizer instance for testing."""
        return PositionSizer()
    
    def test_normal_risk_calculation(
        self,
        position_sizer: PositionSizer,
        sample_account_value: Decimal,
        sample_entry_price: Decimal,
        sample_stop_loss: Decimal,
    ) -> None:
        """Test position size calculation with normal risk (2%)."""
        result = position_sizer.calculate_position_size(
            account_value=sample_account_value,  # $10,000
            risk_category="normal",  # 2%
            entry_price=sample_entry_price,  # $100
            stop_loss=sample_stop_loss,  # $95
        )
        
        # Expected: ($10,000 * 2%) / ($100 - $95) = $200 / $5 = 40 shares
        assert isinstance(result, PositionSizeResult)
        assert result.position_size == 40
        assert result.dollar_risk == Decimal("200.00")
        assert result.validation_status is True
        assert result.portfolio_risk_percentage == Decimal("2.0")
        assert result.risk_category == "normal"
        assert result.account_value == sample_account_value
    
    def test_small_risk_calculation(
        self,
        position_sizer: PositionSizer,
        sample_account_value: Decimal,
        sample_entry_price: Decimal,
        sample_stop_loss: Decimal,
    ) -> None:
        """Test position size calculation with small risk (1%)."""
        result = position_sizer.calculate_position_size(
            account_value=sample_account_value,
            risk_category="small",
            entry_price=sample_entry_price,
            stop_loss=sample_stop_loss,
        )
        
        # Expected: ($10,000 * 1%) / ($100 - $95) = $100 / $5 = 20 shares
        assert result.position_size == 20
        assert result.dollar_risk == Decimal("100.00")
        assert result.portfolio_risk_percentage == Decimal("1.0")
        assert result.risk_category == "small"
    
    def test_large_risk_calculation(
        self,
        position_sizer: PositionSizer,
        sample_account_value: Decimal,
        sample_entry_price: Decimal,
        sample_stop_loss: Decimal,
    ) -> None:
        """Test position size calculation with large risk (3%)."""
        result = position_sizer.calculate_position_size(
            account_value=sample_account_value,
            risk_category="large",
            entry_price=sample_entry_price,
            stop_loss=sample_stop_loss,
        )
        
        # Expected: ($10,000 * 3%) / ($100 - $95) = $300 / $5 = 60 shares
        assert result.position_size == 60
        assert result.dollar_risk == Decimal("300.00")
        assert result.portfolio_risk_percentage == Decimal("3.0")
        assert result.risk_category == "large"
    
    def test_short_position_calculation(
        self,
        position_sizer: PositionSizer,
        sample_account_value: Decimal,
    ) -> None:
        """Test position size calculation for short position."""
        result = position_sizer.calculate_position_size(
            account_value=sample_account_value,
            risk_category="normal",
            entry_price=Decimal("95.00"),  # Short entry
            stop_loss=Decimal("100.00"),   # Stop above entry
        )
        
        # Expected: ($10,000 * 2%) / |$95 - $100| = $200 / $5 = 40 shares
        assert result.position_size == 40
        assert result.dollar_risk == Decimal("200.00")
    
    def test_fractional_shares_rounded_down(
        self,
        position_sizer: PositionSizer,
    ) -> None:
        """Test that fractional shares are rounded down."""
        result = position_sizer.calculate_position_size(
            account_value=Decimal("10000.00"),
            risk_category="normal",
            entry_price=Decimal("100.00"),
            stop_loss=Decimal("96.67"),  # Creates 3.33 price difference
        )
        
        # Expected: $200 / $3.33 = 60.06 shares -> rounds down to 60
        assert result.position_size == 60
        assert result.dollar_risk == Decimal("200.00")
    
    def test_minimum_one_share(
        self,
        position_sizer: PositionSizer,
    ) -> None:
        """Test that minimum position size is 1 share."""
        result = position_sizer.calculate_position_size(
            account_value=Decimal("100.00"),  # Small account
            risk_category="small",             # 1% = $1
            entry_price=Decimal("100.00"),
            stop_loss=Decimal("95.00"),       # $5 difference
        )
        
        # Expected: $1 / $5 = 0.2 shares -> rounds to 1 minimum
        assert result.position_size == 1
        assert result.dollar_risk == Decimal("1.00")
    
    def test_large_price_difference(
        self,
        position_sizer: PositionSizer,
        sample_account_value: Decimal,
    ) -> None:
        """Test calculation with large price difference."""
        result = position_sizer.calculate_position_size(
            account_value=sample_account_value,
            risk_category="normal",
            entry_price=Decimal("100.00"),
            stop_loss=Decimal("50.00"),  # $50 difference
        )
        
        # Expected: $200 / $50 = 4 shares
        assert result.position_size == 4
        assert result.dollar_risk == Decimal("200.00")
    
    def test_small_price_difference(
        self,
        position_sizer: PositionSizer,
        sample_account_value: Decimal,
    ) -> None:
        """Test calculation with small price difference."""
        result = position_sizer.calculate_position_size(
            account_value=sample_account_value,
            risk_category="normal",
            entry_price=Decimal("100.00"),
            stop_loss=Decimal("99.50"),  # $0.50 difference
        )
        
        # Expected: $200 / $0.50 = 400 shares
        assert result.position_size == 400
        assert result.dollar_risk == Decimal("200.00")
    
    def test_case_insensitive_risk_category(
        self,
        position_sizer: PositionSizer,
        sample_account_value: Decimal,
        sample_entry_price: Decimal,
        sample_stop_loss: Decimal,
    ) -> None:
        """Test that risk category is case insensitive."""
        result_upper = position_sizer.calculate_position_size(
            account_value=sample_account_value,
            risk_category="NORMAL",
            entry_price=sample_entry_price,
            stop_loss=sample_stop_loss,
        )
        
        result_mixed = position_sizer.calculate_position_size(
            account_value=sample_account_value,
            risk_category="NoRmAl",
            entry_price=sample_entry_price,
            stop_loss=sample_stop_loss,
        )
        
        assert result_upper.position_size == 40
        assert result_mixed.position_size == 40
        assert result_upper.risk_category == "NORMAL"
        assert result_mixed.risk_category == "NoRmAl"


class TestPositionSizerValidation:
    """Tests for position sizer input validation."""
    
    @pytest.fixture
    def position_sizer(self) -> PositionSizer:
        """Create a position sizer instance for testing."""
        return PositionSizer()
    
    def test_zero_account_value(
        self,
        position_sizer: PositionSizer,
        sample_entry_price: Decimal,
        sample_stop_loss: Decimal,
    ) -> None:
        """Test validation of zero account value."""
        with pytest.raises(InvalidPositionSizeError, match="Account value must be positive"):
            position_sizer.calculate_position_size(
                account_value=Decimal("0.00"),
                risk_category="normal",
                entry_price=sample_entry_price,
                stop_loss=sample_stop_loss,
            )
    
    def test_negative_account_value(
        self,
        position_sizer: PositionSizer,
        sample_entry_price: Decimal,
        sample_stop_loss: Decimal,
    ) -> None:
        """Test validation of negative account value."""
        with pytest.raises(InvalidPositionSizeError, match="Account value must be positive"):
            position_sizer.calculate_position_size(
                account_value=Decimal("-1000.00"),
                risk_category="normal",
                entry_price=sample_entry_price,
                stop_loss=sample_stop_loss,
            )
    
    def test_invalid_risk_category(
        self,
        position_sizer: PositionSizer,
        sample_account_value: Decimal,
        sample_entry_price: Decimal,
        sample_stop_loss: Decimal,
    ) -> None:
        """Test validation of invalid risk category."""
        with pytest.raises(InvalidPositionSizeError, match="Invalid risk category 'invalid'"):
            position_sizer.calculate_position_size(
                account_value=sample_account_value,
                risk_category="invalid",
                entry_price=sample_entry_price,
                stop_loss=sample_stop_loss,
            )
    
    def test_zero_entry_price(
        self,
        position_sizer: PositionSizer,
        sample_account_value: Decimal,
        sample_stop_loss: Decimal,
    ) -> None:
        """Test validation of zero entry price."""
        with pytest.raises(InvalidPositionSizeError, match="Entry price must be positive"):
            position_sizer.calculate_position_size(
                account_value=sample_account_value,
                risk_category="normal",
                entry_price=Decimal("0.00"),
                stop_loss=sample_stop_loss,
            )
    
    def test_negative_entry_price(
        self,
        position_sizer: PositionSizer,
        sample_account_value: Decimal,
        sample_stop_loss: Decimal,
    ) -> None:
        """Test validation of negative entry price."""
        with pytest.raises(InvalidPositionSizeError, match="Entry price must be positive"):
            position_sizer.calculate_position_size(
                account_value=sample_account_value,
                risk_category="normal",
                entry_price=Decimal("-100.00"),
                stop_loss=sample_stop_loss,
            )
    
    def test_zero_stop_loss(
        self,
        position_sizer: PositionSizer,
        sample_account_value: Decimal,
        sample_entry_price: Decimal,
    ) -> None:
        """Test validation of zero stop loss."""
        with pytest.raises(InvalidPositionSizeError, match="Stop loss price must be positive"):
            position_sizer.calculate_position_size(
                account_value=sample_account_value,
                risk_category="normal",
                entry_price=sample_entry_price,
                stop_loss=Decimal("0.00"),
            )
    
    def test_negative_stop_loss(
        self,
        position_sizer: PositionSizer,
        sample_account_value: Decimal,
        sample_entry_price: Decimal,
    ) -> None:
        """Test validation of negative stop loss."""
        with pytest.raises(InvalidPositionSizeError, match="Stop loss price must be positive"):
            position_sizer.calculate_position_size(
                account_value=sample_account_value,
                risk_category="normal",
                entry_price=sample_entry_price,
                stop_loss=Decimal("-95.00"),
            )
    
    def test_entry_equals_stop_loss(
        self,
        position_sizer: PositionSizer,
        sample_account_value: Decimal,
    ) -> None:
        """Test validation of entry price equal to stop loss (zero risk)."""
        with pytest.raises(
            InvalidPositionSizeError, 
            match="Entry price \\(100\\.00\\) cannot equal stop loss \\(100\\.00\\)"
        ):
            position_sizer.calculate_position_size(
                account_value=sample_account_value,
                risk_category="normal",
                entry_price=Decimal("100.00"),
                stop_loss=Decimal("100.00"),
            )


class TestPositionSizerUtilityMethods:
    """Tests for position sizer utility methods."""
    
    @pytest.fixture
    def position_sizer(self) -> PositionSizer:
        """Create a position sizer instance for testing."""
        return PositionSizer()
    
    def test_get_risk_percentage(self, position_sizer: PositionSizer) -> None:
        """Test getting risk percentage for valid categories."""
        assert position_sizer.get_risk_percentage("small") == Decimal("1.0")
        assert position_sizer.get_risk_percentage("normal") == Decimal("2.0")
        assert position_sizer.get_risk_percentage("large") == Decimal("3.0")
        assert position_sizer.get_risk_percentage("NORMAL") == Decimal("2.0")
    
    def test_get_risk_percentage_invalid(self, position_sizer: PositionSizer) -> None:
        """Test getting risk percentage for invalid category."""
        with pytest.raises(InvalidPositionSizeError, match="Invalid risk category 'invalid'"):
            position_sizer.get_risk_percentage("invalid")
    
    def test_get_supported_risk_categories(self, position_sizer: PositionSizer) -> None:
        """Test getting supported risk categories."""
        categories = position_sizer.get_supported_risk_categories()
        assert len(categories) == 3
        assert "small" in categories
        assert "normal" in categories
        assert "large" in categories
    
    def test_calculate_max_position_size(
        self,
        position_sizer: PositionSizer,
        sample_account_value: Decimal,
        sample_entry_price: Decimal,
        sample_stop_loss: Decimal,
    ) -> None:
        """Test calculating maximum position size (using large risk)."""
        max_size = position_sizer.calculate_max_position_size(
            account_value=sample_account_value,
            entry_price=sample_entry_price,
            stop_loss=sample_stop_loss,
        )
        
        # Should be same as large risk category (3%)
        assert max_size == 60
    
    def test_preview_position_sizes(
        self,
        position_sizer: PositionSizer,
        sample_account_value: Decimal,
        sample_entry_price: Decimal,
        sample_stop_loss: Decimal,
    ) -> None:
        """Test previewing position sizes for all categories."""
        preview = position_sizer.preview_position_sizes(
            account_value=sample_account_value,
            entry_price=sample_entry_price,
            stop_loss=sample_stop_loss,
        )
        
        assert len(preview) == 3
        assert "small" in preview
        assert "normal" in preview
        assert "large" in preview
        
        assert preview["small"].position_size == 20
        assert preview["normal"].position_size == 40
        assert preview["large"].position_size == 60
    
    def test_preview_position_sizes_with_error(
        self,
        position_sizer: PositionSizer,
        sample_account_value: Decimal,
    ) -> None:
        """Test preview with invalid parameters doesn't crash."""
        # This should handle the error gracefully and log a warning
        preview = position_sizer.preview_position_sizes(
            account_value=sample_account_value,
            entry_price=Decimal("100.00"),
            stop_loss=Decimal("100.00"),  # Invalid: same as entry
        )
        
        # Should return empty dict when all calculations fail
        assert len(preview) == 0


class TestPositionSizerEdgeCases:
    """Tests for position sizer edge cases and boundary conditions."""
    
    @pytest.fixture
    def position_sizer(self) -> PositionSizer:
        """Create a position sizer instance for testing."""
        return PositionSizer()
    
    def test_very_small_account(self, position_sizer: PositionSizer) -> None:
        """Test with very small account value."""
        result = position_sizer.calculate_position_size(
            account_value=Decimal("1.00"),
            risk_category="small",
            entry_price=Decimal("100.00"),
            stop_loss=Decimal("99.00"),
        )
        
        # $1 * 1% = $0.01, $0.01 / $1.00 = 0.01 shares -> rounds to 1
        assert result.position_size == 1
        assert result.dollar_risk == Decimal("0.01")
    
    def test_very_large_account(self, position_sizer: PositionSizer) -> None:
        """Test with very large account value."""
        result = position_sizer.calculate_position_size(
            account_value=Decimal("1000000.00"),  # $1M
            risk_category="normal",
            entry_price=Decimal("100.00"),
            stop_loss=Decimal("95.00"),
        )
        
        # $1M * 2% = $20,000, $20,000 / $5 = 4,000 shares
        assert result.position_size == 4000
        assert result.dollar_risk == Decimal("20000.00")
    
    def test_very_small_price_difference(self, position_sizer: PositionSizer) -> None:
        """Test with very small price difference."""
        result = position_sizer.calculate_position_size(
            account_value=Decimal("10000.00"),
            risk_category="normal",
            entry_price=Decimal("100.0000"),
            stop_loss=Decimal("99.9999"),
        )
        
        # $200 / $0.0001 = 2,000,000 shares
        assert result.position_size == 2000000
        assert result.dollar_risk == Decimal("200.00")
    
    def test_decimal_precision_handling(self, position_sizer: PositionSizer) -> None:
        """Test handling of decimal precision in calculations."""
        result = position_sizer.calculate_position_size(
            account_value=Decimal("10000.00"),
            risk_category="normal",
            entry_price=Decimal("123.4567"),
            stop_loss=Decimal("120.1234"),
        )
        
        # Price diff: $3.3333, $200 / $3.3333 = 60.0006 -> 60 shares
        assert result.position_size == 60
        assert result.dollar_risk == Decimal("200.00")
        
        # Verify dollar risk is rounded to cents
        assert result.dollar_risk.as_tuple().exponent == -2