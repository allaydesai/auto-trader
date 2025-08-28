# Test suite for OrderRiskValidator
import pytest
from decimal import Decimal
from unittest.mock import Mock, AsyncMock

from auto_trader.models import OrderRequest, OrderType, OrderSide, RiskCategory
from auto_trader.risk_management import (
    OrderRiskValidator,
    PositionSizer,
    PortfolioTracker,
    PositionSizeResult,
    RiskValidationResult,
    PortfolioRiskState,
    PositionRiskEntry,
    PortfolioRiskExceededError,
    InvalidPositionSizeError,
    DailyLossLimitExceededError,
)


@pytest.fixture
def mock_position_sizer():
    """Mock position sizer."""
    mock = Mock(spec=PositionSizer)
    mock.calculate_position_size.return_value = PositionSizeResult(
        position_size=100,
        dollar_risk=Decimal("2000.00"),
        validation_status=True,
        portfolio_risk_percentage=Decimal("2.0"),
        risk_category="normal",
        account_value=Decimal("100000.00"),
    )
    return mock


@pytest.fixture
def mock_portfolio_tracker():
    """Mock portfolio tracker."""
    mock = Mock(spec=PortfolioTracker)
    mock.get_current_state = AsyncMock(return_value=PortfolioRiskState(
        positions=[],
        total_risk_percentage=Decimal("3.0"),
        account_value=Decimal("100000.00"),
    ))
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
    )


@pytest.fixture
def order_risk_validator(mock_position_sizer, mock_portfolio_tracker):
    """Order risk validator with mocked dependencies."""
    return OrderRiskValidator(
        position_sizer=mock_position_sizer,
        portfolio_tracker=mock_portfolio_tracker,
        account_value=Decimal("100000.00"),
    )


