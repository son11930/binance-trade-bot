from concurrent.futures import ThreadPoolExecutor
import requests
from datetime import datetime, timezone

from .config import WEBHOOK_URL, WEBHOOK_TOKEN, FUTURES_LEVERAGE
from .logger import log_msg
from .risk_manager import calculate_pnl
from .state import StateManager
from .database import sanitize_text

def sanitize_dict(d, depth=0):
    if depth > 5:
        return "[MAX_DEPTH_EXCEEDED]"
    if isinstance(d, dict):
        return {sanitize_text(k) if isinstance(k, str) else k: sanitize_dict(v, depth+1) for k, v in d.items()}
    elif isinstance(d, list):
        return [sanitize_dict(v, depth+1) for v in d]
    elif isinstance(d, str):
        return sanitize_text(d)[:1000] # Cap all strings
    return d

# Use a single executor for webhooks to prevent thread explosion
_webhook_executor = ThreadPoolExecutor(max_workers=10)
# Note: we will check _webhook_executor._work_queue.qsize() to prevent queue buildup

def build_webhook_payload(state_manager: StateManager, status_msg: str, thinking=False, symbol="System", ai_debate: dict | None = None, market_type: str = 'spot'):
    positions_data = []
    
    states = state_manager.get_all_states()
    for sym, state in states.items():
        if state.position > 0:
            pnl_amt, pnl_pct = calculate_pnl(state.buy_price, state.last_price, state.position, market_type=market_type, position_side=state.position_side)
            
            position_entry = {
                "symbol": sym,
                "quantity": state.position,
                "buy_price": state.buy_price,
                "current_price": state.last_price,
                "pnl_amount": pnl_amt,
                "pnl_percent": pnl_pct,
                "position_side": state.position_side,
            }

            if market_type == 'futures':
                position_entry["margin"] = (state.position * state.buy_price) / FUTURES_LEVERAGE
                position_entry["funding_rate"] = state_manager.get_funding_rate(sym)
                position_entry["long_short_ratio"] = state_manager.get_long_short_ratio(sym)
                position_entry["liquidations"] = state_manager.get_liquidations(sym)
                
            positions_data.append(position_entry)

    # Sanitize inputs to prevent API key leaks
    safe_status = sanitize_text(status_msg)
    safe_symbol = sanitize_text(symbol)
    
    # Prevent massive payloads from crashing the process
    if ai_debate:
        for key in ["bull", "bear"]:
            if key in ai_debate and isinstance(ai_debate[key], str):
                ai_debate[key] = ai_debate[key][:500] + "..." if len(ai_debate[key]) > 500 else ai_debate[key]
    safe_ai_debate = sanitize_dict(ai_debate) if ai_debate else None
    safe_positions = sanitize_dict(positions_data)

    res = {
        "market_type": market_type,
        "status_message": safe_status,
        "is_thinking": thinking,
        "symbol_active": safe_symbol,
        "live_usdt": state_manager.live_usdt_balance,
        "positions": safe_positions,
        "ai_debate": safe_ai_debate,
        "fear_greed_index": sanitize_text(str(state_manager.fear_greed_index)) if state_manager.fear_greed_index is not None else None,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    try:
        import json
        with open(f"/tmp/webhook_payload_{market_type}.json", "w") as f:
            json.dump(res, f)
    except: pass
    return res

def dispatch_webhook(payload: dict):
    def _send():
        headers = {}
        from urllib.parse import urlparse
        parsed = urlparse(WEBHOOK_URL)
        if parsed.hostname in ["localhost", "127.0.0.1", "45.136.254.62"] and parsed.path.endswith("/api/internal/broadcast"):
            headers["Authorization"] = f"Bearer {WEBHOOK_TOKEN}"
            
        try:
            response = requests.post(WEBHOOK_URL, json=payload, headers=headers, timeout=3)
            response.raise_for_status()
        except Exception as e:
            # We don't retry because state broadcasts are idempotent and a new one will arrive shortly anyway.
            # Retrying old prices blocks the queue and causes the 20-second lag symptom.
            pass
            
    # Protect against unbounded queue growth (DoS mitigation)
    if _webhook_executor._work_queue.qsize() > 50:
        log_msg("WARNING", "⚠️ Webhook queue overloaded. Dropping update to prevent OOM.", market_type=payload.get("market_type", "spot"))
        return
        
    _webhook_executor.submit(_send)

def update_bot_state(state_manager: StateManager, status_msg: str, thinking=False, symbol="System", ai_debate: dict | None = None, market_type: str = 'spot'):
    payload = build_webhook_payload(state_manager, status_msg, thinking, symbol, ai_debate, market_type)
    dispatch_webhook(payload)
