import os
import sys
import pandas as pd
from binance.client import Client
from datetime import datetime, timedelta, timezone
import ta

client = Client()
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT"]
interval = Client.KLINE_INTERVAL_30MINUTE

os.makedirs("scratch", exist_ok=True)

print("1. Loading 365 days of 30m klines...")
all_dfs = {}
for symbol in SYMBOLS:
    cache_file = f"scratch/{symbol}_30m_1y.pkl"
    if os.path.exists(cache_file):
        df = pd.read_pickle(cache_file)
        if df['timestamp'].dt.tz is None:
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
    else:
        print(f"Fetching from Binance API: {symbol}...")
        start_str = (datetime.now(timezone.utc) - timedelta(days=365)).strftime("%d %b %Y %H:%M:%S")
        klines = client.get_historical_klines(symbol, interval, start_str)
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time',
            'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume',
            'taker_buy_quote_asset_volume', 'ignore'
        ])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms', utc=True)
        df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
        
        df['SMA_200'] = ta.trend.sma_indicator(df['close'], window=200)
        df['SMA_99'] = ta.trend.sma_indicator(df['close'], window=99)
        df['EMA_50'] = ta.trend.ema_indicator(df['close'], window=50)
        df['RSI'] = ta.momentum.rsi(df['close'], window=14)
        df['BB_Upper'] = ta.volatility.bollinger_hband(df['close'], window=20, window_dev=2)
        df['BB_Lower'] = ta.volatility.bollinger_lband(df['close'], window=20, window_dev=2)
        df['ADX'] = ta.trend.adx(df['high'], df['low'], df['close'], window=14)
        df['ATR'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14)
        df['SMA_20_Vol'] = ta.trend.sma_indicator(df['volume'], window=20)
        
        df.to_pickle(cache_file)
    all_dfs[symbol] = df

print("Data loaded successfully.\n")

