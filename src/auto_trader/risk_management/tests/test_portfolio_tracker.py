"""Tests for portfolio risk tracking and persistence."""

import json
import tempfile
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

import pytest

from ..portfolio_tracker import PortfolioTracker
from ..risk_models import PortfolioRiskExceededError, PositionRiskEntry


class TestPortfolioTrackerInitialization:
    """Tests for PortfolioTracker initialization."""
    
    def test_default_initialization(self) -> None:
        """Test tracker initialization with defaults."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Test with a fresh directory to avoid existing state
            temp_path = Path(temp_dir) / "fresh_registry.json"
            tracker = PortfolioTracker(state_file=temp_path)
            
            assert tracker.state_file == temp_path
            assert tracker._account_value == Decimal("0")
            assert len(tracker._positions) == 0
            assert tracker.MAX_PORTFOLIO_RISK == Decimal("10.0")
    
    def test_custom_initialization(self) -> None:
        """Test tracker initialization with custom parameters."""
        custom_file = Path("/tmp/test_registry.json")
        account_value = Decimal("50000.00")
        
        tracker = PortfolioTracker(
            state_file=custom_file,
            account_value=account_value,
        )
        
        assert tracker.state_file == custom_file
        assert tracker._account_value == account_value
        assert len(tracker._positions) == 0
    
    def test_set_account_value(self) -> None:
        """Test setting account value after initialization."""
        tracker = PortfolioTracker()
        new_value = Decimal("25000.00")
        
        tracker.set_account_value(new_value)
        
        assert tracker._account_value == new_value


class TestPositionManagement:
    """Tests for position addition and removal."""
    
    @pytest.fixture
    def tracker(self) -> PortfolioTracker:
        """Create tracker with temporary state file."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "test_registry.json"
            tracker = PortfolioTracker(
                state_file=temp_path,
                account_value=Decimal("10000.00"),
            )
            yield tracker
    
    def test_add_single_position(self, tracker: PortfolioTracker) -> None:
        """Test adding a single position."""
        tracker.add_position(
            position_id="TEST_POS_001",
            symbol="AAPL",
            risk_amount=Decimal("200.00"),
            plan_id="AAPL_20250815_001",
        )
        
        assert tracker.get_position_count() == 1
        assert tracker.get_total_dollar_risk() == Decimal("200.00")
        assert tracker.get_current_portfolio_risk() == Decimal("2.00")  # 200/10000 * 100
        
        position = tracker.get_position("TEST_POS_001")
        assert position is not None
        assert position.symbol == "AAPL"
        assert position.risk_amount == Decimal("200.00")
    
    def test_add_multiple_positions(self, tracker: PortfolioTracker) -> None:
        """Test adding multiple positions."""
        positions = [
            ("POS_001", "AAPL", Decimal("200.00"), "AAPL_001"),
            ("POS_002", "MSFT", Decimal("300.00"), "MSFT_001"),
            ("POS_003", "GOOGL", Decimal("150.00"), "GOOGL_001"),
        ]
        
        for pos_id, symbol, risk, plan_id in positions:
            tracker.add_position(pos_id, symbol, risk, plan_id)
        
        assert tracker.get_position_count() == 3
        assert tracker.get_total_dollar_risk() == Decimal("650.00")
        assert tracker.get_current_portfolio_risk() == Decimal("6.50")
    
    def test_remove_existing_position(self, tracker: PortfolioTracker) -> None:
        """Test removing an existing position."""
        tracker.add_position("POS_001", "AAPL", Decimal("200.00"), "AAPL_001")
        tracker.add_position("POS_002", "MSFT", Decimal("300.00"), "MSFT_001")
        
        result = tracker.remove_position("POS_001")
        
        assert result is True
        assert tracker.get_position_count() == 1
        assert tracker.get_total_dollar_risk() == Decimal("300.00")
        assert tracker.get_position("POS_001") is None
        assert tracker.get_position("POS_002") is not None
    
    def test_remove_nonexistent_position(self, tracker: PortfolioTracker) -> None:
        """Test removing a non-existent position."""
        tracker.add_position("POS_001", "AAPL", Decimal("200.00"), "AAPL_001")
        
        result = tracker.remove_position("NONEXISTENT")
        
        assert result is False
        assert tracker.get_position_count() == 1
    
    def test_get_positions_by_symbol(self, tracker: PortfolioTracker) -> None:
        """Test getting positions filtered by symbol."""
        tracker.add_position("POS_001", "AAPL", Decimal("200.00"), "AAPL_001")
        tracker.add_position("POS_002", "AAPL", Decimal("150.00"), "AAPL_002")
        tracker.add_position("POS_003", "MSFT", Decimal("300.00"), "MSFT_001")
        
        aapl_positions = tracker.get_positions_by_symbol("AAPL")
        msft_positions = tracker.get_positions_by_symbol("MSFT")
        
        assert len(aapl_positions) == 2
        assert len(msft_positions) == 1
        assert "POS_001" in aapl_positions
        assert "POS_002" in aapl_positions
        assert "POS_003" in msft_positions
    
    def test_get_all_positions(self, tracker: PortfolioTracker) -> None:
        """Test getting all positions."""
        tracker.add_position("POS_001", "AAPL", Decimal("200.00"), "AAPL_001")
        tracker.add_position("POS_002", "MSFT", Decimal("300.00"), "MSFT_001")
        
        all_positions = tracker.get_all_positions()
        
        assert len(all_positions) == 2
        assert "POS_001" in all_positions
        assert "POS_002" in all_positions
        # Ensure it's a copy
        all_positions.clear()
        assert tracker.get_position_count() == 2


