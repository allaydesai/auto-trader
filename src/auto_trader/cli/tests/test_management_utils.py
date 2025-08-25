"""Tests for plan management utility functions."""

import os
import tempfile
import shutil
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

import pytest
from rich.console import Console
from rich.table import Table

from ..management_utils import (
    create_plan_backup,
    verify_backup,
    get_portfolio_risk_summary,
    calculate_all_plan_risks,
    format_risk_indicator,
    format_plan_status,
    create_plans_table,
    create_portfolio_summary_panel,
    validate_plans_comprehensive,
    _perform_plan_update,
    PlanManagementError,
    BackupCreationError,
    BackupVerificationError,
    PlanLoadingError,
    ValidationError,
    FileSystemError,
    RiskCalculationError,
)
from ...models import TradePlan, TradePlanStatus, RiskCategory


@pytest.fixture
def temp_dir():
    """Provide temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_plan():
    """Provide sample trade plan for testing."""
    return TradePlan(
        plan_id="AAPL_20250822_001",
        symbol="AAPL",
        entry_level=Decimal("180.50"),
        stop_loss=Decimal("178.00"),
        take_profit=Decimal("185.00"),
        risk_category=RiskCategory.NORMAL,
        status=TradePlanStatus.AWAITING_ENTRY,
        entry_function={
            "function_type": "close_above",
            "timeframe": "15min",
            "parameters": {"threshold": "180.50"}
        },
        exit_function={
            "function_type": "stop_loss_take_profit",
            "timeframe": "1min",
            "parameters": {}
        },
    )


@pytest.fixture
def mock_risk_manager():
    """Provide mock risk manager for testing."""
    mock_rm = Mock()
    mock_rm.portfolio_tracker.get_current_portfolio_risk.return_value = Decimal("5.2")
    
    # Mock validation result
    mock_validation = Mock()
    mock_validation.passed = True
    mock_validation.position_size_result = Mock()
    mock_validation.position_size_result.position_size = 100
    mock_validation.position_size_result.risk_amount_percent = Decimal("2.1")
    mock_validation.position_size_result.risk_amount_dollars = Decimal("250.00")
    
    mock_rm.validate_trade_plan.return_value = mock_validation
    return mock_rm


class TestBackupCreation:
    """Test plan backup functionality."""
    
    def test_create_plan_backup_success(self, temp_dir):
        """Test successful plan backup creation."""
        # Create test plan file
        plan_file = temp_dir / "test_plan.yaml"
        plan_file.write_text("test content")
        
        backup_dir = temp_dir / "backups"
        
        # Create backup
        backup_path = create_plan_backup(plan_file, backup_dir)
        
        # Verify backup was created
        assert backup_path.exists()
        assert backup_path.parent == backup_dir
        assert backup_path.name.startswith("test_plan.backup.")
        assert backup_path.name.endswith(".yaml")
        assert backup_path.read_text() == "test content"
    
    def test_create_plan_backup_creates_directory(self, temp_dir):
        """Test backup creation creates directory if it doesn't exist."""
        plan_file = temp_dir / "test_plan.yaml"
        plan_file.write_text("content")
        
        backup_dir = temp_dir / "nonexistent" / "backups"
        
        backup_path = create_plan_backup(plan_file, backup_dir)
        
        assert backup_dir.exists()
        assert backup_path.exists()
    
    def test_create_plan_backup_file_not_exists(self, temp_dir):
        """Test backup creation fails when source file doesn't exist."""
        nonexistent_file = temp_dir / "nonexistent.yaml"
        backup_dir = temp_dir / "backups"
        
        with pytest.raises(BackupCreationError):
            create_plan_backup(nonexistent_file, backup_dir)


