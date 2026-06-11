import os
import pandas as pd
from binance.client import Client
from binance.enums import *
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
        print(f"Error fetching balance for {asset}: {e}")
        return None

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
    order = client.create_order(
        symbol=symbol,
        side=binance_side,
        type=ORDER_TYPE_MARKET,
        quantity=quantity
    )
    return order
