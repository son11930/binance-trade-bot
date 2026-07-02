"""
Evolutionary Strategy Synthesizer (bot_strategy_synthesizer.py)
Automated R&D Alpha Lab running locally on multi-core CPU across 20 symbols.
Discovers and evolves Strategy Genomes across 4 Time Horizons (1M, 3M, 6M, 1Y).
Features anti-ban rate limiting (time.sleep(0.3)) and pushes leaderboard results to Aiven DB / Dashboard JSON.
"""

import os
import time
import json
import pickle
import logging
import requests
from datetime import datetime, timezone, timedelta
import pandas as pd
import numpy as np
from typing import Dict, List, Any, Tuple
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, text
from sqlalchemy.orm import declarative_base, sessionmaker

try:
    import optuna
    from optuna.samplers import TPESampler
    OPTUNA_AVAILABLE = True
except ImportError:
    OPTUNA_AVAILABLE = False

from bot.config import SYMBOLS, DATABASE_URL_FUTURES, DATABASE_URL_SPOT
from bot.indicators_library import apply_all_alpha_features

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("StrategySynthesizer")

CACHE_DIR = os.path.join("e:\\", "Code", "binancetrade", "binace_backtest1y")
DASHBOARD_DATA_DIR = os.path.join("e:\\", "Code", "binancetrade", "dashboard", "data")

Base = declarative_base()

class StrategyLeaderboard(Base):
    __tablename__ = "strategy_leaderboard"
    id = Column(Integer, primary_key=True, index=True)
    rank = Column(Integer)
    name = Column(String(100))
    net_profit_1m = Column(Float)
    net_profit_3m = Column(Float)
    net_profit_6m = Column(Float)
    net_profit_1y = Column(Float)
    win_rate_1y = Column(Float)
    max_drawdown = Column(Float)
    total_trades_1y = Column(Integer)
    moonshots_1y = Column(Integer)
    parameters_json = Column(String(2000))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ==========================================
# 1. SAFE AUTO-DOWNLOADER WITH ANTI-BAN
# ==========================================

def _fetch_binance_klines_chunk(symbol: str, interval: str, start_time: int, limit: int = 1000) -> List[list]:
    url = "https://fapi.binance.com/fapi/v1/klines"
    params = {"symbol": symbol, "interval": interval, "limit": limit, "startTime": start_time}
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code in (418, 429):
            logger.warning(f"Rate limit hit on Binance API! Sleeping 10 seconds...")
            time.sleep(10)
            return []
    except Exception as e:
        logger.error(f"Error fetching klines for {symbol}: {e}")
    return []

def download_symbol_klines_safe(symbol: str, cache_dir: str = CACHE_DIR, days: int = 365) -> pd.DataFrame:
    """
    Safely downloads historical 30m klines from Binance public API with strict rate limiting (time.sleep(0.3))
    to prevent IP bans. Checks file timestamp to avoid re-downloading if cached within 30 days.
    """
    os.makedirs(cache_dir, exist_ok=True)
    file_path = os.path.join(cache_dir, f"{symbol}_30m_{days}d.pkl")
    
    if os.path.exists(file_path):
        mtime = os.path.getmtime(file_path)
        if (time.time() - mtime) < (30 * 86400):
            logger.info(f"[{symbol}] Using cached 30m data (age < 30 days).")
            with open(file_path, "rb") as f:
                return pickle.load(f)
                
    logger.info(f"[{symbol}] Downloading {days} days of 30m data with anti-ban delay...")
    end_time = int(datetime.now(timezone.utc).timestamp() * 1000)
    start_time = int((datetime.now(timezone.utc) - timedelta(days=days)).timestamp() * 1000)
    
    all_klines = []
    curr_time = start_time
    while curr_time < end_time:
        klines = _fetch_binance_klines_chunk(symbol, "30m", curr_time)
        if not klines:
            break
        all_klines.extend(klines)
        curr_time = klines[-1][0] + 1
        time.sleep(0.3) # 100% Zero Ban Guarantee rate limit
        
    if not all_klines:
        return pd.DataFrame()
        
    cols = ['timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time', 'qav', 'num_trades', 'tb_base_av', 'tb_quote_av', 'ignore']
    df = pd.DataFrame(all_klines, columns=cols)
    for c in ['open', 'high', 'low', 'close', 'volume']:
        df[c] = df[c].astype(float)
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    
    with open(file_path, "wb") as f:
        pickle.dump(df, f)
    time.sleep(1.0) # Rest between symbols
    return df


