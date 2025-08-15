"""Tests for CLI schema utilities."""

import pytest
from unittest.mock import patch, Mock

from ..schema_utils import display_schema_console


class TestSchemaUtils:
    """Test schema utility functions."""

    def test_display_schema_console_basic(self):
        """Test basic schema display functionality."""
        schema = {
            "properties": {
                "plan_id": {
                    "type": "string",
                    "description": "Unique identifier for the plan"
                },
                "symbol": {
                    "type": "string", 
                    "description": "Trading symbol"
                }
            },
            "required": ["plan_id", "symbol"]
        }
        
        # Mock console to avoid actual rich output during tests
        with patch('auto_trader.cli.schema_utils.console') as mock_console:
            display_schema_console(schema)
            
            # Verify console.print was called (rich output)
            assert mock_console.print.call_count >= 2  # Panel and Table calls
    
    def test_display_schema_console_with_object_types(self):
        """Test schema display with object and array types."""
        schema = {
            "properties": {
                "entry_function": {
                    "type": "object",
                    "properties": {
                        "function_type": {"type": "string"}
                    },
                    "description": "Entry function configuration"
                },
                "tags": {
                    "type": "array", 
                    "items": {"type": "string"},
                    "description": "List of tags"
                }
            },
            "required": ["entry_function"]
        }
        
        with patch('auto_trader.cli.schema_utils.console') as mock_console:
            display_schema_console(schema)
            
            # Test passes if no exceptions are raised
            assert mock_console.print.call_count >= 2
    
    def test_display_schema_console_long_descriptions(self):
        """Test schema display with long field descriptions."""
        schema = {
            "properties": {
                "plan_id": {
                    "type": "string",
                    "description": "This is a very long description that should be truncated when displayed in the table to ensure proper formatting and readability"
                }
            },
            "required": []
        }
        
        with patch('auto_trader.cli.schema_utils.console') as mock_console:
            display_schema_console(schema)
            
            # Test passes if no exceptions are raised and handles long descriptions
            assert mock_console.print.call_count >= 2
    
    def test_display_schema_console_empty_schema(self):
        """Test schema display with empty schema."""
        schema = {
            "properties": {},
            "required": []
        }
        
        with patch('auto_trader.cli.schema_utils.console') as mock_console:
            display_schema_console(schema)
            
            # Should handle empty schema gracefully
            assert mock_console.print.call_count >= 2
    
    def test_display_schema_console_missing_description(self):
        """Test schema display with missing descriptions."""
        schema = {
            "properties": {
                "plan_id": {
                    "type": "string"
                    # No description field
                }
            },
            "required": ["plan_id"]
        }
        
        with patch('auto_trader.cli.schema_utils.console') as mock_console:
            display_schema_console(schema)
            
            # Should handle missing descriptions gracefully
            assert mock_console.print.call_count >= 2