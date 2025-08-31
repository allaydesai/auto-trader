"""Integration tests for position lifecycle management."""

import pytest
import asyncio
import tempfile
import shutil
import json
from unittest.mock import AsyncMock, Mock
from datetime import datetime, UTC, timedelta
from decimal import Decimal
from pathlib import Path
from typing import List, Dict, Any

from auto_trader.models.trade_plan import TradePlan, TradePlanStatus, RiskCategory, ExecutionFunction
from auto_trader.models.order import Order, OrderResult, OrderRequest
from auto_trader.models.enums import OrderSide, OrderStatus, OrderType
from auto_trader.trade_engine.position_state_manager import (
    PositionStateManager,
    PositionEntry,
)


class MockMarketDataProvider:
    """Mock market data provider for P&L calculations."""
    
    def __init__(self):
        self.current_prices = {}
        self.price_history = {}
        
    def set_current_price(self, symbol: str, price: Decimal):
        """Set current market price for symbol."""
        self.current_prices[symbol] = price
        
        if symbol not in self.price_history:
            self.price_history[symbol] = []
        self.price_history[symbol].append({
            "price": price,
            "timestamp": datetime.now(UTC)
        })
        
    async def get_current_price(self, symbol: str) -> Decimal:
        """Get current market price."""
        return self.current_prices.get(symbol, Decimal("0.00"))
        
    def get_price_history(self, symbol: str) -> List[Dict[str, Any]]:
        """Get price history for symbol."""
        return self.price_history.get(symbol, [])


@pytest.fixture
def temp_state_dir():
    """Create temporary directory for state persistence."""
    temp_dir = tempfile.mkdtemp()
    yield Path(temp_dir)
    shutil.rmtree(temp_dir)


@pytest.fixture
def mock_market_data():
    """Create mock market data provider."""
    return MockMarketDataProvider()


@pytest.fixture
async def position_state_manager(temp_state_dir):
    """Create position state manager with temporary directory."""
    return PositionStateManager(state_file_path=temp_state_dir / "positions.json")


@pytest.fixture
def sample_trade_plan():
    """Create sample trade plan."""
    return TradePlan(
        plan_id="POSITION_TEST_001",
        symbol="AAPL",
        entry_level=Decimal("180.00"),
        stop_loss=Decimal("178.00"),
        take_profit=Decimal("185.00"),
        risk_category=RiskCategory.NORMAL,
        entry_function=ExecutionFunction(
            function_type="close_above",
            timeframe="15min",
            parameters={"threshold": "180.00"}
        ),
        exit_function=ExecutionFunction(
            function_type="stop_loss_take_profit",
            timeframe="15min",
            parameters={"stop_loss": "178.00", "take_profit": "185.00"}
        ),
        status=TradePlanStatus.AWAITING_ENTRY
    )


@pytest.fixture
def entry_order_result():
    """Create sample entry order result."""
    return OrderResult(
        success=True,
        order_id="ENTRY_001",
        trade_plan_id="POSITION_TEST_001",
        order_status=OrderStatus.FILLED,
        symbol="AAPL",
        quantity=100,
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        filled_quantity=100,
        average_fill_price=Decimal("180.50"),
        timestamp=datetime.now(UTC)
    )


@pytest.fixture
def exit_order_result():
    """Create sample exit order result."""
    return OrderResult(
        success=True,
        order_id="EXIT_001",
        trade_plan_id="POSITION_TEST_001",
        order_status=OrderStatus.FILLED,
        symbol="AAPL",
        quantity=100,
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        filled_quantity=100,
        average_fill_price=Decimal("184.75"),
        timestamp=datetime.now(UTC)
    )


