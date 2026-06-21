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
from .config import PAPER_TRADING

def sanitize_error(e: Exception) -> str:
    err_str = str(e)
    if 'signature' in err_str.lower() or 'timestamp' in err_str.lower() or 'api-key' in err_str.lower():
        return 'API connection or authentication error (details sanitized)'
    return err_str

def log_msg(level: str, msg: str, market_type: str = 'spot'):
    safe_msg = sanitize_text(msg)
    print(f"[{market_type.upper()}] {safe_msg}")
    LogRepository.log_event(level, safe_msg, market_type=market_type)

load_dotenv()

API_KEY = os.getenv("BINANCE_API_KEY")
SECRET_KEY = os.getenv("BINANCE_API_SECRET") or os.getenv("BINANCE_SECRET_KEY")

client = Client(API_KEY, SECRET_KEY, requests_params={'timeout': 20})
# Do not initialize ThreadedWebsocketManager with API keys for public streams to prevent unnecessary exposure
twm = ThreadedWebsocketManager()
# twm.start() is now called in main.py to avoid hanging tests

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
        log_msg("ERROR", f"Error fetching order book for {symbol}: {sanitize_error(e)}")
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
        log_msg("ERROR", f"Error fetching balance for {asset}: {sanitize_error(e)}")
        return None

def get_all_spot_balances() -> dict | None:
    """
    Fetch all actual balances from Binance Spot wallet in a single API call.
    Returns a dictionary of {asset: free_balance_float} or None if API fails.
    """
    try:
        account_info = client.get_account()
        balances = {}
        for b in account_info.get('balances', []):
            free = float(b['free'])
            if free > 0:
                balances[b['asset']] = free
        return balances
    except Exception as e:
        log_msg("ERROR", f"Error fetching all spot balances: {sanitize_error(e)}")
        return None

def futures_get_live_balance(asset: str = "USDT") -> float | None:
    """
    Fetch actual balance from Binance Futures wallet.
    Returns None if the API fails.
    """
    try:
        futures_account = client.futures_account()
        for a in futures_account.get('assets', []):
            if a['asset'] == asset:
                return float(a['availableBalance'])
        return 0.0
    except Exception as e:
        log_msg("ERROR", f"Error fetching futures balance for {asset}: {sanitize_error(e)}", market_type='futures')
        return None

_spot_fees = {}
_spot_fee_ts = {}
_futures_fees = {}
_futures_fee_ts = {}

def get_cached_spot_fee(symbol: str) -> float:
    now = time.time()
    if symbol in _spot_fees and now - _spot_fee_ts.get(symbol, 0) < 3600:
        return _spot_fees[symbol]
    try:
        if PAPER_TRADING:
            return 0.001
        res = client.get_trade_fee(symbol=symbol)
        if res and len(res) > 0:
            fee = float(res[0].get('takerCommission', 0.001))
            _spot_fees[symbol] = fee
            _spot_fee_ts[symbol] = now
            return fee
    except Exception as e:
        log_msg("WARNING", f"Could not fetch spot fee for {symbol}, using default 0.001: {e}")
    return 0.001

def get_cached_futures_fee(symbol: str) -> float:
    now = time.time()
    if symbol in _futures_fees and now - _futures_fee_ts.get(symbol, 0) < 3600:
        return _futures_fees[symbol]
    try:
        if PAPER_TRADING:
            return 0.0005
        res = client.futures_commission_rate(symbol=symbol)
        if res:
            fee = float(res.get('takerCommissionRate', 0.0005))
            _futures_fees[symbol] = fee
            _futures_fee_ts[symbol] = now
            return fee
    except Exception as e:
        log_msg("WARNING", f"Could not fetch futures fee for {symbol}, using default 0.0005: {sanitize_error(e)}", market_type='futures')
    return 0.0005

STEP_SIZE_CACHE = {}
FUTURES_STEP_SIZE_CACHE = {}

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
        log_msg("ERROR", f"Error fetching step size for {symbol}: {sanitize_error(e)}")
    return 0.00001 # safe fallback

