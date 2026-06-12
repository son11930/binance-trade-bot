import os
import math
import pandas as pd
import logging
from binance.client import Client
from binance.enums import SIDE_BUY, SIDE_SELL, ORDER_TYPE_MARKET
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("BINANCE_API_KEY")
SECRET_KEY = os.getenv("BINANCE_SECRET_KEY")

client = Client(API_KEY, SECRET_KEY)

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
    for col in ['open', 'high', 'low', 'close', 'volume']:
        df[col] = df[col].astype(float)
    return df

def get_current_price(symbol: str) -> float:
    ticker = client.get_symbol_ticker(symbol=symbol)
    return float(ticker['price'])

def get_live_asset_balance(asset: str) -> float | None:
    """
    Fetch actual balance from Binance Spot wallet.
    Returns None if the API fails, preventing false 'manual sell' triggers.
    """
    try:
        balance = client.get_asset_balance(asset=asset)
        return float(balance['free']) if balance else 0.0
    except Exception as e:
        logging.exception(f"Error fetching balance for {asset}")
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
        logging.exception(f"Error fetching step size for {symbol}")
    return 0.00001 # safe fallback

def round_step_size(quantity: float, step_size: float) -> float:
    precision = int(round(-math.log(step_size, 10), 0))
    return math.floor(quantity * (10**precision)) / (10**precision)

def place_market_order(symbol: str, side: str, quantity: float, is_paper: bool = True):
    """
    Places a market order. If is_paper is True, it simulates the execution.
    side: 'BUY' or 'SELL'
    """
    if is_paper:
        price = get_current_price(symbol)
        print(f"[PAPER TRADE] {side} {quantity} of {symbol} at approx {price}")
        return {
            "status": "FILLED", 
            "price": price, 
            "executedQty": quantity, 
            "side": side, 
            "symbol": symbol, 
            "type": "MARKET"
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
    return order
