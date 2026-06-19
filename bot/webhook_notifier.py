from concurrent.futures import ThreadPoolExecutor
import requests
from datetime import datetime, timezone

from .config import WEBHOOK_URL, WEBHOOK_TOKEN, FUTURES_LEVERAGE
from .logger import log_msg
from .risk_manager import calculate_pnl
from .state import StateManager
from .database import sanitize_text

def sanitize_dict(d):
    if isinstance(d, dict):
        return {sanitize_text(k) if isinstance(k, str) else k: sanitize_dict(v) for k, v in d.items()}
    elif isinstance(d, list):
        return [sanitize_dict(v) for v in d]
    elif isinstance(d, str):
        return sanitize_text(d)
    return d

# Use a single executor for webhooks to prevent thread explosion
_webhook_executor = ThreadPoolExecutor(max_workers=5)
# Note: we will check _webhook_executor._work_queue.qsize() to prevent queue buildup

def update_bot_state(state_manager: StateManager, status_msg: str, thinking=False, symbol="System", ai_debate: dict | None = None, market_type: str = 'spot'):
    positions_data = []
    
    states = state_manager.get_all_states()
    for sym, state in states.items():
        if state.position > 0:
            pnl_amt, pnl_pct = calculate_pnl(state.buy_price, state.last_price, state.position, market_type=market_type, position_side=state.position_side)
            
            margin = None
            if market_type == 'futures':
                margin = (state.position * state.buy_price) / FUTURES_LEVERAGE
                
            positions_data.append({
                "symbol": sym,
                "quantity": state.position,
                "buy_price": state.buy_price,
                "current_price": state.last_price,
                "pnl_amount": pnl_amt,
                "pnl_percent": pnl_pct,
                "position_side": state.position_side,
                "margin": margin
            })

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

    payload = {
        "market_type": market_type,
        "status_message": safe_status,
        "is_thinking": thinking,
        "symbol_active": safe_symbol,
        "live_usdt": state_manager.live_usdt_balance,
        "positions": safe_positions,
        "ai_debate": safe_ai_debate,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    def _send():
        import time
        headers = {}
        from urllib.parse import urlparse
        parsed = urlparse(WEBHOOK_URL)
        if parsed.path.endswith("/api/internal/broadcast"):
            headers["Authorization"] = f"Bearer {WEBHOOK_TOKEN}"
            
        for attempt in range(3):
            try:
                response = requests.post(WEBHOOK_URL, json=payload, headers=headers, timeout=10)
                response.raise_for_status()
                break
            except Exception as e:
                if attempt == 2:
                    log_msg("WARNING", f"Webhook delivery failed after 3 attempts: {e}")
                else:
                    time.sleep(2)
            
    # Protect against unbounded queue growth (DoS mitigation)
    if _webhook_executor._work_queue.qsize() > 50:
        log_msg("WARNING", "⚠️ Webhook queue overloaded. Dropping update to prevent OOM.", market_type=market_type)
        return
        
    _webhook_executor.submit(_send)
