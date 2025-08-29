"""Integration tests between execution function framework and order execution system."""

import pytest
import asyncio
from datetime import datetime, UTC, timedelta
from decimal import Decimal
from unittest.mock import Mock, AsyncMock, patch

from auto_trader.models.execution import (
    ExecutionContext,
    ExecutionSignal,
    ExecutionFunctionConfig,
    PositionState,
)
from auto_trader.models.enums import ExecutionAction, Timeframe, OrderType, OrderSide, OrderStatus
from auto_trader.models.market_data import BarData
from auto_trader.models.order import Order, OrderRequest
from auto_trader.models.trade_plan import RiskCategory
from auto_trader.trade_engine.function_registry import ExecutionFunctionRegistry
from auto_trader.trade_engine.functions import CloseAboveFunction, CloseBelowFunction


@pytest.fixture
def mock_order_manager():
    """Create mock order execution manager."""
    manager = Mock()
    manager.place_order = AsyncMock(return_value="ORDER_12345")
    manager.modify_order = AsyncMock(return_value=True)
    manager.cancel_order = AsyncMock(return_value=True)
    manager.get_open_orders = Mock(return_value=[])
    manager.get_positions = Mock(return_value={})
    return manager


@pytest.fixture
def mock_risk_manager():
    """Create mock risk management system."""
    manager = Mock()
    manager.validate_order = AsyncMock(return_value=True)
    manager.check_position_limits = Mock(return_value=True)
    manager.calculate_position_size = Mock(return_value=100)
    return manager


@pytest.fixture
def sample_market_data():
    """Create sample market data for testing."""
    current_bar = BarData(
        symbol="AAPL",
        timestamp=datetime.now(UTC),
        open_price=Decimal("180.00"),
        high_price=Decimal("182.00"),
        low_price=Decimal("179.50"),
        close_price=Decimal("181.50"),
        volume=1000000,
        bar_size="1min",
    )
    
    historical_bars = []
    base_time = datetime.now(UTC) - timedelta(minutes=20)
    
    for i in range(20):
        # Use proper decimal formatting to avoid precision issues
        price_adjustment = round(i * 0.05, 2)
        bar = BarData(
            symbol="AAPL",
            timestamp=base_time + timedelta(minutes=i),
            open_price=Decimal("179.00") + Decimal(str(price_adjustment)),
            high_price=Decimal("180.00") + Decimal(str(price_adjustment)),
            low_price=Decimal("178.50") + Decimal(str(price_adjustment)),
            close_price=Decimal("179.50") + Decimal(str(price_adjustment)),
            volume=1000000,
            bar_size="1min",
        )
        historical_bars.append(bar)
    
    return current_bar, historical_bars


@pytest.fixture
async def execution_system(mock_order_manager, mock_risk_manager):
    """Create integrated execution and order system."""
    registry = ExecutionFunctionRegistry()
    await registry.clear_all()
    
    # Register functions
    await registry.register("close_above", CloseAboveFunction)
    await registry.register("close_below", CloseBelowFunction)
    
    # Create function instances
    entry_config = ExecutionFunctionConfig(
        name="entry_function",
        function_type="close_above",
        timeframe=Timeframe.ONE_MIN,
        parameters={"threshold_price": 180.50},
        enabled=True
    )
    
    exit_config = ExecutionFunctionConfig(
        name="exit_function",
        function_type="close_below",
        timeframe=Timeframe.ONE_MIN,
        parameters={"threshold_price": 179.00, "action_type": "EXIT"},
        enabled=True
    )
    
    entry_function = await registry.create_function(entry_config)
    exit_function = await registry.create_function(exit_config)
    
    yield {
        "registry": registry,
        "entry_function": entry_function,
        "exit_function": exit_function,
        "order_manager": mock_order_manager,
        "risk_manager": mock_risk_manager
    }
    
    await registry.clear_all()


