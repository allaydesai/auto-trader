# Order execution enums for IBKR integration
from enum import Enum


class OrderType(str, Enum):
    """Order type definitions matching IBKR order types."""
    MARKET = "MKT"
    LIMIT = "LMT"
    STOP = "STP"
    STOP_LIMIT = "STP LMT"
    TRAILING_STOP = "TRAIL"
    MARKET_IF_TOUCHED = "MIT"
    LIMIT_IF_TOUCHED = "LIT"


class OrderSide(str, Enum):
    """Order side definitions."""
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(str, Enum):
    """Order status lifecycle matching IBKR status values."""
    PENDING = "PendingSubmit"
    SUBMITTED = "Submitted"
    PRE_SUBMITTED = "PreSubmitted"
    PARTIALLY_FILLED = "PartiallyFilled"
    FILLED = "Filled"
    CANCELLED = "Cancelled"
    REJECTED = "Rejected"
    EXPIRED = "Expired"
    INACTIVE = "Inactive"


class OrderAction(str, Enum):
    """Order management actions."""
    NEW = "NEW"
    MODIFY = "MODIFY"
    CANCEL = "CANCEL"


class BracketOrderType(str, Enum):
    """Bracket order component types."""
    PARENT = "PARENT"
    STOP_LOSS = "STOP_LOSS"
    TAKE_PROFIT = "TAKE_PROFIT"
    TRAILING_STOP = "TRAILING_STOP"


# RiskCategory is imported from trade_plan.py to avoid duplication


class ExecutionAction(str, Enum):
    """Actions that can be taken by execution functions."""
    NONE = "NONE"  # No action required
    ENTER_LONG = "ENTER_LONG"  # Open long position
    ENTER_SHORT = "ENTER_SHORT"  # Open short position
    EXIT = "EXIT"  # Close position
    MODIFY_STOP = "MODIFY_STOP"  # Modify stop-loss


class ConfidenceLevel(str, Enum):
    """Confidence levels for execution signals."""
    LOW = "LOW"  # 0.0 - 0.33
    MEDIUM = "MEDIUM"  # 0.34 - 0.66
    HIGH = "HIGH"  # 0.67 - 1.0


class Timeframe(str, Enum):
    """Supported timeframes for bar data and execution."""
    ONE_MIN = "1min"
    FIVE_MIN = "5min"
    FIFTEEN_MIN = "15min"
    THIRTY_MIN = "30min"
    ONE_HOUR = "1hour"
    FOUR_HOUR = "4hour"
    ONE_DAY = "1day"


class TimeInForce(str, Enum):
    """Order time in force definitions."""
    DAY = "DAY"
    GTC = "GTC"  # Good Till Cancelled
    IOC = "IOC"  # Immediate or Cancel
    FOK = "FOK"  # Fill or Kill