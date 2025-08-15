"""Trade plan loader for YAML file loading and management."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Any
import yaml

from loguru import logger
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from .trade_plan import TradePlan, TradePlanStatus
from .validation_engine import ValidationEngine
from .error_reporting import ValidationReporter


class TradePlanFileWatcher(FileSystemEventHandler):
    """File system event handler for watching trade plan file changes."""
    
    def __init__(self, loader: TradePlanLoader) -> None:
        """Initialize file watcher with reference to loader."""
        self.loader = loader
        super().__init__()
    
    def on_modified(self, event) -> None:
        """Handle file modification events."""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        if file_path.suffix.lower() in {'.yaml', '.yml'}:
            logger.info(f"Trade plan file modified: {file_path}")
            # Trigger reload in background
            asyncio.create_task(self.loader._reload_file(file_path))
    
    def on_created(self, event) -> None:
        """Handle file creation events."""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        if file_path.suffix.lower() in {'.yaml', '.yml'}:
            logger.info(f"New trade plan file created: {file_path}")
            asyncio.create_task(self.loader._reload_file(file_path))
    
    def on_deleted(self, event) -> None:
        """Handle file deletion events."""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        if file_path.suffix.lower() in {'.yaml', '.yml'}:
            logger.info(f"Trade plan file deleted: {file_path}")
            # Remove from loaded plans
            self.loader._remove_plans_from_file(file_path)


class TradePlanLoader:
    """Loads and manages trade plans from YAML files."""
    
    def __init__(self, plans_directory: Optional[Path] = None) -> None:
        """
        Initialize trade plan loader.
        
        Args:
            plans_directory: Directory containing trade plan YAML files.
                           Defaults to data/trade_plans/
        """
        if plans_directory is None:
            # Default to project plans directory
            project_root = Path(__file__).parents[3]  # Go up from src/auto_trader/models/
            plans_directory = project_root / "data" / "trade_plans"
        
        self.plans_directory = Path(plans_directory)
        self.validation_engine = ValidationEngine()
        self.reporter = ValidationReporter()
        
        # In-memory storage
        self._loaded_plans: Dict[str, TradePlan] = {}
        self._file_to_plans: Dict[Path, Set[str]] = {}
        self._plan_to_file: Dict[str, Path] = {}
        
        # File watching
        self._observer: Optional[Observer] = None
        self._watcher: Optional[TradePlanFileWatcher] = None
        self._watching = False
    
    def load_all_plans(self, validate: bool = True) -> Dict[str, TradePlan]:
        """
        Load all trade plans from the plans directory.
        
        Args:
            validate: Whether to validate plans during loading
            
        Returns:
            Dictionary mapping plan IDs to TradePlan instances
        """
        self._clear_loaded_plans()
        
        if not self.plans_directory.exists():
            logger.warning(f"Plans directory not found: {self.plans_directory}")
            return {}
        
        yaml_files = list(self.plans_directory.glob("*.yaml")) + list(self.plans_directory.glob("*.yml"))
        
        logger.info(f"Loading plans from {len(yaml_files)} files", directory=str(self.plans_directory))
        
        for yaml_file in yaml_files:
            # Skip template files
            if "template" in yaml_file.name.lower():
                continue
            
            try:
                self._load_file(yaml_file, validate)
            except Exception as e:
                logger.error(f"Failed to load plans from {yaml_file}", error=str(e))
                # Continue loading other files
                continue
        
        logger.info(
            f"Loaded {len(self._loaded_plans)} trade plans",
            plan_ids=list(self._loaded_plans.keys())
        )
        
        return self._loaded_plans.copy()
    
    def load_single_file(self, file_path: Path, validate: bool = True) -> List[TradePlan]:
        """
        Load trade plans from a single file.
        
        Args:
            file_path: Path to YAML file
            validate: Whether to validate plans during loading
            
        Returns:
            List of TradePlan instances from the file
        """
        return self._load_file(file_path, validate)
    
    def get_plan(self, plan_id: str) -> Optional[TradePlan]:
        """
        Get a specific trade plan by ID.
        
        Args:
            plan_id: Unique plan identifier
            
        Returns:
            TradePlan instance or None if not found
        """
        return self._loaded_plans.get(plan_id)
    
    def get_plans_by_status(self, status: TradePlanStatus) -> List[TradePlan]:
        """
        Get all plans with a specific status.
        
        Args:
            status: Status to filter by
            
        Returns:
            List of plans with the specified status
        """
        return [plan for plan in self._loaded_plans.values() if plan.status == status]
    
    def get_plans_by_symbol(self, symbol: str) -> List[TradePlan]:
        """
        Get all plans for a specific symbol.
        
        Args:
            symbol: Trading symbol to filter by
            
        Returns:
            List of plans for the specified symbol
        """
        return [plan for plan in self._loaded_plans.values() if plan.symbol == symbol]
    
    def update_plan_status(self, plan_id: str, new_status: TradePlanStatus) -> bool:
        """
        Update the status of a trade plan.
        
        Args:
            plan_id: Plan ID to update
            new_status: New status to set
            
        Returns:
            True if updated successfully, False if plan not found
        """
        if plan_id not in self._loaded_plans:
            logger.warning(f"Plan '{plan_id}' not found for status update")
            return False
        
        old_status = self._loaded_plans[plan_id].status
        
        # Create updated plan (plans are immutable)
        plan_data = self._loaded_plans[plan_id].model_dump()
        plan_data['status'] = new_status
        plan_data['updated_at'] = datetime.now(timezone.utc)
        
        try:
            updated_plan = TradePlan(**plan_data)
            self._loaded_plans[plan_id] = updated_plan
            
            logger.info(
                "Updated plan status",
                plan_id=plan_id,
                old_status=old_status,
                new_status=new_status
            )
            
            # Optionally persist to file
            self._persist_plan_update(plan_id, updated_plan)
            
            return True
            
        except Exception as e:
            logger.error("Failed to update plan status", plan_id=plan_id, error=str(e))
            return False
    
    def get_validation_report(self) -> str:
        """
        Get formatted validation report for all loaded plans.
        
        Returns:
            Formatted validation report
        """
        return self.reporter.format_summary_report()
    
    def start_file_watching(self) -> None:
        """Start watching the plans directory for file changes."""
        if self._watching:
            logger.warning("File watching already started")
            return
        
        if not self.plans_directory.exists():
            logger.warning(f"Cannot watch non-existent directory: {self.plans_directory}")
            return
        
        self._watcher = TradePlanFileWatcher(self)
        self._observer = Observer()
        self._observer.schedule(self._watcher, str(self.plans_directory), recursive=False)
        self._observer.start()
        self._watching = True
        
        logger.info(f"Started watching directory: {self.plans_directory}")
    
    def stop_file_watching(self) -> None:
        """Stop watching the plans directory."""
        if not self._watching:
            return
        
        if self._observer:
            self._observer.stop()
            self._observer.join()
            self._observer = None
        
        self._watcher = None
        self._watching = False
        
        logger.info("Stopped file watching")
    
    def get_loaded_plan_ids(self) -> Set[str]:
        """Get set of all loaded plan IDs."""
        return set(self._loaded_plans.keys())
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get statistics about loaded plans.
        
        Returns:
            Dictionary with plan statistics
        """
        if not self._loaded_plans:
            return {
                "total_plans": 0,
                "by_status": {},
                "by_symbol": {},
                "files_loaded": 0,
            }
        
        # Count by status
        status_counts = {}
        for plan in self._loaded_plans.values():
            status = plan.status.value if hasattr(plan.status, 'value') else str(plan.status)
            status_counts[status] = status_counts.get(status, 0) + 1
        
        # Count by symbol
        symbol_counts = {}
        for plan in self._loaded_plans.values():
            symbol = plan.symbol
            symbol_counts[symbol] = symbol_counts.get(symbol, 0) + 1
        
        return {
            "total_plans": len(self._loaded_plans),
            "by_status": status_counts,
            "by_symbol": symbol_counts,
            "files_loaded": len(self._file_to_plans),
        }
    
    def _load_file(self, file_path: Path, validate: bool) -> List[TradePlan]:
        """Load plans from a single file."""
        try:
            # Validate file first
            result = self.validation_engine.validate_file(file_path)
            self.reporter.add_result(result, file_path)
            
            if not result.is_valid:
                if validate:
                    logger.error(
                        f"Validation failed for {file_path}",
                        errors=[str(error) for error in result.errors]
                    )
                    return []
                else:
                    logger.warning(f"Loading file with validation warnings: {file_path}")
            
            # Parse YAML content
            content = file_path.read_text(encoding='utf-8')
            parsed_data = yaml.safe_load(content)
            
            if parsed_data is None:
                logger.warning(f"Empty YAML file: {file_path}")
                return []
            
            # Handle single plan or list of plans
            if isinstance(parsed_data, dict):
                plans_data = [parsed_data]
            elif isinstance(parsed_data, list):
                plans_data = parsed_data
            else:
                logger.error(f"Invalid YAML structure in {file_path}")
                return []
            
            # Create TradePlan instances
            loaded_plans = []
            plan_ids_in_file = set()
            
            for plan_data in plans_data:
                try:
                    trade_plan = TradePlan(**plan_data)
                    
                    # Check for duplicate plan IDs
                    if trade_plan.plan_id in self._loaded_plans:
                        logger.warning(
                            f"Duplicate plan ID '{trade_plan.plan_id}' in {file_path}",
                            existing_file=str(self._plan_to_file.get(trade_plan.plan_id))
                        )
                        continue
                    
                    # Store plan
                    self._loaded_plans[trade_plan.plan_id] = trade_plan
                    self._plan_to_file[trade_plan.plan_id] = file_path
                    plan_ids_in_file.add(trade_plan.plan_id)
                    loaded_plans.append(trade_plan)
                    
                except Exception as e:
                    logger.error(f"Failed to create plan from data in {file_path}", error=str(e))
                    continue
            
            # Track file to plans mapping
            if plan_ids_in_file:
                self._file_to_plans[file_path] = plan_ids_in_file
            
            logger.info(
                f"Loaded {len(loaded_plans)} plans from {file_path}",
                plan_ids=list(plan_ids_in_file)
            )
            
            return loaded_plans
            
        except Exception as e:
            logger.error(f"Failed to load file {file_path}", error=str(e))
            return []
    
    async def _reload_file(self, file_path: Path) -> None:
        """Reload a specific file (called by file watcher)."""
        logger.info(f"Reloading file: {file_path}")
        
        # Remove existing plans from this file
        self._remove_plans_from_file(file_path)
        
        # Reload the file
        try:
            self._load_file(file_path, validate=True)
        except Exception as e:
            logger.error(f"Failed to reload file {file_path}", error=str(e))
    
    def _remove_plans_from_file(self, file_path: Path) -> None:
        """Remove all plans that came from a specific file."""
        if file_path not in self._file_to_plans:
            return
        
        plan_ids_to_remove = self._file_to_plans[file_path].copy()
        
        for plan_id in plan_ids_to_remove:
            if plan_id in self._loaded_plans:
                del self._loaded_plans[plan_id]
            if plan_id in self._plan_to_file:
                del self._plan_to_file[plan_id]
        
        del self._file_to_plans[file_path]
        
        logger.info(
            f"Removed {len(plan_ids_to_remove)} plans from {file_path}",
            plan_ids=list(plan_ids_to_remove)
        )
    
    def _persist_plan_update(self, plan_id: str, updated_plan: TradePlan) -> None:
        """Persist plan update back to file (optional feature)."""
        # This could be implemented to update the YAML file
        # For now, just log that an update occurred
        file_path = self._plan_to_file.get(plan_id)
        logger.debug(
            "Plan update not persisted to file",
            plan_id=plan_id,
            file_path=str(file_path) if file_path else None,
            reason="File persistence not implemented"
        )
    
    def _clear_loaded_plans(self) -> None:
        """Clear all loaded plans and mappings."""
        self._loaded_plans.clear()
        self._file_to_plans.clear()
        self._plan_to_file.clear()
        self.validation_engine.reset_plan_ids()
        self.reporter.clear()
    
    def __enter__(self):
        """Context manager entry."""
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup file watching."""
        self.stop_file_watching()