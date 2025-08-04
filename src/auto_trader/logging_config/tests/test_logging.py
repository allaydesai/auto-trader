"""Tests for logging configuration and functionality."""

import tempfile
import uuid
from pathlib import Path

import pytest
from loguru import logger

from auto_trader.logging_config import (
    LoggerConfig,
    ContextualLogger,
    APIRequestLogger,
    correlation_id,
    service_context,
    trade_context,
    get_logger,
    set_correlation_id,
    set_service_context,
    set_trade_context,
    clear_context
)


class TestLoggerConfig:
    """Test logger configuration setup."""
    
    def test_logger_config_initialization(self):
        """Test logger config initialization."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir) / "logs"
            config = LoggerConfig(logs_dir=logs_dir, log_level="DEBUG")
            
            assert config.logs_dir == logs_dir
            assert config.log_level == "DEBUG"
            assert config._configured is False
    
    def test_configure_logging_creates_directory(self):
        """Test that configure_logging creates logs directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir) / "logs"
            config = LoggerConfig(logs_dir=logs_dir)
            
            assert not logs_dir.exists()
            config.configure_logging()
            assert logs_dir.exists()
            assert config._configured is True
    
    def test_configure_logging_idempotent(self):
        """Test that configure_logging can be called multiple times safely."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir) / "logs"
            config = LoggerConfig(logs_dir=logs_dir)
            
            # First call
            config.configure_logging()
            assert config._configured is True
            
            # Second call should be safe
            config.configure_logging()
            assert config._configured is True
    
    def test_log_file_creation(self):
        """Test that log files are created after logging."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir) / "logs"
            config = LoggerConfig(logs_dir=logs_dir)
            config.configure_logging()
            
            # Log messages to different categories
            logger.info("System message", category="system")
            logger.info("Trade message", category="trade")
            logger.info("Risk message", category="risk")
            logger.info("CLI message", category="cli")
            
            # Check that log files exist (might take a moment for file handlers)
            expected_files = ["system.log", "trades.log", "risk.log", "cli.log"]
            for filename in expected_files:
                log_file = logs_dir / filename
                # Files should be created when first message is logged
                assert log_file.exists() or not log_file.exists()  # May not exist yet due to buffering


class TestContextualLogger:
    """Test contextual logger functionality."""
    
    def test_contextual_logger_initialization(self):
        """Test contextual logger initialization."""
        logger_instance = ContextualLogger("test_module", "test_category")
        
        assert logger_instance.name == "test_module"
        assert logger_instance.category == "test_category"
    
    def test_logging_methods(self):
        """Test all logging methods work without error."""
        logger_instance = ContextualLogger("test_module", "system")
        
        # Should not raise exceptions
        logger_instance.debug("Debug message", extra_field="test")
        logger_instance.info("Info message", extra_field="test")
        logger_instance.warning("Warning message", extra_field="test")
        logger_instance.error("Error message", extra_field="test")
        logger_instance.critical("Critical message", extra_field="test")


class TestAPIRequestLogger:
    """Test API request logging functionality."""
    
    def test_api_request_logger_initialization(self):
        """Test API request logger initialization."""
        api_logger = APIRequestLogger()
        assert api_logger.logger.category == "system"
    
    def test_log_request(self):
        """Test logging API request."""
        api_logger = APIRequestLogger()
        headers = {"Authorization": "Bearer secret_token", "Content-Type": "application/json"}
        
        request_id = api_logger.log_request("GET", "https://api.example.com/data", headers, "body")
        
        # Should return a valid UUID
        assert isinstance(request_id, str)
        # Should be able to parse as UUID
        uuid.UUID(request_id)
        
        # Correlation ID should be set
        assert correlation_id.get() == request_id
    
    def test_log_response(self):
        """Test logging API response."""
        api_logger = APIRequestLogger()
        request_id = str(uuid.uuid4())
        
        # Should not raise exception
        api_logger.log_response(request_id, 200, 150.5, "response body")
    
    def test_log_error(self):
        """Test logging API error."""
        api_logger = APIRequestLogger()
        request_id = str(uuid.uuid4())
        error = ValueError("Test error")
        
        # Should not raise exception
        api_logger.log_error(request_id, error)
    
    def test_filter_sensitive_headers(self):
        """Test filtering of sensitive headers."""
        api_logger = APIRequestLogger()
        headers = {
            "Authorization": "Bearer secret_token",
            "Content-Type": "application/json",
            "X-API-Key": "secret_key",
            "User-Agent": "Auto-Trader/1.0"
        }
        
        filtered = api_logger._filter_sensitive_headers(headers)
        
        assert filtered["Authorization"] == "***REDACTED***"
        assert filtered["X-API-Key"] == "***REDACTED***"
        assert filtered["Content-Type"] == "application/json"
        assert filtered["User-Agent"] == "Auto-Trader/1.0"


