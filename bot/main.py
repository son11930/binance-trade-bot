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
    state_manager_spot = StateManager(market_type='spot')
    state_manager_spot.sync_state_with_binance(calculate_pnl)
    
    # Initialize Futures State
    state_manager_futures = StateManager(market_type='futures')
    state_manager_futures.sync_state_with_binance(calculate_pnl)
    
    # Fetch initial history for Spot
    log_msg("INFO", "Fetching initial Spot 15m history...")
    for sym in SYMBOLS:
        klines = get_historical_klines(sym, "15m", limit=250)
        state_manager_spot.set_kline_buffer(sym, klines)
        
    # Fetch initial history for Futures
    log_msg("INFO", "Fetching initial Futures 15m history...", market_type='futures')
    for sym in SYMBOLS:
        f_klines = futures_get_klines(sym, "15m", limit=250)
        state_manager_futures.set_kline_buffer(sym, f_klines)
        
    # Start background threads (Shared news)
    threading.Thread(target=news_updater_loop, args=(state_manager_spot, state_manager_futures), daemon=True).start()
    
    # Start auto-sync background thread
    def auto_sync_loop():
        import time
        while True:
            time.sleep(60) # Sync every 1 minute
            try:
                state_manager_futures.sync_state_with_binance(calculate_pnl)
                state_manager_spot.sync_state_with_binance(calculate_pnl)
            except Exception as e:
                log_msg("ERROR", f"Auto-sync failed: {e}")
                
    threading.Thread(target=auto_sync_loop, daemon=True).start()
    
    # Initialize WebSocket Managers
    ws_manager_spot = WebSocketManager(state_manager_spot, market_type='spot')
    ws_manager_futures = WebSocketManager(state_manager_futures, market_type='futures')
    
    # Start ThreadedWebsocketManager
    twm.start()
    
    # Subscribe to streams using multiplexing
    spot_streams = []
    futures_streams = []
    for sym in SYMBOLS:
        sym_lower = sym.lower()
        spot_streams.append(f"{sym_lower}@ticker")
        spot_streams.append(f"{sym_lower}@kline_15m")
        futures_streams.append(f"{sym_lower}@ticker")
        futures_streams.append(f"{sym_lower}@kline_15m")
    
    # Start Spot Multiplex Streams
    twm.start_multiplex_socket(callback=ws_manager_spot.process_ticker_message, streams=[s for s in spot_streams if 'ticker' in s])
    twm.start_multiplex_socket(callback=ws_manager_spot.process_kline_message, streams=[s for s in spot_streams if 'kline' in s])
    
    # Start Futures Multiplex Streams
    try:
        if hasattr(twm, 'start_futures_multiplex_socket'):
            twm.start_futures_multiplex_socket(callback=ws_manager_futures.process_ticker_message, streams=[s for s in futures_streams if 'ticker' in s])
            twm.start_futures_multiplex_socket(callback=ws_manager_futures.process_kline_message, streams=[s for s in futures_streams if 'kline' in s.lower()])
        else:
            log_msg("ERROR", "python-binance ThreadedWebsocketManager does not support start_futures_multiplex_socket", market_type='futures')
    except Exception as e:
        log_msg("ERROR", f"Failed to start futures multiplex socket: {e}", market_type='futures')
        
    log_msg("INFO", "WebSocket streams active. Waiting for candle closes...")
    # Initial state broadcast
    update_bot_state(state_manager_spot, "Waiting for next candle close...", symbol="All", market_type='spot')
    update_bot_state(state_manager_futures, "Waiting for next candle close...", symbol="All", market_type='futures')
    
    try:
        while True:
            time.sleep(2)
            
            if not twm.is_alive():
                log_msg("ERROR", "CRITICAL: ThreadedWebsocketManager has died. Restarting bot...")
                import sys
                import os
                os.execv(sys.executable, ['python'] + sys.argv)

            try:
                update_bot_state(state_manager_spot, "Monitoring Spot markets...", symbol="All", market_type='spot')
                update_bot_state(state_manager_futures, "Monitoring Futures markets...", symbol="All", market_type='futures')
            except Exception as e:
                log_msg("ERROR", f"Error updating bot state: {e}")
    except KeyboardInterrupt:
        twm.stop()
        log_msg("INFO", "Bot stopped by user.")

if __name__ == "__main__":
    main()
