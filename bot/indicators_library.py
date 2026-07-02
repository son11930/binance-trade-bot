"""
Alpha Feature Library (Indicators Library for Strategy Synthesis)
Provides modular, vectorized technical indicator computations for the Evolutionary Strategy Synthesizer.
Isolated from production bot code to prevent dependency clutter while enabling genome evolution.
"""

import pandas as pd
import numpy as np
import ta


# ==========================================
# 1. TREND INDICATORS
# ==========================================

def calc_supertrend(df: pd.DataFrame, period: int = 10, multiplier: float = 3.0) -> pd.DataFrame:
    """Calculates Supertrend indicator (trend direction and trailing boundary)."""
    atr = ta.volatility.average_true_range(df['high'], df['low'], df['close'], window=period)
    hl2 = (df['high'] + df['low']) / 2.0
    upperband = hl2 + (multiplier * atr)
    lowerband = hl2 - (multiplier * atr)
    
    in_uptrend = True
    st_arr = np.zeros(len(df))
    dir_arr = np.zeros(len(df), dtype=int)
    
    close_arr = df['close'].values
    ub_arr = upperband.values
    lb_arr = lowerband.values
    
    for i in range(1, len(df)):
        if close_arr[i] > ub_arr[i - 1]:
            in_uptrend = True
        elif close_arr[i] < lb_arr[i - 1]:
            in_uptrend = False
            
        if in_uptrend:
            lb_arr[i] = max(lb_arr[i], lb_arr[i - 1]) if close_arr[i - 1] > lb_arr[i - 1] else lb_arr[i]
            st_arr[i] = lb_arr[i]
            dir_arr[i] = 1
        else:
            ub_arr[i] = min(ub_arr[i], ub_arr[i - 1]) if close_arr[i - 1] < ub_arr[i - 1] else ub_arr[i]
            st_arr[i] = ub_arr[i]
            dir_arr[i] = -1
            
    res = df.copy()
    res['supertrend'] = st_arr
    res['supertrend_dir'] = dir_arr
    return res


def calc_ichimoku(df: pd.DataFrame) -> pd.DataFrame:
    """Calculates Ichimoku Cloud (Tenkan-sen, Kijun-sen, Senkou Span A/B)."""
    res = df.copy()
    high_9 = res['high'].rolling(window=9).max()
    low_9 = res['low'].rolling(window=9).min()
    res['ichimoku_tenkan'] = (high_9 + low_9) / 2.0
    
    high_26 = res['high'].rolling(window=26).max()
    low_26 = res['low'].rolling(window=26).min()
    res['ichimoku_kijun'] = (high_26 + low_26) / 2.0
    
    res['ichimoku_span_a'] = ((res['ichimoku_tenkan'] + res['ichimoku_kijun']) / 2.0).shift(26)
    
    high_52 = res['high'].rolling(window=52).max()
    low_52 = res['low'].rolling(window=52).min()
    res['ichimoku_span_b'] = ((high_52 + low_52) / 2.0).shift(26)
    return res


def calc_keltner_channels(df: pd.DataFrame, window: int = 20, mult: float = 2.0) -> pd.DataFrame:
    """Calculates Keltner Channels based on EMA and ATR."""
    res = df.copy()
    ema = ta.trend.ema_indicator(res['close'], window=window)
    atr = ta.volatility.average_true_range(res['high'], res['low'], res['close'], window=window)
    res['keltner_mid'] = ema
    res['keltner_upper'] = ema + (mult * atr)
    res['keltner_lower'] = ema - (mult * atr)
    return res


# ==========================================
# 2. MOMENTUM & FLOW INDICATORS
# ==========================================

def calc_momentum_flow(df: pd.DataFrame) -> pd.DataFrame:
    """Applies StochRSI, MFI, CCI, and Williams %R to the dataframe."""
    res = df.copy()
    stoch = ta.momentum.StochRSIIndicator(res['close'], window=14, smooth1=3, smooth2=3)
    res['stoch_rsi_k'] = stoch.stochrsi_k() * 100.0
    res['stoch_rsi_d'] = stoch.stochrsi_d() * 100.0
    
    res['mfi'] = ta.volume.money_flow_index(res['high'], res['low'], res['close'], res['volume'], window=14)
    res['cci'] = ta.trend.cci(res['high'], res['low'], res['close'], window=20)
    res['williams_r'] = ta.momentum.williams_r(res['high'], res['low'], res['close'], lbp=14)
    return res


# ==========================================
# 3. VOLATILITY & VOLUME INDICATORS
# ==========================================

def calc_volatility_volume(df: pd.DataFrame) -> pd.DataFrame:
    """Applies Donchian Channels, VWAP, OBV, Chaikin Money Flow, and BB Width."""
    res = df.copy()
    res['donchian_high_20'] = res['high'].rolling(window=20).max()
    res['donchian_low_20'] = res['low'].rolling(window=20).min()
    
    tp = (res['high'] + res['low'] + res['close']) / 3.0
    res['vwap_48'] = (tp * res['volume']).rolling(window=48).sum() / res['volume'].rolling(window=48).sum()
    
    res['obv'] = ta.volume.on_balance_volume(res['close'], res['volume'])
    res['cmf'] = ta.volume.chaikin_money_flow(res['high'], res['low'], res['close'], res['volume'], window=20)
    
    bb = ta.volatility.BollingerBands(res['close'], window=20, window_dev=2.0)
    res['bb_width'] = (bb.bollinger_hband() - bb.bollinger_lband()) / bb.bollinger_mavg()
    return res


def apply_all_alpha_features(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applies the full suite of Alpha Features to an OHLCV DataFrame.
    Used by the Evolutionary Strategy Synthesizer to test diverse Strategy Genomes.
    """
    if len(df) < 50:
        return df
    res = calc_supertrend(df)
    res = calc_ichimoku(res)
    res = calc_keltner_channels(res)
    res = calc_momentum_flow(res)
    res = calc_volatility_volume(res)
    return res