# ==========================================
# 2. STRATEGY GENOME EVALUATOR
# ==========================================

def simulate_strategy_genome(df: pd.DataFrame, genome: Dict[str, Any]) -> Dict[str, float]:
    """
    Simulates a 30m Futures trading strategy genome on an OHLCV dataframe.
    Returns quantitative performance metrics: net_profit_pct, win_rate, max_dd, trades.
    """
    if len(df) < 200:
        return {"net_profit_pct": 0.0, "win_rate": 0.0, "max_dd": 0.0, "trades": 0}
        
    adx_thresh = genome.get("adx_trend_thresh", 20.0)
    use_dual = genome.get("use_dual_trend", True)
    vol_mult = genome.get("vol_surge_mult", 1.2)
    sl_atr = genome.get("sl_atr_mult", 1.5)
    rsi_sniper = genome.get("gear1_rsi_sniper", 78.0)
    
    # Pre-extract numpy arrays for fast vectorized loop backtest
    close_arr = df['close'].values
    high_arr = df['high'].values
    low_arr = df['low'].values
    vol_arr = df['volume'].values
    
    sma200_arr = df.get('SMA_200', pd.Series(0, index=df.index)).values
    sma50_arr = df.get('SMA_50', pd.Series(0, index=df.index)).values
    atr_arr = df.get('ATR', pd.Series(0, index=df.index)).values
    rsi_arr = df.get('RSI', pd.Series(0, index=df.index)).values
    adx_arr = df.get('ADX', pd.Series(0, index=df.index)).values
    vol_sma_arr = df.get('SMA_20_Vol', pd.Series(0, index=df.index)).values
    bb_up_arr = df.get('BB_Upper', pd.Series(0, index=df.index)).values
    
    in_pos = False
    entry_p, sl_p, tp_p = 0.0, 0.0, 0.0
    balance = 1000.0
    peak_balance = 1000.0
    max_dd = 0.0
    wins, total_trades = 0, 0
    
    for i in range(200, len(df)):
        c, h, l, v = close_arr[i], high_arr[i], low_arr[i], vol_arr[i]
        atr = atr_arr[i]
        
        if not in_pos:
            if adx_arr[i] > adx_thresh and v > (vol_sma_arr[i] * vol_mult):
                trend_ok = (c > sma200_arr[i]) and ((not use_dual) or (sma50_arr[i] > sma200_arr[i]))
                if trend_ok and c <= bb_up_arr[i] and rsi_arr[i] < rsi_sniper:
                    in_pos = True
                    entry_p = c
                    sl_p = c - (atr * sl_atr)
                    tp_p = c + (atr * sl_atr * 2.5) # 2.5 R:R target
        else:
            # Check exit
            if l <= sl_p:
                loss_pct = (sl_p - entry_p) / entry_p
                balance *= (1.0 + loss_pct)
                total_trades += 1
                in_pos = False
            elif h >= tp_p:
                win_pct = (max(tp_p, c) - entry_p) / entry_p
                balance *= (1.0 + win_pct)
                wins += 1
                total_trades += 1
                in_pos = False
            elif rsi_arr[i] >= rsi_sniper:
                win_pct = (c - entry_p) / entry_p
                balance *= (1.0 + win_pct)
                if win_pct > 0:
                    wins += 1
                total_trades += 1
                in_pos = False
            else:
                # Trailing stop update
                sl_p = max(sl_p, c - (atr * sl_atr))
                
        if balance > peak_balance:
            peak_balance = balance
        dd = (peak_balance - balance) / peak_balance if peak_balance > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
            
    net_profit = ((balance - 1000.0) / 1000.0) * 100.0
    win_rate = (wins / total_trades * 100.0) if total_trades > 0 else 0.0
    return {
        "net_profit_pct": round(net_profit, 2),
        "win_rate": round(win_rate, 2),
        "max_dd": round(max_dd * 100.0, 2),
        "trades": total_trades
    }


