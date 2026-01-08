from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import time


# -----------------------------
# Config
# -----------------------------
@dataclass
class IBKRConfig:
    host: str = "127.0.0.1"
    port: int = 7497
    client_id: int = 7
    account: str = ""          # optional DUxxxx / Uxxxx
    mode: str = "paper_api"    # paper_api | live


# -----------------------------
# Real IBKR client (ib_insync)
# -----------------------------
class IBKRRealClient:
    """
    IBKR client wrapper using ib_insync.
    Required methods for KAQT UI/runtime:
      - connect()
      - get_account_info() -> {equity, cash, buying_power, currency}
      - get_positions() -> list[{symbol, quantity, avg_price}]
      - get_trades() -> list[{timestamp, symbol, side, quantity, price}]
    """

    def __init__(self, cfg: IBKRConfig):
        self.cfg = cfg

        # Lazy import so your project can run without IBKR installed in some contexts
        from ib_insync import IB  # type: ignore

        self._IB = IB
        self.ib = IB()
        self.connected = False

    def connect(self) -> None:
        if self.connected and self.ib.isConnected():
            return
        self.ib.connect(self.cfg.host, int(self.cfg.port), clientId=int(self.cfg.client_id))
        self.connected = True

    def disconnect(self) -> None:
        try:
            if self.ib.isConnected():
                self.ib.disconnect()
        finally:
            self.connected = False

    # -----------------------------
    # Account info (IMPORTANT)
    # -----------------------------
    def get_account_info(self) -> Dict[str, Any]:
        """
        Returns:
          equity: NetLiquidation
          cash: TotalCashValue (fallback: AvailableFunds)
          buying_power: BuyingPower (fallback: AvailableFunds)
        """
        self._ensure_connected()

        # If account not set, ib_insync can still return a list (choose first)
        summary = self.ib.accountSummary(account=self.cfg.account or "")
        # accountSummary returns a list of AccountValue objects: .tag, .value, .currency, .account
        d: Dict[str, str] = {}
        currency = "USD"
        for av in summary:
            try:
                d[str(av.tag)] = str(av.value)
                if getattr(av, "currency", None):
                    currency = str(av.currency)
            except Exception:
                pass

        def _f(tag: str, default: float = 0.0) -> float:
            try:
                v = d.get(tag, None)
                if v is None or v == "":
                    return float(default)
                return float(v)
            except Exception:
                return float(default)

        equity = _f("NetLiquidation", 0.0)

        # Cash tags can vary across accounts; this set covers most cases:
        cash = (
            _f("TotalCashValue", 0.0) or
            _f("CashBalance", 0.0) or
            _f("SettledCash", 0.0) or
            _f("AvailableFunds", 0.0)
        )

        buying_power = _f("BuyingPower", 0.0)
        if buying_power == 0.0:
            buying_power = _f("AvailableFunds", 0.0)

        return {
            "equity": float(equity),
            "cash": float(cash),
            "buying_power": float(buying_power),
            "currency": currency,
        }

    # -----------------------------
    # Positions
    # -----------------------------
    def get_positions(self) -> List[Dict[str, Any]]:
        self._ensure_connected()
        out: List[Dict[str, Any]] = []

        for p in self.ib.positions():
            try:
                symbol = getattr(p.contract, "symbol", "") or ""
                qty = float(getattr(p, "position", 0.0) or 0.0)
                avg_cost = float(getattr(p, "avgCost", 0.0) or 0.0)
                out.append({
                    "symbol": symbol,
                    "quantity": qty,
                    "avg_price": avg_cost,
                })
            except Exception:
                continue
        return out

    # -----------------------------
    # Trades (recent fills)
    # -----------------------------
    def get_trades(self) -> List[Dict[str, Any]]:
        """
        Uses ib.trades() (orders + fills). We convert fills to your UI format.
        """
        self._ensure_connected()
        out: List[Dict[str, Any]] = []

        # ib.trades() returns Trade objects; each has .fills
        for tr in self.ib.trades():
            try:
                contract = getattr(tr, "contract", None)
                symbol = getattr(contract, "symbol", "") if contract else ""

                fills = getattr(tr, "fills", []) or []
                for f in fills:
                    exec_ = getattr(f, "execution", None)
                    if exec_ is None:
                        continue

                    side = str(getattr(exec_, "side", "") or "").upper()
                    qty = float(getattr(exec_, "shares", 0.0) or 0.0)
                    price = float(getattr(exec_, "price", 0.0) or 0.0)

                    # execution.time is often a string; use epoch fallback
                    ts = time.time()
                    try:
                        # If it's a datetime, convert
                        tval = getattr(exec_, "time", None)
                        if hasattr(tval, "timestamp"):
                            ts = float(tval.timestamp())
                    except Exception:
                        pass

                    out.append({
                        "timestamp": ts,
                        "symbol": symbol,
                        "side": "BUY" if side.startswith("B") else "SELL",
                        "quantity": qty,
                        "price": price,
                    })
            except Exception:
                continue

        return out

    # -----------------------------
    # Helpers
    # -----------------------------
    def _ensure_connected(self) -> None:
        if not self.connected or not self.ib.isConnected():
            raise RuntimeError("IBKR is not connected. Call connect() first.")


# -----------------------------
# Optional: Sim client for offline tests
# -----------------------------
class IBKRSimClient:
    """
    Minimal simulator for testing UI without TWS/Gateway.
    """
    def __init__(self, starting_cash: float = 100_000.0):
        self._cash = float(starting_cash)
        self._equity = float(starting_cash)
        self._positions: Dict[str, Dict[str, float]] = {}
        self._trades: List[Dict[str, Any]] = []
        self.connected = False

    def connect(self) -> None:
        self.connected = True

    def get_account_info(self) -> Dict[str, Any]:
        return {
            "equity": float(self._equity),
            "cash": float(self._cash),
            "buying_power": float(self._cash),
            "currency": "USD",
        }

    def get_positions(self) -> List[Dict[str, Any]]:
        out = []
        for sym, p in self._positions.items():
            out.append({
                "symbol": sym,
                "quantity": float(p.get("qty", 0.0)),
                "avg_price": float(p.get("avg", 0.0)),
            })
        return out

    def get_trades(self) -> List[Dict[str, Any]]:
        return list(self._trades)