import pandas as pd
import numpy as np

symbols = ["BTCUSDT", "ETHUSDT", "XRPUSDT"]
all_trade_times = []

def strat_macd_sma200(df):
    ema_fast = df['close'].ewm(span=12, adjust=False).mean()
    ema_slow = df['close'].ewm(span=26, adjust=False).mean()
    macd = ema_fast - ema_slow
    sig = macd.ewm(span=9, adjust=False).mean()
    sma200 = df['close'].rolling(200).mean()
    
    buy = (macd > sig) & (macd.shift(1) <= sig.shift(1)) & (df['close'] > sma200)
    sell = (macd < sig) & (macd.shift(1) >= sig.shift(1))
    return buy.values, sell.values

for sym in symbols:
    df = pd.read_csv(f"{sym}_1h_1y.csv")
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    buy_sig, sell_sig = strat_macd_sma200(df)
    closes = df['close'].values
    times = df['timestamp'].values
    
    position = 0.0
    buy_price = 0.0
    
    for i in range(200, len(closes)):
        price = closes[i]
        
        if position > 0:
            drop = (buy_price - price) / buy_price * 100
            if drop >= 2.5:
                position = 0.0
                continue
            if sell_sig[i]:
                position = 0.0
        else:
            if buy_sig[i]:
                position = 1.0
                buy_price = price
                all_trade_times.append(times[i])

if len(all_trade_times) > 0:
    times_series = pd.Series(all_trade_times).sort_values().reset_index(drop=True)
    gaps = times_series.diff().dt.total_seconds() / (3600 * 24)
    max_gap = gaps.max()
    print(f"Max gap in days: {max_gap:.2f}")
    
    max_idx = gaps.idxmax()
    start_gap = times_series.iloc[max_idx - 1]
    end_gap = times_series.iloc[max_idx]
    print(f"Gap from {pd.to_datetime(start_gap).strftime('%Y-%m-%d')} to {pd.to_datetime(end_gap).strftime('%Y-%m-%d')}")
else:
    print("No trades found.")
