"""Enhanced error reporting system for trade plan validation."""

from __future__ import annotations

import yaml
from pathlib import Path
from typing import List, Optional, Dict, Any

from loguru import logger

from .trade_plan import TradePlanValidationError, ValidationResult


class ErrorFormatter:
    """Formats validation errors for different output contexts."""
    
    @staticmethod
    def format_for_console(errors: List[TradePlanValidationError]) -> str:
        """
        Format errors for console output with colors and structure.
        
        Args:
            errors: List of validation errors to format
            
        Returns:
            Formatted error string for console display
        """
        if not errors:
            return "✅ No validation errors found"
        
        lines = [f"❌ Found {len(errors)} validation error(s):\n"]
        
        for i, error in enumerate(errors, 1):
            lines.append(f"{i:2d}. {ErrorFormatter._format_single_error(error)}")
        
        return "\n".join(lines)
    
    @staticmethod
    def format_for_cli(result: ValidationResult, file_path: Optional[Path] = None) -> str:
        """
        Format validation result for CLI display with file context.
        
        Args:
            result: Validation result to format
            file_path: Optional file path for context
            
        Returns:
            Formatted string for CLI output
        """
        file_info = f" in {file_path}" if file_path else ""
        
        if result.is_valid:
            return f"✅ Validation passed{file_info}"
        
        header = f"❌ Validation failed{file_info}:"
        error_details = ErrorFormatter.format_for_console(result.errors)
        
        return f"{header}\n\n{error_details}"
    
    @staticmethod
    def format_for_json(errors: List[TradePlanValidationError]) -> List[Dict[str, Any]]:
        """
        Format errors as JSON-serializable dictionaries.
        
        Args:
            errors: List of validation errors to format
            
        Returns:
            List of error dictionaries
        """
        return [
            {
                "message": error.message,
                "field": error.field,
                "line_number": error.line_number,
                "suggestion": error.suggestion,
                "severity": "error",
            }
            for error in errors
        ]
    
    @staticmethod
    def _format_single_error(error: TradePlanValidationError) -> str:
        """Format a single error with context and suggestion."""
        parts = []
        
        # Add line/field context
        if error.line_number:
            parts.append(f"Line {error.line_number}")
        if error.field:
            parts.append(f"Field '{error.field}'")
        
        # Build error message
        if parts:
            context = " - ".join(parts)
            error_line = f"{context}: {error.message}"
        else:
            error_line = error.message
        
        # Add suggestion if available
        if error.suggestion:
            error_line += f"\n    💡 Fix: {error.suggestion}"
        
        return error_line


class YAMLErrorEnhancer:
    """Enhances YAML parsing errors with line numbers and context."""
    
    @staticmethod
    def enhance_yaml_error(
        yaml_content: str, 
        yaml_error: yaml.YAMLError,
        file_path: Optional[Path] = None
    ) -> TradePlanValidationError:
        """
        Convert YAML parsing error to enhanced validation error.
        
        Args:
            yaml_content: Original YAML content that failed to parse
            yaml_error: The YAML parsing error
            file_path: Optional file path for context
            
        Returns:
            Enhanced validation error with line context
        """
        # Extract line information from YAML error
        line_number = None
        column = None
        problem_mark = getattr(yaml_error, 'problem_mark', None)
        
        if problem_mark:
            line_number = problem_mark.line + 1  # Convert to 1-based
            column = problem_mark.column + 1
        
        # Extract context around the error
        context_lines = YAMLErrorEnhancer._get_error_context(
            yaml_content, line_number, column
        )
        
        # Build descriptive error message
        error_msg = f"YAML syntax error: {yaml_error}"
        if context_lines:
            error_msg += f"\n{context_lines}"
        
        # Generate helpful suggestion
        suggestion = YAMLErrorEnhancer._generate_yaml_suggestion(str(yaml_error))
        
        return TradePlanValidationError(
            message=error_msg,
            line_number=line_number,
            suggestion=suggestion
        )
    
    @staticmethod
    def _get_error_context(
        yaml_content: str, 
        line_number: Optional[int], 
        column: Optional[int]
    ) -> str:
        """Extract context lines around the error."""
        if not line_number:
            return ""
        
        lines = yaml_content.split('\n')
        if line_number > len(lines):
            return ""
        
        # Show 2 lines before and after the error
        start_line = max(0, line_number - 3)
        end_line = min(len(lines), line_number + 2)
        
        context_lines = []
        for i in range(start_line, end_line):
            line_content = lines[i]
            line_num = i + 1
            
            if line_num == line_number:
                # Highlight the error line
                marker = ">>> " if column else ">>> "
                context_lines.append(f"{marker}{line_num:3d}: {line_content}")
                
                # Add column pointer if available
                if column:
                    pointer = " " * (len(marker) + 5 + column - 1) + "^"
                    context_lines.append(pointer)
            else:
                context_lines.append(f"    {line_num:3d}: {line_content}")
        
        return "\n".join(context_lines)
    
    @staticmethod
    def _generate_yaml_suggestion(error_message: str) -> str:
        """Generate helpful suggestion based on YAML error type."""
        error_lower = error_message.lower()
        
        if "mapping" in error_lower and "sequence" in error_lower:
            return "Check indentation - YAML objects need consistent spacing"
        elif "duplicate" in error_lower:
            return "Remove duplicate keys - each key can only appear once"
        elif "tab" in error_lower:
            return "Replace tabs with spaces - YAML requires spaces for indentation"
        elif "indent" in error_lower:
            return "Fix indentation - ensure consistent spacing (2 or 4 spaces)"
        elif "anchor" in error_lower or "alias" in error_lower:
            return "Check YAML anchors and aliases syntax"
        elif "unicode" in error_lower:
            return "Check for invalid characters - ensure UTF-8 encoding"
        else:
            return "Check YAML syntax - ensure proper structure and indentation"


