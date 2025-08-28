# Test suite for order models
import pytest
from decimal import Decimal
from datetime import datetime, UTC
from pydantic import ValidationError

from auto_trader.models import (
    Order,
    OrderRequest,
    OrderResult,
    BracketOrder,
    OrderEvent,
    OrderModification,
    OrderType,
    OrderSide,
    OrderStatus,
    RiskCategory,
    TimeInForce,
)


class TestOrder:
    """Test cases for Order model."""

    def test_create_basic_market_order(self):
        """Test creating a basic market order."""
        order = Order(
            trade_plan_id="AAPL_20250827_001",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100
        )
        
        assert order.symbol == "AAPL"
        assert order.side == OrderSide.BUY
        assert order.order_type == OrderType.MARKET
        assert order.quantity == 100
        assert order.status == OrderStatus.PENDING
        assert order.filled_quantity == 0
        assert order.remaining_quantity == 100

    def test_create_limit_order_with_price(self):
        """Test creating a limit order with price."""
        order = Order(
            trade_plan_id="TSLA_20250827_001",
            symbol="TSLA",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=50,
            price=Decimal("250.75")
        )
        
        assert order.price == Decimal("250.75")
        assert order.order_type == OrderType.LIMIT

    def test_create_stop_order(self):
        """Test creating a stop order."""
        order = Order(
            trade_plan_id="SPY_20250827_001",
            symbol="SPY",
            side=OrderSide.SELL,
            order_type=OrderType.STOP,
            quantity=200,
            stop_price=Decimal("400.00")
        )
        
        assert order.stop_price == Decimal("400.00")
        assert order.order_type == OrderType.STOP

    def test_remaining_quantity_calculation(self):
        """Test that remaining quantity is calculated correctly."""
        order = Order(
            trade_plan_id="NVDA_20250827_001",
            symbol="NVDA",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100,
            filled_quantity=30
        )
        
        assert order.remaining_quantity == 70

    def test_order_validation_failures(self):
        """Test order validation failures."""
        with pytest.raises(ValidationError, match="greater than 0"):
            Order(
                trade_plan_id="TEST_001",
                symbol="AAPL",
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=0  # Invalid: must be > 0
            )

        with pytest.raises(ValidationError, match="at least 1 character"):
            Order(
                trade_plan_id="TEST_001",
                symbol="",  # Invalid: empty symbol
                side=OrderSide.BUY,
                order_type=OrderType.MARKET,
                quantity=100
            )


class TestOrderRequest:
    """Test cases for OrderRequest model."""

    def test_create_order_request(self):
        """Test creating a basic order request."""
        request = OrderRequest(
            trade_plan_id="AAPL_20250827_001",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            entry_price=Decimal("180.50"),
            stop_loss_price=Decimal("178.00"),
            take_profit_price=Decimal("185.00"),
            risk_category=RiskCategory.NORMAL
        )
        
        assert request.symbol == "AAPL"
        assert request.entry_price == Decimal("180.50")
        assert request.stop_loss_price == Decimal("178.00")
        assert request.take_profit_price == Decimal("185.00")
        assert request.risk_category == RiskCategory.NORMAL

    def test_order_request_with_position_size(self):
        """Test order request with calculated position size."""
        request = OrderRequest(
            trade_plan_id="TSLA_20250827_001",
            symbol="TSLA",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            entry_price=Decimal("250.00"),
            stop_loss_price=Decimal("240.00"),
            take_profit_price=Decimal("270.00"),
            risk_category=RiskCategory.LARGE,
            calculated_position_size=50
        )
        
        assert request.calculated_position_size == 50
        assert request.risk_category == RiskCategory.LARGE


class TestOrderResult:
    """Test cases for OrderResult model."""

    def test_successful_order_result(self):
        """Test creating a successful order result."""
        result = OrderResult(
            success=True,
            order_id="12345",
            trade_plan_id="AAPL_20250827_001",
            order_status=OrderStatus.SUBMITTED,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=100,
            order_type=OrderType.MARKET
        )
        
        assert result.success is True
        assert result.order_id == "12345"
        assert result.order_status == OrderStatus.SUBMITTED

    def test_failed_order_result(self):
        """Test creating a failed order result."""
        result = OrderResult(
            success=False,
            trade_plan_id="AAPL_20250827_001",
            order_status=OrderStatus.REJECTED,
            error_message="Insufficient buying power",
            error_code=201,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=1000,
            order_type=OrderType.MARKET
        )
        
        assert result.success is False
        assert result.error_message == "Insufficient buying power"
        assert result.error_code == 201
        assert result.order_status == OrderStatus.REJECTED


class TestBracketOrder:
    """Test cases for BracketOrder model."""

    def test_create_bracket_order(self):
        """Test creating a complete bracket order."""
        parent = Order(
            trade_plan_id="AAPL_20250827_001",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=Decimal("180.50")
        )
        
        stop_loss = Order(
            trade_plan_id="AAPL_20250827_001",
            symbol="AAPL",
            side=OrderSide.SELL,
            order_type=OrderType.STOP,
            quantity=100,
            stop_price=Decimal("178.00")
        )
        
        take_profit = Order(
            trade_plan_id="AAPL_20250827_001",
            symbol="AAPL",
            side=OrderSide.SELL,
            order_type=OrderType.LIMIT,
            quantity=100,
            price=Decimal("185.00")
        )
        
        bracket = BracketOrder(
            bracket_id="BRACKET_001",
            trade_plan_id="AAPL_20250827_001",
            parent_order=parent,
            stop_loss_order=stop_loss,
            take_profit_order=take_profit
        )
        
        assert bracket.bracket_id == "BRACKET_001"
        assert bracket.parent_order.quantity == 100
        assert bracket.stop_loss_order.stop_price == Decimal("178.00")
        assert bracket.take_profit_order.price == Decimal("185.00")


class TestOrderEvent:
    """Test cases for OrderEvent model."""

    def test_create_order_status_event(self):
        """Test creating an order status change event."""
        event = OrderEvent(
            event_id="EVT_001",
            order_id="12345",
            trade_plan_id="AAPL_20250827_001",
            event_type="status_change",
            old_status=OrderStatus.SUBMITTED,
            new_status=OrderStatus.FILLED
        )
        
        assert event.event_type == "status_change"
        assert event.old_status == OrderStatus.SUBMITTED
        assert event.new_status == OrderStatus.FILLED

    def test_create_fill_event(self):
        """Test creating an order fill event."""
        event = OrderEvent(
            event_id="EVT_002",
            order_id="12345",
            trade_plan_id="AAPL_20250827_001",
            event_type="fill",
            old_status=OrderStatus.SUBMITTED,
            new_status=OrderStatus.FILLED,
            fill_quantity=100,
            fill_price=Decimal("180.75")
        )
        
        assert event.fill_quantity == 100
        assert event.fill_price == Decimal("180.75")


class TestOrderModification:
    """Test cases for OrderModification model."""

    def test_create_price_modification(self):
        """Test creating an order price modification."""
        modification = OrderModification(
            order_id="12345",
            new_price=Decimal("181.00"),
            reason="Market conditions changed"
        )
        
        assert modification.order_id == "12345"
        assert modification.new_price == Decimal("181.00")
        assert modification.reason == "Market conditions changed"

    def test_create_quantity_modification(self):
        """Test creating an order quantity modification."""
        modification = OrderModification(
            order_id="12345",
            new_quantity=150,
            reason="Increased position size"
        )
        
        assert modification.new_quantity == 150
        assert modification.reason == "Increased position size"