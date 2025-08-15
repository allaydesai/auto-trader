"""Unit tests for error reporting system."""

import pytest
import yaml
from pathlib import Path

from auto_trader.models.error_reporting import (
    ErrorFormatter,
    YAMLErrorEnhancer,
    ValidationReporter,
    ErrorCodeGenerator,
)
from auto_trader.models.trade_plan import TradePlanValidationError, ValidationResult


class TestErrorFormatter:
    """Test ErrorFormatter functionality."""
    
    def test_format_for_console_no_errors(self):
        """Test console formatting with no errors."""
        result = ErrorFormatter.format_for_console([])
        assert result == "✅ No validation errors found"
    
    def test_format_for_console_single_error(self):
        """Test console formatting with single error."""
        error = TradePlanValidationError(
            "Invalid symbol format",
            field="symbol",
            line_number=5,
            suggestion="Use uppercase letters only"
        )
        
        result = ErrorFormatter.format_for_console([error])
        
        assert "❌ Found 1 validation error(s)" in result
        assert "Line 5 - Field 'symbol'" in result
        assert "Invalid symbol format" in result
        assert "💡 Fix: Use uppercase letters only" in result
    
    def test_format_for_console_multiple_errors(self):
        """Test console formatting with multiple errors."""
        errors = [
            TradePlanValidationError("Error 1", field="field1"),
            TradePlanValidationError("Error 2", field="field2"),
        ]
        
        result = ErrorFormatter.format_for_console(errors)
        
        assert "❌ Found 2 validation error(s)" in result
        assert "1." in result
        assert "2." in result
        assert "Error 1" in result
        assert "Error 2" in result
    
    def test_format_for_cli_valid_result(self):
        """Test CLI formatting for valid result."""
        result = ValidationResult(is_valid=True, plan_id="TEST_001")
        formatted = ErrorFormatter.format_for_cli(result)
        
        assert "✅ Validation passed" in formatted
    
    def test_format_for_cli_invalid_result(self):
        """Test CLI formatting for invalid result."""
        errors = [TradePlanValidationError("Test error")]
        result = ValidationResult(is_valid=False, errors=errors)
        
        formatted = ErrorFormatter.format_for_cli(result, Path("test.yaml"))
        
        assert "❌ Validation failed in test.yaml" in formatted
        assert "Test error" in formatted
    
    def test_format_for_json(self):
        """Test JSON formatting of errors."""
        errors = [
            TradePlanValidationError(
                "Test error",
                field="test_field",
                line_number=10,
                suggestion="Fix suggestion"
            )
        ]
        
        json_errors = ErrorFormatter.format_for_json(errors)
        
        assert len(json_errors) == 1
        assert json_errors[0]["message"] == "Test error"
        assert json_errors[0]["field"] == "test_field"
        assert json_errors[0]["line_number"] == 10
        assert json_errors[0]["suggestion"] == "Fix suggestion"
        assert json_errors[0]["severity"] == "error"


class TestYAMLErrorEnhancer:
    """Test YAMLErrorEnhancer functionality."""
    
    def test_enhance_yaml_error_with_line_info(self):
        """Test enhancing YAML error with line information."""
        yaml_content = """
plan_id: "TEST_001"
symbol: "AAPL"
    invalid_indentation: value
entry_level: 180.50
"""
        
        try:
            yaml.safe_load(yaml_content)
        except yaml.YAMLError as e:
            enhanced_error = YAMLErrorEnhancer.enhance_yaml_error(yaml_content, e)
            
            assert "YAML syntax error" in enhanced_error.message
            assert enhanced_error.line_number is not None
            assert enhanced_error.suggestion is not None
    
    def test_enhance_yaml_error_without_line_info(self):
        """Test enhancing YAML error without line information."""
        yaml_content = "invalid: yaml: content"
        
        # Create a mock YAML error without problem_mark
        class MockYAMLError(yaml.YAMLError):
            def __str__(self):
                return "mock error"
        
        mock_error = MockYAMLError()
        enhanced_error = YAMLErrorEnhancer.enhance_yaml_error(yaml_content, mock_error)
        
        assert "YAML syntax error" in enhanced_error.message
        assert enhanced_error.line_number is None
        assert enhanced_error.suggestion is not None
    
    def test_generate_yaml_suggestion_indentation(self):
        """Test YAML suggestion generation for indentation errors."""
        suggestion = YAMLErrorEnhancer._generate_yaml_suggestion("indentation error")
        assert "indentation" in suggestion.lower()
    
    def test_generate_yaml_suggestion_duplicate(self):
        """Test YAML suggestion generation for duplicate key errors."""
        suggestion = YAMLErrorEnhancer._generate_yaml_suggestion("duplicate key error")
        assert "duplicate" in suggestion.lower()
    
    def test_generate_yaml_suggestion_tab(self):
        """Test YAML suggestion generation for tab errors."""
        suggestion = YAMLErrorEnhancer._generate_yaml_suggestion("tab character found")
        assert "tab" in suggestion.lower() and "spaces" in suggestion.lower()