def futures_get_step_size(symbol: str) -> float:
    if symbol in FUTURES_STEP_SIZE_CACHE:
        return FUTURES_STEP_SIZE_CACHE[symbol]
    try:
        info = client.futures_exchange_info()
        for s in info['symbols']:
            if s['symbol'] == symbol:
                for f in s['filters']:
                    if f['filterType'] == 'LOT_SIZE':
                        step_size = float(f['stepSize'])
                        FUTURES_STEP_SIZE_CACHE[symbol] = step_size
                        return step_size
    except Exception as e:
        log_msg("ERROR", f"Error fetching futures step size for {symbol}: {sanitize_error(e)}")
    return 0.001 # common fallback for futures

from decimal import Decimal, ROUND_DOWN

def round_step_size(quantity: float, step_size: float) -> float:
    try:
        dec_qty = Decimal(str(quantity))
        dec_step = Decimal(str(step_size))
        # Floor division ensures we round down to nearest multiple of step_size
        rounded = (dec_qty // dec_step) * dec_step
        return float(rounded)
    except Exception as e:
        log_msg("ERROR", f"Error in round_step_size: {sanitize_error(e)}")
        # Fallback to math
        precision = int(round(-math.log(step_size, 10), 0))
        return math.floor(quantity * (10**precision)) / (10**precision)

def place_market_order(symbol: str, side: str, quantity: float, is_paper: bool = True):
    """
    Places a market order. If is_paper is True, it simulates the execution.
    side: 'BUY' or 'SELL'
    """
    if is_paper or PAPER_TRADING:
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
        quantity=f"{rounded_quantity:.10f}".rstrip('0').rstrip('.')
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

def futures_get_klines(symbol: str, interval: str, limit: int = 100) -> pd.DataFrame:
    """Fetch historical klines for USDⓈ-M Futures."""
    try:
        klines = client.futures_klines(symbol=symbol, interval=interval, limit=limit)
        df = pd.DataFrame(klines, columns=[
            'timestamp', 'open', 'high', 'low', 'close', 'volume', 'close_time',
            'quote_asset_volume', 'number_of_trades', 'taker_buy_base_asset_volume',
            'taker_buy_quote_asset_volume', 'ignore'
        ])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df[['open', 'high', 'low', 'close', 'volume']] = df[['open', 'high', 'low', 'close', 'volume']].astype(float)
        return df
    except Exception as e:
        log_msg("ERROR", f"Error fetching futures klines for {symbol}: {sanitize_error(e)}", market_type='futures')
        return pd.DataFrame()

def futures_set_leverage(symbol: str, leverage: int = 3, is_paper: bool = True):
    """Set leverage for a specific futures symbol."""
    if is_paper:
        log_msg("INFO", f"[PAPER] Skipped setting leverage to {leverage}x for {symbol}", market_type='futures')
        return
    try:
        client.futures_change_leverage(symbol=symbol, leverage=leverage)
        log_msg("INFO", f"Leverage set to {leverage}x for {symbol}", market_type='futures')
    except Exception as e:
        if isinstance(e, BinanceAPIException) and "No need to change leverage" in str(e):
            return
        log_msg("ERROR", f"Failed to set leverage for {symbol}: {sanitize_error(e)}", market_type='futures')

def futures_set_position_mode(is_paper: bool = True):
    """Set Hedge Mode (Dual-Side Position) for Futures trading."""
    if is_paper:
        log_msg("INFO", f"[PAPER] Skipped setting Hedge Mode (Dual-Side Position)", market_type='futures')
        return
    try:
        client.futures_change_position_mode(dualSidePosition="true")
        log_msg("INFO", f"Hedge Mode (Dual-Side Position) enabled for Futures", market_type='futures')
    except Exception as e:
        if isinstance(e, BinanceAPIException) and "No need to change position side" in str(e):
            return
        log_msg("ERROR", f"Failed to set Hedge Mode for Futures: {sanitize_error(e)}", market_type='futures')

def futures_set_margin_type(symbol: str, margin_type: str = "ISOLATED", is_paper: bool = True):
    """Set margin type for a specific futures symbol (ISOLATED or CROSSED)."""
    if is_paper:
        log_msg("INFO", f"[PAPER] Skipped setting margin type to {margin_type} for {symbol}", market_type='futures')
        return
    try:
        client.futures_change_margin_type(symbol=symbol, marginType=margin_type)
        log_msg("INFO", f"Margin type set to {margin_type} for {symbol}", market_type='futures')
    except Exception as e:
        err_str = str(e)
        if isinstance(e, BinanceAPIException) and ("No need to change margin type" in err_str or "-4047" in err_str):
            return
        log_msg("ERROR", f"Failed to set margin type for {symbol}: {sanitize_error(e)}", market_type='futures')

def futures_get_current_price(symbol: str) -> float:
    try:
        ticker = client.futures_symbol_ticker(symbol=symbol)
        return float(ticker['price'])
    except Exception as e:
        log_msg("ERROR", f"Failed to get futures price for {symbol}: {sanitize_error(e)}")
        return 0.0

def futures_place_order(symbol: str, side: str, positionSide: str, quantity: float, is_paper: bool = True):
    """
    Places a Futures market order.
    side: 'BUY' or 'SELL'
    positionSide: 'LONG' or 'SHORT'
    """
    if is_paper or PAPER_TRADING:
        price = futures_get_current_price(symbol)
        log_msg("INFO", f"[FUTURES PAPER] {side} {positionSide} {quantity} of {symbol} at approx {price}")
        return {
            "status": "FILLED",
            "price": price,
            "executedQty": quantity,
            "side": side,
            "positionSide": positionSide,
            "symbol": symbol,
            "type": "MARKET",
            "parsed_avg_price": price,
            "parsed_exec_qty": quantity,
            "parsed_commission": 0.0,
            "parsed_commission_asset": "USDT"
        }
    
    # Live execution
    binance_side = SIDE_BUY if side.upper() == 'BUY' else SIDE_SELL
    step_size = futures_get_step_size(symbol)
    rounded_quantity = round_step_size(quantity, step_size)
    
    if rounded_quantity <= 0:
        raise Exception("APIError(code=-4003): Quantity less than or equal to zero after rounding.")
        
    try:
        order = client.futures_create_order(
            symbol=symbol,
            side=binance_side,
            positionSide=positionSide,
            type=ORDER_TYPE_MARKET,
            quantity=rounded_quantity
        )
        avg_price = float(order.get('avgPrice', 0.0))
        exec_qty = float(order.get('executedQty', 0.0))
        commission = 0.0
        commission_asset = "USDT"
        
        # Market orders might not have avgPrice populated yet, or we need exact commission
        if exec_qty > 0:
            try:
                # Query the exact trades for this order to get commission and exact price
                order_id = order.get('orderId')
                if order_id:
                    # Small delay to ensure trades are registered
                    import time
                    time.sleep(0.5)
                    trades = client.futures_account_trades(symbol=symbol, orderId=order_id)
                    if trades:
                        commission = sum(float(t['commission']) for t in trades)
                        # Commission asset is usually the same for all fills in USDT-M futures
                        commission_asset = trades[0]['commissionAsset']
                        
                        # Recalculate exact avg price from fills if Binance didn't provide it
                        if avg_price == 0.0:
                            total_cost = sum(float(t['price']) * float(t['qty']) for t in trades)
                            avg_price = total_cost / exec_qty
            except Exception as e:
                log_msg("WARNING", f"Could not fetch exact commission for futures order {order.get('orderId')}: {e}", market_type="futures")
                
        if avg_price == 0.0:
            avg_price = float(order.get('price', 0.0))
        if avg_price == 0.0:
            avg_price = futures_get_current_price(symbol)
            
        if exec_qty == 0.0:
            exec_qty = float(order.get('origQty', rounded_quantity))
        
        return {
            **order,
            "parsed_avg_price": avg_price,
            "parsed_exec_qty": exec_qty,
            "parsed_commission": commission,
            "parsed_commission_asset": commission_asset
        }
    except Exception as e:
        log_msg("ERROR", f"Failed to execute futures trade for {symbol}: {sanitize_error(e)}", market_type="futures")
        raise Exception(f"Binance API Execution Error: {sanitize_error(e)}")
from dataclasses import replace
import logging
from bot.database import sanitize_text

def futures_cancel_all_orders(symbol: str):
    """Cancel all open orders (including TP/SL) for a futures symbol."""
    try:
        if PAPER_TRADING:
            log_msg("INFO", f"[FUTURES PAPER] Cancelled all orders for {symbol}")
            return True
            
        client.futures_cancel_all_open_orders(symbol=symbol)
        log_msg("INFO", f"Cancelled all open orders for {symbol}", market_type='futures')
        return True
    except Exception as e:
        log_msg("ERROR", f"Failed to cancel orders for {symbol}: {sanitize_error(e)}", market_type='futures')
        return False

def futures_set_tp_sl(symbol: str, positionSide: str, tp_price: float, sl_price: float):
    """Set Take Profit and Stop Loss for a specific position using closePosition=True"""
    if PAPER_TRADING:
        log_msg("INFO", f"[FUTURES PAPER] Set TP={tp_price} SL={sl_price} for {positionSide} {symbol}")
        return True
        
    # For a LONG position, to close it we SELL. For a SHORT position, we BUY.
    close_side = SIDE_SELL if positionSide == "LONG" else SIDE_BUY
    
    try:
        # Cancel existing orders first
        futures_cancel_all_orders(symbol)
        
        # Place Take Profit
        if tp_price > 0:
            client.futures_create_order(
                symbol=symbol,
                side=close_side,
                positionSide=positionSide,
                type='TAKE_PROFIT_MARKET',
                stopPrice=str(round(tp_price, 4)),
                closePosition=True
            )
            
        # Place Stop Loss
        if sl_price > 0:
            client.futures_create_order(
                symbol=symbol,
                side=close_side,
                positionSide=positionSide,
                type='STOP_MARKET',
                stopPrice=str(round(sl_price, 4)),
                closePosition=True
            )
        return True
    except Exception as e:
        log_msg("ERROR", f"Failed to set TP/SL for {symbol}: {sanitize_error(e)}", market_type='futures')
        return False


def futures_get_position(symbol: str, positionSide: str = None) -> dict | None:
    """Fetch position details for a specific futures symbol."""
    from bot.binance_client import client
    try:
        positions = client.futures_position_information(symbol=symbol)
        if positions:
            if positionSide:
                for pos in positions:
                    if pos.get("positionSide") == positionSide:
                        return pos
                for pos in positions:
                    if float(pos.get("positionAmt", "0")) != 0:
                        return pos
                return positions[0]
            else:
                for pos in positions:
                    if float(pos.get("positionAmt", "0")) != 0:
                        return pos
                return positions[0]
        
        # If API returns empty list, it means no position exists
        return {"positionAmt": "0", "entryPrice": "0", "positionSide": positionSide or "LONG"}
    except Exception as e:
        log_msg("ERROR", f"Error fetching futures position for {symbol}: {sanitize_error(e)}", market_type='futures')
        return None

def futures_account_balance(asset: str = "USDT") -> float | None:
    """Fetch live available balance for the Futures wallet."""
    try:
        balances = client.futures_account_balance()
        for b in balances:
            if b['asset'] == asset:
                return float(b['availableBalance']) # available for trading
        return 0.0
    except Exception as e:
        log_msg("ERROR", f"Error fetching futures balance for {asset}: {sanitize_error(e)}")
        return None
