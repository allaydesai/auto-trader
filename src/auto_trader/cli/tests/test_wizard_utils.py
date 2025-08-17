"""Tests for interactive wizard utilities."""

import pytest
from decimal import Decimal
from unittest.mock import Mock, patch

from ..wizard_utils import WizardFieldCollector
from ..wizard_preview import TradePlanPreview
from ..wizard_plan_utils import generate_plan_id, save_plan_to_yaml
from ...models import RiskCategory, ExecutionFunction, TradePlan
from ...risk_management import RiskManager
from config import ConfigLoader


class TestWizardFieldCollector:
    """Test suite for WizardFieldCollector."""
    
    @pytest.fixture
    def mock_config_loader(self):
        """Mock configuration loader."""
        config_loader = Mock(spec=ConfigLoader)
        config_loader.user_preferences.account_value = Decimal("10000")
        return config_loader
    
    @pytest.fixture
    def mock_risk_manager(self):
        """Mock risk manager."""
        risk_manager = Mock(spec=RiskManager)
        risk_manager.account_value = Decimal("10000")
        
        # Setup position_sizer mock
        risk_manager.position_sizer = Mock()
        risk_manager.position_sizer.calculate_position_size = Mock()
        
        # Setup portfolio_tracker mock
        risk_manager.portfolio_tracker = Mock()
        risk_manager.check_portfolio_risk_limit = Mock()
        
        return risk_manager
    
    @pytest.fixture
    def field_collector(self, mock_config_loader, mock_risk_manager):
        """Create field collector instance for testing."""
        return WizardFieldCollector(mock_config_loader, mock_risk_manager)
    
    def test_initialization(self, field_collector):
        """Test field collector initializes correctly."""
        assert field_collector.collected_data == {}
        assert field_collector.validation_engine is not None
        assert field_collector.console is not None
    
    @patch('auto_trader.cli.wizard_utils.Prompt.ask')
    def test_collect_symbol_valid(self, mock_prompt, field_collector):
        """Test collecting valid symbol."""
        mock_prompt.return_value = "aapl"
        
        result = field_collector.collect_symbol()
        
        assert result == "AAPL"
        assert field_collector.collected_data["symbol"] == "AAPL"
        mock_prompt.assert_called_once()
    
    @patch('auto_trader.cli.wizard_utils.Prompt.ask')
    def test_collect_symbol_with_cli_value(self, mock_prompt, field_collector):
        """Test collecting symbol with CLI pre-populated value."""
        result = field_collector.collect_symbol("MSFT")
        
        assert result == "MSFT"
        assert field_collector.collected_data["symbol"] == "MSFT"
        mock_prompt.assert_not_called()
    
    @patch('auto_trader.cli.wizard_utils.Prompt.ask')
    def test_collect_symbol_invalid_then_valid(self, mock_prompt, field_collector):
        """Test symbol validation with invalid input followed by valid."""
        mock_prompt.side_effect = ["TOOLONGSYMBOL123", "AAPL"]
        
        result = field_collector.collect_symbol()
        
        assert result == "AAPL"
        assert mock_prompt.call_count == 2
    
    @patch('auto_trader.cli.wizard_utils.Prompt.ask')
    def test_collect_entry_level_valid(self, mock_prompt, field_collector):
        """Test collecting valid entry level."""
        mock_prompt.return_value = "180.50"
        
        result = field_collector.collect_entry_level()
        
        assert result == Decimal("180.50")
        assert field_collector.collected_data["entry_level"] == Decimal("180.50")
    
    @patch('auto_trader.cli.wizard_utils.Prompt.ask')
    def test_collect_entry_level_with_cli_value(self, mock_prompt, field_collector):
        """Test collecting entry level with CLI pre-populated value."""
        result = field_collector.collect_entry_level("175.25")
        
        assert result == Decimal("175.25")
        mock_prompt.assert_not_called()
    
    @patch('auto_trader.cli.wizard_utils.Prompt.ask')
    def test_collect_entry_level_invalid_then_valid(self, mock_prompt, field_collector):
        """Test entry level validation with invalid input."""
        mock_prompt.side_effect = ["-100", "180.50"]
        
        result = field_collector.collect_entry_level()
        
        assert result == Decimal("180.50")
        assert mock_prompt.call_count == 2
    
    @patch('auto_trader.cli.wizard_utils.Prompt.ask')
    def test_collect_stop_loss_valid(self, mock_prompt, field_collector):
        """Test collecting valid stop loss."""
        entry_level = Decimal("180.50")
        mock_prompt.return_value = "178.00"
        
        result = field_collector.collect_stop_loss(entry_level)
        
        assert result == Decimal("178.00")
        assert field_collector.collected_data["stop_loss"] == Decimal("178.00")
    
    @patch('auto_trader.cli.wizard_utils.Prompt.ask')
    def test_collect_stop_loss_equal_to_entry_rejected(self, mock_prompt, field_collector):
        """Test stop loss equal to entry level is rejected."""
        entry_level = Decimal("180.50")
        mock_prompt.side_effect = ["180.50", "178.00"]
        
        result = field_collector.collect_stop_loss(entry_level)
        
        assert result == Decimal("178.00")
        assert mock_prompt.call_count == 2
    
    def test_collect_risk_category_valid(self, field_collector):
        """Test collecting valid risk category."""
        result = field_collector.collect_risk_category("normal")
        
        assert result == RiskCategory.NORMAL
        assert field_collector.collected_data["risk_category"] == RiskCategory.NORMAL
    
    @patch('auto_trader.cli.wizard_utils.Prompt.ask')
    def test_collect_risk_category_interactive(self, mock_prompt, field_collector):
        """Test interactive risk category collection."""
        mock_prompt.return_value = "large"
        
        result = field_collector.collect_risk_category()
        
        assert result == RiskCategory.LARGE
        mock_prompt.assert_called_once()
    
    def test_calculate_and_display_position_size(self, field_collector):
        """Test position size calculation and display."""
        # Setup mock position sizer result
        mock_position_result = Mock()
        mock_position_result.position_size = 100
        mock_position_result.dollar_risk = Decimal("200.00")
        mock_position_result.portfolio_risk_percentage = Decimal("2.0")
        
        field_collector.risk_manager.position_sizer.calculate_position_size.return_value = mock_position_result
        
        # Setup mock portfolio check
        mock_portfolio_check = Mock()
        mock_portfolio_check.passed = True
        mock_portfolio_check.current_risk = Decimal("1.5")
        mock_portfolio_check.new_trade_risk = Decimal("2.0")
        mock_portfolio_check.total_risk = Decimal("3.5")
        mock_portfolio_check.limit = Decimal("10.0")
        
        field_collector.risk_manager.check_portfolio_risk_limit.return_value = mock_portfolio_check
        
        position_size, dollar_risk = field_collector.calculate_and_display_position_size(
            Decimal("180.50"),
            Decimal("178.00"),
            RiskCategory.NORMAL
        )
        
        assert position_size == 100
        assert dollar_risk == Decimal("200.00")
    
    def test_calculate_position_size_risk_limit_exceeded(self, field_collector):
        """Test position size calculation when risk limit exceeded."""
        # Setup mock position sizer result
        mock_position_result = Mock()
        mock_position_result.position_size = 500
        mock_position_result.dollar_risk = Decimal("1500.00")
        mock_position_result.portfolio_risk_percentage = Decimal("15.0")
        
        field_collector.risk_manager.position_sizer.calculate_position_size.return_value = mock_position_result
        
        # Setup mock portfolio check - FAIL
        mock_portfolio_check = Mock()
        mock_portfolio_check.passed = False
        mock_portfolio_check.current_risk = Decimal("2.0")
        mock_portfolio_check.new_trade_risk = Decimal("15.0")
        mock_portfolio_check.total_risk = Decimal("17.0")
        mock_portfolio_check.limit = Decimal("10.0")
        
        field_collector.risk_manager.check_portfolio_risk_limit.return_value = mock_portfolio_check
        
        # Mock user confirmation to continue anyway
        with patch('auto_trader.cli.wizard_utils.Confirm.ask', return_value=True):
            position_size, dollar_risk = field_collector.calculate_and_display_position_size(
                Decimal("180.50"),
                Decimal("178.00"),
                RiskCategory.LARGE
            )
            
            assert position_size == 500
            assert dollar_risk == Decimal("1500.00")
    
    def test_calculate_position_size_risk_limit_cancelled(self, field_collector):
        """Test position size calculation cancelled when risk limit exceeded."""
        # Setup mock position sizer result
        mock_position_result = Mock()
        mock_position_result.position_size = 500
        mock_position_result.dollar_risk = Decimal("1500.00")
        mock_position_result.portfolio_risk_percentage = Decimal("15.0")
        
        field_collector.risk_manager.position_sizer.calculate_position_size.return_value = mock_position_result
        
        # Setup mock portfolio check - FAIL
        mock_portfolio_check = Mock()
        mock_portfolio_check.passed = False
        mock_portfolio_check.current_risk = Decimal("2.0")
        mock_portfolio_check.new_trade_risk = Decimal("15.0")
        mock_portfolio_check.total_risk = Decimal("17.0")
        mock_portfolio_check.limit = Decimal("10.0")
        
        field_collector.risk_manager.check_portfolio_risk_limit.return_value = mock_portfolio_check
        
        # Mock user confirmation to cancel
        with patch('auto_trader.cli.wizard_utils.Confirm.ask', return_value=False):
            with pytest.raises(ValueError, match="Portfolio risk limit exceeded"):
                field_collector.calculate_and_display_position_size(
                    Decimal("180.50"),
                    Decimal("178.00"),
                    RiskCategory.LARGE
                )
    
    @patch('auto_trader.cli.wizard_utils.Prompt.ask')
    def test_collect_take_profit_valid(self, mock_prompt, field_collector):
        """Test collecting valid take profit."""
        mock_prompt.return_value = "185.00"
        
        result = field_collector.collect_take_profit()
        
        assert result == Decimal("185.00")
        assert field_collector.collected_data["take_profit"] == Decimal("185.00")
    
    @patch('auto_trader.cli.wizard_utils.Prompt.ask')
    def test_collect_execution_functions(self, mock_prompt, field_collector):
        """Test collecting execution functions."""
        mock_prompt.side_effect = ["close_above", "15min", "stop_loss_take_profit", "15min"]
        
        entry_func, exit_func = field_collector.collect_execution_functions()
        
        assert isinstance(entry_func, ExecutionFunction)
        assert entry_func.function_type == "close_above"
        assert entry_func.timeframe == "15min"
        
        assert isinstance(exit_func, ExecutionFunction)
        assert exit_func.function_type == "stop_loss_take_profit"
        assert exit_func.timeframe == "15min"
    


