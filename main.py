import os
import datetime as dt

import matplotlib.pyplot as plt
import pandas as pd
import getpass

from license_manager import validate_license
from kaqt_app import default_engine_config, AssetConfig
from kaqt_app import load_universe_data
from kaqt_app import Backtester
from kaqt_app import KAQTMultiAlphaEngine


def plot_equity_curve(equity, out_path: str):
    """
    Create a clean, institutional-style equity curve chart.

    - Log scale (standard in quant reports)
    - Light grid
    - Simple, professional styling
    """
    # Convert to Series if needed
    if isinstance(equity, pd.DataFrame):
        equity = equity.iloc[:, 0]
    elif not isinstance(equity, pd.Series):
        equity = pd.Series(equity)

    eq = equity.copy()
    # Ensure datetime index if possible
    try:
        eq.index = pd.to_datetime(eq.index)
    except Exception:
        pass

    plt.figure(figsize=(10, 6))

    # Equity curve
    plt.plot(eq.index, eq.values)

    plt.title("KAQT Multi-Alpha Engine v3.0\nEquity Curve (Starting Capital: $20,000)")
    plt.xlabel("Date")
    plt.ylabel("Portfolio Value (USD)")

    # Log scale is what banks / institutional reports usually use
    plt.yscale("log")

    # Subtle grid
    plt.grid(True, which="both", linestyle="--", linewidth=0.5, alpha=0.7)

    plt.tight_layout()
    plt.savefig(out_path, dpi=300)
    plt.close()


def main():
    # Make sure we know exactly where we are saving files
    base_dir = os.path.dirname(os.path.abspath(__file__))

    # =========================
    # 1. Engine configuration
    # =========================
    cfg = default_engine_config()
    cfg.start_date = dt.date(2005, 1, 1)
    cfg.end_date = dt.date(2025, 1, 1)

    # NQ Aggressive v1.0 risk settings (baseline)
    cfg.vol_target_annual = 0.25   # 25% annual vol target
    cfg.max_leverage = 5.0         # allow up to 5x notional

    # =========================
    # 2. Define asset (NQ proxy via QQQ)
    # =========================
    nq_asset = AssetConfig(
        symbol="NQ",
        yf_symbol="QQQ",
        weight=1.0,
    )

    def main():
        print("=== KAQT Multi-Alpha Engine v3.0 ===")
        print("License verification required.\n")

        # 🔐 Ask user for their KAQT license key (passcode)
        license_key = getpass.getpass("Enter your KAQT license key: ")

        if not validate_license(license_key):
            print("\n[LICENSE] Invalid or inactive license key.")
            print("Please check your passcode or contact KhomaAlgorithms support.")
            return  # stop the program here

        print("[LICENSE] License validated. Loading engine...\n")

        # ⬇️ Your existing backtest / live engine code goes below ⬇️
        # e.g.
        # data_panel = load_universe_data(...)
        # engine = KAQTMultiAlphaEngine(...)
        # bt = Backtester(...)
        # result = bt.run()

    # =========================
    # 3. Load data
    # =========================
    data_panel = load_universe_data(
        [nq_asset],
        start_date=cfg.start_date,
        end_date=cfg.end_date,
        force_refresh=False,
    )

    if "NQ" not in data_panel:
        raise ValueError("NQ data not found in data_panel. Check data_loader / symbol mapping.")

    df_nq = data_panel["NQ"]

    if df_nq.empty:
        raise ValueError("No price data for NQ. Check internet / yf_symbol='QQQ'.")

    # =========================
    # 4. Strategy: Multi-Alpha Engine
    # =========================
    strat = KAQTMultiAlphaEngine(cfg, "NQ", df_nq)

    # =========================
    # 5. Backtest
    # =========================
    bt = Backtester(
        config=cfg,
        data_panel={"NQ": df_nq},
        strategy=strat,
    )

    result = bt.run()

    # =========================
    # 6. Print results
    # =========================
    print("=== KAQT Multi-Alpha Engine v3.0 Backtest ===")
    print(f"CAGR: {result['CAGR']:.4f}")
    print(f"Vol_Annual: {result['Vol_Annual']:.4f}")
    print(f"Sharpe: {result['Sharpe']:.4f}")
    print(f"Max_Drawdown: {result['Max_Drawdown']:.4f}")

    # =========================
    # 7. Save outputs (CSV)
    # =========================
    equity = result["Equity"]
    weights = result["Weights"]

    equity_csv_path = os.path.join(base_dir, "kaqt_v3_equity_curve.csv")
    weights_csv_path = os.path.join(base_dir, "kaqt_v3_weights.csv")

    pd.DataFrame(equity).to_csv(equity_csv_path, header=["equity"])
    pd.DataFrame(weights).to_csv(weights_csv_path)
    print(f"Saved equity curve CSV to: {equity_csv_path}")
    print(f"Saved weights CSV to:     {weights_csv_path}")

    # =========================
    # 8. Generate institutional equity chart (PNG)
    # =========================
    equity_png_path = os.path.join(base_dir, "kaqt_v3_equity_curve.png")
    plot_equity_curve(equity, equity_png_path)
    print(f"Saved bank-ready equity curve chart to: {equity_png_path}")


if __name__ == "__main__":
    main()