# ==========================================
# 3. 4-HORIZON MULTI-PERIOD EVALUATION
# ==========================================

def evaluate_single_horizon(symbol_dfs: Dict[str, pd.DataFrame], genome: Dict[str, Any], bars: int) -> float:
    """Evaluates net profit % for a single horizon across all symbols."""
    h_profits = []
    for sym, df in symbol_dfs.items():
        if df.empty or len(df) < bars:
            continue
        sub_df = df.iloc[-bars:]
        stats = simulate_strategy_genome(sub_df, genome)
        h_profits.append(stats["net_profit_pct"])
    return round(np.mean(h_profits), 2) if h_profits else 0.0

def evaluate_genome_4_horizons(symbol_dfs: Dict[str, pd.DataFrame], genome: Dict[str, Any]) -> Dict[str, Any]:
    """Evaluates a genome across 1M, 3M, 6M, and 1Y periods across all symbols."""
    horizons = {"1m": 30 * 48, "3m": 90 * 48, "6m": 180 * 48, "1y": 365 * 48}
    res = {}
    total_trades_1y = 0
    win_rate_1y = 0.0
    max_dd_all = 0.0
    moonshots = 0
    
    for h_name, bars in horizons.items():
        h_profits = []
        h_trades = []
        h_wins = []
        for sym, df in symbol_dfs.items():
            if df.empty or len(df) < bars:
                continue
            sub_df = df.iloc[-bars:]
            stats = simulate_strategy_genome(sub_df, genome)
            h_profits.append(stats["net_profit_pct"])
            if h_name == "1y":
                h_trades.append(stats["trades"])
                h_wins.append(stats["win_rate"] * stats["trades"] / 100.0)
                if stats["max_dd"] > max_dd_all:
                    max_dd_all = stats["max_dd"]
                if stats["net_profit_pct"] > 30.0:
                    moonshots += 1
                    
        avg_profit = np.mean(h_profits) if h_profits else 0.0
        res[f"net_profit_{h_name}"] = round(avg_profit, 2)
        res[f"net_profit_{h_name}_dollar"] = round(avg_profit * 10.0, 2) # Assuming $1,000 base per asset
        if h_name == "1y":
            total_trades_1y = sum(h_trades)
            win_rate_1y = (sum(h_wins) / total_trades_1y * 100.0) if total_trades_1y > 0 else 0.0
            
    res["win_rate_1y"] = round(win_rate_1y, 2)
    res["max_dd"] = round(max_dd_all, 2)
    res["total_trades_1y"] = total_trades_1y
    res["moonshots_1y"] = moonshots
    
    # Averages per month and per day
    avg_trades_month = total_trades_1y / 12.0
    res["avg_trades_month"] = round(avg_trades_month, 1)
    res["avg_trades_day"] = round(total_trades_1y / 365.0, 1)
    
    # Composite Fitness Score (User's Exact Priorities):
    # 1. Primary: Net Profit across all horizons + All-Horizon Winner Bonus
    total_profit_pct = res["net_profit_1y"] + res["net_profit_6m"] + res["net_profit_3m"] + res["net_profit_1m"]
    all_horizon_bonus = 500.0 if (res["net_profit_1y"] > 0 and res["net_profit_6m"] > 0 and res["net_profit_3m"] > 0 and res["net_profit_1m"] > 0) else 0.0
    
    # 2. Secondary: Win Rate
    win_rate_score = res["win_rate_1y"] * 2.0
    
    # 3. Tertiary: Trade Activity (rewarding active consistent trading without overtrading)
    trade_activity_score = min(avg_trades_month, 100.0) * 0.5
    
    fitness = total_profit_pct + all_horizon_bonus + win_rate_score + trade_activity_score - (res["max_dd"] * 1.5)
    res["fitness_score"] = round(fitness, 2)
    return res


