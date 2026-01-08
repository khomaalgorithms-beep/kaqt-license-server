import datetime as dt
from typing import Dict, List

import pandas as pd
import yfinance as yf

from .config import AssetConfig


def download_data(
    asset: AssetConfig,
    start_date: dt.date,
    end_date: dt.date,
) -> pd.DataFrame:
    """
    Clean, simple data downloader.

    - No caching
    - No CSV reading
    - Always pulls fresh from yfinance
    """
    print(f"[DATA] Downloading {asset.yf_symbol} from yfinance...")

    df = yf.download(
        asset.yf_symbol,
        start=start_date,
        end=end_date + dt.timedelta(days=1),
        progress=False,
        auto_adjust=False,  # keep raw OHLC + Adj Close if available
    )

    if df.empty:
        raise ValueError(f"No data returned for {asset.yf_symbol}.")

    # Ensure index is datetime and called 'Date'
    df = df.rename_axis("Date")
    df.index = pd.to_datetime(df.index)

    # If 'Adj Close' is missing, synthesize it from 'Close'
    if "Adj Close" not in df.columns and "Close" in df.columns:
        df["Adj Close"] = df["Close"]

    # Enforce required columns
    needed_cols = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    missing = [c for c in needed_cols if c not in df.columns]
    if missing:
        raise ValueError(f"{asset.yf_symbol}: missing columns in data: {missing}")

    df = df[needed_cols].copy()
    df.columns = ["open", "high", "low", "close", "adj_close", "volume"]
    df = df.sort_index()
    df = df.dropna()

    return df


def load_universe_data(
    assets: List[AssetConfig],
    start_date: dt.date,
    end_date: dt.date,
    force_refresh: bool = False,  # kept for compatibility, ignored
) -> Dict[str, pd.DataFrame]:
    """
    Loads OHLCV data for all configured assets (fresh each time).
    Returns a dict: {asset_symbol: df}
    """
    data = {}
    for a in assets:
        df = download_data(a, start_date, end_date)
        data[a.symbol] = df
    return data