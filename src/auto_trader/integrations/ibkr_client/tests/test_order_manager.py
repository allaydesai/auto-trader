# Test suite for OrderExecutionManager
import pytest
import asyncio
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch

from auto_trader.models import (
    OrderRequest, 
    OrderResult, 
    BracketOrder, 
    OrderModification,
    OrderType, 
    OrderSide, 
    OrderStatus,
    RiskCategory,
)
from auto_trader.risk_management import (
    OrderRiskValidator, 
    RiskValidationResult,
    PositionSizeResult,
    RiskCheck,
)
from auto_trader.integrations.ibkr_client import (
    IBKRClient,
    OrderExecutionManager, 
    OrderExecutionError,
    OrderNotFoundError,
)


@pytest.fixture
def mock_ibkr_client():
    """Mock IBKR client."""
    mock = Mock(spec=IBKRClient)
    mock._ib = Mock()
    mock._ib.qualifyContractsAsync = AsyncMock()
    mock._ib.placeOrder = Mock()
    mock._ib.cancelOrder = Mock()
    mock._ib.client.getReqId = Mock(side_effect=lambda: 12345)
    return mock


@pytest.fixture
def mock_risk_validator():
    """Mock risk validator that passes validation."""
    mock = Mock(spec=OrderRiskValidator)
    
    # Default successful validation
    successful_validation = RiskValidationResult(
        is_valid=True,
        position_size_result=PositionSizeResult(
            position_size=100,
            dollar_risk=Decimal("2000.00"),
            validation_status=True,
            portfolio_risk_percentage=Decimal("2.0"),
            risk_category="normal",
            account_value=Decimal("100000.00"),
        ),
        portfolio_risk_check=RiskCheck(
            passed=True,
            reason=None,
            current_risk=Decimal("3.0"),
            new_trade_risk=Decimal("2.0"),
            total_risk=Decimal("5.0"),
            limit=Decimal("10.0"),
        ),
        errors=[],
        warnings=[],
    )
    
    mock.validate_order_request = AsyncMock(return_value=successful_validation)
    mock.create_order_rejection_result = Mock()
    
    return mock


@pytest.fixture
def sample_order_request():
    """Sample order request for testing."""
    return OrderRequest(
        trade_plan_id="AAPL_20250827_001",
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.MARKET,
        entry_price=Decimal("180.50"),
        stop_loss_price=Decimal("178.00"),
        take_profit_price=Decimal("185.00"),
        risk_category=RiskCategory.NORMAL,
        calculated_position_size=100,
    )


@pytest.fixture
def order_manager(mock_ibkr_client, mock_risk_validator, tmp_path):
    """Order execution manager with mocked dependencies."""
    return OrderExecutionManager(
        ibkr_client=mock_ibkr_client,
        risk_validator=mock_risk_validator,
        simulation_mode=True,  # Use simulation by default for testing
        state_dir=tmp_path / "test_orders",  # Use temporary directory for testing
    )