class TestRiskIndicatorFormatting:
    """Test risk indicator formatting functions."""
    
    def test_format_risk_indicator_safe(self):
        """Test risk indicator for safe levels."""
        result = format_risk_indicator(Decimal("3.0"), Decimal("10.0"))
        assert result == "🟢 3.0%"
    
    def test_format_risk_indicator_warning(self):
        """Test risk indicator for warning levels (80% of limit)."""
        result = format_risk_indicator(Decimal("8.5"), Decimal("10.0"))
        assert result == "🟡 8.5%"
    
    def test_format_risk_indicator_danger(self):
        """Test risk indicator for dangerous levels (over limit)."""
        result = format_risk_indicator(Decimal("11.0"), Decimal("10.0"))
        assert result == "🔴 11.0%"
    
    def test_format_plan_status_all_statuses(self):
        """Test plan status formatting for all status types."""
        expected_results = {
            TradePlanStatus.AWAITING_ENTRY: "✅ awaiting_entry",
            TradePlanStatus.POSITION_OPEN: "🔄 position_open",
            TradePlanStatus.COMPLETED: "✅ completed",
            TradePlanStatus.CANCELLED: "⏹️ cancelled",
            TradePlanStatus.ERROR: "❌ error",
        }
        
        for status, expected in expected_results.items():
            result = format_plan_status(status)
            assert result == expected


class TestPortfolioRiskSummary:
    """Test portfolio risk summary calculation."""
    
    def test_get_portfolio_risk_summary(self, sample_plan, mock_risk_manager):
        """Test portfolio risk summary calculation."""
        plans = [sample_plan]
        
        result = get_portfolio_risk_summary(mock_risk_manager, plans)
        
        assert result["current_risk_percent"] == Decimal("5.2")
        assert result["portfolio_limit_percent"] == Decimal("10.0")
        assert result["remaining_capacity_percent"] == Decimal("4.8")
        assert result["capacity_utilization_percent"] == Decimal("52.00")  # Fixed: (5.2/10.0)*100
        assert not result["exceeds_limit"]
        assert not result["near_limit"]
        assert sample_plan.plan_id in result["plan_risks"]
    
    def test_get_portfolio_risk_summary_near_limit(self, sample_plan, mock_risk_manager):
        """Test portfolio risk summary when near limit."""
        mock_risk_manager.portfolio_tracker.get_current_portfolio_risk.return_value = Decimal("8.5")
        
        result = get_portfolio_risk_summary(mock_risk_manager, [sample_plan])
        
        assert result["near_limit"]
        assert not result["exceeds_limit"]
    
    def test_get_portfolio_risk_summary_over_limit(self, sample_plan, mock_risk_manager):
        """Test portfolio risk summary when over limit."""
        mock_risk_manager.portfolio_tracker.get_current_portfolio_risk.return_value = Decimal("11.0")
        
        result = get_portfolio_risk_summary(mock_risk_manager, [sample_plan])
        
        assert result["exceeds_limit"]


class TestTableCreation:
    """Test Rich table creation functions."""
    
    def test_create_plans_table_basic(self, sample_plan, mock_risk_manager):
        """Test basic plans table creation."""
        plans = [sample_plan]
        
        # Create mock risk data
        plan_risk_data = {
            sample_plan.plan_id: {
                "risk_percent": Decimal("2.5"),
                "position_size": 100,
                "is_valid": True
            }
        }
        
        table = create_plans_table(plans, plan_risk_data, show_verbose=False)
        
        assert isinstance(table, Table)
        assert table.title == "📊 TRADE PLANS"
        assert len(table.columns) == 5  # Basic columns
    
    def test_create_plans_table_verbose(self, sample_plan, mock_risk_manager):
        """Test verbose plans table creation."""
        plans = [sample_plan]
        
        # Create mock risk data  
        plan_risk_data = {
            sample_plan.plan_id: {
                "risk_percent": Decimal("2.5"),
                "position_size": 100,
                "is_valid": True
            }
        }
        
        table = create_plans_table(plans, plan_risk_data, show_verbose=True)
        
        assert isinstance(table, Table)
        assert len(table.columns) == 9  # Basic + verbose columns
    
    def test_create_portfolio_summary_panel(self):
        """Test portfolio summary panel creation."""
        portfolio_data = {
            "current_risk_percent": Decimal("6.2"),
            "portfolio_limit_percent": Decimal("10.0"),
            "remaining_capacity_percent": Decimal("3.8"),
            "capacity_utilization_percent": Decimal("62.0"),
            "exceeds_limit": False,
            "near_limit": False,
        }
        
        panel = create_portfolio_summary_panel(portfolio_data)
        
        assert panel.title == "Portfolio Risk Summary"
        assert "6.2%" in panel.renderable
        assert "62%" in panel.renderable


