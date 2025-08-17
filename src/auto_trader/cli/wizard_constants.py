"""Constants for the wizard interface."""

from typing import Dict, List

# Risk category configurations
RISK_CATEGORIES: Dict[str, str] = {
    "small": "Small (1% risk)",
    "normal": "Normal (2% risk)", 
    "large": "Large (3% risk)"
}

# Available timeframes for execution functions
AVAILABLE_TIMEFRAMES: List[str] = ["1min", "5min", "15min", "30min", "60min"]

# Default timeframe selection
DEFAULT_TIMEFRAME: str = "15min"

# Plan ID generation limits
MAX_PLANS_PER_DAY_PER_SYMBOL: int = 999

# Default paths
DEFAULT_TRADE_PLANS_DIR: str = "data/trade_plans"