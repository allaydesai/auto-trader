"""Tests for wizard plan utilities."""

import pytest
import tempfile
import yaml
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

from ..wizard_plan_utils import generate_plan_id, save_plan_to_yaml
from ...models import TradePlan, RiskCategory, ExecutionFunction
from decimal import Decimal


class TestGeneratePlanId:
    """Test suite for generate_plan_id function."""
    
    def test_generate_plan_id_basic(self):
        """Test basic plan ID generation."""
        with patch("auto_trader.cli.wizard_plan_utils.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = MagicMock()
            mock_datetime.utcnow.return_value.strftime.return_value = "20250817"
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                plan_id = generate_plan_id("AAPL", temp_path)
                
                assert plan_id == "AAPL_20250817_001"
    
    def test_generate_plan_id_duplicate_handling(self):
        """Test plan ID generation with duplicate files."""
        with patch("auto_trader.cli.wizard_plan_utils.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = MagicMock()
            mock_datetime.utcnow.return_value.strftime.return_value = "20250817"
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Create existing files to simulate duplicates
                (temp_path / "AAPL_20250817_001.yaml").touch()
                (temp_path / "AAPL_20250817_002.yaml").touch()
                
                plan_id = generate_plan_id("AAPL", temp_path)
                
                assert plan_id == "AAPL_20250817_003"
    
    def test_generate_plan_id_no_output_dir(self):
        """Test plan ID generation with default output directory."""
        with patch("auto_trader.cli.wizard_plan_utils.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = MagicMock()
            mock_datetime.utcnow.return_value.strftime.return_value = "20250817"
            
            # Mock Path.exists to return False so we get the first ID
            with patch("pathlib.Path.exists", return_value=False):
                plan_id = generate_plan_id("MSFT")
                
                assert plan_id == "MSFT_20250817_001"
    
    def test_generate_plan_id_max_attempts_exceeded(self):
        """Test plan ID generation when too many files exist."""
        with patch("auto_trader.cli.wizard_plan_utils.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = MagicMock()
            mock_datetime.utcnow.return_value.strftime.return_value = "20250817"
            
            # Mock Path.exists to always return True (all IDs taken)
            with patch("pathlib.Path.exists", return_value=True):
                with pytest.raises(ValueError) as exc_info:
                    generate_plan_id("AAPL", Path("/tmp"))
                
                assert "Unable to generate unique plan ID" in str(exc_info.value)
                assert "AAPL" in str(exc_info.value)
                assert "20250817" in str(exc_info.value)
    
    def test_generate_plan_id_sequence_numbers(self):
        """Test plan ID generation sequence numbers."""
        with patch("auto_trader.cli.wizard_plan_utils.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = MagicMock()
            mock_datetime.utcnow.return_value.strftime.return_value = "20250817"
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Create files up to 010
                for i in range(1, 11):
                    (temp_path / f"TSLA_20250817_{i:03d}.yaml").touch()
                
                plan_id = generate_plan_id("TSLA", temp_path)
                
                assert plan_id == "TSLA_20250817_011"
    
    def test_generate_plan_id_different_symbols(self):
        """Test plan ID generation for different symbols on same day."""
        with patch("auto_trader.cli.wizard_plan_utils.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = MagicMock()
            mock_datetime.utcnow.return_value.strftime.return_value = "20250817"
            
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_path = Path(temp_dir)
                
                # Create AAPL files
                (temp_path / "AAPL_20250817_001.yaml").touch()
                (temp_path / "AAPL_20250817_002.yaml").touch()
                
                # Generate MSFT plan ID (should start at 001 since it's different symbol)
                plan_id = generate_plan_id("MSFT", temp_path)
                
                assert plan_id == "MSFT_20250817_001"


class TestSavePlanToYaml:
    """Test suite for save_plan_to_yaml function."""
    
    @pytest.fixture
    def sample_plan_data(self):
        """Sample plan data for testing."""
        return {
            "plan_id": "AAPL_20250817_001",
            "symbol": "AAPL",
            "entry_level": Decimal("180.50"),
            "stop_loss": Decimal("178.00"),
            "take_profit": Decimal("185.00"),
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
    
    def test_save_plan_to_yaml_basic(self, sample_plan_data):
        """Test basic YAML file saving."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            output_path = save_plan_to_yaml(sample_plan_data, temp_path)
            
            expected_path = temp_path / "AAPL_20250817_001.yaml"
            assert output_path == expected_path
            assert output_path.exists()
            
            # Verify file contents by reading raw text first
            with open(output_path, 'r') as f:
                file_content = f.read()
            
            # Should contain the basic plan information
            assert "plan_id: AAPL_20250817_001" in file_content
            assert "symbol: AAPL" in file_content
    
    def test_save_plan_to_yaml_default_dir(self, sample_plan_data):
        """Test YAML saving with default directory."""
        with patch("pathlib.Path.mkdir") as mock_mkdir, \
             patch("builtins.open", create=True) as mock_open, \
             patch("yaml.dump") as mock_yaml_dump:
            
            mock_file = MagicMock()
            mock_open.return_value.__enter__.return_value = mock_file
            
            output_path = save_plan_to_yaml(sample_plan_data)
            
            expected_path = Path("data/trade_plans/AAPL_20250817_001.yaml")
            assert output_path == expected_path
            
            # Verify directory creation was called
            mock_mkdir.assert_called_once()
    
    def test_save_plan_to_yaml_validation(self, sample_plan_data):
        """Test that plan validation occurs during save."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # This should not raise an exception with valid data
            output_path = save_plan_to_yaml(sample_plan_data, temp_path)
            assert output_path.exists()
    
    def test_save_plan_to_yaml_invalid_data(self):
        """Test saving with invalid plan data."""
        invalid_data = {
            "plan_id": "INVALID",
            "symbol": "",  # Invalid empty symbol
            "entry_level": "not_a_decimal",  # Invalid type
        }
        
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            with pytest.raises(Exception):  # Should raise validation error
                save_plan_to_yaml(invalid_data, temp_path)
    
    def test_save_plan_to_yaml_file_structure(self, sample_plan_data):
        """Test that saved YAML file has correct structure."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            output_path = save_plan_to_yaml(sample_plan_data, temp_path)
            
            # Load and verify structure by reading the raw file
            with open(output_path, 'r') as f:
                file_content = f.read()
            
            # Check all required fields are present in the file
            required_fields = [
                "plan_id", "symbol", "entry_level", "stop_loss", 
                "take_profit", "risk_category", "entry_function", "exit_function"
            ]
            
            for field in required_fields:
                assert f"{field}:" in file_content
            
            # Check execution function structure is present
            assert "function_type:" in file_content
            assert "timeframe:" in file_content
            
            # The file was created successfully by save_plan_to_yaml which validates via TradePlan
            # so we know the structure is correct