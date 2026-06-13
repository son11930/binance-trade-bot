import os
import time
import requests
import hashlib
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

from .binance_client import get_historical_klines, place_market_order, get_current_price, get_live_asset_balance, twm
from .strategy import apply_indicators, analyze_market
from .ai_engine import fetch_crypto_news, analyze_sentiment
from .database import TradeRepository, LogRepository

load_dotenv()

SYMBOLS = ["BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT", "BNBUSDT"]
QUANTITY_USDT = float(os.getenv("TRADE_QUANTITY_USDT", "10.0"))
PAPER_TRADING = os.getenv("PAPER_TRADING", "True").lower() == "true"
COOLDOWN_MINUTES = int(os.getenv("COOLDOWN_MINUTES", "60"))
STOP_LOSS_PERCENT = float(os.getenv("STOP_LOSS_PERCENT", "2.5"))
WEBHOOK_URL = "http://127.0.0.1:8000/api/internal/broadcast"

USER = os.getenv("DASHBOARD_USER")
PASS = os.getenv("DASHBOARD_PASS")
SECRET_SALT = os.getenv("DASHBOARD_SECRET_SALT")

if not USER or not PASS or not SECRET_SALT:
    raise ValueError("CRITICAL SECURITY ERROR: DASHBOARD_USER, DASHBOARD_PASS, and DASHBOARD_SECRET_SALT must be set in .env")

AUTH_TOKEN = hashlib.sha256(f"{USER}:{PASS}:{SECRET_SALT}".encode()).hexdigest()

current_positions = {sym: 0.0 for sym in SYMBOLS}
buy_prices = {sym: 0.0 for sym in SYMBOLS}
last_trade_times = {sym: None for sym in SYMBOLS}
last_prices = {sym: 0.0 for sym in SYMBOLS}
highest_prices = {sym: 0.0 for sym in SYMBOLS}
live_usdt_balance = 0.0

def process_ticker_message(msg):
    if msg.get('e') == '24hrTicker':
        sym = msg['s']
        if sym in last_prices:
            last_prices[sym] = float(msg['c'])

# Start websocket listeners
for symbol in SYMBOLS:
    twm.start_symbol_ticker_socket(callback=process_ticker_message, symbol=symbol)

def log_msg(level: str, msg: str):
    print(msg)
    LogRepository.log_event(level, msg)

def sync_state_with_binance():
    """
    Syncs internal bot state with actual Binance Wallet.
    - Handles manual sells on the app.
    - Recovers state if the PC is restarted.
    """
    global live_usdt_balance
    if not PAPER_TRADING:
        bal = get_live_asset_balance("USDT")
        if bal is not None:
            live_usdt_balance = bal

    if PAPER_TRADING:
        # User is testing logic but paper trading relies on fake balances. 
        # In this mode, we skip API sync to avoid API errors if testing without funds.
        return
        
    for symbol in SYMBOLS:
        asset = symbol.replace("USDT", "")
        real_bal = get_live_asset_balance(asset)
        
        if real_bal is None:
            log_msg("WARNING", f"⚠️ Skipping sync for {symbol} due to API error.")
            continue
            
        current_price = last_prices[symbol] if last_prices[symbol] > 0 else get_current_price(symbol)
            
        # If value is less than $2, we consider it dust (sold)
        if real_bal * current_price < 2.0:
            if current_positions[symbol] > 0:
                log_msg("WARNING", f"⚠️ Detected manual SELL for {symbol}. Syncing state.")
                bp = buy_prices[symbol]
                qty = current_positions[symbol]
                pnl_amount = (current_price - bp) * qty if bp > 0 else None
                pnl_percent = (current_price - bp) / bp * 100.0 if bp > 0 else None
                TradeRepository.create_trade(
                    symbol, "SELL", current_price, qty, None, "Manual SELL", PAPER_TRADING,
                    0.0, "USDT", pnl_amount, pnl_percent
                )
            current_positions[symbol] = 0.0
            buy_prices[symbol] = 0.0
            highest_prices[symbol] = 0.0
        else:
            # We hold this coin
            current_positions[symbol] = real_bal
            if buy_prices[symbol] == 0.0:
                # Recover buy price from DB
                db_price = TradeRepository.get_last_buy_price(symbol)
                if db_price > 0:
                    buy_prices[symbol] = db_price
                else:
                    # Manual buy detected or missing DB
                    buy_prices[symbol] = current_price
                    log_msg("WARNING", f"⚠️ Manual BUY detected for {symbol} or DB missing. Using current price as baseline.")