class TestValidationReporter:
    """Test ValidationReporter functionality."""
    
    @pytest.fixture
    def reporter(self):
        """Provide a fresh validation reporter."""
        return ValidationReporter()
    
    def test_add_valid_result(self, reporter):
        """Test adding valid validation result."""
        result = ValidationResult(is_valid=True, plan_id="TEST_001")
        reporter.add_result(result, Path("test.yaml"))
        
        summary = reporter.get_summary()
        assert summary["total_files"] == 1
        assert summary["valid_files"] == 1
        assert summary["invalid_files"] == 0
        assert summary["total_errors"] == 0
        assert summary["success_rate"] == 1.0
    
    def test_add_invalid_result(self, reporter):
        """Test adding invalid validation result."""
        errors = [TradePlanValidationError("Test error")]
        result = ValidationResult(is_valid=False, errors=errors)
        reporter.add_result(result, Path("test.yaml"))
        
        summary = reporter.get_summary()
        assert summary["total_files"] == 1
        assert summary["valid_files"] == 0
        assert summary["invalid_files"] == 1
        assert summary["total_errors"] == 1
        assert summary["success_rate"] == 0.0
    
    def test_multiple_results(self, reporter):
        """Test adding multiple validation results."""
        # Add valid result
        valid_result = ValidationResult(is_valid=True, plan_id="VALID_001")
        reporter.add_result(valid_result, Path("valid.yaml"))
        
        # Add invalid result
        errors = [TradePlanValidationError("Error 1"), TradePlanValidationError("Error 2")]
        invalid_result = ValidationResult(is_valid=False, errors=errors)
        reporter.add_result(invalid_result, Path("invalid.yaml"))
        
        summary = reporter.get_summary()
        assert summary["total_files"] == 2
        assert summary["valid_files"] == 1
        assert summary["invalid_files"] == 1
        assert summary["total_errors"] == 2
        assert summary["success_rate"] == 0.5
    
    def test_format_summary_report_no_results(self, reporter):
        """Test summary report with no results."""
        report = reporter.format_summary_report()
        assert "No validation results to report" in report
    
    def test_format_summary_report_with_errors(self, reporter):
        """Test summary report with validation errors."""
        errors = [TradePlanValidationError("Test error", field="test_field")]
        result = ValidationResult(is_valid=False, errors=errors)
        reporter.add_result(result, Path("test.yaml"))
        
        report = reporter.format_summary_report()
        
        assert "TRADE PLAN VALIDATION SUMMARY" in report
        assert "Total files processed: 1" in report
        assert "Invalid files: 1" in report
        assert "DETAILED ERROR REPORT" in report
        assert "test.yaml" in report
        assert "Test error" in report
    
    def test_get_all_errors(self, reporter):
        """Test getting all errors from multiple results."""
        # Add first result with 1 error
        errors1 = [TradePlanValidationError("Error 1")]
        result1 = ValidationResult(is_valid=False, errors=errors1)
        reporter.add_result(result1)
        
        # Add second result with 2 errors
        errors2 = [TradePlanValidationError("Error 2"), TradePlanValidationError("Error 3")]
        result2 = ValidationResult(is_valid=False, errors=errors2)
        reporter.add_result(result2)
        
        all_errors = reporter.get_all_errors()
        assert len(all_errors) == 3
        error_messages = [str(error) for error in all_errors]
        assert "Error 1" in error_messages
        assert "Error 2" in error_messages
        assert "Error 3" in error_messages
    
    def test_clear_results(self, reporter):
        """Test clearing reporter results."""
        result = ValidationResult(is_valid=True, plan_id="TEST_001")
        reporter.add_result(result)
        
        assert reporter.get_summary()["total_files"] == 1
        
        reporter.clear()
        assert reporter.get_summary()["total_files"] == 0


class TestErrorCodeGenerator:
    """Test ErrorCodeGenerator functionality."""
    
    def test_categorize_yaml_syntax_error(self):
        """Test categorizing YAML syntax errors."""
        error = TradePlanValidationError("YAML syntax error: invalid format")
        code = ErrorCodeGenerator.categorize_error(error)
        assert code == "Y001"
    
    def test_categorize_missing_field_error(self):
        """Test categorizing missing field errors."""
        error = TradePlanValidationError("Missing required fields: symbol, entry_level")
        code = ErrorCodeGenerator.categorize_error(error)
        assert code == "F001"
    
    def test_categorize_invalid_format_error(self):
        """Test categorizing invalid format errors."""
        error = TradePlanValidationError("Invalid symbol format 'aapl123'")
        code = ErrorCodeGenerator.categorize_error(error)
        assert code == "F002"
    
    def test_categorize_duplicate_error(self):
        """Test categorizing duplicate errors."""
        error = TradePlanValidationError("Duplicate plan_id 'TEST_001'")
        code = ErrorCodeGenerator.categorize_error(error)
        assert code == "D001"
    
    def test_categorize_business_rule_error(self):
        """Test categorizing business rule errors."""
        error = TradePlanValidationError("entry_level cannot equal stop_loss")
        code = ErrorCodeGenerator.categorize_error(error)
        assert code == "B001"
    
    def test_categorize_file_access_error(self):
        """Test categorizing file access errors."""
        error = TradePlanValidationError("File not found: /path/to/file.yaml")
        code = ErrorCodeGenerator.categorize_error(error)
        assert code == "A001"
    
    def test_categorize_generic_value_error(self):
        """Test categorizing generic value errors."""
        error = TradePlanValidationError("Price must be positive")
        code = ErrorCodeGenerator.categorize_error(error)
        assert code == "V001"
    
    def test_add_error_codes(self):
        """Test adding error codes to validation errors."""
        errors = [
            TradePlanValidationError("YAML syntax error", field="root"),
            TradePlanValidationError("Missing required fields: symbol", field="symbol"),
            TradePlanValidationError("Duplicate plan_id", field="plan_id"),
        ]
        
        coded_errors = ErrorCodeGenerator.add_error_codes(errors)
        
        assert len(coded_errors) == 3
        assert coded_errors[0]["code"] == "Y001"
        assert coded_errors[1]["code"] == "F001"
        assert coded_errors[2]["code"] == "D001"
        
        # Check all required fields are present
        for coded_error in coded_errors:
            assert "code" in coded_error
            assert "message" in coded_error
            assert "field" in coded_error
            assert "line_number" in coded_error
            assert "suggestion" in coded_error