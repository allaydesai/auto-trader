"""Test suite for OrderStateManager."""

import pytest
import asyncio
import json
import tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from decimal import Decimal

from auto_trader.models import Order, OrderSide, OrderType, OrderStatus
from auto_trader.integrations.ibkr_client import OrderStateManager, OrderStateSnapshot


@pytest.fixture
def temp_state_dir():
    """Temporary directory for state files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def state_manager(temp_state_dir):
    """OrderStateManager instance with temporary directory."""
    return OrderStateManager(
        state_dir=temp_state_dir,
        max_backups=5,
        backup_interval=1,  # 1 second for faster testing
    )


@pytest.fixture
def sample_orders():
    """Sample orders for testing."""
    return {
        "SIM_001": Order(
            order_id="SIM_001",
            trade_plan_id="AAPL_20250827_001",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100,
            status=OrderStatus.FILLED,
            price=Decimal("180.50"),
            filled_quantity=100,
            average_fill_price=Decimal("180.52"),
        ),
        "SIM_002": Order(
            order_id="SIM_002",
            trade_plan_id="TSLA_20250827_001",
            symbol="TSLA",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=50,
            status=OrderStatus.SUBMITTED,
            price=Decimal("250.00"),
        ),
    }


class TestOrderStateManager:
    """Test cases for OrderStateManager."""

    def test_initialization(self, temp_state_dir):
        """Test state manager initialization."""
        manager = OrderStateManager(temp_state_dir, max_backups=3, backup_interval=60)
        
        assert manager.state_dir == temp_state_dir
        assert manager.max_backups == 3
        assert manager.backup_interval == 60
        
        # Check directories were created
        assert manager.state_dir.exists()
        assert manager.backup_dir.exists()
        
        # Check file paths
        assert manager.state_file == temp_state_dir / "order_state.json"
        assert manager.backup_dir == temp_state_dir / "backups"

    @pytest.mark.asyncio
    async def test_save_and_load_state(self, state_manager, sample_orders):
        """Test saving and loading order state."""
        # Save state
        await state_manager.save_state(sample_orders)
        
        # Verify state file exists
        assert state_manager.state_file.exists()
        
        # Load state
        loaded_orders = await state_manager.load_state()
        
        # Verify loaded orders match saved orders
        assert len(loaded_orders) == 2
        assert "SIM_001" in loaded_orders
        assert "SIM_002" in loaded_orders
        
        # Verify order details
        loaded_order_1 = loaded_orders["SIM_001"]
        assert loaded_order_1.order_id == "SIM_001"
        assert loaded_order_1.symbol == "AAPL"
        assert loaded_order_1.quantity == 100
        assert loaded_order_1.status == OrderStatus.FILLED
        assert loaded_order_1.average_fill_price == Decimal("180.52")

    @pytest.mark.asyncio
    async def test_save_empty_orders(self, state_manager):
        """Test saving empty order dictionary."""
        await state_manager.save_state({})
        
        loaded_orders = await state_manager.load_state()
        assert loaded_orders == {}

    @pytest.mark.asyncio
    async def test_load_nonexistent_state(self, state_manager):
        """Test loading when no state file exists."""
        # Should return empty dict without error
        loaded_orders = await state_manager.load_state()
        assert loaded_orders == {}

    @pytest.mark.asyncio
    async def test_save_with_serialization_error(self, state_manager):
        """Test handling serialization errors for invalid orders."""
        # Create a mock order that will fail serialization
        class BadOrder(Order):
            def model_dump(self):
                raise ValueError("Serialization error")
        
        # Create mixed valid/invalid orders
        orders = {
            "GOOD_001": Order(
                order_id="GOOD_001",
                trade_plan_id="TEST_001",
                symbol="AAPL",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=100,
                status=OrderStatus.PENDING,
            ),
            "BAD_001": BadOrder(
                order_id="BAD_001",
                trade_plan_id="TEST_002", 
                symbol="TSLA",
                side=OrderSide.SELL,
                order_type=OrderType.LIMIT,
                quantity=50,
                status=OrderStatus.PENDING,
            ),
        }
        
        # Should save successfully (skipping bad order)
        await state_manager.save_state(orders)
        
        # Load should only contain good order
        loaded_orders = await state_manager.load_state()
        assert len(loaded_orders) == 1
        assert "GOOD_001" in loaded_orders
        assert "BAD_001" not in loaded_orders

    @pytest.mark.asyncio
    async def test_backup_creation(self, state_manager, sample_orders):
        """Test manual backup creation."""
        # Save initial state
        await state_manager.save_state(sample_orders)
        
        # Create backup
        backup_path = await state_manager.create_backup("test_backup")
        
        # Verify backup file exists
        assert backup_path
        backup_file = Path(backup_path)
        assert backup_file.exists()
        assert "test_backup" in backup_file.name
        
        # Verify backup contains same data
        with open(backup_file, 'r') as f:
            backup_data = json.load(f)
        
        snapshot = OrderStateSnapshot(**backup_data)
        assert len(snapshot.active_orders) == 2

    @pytest.mark.asyncio
    async def test_backup_cleanup(self, state_manager, sample_orders):
        """Test automatic cleanup of old backup files."""
        # Save initial state
        await state_manager.save_state(sample_orders)
        
        # Create more backups than max_backups (5)
        backup_paths = []
        for i in range(7):
            backup_path = await state_manager.create_backup(f"backup_{i}")
            backup_paths.append(backup_path)
            # Small delay to ensure different timestamps
            await asyncio.sleep(0.01)
        
        # Check that only max_backups (5) files remain
        backup_files = list(state_manager.backup_dir.glob("order_state_*.json"))
        assert len(backup_files) == 5, f"Expected 5 backup files, found {len(backup_files)}"
        
        # The cleanup should have removed the oldest files
        # Since we created 7 backups and limit is 5, the 2 oldest should be removed
        backup_names = [f.name for f in backup_files]
        
        # Just verify that the most recent backup exists
        assert any("backup_6" in name for name in backup_names), f"backup_6 not found in {backup_names}"

    @pytest.mark.asyncio
    async def test_load_from_backup_when_main_corrupted(self, state_manager, sample_orders):
        """Test loading from backup when main state file is corrupted."""
        # Save valid state
        await state_manager.save_state(sample_orders)
        
        # Create backup
        await state_manager.create_backup("good_backup")
        
        # Corrupt main state file
        with open(state_manager.state_file, 'w') as f:
            f.write("invalid json content")
        
        # Load should fall back to backup
        loaded_orders = await state_manager.load_state()
        
        # Should successfully load from backup
        assert len(loaded_orders) == 2
        assert "SIM_001" in loaded_orders

    @pytest.mark.asyncio 
    async def test_periodic_backup(self, state_manager, sample_orders):
        """Test periodic backup functionality."""
        # Save initial state
        await state_manager.save_state(sample_orders)
        
        # Start periodic backup
        await state_manager.start_periodic_backup()
        
        # Wait longer than backup interval
        await asyncio.sleep(1.2)
        
        # Stop periodic backup
        await state_manager.stop_periodic_backup()
        
        # Check that periodic backup was created
        backup_files = list(state_manager.backup_dir.glob("*periodic*"))
        assert len(backup_files) >= 1

    @pytest.mark.asyncio
    async def test_clear_state(self, state_manager, sample_orders):
        """Test clearing state file."""
        # Save initial state
        await state_manager.save_state(sample_orders)
        assert state_manager.state_file.exists()
        
        # Clear state
        await state_manager.clear_state()
        
        # State file should be removed
        assert not state_manager.state_file.exists()
        
        # Load should return empty
        loaded_orders = await state_manager.load_state()
        assert loaded_orders == {}

    @pytest.mark.asyncio
    async def test_atomic_write(self, state_manager, sample_orders):
        """Test that saves are atomic (temp file -> rename)."""
        # Ensure temp file doesn't exist initially
        assert not state_manager.temp_file.exists()
        
        # Save state
        await state_manager.save_state(sample_orders)
        
        # Temp file should be cleaned up after successful save
        assert not state_manager.temp_file.exists()
        assert state_manager.state_file.exists()

    def test_order_state_snapshot_model(self):
        """Test OrderStateSnapshot pydantic model."""
        timestamp = datetime.now(timezone.utc)
        
        snapshot = OrderStateSnapshot(
            timestamp=timestamp,
            active_orders={
                "TEST_001": {
                    "order_id": "TEST_001",
                    "symbol": "AAPL",
                    "quantity": 100,
                }
            },
            metadata={"reason": "test"},
        )
        
        assert snapshot.timestamp == timestamp
        assert len(snapshot.active_orders) == 1
        assert snapshot.metadata["reason"] == "test"
        
        # Test serialization
        data = snapshot.model_dump()
        assert "timestamp" in data
        assert "active_orders" in data
        assert "metadata" in data

    @pytest.mark.asyncio
    async def test_deserialization_error_handling(self, state_manager):
        """Test handling of deserialization errors during load."""
        # Create state file with partially invalid order data
        snapshot_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "active_orders": {
                "GOOD_001": {
                    "order_id": "GOOD_001",
                    "trade_plan_id": "TEST_001",
                    "symbol": "AAPL",
                    "side": "BUY",
                    "order_type": "MKT",
                    "quantity": 100,
                    "status": "PendingSubmit",
                    "filled_quantity": 0,
                    "remaining_quantity": 100,
                },
                "BAD_001": {
                    "order_id": "BAD_001",
                    "invalid_field": "this will cause deserialization error",
                    # Missing required fields
                },
            },
            "metadata": {},
        }
        
        # Write invalid data to state file
        with open(state_manager.state_file, 'w') as f:
            json.dump(snapshot_data, f)
        
        # Load should skip invalid orders and continue with valid ones
        loaded_orders = await state_manager.load_state()
        
        assert len(loaded_orders) == 1  # Only valid order loaded
        assert "GOOD_001" in loaded_orders
        assert "BAD_001" not in loaded_orders

    @pytest.mark.asyncio
    async def test_backup_no_state_file(self, state_manager):
        """Test creating backup when no state file exists."""
        # Try to create backup without state file
        backup_path = await state_manager.create_backup("no_state")
        
        # Should return empty string and log warning
        assert backup_path == ""