class TestOrderRiskValidator:
    """Test cases for OrderRiskValidator."""

    @pytest.mark.asyncio
    async def test_successful_validation(
        self, order_risk_validator, sample_order_request
    ):
        """Test successful order validation."""
        result = await order_risk_validator.validate_order_request(sample_order_request)
        
        assert result.is_valid is True
        assert result.position_size_result is not None
        assert result.position_size_result.position_size == 100
        assert result.portfolio_risk_check.passed is True
        assert len(result.errors) == 0
        assert sample_order_request.calculated_position_size == 100

    @pytest.mark.asyncio
    async def test_portfolio_risk_limit_exceeded(
        self, mock_position_sizer, mock_portfolio_tracker, sample_order_request
    ):
        """Test validation failure when portfolio risk limit is exceeded."""
        # Set high current risk to trigger limit
        mock_portfolio_tracker.get_current_state = AsyncMock(return_value=PortfolioRiskState(
            positions=[],
            total_risk_percentage=Decimal("9.0"),  # High current risk
            account_value=Decimal("100000.00"),
        ))
        
        validator = OrderRiskValidator(
            position_sizer=mock_position_sizer,
            portfolio_tracker=mock_portfolio_tracker,
            account_value=Decimal("100000.00"),
        )
        
        result = await validator.validate_order_request(sample_order_request)
        
        assert result.is_valid is False
        assert len(result.errors) > 0
        assert "Portfolio risk limit exceeded" in result.errors[0]

    @pytest.mark.asyncio
    async def test_daily_loss_limit_validation(
        self, mock_position_sizer, mock_portfolio_tracker, sample_order_request
    ):
        """Test daily loss limit validation (currently simplified implementation)."""        
        validator = OrderRiskValidator(
            position_sizer=mock_position_sizer,
            portfolio_tracker=mock_portfolio_tracker,
            account_value=Decimal("100000.00"),
        )
        
        result = await validator.validate_order_request(sample_order_request)
        
        # With simplified implementation, daily loss limit always passes
        assert result.is_valid is True

    @pytest.mark.asyncio
    async def test_invalid_position_size(
        self, mock_position_sizer, mock_portfolio_tracker, sample_order_request
    ):
        """Test validation failure due to invalid position size calculation."""
        # Make position sizer raise error
        mock_position_sizer.calculate_position_size.side_effect = InvalidPositionSizeError(
            "Invalid entry/stop prices"
        )
        
        validator = OrderRiskValidator(
            position_sizer=mock_position_sizer,
            portfolio_tracker=mock_portfolio_tracker,
            account_value=Decimal("100000.00"),
        )
        
        result = await validator.validate_order_request(sample_order_request)
        
        assert result.is_valid is False
        assert len(result.errors) > 0
        assert "Invalid entry/stop prices" in result.errors[0]

    @pytest.mark.asyncio
    async def test_insufficient_capital(
        self, mock_position_sizer, mock_portfolio_tracker, sample_order_request
    ):
        """Test validation failure due to insufficient capital."""
        # Set very high position size to trigger capital check
        mock_position_sizer.calculate_position_size.return_value = PositionSizeResult(
            position_size=10000,  # Very large position
            dollar_risk=Decimal("5000.00"),  # Lower dollar risk to avoid portfolio limit
            validation_status=True,
            portfolio_risk_percentage=Decimal("5.0"),  # 5% portfolio risk (within 10% limit)
            risk_category="normal",
            account_value=Decimal("100000.00"),
        )
        
        validator = OrderRiskValidator(
            position_sizer=mock_position_sizer,
            portfolio_tracker=mock_portfolio_tracker,
            account_value=Decimal("100000.00"),  # Not enough for 10000 * $180.50
        )
        
        result = await validator.validate_order_request(sample_order_request)
        
        assert result.is_valid is False
        assert len(result.errors) > 0
        assert "Insufficient capital" in result.errors[0]

    def test_create_order_rejection_result(
        self, order_risk_validator, sample_order_request
    ):
        """Test creating order rejection result."""
        from auto_trader.risk_management import RiskCheck
        
        risk_check = RiskCheck(
            passed=False,
            reason="Test failure",
            current_risk=Decimal("5.0"),
            new_trade_risk=Decimal("3.0"),
            total_risk=Decimal("8.0"),
            limit=Decimal("10.0"),
        )
        
        validation_result = RiskValidationResult(
            is_valid=False,
            position_size_result=None,
            portfolio_risk_check=risk_check,
            errors=["Test error"],
            warnings=[],
        )
        
        order_result = order_risk_validator.create_order_rejection_result(
            sample_order_request, validation_result
        )
        
        assert order_result.success is False
        assert order_result.trade_plan_id == sample_order_request.trade_plan_id
        assert "Risk validation failed" in order_result.error_message
        assert order_result.symbol == sample_order_request.symbol
        assert order_result.quantity == 0

    @pytest.mark.asyncio
    async def test_risk_category_mapping(
        self, mock_position_sizer, mock_portfolio_tracker
    ):
        """Test that RiskCategory enum values are correctly mapped to strings."""
        order_request = OrderRequest(
            trade_plan_id="TEST_001",
            symbol="TSLA",
            side=OrderSide.BUY,
            order_type=OrderType.MARKET,
            entry_price=Decimal("250.00"),
            stop_loss_price=Decimal("240.00"),
            take_profit_price=Decimal("270.00"),
            risk_category=RiskCategory.LARGE,  # Test LARGE category
        )
        
        validator = OrderRiskValidator(
            position_sizer=mock_position_sizer,
            portfolio_tracker=mock_portfolio_tracker,
            account_value=Decimal("100000.00"),
        )
        
        await validator.validate_order_request(order_request)
        
        # Check that position sizer was called with correct risk category string
        mock_position_sizer.calculate_position_size.assert_called_once()
        args = mock_position_sizer.calculate_position_size.call_args[1]
        assert args["risk_category"] == "large"  # Enum value converted to lowercase

    @pytest.mark.asyncio
    async def test_account_value_precedence(
        self, mock_position_sizer, mock_portfolio_tracker, sample_order_request
    ):
        """Test that explicitly set account value takes precedence."""
        explicit_account_value = Decimal("50000.00")
        
        validator = OrderRiskValidator(
            position_sizer=mock_position_sizer,
            portfolio_tracker=mock_portfolio_tracker,
            account_value=explicit_account_value,
        )
        
        account_value = await validator._get_account_value()
        assert account_value == explicit_account_value

    @pytest.mark.asyncio
    async def test_default_account_value(
        self, mock_position_sizer, mock_portfolio_tracker, sample_order_request
    ):
        """Test that default account value is used when not explicitly set."""
        validator = OrderRiskValidator(
            position_sizer=mock_position_sizer,
            portfolio_tracker=mock_portfolio_tracker,
            account_value=None,  # No explicit value
        )
        
        account_value = await validator._get_account_value()
        assert account_value == Decimal("100000.00")  # Default value