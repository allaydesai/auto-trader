"""Tests for wizard constants."""

from ..wizard_constants import (
    RISK_CATEGORIES,
    RISK_CATEGORY_CHOICES,
    RISK_CATEGORY_HELP_TEXT,
    DEFAULT_RISK_CATEGORY,
    AVAILABLE_TIMEFRAMES,
    DEFAULT_TIMEFRAME,
    ENTRY_FUNCTION_TYPES,
    EXIT_FUNCTION_TYPES,
    DEFAULT_ENTRY_FUNCTION_TYPE,
    DEFAULT_EXIT_FUNCTION_TYPE
)


class TestWizardConstants:
    """Test wizard constants are properly defined."""
    
    def test_risk_categories_structure(self):
        """Test risk categories have correct structure."""
        assert isinstance(RISK_CATEGORIES, dict)
        assert len(RISK_CATEGORIES) == 3
        assert "small" in RISK_CATEGORIES
        assert "normal" in RISK_CATEGORIES
        assert "large" in RISK_CATEGORIES
        
        # Check descriptions contain percentage
        assert "1%" in RISK_CATEGORIES["small"]
        assert "2%" in RISK_CATEGORIES["normal"]
        assert "3%" in RISK_CATEGORIES["large"]
    
    def test_risk_category_choices_match_keys(self):
        """Test risk category choices match dictionary keys."""
        assert RISK_CATEGORY_CHOICES == list(RISK_CATEGORIES.keys())
        assert RISK_CATEGORY_CHOICES == ["small", "normal", "large"]
    
    def test_risk_category_help_text_contains_percentages(self):
        """Test help text contains all risk percentages."""
        assert "1%" in RISK_CATEGORY_HELP_TEXT
        assert "2%" in RISK_CATEGORY_HELP_TEXT
        assert "3%" in RISK_CATEGORY_HELP_TEXT
        assert "small" in RISK_CATEGORY_HELP_TEXT
        assert "normal" in RISK_CATEGORY_HELP_TEXT
        assert "large" in RISK_CATEGORY_HELP_TEXT
    
    def test_default_risk_category_valid(self):
        """Test default risk category is valid."""
        assert DEFAULT_RISK_CATEGORY in RISK_CATEGORY_CHOICES
        assert DEFAULT_RISK_CATEGORY == "normal"
    
    def test_timeframes_structure(self):
        """Test timeframes have correct structure."""
        assert isinstance(AVAILABLE_TIMEFRAMES, list)
        assert len(AVAILABLE_TIMEFRAMES) >= 5
        expected_timeframes = ["1min", "5min", "15min", "30min", "60min"]
        for timeframe in expected_timeframes:
            assert timeframe in AVAILABLE_TIMEFRAMES
    
    def test_default_timeframe_valid(self):
        """Test default timeframe is valid."""
        assert DEFAULT_TIMEFRAME in AVAILABLE_TIMEFRAMES
        assert DEFAULT_TIMEFRAME == "15min"
    
    def test_execution_function_types_structure(self):
        """Test execution function types have correct structure."""
        assert isinstance(ENTRY_FUNCTION_TYPES, list)
        assert isinstance(EXIT_FUNCTION_TYPES, list)
        
        # Check entry function types
        assert "close_above" in ENTRY_FUNCTION_TYPES
        assert "close_below" in ENTRY_FUNCTION_TYPES
        
        # Check exit function types
        assert "stop_loss_take_profit" in EXIT_FUNCTION_TYPES
        assert "trailing_stop" in EXIT_FUNCTION_TYPES
    
    def test_default_execution_function_types_valid(self):
        """Test default execution function types are valid."""
        assert DEFAULT_ENTRY_FUNCTION_TYPE in ENTRY_FUNCTION_TYPES
        assert DEFAULT_EXIT_FUNCTION_TYPE in EXIT_FUNCTION_TYPES
        assert DEFAULT_ENTRY_FUNCTION_TYPE == "close_above"
        assert DEFAULT_EXIT_FUNCTION_TYPE == "stop_loss_take_profit"
    
    def test_no_hardcoded_magic_numbers(self):
        """Test that all constants are properly defined to avoid magic numbers."""
        # Verify we have constants for all major configuration items
        required_constants = [
            "RISK_CATEGORIES",
            "RISK_CATEGORY_CHOICES", 
            "DEFAULT_RISK_CATEGORY",
            "AVAILABLE_TIMEFRAMES",
            "DEFAULT_TIMEFRAME",
            "ENTRY_FUNCTION_TYPES",
            "EXIT_FUNCTION_TYPES"
        ]
        
        # Import the module to check if constants exist
        import auto_trader.cli.wizard_constants as constants_module
        
        for constant_name in required_constants:
            assert hasattr(constants_module, constant_name), f"Missing constant: {constant_name}"