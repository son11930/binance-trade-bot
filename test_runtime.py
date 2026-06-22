import sys
import traceback
try:
    import pandas as pd
    from bot.websocket_manager import WebSocketManager
    from bot.state import StateManager
    from bot.database import TradeRepository
    
    sm = StateManager()
    wm = WebSocketManager(sm, market_type='spot')
    
    df = pd.DataFrame([{
        'timestamp': pd.to_datetime('2026-06-23 00:00:00'),
        'open': 100, 'high': 110, 'low': 90, 'close': 105, 'volume': 1000
    }])
    sm.set_kline_buffer('BTCUSDT', df)
    
    msg = {
        't': pd.to_datetime('2026-06-23 00:00:00').value // 10**6, # ms
        'o': '101', 'h': '112', 'l': '89', 'c': '106', 'v': '1100'
    }
    
    wm.update_kline_buffer('BTCUSDT', msg)
    print("Websocket buffer update OK:", df.iloc[-1]['close'])
    
except Exception as e:
    print("Error during test:")
    traceback.print_exc()
