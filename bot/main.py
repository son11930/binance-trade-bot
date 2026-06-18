import time
import threading

from .config import SYMBOLS, PAPER_TRADING, FUTURES_LEVERAGE, FUTURES_MARGIN_TYPE
from .state import StateManager
from .database import setup_logging
from .logger import log_msg
from .binance_client import get_historical_klines, futures_get_klines, twm, futures_set_leverage, futures_set_margin_type, futures_set_position_mode
from .news_worker import news_updater_loop
from .websocket_manager import WebSocketManager
from .webhook_notifier import update_bot_state
from .risk_manager import calculate_pnl

setup_logging()

def main():
    log_msg("INFO", "Starting Multi-Coin Dual-Engine Bot (Spot & Futures)...")
    
    # Configure Futures settings on real account
    if not PAPER_TRADING:
        log_msg("INFO", f"Setting up Futures Margin ({FUTURES_MARGIN_TYPE}) and Leverage ({FUTURES_LEVERAGE}x)...", market_type='futures')
        futures_set_position_mode(is_paper=False)
        for sym in SYMBOLS:
            futures_set_margin_type(sym, FUTURES_MARGIN_TYPE, is_paper=False)
            futures_set_leverage(sym, FUTURES_LEVERAGE, is_paper=False)
            
    # Initialize Spot State
    state_manager_spot = StateManager()
    state_manager_spot.sync_state_with_binance(calculate_pnl)
    
    # Initialize Futures State
    state_manager_futures = StateManager()
    
    # Fetch initial history for Spot
    log_msg("INFO", "Fetching initial Spot 15m history...")
    for sym in SYMBOLS:
        klines = get_historical_klines(sym, "15m", limit=250)
        state_manager_spot.set_kline_buffer(sym, klines)
        
    # Fetch initial history for Futures
    log_msg("INFO", "Fetching initial Futures 5m history...", market_type='futures')
    for sym in SYMBOLS:
        f_klines = futures_get_klines(sym, "5m", limit=250)
        state_manager_futures.set_kline_buffer(sym, f_klines)
        
    # Start background threads (Shared news)
    threading.Thread(target=news_updater_loop, args=(state_manager_spot,), daemon=True).start()
    
    # Initialize WebSocket Managers
    ws_manager_spot = WebSocketManager(state_manager_spot, market_type='spot')
    ws_manager_futures = WebSocketManager(state_manager_futures, market_type='futures')
    
    # Start ThreadedWebsocketManager
    twm.start()
    
    # Subscribe to streams
    for sym in SYMBOLS:
        # Spot Streams
        twm.start_symbol_ticker_socket(callback=ws_manager_spot.process_ticker_message, symbol=sym)
        twm.start_kline_socket(callback=ws_manager_spot.process_kline_message, symbol=sym, interval='15m')
        
        # Futures Streams
        try:
            if hasattr(twm, 'start_kline_futures_socket'):
                twm.start_kline_futures_socket(callback=ws_manager_futures.process_kline_message, symbol=sym, interval='5m')
            else:
                log_msg("ERROR", "python-binance ThreadedWebsocketManager does not support start_kline_futures_socket", market_type='futures')
        except Exception as e:
            log_msg("ERROR", f"Failed to start futures kline socket for {sym}: {e}", market_type='futures')
        
    log_msg("INFO", "WebSocket streams active. Waiting for candle closes...")
    update_bot_state(state_manager_spot, "Waiting for next candle close...", symbol="All")
    
    try:
        while True:
            time.sleep(60)
            update_bot_state(state_manager_spot, "Monitoring Spot markets...", symbol="All")
    except KeyboardInterrupt:
        twm.stop()
        log_msg("INFO", "Bot stopped by user.")

if __name__ == "__main__":
    main()