class TestRiskCalculations:
    """Tests for portfolio risk calculations."""
    
    @pytest.fixture
    def tracker(self) -> PortfolioTracker:
        """Create tracker for risk testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "risk_test_registry.json"
            tracker = PortfolioTracker(
                state_file=temp_path,
                account_value=Decimal("10000.00"),
            )
            yield tracker
    
    def test_empty_portfolio_risk(self, tracker: PortfolioTracker) -> None:
        """Test risk calculation with empty portfolio."""
        assert tracker.get_current_portfolio_risk() == Decimal("0.00")
        assert tracker.get_total_dollar_risk() == Decimal("0.00")
    
    def test_zero_account_value_risk(self) -> None:
        """Test risk calculation with zero account value."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "zero_account_test.json"
            tracker = PortfolioTracker(
                state_file=temp_path,
                account_value=Decimal("0.00"),
            )
            tracker.add_position("POS_001", "AAPL", Decimal("200.00"), "AAPL_001")
            
            assert tracker.get_current_portfolio_risk() == Decimal("0.00")
    
    def test_single_position_risk(self, tracker: PortfolioTracker) -> None:
        """Test risk calculation with single position."""
        tracker.add_position("POS_001", "AAPL", Decimal("500.00"), "AAPL_001")
        
        # $500 / $10,000 * 100 = 5%
        assert tracker.get_current_portfolio_risk() == Decimal("5.00")
    
    def test_multiple_positions_risk(self, tracker: PortfolioTracker) -> None:
        """Test risk calculation with multiple positions."""
        tracker.add_position("POS_001", "AAPL", Decimal("200.00"), "AAPL_001")
        tracker.add_position("POS_002", "MSFT", Decimal("300.00"), "MSFT_001")
        tracker.add_position("POS_003", "GOOGL", Decimal("150.00"), "GOOGL_001")
        
        # ($200 + $300 + $150) / $10,000 * 100 = 6.5%
        assert tracker.get_current_portfolio_risk() == Decimal("6.50")
        assert tracker.get_total_dollar_risk() == Decimal("650.00")
    
    def test_risk_precision(self, tracker: PortfolioTracker) -> None:
        """Test risk calculation precision."""
        # Add position that creates non-round percentage
        tracker.add_position("POS_001", "AAPL", Decimal("333.33"), "AAPL_001")
        
        # $333.33 / $10,000 * 100 = 3.3333% -> rounds to 3.33%
        risk = tracker.get_current_portfolio_risk()
        assert risk == Decimal("3.33")
        assert risk.as_tuple().exponent == -2  # Two decimal places


