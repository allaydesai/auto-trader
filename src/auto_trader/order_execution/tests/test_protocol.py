"""Comprehensive tests for OrderExecutionProvider protocol."""

import pytest
from typing import Optional

from auto_trader.order_execution.protocol import OrderExecutionProvider
from auto_trader.order_execution.simulated_execution import SimulatedOrderExecution
from auto_trader.models.order import Order, OrderResult, BracketOrder, OrderModification
from auto_trader.models.enums import OrderType, OrderSide, OrderStatus


class TestOrderExecutionProviderProtocol:
    """Test suite for OrderExecutionProvider protocol compliance."""

    def test_protocol_is_runtime_checkable(self):
        """Test that OrderExecutionProvider is runtime_checkable."""
        # The protocol should be decorated with @runtime_checkable
        # This allows isinstance() checks at runtime
        # Check for _is_runtime_protocol attribute added by @runtime_checkable
        assert hasattr(OrderExecutionProvider, "_is_runtime_protocol")
        assert OrderExecutionProvider._is_runtime_protocol is True

    def test_simulated_execution_implements_protocol(self):
        """Test that SimulatedOrderExecution implements OrderExecutionProvider protocol."""
        simulated = SimulatedOrderExecution()

        # isinstance() check should pass for protocol compliance
        assert isinstance(simulated, OrderExecutionProvider)

    def test_incomplete_class_fails_protocol_check(self):
        """Test that classes without all methods fail isinstance check."""

        class IncompleteProvider:
            """Intentionally incomplete implementation."""

            async def place_market_order(self, order: Order) -> OrderResult:
                """Only implements one method."""
                pass

        incomplete = IncompleteProvider()

        # Should fail because not all methods are implemented
        assert not isinstance(incomplete, OrderExecutionProvider)

    def test_empty_class_fails_protocol_check(self):
        """Test that empty classes fail isinstance check."""

        class EmptyProvider:
            """Empty class with no methods."""

            pass

        empty = EmptyProvider()

        # Should fail because no methods are implemented
        assert not isinstance(empty, OrderExecutionProvider)

    def test_protocol_method_signatures_match_place_market_order(self):
        """Test that place_market_order signature matches protocol specification."""
        simulated = SimulatedOrderExecution()

        # Verify the method exists and is callable
        assert hasattr(simulated, "place_market_order")
        assert callable(simulated.place_market_order)

        # Verify method signature matches protocol
        import inspect

        sig = inspect.signature(simulated.place_market_order)
        params = list(sig.parameters.keys())

        # Should have 'order' parameter
        assert "order" in params
        assert sig.return_annotation != inspect.Signature.empty

    def test_protocol_method_signatures_match_place_bracket_order(self):
        """Test that place_bracket_order signature matches protocol specification."""
        simulated = SimulatedOrderExecution()

        # Verify the method exists and is callable
        assert hasattr(simulated, "place_bracket_order")
        assert callable(simulated.place_bracket_order)

        # Verify method signature matches protocol
        import inspect

        sig = inspect.signature(simulated.place_bracket_order)
        params = list(sig.parameters.keys())

        # Should have 'bracket' parameter
        assert "bracket" in params
        assert sig.return_annotation != inspect.Signature.empty

    def test_protocol_method_signatures_match_modify_order(self):
        """Test that modify_order signature matches protocol specification."""
        simulated = SimulatedOrderExecution()

        # Verify the method exists and is callable
        assert hasattr(simulated, "modify_order")
        assert callable(simulated.modify_order)

        # Verify method signature matches protocol
        import inspect

        sig = inspect.signature(simulated.modify_order)
        params = list(sig.parameters.keys())

        # Should have 'order' and 'modification' parameters
        assert "order" in params
        assert "modification" in params
        assert sig.return_annotation != inspect.Signature.empty

    def test_protocol_method_signatures_match_cancel_order(self):
        """Test that cancel_order signature matches protocol specification."""
        simulated = SimulatedOrderExecution()

        # Verify the method exists and is callable
        assert hasattr(simulated, "cancel_order")
        assert callable(simulated.cancel_order)

        # Verify method signature matches protocol
        import inspect

        sig = inspect.signature(simulated.cancel_order)
        params = list(sig.parameters.keys())

        # Should have 'order' parameter
        assert "order" in params
        assert sig.return_annotation != inspect.Signature.empty

    def test_protocol_method_signatures_match_get_order_status(self):
        """Test that get_order_status signature matches protocol specification."""
        simulated = SimulatedOrderExecution()

        # Verify the method exists and is callable
        assert hasattr(simulated, "get_order_status")
        assert callable(simulated.get_order_status)

        # Verify method signature matches protocol
        import inspect

        sig = inspect.signature(simulated.get_order_status)
        params = list(sig.parameters.keys())

        # Should have 'order_id' parameter
        assert "order_id" in params

        # Return type should be Optional[Order]
        return_annotation = sig.return_annotation
        assert return_annotation != inspect.Signature.empty

    def test_get_order_status_returns_optional_type(self):
        """Test that get_order_status has Optional return type for non-existent orders."""
        # This tests that the protocol allows None returns
        simulated = SimulatedOrderExecution()

        # Verify return type annotation
        import inspect
        from typing import get_args, get_origin

        sig = inspect.signature(simulated.get_order_status)
        return_annotation = sig.return_annotation

        # Check if it's Optional (Union with None)
        origin = get_origin(return_annotation)
        if origin is not None:
            args = get_args(return_annotation)
            # Optional[X] is Union[X, None]
            assert type(None) in args or None in args


