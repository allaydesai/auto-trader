"""Built-in execution functions for the Auto-Trader system."""

from auto_trader.trade_engine.functions.close_above import CloseAboveFunction
from auto_trader.trade_engine.functions.close_below import CloseBelowFunction
from auto_trader.trade_engine.functions.trailing_stop import TrailingStopFunction

__all__ = ["CloseAboveFunction", "CloseBelowFunction", "TrailingStopFunction"]
