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
    expected_cols = ['SMA_200', 'SMA_50', 'MACD', 'MACD_Signal', 'RSI', 'BB_Upper', 'BB_Lower', 'BB_Mid', 'ADX', 'ATR', 'SMA_20_Vol', 'SMA_ADX_3', 'SMA_ADX_5', 'MACD_Histogram', 'Bollinger_Band_Width', 'Distance_to_SMA_200']
    for col in expected_cols:
        assert col in result.columns

def test_detect_regime_less_than_14():
    df = pd.DataFrame({'ADX': range(10)})
    assert detect_regime(df) == "UNKNOWN"

def test_detect_regime_nan_adx():
    df = pd.DataFrame({'ADX': [np.nan] * 20})
    assert detect_regime(df) == "UNKNOWN"

def test_detect_regime_trending():
    df = pd.DataFrame({'ADX': [20] * 13 + [26], 'SMA_ADX_3': [20] * 13 + [25], 'SMA_ADX_5': [20] * 13 + [20]}) 
    assert detect_regime(df) == "TRENDING"

def test_detect_regime_sideways_low_adx():
    df = pd.DataFrame({'ADX': [20] * 13 + [24], 'SMA_ADX_3': [20] * 14, 'SMA_ADX_5': [20] * 14}) 
    assert detect_regime(df) == "SIDEWAYS"

def test_detect_regime_sideways_falling_adx():
    df = pd.DataFrame({'ADX': [30] * 13 + [28], 'SMA_ADX_3': [28] * 14, 'SMA_ADX_5': [30] * 14}) 
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
    df = pd.DataFrame({
        'SMA_200': [10] * 201,
        'RSI': [50] * 201,
        'MACD': [0] * 199 + [0, 2], 
        'MACD_Signal': [0] * 199 + [1, 1], 
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
        'RSI': [50] * 199 + [20, 35], 
        'MACD': [0] * 201,
        'MACD_Signal': [0] * 201,
        'BB_Lower': [10] * 201,
        'BB_Upper': [20] * 201,
        'ATR': [1] * 201,
        'SMA_20_Vol': [1000] * 201,
        'ADX': [20] * 201,
        'close': [10] * 201, 
        'volume': [500] * 201 # vol <= SMA_20_Vol
    })
    result = analyze_market(df)
    assert result.action == "BUY"
    assert result.strategy_used == "SIDEWAYS_RSI_BB"

def test_execute_trend_strategy_buy():
    df = pd.DataFrame({
        'MACD': [0, 0, 0, 2],
        'MACD_Signal': [1, 1, 1, 1]
    })
    prev = df.iloc[-2]
    latest = pd.Series({'MACD': 2, 'MACD_Signal': 1, 'SMA_200': 10, 'RSI': 50, 'volume': 2000, 'SMA_20_Vol': 1000})
    price = 15
    atr = 2
    result = execute_trend_strategy(df, latest, prev, price, atr)
    assert result.action == "BUY"
    assert result.stop_loss == 15 - (2 * 1.5)
    assert result.take_profit == 0.0
    assert result.time_in_trade == 24

def test_execute_trend_strategy_sell():
    df = pd.DataFrame({
        'MACD': [2, 2, 2, 0],
        'MACD_Signal': [1, 1, 1, 1]
    })
    prev = df.iloc[-2]
    latest = pd.Series({'MACD': 0, 'MACD_Signal': 1, 'SMA_200': 10, 'RSI': 50, 'volume': 1000, 'SMA_20_Vol': 1000})
    price = 15
    atr = 2
    result = execute_trend_strategy(df, latest, prev, price, atr)
    assert result.action == "SELL"

def test_execute_trend_strategy_hold():
    df = pd.DataFrame({
        'MACD': [2, 2, 2, 3],
        'MACD_Signal': [1, 1, 1, 1]
    })
    prev = df.iloc[-2]
    latest = pd.Series({'MACD': 3, 'MACD_Signal': 1, 'SMA_200': 10, 'RSI': 50, 'volume': 1000, 'SMA_20_Vol': 1000})
    price = 15
    atr = 2
    result = execute_trend_strategy(df, latest, prev, price, atr)
    assert result.action == "HOLD"

def test_execute_sideways_strategy_buy():
    prev = pd.Series({'RSI': 20})
    latest = pd.Series({'RSI': 35, 'BB_Lower': 10, 'BB_Upper': 20, 'volume': 500, 'SMA_20_Vol': 1000})
    price = 10
    atr = 2
    result = execute_sideways_strategy(latest, prev, price, atr)
    assert result.action == "BUY"
    assert result.stop_loss == 10 - (2 * 1.5)
    assert result.take_profit == 20
    assert result.time_in_trade == 10

def test_execute_sideways_strategy_sell_condition_1():
    prev = pd.Series({'RSI': 75})
    latest = pd.Series({'RSI': 65, 'BB_Lower': 10, 'BB_Upper': 20, 'volume': 1000, 'SMA_20_Vol': 1000})
    price = 19.9
    atr = 2
    result = execute_sideways_strategy(latest, prev, price, atr)
    assert result.action == "SELL"

def test_execute_sideways_strategy_sell_condition_2():
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
