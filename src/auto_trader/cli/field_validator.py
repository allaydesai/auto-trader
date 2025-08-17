"""Field validation utilities for interactive wizard."""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict

from ..models import ExecutionFunction, RiskCategory, TradePlan


class WizardFieldValidator:
    """Validates individual fields for trade plan creation wizard."""
    
    def __init__(self) -> None:
        """Initialize field validator."""
        pass
    
    def validate_symbol(self, symbol: str) -> Dict[str, Any]:
        """
        Validate trading symbol field.
        
        Args:
            symbol: Symbol to validate
            
        Returns:
            Dictionary with validation result and error message if invalid
        """
        return self._validate_field_with_model("symbol", symbol)
    
    def validate_entry_level(self, entry_level: Decimal) -> Dict[str, Any]:
        """
        Validate entry level field.
        
        Args:
            entry_level: Entry level to validate
            
        Returns:
            Dictionary with validation result and error message if invalid
        """
        return self._validate_field_with_model("entry_level", entry_level)
    
    def validate_stop_loss(self, stop_loss: Decimal, entry_level: Decimal) -> Dict[str, Any]:
        """
        Validate stop loss field including business rules.
        
        Args:
            stop_loss: Stop loss to validate
            entry_level: Entry level for business rule validation
            
        Returns:
            Dictionary with validation result and error message if invalid
        """
        # First validate the field itself
        result = self._validate_field_with_model("stop_loss", stop_loss)
        if not result["is_valid"]:
            return result
        
        # Additional business rule: stop loss cannot equal entry level
        if stop_loss == entry_level:
            return {
                "is_valid": False,
                "error": "Stop loss cannot equal entry level"
            }
        
        return {"is_valid": True, "error": None}
    
    def validate_take_profit(self, take_profit: Decimal) -> Dict[str, Any]:
        """
        Validate take profit field.
        
        Args:
            take_profit: Take profit to validate
            
        Returns:
            Dictionary with validation result and error message if invalid
        """
        return self._validate_field_with_model("take_profit", take_profit)
    
    def validate_risk_category(self, risk_category: RiskCategory) -> Dict[str, Any]:
        """
        Validate risk category field.
        
        Args:
            risk_category: Risk category to validate
            
        Returns:
            Dictionary with validation result and error message if invalid
        """
        return self._validate_field_with_model("risk_category", risk_category)
    
    def _validate_field_with_model(self, field_name: str, value: Any) -> Dict[str, Any]:
        """
        Validate a single field using TradePlan model validation.
        
        Args:
            field_name: Name of the field to validate
            value: Value to validate
            
        Returns:
            Dictionary with validation result and error message if invalid
        """
        try:
            # Create dummy data that adapts to the field being validated
            dummy_data = self._create_dummy_data_for_field(field_name, value)
            
            # Try to create TradePlan instance for validation
            TradePlan(**dummy_data)
            return {"is_valid": True, "error": None}
            
        except Exception as e:
            # Extract meaningful error message
            error_msg = str(e)
            if "validation error" in error_msg.lower():
                # Extract the specific field error from Pydantic validation
                lines = error_msg.split("\n")
                for line in lines:
                    if field_name in line and "Input should be" in line:
                        error_msg = line.split("Input should be")[-1].strip()
                        break
                    elif field_name in line:
                        error_msg = line.strip()
                        break
            
            return {"is_valid": False, "error": error_msg}
    
    def _create_dummy_data_for_field(self, field_name: str, value: Any) -> Dict[str, Any]:
        """
        Create dummy data that makes sense for the field being validated.
        
        Args:
            field_name: Name of the field being validated
            value: Value being tested
            
        Returns:
            Dictionary with appropriate dummy data
        """
        # Base dummy data
        dummy_data = {
            "plan_id": "TEST_20250101_001",
            "symbol": "TEST",
            "entry_level": Decimal("100.00"),
            "stop_loss": Decimal("95.00"),
            "take_profit": Decimal("105.00"),
            "risk_category": RiskCategory.NORMAL,
            "entry_function": ExecutionFunction(
                function_type="close_above",
                timeframe="15min"
            ),
            "exit_function": ExecutionFunction(
                function_type="stop_loss_take_profit", 
                timeframe="15min"
            ),
        }
        
        # Replace the field we want to validate
        dummy_data[field_name] = value
        
        # Adjust related fields to maintain valid relationships
        if field_name == "entry_level" and isinstance(value, Decimal):
            # Adjust stop and target based on entry level, rounded to 4 decimal places
            dummy_data["stop_loss"] = round(value * Decimal("0.95"), 4)  # 5% below entry
            dummy_data["take_profit"] = round(value * Decimal("1.05"), 4)  # 5% above entry
        
        elif field_name == "stop_loss" and isinstance(value, Decimal):
            # Adjust entry and target to be valid relative to stop
            if value > Decimal("0"):
                dummy_data["entry_level"] = round(value * Decimal("1.05"), 4)  # Entry above stop
                dummy_data["take_profit"] = round(value * Decimal("1.15"), 4)  # Target above entry
        
        elif field_name == "take_profit" and isinstance(value, Decimal):
            # Adjust entry and stop to be valid relative to target
            if value > Decimal("0"):
                dummy_data["entry_level"] = round(value * Decimal("0.95"), 4)  # Entry below target
                dummy_data["stop_loss"] = round(value * Decimal("0.90"), 4)   # Stop below entry
        
        return dummy_data