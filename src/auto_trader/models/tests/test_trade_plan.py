"""Unit tests for trade plan data models."""

import pytest
from datetime import datetime
from decimal import Decimal
from pydantic import ValidationError

from auto_trader.models.trade_plan import (
    TradePlan,
    ExecutionFunction,
    TradePlanStatus,
    RiskCategory,
    TradePlanValidationError,
    ValidationResult,
)


class TestExecutionFunction:
    """Test ExecutionFunction model validation."""
    
    def test_valid_execution_function(self):
        """Test creating valid execution function."""
        func = ExecutionFunction(
            function_type="close_above",
            timeframe="15min",
            parameters={"threshold": 180.50},
        )
        
        assert func.function_type == "close_above"
        assert func.timeframe == "15min"
        assert func.parameters == {"threshold": 180.50}
        assert func.last_evaluated is None
    
    def test_invalid_function_type(self):
        """Test validation fails for unsupported function type."""
        with pytest.raises(ValidationError) as exc_info:
            ExecutionFunction(
                function_type="invalid_function",
                timeframe="15min",
                parameters={},
            )
        
        error = str(exc_info.value)
        assert "Unsupported function_type 'invalid_function'" in error
        assert "close_above" in error
    
    def test_invalid_timeframe(self):
        """Test validation fails for invalid timeframe."""
        with pytest.raises(ValidationError) as exc_info:
            ExecutionFunction(
                function_type="close_above",
                timeframe="invalid",
                parameters={},
            )
        
        error = str(exc_info.value)
        assert "String should match pattern" in error
    
    def test_valid_timeframes(self):
        """Test all valid timeframe patterns."""
        valid_timeframes = [
            "1min", "5min", "15min", "30min", "60min", "240min", "1440min",
            "1h", "4h", "1440h", "1d"
        ]
        
        for timeframe in valid_timeframes:
            func = ExecutionFunction(
                function_type="close_above",
                timeframe=timeframe,
                parameters={},
            )
            assert func.timeframe == timeframe
    
    def test_function_immutability(self):
        """Test that execution function is immutable."""
        func = ExecutionFunction(
            function_type="close_above",
            timeframe="15min",
            parameters={},
        )
        
        with pytest.raises(ValidationError):
            func.function_type = "close_below"


