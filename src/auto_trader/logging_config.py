"""Enhanced logging configuration with loguru."""

import sys
import uuid
from contextvars import ContextVar
from pathlib import Path
from typing import Any, Dict, Optional

from loguru import logger

# Context variables for correlation tracking
correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)
service_context: ContextVar[Optional[str]] = ContextVar("service_context", default=None)
trade_context: ContextVar[Optional[str]] = ContextVar("trade_context", default=None)


class LoggerConfig:
    """Enhanced logging configuration manager."""
    
    def __init__(self, logs_dir: Path = Path("logs"), log_level: str = "INFO"):
        """Initialize logger configuration."""
        self.logs_dir = logs_dir
        self.log_level = log_level
        self._configured = False
        
    def configure_logging(self) -> None:
        """Configure loguru with structured JSON logging and multiple handlers."""
        if self._configured:
            return
            
        # Create logs directory if it doesn't exist
        self.logs_dir.mkdir(exist_ok=True)
        
        # Remove default handler
        logger.remove()
        
        # Console handler for development
        logger.add(
            sys.stderr,
            level=self.log_level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
                   "<level>{level: <8}</level> | "
                   "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
                   "<level>{message}</level>",
            colorize=True,
            filter=self._add_context_filter
        )
        
        # System log - general application events
        logger.add(
            self.logs_dir / "system.log",
            level=self.log_level,
            rotation="1 day",
            retention="30 days",
            compression="gz",
            format=self._json_format,
            serialize=True,
            filter=lambda record: not any(
                tag in record["extra"].get("category", "") 
                for tag in ["trade", "risk", "cli"]
            )
        )
        
        # Trade log - all trading-related events
        logger.add(
            self.logs_dir / "trades.log",
            level="INFO",
            rotation="1 day", 
            retention="30 days",
            compression="gz",
            format=self._json_format,
            serialize=True,
            filter=lambda record: record["extra"].get("category") == "trade"
        )
        
        # Risk log - risk management and validation events
        logger.add(
            self.logs_dir / "risk.log",
            level="INFO",
            rotation="1 day",
            retention="30 days", 
            compression="gz",
            format=self._json_format,
            serialize=True,
            filter=lambda record: record["extra"].get("category") == "risk"
        )
        
        # CLI log - command-line interface events
        logger.add(
            self.logs_dir / "cli.log",
            level="INFO",
            rotation="1 day",
            retention="30 days",
            compression="gz", 
            format=self._json_format,
            serialize=True,
            filter=lambda record: record["extra"].get("category") == "cli"
        )
        
        self._configured = True
        logger.info("Logging configuration initialized", category="system")
    
    def _add_context_filter(self, record: Dict[str, Any]) -> bool:
        """Add context information to log records."""
        # Add correlation ID if available
        if correlation_id.get():
            record["extra"]["correlation_id"] = correlation_id.get()
            
        # Add service context if available  
        if service_context.get():
            record["extra"]["service_context"] = service_context.get()
            
        # Add trade context if available
        if trade_context.get():
            record["extra"]["trade_context"] = trade_context.get()
            
        return True
    
    def _json_format(self, record: Dict[str, Any]) -> str:
        """Custom JSON format for structured logging."""
        return (
            "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
            "{level} | "
            "{name}:{function}:{line} | "
            "{message}"
        )


class ContextualLogger:
    """Logger wrapper with context management."""
    
    def __init__(self, name: str, category: str = "system"):
        """Initialize contextual logger."""
        self.name = name
        self.category = category
        self.logger = logger.bind(name=name, category=category)
    
    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message with context."""
        self.logger.debug(message, **kwargs)
    
    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message with context."""
        self.logger.info(message, **kwargs)
    
    def warning(self, message: str, **kwargs: Any) -> None:
        """Log warning message with context."""
        self.logger.warning(message, **kwargs)
    
    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message with context."""
        self.logger.error(message, **kwargs)
    
    def critical(self, message: str, **kwargs: Any) -> None:
        """Log critical message with context."""
        self.logger.critical(message, **kwargs)


class APIRequestLogger:
    """Logger for external API requests and responses."""
    
    def __init__(self):
        """Initialize API request logger."""
        self.logger = ContextualLogger("api", "system")
    
    def log_request(self, method: str, url: str, headers: Optional[Dict[str, str]] = None, 
                   body: Optional[str] = None) -> str:
        """Log outgoing API request and return correlation ID."""
        request_id = str(uuid.uuid4())
        correlation_id.set(request_id)
        
        # Filter sensitive headers
        safe_headers = self._filter_sensitive_headers(headers or {})
        
        self.logger.info(
            "API request sent",
            request_id=request_id,
            method=method,
            url=url,
            headers=safe_headers,
            body_length=len(body) if body else 0
        )
        
        return request_id
    
    def log_response(self, request_id: str, status_code: int, 
                    response_time_ms: float, body: Optional[str] = None) -> None:
        """Log API response."""
        correlation_id.set(request_id)
        
        self.logger.info(
            "API response received",
            request_id=request_id,
            status_code=status_code,
            response_time_ms=response_time_ms,
            body_length=len(body) if body else 0,
            success=200 <= status_code < 300
        )
    
    def log_error(self, request_id: str, error: Exception) -> None:
        """Log API request error."""
        correlation_id.set(request_id)
        
        self.logger.error(
            "API request failed",
            request_id=request_id,
            error_type=type(error).__name__,
            error_message=str(error)
        )
    
    def _filter_sensitive_headers(self, headers: Dict[str, str]) -> Dict[str, str]:
        """Filter sensitive information from headers."""
        sensitive_keys = {"authorization", "x-api-key", "token", "secret"}
        
        return {
            key: "***REDACTED***" if key.lower() in sensitive_keys else value
            for key, value in headers.items()
        }


def get_logger(name: str, category: str = "system") -> ContextualLogger:
    """Get a contextual logger instance."""
    return ContextualLogger(name, category)


def set_correlation_id(request_id: Optional[str] = None) -> str:
    """Set correlation ID for request tracking."""
    if request_id is None:
        request_id = str(uuid.uuid4())
    correlation_id.set(request_id)
    return request_id


def set_service_context(module: str, function: str) -> None:
    """Set service context for logging."""
    service_context.set(f"{module}.{function}")


def set_trade_context(symbol: str, trade_id: Optional[str] = None) -> None:
    """Set trade context for logging."""
    context = symbol
    if trade_id:
        context = f"{symbol}:{trade_id}"
    trade_context.set(context)


def clear_context() -> None:
    """Clear all logging context."""
    correlation_id.set(None)
    service_context.set(None)
    trade_context.set(None)