def update_bot_state(status_msg, thinking=False, symbol="System"):
    positions_data = []
    for sym, pos in current_positions.items():
        if pos > 0:
            bp = buy_prices[sym]
            cp = last_prices[sym]
            pnl_amt = (cp - bp) * pos if cp > 0 else 0
            pnl_pct = ((cp - bp) / bp * 100.0) if (bp > 0 and cp > 0) else 0
            positions_data.append({
                "symbol": sym,
                "quantity": pos,
                "buy_price": bp,
                "current_price": cp,
                "pnl_amount": pnl_amt,
                "pnl_percent": pnl_pct
            })

    state = {
        "status_message": status_msg,
        "is_thinking": thinking,
        "symbol_active": symbol,
        "live_usdt": live_usdt_balance,
        "positions": positions_data,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    try:
        headers = {"Authorization": f"Bearer {AUTH_TOKEN}"}
        requests.post(WEBHOOK_URL, json=state, headers=headers, timeout=2)
    except Exception as e:
        pass

def check_risk_management(symbol, current_price, atr_value):
    pos = current_positions[symbol]
    bp = buy_prices[symbol]
    
    if pos > 0 and bp > 0:
        # Update highest price seen since bought
        if current_price > highest_prices[symbol]:
            highest_prices[symbol] = current_price
            
        profit_percent = (current_price - bp) / bp * 100
        hp_drop_percent = (highest_prices[symbol] - current_price) / highest_prices[symbol] * 100
        
        # 1. Strict Take Profit (e.g. 3.0%)
        if profit_percent >= 3.0:
            return "Take Profit 🎯"
            
        # 2. Trailing Stop (If we were up by at least 1.5%, sell if it drops 0.5% from peak)
        max_profit_percent = (highest_prices[symbol] - bp) / bp * 100
        if max_profit_percent >= 1.5 and hp_drop_percent >= 0.5:
            return "Trailing Stop 🛡️"
            
        # 3. Dynamic Stop Loss using ATR (or fixed 2.5%, whichever is hit first)
        # Assuming ATR gives absolute price movement. Convert to % 
        atr_percent = (atr_value / current_price) * 100 if atr_value else 2.5
        stop_loss_threshold = min(STOP_LOSS_PERCENT, atr_percent * 1.5) # Use 1.5x ATR as max stop
        
        if profit_percent <= -stop_loss_threshold:
            return "Stop Loss 🚨"
            
    return None

def run_bot_cycle():
    global live_usdt_balance
    sync_state_with_binance()
    
    # Pre-calculate holding value to avoid O(N^2) API calls
    current_holding_value = 0.0
    for sym, pos in current_positions.items():
        if pos > 0:
            cp = last_prices[sym] if last_prices[sym] > 0 else get_current_price(sym)
            current_holding_value += pos * cp
    
    for symbol in SYMBOLS:
        try:
            update_bot_state(f"Monitoring {symbol}...", symbol=symbol)
            df = get_historical_klines(symbol, "1h", limit=250)
            
            if df.empty:
                continue
                
            df = apply_indicators(df)
            signal = analyze_market(df)
            current_price = df.iloc[-1]['close']
            last_prices[symbol] = current_price
            
            atr_value = df.iloc[-1].get('ATR', 0)
            
            # Check Risk Management (Take Profit, Trailing Stop, Stop Loss)
            rm_signal = check_risk_management(symbol, current_price, atr_value)
            if rm_signal:
                log_msg("WARNING", f"🚨 {rm_signal} TRIGGERED for {symbol} at {current_price}!")
                trade = execute_trade(symbol, "SELL", current_positions[symbol], current_price, reason=rm_signal)
                if trade:
                    if not PAPER_TRADING:
                        live_usdt_balance += current_positions[symbol] * current_price
                    current_positions[symbol] = 0.0
                    highest_prices[symbol] = 0.0
                    last_trade_times[symbol] = datetime.now(timezone.utc)
                continue

            # Enforce Cooldown
            ltt = last_trade_times[symbol]
            if ltt and datetime.now(timezone.utc) - ltt < timedelta(minutes=COOLDOWN_MINUTES):
                continue

            if signal == "BUY" and current_positions[symbol] == 0:
                update_bot_state(f"BUY Signal on {symbol}. AI evaluating...", thinking=True, symbol=symbol)
                news = fetch_crypto_news(5)
                ai_result = analyze_sentiment(news, symbol)
                
                # Input Validation & Sanitization
                if not isinstance(ai_result, dict):
                    log_msg("WARNING", f"⚠️ Invalid AI response for {symbol}. Aborting trade.")
                    continue
                    
                decision = ai_result.get('decision')
                risk_score = ai_result.get('risk_score')
                reason = str(ai_result.get('reason', 'No reason provided'))[:255] # Truncate bloat
                
                if risk_score is None or not isinstance(risk_score, (int, float)):
                    risk_score = 100
                    
                update_bot_state(f"AI: {decision} {symbol} (Risk: {risk_score})", symbol=symbol)
                
                if decision == "BUY" and risk_score <= 40:
                    log_msg("INFO", f"🚀 Executing BUY for {symbol}...")
                    
                    # Dynamic Position Sizing using LIVE BALANCE
                    if not PAPER_TRADING:
                        if live_usdt_balance < 10.0:
                            log_msg("WARNING", f"⚠️ Insufficient Binance USDT to buy {symbol}")
                            continue
                            
                        total_equity = live_usdt_balance + current_holding_value
                        
                        trade_amount = total_equity / 5.0 # 5 Tranches
                        
                        if trade_amount < 10.0:
                            trade_amount = 10.0
                            
                        if trade_amount > live_usdt_balance:
                            trade_amount = live_usdt_balance
                            
                    else:
                        trade_amount = QUANTITY_USDT
                        
                    qty = trade_amount / current_price 
                    trade = execute_trade(symbol, "BUY", qty, current_price, reason=reason, ai_risk=risk_score)
                    if trade:
                        if not PAPER_TRADING:
                            live_usdt_balance -= trade_amount
                        current_positions[symbol] = qty
                        buy_prices[symbol] = current_price
                        highest_prices[symbol] = current_price
                        last_trade_times[symbol] = datetime.now(timezone.utc)
                else:
                    log_msg("INFO", f"⚠️ AI aborted BUY for {symbol} (Risk {risk_score}). Applying cooldown.")
                    last_trade_times[symbol] = datetime.now(timezone.utc)
                    
            elif signal == "SELL" and current_positions[symbol] > 0:
                log_msg("INFO", f"📉 SELL Signal for {symbol}. Executing...")
                trade = execute_trade(symbol, "SELL", current_positions[symbol], current_price, reason="MACD Death Cross")
                if trade:
                    if not PAPER_TRADING:
                        live_usdt_balance += current_positions[symbol] * current_price
                    current_positions[symbol] = 0.0
                    highest_prices[symbol] = 0.0
                    last_trade_times[symbol] = datetime.now(timezone.utc)
                
        except Exception as e:
            log_msg("ERROR", f"❌ Error processing {symbol}: {e}")
            # Apply a 5-minute soft cooldown on error to prevent API spam loops
            last_trade_times[symbol] = datetime.now(timezone.utc) - timedelta(minutes=COOLDOWN_MINUTES) + timedelta(minutes=5)
            continue
            
    update_bot_state("Cycle complete. Waiting...", symbol="All")

def execute_trade(symbol: str, side: str, qty: float, price: float, reason: str = "", ai_risk: float = None):
    try:
        order = place_market_order(symbol, side, qty, is_paper=PAPER_TRADING)
        avg_price = order.get('parsed_avg_price')
        if not avg_price:
            avg_price = price
        exec_qty = order.get('parsed_exec_qty', qty)
        commission = order.get('parsed_commission', 0.0)
        commission_asset = order.get('parsed_commission_asset', 'USDT')
    except Exception as e:
        log_msg("ERROR", f"⚠️ Exchange Execution Failed for {symbol}: {e}")
        return # Do not log trade if it failed on exchange
        
    pnl_amount = None
    pnl_percent = None
    if side == "SELL":
        bp = buy_prices[symbol]
        if bp > 0:
            pnl_amount = (avg_price - bp) * exec_qty
            pnl_percent = (avg_price - bp) / bp * 100.0
            
    trade = TradeRepository.create_trade(
        symbol, side, avg_price, exec_qty, ai_risk, reason, PAPER_TRADING,
        commission, commission_asset, pnl_amount, pnl_percent
    )
    if trade:
        log_msg("INFO", f"✅ Trade logged: {side} {exec_qty} {symbol} at {avg_price} (PNL: {pnl_amount})")
        return trade
    else:
        log_msg("ERROR", f"⚠️ Failed to save trade to database for {symbol}")
        return None

if __name__ == "__main__":
    log_msg("INFO", "Starting Multi-Coin MACD Trading Bot Loop...")
    while True:
        try:
            run_bot_cycle()
        except Exception as e:
            log_msg("ERROR", f"Error in bot cycle: {e}")
        time.sleep(60)