class TestComprehensiveValidation:
    """Test comprehensive plan validation function."""
    
    @patch('auto_trader.cli.management_utils.TradePlanLoader')
    def test_validate_plans_comprehensive_success(self, mock_loader_class, temp_dir, mock_risk_manager):
        """Test successful comprehensive validation."""
        # Setup mocks
        mock_validation_engine = Mock()
        mock_validation_result = Mock()
        mock_validation_result.is_valid = True
        mock_validation_result.errors = []
        mock_validation_engine.validate_file.return_value = mock_validation_result
        
        mock_loader = Mock()
        mock_loader.load_plan_from_file.return_value = Mock()
        mock_loader_class.return_value = mock_loader
        
        # Create test files
        test_file = temp_dir / "test.yaml"
        test_file.write_text("test content")
        
        result = validate_plans_comprehensive(
            plans_dir=temp_dir,
            validation_engine=mock_validation_engine,
            risk_manager=mock_risk_manager,
        )
        
        assert result["files_checked"] == 1
        assert result["syntax_passed"] == 1
        assert result["business_logic_passed"] == 1
        assert result["portfolio_risk_passed"]
    
    @patch('auto_trader.cli.management_utils.TradePlanLoader')
    def test_validate_plans_comprehensive_syntax_error(self, mock_loader_class, temp_dir, mock_risk_manager):
        """Test validation with syntax errors."""
        mock_validation_engine = Mock()
        mock_validation_result = Mock()
        mock_validation_result.is_valid = False
        mock_validation_result.errors = ["Invalid YAML syntax"]
        mock_validation_engine.validate_file.return_value = mock_validation_result
        
        test_file = temp_dir / "test.yaml"
        test_file.write_text("invalid yaml")
        
        result = validate_plans_comprehensive(
            plans_dir=temp_dir,
            validation_engine=mock_validation_engine,
            risk_manager=mock_risk_manager,
        )
        
        assert result["files_checked"] == 1
        assert result["syntax_passed"] == 0
        assert result["business_logic_passed"] == 0
    
    def test_validate_plans_comprehensive_single_file(self, temp_dir, mock_risk_manager):
        """Test validation of single file."""
        mock_validation_engine = Mock()
        mock_validation_result = Mock()
        mock_validation_result.is_valid = True
        mock_validation_result.errors = []
        mock_validation_engine.validate_file.return_value = mock_validation_result
        
        test_file = temp_dir / "single_test.yaml"
        test_file.write_text("test content")
        
        with patch('auto_trader.cli.management_utils.TradePlanLoader'):
            result = validate_plans_comprehensive(
                plans_dir=temp_dir,
                validation_engine=mock_validation_engine,
                risk_manager=mock_risk_manager,
                single_file=test_file,
            )
        
        assert result["files_checked"] == 1


class TestErrorHandling:
    """Test error handling in management utilities."""
    
    def test_plan_management_error_inheritance(self):
        """Test PlanManagementError inheritance."""
        error = PlanManagementError("Test error")
        assert isinstance(error, Exception)
        assert str(error) == "Test error"
    
    def test_backup_creation_error_inheritance(self):
        """Test BackupCreationError inheritance."""
        error = BackupCreationError("Backup failed")
        assert isinstance(error, PlanManagementError)
        assert str(error) == "Backup failed"


@pytest.mark.integration
class TestIntegrationScenarios:
    """Integration tests for management utilities."""
    
    def test_end_to_end_backup_and_validation(self, temp_dir, sample_plan):
        """Test end-to-end backup and validation scenario."""
        # Create plan file
        plan_file = temp_dir / "test_plan.yaml"
        plan_file.write_text("plan: content")
        
        backup_dir = temp_dir / "backups"
        
        # Create backup
        backup_path = create_plan_backup(plan_file, backup_dir)
        
        # Verify backup exists and has correct content
        assert backup_path.exists()
        assert backup_path.read_text() == "plan: content"
        
        # Verify original file still exists
        assert plan_file.exists()
        assert plan_file.read_text() == "plan: content"