class TestTradePlan:
    """Test TradePlan model validation."""
    
    @pytest.fixture
    def valid_trade_plan_data(self):
        """Provide valid trade plan data."""
        return {
            "plan_id": "AAPL_20250815_001",
            "symbol": "AAPL",
            "entry_level": Decimal("180.50"),
            "stop_loss": Decimal("178.00"),
            "take_profit": Decimal("185.00"),
            "risk_category": RiskCategory.NORMAL,
            "entry_function": ExecutionFunction(
                function_type="close_above",
                timeframe="15min",
                parameters={"threshold": 180.50},
            ),
            "exit_function": ExecutionFunction(
                function_type="stop_loss_take_profit",
                timeframe="1min",
                parameters={},
            ),
        }
    
    def test_valid_trade_plan_creation(self, valid_trade_plan_data):
        """Test creating valid trade plan."""
        plan = TradePlan(**valid_trade_plan_data)
        
        assert plan.plan_id == "AAPL_20250815_001"
        assert plan.symbol == "AAPL"
        assert plan.entry_level == Decimal("180.50")
        assert plan.stop_loss == Decimal("178.00")
        assert plan.take_profit == Decimal("185.00")
        assert plan.risk_category == RiskCategory.NORMAL
        assert plan.status == TradePlanStatus.AWAITING_ENTRY
        assert plan.calculated_position_size is None
        assert plan.dollar_risk is None
        assert isinstance(plan.created_at, datetime)
    
    def test_invalid_symbol_format(self, valid_trade_plan_data):
        """Test symbol validation with various invalid formats."""
        invalid_symbols = [
            "aapl",      # lowercase
            "AAPL123",   # contains numbers
            "AAPL-USD",  # contains hyphen
            "AAPL.USD",  # contains dot
            "",          # empty
            "TOOLONGNAME",  # too long (>10 chars)
        ]
        
        for invalid_symbol in invalid_symbols:
            data = valid_trade_plan_data.copy()
            data["symbol"] = invalid_symbol
            
            with pytest.raises(ValidationError) as exc_info:
                TradePlan(**data)
            
            error = str(exc_info.value)
            assert any(phrase in error for phrase in [
                "Invalid symbol", "String should match pattern", 
                "string_too_short", "string_too_long"
            ])
    
    def test_valid_symbols(self, valid_trade_plan_data):
        """Test valid symbol formats."""
        valid_symbols = ["A", "AAPL", "MSFT", "GOOGL", "BERKSHIREA"]
        
        for symbol in valid_symbols:
            data = valid_trade_plan_data.copy()
            data["symbol"] = symbol
            plan = TradePlan(**data)
            assert plan.symbol == symbol
    
    def test_invalid_price_precision(self, valid_trade_plan_data):
        """Test price precision validation."""
        # More than 4 decimal places
        invalid_price = Decimal("180.123456")
        
        for price_field in ["entry_level", "stop_loss", "take_profit"]:
            data = valid_trade_plan_data.copy()
            data[price_field] = invalid_price
            
            with pytest.raises(ValidationError) as exc_info:
                TradePlan(**data)
            
            error = str(exc_info.value)
            assert "decimal_max_places" in error or "too many decimal places" in error
    
    def test_zero_risk_validation(self, valid_trade_plan_data):
        """Test prevention of zero-risk trades."""
        data = valid_trade_plan_data.copy()
        data["entry_level"] = Decimal("180.00")
        data["stop_loss"] = Decimal("180.00")  # Same as entry
        
        with pytest.raises(ValidationError) as exc_info:
            TradePlan(**data)
        
        error = str(exc_info.value)
        assert "cannot equal stop_loss" in error
        assert "zero-risk trades" in error
    
    def test_long_position_price_validation(self, valid_trade_plan_data):
        """Test valid long position price relationships."""
        # Valid long: stop < entry < target
        data = valid_trade_plan_data.copy()
        data["entry_level"] = Decimal("180.00")
        data["stop_loss"] = Decimal("178.00")
        data["take_profit"] = Decimal("185.00")
        
        plan = TradePlan(**data)
        assert plan.stop_loss < plan.entry_level < plan.take_profit
    
    def test_short_position_price_validation(self, valid_trade_plan_data):
        """Test valid short position price relationships."""
        # Valid short: target < entry < stop
        data = valid_trade_plan_data.copy()
        data["entry_level"] = Decimal("180.00")
        data["stop_loss"] = Decimal("182.00")
        data["take_profit"] = Decimal("175.00")
        
        plan = TradePlan(**data)
        assert plan.take_profit < plan.entry_level < plan.stop_loss
    
    def test_invalid_price_relationships(self, valid_trade_plan_data):
        """Test invalid price relationship scenarios."""
        invalid_scenarios = [
            # Long position with wrong stop_loss placement
            {
                "entry_level": Decimal("180.00"),
                "stop_loss": Decimal("185.00"),  # stop > entry (wrong for long)
                "take_profit": Decimal("190.00"),
            },
            # Short position with wrong stop_loss placement  
            {
                "entry_level": Decimal("180.00"),
                "stop_loss": Decimal("175.00"),  # stop < entry (wrong for short)
                "take_profit": Decimal("170.00"),
            },
            # Completely illogical: entry equals take_profit
            {
                "entry_level": Decimal("180.00"),
                "stop_loss": Decimal("178.00"),
                "take_profit": Decimal("180.00"),  # target = entry (no profit)
            },
        ]
        
        for scenario in invalid_scenarios:
            data = valid_trade_plan_data.copy()
            data.update(scenario)
            
            with pytest.raises(ValidationError) as exc_info:
                TradePlan(**data)
            
            error = str(exc_info.value)
            assert "Invalid" in error and "price relationship" in error
    
    def test_invalid_plan_id_format(self, valid_trade_plan_data):
        """Test plan_id format validation."""
        invalid_plan_ids = [
            "aapl_20250815_001",  # lowercase
            "AAPL-20250815-001",  # hyphens
            "AAPL 20250815 001",  # spaces
            "AAPL@20250815#001",  # special chars
        ]
        
        for invalid_id in invalid_plan_ids:
            data = valid_trade_plan_data.copy()
            data["plan_id"] = invalid_id
            
            with pytest.raises(ValidationError) as exc_info:
                TradePlan(**data)
            
            error = str(exc_info.value)
            assert "Invalid plan_id" in error or "String should match pattern" in error
    
    def test_negative_prices_rejected(self, valid_trade_plan_data):
        """Test that negative prices are rejected."""
        for price_field in ["entry_level", "stop_loss", "take_profit"]:
            data = valid_trade_plan_data.copy()
            data[price_field] = Decimal("-10.00")
            
            with pytest.raises(ValidationError) as exc_info:
                TradePlan(**data)
            
            error = str(exc_info.value)
            assert "greater than 0" in error
    
    def test_risk_category_validation(self, valid_trade_plan_data):
        """Test risk category enum validation."""
        # Valid risk categories
        for risk_cat in [RiskCategory.SMALL, RiskCategory.NORMAL, RiskCategory.LARGE]:
            data = valid_trade_plan_data.copy()
            data["risk_category"] = risk_cat
            plan = TradePlan(**data)
            assert plan.risk_category == risk_cat
    
    def test_optional_fields_default_values(self, valid_trade_plan_data):
        """Test optional fields have correct defaults."""
        plan = TradePlan(**valid_trade_plan_data)
        
        assert plan.status == TradePlanStatus.AWAITING_ENTRY
        assert plan.calculated_position_size is None
        assert plan.dollar_risk is None
        assert isinstance(plan.created_at, datetime)
        assert plan.updated_at is None


