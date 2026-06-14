from datetime import datetime, timezone
from .state import SymbolState

def calculate_pnl(buy_price: float, current_price: float, quantity: float, fee_rate: float = 0.001) -> tuple[float, float]:
    """Returns (pnl_amount, pnl_percent)"""
    if buy_price <= 0 or quantity <= 0:
        return 0.0, 0.0
    pnl_amount = ((current_price - buy_price) * quantity) - ((buy_price + current_price) * quantity * fee_rate)
    pnl_percent = (pnl_amount / (buy_price * quantity)) * 100.0
    return pnl_amount, pnl_percent

def check_risk_management(state: SymbolState, atr_value: float, stop_loss_percent: float) -> str | None:
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
        stop_loss_threshold = min(stop_loss_percent, atr_percent * 1.5)
        if profit_percent <= -stop_loss_threshold:
            return "Fallback Stop Loss 🚨"
            
    return None
