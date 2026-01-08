from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple
from kaqt_core.data_loader import download_data
import pandas as pd

from kaqt_core.config import EngineConfig, AssetConfig, default_engine_config




from kaqt_core.engine import KAQTMultiAlphaEngine


from kaqt_core.engine import KAQTMultiAlphaEngine

@dataclass
class LiveDecision:
    symbol: str
    target_weight: float
    signal_state: str         # "LONG" or "FLAT"
    last_price: float
    timestamp: float
    message: str


def _now_ts() -> float:
    return float(time.time())


def _fmt_time(ts: float) -> str:
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts))
    except Exception:
        return str(ts)


def _get_last_price(price_df: pd.DataFrame) -> float:
    # Prefer adjusted close if present
    for col in ["adj_close", "Adj Close", "close", "Close"]:
        if col in price_df.columns:
            s = price_df[col]
            if isinstance(s, pd.DataFrame):
                s = s.iloc[:, 0]
            return float(pd.to_numeric(s, errors="coerce").dropna().iloc[-1])
    # fallback: last numeric value in df
    return float(pd.to_numeric(price_df.iloc[:, 0], errors="coerce").dropna().iloc[-1])


def _extract_position_qty(positions: Any, symbol: str) -> float:
    """
    Handles both SIM and REAL position formats.
    Expected shape: list of dicts. We look for keys: quantity or size.
    """
    if not positions:
        return 0.0

    sym = symbol.upper().strip()
    try:
        for p in positions:
            ps = str(p.get("symbol", "")).upper().strip()
            if ps == sym:
                if "quantity" in p:
                    return float(p.get("quantity") or 0.0)
                if "size" in p:
                    return float(p.get("size") or 0.0)
                return 0.0
    except Exception:
        pass
    return 0.0


def _cash_only_target_qty(equity: float, cash: float, price: float, target_weight: float) -> int:
    """
    CASH-ONLY sizing:
      - clamp target_weight to [0, 1]
      - shares limited by equity target AND by available cash
    """
    tw = max(0.0, min(float(target_weight), 1.0))

    if price <= 0:
        return 0

    target_notional = tw * float(equity)
    shares_by_target = int(math.floor(target_notional / price))

    shares_by_cash = int(math.floor(float(cash) / price))

    return max(0, min(shares_by_target, shares_by_cash))


class StrategyLiveRunner:
    """
    Runs KAQT engine in "live mode" by:
      - loading latest data for symbol
      - generating the latest target weight
      - translating target weight -> target shares (cash-only)
      - placing delta order on broker

    Broker contract expected:
      - connect()
      - get_account_info() -> {"equity":..., "cash":..., ...}
      - get_positions() -> list[dict]
      - market_order(symbol, side, qty)
    """

    def __init__(self, symbol: str = "QQQ", yf_symbol: str = "QQQ", cfg: Optional[EngineConfig] = None):
        self.symbol = symbol.upper().strip()
        self.yf_symbol = yf_symbol
        self.cfg = cfg or EngineConfig()

        # state
        self.last_decision: Optional[LiveDecision] = None

    def get_signal_state(self) -> Dict[str, Any]:
        """
        Used by UI to display LONG/FLAT and decision time.
        """
        if self.last_decision is None:
            return {
                "symbol": self.symbol,
                "signal_state": "UNKNOWN",
                "target_weight": 0.0,
                "last_price": 0.0,
                "last_decision_time": None,
                "last_message": "No decision yet.",
            }

        d = self.last_decision
        return {
            "symbol": d.symbol,
            "signal_state": d.signal_state,
            "target_weight": float(d.target_weight),
            "last_price": float(d.last_price),
            "last_decision_time": _fmt_time(d.timestamp),
            "last_message": d.message,
        }

    def _compute_latest_target_weight(self) -> Tuple[float, float, pd.DataFrame]:
        """
        Returns: (target_weight, last_price, data_df)
        """
        asset = AssetConfig(symbol=self.symbol, yf_symbol=self.yf_symbol)
        data = download_data(asset, self.cfg.start_date, self.cfg.end_date)

        last_price = _get_last_price(data)

        engine = KAQTMultiAlphaEngine(
            config=self.cfg,
            asset_symbol=self.symbol,
            price_df=data,
        )

        weights = engine.generate_daily_target_weights()

        if self.symbol not in weights.columns:
            # if engine used a different column name, fallback to first
            col = weights.columns[0]
            target_weight = float(weights[col].iloc[-1])
        else:
            target_weight = float(weights[self.symbol].iloc[-1])

        # Safety clamp (cash only)
        target_weight = max(0.0, min(float(target_weight), 1.0))

        return target_weight, float(last_price), data

    def run_once(self, broker) -> Dict[str, Any]:
        """
        Executes one decision cycle + optional trade.
        """
        ts = _now_ts()

        # 1) Compute target weight + price
        target_weight, last_price, _data = self._compute_latest_target_weight()

        signal_state = "LONG" if target_weight > 0.001 else "FLAT"

        # 2) Pull account info
        info = broker.get_account_info()
        equity = float(info.get("equity", 0.0) or 0.0)
        cash = float(info.get("cash", 0.0) or 0.0)

        # 3) Current position
        positions = broker.get_positions()
        current_qty = float(_extract_position_qty(positions, self.symbol))

        # 4) Cash-only target shares
        target_qty = int(_cash_only_target_qty(equity, cash, last_price, target_weight))

        # 5) Delta and trade
        delta = int(target_qty - int(round(current_qty)))

        msg: str
        if delta > 0:
            # BUY delta shares
            broker.market_order(self.symbol, "BUY", float(delta))
            msg = f"Placed BUY {delta} {self.symbol} (target_weight={target_weight:.3f})."
        elif delta < 0:
            # SELL abs(delta) shares
            broker.market_order(self.symbol, "SELL", float(abs(delta)))
            msg = f"Placed SELL {abs(delta)} {self.symbol} (target_weight={target_weight:.3f})."
        else:
            msg = f"No trade needed. Target already met ({int(round(current_qty))} shares)."

        self.last_decision = LiveDecision(
            symbol=self.symbol,
            target_weight=float(target_weight),
            signal_state=signal_state,
            last_price=float(last_price),
            timestamp=ts,
            message=msg,
        )

        return {
            "ok": True,
            "message": msg,
            "symbol": self.symbol,
            "signal_state": signal_state,
            "target_weight": float(target_weight),
            "last_price": float(last_price),
            "target_qty": int(target_qty),
            "current_qty": float(current_qty),
            "cash": float(cash),
            "equity": float(equity),
            "last_decision_time": _fmt_time(ts),
        }