import math
import numpy as np
import pandas as pd

from .config import EngineConfig


class KAQTMultiAlphaEngine:
    """
    KAQT NQ AGGRESSIVE v1.1 (Risk-Reduced)
    -------------------------------------
    Clean single-asset engine for NQ (using QQQ as proxy in backtests).

    Logic (same core):
      - Long-only trend-following using 50/200 EMA.
      - Only go long when 200 EMA is rising.
      - Volatility targeting (20d realized vol).
      - Max leverage cap from config.
      - Light smoothing of weights.

    Risk brakes (added, small changes):
      - Crash filter: go flat if price is below slow EMA by a buffer.
      - Vol floor: prevents leverage exploding when vol is extremely low.
      - Still uses vol_target_annual + max_leverage from config.
    """

    def __init__(self, config: EngineConfig, asset_symbol: str, price_df: pd.DataFrame):
        self.cfg = config
        self.symbol = asset_symbol
        self.data = price_df.sort_index()

    # -----------------------------
    # Helpers
    # -----------------------------
    def _get_close_series(self) -> pd.Series:
        """
        Extract a 1D close/adj_close series from a price DataFrame.
        """
        df = self.data
        for col in ["adj_close", "Adj Close", "Adj_Close", "adj close", "adj_close", "close", "Close"]:
            if col in df.columns:
                s = df[col]
                if isinstance(s, pd.DataFrame):
                    s = s.iloc[:, 0]
                return pd.to_numeric(s, errors="coerce")

        # Fallback: first column
        s = df.iloc[:, 0]
        return pd.to_numeric(s, errors="coerce")

    # -----------------------------
    # Core
    # -----------------------------
    def generate_daily_target_weights(self) -> pd.DataFrame:
        """
        Core entry point used by Backtester.
        Returns a DataFrame of daily weights for this asset.
        """

        close = self._get_close_series().dropna().sort_index()
        ret = close.pct_change().fillna(0.0)

        # 1) Trend EMAs
        ema_fast = close.ewm(span=50, adjust=False).mean()
        ema_slow = close.ewm(span=200, adjust=False).mean()

        # Long signal when fast EMA clearly above slow EMA
        cross_up = ema_fast > ema_slow * 1.001  # small buffer to avoid chop

        # Long-term trend filter: 200 EMA rising over the last 50 days
        ema_slow_prev = ema_slow.shift(50)
        trend_up = ema_slow > ema_slow_prev.fillna(ema_slow)

        # -----------------------------
        # Risk brake A: Crash filter
        # If price is meaningfully below the slow EMA, go flat (risk-off).
        # -----------------------------
        crash_buffer = getattr(self.cfg, "crash_buffer", 0.97)  # default: 3% below slow EMA
        crash_off = close < (ema_slow * float(crash_buffer))

        # Final long condition: fast above slow AND slow trending up AND not in crash-off
        long_mask = cross_up & trend_up & (~crash_off)

        signal = pd.Series(0.0, index=close.index)
        signal[long_mask] = 1.0

        # 2) 20-day realized vol (annualized)
        vol_20d = ret.rolling(20).std(ddof=1) * math.sqrt(252.0)
        vol_20d = vol_20d.replace(0.0, np.nan)

        # 3) Volatility targeting
        target_vol = float(getattr(self.cfg, "vol_target_annual", 0.25))
        max_leverage = 1.0  # CASH-ONLY mode: never exceed 100% exposure

        leverage = target_vol / vol_20d

        # -----------------------------
        # Risk brake B: Volatility floor adjustment
        # Prevent leverage spikes when realized vol is extremely low.
        # -----------------------------
        min_vol_floor = float(getattr(self.cfg, "min_vol_floor", 0.12))  # 12% annual floor default
        vol_adj = (vol_20d / min_vol_floor).clip(lower=0.5, upper=1.0)   # reduce leverage if vol < floor
        leverage = leverage * vol_adj

        leverage = leverage.clip(0.0, max_leverage).fillna(0.0)

        # Base weight from signal * leverage
        w_raw = signal * leverage

        # 4) Light smoothing of weights to avoid flip-flop
        w_smooth = w_raw.ewm(span=3, adjust=False).mean()

        # 5) Final weights DataFrame
        w_smooth = w_smooth.clip(0.0, 1.0)
        weights_df = pd.DataFrame(w_smooth, columns=[self.symbol]).fillna(0.0)

        return weights_df
def get_latest_signal(self) -> dict:
    """
    Returns the latest desired state from the strategy (cash vs long).
    """
    weights = self.generate_daily_target_weights()
    if weights.empty:
        return {"ok": False, "message": "No weights produced."}

    last_dt = weights.index[-1]
    w = float(weights.iloc[-1][self.symbol])

    return {
        "ok": True,
        "symbol": self.symbol,
        "date": str(last_dt.date()),
        "target_weight": round(w, 4),
        "state": "LONG" if w > 0 else "CASH",
    }