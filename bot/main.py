import os
import time
import requests
import hashlib
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, replace
from dotenv import load_dotenv

from .binance_client import get_historical_klines, place_market_order, get_current_price, get_live_asset_balance, twm
from .strategy import apply_indicators, analyze_market
from .ai_engine import fetch_crypto_news, analyze_sentiment
from .database import TradeRepository, LogRepository, sanitize_text, setup_logging

load_dotenv()
setup_logging()

SYMBOLS = ["BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT", "AVAXUSDT", "DOGEUSDT", "DOTUSDT", "LINKUSDT"]
QUANTITY_USDT = float(os.getenv("TRADE_QUANTITY_USDT", "10.0"))
PAPER_TRADING = os.getenv("PAPER_TRADING", "True").lower() == "true"
COOLDOWN_MINUTES = int(os.getenv("COOLDOWN_MINUTES", "15"))
STOP_LOSS_PERCENT = float(os.getenv("STOP_LOSS_PERCENT", "2.5"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "http://127.0.0.1:8000/api/internal/broadcast")

USER = os.getenv("DASHBOARD_USER")
PASS = os.getenv("DASHBOARD_PASS")
SECRET_SALT = os.getenv("DASHBOARD_SECRET_SALT")

if not USER or not PASS or not SECRET_SALT:
    raise ValueError("CRITICAL SECURITY ERROR: DASHBOARD_USER, DASHBOARD_PASS, and DASHBOARD_SECRET_SALT must be set in .env")

AUTH_TOKEN = hashlib.sha256(f"{USER}:{PASS}:{SECRET_SALT}".encode()).hexdigest()
WEBHOOK_TOKEN = hashlib.sha256(f"{USER}:{PASS}:{SECRET_SALT}_webhook".encode()).hexdigest()

@dataclass(frozen=True)
class SymbolState:
    symbol: str
    position: float = 0.0
    buy_price: float = 0.0
    last_trade_time: datetime | None = None
    trade_entry_time: datetime | None = None
    active_strategy: str = "NONE"
    dynamic_sl: float = 0.0
    dynamic_tp: float = 0.0
    max_time_in_trade: int = 0
    last_price: float = 0.0
    highest_price: float = 0.0

states = {sym: SymbolState(sym) for sym in SYMBOLS}
live_usdt_balance = 1000.0 if PAPER_TRADING else 0.0

def process_ticker_message(msg):
    if msg.get('e') == '24hrTicker':
        sym = msg['s']
        if sym in states:
            states[sym] = replace(states[sym], last_price=float(msg['c']))

for symbol in SYMBOLS:
    twm.start_symbol_ticker_socket(callback=process_ticker_message, symbol=symbol)

def log_msg(level: str, msg: str):
    safe_msg = sanitize_text(msg)
    print(safe_msg)
    LogRepository.log_event(level, safe_msg)

def calculate_pnl(buy_price: float, current_price: float, quantity: float, fee_rate: float = 0.001) -> tuple[float, float]:
    """Returns (pnl_amount, pnl_percent)"""
    if buy_price <= 0 or quantity <= 0:
        return 0.0, 0.0
    pnl_amount = ((current_price - buy_price) * quantity) - ((buy_price + current_price) * quantity * fee_rate)
    pnl_percent = (pnl_amount / (buy_price * quantity)) * 100.0
    return pnl_amount, pnl_percent

def sync_state_with_binance():
    global live_usdt_balance, states
    if not PAPER_TRADING:
        bal = get_live_asset_balance("USDT")
        if bal is not None:
            live_usdt_balance = bal

    if PAPER_TRADING:
        return
        
    for symbol in SYMBOLS:
        state = states[symbol]
        asset = symbol.replace("USDT", "")
        real_bal = get_live_asset_balance(asset)
        
        if real_bal is None:
            log_msg("WARNING", f"⚠️ Skipping sync for {symbol} due to API error.")
            continue
            
        current_price = state.last_price if state.last_price > 0 else get_current_price(symbol)
            
        if real_bal * current_price < 2.0:
            if state.position > 0:
                log_msg("WARNING", f"⚠️ Detected manual SELL for {symbol}. Syncing state.")
                pnl_amount, pnl_percent = calculate_pnl(state.buy_price, current_price, state.position)
                TradeRepository.create_trade(
                    symbol, "SELL", current_price, state.position, None, "Manual SELL", PAPER_TRADING,
                    0.0, "USDT", pnl_amount, pnl_percent
                )
            states[symbol] = replace(state, position=0.0, buy_price=0.0, highest_price=0.0)
        else:
            if state.buy_price == 0.0:
                db_price = TradeRepository.get_last_buy_price(symbol)
                bp = db_price if db_price > 0 else current_price
                if db_price == 0:
                    log_msg("WARNING", f"⚠️ Manual BUY detected for {symbol} or DB missing. Using current price as baseline.")
                states[symbol] = replace(state, position=real_bal, buy_price=bp)
            else:
                states[symbol] = replace(state, position=real_bal)

def update_bot_state(status_msg, thinking=False, symbol="System", ai_debate: dict | None = None):
    positions_data = []
    for sym, state in states.items():
        if state.position > 0:
            pnl_amt, pnl_pct = calculate_pnl(state.buy_price, state.last_price, state.position)
            positions_data.append({
                "symbol": sym,
                "quantity": state.position,
                "buy_price": state.buy_price,
                "current_price": state.last_price,
                "pnl_amount": pnl_amt,
                "pnl_percent": pnl_pct
            })

    payload = {
        "status_message": status_msg,
        "is_thinking": thinking,
        "symbol_active": symbol,
        "live_usdt": live_usdt_balance,
        "positions": positions_data,
        "ai_debate": ai_debate,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    import threading
    
    def _send():
        try:
            headers = {"Authorization": f"Bearer {WEBHOOK_TOKEN}"}
            requests.post(WEBHOOK_URL, json=payload, headers=headers, timeout=5)
        except Exception as e:
            log_msg("WARNING", f"Webhook delivery failed: {e}")
            
    threading.Thread(target=_send, daemon=True).start()

def check_risk_management(state: SymbolState, atr_value: float) -> str | None:
    if state.position > 0 and state.buy_price > 0:
        current_price = state.last_price
        
        _, profit_percent = calculate_pnl(state.buy_price, current_price, 1.0)
        _, max_profit_percent = calculate_pnl(state.buy_price, state.highest_price, 1.0)
        hp_drop_percent = ((state.highest_price - current_price) / state.highest_price) * 100 if state.highest_price > 0 else 0
        
        if state.trade_entry_time and state.max_time_in_trade > 0:
            minutes_elapsed = (datetime.now(timezone.utc) - state.trade_entry_time).total_seconds() / 60
            if minutes_elapsed >= state.max_time_in_trade * 15:
                return f"Time-in-Trade Stop ({state.max_time_in_trade} periods) ⏰"

        if state.dynamic_tp > 0 and current_price >= state.dynamic_tp:
            return f"Dynamic Take Profit ({state.dynamic_tp}) 🎯"
            
        if profit_percent >= 3.0:
            return "Take Profit 🎯"
            
        if max_profit_percent >= 1.5 and hp_drop_percent >= 0.5:
            return "Trailing Stop 🛡️"
            
        if state.dynamic_sl > 0 and current_price <= state.dynamic_sl:
            return f"Dynamic Stop Loss ({state.dynamic_sl}) 🚨"
            
        atr_percent = (atr_value / current_price) * 100 if atr_value else 2.5
        stop_loss_threshold = min(STOP_LOSS_PERCENT, atr_percent * 1.5)
        if profit_percent <= -stop_loss_threshold:
            return "Fallback Stop Loss 🚨"
            
    return None

def execute_trade(symbol: str, side: str, qty: float, price: float, reason: str = "", ai_risk: float = None):
    try:
        order = place_market_order(symbol, side, qty, is_paper=PAPER_TRADING)
        avg_price = order.get('parsed_avg_price', price)
        exec_qty = order.get('parsed_exec_qty', qty)
        commission = order.get('parsed_commission', 0.0)
        commission_asset = order.get('parsed_commission_asset', 'USDT')
    except Exception as e:
        log_msg("ERROR", f"⚠️ Exchange Execution Failed for {symbol}: {e}")
        return None
        
    pnl_amount = None
    pnl_percent = None
    state = states[symbol]
    if side == "SELL" and state.buy_price > 0 and exec_qty > 0:
        pnl_amount, pnl_percent = calculate_pnl(state.buy_price, avg_price, exec_qty)
            
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

kline_buffers = {}
latest_news = "No recent news available."

def update_kline_buffer(symbol, k):
    df = kline_buffers.get(symbol)
    if df is None: return None
    
    msg_timestamp = pd.to_datetime(k['t'], unit='ms')
    last_timestamp = df['timestamp'].iloc[-1]
    
    if msg_timestamp == last_timestamp:
        df.loc[df.index[-1], ['open', 'high', 'low', 'close', 'volume']] = [
            float(k['o']), float(k['h']), float(k['l']), float(k['c']), float(k['v'])
        ]
    elif msg_timestamp > last_timestamp:
        import pandas as pd
        new_row = pd.DataFrame([{
            'timestamp': msg_timestamp,
            'open': float(k['o']),
            'high': float(k['h']),
            'low': float(k['l']),
            'close': float(k['c']),
            'volume': float(k['v'])
        }])
        kline_buffers[symbol] = pd.concat([df, new_row], ignore_index=True).tail(250)
        df = kline_buffers[symbol]
    return df

def process_kline_message(msg):
    if msg['e'] != 'kline':
        return
        
    symbol = msg['s']
    k = msg['k']
    is_closed = k['x']
    current_price = float(k['c'])
    
    # Update local buffer
    df = update_kline_buffer(symbol, k)
    if df is None: return
    
    global live_usdt_balance
    
    # 1. Constant Risk Management
    state = states[symbol]
    if state.position > 0:
        highest = max(state.highest_price, current_price)
        states[symbol] = replace(state, last_price=current_price, highest_price=highest)
        state = states[symbol] # Update local ref
        
        atr_value = 2.5
        if not df.empty and 'ATR' in df.columns:
            atr_value = df.iloc[-1]['ATR']
            
        rm_signal = check_risk_management(state, atr_value)
        if rm_signal:
            log_msg("WARNING", f"🚨 {rm_signal} TRIGGERED for {symbol} at {current_price}!")
            trade = execute_trade(symbol, "SELL", state.position, current_price, reason=rm_signal)
            if trade:
                gross_return = state.position * current_price
                fee = gross_return * 0.001
                net_return = gross_return - fee
                live_usdt_balance += net_return
                states[symbol] = replace(state, position=0.0, highest_price=0.0, active_strategy="NONE", last_trade_time=datetime.now(timezone.utc))
                
    # 2. Strategy evaluation on candle close
    if is_closed:
        evaluate_strategy_for_symbol(symbol, df, current_price)

def evaluate_strategy_for_symbol(symbol: str, df, current_price: float):
    global live_usdt_balance, states
    try:
        update_bot_state(f"Evaluating {symbol}...", symbol=symbol)
        
        df = apply_indicators(df)
        signal_plan = analyze_market(df)
    
        current_holding_value = sum(s.position * (s.last_price if s.last_price > 0 else get_current_price(s.symbol)) for s in states.values() if s.position > 0)
        
        # Fetch news ONCE per cycle to avoid network bottlenecks
        signal = signal_plan.action
        strategy_used = signal_plan.strategy_used
        sl_target = signal_plan.stop_loss
        tp_target = signal_plan.take_profit
        time_limit = signal_plan.time_in_trade
        
        state = states[symbol]
        
        if signal == "BUY" and state.position == 0:
            update_bot_state(f"BUY Signal on {symbol}. AI evaluating...", thinking=True, symbol=symbol)
            
            if strategy_used == "SIDEWAYS_RSI_BB":
                from .binance_client import analyze_order_book_walls
                walls = analyze_order_book_walls(symbol)
                log_msg("INFO", f"Order Book Check for {symbol} - Largest Bid: {walls['largest_bid_price']}, Total Bid Vol: {walls.get('total_bid_qty', 0)}")

            tech_data = {
                "strategy_used": strategy_used,
                "adx": df.iloc[-1].get('ADX', 'N/A'),
                "rsi": df.iloc[-1].get('RSI', 'N/A')
            }
            
            ai_result = analyze_sentiment(latest_news, symbol, tech_data)
            
            if not isinstance(ai_result, dict):
                log_msg("WARNING", f"⚠️ Invalid AI response for {symbol}. Aborting trade.")
                return
                
            decision = ai_result.get('decision')
            risk_score = ai_result.get('risk_score')
            reason = str(ai_result.get('reason', 'No reason provided'))[:255]
            committee_debate = ai_result.get('committee_debate', {})
            
            if risk_score is None or not isinstance(risk_score, (int, float)):
                risk_score = 100
                
            ai_debate_payload = {
                "symbol": symbol,
                "strategy": strategy_used,
                "bull": sanitize_text(committee_debate.get("bullish_analysis", "")),
                "bear": sanitize_text(committee_debate.get("bearish_analysis", "")),
                "chief_reason": sanitize_text(reason),
                "decision": decision,
                "risk_score": risk_score
            }
                
            update_bot_state(f"AI: {decision} {symbol} (Risk: {risk_score})", symbol=symbol, ai_debate=ai_debate_payload)
            
            if decision == "BUY" and risk_score <= 60:
                log_msg("INFO", f"🚀 Executing BUY for {symbol} via {strategy_used}...")
                
                total_equity = live_usdt_balance + current_holding_value
                trade_amount = total_equity * 0.20 # 20% per trade
                if trade_amount < 10.0: trade_amount = 10.0
                if trade_amount > live_usdt_balance: trade_amount = live_usdt_balance
                
                if live_usdt_balance < 10.0 or live_usdt_balance < trade_amount:
                    log_msg("WARNING", f"⚠️ Insufficient {'Binance' if not PAPER_TRADING else 'Paper'} USDT to buy {symbol}")
                    return
                    
                safe_trade_amount = trade_amount * 0.999 # 0.1% fee simulation
                qty = safe_trade_amount / current_price 
                trade = execute_trade(symbol, "BUY", qty, current_price, reason=f"{strategy_used} + AI: {reason}", ai_risk=risk_score)
                if trade:
                    live_usdt_balance -= trade_amount

                    states[symbol] = replace(
                        state, 
                        position=qty, 
                        buy_price=current_price, 
                        highest_price=current_price, 
                        last_trade_time=datetime.now(timezone.utc),
                        trade_entry_time=datetime.now(timezone.utc),
                        active_strategy=strategy_used,
                        dynamic_sl=sl_target,
                        dynamic_tp=tp_target,
                        max_time_in_trade=time_limit
                    )
            else:
                log_msg("INFO", f"⚠️ AI aborted BUY for {symbol} (Risk {risk_score}). Applying cooldown.")
                states[symbol] = replace(state, last_trade_time=datetime.now(timezone.utc))
                
        elif signal == "SELL" and state.position > 0:
            log_msg("INFO", f"📉 SELL Signal for {symbol} via {strategy_used}. Executing...")
            trade = execute_trade(symbol, "SELL", state.position, current_price, reason=f"Strategy SELL: {strategy_used}")
            if trade:
                gross_return = state.position * current_price
                fee = gross_return * 0.001
                net_return = gross_return - fee
                live_usdt_balance += net_return
                states[symbol] = replace(state, position=0.0, highest_price=0.0, active_strategy="NONE", last_trade_time=datetime.now(timezone.utc))
                
    except Exception as e:
        log_msg("ERROR", f"❌ Error processing {symbol}: {e}")
        states[symbol] = replace(states[symbol], last_trade_time=datetime.now(timezone.utc) - timedelta(minutes=COOLDOWN_MINUTES) + timedelta(minutes=5))

def news_updater_loop():
    global latest_news
    while True:
        try:
            latest_news = fetch_crypto_news(5)
        except Exception:
            pass
        time.sleep(3600) # Update news every hour

if __name__ == "__main__":
    log_msg("INFO", "Starting Multi-Coin MACD Trading Bot with WebSockets...")
    sync_state_with_binance()
    
    # Fetch initial history
    log_msg("INFO", "Fetching initial 15m history...")
    for sym in SYMBOLS:
        kline_buffers[sym] = get_historical_klines(sym, "15m", limit=250)
        
    import threading
    threading.Thread(target=news_updater_loop, daemon=True).start()
    
    # Subscribe to streams
    from .binance_client import twm
    for sym in SYMBOLS:
        twm.start_kline_socket(callback=process_kline_message, symbol=sym, interval='15m')
        
    log_msg("INFO", "WebSocket streams active. Waiting for candle closes...")
    update_bot_state("Waiting for next candle close...", symbol="All")
    
    try:
        while True:
            time.sleep(60)
            update_bot_state("Monitoring markets via WebSockets...", symbol="All")
    except KeyboardInterrupt:
        twm.stop()
        log_msg("INFO", "Bot stopped by user.")
