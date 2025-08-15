"""File system monitoring for automatic trade plan validation."""

import asyncio
import time
from pathlib import Path
from typing import Callable, Optional, Set, Dict
from dataclasses import dataclass
from enum import Enum

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent, FileCreatedEvent, FileDeletedEvent
from loguru import logger

from ..models import TradePlanLoader, ValidationEngine


class FileWatchEventType(Enum):
    """File watch event types."""
    CREATED = "created"
    MODIFIED = "modified"
    DELETED = "deleted"


@dataclass
class FileWatchEvent:
    """File watch event data."""
    event_type: FileWatchEventType
    file_path: Path
    timestamp: float


class TradeplanFileHandler(FileSystemEventHandler):
    """File system event handler for trade plan files."""
    
    def __init__(self, callback: Callable[[FileWatchEvent], None], debounce_delay: float = 0.5):
        """
        Initialize file handler.
        
        Args:
            callback: Function to call when file events occur
            debounce_delay: Minimum time between processing same file events (seconds)
        """
        super().__init__()
        self.callback = callback
        self.debounce_delay = debounce_delay
        self._pending_events: Dict[str, FileWatchEvent] = {}
        self._debounce_tasks: Dict[str, asyncio.Task] = {}
        
    def on_created(self, event):
        """Handle file creation events."""
        if not event.is_directory and self._is_yaml_file(event.src_path):
            self._queue_event(FileWatchEvent(
                FileWatchEventType.CREATED,
                Path(event.src_path),
                time.time()
            ))
            
    def on_modified(self, event):
        """Handle file modification events.""" 
        if not event.is_directory and self._is_yaml_file(event.src_path):
            self._queue_event(FileWatchEvent(
                FileWatchEventType.MODIFIED,
                Path(event.src_path),
                time.time()
            ))
            
    def on_deleted(self, event):
        """Handle file deletion events."""
        if not event.is_directory and self._is_yaml_file(event.src_path):
            self._queue_event(FileWatchEvent(
                FileWatchEventType.DELETED,
                Path(event.src_path),
                time.time()
            ))
            
    def _is_yaml_file(self, file_path: str) -> bool:
        """Check if file is a YAML file we should monitor."""
        path = Path(file_path)
        
        # Only monitor .yaml and .yml files
        if path.suffix.lower() not in ['.yaml', '.yml']:
            return False
            
        # Exclude temporary, backup, and hidden files
        name = path.name.lower()
        if name.startswith('.') or name.endswith('.tmp') or name.endswith('.bak'):
            return False
            
        return True
        
    def _queue_event(self, event: FileWatchEvent):
        """Queue event for debounced processing."""
        key = str(event.file_path)
        
        # Cancel existing debounce task for this file
        if key in self._debounce_tasks:
            self._debounce_tasks[key].cancel()
            
        # Store the event
        self._pending_events[key] = event
        
        # Schedule debounced processing
        try:
            loop = asyncio.get_running_loop()
            self._debounce_tasks[key] = loop.call_later(
                self.debounce_delay,
                self._process_debounced_event,
                key
            )
        except RuntimeError:
            # No running loop - process immediately
            self._process_debounced_event(key)
        
    def _process_debounced_event(self, key: str):
        """Process debounced event after delay."""
        if key in self._pending_events:
            event = self._pending_events.pop(key)
            self._debounce_tasks.pop(key, None)
            
            try:
                self.callback(event)
            except Exception as e:
                logger.error(f"Error processing file event: {e}", file_path=key)


