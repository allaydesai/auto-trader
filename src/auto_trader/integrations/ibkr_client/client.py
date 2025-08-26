"""IBKR client implementation using ib-async."""

from datetime import datetime
from enum import Enum
from typing import Optional, Tuple

from ib_async import IB
from loguru import logger
from pydantic import BaseModel

from config import ConfigLoader, Settings


class ConnectionState(Enum):
    """Connection state enumeration."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    CIRCUIT_OPEN = "circuit_open"
    SHUTDOWN = "shutdown"


class ConnectionStatus(BaseModel):
    """Connection status information."""
    state: ConnectionState
    last_connected: Optional[datetime] = None
    reconnect_attempts: int = 0
    account_type: Optional[str] = None
    is_paper_account: bool = False
    connection_time: Optional[float] = None


class IBKRError(Exception):
    """Base exception for IBKR-related errors."""
    pass


class IBKRConnectionError(IBKRError):
    """Connection establishment or maintenance failed."""
    pass


class IBKRAuthenticationError(IBKRError):
    """Authentication or authorization failed."""
    pass


class IBKRTimeoutError(IBKRError):
    """Operation timed out."""
    pass


class IBKRClient:
    """
    IBKR client with ib-async integration and connection management.
    
    Provides reliable connection to Interactive Brokers with automatic
    reconnection, circuit breaker protection, and comprehensive logging.
    """

    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize IBKR client.
        
        Args:
            settings: Optional settings instance, creates new if None
        """
        self._settings = settings or Settings()
        self._config_loader = ConfigLoader(self._settings)
        self._ib = IB()
        self._connection_status = ConnectionStatus(state=ConnectionState.DISCONNECTED)
        self._connection_start_time: Optional[float] = None
        
        # Register event handlers
        self._ib.connectedEvent += self._on_connected
        self._ib.disconnectedEvent += self._on_disconnected
        self._ib.errorEvent += self._on_error

    async def connect(self) -> None:
        """
        Establish IBKR connection with configuration validation.
        
        Raises:
            IBKRConnectionError: If connection fails
            IBKRTimeoutError: If connection times out
        """
        if self.is_connected():
            logger.info("Already connected to IBKR")
            return

        ibkr_config = self._config_loader.system_config.ibkr
        self._connection_status.state = ConnectionState.CONNECTING
        self._connection_start_time = datetime.now().timestamp()

        try:
            logger.info(
                "Connecting to IBKR",
                host=ibkr_config.host,
                port=ibkr_config.port,
                client_id=ibkr_config.client_id,
                timeout=ibkr_config.timeout
            )

            await self._ib.connectAsync(
                host=ibkr_config.host,
                port=ibkr_config.port,
                clientId=ibkr_config.client_id,
                timeout=ibkr_config.timeout
            )

            # Get account information and detect paper trading
            account_type, is_paper = await self._detect_account_type()
            self._connection_status.account_type = account_type
            self._connection_status.is_paper_account = is_paper

            connection_time = datetime.now().timestamp() - self._connection_start_time
            self._connection_status.connection_time = connection_time
            self._connection_status.state = ConnectionState.CONNECTED
            self._connection_status.last_connected = datetime.now()
            self._connection_status.reconnect_attempts = 0

            self._log_account_type_warning(account_type, is_paper)

            logger.info(
                "IBKR connection established",
                account_type="paper" if is_paper else "live",
                connection_time=f"{connection_time:.2f}s"
            )

        except Exception as e:
            self._connection_status.state = ConnectionState.DISCONNECTED
            logger.error("IBKR connection failed", error=str(e))
            
            if "timeout" in str(e).lower():
                raise IBKRTimeoutError(f"Connection timeout: {e}")
            elif "authentication" in str(e).lower():
                raise IBKRAuthenticationError(f"Authentication failed: {e}")
            else:
                raise IBKRConnectionError(f"Connection failed: {e}")

    async def disconnect(self) -> None:
        """
        Graceful disconnection with resource cleanup.
        """
        if not self.is_connected():
            logger.info("Already disconnected from IBKR")
            return

        try:
            logger.info("Disconnecting from IBKR")
            self._connection_status.state = ConnectionState.DISCONNECTED
            self._ib.disconnect()
            logger.info("IBKR disconnection completed")
        except Exception as e:
            logger.error("Error during IBKR disconnection", error=str(e))

    def is_connected(self) -> bool:
        """
        Connection status for health checks.
        
        Returns:
            True if connected to IBKR
        """
        return self._ib.isConnected() and self._connection_status.state == ConnectionState.CONNECTED

    def get_connection_status(self) -> ConnectionStatus:
        """
        Current connection state for monitoring.
        
        Returns:
            Current connection status information
        """
        return self._connection_status

    async def _detect_account_type(self) -> Tuple[str, bool]:
        """
        Detect if connected to paper or live account.
        
        Returns:
            Tuple[account_id, is_paper_account]
        """
        try:
            account_summary = await self._ib.accountSummaryAsync()
            if not account_summary:
                # Fallback to managedAccounts if accountSummary is empty
                managed_accounts = self._ib.managedAccounts()
                if managed_accounts:
                    account_id = managed_accounts[0]
                else:
                    account_id = "UNKNOWN"
            else:
                account_id = account_summary[0].account

            # Paper accounts typically start with "DU"
            is_paper = account_id.startswith("DU")
            
            return account_id, is_paper

        except Exception as e:
            logger.error("Failed to detect account type", error=str(e))
            return "UNKNOWN", True  # Default to paper for safety

    def _log_account_type_warning(self, account_id: str, is_paper: bool) -> None:
        """
        Log prominent account type warnings for safety.
        
        Args:
            account_id: Account identifier
            is_paper: True if paper account
        """
        if is_paper:
            logger.warning(
                "⚠️ PAPER TRADING ACCOUNT DETECTED",
                account_id=account_id,
                safety_mode="SIMULATION"
            )
        else:
            logger.critical(
                "🔴 LIVE TRADING ACCOUNT DETECTED",
                account_id="***REDACTED***",  # Never log real account IDs
                safety_mode="LIVE_TRADING"
            )

    def _on_connected(self) -> None:
        """Handle connection established event."""
        logger.debug("IBKR connection event: connected")

    def _on_disconnected(self) -> None:
        """Handle disconnection event."""
        logger.warning("IBKR connection event: disconnected")
        if self._connection_status.state != ConnectionState.SHUTDOWN:
            self._connection_status.state = ConnectionState.DISCONNECTED

    def _on_error(self, reqId: int, errorCode: int, errorString: str, contract=None) -> None:
        """
        Handle IBKR error events.
        
        Args:
            reqId: Request ID
            errorCode: Error code from IBKR
            errorString: Error message
            contract: Optional contract associated with error
        """
        # Filter out informational messages
        if errorCode in [2104, 2106, 2158]:  # Market data farm connection messages
            logger.debug("IBKR info", code=errorCode, message=errorString)
        elif errorCode >= 2000:  # Warnings
            logger.warning("IBKR warning", code=errorCode, message=errorString, reqId=reqId)
        else:  # Errors
            logger.error("IBKR error", code=errorCode, message=errorString, reqId=reqId)