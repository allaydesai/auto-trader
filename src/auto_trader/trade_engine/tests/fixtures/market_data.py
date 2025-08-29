"""Market data fixtures for testing execution functions."""

import pytest
from decimal import Decimal
from datetime import datetime, UTC, timedelta
from typing import List

from auto_trader.models.market_data import BarData
from auto_trader.models.execution import ExecutionContext, PositionState
from auto_trader.models.enums import Timeframe


@pytest.fixture
def trending_up_bars() -> List[BarData]:
    """Generate bars showing upward trending market."""
    bars = []
    base_time = datetime.now(UTC)
    base_price = Decimal("100.00")
    
    for i in range(20):
        # Gradual uptrend with some noise
        price_trend = base_price + (Decimal(str(i)) * Decimal("0.50"))
        noise = Decimal(str((i % 3 - 1) * 0.10))  # -0.10, 0, +0.10 rotation
        
        open_price = price_trend + noise
        high_price = open_price + Decimal("0.30")
        low_price = open_price - Decimal("0.20")
        close_price = open_price + Decimal("0.15")  # Slightly bullish bias
        
        bars.append(BarData(
            symbol="AAPL",
            timestamp=base_time + timedelta(minutes=i),
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
            volume=1000000 + (i * 10000),  # Increasing volume
            bar_size="1min",
        ))
    
    return bars


@pytest.fixture
def trending_down_bars() -> List[BarData]:
    """Generate bars showing downward trending market."""
    bars = []
    base_time = datetime.now(UTC)
    base_price = Decimal("100.00")
    
    for i in range(20):
        # Gradual downtrend with some noise
        price_trend = base_price - (Decimal(str(i)) * Decimal("0.40"))
        noise = Decimal(str((i % 3 - 1) * 0.10))  # -0.10, 0, +0.10 rotation
        
        open_price = price_trend + noise
        high_price = open_price + Decimal("0.20")
        low_price = open_price - Decimal("0.30")  
        close_price = open_price - Decimal("0.15")  # Slightly bearish bias
        
        bars.append(BarData(
            symbol="AAPL",
            timestamp=base_time + timedelta(minutes=i),
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
            volume=1200000 - (i * 5000),  # Decreasing volume
            bar_size="1min",
        ))
    
    return bars


@pytest.fixture
def ranging_market_bars() -> List[BarData]:
    """Generate bars showing sideways/ranging market."""
    bars = []
    base_time = datetime.now(UTC)
    base_price = Decimal("100.00")
    
    for i in range(20):
        # Oscillate around base price
        cycle_position = (i % 8) / 8  # 8-bar cycle
        import math
        wave = math.sin(cycle_position * 2 * math.pi) * 0.5  # +/- 0.5 range
        
        open_price = (base_price + Decimal(str(wave))).quantize(Decimal("0.0001"))
        close_price = (open_price + Decimal(str(wave * 0.3))).quantize(Decimal("0.0001"))  # Some momentum
        
        # Ensure proper OHLC relationships
        high_price = max(open_price, close_price) + Decimal("0.25")
        low_price = min(open_price, close_price) - Decimal("0.25")
        
        bars.append(BarData(
            symbol="AAPL",
            timestamp=base_time + timedelta(minutes=i),
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
            volume=1000000 + int(abs(wave) * 100000),  # Volume varies with price movement
            bar_size="1min",
        ))
    
    return bars


@pytest.fixture
def volatile_market_bars() -> List[BarData]:
    """Generate bars showing high volatility market with gaps."""
    bars = []
    base_time = datetime.now(UTC)
    base_price = Decimal("100.00")
    
    for i in range(20):
        # High volatility with occasional gaps
        if i in [5, 12]:  # Create gaps at these positions
            gap_size = Decimal("2.00") if i == 5 else Decimal("-1.50")
            base_price += gap_size
        
        # Random-like price movement
        movement = Decimal(str(((i * 7) % 13 - 6) * 0.3))  # -1.8 to +1.8
        
        open_price = (base_price + movement).quantize(Decimal("0.0001"))
        close_price = (open_price + (movement * Decimal("0.5"))).quantize(Decimal("0.0001"))
        
        # Ensure proper OHLC relationships
        high_price = (max(open_price, close_price) + Decimal("1.00")).quantize(Decimal("0.0001"))
        low_price = (min(open_price, close_price) - Decimal("1.00")).quantize(Decimal("0.0001"))
        
        bars.append(BarData(
            symbol="AAPL",
            timestamp=base_time + timedelta(minutes=i),
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
            volume=int(500000 + abs(float(movement)) * 200000),  # High volume on big moves, convert to int
            bar_size="1min",
        ))
        
        base_price = close_price  # Update base for next bar
    
    return bars


@pytest.fixture
def low_volume_bars() -> List[BarData]:
    """Generate bars with very low volume."""
    bars = []
    base_time = datetime.now(UTC)
    base_price = Decimal("100.00")
    
    for i in range(10):
        open_price = base_price + Decimal(str((i % 3 - 1) * 0.05))
        high_price = open_price + Decimal("0.10")
        low_price = open_price - Decimal("0.10")
        close_price = open_price + Decimal("0.02")
        
        bars.append(BarData(
            symbol="AAPL",
            timestamp=base_time + timedelta(minutes=i),
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
            volume=100 + (i * 10),  # Very low volume
            bar_size="1min",
        ))
    
    return bars


