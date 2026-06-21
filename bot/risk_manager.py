from datetime import datetime, timezone
import math
from .state import SymbolState
from .config import FUTURES_LEVERAGE

def calculate_pnl(entry_price: float, current_price: float, quantity: float, fee_rate: float = 0.001, position_side: str = "LONG", market_type: str = "spot") -> tuple[float, float]:
    """Returns (pnl_amount, pnl_percent). pnl_percent reflects return on margin if short/futures."""
    if entry_price <= 0 or quantity <= 0:
        return 0.0, 0.0
    if market_type == "futures":
        fee_rate = 0.0005
        
    fee = (entry_price + current_price) * quantity * fee_rate
    
    if position_side == "SHORT":
        pnl_amount = ((entry_price - current_price) * quantity) - fee
    else:
        pnl_amount = ((current_price - entry_price) * quantity) - fee

    # Calculate margin required based on market type
    if market_type == "futures":
        margin_required = (entry_price * quantity) / FUTURES_LEVERAGE
    else:
        margin_required = entry_price * quantity

    pnl_percent = (pnl_amount / margin_required) * 100.0 if margin_required > 0 else 0.0
        
    return pnl_amount, pnl_percent

def check_risk_management(state: SymbolState, atr_value: float, stop_loss_percent: float, market_type: str = "spot") -> str | None:
    if state.position > 0 and state.buy_price > 0:
        current_price = state.last_price
        
        _, profit_percent = calculate_pnl(state.buy_price, current_price, 1.0, position_side=state.position_side or "LONG", market_type=market_type)
        
        # for maximum profit, if SHORT, lowest_price is best. if LONG, highest_price is best.
        if state.position_side == "SHORT":
            best_price = state.lowest_price if state.lowest_price > 0 else current_price
        else:
            best_price = state.highest_price if state.highest_price > 0 else current_price

        _, max_profit_percent = calculate_pnl(state.buy_price, best_price, 1.0, position_side=state.position_side or "LONG", market_type=market_type)
        
        if state.position_side == "SHORT":
            # For SHORT, trailing drop means price goes UP from the best (lowest) price
            hp_drop_percent = ((current_price - best_price) / best_price) * 100 if best_price > 0 else 0
        else:
            hp_drop_percent = ((best_price - current_price) / best_price) * 100 if best_price > 0 else 0
        
        if state.trade_entry_time and state.max_time_in_trade > 0:
            minutes_elapsed = (datetime.now(timezone.utc) - state.trade_entry_time).total_seconds() / 60
            candle_interval_minutes = 15 # Both spot and futures are now 15m
            if minutes_elapsed >= state.max_time_in_trade * candle_interval_minutes:
                return f"Time-in-Trade Stop ({state.max_time_in_trade} periods) ⏰"

        # Fix Dynamic TP and SL for Short vs Long
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
        
        # ATR Trailing Stop (Chandelier Exit)
        # 1. We must be in profit to activate the trailing stop
        # For Spot, we want to lock in at least some profit, so trailing_drop must be < min_profit
        min_profit_to_trail = atr_percent * 2.0 * (FUTURES_LEVERAGE if market_type == 'futures' else 1.0)
        
        if max_profit_percent >= min_profit_to_trail:
            # 2. Trail by 1.0x ATR raw price drop (so we lock in at least 1.0x ATR profit)
            trailing_drop_raw_percent = atr_percent * 1.0
            if hp_drop_percent >= trailing_drop_raw_percent:
                return "ATR Trailing Stop 🛡️"
            
        # Fallback Stop Loss
        if market_type == 'futures':
            stop_loss_threshold = atr_percent * 1.5 * FUTURES_LEVERAGE
            # Cap maximum futures stop loss
            stop_loss_threshold = min(stop_loss_percent, stop_loss_threshold)
        else:
            # For Spot, volatility is high, prevent getting chopped out by tight ATR
            # Enforce a minimum stop loss of 3.0% or 2.0x ATR, whichever is higher, but capped by the user's config
            stop_loss_threshold = max(3.0, atr_percent * 2.0)
            stop_loss_threshold = min(stop_loss_percent, stop_loss_threshold)
            
        if profit_percent <= -stop_loss_threshold:
            return "Fallback Stop Loss 🚨"
            
    return None
