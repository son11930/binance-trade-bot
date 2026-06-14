import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch

from bot.strategy import (
    apply_indicators,
    detect_regime,
    analyze_market,
    execute_trend_strategy,
    execute_sideways_strategy,
    SignalPlan
)

def test_apply_indicators_less_than_200():
    df = pd.DataFrame({'close': range(100)})
    result = apply_indicators(df)
    assert 'SMA_200' not in result.columns

def test_apply_indicators_success():
    df = pd.DataFrame({
        'close': np.random.rand(250) * 100,
        'high': np.random.rand(250) * 110,
        'low': np.random.rand(250) * 90,
        'volume': np.random.rand(250) * 1000
    })
    result = apply_indicators(df)
    expected_cols = ['SMA_200', 'SMA_50', 'MACD', 'MACD_Signal', 'RSI', 'BB_Upper', 'BB_Lower', 'BB_Mid', 'ADX', 'ATR', 'SMA_20_Vol']
    for col in expected_cols:
        assert col in result.columns

def test_detect_regime_less_than_14():
    df = pd.DataFrame({'ADX': range(10)})
    assert detect_regime(df) == "UNKNOWN"

def test_detect_regime_nan_adx():
    df = pd.DataFrame({'ADX': [np.nan] * 20})
    assert detect_regime(df) == "UNKNOWN"

def test_detect_regime_trending():
    df = pd.DataFrame({'ADX': [20] * 12 + [24, 26]}) # len 14, prev=24, latest=26 -> >25 and >prev
    assert detect_regime(df) == "TRENDING"

def test_detect_regime_sideways_low_adx():
    df = pd.DataFrame({'ADX': [20] * 12 + [26, 24]}) # len 14, latest=24 -> <= 25
    assert detect_regime(df) == "SIDEWAYS"

def test_detect_regime_sideways_falling_adx():
    df = pd.DataFrame({'ADX': [20] * 12 + [30, 28]}) # len 14, latest=28, prev=30 -> falling
    assert detect_regime(df) == "SIDEWAYS"

def test_analyze_market_less_than_200():
    df = pd.DataFrame({'close': range(100)})
    result = analyze_market(df)
    assert result.action == "HOLD"

def test_analyze_market_missing_cols():
    df = pd.DataFrame({'close': range(201)})
    result = analyze_market(df)
    assert result.action == "HOLD"

def test_analyze_market_nan_values():
    df = pd.DataFrame({
        'SMA_200': [np.nan] * 201,
        'RSI': [50] * 201,
        'MACD': [0] * 201,
        'MACD_Signal': [0] * 201,
        'BB_Lower': [10] * 201,
        'BB_Upper': [20] * 201,
        'ATR': [1] * 201,
        'SMA_20_Vol': [1000] * 201,
        'ADX': [30] * 201,
        'close': [15] * 201
    })
    result = analyze_market(df)
    assert result.action == "HOLD"

@patch('bot.strategy.detect_regime')
def test_analyze_market_routes_to_trending(mock_detect_regime):
    mock_detect_regime.return_value = "TRENDING"
    # Will call execute_trend_strategy with latest MACD=2, Signal=1, prev MACD=0, prev Signal=1.
    df = pd.DataFrame({
        'SMA_200': [10] * 201,
        'RSI': [50] * 201,
        'MACD': [0] * 199 + [0, 2], # prev=0, latest=2
        'MACD_Signal': [0] * 199 + [1, 1], # prev=1, latest=1 -> MACD crosses above signal
        'BB_Lower': [10] * 201,
        'BB_Upper': [20] * 201,
        'ATR': [1] * 201,
        'SMA_20_Vol': [1000] * 201,
        'ADX': [30] * 201,
        'close': [15] * 201,
        'volume': [2000] * 201
    })
    result = analyze_market(df)
    assert result.action == "BUY"
    assert result.strategy_used == "TREND_MACD"

