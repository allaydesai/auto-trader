"""Constants for the wizard interface."""

from typing import Dict, List

# Risk category configurations
RISK_CATEGORIES: Dict[str, str] = {
    "small": "Small (1% risk)",
    "normal": "Normal (2% risk)", 
    "large": "Large (3% risk)"
}

# Risk category choices (just the keys for prompts)
RISK_CATEGORY_CHOICES: List[str] = list(RISK_CATEGORIES.keys())

# Risk category help text for CLI commands
RISK_CATEGORY_HELP_TEXT: str = "Risk category: small (1%), normal (2%), large (3%)"

# Default risk category
DEFAULT_RISK_CATEGORY: str = "normal"

# Available timeframes for execution functions
AVAILABLE_TIMEFRAMES: List[str] = ["1min", "5min", "15min", "30min", "60min"]

# Default timeframe selection
DEFAULT_TIMEFRAME: str = "15min"

# Execution function types
ENTRY_FUNCTION_TYPES: List[str] = ["close_above", "close_below"]
EXIT_FUNCTION_TYPES: List[str] = ["stop_loss_take_profit", "trailing_stop"]

# Default execution function types
DEFAULT_ENTRY_FUNCTION_TYPE: str = "close_above"
DEFAULT_EXIT_FUNCTION_TYPE: str = "stop_loss_take_profit"

# Plan ID generation limits
MAX_PLANS_PER_DAY_PER_SYMBOL: int = 999

# Default paths
DEFAULT_TRADE_PLANS_DIR: str = "data/trade_plans"