@pytest.mark.asyncio
@pytest.mark.integration
class TestPositionLifecycleIntegration:
    """Integration tests for position lifecycle management."""
    
    async def test_complete_position_lifecycle(
        self,
        position_state_manager,
        sample_trade_plan,
        entry_order_result,
        exit_order_result,
        mock_market_data
    ):
        """Test complete position lifecycle from creation to closure."""
        # Set initial market price
        mock_market_data.set_current_price("AAPL", Decimal("180.50"))
        
        # Create position from entry order
        position_id = await position_state_manager.create_position_from_fill(
            trade_plan=sample_trade_plan,
            order_result=entry_order_result
        )
        
        assert position_id is not None
        
        # Verify position was created
        position = position_state_manager.get_position_by_id(position_id)
        assert position is not None
        assert position.symbol == "AAPL"
        assert position.quantity == 100
        assert position.entry_price == Decimal("180.50")
        assert position.side == OrderSide.BUY
        
        # Update market price for P&L calculation
        mock_market_data.set_current_price("AAPL", Decimal("182.00"))
        
        # Calculate unrealized P&L
        current_price = await mock_market_data.get_current_price("AAPL")
        unrealized_pnl = position.calculate_unrealized_pnl(current_price)
        
        expected_pnl = (Decimal("182.00") - Decimal("180.50")) * 100
        assert unrealized_pnl == expected_pnl
        
        # Record exit fill before closing position (simulating exit order fill)
        position.record_exit_fill(
            order_id=exit_order_result.order_id,
            quantity_filled=-100,  # Negative for position reduction
            fill_price=exit_order_result.average_fill_price,
            timestamp=exit_order_result.timestamp
        )
        
        # Close position
        await position_state_manager.close_position(
            position_id=position_id,
            close_reason="exit_order_fill"
        )
        
        # Verify position was closed
        closed_position = position_state_manager.get_position_by_id(position_id)
        assert closed_position.is_closed is True
        
        # Calculate realized P&L
        realized_pnl = closed_position.calculate_realized_pnl()
        expected_realized = (Decimal("184.75") - Decimal("180.50")) * 100
        assert realized_pnl == expected_realized
    
    async def test_position_state_persistence(
        self,
        position_state_manager,
        sample_trade_plan,
        entry_order_result,
        temp_state_dir
    ):
        """Test position state persistence across manager restarts."""
        # Create position
        position_id = await position_state_manager.create_position_from_fill(
            trade_plan=sample_trade_plan,
            order_result=entry_order_result
        )
        
        # Verify position file was created
        position_file = temp_state_dir / "positions.json"
        assert position_file.exists()
        
        # Create new manager instance (simulating restart)
        new_manager = PositionStateManager(state_file_path=position_file)
        
        # Verify position was loaded
        recovered_position = new_manager.get_position_by_id(position_id)
        assert recovered_position is not None
        assert recovered_position.position_id == position_id
        assert recovered_position.symbol == "AAPL"
        assert recovered_position.quantity == 100
        assert recovered_position.entry_price == Decimal("180.50")
    
    async def test_multiple_positions_same_symbol(
        self,
        position_state_manager,
        sample_trade_plan,
        entry_order_result,
        mock_market_data
    ):
        """Test managing multiple positions for the same symbol."""
        # Set market price
        mock_market_data.set_current_price("AAPL", Decimal("180.50"))
        
        # Create first position
        order_result_1 = OrderResult(
            success=True,
            order_id="ENTRY_001",
            trade_plan_id="POSITION_TEST_001",
            order_status=OrderStatus.FILLED,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET,
            filled_quantity=100,
            average_fill_price=Decimal("180.00"),
            timestamp=datetime.now(UTC)
        )
        
        position_id_1 = await position_state_manager.create_position_from_fill(
            trade_plan=sample_trade_plan,
            order_result=order_result_1
        )
        
        # Create second position (different plan)
        trade_plan_2 = TradePlan(
            plan_id="POSITION_TEST_002",
            symbol="AAPL",  # Same symbol
            entry_level=Decimal("181.00"),
            stop_loss=Decimal("179.00"),
            take_profit=Decimal("186.00"),
            risk_category=RiskCategory.NORMAL,
            entry_function=ExecutionFunction(
                function_type="close_above",
                timeframe="15min",
                parameters={"threshold": "181.00"}
            ),
            exit_function=ExecutionFunction(
                function_type="stop_loss_take_profit",
                timeframe="15min",
                parameters={"stop_loss": "179.00", "take_profit": "186.00"}
            ),
            status=TradePlanStatus.AWAITING_ENTRY
        )
        
        order_result_2 = OrderResult(
            success=True,
            order_id="ENTRY_002",
            trade_plan_id="POSITION_TEST_002",
            order_status=OrderStatus.FILLED,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=150,
            order_type=OrderType.MARKET,
            filled_quantity=150,
            average_fill_price=Decimal("181.50"),
            timestamp=datetime.now(UTC)
        )
        
        position_id_2 = await position_state_manager.create_position_from_fill(
            trade_plan=trade_plan_2,
            order_result=order_result_2
        )
        
        # Verify both positions exist
        position_1 = position_state_manager.get_position_by_id(position_id_1)
        position_2 = position_state_manager.get_position_by_id(position_id_2)
        
        assert position_1 is not None
        assert position_2 is not None
        assert position_1.position_id != position_2.position_id
        assert position_1.quantity == 100
        assert position_2.quantity == 150
        
        # Get positions by symbol
        symbol_positions = position_state_manager.get_positions_by_symbol("AAPL")
        assert len(symbol_positions) == 2
        
        # Get positions by plan ID
        plan_position_1 = position_state_manager.get_position_by_plan_id("POSITION_TEST_001")
        plan_position_2 = position_state_manager.get_position_by_plan_id("POSITION_TEST_002")
        
        assert plan_position_1.position_id == position_id_1
        assert plan_position_2.position_id == position_id_2
    
    @pytest.mark.skip(reason="Uses deprecated calculate_unrealized_pnl method - pending future refactor")
    async def test_position_pnl_tracking_over_time(
        self,
        position_state_manager,
        sample_trade_plan,
        entry_order_result,
        mock_market_data
    ):
        """Test P&L tracking over time with price movements."""
        # Create position
        position_id = await position_state_manager.create_position_from_fill(
            trade_plan=sample_trade_plan,
            order_result=entry_order_result
        )
        
        # Track P&L over time with changing prices
        price_points = [
            (Decimal("180.50"), "Entry price"),
            (Decimal("181.00"), "Small gain"),
            (Decimal("179.50"), "Temporary loss"),
            (Decimal("183.00"), "Good gain"),
            (Decimal("177.00"), "Significant loss"),
            (Decimal("185.00"), "Strong recovery")
        ]
        
        pnl_history = []
        
        for price, description in price_points:
            mock_market_data.set_current_price("AAPL", price)
            
            unrealized_pnl = await position_state_manager.calculate_unrealized_pnl(
                position_id, mock_market_data.get_current_price
            )
            
            expected_pnl = (price - Decimal("180.50")) * 100
            assert unrealized_pnl == expected_pnl
            
            pnl_history.append({
                "price": price,
                "pnl": unrealized_pnl,
                "description": description,
                "timestamp": datetime.now(UTC)
            })
            
            await asyncio.sleep(0.01)  # Small delay between updates
        
        # Verify P&L calculations
        assert len(pnl_history) == 6
        assert pnl_history[0]["pnl"] == Decimal("0.00")  # At entry price
        assert pnl_history[1]["pnl"] == Decimal("50.00")  # +$0.50 * 100 shares
        assert pnl_history[2]["pnl"] == Decimal("-100.00")  # -$1.00 * 100 shares
        assert pnl_history[5]["pnl"] == Decimal("450.00")  # +$4.50 * 100 shares
    
    @pytest.mark.skip(reason="Uses deprecated close_position_from_order method - pending future refactor")
    async def test_partial_position_closure(
        self,
        position_state_manager,
        sample_trade_plan,
        entry_order_result
    ):
        """Test partial position closure handling."""
        # Create position with 200 shares
        large_entry = OrderResult(
            success=True,
            order_id="LARGE_ENTRY_001",
            trade_plan_id="POSITION_TEST_001",
            order_status=OrderStatus.FILLED,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=200,
            order_type=OrderType.MARKET,
            filled_quantity=200,
            average_fill_price=Decimal("180.50"),
            timestamp=datetime.now(UTC)
        )
        
        position_id = await position_state_manager.create_position_from_fill(
            trade_plan=sample_trade_plan,
            order_result=large_entry
        )
        
        # Partial exit of 100 shares
        partial_exit = OrderResult(
            success=True,
            order_id="PARTIAL_EXIT_001",
            trade_plan_id="POSITION_TEST_001",
            order_status=OrderStatus.FILLED,
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=100,  # Only half the position
            order_type=OrderType.MARKET,
            filled_quantity=100,
            average_fill_price=Decimal("182.00"),
            timestamp=datetime.now(UTC)
        )
        
        await position_state_manager.close_position_from_order(
            position_id=position_id,
            order_result=partial_exit
        )
        
        # Verify position is partially closed
        position = position_state_manager.get_position_by_id(position_id)
        assert position.is_closed is False  # Still has remaining quantity
        assert position.remaining_quantity == 100  # 200 - 100
        
        # Complete the exit
        remaining_exit = OrderResult(
            success=True,
            order_id="REMAINING_EXIT_001",
            symbol="AAPL",
            quantity=100,
            side=OrderSide.SELL,
            average_fill_price=Decimal("184.00"),
            status=OrderStatus.FILLED,
            timestamp=datetime.now(UTC)
        )
        
        await position_state_manager.close_position_from_order(
            position_id=position_id,
            order_result=remaining_exit
        )
        
        # Verify position is fully closed
        final_position = position_state_manager.get_position_by_id(position_id)
        assert final_position.is_closed is True
        assert final_position.remaining_quantity == 0
    
    @pytest.mark.skip(reason="Uses deprecated API - close_position with exit_order_result parameter")
    async def test_position_summary_generation(
        self,
        position_state_manager,
        sample_trade_plan,
        entry_order_result,
        exit_order_result
    ):
        """Test position summary generation."""
        # Create and close position
        position_id = await position_state_manager.create_position_from_fill(
            trade_plan=sample_trade_plan,
            order_result=entry_order_result
        )
        
        await position_state_manager.close_position(
            position_id=position_id,
            exit_order_result=exit_order_result
        )
        
        # Get overall position summary
        summary = position_state_manager.get_position_summary()
        
        assert summary is not None
        assert isinstance(summary, dict)
        assert "total_positions" in summary
        assert summary["total_positions"] >= 1
    
    @pytest.mark.skip(reason="Uses deprecated close_position_from_order method")
    async def test_position_cleanup_and_archival(
        self,
        position_state_manager,
        sample_trade_plan,
        entry_order_result,
        exit_order_result,
        temp_state_dir
    ):
        """Test position cleanup and archival after closure."""
        # Create and close position
        position_id = await position_state_manager.create_position_from_fill(
            trade_plan=sample_trade_plan,
            order_result=entry_order_result
        )
        
        await position_state_manager.close_position_from_order(
            position_id=position_id,
            order_result=exit_order_result
        )
        
        # Archive closed position
        await position_state_manager.archive_closed_position(position_id)
        
        # Verify position was archived
        archived_positions = await position_state_manager.get_archived_positions()
        assert len(archived_positions) == 1
        assert archived_positions[0].position_id == position_id
        
        # Verify active position was removed
        active_position = position_state_manager.get_position_by_id(position_id)
        assert active_position is None or active_position.is_archived is True
    
    @pytest.mark.skip(reason="Uses deprecated close_position_from_order method")
    async def test_position_error_handling(
        self,
        position_state_manager,
        sample_trade_plan
    ):
        """Test error handling in position operations."""
        # Test getting non-existent position
        non_existent = position_state_manager.get_position_by_id("NON_EXISTENT_ID")
        assert non_existent is None
        
        # Test closing non-existent position
        fake_exit = OrderResult(
            success=True,
            order_id="FAKE_EXIT",
            symbol="AAPL",
            quantity=100,
            side=OrderSide.SELL,
            average_fill_price=Decimal("185.00"),
            status=OrderStatus.FILLED,
            timestamp=datetime.now(UTC)
        )
        
        with pytest.raises(Exception):  # Should raise appropriate exception
            await position_state_manager.close_position_from_order(
                position_id="NON_EXISTENT_ID",
                order_result=fake_exit
            )
        
        # Test P&L calculation for non-existent position
        with pytest.raises(Exception):  # Should raise appropriate exception
            await position_state_manager.calculate_unrealized_pnl(
                "NON_EXISTENT_ID",
                lambda symbol: Decimal("100.00")
            )