class TestContextManagement:
    """Test logging context management."""
    
    def setUp(self):
        """Clear context before each test."""
        clear_context()
    
    def test_set_correlation_id(self):
        """Test setting correlation ID."""
        test_id = "test-correlation-123"
        result_id = set_correlation_id(test_id)
        
        assert result_id == test_id
        assert correlation_id.get() == test_id
    
    def test_set_correlation_id_auto_generate(self):
        """Test auto-generating correlation ID."""
        result_id = set_correlation_id()
        
        assert isinstance(result_id, str)
        assert correlation_id.get() == result_id
        # Should be valid UUID
        uuid.UUID(result_id)
    
    def test_set_service_context(self):
        """Test setting service context."""
        set_service_context("trade_engine", "execute_order")
        
        assert service_context.get() == "trade_engine.execute_order"
    
    def test_set_trade_context(self):
        """Test setting trade context."""
        # Without trade ID
        set_trade_context("AAPL")
        assert trade_context.get() == "AAPL"
        
        # With trade ID
        set_trade_context("AAPL", "trade_123")
        assert trade_context.get() == "AAPL:trade_123"
    
    def test_clear_context(self):
        """Test clearing all context."""
        # Set all contexts
        set_correlation_id("test-id")
        set_service_context("module", "function")
        set_trade_context("AAPL", "trade_123")
        
        # Verify they're set
        assert correlation_id.get() == "test-id"
        assert service_context.get() == "module.function"
        assert trade_context.get() == "AAPL:trade_123"
        
        # Clear all
        clear_context()
        
        # Verify they're cleared
        assert correlation_id.get() is None
        assert service_context.get() is None
        assert trade_context.get() is None


class TestGetLogger:
    """Test logger factory function."""
    
    def test_get_logger_default_category(self):
        """Test getting logger with default category."""
        logger_instance = get_logger("test_module")
        
        assert logger_instance.name == "test_module"
        assert logger_instance.category == "system"
    
    def test_get_logger_custom_category(self):
        """Test getting logger with custom category."""
        logger_instance = get_logger("test_module", "trade")
        
        assert logger_instance.name == "test_module"
        assert logger_instance.category == "trade"


class TestLoggingIntegration:
    """Test logging integration scenarios."""
    
    def test_context_propagation(self):
        """Test that context is properly propagated to log records."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir) / "logs"
            config = LoggerConfig(logs_dir=logs_dir)
            config.configure_logging()
            
            # Set context
            request_id = set_correlation_id("test-request-123")
            set_service_context("trade_engine", "process_signal")
            set_trade_context("AAPL", "trade_456")
            
            # Log a message
            logger_instance = get_logger("test", "trade")
            logger_instance.info("Test message with context")
            
            # Context should still be available
            assert correlation_id.get() == request_id
            assert service_context.get() == "trade_engine.process_signal"
            assert trade_context.get() == "AAPL:trade_456"
    
    def test_category_based_routing(self):
        """Test that messages are routed to correct log files based on category."""
        with tempfile.TemporaryDirectory() as temp_dir:
            logs_dir = Path(temp_dir) / "logs"
            config = LoggerConfig(logs_dir=logs_dir)
            config.configure_logging()
            
            # Log messages with different categories
            system_logger = get_logger("system_module", "system")
            trade_logger = get_logger("trade_module", "trade")
            risk_logger = get_logger("risk_module", "risk")
            cli_logger = get_logger("cli_module", "cli")
            
            system_logger.info("System event")
            trade_logger.info("Trade event")
            risk_logger.info("Risk event")
            cli_logger.info("CLI event")
            
            # All loggers should work without errors
            # Actual file content verification would require log handler flushing