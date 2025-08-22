"""Tests for plan management utility functions."""

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
    get_portfolio_risk_summary,
    format_risk_indicator,
    format_plan_status,
    create_plans_table,
    create_portfolio_summary_panel,
    validate_plans_comprehensive,
    PlanManagementError,
    BackupCreationError,
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
        assert result["capacity_utilization_percent"] == Decimal("48.0")
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
        
        table = create_plans_table(plans, mock_risk_manager, show_verbose=False)
        
        assert isinstance(table, Table)
        assert table.title == "📊 TRADE PLANS"
        assert len(table.columns) == 5  # Basic columns
    
    def test_create_plans_table_verbose(self, sample_plan, mock_risk_manager):
        """Test verbose plans table creation."""
        plans = [sample_plan]
        
        table = create_plans_table(plans, mock_risk_manager, show_verbose=True)
        
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