@patch('bot.strategy.detect_regime')
def test_analyze_market_routes_to_sideways(mock_detect_regime):
    mock_detect_regime.return_value = "SIDEWAYS"
    df = pd.DataFrame({
        'SMA_200': [10] * 201,
        'RSI': [50] * 199 + [20, 35], # prev=20, latest=35
        'MACD': [0] * 201,
        'MACD_Signal': [0] * 201,
        'BB_Lower': [10] * 201,
        'BB_Upper': [20] * 201,
        'ATR': [1] * 201,
        'SMA_20_Vol': [1000] * 201,
        'ADX': [20] * 201,
        'close': [10] * 201, # price <= BB_lower * 1.01 (10 <= 10.1)
        'volume': [2000] * 201 # vol > 1500
    })
    result = analyze_market(df)
    assert result.action == "BUY"
    assert result.strategy_used == "SIDEWAYS_RSI_BB"

def test_execute_trend_strategy_buy():
    prev = pd.Series({'MACD': 0, 'MACD_Signal': 1})
    latest = pd.Series({'MACD': 2, 'MACD_Signal': 1, 'SMA_200': 10, 'RSI': 50, 'volume': 2000, 'SMA_20_Vol': 1000})
    price = 15
    atr = 2
    result = execute_trend_strategy(latest, prev, price, atr)
    assert result.action == "BUY"
    assert result.stop_loss == 15 - (2 * 1.5)
    assert result.take_profit == 15 + (2 * 2.5)
    assert result.time_in_trade == 24

def test_execute_trend_strategy_sell():
    prev = pd.Series({'MACD': 2, 'MACD_Signal': 1})
    latest = pd.Series({'MACD': 0, 'MACD_Signal': 1, 'SMA_200': 10, 'RSI': 50, 'volume': 1000, 'SMA_20_Vol': 1000})
    price = 15
    atr = 2
    result = execute_trend_strategy(latest, prev, price, atr)
    assert result.action == "SELL"

def test_execute_trend_strategy_hold():
    prev = pd.Series({'MACD': 2, 'MACD_Signal': 1})
    latest = pd.Series({'MACD': 3, 'MACD_Signal': 1, 'SMA_200': 10, 'RSI': 50, 'volume': 1000, 'SMA_20_Vol': 1000})
    price = 15
    atr = 2
    result = execute_trend_strategy(latest, prev, price, atr)
    assert result.action == "HOLD"

def test_execute_sideways_strategy_buy():
    prev = pd.Series({'RSI': 20})
    latest = pd.Series({'RSI': 35, 'BB_Lower': 10, 'BB_Upper': 20, 'volume': 2000, 'SMA_20_Vol': 1000})
    price = 10
    atr = 2
    result = execute_sideways_strategy(latest, prev, price, atr)
    assert result.action == "BUY"
    assert result.stop_loss == 10 - (2 * 1.5)
    assert result.take_profit == 10 + (2 * 2.5)
    assert result.time_in_trade == 10

def test_execute_sideways_strategy_sell_condition_1():
    # RSI crosses back BELOW 70 (Reversal confirmation) AND price is near upper BB
    prev = pd.Series({'RSI': 75})
    latest = pd.Series({'RSI': 65, 'BB_Lower': 10, 'BB_Upper': 20, 'volume': 1000, 'SMA_20_Vol': 1000})
    price = 19.9  # >= 20 * 0.99 = 19.8
    atr = 2
    result = execute_sideways_strategy(latest, prev, price, atr)
    assert result.action == "SELL"

def test_execute_sideways_strategy_sell_condition_2():
    # price >= bb_upper
    prev = pd.Series({'RSI': 50})
    latest = pd.Series({'RSI': 50, 'BB_Lower': 10, 'BB_Upper': 20, 'volume': 1000, 'SMA_20_Vol': 1000})
    price = 21
    atr = 2
    result = execute_sideways_strategy(latest, prev, price, atr)
    assert result.action == "SELL"

def test_execute_sideways_strategy_hold():
    prev = pd.Series({'RSI': 50})
    latest = pd.Series({'RSI': 50, 'BB_Lower': 10, 'BB_Upper': 20, 'volume': 1000, 'SMA_20_Vol': 1000})
    price = 15
    atr = 2
    result = execute_sideways_strategy(latest, prev, price, atr)
    assert result.action == "HOLD"
