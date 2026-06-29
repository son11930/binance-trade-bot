import pandas as pd
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from bot.binance_client import futures_get_klines
from bot.strategy import analyze_futures_market, apply_indicators

def check_market(symbol):
    print(f"\n--- Checking {symbol} ---")
    df = futures_get_klines(symbol, "15m", limit=300)
    df = apply_indicators(df)
    if df is not None:
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        print(f"Current Price: {latest['close']:.4f}")
        print(f"EMA 50: {latest['EMA_50']:.4f}")
        print(f"RSI: {latest['RSI']:.2f} (Prev: {prev['RSI']:.2f})")
        print(f"MACD Hist: {latest['MACD_Histogram']:.6f} (Prev: {prev['MACD_Histogram']:.6f})")
        print(f"Volume: {latest['volume']:.2f} (SMA: {latest['SMA_20_Vol']:.2f})")
        print(f"BB Lower: {latest['BB_Lower']:.4f}")
        print(f"BB Upper: {latest['BB_Upper']:.4f}")
        
        rsi_hook_up = latest['RSI'] > prev['RSI'] and prev['RSI'] < 30
        print(f"RSI Hook Up: {rsi_hook_up}")
        
        rsi_hook_down = latest['RSI'] < prev['RSI'] and prev['RSI'] > 70
        print(f"RSI Hook Down: {rsi_hook_down}")
        
        fast_momentum_up = latest['MACD_Histogram'] > prev['MACD_Histogram'] and latest['MACD_Histogram'] > 0
        print(f"Fast Momentum Up: {fast_momentum_up}")
        
        fast_momentum_down = latest['MACD_Histogram'] < prev['MACD_Histogram'] and latest['MACD_Histogram'] < 0
        print(f"Fast Momentum Down: {fast_momentum_down}")
        
        strong_volume = latest['volume'] > (latest['SMA_20_Vol'] * 0.8)
        print(f"Strong Volume: {strong_volume}")
        
        signal = analyze_futures_market(df)
        print(f"\nFinal Signal: {signal.action} ({signal.strategy_used})")
        if signal.near_miss_reason:
            print(f"Near Miss: {signal.near_miss_reason}")
    else:
        print("Failed to fetch data")

check_market("BNBUSDT")
check_market("BTCUSDT")
check_market("ADAUSDT")
