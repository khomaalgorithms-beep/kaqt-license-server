# test_paper_broker.py

from kaqt_app import PaperBroker

def main():
    broker = PaperBroker(initial_cash=100_000)
    broker.connect()
    print("Connected:", broker.connected)
    print("Starting cash:", broker.cash)

    # Simulate some prices for QQQ
    broker.update_price("QQQ", 400.0)
    broker.market_order("QQQ", 100)   # buy 100 shares at 400
    broker.update_price("QQQ", 410.0)
    broker.market_order("QQQ", -50)   # sell 50 shares at 410

    print("\nPositions snapshot:")
    for p in broker.open_positions_snapshot():
        print(p)

    print("\nTrades:")
    for t in broker.trade_log_snapshot():
        print(t)

    print("\nCash:", broker.cash)
    print("Portfolio value:", broker.portfolio_value())
    print("Buying power:", broker.buying_power())

if __name__ == "__main__":
    main()