from binance.client import Client
from datetime import datetime, timedelta, timezone
import pandas as pd
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from bot.strategy import apply_indicators, analyze_futures_market

client = Client()
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT"]
interval = Client.KLINE_INTERVAL_15MINUTE

start_str = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%d %b %Y %H:%M:%S")
print(f"Fetching 30 days of 15m data since {start_str}...")

capital = 1000.0
trades = []

for symbol in SYMBOLS:
    print(f"Backtesting {symbol}...")
    try:
        klines = client.get_historical_klines(symbol, interval, start_str)
    except Exception as e:
        print(f"Skipping {symbol}: {e}")
        continue
        
    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time',
        'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume',
        'taker_buy_quote_asset_volume', 'ignore'
    ])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)

    df = apply_indicators(df)

    position = 0.0
    position_side = ""
    buy_price = 0.0
    highest_price = 0.0
    lowest_price = float('inf')
    
    active_strategy = "NONE"
    dynamic_sl = 0.0
    dynamic_tp = 0.0

    for i in range(200, len(df)):
        # Very fast slice simulation
        slice_df = df.iloc[:i+1]
        row = slice_df.iloc[-1]
        price = row['close']
        atr_value = row['ATR']
        
        if position > 0:
            if position_side == "LONG":
                if price > highest_price: highest_price = price
                if price < lowest_price: lowest_price = price
                profit_percent = (((price - buy_price) / buy_price) * 100) * 3  # 3x leverage
            else:
                if price < lowest_price: lowest_price = price
                if price > highest_price: highest_price = price
                profit_percent = (((buy_price - price) / buy_price) * 100) * 3

            profit_percent -= 0.1  # 0.1% fees

            rm_signal = None
            if position_side == "LONG":
                if dynamic_tp > 0 and price >= dynamic_tp: rm_signal = "Take Profit"
                elif dynamic_sl > 0 and price <= dynamic_sl: rm_signal = "Stop Loss"
            else:
                if dynamic_tp > 0 and price <= dynamic_tp: rm_signal = "Take Profit"
                elif dynamic_sl > 0 and price >= dynamic_sl: rm_signal = "Stop Loss"

            if rm_signal:
                capital += (position * buy_price) * (profit_percent / 100)
                trades.append({"symbol": symbol, "type": "WIN" if profit_percent > 0 else "LOSS", "profit_pct": profit_percent, "reason": rm_signal})
                position = 0.0
                position_side = ""
                continue
                
        signal_plan = analyze_futures_market(slice_df)
        signal = signal_plan.action
        
        if position == 0 and signal in ["BUY", "SELL"]:
            invest = capital * 0.20  # 20% allocation per trade
            if invest < 10.0: invest = 10.0
            
            if capital >= invest:
                position = (invest * 3) / price  # 3x leverage qty
                buy_price = price
                highest_price = price
                lowest_price = price
                position_side = signal_plan.position_side
                dynamic_sl = signal_plan.stop_loss
                dynamic_tp = signal_plan.take_profit
                active_strategy = signal_plan.strategy_used

print("\n--- RESULTS ---")
print(f"Final Capital: ${capital:.2f}")
wins = len([t for t in trades if t['type'] == 'WIN'])
losses = len([t for t in trades if t['type'] == 'LOSS'])
total = wins + losses
win_rate = (wins / total * 100) if total > 0 else 0
print(f"Total Trades: {total} (Wins: {wins}, Losses: {losses})")
print(f"Win Rate: {win_rate:.2f}%")
