from binance.client import Client
from datetime import datetime, timedelta, timezone
import pandas as pd
import os
import sys

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from bot.strategy import apply_indicators, analyze_market

client = Client()
SYMBOLS = ["BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT", "AVAXUSDT", "DOGEUSDT", "DOTUSDT", "LINKUSDT"]
interval = Client.KLINE_INTERVAL_15MINUTE

start_str = (datetime.now(timezone.utc) - timedelta(days=90)).strftime("%d %b %Y %H:%M:%S")
print(f"Fetching 90 days of 15m data since {start_str}...")

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
    buy_price = 0.0
    highest_price = 0.0
    
    active_strategy = "NONE"
    dynamic_sl = 0.0
    dynamic_tp = 0.0
    time_in_trade = 0
    max_time_limit = 0

    for i in range(200, len(df)):
        slice_df = df.iloc[:i+1]
        row = slice_df.iloc[-1]
        price = row['close']
        atr_value = row['ATR']
        
        if position > 0:
            if price > highest_price:
                highest_price = price
                
            profit_percent = (((price - buy_price) - (buy_price + price) * 0.001) / buy_price) * 100
            hp_drop_percent = ((highest_price - price) / highest_price) * 100 if highest_price > 0 else 0
            max_profit_percent = (((highest_price - buy_price) - (buy_price + highest_price) * 0.001) / buy_price) * 100
            
            time_in_trade += 1
            
            rm_signal = None
            if max_time_limit > 0 and time_in_trade >= max_time_limit:
                rm_signal = "Time-in-Trade Stop"
            elif dynamic_tp > 0 and price >= dynamic_tp:
                rm_signal = "Dynamic Take Profit"
            elif profit_percent >= 3.0:
                rm_signal = "Take Profit"
            elif max_profit_percent >= 1.5 and hp_drop_percent >= 0.5:
                rm_signal = "Trailing Stop"
            elif dynamic_sl > 0 and price <= dynamic_sl:
                rm_signal = "Dynamic Stop Loss"
            else:
                atr_percent = (atr_value / price) * 100 if atr_value else 2.5
                fallback_sl = min(2.5, atr_percent * 1.5)
                if profit_percent <= -fallback_sl:
                    rm_signal = "Fallback Stop Loss"
                
            if rm_signal:
                capital += (position * price) - (buy_price + price) * position * 0.001
                trades.append({"symbol": symbol, "type": "WIN" if profit_percent > 0 else "LOSS", "profit_pct": profit_percent, "reason": rm_signal})
                position = 0.0
                highest_price = 0.0
                active_strategy = "NONE"
                continue
                
        signal_plan = analyze_market(slice_df)
        signal = signal_plan.action
        
        if position == 0 and signal == "BUY":
            invest = capital * 0.10  # 10% of portfolio per trade
            if invest < 10.0:
                invest = 10.0
            
            if capital >= invest:
                capital -= invest
                position = invest / price
                buy_price = price
                highest_price = price
                
                active_strategy = signal_plan.strategy_used
                dynamic_sl = signal_plan.stop_loss
                dynamic_tp = signal_plan.take_profit
                max_time_limit = signal_plan.time_in_trade
                time_in_trade = 0
                
        elif position > 0 and signal == "SELL":
            profit = (((price - buy_price) - (buy_price + price) * 0.001) / buy_price) * 100
            capital += (position * price) - (buy_price + price) * position * 0.001
            trades.append({"symbol": symbol, "type": "WIN" if profit > 0 else "LOSS", "profit_pct": profit, "reason": "Strategy SELL"})
            position = 0.0
            highest_price = 0.0
            active_strategy = "NONE"

    if position > 0:
        price = df.iloc[-1]['close']
        profit = (((price - buy_price) - (buy_price + price) * 0.001) / buy_price) * 100
        capital += (position * price) - (buy_price + price) * position * 0.001
        trades.append({"symbol": symbol, "type": "WIN" if profit > 0 else "LOSS", "profit_pct": profit, "reason": "End of period"})

wins = [t for t in trades if t['type'] == "WIN"]
losses = [t for t in trades if t['type'] == "LOSS"]

print("\n--- BACKTEST RESULTS (90 Days / 10 Coins / 15m) ---")
print(f"Initial Capital: $1000.00")
print(f"Final Capital:   ${capital:.2f}")
print(f"Net Profit:      ${capital - 1000.00:.2f} ({((capital - 1000.00) / 1000.00) * 100:.2f}%)")
print(f"Total Trades:    {len(trades)}")
print(f"Estimated Yearly: {len(trades) * 4} trades")
print(f"Wins: {len(wins)} | Losses: {len(losses)}")
if len(trades) > 0:
    print(f"Win Rate:        {(len(wins)/len(trades))*100:.2f}%")

print("\nRecent Trades:")
for t in trades[-10:]:
    print(f"- {t['symbol']} | {t['type']}: {t['profit_pct']:.2f}% ({t['reason']})")