# ==========================================
# 4. OPTUNA TPE WITH EARLY PRUNING & DB PUSH
# ==========================================

def push_leaderboard_to_db_and_json(leaderboard: List[Dict[str, Any]]) -> None:
    """Saves Top 10 strategies to dashboard JSON and pushes to Aiven DB."""
    os.makedirs(DASHBOARD_DATA_DIR, exist_ok=True)
    json_path = os.path.join(DASHBOARD_DATA_DIR, "strategy_leaderboard.json")
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump({"updated_at": datetime.now(timezone.utc).isoformat(), "strategies": leaderboard}, f, indent=2)
    logger.info(f"Saved Top 10 Leaderboard to {json_path}")
    
    # Connect to Aiven DB / SQLite and push
    try:
        db_url = DATABASE_URL_FUTURES or DATABASE_URL_SPOT or "sqlite:///./trades_futures.db"
        if db_url and db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql://", 1)
        engine = create_engine(db_url, pool_pre_ping=True)
        Base.metadata.create_all(bind=engine)
        
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        session = SessionLocal()
        
        session.query(StrategyLeaderboard).delete()
        for idx, item in enumerate(leaderboard, 1):
            row = StrategyLeaderboard(
                rank=int(idx),
                name=str(item["name"]),
                net_profit_1m=float(item["net_profit_1m"]),
                net_profit_3m=float(item["net_profit_3m"]),
                net_profit_6m=float(item["net_profit_6m"]),
                net_profit_1y=float(item["net_profit_1y"]),
                win_rate_1y=float(item["win_rate_1y"]),
                max_drawdown=float(item["max_dd"]),
                total_trades_1y=int(item["total_trades_1y"]),
                moonshots_1y=int(item["moonshots_1y"]),
                parameters_json=json.dumps(item["parameters"])
            )
            session.add(row)
        session.commit()
        session.close()
        logger.info("Successfully pushed Top 10 Leaderboard to Database!")
    except Exception as e:
        logger.error(f"Failed to push leaderboard to database: {e}")