class FileWatcher:
    """File system watcher for trade plan files with automatic validation."""
    
    def __init__(
        self,
        watch_directory: Optional[Path] = None,
        validation_callback: Optional[Callable[[Path, FileWatchEventType], None]] = None,
        debounce_delay: float = 0.5
    ):
        """
        Initialize file watcher.
        
        Args:
            watch_directory: Directory to monitor (defaults to data/trade_plans/)
            validation_callback: Callback for validation notifications
            debounce_delay: Minimum delay between processing same file events
        """
        self.watch_directory = watch_directory or Path("data/trade_plans")
        self.validation_callback = validation_callback
        self.debounce_delay = debounce_delay
        
        # Initialize components
        self.trade_plan_loader = TradePlanLoader(self.watch_directory)
        self.validation_engine = ValidationEngine()
        
        # Watchdog components
        self.observer: Optional[Observer] = None
        self.event_handler: Optional[TradeplanFileHandler] = None
        
        # Statistics
        self.events_processed = 0
        self.validation_errors = 0
        self.last_validation_time: Optional[float] = None
        
    def start(self) -> bool:
        """
        Start file watching.
        
        Returns:
            True if watcher started successfully, False otherwise
        """
        try:
            # Ensure watch directory exists
            if not self.watch_directory.exists():
                logger.warning(f"Watch directory does not exist: {self.watch_directory}")
                self.watch_directory.mkdir(parents=True, exist_ok=True)
                
            # Create event handler
            self.event_handler = TradeplanFileHandler(
                callback=self._handle_file_event,
                debounce_delay=self.debounce_delay
            )
            
            # Create observer
            self.observer = Observer()
            self.observer.schedule(
                self.event_handler,
                path=str(self.watch_directory),
                recursive=True
            )
            
            # Start observer
            self.observer.start()
            
            logger.info(
                "File watcher started",
                watch_directory=str(self.watch_directory),
                debounce_delay=self.debounce_delay
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start file watcher: {e}")
            return False
            
    def stop(self):
        """Stop file watching."""
        if self.observer and self.observer.is_alive():
            self.observer.stop()
            self.observer.join(timeout=5.0)
            
        logger.info("File watcher stopped")
        
    def _handle_file_event(self, event: FileWatchEvent):
        """Handle file system events."""
        self.events_processed += 1
        
        logger.debug(
            f"Processing file event: {event.event_type.value}",
            file_path=str(event.file_path),
            timestamp=event.timestamp
        )
        
        # Perform validation based on event type
        try:
            if event.event_type in [FileWatchEventType.CREATED, FileWatchEventType.MODIFIED]:
                self._validate_file(event.file_path)
            elif event.event_type == FileWatchEventType.DELETED:
                self._handle_file_deletion(event.file_path)
                
            # Notify callback if provided
            if self.validation_callback:
                self.validation_callback(event.file_path, event.event_type)
                
        except Exception as e:
            self.validation_errors += 1
            logger.error(f"Error handling file event: {e}", file_path=str(event.file_path))
            
        self.last_validation_time = time.time()
        
    def _validate_file(self, file_path: Path):
        """Validate a single trade plan file."""
        if not file_path.exists():
            logger.warning(f"File no longer exists: {file_path}")
            return
            
        try:
            # Use ValidationEngine to validate the file
            results = self.validation_engine.validate_file(file_path)
            
            if results.is_valid:
                logger.info(f"✅ File validation passed: {file_path.name}")
            else:
                logger.warning(f"❌ File validation failed: {file_path.name}")
                for error in results.errors:
                    logger.warning(f"  - {error}")
                    
        except Exception as e:
            logger.error(f"Failed to validate file {file_path}: {e}")
            
    def _handle_file_deletion(self, file_path: Path):
        """Handle file deletion events."""
        logger.info(f"🗑️  File deleted: {file_path.name}")
        
        # Clear any cached data for this file
        self.trade_plan_loader.clear_cache_for_file(file_path)
        
    def get_stats(self) -> Dict[str, any]:
        """Get file watcher statistics."""
        return {
            "watch_directory": str(self.watch_directory),
            "events_processed": self.events_processed,
            "validation_errors": self.validation_errors,
            "last_validation_time": self.last_validation_time,
            "is_running": self.observer.is_alive() if self.observer else False,
            "debounce_delay": self.debounce_delay,
        }
        
    def force_validation(self):
        """Force validation of all files in watch directory."""
        logger.info("Forcing validation of all trade plan files")
        
        yaml_files = list(self.watch_directory.glob("*.yaml")) + list(self.watch_directory.glob("*.yml"))
        
        for file_path in yaml_files:
            if self._is_valid_plan_file(file_path):
                self._validate_file(file_path)
                
    def _is_valid_plan_file(self, file_path: Path) -> bool:
        """Check if file should be validated as a trade plan."""
        name = file_path.name.lower()
        
        # Exclude template and example files
        if 'template' in name or 'example' in name:
            return False
            
        # Exclude temporary and backup files
        if name.startswith('.') or name.endswith('.tmp') or name.endswith('.bak'):
            return False
            
        return True


class FileWatchConfig:
    """Configuration for file watching functionality."""
    
    def __init__(
        self,
        watch_directory: Optional[Path] = None,
        debounce_delay: float = 0.5,
        enable_notifications: bool = True,
        auto_start: bool = False
    ):
        """
        Initialize file watch configuration.
        
        Args:
            watch_directory: Directory to monitor
            debounce_delay: Delay between events for same file (seconds)
            enable_notifications: Whether to enable progress notifications
            auto_start: Whether to auto-start watching on initialization
        """
        self.watch_directory = watch_directory or Path("data/trade_plans")
        self.debounce_delay = debounce_delay
        self.enable_notifications = enable_notifications
        self.auto_start = auto_start
        
    @classmethod
    def from_settings(cls, settings_dict: Dict[str, any]) -> "FileWatchConfig":
        """Create configuration from settings dictionary."""
        return cls(
            watch_directory=Path(settings_dict.get("watch_directory", "data/trade_plans")),
            debounce_delay=settings_dict.get("debounce_delay", 0.5),
            enable_notifications=settings_dict.get("enable_notifications", True),
            auto_start=settings_dict.get("auto_start", False)
        )