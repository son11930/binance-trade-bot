import os
import json
import time
import logging
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

from .binance_client import get_historical_klines, place_market_order, get_current_price, get_live_asset_balance
from .strategy import apply_indicators, analyze_market
from .ai_engine import fetch_crypto_news, analyze_sentiment
from .database import TradeRepository

load_dotenv()

SYMBOLS = ["BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT", "BNBUSDT"]
QUANTITY_USDT = float(os.getenv("TRADE_QUANTITY_USDT", "10.0"))
PAPER_TRADING = os.getenv("PAPER_TRADING", "True").lower() == "true"
COOLDOWN_MINUTES = int(os.getenv("COOLDOWN_MINUTES", "60"))
STOP_LOSS_PERCENT = float(os.getenv("STOP_LOSS_PERCENT", "2.5"))

current_positions = {sym: 0.0 for sym in SYMBOLS}
buy_prices = {sym: 0.0 for sym in SYMBOLS}
last_trade_times = {sym: None for sym in SYMBOLS}
live_usdt_balance = 0.0

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
            print(f"⚠️ Skipping sync for {symbol} due to API error.")
            continue
            
        try:
            current_price = get_current_price(symbol)
        except Exception:
            continue
            
        # If value is less than $2, we consider it dust (sold)
        if real_bal * current_price < 2.0:
            if current_positions[symbol] > 0:
                print(f"⚠️ Detected manual SELL for {symbol}. Syncing state.")
            current_positions[symbol] = 0.0
            buy_prices[symbol] = 0.0
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
                    print(f"⚠️ Manual BUY detected for {symbol} or DB missing. Using current price as baseline.")

def update_bot_state(status_msg, thinking=False, symbol="System"):
    state = {
        "status_message": status_msg,
        "is_thinking": thinking,
        "symbol_active": symbol,
        "live_usdt": live_usdt_balance,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    try:
        with open("tmp/bot_state.json", "w", encoding="utf-8") as f:
            json.dump(state, f)
    except Exception as e:
        logging.exception(f"⚠️ Failed to write bot_state.json: {e}")

def check_stop_loss(symbol, current_price):
    pos = current_positions[symbol]
    bp = buy_prices[symbol]
    if pos > 0:
        drop = (bp - current_price) / bp * 100
        if drop >= STOP_LOSS_PERCENT:
            return True
    return False

def run_bot_cycle():
    sync_state_with_binance()
    
    # Pre-calculate holding value to avoid O(N^2) API calls
    current_holding_value = 0.0
    for sym, pos in current_positions.items():
        if pos > 0:
            try:
                current_holding_value += pos * get_current_price(sym)
            except Exception:
                current_holding_value += pos * buy_prices[sym]
    
    for symbol in SYMBOLS:
        try:
            update_bot_state(f"Monitoring {symbol}...", symbol=symbol)
            df = get_historical_klines(symbol, "1h", limit=250)
            
            if df.empty:
                continue
                
            df = apply_indicators(df)
            signal = analyze_market(df)
            current_price = df.iloc[-1]['close']
            
            # Check Stop Loss
            if check_stop_loss(symbol, current_price):
                print(f"🚨 STOP LOSS TRIGGERED for {symbol} at {current_price}!")
                execute_trade(symbol, "SELL", current_positions[symbol], current_price, reason="Stop Loss Triggered")
                current_positions[symbol] = 0.0
                continue

            # Enforce Cooldown
            ltt = last_trade_times[symbol]
            if ltt and datetime.now(timezone.utc) - ltt < timedelta(minutes=COOLDOWN_MINUTES):
                continue

            if signal == "BUY" and current_positions[symbol] == 0:
                update_bot_state(f"BUY Signal on {symbol}. AI evaluating...", thinking=True, symbol=symbol)
                news = fetch_crypto_news(5)
                ai_result = analyze_sentiment(news)
                
                # Input Validation & Sanitization
                if not isinstance(ai_result, dict):
                    print(f"⚠️ Invalid AI response for {symbol}. Aborting trade.")
                    continue
                    
                decision = ai_result.get('decision')
                risk_score = ai_result.get('risk_score')
                reason = str(ai_result.get('reason', 'No reason provided'))[:255] # Truncate bloat
                
                if risk_score is None or not isinstance(risk_score, (int, float)):
                    risk_score = 100
                    
                update_bot_state(f"AI: {decision} {symbol} (Risk: {risk_score})", symbol=symbol)
                
                if decision == "BUY" and risk_score <= 40:
                    print(f"🚀 Executing BUY for {symbol}...")
                    
                    # Dynamic Position Sizing using LIVE BALANCE
                    if not PAPER_TRADING:
                        if live_usdt_balance < 10.0:
                            print(f"⚠️ Insufficient Binance USDT to buy {symbol}")
                            continue
                            
                        total_equity = live_usdt_balance + current_holding_value
                        
                        trade_amount = total_equity / 5.0 # 5 Tranches
                        
                        if trade_amount > live_usdt_balance:
                            trade_amount = live_usdt_balance
                            
                    else:
                        trade_amount = QUANTITY_USDT
                        
                    qty = trade_amount / current_price 
                    execute_trade(symbol, "BUY", qty, current_price, reason=reason, ai_risk=risk_score)
                    current_positions[symbol] = qty
                    buy_prices[symbol] = current_price
                    last_trade_times[symbol] = datetime.now(timezone.utc)
                else:
                    print(f"⚠️ AI aborted BUY for {symbol} (Risk {risk_score}).")
                    
            elif signal == "SELL" and current_positions[symbol] > 0:
                print(f"📉 SELL Signal for {symbol}. Executing...")
                execute_trade(symbol, "SELL", current_positions[symbol], current_price, reason="MACD Death Cross")
                current_positions[symbol] = 0.0
                last_trade_times[symbol] = datetime.now(timezone.utc)
                
        except Exception as e:
            logging.exception(f"❌ Error processing {symbol}")
            continue
            
    update_bot_state("Cycle complete. Waiting...", symbol="All")

def execute_trade(symbol: str, side: str, qty: float, price: float, reason: str = "", ai_risk: float = None):
    try:
        place_market_order(symbol, side, qty, is_paper=PAPER_TRADING)
    except Exception as e:
        logging.exception(f"⚠️ Exchange Execution Failed for {symbol}")
        return # Do not log trade if it failed on exchange
        
    trade = TradeRepository.create_trade(symbol, side, price, qty, ai_risk, reason, PAPER_TRADING)
    if trade:
        print(f"✅ Trade logged: {side} {qty} {symbol} at {price}")
    else:
        print(f"⚠️ Failed to save trade to database for {symbol}")

if __name__ == "__main__":
    print("Starting Multi-Coin MACD Trading Bot Loop...")
    while True:
        try:
            run_bot_cycle()
        except Exception as e:
            print(f"Error in bot cycle: {e}")
        time.sleep(60)
