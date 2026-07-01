import time
from .logger import log_msg
import concurrent.futures
from .config import SYMBOLS
from .state import StateManager
from .news_client import fetch_crypto_news
from .binance_client_data import (
    fetch_funding_rate,
    fetch_long_short_ratio,
    fetch_liquidations,
    fetch_order_book_walls
)

def update_symbol_data(symbol: str, state_managers: list):
    fr = fetch_funding_rate(symbol)
    lsr = fetch_long_short_ratio(symbol)
    liqs = fetch_liquidations(symbol)
    walls = fetch_order_book_walls(symbol)
    
    for sm in state_managers:
        sm.set_funding_rate(symbol, fr)
        sm.set_long_short_ratio(symbol, lsr)
        sm.set_liquidations(symbol, liqs)
        sm.set_order_book(symbol, walls)

def market_context_updater_loop(state_managers):
    if not isinstance(state_managers, (list, tuple)):
        state_managers = [state_managers]
    log_msg("INFO", "Starting Market Context Worker...")
    
    UPDATE_NEWS_INTERVAL = 12 # 12 * 300s = 3600s (1 hour)
    iteration = 0
    
    while True:
        try:
            if iteration % UPDATE_NEWS_INTERVAL == 0:
                news = fetch_crypto_news(5)
                for sm in state_managers:
                    sm.latest_news = news
            
            # Use ThreadPoolExecutor to fetch symbol data concurrently
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(update_symbol_data, symbol, state_managers) for symbol in SYMBOLS]
                concurrent.futures.wait(futures)
                
            iteration += 1
            time.sleep(300)  # Update every 5 minutes
        except Exception as e:
            log_msg("ERROR", f"Error in market_context_updater_loop: {e}")
            time.sleep(60)
