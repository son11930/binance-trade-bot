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

def check_spot_risk_management(state: SymbolState, atr_value: float, stop_loss_percent: float, rsi_value: float = None) -> str | None:
    if state.position > 0 and state.buy_price > 0:
        current_price = state.last_price
        
        _, profit_percent = calculate_spot_pnl(state.buy_price, current_price, 1.0, symbol=state.symbol)
        best_price = state.highest_price if state.highest_price > 0 else current_price
        _, max_profit_percent = calculate_spot_pnl(state.buy_price, best_price, 1.0, symbol=state.symbol)
        
        hp_drop_percent = ((best_price - current_price) / best_price) * 100 if best_price > 0 else 0
        
        if state.trade_entry_time and state.max_time_in_trade > 0:
            minutes_elapsed = (datetime.now(timezone.utc) - state.trade_entry_time).total_seconds() / 60
            if minutes_elapsed >= state.max_time_in_trade * 15:
                # Time-Expired Tight Stop Logic
                if profit_percent < 0.5:
                    return f"Time Limit Exceeded (Stalled/Loss at {profit_percent:.2f}%) ⏰"
                if profit_percent >= 10.0:
                    return "Time Limit Exceeded (Max Profit Hit) ⏰🎯"
                
                # Tight Ladder for Time-Expired Trades
                if max_profit_percent >= 7.0 and profit_percent <= 5.0:
                    return "Time Limit Tight Stop (Locked 5.0%) ⏰🛡️"
                elif max_profit_percent >= 5.0 and profit_percent <= 3.5:
                    return "Time Limit Tight Stop (Locked 3.5%) ⏰🛡️"
                elif max_profit_percent >= 3.0 and profit_percent <= 2.0:
                    return "Time Limit Tight Stop (Locked 2.0%) ⏰🛡️"
                elif max_profit_percent >= 1.5 and profit_percent <= 1.0:
                    return "Time Limit Tight Stop (Locked 1.0%) ⏰🛡️"
                elif max_profit_percent >= 0.5 and profit_percent <= 0.5:
                    return "Time Limit Tight Stop (Breakeven 0.5%) ⏰🛡️"

        if state.dynamic_tp > 0 and current_price >= state.dynamic_tp:
            return f"Dynamic Take Profit ({state.dynamic_tp}) 🎯"
        if state.dynamic_sl > 0 and current_price <= state.dynamic_sl:
            return f"Dynamic Stop Loss ({state.dynamic_sl}) 🚨"
            
        atr_percent = (atr_value / current_price) * 100 if current_price > 0 and atr_value and not math.isnan(atr_value) else 2.5
        
        # ---------------------------------------------------------
        # Sell into Strength (Momentum Take Profit)
        # ---------------------------------------------------------
        if rsi_value is not None:
            if profit_percent >= 4.0 and rsi_value >= 75:
                return "Momentum Take Profit (Fast Surge) 🎯"
            if profit_percent >= 3.0 and rsi_value >= 80:
                return "Momentum Take Profit (RSI Overbought) 🎯"
            
        # ---------------------------------------------------------
        # Spot Step-based Trailing / Breakeven Stop Ladder
        # ---------------------------------------------------------
        if max_profit_percent >= 10.0:
            # Hybrid Moonshot: Let profit run using ATR, but hard floor at 8.0%
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
                # 0.5% safely covers Binance 0.2% total fees and leaves 0.3% net profit
                return "Step Breakeven Stop (Lock 0.5%) 🛡️"
                
        # Spot Fallback Stop Loss
        # Hard cap at exactly 3.0% loss. Uses ATR for tighter stops in low volatility.
        stop_loss_threshold = min(3.0, atr_percent * 2.0)
            
        if profit_percent <= -stop_loss_threshold:
            return "Fallback Stop Loss 🚨"
            
    return None

def check_futures_risk_management(state: SymbolState, atr_value: float, stop_loss_percent: float, rsi_value: float = None) -> str | None:
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
                # Time-Expired Tight Stop Logic
                if profit_percent < 0.5:
                    return f"Time Limit Exceeded (Stalled/Loss at {profit_percent:.2f}%) ⏰"
                if profit_percent >= 10.0:
                    return "Time Limit Exceeded (Max Profit Hit) ⏰🎯"
                
                # Tight Ladder for Time-Expired Trades
                if max_profit_percent >= 7.0 and profit_percent <= 5.0:
                    return "Time Limit Tight Stop (Locked 5.0%) ⏰🛡️"
                elif max_profit_percent >= 5.0 and profit_percent <= 3.5:
                    return "Time Limit Tight Stop (Locked 3.5%) ⏰🛡️"
                elif max_profit_percent >= 3.0 and profit_percent <= 2.0:
                    return "Time Limit Tight Stop (Locked 2.0%) ⏰🛡️"
                elif max_profit_percent >= 1.5 and profit_percent <= 1.0:
                    return "Time Limit Tight Stop (Locked 1.0%) ⏰🛡️"
                elif max_profit_percent >= 0.5 and profit_percent <= 0.5:
                    return "Time Limit Tight Stop (Breakeven 0.5%) ⏰🛡️"

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
        
        # ---------------------------------------------------------
        # Sell into Strength (Momentum Take Profit)
        # ---------------------------------------------------------
        if rsi_value is not None:
            if profit_percent >= 3.0:
                if state.position_side == "LONG" and rsi_value >= 70:
                    return "Momentum Take Profit (Fast Surge) 🎯"
                elif state.position_side == "SHORT" and rsi_value <= 30:
                    return "Momentum Take Profit (Fast Surge) 🎯"
                    
            if profit_percent >= 2.0:
                if state.position_side == "LONG" and rsi_value >= 75:
                    return "Momentum Take Profit (RSI Overbought) 🎯"
                elif state.position_side == "SHORT" and rsi_value <= 25:
                    return "Momentum Take Profit (RSI Oversold) 🎯"
        
        # ---------------------------------------------------------
        # Futures Step-based Trailing / Breakeven Stop Ladder
        # ---------------------------------------------------------
        if max_profit_percent >= 10.0:
            # Hybrid Moonshot: Let profit run using ATR, but hard floor at 8.5% ROE
            trailing_drop_raw_percent = atr_percent * 1.5  # Wider trail for big trends
            if hp_drop_percent >= trailing_drop_raw_percent and profit_percent > 8.5:
                return "ATR Trailing Stop (Moonshot) 🚀"
            if profit_percent <= 8.5:
                return "Step Trailing Stop (Lock 8.5%) 🛡️"
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
                
        # Futures Fallback Stop Loss (ROE based)
        # Cap maximum loss at exactly 3.0% ROE (Hard cap, not multiplied by leverage again)
        stop_loss_threshold = 3.0 
            
        if profit_percent <= -stop_loss_threshold:
            return "Fallback Stop Loss 🚨"
            
    return None

def check_risk_management(state: SymbolState, atr_value: float, stop_loss_percent: float, market_type: str = "spot", rsi_value: float = None) -> str | None:
    """Legacy dispatcher to maintain compatibility."""
    if market_type == "futures":
        return check_futures_risk_management(state, atr_value, stop_loss_percent, rsi_value)
    else:
        return check_spot_risk_management(state, atr_value, stop_loss_percent, rsi_value)
