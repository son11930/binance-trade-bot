import pandas as pd

def apply_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Applies MACD and SMA 200 for Trend Following.
    """
    # SMA 200
    df['SMA_200'] = df['close'].rolling(window=200).mean()
    
    # MACD (12, 26, 9)
    ema_fast = df['close'].ewm(span=12, adjust=False).mean()
    ema_slow = df['close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema_fast - ema_slow
    df['Signal_Line'] = df['MACD'].ewm(span=9, adjust=False).mean()
    
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
    
    if pd.isna(latest['SMA_200']):
        return "HOLD"
        
    price = latest['close']
    sma_200 = latest['SMA_200']
    
    macd_curr = latest['MACD']
    sig_curr = latest['Signal_Line']
    macd_prev = prev['MACD']
    sig_prev = prev['Signal_Line']
    
    # BUY: MACD crosses ABOVE Signal Line AND Price > SMA 200
    if macd_curr > sig_curr and macd_prev <= sig_prev and price > sma_200:
        return "BUY"
        
    # SELL: MACD crosses BELOW Signal Line (Let profit run until momentum dies)
    if macd_curr < sig_curr and macd_prev >= sig_prev:
        return "SELL"
        
    return "HOLD"
