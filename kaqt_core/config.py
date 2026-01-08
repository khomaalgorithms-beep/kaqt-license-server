from __future__ import annotations

from dataclasses import dataclass
import datetime as dt
from typing import List, Optional


@dataclass
class AssetConfig:
    """
    Configuration for a single tradable asset.
    """
    symbol: str
    yf_symbol: str
    weight: float = 1.0
    min_volatility: float = 0.0
    max_volatility: float = 1.0


@dataclass
class EngineConfig:
    """
    Global engine configuration for KAQT engines / backtests / live runner.
    Keep this backward-compatible: add new fields with defaults only.
    """
    # Backtest / live window
    start_date: dt.date = dt.date(2005, 1, 1)
    end_date: dt.date = dt.date(2025, 1, 1)

    # Universe (optional)
    assets: Optional[List[AssetConfig]] = None

    # Portfolio settings
    initial_capital: float = 100_000.0
    risk_free_rate: float = 0.01

    # Risk targeting
    vol_target_annual: float = 0.25
    max_leverage: float = 1.0
    min_leverage: float = 0.0

    # Execution realism (optional; safe defaults)
    apply_1d_lag: bool = False
    cost_bps: float = 0.0


def default_engine_config() -> EngineConfig:
    """
    Used by StrategyLiveRunner and any place that wants safe defaults.
    """
    return EngineConfig()