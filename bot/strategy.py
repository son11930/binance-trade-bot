import pandas as pd
import ta
from typing import NamedTuple

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
            time_in_trade=24,
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
            time_in_trade=16,
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

def analyze_futures_market(df: pd.DataFrame) -> SignalPlan:
    """
    Analyzes the latest 15m candle for Futures Long/Short trading.
    """
    default_signal = SignalPlan(
        action="HOLD", strategy_used="NONE", stop_loss=0.0, 
        take_profit=0.0, time_in_trade=0, near_miss_reason="", position_side=""
    )

    if len(df) < 200:
        return default_signal
        
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    required_cols = ['SMA_200', 'EMA_50', 'RSI', 'MACD', 'MACD_Signal', 'ATR', 'ADX', 'SMA_20_Vol', 'BB_Lower', 'BB_Upper']
    if not all(col in latest for col in required_cols) or pd.isna(latest['SMA_200']) or pd.isna(latest['ADX']):
        return default_signal
        
    price = latest['close']
    atr = latest['ATR']
    sma_200 = latest['SMA_200']
    ema_50 = latest['EMA_50']
    macd_curr = latest['MACD']
    sig_curr = latest['MACD_Signal']
    macd_prev = prev['MACD']
    sig_prev = prev['MACD_Signal']
    rsi_curr = latest['RSI']
    adx_curr = latest['ADX']
    adx_prev = prev['ADX']
    vol_curr = latest['volume']
    vol_sma = latest['SMA_20_Vol']
    
    # Check if MACD crossed within last 5 periods. Only take the MOST RECENT cross.
    recent_macd_cross_up = False
    recent_macd_cross_down = False
    if len(df) >= 5:
        for i in range(1, 6):
            idx_curr = -i
            idx_prev = -i - 1
            if df.iloc[idx_curr]['MACD'] > df.iloc[idx_curr]['MACD_Signal'] and df.iloc[idx_prev]['MACD'] <= df.iloc[idx_prev]['MACD_Signal']:
                recent_macd_cross_up = True
                break
            if df.iloc[idx_curr]['MACD'] < df.iloc[idx_curr]['MACD_Signal'] and df.iloc[idx_prev]['MACD'] >= df.iloc[idx_prev]['MACD_Signal']:
                recent_macd_cross_down = True
                break
    
    macd_cross_up = recent_macd_cross_up
    macd_cross_down = recent_macd_cross_down
    
    # 15M V-Shape Sniper: Ultra-tight stop loss for 1% risk
    sl_multiplier = 1.0
    tp_multiplier = 3.5
    
    # Volume Filter: Ensure volume isn't dead
    strong_volume = vol_curr > (vol_sma * 0.8)
    
    # Fast Momentum (Histogram Reversal)
    macd_hist_curr = macd_curr - sig_curr
    macd_hist_prev = macd_prev - sig_prev
    fast_momentum_up = macd_hist_curr > macd_hist_prev and macd_hist_curr > 0
    fast_momentum_down = macd_hist_curr < macd_hist_prev and macd_hist_curr < 0
    
    # Mean Reversion (V-Shape Sniping)
    
    # Trend Strength & Macro Filters
    is_strong_trend = adx_curr >= 25
    is_macro_uptrend = price > sma_200
    is_macro_downtrend = price < sma_200
    
    # Smart RSI Hooks (Demand extreme RSI if fighting a strong trend)
    valid_dip_rsi = (prev['RSI'] < 25) if (is_strong_trend and is_macro_downtrend) else (prev['RSI'] < 45 if is_macro_uptrend else prev['RSI'] < 35)
    rsi_hook_up_smart = rsi_curr > prev['RSI'] and valid_dip_rsi
    
    valid_peak_rsi = (prev['RSI'] > 75) if (is_strong_trend and is_macro_uptrend) else (prev['RSI'] > 55 if is_macro_downtrend else prev['RSI'] > 65)
    rsi_hook_down_smart = rsi_curr < prev['RSI'] and valid_peak_rsi
    
    # Long Entry conditions
    # Buy the Dip (Pullback in Bull Market or Extreme Crash in Bear Market)
    dip_buy_signal = rsi_hook_up_smart and price <= ema_50 * 1.005 # Relaxed to allow 0.5% above EMA50
    
    # Trend Buy must align with macro trend AND enter near the dynamic support (EMA 50)
    # 2.5% ceiling to prevent buying the absolute top of a pump, while still allowing breakouts
    trend_buy_signal = (price <= ema_50 * 1.025) and (price >= ema_50 * 0.985) and fast_momentum_up and rsi_curr < 70 and is_macro_uptrend
    
    if (dip_buy_signal or trend_buy_signal) and strong_volume:
        strategy_name = "FUTURES_15M_DIP_BUY" if dip_buy_signal else "FUTURES_15M_TREND_FAST"
        return SignalPlan(
            action="BUY", strategy_used=strategy_name,
            stop_loss=price - (atr * sl_multiplier), take_profit=0.0,
            time_in_trade=24, near_miss_reason="", position_side="LONG"
        )
        
    # Short Entry conditions
    # Short the Peak (Bounce in Bear Market or Extreme Pump in Bull Market)
    peak_short_signal = rsi_hook_down_smart and price > ema_50
    
    # Trend Short must align with macro trend AND enter near dynamic resistance (EMA 50)
    # 2.5% floor to prevent shorting the absolute bottom of a dump, while still allowing breakdowns
    trend_short_signal = (price >= ema_50 * 0.975) and (price <= ema_50 * 1.015) and fast_momentum_down and rsi_curr > 30 and is_macro_downtrend
    
    if (peak_short_signal or trend_short_signal) and strong_volume:
        strategy_name = "FUTURES_15M_PEAK_SHORT" if peak_short_signal else "FUTURES_15M_TREND_FAST_SHORT"
        return SignalPlan(
            action="SELL", strategy_used=strategy_name,
            stop_loss=price + (atr * sl_multiplier), take_profit=0.0,
            time_in_trade=24, near_miss_reason="", position_side="SHORT"
        )
    if macd_cross_down and rsi_curr > 65:
        return SignalPlan("SELL", "FUTURES_15M_EXIT", 0.0, 0.0, 0, "", "LONG") # Close Long
        
    # We exit SHORT if MACD crosses up AND RSI was oversold recently (< 35)
    if macd_cross_up and rsi_curr < 35:
        return SignalPlan("BUY", "FUTURES_15M_EXIT", 0.0, 0.0, 0, "", "SHORT") # Close Short
        
    near_miss_reason = ""
    strategy_used = "NONE"
    
    if rsi_hook_up_smart:
        strategy_used = "FUTURES_15M_DIP_BUY"
        if price > ema_50 * 1.005:
            near_miss_reason = f"Price not below EMA50 ({price:.2f} > {ema_50 * 1.005:.2f})"
            
    elif rsi_hook_down_smart:
        strategy_used = "FUTURES_15M_PEAK_SHORT"
        if price <= ema_50:
            near_miss_reason = f"Price not above EMA50 ({price:.2f} <= {ema_50:.2f})"
            
    elif fast_momentum_up and macd_cross_up:
        strategy_used = "FUTURES_15M_TREND_FAST"
        if price > ema_50 * 1.025 or price < ema_50 * 0.985:
            near_miss_reason = f"Price not in Pullback Zone ({price:.2f} vs EMA50 {ema_50:.2f})"
        elif rsi_curr >= 70:
            near_miss_reason = f"RSI Overbought ({rsi_curr:.1f} >= 70)"
            
    elif fast_momentum_down and macd_cross_down:
        strategy_used = "FUTURES_15M_TREND_FAST_SHORT"
        if price > ema_50 * 1.015 or price < ema_50 * 0.975:
            near_miss_reason = f"Price not in Pullback Zone ({price:.2f} vs EMA50 {ema_50:.2f})"
        elif rsi_curr <= 30:
            near_miss_reason = f"RSI Oversold ({rsi_curr:.1f} <= 30)"
            
    if near_miss_reason:
        return SignalPlan(
            action="HOLD", strategy_used=strategy_used, stop_loss=0.0, 
            take_profit=0.0, time_in_trade=0, near_miss_reason=near_miss_reason, position_side=""
        )
        
    return default_signal
