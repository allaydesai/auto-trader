"""Unit tests for trade plan loader."""

import pytest
import tempfile
from pathlib import Path
from decimal import Decimal

from auto_trader.models.plan_loader import TradePlanLoader
from auto_trader.models.trade_plan import TradePlan, TradePlanStatus


class TestTradePlanLoader:
    """Test TradePlanLoader functionality."""
    
    @pytest.fixture
    def temp_plans_dir(self):
        """Create temporary plans directory with test files."""
        with tempfile.TemporaryDirectory() as temp_dir:
            plans_dir = Path(temp_dir) / "plans"
            plans_dir.mkdir()
            
            # Create single plan file
            single_plan = """
plan_id: "AAPL_20250815_001"
symbol: "AAPL"
entry_level: 180.50
stop_loss: 178.00
take_profit: 185.00
risk_category: "normal"
entry_function:
  function_type: "close_above"
  timeframe: "15min"
  parameters:
    threshold: 180.50
exit_function:
  function_type: "stop_loss_take_profit"
  timeframe: "1min"
  parameters: {}
status: "awaiting_entry"
"""
            single_plan_file = plans_dir / "single_plan.yaml"
            single_plan_file.write_text(single_plan)
            
            # Create multiple plans file
            multiple_plans = """
- plan_id: "MSFT_20250815_001"
  symbol: "MSFT"
  entry_level: 300.00
  stop_loss: 295.00
  take_profit: 310.00
  risk_category: "small"
  entry_function:
    function_type: "close_below"
    timeframe: "30min"
    parameters:
      threshold: 300.00
  exit_function:
    function_type: "stop_loss_take_profit"
    timeframe: "5min"
    parameters: {}
  status: "awaiting_entry"

- plan_id: "GOOGL_20250815_001"
  symbol: "GOOGL"
  entry_level: 2500.00
  stop_loss: 2450.00
  take_profit: 2600.00
  risk_category: "large"
  entry_function:
    function_type: "close_above"
    timeframe: "1h"
    parameters:
      threshold: 2500.00
  exit_function:
    function_type: "trailing_stop"
    timeframe: "5min"
    parameters:
      trail_percent: 2.0
  status: "position_open"
"""
            multiple_plans_file = plans_dir / "multiple_plans.yaml"
            multiple_plans_file.write_text(multiple_plans)
            
            # Create invalid plan file
            invalid_plan = """
plan_id: "INVALID_001"
symbol: "aapl"  # lowercase - invalid
entry_level: -180.50  # negative - invalid
"""
            invalid_plan_file = plans_dir / "invalid_plan.yaml"
            invalid_plan_file.write_text(invalid_plan)
            
            # Create template file (should be skipped)
            template_file = plans_dir / "template_close_above.yaml"
            template_file.write_text("# Template file - should be skipped")
            
            yield plans_dir
    
    @pytest.fixture
    def loader(self, temp_plans_dir):
        """Provide loader with temporary directory."""
        return TradePlanLoader(temp_plans_dir)
    
    def test_load_all_plans_success(self, loader):
        """Test loading all plans successfully."""
        plans = loader.load_all_plans()
        
        # Should load 3 valid plans (1 single + 2 multiple)
        assert len(plans) == 3
        assert "AAPL_20250815_001" in plans
        assert "MSFT_20250815_001" in plans
        assert "GOOGL_20250815_001" in plans
        
        # Check plan details
        aapl_plan = plans["AAPL_20250815_001"]
        assert aapl_plan.symbol == "AAPL"
        assert aapl_plan.entry_level == Decimal("180.50")
        assert aapl_plan.status == TradePlanStatus.AWAITING_ENTRY
    
    def test_load_all_plans_with_validation_disabled(self, loader):
        """Test loading plans with validation disabled."""
        plans = loader.load_all_plans(validate=False)
        
        # Should still load valid plans, invalid ones filtered by pydantic
        assert len(plans) >= 3
    
    def test_load_single_file(self, loader, temp_plans_dir):
        """Test loading a single file."""
        single_file = temp_plans_dir / "single_plan.yaml"
        plans = loader.load_single_file(single_file)
        
        assert len(plans) == 1
        assert plans[0].plan_id == "AAPL_20250815_001"
        assert plans[0].symbol == "AAPL"
    
    def test_load_single_file_multiple_plans(self, loader, temp_plans_dir):
        """Test loading single file with multiple plans."""
        multiple_file = temp_plans_dir / "multiple_plans.yaml"
        plans = loader.load_single_file(multiple_file)
        
        assert len(plans) == 2
        plan_ids = [plan.plan_id for plan in plans]
        assert "MSFT_20250815_001" in plan_ids
        assert "GOOGL_20250815_001" in plan_ids
    
    def test_load_single_file_invalid(self, loader, temp_plans_dir):
        """Test loading invalid file."""
        invalid_file = temp_plans_dir / "invalid_plan.yaml"
        plans = loader.load_single_file(invalid_file, validate=True)
        
        # Should return empty list due to validation failure
        assert len(plans) == 0
    
    def test_load_nonexistent_file(self, loader):
        """Test loading non-existent file."""
        nonexistent = Path("/nonexistent/file.yaml")
        plans = loader.load_single_file(nonexistent)
        
        assert len(plans) == 0
    
    def test_get_plan(self, loader):
        """Test getting specific plan by ID."""
        loader.load_all_plans()
        
        plan = loader.get_plan("AAPL_20250815_001")
        assert plan is not None
        assert plan.symbol == "AAPL"
        
        nonexistent = loader.get_plan("NONEXISTENT_001")
        assert nonexistent is None
    
    def test_get_plans_by_status(self, loader):
        """Test filtering plans by status."""
        loader.load_all_plans()
        
        awaiting_plans = loader.get_plans_by_status(TradePlanStatus.AWAITING_ENTRY)
        assert len(awaiting_plans) == 2  # AAPL and MSFT
        
        open_plans = loader.get_plans_by_status(TradePlanStatus.POSITION_OPEN)
        assert len(open_plans) == 1  # GOOGL
        
        completed_plans = loader.get_plans_by_status(TradePlanStatus.COMPLETED)
        assert len(completed_plans) == 0
    
    def test_get_plans_by_symbol(self, loader):
        """Test filtering plans by symbol."""
        loader.load_all_plans()
        
        aapl_plans = loader.get_plans_by_symbol("AAPL")
        assert len(aapl_plans) == 1
        assert aapl_plans[0].plan_id == "AAPL_20250815_001"
        
        msft_plans = loader.get_plans_by_symbol("MSFT")
        assert len(msft_plans) == 1
        
        nonexistent_plans = loader.get_plans_by_symbol("TSLA")
        assert len(nonexistent_plans) == 0
    
    def test_update_plan_status(self, loader):
        """Test updating plan status."""
        loader.load_all_plans()
        
        # Update status
        success = loader.update_plan_status("AAPL_20250815_001", TradePlanStatus.POSITION_OPEN)
        assert success is True
        
        # Verify update
        plan = loader.get_plan("AAPL_20250815_001")
        assert plan.status == TradePlanStatus.POSITION_OPEN
        assert plan.updated_at is not None
        
        # Try to update non-existent plan
        success = loader.update_plan_status("NONEXISTENT_001", TradePlanStatus.COMPLETED)
        assert success is False
    
    def test_get_loaded_plan_ids(self, loader):
        """Test getting loaded plan IDs."""
        # Initially empty
        plan_ids = loader.get_loaded_plan_ids()
        assert len(plan_ids) == 0
        
        # After loading
        loader.load_all_plans()
        plan_ids = loader.get_loaded_plan_ids()
        assert len(plan_ids) == 3
        assert "AAPL_20250815_001" in plan_ids
        assert "MSFT_20250815_001" in plan_ids
        assert "GOOGL_20250815_001" in plan_ids
    
    def test_get_stats(self, loader):
        """Test getting plan statistics."""
        # Initially empty
        stats = loader.get_stats()
        assert stats["total_plans"] == 0
        assert stats["files_loaded"] == 0
        
        # After loading
        loader.load_all_plans()
        stats = loader.get_stats()
        
        assert stats["total_plans"] == 3
        assert stats["files_loaded"] == 2  # single_plan.yaml and multiple_plans.yaml
        
        # Check status breakdown
        assert stats["by_status"]["awaiting_entry"] == 2
        assert stats["by_status"]["position_open"] == 1
        
        # Check symbol breakdown
        assert stats["by_symbol"]["AAPL"] == 1
        assert stats["by_symbol"]["MSFT"] == 1
        assert stats["by_symbol"]["GOOGL"] == 1
    
    def test_get_validation_report(self, loader):
        """Test getting validation report."""
        loader.load_all_plans()
        report = loader.get_validation_report()
        
        assert "TRADE PLAN VALIDATION SUMMARY" in report
        assert "Total files processed:" in report
    
    def test_context_manager(self, temp_plans_dir):
        """Test using loader as context manager."""
        with TradePlanLoader(temp_plans_dir) as loader:
            plans = loader.load_all_plans()
            assert len(plans) >= 3
        
        # Should cleanly exit without errors
    
    def test_duplicate_plan_id_handling(self, temp_plans_dir):
        """Test handling of duplicate plan IDs across files."""
        # Create file with duplicate plan ID
        duplicate_plan = """
plan_id: "AAPL_20250815_001"  # Same as in single_plan.yaml
symbol: "TSLA"
entry_level: 250.00
stop_loss: 245.00
take_profit: 260.00
risk_category: "normal"
entry_function:
  function_type: "close_above"
  timeframe: "15min"
  parameters:
    threshold: 250.00
exit_function:
  function_type: "stop_loss_take_profit"
  timeframe: "1min"
  parameters: {}
"""
        duplicate_file = temp_plans_dir / "duplicate.yaml"
        duplicate_file.write_text(duplicate_plan)
        
        loader = TradePlanLoader(temp_plans_dir)
        plans = loader.load_all_plans()
        
        # Should only have one plan with this ID (first one loaded wins)
        aapl_plans = [p for p in plans.values() if p.plan_id == "AAPL_20250815_001"]
        assert len(aapl_plans) == 1
        # The symbol could be either AAPL or TSLA depending on file load order
        assert aapl_plans[0].symbol in ["AAPL", "TSLA"]
    
    def test_load_empty_directory(self):
        """Test loading from empty directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            empty_dir = Path(temp_dir) / "empty"
            empty_dir.mkdir()
            
            loader = TradePlanLoader(empty_dir)
            plans = loader.load_all_plans()
            
            assert len(plans) == 0
    
    def test_load_nonexistent_directory(self):
        """Test loading from non-existent directory."""
        nonexistent_dir = Path("/nonexistent/directory")
        loader = TradePlanLoader(nonexistent_dir)
        plans = loader.load_all_plans()
        
        assert len(plans) == 0


class TestTradePlanLoaderFileWatching:
    """Test file watching functionality."""
    
    @pytest.fixture
    def temp_plans_dir(self):
        """Create temporary plans directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            plans_dir = Path(temp_dir) / "plans"
            plans_dir.mkdir()
            yield plans_dir
    
    @pytest.fixture
    def loader(self, temp_plans_dir):
        """Provide loader with temporary directory."""
        return TradePlanLoader(temp_plans_dir)
    
    def test_start_stop_file_watching(self, loader):
        """Test starting and stopping file watching."""
        # Initially not watching
        assert loader._watching is False
        
        # Start watching
        loader.start_file_watching()
        assert loader._watching is True
        assert loader._observer is not None
        
        # Stop watching
        loader.stop_file_watching()
        assert loader._watching is False
        assert loader._observer is None
    
    def test_start_watching_twice(self, loader):
        """Test starting file watching twice."""
        loader.start_file_watching()
        assert loader._watching is True
        
        # Should not error when starting again
        loader.start_file_watching()
        assert loader._watching is True
        
        loader.stop_file_watching()
    
    def test_stop_watching_when_not_started(self, loader):
        """Test stopping file watching when not started."""
        # Should not error
        loader.stop_file_watching()
        assert loader._watching is False
    
    def test_watch_nonexistent_directory(self):
        """Test watching non-existent directory."""
        nonexistent_dir = Path("/nonexistent/directory")
        loader = TradePlanLoader(nonexistent_dir)
        
        # Should not error, but should not start watching
        loader.start_file_watching()
        assert loader._watching is False