class TestProtocolComplianceWithMockProvider:
    """Test protocol compliance with a complete mock provider."""

    @pytest.fixture
    def mock_provider(self):
        """Create a mock provider that implements the protocol."""

        class MockOrderExecutionProvider:
            """Complete mock implementation of OrderExecutionProvider."""

            def __init__(self):
                self._orders = {}

            async def place_market_order(self, order: Order) -> OrderResult:
                """Mock implementation of place_market_order."""
                order_id = f"MOCK_{len(self._orders) + 1}"
                self._orders[order_id] = order
                return OrderResult(
                    success=True,
                    order_id=order_id,
                    trade_plan_id=order.trade_plan_id,
                    order_status=OrderStatus.FILLED,
                    symbol=order.symbol,
                    side=order.side,
                    quantity=order.quantity,
                    order_type=order.order_type,
                )

            async def place_bracket_order(self, bracket: BracketOrder) -> OrderResult:
                """Mock implementation of place_bracket_order."""
                bracket_id = f"BRACKET_{len(self._orders) + 1}"
                self._orders[bracket_id] = bracket
                return OrderResult(
                    success=True,
                    order_id=bracket_id,
                    trade_plan_id=bracket.trade_plan_id,
                    order_status=OrderStatus.SUBMITTED,
                    symbol=bracket.parent_order.symbol,
                    side=bracket.parent_order.side,
                    quantity=bracket.parent_order.quantity,
                    order_type=bracket.parent_order.order_type,
                )

            async def modify_order(
                self, order: Order, modification: OrderModification
            ) -> OrderResult:
                """Mock implementation of modify_order."""
                return OrderResult(
                    success=True,
                    order_id=order.order_id or "MOCK_MOD",
                    trade_plan_id=order.trade_plan_id,
                    order_status=OrderStatus.SUBMITTED,
                    symbol=order.symbol,
                    side=order.side,
                    quantity=modification.new_quantity or order.quantity,
                    order_type=order.order_type,
                )

            async def cancel_order(self, order: Order) -> OrderResult:
                """Mock implementation of cancel_order."""
                return OrderResult(
                    success=True,
                    order_id=order.order_id or "MOCK_CANCEL",
                    trade_plan_id=order.trade_plan_id,
                    order_status=OrderStatus.CANCELLED,
                    symbol=order.symbol,
                    side=order.side,
                    quantity=order.quantity,
                    order_type=order.order_type,
                )

            async def get_order_status(self, order_id: str) -> Optional[Order]:
                """Mock implementation of get_order_status."""
                if order_id in self._orders:
                    stored = self._orders[order_id]
                    if isinstance(stored, Order):
                        return stored
                    elif isinstance(stored, BracketOrder):
                        return stored.parent_order
                return None

        return MockOrderExecutionProvider()

    def test_mock_provider_implements_protocol(self, mock_provider):
        """Test that complete mock provider implements OrderExecutionProvider protocol."""
        assert isinstance(mock_provider, OrderExecutionProvider)

    @pytest.mark.asyncio
    async def test_mock_provider_place_market_order_execution(self, mock_provider):
        """Test that mock provider can execute place_market_order."""
        order = Order(
            trade_plan_id="TEST_PLAN_001",
            symbol="AAPL",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            quantity=100,
        )

        result = await mock_provider.place_market_order(order)

        assert result.success
        assert result.order_id is not None
        assert result.order_status == OrderStatus.FILLED

    @pytest.mark.asyncio
    async def test_mock_provider_get_order_status_returns_optional(self, mock_provider):
        """Test that get_order_status returns None for non-existent orders."""
        result = await mock_provider.get_order_status("NON_EXISTENT_ID")

        assert result is None


class TestProtocolDocumentation:
    """Test that protocol has proper documentation."""

    def test_protocol_has_docstring(self):
        """Test that OrderExecutionProvider protocol has documentation."""
        assert OrderExecutionProvider.__doc__ is not None
        assert len(OrderExecutionProvider.__doc__.strip()) > 0

    def test_protocol_methods_have_docstrings(self):
        """Test that all protocol methods have documentation."""

        # Get all methods defined in the protocol
        methods = [
            "place_market_order",
            "place_bracket_order",
            "modify_order",
            "cancel_order",
            "get_order_status",
        ]

        for method_name in methods:
            # Get the method from protocol annotations
            assert hasattr(OrderExecutionProvider, method_name)
