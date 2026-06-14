import time
from .ai_engine import fetch_crypto_news
from .logger import log_msg
from .state import StateManager

def news_updater_loop(state_manager: StateManager):
    while True:
        try:
            news = fetch_crypto_news(5)
            state_manager.latest_news = news
        except Exception as e:
            log_msg("ERROR", f"News fetch failed: {e}")
        time.sleep(3600) # Update news every hour
