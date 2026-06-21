import time
import requests
import traceback
from .ai_engine import fetch_crypto_news
from .logger import log_msg
from .state import StateManager
from .config import SYMBOLS

def fetch_fear_and_greed_index() -> str:
    try:
        response = requests.get("https://api.alternative.me/fng/", timeout=10)
        response.raise_for_status()
        data = response.json()
        if "data" in data and len(data["data"]) > 0:
            value = data["data"][0]["value"]
            classification = data["data"][0]["value_classification"]
            return f"{classification} ({value})"
    except Exception as e:
        log_msg("ERROR", f"Fear & Greed fetch failed: {e}")
    return "Neutral (50)"

def fetch_funding_rate(symbol: str) -> float:
    try:
        url = f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={symbol}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        return float(data.get("lastFundingRate", 0.0))
    except Exception as e:
        return 0.0

def fetch_long_short_ratio(symbol: str) -> float:
    try:
        url = f"https://fapi.binance.com/futures/data/globalLongShortAccountRatio?symbol={symbol}&period=15m"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        if len(data) > 0:
            return float(data[-1].get("longShortRatio", 1.0))
    except Exception as e:
        return 1.0

def market_context_updater_loop(*state_managers: StateManager):
    """
    Background worker that updates market context:
    1. News (Layer 1 & 2 logic implemented in fetch_crypto_news)
    2. Quantitative Metrics (Funding Rate, Long/Short Ratio, Fear & Greed)
    """
    iteration = 0
    while True:
        try:
            if iteration % 12 == 0:
                news = fetch_crypto_news(5)
                for sm in state_managers:
                    sm.latest_news = news
                    
            if iteration % 12 == 0:
                fng = fetch_fear_and_greed_index()
                for sm in state_managers:
                    sm.fear_greed_index = fng
                    
            for symbol in SYMBOLS:
                fr = fetch_funding_rate(symbol)
                lsr = fetch_long_short_ratio(symbol)
                for sm in state_managers:
                    sm.set_funding_rate(symbol, fr)
                    sm.set_long_short_ratio(symbol, lsr)
                    
            iteration += 1
            time.sleep(300)
            
        except Exception as e:
            log_msg("ERROR", f"Market Context fetch failed: {e}")
            time.sleep(60)