class TestTradePlanPreview:
    """Test suite for TradePlanPreview."""
    
    @pytest.fixture
    def mock_console(self):
        """Mock console for testing."""
        return Mock()
    
    @pytest.fixture
    def preview_manager(self, mock_console):
        """Create preview manager instance."""
        return TradePlanPreview(mock_console)
    
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
            "calculated_position_size": 100,
            "dollar_risk": Decimal("250.00"),
            "entry_function": ExecutionFunction(
                function_type="close_above",
                timeframe="15min"
            ),
            "exit_function": ExecutionFunction(
                function_type="stop_loss_take_profit",
                timeframe="15min"
            ),
        }
    
    @patch('auto_trader.cli.wizard_preview.Prompt.ask')
    def test_show_preview_confirm(self, mock_prompt, preview_manager, sample_plan_data):
        """Test preview with user confirmation."""
        mock_prompt.return_value = "confirm"
        
        result = preview_manager.show_preview(sample_plan_data)
        
        assert result is True
        mock_prompt.assert_called_once()
    
    @patch('auto_trader.cli.wizard_preview.Prompt.ask')
    def test_show_preview_cancel(self, mock_prompt, preview_manager, sample_plan_data):
        """Test preview with user cancellation."""
        mock_prompt.return_value = "cancel"
        
        result = preview_manager.show_preview(sample_plan_data)
        
        assert result is False
        mock_prompt.assert_called_once()
    
    @patch('auto_trader.cli.wizard_preview.Prompt.ask')
    def test_show_preview_modify_then_confirm(self, mock_prompt, preview_manager, sample_plan_data):
        """Test preview with modification request then confirmation."""
        mock_prompt.side_effect = ["modify", "confirm"]
        
        result = preview_manager.show_preview(sample_plan_data)
        
        assert result is True
        assert mock_prompt.call_count == 2


