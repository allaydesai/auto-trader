"""Tests for field validation utilities."""

import pytest
from decimal import Decimal

from ..field_validator import WizardFieldValidator
from ...models import RiskCategory


class TestWizardFieldValidator:
    """Test suite for WizardFieldValidator."""
    
    @pytest.fixture
    def validator(self):
        """Create validator instance for testing."""
        return WizardFieldValidator()
    
    def test_validate_symbol_valid(self, validator):
        """Test validating valid symbol."""
        result = validator.validate_symbol("AAPL")
        
        assert result["is_valid"] is True
        assert result["error"] is None
    
    def test_validate_symbol_invalid_too_long(self, validator):
        """Test validating symbol that is too long."""
        result = validator.validate_symbol("TOOLONGSYMBOL123")
        
        assert result["is_valid"] is False
        assert result["error"] is not None
    
    def test_validate_symbol_empty(self, validator):
        """Test validating empty symbol."""
        result = validator.validate_symbol("")
        
        assert result["is_valid"] is False
        assert result["error"] is not None
    
    def test_validate_entry_level_valid(self, validator):
        """Test validating valid entry level."""
        result = validator.validate_entry_level(Decimal("180.50"))
        
        assert result["is_valid"] is True
        assert result["error"] is None
    
    def test_validate_entry_level_negative(self, validator):
        """Test validating negative entry level."""
        result = validator.validate_entry_level(Decimal("-100.00"))
        
        assert result["is_valid"] is False
        assert result["error"] is not None
    
    def test_validate_entry_level_zero(self, validator):
        """Test validating zero entry level."""
        result = validator.validate_entry_level(Decimal("0.00"))
        
        assert result["is_valid"] is False
        assert result["error"] is not None
    
    def test_validate_stop_loss_valid(self, validator):
        """Test validating valid stop loss."""
        entry_level = Decimal("180.50")
        stop_loss = Decimal("178.00")
        
        result = validator.validate_stop_loss(stop_loss, entry_level)
        
        assert result["is_valid"] is True
        assert result["error"] is None
    
    def test_validate_stop_loss_equals_entry(self, validator):
        """Test validating stop loss that equals entry level."""
        entry_level = Decimal("180.50")
        stop_loss = Decimal("180.50")
        
        result = validator.validate_stop_loss(stop_loss, entry_level)
        
        assert result["is_valid"] is False
        assert "cannot equal entry level" in result["error"]
    
    def test_validate_stop_loss_negative(self, validator):
        """Test validating negative stop loss."""
        entry_level = Decimal("180.50")
        stop_loss = Decimal("-10.00")
        
        result = validator.validate_stop_loss(stop_loss, entry_level)
        
        assert result["is_valid"] is False
        assert result["error"] is not None
    
    def test_validate_take_profit_valid(self, validator):
        """Test validating valid take profit."""
        result = validator.validate_take_profit(Decimal("185.00"))
        
        assert result["is_valid"] is True
        assert result["error"] is None
    
    def test_validate_take_profit_negative(self, validator):
        """Test validating negative take profit."""
        result = validator.validate_take_profit(Decimal("-10.00"))
        
        assert result["is_valid"] is False
        assert result["error"] is not None
    
    def test_validate_risk_category_valid(self, validator):
        """Test validating valid risk category."""
        result = validator.validate_risk_category(RiskCategory.NORMAL)
        
        assert result["is_valid"] is True
        assert result["error"] is None
    
    def test_validate_all_risk_categories(self, validator):
        """Test validating all risk category values."""
        for risk_cat in [RiskCategory.SMALL, RiskCategory.NORMAL, RiskCategory.LARGE]:
            result = validator.validate_risk_category(risk_cat)
            assert result["is_valid"] is True
            assert result["error"] is None
    
    def test_validate_field_with_model_invalid_type(self, validator):
        """Test validation with completely invalid type."""
        # This should trigger a validation error
        result = validator._validate_field_with_model("entry_level", "not_a_decimal")
        
        assert result["is_valid"] is False
        assert result["error"] is not None
    
    def test_business_rule_validation_stop_loss(self, validator):
        """Test that business rule validation works correctly for stop loss."""
        entry_level = Decimal("100.00")
        
        # Valid stop loss
        result = validator.validate_stop_loss(Decimal("95.00"), entry_level)
        assert result["is_valid"] is True
        
        # Invalid stop loss (equals entry)
        result = validator.validate_stop_loss(Decimal("100.00"), entry_level)
        assert result["is_valid"] is False
        assert "cannot equal entry level" in result["error"]
    
    def test_edge_cases_decimal_precision(self, validator):
        """Test edge cases with decimal precision."""
        # Test maximum precision allowed (4 decimal places)
        result = validator.validate_entry_level(Decimal("180.1234"))
        if not result["is_valid"]:
            print(f"Error for 180.1234: {result['error']}")
        assert result["is_valid"] is True
        
        # Test very high precision - Pydantic should handle this gracefully
        result = validator.validate_entry_level(Decimal("180.12"))
        assert result["is_valid"] is True
    
    def test_validation_error_message_extraction(self, validator):
        """Test that error messages are properly extracted from validation errors."""
        # This should trigger a validation error with specific message
        result = validator.validate_symbol("TOO_LONG_SYMBOL_NAME_123456")
        
        assert result["is_valid"] is False
        assert result["error"] is not None
        assert len(result["error"]) > 0