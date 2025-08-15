"""Unit tests for validation engine."""

import pytest
import tempfile
from pathlib import Path

from auto_trader.models.validation_engine import ValidationEngine


class TestValidationEngine:
    """Test ValidationEngine functionality."""
    
    @pytest.fixture
    def engine(self):
        """Provide a fresh validation engine."""
        return ValidationEngine()
    
    @pytest.fixture
    def valid_yaml_content(self):
        """Provide valid YAML trade plan content."""
        return """
plan_id: "AAPL_20250815_001"
symbol: "AAPL"
entry_level: 180.50
stop_loss: 178.00
take_profit: 185.00
risk_category: "normal"
entry_function:
  function_type: "close_above"
  timeframe: "15min"
  parameters:
    threshold: 180.50
exit_function:
  function_type: "stop_loss_take_profit"
  timeframe: "1min"
  parameters: {}
"""
    
    def test_valid_yaml_validation(self, engine, valid_yaml_content):
        """Test validation of valid YAML content."""
        result = engine.validate_yaml_content(valid_yaml_content)
        
        assert result.is_valid is True
        assert result.error_count == 0
        assert result.plan_id == "AAPL_20250815_001"
    
    def test_empty_yaml_content(self, engine):
        """Test validation of empty YAML content."""
        result = engine.validate_yaml_content("")
        
        assert result.is_valid is False
        assert result.error_count == 1
        assert "Empty YAML content" in str(result.errors[0])
    
    def test_invalid_yaml_syntax(self, engine):
        """Test validation of invalid YAML syntax."""
        invalid_yaml = """
plan_id: "TEST_001"
symbol: "AAPL"
entry_level: 180.50
    invalid: indentation
stop_loss: 178.00
"""
        result = engine.validate_yaml_content(invalid_yaml)
        
        assert result.is_valid is False
        assert result.error_count == 1
        assert "YAML syntax error" in str(result.errors[0])
    
    def test_missing_required_fields(self, engine):
        """Test validation with missing required fields."""
        incomplete_yaml = """
plan_id: "TEST_001"
symbol: "AAPL"
# Missing entry_level, stop_loss, take_profit, etc.
"""
        result = engine.validate_yaml_content(incomplete_yaml)
        
        assert result.is_valid is False
        assert result.error_count >= 1
        assert any("Missing required fields" in str(error) for error in result.errors)
    
    def test_invalid_symbol_format(self, engine, valid_yaml_content):
        """Test validation with invalid symbol format."""
        invalid_yaml = valid_yaml_content.replace('symbol: "AAPL"', 'symbol: "aapl123"')
        result = engine.validate_yaml_content(invalid_yaml)
        
        assert result.is_valid is False
        assert any("Invalid symbol format" in str(error) for error in result.errors)
    
    def test_invalid_plan_id_format(self, engine, valid_yaml_content):
        """Test validation with invalid plan_id format."""
        invalid_yaml = valid_yaml_content.replace(
            'plan_id: "AAPL_20250815_001"', 
            'plan_id: "aapl-2025-08-15"'
        )
        result = engine.validate_yaml_content(invalid_yaml)
        
        assert result.is_valid is False
        assert any("Invalid plan_id format" in str(error) for error in result.errors)
    
    def test_negative_price_validation(self, engine, valid_yaml_content):
        """Test validation with negative prices."""
        invalid_yaml = valid_yaml_content.replace('entry_level: 180.50', 'entry_level: -180.50')
        result = engine.validate_yaml_content(invalid_yaml)
        
        assert result.is_valid is False
        assert any("must be positive" in str(error) for error in result.errors)
    
    def test_excessive_decimal_places(self, engine, valid_yaml_content):
        """Test validation with too many decimal places."""
        invalid_yaml = valid_yaml_content.replace('entry_level: 180.50', 'entry_level: 180.123456')
        result = engine.validate_yaml_content(invalid_yaml)
        
        assert result.is_valid is False
        assert any("too many decimal places" in str(error) for error in result.errors)
    
    def test_invalid_risk_category(self, engine, valid_yaml_content):
        """Test validation with invalid risk category."""
        invalid_yaml = valid_yaml_content.replace('risk_category: "normal"', 'risk_category: "medium"')
        result = engine.validate_yaml_content(invalid_yaml)
        
        assert result.is_valid is False
        assert any("Invalid risk_category" in str(error) for error in result.errors)
    
    def test_unsupported_function_type(self, engine, valid_yaml_content):
        """Test validation with unsupported function type."""
        invalid_yaml = valid_yaml_content.replace(
            'function_type: "close_above"', 
            'function_type: "unsupported_function"'
        )
        result = engine.validate_yaml_content(invalid_yaml)
        
        assert result.is_valid is False
        assert any("Unsupported function_type" in str(error) for error in result.errors)
    
    def test_unsupported_timeframe(self, engine, valid_yaml_content):
        """Test validation with unsupported timeframe."""
        invalid_yaml = valid_yaml_content.replace('timeframe: "15min"', 'timeframe: "2min"')
        result = engine.validate_yaml_content(invalid_yaml)
        
        assert result.is_valid is False
        assert any("Unsupported timeframe" in str(error) for error in result.errors)
    
    def test_duplicate_plan_ids(self, engine):
        """Test validation with duplicate plan IDs."""
        yaml_with_duplicates = """
- plan_id: "AAPL_001"
  symbol: "AAPL"
  entry_level: 180.50
  stop_loss: 178.00
  take_profit: 185.00
  risk_category: "normal"
  entry_function:
    function_type: "close_above"
    timeframe: "15min"
    parameters: {}
  exit_function:
    function_type: "stop_loss_take_profit"
    timeframe: "1min"
    parameters: {}

- plan_id: "AAPL_001"  # Duplicate ID
  symbol: "MSFT"
  entry_level: 300.00
  stop_loss: 295.00
  take_profit: 310.00
  risk_category: "small"
  entry_function:
    function_type: "close_below"
    timeframe: "30min"
    parameters: {}
  exit_function:
    function_type: "stop_loss_take_profit"
    timeframe: "1min"
    parameters: {}
"""
        result = engine.validate_yaml_content(yaml_with_duplicates)
        
        assert result.is_valid is False
        assert any("Duplicate plan_id" in str(error) for error in result.errors)
    
    def test_multiple_plans_validation(self, engine):
        """Test validation of multiple plans in a list."""
        multiple_plans_yaml = """
- plan_id: "AAPL_001"
  symbol: "AAPL"
  entry_level: 180.50
  stop_loss: 178.00
  take_profit: 185.00
  risk_category: "normal"
  entry_function:
    function_type: "close_above"
    timeframe: "15min"
    parameters: {}
  exit_function:
    function_type: "stop_loss_take_profit"
    timeframe: "1min"
    parameters: {}

- plan_id: "MSFT_001"
  symbol: "MSFT"
  entry_level: 300.00
  stop_loss: 295.00
  take_profit: 310.00
  risk_category: "small"
  entry_function:
    function_type: "close_below"
    timeframe: "30min"
    parameters: {}
  exit_function:
    function_type: "stop_loss_take_profit"
    timeframe: "1min"
    parameters: {}
"""
        result = engine.validate_yaml_content(multiple_plans_yaml)
        
        assert result.is_valid is True
        assert result.error_count == 0
    
    def test_file_validation_success(self, engine, valid_yaml_content):
        """Test successful file validation."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(valid_yaml_content)
            temp_path = Path(f.name)
        
        try:
            result = engine.validate_file(temp_path)
            assert result.is_valid is True
            assert result.error_count == 0
        finally:
            temp_path.unlink()
    
    def test_file_not_found(self, engine):
        """Test validation of non-existent file."""
        non_existent_path = Path("/non/existent/file.yaml")
        result = engine.validate_file(non_existent_path)
        
        assert result.is_valid is False
        assert result.error_count == 1
        assert "File not found" in str(result.errors[0])
    
    def test_invalid_file_extension(self, engine):
        """Test validation of file with invalid extension."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write("some content")
            temp_path = Path(f.name)
        
        try:
            result = engine.validate_file(temp_path)
            assert result.is_valid is False
            assert "Invalid file extension" in str(result.errors[0])
        finally:
            temp_path.unlink()
    
    def test_plan_id_tracking(self, engine, valid_yaml_content):
        """Test plan ID tracking and reset functionality."""
        # Initially empty
        assert len(engine.get_loaded_plan_ids()) == 0
        
        # Validate a plan
        result = engine.validate_yaml_content(valid_yaml_content)
        assert result.is_valid is True
        assert "AAPL_20250815_001" in engine.get_loaded_plan_ids()
        
        # Reset and check
        engine.reset_plan_ids()
        assert len(engine.get_loaded_plan_ids()) == 0
    
    def test_execution_function_validation(self, engine):
        """Test detailed execution function validation."""
        yaml_with_invalid_function = """
plan_id: "TEST_001"
symbol: "AAPL"
entry_level: 180.50
stop_loss: 178.00
take_profit: 185.00
risk_category: "normal"
entry_function:
  function_type: "close_above"
  timeframe: "15min"
  parameters: "invalid_parameters"  # Should be object, not string
exit_function:
  function_type: "stop_loss_take_profit"
  timeframe: "1min"
  parameters: {}
"""
        result = engine.validate_yaml_content(yaml_with_invalid_function)
        
        assert result.is_valid is False
        assert any("parameters" in str(error) and "must be an object" in str(error) 
                  for error in result.errors)
    
    def test_price_relationship_validation(self, engine):
        """Test price relationship validation through the engine."""
        yaml_with_invalid_prices = """
plan_id: "TEST_001"
symbol: "AAPL"
entry_level: 180.50
stop_loss: 180.50  # Same as entry - zero risk
take_profit: 185.00
risk_category: "normal"
entry_function:
  function_type: "close_above"
  timeframe: "15min"
  parameters: {}
exit_function:
  function_type: "stop_loss_take_profit"
  timeframe: "1min"
  parameters: {}
"""
        result = engine.validate_yaml_content(yaml_with_invalid_prices)
        
        assert result.is_valid is False
        assert any("cannot equal stop_loss" in str(error) for error in result.errors)
    
    def test_comprehensive_error_aggregation(self, engine):
        """Test that all errors are collected, not just the first one."""
        yaml_with_multiple_errors = """
plan_id: "invalid-plan-id"  # Invalid format
symbol: "aapl123"           # Invalid symbol  
entry_level: -180.50        # Negative price
stop_loss: 178.123456       # Too many decimals
take_profit: 185.00
risk_category: "invalid"    # Invalid category
entry_function:
  function_type: "invalid_function"  # Invalid function
  timeframe: "invalid_time"          # Invalid timeframe
  parameters: {}
exit_function:
  function_type: "stop_loss_take_profit"
  timeframe: "1min"
  parameters: {}
"""
        result = engine.validate_yaml_content(yaml_with_multiple_errors)
        
        assert result.is_valid is False
        assert result.error_count >= 5  # Should catch multiple errors
        
        error_messages = [str(error) for error in result.errors]
        assert any("Invalid plan_id format" in msg for msg in error_messages)
        assert any("Invalid symbol format" in msg for msg in error_messages)
        assert any("must be positive" in msg for msg in error_messages)
        assert any("too many decimal places" in msg for msg in error_messages)
        assert any("Invalid risk_category" in msg for msg in error_messages)