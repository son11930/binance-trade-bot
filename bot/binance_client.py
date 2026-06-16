import os
import math
import pandas as pd
import time
from binance.client import Client
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET
from binance import ThreadedWebsocketManager
from binance.exceptions import BinanceAPIException
from dotenv import load_dotenv

from .database import LogRepository, sanitize_text

def log_msg(level: str, msg: str):
    safe_msg = sanitize_text(msg)
    print(safe_msg)
    LogRepository.log_event(level, safe_msg)

load_dotenv()

API_KEY = os.getenv("BINANCE_API_KEY")
SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")

client = Client(API_KEY, SECRET_KEY)
twm = ThreadedWebsocketManager(api_key=API_KEY, api_secret=SECRET_KEY)
twm.start()

def get_historical_klines(symbol: str, interval: str, limit: int = 100) -> pd.DataFrame:
    """
    Fetch historical klines and return as a pandas DataFrame.
    """
    klines = client.get_klines(symbol=symbol, interval=interval, limit=limit)
    df = pd.DataFrame(klines, columns=[
        'timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time',
        'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume',
        'taker_buy_quote_asset_volume', 'ignore'
    ])
    df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
    df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
    return df

def get_current_price(symbol: str) -> float:
    ticker = client.get_symbol_ticker(symbol=symbol)
    return float(ticker['price'])

def analyze_order_book_walls(symbol: str, depth: int = 50) -> dict:
    """
    Fetches the order book and finds the largest Bid and Ask walls within the given depth.
    Returns a dict with 'largest_bid_price', 'largest_bid_qty', 'largest_ask_price', 'largest_ask_qty'
    """
    try:
        order_book = client.get_order_book(symbol=symbol, limit=depth)
        
        bids = order_book['bids'] # [price, qty]
        asks = order_book['asks']
        
        total_bid_qty = sum(float(x[1]) for x in bids) if bids else 0.0
        total_ask_qty = sum(float(x[1]) for x in asks) if asks else 0.0
        
        largest_bid = max(bids, key=lambda x: float(x[1])) if bids else [0, 0]
        largest_ask = max(asks, key=lambda x: float(x[1])) if asks else [0, 0]
        
        return {
            "largest_bid_price": float(largest_bid[0]),
            "largest_bid_qty": float(largest_bid[1]),
            "total_bid_qty": total_bid_qty,
            "largest_ask_price": float(largest_ask[0]),
            "largest_ask_qty": float(largest_ask[1]),
            "total_ask_qty": total_ask_qty
        }
    except Exception as e:
        log_msg("ERROR", f"Error fetching order book for {symbol}: {e}")
        return {
            "largest_bid_price": 0.0, "largest_bid_qty": 0.0,
            "largest_ask_price": 0.0, "largest_ask_qty": 0.0
        }

def get_live_asset_balance(asset: str) -> float | None:
    """
    Fetch actual balance from Binance Spot wallet.
    Returns None if the API fails, preventing false 'manual sell' triggers.
    """
    try:
        balance = client.get_asset_balance(asset=asset)
        return float(balance['free']) if balance else 0.0
    except Exception as e:
        log_msg("ERROR", f"Error fetching balance for {asset}: {e}")
        return None

STEP_SIZE_CACHE = {}

def get_step_size(symbol: str) -> float:
    if symbol in STEP_SIZE_CACHE:
        return STEP_SIZE_CACHE[symbol]
    try:
        info = client.get_symbol_info(symbol)
        for f in info['filters']:
            if f['filterType'] == 'LOT_SIZE':
                step_size = float(f['stepSize'])
                STEP_SIZE_CACHE[symbol] = step_size
                return step_size
    except Exception as e:
        log_msg("ERROR", f"Error fetching step size for {symbol}: {e}")
    return 0.00001 # safe fallback

from decimal import Decimal, ROUND_DOWN

def round_step_size(quantity: float, step_size: float) -> float:
    try:
        dec_qty = Decimal(str(quantity))
        dec_step = Decimal(str(step_size))
        # Floor division ensures we round down to nearest multiple of step_size
        rounded = (dec_qty // dec_step) * dec_step
        return float(rounded)
    except Exception as e:
        log_msg("ERROR", f"Error in round_step_size: {e}")
        # Fallback to math
        precision = int(round(-math.log(step_size, 10), 0))
        return math.floor(quantity * (10**precision)) / (10**precision)

def place_market_order(symbol: str, side: str, quantity: float, is_paper: bool = True):
    """
    Places a market order. If is_paper is True, it simulates the execution.
    side: 'BUY' or 'SELL'
    """
    if is_paper:
        price = get_current_price(symbol)
        log_msg("INFO", f"[PAPER TRADE] {side} {quantity} of {symbol} at approx {price}")
        return {
            "status": "FILLED", 
            "price": price, 
            "executedQty": quantity, 
            "side": side, 
            "symbol": symbol, 
            "type": "MARKET",
            "parsed_avg_price": price,
            "parsed_exec_qty": quantity,
            "parsed_commission": 0.0,
            "parsed_commission_asset": "USDT"
        }
    
    # Live execution
    binance_side = SIDE_BUY if side.upper() == 'BUY' else SIDE_SELL
    step_size = get_step_size(symbol)
    rounded_quantity = round_step_size(quantity, step_size)
    
    order = client.create_order(
        symbol=symbol,
        side=binance_side,
        type=ORDER_TYPE_MARKET,
        quantity=rounded_quantity
    )

    fills = order.get('fills', [])
    total_qty = 0.0
    total_quote = 0.0
    total_commission = 0.0
    commission_asset = None
    
    for fill in fills:
        p = float(fill['price'])
        q = float(fill['qty'])
        c = float(fill['commission'])
        ca = fill['commissionAsset']
        
        total_qty += q
        total_quote += p * q
        total_commission += c
        if not commission_asset:
            commission_asset = ca
            
    avg_price = total_quote / total_qty if total_qty > 0 else 0.0
    if avg_price == 0.0 and 'price' in order:
        avg_price = float(order['price'])
        
    exec_qty = total_qty if total_qty > 0 else float(order.get('executedQty', rounded_quantity))
    
    return {
        **order,
        "parsed_avg_price": avg_price,
        "parsed_exec_qty": exec_qty,
        "parsed_commission": total_commission,
        "parsed_commission_asset": commission_asset
    }
