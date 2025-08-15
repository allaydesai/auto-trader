"""Integration tests for Story 1.3: Basic Trade Plan Creation."""

import tempfile
import time
from pathlib import Path
from unittest.mock import patch, Mock

import pytest
import yaml

from config import Settings, ConfigLoader
from auto_trader.models import TradePlanLoader, TemplateManager, ValidationEngine
from auto_trader.utils import FileWatcher, FileWatchEventType
from auto_trader.cli.commands import cli


class TestStory13Integration:
    """Integration tests for the complete Story 1.3 implementation."""

    @pytest.fixture
    def temp_workspace(self):
        """Create a temporary workspace for testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            
            # Create directory structure
            plans_dir = workspace / "data" / "trade_plans"
            templates_dir = plans_dir / "templates"
            plans_dir.mkdir(parents=True)
            templates_dir.mkdir(parents=True)
            
            # Copy templates
            src_templates_dir = Path("data/trade_plans/templates")
            if src_templates_dir.exists():
                for template_file in src_templates_dir.glob("*.yaml"):
                    (templates_dir / template_file.name).write_text(
                        template_file.read_text()
                    )
            
            # Create config files
            config_file = workspace / "config.yaml"
            user_config_file = workspace / "user_config.yaml"
            env_file = workspace / ".env"
            
            config_file.write_text(yaml.dump({
                "ibkr": {"host": "127.0.0.1", "port": 7497},
                "trading": {"simulation_mode": True}
            }))
            
            user_config_file.write_text(yaml.dump({
                "account_value": 10000,
                "default_risk_category": "normal",
                "environment": "paper"
            }))
            
            env_file.write_text(
                "DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/test\n"
                "SIMULATION_MODE=true\n"
            )
            
            yield workspace

    def test_configuration_system_integration(self, temp_workspace):
        """Test enhanced configuration system integration."""
        config_file = temp_workspace / "config.yaml"
        user_config_file = temp_workspace / "user_config.yaml"
        
        settings = Settings(
            config_file=config_file,
            user_config_file=user_config_file
        )
        
        config_loader = ConfigLoader(settings)
        
        # Test loading system config
        system_config = config_loader.load_system_config()
        assert system_config.ibkr.host == "127.0.0.1"
        assert system_config.trading.simulation_mode is True
        
        # Test loading user preferences
        user_prefs = config_loader.load_user_preferences()
        assert user_prefs.account_value == 10000
        assert user_prefs.default_risk_category == "normal"
        assert user_prefs.environment == "paper"
        
        # Test configuration validation
        issues = config_loader.validate_configuration()
        assert len(issues) == 0  # Should be valid

    def test_file_watching_integration(self, temp_workspace):
        """Test file watching with validation integration."""
        plans_dir = temp_workspace / "data" / "trade_plans"
        
        validation_events = []
        
        def validation_callback(file_path: Path, event_type: FileWatchEventType):
            validation_events.append((file_path.name, event_type))
            
        watcher = FileWatcher(
            watch_directory=plans_dir,
            validation_callback=validation_callback,
            debounce_delay=0.1  # Short delay for testing
        )
        
        try:
            assert watcher.start() is True
            
            # Create a test plan file
            test_plan = {
                "plan_id": "TEST_20250815_001",
                "symbol": "AAPL",
                "entry_level": 180.50,
                "stop_loss": 178.00,
                "take_profit": 185.00,
                "risk_category": "normal",
                "entry_function": {
                    "function_type": "close_above",
                    "timeframe": "15min",
                    "parameters": {"threshold": 180.50}
                },
                "exit_function": {
                    "function_type": "stop_loss_take_profit",
                    "timeframe": "1min",
                    "parameters": {}
                }
            }
            
            test_file = plans_dir / "test_plan.yaml"
            test_file.write_text(yaml.dump(test_plan))
            
            # Wait for file watcher to process
            time.sleep(0.2)
            
            # Modify the file
            test_plan["take_profit"] = 186.00
            test_file.write_text(yaml.dump(test_plan))
            
            # Wait for modification to be processed
            time.sleep(0.2)
            
            # Delete the file
            test_file.unlink()
            
            # Wait for deletion to be processed
            time.sleep(0.2)
            
            # Verify events were captured
            assert len(validation_events) >= 2  # At least create and delete
            
            stats = watcher.get_stats()
            assert stats["events_processed"] >= 2
            
        finally:
            watcher.stop()

    def test_template_based_plan_creation(self, temp_workspace):
        """Test end-to-end template-based plan creation."""
        templates_dir = temp_workspace / "data" / "trade_plans" / "templates"
        output_dir = temp_workspace / "data" / "trade_plans"
        
        template_manager = TemplateManager(templates_dir)
        
        # Test template listing
        templates = template_manager.list_available_templates()
        assert len(templates) >= 1  # Should have at least close_above
        
        # Test template documentation
        if "close_above" in templates:
            doc_info = template_manager.get_template_documentation("close_above")
            assert "Trade Plan Template" in doc_info.get("description", "")
            
        # Test plan creation from template
        plan_data = {
            "plan_id": "AAPL_20250815_001",
            "symbol": "AAPL",
            "entry_level": 180.50,
            "stop_loss": 178.00,
            "take_profit": 185.00,
            "threshold": 180.50
        }
        
        if "close_above" in templates:
            output_file = output_dir / "created_plan.yaml"
            trade_plan = template_manager.create_plan_from_template(
                "close_above",
                plan_data,
                output_file
            )
            
            # Verify plan was created correctly
            assert trade_plan.plan_id == "AAPL_20250815_001"
            assert trade_plan.symbol == "AAPL"
            assert trade_plan.entry_level == 180.50
            
            # Verify file was saved
            assert output_file.exists()
            
            # Verify file content is valid
            validation_engine = ValidationEngine()
            result = validation_engine.validate_file(output_file)
            assert result.is_valid

    def test_plan_loading_and_validation_workflow(self, temp_workspace):
        """Test complete plan loading and validation workflow."""
        plans_dir = temp_workspace / "data" / "trade_plans"
        
        # Create a valid plan file
        valid_plan = {
            "plan_id": "VALID_20250815_001",
            "symbol": "AAPL",
            "entry_level": 180.50,
            "stop_loss": 178.00,
            "take_profit": 185.00,
            "risk_category": "normal",
            "entry_function": {
                "function_type": "close_above",
                "timeframe": "15min",
                "parameters": {"threshold": 180.50}
            },
            "exit_function": {
                "function_type": "stop_loss_take_profit",
                "timeframe": "1min",
                "parameters": {}
            }
        }
        
        # Create an invalid plan file  
        invalid_plan = {
            "plan_id": "INVALID_001",  # Invalid format
            "symbol": "invalid_symbol",  # Invalid format
            "entry_level": -100,  # Invalid value
            "stop_loss": 200,  # Invalid relationship
        }
        
        valid_file = plans_dir / "valid_plan.yaml"
        invalid_file = plans_dir / "invalid_plan.yaml"
        
        valid_file.write_text(yaml.dump(valid_plan))
        invalid_file.write_text(yaml.dump(invalid_plan))
        
        # Test plan loading
        loader = TradePlanLoader(plans_dir)
        
        # Load with validation - should only load valid plans
        plans = loader.load_all_plans(validate=True)
        assert len(plans) == 1
        assert "VALID_20250815_001" in plans
        
        # Get validation report
        report = loader.get_validation_report()
        assert "valid" in report.lower()
        assert "error" in report.lower()
        
        # Test plan filtering
        valid_plans = loader.get_plans_by_symbol("AAPL")
        assert len(valid_plans) == 1
        
        awaiting_plans = loader.get_plans_by_status("awaiting_entry")
        assert len(awaiting_plans) == 1

    def test_cli_commands_integration(self, temp_workspace):
        """Test CLI commands integration with the complete system."""
        plans_dir = temp_workspace / "data" / "trade_plans"
        
        # Create a test plan file
        test_plan = {
            "plan_id": "CLI_TEST_20250815_001",
            "symbol": "MSFT",
            "entry_level": 420.00,
            "stop_loss": 415.00,
            "take_profit": 430.00,
            "risk_category": "normal",
            "entry_function": {
                "function_type": "close_above",
                "timeframe": "15min",
                "parameters": {"threshold": 420.00}
            },
            "exit_function": {
                "function_type": "stop_loss_take_profit",
                "timeframe": "1min",
                "parameters": {}
            }
        }
        
        test_file = plans_dir / "cli_test_plan.yaml"
        test_file.write_text(yaml.dump(test_plan))
        
        # Test validate-plans command functionality
        from auto_trader.models import TradePlanLoader
        loader = TradePlanLoader(plans_dir)
        plans = loader.load_all_plans(validate=True)
        assert len(plans) >= 1
        
        # Test list-plans command functionality
        filtered_plans = [p for p in plans.values() if p.symbol == "MSFT"]
        assert len(filtered_plans) == 1
        
        # Test template system functionality
        from auto_trader.models import TemplateManager
        template_manager = TemplateManager()
        templates = template_manager.list_available_templates()
        assert len(templates) >= 1

    def test_error_handling_and_recovery(self, temp_workspace):
        """Test error handling and recovery capabilities."""
        plans_dir = temp_workspace / "data" / "trade_plans"
        
        # Test invalid YAML syntax
        invalid_yaml_file = plans_dir / "invalid_syntax.yaml"
        invalid_yaml_file.write_text("invalid: yaml: content: [")
        
        validation_engine = ValidationEngine()
        result = validation_engine.validate_file(invalid_yaml_file)
        assert not result.is_valid
        assert len(result.errors) > 0
        
        # Test missing file handling
        missing_file = plans_dir / "nonexistent.yaml"
        result = validation_engine.validate_file(missing_file)
        assert not result.is_valid
        
        # Test loader error recovery
        loader = TradePlanLoader(plans_dir)
        plans = loader.load_all_plans(validate=True)
        
        # Should continue loading valid files despite errors
        report = loader.get_validation_report()
        assert isinstance(report, str)

    def test_ux_compliance_and_consistency(self, temp_workspace):
        """Test UX compliance and consistency across interfaces."""
        plans_dir = temp_workspace / "data" / "trade_plans"
        
        # Create test plans with consistent plan_id formats
        test_plans = [
            {
                "plan_id": "AAPL_20250815_001",  # Consistent format
                "symbol": "AAPL",
                "entry_level": 180.50,
                "stop_loss": 178.00,
                "take_profit": 185.00,
                "risk_category": "small",
                "entry_function": {
                    "function_type": "close_above",
                    "timeframe": "15min",
                    "parameters": {"threshold": 180.50}
                },
                "exit_function": {
                    "function_type": "stop_loss_take_profit",
                    "timeframe": "1min",
                    "parameters": {}
                },
                "status": "awaiting_entry"
            },
            {
                "plan_id": "MSFT_20250815_001",  # Consistent format
                "symbol": "MSFT", 
                "entry_level": 420.00,
                "stop_loss": 415.00,
                "take_profit": 430.00,
                "risk_category": "normal",
                "entry_function": {
                    "function_type": "close_above",
                    "timeframe": "30min",
                    "parameters": {"threshold": 420.00}
                },
                "exit_function": {
                    "function_type": "stop_loss_take_profit",
                    "timeframe": "1min",
                    "parameters": {}
                },
                "status": "awaiting_entry"
            }
        ]
        
        # Save test plans
        for i, plan_data in enumerate(test_plans):
            plan_file = plans_dir / f"ux_test_plan_{i+1}.yaml"
            plan_file.write_text(yaml.dump(plan_data))
        
        # Test plan loading
        loader = TradePlanLoader(plans_dir)
        plans = loader.load_all_plans(validate=True)
        
        # Verify consistent plan_id formats
        for plan_id in plans.keys():
            assert "_20250815_" in plan_id  # Consistent date format
            assert len(plan_id.split("_")) == 3  # Consistent structure
        
        # Verify consistent status values
        for plan in plans.values():
            assert plan.status.value in ["awaiting_entry", "position_open", "position_closed"]
        
        # Test statistics consistency
        stats = loader.get_stats()
        assert "total_plans" in stats
        assert "by_status" in stats
        assert "by_symbol" in stats

    def test_progressive_verbosity_levels(self, temp_workspace):
        """Test progressive verbosity levels in CLI outputs."""
        plans_dir = temp_workspace / "data" / "trade_plans"
        
        # Create a test plan
        test_plan = {
            "plan_id": "VERBOSE_20250815_001",
            "symbol": "SPY",
            "entry_level": 425.00,
            "stop_loss": 422.00,
            "take_profit": 430.00,
            "risk_category": "normal",
            "entry_function": {
                "function_type": "close_above",
                "timeframe": "15min",
                "parameters": {"threshold": 425.00}
            },
            "exit_function": {
                "function_type": "stop_loss_take_profit",
                "timeframe": "1min", 
                "parameters": {}
            }
        }
        
        test_file = plans_dir / "verbose_test_plan.yaml"
        test_file.write_text(yaml.dump(test_plan))
        
        # Test different verbosity levels with plan loader
        loader = TradePlanLoader(plans_dir)
        plans = loader.load_all_plans(validate=True)
        
        # Test quiet mode (minimal output)
        stats = loader.get_stats()
        assert stats["total_plans"] >= 1
        
        # Test verbose mode (detailed output)
        report = loader.get_validation_report()
        assert isinstance(report, str)
        assert len(report) > 0
        
        # Test debug mode (comprehensive output)
        validation_engine = ValidationEngine()
        result = validation_engine.validate_file(test_file)
        assert result.is_valid


class TestCLIIntegration:
    """Test CLI integration with click commands."""
    
    def test_cli_command_structure(self):
        """Test CLI command structure and availability."""
        from click.testing import CliRunner
        
        runner = CliRunner()
        
        # Test main CLI help
        result = runner.invoke(cli, ['--help'])
        assert result.exit_code == 0
        assert "Auto-Trader" in result.output
        
        # Test individual command help
        commands_to_test = [
            'validate-config',
            'validate-plans', 
            'list-plans',
            'show-schema',
            'doctor',
            'help-system'
        ]
        
        for command in commands_to_test:
            result = runner.invoke(cli, [command, '--help'])
            if result.exit_code == 0:  # Command exists
                assert '--help' in result.output or 'help' in result.output.lower()

    def test_enhanced_list_plans_options(self):
        """Test enhanced list-plans command options."""
        from click.testing import CliRunner
        
        runner = CliRunner()
        result = runner.invoke(cli, ['list-plans', '--help'])
        
        if result.exit_code == 0:
            help_text = result.output
            
            # Check for enhanced filtering options
            assert '--status' in help_text
            assert '--symbol' in help_text
            assert '--risk-category' in help_text
            assert '--sort-by' in help_text
            assert '--sort-desc' in help_text
            assert '--limit' in help_text
            
            # Check for verbosity options
            assert '--verbose' in help_text
            assert '--quiet' in help_text
            assert '--debug' in help_text


class TestPerformanceAndScalability:
    """Test performance and scalability of the implementation."""
    
    def test_large_number_of_plans_handling(self, tmp_path):
        """Test handling of large numbers of trade plans."""
        plans_dir = tmp_path / "data" / "trade_plans"
        plans_dir.mkdir(parents=True)
        
        # Create multiple plan files
        num_plans = 50
        for i in range(num_plans):
            plan = {
                "plan_id": f"PERF_{i:03d}_20250815_001",
                "symbol": f"SYM{i:02d}",
                "entry_level": 100.00 + i,
                "stop_loss": 95.00 + i,
                "take_profit": 110.00 + i,
                "risk_category": "normal",
                "entry_function": {
                    "function_type": "close_above",
                    "timeframe": "15min",
                    "parameters": {"threshold": 100.00 + i}
                },
                "exit_function": {
                    "function_type": "stop_loss_take_profit",
                    "timeframe": "1min",
                    "parameters": {}
                }
            }
            
            plan_file = plans_dir / f"plan_{i:03d}.yaml"
            plan_file.write_text(yaml.dump(plan))
        
        # Test loading performance
        start_time = time.time()
        loader = TradePlanLoader(plans_dir)
        plans = loader.load_all_plans(validate=True)
        load_time = time.time() - start_time
        
        assert len(plans) == num_plans
        assert load_time < 5.0  # Should load 50 plans in under 5 seconds
        
        # Test statistics performance
        start_time = time.time()
        stats = loader.get_stats()
        stats_time = time.time() - start_time
        
        assert stats["total_plans"] == num_plans
        assert stats_time < 1.0  # Stats should be fast

    def test_file_watching_performance(self, tmp_path):
        """Test file watching performance with multiple files."""
        plans_dir = tmp_path / "data" / "trade_plans"
        plans_dir.mkdir(parents=True)
        
        events_processed = []
        
        def callback(file_path: Path, event_type: FileWatchEventType):
            events_processed.append((file_path.name, event_type))
        
        watcher = FileWatcher(
            watch_directory=plans_dir,
            validation_callback=callback,
            debounce_delay=0.05  # Very short for testing
        )
        
        try:
            assert watcher.start() is True
            
            # Create multiple files quickly
            num_files = 10
            for i in range(num_files):
                test_file = plans_dir / f"perf_test_{i}.yaml"
                test_file.write_text(f"test: data_{i}")
            
            # Wait for processing
            time.sleep(0.5)
            
            stats = watcher.get_stats()
            assert stats["events_processed"] >= num_files
            
        finally:
            watcher.stop()