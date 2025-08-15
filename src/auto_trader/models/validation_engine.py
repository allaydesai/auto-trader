"""Schema validation engine for trade plans."""

from __future__ import annotations

import re
import yaml
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import ValidationError
from loguru import logger

from .trade_plan import (
    TradePlan,
    TradePlanValidationError,
    ValidationResult,
    RiskCategory,
)


class ValidationEngine:
    """Validation engine for trade plan schema and business rules."""
    
    SUPPORTED_FUNCTIONS = {
        "close_above",
        "close_below", 
        "trailing_stop",
        "stop_loss_take_profit",
    }
    
    SUPPORTED_TIMEFRAMES = {
        "1min", "5min", "15min", "30min", "60min", "240min", "1440min",
        "1h", "4h", "1440h", "1d"
    }
    
    def __init__(self) -> None:
        """Initialize validation engine."""
        self._loaded_plan_ids: set[str] = set()
    
    def validate_yaml_content(
        self, 
        yaml_content: str, 
        file_path: Optional[Path] = None
    ) -> ValidationResult:
        """
        Validate YAML content for trade plan schema compliance.
        
        Args:
            yaml_content: Raw YAML content to validate
            file_path: Optional path for context in error messages
            
        Returns:
            ValidationResult with validation status and any errors
        """
        errors: List[TradePlanValidationError] = []
        
        try:
            # Parse YAML content
            parsed_data = yaml.safe_load(yaml_content)
            
            if parsed_data is None:
                errors.append(TradePlanValidationError(
                    "Empty YAML content",
                    suggestion="Add valid trade plan data to the file"
                ))
                return ValidationResult(is_valid=False, errors=errors)
            
            # Handle single plan or list of plans
            if isinstance(parsed_data, dict):
                plans_data = [parsed_data]
            elif isinstance(parsed_data, list):
                plans_data = parsed_data
            else:
                errors.append(TradePlanValidationError(
                    f"Invalid YAML structure. Expected dict or list, got {type(parsed_data).__name__}",
                    suggestion="Ensure YAML contains a trade plan object or list of objects"
                ))
                return ValidationResult(is_valid=False, errors=errors)
            
            # Validate each plan
            for i, plan_data in enumerate(plans_data):
                plan_errors = self._validate_single_plan(plan_data, i + 1)
                errors.extend(plan_errors)
            
        except yaml.YAMLError as e:
            line_num = getattr(e, 'problem_mark', None)
            line_info = f" at line {line_num.line + 1}" if line_num else ""
            
            errors.append(TradePlanValidationError(
                f"YAML syntax error{line_info}: {e}",
                line_number=line_num.line + 1 if line_num else None,
                suggestion="Check YAML syntax - ensure proper indentation and structure"
            ))
        except Exception as e:
            errors.append(TradePlanValidationError(
                f"Unexpected validation error: {e}",
                suggestion="Check file content and try again"
            ))
        
        # Log validation results
        if errors:
            logger.warning(
                "Trade plan validation failed",
                file_path=str(file_path) if file_path else "string",
                error_count=len(errors),
                errors=[str(error) for error in errors]
            )
        else:
            logger.info(
                "Trade plan validation successful",
                file_path=str(file_path) if file_path else "string",
                plan_count=len(plans_data)
            )
        
        is_valid = len(errors) == 0
        plan_id = plans_data[0].get("plan_id") if is_valid and plans_data else None
        
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            plan_id=plan_id
        )
    
    def validate_file(self, file_path: Path) -> ValidationResult:
        """
        Validate a YAML file containing trade plan(s).
        
        Args:
            file_path: Path to YAML file to validate
            
        Returns:
            ValidationResult with validation status and any errors
        """
        try:
            if not file_path.exists():
                return ValidationResult(
                    is_valid=False,
                    errors=[TradePlanValidationError(
                        f"File not found: {file_path}",
                        suggestion="Check the file path and ensure the file exists"
                    )]
                )
            
            if file_path.suffix.lower() not in {'.yaml', '.yml'}:
                return ValidationResult(
                    is_valid=False,
                    errors=[TradePlanValidationError(
                        f"Invalid file extension: {file_path.suffix}",
                        suggestion="Use .yaml or .yml file extension"
                    )]
                )
            
            content = file_path.read_text(encoding='utf-8')
            return self.validate_yaml_content(content, file_path)
            
        except PermissionError:
            return ValidationResult(
                is_valid=False,
                errors=[TradePlanValidationError(
                    f"Permission denied reading file: {file_path}",
                    suggestion="Check file permissions"
                )]
            )
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                errors=[TradePlanValidationError(
                    f"Error reading file {file_path}: {e}",
                    suggestion="Check file accessibility and content"
                )]
            )
    
    def _validate_single_plan(self, plan_data: Dict[str, Any], plan_index: int) -> List[TradePlanValidationError]:
        """Validate a single trade plan dictionary."""
        errors: List[TradePlanValidationError] = []
        
        if not isinstance(plan_data, dict):
            errors.append(TradePlanValidationError(
                f"Plan {plan_index}: Expected dictionary, got {type(plan_data).__name__}",
                suggestion="Each trade plan must be a YAML object with key-value pairs"
            ))
            return errors
        
        # Check required fields
        required_fields = {
            "plan_id", "symbol", "entry_level", "stop_loss", 
            "take_profit", "risk_category", "entry_function", "exit_function"
        }
        
        missing_fields = required_fields - set(plan_data.keys())
        if missing_fields:
            errors.append(TradePlanValidationError(
                f"Plan {plan_index}: Missing required fields: {', '.join(sorted(missing_fields))}",
                suggestion=f"Add missing fields: {', '.join(sorted(missing_fields))}"
            ))
        
        # Validate individual fields
        self._validate_plan_id(plan_data, errors, plan_index)
        self._validate_symbol(plan_data, errors, plan_index)
        self._validate_prices(plan_data, errors, plan_index)
        self._validate_risk_category(plan_data, errors, plan_index)
        self._validate_execution_functions(plan_data, errors, plan_index)
        
        # If no field-level errors, try creating the full model
        if not errors:
            try:
                TradePlan(**plan_data)
            except ValidationError as e:
                for error_detail in e.errors():
                    field_name = '.'.join(str(loc) for loc in error_detail['loc'])
                    errors.append(TradePlanValidationError(
                        f"Plan {plan_index}: {error_detail['msg']}",
                        field=field_name,
                        suggestion=self._get_field_suggestion(field_name, error_detail)
                    ))
        
        return errors
    
    def _validate_plan_id(self, plan_data: Dict[str, Any], errors: List[TradePlanValidationError], plan_index: int) -> None:
        """Validate plan_id field."""
        plan_id = plan_data.get("plan_id")
        
        if not plan_id:
            return  # Already handled by required field check
        
        if not isinstance(plan_id, str):
            errors.append(TradePlanValidationError(
                f"Plan {plan_index}: plan_id must be a string",
                field="plan_id",
                suggestion="Use a string value like 'AAPL_20250815_001'"
            ))
            return
        
        # Validate format
        if not re.match(r"^[A-Z0-9_]+$", plan_id):
            errors.append(TradePlanValidationError(
                f"Plan {plan_index}: Invalid plan_id format '{plan_id}'",
                field="plan_id",
                suggestion="Use only uppercase letters, numbers, and underscores (e.g., 'AAPL_20250815_001')"
            ))
        
        # Check uniqueness
        if plan_id in self._loaded_plan_ids:
            errors.append(TradePlanValidationError(
                f"Plan {plan_index}: Duplicate plan_id '{plan_id}'",
                field="plan_id",
                suggestion=f"Use a unique plan_id ('{plan_id}' already exists)"
            ))
        else:
            self._loaded_plan_ids.add(plan_id)
    
    def _validate_symbol(self, plan_data: Dict[str, Any], errors: List[TradePlanValidationError], plan_index: int) -> None:
        """Validate symbol field."""
        symbol = plan_data.get("symbol")
        
        if not symbol:
            return  # Already handled by required field check
        
        if not isinstance(symbol, str):
            errors.append(TradePlanValidationError(
                f"Plan {plan_index}: symbol must be a string",
                field="symbol",
                suggestion="Use a string value like 'AAPL'"
            ))
            return
        
        # Validate format: 1-10 uppercase characters, no special chars
        if not re.match(r"^[A-Z]{1,10}$", symbol):
            errors.append(TradePlanValidationError(
                f"Plan {plan_index}: Invalid symbol format '{symbol}'",
                field="symbol",
                suggestion="Use 1-10 uppercase letters only (e.g., 'AAPL', 'MSFT')"
            ))
    
    def _validate_prices(self, plan_data: Dict[str, Any], errors: List[TradePlanValidationError], plan_index: int) -> None:
        """Validate price fields."""
        price_fields = ["entry_level", "stop_loss", "take_profit"]
        
        for field in price_fields:
            value = plan_data.get(field)
            
            if value is None:
                continue  # Already handled by required field check
            
            # Convert to Decimal for validation
            try:
                if isinstance(value, (int, float)):
                    decimal_value = Decimal(str(value))
                elif isinstance(value, str):
                    decimal_value = Decimal(value)
                else:
                    errors.append(TradePlanValidationError(
                        f"Plan {plan_index}: {field} must be a number",
                        field=field,
                        suggestion="Use a decimal number like 180.50"
                    ))
                    continue
                
                # Check positive value
                if decimal_value <= 0:
                    errors.append(TradePlanValidationError(
                        f"Plan {plan_index}: {field} must be positive, got {decimal_value}",
                        field=field,
                        suggestion="Use a positive price value like 180.50"
                    ))
                
                # Check decimal places (max 4)
                exponent = decimal_value.as_tuple().exponent
                if isinstance(exponent, int) and exponent < -4:
                    errors.append(TradePlanValidationError(
                        f"Plan {plan_index}: {field} has too many decimal places ({decimal_value})",
                        field=field,
                        suggestion="Use maximum 4 decimal places (e.g., 180.1234)"
                    ))
                
            except (ValueError, TypeError) as e:
                errors.append(TradePlanValidationError(
                    f"Plan {plan_index}: Invalid {field} value '{value}': {e}",
                    field=field,
                    suggestion="Use a valid decimal number like 180.50"
                ))
    
    def _validate_risk_category(self, plan_data: Dict[str, Any], errors: List[TradePlanValidationError], plan_index: int) -> None:
        """Validate risk_category field."""
        risk_category = plan_data.get("risk_category")
        
        if not risk_category:
            return  # Already handled by required field check
        
        if not isinstance(risk_category, str):
            errors.append(TradePlanValidationError(
                f"Plan {plan_index}: risk_category must be a string",
                field="risk_category",
                suggestion="Use one of: 'small', 'normal', 'large'"
            ))
            return
        
        valid_categories = {cat.value for cat in RiskCategory}
        if risk_category not in valid_categories:
            errors.append(TradePlanValidationError(
                f"Plan {plan_index}: Invalid risk_category '{risk_category}'",
                field="risk_category",
                suggestion=f"Use one of: {', '.join(sorted(valid_categories))}"
            ))
    
    def _validate_execution_functions(self, plan_data: Dict[str, Any], errors: List[TradePlanValidationError], plan_index: int) -> None:
        """Validate execution function fields."""
        function_fields = ["entry_function", "exit_function"]
        
        for field in function_fields:
            func_data = plan_data.get(field)
            
            if not func_data:
                continue  # Already handled by required field check
            
            if not isinstance(func_data, dict):
                errors.append(TradePlanValidationError(
                    f"Plan {plan_index}: {field} must be an object",
                    field=field,
                    suggestion="Use an object with function_type, timeframe, and parameters"
                ))
                continue
            
            # Validate function_type
            function_type = func_data.get("function_type")
            if function_type not in self.SUPPORTED_FUNCTIONS:
                errors.append(TradePlanValidationError(
                    f"Plan {plan_index}: Unsupported function_type '{function_type}' in {field}",
                    field=f"{field}.function_type",
                    suggestion=f"Use one of: {', '.join(sorted(self.SUPPORTED_FUNCTIONS))}"
                ))
            
            # Validate timeframe
            timeframe = func_data.get("timeframe")
            if timeframe not in self.SUPPORTED_TIMEFRAMES:
                errors.append(TradePlanValidationError(
                    f"Plan {plan_index}: Unsupported timeframe '{timeframe}' in {field}",
                    field=f"{field}.timeframe",
                    suggestion=f"Use one of: {', '.join(sorted(self.SUPPORTED_TIMEFRAMES))}"
                ))
            
            # Validate parameters (should be a dict)
            parameters = func_data.get("parameters")
            if parameters is not None and not isinstance(parameters, dict):
                errors.append(TradePlanValidationError(
                    f"Plan {plan_index}: parameters in {field} must be an object",
                    field=f"{field}.parameters",
                    suggestion="Use an object with key-value pairs for function parameters"
                ))
    
    def _get_field_suggestion(self, field_name: str, error_detail: Dict[str, Any]) -> str:
        """Generate helpful suggestion based on field validation error."""
        error_type = error_detail.get('type', '')
        
        suggestions = {
            'string_too_short': "Provide a non-empty string value",
            'string_too_long': "Use a shorter string value",
            'greater_than': "Use a positive number greater than 0",
            'decimal_max_places': "Use maximum 4 decimal places",
            'value_error': "Check the value format and constraints",
        }
        
        return suggestions.get(error_type, "Check the field value and format")
    
    def reset_plan_ids(self) -> None:
        """Reset the tracked plan IDs (useful for testing or reloading)."""
        self._loaded_plan_ids.clear()
    
    def get_loaded_plan_ids(self) -> set[str]:
        """Get the set of currently loaded plan IDs."""
        return self._loaded_plan_ids.copy()