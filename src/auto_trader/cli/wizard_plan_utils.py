"""Plan generation and saving utilities for wizard."""

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from ..logging_config import get_logger
from ..models import TradePlan

logger = get_logger("wizard_plan_utils", "cli")


def generate_plan_id(symbol: str, output_dir: Optional[Path] = None) -> str:
    """
    Generate unique plan ID in SYMBOL_YYYYMMDD_NNN format with duplicate handling.
    
    Args:
        symbol: Trading symbol
        output_dir: Directory to check for existing plan files
        
    Returns:
        Unique plan ID
        
    Raises:
        ValueError: If unable to generate unique ID after 999 attempts
    """
    date_str = datetime.utcnow().strftime("%Y%m%d")
    base_id = f"{symbol}_{date_str}"
    
    # Default output directory
    if output_dir is None:
        output_dir = Path("data/trade_plans")
    
    # Check for existing files and find next available number
    for sequence_num in range(1, 1000):  # Support up to 999 plans per day per symbol
        plan_id = f"{base_id}_{sequence_num:03d}"
        potential_file = output_dir / f"{plan_id}.yaml"
        
        if not potential_file.exists():
            logger.info("Plan ID generated", plan_id=plan_id, sequence_num=sequence_num)
            return plan_id
    
    # If we get here, we couldn't find a unique ID
    error_msg = f"Unable to generate unique plan ID for {symbol} on {date_str} - too many plans exist"
    logger.error("Plan ID generation failed", symbol=symbol, date=date_str)
    raise ValueError(error_msg)


def save_plan_to_yaml(
    plan_data: Dict[str, Any], 
    output_dir: Optional[Path] = None
) -> Path:
    """
    Save trade plan to YAML file.
    
    Args:
        plan_data: Complete plan data
        output_dir: Optional output directory
        
    Returns:
        Path to saved file
    """
    # Default output directory
    if output_dir is None:
        output_dir = Path("data/trade_plans")
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename
    plan_id = plan_data.get("plan_id", "unknown")
    filename = f"{plan_id}.yaml"
    output_path = output_dir / filename
    
    # Create TradePlan object for validation
    trade_plan = TradePlan(**plan_data)
    
    # Convert to YAML-compatible dict
    yaml_data = trade_plan.model_dump()
    
    # Write to file
    with open(output_path, "w") as f:
        yaml.dump(yaml_data, f, default_flow_style=False, sort_keys=False)
    
    logger.info("Plan saved to YAML", path=str(output_path))
    return output_path