class TestTradePlanLoaderWithRealPlans:
    """Test loader with actual project plans."""
    
    def test_load_real_sample_plans(self):
        """Test loading real sample plans from project."""
        # Use default plans directory (should find sample_plans.yaml)
        loader = TradePlanLoader()
        plans = loader.load_all_plans()
        
        # Should load at least the sample plans
        assert len(plans) >= 2
        
        # Check that AAPL and MSFT plans exist
        plan_ids = set(plans.keys())
        assert any("AAPL" in plan_id for plan_id in plan_ids)
        assert any("MSFT" in plan_id for plan_id in plan_ids)
    
    def test_real_plans_validation(self):
        """Test that real plans pass validation."""
        loader = TradePlanLoader()
        plans = loader.load_all_plans(validate=True)
        
        # All loaded plans should be valid
        for plan in plans.values():
            assert isinstance(plan, TradePlan)
            assert plan.plan_id
            assert plan.symbol
            assert plan.entry_level > 0
            assert plan.stop_loss > 0
            assert plan.take_profit > 0
    
    def test_real_plans_stats(self):
        """Test statistics on real plans."""
        loader = TradePlanLoader()
        loader.load_all_plans()
        
        stats = loader.get_stats()
        assert stats["total_plans"] >= 2
        assert stats["files_loaded"] >= 1
        assert len(stats["by_status"]) > 0
        assert len(stats["by_symbol"]) > 0