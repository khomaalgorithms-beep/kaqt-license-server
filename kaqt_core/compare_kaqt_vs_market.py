import datetime as dt
import pandas as pd
import matplotlib.pyplot as plt
import yfinance as yf

from kaqt_app import EngineConfig, AssetConfig
from kaqt_app import download_data
from kaqt_app import KAQTMultiAlphaEngine
from kaqt_app import Backtester


START = dt.date(2005, 1, 1)
END   = dt.date(2025, 1, 1)


# ----------------------------
# Helpers
# ----------------------------
def _as_series(x) -> pd.Series:
    """Convert yfinance column output to a 1D Series safely."""
    if isinstance(x, pd.Series):
        return x
    if isinstance(x, pd.DataFrame):
        # Take first column if it’s a 2D frame
        if x.shape[1] >= 1:
            return x.iloc[:, 0]
    raise TypeError("Could not convert to 1D Series")


def _get_close_series_from_yf(df: pd.DataFrame, prefer_adj: bool = True) -> pd.Series:
    """
    Robustly extract a 1D price series from yfinance output.
    Handles both:
      - normal columns
      - MultiIndex columns
      - cases where df["Adj Close"] returns a DataFrame
    """
    if df is None or df.empty:
        raise ValueError("yfinance returned empty dataframe")

    # 1) Normal columns
    if isinstance(df.columns, pd.Index):
        if prefer_adj and "Adj Close" in df.columns:
            s = _as_series(df["Adj Close"])
            return pd.to_numeric(s, errors="coerce").dropna()
        if "Close" in df.columns:
            s = _as_series(df["Close"])
            return pd.to_numeric(s, errors="coerce").dropna()

    # 2) MultiIndex columns
    if isinstance(df.columns, pd.MultiIndex):
        # Try to find an "Adj Close" column anywhere
        if prefer_adj:
            for col in df.columns:
                if any("Adj" in str(level) and "Close" in str(level) for level in col):
                    s = _as_series(df[col])
                    return pd.to_numeric(s, errors="coerce").dropna()

        # Fallback: find "Close"
        for col in df.columns:
            if any(str(level) == "Close" for level in col):
                s = _as_series(df[col])
                return pd.to_numeric(s, errors="coerce").dropna()

    raise KeyError("Could not find Close/Adj Close in yfinance dataframe")


def equity_from_prices(px: pd.Series, initial_capital: float = 100_000.0) -> pd.Series:
    px = px.sort_index().dropna()
    rets = px.pct_change().fillna(0.0)
    eq = (1.0 + rets).cumprod() * float(initial_capital)
    eq.name = "equity"
    return eq


def yearly_returns_from_equity(equity: pd.Series) -> pd.Series:
    equity = equity.sort_index().dropna()
    year_end = equity.resample("YE").last()
    yr = year_end.pct_change().dropna()
    yr.index = yr.index.year
    return (yr * 100.0).round(2)


# ----------------------------
# Main
# ----------------------------
def main():
    initial_capital = 100_000.0

    # ====== 1) KAQT strategy equity ======
    cfg = EngineConfig(
        start_date=START,
        end_date=END,
        initial_capital=initial_capital,
        risk_free_rate=0.01,
        vol_target_annual=0.25,
        max_leverage=2.0,
    )

    qqq_asset = AssetConfig(symbol="QQQ", yf_symbol="QQQ")
    qqq_df = download_data(asset=qqq_asset, start_date=cfg.start_date, end_date=cfg.end_date)

    strategy = KAQTMultiAlphaEngine(config=cfg, asset_symbol="QQQ", price_df=qqq_df)

    bt = Backtester(
        config=cfg,
        data_panel={"QQQ": qqq_df},
        strategy=strategy,
    )

    results = bt.run()
    kaqt_eq = results["Equity"].copy()
    kaqt_eq.name = "KAQT"

    # ====== 2) QQQ & SPY buy-and-hold equity ======
    qqq_yf = yf.download("QQQ", start=str(START), end=str(END), progress=False, auto_adjust=False)
    spy_yf = yf.download("SPY", start=str(START), end=str(END), progress=False, auto_adjust=False)

    qqq_px = _get_close_series_from_yf(qqq_yf, prefer_adj=True)
    spy_px = _get_close_series_from_yf(spy_yf, prefer_adj=True)

    qqq_eq = equity_from_prices(qqq_px, initial_capital=initial_capital)
    spy_eq = equity_from_prices(spy_px, initial_capital=initial_capital)
    qqq_eq.name = "QQQ"
    spy_eq.name = "SPY"

    # Align dates
    common = kaqt_eq.index.intersection(qqq_eq.index).intersection(spy_eq.index)
    kaqt_eq = kaqt_eq.reindex(common).dropna()
    qqq_eq  = qqq_eq.reindex(common).dropna()
    spy_eq  = spy_eq.reindex(common).dropna()

    # ====== 3) Annual returns table ======
    yearly = pd.DataFrame({
        "KAQT %": yearly_returns_from_equity(kaqt_eq),
        "QQQ %":  yearly_returns_from_equity(qqq_eq),
        "SPY %":  yearly_returns_from_equity(spy_eq),
    }).dropna(how="all")

    print("\n========== YEARLY RETURNS (%) ==========")
    print(yearly.to_string())
    print("=======================================\n")

    # ====== 4) Plot equity curves ======
    plt.figure()
    plt.plot(kaqt_eq.index, kaqt_eq.values, label="KAQT")
    plt.plot(qqq_eq.index,  qqq_eq.values,  label="QQQ Buy&Hold")
    plt.plot(spy_eq.index,  spy_eq.values,  label="SPY Buy&Hold")
    plt.title("Equity Curve Comparison (Same Starting Capital)")
    plt.xlabel("Date")
    plt.ylabel("Equity ($)")
    plt.legend()
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()