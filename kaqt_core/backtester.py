from __future__ import annotations

from typing import Dict
import numpy as np
import pandas as pd

from .config import EngineConfig


class Backtester:
    def __init__(self, config: EngineConfig, data_panel: Dict[str, pd.DataFrame], strategy):
        self.config = config
        self.data_panel = data_panel
        self.strategy = strategy

    def _build_asset_returns(self) -> pd.DataFrame:
        rets = {}
        for sym, df in self.data_panel.items():
            if "adj_close" in df.columns:
                px = df["adj_close"]
            elif "Adj Close" in df.columns:
                px = df["Adj Close"]
            elif "close" in df.columns:
                px = df["close"]
            else:
                px = df.iloc[:, 0]

            px = pd.to_numeric(px, errors="coerce").dropna()
            px.index = pd.to_datetime(px.index)
            px = px.sort_index()
            rets[sym] = px.pct_change().fillna(0.0)

        returns = pd.DataFrame(rets).dropna(how="all")
        returns.index = pd.to_datetime(returns.index)
        return returns.sort_index()

    def run(self) -> Dict:
        cfg = self.config

        returns = self._build_asset_returns()
        weights = self.strategy.generate_daily_target_weights()

        common_idx = returns.index.intersection(weights.index)
        returns = returns.reindex(common_idx).fillna(0.0)
        weights = weights.reindex(common_idx).fillna(0.0)

        # apply 1-day lag (realistic)
        w_exec = weights.shift(1).fillna(0.0) if cfg.apply_1d_lag else weights

        # transaction costs on turnover
        # cost = bps * turnover, turnover = sum(|w_t - w_{t-1}|)
        cost_bps = float(getattr(cfg, "cost_bps", 0.0) or 0.0)
        if cost_bps > 0:
            turnover = (weights - weights.shift(1)).abs().sum(axis=1).fillna(0.0)
            costs = turnover * (cost_bps / 10_000.0)
        else:
            costs = pd.Series(0.0, index=common_idx)

        port_ret = (w_exec * returns).sum(axis=1) - costs

        initial_capital = float(cfg.initial_capital)
        equity = (1.0 + port_ret).cumprod() * initial_capital

        n_days = len(port_ret)
        rf_annual = float(getattr(cfg, "risk_free_rate", 0.0) or 0.0)
        rf_daily = (1.0 + rf_annual) ** (1.0 / 252.0) - 1.0
        excess = port_ret - rf_daily

        mean_daily = excess.mean()
        std_daily = excess.std(ddof=1)

        sharpe = float((mean_daily / std_daily) * np.sqrt(252.0)) if std_daily > 0 else 0.0

        total_return = float(equity.iloc[-1] / initial_capital)
        years = n_days / 252.0
        cagr = float(total_return ** (1.0 / years) - 1.0) if years > 0 and total_return > 0 else 0.0

        running_max = equity.cummax()
        drawdown = equity / running_max - 1.0
        max_dd = float(drawdown.min())

        return {
            "CAGR": cagr,
            "Vol_Annual": float(port_ret.std(ddof=1) * np.sqrt(252.0)),
            "Sharpe": sharpe,
            "Max_Drawdown": max_dd,
            "Equity": equity,
            "Weights": weights,
            "PortRet": port_ret,
            "Costs": costs,
        }