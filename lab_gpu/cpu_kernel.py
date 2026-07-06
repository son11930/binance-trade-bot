"""
cpu_kernel.py — Pure Python/NumPy multi-worker simulation fallback.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any

def simulate_strategy_genome_cpu(df: pd.DataFrame, genome: Dict[str, Any]) -> Dict[str, float]:
    """CPU fallback for simulate_strategy_genome (re-uses CPU logic from original synthesizer)."""
    if len(df) < 200:
        return {"net_profit_pct": 0.0, "win_rate": 0.0, "max_dd": 0.0, "trades": 0}

    STRAT = genome.get("strategy_type", "rsi_sniper")
    adx_thresh   = genome.get("adx_trend_thresh", 20.0)
    use_dual     = genome.get("use_dual_trend", True)
    vol_mult     = genome.get("vol_surge_mult", 1.2)
    sl_atr       = genome.get("sl_atr_mult", 1.5)
    tp_rr        = genome.get("tp_rr_mult", 2.5)
    rsi_sniper   = genome.get("gear1_rsi_sniper", 78.0)
    mfi_thresh   = genome.get("mfi_bull_thresh", 40.0)
    cci_thresh   = genome.get("cci_trend_thresh", 0.0)
    williams_thresh = genome.get("williams_r_thresh", -80.0)
    stoch_thresh = genome.get("stoch_k_thresh", 80.0)
    moonshot_trig= genome.get("gear2_moonshot_trigger_pct", 0.02)
    moonshot_gap = genome.get("gear2_moonshot_gap_pct", 0.005)
    trail_trig   = genome.get("gear3_trailing_trigger_pct", 0.012)
    trail_gap    = genome.get("gear3_trailing_gap_pct", 0.008)
    be_trig      = genome.get("gear4_breakeven_trigger_pct", 0.006)
    be_buf       = min(float(genome.get("gear4_breakeven_buffer_pct", 0.001)), 0.02)
    max_hold     = int(genome.get("max_hold_bars", 36))
    sma200_buf   = genome.get("sma200_buffer_pct", 0.995)
    vol_floor    = genome.get("volume_floor_mult", 0.7)
    rsi_surge_ceil = genome.get("rsi_surge_ceiling", 82.0)
    sl_cap       = genome.get("sl_hard_cap_pct", 0.04)
    tp_cap       = genome.get("tp_hard_cap_pct", 0.10)
    cooldown_lim = int(genome.get("cooldown_bars_after_sl", 2))
    kelly        = max(0.20, min(0.40, float(genome.get("kelly_fraction_cap", 0.25))))
    giant_mult   = genome.get("giant_candle_atr_mult", 2.0)
    req_green    = genome.get("require_green_candle", False)
    macro_regime = genome.get("macro_regime_filter", "sma200_only")
    trend_min_adx= genome.get("trend_strength_min_adx", 15.0)

    g = lambda col, d=0.0: df.get(col, pd.Series(d, index=df.index)).values

    close_arr = df["close"].values; high_arr = df["high"].values
    low_arr   = df["low"].values;   open_arr = df["open"].values
    vol_arr   = df["volume"].values
    sma200_arr= g("SMA_200"); sma50_arr= g("SMA_50"); atr_arr= g("ATR")
    rsi_arr   = g("RSI");     adx_arr  = g("ADX");    vol_sma= g("SMA_20_Vol")
    bb_up_arr = g("BB_Upper");ema10    = g("EMA_10"); ema50   = g("EMA_50")
    st_dir    = g("supertrend_dir"); mfi_arr= g("mfi", 50.0)
    stoch_k   = g("stoch_rsi_k", 50.0); cci_arr= g("cci"); wlr= g("williams_r", -50.0)
    kelt_low  = g("keltner_lower"); tenkan= g("ichimoku_tenkan"); kijun= g("ichimoku_kijun")
    don_high  = g("donchian_high_20", close_arr)

    in_pos = False; entry_p = sl_p = tp_p = 0.0
    balance = peak_balance = 1000.0; max_dd = 0.0
    wins = total_trades = bars_in_trade = cooldown = 0

    for i in range(200, len(df)):
        c, h, l, o, v = close_arr[i], high_arr[i], low_arr[i], open_arr[i], vol_arr[i]
        atr = atr_arr[i]
        if cooldown > 0:
            cooldown -= 1
        if not in_pos and cooldown == 0:
            if adx_arr[i] > adx_thresh and v > vol_sma[i] * vol_floor:
                trend_ok = False
                if macro_regime == "sma200_only":
                    trend_ok = c > sma200_arr[i] * sma200_buf and ((not use_dual) or sma50_arr[i] > sma200_arr[i])
                elif macro_regime == "sma200_and_adx":
                    trend_ok = c > sma200_arr[i] * sma200_buf and adx_arr[i] > trend_min_adx
                else:
                    trend_ok = True
                not_blowoff = (h - l) <= atr * giant_mult
                candle_ok = (c > o) if req_green else True
                if trend_ok and not_blowoff and candle_ok and (c <= bb_up_arr[i] or STRAT == "bollinger_squeeze_explosion"):
                    entry_ok = False
                    if   STRAT == "rsi_sniper":                  entry_ok = rsi_arr[i] < rsi_sniper or (v > vol_sma[i] * vol_mult and rsi_arr[i] < rsi_surge_ceil)
                    elif STRAT == "ema_cross":                   entry_ok = ema10[i] > ema50[i] and ema10[i-1] <= ema50[i-1]
                    elif STRAT == "supertrend_momentum":         entry_ok = st_dir[i] == 1 and mfi_arr[i] > mfi_thresh
                    elif STRAT == "ichimoku_cloud":              entry_ok = c > tenkan[i] and tenkan[i] > kijun[i] and cci_arr[i] > cci_thresh
                    elif STRAT == "keltner_bounce":              entry_ok = l <= kelt_low[i] and c > kelt_low[i]
                    elif STRAT == "stoch_mfi_flow":              entry_ok = stoch_k[i] < stoch_thresh and mfi_arr[i] > mfi_thresh
                    elif STRAT == "williams_mean_rev":           entry_ok = wlr[i] < williams_thresh and rsi_arr[i] < rsi_sniper
                    elif STRAT == "donchian_breakout":           entry_ok = c >= don_high[i-1] and adx_arr[i] > 25.0
                    elif STRAT == "macd_momentum_surge":         entry_ok = (ema10[i] - ema50[i]) / c > 0.005 and ema10[i] > ema10[i-1] and v > vol_sma[i] * vol_mult
                    elif STRAT == "bollinger_squeeze_explosion": entry_ok = c > bb_up_arr[i] and adx_arr[i] > adx_thresh and (atr / c) < 0.03
                    elif STRAT == "parabolic_sar_vortex":        entry_ok = st_dir[i] == 1 and tenkan[i] > kijun[i] and mfi_arr[i] > mfi_thresh and rsi_arr[i] > 50.0
                    elif STRAT == "fibonacci_golden_pullback":   entry_ok = c > sma200_arr[i] and don_high[i-1] > 0 and (don_high[i-1] - c) / don_high[i-1] >= 0.02 and (don_high[i-1] - c) / don_high[i-1] <= 0.08 and rsi_arr[i] < 45.0
                    if entry_ok:
                        in_pos = True; entry_p = c
                        sl_p = max(c - atr * sl_atr, c * (1 - sl_cap))
                        tp_p = min(c + atr * sl_atr * tp_rr, c * (1 + tp_cap))
                        bars_in_trade = 0
        elif in_pos:
            bars_in_trade += 1
            cur_close = (c - entry_p) / entry_p
            exited = False; pnl = 0.0
            if l <= sl_p:
                pnl = ((sl_p - entry_p) / entry_p) - 0.0015; balance *= 1 + pnl * kelly * 4
                if pnl > 0: wins += 1
                total_trades += 1; in_pos = False; bars_in_trade = 0; cooldown = cooldown_lim; exited = True
            elif h >= tp_p:
                pnl = ((tp_p - entry_p) / entry_p) - 0.0015; balance *= 1 + pnl * kelly * 4
                if pnl > 0: wins += 1
                total_trades += 1; in_pos = False; bars_in_trade = 0; exited = True
            elif bars_in_trade >= max_hold:
                pnl = cur_close - 0.0015; balance *= 1 + pnl * kelly * 4
                if pnl > 0: wins += 1
                total_trades += 1; in_pos = False; bars_in_trade = 0; exited = True
            if not exited:
                cur_gain = (max(h, c) - entry_p) / entry_p
                if cur_gain >= be_trig:  sl_p = max(sl_p, entry_p * (1 + be_buf))
                if cur_gain >= trail_trig: sl_p = max(sl_p, c * (1 - trail_gap))
                if cur_gain >= moonshot_trig: sl_p = max(sl_p, c * (1 - moonshot_gap))
                sl_p = max(sl_p, c - atr * sl_atr)
                sl_p = min(sl_p, c)  # ABSOLUTE SAFETY: Stop Loss can NEVER exceed current close price!
        if balance > peak_balance: peak_balance = balance
        dd = (peak_balance - balance) / peak_balance if peak_balance > 0 else 0
        if dd > max_dd: max_dd = dd

    net_profit = ((balance - 1000.0) / 1000.0) * 100.0
    win_rate = wins / total_trades * 100.0 if total_trades > 0 else 0.0
    return {"net_profit_pct": round(net_profit, 2), "win_rate": round(win_rate, 2),
            "max_dd": round(max_dd * 100.0, 2), "trades": total_trades}