class TestRiskLimitValidation:
    """Tests for portfolio risk limit enforcement."""
    
    @pytest.fixture
    def tracker(self) -> PortfolioTracker:
        """Create tracker for risk limit testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "risk_limit_test.json"
            tracker = PortfolioTracker(
                state_file=temp_path,
                account_value=Decimal("10000.00"),
            )
            yield tracker
    
    def test_check_new_trade_within_limit(self, tracker: PortfolioTracker) -> None:
        """Test new trade that stays within limit."""
        # Add positions totaling 7% risk
        tracker.add_position("POS_001", "AAPL", Decimal("400.00"), "AAPL_001")
        tracker.add_position("POS_002", "MSFT", Decimal("300.00"), "MSFT_001")
        
        # Try to add 2% more (total 9%, within 10% limit)
        can_trade, message = tracker.check_new_trade_risk(Decimal("200.00"))
        
        assert can_trade is True
        assert message == ""
    
    def test_check_new_trade_exceeds_limit(self, tracker: PortfolioTracker) -> None:
        """Test new trade that exceeds limit."""
        # Add positions totaling 8.5% risk
        tracker.add_position("POS_001", "AAPL", Decimal("500.00"), "AAPL_001")
        tracker.add_position("POS_002", "MSFT", Decimal("350.00"), "MSFT_001")
        
        # Try to add 2% more (total 10.5%, exceeds 10% limit)
        can_trade, message = tracker.check_new_trade_risk(Decimal("200.00"))
        
        assert can_trade is False
        assert "Portfolio risk limit exceeded" in message
        assert "10.50%" in message
        assert "8.50%" in message
        assert "2.00%" in message
    
    def test_check_new_trade_exactly_at_limit(self, tracker: PortfolioTracker) -> None:
        """Test new trade that exactly reaches limit."""
        # Add positions totaling 8% risk
        tracker.add_position("POS_001", "AAPL", Decimal("800.00"), "AAPL_001")
        
        # Try to add exactly 2% more (total 10%, exactly at limit)
        can_trade, message = tracker.check_new_trade_risk(Decimal("200.00"))
        
        assert can_trade is True
        assert message == ""
    
    def test_validate_new_trade_risk_success(self, tracker: PortfolioTracker) -> None:
        """Test validate method with successful trade."""
        tracker.add_position("POS_001", "AAPL", Decimal("500.00"), "AAPL_001")
        
        # Should not raise exception
        tracker.validate_new_trade_risk(Decimal("200.00"))
    
    def test_validate_new_trade_risk_failure(self, tracker: PortfolioTracker) -> None:
        """Test validate method with failed trade."""
        tracker.add_position("POS_001", "AAPL", Decimal("900.00"), "AAPL_001")
        
        with pytest.raises(PortfolioRiskExceededError) as exc_info:
            tracker.validate_new_trade_risk(Decimal("200.00"))
        
        error = exc_info.value
        assert error.current_risk == Decimal("9.00")
        assert error.new_risk == Decimal("2.00")
        assert error.limit == Decimal("10.0")
    
    def test_check_new_trade_zero_account_value(self) -> None:
        """Test risk check with zero account value."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "zero_account_risk_test.json"
            tracker = PortfolioTracker(
                state_file=temp_path,
                account_value=Decimal("0.00"),
            )
            
            can_trade, message = tracker.check_new_trade_risk(Decimal("100.00"))
            
            assert can_trade is False
            assert "Invalid account value" in message


