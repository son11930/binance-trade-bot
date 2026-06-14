import pandas as pd
import numpy as np
import ta
from typing import NamedTuple

class SignalPlan(NamedTuple):
    action: str
    strategy_used: str
    stop_loss: float
    take_profit: float
    time_in_trade: int


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
    
    # Check if MACD crossed above signal within last 3 periods
    recent_macd_cross = False
    if len(df) >= 3:
        for i in range(1, 4):
            idx_curr = -i
            idx_prev = -i - 1
            if df.iloc[idx_curr]['MACD'] > df.iloc[idx_curr]['MACD_Signal'] and df.iloc[idx_prev]['MACD'] <= df.iloc[idx_prev]['MACD_Signal']:
                recent_macd_cross = True
                break

    # BUY: MACD crossed ABOVE Signal Line in last 3 periods AND Price > SMA 200 AND RSI < 65 AND Volume > 1.5x SMA
    if recent_macd_cross and price > sma_200 and rsi_curr < 65 and vol_curr > (vol_sma * 1.5):
        return SignalPlan(
            action="BUY",
            strategy_used="TREND_MACD",
            stop_loss=price - (atr * 1.5), # Keep trailing SL
            take_profit=0.0,               # Remove fixed TP for trend riding
            time_in_trade=24
        )
        
    # SELL: MACD crosses BELOW Signal Line
    if macd_curr < sig_curr and macd_prev >= sig_prev:
        return SignalPlan(
            action="SELL",
            strategy_used="TREND_MACD",
            stop_loss=0.0,
            take_profit=0.0,
            time_in_trade=0
        )
        
    return SignalPlan(
        action="HOLD",
        strategy_used="TREND_MACD",
        stop_loss=0.0,
        take_profit=0.0,
        time_in_trade=0
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
    
    # BUY: RSI crosses back ABOVE 30 (Reversal) AND price near lower BB AND Volume <= SMA
    if rsi_curr > 30 and rsi_prev <= 30 and price <= bb_lower * 1.01 and vol_curr <= vol_sma:
        return SignalPlan(
            action="BUY",
            strategy_used="SIDEWAYS_RSI_BB",
            stop_loss=price - (atr * 1.5), 
            take_profit=latest['BB_Upper'],             
            time_in_trade=10                  
        )
        
    # SELL: RSI crosses back BELOW 70 (Reversal confirmation) AND price is near upper BB
    if (rsi_curr < 70 and rsi_prev >= 70 and price >= bb_upper * 0.99) or (price >= bb_upper):
        return SignalPlan(
            action="SELL",
            strategy_used="SIDEWAYS_RSI_BB",
            stop_loss=0.0,
            take_profit=0.0,
            time_in_trade=0
        )
        
    return SignalPlan(
        action="HOLD",
        strategy_used="SIDEWAYS_RSI_BB",
        stop_loss=0.0,
        take_profit=0.0,
        time_in_trade=0
    )
