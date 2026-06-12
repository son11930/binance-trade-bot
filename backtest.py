from binance.client import Client
from binance.client import Client
from datetime import datetime, timedelta, timezone
import pandas as pd
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from bot.strategy import apply_indicators

client = Client()
symbol = "BTCUSDT"
interval = Client.KLINE_INTERVAL_1HOUR

start_str = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%d %b %Y %H:%M:%S")
print(f"Fetching 1 year of data since {start_str}...")
klines = client.get_historical_klines(symbol, interval, start_str)

df = pd.DataFrame(klines, columns=[
    'timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time',
    'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume',
    'taker_buy_quote_asset_volume', 'ignore'
])
df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
for col in ['open', 'high', 'low', 'close', 'volume']:
    df[col] = df[col].astype(float)

df = apply_indicators(df)

capital = 1000.0
position = 0.0
buy_price = 0.0
stop_loss_pct = 2.5
trades = []

for i in range(200, len(df)):
    row = df.iloc[i]
    prev_row = df.iloc[i-1]
    price = row['close']
    macd = row['MACD']
    signal_line = row['Signal_Line']
    prev_macd = prev_row['MACD']
    prev_signal = prev_row['Signal_Line']
    sma_200 = row['SMA_200']
    
    is_uptrend = price > sma_200
    macd_bullish_cross = prev_macd <= prev_signal and macd > signal_line
    macd_bearish_cross = prev_macd >= prev_signal and macd < signal_line
    
    if position > 0:
        drop = (buy_price - price) / buy_price * 100
        if drop >= stop_loss_pct:
            capital += (position * price)
            trades.append({"type": "LOSS", "profit_pct": -drop, "reason": "Stop Loss"})
            position = 0.0
            continue
            
    if position == 0 and macd_bullish_cross and is_uptrend:
        invest = 10.0
        if capital >= invest:
            capital -= invest
            position = invest / price
            buy_price = price
            
    elif position > 0 and macd_bearish_cross:
        profit = (price - buy_price) / buy_price * 100
        capital += (position * price)
        trades.append({"type": "WIN" if profit > 0 else "LOSS", "profit_pct": profit, "reason": "MACD Death Cross"})
        position = 0.0

if position > 0:
    price = df.iloc[-1]['close']
    profit = (price - buy_price) / buy_price * 100
    capital += (position * price)
    trades.append({"type": "WIN" if profit > 0 else "LOSS", "profit_pct": profit, "reason": "End of period"})

wins = [t for t in trades if t["type"] == "WIN"]
losses = [t for t in trades if t["type"] == "LOSS"]

print(f"\n--- 1 Year Backtest (Layer 1 Only) ---")
for i, t in enumerate(trades):
    print(f"Trade {i+1}: {t['type']} | Profit: {t['profit_pct']:.2f}% | Reason: {t['reason']}")

print(f"Total Trades: {len(trades)}")
print(f"Wins: {len(wins)}")
print(f"Losses: {len(losses)}")
if len(trades) > 0:
    print(f"Win Rate: {len(wins) / len(trades) * 100:.2f}%")
print(f"Final Capital (Started $1000, $10 per trade): ${capital:.2f}")