class TestErrorHandling:
    """Test improved error handling with specific exception types."""
    
    @pytest.mark.skipif(os.name == 'nt', reason="Permission testing not reliable on Windows")
    def test_backup_creation_permission_error(self, temp_dir):
        """Test backup creation handles permission errors specifically."""
        import os
        
        plan_file = temp_dir / "test_plan.yaml"
        plan_file.write_text("plan: content")
        
        # Create backup directory but make it read-only
        backup_dir = temp_dir / "readonly_backup"
        backup_dir.mkdir()
        
        try:
            # Create a nested directory to prevent write access 
            nested_backup_dir = backup_dir / "nested"
            os.chmod(backup_dir, 0o444)  # Read-only
            
            with pytest.raises(BackupCreationError) as exc_info:
                create_plan_backup(plan_file, nested_backup_dir)
            
            # Verify specific error message mentions directory creation
            assert "Failed to create backup" in str(exc_info.value)
            
        finally:
            # Cleanup: restore permissions
            os.chmod(backup_dir, 0o755)
    
    def test_backup_creation_same_file_error(self, temp_dir):
        """Test backup creation handles same file errors."""
        plan_file = temp_dir / "test_plan.yaml"
        plan_file.write_text("plan: content")
        
        # Mock shutil.copy2 to raise SameFileError
        with patch('shutil.copy2') as mock_copy:
            mock_copy.side_effect = shutil.SameFileError("Same file error")
            
            with pytest.raises(BackupCreationError) as exc_info:
                create_plan_backup(plan_file, temp_dir)
                
            assert "Failed to copy plan file to backup" in str(exc_info.value)
    
    def test_verify_backup_file_not_exists(self, temp_dir):
        """Test backup verification when backup file doesn't exist."""
        original_file = temp_dir / "original.yaml"
        original_file.write_text("plan: content")
        
        nonexistent_backup = temp_dir / "nonexistent_backup.yaml"
        
        with pytest.raises(BackupVerificationError) as exc_info:
            verify_backup(original_file, nonexistent_backup)
            
        assert "Backup file does not exist" in str(exc_info.value)
    
    def test_verify_backup_size_mismatch(self, temp_dir):
        """Test backup verification when file sizes don't match."""
        original_file = temp_dir / "original.yaml"
        original_file.write_text("original content")
        
        backup_file = temp_dir / "backup.yaml"
        backup_file.write_text("different length content")
        
        with pytest.raises(BackupVerificationError) as exc_info:
            verify_backup(original_file, backup_file)
            
        assert "Backup size mismatch" in str(exc_info.value)
    
    def test_verify_backup_invalid_yaml(self, temp_dir):
        """Test backup verification when backup contains invalid YAML."""
        original_file = temp_dir / "original.yaml"
        original_content = "valid: yaml"
        original_file.write_text(original_content)
        
        backup_file = temp_dir / "backup.yaml"
        # Same length as original but invalid YAML (unmatched bracket)
        backup_file.write_text("valid: [bad")  # Invalid YAML, same length as "valid: yaml"
        
        with pytest.raises(BackupVerificationError) as exc_info:
            verify_backup(original_file, backup_file)
            
        assert "Backup contains invalid YAML" in str(exc_info.value)
    
    def test_verify_backup_empty_file(self, temp_dir):
        """Test backup verification when backup file is empty."""
        original_file = temp_dir / "original.yaml"
        original_file.write_text("   ")  # Only whitespace, will be considered empty after strip()
        
        backup_file = temp_dir / "backup.yaml"
        backup_file.write_text("   ")  # Only whitespace, will be considered empty after strip()
        
        with pytest.raises(BackupVerificationError) as exc_info:
            verify_backup(original_file, backup_file)
            
        assert "Backup file is empty" in str(exc_info.value)
    
    def test_verify_backup_success(self, temp_dir):
        """Test successful backup verification."""
        original_file = temp_dir / "original.yaml"
        content = "plan_id: TEST_001\nsymbol: AAPL"
        original_file.write_text(content)
        
        backup_file = temp_dir / "backup.yaml"
        backup_file.write_text(content)
        
        # Should not raise any exception
        result = verify_backup(original_file, backup_file)
        assert result is True

    @patch('auto_trader.cli.management_utils.create_plan_backup')
    def test_perform_plan_update_backup_creation_fails(self, mock_backup, temp_dir):
        """Test plan update when backup creation fails."""
        mock_backup.side_effect = BackupCreationError("Backup failed")
        
        mock_plan = Mock()
        
        with pytest.raises(FileSystemError) as exc_info:
            _perform_plan_update("TEST_001", mock_plan, temp_dir, temp_dir)
            
        assert "Failed to create backup before update" in str(exc_info.value)

    @patch('auto_trader.cli.management_utils.verify_backup')
    @patch('auto_trader.cli.management_utils.create_plan_backup')
    def test_perform_plan_update_backup_verification_fails(self, mock_backup, mock_verify, temp_dir):
        """Test plan update when backup verification fails."""
        backup_path = temp_dir / "backup.yaml"
        mock_backup.return_value = backup_path
        mock_verify.side_effect = BackupVerificationError("Verification failed")
        
        # Create a fake backup file for cleanup test
        backup_path.touch()
        
        mock_plan = Mock()
        
        with pytest.raises(FileSystemError) as exc_info:
            _perform_plan_update("TEST_001", mock_plan, temp_dir, temp_dir)
            
        assert "Backup verification failed, update cancelled" in str(exc_info.value)
        # Verify backup file was cleaned up
        assert not backup_path.exists()

    @patch('auto_trader.cli.management_utils.verify_backup')
    @patch('auto_trader.cli.management_utils.create_plan_backup')
    def test_perform_plan_update_yaml_write_fails(self, mock_backup, mock_verify, temp_dir):
        """Test plan update when YAML write operation fails."""
        backup_path = temp_dir / "backup.yaml"
        mock_backup.return_value = backup_path
        mock_verify.return_value = True
        
        # Make the plan file directory read-only to cause write failure
        import os
        os.chmod(temp_dir, 0o444)
        
        mock_plan = Mock()
        mock_plan.model_dump.return_value = {"plan_id": "TEST_001"}
        
        try:
            with pytest.raises(FileSystemError) as exc_info:
                _perform_plan_update("TEST_001", mock_plan, temp_dir, temp_dir)
                
            assert "Failed to write updated plan file" in str(exc_info.value)
            
        finally:
            # Cleanup: restore permissions
            os.chmod(temp_dir, 0o755)

    @patch('auto_trader.cli.management_utils.verify_backup')
    @patch('auto_trader.cli.management_utils.create_plan_backup')
    def test_perform_plan_update_success(self, mock_backup, mock_verify, temp_dir):
        """Test successful plan update with backup verification."""
        backup_path = temp_dir / "backup.yaml"
        mock_backup.return_value = backup_path
        mock_verify.return_value = True
        
        mock_plan = Mock()
        mock_plan.model_dump.return_value = {"plan_id": "TEST_001", "symbol": "AAPL"}
        
        result_backup_path = _perform_plan_update("TEST_001", mock_plan, temp_dir, temp_dir)
        
        assert result_backup_path == backup_path
        mock_verify.assert_called_once()
        
        # Verify plan file was created with correct content
        plan_file = temp_dir / "TEST_001.yaml"
        assert plan_file.exists()