def run_simulation(dfs, days, rsi_long_th=70, rsi_short_th=30, sl_mult=1.2):
    total_capital = 1000.0
    wins = 0
    losses = 0
    trades = []
    rsi_sniper_count = 0
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    for symbol, df_full in dfs.items():
        df = df_full[df_full['timestamp'] >= pd.to_datetime(cutoff_date, utc=True)].copy().reset_index(drop=True)
        if len(df) < 50:
            continue
            
        position = 0.0
        position_side = ""
        buy_price = 0.0
        highest_price = 0.0
        lowest_price = float('inf')
        dynamic_sl = 0.0
        
        for i in range(20, len(df)):
            row = df.iloc[i]
            prev = df.iloc[i-1]
            price = row['close']
            atr = row['ATR']
            
            if pd.isna(row['SMA_200']) or pd.isna(row['ATR']):
                continue
                
            if position > 0:
                if position_side == "LONG":
                    profit_percent = (((price - buy_price) / buy_price) * 100) * 3
                else:
                    profit_percent = (((buy_price - price) / buy_price) * 100) * 3
                profit_percent -= 0.1 # fee
                
                rm_signal = ""
                if position_side == "LONG":
                    if price <= dynamic_sl: rm_signal = "Stop Loss"
                    elif profit_percent >= 2.0 and row['RSI'] > rsi_long_th: 
                        rm_signal = "RSI Sniper Exit"
                        rsi_sniper_count += 1
                else:
                    if price >= dynamic_sl: rm_signal = "Stop Loss"
                    elif profit_percent >= 2.0 and row['RSI'] < rsi_short_th: 
                        rm_signal = "RSI Sniper Exit"
                        rsi_sniper_count += 1
                        
                if rm_signal:
                    pnl = (position * buy_price) * (profit_percent / 100)
                    total_capital += pnl
                    if profit_percent > 0: wins += 1
                    else: losses += 1
                    trades.append({"symbol": symbol, "profit_pct": profit_percent, "reason": rm_signal})
                    position = 0.0
                    continue

            if position == 0:
                sma_200 = row['SMA_200']
                ema_50 = row['EMA_50']
                sma_99 = row['SMA_99']
                bb_upper = row['BB_Upper']
                bb_lower = row['BB_Lower']
                
                is_macro_uptrend = price > sma_200
                is_macro_downtrend = price < sma_200
                
                strong_volume = row['volume'] > row['SMA_20_Vol']
                
                body = abs(row['close'] - row['open'])
                lower_wick = min(row['open'], row['close']) - row['low']
                upper_wick = row['high'] - max(row['open'], row['close'])
                is_giant = body > (atr * 2.0)
                
                bullish_sweep = (lower_wick > 2 * body) and (row['low'] <= bb_lower) and (row['close'] > bb_lower)
                bearish_sweep = (upper_wick > 2 * body) and (row['high'] >= bb_upper) and (row['close'] < bb_upper)
                
                sma200_bounce = (row['low'] <= sma_200) and (row['close'] > sma_200) and (row['close'] > row['open'])
                sma200_reject = (row['high'] >= sma_200) and (row['close'] < sma_200) and (row['close'] < row['open'])
                
                bullish_div = False
                bearish_div = False
                if i >= 16:
                    window = df.iloc[i-15:i]
                    prev_min_idx = window['close'].idxmin()
                    if row['close'] <= df.loc[prev_min_idx, 'close'] and row['RSI'] > df.loc[prev_min_idx, 'RSI'] + 2.0 and row['close'] > row['open']:
                        bullish_div = True
                    prev_max_idx = window['close'].idxmax()
                    if row['close'] >= df.loc[prev_max_idx, 'close'] and row['RSI'] < df.loc[prev_max_idx, 'RSI'] - 2.0 and row['close'] < row['open']:
                        bearish_div = True
                        
                sniper_long = (bullish_sweep or bullish_div or sma200_bounce) and strong_volume and is_macro_uptrend and not is_giant and (row['close'] <= bb_upper)
                sniper_short = (bearish_sweep or bearish_div or sma200_reject) and strong_volume and is_macro_downtrend and not is_giant and (row['close'] >= bb_lower)
                
                if sniper_long:
                    invest = total_capital * 0.20
                    position = (invest * 3) / price
                    buy_price = price
                    position_side = "LONG"
                    dynamic_sl = price - (atr * sl_mult)
                elif sniper_short:
                    invest = total_capital * 0.20
                    position = (invest * 3) / price
                    buy_price = price
                    position_side = "SHORT"
                    dynamic_sl = price + (atr * sl_mult)

    total_trades = wins + losses
    win_rate = (wins / total_trades * 100) if total_trades > 0 else 0.0
    net_profit = total_capital - 1000.0
    net_pct = (net_profit / 1000.0) * 100
    
    return {
        "final_cap": total_capital,
        "net_profit": net_profit,
        "net_pct": net_pct,
        "trades": total_trades,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate,
        "rsi_snipers": rsi_sniper_count
    }

print("=== PART 1: MULTI-PERIOD BACKTEST RESULTS (30m Timeframe, 3x Leverage, 20% Compounding Sizing) ===")
periods = [(30, "1 Month (30 Days)"), (90, "3 Months (90 Days)"), (180, "6 Months (180 Days)"), (365, "1 Year (365 Days)")]
for days, label in periods:
    res = run_simulation(all_dfs, days=days)
    print(f"[{label}]")
    print(f"  Final Capital: ${res['final_cap']:.2f} | Net Profit: ${res['net_profit']:.2f} (+{res['net_pct']:.2f}%)")
    print(f"  Total Trades:  {res['trades']} (Wins: {res['wins']} | Losses: {res['losses']} | Win Rate: {res['win_rate']:.2f}%)")
    print(f"  RSI Sniper Exits Triggered: {res['rsi_snipers']} times\n")

print("=== PART 7: 1-MONTH RSI THRESHOLD SENSITIVITY BACKTEST ===")
print("Comparing different RSI levels for Sniper Exit (Long RSI > X / Short RSI < Y) over the last 30 days:")
rsi_levels = [(65, 35), (70, 30), (75, 25), (80, 20)]
for r_long, r_short in rsi_levels:
    res = run_simulation(all_dfs, days=30, rsi_long_th=r_long, rsi_short_th=r_short)
    print(f"RSI Thresholds (Long > {r_long} / Short < {r_short}):")
    print(f"  Net Profit: ${res['net_profit']:.2f} (+{res['net_pct']:.2f}%) | Win Rate: {res['win_rate']:.2f}% | RSI Snipers Triggered: {res['rsi_snipers']} times")
