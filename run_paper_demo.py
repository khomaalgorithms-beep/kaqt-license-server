import yfinance as yf

# Import your core KAQT engine + config
from kaqt_app import EngineConfig
from kaqt_app import KAQTMultiAlphaEngine

# Import the paper broker simulator
from kaqt_app import PaperBroker


def main():
    print("=== PAPER BROKER DEMO (KAQT v3 SAFE ENGINE) ===")

    symbol = "QQQ"          # data symbol (ETF proxy for NQ)
    logical_asset = "NQ"    # name we use inside the engine/weights
    start = "2020-01-01"
    end   = "2021-01-01"

    print(f"[DATA] Downloading {symbol} from {start} to {end}...")
    df = yf.download(symbol, start=start, end=end, progress=False)

    if df.empty:
        print("ERROR: No data downloaded.")
        return

    # -------------------------------------------------
    # 1) Build engine + weights using your KAQT core
    # -------------------------------------------------
    cfg = EngineConfig()
    engine = KAQTMultiAlphaEngine(cfg, logical_asset, df)

    # This returns a DataFrame with ONE column named logical_asset (e.g. "NQ")
    weights_df = engine.generate_daily_target_weights()

    # Align weights with price index (handles weekends/holidays)
    weights_aligned = (
        weights_df
        .reindex(df.index)           # align to daily price index
        .fillna(method="ffill")      # forward-fill previous weight
        .fillna(0.0)                 # still NaN at very start → 0
    )

    # -------------------------------------------------
    # 2) Create paper broker and simulate trading
    # -------------------------------------------------
    broker = PaperBroker(starting_cash=100000)

    for date, row in df.iterrows():
        price = float(row["Close"])
        broker.update_price(logical_asset, price)

        # today's target weight for our logical asset "NQ"
        w = float(weights_aligned.loc[date, logical_asset])

        # portfolio value at start of day
        value = broker.get_value()

        # convert weight → target position size (shares/contracts)
        if price <= 0:
            continue

        target_pos = w * (value / price)

        # current position
        curr_pos = broker.position.get(logical_asset, 0.0)

        # difference is the order size
        qty = target_pos - curr_pos

        # execute order if meaningful
        if abs(qty) > 0.001:
            broker.send_order(logical_asset, qty)

    # -------------------------------------------------
    # 3) End of period — flatten and report
    # -------------------------------------------------
    broker.close_all()

    final_value = broker.get_value()
    print("\n=== PAPER DEMO COMPLETE ===")
    print("Final Portfolio Value:", round(final_value, 2))
    print("Number of trades:", len(broker.trade_log))


if __name__ == "__main__":
    main()