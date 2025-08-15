"""File watching utilities for CLI commands."""

import time
from pathlib import Path
from datetime import datetime
from typing import Optional

from rich.console import Console
from rich.panel import Panel

from ..utils import FileWatcher, FileWatchEventType
from ..logging_config import get_logger

console = Console()
logger = get_logger("cli.watch", "cli")


def start_file_watching(watch_directory: Path, verbose: bool) -> None:
    """Start file watching with rich progress indicators."""
    console.print(
        Panel(
            f"[blue]🔄 Starting file watcher for: {watch_directory}[/blue]\n"
            "Press 'Ctrl+C' to stop watching...",
            title="File Watching",
            border_style="blue",
        )
    )
    
    def validation_callback(file_path: Path, event_type: FileWatchEventType) -> None:
        """Handle validation callbacks with rich formatting."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        if event_type == FileWatchEventType.CREATED:
            console.print(f"[green]{timestamp} ✅ File created:[/green] {file_path.name}")
        elif event_type == FileWatchEventType.MODIFIED:
            console.print(f"[yellow]{timestamp} 🔄 File modified:[/yellow] {file_path.name}")
        elif event_type == FileWatchEventType.DELETED:
            console.print(f"[red]{timestamp} 🗑️  File deleted:[/red] {file_path.name}")
            
        if verbose and event_type != FileWatchEventType.DELETED:
            console.print(f"[dim]    Validating {file_path.name}...[/dim]")
    
    # Create file watcher
    watcher = FileWatcher(
        watch_directory=watch_directory,
        validation_callback=validation_callback,
        debounce_delay=0.5
    )
    
    try:
        if watcher.start():
            console.print("[green]✓ File watcher started successfully[/green]")
            
            # Run until interrupted
            while True:
                time.sleep(1.0)
                
        else:
            console.print("[red]❌ Failed to start file watcher[/red]")
            
    except KeyboardInterrupt:
        console.print("\n[yellow]File watching stopped by user[/yellow]")
    finally:
        watcher.stop()
        
        # Show final statistics
        stats = watcher.get_stats()
        console.print(
            Panel(
                f"[blue]File Watching Statistics[/blue]\n"
                f"Events processed: {stats['events_processed']}\n"
                f"Validation errors: {stats['validation_errors']}\n"
                f"Watch duration: Active",
                title="Summary",
                border_style="blue",
            )
        )