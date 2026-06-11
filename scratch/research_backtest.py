import pandas as pd
import numpy as np
from binance.client import Client
from datetime import datetime, timedelta
import os

client = Client()
symbol = "BTCUSDT"
interval = Client.KLINE_INTERVAL_15MINUTE
filename = "btc_15m_1y.csv"

# 1. Fetch Data
if not os.path.exists(filename):
    print("Fetching 1 year of 15m data... this may take a moment.")
    start_str = (datetime.utcnow() - timedelta(days=365)).strftime("%d %b %Y %H:%M:%S")
    klines = client.get_historical_klines(symbol, interval, start_str)
    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time',
        'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume',
        'taker_buy_quote_asset_volume', 'ignore'
    ])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
    df.to_csv(filename, index=False)
else:
    print("Loading data from local CSV...")
    df = pd.read_csv(filename)
    df['timestamp'] = pd.to_datetime(df['timestamp'])

print(f"Data loaded: {len(df)} candles.")

def backtest_ema_crossover(df, short_window=9, long_window=21, stop_loss_pct=2.5):
    df = df.copy()
    df['EMA_short'] = df['close'].ewm(span=short_window, adjust=False).mean()
    df['EMA_long'] = df['close'].ewm(span=long_window, adjust=False).mean()
    
    capital = 1000.0
    position = 0.0
    buy_price = 0.0
    trades = []
    
    closes = df['close'].values
    ema_s = df['EMA_short'].values
    ema_l = df['EMA_long'].values
    
    for i in range(50, len(closes)):
        price = closes[i]
        
        if position > 0:
            drop = (buy_price - price) / buy_price * 100
            if drop >= stop_loss_pct:
                capital += position * price
                trades.append({"type": "LOSS", "profit_pct": -drop})
                position = 0.0
                continue
                
            # Exit condition: Short EMA crosses below Long EMA
            if ema_s[i] < ema_l[i] and ema_s[i-1] >= ema_l[i-1]:
                profit = (price - buy_price) / buy_price * 100
                capital += position * price
                trades.append({"type": "WIN" if profit > 0 else "LOSS", "profit_pct": profit})
                position = 0.0
                
        else:
            # Buy condition: Short EMA crosses above Long EMA
            if ema_s[i] > ema_l[i] and ema_s[i-1] <= ema_l[i-1]:
                invest = 10.0
                if capital >= invest:
                    capital -= invest
                    position = invest / price
                    buy_price = price
                    
    if position > 0:
        price = closes[-1]
        profit = (price - buy_price) / buy_price * 100
        capital += position * price
        trades.append({"type": "WIN" if profit > 0 else "LOSS", "profit_pct": profit})

    wins = [t for t in trades if t["type"] == "WIN"]
    return {
        "name": f"EMA Crossover ({short_window}/{long_window})",
        "trades": len(trades),
        "wins": len(wins),
        "win_rate": (len(wins) / len(trades) * 100) if trades else 0,
        "final_capital": capital,
        "avg_profit": sum(t['profit_pct'] for t in trades) / len(trades) if trades else 0
    }

def backtest_macd_trend(df, fast=12, slow=26, signal=9, trend_window=200):
    df = df.copy()
    ema_fast = df['close'].ewm(span=fast, adjust=False).mean()
    ema_slow = df['close'].ewm(span=slow, adjust=False).mean()
    df['MACD'] = ema_fast - ema_slow
    df['Signal'] = df['MACD'].ewm(span=signal, adjust=False).mean()
    df['SMA_200'] = df['close'].rolling(window=trend_window).mean()
    
    capital = 1000.0
    position = 0.0
    buy_price = 0.0
    trades = []
    
    closes = df['close'].values
    macd = df['MACD'].values
    sig = df['Signal'].values
    sma200 = df['SMA_200'].values
    
    for i in range(trend_window, len(closes)):
        price = closes[i]
        
        if position > 0:
            drop = (buy_price - price) / buy_price * 100
            if drop >= 2.5: # fixed stop loss
                capital += position * price
                trades.append({"type": "LOSS", "profit_pct": -drop})
                position = 0.0
                continue
                
            # Exit: MACD crosses below Signal
            if macd[i] < sig[i] and macd[i-1] >= sig[i-1]:
                profit = (price - buy_price) / buy_price * 100
                capital += position * price
                trades.append({"type": "WIN" if profit > 0 else "LOSS", "profit_pct": profit})
                position = 0.0
                
        else:
            # Buy: MACD crosses above Signal AND Price > SMA200 (Uptrend)
            if macd[i] > sig[i] and macd[i-1] <= sig[i-1] and price > sma200[i]:
                invest = 10.0
                if capital >= invest:
                    capital -= invest
                    position = invest / price
                    buy_price = price
                    
    if position > 0:
        price = closes[-1]
        profit = (price - buy_price) / buy_price * 100
        capital += position * price
        trades.append({"type": "WIN" if profit > 0 else "LOSS", "profit_pct": profit})

    wins = [t for t in trades if t["type"] == "WIN"]
    return {
        "name": f"MACD + SMA{trend_window}",
        "trades": len(trades),
        "wins": len(wins),
        "win_rate": (len(wins) / len(trades) * 100) if trades else 0,
        "final_capital": capital,
        "avg_profit": sum(t['profit_pct'] for t in trades) / len(trades) if trades else 0
    }

results = []
results.append(backtest_ema_crossover(df, 9, 21))
results.append(backtest_ema_crossover(df, 20, 50))
results.append(backtest_macd_trend(df))

for r in results:
    print(f"--- {r['name']} ---")
    print(f"Trades: {r['trades']} | Win Rate: {r['win_rate']:.2f}% | Avg Profit/Trade: {r['avg_profit']:.2f}% | Final Cap: ${r['final_capital']:.2f}")

