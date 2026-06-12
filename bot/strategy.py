import pandas as pd
import numpy as np

def apply_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applies MACD, SMA 200, RSI, and ATR for Trend Following and Risk Management.
    """
    # SMA 200
    df['SMA_200'] = df['close'].rolling(window=200).mean()
    
    # MACD (12, 26, 9)
    ema_fast = df['close'].ewm(span=12, adjust=False).mean()
    ema_slow = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema_fast - ema_slow
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
    # RSI (14) - Wilder's Smoothing
    delta = df['close'].diff()
    gain = delta.where(delta > 0, 0)
    loss = -delta.where(delta < 0, 0)
    avg_gain = gain.ewm(alpha=1/14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1/14, adjust=False).mean()
    rs = avg_gain / avg_loss
    df['RSI'] = 100 - (100 / (1 + rs))
    
    # ATR (14) - Wilder's Smoothing
    high_low = df['high'] - df['low']
    high_close = np.abs(df['high'] - df['close'].shift())
    low_close = np.abs(df['low'] - df['close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    true_range = ranges.max(axis=1)
    df['ATR'] = true_range.ewm(alpha=1/14, adjust=False).mean()
    
    return df

def analyze_market(df: pd.DataFrame):
    """
    Analyzes the latest candle and returns a trading signal.
    Returns: 'BUY', 'SELL', or 'HOLD'
    """
    if len(df) < 200:
        return "HOLD"
        
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    if pd.isna(latest['SMA_200']) or pd.isna(latest['RSI']):
        return "HOLD"
        
    price = latest['close']
    sma_200 = latest['SMA_200']
    rsi_curr = latest['RSI']
    
    macd_curr = latest['MACD']
    sig_curr = latest['Signal_Line']
    macd_prev = prev['MACD']
    sig_prev = prev['Signal_Line']
    
    # BUY: MACD crosses ABOVE Signal Line AND Price > SMA 200 AND RSI < 65 (Not overbought)
    if macd_curr > sig_curr and macd_prev <= sig_prev and price > sma_200 and rsi_curr < 65:
        return "BUY"
        
    # SELL: MACD crosses BELOW Signal Line (Trend momentum dies)
    if macd_curr < sig_curr and macd_prev >= sig_prev:
        return "SELL"
        
    return "HOLD"

