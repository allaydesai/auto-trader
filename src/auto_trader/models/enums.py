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


class TimeInForce(str, Enum):
    """Order time in force definitions."""
    DAY = "DAY"
    GTC = "GTC"  # Good Till Cancelled
    IOC = "IOC"  # Immediate or Cancel
    FOK = "FOK"  # Fill or Kill