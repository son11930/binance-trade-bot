import requests
import time
import logging

def fetch_funding_rate(symbol: str) -> float:
    try:
        url = "https://fapi.binance.com/fapi/v1/premiumIndex"
        response = requests.get(url, params={"symbol": symbol}, timeout=10)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, dict):
            return float(data.get("lastFundingRate", 0.0))
        return 0.0
    except Exception as e:
        logging.error(f"Error fetching funding rate for {symbol}: {e}")
        return 0.0

def fetch_long_short_ratio(symbol: str) -> float:
    try:
        url = "https://fapi.binance.com/futures/data/globalLongShortAccountRatio"
        response = requests.get(url, params={"symbol": symbol, "period": "15m"}, timeout=10)
        response.raise_for_status()
        data = response.json()
        if isinstance(data, list) and len(data) > 0:
            return float(data[-1].get("longShortRatio", 1.0))
        return 1.0
    except Exception as e:
        logging.error(f"Error fetching long/short ratio for {symbol}: {e}")
        return 1.0

def fetch_liquidations(symbol: str) -> dict:
    try:
        url = "https://fapi.binance.com/fapi/v1/allForceOrders"
        response = requests.get(url, params={"symbol": symbol, "limit": 100}, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not isinstance(data, list):
            logging.error(f"Invalid liquidations data format for {symbol}: expected list, got {type(data)}")
            return {"long_liq_usd": 0.0, "short_liq_usd": 0.0}
            
        long_liq = 0.0
        short_liq = 0.0
        
        current_time = time.time() * 1000
        for order in data:
            if not isinstance(order, dict):
                continue
            if current_time - order.get("time", 0) > 3600000:
                continue
            qty = float(order.get("executedQty", 0.0))
            price = float(order.get("averagePrice", 0.0))
            usd_value = qty * price
            if order.get("side") == "SELL":
                long_liq += usd_value
            else:
                short_liq += usd_value
        return {"long_liq_usd": round(long_liq, 2), "short_liq_usd": round(short_liq, 2)}
    except Exception as e:
        logging.error(f"Error fetching liquidations for {symbol}: {e}")
        return {"long_liq_usd": 0.0, "short_liq_usd": 0.0}

def fetch_order_book_walls(symbol: str) -> dict:
    try:
        url = "https://fapi.binance.com/fapi/v1/depth"
        response = requests.get(url, params={"symbol": symbol, "limit": 100}, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if not isinstance(data, dict):
            logging.error(f"Invalid depth data format for {symbol}: expected dict, got {type(data)}")
            return {"bid_volume": 0.0, "ask_volume": 0.0, "wall_type": "NONE"}
            
        bids = data.get("bids", [])
        asks = data.get("asks", [])
        
        if not bids or not asks:
            return {"bid_volume": 0.0, "ask_volume": 0.0, "wall_type": "NONE"}
            
        current_price = float(bids[0][0])
        price_range = current_price * 0.015
        
        bid_vol = sum(float(b[1]) for b in bids if float(b[0]) >= current_price - price_range)
        ask_vol = sum(float(a[1]) for a in asks if float(a[0]) <= current_price + price_range)
        
        wall_type = "NONE"
        if bid_vol > ask_vol * 3.0:
            wall_type = "BULLISH_WALL"
        elif ask_vol > bid_vol * 3.0:
            wall_type = "BEARISH_WALL"
            
        return {"bid_volume": round(bid_vol, 2), "ask_volume": round(ask_vol, 2), "wall_type": wall_type}
    except Exception as e:
        logging.error(f"Error fetching order book for {symbol}: {e}")
        return {"bid_volume": 0.0, "ask_volume": 0.0, "wall_type": "NONE"}