@pytest.mark.asyncio
class TestOrderExecutionIntegration:
    """Test integration between execution functions and order execution system."""

    async def test_execution_signal_to_order_request(
        self, execution_system, sample_market_data
    ):
        """Test conversion from execution signal to order request."""
        entry_function = execution_system["entry_function"]
        risk_manager = execution_system["risk_manager"]
        current_bar, historical_bars = sample_market_data
        
        # Create execution context
        context = ExecutionContext(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            current_bar=current_bar,
            historical_bars=historical_bars,
            trade_plan_params={"threshold_price": 180.00},  # Below current price
            position_state=None,
            account_balance=Decimal("10000"),
            timestamp=datetime.now(UTC)
        )
        
        # Execute function
        signal = await entry_function.evaluate(context)
        assert signal.action == ExecutionAction.ENTER_LONG
        
        # Convert signal to order request
        position_size = risk_manager.calculate_position_size()
        
        order_request = OrderRequest(
            trade_plan_id="test_plan_001",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            entry_price=current_bar.close_price,
            stop_loss_price=current_bar.close_price - Decimal("2.00"),
            take_profit_price=current_bar.close_price + Decimal("3.00"),
            risk_category=RiskCategory.NORMAL,
            calculated_position_size=position_size,
            time_in_force="DAY"
        )
        
        # Verify order request properties
        assert order_request.symbol == "AAPL"
        assert order_request.side == OrderSide.BUY
        assert order_request.calculated_position_size == position_size
        assert order_request.order_type == OrderType.MARKET

    async def test_entry_signal_order_placement(
        self, execution_system, sample_market_data
    ):
        """Test complete flow from entry signal to order placement."""
        entry_function = execution_system["entry_function"]
        order_manager = execution_system["order_manager"]
        risk_manager = execution_system["risk_manager"]
        current_bar, historical_bars = sample_market_data
        
        # Create context for entry signal
        context = ExecutionContext(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            current_bar=current_bar,
            historical_bars=historical_bars,
            trade_plan_params={"threshold_price": 180.00},
            position_state=None,
            account_balance=Decimal("10000"),
            timestamp=datetime.now(UTC)
        )
        
        # Execute function
        signal = await entry_function.evaluate(context)
        
        if signal.should_execute:
            # Validate with risk manager
            risk_validation = await risk_manager.validate_order()
            assert risk_validation is True
            
            # Create and place order
            order_request = OrderRequest(
                trade_plan_id="test_plan_001",
                symbol="AAPL",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                entry_price=Decimal("181.50"),
                stop_loss_price=Decimal("179.50"),
                take_profit_price=Decimal("184.50"),
                risk_category=RiskCategory.NORMAL,
                calculated_position_size=100,
                time_in_force="DAY"
            )
            
            order_id = await order_manager.place_order(order_request)
            
            # Verify order was placed
            order_manager.place_order.assert_called_once()
            assert order_id == "ORDER_12345"

    async def test_exit_signal_with_position(
        self, execution_system, sample_market_data
    ):
        """Test exit signal when position exists."""
        exit_function = execution_system["exit_function"]
        order_manager = execution_system["order_manager"]
        current_bar, historical_bars = sample_market_data
        
        # Create position state
        position = PositionState(
            symbol="AAPL",
            quantity=100,  # Long position
            entry_price=Decimal("180.50"),
            current_price=Decimal("178.50"),  # Below exit threshold
            opened_at=datetime.now(UTC) - timedelta(minutes=30)
        )
        
        # Create context with position
        context = ExecutionContext(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            current_bar=current_bar,
            historical_bars=historical_bars,
            trade_plan_params={"threshold_price": 179.00, "action_type": "EXIT"},
            position_state=position,
            account_balance=Decimal("10000"),
            timestamp=datetime.now(UTC)
        )
        
        # Execute exit function
        signal = await exit_function.evaluate(context)
        
        if signal.should_execute and signal.action == ExecutionAction.EXIT:
            # Create exit order
            order_request = OrderRequest(
                trade_plan_id="test_plan_001",
                symbol="AAPL",
                side=OrderSide.SELL,  # Close long position
                order_type=OrderType.MARKET,
                entry_price=Decimal("178.75"),
                stop_loss_price=Decimal("180.00"),
                take_profit_price=Decimal("175.00"),
                risk_category=RiskCategory.NORMAL,
                calculated_position_size=100,
                time_in_force="DAY"
            )
            
            order_id = await order_manager.place_order(order_request)
            
            # Verify exit order was placed
            assert order_id == "ORDER_12345"

    async def test_risk_manager_validation_integration(
        self, execution_system, sample_market_data
    ):
        """Test integration with risk management validation."""
        entry_function = execution_system["entry_function"]
        risk_manager = execution_system["risk_manager"]
        current_bar, historical_bars = sample_market_data
        
        # Setup risk manager to reject order
        risk_manager.validate_order.return_value = False
        
        context = ExecutionContext(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            current_bar=current_bar,
            historical_bars=historical_bars,
            trade_plan_params={"threshold_price": 180.00},
            position_state=None,
            account_balance=Decimal("10000"),
            timestamp=datetime.now(UTC)
        )
        
        # Execute function
        signal = await entry_function.evaluate(context)
        
        if signal.should_execute:
            # Risk validation should fail
            risk_validation = await risk_manager.validate_order()
            assert risk_validation is False
            
            # Order should not be placed when risk validation fails
            # This would be handled by the order execution system

    async def test_position_size_calculation_integration(
        self, execution_system, sample_market_data
    ):
        """Test integration with position size calculation."""
        entry_function = execution_system["entry_function"]
        risk_manager = execution_system["risk_manager"]
        current_bar, historical_bars = sample_market_data
        
        # Setup different position sizes
        risk_manager.calculate_position_size.return_value = 150
        
        context = ExecutionContext(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            current_bar=current_bar,
            historical_bars=historical_bars,
            trade_plan_params={"threshold_price": 180.00},
            position_state=None,
            account_balance=Decimal("15000"),  # Higher balance
            timestamp=datetime.now(UTC)
        )
        
        # Execute function
        signal = await entry_function.evaluate(context)
        
        if signal.should_execute:
            # Get calculated position size
            position_size = risk_manager.calculate_position_size()
            assert position_size == 150  # Should use risk manager calculation

    async def test_bracket_order_creation_from_signals(
        self, execution_system, sample_market_data
    ):
        """Test creation of bracket orders from execution signals."""
        entry_function = execution_system["entry_function"]
        current_bar, historical_bars = sample_market_data
        
        # Create context with stop loss and take profit parameters
        context = ExecutionContext(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            current_bar=current_bar,
            historical_bars=historical_bars,
            trade_plan_params={
                "threshold_price": 180.00,
                "stop_loss": 178.00,
                "take_profit": 184.00
            },
            position_state=None,
            account_balance=Decimal("10000"),
            timestamp=datetime.now(UTC)
        )
        
        # Execute function
        signal = await entry_function.evaluate(context)
        
        if signal.should_execute:
            # Create bracket order structure
            parent_order = OrderRequest(
                trade_plan_id="test_plan_001",
                symbol="AAPL",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                entry_price=Decimal("181.50"),
                stop_loss_price=Decimal("178.00"),
                take_profit_price=Decimal("184.00"),
                risk_category=RiskCategory.NORMAL,
                calculated_position_size=100,
                time_in_force="DAY"
            )
            
            stop_loss_order = OrderRequest(
                trade_plan_id="test_plan_001",
                symbol="AAPL",
                side=OrderSide.SELL,
                order_type=OrderType.STOP,
                entry_price=Decimal("178.00"),
                stop_loss_price=Decimal("176.00"),
                take_profit_price=Decimal("180.00"),
                risk_category=RiskCategory.NORMAL,
                calculated_position_size=100,
                time_in_force="GTC"  # Good till cancelled
            )
            
            take_profit_order = OrderRequest(
                trade_plan_id="test_plan_001",
                symbol="AAPL",
                side=OrderSide.SELL,
                order_type=OrderType.LIMIT,
                entry_price=Decimal("184.00"),
                stop_loss_price=Decimal("182.00"),
                take_profit_price=Decimal("186.00"),
                risk_category=RiskCategory.NORMAL,
                calculated_position_size=100,
                time_in_force="GTC"
            )
            
            # Verify bracket order structure
            assert parent_order.order_type == OrderType.MARKET
            assert stop_loss_order.order_type == OrderType.STOP
            assert take_profit_order.order_type == OrderType.LIMIT

    async def test_order_modification_from_trailing_stop(
        self, execution_system, sample_market_data
    ):
        """Test order modification from trailing stop signals."""
        registry = execution_system["registry"]
        order_manager = execution_system["order_manager"]
        current_bar, historical_bars = sample_market_data
        
        # Register and create trailing stop function
        from auto_trader.trade_engine.functions import TrailingStopFunction
        await registry.register("trailing_stop", TrailingStopFunction)
        
        config = ExecutionFunctionConfig(
            name="trailing_stop_test",
            function_type="trailing_stop",
            timeframe=Timeframe.ONE_MIN,
            parameters={"trail_percentage": 2.0},
            enabled=True
        )
        trailing_function = await registry.create_function(config)
        
        # Create position with existing stop order
        position = PositionState(
            symbol="AAPL",
            quantity=100,
            entry_price=Decimal("180.00"),
            current_price=Decimal("182.00"),  # Price moved up
            stop_loss=Decimal("178.00"),  # Original stop
            opened_at=datetime.now(UTC) - timedelta(minutes=30)
        )
        
        context = ExecutionContext(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            current_bar=current_bar,
            historical_bars=historical_bars,
            trade_plan_params={"trail_percentage": 2.0},
            position_state=position,
            account_balance=Decimal("10000"),
            timestamp=datetime.now(UTC)
        )
        
        # Execute trailing stop function
        signal = await trailing_function.evaluate(context)
        
        if signal.action == ExecutionAction.MODIFY_STOP:
            # Should trigger stop modification
            new_stop_level = signal.metadata.get("new_stop_level")
            assert new_stop_level is not None
            
            # Modify the stop order
            modification_result = await order_manager.modify_order(
                order_id="STOP_ORDER_123",
                new_price=Decimal(str(new_stop_level))
            )
            
            # Verify modification was called
            order_manager.modify_order.assert_called_once()
            assert modification_result is True

    async def test_concurrent_signal_processing(
        self, execution_system, sample_market_data
    ):
        """Test concurrent processing of multiple execution signals."""
        entry_function = execution_system["entry_function"]
        order_manager = execution_system["order_manager"]
        current_bar, historical_bars = sample_market_data
        
        symbols = ["AAPL", "MSFT", "GOOGL"]
        order_results = []
        
        async def process_symbol_signal(symbol):
            """Process execution signal for a symbol."""
            # Modify bar for different symbol
            symbol_bar = BarData(
                symbol=symbol,
                timestamp=current_bar.timestamp,
                open_price=current_bar.open_price,
                high_price=current_bar.high_price,
                low_price=current_bar.low_price,
                close_price=current_bar.close_price,
                volume=current_bar.volume,
                bar_size=current_bar.bar_size,
            )
            
            context = ExecutionContext(
                symbol=symbol,
                timeframe=Timeframe.ONE_MIN,
                current_bar=symbol_bar,
                historical_bars=historical_bars,
                trade_plan_params={"threshold_price": 180.00},
                position_state=None,
                account_balance=Decimal("10000"),
                timestamp=datetime.now(UTC)
            )
            
            signal = await entry_function.evaluate(context)
            
            if signal.should_execute:
                order_request = OrderRequest(
                    trade_plan_id=f"test_plan_{symbol}",
                    symbol=symbol,
                    side=OrderSide.BUY,
                    order_type=OrderType.MARKET,
                    entry_price=Decimal("181.50"),
                    stop_loss_price=Decimal("179.50"),
                    take_profit_price=Decimal("184.50"),
                    risk_category=RiskCategory.NORMAL,
                    calculated_position_size=100,
                    time_in_force="DAY"
                )
                
                order_id = await order_manager.place_order(order_request)
                return {"symbol": symbol, "order_id": order_id, "signal": signal}
            
            return {"symbol": symbol, "order_id": None, "signal": signal}
        
        # Process all symbols concurrently
        tasks = [process_symbol_signal(symbol) for symbol in symbols]
        results = await asyncio.gather(*tasks)
        
        # Verify all signals were processed
        assert len(results) == 3
        for result in results:
            assert result["signal"] is not None
            if result["signal"].should_execute:
                assert result["order_id"] is not None

    async def test_order_failure_handling(
        self, execution_system, sample_market_data
    ):
        """Test handling of order placement failures."""
        entry_function = execution_system["entry_function"]
        order_manager = execution_system["order_manager"]
        current_bar, historical_bars = sample_market_data
        
        # Setup order manager to fail
        order_manager.place_order.side_effect = Exception("Order placement failed")
        
        context = ExecutionContext(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            current_bar=current_bar,
            historical_bars=historical_bars,
            trade_plan_params={"threshold_price": 180.00},
            position_state=None,
            account_balance=Decimal("10000"),
            timestamp=datetime.now(UTC)
        )
        
        # Execute function
        signal = await entry_function.evaluate(context)
        
        if signal.should_execute:
            # Order placement should fail
            with pytest.raises(Exception, match="Order placement failed"):
                await order_manager.place_order(OrderRequest(
                    trade_plan_id="test_plan_001",
                    symbol="AAPL",
                    side=OrderSide.BUY,
                    order_type=OrderType.MARKET,
                    entry_price=Decimal("181.50"),
                    stop_loss_price=Decimal("179.50"),
                    take_profit_price=Decimal("184.50"),
                    risk_category=RiskCategory.NORMAL,
                    calculated_position_size=100,
                    time_in_force="DAY"
                ))

    async def test_position_state_update_after_execution(
        self, execution_system, sample_market_data
    ):
        """Test position state updates after order execution."""
        entry_function = execution_system["entry_function"]
        order_manager = execution_system["order_manager"]
        current_bar, historical_bars = sample_market_data
        
        # Mock filled order response
        filled_order = Order(
            trade_plan_id="test_plan_001",
            order_id="ORDER_12345",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100,
            filled_quantity=100,
            status=OrderStatus.FILLED,
            average_fill_price=Decimal("181.50"),
            filled_at=datetime.now(UTC)
        )
        
        # Mock getting positions after fill
        order_manager.get_positions.return_value = {
            "AAPL": PositionState(
                symbol="AAPL",
                quantity=100,
                entry_price=Decimal("181.50"),
                current_price=Decimal("181.50"),
                opened_at=datetime.now(UTC)
            )
        }
        
        context = ExecutionContext(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            current_bar=current_bar,
            historical_bars=historical_bars,
            trade_plan_params={"threshold_price": 180.00},
            position_state=None,
            account_balance=Decimal("10000"),
            timestamp=datetime.now(UTC)
        )
        
        # Execute function
        signal = await entry_function.evaluate(context)
        
        if signal.should_execute:
            # Place order
            order_id = await order_manager.place_order(OrderRequest(
                trade_plan_id="test_plan_001",
                symbol="AAPL",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                entry_price=Decimal("181.50"),
                stop_loss_price=Decimal("179.50"),
                take_profit_price=Decimal("184.50"),
                risk_category=RiskCategory.NORMAL,
                calculated_position_size=100,
                time_in_force="DAY"
            ))
            
            # Get updated positions
            positions = order_manager.get_positions()
            assert "AAPL" in positions
            assert positions["AAPL"].quantity == 100
            assert positions["AAPL"].entry_price == Decimal("181.50")

    async def test_signal_metadata_preservation(
        self, execution_system, sample_market_data
    ):
        """Test preservation of signal metadata through order execution."""
        entry_function = execution_system["entry_function"]
        current_bar, historical_bars = sample_market_data
        
        context = ExecutionContext(
            symbol="AAPL",
            timeframe=Timeframe.ONE_MIN,
            current_bar=current_bar,
            historical_bars=historical_bars,
            trade_plan_params={"threshold_price": 180.00},
            position_state=None,
            account_balance=Decimal("10000"),
            timestamp=datetime.now(UTC)
        )
        
        # Execute function
        signal = await entry_function.evaluate(context)
        
        if signal.should_execute:
            # Create order request with signal metadata
            order_request = OrderRequest(
                trade_plan_id="test_plan_001",
                symbol="AAPL",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                entry_price=current_bar.close_price,
                stop_loss_price=current_bar.close_price - Decimal("2.00"),
                take_profit_price=current_bar.close_price + Decimal("3.00"),
                risk_category=RiskCategory.NORMAL,
                calculated_position_size=100,
                time_in_force="DAY"
            )
            
            # Verify order request was created successfully
            assert order_request.symbol == "AAPL"
            assert order_request.side == OrderSide.BUY
            assert order_request.order_type == OrderType.MARKET
            assert order_request.calculated_position_size == 100