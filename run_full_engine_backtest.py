import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
import math
import pandas as pd
from datetime import datetime, timedelta, timezone

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import bot.binance_client as bc
bc.get_cached_futures_fee = lambda symbol: 0.0005
bc.get_cached_spot_fee = lambda symbol: 0.001

from bot.strategy import analyze_futures_market
from bot.risk_manager import check_futures_risk_management

class MockSymbolState:
    def __init__(self, symbol):
        self.symbol = symbol
        self.position = 0.0
        self.position_side = ""
        self.buy_price = 0.0
        self.last_price = 0.0
        self.highest_price = 0.0
        self.lowest_price = 0.0
        self.trade_entry_time = None
        self.max_time_in_trade = 0
        self.dynamic_tp = 0.0
        self.dynamic_sl = 0.0

SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT", "DOGEUSDT"]

print("Loading cached 30m data from binace_backtest1y for Grand Production Showdown...")
all_dfs = {}
for symbol in SYMBOLS:
    cache_file = f"binace_backtest1y/{symbol}_30m_1y.pkl"
    if not os.path.exists(cache_file):
        fallback = f"scratch/{symbol}_30m_1y.pkl"
        if os.path.exists(fallback):
            cache_file = fallback
    if os.path.exists(cache_file):
        df = pd.read_pickle(cache_file)
        if df['timestamp'].dt.tz is None:
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        all_dfs[symbol] = df
    else:
        print(f"Error: {cache_file} missing!")
        sys.exit(1)

def run_full_backtest(dfs, days, mode="SYS3"):
    total_capital = 1000.0
    wins = 0
    losses = 0
    trades = []
    gear_counts = {}
    
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    for symbol, df_full in dfs.items():
        df = df_full[df_full['timestamp'] >= pd.to_datetime(cutoff_date, utc=True)].copy().reset_index(drop=True)
        if len(df) < 201: continue
        
        state = MockSymbolState(symbol)
        
        for i in range(200, len(df)):
            row = df.iloc[i]
            price = row['close']
            atr = row['ATR']
            rsi = row['RSI']
            
            if pd.isna(row['SMA_200']) or pd.isna(atr): continue
            
            # 1. Update State & Check Risk Manager (4 Gears)
            if state.position > 0:
                state.last_price = price
                if state.position_side == "LONG":
                    if price > state.highest_price: state.highest_price = price
                    if price < state.lowest_price: state.lowest_price = price
                    profit_pct = (((price - state.buy_price) / state.buy_price) * 100) * 3
                else:
                    if price < state.lowest_price: state.lowest_price = price
                    if price > state.highest_price: state.highest_price = price
                    profit_pct = (((state.buy_price - price) / state.buy_price) * 100) * 3
                
                profit_pct -= 0.1 # fee
                
                rm_signal = check_futures_risk_management(state, atr, stop_loss_percent=2.0, rsi_value=rsi)
                if rm_signal:
                    pnl = (state.position * state.buy_price) * (profit_pct / 100)
                    total_capital += pnl
                    if profit_pct > 0: wins += 1
                    else: losses += 1
                    
                    gear_name = rm_signal.split("(")[0].strip() if "(" in rm_signal else rm_signal
                    gear_counts[gear_name] = gear_counts.get(gear_name, 0) + 1
                    
                    trades.append({"symbol": symbol, "profit_pct": profit_pct, "reason": rm_signal})
                    state.position = 0.0
                    state.position_side = ""
                    continue
                
                # Check Strategy Exit / Reversal
                slice_df = df.iloc[i-200:i+1]
                signal_plan = analyze_futures_market(slice_df)
                
                is_exit_signal = (state.position_side == "LONG" and signal_plan.action == "SELL") or \
                                 (state.position_side == "SHORT" and signal_plan.action == "BUY")
                                 
                if is_exit_signal:
                    if signal_plan.strategy_used == "FUTURES_30M_EXIT":
                        if mode == "SYS4_NO_EXIT":
                            continue # Ignore RSI Exit 100%
                        elif mode == "SYS5A_HYBRID":
                            # If volume surge > 2.5x SMA, ignore RSI Exit!
                            if row['volume'] > row['SMA_20_Vol'] * 2.5:
                                continue
                                
                    pnl = (state.position * state.buy_price) * (profit_pct / 100)
                    total_capital += pnl
                    if profit_pct > 0: wins += 1
                    else: losses += 1
                    gear_counts["Strategy Reversal/Exit"] = gear_counts.get("Strategy Reversal/Exit", 0) + 1
                    trades.append({"symbol": symbol, "profit_pct": profit_pct, "reason": "Strategy Exit"})
                    state.position = 0.0
                    state.position_side = ""
                    continue

            # 2. Check Entry
            if state.position == 0:
                slice_df = df.iloc[i-200:i+1]
                signal_plan = analyze_futures_market(slice_df)
                if signal_plan.action in ["BUY", "SELL"] and signal_plan.strategy_used != "FUTURES_30M_EXIT":
                    invest = total_capital * 0.20 # 20% compounding
                    state.position = (invest * 3) / price # 3x leverage
                    state.buy_price = price
                    state.last_price = price
                    state.highest_price = price
                    state.lowest_price = price
                    state.position_side = signal_plan.position_side
                    state.dynamic_sl = signal_plan.stop_loss
                    state.dynamic_tp = signal_plan.take_profit
                    state.trade_entry_time = row['timestamp']
                    state.max_time_in_trade = signal_plan.time_in_trade

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
        "gears": gear_counts
    }

print("==========================================================================================")
print("🏆 GRAND PRODUCTION SHOWDOWN: SYS 3 vs SYS 4 vs SYS 5A (HYBRID) IN SAME ENVIRONMENT")
print("==========================================================================================")
periods = [(30, "1 Month (30 Days)"), (90, "3 Months (90 Days)"), (180, "6 Months (180 Days)")]
modes = [("System 3 (Standard RSI Exit)", "SYS3"), ("System 4 (No RSI Exit / 4-Gears)", "SYS4_NO_EXIT"), ("System 5A (Smart Hybrid Override)", "SYS5A_HYBRID")]

for days, label in periods:
    print(f"\n--- BACKTEST PERIOD: {label} ---")
    print(f"{'Strategy Architecture':<34} | {'Net Profit':<12} | {'Win Rate':<10} | {'Total Trades':<14} | {'G2 Moonshot':<11}")
    print("-" * 95)
    for name, mode_code in modes:
        res = run_full_backtest(all_dfs, days=days, mode=mode_code)
        moon_cnt = res['gears'].get('Moonshot Trailing Stop', 0)
        print(f"{name:<34} | +{res['net_pct']:>8.2f}%   | {res['win_rate']:>7.2f}%  | {res['trades']:>12}   | {moon_cnt:>11}")
print("==========================================================================================")
