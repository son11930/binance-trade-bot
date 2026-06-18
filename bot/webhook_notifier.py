from concurrent.futures import ThreadPoolExecutor
import requests
from datetime import datetime, timezone

from .config import WEBHOOK_URL, WEBHOOK_TOKEN
from .logger import log_msg
from .risk_manager import calculate_pnl
from .state import StateManager
from .database import sanitize_text

# Use a single executor for webhooks to prevent thread explosion
_webhook_executor = ThreadPoolExecutor(max_workers=5)

def update_bot_state(state_manager: StateManager, status_msg: str, thinking=False, symbol="System", ai_debate: dict | None = None, market_type: str = 'spot'):
    positions_data = []
    
    states = state_manager.get_all_states()
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

    # Sanitize inputs to prevent API key leaks
    safe_status = sanitize_text(status_msg)
    safe_ai_debate = None
    if ai_debate:
        import json
        # serialize, sanitize, and deserialize
        safe_ai_debate = json.loads(sanitize_text(json.dumps(ai_debate)))

    payload = {
        "market_type": market_type,
        "status_message": safe_status,
        "is_thinking": thinking,
        "symbol_active": symbol,
        "live_usdt": state_manager.live_usdt_balance,
        "positions": positions_data,
        "ai_debate": safe_ai_debate,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    def _send():
        import time
        headers = {}
        # Only attach token if hitting our internal API (which ends in /api/internal/broadcast)
        if "127.0.0.1" in WEBHOOK_URL or "localhost" in WEBHOOK_URL or "/api/internal/broadcast" in WEBHOOK_URL:
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
            
    _webhook_executor.submit(_send)