class TestRiskCapacity:
    """Tests for risk capacity calculations."""
    
    @pytest.fixture
    def tracker(self) -> PortfolioTracker:
        """Create tracker for capacity testing."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "capacity_test.json"
            tracker = PortfolioTracker(
                state_file=temp_path,
                account_value=Decimal("10000.00"),
            )
            yield tracker
    
    def test_available_capacity_empty_portfolio(self, tracker: PortfolioTracker) -> None:
        """Test available capacity with empty portfolio."""
        percent_capacity, dollar_capacity = tracker.get_available_risk_capacity()
        
        assert percent_capacity == Decimal("10.0")  # Full 10% available
        assert dollar_capacity == Decimal("1000.00")  # $1000 available
    
    def test_available_capacity_partial_portfolio(self, tracker: PortfolioTracker) -> None:
        """Test available capacity with partial positions."""
        tracker.add_position("POS_001", "AAPL", Decimal("300.00"), "AAPL_001")  # 3%
        
        percent_capacity, dollar_capacity = tracker.get_available_risk_capacity()
        
        assert percent_capacity == Decimal("7.00")  # 7% remaining
        assert dollar_capacity == Decimal("700.00")  # $700 remaining
    
    def test_available_capacity_full_portfolio(self, tracker: PortfolioTracker) -> None:
        """Test available capacity with full portfolio."""
        tracker.add_position("POS_001", "AAPL", Decimal("1000.00"), "AAPL_001")  # 10%
        
        percent_capacity, dollar_capacity = tracker.get_available_risk_capacity()
        
        assert percent_capacity == Decimal("0.00")  # No capacity remaining
        assert dollar_capacity == Decimal("0.00")


class TestPortfolioSummary:
    """Tests for portfolio summary functionality."""
    
    def test_portfolio_summary_empty(self) -> None:
        """Test portfolio summary with empty portfolio."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "summary_empty_test.json"
            tracker = PortfolioTracker(
                state_file=temp_path,
                account_value=Decimal("10000.00"),
            )
            summary = tracker.get_portfolio_summary()
            
            assert summary["account_value"] == 10000.0
            assert summary["position_count"] == 0
            assert summary["total_dollar_risk"] == 0.0
            assert summary["current_risk_percentage"] == 0.0
            assert summary["risk_limit"] == 10.0
            assert summary["remaining_capacity_percent"] == 10.0
            assert summary["remaining_capacity_dollars"] == 1000.0
            assert len(summary["positions"]) == 0
    
    def test_portfolio_summary_with_positions(self) -> None:
        """Test portfolio summary with positions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "summary_positions_test.json"
            tracker = PortfolioTracker(
                state_file=temp_path,
                account_value=Decimal("10000.00"),
            )
            tracker.add_position("POS_001", "AAPL", Decimal("200.00"), "AAPL_001")
            tracker.add_position("POS_002", "MSFT", Decimal("300.00"), "MSFT_001")
            
            summary = tracker.get_portfolio_summary()
            
            assert summary["account_value"] == 10000.0
            assert summary["position_count"] == 2
            assert summary["total_dollar_risk"] == 500.0
            assert summary["current_risk_percentage"] == 5.0
            assert summary["remaining_capacity_percent"] == 5.0
            assert summary["remaining_capacity_dollars"] == 500.0
            assert len(summary["positions"]) == 2
            
            # Check position details
            positions = summary["positions"]
            pos_ids = [pos["position_id"] for pos in positions]
            assert "POS_001" in pos_ids
            assert "POS_002" in pos_ids


class TestStatePersistence:
    """Tests for state persistence and recovery."""
    
    def test_persist_and_load_empty_state(self) -> None:
        """Test persisting and loading empty state."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "empty_state_test.json"
            
            # Create tracker and force a persist by adding then removing a position
            tracker1 = PortfolioTracker(
                state_file=temp_path,
                account_value=Decimal("10000.00"),
            )
            
            # Force state persistence by adding and removing a position
            tracker1.add_position("TEMP", "TEST", Decimal("100.00"), "TEMP_PLAN")
            tracker1.remove_position("TEMP")
            
            # Create new tracker that loads the state
            tracker2 = PortfolioTracker(state_file=temp_path)
            
            assert tracker2.get_position_count() == 0
            assert tracker2._account_value == Decimal("10000.00")
    
    def test_persist_and_load_with_positions(self) -> None:
        """Test persisting and loading state with positions."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as f:
            temp_path = Path(f.name)
        
        try:
            # Create tracker with positions
            tracker1 = PortfolioTracker(
                state_file=temp_path,
                account_value=Decimal("10000.00"),
            )
            tracker1.add_position("POS_001", "AAPL", Decimal("200.00"), "AAPL_001")
            tracker1.add_position("POS_002", "MSFT", Decimal("300.00"), "MSFT_001")
            
            # Create new tracker that loads the state
            tracker2 = PortfolioTracker(state_file=temp_path)
            
            assert tracker2.get_position_count() == 2
            assert tracker2.get_total_dollar_risk() == Decimal("500.00")
            assert tracker2.get_current_portfolio_risk() == Decimal("5.00")
            
            # Check specific positions
            pos1 = tracker2.get_position("POS_001")
            pos2 = tracker2.get_position("POS_002")
            
            assert pos1 is not None
            assert pos1.symbol == "AAPL"
            assert pos1.risk_amount == Decimal("200.00")
            
            assert pos2 is not None
            assert pos2.symbol == "MSFT"
            assert pos2.risk_amount == Decimal("300.00")
            
        finally:
            if temp_path.exists():
                temp_path.unlink()
    
    def test_load_corrupted_state_file(self) -> None:
        """Test loading corrupted state file."""
        with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".json") as f:
            f.write("invalid json content")
            temp_path = Path(f.name)
        
        try:
            # Should handle corrupted file gracefully
            tracker = PortfolioTracker(state_file=temp_path)
            
            # Should start with empty state
            assert tracker.get_position_count() == 0
            
        finally:
            if temp_path.exists():
                temp_path.unlink()
    
    def test_atomic_write_integrity(self) -> None:
        """Test atomic write preserves data integrity."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as f:
            temp_path = Path(f.name)
        
        try:
            tracker = PortfolioTracker(
                state_file=temp_path,
                account_value=Decimal("10000.00"),
            )
            tracker.add_position("POS_001", "AAPL", Decimal("200.00"), "AAPL_001")
            
            # Verify file exists and contains valid JSON
            assert temp_path.exists()
            
            with open(temp_path, "r") as f:
                data = json.load(f)
            
            assert "positions" in data
            assert "account_value" in data
            assert len(data["positions"]) == 1
            
        finally:
            if temp_path.exists():
                temp_path.unlink()


