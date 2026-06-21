from datetime import datetime, timezone
import math
from .state import SymbolState
from .config import FUTURES_LEVERAGE

def calculate_spot_pnl(entry_price: float, current_price: float, quantity: float, fee_rate: float | None = None, symbol: str = "") -> tuple[float, float]:
    """Returns (pnl_amount, pnl_percent) for Spot."""
    if entry_price <= 0 or quantity <= 0:
        return 0.0, 0.0
    
    if fee_rate is None:
        from .binance_client import get_cached_spot_fee
        fee_rate = get_cached_spot_fee(symbol) if symbol else 0.001
        
    fee = (entry_price + current_price) * quantity * fee_rate
    pnl_amount = ((current_price - entry_price) * quantity) - fee
    cost = entry_price * quantity
    pnl_percent = (pnl_amount / cost) * 100.0 if cost > 0 else 0.0
        
    return pnl_amount, pnl_percent

def calculate_futures_pnl(entry_price: float, current_price: float, quantity: float, position_side: str = "LONG", fee_rate: float | None = None, symbol: str = "") -> tuple[float, float]:
    """Returns (pnl_amount, pnl_percent) for Futures. pnl_percent reflects return on margin (ROE)."""
    if entry_price <= 0 or quantity <= 0:
        return 0.0, 0.0
        
    if fee_rate is None:
        from .binance_client import get_cached_futures_fee
        fee_rate = get_cached_futures_fee(symbol) if symbol else 0.0005
    
    fee = (entry_price + current_price) * quantity * fee_rate
    
    if position_side == "SHORT":
        pnl_amount = ((entry_price - current_price) * quantity) - fee
    else:
        pnl_amount = ((current_price - entry_price) * quantity) - fee

    margin_required = (entry_price * quantity) / FUTURES_LEVERAGE
    pnl_percent = (pnl_amount / margin_required) * 100.0 if margin_required > 0 else 0.0
        
    return pnl_amount, pnl_percent

def calculate_pnl(entry_price: float, current_price: float, quantity: float, fee_rate: float | None = None, position_side: str = "LONG", market_type: str = "spot", symbol: str = "") -> tuple[float, float]:
    """Legacy wrapper for calculate_pnl to maintain compatibility if called from elsewhere."""
    if market_type == "futures":
        return calculate_futures_pnl(entry_price, current_price, quantity, position_side, fee_rate, symbol=symbol)
    else:
        return calculate_spot_pnl(entry_price, current_price, quantity, fee_rate, symbol=symbol)

def check_spot_risk_management(state: SymbolState, atr_value: float, stop_loss_percent: float) -> str | None:
    if state.position > 0 and state.buy_price > 0:
        current_price = state.last_price
        
        _, profit_percent = calculate_spot_pnl(state.buy_price, current_price, 1.0, symbol=state.symbol)
        best_price = state.highest_price if state.highest_price > 0 else current_price
        _, max_profit_percent = calculate_spot_pnl(state.buy_price, best_price, 1.0, symbol=state.symbol)
        
        hp_drop_percent = ((best_price - current_price) / best_price) * 100 if best_price > 0 else 0
        
        if state.trade_entry_time and state.max_time_in_trade > 0:
            minutes_elapsed = (datetime.now(timezone.utc) - state.trade_entry_time).total_seconds() / 60
            if minutes_elapsed >= state.max_time_in_trade * 15:
                return f"Time-in-Trade Stop ({state.max_time_in_trade} periods) ⏰"

        if state.dynamic_tp > 0 and current_price >= state.dynamic_tp:
            return f"Dynamic Take Profit ({state.dynamic_tp}) 🎯"
        if state.dynamic_sl > 0 and current_price <= state.dynamic_sl:
            return f"Dynamic Stop Loss ({state.dynamic_sl}) 🚨"
            
        atr_percent = (atr_value / current_price) * 100 if current_price > 0 and atr_value and not math.isnan(atr_value) else 2.5
        
        # Spot Trailing Stop (ตอบสนองไวขึ้น)
        min_profit_to_trail = atr_percent * 1.2
        if max_profit_percent >= min_profit_to_trail:
            trailing_drop_raw_percent = atr_percent * 0.8
            if hp_drop_percent >= trailing_drop_raw_percent:
                return "ATR Trailing Stop 🛡️"
            
        # Spot Breakeven Stop (ปกป้องทุนและค่าธรรมเนียมทันทีที่เริ่มกำไรชัดเจน)
        # หากราคาวิ่งไป 1.2% ให้ล็อคปิดที่ 0.3%
        if max_profit_percent >= 1.2:
            if profit_percent <= 0.3:
                return "Breakeven Stop 🛡️"
                
        # Spot Fallback Stop Loss
        # ใช้ ATR คุมระยะตัดขาดทุน แต่ไม่ให้เกิน 3.0%
        stop_loss_threshold = min(3.0, atr_percent * 2.0)
            
        if profit_percent <= -stop_loss_threshold:
            return "Fallback Stop Loss 🚨"
            
    return None