def save_lab_progress(status: str, current_trial: int, total_trials: int, best_score: float, best_name: str, elapsed_sec: int):
    prog_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "dashboard", "data", "lab_progress.json")
    os.makedirs(os.path.dirname(prog_path), exist_ok=True)
    pct = round(min(100.0, (current_trial / total_trials) * 100.0), 1) if (total_trials and total_trials > 0) else 100.0
    data = {
        "status": status,
        "current_trial": current_trial,
        "total_trials": total_trials if (total_trials and total_trials > 0) else 0,
        "progress_pct": pct,
        "best_score": round(float(best_score), 2),
        "best_strategy_name": str(best_name),
        "elapsed_seconds": int(elapsed_sec),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    try:
        with open(prog_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to write lab progress: {e}")


def _get_safe_best_value(study, fallback=0.0):
    if not study:
        return fallback
    try:
        return study.best_value
    except (ValueError, AttributeError):
        return fallback


def run_synthesizer_lab(n_trials: int = 30) -> List[Dict[str, Any]]:
    """Runs the full Evolutionary Strategy Lab across all 20 symbols with Optuna TPE Early Pruning."""
    start_time = time.time()
    if n_trials <= 0:
        n_trials = None  # 0 means Infinite / Unlimited runs in Optuna!
    save_lab_progress("running", 0, n_trials if n_trials else 0, 0.0, "Initializing Lab...", 0)
    logger.info("==========================================================")
    logger.info("Starting Evolutionary Strategy Synthesizer Lab (Optuna TPE)")
    logger.info("==========================================================")
    
    import ta
    symbol_dfs = {}
    for sym in SYMBOLS:
        df = download_symbol_klines_safe(sym)
        if not df.empty:
            df['SMA_200'] = ta.trend.sma_indicator(df['close'], window=200)
            df['SMA_50'] = ta.trend.sma_indicator(df['close'], window=50)
            df['ATR'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14)
            df['RSI'] = ta.momentum.rsi(df['close'], window=14)
            df['ADX'] = ta.trend.adx(df['high'], df['low'], df['close'], window=14)
            df['SMA_20_Vol'] = df['volume'].rolling(window=20).mean()
            bb = ta.volatility.BollingerBands(df['close'], window=20, window_dev=2.0)
            df['BB_Upper'] = bb.bollinger_hband()
            symbol_dfs[sym] = df
            
    logger.info(f"Loaded and processed historical data for {len(symbol_dfs)} symbols.")
    
    leaderboard_map = {}
    
    # 1. Baseline System 4 Reference
    base_genome = {"adx_trend_thresh": 20.0, "use_dual_trend": True, "vol_surge_mult": 1.2, "sl_atr_mult": 1.5, "gear1_rsi_sniper": 78.0}
    base_res = evaluate_genome_4_horizons(symbol_dfs, base_genome)
    base_res["name"] = "Blueprint #1: System 4 Baseline (Reference)"
    base_res["parameters"] = base_genome
    leaderboard_map["baseline"] = base_res
    
    if OPTUNA_AVAILABLE:
        logger.info("Running Optuna Tree-Structured Parzen Estimators with Early Median Pruning...")
        study = optuna.create_study(
            direction="maximize",
            sampler=TPESampler(seed=42),
            pruner=optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=1)
        )
        
        def objective(trial):
            genome = {
                "adx_trend_thresh": trial.suggest_float("adx_trend_thresh", 15.0, 32.0, step=1.0),
                "use_dual_trend": trial.suggest_categorical("use_dual_trend", [True, False]),
                "vol_surge_mult": trial.suggest_float("vol_surge_mult", 1.0, 2.2, step=0.1),
                "sl_atr_mult": trial.suggest_float("sl_atr_mult", 1.2, 2.2, step=0.1),
                "gear1_rsi_sniper": trial.suggest_float("gear1_rsi_sniper", 73.0, 84.0, step=1.0)
            }
            
            # Step 1: 1M Horizon (Early Pruning Gate - cuts bottom 50% immediately!)
            p_1m = evaluate_single_horizon(symbol_dfs, genome, 30 * 48)
            trial.report(p_1m, step=1)
            if trial.should_prune():
                elapsed = int(time.time() - start_time)
                best_val = _get_safe_best_value(study, 0.0)
                save_lab_progress("running", trial.number + 1, n_trials if n_trials else 0, best_val, f"Pruned Trial #{trial.number}", elapsed)
                raise optuna.TrialPruned()
                
            # Step 2: 3M Horizon
            p_3m = evaluate_single_horizon(symbol_dfs, genome, 90 * 48)
            trial.report(p_3m, step=2)
            if trial.should_prune():
                elapsed = int(time.time() - start_time)
                best_val = _get_safe_best_value(study, 0.0)
                save_lab_progress("running", trial.number + 1, n_trials if n_trials else 0, best_val, f"Pruned Trial #{trial.number}", elapsed)
                raise optuna.TrialPruned()
                
            # Step 3: 6M Horizon
            p_6m = evaluate_single_horizon(symbol_dfs, genome, 180 * 48)
            trial.report(p_6m, step=3)
            if trial.should_prune():
                elapsed = int(time.time() - start_time)
                best_val = _get_safe_best_value(study, 0.0)
                save_lab_progress("running", trial.number + 1, n_trials if n_trials else 0, best_val, f"Pruned Trial #{trial.number}", elapsed)
                raise optuna.TrialPruned()
                
            # Step 4: Full Annual Evaluation
            full_res = evaluate_genome_4_horizons(symbol_dfs, genome)
            full_res["name"] = f"Blueprint #{trial.number + 2}: Evolved Alpha TPE #{trial.number}"
            full_res["parameters"] = genome
            leaderboard_map[f"trial_{trial.number}"] = full_res
            elapsed = int(time.time() - start_time)
            best_val = _get_safe_best_value(study, full_res["fitness_score"])
            save_lab_progress("running", trial.number + 1, n_trials if n_trials else 0, best_val, full_res["name"], elapsed)
            return full_res["fitness_score"]
            
        study.optimize(objective, n_trials=n_trials, show_progress_bar=True)
    else:
        logger.warning("Optuna not available, falling back to candidate grid search...")
        candidates = [
            {"adx_trend_thresh": 25.0, "use_dual_trend": True, "vol_surge_mult": 1.5, "sl_atr_mult": 1.8, "gear1_rsi_sniper": 80.0, "name": "Blueprint #2: High-ADX Momentum Sniper"},
            {"adx_trend_thresh": 18.0, "use_dual_trend": True, "vol_surge_mult": 1.1, "sl_atr_mult": 1.3, "gear1_rsi_sniper": 75.0, "name": "Blueprint #3: Agile Trend Scalper"},
            {"adx_trend_thresh": 22.0, "use_dual_trend": False, "vol_surge_mult": 2.0, "sl_atr_mult": 2.0, "gear1_rsi_sniper": 82.0, "name": "Blueprint #4: Institutional Volume Breakout"},
            {"adx_trend_thresh": 28.0, "use_dual_trend": True, "vol_surge_mult": 1.3, "sl_atr_mult": 1.5, "gear1_rsi_sniper": 77.0, "name": "Blueprint #5: Macro Trend Armor"},
            {"adx_trend_thresh": 20.0, "use_dual_trend": True, "vol_surge_mult": 1.4, "sl_atr_mult": 1.6, "gear1_rsi_sniper": 79.0, "name": "Blueprint #6: Balanced Alpha Genome"}
        ]
        for idx, cand in enumerate(candidates, 2):
            name = cand.pop("name")
            res = evaluate_genome_4_horizons(symbol_dfs, cand)
            res["name"] = name
            res["parameters"] = cand
            leaderboard_map[f"cand_{idx}"] = res
            
    leaderboard = list(leaderboard_map.values())
    # Sort by user priority: All-Horizon winners first, then total profit, win rate, and activity
    leaderboard.sort(key=lambda x: x["fitness_score"], reverse=True)
    for idx, item in enumerate(leaderboard, 1):
        item["rank"] = idx
        if idx == 1:
            item["name"] = f"🏆 #{idx} ALPHA GENOME: " + item["name"].split(": ")[-1]
        else:
            item["name"] = f"#{idx} BLUEPRINT: " + item["name"].split(": ")[-1]
            
    push_leaderboard_to_db_and_json(leaderboard[:10])
    elapsed = int(time.time() - start_time)
    best_item = leaderboard[0] if leaderboard else {}
    best_val = _get_safe_best_value(study if OPTUNA_AVAILABLE else None, best_item.get("fitness_score", 0.0))
    save_lab_progress("completed", n_trials if n_trials else len(leaderboard_map), n_trials if n_trials else 0, best_val, best_item.get("name", "N/A"), elapsed)
    return leaderboard[:10]

if __name__ == "__main__":
    run_synthesizer_lab()