class ValidationReporter:
    """Aggregates and reports validation results across multiple files."""
    
    def __init__(self) -> None:
        """Initialize validation reporter."""
        self.results: List[tuple[Optional[Path], ValidationResult]] = []
    
    def add_result(self, result: ValidationResult, file_path: Optional[Path] = None) -> None:
        """Add a validation result to the reporter."""
        self.results.append((file_path, result))
        
        # Log the result
        if result.is_valid:
            logger.info(
                "Validation successful",
                file_path=str(file_path) if file_path else "string_content",
                plan_id=result.plan_id
            )
        else:
            logger.warning(
                "Validation failed",
                file_path=str(file_path) if file_path else "string_content",
                error_count=result.error_count,
                errors=[str(error) for error in result.errors]
            )
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary statistics of all validation results."""
        total_files = len(self.results)
        valid_files = sum(1 for _, result in self.results if result.is_valid)
        invalid_files = total_files - valid_files
        total_errors = sum(result.error_count for _, result in self.results)
        
        return {
            "total_files": total_files,
            "valid_files": valid_files,
            "invalid_files": invalid_files,
            "total_errors": total_errors,
            "success_rate": valid_files / total_files if total_files > 0 else 0.0
        }
    
    def format_summary_report(self) -> str:
        """Format a comprehensive summary report."""
        if not self.results:
            return "No validation results to report"
        
        summary = self.get_summary()
        
        # Header
        lines = [
            "=" * 60,
            "TRADE PLAN VALIDATION SUMMARY",
            "=" * 60,
            f"Total files processed: {summary['total_files']}",
            f"✅ Valid files: {summary['valid_files']}",
            f"❌ Invalid files: {summary['invalid_files']}",
            f"Total errors: {summary['total_errors']}",
            f"Success rate: {summary['success_rate']:.1%}",
            ""
        ]
        
        # Detailed results for invalid files
        if summary['invalid_files'] > 0:
            lines.append("DETAILED ERROR REPORT:")
            lines.append("-" * 40)
            
            for file_path, result in self.results:
                if not result.is_valid:
                    file_name = file_path.name if file_path else "string_content"
                    lines.append(f"\n📄 {file_name}:")
                    lines.append(ErrorFormatter.format_for_console(result.errors))
        
        return "\n".join(lines)
    
    def get_all_errors(self) -> List[TradePlanValidationError]:
        """Get all errors from all validation results."""
        all_errors = []
        for _, result in self.results:
            all_errors.extend(result.errors)
        return all_errors
    
    def clear(self) -> None:
        """Clear all stored results."""
        self.results.clear()


class ErrorCodeGenerator:
    """Generates error codes for categorizing validation errors."""
    
    ERROR_CATEGORIES = {
        "YAML_SYNTAX": "Y001",
        "MISSING_FIELD": "F001", 
        "INVALID_FORMAT": "F002",
        "INVALID_VALUE": "V001",
        "BUSINESS_RULE": "B001",
        "DUPLICATE": "D001",
        "FILE_ACCESS": "A001",
    }
    
    @staticmethod
    def categorize_error(error: TradePlanValidationError) -> str:
        """
        Categorize error and return error code.
        
        Args:
            error: Validation error to categorize
            
        Returns:
            Error code string
        """
        message = error.message.lower()
        
        if "yaml" in message and "syntax" in message:
            return ErrorCodeGenerator.ERROR_CATEGORIES["YAML_SYNTAX"]
        elif "missing" in message and "field" in message:
            return ErrorCodeGenerator.ERROR_CATEGORIES["MISSING_FIELD"]
        elif "invalid" in message and "format" in message:
            return ErrorCodeGenerator.ERROR_CATEGORIES["INVALID_FORMAT"]
        elif "duplicate" in message:
            return ErrorCodeGenerator.ERROR_CATEGORIES["DUPLICATE"]
        elif "file" in message and ("not found" in message or "permission" in message):
            return ErrorCodeGenerator.ERROR_CATEGORIES["FILE_ACCESS"]
        elif any(word in message for word in ["cannot equal", "relationship", "logic"]):
            return ErrorCodeGenerator.ERROR_CATEGORIES["BUSINESS_RULE"]
        else:
            return ErrorCodeGenerator.ERROR_CATEGORIES["INVALID_VALUE"]
    
    @staticmethod
    def add_error_codes(errors: List[TradePlanValidationError]) -> List[Dict[str, Any]]:
        """Add error codes to validation errors."""
        return [
            {
                "code": ErrorCodeGenerator.categorize_error(error),
                "message": error.message,
                "field": error.field,
                "line_number": error.line_number,
                "suggestion": error.suggestion,
            }
            for error in errors
        ]