@pytest.fixture
def gap_up_scenario() -> List[BarData]:
    """Generate scenario with significant gap up."""
    bars = []
    base_time = datetime.now(UTC)
    
    # Normal bar before gap
    bars.append(BarData(
        symbol="AAPL",
        timestamp=base_time,
        open_price=Decimal("100.00"),
        high_price=Decimal("100.50"),
        low_price=Decimal("99.80"),
        close_price=Decimal("100.20"),
        volume=1000000,
        bar_size="1min",
    ))
    
    # Gap up bar (opens significantly higher than previous close)
    bars.append(BarData(
        symbol="AAPL",
        timestamp=base_time + timedelta(minutes=1),
        open_price=Decimal("102.50"),  # 2.3% gap up
        high_price=Decimal("103.00"),
        low_price=Decimal("102.30"),
        close_price=Decimal("102.80"),
        volume=2000000,  # High volume on gap
        bar_size="1min",
    ))
    
    return bars


@pytest.fixture
def gap_down_scenario() -> List[BarData]:
    """Generate scenario with significant gap down."""
    bars = []
    base_time = datetime.now(UTC)
    
    # Normal bar before gap
    bars.append(BarData(
        symbol="AAPL",
        timestamp=base_time,
        open_price=Decimal("100.00"),
        high_price=Decimal("100.30"),
        low_price=Decimal("99.70"),
        close_price=Decimal("100.10"),
        volume=1000000,
        bar_size="1min",
    ))
    
    # Gap down bar (opens significantly lower than previous close)
    bars.append(BarData(
        symbol="AAPL",
        timestamp=base_time + timedelta(minutes=1),
        open_price=Decimal("97.50"),  # 2.6% gap down
        high_price=Decimal("97.80"),
        low_price=Decimal("97.20"),
        close_price=Decimal("97.40"),
        volume=3000000,  # Very high volume on gap down
        bar_size="1min",
    ))
    
    return bars


@pytest.fixture
def limit_up_scenario() -> List[BarData]:
    """Generate scenario simulating limit up move."""
    bars = []
    base_time = datetime.now(UTC)
    base_price = Decimal("100.00")
    
    # Build up with increasing momentum
    for i in range(5):
        price_increase = Decimal(str(i * 0.5))
        bars.append(BarData(
            symbol="AAPL",
            timestamp=base_time + timedelta(minutes=i),
            open_price=base_price + price_increase,
            high_price=base_price + price_increase + Decimal("0.30"),
            low_price=base_price + price_increase - Decimal("0.10"),
            close_price=base_price + price_increase + Decimal("0.25"),
            volume=1000000 * (i + 1),
            bar_size="1min",
        ))
    
    # Limit up bar - massive move
    bars.append(BarData(
        symbol="AAPL",
        timestamp=base_time + timedelta(minutes=5),
        open_price=Decimal("102.25"),
        high_price=Decimal("115.00"),  # 15% move up
        low_price=Decimal("102.25"),
        close_price=Decimal("115.00"),  # Locked at high
        volume=10000000,  # Extreme volume
        bar_size="1min",
    ))
    
    return bars


@pytest.fixture
def invalid_data_bars() -> List[BarData]:
    """Generate bars with data quality issues."""
    bars = []
    base_time = datetime.now(UTC)
    
    # Normal bar
    bars.append(BarData(
        symbol="AAPL",
        timestamp=base_time,
        open_price=Decimal("100.00"),
        high_price=Decimal("100.50"),
        low_price=Decimal("99.80"),
        close_price=Decimal("100.20"),
        volume=1000000,
        bar_size="1min",
    ))
    
    # Bar with high < low (invalid) - Note: This will be caught by validation
    try:
        invalid_bar = BarData(
            symbol="AAPL",
            timestamp=base_time + timedelta(minutes=1),
            open_price=Decimal("100.20"),
            high_price=Decimal("99.50"),  # Invalid: high < low
            low_price=Decimal("100.80"),  # Invalid: low > high  
            close_price=Decimal("100.00"),
            volume=1000000,
            bar_size="1min",
        )
        bars.append(invalid_bar)
    except ValueError:
        # Create a bar that will pass validation but represent invalid data conceptually
        # We'll use this to test edge case detection logic rather than pydantic validation
        bars.append(BarData(
            symbol="AAPL",
            timestamp=base_time + timedelta(minutes=1),
            open_price=Decimal("100.20"),
            high_price=Decimal("100.80"),  # Valid: high >= max(open, close)
            low_price=Decimal("99.50"),   # Valid: low <= min(open, close)
            close_price=Decimal("100.00"),
            volume=1000000,
            bar_size="1min",
        ))
    
    return bars


@pytest.fixture
def sample_position_long() -> PositionState:
    """Create sample long position for testing."""
    return PositionState(
        symbol="AAPL",
        quantity=100,
        entry_price=Decimal("100.00"),
        current_price=Decimal("102.00"),
        stop_loss=Decimal("98.00"),
        take_profit=Decimal("105.00"),
        opened_at=datetime.now(UTC),
    )


@pytest.fixture
def sample_position_short() -> PositionState:
    """Create sample short position for testing."""
    return PositionState(
        symbol="AAPL",
        quantity=-100,  # Negative for short position
        entry_price=Decimal("100.00"),
        current_price=Decimal("98.00"),
        stop_loss=Decimal("102.00"),
        take_profit=Decimal("95.00"),
        opened_at=datetime.now(UTC),
    )


def create_execution_context(
    current_bar: BarData,
    historical_bars: List[BarData],
    position_state: PositionState = None,
    **params
) -> ExecutionContext:
    """Helper function to create execution context."""
    return ExecutionContext(
        symbol=current_bar.symbol,
        timeframe=Timeframe.ONE_MIN,
        current_bar=current_bar,
        historical_bars=historical_bars,
        trade_plan_params=params,
        position_state=position_state,
        account_balance=Decimal("10000"),
        timestamp=datetime.now(UTC),
    )