# brokers/ibkr_sim.py
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List

from brokers.base import BrokerClient, AccountInfo
from kaqt_app import PaperBroker


@dataclass
class IBKRSimConfig:
    starting_cash: float = 100_000.0
    account_id: str = "IBKR_SIM_001"


class IBKRSimClient(BrokerClient):
    """
    IBKR Simulator (NO real IBKR required).
    Uses the existing PaperBroker internally, but exposes IBKR-like behavior.
    """

    def __init__(self, config: IBKRSimConfig):
        super().__init__(name="ibkr_sim")
        self.cfg = config
        self.paper = PaperBroker(starting_cash=float(config.starting_cash))

    def connect(self) -> None:
        self.connected = True

    def disconnect(self) -> None:
        self.connected = False

    def get_account_info(self) -> AccountInfo:
        snap = self.paper.snapshot()
        equity = float(snap.get("portfolio_value", 0.0))
        cash = float(snap.get("cash", 0.0))
        bp = float(snap.get("buying_power", cash))
        return AccountInfo(
            equity=equity,
            cash=cash,
            buying_power=bp,
            currency="USD",
            raw={"account_id": self.cfg.account_id, "snapshot": snap},
        )

    def market_order(self, symbol: str, side: str, quantity: float) -> None:
        if not self.connected:
            raise RuntimeError("IBKRSimClient is not connected.")
        self.paper.market_order(symbol, side, quantity)

    def get_positions(self) -> List[Dict[str, Any]]:
        return self.paper.get_positions()

    def get_trades(self) -> List[Dict[str, Any]]:
        return self.paper.get_trades()