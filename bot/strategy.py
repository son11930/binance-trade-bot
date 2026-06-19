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
    rsi_limit = 75 if vol_surge_multiplier >= 3.0 else 70
    
    # Check if MACD crossed above signal within last 5 periods
    recent_macd_cross = False
    if len(df) >= 5:
        for i in range(1, 6):
            idx_curr = -i
            idx_prev = -i - 1
            if df.iloc[idx_curr]['MACD'] > df.iloc[idx_curr]['MACD_Signal'] and df.iloc[idx_prev]['MACD'] <= df.iloc[idx_prev]['MACD_Signal']:
                recent_macd_cross = True
                break

    near_miss_reason = ""
    if recent_macd_cross and price > sma_200:
        if rsi_curr >= rsi_limit:
            near_miss_reason = f"RSI too high ({rsi_curr:.1f} >= {rsi_limit})"
        elif vol_curr <= vol_sma:
            near_miss_reason = f"Volume too low ({vol_curr:.1f} <= {vol_sma:.1f})"

    # BUY: MACD crossed ABOVE Signal Line in last 5 periods AND Price > SMA 200 AND RSI < dynamic limit AND Volume > SMA
    if recent_macd_cross and price > sma_200 and rsi_curr < rsi_limit and vol_curr > vol_sma:
        return SignalPlan(
            action="BUY",
            strategy_used="TREND_MACD",
            stop_loss=price - (atr * 1.5), # Keep trailing SL
            take_profit=0.0,               # Remove fixed TP for trend riding
            time_in_trade=24,
            near_miss_reason=""
        )
        
    # SELL: MACD is BELOW Signal Line
    if macd_curr < sig_curr:
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
    
    rsi_hook = rsi_curr > rsi_prev and rsi_prev <= 40
    
    # 1. Price Action Proof of Absorption
    is_green_candle = latest.get('close', 0) > latest.get('open', 0)
    candle_range = latest.get('high', 0) - latest.get('low', 0)
    lower_wick = min(latest.get('open', 0), latest.get('close', 0)) - latest.get('low', 0)
    is_strong_rejection = (lower_wick / candle_range) > 0.4 if candle_range > 0 else False
    
    # 2. Dynamic Volume Cap
    vol_limit_multiplier = 3.0 if (is_green_candle or is_strong_rejection) else 1.5
    dynamic_vol_limit = vol_sma * vol_limit_multiplier
    
    near_miss_reason = ""
    if rsi_hook and price <= bb_lower * 1.01:
        if vol_curr > dynamic_vol_limit:
            near_miss_reason = f"Volume too high ({vol_curr:.1f} > {dynamic_vol_limit:.1f})"

    # BUY: RSI Hook AND price near lower BB AND Volume <= Dynamic Limit
    if rsi_hook and price <= bb_lower * 1.01 and vol_curr <= dynamic_vol_limit:
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
    
    required_cols = ['SMA_200', 'RSI', 'MACD', 'MACD_Signal', 'ATR', 'ADX', 'SMA_20_Vol']
    if not all(col in latest for col in required_cols) or pd.isna(latest['SMA_200']) or pd.isna(latest['ADX']):
        return default_signal
        
    price = latest['close']
    atr = latest['ATR']
    sma_200 = latest['SMA_200']
    macd_curr = latest['MACD']
    sig_curr = latest['MACD_Signal']
    macd_prev = prev['MACD']
    sig_prev = prev['MACD_Signal']
    rsi_curr = latest['RSI']
    adx_curr = latest['ADX']
    vol_curr = latest['volume']
    vol_sma = latest['SMA_20_Vol']
    
    # Check if MACD crossed within last 5 periods
    recent_macd_cross_up = False
    recent_macd_cross_down = False
    if len(df) >= 5:
        for i in range(1, 6):
            idx_curr = -i
            idx_prev = -i - 1
            if df.iloc[idx_curr]['MACD'] > df.iloc[idx_curr]['MACD_Signal'] and df.iloc[idx_prev]['MACD'] <= df.iloc[idx_prev]['MACD_Signal']:
                recent_macd_cross_up = True
            if df.iloc[idx_curr]['MACD'] < df.iloc[idx_curr]['MACD_Signal'] and df.iloc[idx_prev]['MACD'] >= df.iloc[idx_prev]['MACD_Signal']:
                recent_macd_cross_down = True
    
    macd_cross_up = recent_macd_cross_up
    macd_cross_down = recent_macd_cross_down
    
    # 15M needs more room to breathe, wide stop loss (2.5x ATR) and high take profit (5.0x ATR)
    sl_multiplier = 2.5
    tp_multiplier = 5.0
    
    # Momentum Filter: ADX must be > 15 for a trend
    strong_trend = adx_curr > 15
    
    # Volume Filter: Relaxed to allow AI Council to decide
    strong_volume = True
    
    # Long Entry
    if price > sma_200 and macd_cross_up and rsi_curr < 70 and strong_trend and strong_volume:
        return SignalPlan(
            action="BUY", strategy_used="FUTURES_15M_LONG",
            stop_loss=price - (atr * sl_multiplier), take_profit=price + (atr * tp_multiplier),
            time_in_trade=24, near_miss_reason="", position_side="LONG"
        )
        
    # Short Entry
    if price < sma_200 and macd_cross_down and rsi_curr > 30 and strong_trend and strong_volume:
        return SignalPlan(
            action="SELL", strategy_used="FUTURES_15M_SHORT",
            stop_loss=price + (atr * sl_multiplier), take_profit=price - (atr * tp_multiplier),
            time_in_trade=24, near_miss_reason="", position_side="SHORT"
        )
        
    # Exits: Reversals (Wait for definitive cross, or rely on SL/TP)
    # Since we are on 15M, a simple MACD reverse cross is less frequent, but still happens. 
    # Let's add an RSI condition to prevent exiting purely on minor pullbacks.
    # We exit LONG if MACD crosses down AND RSI was overbought recently (> 65)
    if macd_cross_down and rsi_curr > 65:
        return SignalPlan("SELL", "FUTURES_15M_EXIT", 0.0, 0.0, 0, "", "LONG") # Close Long
        
    # We exit SHORT if MACD crosses up AND RSI was oversold recently (< 35)
    if macd_cross_up and rsi_curr < 35:
        return SignalPlan("BUY", "FUTURES_15M_EXIT", 0.0, 0.0, 0, "", "SHORT") # Close Short
        
    near_miss_reason = ""
    strategy_used = "NONE"
    
    if macd_cross_up:
        strategy_used = "FUTURES_15M_LONG"
        if price <= sma_200:
            near_miss_reason = f"Price below SMA200 ({price:.2f} <= {sma_200:.2f})"
        elif rsi_curr >= 70:
            near_miss_reason = f"RSI Overbought ({rsi_curr:.1f} >= 70)"
        elif not strong_trend:
            near_miss_reason = f"Weak Trend (ADX {adx_curr:.1f} <= 15)"
            
    elif macd_cross_down:
        strategy_used = "FUTURES_15M_SHORT"
        if price >= sma_200:
            near_miss_reason = f"Price above SMA200 ({price:.2f} >= {sma_200:.2f})"
        elif rsi_curr <= 30:
            near_miss_reason = f"RSI Oversold ({rsi_curr:.1f} <= 30)"
        elif not strong_trend:
            near_miss_reason = f"Weak Trend (ADX {adx_curr:.1f} <= 15)"
            
    if near_miss_reason:
        return SignalPlan(
            action="HOLD", strategy_used=strategy_used, stop_loss=0.0, 
            take_profit=0.0, time_in_trade=0, near_miss_reason=near_miss_reason, position_side=""
        )
        
    return default_signal
