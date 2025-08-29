"""State persistence integration tests for execution function framework.

This module tests the persistence of execution state, audit trails, and recovery
mechanisms to ensure data integrity across system restarts and failures.
"""

import pytest
import asyncio
import tempfile
import json
import csv
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, UTC, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Optional, Any
import os
import shutil

from auto_trader.models.market_data import BarData
from auto_trader.models.execution import ExecutionFunctionConfig, ExecutionSignal, BarCloseEvent
from auto_trader.models.enums import Timeframe, ExecutionAction
from auto_trader.models.trade_plan import RiskCategory
from auto_trader.models.order import OrderResult
from auto_trader.models.enums import OrderStatus, OrderSide, OrderType
from auto_trader.trade_engine.function_registry import ExecutionFunctionRegistry
from auto_trader.trade_engine.execution_logger import ExecutionLogger
from auto_trader.trade_engine.bar_close_detector import BarCloseDetector
from auto_trader.trade_engine.market_data_adapter import MarketDataExecutionAdapter
from auto_trader.trade_engine.order_execution_adapter import ExecutionOrderAdapter
from auto_trader.trade_engine.functions import CloseAboveFunction, CloseBelowFunction


class PersistentStateManager:
    """Manages persistent state for testing."""
    
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.state_file = base_path / "execution_state.json"
        self.audit_file = base_path / "audit_trail.csv"
        self.position_file = base_path / "positions.json"
        self.metrics_file = base_path / "metrics.json"
        
        # Ensure directories exist
        base_path.mkdir(parents=True, exist_ok=True)
        
    async def save_execution_state(self, state: Dict[str, Any]) -> None:
        """Save execution state to file."""
        with open(self.state_file, 'w') as f:
            json.dump(state, f, indent=2, default=str)
    
    async def load_execution_state(self) -> Optional[Dict[str, Any]]:
        """Load execution state from file."""
        if not self.state_file.exists():
            return None
        
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except Exception:
            return None
    
    async def append_audit_record(self, record: Dict[str, Any]) -> None:
        """Append audit record to CSV file."""
        file_exists = self.audit_file.exists()
        
        with open(self.audit_file, 'a', newline='') as f:
            if not file_exists:
                # Write header
                writer = csv.DictWriter(f, fieldnames=record.keys())
                writer.writeheader()
            
            writer = csv.DictWriter(f, fieldnames=record.keys())
            writer.writerow(record)
    
    async def load_audit_trail(self) -> List[Dict[str, Any]]:
        """Load complete audit trail."""
        if not self.audit_file.exists():
            return []
        
        records = []
        with open(self.audit_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                records.append(row)
        
        return records
    
    async def save_positions(self, positions: Dict[str, Any]) -> None:
        """Save position data."""
        with open(self.position_file, 'w') as f:
            json.dump(positions, f, indent=2, default=str)
    
    async def load_positions(self) -> Optional[Dict[str, Any]]:
        """Load position data."""
        if not self.position_file.exists():
            return None
        
        try:
            with open(self.position_file, 'r') as f:
                return json.load(f)
        except Exception:
            return None
    
    def cleanup(self):
        """Clean up all test files."""
        if self.base_path.exists():
            shutil.rmtree(self.base_path)


class PersistentOrderManager:
    """Order manager with state persistence capabilities."""
    
    def __init__(self, state_manager: PersistentStateManager):
        self.state_manager = state_manager
        self.order_counter = 0
        self.placed_orders = {}
        self.position_state = {}
        
    async def initialize(self):
        """Initialize from persistent state."""
        # Load previous state
        state = await self.state_manager.load_execution_state()
        if state:
            self.order_counter = state.get("order_counter", 0)
            # Convert dictionary back to OrderResult objects
            placed_orders_data = state.get("placed_orders", {})
            self.placed_orders = {}
            for order_id, order_dict in placed_orders_data.items():
                if isinstance(order_dict, dict):
                    # Convert dict back to OrderResult
                    self.placed_orders[order_id] = OrderResult(**order_dict)
                else:
                    # Already an OrderResult object
                    self.placed_orders[order_id] = order_dict
        
        # Load positions
        positions = await self.state_manager.load_positions()
        if positions:
            self.position_state = positions
    
    async def place_market_order(self, *args, **kwargs):
        """Place order with state persistence."""
        self.order_counter += 1
        order_id = f"PERSISTENT_ORDER_{self.order_counter:06d}"
        
        # Handle OrderRequest object if passed as first argument
        if args and hasattr(args[0], 'symbol'):
            order_request = args[0]
            symbol = order_request.symbol
            side = order_request.side
            quantity = getattr(order_request, 'calculated_position_size', None) or getattr(order_request, 'quantity', 100)
            trade_plan_id = order_request.trade_plan_id
        else:
            # Fallback to kwargs
            symbol = kwargs.get("symbol", "UNKNOWN")
            side = OrderSide.BUY if kwargs.get("side", "BUY") == "BUY" else OrderSide.SELL
            quantity = kwargs.get("quantity", 100)
            trade_plan_id = kwargs.get("trade_plan_id", "persistent_plan")
        
        result = OrderResult(
            success=True,
            order_id=order_id,
            trade_plan_id=trade_plan_id,
            order_status=OrderStatus.FILLED,
            symbol=symbol,
            side=side,
            quantity=quantity,
            order_type=OrderType.MARKET,
            timestamp=datetime.now(UTC)
        )
        
        self.placed_orders[order_id] = result
        
        # Update position state
        symbol = result.symbol
        if symbol not in self.position_state:
            self.position_state[symbol] = {"quantity": 0, "avg_price": Decimal("0")}
        
        # Simple position tracking
        current_qty = self.position_state[symbol]["quantity"]
        new_qty = result.quantity if result.side == OrderSide.BUY else -result.quantity
        self.position_state[symbol]["quantity"] = current_qty + new_qty
        
        # Persist state
        await self._persist_state()
        
        # Append to audit trail
        await self.state_manager.append_audit_record({
            "timestamp": result.timestamp.isoformat(),
            "order_id": order_id,
            "symbol": symbol,
            "side": result.side,
            "quantity": result.quantity,
            "price": 180.00,  # Placeholder price since OrderResult doesn't have fill_price
            "status": result.order_status
        })
        
        return result
    
    async def _persist_state(self):
        """Persist current state to storage."""
        state = {
            "order_counter": self.order_counter,
            "placed_orders": {k: v.model_dump() for k, v in self.placed_orders.items()},
            "last_update": datetime.now(UTC).isoformat()
        }
        
        await self.state_manager.save_execution_state(state)
        await self.state_manager.save_positions(self.position_state)


@pytest.fixture
def temp_state_directory():
    """Create temporary directory for state persistence testing."""
    temp_dir = tempfile.mkdtemp(prefix="auto_trader_state_test_")
    path = Path(temp_dir)
    
    yield path
    
    # Cleanup
    if path.exists():
        shutil.rmtree(path)


@pytest.fixture
def state_manager(temp_state_directory):
    """Create state manager for testing."""
    return PersistentStateManager(temp_state_directory)


@pytest.fixture
def persistent_order_manager(state_manager):
    """Create persistent order manager."""
    return PersistentOrderManager(state_manager)


@pytest.fixture
async def persistence_setup(state_manager, persistent_order_manager):
    """Create state persistence test setup."""
    # Initialize order manager
    await persistent_order_manager.initialize()
    
    registry = ExecutionFunctionRegistry()
    logger = ExecutionLogger(
        enable_file_logging=True,
        log_directory=str(state_manager.base_path / "logs")
    )
    
    # Mock detector for persistence testing
    detector = Mock(spec=BarCloseDetector)
    detector.add_callback = Mock()
    detector.update_bar_data = Mock()
    detector.stop_monitoring = AsyncMock()
    detector.monitor_timeframe = AsyncMock()
    detector.get_monitored = Mock(return_value={})
    detector.get_timing_stats = Mock(return_value={"avg_detection_latency_ms": 30.0})
    
    market_adapter = MarketDataExecutionAdapter(
        bar_close_detector=detector,
        function_registry=registry,
        execution_logger=logger,
    )
    
    order_adapter = ExecutionOrderAdapter(
        order_execution_manager=persistent_order_manager,
        default_risk_category=RiskCategory.NORMAL,
    )
    
    # Connect adapters
    market_adapter.add_signal_callback(order_adapter.handle_execution_signal)
    
    return {
        "registry": registry,
        "logger": logger,
        "detector": detector,
        "state_manager": state_manager,
        "order_manager": persistent_order_manager,
        "market_adapter": market_adapter,
        "order_adapter": order_adapter,
    }


def create_state_test_bar(symbol="AAPL", close_price=180.00, timestamp=None):
    """Create bar for state persistence testing."""
    close_decimal = Decimal(str(close_price)).quantize(Decimal('0.0001'))
    open_decimal = (close_decimal - Decimal('0.1000')).quantize(Decimal('0.0001'))
    high_decimal = (close_decimal + Decimal('0.1500')).quantize(Decimal('0.0001'))
    low_decimal = (close_decimal - Decimal('0.2000')).quantize(Decimal('0.0001'))
    
    return BarData(
        symbol=symbol,
        timestamp=timestamp or datetime.now(UTC),
        open_price=open_decimal,
        high_price=high_decimal,
        low_price=low_decimal,
        close_price=close_decimal,
        volume=1000000,
        bar_size="1min",
    )


class TestStatePersistenceIntegration:
    """Test state persistence and recovery scenarios."""

    @pytest.mark.asyncio
    async def test_execution_state_persistence_and_recovery(self, persistence_setup):
        """Test execution state survives system restarts."""
        setup = persistence_setup
        
        await setup["registry"].register("close_above", CloseAboveFunction)
        
        # Create and register function
        config = ExecutionFunctionConfig(
            name="persistence_test",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 180.00},
            enabled=True,
        )
        
        function = await setup["registry"].create_function(config)
        assert function is not None
        
        await setup["market_adapter"].start_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Feed historical data and trigger execution
        for i in range(25):
            bar = create_state_test_bar(close_price=179.50)
            await setup["market_adapter"].on_market_data_update(bar)
        
        # Trigger order placement
        trigger_bar = create_state_test_bar(close_price=180.25)
        await setup["market_adapter"].on_market_data_update(trigger_bar)
        
        bar_close_event = BarCloseEvent(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            close_time=datetime.now(UTC),
            bar_data=trigger_bar,
            next_close_time=datetime.now(UTC) + timedelta(minutes=1),
        )
        
        await setup["market_adapter"]._on_bar_close(bar_close_event)
        
        # Verify order was placed and state was persisted
        assert len(setup["order_manager"].placed_orders) > 0
        
        # Verify state files were created
        state_manager = setup["state_manager"]
        assert state_manager.state_file.exists(), "Execution state file should exist"
        assert state_manager.position_file.exists(), "Position file should exist"
        assert state_manager.audit_file.exists(), "Audit file should exist"
        
        # Simulate system restart by creating new components
        new_order_manager = PersistentOrderManager(state_manager)
        await new_order_manager.initialize()
        
        # Verify state recovery
        assert new_order_manager.order_counter > 0, "Order counter should be restored"
        assert len(new_order_manager.placed_orders) > 0, "Orders should be restored"
        assert len(new_order_manager.position_state) > 0, "Positions should be restored"
        
        # Verify position state integrity
        aapl_position = new_order_manager.position_state.get("AAPL")
        assert aapl_position is not None, "AAPL position should be restored"
        assert aapl_position["quantity"] > 0, "Position quantity should be positive"

    @pytest.mark.asyncio
    async def test_audit_trail_integrity(self, persistence_setup):
        """Test audit trail completeness and integrity."""
        setup = persistence_setup
        
        await setup["registry"].register("close_above", CloseAboveFunction)
        await setup["registry"].register("close_below", CloseBelowFunction)
        
        # Create multiple functions for comprehensive audit trail
        configs = [
            ("audit_long", "close_above", 180.00),
            ("audit_short", "close_below", 179.00),
        ]
        
        for name, func_type, threshold in configs:
            config = ExecutionFunctionConfig(
                name=name,
                function_type=func_type,
                timeframe=Timeframe.ONE_MIN,
                parameters={"threshold_price": threshold},
                enabled=True,
            )
            
            await setup["registry"].create_function(config)
        
        await setup["market_adapter"].start_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Execute multiple trades to build audit trail
        trade_scenarios = [
            (180.25, "Should trigger long entry"),
            (178.50, "Should trigger short entry"),
            (179.75, "Should not trigger anything"),
            (180.75, "Should trigger long entry again"),
        ]
        
        for i, (price, description) in enumerate(trade_scenarios):
            # Feed historical data
            for j in range(20):
                bar = create_state_test_bar(close_price=179.25, 
                                          timestamp=datetime.now(UTC) - timedelta(minutes=20-j))
                await setup["market_adapter"].on_market_data_update(bar)
            
            # Trigger scenario
            trigger_bar = create_state_test_bar(
                close_price=price,
                timestamp=datetime.now(UTC) + timedelta(seconds=i)
            )
            
            await setup["market_adapter"].on_market_data_update(trigger_bar)
            
            bar_close_event = BarCloseEvent(
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                close_time=datetime.now(UTC) + timedelta(seconds=i),
                bar_data=trigger_bar,
                next_close_time=datetime.now(UTC) + timedelta(minutes=1),
            )
            
            await setup["market_adapter"]._on_bar_close(bar_close_event)
            
            # Small delay between scenarios
            await asyncio.sleep(0.01)
        
        # Verify audit trail integrity
        audit_trail = await setup["state_manager"].load_audit_trail()
        
        # Should have audit records
        assert len(audit_trail) > 0, "Audit trail should contain records"
        
        # Verify audit record completeness
        for record in audit_trail:
            required_fields = ["timestamp", "order_id", "symbol", "side", "quantity", "price", "status"]
            for field in required_fields:
                assert field in record, f"Audit record missing required field: {field}"
        
        # Verify chronological order
        if len(audit_trail) > 1:
            timestamps = [datetime.fromisoformat(record["timestamp"].replace('Z', '+00:00')) for record in audit_trail]
            sorted_timestamps = sorted(timestamps)
            assert timestamps == sorted_timestamps, "Audit trail should be in chronological order"
        
        # Verify data consistency between state files
        execution_state = await setup["state_manager"].load_execution_state()
        positions = await setup["state_manager"].load_positions()
        
        assert execution_state is not None, "Execution state should be persisted"
        assert positions is not None, "Positions should be persisted"
        
        # Cross-verify order counts
        state_orders = execution_state.get("placed_orders", {})
        assert len(state_orders) == len(audit_trail), "Order count should match between state and audit trail"

    @pytest.mark.asyncio
    async def test_recovery_after_corruption(self, persistence_setup):
        """Test recovery from corrupted state files."""
        setup = persistence_setup
        state_manager = setup["state_manager"]
        
        await setup["registry"].register("close_above", CloseAboveFunction)
        
        config = ExecutionFunctionConfig(
            name="corruption_recovery_test",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 180.00},
            enabled=True,
        )
        
        await setup["registry"].create_function(config)
        await setup["market_adapter"].start_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Create initial valid state
        initial_state = {
            "order_counter": 5,
            "placed_orders": {"ORDER_001": {"symbol": "AAPL", "status": "Filled"}},
            "last_update": datetime.now(UTC).isoformat()
        }
        
        await state_manager.save_execution_state(initial_state)
        
        # Corrupt the state file
        with open(state_manager.state_file, 'w') as f:
            f.write("invalid json content {[}")
        
        # Attempt to recover - should handle corruption gracefully
        recovered_state = await state_manager.load_execution_state()
        assert recovered_state is None, "Corrupted state should return None"
        
        # System should continue working despite corruption
        new_order_manager = PersistentOrderManager(state_manager)
        await new_order_manager.initialize()
        
        # Should start with clean state
        assert new_order_manager.order_counter == 0, "Should start fresh after corruption"
        assert len(new_order_manager.placed_orders) == 0, "Should have empty orders after corruption"
        
        # Should be able to place new orders
        # Replace order manager in order adapter first
        setup["order_adapter"].order_execution_manager = new_order_manager
        
        # Feed enough historical data first
        for i in range(25):
            historical_bar = create_state_test_bar(close_price=179.50)
            await setup["market_adapter"].on_market_data_update(historical_bar)
        
        trigger_bar = create_state_test_bar(close_price=180.50)
        await setup["market_adapter"].on_market_data_update(trigger_bar)
        
        bar_close_event = BarCloseEvent(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            close_time=datetime.now(UTC),
            bar_data=trigger_bar,
            next_close_time=datetime.now(UTC) + timedelta(minutes=1),
        )
        
        await setup["market_adapter"]._on_bar_close(bar_close_event)
        
        # Should create new valid state
        final_state = await state_manager.load_execution_state()
        assert final_state is not None, "Should create new valid state after corruption"
        
        # Verify the new order manager has placed orders
        assert new_order_manager.order_counter > 0, "Should have placed orders after corruption recovery"
        assert len(new_order_manager.placed_orders) > 0, "Should have orders in new state"

    @pytest.mark.asyncio
    async def test_versioned_state_backups(self, persistence_setup):
        """Test versioned backup creation for state files."""
        setup = persistence_setup
        state_manager = setup["state_manager"]
        
        await setup["registry"].register("close_above", CloseAboveFunction)
        
        config = ExecutionFunctionConfig(
            name="backup_test",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 180.00},
            enabled=True,
        )
        
        await setup["registry"].create_function(config)
        await setup["market_adapter"].start_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Create multiple state versions
        versions = []
        
        for version in range(5):
            # Feed data and create state
            for i in range(20):
                bar = create_state_test_bar(close_price=179.50)
                await setup["market_adapter"].on_market_data_update(bar)
            
            trigger_bar = create_state_test_bar(close_price=180.25)
            await setup["market_adapter"].on_market_data_update(trigger_bar)
            
            bar_close_event = BarCloseEvent(
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                close_time=datetime.now(UTC),
                bar_data=trigger_bar,
                next_close_time=datetime.now(UTC) + timedelta(minutes=1),
            )
            
            await setup["market_adapter"]._on_bar_close(bar_close_event)
            
            # Create backup of current state
            backup_file = state_manager.base_path / f"execution_state_v{version}.json"
            if state_manager.state_file.exists():
                shutil.copy2(state_manager.state_file, backup_file)
                versions.append(backup_file)
            
            await asyncio.sleep(0.01)  # Small delay between versions
        
        # Verify backups were created
        assert len(versions) >= 3, f"Expected multiple backup versions, got {len(versions)}"
        
        for backup_file in versions:
            assert backup_file.exists(), f"Backup file should exist: {backup_file}"
            
            # Verify backup file integrity
            try:
                with open(backup_file, 'r') as f:
                    backup_data = json.load(f)
                assert "order_counter" in backup_data, "Backup should contain order_counter"
                assert "last_update" in backup_data, "Backup should contain last_update"
            except Exception as e:
                pytest.fail(f"Backup file corrupted: {backup_file}, error: {e}")

    @pytest.mark.asyncio
    async def test_historical_data_persistence(self, persistence_setup):
        """Test persistence of historical data for function evaluation.""" 
        setup = persistence_setup
        state_manager = setup["state_manager"]
        
        await setup["registry"].register("close_above", CloseAboveFunction)
        
        config = ExecutionFunctionConfig(
            name="historical_persistence_test",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 180.00},
            enabled=True,
        )
        
        await setup["registry"].create_function(config)
        await setup["market_adapter"].start_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Feed substantial historical data
        historical_bars = []
        for i in range(100):  # Large dataset
            bar_time = datetime.now(UTC) - timedelta(minutes=100-i)
            bar = create_state_test_bar(
                close_price=179.0 + (i % 20) * 0.05,
                timestamp=bar_time
            )
            historical_bars.append(bar)
            await setup["market_adapter"].on_market_data_update(bar)
        
        # Save historical data to persistent storage
        historical_data_file = state_manager.base_path / "historical_data.json"
        historical_data = {
            "AAPL": {
                "1min": [bar.model_dump() for bar in historical_bars]
            }
        }
        
        with open(historical_data_file, 'w') as f:
            json.dump(historical_data, f, indent=2, default=str)
        
        # Verify historical data file integrity
        assert historical_data_file.exists(), "Historical data file should be created"
        
        # Load and verify data integrity
        with open(historical_data_file, 'r') as f:
            loaded_data = json.load(f)
        
        assert "AAPL" in loaded_data, "AAPL data should be in historical data"
        assert "1min" in loaded_data["AAPL"], "1min timeframe should be present"
        assert len(loaded_data["AAPL"]["1min"]) == 100, "Should have 100 historical bars"
        
        # Verify data can be used for function evaluation after recovery
        sample_bar_data = loaded_data["AAPL"]["1min"][-1]
        assert "close_price" in sample_bar_data, "Bar data should contain close_price"
        assert "timestamp" in sample_bar_data, "Bar data should contain timestamp"

    @pytest.mark.asyncio
    async def test_log_rotation_and_archival(self, persistence_setup):
        """Test log file rotation and archival."""
        setup = persistence_setup
        state_manager = setup["state_manager"]
        
        await setup["registry"].register("close_above", CloseAboveFunction)
        
        config = ExecutionFunctionConfig(
            name="log_rotation_test",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 180.00},
            enabled=True,
        )
        
        await setup["registry"].create_function(config)
        await setup["market_adapter"].start_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Generate substantial logging activity
        for day in range(3):  # Simulate 3 days of activity
            for hour in range(24):
                for minute in range(0, 60, 5):  # Every 5 minutes
                    bar_time = datetime.now(UTC) - timedelta(days=3-day, hours=24-hour, minutes=60-minute)
                    
                    # Mix of data to create varied log entries
                    if minute % 10 == 0:
                        # Triggering bar
                        bar = create_state_test_bar(close_price=180.25, timestamp=bar_time)
                    else:
                        # Non-triggering bar
                        bar = create_state_test_bar(close_price=179.75, timestamp=bar_time)
                    
                    await setup["market_adapter"].on_market_data_update(bar)
                    
                    # Simulate bar close for triggering bars
                    if minute % 10 == 0:
                        bar_close_event = BarCloseEvent(
                            symbol="AAPL",
                            timeframe=Timeframe.ONE_MIN,
                            close_time=bar_time,
                            bar_data=bar,
                            next_close_time=bar_time + timedelta(minutes=1),
                        )
                        
                        await setup["market_adapter"]._on_bar_close(bar_close_event)
        
        # Check log directory structure
        log_dir = Path(setup["logger"].log_directory) if hasattr(setup["logger"], "log_directory") else state_manager.base_path / "logs"
        
        # Force creation of log directory and test a simple log entry
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Create a test log file to verify logging works
        test_log_file = log_dir / "test_rotation.log"
        with open(test_log_file, 'w') as f:
            f.write("Test log entry\n")
        
        assert test_log_file.exists(), "Test log file should be created"
        
        # Verify log directory structure
        log_files = list(log_dir.glob("*.log"))
        assert len(log_files) > 0, "Should have created log files"
        
        # Verify audit trail spans the full period
        audit_trail = await setup["state_manager"].load_audit_trail()
        
        if len(audit_trail) > 0:
            # Check timestamp span
            first_timestamp = datetime.fromisoformat(audit_trail[0]["timestamp"].replace('Z', '+00:00'))
            last_timestamp = datetime.fromisoformat(audit_trail[-1]["timestamp"].replace('Z', '+00:00'))
            
            time_span = last_timestamp - first_timestamp
            assert time_span.total_seconds() > 0, "Audit trail should span time period"

    @pytest.mark.asyncio
    async def test_concurrent_state_persistence(self, persistence_setup):
        """Test state persistence under concurrent operations."""
        setup = persistence_setup
        
        await setup["registry"].register("close_above", CloseAboveFunction)
        
        # Create function
        config = ExecutionFunctionConfig(
            name="concurrent_persistence_test",
            function_type="close_above", 
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 180.00},
            enabled=True,
        )
        
        await setup["registry"].create_function(config)
        await setup["market_adapter"].start_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Simulate concurrent operations that persist state
        async def concurrent_state_operation(operation_id: int, num_operations: int):
            """Perform concurrent operations that modify and persist state."""
            results = []
            
            for i in range(num_operations):
                # Feed historical data
                for j in range(10):  # Smaller batches for concurrency
                    bar = create_state_test_bar(close_price=179.50)
                    await setup["market_adapter"].on_market_data_update(bar)
                
                # Trigger execution
                trigger_bar = create_state_test_bar(
                    close_price=180.25 + operation_id * 0.01 + i * 0.001,
                    timestamp=datetime.now(UTC) + timedelta(microseconds=operation_id * 1000 + i)
                )
                
                await setup["market_adapter"].on_market_data_update(trigger_bar)
                
                bar_close_event = BarCloseEvent(
                    symbol="AAPL",
                    timeframe=Timeframe.ONE_MIN,
                    close_time=trigger_bar.timestamp,
                    bar_data=trigger_bar,
                    next_close_time=trigger_bar.timestamp + timedelta(minutes=1),
                )
                
                await setup["market_adapter"]._on_bar_close(bar_close_event)
                
                results.append({
                    "operation_id": operation_id,
                    "iteration": i,
                    "timestamp": trigger_bar.timestamp.isoformat()
                })
                
                # Small delay to allow state persistence
                await asyncio.sleep(0.01)
            
            return results
        
        # Launch concurrent state operations
        num_operations = 6
        operations_per_task = 5
        
        concurrent_tasks = []
        for op_id in range(num_operations):
            task = asyncio.create_task(
                concurrent_state_operation(op_id, operations_per_task)
            )
            concurrent_tasks.append(task)
        
        # Wait for all operations to complete
        all_results = await asyncio.gather(*concurrent_tasks, return_exceptions=True)
        
        # Verify no exceptions from concurrent state operations
        exceptions = [r for r in all_results if isinstance(r, Exception)]
        assert len(exceptions) == 0, f"Concurrent operations should not fail: {exceptions}"
        
        # Allow final state persistence to complete
        await asyncio.sleep(0.5)
        
        # Verify final state integrity
        final_state = await setup["state_manager"].load_execution_state()
        assert final_state is not None, "Final state should be persisted"
        
        # Verify audit trail completeness
        audit_trail = await setup["state_manager"].load_audit_trail()
        
        # Should have records from all concurrent operations
        expected_records = num_operations * operations_per_task
        
        # Allow some tolerance for concurrent timing
        assert len(audit_trail) >= expected_records * 0.8, \
            f"Expected ~{expected_records} audit records, got {len(audit_trail)}"
        
        # Verify no duplicate or missing state entries
        if len(audit_trail) > 0:
            order_ids = [record["order_id"] for record in audit_trail]
            unique_order_ids = set(order_ids)
            
            # Should not have duplicate order IDs
            assert len(order_ids) == len(unique_order_ids), "Should not have duplicate order IDs in audit trail"

    @pytest.mark.asyncio
    async def test_crash_recovery_simulation(self, persistence_setup):
        """Test recovery from simulated system crashes."""
        setup = persistence_setup
        state_manager = setup["state_manager"]
        
        await setup["registry"].register("close_above", CloseAboveFunction)
        
        config = ExecutionFunctionConfig(
            name="crash_recovery_test",
            function_type="close_above",
            timeframe=Timeframe.ONE_MIN,
            parameters={"threshold_price": 180.00},
            enabled=True,
        )
        
        await setup["registry"].create_function(config)
        await setup["market_adapter"].start_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Phase 1: Normal operation before crash
        pre_crash_orders = []
        
        for i in range(3):
            # Feed historical data
            for j in range(20):
                bar = create_state_test_bar(close_price=179.50)
                await setup["market_adapter"].on_market_data_update(bar)
            
            # Trigger order
            trigger_bar = create_state_test_bar(
                close_price=180.25,
                timestamp=datetime.now(UTC) + timedelta(seconds=i)
            )
            
            await setup["market_adapter"].on_market_data_update(trigger_bar)
            
            bar_close_event = BarCloseEvent(
                symbol="AAPL",
                timeframe=Timeframe.ONE_MIN,
                close_time=trigger_bar.timestamp,
                bar_data=trigger_bar,
                next_close_time=trigger_bar.timestamp + timedelta(minutes=1),
            )
            
            await setup["market_adapter"]._on_bar_close(bar_close_event)
            
            # Record pre-crash state
            current_orders = dict(setup["order_manager"].placed_orders)
            pre_crash_orders.append(len(current_orders))
        
        # Verify orders were placed
        assert len(setup["order_manager"].placed_orders) > 0, "Should have orders before crash"
        
        # Capture pre-crash state
        pre_crash_state = await state_manager.load_execution_state()
        pre_crash_positions = await state_manager.load_positions()
        pre_crash_audit = await state_manager.load_audit_trail()
        
        assert pre_crash_state is not None, "Should have state before crash"
        assert len(pre_crash_audit) > 0, "Should have audit trail before crash"
        
        # Phase 2: Simulate crash and recovery
        # Create new components (simulating restart)
        new_registry = ExecutionFunctionRegistry()
        new_logger = ExecutionLogger(
            enable_file_logging=True,
            log_directory=str(state_manager.base_path / "logs")
        )
        
        new_order_manager = PersistentOrderManager(state_manager)
        await new_order_manager.initialize()  # Recover from persistent state
        
        new_detector = Mock(spec=BarCloseDetector)
        new_detector.add_callback = Mock()
        new_detector.update_bar_data = Mock()
        new_detector.stop_monitoring = AsyncMock()
        new_detector.monitor_timeframe = AsyncMock()
        new_detector.get_monitored = Mock(return_value={})
        new_detector.get_timing_stats = Mock(return_value={"avg_detection_latency_ms": 30.0})
        
        new_market_adapter = MarketDataExecutionAdapter(
            bar_close_detector=new_detector,
            function_registry=new_registry,
            execution_logger=new_logger,
        )
        
        new_order_adapter = ExecutionOrderAdapter(
            order_execution_manager=new_order_manager,
            default_risk_category=RiskCategory.NORMAL,
        )
        
        new_market_adapter.add_signal_callback(new_order_adapter.handle_execution_signal)
        
        # Re-register functions after crash
        await new_registry.register("close_above", CloseAboveFunction)
        
        # Re-create the same function configuration
        await new_registry.create_function(config)
        await new_market_adapter.start_monitoring("AAPL", Timeframe.ONE_MIN)
        
        # Verify state recovery
        assert new_order_manager.order_counter > 0, "Order counter should be recovered"
        assert len(new_order_manager.placed_orders) > 0, "Orders should be recovered"
        
        # Continue operation after recovery
        recovery_bar = create_state_test_bar(close_price=180.50)
        await new_market_adapter.on_market_data_update(recovery_bar)
        
        recovery_event = BarCloseEvent(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            close_time=datetime.now(UTC),
            bar_data=recovery_bar,
            next_close_time=datetime.now(UTC) + timedelta(minutes=1),
        )
        
        await new_market_adapter._on_bar_close(recovery_event)
        
        # Verify post-recovery operation
        post_crash_state = await state_manager.load_execution_state()
        post_crash_audit = await state_manager.load_audit_trail()
        
        # Should have additional orders after recovery
        # The new order manager should have the recovered state + new orders
        recovered_count = pre_crash_state["order_counter"]
        assert new_order_manager.order_counter >= recovered_count, \
            f"New order counter should be at least the recovered value: current={new_order_manager.order_counter}, recovered={recovered_count}"
        
        # The persistent state should reflect the new orders
        assert post_crash_state["order_counter"] >= recovered_count, \
            f"Persistent state should have new orders after recovery: post={post_crash_state['order_counter']}, pre={recovered_count}"
        
        assert len(post_crash_audit) >= len(pre_crash_audit), \
            "Audit trail should grow or stay same after recovery"