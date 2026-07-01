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

def _check_spot_momentum_tp(profit_percent: float, rsi_value: float | None, hp_drop_percent: float) -> str | None:
    if rsi_value is not None:
        if profit_percent >= 4.0 and rsi_value >= 75 and hp_drop_percent >= 0.3:
            return "Momentum Take Profit (Fast Surge Waning) 🎯"
        if profit_percent >= 3.0 and rsi_value >= 80 and hp_drop_percent >= 0.2:
            return "Momentum Take Profit (RSI Overbought Waning) 🎯"
    return None

def _check_spot_step_ladder(max_profit_percent: float, profit_percent: float, hp_drop_percent: float, atr_percent: float) -> str | None:
    if max_profit_percent >= 10.0:
        trailing_drop_raw_percent = atr_percent * 1.5
        if hp_drop_percent >= trailing_drop_raw_percent and profit_percent > 8.0:
            return "ATR Trailing Stop (Moonshot) 🚀"
        if profit_percent <= 8.0:
            return "Step Trailing Stop (Lock 8.0%) 🛡️"
    elif max_profit_percent >= 7.0:
        if profit_percent <= 5.5:
            return "Step Trailing Stop (Lock 5.5%) 🛡️"
    elif max_profit_percent >= 5.0:
        if profit_percent <= 4.0:
            return "Step Trailing Stop (Lock 4.0%) 🛡️"
    elif max_profit_percent >= 4.0:
        if profit_percent <= 3.0:
            return "Step Trailing Stop (Lock 3.0%) 🛡️"
    elif max_profit_percent >= 3.0:
        if profit_percent <= 2.0:
            return "Step Breakeven Stop (Lock 2.0%) 🛡️"
    elif max_profit_percent >= 2.0:
        if profit_percent <= 1.0:
            return "Step Breakeven Stop (Lock 1.0%) 🛡️"
    elif max_profit_percent >= 1.5:
        if profit_percent <= 0.5:
            return "Step Breakeven Stop (Lock 0.5%) 🛡️"
    return None

def check_spot_risk_management(state: SymbolState, atr_value: float, stop_loss_percent: float, rsi_value: float = None) -> str | None:
    if state.position <= 0 or state.buy_price <= 0:
        return None
        
    current_price = state.last_price
    _, profit_percent = calculate_spot_pnl(state.buy_price, current_price, 1.0, symbol=state.symbol)
    best_price = state.highest_price if state.highest_price > 0 else current_price
    _, max_profit_percent = calculate_spot_pnl(state.buy_price, best_price, 1.0, symbol=state.symbol)
    hp_drop_percent = ((best_price - current_price) / best_price) * 100 if best_price > 0 else 0

    if state.dynamic_tp > 0 and current_price >= state.dynamic_tp:
        return f"Dynamic Take Profit ({state.dynamic_tp}) 🎯"
    if state.dynamic_sl > 0 and current_price <= state.dynamic_sl:
        return f"Dynamic Stop Loss ({state.dynamic_sl}) 🚨"
        
    atr_percent = (atr_value / current_price) * 100 if current_price > 0 and atr_value and not math.isnan(atr_value) else 2.5
    
    if res := _check_spot_momentum_tp(profit_percent, rsi_value, hp_drop_percent):
        return res
    if res := _check_spot_step_ladder(max_profit_percent, profit_percent, hp_drop_percent, atr_percent):
        return res
        
    stop_loss_threshold = min(3.0, atr_percent * 2.0)
    if profit_percent <= -stop_loss_threshold:
        return "Fallback Stop Loss 🚨"
        
    return None

def _check_gear1_rsi_sniper(max_profit_percent: float, profit_percent: float, rsi_value: float | None, position_side: str) -> str | None:
    if max_profit_percent >= 2.0 and rsi_value is not None:
        dynamic_rsi_overbought = min(85.0, 75.0 + ((profit_percent - 2.0) * 1.5))
        dynamic_rsi_oversold = max(15.0, 25.0 - ((profit_percent - 2.0) * 1.5))
        if position_side == "LONG" and rsi_value >= dynamic_rsi_overbought:
            return f"Dynamic Sniper (RSI {rsi_value:.1f}) 🎯"
        if position_side == "SHORT" and rsi_value <= dynamic_rsi_oversold:
            return f"Dynamic Sniper (RSI {rsi_value:.1f}) 🎯"
    return None

def _check_gears_2_3_4_trailing(max_profit_percent: float, profit_percent: float, atr_percent: float) -> str | None:
    atr_roe = atr_percent * FUTURES_LEVERAGE
    if max_profit_percent >= 10.0:
        trailing_gap = max(3.0, atr_roe * 2.0)
        locked_roe = max(8.5, max_profit_percent - trailing_gap)
        if profit_percent <= locked_roe:
            return "Moonshot Trailing Stop (Gear 2) 🚀"
    elif max_profit_percent >= 2.0:
        trailing_gap = max(1.5, atr_roe * 1.2)
        locked_roe = max_profit_percent - trailing_gap
        if profit_percent <= locked_roe:
            return "Standard Trailing Stop (Gear 3) 🛡️"
    elif max_profit_percent >= 1.0:
        if profit_percent <= 0.2:
            return "Early Breakeven (Gear 4) 🛡️"
    return None

def check_futures_risk_management(state: SymbolState, atr_value: float, stop_loss_percent: float, rsi_value: float = None) -> str | None:
    if state.position <= 0 or state.buy_price <= 0:
        return None
        
    current_price = state.last_price
    _, profit_percent = calculate_futures_pnl(state.buy_price, current_price, 1.0, position_side=state.position_side or "LONG", symbol=state.symbol)
    
    if state.position_side == "SHORT":
        best_price = state.lowest_price if state.lowest_price > 0 else current_price
    else:
        best_price = state.highest_price if state.highest_price > 0 else current_price

    _, max_profit_percent = calculate_futures_pnl(state.buy_price, best_price, 1.0, position_side=state.position_side or "LONG", symbol=state.symbol)

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
    
    if res := _check_gear1_rsi_sniper(max_profit_percent, profit_percent, rsi_value, state.position_side):
        return res
    if res := _check_gears_2_3_4_trailing(max_profit_percent, profit_percent, atr_percent):
        return res
        
    stop_loss_threshold = stop_loss_percent * FUTURES_LEVERAGE 
    if profit_percent <= -stop_loss_threshold:
        return "Fallback Stop Loss 🚨"
        
    return None

def check_risk_management(state: SymbolState, atr_value: float, stop_loss_percent: float, market_type: str = "spot", rsi_value: float = None) -> str | None:
    """Legacy dispatcher to maintain compatibility."""
    if market_type == "futures":
        return check_futures_risk_management(state, atr_value, stop_loss_percent, rsi_value)
    else:
        return check_spot_risk_management(state, atr_value, stop_loss_percent, rsi_value)