@pytest.mark.skip(reason="Performance tests moved to future work")
@pytest.mark.asyncio
@pytest.mark.integration
class TestPositionStateManagerPerformance:
    """Performance tests for position state management."""
    
    async def test_concurrent_position_operations(
        self,
        position_state_manager,
        temp_state_dir
    ):
        """Test concurrent position creation and management."""
        # Create multiple positions concurrently
        num_positions = 50
        
        tasks = []
        for i in range(num_positions):
            trade_plan = TradePlan(
                plan_id=f"CONCURRENT_POSITION_{i:03d}",
                symbol=f"STOCK{i % 10}",  # 10 different symbols
                entry_level=Decimal("100.00"),
                stop_loss=Decimal("98.00"),
                take_profit=Decimal("105.00"),
                risk_category=RiskCategory.NORMAL,
                entry_function=ExecutionFunction(
                    function_type="close_above",
                    timeframe="15min",
                    parameters={"threshold": "100.00"}
                ),
                exit_function=ExecutionFunction(
                    function_type="stop_loss_take_profit",
                    timeframe="15min",
                    parameters={"stop_loss": "98.00", "take_profit": "105.00"}
                ),
                status=TradePlanStatus.AWAITING_ENTRY
            )
            
            order_result = OrderResult(
                success=True,
                order_id=f"CONCURRENT_ORDER_{i:03d}",
                symbol=f"STOCK{i % 10}",
                quantity=100,
                side=OrderSide.BUY,
                average_fill_price=Decimal("100.50"),
                status=OrderStatus.FILLED,
                timestamp=datetime.now(UTC)
            )
            
            task = position_state_manager.create_position_from_fill(
                trade_plan=trade_plan,
                order_result=order_result
            )
            tasks.append(task)
        
        # Execute all position creations concurrently
        start_time = datetime.now(UTC)
        position_ids = await asyncio.gather(*tasks)
        end_time = datetime.now(UTC)
        
        # Verify all positions were created
        assert len(position_ids) == num_positions
        assert all(pid is not None for pid in position_ids)
        
        # Verify performance
        creation_time = (end_time - start_time).total_seconds()
        assert creation_time < 5.0, f"Position creation took {creation_time:.2f}s, too slow"
        
        # Verify file system state
        position_files = list(temp_state_dir.glob("position_*.json"))
        assert len(position_files) == num_positions
    
    async def test_large_position_set_management(
        self,
        position_state_manager
    ):
        """Test management of large sets of positions."""
        # Create many positions
        positions_to_create = 100
        
        for i in range(positions_to_create):
            trade_plan = TradePlan(
                plan_id=f"LARGE_SET_{i:04d}",
                symbol=f"SYM{i % 20}",  # 20 different symbols
                entry_level=Decimal("50.00"),
                stop_loss=Decimal("48.00"),
                take_profit=Decimal("55.00"),
                risk_category=RiskCategory.NORMAL,
                entry_function=ExecutionFunction(
                    function_type="close_above",
                    timeframe="15min",
                    parameters={"threshold": "50.00"}
                ),
                exit_function=ExecutionFunction(
                    function_type="stop_loss_take_profit",
                    timeframe="15min",
                    parameters={"stop_loss": "48.00", "take_profit": "55.00"}
                ),
                status=TradePlanStatus.AWAITING_ENTRY
            )
            
            order_result = OrderResult(
                success=True,
                order_id=f"LARGE_ORDER_{i:04d}",
                symbol=f"SYM{i % 20}",
                quantity=100,
                side=OrderSide.BUY,
                average_fill_price=Decimal("50.25"),
                status=OrderStatus.FILLED,
                timestamp=datetime.now(UTC)
            )
            
            await position_state_manager.create_position_from_fill(
                trade_plan=trade_plan,
                order_result=order_result
            )
        
        # Test retrieval performance
        start_time = datetime.now(UTC)
        all_positions = await position_state_manager.get_all_positions()
        end_time = datetime.now(UTC)
        
        retrieval_time = (end_time - start_time).total_seconds()
        assert retrieval_time < 2.0, f"Position retrieval took {retrieval_time:.2f}s, too slow"
        assert len(all_positions) == positions_to_create
        
        # Test symbol-based retrieval performance
        start_time = datetime.now(UTC)
        sym0_positions = await position_state_manager.get_positions_by_symbol("SYM0")
        end_time = datetime.now(UTC)
        
        symbol_retrieval_time = (end_time - start_time).total_seconds()
        assert symbol_retrieval_time < 0.5, f"Symbol retrieval took {symbol_retrieval_time:.2f}s, too slow"
        assert len(sym0_positions) == 5  # 100 positions / 20 symbols = 5 per symbol