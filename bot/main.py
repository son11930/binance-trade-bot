import time
import threading

from .config import SYMBOLS
from .state import StateManager
from .database import setup_logging
from .logger import log_msg
from .binance_client import get_historical_klines, twm
from .news_worker import news_updater_loop
from .websocket_manager import WebSocketManager
from .webhook_notifier import update_bot_state
from .risk_manager import calculate_pnl

setup_logging()

def main():
    log_msg("INFO", "Starting Multi-Coin MACD Trading Bot with WebSockets...")
    
    # Initialize State
    state_manager = StateManager()
    state_manager.sync_state_with_binance(calculate_pnl)
    
    # Fetch initial history
    log_msg("INFO", "Fetching initial 15m history...")
    for sym in SYMBOLS:
        klines = get_historical_klines(sym, "15m", limit=250)
        state_manager.set_kline_buffer(sym, klines)
        
    # Start background threads
    threading.Thread(target=news_updater_loop, args=(state_manager,), daemon=True).start()
    
    # Initialize WebSocket Manager
    ws_manager = WebSocketManager(state_manager)
    
    # Subscribe to streams
    for sym in SYMBOLS:
        twm.start_symbol_ticker_socket(callback=ws_manager.process_ticker_message, symbol=sym)
        twm.start_kline_socket(callback=ws_manager.process_kline_message, symbol=sym, interval='15m')
        
    log_msg("INFO", "WebSocket streams active. Waiting for candle closes...")
    update_bot_state(state_manager, "Waiting for next candle close...", symbol="All")
    
    try:
        while True:
            time.sleep(60)
            update_bot_state(state_manager, "Monitoring markets via WebSockets...", symbol="All")
    except KeyboardInterrupt:
        twm.stop()
        log_msg("INFO", "Bot stopped by user.")

if __name__ == "__main__":
    main()