class TestCalculateAllPlanRisks:
    """Comprehensive tests for the calculate_all_plan_risks function logic."""
    
    def test_calculate_all_plan_risks_utilization_percent_accuracy(self, sample_plan, mock_risk_manager):
        """Test that capacity utilization percent is calculated correctly with precise values."""
        plans = [sample_plan]
        
        # Set specific portfolio risk for precise testing
        mock_risk_manager.portfolio_tracker.get_current_portfolio_risk.return_value = Decimal("3.75")
        
        result = calculate_all_plan_risks(plans, mock_risk_manager)
        portfolio_summary = result["portfolio_summary"]
        
        # Verify exact calculations
        current_risk = Decimal("3.75")
        portfolio_limit = Decimal("10.0")
        expected_utilization = (current_risk / portfolio_limit) * 100  # Should be 37.5%
        expected_remaining = portfolio_limit - current_risk  # Should be 6.25%
        
        assert portfolio_summary["current_risk_percent"] == current_risk
        assert portfolio_summary["portfolio_limit_percent"] == portfolio_limit
        assert portfolio_summary["capacity_utilization_percent"] == expected_utilization
        assert portfolio_summary["remaining_capacity_percent"] == expected_remaining
        assert portfolio_summary["exceeds_limit"] is False
        assert portfolio_summary["near_limit"] is False
    
    def test_calculate_all_plan_risks_near_limit_logic(self, sample_plan, mock_risk_manager):
        """Test near limit detection logic (80% threshold)."""
        plans = [sample_plan]
        
        # Set portfolio risk to 85% of limit (8.5% of 10%)
        mock_risk_manager.portfolio_tracker.get_current_portfolio_risk.return_value = Decimal("8.5")
        
        result = calculate_all_plan_risks(plans, mock_risk_manager)
        portfolio_summary = result["portfolio_summary"]
        
        # Verify near limit detection
        assert portfolio_summary["current_risk_percent"] == Decimal("8.5")
        assert portfolio_summary["capacity_utilization_percent"] == Decimal("85.0")
        assert portfolio_summary["remaining_capacity_percent"] == Decimal("1.5")
        assert portfolio_summary["exceeds_limit"] is False
        assert portfolio_summary["near_limit"] is True  # Should be True (8.5 > 8.0)
    
    def test_calculate_all_plan_risks_exceeds_limit_logic(self, sample_plan, mock_risk_manager):
        """Test exceeds limit detection logic."""
        plans = [sample_plan]
        
        # Set portfolio risk above limit (12% of 10%)
        mock_risk_manager.portfolio_tracker.get_current_portfolio_risk.return_value = Decimal("12.0")
        
        result = calculate_all_plan_risks(plans, mock_risk_manager)
        portfolio_summary = result["portfolio_summary"]
        
        # Verify exceeds limit detection
        assert portfolio_summary["current_risk_percent"] == Decimal("12.0")
        assert portfolio_summary["capacity_utilization_percent"] == Decimal("120.0")
        assert portfolio_summary["remaining_capacity_percent"] == Decimal("0.0")  # Clamped to 0
        assert portfolio_summary["exceeds_limit"] is True
        assert portfolio_summary["near_limit"] is True  # Also near limit
    
    def test_calculate_all_plan_risks_multiple_plans_aggregation(self):
        """Test correct aggregation of multiple plans with different statuses."""
        from decimal import Decimal
        from unittest.mock import Mock
        
        # Create multiple plans with different statuses
        awaiting_plan = TradePlan(
            plan_id="AAPL_20250825_001",
            symbol="AAPL",
            entry_level=Decimal("180.50"),
            stop_loss=Decimal("178.00"),
            take_profit=Decimal("185.00"),
            risk_category=RiskCategory.NORMAL,
            status=TradePlanStatus.AWAITING_ENTRY,
            entry_function={"function_type": "close_above", "parameters": {"threshold": "180.50"}, "timeframe": "15min"},
            exit_function={"function_type": "stop_loss_take_profit", "parameters": {}, "timeframe": "1min"}
        )
        
        open_plan = TradePlan(
            plan_id="MSFT_20250825_002",
            symbol="MSFT",
            entry_level=Decimal("320.00"),
            stop_loss=Decimal("315.00"),
            take_profit=Decimal("330.00"),
            risk_category=RiskCategory.NORMAL,
            status=TradePlanStatus.POSITION_OPEN,
            entry_function={"function_type": "close_above", "parameters": {"threshold": "320.00"}, "timeframe": "15min"},
            exit_function={"function_type": "stop_loss_take_profit", "parameters": {}, "timeframe": "1min"}
        )
        
        completed_plan = TradePlan(
            plan_id="TSLA_20250825_003",
            symbol="TSLA",
            entry_level=Decimal("250.00"),
            stop_loss=Decimal("245.00"),
            take_profit=Decimal("260.00"),
            risk_category=RiskCategory.NORMAL,
            status=TradePlanStatus.COMPLETED,  # Should be excluded from active risk
            entry_function={"function_type": "close_above", "parameters": {"threshold": "250.00"}, "timeframe": "15min"},
            exit_function={"function_type": "stop_loss_take_profit", "parameters": {}, "timeframe": "1min"}
        )
        
        plans = [awaiting_plan, open_plan, completed_plan]
        
        # Mock risk manager
        mock_risk_manager = Mock()
        mock_risk_manager.portfolio_tracker.get_current_portfolio_risk.return_value = Decimal("6.5")
        
        # Mock validation results for each plan
        def mock_validate_trade_plan(plan):
            validation_result = Mock()
            validation_result.passed = True
            validation_result.position_size_result = Mock()
            
            if plan.plan_id == "AAPL_20250825_001":
                validation_result.position_size_result.risk_amount_percent = Decimal("2.5")
                validation_result.position_size_result.position_size = 100
                validation_result.position_size_result.risk_amount_dollars = Decimal("250.0")
            elif plan.plan_id == "MSFT_20250825_002":
                validation_result.position_size_result.risk_amount_percent = Decimal("1.8")
                validation_result.position_size_result.position_size = 75
                validation_result.position_size_result.risk_amount_dollars = Decimal("180.0")
            else:  # TSLA - completed, should still validate but not count in active risks
                validation_result.position_size_result.risk_amount_percent = Decimal("1.2")
                validation_result.position_size_result.position_size = 50
                validation_result.position_size_result.risk_amount_dollars = Decimal("120.0")
            
            return validation_result
        
        mock_risk_manager.validate_trade_plan = mock_validate_trade_plan
        
        result = calculate_all_plan_risks(plans, mock_risk_manager)
        
        # Verify plan risk data for all plans
        assert len(result["plan_risk_data"]) == 3
        assert "AAPL_20250825_001" in result["plan_risk_data"]
        assert "MSFT_20250825_002" in result["plan_risk_data"]
        assert "TSLA_20250825_003" in result["plan_risk_data"]
        
        # Verify individual plan data
        aapl_data = result["plan_risk_data"]["AAPL_20250825_001"]
        assert aapl_data["risk_percent"] == Decimal("2.5")
        assert aapl_data["position_size"] == 100
        assert aapl_data["is_valid"] is True
        
        # Verify portfolio summary
        portfolio_summary = result["portfolio_summary"]
        
        # Only AWAITING_ENTRY and POSITION_OPEN plans should count in total_plan_risk
        expected_plan_risk_sum = Decimal("2.5") + Decimal("1.8")  # AAPL + MSFT, not TSLA
        assert portfolio_summary["total_plan_risk_percent"] == expected_plan_risk_sum
        
        # Active plan risks should only include awaiting_entry and position_open
        assert len(portfolio_summary["plan_risks"]) == 2
        assert "AAPL_20250825_001" in portfolio_summary["plan_risks"]
        assert "MSFT_20250825_002" in portfolio_summary["plan_risks"]
        assert "TSLA_20250825_003" not in portfolio_summary["plan_risks"]  # Completed plan excluded
        
        # Portfolio risk should use actual tracker value, not plan sum
        assert portfolio_summary["current_risk_percent"] == Decimal("6.5")
        assert portfolio_summary["capacity_utilization_percent"] == Decimal("65.0")
    
    def test_calculate_all_plan_risks_invalid_plans_handling(self):
        """Test handling of plans with failed validation."""
        from unittest.mock import Mock
        
        # Create a plan
        plan = TradePlan(
            plan_id="INVALID_20250825_001",
            symbol="INVALID",
            entry_level=Decimal("100.00"),
            stop_loss=Decimal("95.00"),
            take_profit=Decimal("105.00"),
            risk_category=RiskCategory.NORMAL,
            status=TradePlanStatus.AWAITING_ENTRY,
            entry_function={"function_type": "close_above", "parameters": {"threshold": "100.00"}, "timeframe": "15min"},
            exit_function={"function_type": "stop_loss_take_profit", "parameters": {}, "timeframe": "1min"}
        )
        
        plans = [plan]
        
        # Mock risk manager with failed validation
        mock_risk_manager = Mock()
        mock_risk_manager.portfolio_tracker.get_current_portfolio_risk.return_value = Decimal("2.0")
        
        validation_result = Mock()
        validation_result.passed = False  # Validation failed
        validation_result.position_size_result = None
        mock_risk_manager.validate_trade_plan.return_value = validation_result
        
        result = calculate_all_plan_risks(plans, mock_risk_manager)
        
        # Verify invalid plan handling
        plan_data = result["plan_risk_data"]["INVALID_20250825_001"]
        assert plan_data["is_valid"] is False
        assert plan_data["risk_percent"] == Decimal("0")
        assert plan_data["position_size"] == 0
        assert plan_data["dollar_risk"] == Decimal("0")
        
        # Invalid plans should not contribute to active risks
        portfolio_summary = result["portfolio_summary"]
        assert portfolio_summary["total_plan_risk_percent"] == Decimal("0.0")
        assert len(portfolio_summary["plan_risks"]) == 0
    
    def test_calculate_all_plan_risks_cache_performance(self):
        """Test cache performance with multiple identical plans."""
        from unittest.mock import Mock
        
        # Create identical plans (same cache key)
        plan1 = TradePlan(
            plan_id="AAPL_20250825_001",
            symbol="AAPL",
            entry_level=Decimal("180.50"),
            stop_loss=Decimal("178.00"),
            take_profit=Decimal("185.00"),
            risk_category=RiskCategory.NORMAL,
            status=TradePlanStatus.AWAITING_ENTRY,
            entry_function={"function_type": "close_above", "parameters": {"threshold": "180.50"}, "timeframe": "15min"},
            exit_function={"function_type": "stop_loss_take_profit", "parameters": {}, "timeframe": "1min"}
        )
        
        plan2 = TradePlan(
            plan_id="AAPL_20250825_002", # Different ID but same risk parameters
            symbol="AAPL",
            entry_level=Decimal("180.50"),  # Same values = same cache key
            stop_loss=Decimal("178.00"),
            take_profit=Decimal("185.00"),
            risk_category=RiskCategory.NORMAL,
            status=TradePlanStatus.AWAITING_ENTRY,
            entry_function={"function_type": "close_above", "parameters": {"threshold": "180.50"}, "timeframe": "15min"},
            exit_function={"function_type": "stop_loss_take_profit", "parameters": {}, "timeframe": "1min"}
        )
        
        plans = [plan1, plan2]
        
        # Mock risk manager
        mock_risk_manager = Mock()
        mock_risk_manager.portfolio_tracker.get_current_portfolio_risk.return_value = Decimal("4.0")
        
        validation_result = Mock()
        validation_result.passed = True
        validation_result.position_size_result = Mock()
        validation_result.position_size_result.risk_amount_percent = Decimal("2.0")
        validation_result.position_size_result.position_size = 50
        validation_result.position_size_result.risk_amount_dollars = Decimal("100.0")
        mock_risk_manager.validate_trade_plan.return_value = validation_result
        
        # Test with cache enabled
        result = calculate_all_plan_risks(plans, mock_risk_manager, use_cache=True)
        
        # Verify cache statistics
        cache_stats = result["cache_stats"]
        assert cache_stats is not None
        assert cache_stats["total_requests"] == 2
        # Second plan should hit cache (same risk parameters)
        assert cache_stats["cache_hits"] == 1
        assert cache_stats["cache_misses"] == 1
        assert cache_stats["hit_rate_percent"] == 50.0
        
        # Verify both plans are processed correctly
        assert len(result["plan_risk_data"]) == 2
        assert result["performance"]["plans_processed"] == 2
    
    def test_calculate_all_plan_risks_performance_metrics(self, sample_plan, mock_risk_manager):
        """Test that performance metrics are accurate and complete."""
        plans = [sample_plan] * 5  # Process 5 plans
        
        result = calculate_all_plan_risks(plans, mock_risk_manager)
        
        performance = result["performance"]
        assert "execution_time_seconds" in performance
        assert "plans_processed" in performance
        assert "calculations_per_second" in performance
        
        # Verify counts
        assert performance["plans_processed"] == 5
        
        # Verify execution time is reasonable (should be very fast for mocked operations)
        assert performance["execution_time_seconds"] >= 0
        assert performance["execution_time_seconds"] < 1.0  # Should be sub-second for 5 mock operations
        
        # Verify calculations per second
        if performance["execution_time_seconds"] > 0:
            expected_cps = 5 / performance["execution_time_seconds"]
            assert performance["calculations_per_second"] == expected_cps
        else:
            assert performance["calculations_per_second"] == 0


class TestSpecificExceptionTypes:
    """Test that specific exception types are raised appropriately."""
    
    def test_exception_hierarchy(self):
        """Test that all custom exceptions inherit from PlanManagementError."""
        assert issubclass(BackupCreationError, PlanManagementError)
        assert issubclass(BackupVerificationError, PlanManagementError)
        assert issubclass(PlanLoadingError, PlanManagementError)
        assert issubclass(ValidationError, PlanManagementError)
        assert issubclass(FileSystemError, PlanManagementError)
        assert issubclass(RiskCalculationError, PlanManagementError)
    
    def test_exception_messages(self):
        """Test that exceptions can be created with custom messages."""
        message = "Custom error message"
        
        exc = BackupCreationError(message)
        assert str(exc) == message
        
        exc = BackupVerificationError(message)
        assert str(exc) == message
        
        exc = PlanLoadingError(message)
        assert str(exc) == message
        
        exc = ValidationError(message)
        assert str(exc) == message
        
        exc = FileSystemError(message)
        assert str(exc) == message
        
        exc = RiskCalculationError(message)
        assert str(exc) == message