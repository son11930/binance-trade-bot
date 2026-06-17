import threading
import requests
from datetime import datetime, timezone

from .config import WEBHOOK_URL, WEBHOOK_TOKEN
from .logger import log_msg
from .risk_manager import calculate_pnl
from .state import StateManager

def update_bot_state(state_manager: StateManager, status_msg: str, thinking=False, symbol="System", ai_debate: dict | None = None):
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

    payload = {
        "status_message": status_msg,
        "is_thinking": thinking,
        "symbol_active": symbol,
        "live_usdt": state_manager.live_usdt_balance,
        "positions": positions_data,
        "ai_debate": ai_debate,
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    def _send():
        import time
        headers = {"Authorization": f"Bearer {WEBHOOK_TOKEN}"}
        for attempt in range(3):
            try:
                requests.post(WEBHOOK_URL, json=payload, headers=headers, timeout=10)
                break
            except Exception as e:
                if attempt == 2:
                    log_msg("WARNING", f"Webhook delivery failed after 3 attempts: {e}")
                else:
                    time.sleep(2)
            
    threading.Thread(target=_send, daemon=True).start()
