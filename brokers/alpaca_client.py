# brokers/alpaca_client.py
from __future__ import annotations

from typing import Dict, Any, List, Optional

from .base import BrokerClient, AccountInfo


class AlpacaClient(BrokerClient):
    """
    Skeleton adapter for Alpaca.

    IMPORTANT:
    - This is a placeholder only.
    - No HTTP requests to Alpaca are made yet.
    - All trading methods either return empty data or raise NotImplementedError.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        super().__init__(name="alpaca")
        self.config: Dict[str, Any] = config or {}
        self._account_info = AccountInfo()

    # ---------- lifecycle ----------

    def connect(self) -> None:
        """
        Later: initialize Alpaca REST/WebSocket client using API keys in self.config.

        For now, we explicitly do NOT connect to anything.
        """
        raise NotImplementedError(
            "AlpacaClient.connect is not implemented yet. "
            "Config is stored, but no real API calls are made."
        )

    def disconnect(self) -> None:
        """
        Later: clean up any Alpaca sessions or sockets.
        """
        self.connected = False

    # ---------- account / status ----------

    def get_account_info(self) -> AccountInfo:
        """
        Later: fetch /v2/account from Alpaca and normalize it.

        For now, return an empty snapshot so reading it is safe.
        """
        return self._account_info

    # ---------- positions / trades ----------

    def get_positions(self) -> List[Dict[str, Any]]:
        """
        Later: fetch open positions from Alpaca (/v2/positions).
        """
        return []

    def get_trades(self) -> List[Dict[str, Any]]:
        """
        Later: fetch recent orders/fills (v2/orders or activities).
        """
        return []

    # ---------- trading ----------

    def market_order(self, symbol: str, side: str, quantity: float) -> None:
        """
        Later: send a market order to Alpaca.

        For now we block this entirely, so there is zero chance
        of accidentally sending a real order.
        """
        raise NotImplementedError(
            "AlpacaClient.market_order is not implemented yet. "
            "No live orders are sent."
        )

    def sync_target_weights(self, symbol: str, weights_series) -> None:
        """
        Later: use Alpaca orders to follow a target weight time series.

        Not needed for first live tests – left unimplemented.
        """
        raise NotImplementedError(
            "AlpacaClient.sync_target_weights not implemented yet."
        )