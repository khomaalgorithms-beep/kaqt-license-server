# brokers/base.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List


@dataclass
class AccountInfo:
    equity: float = 0.0
    cash: float = 0.0
    buying_power: float = 0.0
    currency: str = "USD"
    raw: Dict[str, Any] = field(default_factory=dict)


class BrokerClient(ABC):
    def __init__(self, name: str):
        self.name = name
        self.connected: bool = False

    # ----- lifecycle -----
    @abstractmethod
    def connect(self) -> None: ...

    @abstractmethod
    def disconnect(self) -> None: ...

    # ----- account / status -----
    @abstractmethod
    def get_account_info(self) -> AccountInfo: ...

    # ----- views -----
    @abstractmethod
    def get_positions(self) -> List[Dict[str, Any]]: ...

    @abstractmethod
    def get_trades(self) -> List[Dict[str, Any]]: ...

    # ----- trading -----
    @abstractmethod
    def market_order(self, symbol: str, side: str, quantity: float) -> Dict[str, Any]: ...

    @abstractmethod
    def sync_target_weights(self, symbol: str, weights_series) -> None: ...