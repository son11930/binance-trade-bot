import time
import pytest
from unittest.mock import MagicMock
from bot.websocket_manager import WebSocketManager
from bot.state import StateManager

def test_websocket_manager_last_message_time_init():
    sm = MagicMock(spec=StateManager)
    before = time.time()
    wsm = WebSocketManager(sm, market_type='spot')
    after = time.time()
    assert hasattr(wsm, 'last_message_time')
    assert before <= wsm.last_message_time <= after

def test_websocket_manager_last_message_time_ticker(monkeypatch):
    sm = MagicMock(spec=StateManager)
    wsm = WebSocketManager(sm, market_type='spot')
    
    wsm.last_message_time = 1000.0
    monkeypatch.setattr(time, "time", lambda: 2000.0)
    msg = {"e": "24hrTicker", "s": "BTCUSDT", "c": "50000.0"}
    wsm.process_ticker_message(msg)
    
    assert wsm.last_message_time == 2000.0

def test_websocket_manager_last_message_time_kline(monkeypatch):
    sm = MagicMock(spec=StateManager)
    mock_state = MagicMock()
    mock_state.position = 0.0
    sm.get_state.return_value = mock_state
    
    wsm = WebSocketManager(sm, market_type='spot')
    wsm.update_kline_buffer = MagicMock(return_value=MagicMock())
    
    wsm.last_message_time = 1000.0
    monkeypatch.setattr(time, "time", lambda: 3000.0)
    
    msg = {
        "e": "kline",
        "s": "BTCUSDT",
        "k": {
            "t": 1600000000000,
            "o": "50000.0",
            "h": "51000.0",
            "l": "49000.0",
            "c": "50500.0",
            "v": "100.0",
            "x": False
        }
    }
    wsm.process_kline_message(msg)
    assert wsm.last_message_time == 3000.0
