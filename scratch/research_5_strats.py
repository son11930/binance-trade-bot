import pandas as pd
import numpy as np
from binance.client import Client
from datetime import datetime, timedelta
import os

client = Client()
symbols = ["BTCUSDT", "ETHUSDT", "XRPUSDT"]
interval = Client.KLINE_INTERVAL_1HOUR

dataframes = {}

for sym in symbols:
    filename = f"{sym}_1h_1y.csv"
    if not os.path.exists(filename):
        print(f"Fetching 1 year of 1h data for {sym}...")
        start_str = (datetime.utcnow() - timedelta(days=365)).strftime("%d %b %Y %H:%M:%S")
        klines = client.get_historical_klines(sym, interval, start_str)
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
        df = pd.read_csv(filename)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
    dataframes[sym] = df
    print(f"Loaded {sym}: {len(df)} candles.")

def run_backtest(df, strategy_func):
    df = df.copy()
    capital = 1000.0
    position = 0.0
    buy_price = 0.0
    trades = []
    
    signals = strategy_func(df) # returns dict of arrays
    closes = df['close'].values
    buy_signal = signals['buy']
    sell_signal = signals['sell']
    
    stop_loss_pct = 2.5
    
    for i in range(200, len(closes)):
        price = closes[i]
        
        if position > 0:
            drop = (buy_price - price) / buy_price * 100
            if drop >= stop_loss_pct:
                capital += position * price
                trades.append({"type": "LOSS", "profit_pct": -drop})
                position = 0.0
                continue
                
            if sell_signal[i]:
                profit = (price - buy_price) / buy_price * 100
                capital += position * price
                trades.append({"type": "WIN" if profit > 0 else "LOSS", "profit_pct": profit})
                position = 0.0
                
        else:
            if buy_signal[i]:
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
        "trades": len(trades),
        "wins": len(wins),
        "win_rate": (len(wins) / len(trades) * 100) if trades else 0,
        "final_capital": capital,
        "avg_profit": sum(t['profit_pct'] for t in trades) / len(trades) if trades else 0
    }

# Strategy 1: MACD + SMA200
def strat_macd_sma200(df):
    ema_fast = df['close'].ewm(span=12, adjust=False).mean()
    ema_slow = df['close'].ewm(span=26, adjust=False).mean()
    macd = ema_fast - ema_slow
    sig = macd.ewm(span=9, adjust=False).mean()
    sma200 = df['close'].rolling(200).mean()
    
    buy = (macd > sig) & (macd.shift(1) <= sig.shift(1)) & (df['close'] > sma200)
    sell = (macd < sig) & (macd.shift(1) >= sig.shift(1))
    return {'buy': buy.values, 'sell': sell.values}

# Strategy 2: EMA 9/21 Crossover + SMA200
def strat_ema_cross(df):
    ema9 = df['close'].ewm(span=9, adjust=False).mean()
    ema21 = df['close'].ewm(span=21, adjust=False).mean()
    sma200 = df['close'].rolling(200).mean()
    
    buy = (ema9 > ema21) & (ema9.shift(1) <= ema21.shift(1)) & (df['close'] > sma200)
    sell = (ema9 < ema21) & (ema9.shift(1) >= ema21.shift(1))
    return {'buy': buy.values, 'sell': sell.values}

# Strategy 3: RSI Mean Reversion (Buy < 30, Sell > 50) + SMA200 Filter
def strat_rsi_mr(df):
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    sma200 = df['close'].rolling(200).mean()
    
    buy = (rsi < 30) & (df['close'] > sma200)
    sell = (rsi > 50)
    return {'buy': buy.values, 'sell': sell.values}

# Strategy 4: Bollinger Bands Reversion
def strat_bb_mr(df):
    sma20 = df['close'].rolling(20).mean()
    std20 = df['close'].rolling(20).std()
    lower = sma20 - (std20 * 2)
    upper = sma20 + (std20 * 2)
    sma200 = df['close'].rolling(200).mean()
    
    buy = (df['close'] < lower) & (df['close'] > sma200)
    sell = (df['close'] > upper)
    return {'buy': buy.values, 'sell': sell.values}

# Strategy 5: Momentum Breakout (RSI > 60 Buy, RSI < 40 Sell)
def strat_rsi_momentum(df):
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0).ewm(alpha=1/14, adjust=False).mean()
    loss = (-delta.where(delta < 0, 0)).ewm(alpha=1/14, adjust=False).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    sma200 = df['close'].rolling(200).mean()
    
    buy = (rsi > 60) & (rsi.shift(1) <= 60) & (df['close'] > sma200)
    sell = (rsi < 40) & (rsi.shift(1) >= 40)
    return {'buy': buy.values, 'sell': sell.values}

strats = {
    "MACD + SMA200": strat_macd_sma200,
    "EMA 9/21 Cross": strat_ema_cross,
    "RSI Mean Reversion": strat_rsi_mr,
    "Bollinger Bands": strat_bb_mr,
    "RSI Momentum Breakout": strat_rsi_momentum
}

print("\n--- Backtest Results (1 Year on 1H Timeframe for BTC, ETH, XRP) ---")
for s_name, s_func in strats.items():
    print(f"\nEvaluating: {s_name}")
    total_trades = 0
    total_wins = 0
    combined_cap = 1000.0 * len(symbols)
    total_profit_pct_sum = 0
    
    for sym in symbols:
        res = run_backtest(dataframes[sym], s_func)
        total_trades += res['trades']
        total_wins += res['wins']
        combined_cap += (res['final_capital'] - 1000.0)
        total_profit_pct_sum += res['avg_profit'] * res['trades']
        
    overall_win_rate = (total_wins / total_trades * 100) if total_trades else 0
    avg_prof = total_profit_pct_sum / total_trades if total_trades else 0
    print(f"Overall Trades (All 3 Coins): {total_trades} (~{total_trades/365:.2f} per day)")
    print(f"Overall Win Rate: {overall_win_rate:.2f}%")
    print(f"Avg Profit/Trade: {avg_prof:.2f}%")
