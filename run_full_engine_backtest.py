import os
import sys
sys.stdout.reconfigure(encoding='utf-8')
import math
import pandas as pd
from datetime import datetime, timedelta, timezone

# Add current dir to path to import bot modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Monkeypatch binance_client fee functions BEFORE importing risk_manager/strategy
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

print("Loading cached 30m data...")
all_dfs = {}
for symbol in SYMBOLS:
    cache_file = f"scratch/{symbol}_30m_1y.pkl"
    if os.path.exists(cache_file):
        df = pd.read_pickle(cache_file)
        if df['timestamp'].dt.tz is None:
            df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
        all_dfs[symbol] = df
    else:
        print(f"Error: {cache_file} missing! Run test_30m_multiperiod.py first.")
        sys.exit(1)

def run_full_backtest(dfs, days):
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
                if (state.position_side == "LONG" and signal_plan.action == "SELL") or \
                   (state.position_side == "SHORT" and signal_plan.action == "BUY"):
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
                if signal_plan.action in ["BUY", "SELL"]:
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

print("=== LIVE 4-GEAR HYBRID RISK MANAGER & STRATEGY BACKTEST (30m Timeframe) ===")
periods = [(30, "1 Month (30 Days)"), (90, "3 Months (90 Days)"), (180, "6 Months (180 Days)"), (365, "1 Year (365 Days)")]
for days, label in periods:
    res = run_full_backtest(all_dfs, days=days)
    print(f"[{label}]")
    print(f"  Final Capital: ${res['final_cap']:.2f} | Net Profit: ${res['net_profit']:.2f} (+{res['net_pct']:.2f}%)")
    print(f"  Total Trades:  {res['trades']} (Wins: {res['wins']} | Losses: {res['losses']} | Win Rate: {res['win_rate']:.2f}%)")
    print("  Exit Reasons Breakdown:")
    for g, cnt in sorted(res['gears'].items(), key=lambda x: x[1], reverse=True):
        print(f"    - {g}: {cnt} trades")
    print("")