def check_futures_risk_management(state: SymbolState, atr_value: float, stop_loss_percent: float) -> str | None:
    if state.position > 0 and state.buy_price > 0:
        current_price = state.last_price
        
        _, profit_percent = calculate_futures_pnl(state.buy_price, current_price, 1.0, position_side=state.position_side or "LONG", symbol=state.symbol)
        
        if state.position_side == "SHORT":
            best_price = state.lowest_price if state.lowest_price > 0 else current_price
        else:
            best_price = state.highest_price if state.highest_price > 0 else current_price

        _, max_profit_percent = calculate_futures_pnl(state.buy_price, best_price, 1.0, position_side=state.position_side or "LONG", symbol=state.symbol)
        
        if state.position_side == "SHORT":
            hp_drop_percent = ((current_price - best_price) / best_price) * 100 if best_price > 0 else 0
        else:
            hp_drop_percent = ((best_price - current_price) / best_price) * 100 if best_price > 0 else 0
        
        if state.trade_entry_time and state.max_time_in_trade > 0:
            minutes_elapsed = (datetime.now(timezone.utc) - state.trade_entry_time).total_seconds() / 60
            if minutes_elapsed >= state.max_time_in_trade * 15:
                return f"Time-in-Trade Stop ({state.max_time_in_trade} periods) ⏰"

        if state.position_side == "SHORT":
            if state.dynamic_tp > 0 and current_price <= state.dynamic_tp:
                return f"Dynamic Take Profit ({state.dynamic_tp}) 🎯"
            if state.dynamic_sl > 0 and current_price >= state.dynamic_sl:
                return f"Dynamic Stop Loss ({state.dynamic_sl}) 🚨"
        else:
            if state.dynamic_tp > 0 and current_price >= state.dynamic_tp:
                return f"Dynamic Take Profit ({state.dynamic_tp}) 🎯"
            if state.dynamic_sl > 0 and current_price <= state.dynamic_sl:
                return f"Dynamic Stop Loss ({state.dynamic_sl}) 🚨"
            
        atr_percent = (atr_value / current_price) * 100 if current_price > 0 and atr_value and not math.isnan(atr_value) else 2.5
        
        # Futures Trailing Stop (Based on ROE)
        min_profit_to_trail = atr_percent * 1.5 * FUTURES_LEVERAGE
        if max_profit_percent >= min_profit_to_trail:
            trailing_drop_raw_percent = atr_percent * 1.0
            if hp_drop_percent >= trailing_drop_raw_percent:
                return "ATR Trailing Stop 🛡️"
            
        # Futures Breakeven Stop
        if max_profit_percent >= 3.0:
            if profit_percent <= 1.0:
                return "Breakeven Stop 🛡️"
                
        # Futures Fallback Stop Loss (ROE based)
        stop_loss_threshold = atr_percent * 1.5 * FUTURES_LEVERAGE
        stop_loss_threshold = min(stop_loss_percent * FUTURES_LEVERAGE, stop_loss_threshold)
            
        if profit_percent <= -stop_loss_threshold:
            return "Fallback Stop Loss 🚨"
            
    return None

def check_risk_management(state: SymbolState, atr_value: float, stop_loss_percent: float, market_type: str = "spot") -> str | None:
    """Legacy dispatcher to maintain compatibility."""
    if market_type == "futures":
        return check_futures_risk_management(state, atr_value, stop_loss_percent)
    else:
        return check_spot_risk_management(state, atr_value, stop_loss_percent)
