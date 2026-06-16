import pytest
from unittest.mock import patch, MagicMock
from bot.trade_executor import execute_trade
from bot.state import StateManager

@pytest.fixture
def state_manager():
    sm = StateManager()
    mock_state = MagicMock()
    mock_state.buy_price = 45000.0
    sm.get_state = MagicMock(return_value=mock_state)
    return sm

@patch("bot.trade_executor.get_live_asset_balance")
@patch("bot.trade_executor.place_market_order")
@patch("bot.trade_executor.TradeRepository.create_trade")
@patch("bot.trade_executor.log_msg")
def test_execute_trade_sell_actual_balance_less_than_qty(mock_log, mock_create_trade, mock_place_order, mock_get_balance, state_manager):
    # Scenario: actual_balance < qty (e.g. fee deduction simulation)
    symbol = "BTCUSDT"
    side = "SELL"
    original_qty = 1.0
    actual_balance = 0.99  # Less than original_qty
    price = 50000.0
    is_paper = False
    
    mock_get_balance.return_value = actual_balance
    
    # Mock place_market_order response
    mock_place_order.return_value = {
        'parsed_avg_price': price,
        'parsed_exec_qty': actual_balance,
        'parsed_commission': 0.0,
        'parsed_commission_asset': 'USDT'
    }
    
    # Execute trade
    execute_trade(state_manager, symbol, side, original_qty, price, reason="Test reason", is_paper=is_paper)
    
    # Verify get_live_asset_balance called with base asset
    mock_get_balance.assert_called_once_with("BTC")
    
    # Verify place_market_order was called with actual_balance
    mock_place_order.assert_called_once_with(symbol, side, actual_balance, is_paper=is_paper)
    
    # Check log message for adjusting
    mock_log.assert_any_call("INFO", f"📉 Adjusted SELL qty for {symbol} from {original_qty} to {actual_balance} to prevent -2010 Insufficient Balance error.")

@patch("bot.trade_executor.get_live_asset_balance")
@patch("bot.trade_executor.place_market_order")
@patch("bot.trade_executor.TradeRepository.create_trade")
@patch("bot.trade_executor.log_msg")
def test_execute_trade_sell_actual_balance_greater_than_qty(mock_log, mock_create_trade, mock_place_order, mock_get_balance, state_manager):
    # Scenario: actual_balance > qty (e.g. manual holdings simulation)
    symbol = "BTCUSDT"
    side = "SELL"
    original_qty = 1.0
    actual_balance = 1.5  # Greater than original_qty
    price = 50000.0
    is_paper = False
    
    mock_get_balance.return_value = actual_balance
    
    # Mock place_market_order response
    mock_place_order.return_value = {
        'parsed_avg_price': price,
        'parsed_exec_qty': original_qty,
        'parsed_commission': 0.0,
        'parsed_commission_asset': 'USDT'
    }
    
    # Execute trade
    execute_trade(state_manager, symbol, side, original_qty, price, reason="Test reason", is_paper=is_paper)
    
    # Verify get_live_asset_balance called with base asset
    mock_get_balance.assert_called_once_with("BTC")
    
    # Verify place_market_order was called with original_qty (NOT actual_balance)
    mock_place_order.assert_called_once_with(symbol, side, original_qty, is_paper=is_paper)
    
    # Make sure we didn't log the adjustment message
    for call_args in mock_log.call_args_list:
        args, _ = call_args
        assert f"Adjusted SELL qty for {symbol}" not in args[1]

@patch("bot.trade_executor.get_live_asset_balance")
@patch("bot.trade_executor.place_market_order")
@patch("bot.trade_executor.TradeRepository.create_trade")
@patch("bot.trade_executor.log_msg")
def test_execute_trade_sell_paper_trade(mock_log, mock_create_trade, mock_place_order, mock_get_balance, state_manager):
    # Scenario: is_paper = True, logic should not trigger
    symbol = "BTCUSDT"
    side = "SELL"
    original_qty = 1.0
    price = 50000.0
    is_paper = True
    
    # Mock place_market_order response
    mock_place_order.return_value = {
        'parsed_avg_price': price,
        'parsed_exec_qty': original_qty,
        'parsed_commission': 0.0,
        'parsed_commission_asset': 'USDT'
    }
    
    execute_trade(state_manager, symbol, side, original_qty, price, reason="Test reason", is_paper=is_paper)
    
    # get_live_asset_balance should not be called
    mock_get_balance.assert_not_called()
    mock_place_order.assert_called_once_with(symbol, side, original_qty, is_paper=is_paper)

@patch("bot.trade_executor.get_live_asset_balance")
@patch("bot.trade_executor.place_market_order")
@patch("bot.trade_executor.TradeRepository.create_trade")
@patch("bot.trade_executor.log_msg")
def test_execute_trade_buy_order(mock_log, mock_create_trade, mock_place_order, mock_get_balance, state_manager):
    # Scenario: side = BUY, logic should not trigger
    symbol = "BTCUSDT"
    side = "BUY"
    original_qty = 1.0
    price = 50000.0
    is_paper = False
    
    # Mock place_market_order response
    mock_place_order.return_value = {
        'parsed_avg_price': price,
        'parsed_exec_qty': original_qty,
        'parsed_commission': 0.0,
        'parsed_commission_asset': 'USDT'
    }
    
    execute_trade(state_manager, symbol, side, original_qty, price, reason="Test reason", is_paper=is_paper)
    
    # get_live_asset_balance should not be called
    mock_get_balance.assert_not_called()
    mock_place_order.assert_called_once_with(symbol, side, original_qty, is_paper=is_paper)

@patch("bot.trade_executor.get_live_asset_balance")
@patch("bot.trade_executor.place_market_order")
@patch("bot.trade_executor.TradeRepository.create_trade")
@patch("bot.trade_executor.log_msg")
def test_execute_trade_sell_balance_none(mock_log, mock_create_trade, mock_place_order, mock_get_balance, state_manager):
    # Scenario: get_live_asset_balance returns None
    symbol = "BTCUSDT"
    side = "SELL"
    original_qty = 1.0
    price = 50000.0
    is_paper = False
    
    mock_get_balance.return_value = None
    
    # Mock place_market_order response
    mock_place_order.return_value = {
        'parsed_avg_price': price,
        'parsed_exec_qty': original_qty,
        'parsed_commission': 0.0,
        'parsed_commission_asset': 'USDT'
    }
    
    execute_trade(state_manager, symbol, side, original_qty, price, reason="Test reason", is_paper=is_paper)
    
    mock_get_balance.assert_called_once_with("BTC")
    mock_place_order.assert_called_once_with(symbol, side, original_qty, is_paper=is_paper)
