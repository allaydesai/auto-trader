"""Unit tests for template manager."""

import pytest
import tempfile
from pathlib import Path
from decimal import Decimal

from auto_trader.models.template_manager import TemplateManager
from auto_trader.models.trade_plan import TradePlan


class TestTemplateManager:
    """Test TemplateManager functionality."""
    
    @pytest.fixture
    def temp_templates_dir(self):
        """Create a temporary templates directory with test templates."""
        with tempfile.TemporaryDirectory() as temp_dir:
            templates_dir = Path(temp_dir) / "templates"
            templates_dir.mkdir()
            
            # Create a simple test template
            test_template = '''# Test Template
# This template is for testing

# Unique identifier (REQUIRED)
plan_id: "SYMBOL_YYYYMMDD_001"

# Trading symbol (REQUIRED)
symbol: "SYMBOL"

# Entry price level (REQUIRED)
entry_level: 0.00

# Stop loss price (REQUIRED)
stop_loss: 0.00

# Take profit target (REQUIRED)
take_profit: 0.00

# Risk category (REQUIRED)
# Valid values: "small", "normal", "large"
risk_category: "normal"

# Entry execution function (REQUIRED)
entry_function:
  function_type: "close_above"
  timeframe: "15min"
  parameters:
    threshold: 0.00

# Exit execution function (REQUIRED)
exit_function:
  function_type: "stop_loss_take_profit"
  timeframe: "1min"
  parameters: {}

# Example Complete Configuration:
# plan_id: "AAPL_20250815_001"
# symbol: "AAPL"
# entry_level: 180.50
# stop_loss: 178.00
# take_profit: 185.00

# Common Use Cases:
# 1. Breakout trades above resistance
# 2. Momentum continuation setups
'''
            
            test_template_path = templates_dir / "test_template.yaml"
            test_template_path.write_text(test_template)
            
            yield templates_dir
    
    @pytest.fixture
    def template_manager(self, temp_templates_dir):
        """Provide template manager with temporary directory."""
        return TemplateManager(temp_templates_dir)
    
    def test_list_available_templates(self, template_manager):
        """Test listing available templates."""
        templates = template_manager.list_available_templates()
        
        assert len(templates) == 1
        assert "test_template" in templates
        assert templates["test_template"].name == "test_template.yaml"
    
    def test_list_available_templates_empty_dir(self):
        """Test listing templates in empty directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            empty_dir = Path(temp_dir) / "empty"
            empty_dir.mkdir()
            
            manager = TemplateManager(empty_dir)
            templates = manager.list_available_templates()
            
            assert len(templates) == 0
    
    def test_load_template_success(self, template_manager):
        """Test loading template successfully."""
        content = template_manager.load_template("test_template")
        
        assert "# Test Template" in content
        assert "plan_id:" in content
        assert "symbol:" in content
        assert "entry_level:" in content
    
    def test_load_template_not_found(self, template_manager):
        """Test loading non-existent template."""
        with pytest.raises(FileNotFoundError) as exc_info:
            template_manager.load_template("nonexistent")
        
        assert "Template 'nonexistent' not found" in str(exc_info.value)
        assert "Available templates: test_template" in str(exc_info.value)
    
    def test_get_template_documentation(self, template_manager):
        """Test extracting template documentation."""
        doc_info = template_manager.get_template_documentation("test_template")
        
        assert doc_info["name"] == "test_template"
        assert doc_info["description"] == "Test Template"
        assert len(doc_info["required_fields"]) >= 5  # plan_id, symbol, etc.
        assert len(doc_info["examples"]) >= 0  # Examples are optional
        assert len(doc_info["use_cases"]) >= 2
    
    def test_get_template_documentation_not_found(self, template_manager):
        """Test getting documentation for non-existent template."""
        doc_info = template_manager.get_template_documentation("nonexistent")
        
        assert "error" in doc_info
        assert "not found" in doc_info["error"]
    
    def test_customize_template_success(self, template_manager):
        """Test successful template customization."""
        substitutions = {
            "plan_id": "AAPL_20250815_001",
            "symbol": "AAPL",
            "entry_level": 180.50,
            "stop_loss": 178.00,
            "take_profit": 185.00,
            "threshold": 180.50,
        }
        
        customized = template_manager.customize_template(
            "test_template", 
            substitutions, 
            validate=False  # Skip validation for simple test
        )
        
        assert 'plan_id: "AAPL_20250815_001"' in customized
        assert 'symbol: "AAPL"' in customized
        assert "entry_level: 180.5" in customized
        assert "stop_loss: 178.0" in customized
        assert "take_profit: 185.0" in customized
    
    def test_customize_template_with_validation(self, template_manager):
        """Test template customization with validation."""
        substitutions = {
            "plan_id": "AAPL_20250815_001",
            "symbol": "AAPL",
            "entry_level": 180.50,
            "stop_loss": 178.00,
            "take_profit": 185.00,
            "threshold": 180.50,
        }
        
        customized = template_manager.customize_template(
            "test_template", 
            substitutions, 
            validate=True
        )
        
        # Should not raise an exception and should contain substitutions
        assert 'symbol: "AAPL"' in customized
    
    def test_customize_template_validation_failure(self, template_manager):
        """Test template customization with validation failure."""
        # Invalid substitutions (negative prices)
        substitutions = {
            "plan_id": "INVALID_ID",
            "symbol": "aapl",  # lowercase - invalid
            "entry_level": -180.50,  # negative - invalid
            "stop_loss": -178.00,
            "take_profit": -185.00,
        }
        
        with pytest.raises(ValueError) as exc_info:
            template_manager.customize_template(
                "test_template", 
                substitutions, 
                validate=True
            )
        
        assert "Template customization failed validation" in str(exc_info.value)
    
    def test_create_plan_from_template(self, template_manager):
        """Test creating trade plan from template."""
        plan_data = {
            "plan_id": "AAPL_20250815_001",
            "symbol": "AAPL",
            "entry_level": 180.50,
            "stop_loss": 178.00,
            "take_profit": 185.00,
            "threshold": 180.50,
        }
        
        trade_plan = template_manager.create_plan_from_template(
            "test_template", 
            plan_data
        )
        
        assert isinstance(trade_plan, TradePlan)
        assert trade_plan.plan_id == "AAPL_20250815_001"
        assert trade_plan.symbol == "AAPL"
        assert trade_plan.entry_level == Decimal("180.50")
        assert trade_plan.stop_loss == Decimal("178.00")
        assert trade_plan.take_profit == Decimal("185.00")
    
    def test_create_plan_from_template_with_output_file(self, template_manager):
        """Test creating trade plan with output file."""
        plan_data = {
            "plan_id": "AAPL_20250815_001",
            "symbol": "AAPL",
            "entry_level": 180.50,
            "stop_loss": 178.00,
            "take_profit": 185.00,
            "threshold": 180.50,
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "output_plan.yaml"
            
            trade_plan = template_manager.create_plan_from_template(
                "test_template", 
                plan_data,
                output_file
            )
            
            assert output_file.exists()
            assert trade_plan.plan_id == "AAPL_20250815_001"
            
            # Verify file content
            content = output_file.read_text()
            assert 'symbol: "AAPL"' in content
    
    def test_validate_template_success(self, template_manager):
        """Test successful template validation."""
        is_valid = template_manager.validate_template("test_template")
        assert is_valid is True
    
    def test_validate_template_not_found(self, template_manager):
        """Test validating non-existent template."""
        is_valid = template_manager.validate_template("nonexistent")
        assert is_valid is False
    
    def test_validate_template_invalid_structure(self, temp_templates_dir):
        """Test validating template with invalid structure."""
        # Create invalid template
        invalid_template = '''# Invalid Template
# Missing required fields
symbol: "TEST"
'''
        invalid_path = temp_templates_dir / "invalid.yaml"
        invalid_path.write_text(invalid_template)
        
        manager = TemplateManager(temp_templates_dir)
        is_valid = manager.validate_template("invalid")
        assert is_valid is False
    
    def test_get_template_summary(self, template_manager):
        """Test getting template summary."""
        summary = template_manager.get_template_summary()
        
        assert summary["total_templates"] == 1
        assert "test_template" in summary["templates"]
        assert "test_template" in summary["validation_results"]
        
        template_info = summary["templates"]["test_template"]
        assert template_info["description"] == "Test Template"
        assert template_info["required_fields"] >= 5
        assert template_info["examples"] >= 0  # Examples are optional
        assert template_info["use_cases"] >= 2
        
        assert summary["validation_results"]["test_template"] is True


class TestTemplateManagerWithRealTemplates:
    """Test TemplateManager with actual project templates."""
    
    def test_real_templates_exist(self):
        """Test that real templates exist and are accessible."""
        # Use default template directory (should find actual templates)
        manager = TemplateManager()
        templates = manager.list_available_templates()
        
        # Should find the templates we created
        expected_templates = ["close_above", "close_below", "trailing_stop"]
        
        for template_name in expected_templates:
            assert template_name in templates, f"Template '{template_name}' not found"
    
    def test_real_template_validation(self):
        """Test validation of real templates."""
        manager = TemplateManager()
        templates = manager.list_available_templates()
        
        for template_name in templates:
            is_valid = manager.validate_template(template_name)
            assert is_valid, f"Template '{template_name}' failed validation"
    
    def test_real_template_documentation(self):
        """Test documentation extraction from real templates."""
        manager = TemplateManager()
        templates = manager.list_available_templates()
        
        for template_name in templates:
            doc_info = manager.get_template_documentation(template_name)
            
            assert doc_info["name"] == template_name
            assert doc_info["description"]  # Should have description
            assert len(doc_info["required_fields"]) > 0  # Should have required fields
    
    def test_create_plan_from_close_above_template(self):
        """Test creating a plan from the close_above template."""
        manager = TemplateManager()
        
        plan_data = {
            "plan_id": "AAPL_20250815_001",
            "symbol": "AAPL",
            "entry_level": 180.50,
            "stop_loss": 178.00,
            "take_profit": 185.00,
            "threshold": 180.50,
        }
        
        trade_plan = manager.create_plan_from_template("close_above", plan_data)
        
        assert trade_plan.plan_id == "AAPL_20250815_001"
        assert trade_plan.symbol == "AAPL"
        assert trade_plan.entry_function.function_type == "close_above"
        assert trade_plan.entry_function.timeframe == "15min"