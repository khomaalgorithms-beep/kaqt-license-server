# kaqt_core/paper_client.py

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any
import time
import random


@dataclass
class Trade:
    timestamp: float
    symbol: str
    side: str
    quantity: float
    price: float
    cash_after: float


class PaperBroker:
    """
    Very simple in-memory paper broker for demo/testing.
    """

    def __init__(self, starting_cash: float = 100_000.0):
        self.cash: float = float(starting_cash)
        self.positions: Dict[str, Dict[str, Any]] = {}
        self.trades: List[Trade] = []

    # ----------- snapshots / prices -----------

    def snapshot(self) -> Dict[str, Any]:
        portfolio_value = self.cash
        for pos in self.positions.values():
            portfolio_value += pos.get("market_value", 0.0)

        return {
            "cash": self.cash,
            "buying_power": self.cash,
            "portfolio_value": portfolio_value,
        }

    def get_price(self, symbol: str) -> float:
        """
        Tiny fake price feed so we can see PnL move.
        """
        s = symbol.upper()
        if s == "QQQ":
            base = 400.0
        elif s == "SPY":
            base = 450.0
        else:
            base = 100.0
        return base + random.uniform(-2, 2)

    # ----------- orders -----------

    def market_order(self, symbol: str, side: str, quantity: float) -> None:
        side = side.upper()
        qty = float(quantity)
        price = self.get_price(symbol)
        notional = price * qty

        if side == "BUY":
            self.cash -= notional
            qty_change = qty
        elif side == "SELL":
            self.cash += notional
            qty_change = -qty
        else:
            raise ValueError(f"Unsupported side: {side}")

        pos = self.positions.get(
            symbol,
            {
                "symbol": symbol,
                "quantity": 0.0,
                "avg_price": price,
                "last_price": price,
                "market_value": 0.0,
            },
        )

        old_qty = pos["quantity"]
        new_qty = old_qty + qty_change

        if new_qty != 0:
            pos["avg_price"] = (
                (old_qty * pos["avg_price"]) + (qty_change * price)
            ) / new_qty

        pos["quantity"] = new_qty
        pos["last_price"] = price
        pos["market_value"] = new_qty * price

        if new_qty == 0:
            self.positions.pop(symbol, None)
        else:
            self.positions[symbol] = pos

        self.trades.append(
            Trade(
                timestamp=time.time(),
                symbol=symbol,
                side=side,
                quantity=qty_change,
                price=price,
                cash_after=self.cash,
            )
        )

    # ----------- views -----------

    def get_trades(self) -> List[Dict[str, Any]]:
        return [t.__dict__ for t in self.trades]

    def get_positions(self) -> List[Dict[str, Any]]:
        return list(self.positions.values())