class TestUtilityFunctions:
    """Test utility functions."""
    
    def test_generate_plan_id(self):
        """Test plan ID generation."""
        plan_id = generate_plan_id("AAPL")
        
        assert plan_id.startswith("AAPL_")
        assert plan_id.endswith("_001")
        assert len(plan_id.split("_")) == 3
    
    def test_save_plan_to_yaml(self, tmp_path):
        """Test saving plan to YAML file."""
        plan_data = {
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
        
        output_path = save_plan_to_yaml(plan_data, tmp_path)
        
        assert output_path.exists()
        assert output_path.name == "AAPL_20250817_001.yaml"
        
        # Verify file content can be loaded as TradePlan
        import yaml
        with open(output_path) as f:
            loaded_data = yaml.safe_load(f)
        
        # Convert back to TradePlan to validate structure
        trade_plan = TradePlan(**loaded_data)
        assert trade_plan.plan_id == "AAPL_20250817_001"
        assert trade_plan.symbol == "AAPL"


@pytest.fixture
def sample_config_loader():
    """Create a sample config loader for integration tests."""
    config_loader = Mock(spec=ConfigLoader)
    config_loader.user_preferences.account_value = Decimal("10000")
    return config_loader


@pytest.fixture
def sample_risk_manager():
    """Create a sample risk manager for integration tests."""
    risk_manager = Mock(spec=RiskManager)
    risk_manager.account_value = Decimal("10000")
    
    # Setup position_sizer mock
    risk_manager.position_sizer = Mock()
    risk_manager.position_sizer.calculate_position_size = Mock()
    
    # Setup portfolio_tracker mock
    risk_manager.portfolio_tracker = Mock()
    risk_manager.check_portfolio_risk_limit = Mock()
    
    # Mock portfolio summary
    risk_manager.get_portfolio_summary.return_value = {
        "account_value": 10000.0,
        "current_portfolio_risk": 2.5,
        "available_risk_capacity_percent": 7.5,
        "position_count": 2,
    }
    
    return risk_manager


class TestIntegrationScenarios:
    """Integration test scenarios for wizard workflow."""
    
    def test_complete_wizard_flow_valid_inputs(self, sample_config_loader, sample_risk_manager):
        """Test complete wizard flow with all valid inputs."""
        field_collector = WizardFieldCollector(sample_config_loader, sample_risk_manager)
        
        # Mock all prompts for complete flow
        with patch.multiple(
            'auto_trader.cli.wizard_utils.Prompt',
            ask=Mock(side_effect=[
                "AAPL",  # symbol
                "180.50",  # entry
                "178.00",  # stop
                "normal",  # risk category
                "185.00",  # take profit
                "close_above",  # entry function
                "15min",  # entry timeframe
                "stop_loss_take_profit",  # exit function
                "15min",  # exit timeframe
            ])
        ):
            # Mock position sizing
            mock_position_result = Mock()
            mock_position_result.position_size = 100
            mock_position_result.dollar_risk = Decimal("250.00")
            mock_position_result.portfolio_risk_percentage = Decimal("2.5")
            
            sample_risk_manager.position_sizer.calculate_position_size.return_value = mock_position_result
            
            # Mock portfolio check
            mock_portfolio_check = Mock()
            mock_portfolio_check.passed = True
            mock_portfolio_check.current_risk = Decimal("2.5")
            mock_portfolio_check.new_trade_risk = Decimal("2.5")
            mock_portfolio_check.total_risk = Decimal("5.0")
            mock_portfolio_check.limit = Decimal("10.0")
            
            sample_risk_manager.check_portfolio_risk_limit.return_value = mock_portfolio_check
            
            # Collect all fields
            symbol = field_collector.collect_symbol()
            entry = field_collector.collect_entry_level()
            stop = field_collector.collect_stop_loss(entry)
            risk = field_collector.collect_risk_category()
            position_size, dollar_risk = field_collector.calculate_and_display_position_size(entry, stop, risk)
            target = field_collector.collect_take_profit()
            entry_func, exit_func = field_collector.collect_execution_functions()
            
            # Verify results
            assert symbol == "AAPL"
            assert entry == Decimal("180.50")
            assert stop == Decimal("178.00")
            assert risk == RiskCategory.NORMAL
            assert position_size == 100
            assert dollar_risk == Decimal("250.00")
            assert target == Decimal("185.00")
            assert entry_func.function_type == "close_above"
            assert exit_func.function_type == "stop_loss_take_profit"
    
    def test_cli_shortcuts_prepopulation(self, sample_config_loader, sample_risk_manager):
        """Test wizard flow with CLI shortcuts pre-populating fields."""
        field_collector = WizardFieldCollector(sample_config_loader, sample_risk_manager)
        
        # Test symbol with CLI value
        symbol = field_collector.collect_symbol("MSFT")
        assert symbol == "MSFT"
        
        # Test entry with CLI value
        entry = field_collector.collect_entry_level("150.25")
        assert entry == Decimal("150.25")
        
        # Test stop with CLI value
        stop = field_collector.collect_stop_loss(entry, "148.00")
        assert stop == Decimal("148.00")
        
        # Test risk with CLI value
        risk = field_collector.collect_risk_category("large")
        assert risk == RiskCategory.LARGE
        
        # Test target with CLI value
        target = field_collector.collect_take_profit("155.00")
        assert target == Decimal("155.00")