class TestOrderExecutionManager:
    """Test cases for OrderExecutionManager."""

    def test_initialization(self, mock_ibkr_client, mock_risk_validator, tmp_path):
        """Test manager initialization."""
        manager = OrderExecutionManager(
            ibkr_client=mock_ibkr_client,
            risk_validator=mock_risk_validator,
            simulation_mode=True,
            state_dir=tmp_path / "test_orders",
        )
        
        assert manager.ibkr_client == mock_ibkr_client
        assert manager.risk_validator == mock_risk_validator
        assert manager.simulation_mode is True
        assert len(manager._active_orders) == 0
        assert len(manager._event_handlers) == 0

    @pytest.mark.asyncio
    async def test_place_market_order_simulation_success(
        self, order_manager, sample_order_request
    ):
        """Test successful market order placement in simulation mode."""
        result = await order_manager.place_market_order(sample_order_request)
        
        assert result.success is True
        assert result.order_id.startswith("SIM_")
        assert result.trade_plan_id == sample_order_request.trade_plan_id
        assert result.symbol == sample_order_request.symbol
        assert result.side == sample_order_request.side
        assert result.quantity == sample_order_request.calculated_position_size
        assert result.order_type == OrderType.MARKET
        
        # Check order is tracked
        assert result.order_id in order_manager._active_orders
        order = order_manager._active_orders[result.order_id]
        assert order.status == OrderStatus.FILLED  # Market orders fill immediately in simulation

    @pytest.mark.asyncio
    async def test_place_market_order_risk_validation_failure(
        self, mock_ibkr_client, mock_risk_validator, sample_order_request, tmp_path
    ):
        """Test market order placement with risk validation failure."""
        # Configure risk validator to fail
        failed_validation = RiskValidationResult(
            is_valid=False,
            position_size_result=None,
            portfolio_risk_check=RiskCheck(
                passed=False,
                reason="Portfolio risk exceeded",
                current_risk=Decimal("8.0"),
                new_trade_risk=Decimal("3.0"),
                total_risk=Decimal("11.0"),
                limit=Decimal("10.0"),
            ),
            errors=["Portfolio risk limit exceeded"],
            warnings=[],
        )
        
        mock_risk_validator.validate_order_request = AsyncMock(return_value=failed_validation)
        mock_risk_validator.create_order_rejection_result.return_value = OrderResult(
            success=False,
            trade_plan_id=sample_order_request.trade_plan_id,
            order_status=OrderStatus.REJECTED,
            error_message="Risk validation failed",
            symbol=sample_order_request.symbol,
            side=sample_order_request.side,
            quantity=0,
            order_type=OrderType.MARKET,
        )
        
        manager = OrderExecutionManager(
            ibkr_client=mock_ibkr_client,
            risk_validator=mock_risk_validator,
            simulation_mode=True,
            state_dir=tmp_path / "test_orders_2",
        )
        
        result = await manager.place_market_order(sample_order_request)
        
        assert result.success is False
        assert result.order_status == OrderStatus.REJECTED
        assert "Risk validation failed" in result.error_message

    @pytest.mark.asyncio
    async def test_place_bracket_order_simulation(
        self, order_manager, sample_order_request
    ):
        """Test bracket order placement in simulation mode."""
        stop_loss_price = Decimal("178.00")
        take_profit_price = Decimal("185.00")
        
        result = await order_manager.place_bracket_order(
            sample_order_request, stop_loss_price, take_profit_price
        )
        
        assert result.success is True
        assert result.order_id.startswith("SIM_")
        
        # Check all bracket orders are tracked
        parent_order = order_manager._active_orders[result.order_id]
        assert parent_order.parent_order_id.startswith("BRACKET_")
        
        # Find child orders
        child_orders = [
            order for order in order_manager._active_orders.values()
            if order.parent_order_id == parent_order.parent_order_id and order.order_id != result.order_id
        ]
        
        assert len(child_orders) == 2  # Stop loss + take profit
        
        # Verify child order types
        stop_orders = [o for o in child_orders if o.order_type == OrderType.STOP]
        limit_orders = [o for o in child_orders if o.order_type == OrderType.LIMIT]
        
        assert len(stop_orders) == 1
        assert len(limit_orders) == 1
        assert stop_orders[0].stop_price == stop_loss_price
        assert limit_orders[0].price == take_profit_price

    @pytest.mark.asyncio
    async def test_modify_order_simulation(self, order_manager, sample_order_request):
        """Test order modification in simulation mode."""
        # First place an order
        result = await order_manager.place_market_order(sample_order_request)
        assert result.success is True
        
        # Create modification
        modification = OrderModification(
            order_id=result.order_id,
            new_price=Decimal("181.00"),
            new_quantity=150,
            reason="Market conditions changed"
        )
        
        # Modify the order
        mod_result = await order_manager.modify_order(modification)
        
        assert mod_result.success is True
        assert mod_result.order_id == result.order_id
        
        # Check order was updated
        order = order_manager._active_orders[result.order_id]
        assert order.price == Decimal("181.00")
        assert order.quantity == 150

    @pytest.mark.asyncio
    async def test_modify_nonexistent_order(self, order_manager):
        """Test modifying a nonexistent order."""
        modification = OrderModification(
            order_id="NONEXISTENT",
            new_price=Decimal("181.00"),
            reason="Test"
        )
        
        result = await order_manager.modify_order(modification)
        
        assert result.success is False
        assert "not found" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_cancel_order_simulation(self, order_manager, sample_order_request):
        """Test order cancellation in simulation mode."""
        # First place an order
        result = await order_manager.place_market_order(sample_order_request)
        assert result.success is True
        assert result.order_id in order_manager._active_orders
        
        # Cancel the order
        cancel_result = await order_manager.cancel_order(result.order_id)
        
        assert cancel_result.success is True
        assert cancel_result.order_status == OrderStatus.CANCELLED
        
        # Check order was removed from active orders
        assert result.order_id not in order_manager._active_orders

    @pytest.mark.asyncio
    async def test_cancel_nonexistent_order(self, order_manager):
        """Test canceling a nonexistent order."""
        result = await order_manager.cancel_order("NONEXISTENT")
        
        assert result.success is False
        assert "not found" in result.error_message.lower()

    @pytest.mark.asyncio
    async def test_get_order_status(self, order_manager, sample_order_request):
        """Test getting order status."""
        # Place an order
        result = await order_manager.place_market_order(sample_order_request)
        assert result.success is True
        
        # Get order status
        order = await order_manager.get_order_status(result.order_id)
        
        assert order is not None
        assert order.order_id == result.order_id
        assert order.trade_plan_id == sample_order_request.trade_plan_id
        
        # Test nonexistent order
        nonexistent = await order_manager.get_order_status("NONEXISTENT")
        assert nonexistent is None

    @pytest.mark.asyncio
    async def test_get_active_orders(self, order_manager, sample_order_request):
        """Test getting all active orders."""
        # Initially no orders
        orders = await order_manager.get_active_orders()
        assert len(orders) == 0
        
        # Place a couple orders
        result1 = await order_manager.place_market_order(sample_order_request)
        
        # Create second order request
        request2 = OrderRequest(
            trade_plan_id="TSLA_20250827_001",
            symbol="TSLA",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            entry_price=Decimal("250.00"),
            stop_loss_price=Decimal("255.00"),
            take_profit_price=Decimal("240.00"),
            risk_category=RiskCategory.SMALL,
            calculated_position_size=50,
        )
        result2 = await order_manager.place_market_order(request2)
        
        # Get all active orders
        orders = await order_manager.get_active_orders()
        assert len(orders) == 2
        
        order_ids = [o.order_id for o in orders]
        assert result1.order_id in order_ids
        assert result2.order_id in order_ids

    def test_event_handler_management(self, order_manager):
        """Test adding and removing event handlers."""
        def dummy_handler(event):
            pass
        
        # Add handler
        order_manager.add_event_handler(dummy_handler)
        assert dummy_handler in order_manager._event_handlers
        
        # Remove handler
        order_manager.remove_event_handler(dummy_handler)
        assert dummy_handler not in order_manager._event_handlers
        
        # Remove nonexistent handler (should not error)
        order_manager.remove_event_handler(dummy_handler)

    def test_status_mapping(self, order_manager):
        """Test IBKR status mapping."""
        # Test various IBKR status mappings
        assert order_manager._map_ibkr_status("PendingSubmit") == OrderStatus.PENDING
        assert order_manager._map_ibkr_status("Submitted") == OrderStatus.SUBMITTED
        assert order_manager._map_ibkr_status("Filled") == OrderStatus.FILLED
        assert order_manager._map_ibkr_status("Cancelled") == OrderStatus.CANCELLED
        assert order_manager._map_ibkr_status("Inactive") == OrderStatus.REJECTED
        assert order_manager._map_ibkr_status("UnknownStatus") == OrderStatus.PENDING  # Default

    @pytest.mark.asyncio
    async def test_real_order_execution_fails_gracefully(
        self, mock_ibkr_client, mock_risk_validator, sample_order_request, tmp_path
    ):
        """Test that real order execution fails gracefully when IBKR client raises an exception."""
        # Mock IBKR client to raise an exception
        mock_ibkr_client._ib.placeOrder.side_effect = Exception("IBKR connection failed")
        
        # Create manager with simulation_mode=False
        manager = OrderExecutionManager(
            ibkr_client=mock_ibkr_client,
            risk_validator=mock_risk_validator,
            simulation_mode=False,
            state_dir=tmp_path / "test_orders_3",
        )
        
        # Real order execution should return failed OrderResult when IBKR client fails
        result = await manager.place_market_order(sample_order_request)
        
        assert result.success is False
        assert result.order_status == OrderStatus.REJECTED
        assert "IBKR execution failed" in result.error_message

    def test_create_order_from_request(self, order_manager, sample_order_request):
        """Test creating Order object from OrderRequest."""
        order = order_manager._create_order_from_request(sample_order_request, OrderType.MARKET)
        
        assert order.order_id is None  # Not set until placement
        assert order.trade_plan_id == sample_order_request.trade_plan_id
        assert order.symbol == sample_order_request.symbol
        assert order.side == sample_order_request.side
        assert order.order_type == OrderType.MARKET
        assert order.quantity == sample_order_request.calculated_position_size

    def test_create_child_order(self, order_manager, sample_order_request):
        """Test creating child order for bracket orders."""
        parent_order = order_manager._create_order_from_request(sample_order_request, OrderType.MARKET)
        parent_order.parent_order_id = "BRACKET_TEST"
        
        child_order = order_manager._create_child_order(
            parent_order, OrderType.STOP, Decimal("178.00"), "STOP_LOSS"
        )
        
        assert child_order.parent_order_id == "BRACKET_TEST"
        assert child_order.side == OrderSide.SELL  # Opposite of parent BUY
        assert child_order.order_type == OrderType.STOP
        assert child_order.stop_price == Decimal("178.00")
        assert child_order.quantity == parent_order.quantity
        assert child_order.transmit is False

    @pytest.mark.asyncio
    async def test_state_management_lifecycle(self, order_manager, sample_order_request):
        """Test complete state management lifecycle."""
        # Start state management
        await order_manager.start_state_management()
        
        # Place an order (should trigger state save)
        result = await order_manager.place_market_order(sample_order_request)
        assert result.success is True
        
        # Wait a moment for async state save to complete
        await asyncio.sleep(0.1)
        
        # Check that state file exists
        assert order_manager.state_manager.state_file.exists()
        
        # Create a new manager instance and recover state
        new_manager = OrderExecutionManager(
            ibkr_client=order_manager.ibkr_client,
            risk_validator=order_manager.risk_validator,
            simulation_mode=True,
            state_dir=order_manager.state_manager.state_dir,
        )
        
        # Load state in new manager
        await new_manager._recover_orders()
        
        # In simulation mode, market orders fill immediately (FILLED status)
        # so they won't be recovered as "active" orders. Let's verify the order
        # was properly saved and loaded by checking the raw state data
        loaded_orders = await new_manager.state_manager.load_state()
        assert len(loaded_orders) == 1
        assert result.order_id in loaded_orders
        
        # Verify order details were preserved
        recovered_order = loaded_orders[result.order_id]
        assert recovered_order.order_id == result.order_id
        assert recovered_order.symbol == sample_order_request.symbol
        assert recovered_order.status == OrderStatus.FILLED  # Market orders fill immediately in simulation
        
        # Stop state management
        await order_manager.stop_state_management()

    @pytest.mark.asyncio
    async def test_state_persistence_on_order_operations(self, order_manager, sample_order_request):
        """Test that state is saved after each order operation."""
        # Start state management
        await order_manager.start_state_management()
        
        # Place order - should save state
        result = await order_manager.place_market_order(sample_order_request)
        assert result.success is True
        
        # Wait for async state save
        await asyncio.sleep(0.1)
        
        # Verify state was saved
        loaded_orders = await order_manager.state_manager.load_state()
        assert len(loaded_orders) == 1
        assert result.order_id in loaded_orders
        
        # Cancel order - should update state
        cancel_result = await order_manager.cancel_order(result.order_id)
        assert cancel_result.success is True
        
        # Wait for async state save
        await asyncio.sleep(0.1)
        
        # Verify order was removed from state
        loaded_orders = await order_manager.state_manager.load_state()
        assert len(loaded_orders) == 0  # Order should be removed after cancellation
        
        # Stop state management
        await order_manager.stop_state_management()

    @pytest.mark.asyncio
    async def test_bracket_order_state_persistence(self, order_manager, sample_order_request):
        """Test state persistence for bracket orders."""
        # Start state management
        await order_manager.start_state_management()
        
        # Place bracket order
        result = await order_manager.place_bracket_order(
            sample_order_request,
            stop_loss_price=Decimal("178.00"),
            take_profit_price=Decimal("185.00"),
        )
        assert result.success is True
        
        # Wait for async state save
        await asyncio.sleep(0.1)
        
        # Verify all bracket orders were saved to state
        loaded_orders = await order_manager.state_manager.load_state()
        assert len(loaded_orders) == 3  # Parent + stop loss + take profit
        
        # Find parent order
        parent_orders = [o for o in loaded_orders.values() if o.order_id == result.order_id]
        assert len(parent_orders) == 1
        parent_order = parent_orders[0]
        
        # Find child orders
        child_orders = [
            o for o in loaded_orders.values()
            if o.parent_order_id == parent_order.parent_order_id and o.order_id != result.order_id
        ]
        assert len(child_orders) == 2
        
        # Verify child order types
        order_types = {o.order_type for o in child_orders}
        assert OrderType.STOP in order_types
        assert OrderType.LIMIT in order_types
        
        # Stop state management
        await order_manager.stop_state_management()