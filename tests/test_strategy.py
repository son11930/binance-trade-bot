import pytest
import pandas as pd
from unittest.mock import patch
from bot.strategy import (
    analyze_market,
    execute_trend_strategy,
    execute_sideways_strategy,
    detect_regime,
    SignalPlan
)

def create_df(macd_vals, sig_vals):
    # Pad to 200 length
    pad_len = max(0, 200 - len(macd_vals))
    macd_vals = [0]*pad_len + macd_vals
    sig_vals = [1]*pad_len + sig_vals

    return pd.DataFrame({
        'MACD': macd_vals,
        'MACD_Signal': sig_vals,
        'SMA_200': [10] * len(macd_vals),
        'EMA_50': [10] * len(macd_vals),
        'RSI': [50] * len(macd_vals),
        'volume': [1000] * len(macd_vals),
        'SMA_20_Vol': [1000] * len(macd_vals),
        'BB_Lower': [5] * len(macd_vals),
        'BB_Upper': [15] * len(macd_vals),
        'open': [15] * len(macd_vals),
        'high': [15] * len(macd_vals),
        'low': [15] * len(macd_vals),
        'close': [15] * len(macd_vals),
        'ADX': [30] * len(macd_vals),
        'ATR': [1] * len(macd_vals)
    })

def test_analyze_market_trending():
    # recent macd cross
    df = create_df([0]*8 + [-1, 2], [1]*8 + [0, 1])
    with patch('bot.strategy.detect_regime', return_value="TRENDING"):
        res = analyze_market(df)
        assert res.action == "BUY"

def test_analyze_market_sideways():
    df = create_df([0]*10, [0]*10)
    df.iloc[-1, df.columns.get_loc('RSI')] = 35
    df.iloc[-2, df.columns.get_loc('RSI')] = 20
    df.iloc[-1, df.columns.get_loc('close')] = 5
    df.iloc[-1, df.columns.get_loc('open')] = 10
    df.iloc[-1, df.columns.get_loc('high')] = 10
    df.iloc[-1, df.columns.get_loc('low')] = 10
    df.iloc[-1, df.columns.get_loc('volume')] = 500
    with patch('bot.strategy.detect_regime', return_value="SIDEWAYS"):
        res = analyze_market(df)
        assert res.action == "BUY"

def test_execute_trend_strategy_buy():
    df = create_df([0]*8 + [-1, 2], [1]*8 + [0, 1])
    prev = df.iloc[-2]
    latest = df.iloc[-1]
    res = execute_trend_strategy(df, latest, prev, 15, 2)
    assert res.action == "BUY"

def test_execute_trend_strategy_sell():
    # No recent cross up. MACD just crossed down.
    df = create_df([-1]*8 + [1, -1], [1]*8 + [0, 1])
    prev = df.iloc[-2]
    latest = df.iloc[-1]
    latest['RSI'] = 85
    res = execute_trend_strategy(df, latest, prev, 15, 2)
    assert res.action == "SELL"

def test_execute_trend_strategy_hold():
    df = create_df([0]*10, [1]*10)
    prev = df.iloc[-2]
    latest = df.iloc[-1]
    res = execute_trend_strategy(df, latest, prev, 15, 2)
    assert res.action == "HOLD"

def test_execute_sideways_strategy_buy():
    prev = pd.Series({'RSI': 20})
    latest = pd.Series({'RSI': 35, 'BB_Lower': 10, 'BB_Upper': 20, 'volume': 500, 'SMA_20_Vol': 1000, 'open': 10, 'close': 10, 'high': 10, 'low': 10})
    res = execute_sideways_strategy(latest, prev, 10, 2)
    assert res.action == "BUY"

def test_execute_sideways_strategy_sell():
    prev = pd.Series({'RSI': 75})
    latest = pd.Series({'RSI': 65, 'BB_Lower': 10, 'BB_Upper': 20, 'volume': 1000, 'SMA_20_Vol': 1000, 'open': 20, 'close': 19.9, 'high': 20, 'low': 19})
    res = execute_sideways_strategy(latest, prev, 19.9, 2)
    assert res.action == "SELL"
