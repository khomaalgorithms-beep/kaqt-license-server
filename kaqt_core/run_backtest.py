import datetime as dt

from kaqt_app import EngineConfig
from kaqt_app import download_data
from kaqt_app import KAQTMultiAlphaEngine
from kaqt_app import Backtester


def run_backtest():
    cfg = EngineConfig(
        start_date=dt.date(2005, 1, 1),
        end_date=dt.date(2025, 1, 1),
        initial_capital=100_000.0,
        vol_target_annual=0.30,
        max_leverage=2.0,
    )

    from kaqt_app import AssetConfig
    qqq = AssetConfig(symbol="QQQ", yf_symbol="QQQ")

    data = download_data(
        asset=qqq,
        start_date=cfg.start_date,
        end_date=cfg.end_date,
    )

    strategy = KAQTMultiAlphaEngine(
        config=cfg,
        asset_symbol="QQQ",
        price_df=data,
    )

    bt = Backtester(
        config=cfg,
        data_panel={"QQQ": data},
        strategy=strategy,
    )

    results = bt.run()

    print("\n========== KAQT BACKTEST RESULTS ==========")
    print(f"CAGR:           {results['CAGR']*100:.2f}%")
    print(f"Annual Vol:     {results['Vol_Annual']*100:.2f}%")
    print(f"Sharpe Ratio:   {results['Sharpe']:.2f}")
    print(f"Max Drawdown:   {results['Max_Drawdown']*100:.2f}%")
    print("===========================================\n")


if __name__ == "__main__":
    run_backtest()