import pandas as pd
from binance.client import Client
from datetime import datetime, timedelta, timezone
import ta
import itertools

client = Client()
SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT"]
interval = Client.KLINE_INTERVAL_1HOUR

start_str = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%d %b %Y %H:%M:%S")
print(f"Fetching 30 days of 1h data since {start_str}...")

all_dfs = {}
for symbol in SYMBOLS:
    try:
        klines = client.get_historical_klines(symbol, interval, start_str)
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time',
            'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume',
            'taker_buy_quote_asset_volume', 'ignore'
        ])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
        
        # Precompute ALL indicators
        df['SMA_200'] = ta.trend.sma_indicator(df['close'], window=200)
        df['SMA_99'] = ta.trend.sma_indicator(df['close'], window=99)
        df['EMA_50'] = ta.trend.ema_indicator(df['close'], window=50)
        df['RSI'] = ta.momentum.rsi(df['close'], window=14)
        df['BB_Upper'] = ta.volatility.bollinger_hband(df['close'], window=20, window_dev=2)
        df['BB_Lower'] = ta.volatility.bollinger_lband(df['close'], window=20, window_dev=2)
        df['ADX'] = ta.trend.adx(df['high'], df['low'], df['close'], window=14)
        df['ATR'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14)
        df['SMA_20_Vol'] = ta.trend.sma_indicator(df['volume'], window=20)
        
        all_dfs[symbol] = df
    except Exception as e:
        print(f"Failed {symbol}: {e}")

# Parameter Grid
adx_thresholds = [0, 15, 20]
ma99_filters = [True, False]
sl_multipliers = [1.0, 1.2, 1.5]
use_macro_trends = [True, False] # If True, use EMA50 > SMA200. If False, only price > SMA200.

best_profit = -9999
best_params = None
best_stats = {}

print("Starting Grid Search...")
for adx_th, use_ma99, sl_mult, strict_macro in itertools.product(adx_thresholds, ma99_filters, sl_multipliers, use_macro_trends):
    total_capital = 1000.0
    wins = 0
    losses = 0
    
    for symbol, df in all_dfs.items():
        position = 0.0
        position_side = ""
        buy_price = 0.0
        highest_price = 0.0
        lowest_price = float('inf')
        dynamic_sl = 0.0
        
        for i in range(200, len(df)):
            row = df.iloc[i]
            prev = df.iloc[i-1]
            
            price = row['close']
            atr = row['ATR']
            
            # Check Exits first
            if position > 0:
                profit_percent = (((price - buy_price) / buy_price) * 100) * 3 if position_side == "LONG" else (((buy_price - price) / buy_price) * 100) * 3
                profit_percent -= 0.1 # fee
                
                rm_signal = False
                if position_side == "LONG":
                    if price <= dynamic_sl: rm_signal = True
                    # Momentum TP
                    if profit_percent >= 2.0 and row['RSI'] > 70: rm_signal = True
                else:
                    if price >= dynamic_sl: rm_signal = True
                    if profit_percent >= 2.0 and row['RSI'] < 30: rm_signal = True
                    
                if rm_signal:
                    total_capital += (position * buy_price) * (profit_percent / 100)
                    if profit_percent > 0: wins += 1
                    else: losses += 1
                    position = 0.0
                    continue

            # Check Entries
            if position == 0:
                sma_200 = row['SMA_200']
                ema_50 = row['EMA_50']
                sma_99 = row['SMA_99']
                bb_upper = row['BB_Upper']
                bb_lower = row['BB_Lower']
                
                is_macro_uptrend = (price > sma_200 and ema_50 > sma_200) if strict_macro else (price > sma_200)
                is_macro_downtrend = (price < sma_200 and ema_50 < sma_200) if strict_macro else (price < sma_200)
                
                above_ma99 = (price >= sma_99) if use_ma99 else True
                below_ma99 = (price <= sma_99) if use_ma99 else True
                
                strong_volume = row['volume'] > row['SMA_20_Vol']
                adx_pass = row['ADX'] > adx_th if adx_th > 0 else True
                
                body = abs(row['close'] - row['open'])
                lower_wick = min(row['open'], row['close']) - row['low']
                upper_wick = row['high'] - max(row['open'], row['close'])
                is_giant = body > (atr * 2.0)
                
                bullish_sweep = (lower_wick > 2 * body) and (row['low'] <= bb_lower) and (row['close'] > bb_lower)
                bearish_sweep = (upper_wick > 2 * body) and (row['high'] >= bb_upper) and (row['close'] < bb_upper)
                
                sma200_bounce = (row['low'] <= sma_200) and (row['close'] > sma_200) and (row['close'] > row['open'])
                sma200_reject = (row['high'] >= sma_200) and (row['close'] < sma_200) and (row['close'] < row['open'])
                
                # Div logic simplified
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
                        
                sniper_long = (bullish_sweep or bullish_div or sma200_bounce) and strong_volume and is_macro_uptrend and not is_giant and (row['close'] <= bb_upper) and above_ma99 and adx_pass
                sniper_short = (bearish_sweep or bearish_div or sma200_reject) and strong_volume and is_macro_downtrend and not is_giant and (row['close'] >= bb_lower) and below_ma99 and adx_pass
                
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

    profit = total_capital - 1000.0
    if profit > best_profit:
        best_profit = profit
        best_params = (adx_th, use_ma99, sl_mult, strict_macro)
        best_stats = {"wins": wins, "losses": losses, "total": wins+losses}
        print(f"NEW BEST: Profit=${profit:.2f}, Params: ADX>{adx_th}, MA99={use_ma99}, SL={sl_mult}x, StrictMacro={strict_macro} | Trades: {wins+losses} (W:{wins} L:{losses})")

print("\n--- FINAL BEST ---")
print(f"Profit: ${best_profit:.2f}")
print(f"Params: ADX>{best_params[0]}, MA99={best_params[1]}, SL={best_params[2]}x, StrictMacro={best_params[3]}")
print(f"Trades: {best_stats['total']} (W:{best_stats['wins']} L:{best_stats['losses']})")
