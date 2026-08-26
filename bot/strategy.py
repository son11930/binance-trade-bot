import pandas as pd
import ta
import logging
import math
from typing import NamedTuple, Dict, Any
from .indicators_library import apply_all_alpha_features
from .strategy_contract import normalize_strategy_parameters, strategy_id


class SignalPlan(NamedTuple):
    action: str
    strategy_used: str
    stop_loss: float
    take_profit: float
    time_in_trade: int
    near_miss_reason: str = ""
    position_side: str = ""


def apply_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applies MACD, SMA 200, SMA 50, RSI, Bollinger Bands, ADX, and ATR for Market Regime Detection and Strategy Routing.
    """
    if len(df) < 200:
        return df
        
    # Moving Averages
    df['SMA_200'] = ta.trend.sma_indicator(df['close'], window=200)
    df['SMA_99'] = ta.trend.sma_indicator(df['close'], window=99)
    df['SMA_50'] = ta.trend.sma_indicator(df['close'], window=50)
    df['EMA_50'] = ta.trend.ema_indicator(df['close'], window=50)
    
    # MACD (12, 26, 9)
    df['MACD'] = ta.trend.macd(df['close'], window_slow=26, window_fast=12)
    df['MACD_Signal'] = ta.trend.macd_signal(df['close'], window_slow=26, window_fast=12, window_sign=9)
    
    # RSI (14)
    df['RSI'] = ta.momentum.rsi(df['close'], window=14)
    
    # Bollinger Bands (20, 2)
    df['BB_Upper'] = ta.volatility.bollinger_hband(df['close'], window=20, window_dev=2)
    df['BB_Lower'] = ta.volatility.bollinger_lband(df['close'], window=20, window_dev=2)
    df['BB_Mid'] = ta.volatility.bollinger_mavg(df['close'], window=20)
    
    # ADX (14)
    df['ADX'] = ta.trend.adx(df['high'], df['low'], df['close'], window=14)
    
    # ATR (14)
    df['ATR'] = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=14)
    
    # Volume SMA (20)
    df['SMA_20_Vol'] = ta.trend.sma_indicator(df['volume'], window=20)

    # Strategy Review Enhancements
    df['SMA_ADX_3'] = ta.trend.sma_indicator(df['ADX'], window=3)
    df['SMA_ADX_5'] = ta.trend.sma_indicator(df['ADX'], window=5)
    df['MACD_Histogram'] = df['MACD'] - df['MACD_Signal']
    df['Bollinger_Band_Width'] = (df['BB_Upper'] - df['BB_Lower']) / df['BB_Mid']
    df['Distance_to_SMA_200'] = ((df['close'] - df['SMA_200']) / df['SMA_200']) * 100
    
    df['EMA_10'] = ta.trend.ema_indicator(df['close'], window=10)
    
    # Apply all Alpha Features for dynamic evaluation
    df = apply_all_alpha_features(df)
    
    return df

def detect_regime(df: pd.DataFrame) -> str:
    """
    Detects market regime: TRENDING or SIDEWAYS based on ADX slope and SMA.
    """
    if len(df) < 14:
        return "UNKNOWN"
        
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    if pd.isna(latest.get('ADX')):
        return "UNKNOWN"
        
    adx_curr = latest['ADX']
    sma_adx_3 = latest.get('SMA_ADX_3', 0)
    sma_adx_5 = latest.get('SMA_ADX_5', 0)
    
    # ADX > 25 and short SMA of ADX > longer SMA of ADX indicates strong trend
    if adx_curr > 25 and sma_adx_3 > sma_adx_5:
        return "TRENDING"
        
    # ADX < 25 or falling indicates sideways / consolidation
    return "SIDEWAYS"

def analyze_market(df: pd.DataFrame) -> SignalPlan:
    """
    Analyzes the latest candle and returns a Trading Plan (SignalPlan).
    """
    default_signal = SignalPlan(
        action="HOLD",
        strategy_used="NONE",
        stop_loss=0.0,
        take_profit=0.0,
        time_in_trade=0
    )
    
    if len(df) < 200:
        return default_signal
        
    regime = detect_regime(df)
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    required_cols = ['SMA_200', 'RSI', 'MACD', 'MACD_Signal', 'BB_Lower', 'BB_Upper', 'ATR', 'SMA_20_Vol']
    if not all(col in latest for col in required_cols) or pd.isna(latest['SMA_200']) or pd.isna(latest['SMA_20_Vol']):
        return default_signal
        
    price = latest['close']
    atr = latest['ATR']
    
    if regime == "TRENDING":
        return execute_trend_strategy(df, latest, prev, price, atr)
    elif regime == "SIDEWAYS":
        return execute_sideways_strategy(latest, prev, price, atr)
        
    return default_signal

def execute_trend_strategy(df, latest, prev, price, atr) -> SignalPlan:
    """
    Trend Strategy: MACD Crossover + SMA 200
    """
    sma_200 = latest['SMA_200']
    macd_curr = latest['MACD']
    sig_curr = latest['MACD_Signal']
    macd_prev = prev['MACD']
    sig_prev = prev['MACD_Signal']
    rsi_curr = latest['RSI']
    
    vol_curr = latest['volume']
    vol_sma = latest['SMA_20_Vol']
    
    vol_surge_multiplier = vol_curr / vol_sma if vol_sma > 0 else 1.0
    rsi_limit = 80 if vol_surge_multiplier >= 2.0 else 75
    
    # Check if MACD crossed above signal within last 8 periods
    recent_macd_cross = False
    if len(df) >= 8:
        for i in range(1, 9):
            idx_curr = -i
            idx_prev = -i - 1
            if df.iloc[idx_curr]['MACD'] > df.iloc[idx_curr]['MACD_Signal'] and df.iloc[idx_prev]['MACD'] <= df.iloc[idx_prev]['MACD_Signal']:
                recent_macd_cross = True
                break

    near_miss_reason = ""
    if recent_macd_cross and price > sma_200 * 0.995 and price > latest['EMA_50']:
        if rsi_curr >= rsi_limit:
            near_miss_reason = f"RSI too high ({rsi_curr:.1f} >= {rsi_limit})"
        elif vol_curr <= vol_sma * 0.7:
            near_miss_reason = f"Volume too low ({vol_curr:.1f} <= {vol_sma * 0.7:.1f})"

    # BUY: MACD crossed ABOVE Signal Line in last 8 periods AND Price > SMA 200 AND Price > EMA 50 AND RSI < dynamic limit AND Volume > SMA * 0.7
    if recent_macd_cross and price > sma_200 * 0.995 and price > latest['EMA_50'] and rsi_curr < rsi_limit and vol_curr > vol_sma * 0.7:
        return SignalPlan(
            action="BUY",
            strategy_used="TREND_MACD",
            stop_loss=price - (atr * 1.5), # Keep trailing SL
            take_profit=0.0,               # Remove fixed TP for trend riding
            time_in_trade=0,
            near_miss_reason=""
        )
        
    macd_cross_down = macd_curr < sig_curr and macd_prev >= sig_prev
    # SELL: Exit if MACD crosses down clearly and we are overbought, OR if price breaks below EMA_50 (trend breakdown)
    if (macd_cross_down and rsi_curr > 60) or price < latest['EMA_50']:
        return SignalPlan(
            action="SELL",
            strategy_used="TREND_MACD",
            stop_loss=0.0,
            take_profit=0.0,
            time_in_trade=0,
            near_miss_reason=""
        )
        
    return SignalPlan(
        action="HOLD",
        strategy_used="TREND_MACD",
        stop_loss=0.0,
        take_profit=0.0,
        time_in_trade=0,
        near_miss_reason=near_miss_reason
    )

def execute_sideways_strategy(latest, prev, price, atr) -> SignalPlan:
    """
    Sideways Strategy: RSI Reversal + Bollinger Bands + Dynamic ATR Stop
    """
    rsi_curr = latest['RSI']
    rsi_prev = prev['RSI']
    bb_lower = latest['BB_Lower']
    bb_upper = latest['BB_Upper']
    
    vol_curr = latest['volume']
    vol_sma = latest['SMA_20_Vol']
    
    rsi_hook = rsi_curr > rsi_prev and rsi_prev <= 45
    
    # 1. Price Action Proof of Absorption
    is_green_candle = latest.get('close', 0) > latest.get('open', 0)
    candle_range = latest.get('high', 0) - latest.get('low', 0)
    lower_wick = min(latest.get('open', 0), latest.get('close', 0)) - latest.get('low', 0)
    is_strong_rejection = (lower_wick / candle_range) > 0.4 if candle_range > 0 else False
    
    # 2. Dynamic Volume Cap
    vol_limit_multiplier = 4.0 if (is_green_candle or is_strong_rejection) else 2.5
    dynamic_vol_limit = vol_sma * vol_limit_multiplier
    
    near_miss_reason = ""
    if rsi_hook and price <= bb_lower * 1.02:
        if vol_curr > dynamic_vol_limit:
            near_miss_reason = f"Volume too high ({vol_curr:.1f} > {dynamic_vol_limit:.1f})"

    # BUY: RSI Hook AND price near lower BB AND Volume <= Dynamic Limit
    if rsi_hook and price <= bb_lower * 1.02 and vol_curr <= dynamic_vol_limit:
        return SignalPlan(
            action="BUY",
            strategy_used="SIDEWAYS_RSI_BB",
            stop_loss=price - (atr * 1.5),
            take_profit=bb_upper,
            time_in_trade=0,
            near_miss_reason=""
        )
        
    # SELL: RSI crosses back BELOW 70 (Reversal confirmation) AND price is near upper BB
    if (rsi_curr < 70 and rsi_prev >= 70 and price >= bb_upper * 0.99) or (price >= bb_upper):
        return SignalPlan(
            action="SELL",
            strategy_used="SIDEWAYS_RSI_BB",
            stop_loss=0.0,
            take_profit=0.0,
            time_in_trade=0,
            near_miss_reason=""
        )
        
    return SignalPlan(
        action="HOLD",
        strategy_used="SIDEWAYS_RSI_BB",
        stop_loss=0.0,
        take_profit=0.0,
        time_in_trade=0,
        near_miss_reason=near_miss_reason,
        position_side=""
    )

def _check_liquidity_sweeps(open_p: float, high_p: float, low_p: float, close_p: float, bb_lower: float, bb_upper: float, body: float) -> tuple[bool, bool]:
    lower_wick = min(open_p, close_p) - low_p
    upper_wick = high_p - max(open_p, close_p)
    bullish_sweep = (lower_wick > 2 * body) and (low_p <= bb_lower) and (close_p > bb_lower)
    bearish_sweep = (upper_wick > 2 * body) and (high_p >= bb_upper) and (close_p < bb_upper)
    return bullish_sweep, bearish_sweep

def _check_rsi_divergence(df: pd.DataFrame, close_p: float, open_p: float, rsi_curr: float) -> tuple[bool, bool]:
    bullish_div = False
    bearish_div = False
    if len(df) >= 16:
        window = df.iloc[-16:-1]
        prev_min_idx = window['close'].idxmin()
        prev_max_idx = window['close'].idxmax()
        bullish_div = (close_p <= df.loc[prev_min_idx, 'close']) and (rsi_curr > df.loc[prev_min_idx, 'RSI'] + 2.0) and (close_p > open_p)
        bearish_div = (close_p >= df.loc[prev_max_idx, 'close']) and (rsi_curr < df.loc[prev_max_idx, 'RSI'] - 2.0) and (close_p < open_p)
    return bullish_div, bearish_div

def _check_sma200_rejections(open_p: float, high_p: float, low_p: float, close_p: float, sma_200: float) -> tuple[bool, bool]:
    sma200_bounce = (low_p <= sma_200) and (close_p > sma_200) and (close_p > open_p)
    sma200_reject = (high_p >= sma_200) and (close_p < sma_200) and (close_p < open_p)
    return sma200_bounce, sma200_reject

def analyze_futures_market(df: pd.DataFrame) -> SignalPlan:
    """
    Analyzes the latest 30m candle for Futures Long/Short trading.
    """
    default_signal = SignalPlan(
        action="HOLD", strategy_used="NONE", stop_loss=0.0, 
        take_profit=0.0, time_in_trade=0, near_miss_reason="", position_side=""
    )
    if len(df) < 200:
        return default_signal
        
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    required_cols = ['SMA_200', 'SMA_99', 'RSI', 'ATR', 'SMA_20_Vol', 'BB_Lower', 'BB_Upper', 'ADX']
    if not all(col in latest for col in required_cols) or pd.isna(latest['SMA_200']):
        return default_signal
        
    price, atr, sma_200, sma_99 = latest['close'], latest['ATR'], latest['SMA_200'], latest['SMA_99']
    rsi_curr, vol_curr, vol_sma = latest['RSI'], latest['volume'], latest['SMA_20_Vol']
    open_p, high_p, low_p, close_p = latest['open'], latest['high'], latest['low'], latest['close']
    bb_lower, bb_upper = latest['BB_Lower'], latest['BB_Upper']
    sl_multiplier = 1.5
    
    is_macro_uptrend, is_macro_downtrend = price > sma_200, price < sma_200
    above_ma99, below_ma99 = price >= sma_99, price <= sma_99
    strong_volume = vol_curr > vol_sma
    body = abs(close_p - open_p)
    
    bullish_sweep, bearish_sweep = _check_liquidity_sweeps(open_p, high_p, low_p, close_p, bb_lower, bb_upper, body)
    bullish_div, bearish_div = _check_rsi_divergence(df, close_p, open_p, rsi_curr)
    sma200_bounce, sma200_reject = _check_sma200_rejections(open_p, high_p, low_p, close_p, sma_200)
    is_giant_candle = body > (atr * 2.0)
    
    sniper_long = (bullish_sweep or bullish_div or sma200_bounce) and strong_volume and is_macro_uptrend and not is_giant_candle and (close_p <= bb_upper) and above_ma99
    sniper_short = (bearish_sweep or bearish_div or sma200_reject) and strong_volume and is_macro_downtrend and not is_giant_candle and (close_p >= bb_lower) and below_ma99
    
    if sniper_long:
        return SignalPlan("BUY", "FUTURES_30M_SNIPER_LONG", price - (atr * sl_multiplier), 0.0, 0, "", "LONG")
    if sniper_short:
        return SignalPlan("SELL", "FUTURES_30M_SNIPER_SHORT", price + (atr * sl_multiplier), 0.0, 0, "", "SHORT")
        
    if rsi_curr > prev['RSI'] and prev['RSI'] < 30:
        return SignalPlan("BUY", "FUTURES_30M_EXIT", 0.0, 0.0, 0, "", "SHORT")
    if rsi_curr < prev['RSI'] and prev['RSI'] > 70:
        return SignalPlan("SELL", "FUTURES_30M_EXIT", 0.0, 0.0, 0, "", "LONG")
        
    near_miss_reason, strategy_used = "", "NONE"
    if bullish_sweep or bullish_div or sma200_bounce:
        strategy_used = "FUTURES_30M_SNIPER_LONG"
        near_miss_reason = f"No Volume Surge ({vol_curr:.1f} <= {vol_sma:.1f})" if not strong_volume else ("Against Macro Uptrend" if not is_macro_uptrend else "")
    elif bearish_sweep or bearish_div or sma200_reject:
        strategy_used = "FUTURES_30M_SNIPER_SHORT"
        near_miss_reason = f"No Volume Surge ({vol_curr:.1f} <= {vol_sma:.1f})" if not strong_volume else ("Against Macro Downtrend" if not is_macro_downtrend else "")
            
    if near_miss_reason:
        return SignalPlan("HOLD", strategy_used, 0.0, 0.0, 0, near_miss_reason, "")
        
    return default_signal

def evaluate_dynamic_strategy(df: pd.DataFrame, parameters: Dict[str, Any]) -> SignalPlan:
    """
    Evaluate the latest closed candle using the canonical lab strategy contract.

    The GPU kernel mirrors these predicates numerically.  This function is the
    live/paper boundary, so invalid manifests fail closed instead of silently
    falling back to strategy 0.
    """
    default_signal = SignalPlan("HOLD", "NONE", 0.0, 0.0, 0, "", "")
    if len(df) < 200:
        return default_signal

    try:
        params = normalize_strategy_parameters(parameters)
        strat_type = params["strategy_type"]
        strat = strategy_id(strat_type)
    except (TypeError, ValueError) as exc:
        return SignalPlan("HOLD", "INVALID_STRATEGY", 0.0, 0.0, 0, f"Invalid strategy parameters: {exc}", "")

    latest = df.iloc[-1]
    prev = df.iloc[-2]
    def value(name: str, fallback: float = 0.0) -> float:
        raw = latest.get(name, fallback)
        try:
            number = float(raw)
        except (TypeError, ValueError):
            return float(fallback)
        return number if math.isfinite(number) else float(fallback)

    c = value("close")
    h = value("high")
    l = value("low")
    o = value("open")
    v = value("volume")
    sma200 = value("SMA_200")
    sma50 = value("SMA_50")
    atr = value("ATR")
    rsi = value("RSI")
    adx = value("ADX")
    vol_sma = value("SMA_20_Vol")
    bb_up = value("BB_Upper")
    ema10 = value("EMA_10")
    ema50 = value("EMA_50")
    st_dir = value("supertrend_dir", 1.0)
    mfi = value("mfi", 50.0)
    stoch_k = value("stoch_rsi_k", 50.0)
    cci = value("cci")
    williams = value("williams_r", -50.0)
    keltner_low = value("keltner_lower")
    tenkan = value("ichimoku_tenkan")
    kijun = value("ichimoku_kijun")

    def previous_value(name: str, fallback: float = 0.0) -> float:
        raw = prev.get(name, fallback)
        try:
            number = float(raw)
        except (TypeError, ValueError):
            return float(fallback)
        return number if math.isfinite(number) else float(fallback)

    donchian_high_prev = previous_value("donchian_high_20")
    ema10_prev = previous_value("EMA_10")
    ema50_prev = previous_value("EMA_50")

    adx_thresh = float(params["adx_trend_thresh"])
    vol_mult = float(params["vol_surge_mult"])
    sl_atr = float(params["sl_atr_mult"])
    tp_rr = float(params["tp_rr_mult"])
    rsi_sniper = float(params["gear1_rsi_sniper"])
    stoch_thresh = float(params["stoch_k_thresh"])
    mfi_thresh = float(params["mfi_bull_thresh"])
    cci_thresh = float(params["cci_trend_thresh"])
    williams_thresh = float(params["williams_r_thresh"])
    sma200_buf = float(params["sma200_buffer_pct"])
    vol_floor = float(params["volume_floor_mult"])
    rsi_surge_ceil = float(params["rsi_surge_ceiling"])
    sl_cap = float(params["sl_hard_cap_pct"])
    tp_cap = float(params["tp_hard_cap_pct"])
    giant_mult = float(params["giant_candle_atr_mult"])
    use_dual = bool(params["use_dual_trend"])
    req_green = bool(params["require_green_candle"])
    macro = {"sma200_only": 0, "sma200_and_adx": 1, "none": 2}[params["macro_regime_filter"]]
    trend_min_adx = float(params["trend_strength_min_adx"])

    # Keep these guards identical in meaning to the lab kernel.  In
    # particular, exhaustion is a low-volume veto; using `>` here would make
    # every volume that passed the entry floor fail immediately.
    if not (c > 0.0 and atr > 0.0 and vol_sma > 0.0 and adx > adx_thresh and v > vol_sma * vol_floor):
        return default_signal

    trend_ok = True if macro == 2 else c > sma200 * sma200_buf
    if macro == 0 and use_dual:
        trend_ok = trend_ok and sma50 > sma200
    if macro == 1:
        trend_ok = trend_ok and adx > trend_min_adx
    if adx < float(params["sideways_max_adx"]):
        trend_ok = False
    if bool(params["adx_slope_check"]) and adx < 20.0:
        trend_ok = False

    candle_ok = not req_green or c > o
    if v < vol_sma * float(params["vol_exhaustion_mult"]):
        candle_ok = False
    is_not_blowoff = (h - l) <= atr * giant_mult
    is_rejection = ((min(o, c) - l) / (h - l)) > float(params["rejection_wick_ratio"]) if h > l else False
    volume_cap = float(params["vol_cap_rejection"] if is_rejection else params["vol_cap_normal"])
    candle_ok = candle_ok and v < vol_sma * volume_cap
    candle_ok = candle_ok and abs(c - o) / atr >= float(params["body_min_atr_pct"])
    candle_ok = candle_ok and (h - l) / c <= float(params["high_low_spread_cap"]) / 100.0

    bb_ok = strat == 9 or (bb_up > 0.0 and c <= bb_up * float(params["bb_upper_buffer"]))
    if not (trend_ok and is_not_blowoff and candle_ok and bb_ok):
        return default_signal

    momentum_positive = not bool(params["momentum_req_pos_hist"]) or cci > 0.0
    keltner_band = keltner_low * (1.0 + (float(params["keltner_mult"]) - 2.0) * 0.01)
    entry_ok = False
    if strat == 0:
        ema_slope_ok = ema10 >= ema10_prev + atr * (float(params["gear1_sniper_slope"]) - 1.0)
        entry_ok = (
            (rsi < rsi_sniper and rsi > float(params["gear1_sniper_min_rsi"])
             and rsi < float(params["gear1_sniper_max_rsi"]) and ema_slope_ok)
            or (v > vol_sma * vol_mult and rsi < rsi_surge_ceil)
        )
    elif strat == 1:
        entry_ok = ema10 > ema50 and ema10_prev <= ema50_prev and float(params["macd_cross_lookback"]) > 0.0
    elif strat == 2:
        entry_ok = st_dir > 0.5 and mfi > mfi_thresh and momentum_positive
    elif strat == 3:
        entry_ok = c > tenkan * float(params["ichi_cloud_buffer"]) and tenkan > kijun and cci > cci_thresh
    elif strat == 4:
        entry_ok = l <= keltner_band and c > keltner_low
    elif strat == 5:
        entry_ok = stoch_k < stoch_thresh and mfi > mfi_thresh
    elif strat == 6:
        entry_ok = williams < williams_thresh and rsi < rsi_sniper
    elif strat == 7:
        entry_ok = c >= donchian_high_prev and adx > trend_min_adx
    elif strat == 8:
        entry_ok = (ema10 - ema50) / c > 0.005 and ema10 > ema10_prev and v > vol_sma * vol_mult
    elif strat == 9:
        entry_ok = c > bb_up * float(params["bb_lower_buffer"]) and adx > adx_thresh and (atr / c) < 0.03
    elif strat == 10:
        entry_ok = st_dir > 0.5 and tenkan > kijun and mfi > mfi_thresh and rsi > 50.0
    elif strat == 11:
        pullback = (donchian_high_prev - c) / donchian_high_prev if donchian_high_prev > 0.0 else -1.0
        entry_ok = c > sma200 and float(params["spot_step_lock1"]) <= pullback <= float(params["spot_step_trigger1"]) and rsi < float(params["rsi_hook_oversold"])

    if not entry_ok:
        return default_signal

    sl_val = c - atr * sl_atr
    final_sl = max(sl_val, c * (1.0 - sl_cap))
    tp_val = c + atr * sl_atr * tp_rr
    final_tp = min(tp_val, c * (1.0 + tp_cap))
    return SignalPlan("BUY", strat_type.upper(), final_sl, final_tp, int(params["max_hold_bars"]), "", "LONG")