class TestTradePlanValidationError:
    """Test custom validation error functionality."""
    
    def test_basic_error_creation(self):
        """Test creating basic validation error."""
        error = TradePlanValidationError("Invalid symbol format")
        assert str(error) == "Invalid symbol format"
    
    def test_error_with_field_context(self):
        """Test error with field information."""
        error = TradePlanValidationError(
            "Invalid value",
            field="symbol",
            line_number=5,
        )
        assert "Line 5 - Field 'symbol': Invalid value" in str(error)
    
    def test_error_with_suggestion(self):
        """Test error with fix suggestion."""
        error = TradePlanValidationError(
            "Invalid risk category",
            field="risk_category",
            suggestion="Change 'medium' to 'normal'",
        )
        result = str(error)
        assert "Invalid risk category" in result
        assert "Fix: Change 'medium' to 'normal'" in result


class TestValidationResult:
    """Test validation result functionality."""
    
    def test_valid_result(self):
        """Test creating valid validation result."""
        result = ValidationResult(
            is_valid=True,
            plan_id="AAPL_20250815_001",
        )
        
        assert result.is_valid is True
        assert result.plan_id == "AAPL_20250815_001"
        assert result.error_count == 0
        assert result.get_error_summary() == "No validation errors"
    
    def test_invalid_result_with_errors(self):
        """Test validation result with errors."""
        errors = [
            TradePlanValidationError("Error 1", field="symbol"),
            TradePlanValidationError("Error 2", field="price"),
        ]
        
        result = ValidationResult(
            is_valid=False,
            errors=errors,
        )
        
        assert result.is_valid is False
        assert result.plan_id is None
        assert result.error_count == 2
        
        summary = result.get_error_summary()
        assert "Found 2 validation error(s)" in summary
        assert "Error 1" in summary
        assert "Error 2" in summary