class TestBackupAndMaintenance:
    """Tests for backup and maintenance operations."""
    
    def test_create_backup(self) -> None:
        """Test creating state backup."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as f:
            temp_path = Path(f.name)
        
        try:
            tracker = PortfolioTracker(
                state_file=temp_path,
                account_value=Decimal("10000.00"),
            )
            tracker.add_position("POS_001", "AAPL", Decimal("200.00"), "AAPL_001")
            
            # Create backup
            backup_path = tracker.create_backup()
            
            assert backup_path.exists()
            assert backup_path != temp_path
            assert backup_path.suffix == ".json"
            assert "backup_" in backup_path.name
            
            # Verify backup content
            with open(backup_path, "r") as f:
                backup_data = json.load(f)
            
            assert len(backup_data["positions"]) == 1
            
            # Cleanup backup
            backup_path.unlink()
            
        finally:
            if temp_path.exists():
                temp_path.unlink()
    
    def test_clear_all_positions(self) -> None:
        """Test clearing all positions."""
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir) / "clear_positions_test.json"
            tracker = PortfolioTracker(
                state_file=temp_path,
                account_value=Decimal("10000.00"),
            )
            tracker.add_position("POS_001", "AAPL", Decimal("200.00"), "AAPL_001")
            tracker.add_position("POS_002", "MSFT", Decimal("300.00"), "MSFT_001")
            
            cleared_count = tracker.clear_all_positions()
            
            assert cleared_count == 2
            assert tracker.get_position_count() == 0
            assert tracker.get_total_dollar_risk() == Decimal("0.00")
            assert tracker.get_current_portfolio_risk() == Decimal("0.00")