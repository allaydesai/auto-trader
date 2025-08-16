"""Shared fixtures for risk management tests."""

import tempfile
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from ...models import TradePlan, ExecutionFunction, RiskCategory, TradePlanStatus
from ..risk_models import (
    PositionRiskEntry,
    PositionSizeResult,
    PortfolioRiskState,
    RiskCheck,
)


@pytest.fixture
def sample_account_value() -> Decimal:
    """Sample account value for testing."""
    return Decimal("10000.00")


@pytest.fixture
def sample_entry_price() -> Decimal:
    """Sample entry price for testing."""
    return Decimal("100.00")


@pytest.fixture
def sample_stop_loss() -> Decimal:
    """Sample stop loss price for testing."""
    return Decimal("95.00")


@pytest.fixture
def sample_position_size_result() -> PositionSizeResult:
    """Sample position size result for testing."""
    return PositionSizeResult(
        position_size=40,
        dollar_risk=Decimal("200.00"),
        validation_status=True,
        portfolio_risk_percentage=Decimal("2.0"),
        risk_category="normal",
        account_value=Decimal("10000.00"),
    )


@pytest.fixture
def sample_risk_check_passed() -> RiskCheck:
    """Sample passing risk check for testing."""
    return RiskCheck(
        passed=True,
        current_risk=Decimal("5.0"),
        new_trade_risk=Decimal("2.0"),
        total_risk=Decimal("7.0"),
        limit=Decimal("10.0"),
    )


@pytest.fixture
def sample_risk_check_failed() -> RiskCheck:
    """Sample failing risk check for testing."""
    return RiskCheck(
        passed=False,
        reason="Portfolio risk limit exceeded",
        current_risk=Decimal("8.5"),
        new_trade_risk=Decimal("2.0"),
        total_risk=Decimal("10.5"),
        limit=Decimal("10.0"),
    )


@pytest.fixture
def sample_position_risk_entry() -> PositionRiskEntry:
    """Sample position risk entry for testing."""
    return PositionRiskEntry(
        position_id="TEST_POS_001",
        symbol="AAPL",
        risk_amount=Decimal("200.00"),
        plan_id="AAPL_20250815_001",
        entry_time=datetime(2025, 8, 15, 10, 30, 0),
    )


@pytest.fixture
def sample_portfolio_risk_state(sample_position_risk_entry: PositionRiskEntry) -> PortfolioRiskState:
    """Sample portfolio risk state for testing."""
    return PortfolioRiskState(
        positions=[sample_position_risk_entry],
        total_risk_percentage=Decimal("2.0"),
        account_value=Decimal("10000.00"),
        last_updated=datetime(2025, 8, 15, 10, 30, 0),
    )


@pytest.fixture
def multiple_position_entries() -> list[PositionRiskEntry]:
    """Multiple position risk entries for testing."""
    return [
        PositionRiskEntry(
            position_id="TEST_POS_001",
            symbol="AAPL",
            risk_amount=Decimal("200.00"),
            plan_id="AAPL_20250815_001",
        ),
        PositionRiskEntry(
            position_id="TEST_POS_002", 
            symbol="MSFT",
            risk_amount=Decimal("300.00"),
            plan_id="MSFT_20250815_001",
        ),
        PositionRiskEntry(
            position_id="TEST_POS_003",
            symbol="GOOGL", 
            risk_amount=Decimal("150.00"),
            plan_id="GOOGL_20250815_001",
        ),
    ]


@pytest.fixture
def sample_trade_plan() -> TradePlan:
    """Sample trade plan for testing."""
    return TradePlan(
        plan_id="AAPL_20250815_001",
        symbol="AAPL",
        entry_level=Decimal("180.00"),
        stop_loss=Decimal("175.00"),
        take_profit=Decimal("190.00"),
        risk_category=RiskCategory.NORMAL,
        entry_function=ExecutionFunction(
            function_type="close_above",
            timeframe="15min",
            parameters={"threshold": 180.00},
        ),
        exit_function=ExecutionFunction(
            function_type="stop_loss_take_profit",
            timeframe="15min",
            parameters={},
        ),
        status=TradePlanStatus.AWAITING_ENTRY,
    )


@pytest.fixture
def high_risk_trade_plan() -> TradePlan:
    """High risk trade plan for testing limit violations."""
    return TradePlan(
        plan_id="TSLA_20250815_001",
        symbol="TSLA",
        entry_level=Decimal("250.00"),
        stop_loss=Decimal("240.00"),
        take_profit=Decimal("270.00"),
        risk_category=RiskCategory.LARGE,  # 3% risk
        entry_function=ExecutionFunction(
            function_type="close_above",
            timeframe="15min",
            parameters={"threshold": 250.00},
        ),
        exit_function=ExecutionFunction(
            function_type="stop_loss_take_profit",
            timeframe="15min",
            parameters={},
        ),
        status=TradePlanStatus.AWAITING_ENTRY,
    )


@pytest.fixture
def temp_state_file() -> Path:
    """Temporary state file for testing."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".json") as f:
        temp_path = Path(f.name)
    
    yield temp_path
    
    # Cleanup
    if temp_path.exists():
        temp_path.unlink()