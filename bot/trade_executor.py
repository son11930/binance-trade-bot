from .binance_client import place_market_order, get_live_asset_balance, futures_place_order, futures_set_leverage, futures_set_margin_type
from .database import TradeRepository
from .logger import log_msg
from .risk_manager import calculate_pnl
from .state import StateManager
from .config import FUTURES_LEVERAGE, FUTURES_MARGIN_TYPE

def execute_trade(state_manager: StateManager, symbol: str, side: str, qty: float, price: float, reason: str = "", ai_risk: float = None, is_paper: bool = True):
    if side == "SELL" and not is_paper:
        base_asset = symbol.replace("USDT", "")
        actual_balance = get_live_asset_balance(base_asset)
        if actual_balance is not None:
            safe_qty = min(qty, actual_balance)
            if safe_qty < qty:
                log_msg("INFO", f"📉 Adjusted SELL qty for {symbol} from {qty} to {safe_qty} to prevent -2010 Insufficient Balance error.")
            qty = safe_qty

    if qty <= 0:
        log_msg("WARNING", f"⚠️ Skipped {side} for {symbol} because quantity is <= 0.")
        return None

    try:
        order = place_market_order(symbol, side, qty, is_paper=is_paper)
        avg_price = order.get('parsed_avg_price')
        if not avg_price:
            avg_price = price
        exec_qty = order.get('parsed_exec_qty')
        if not exec_qty:
            exec_qty = qty
        commission = order.get('parsed_commission', 0.0)
        commission_asset = order.get('parsed_commission_asset', 'USDT')
    except Exception as e:
        log_msg("ERROR", f"⚠️ Exchange Execution Failed for {symbol}: {e}")
        return None
        
    pnl_amount = None
    pnl_percent = None
    
    state = state_manager.get_state(symbol)
    
    if side == "SELL" and state.buy_price > 0 and exec_qty > 0:
        pnl_amount, pnl_percent = calculate_pnl(state.buy_price, avg_price, exec_qty)
            
    trade = TradeRepository.create_trade(
        symbol=symbol, side=side, price=avg_price, quantity=exec_qty, 
        risk_score=ai_risk, reason=reason, is_paper=is_paper,
        fee=commission, fee_asset=commission_asset, 
        pnl_amount=pnl_amount, pnl_percent=pnl_percent,
        market_type='spot'
    )
    if trade:
        log_msg("INFO", f"✅ Trade logged: {side} {exec_qty} {symbol} at {avg_price} (PNL: {pnl_amount})")
        return trade
    else:
        log_msg("ERROR", f"⚠️ Failed to save trade to database for {symbol}")
        return None

def execute_futures_trade(state_manager: StateManager, symbol: str, side: str, positionSide: str, qty: float, price: float, reason: str = "", ai_risk: float = None, is_paper: bool = True):
    if qty <= 0:
        log_msg("WARNING", f"⚠️ Skipped {side} {positionSide} for {symbol} because quantity is <= 0.", market_type="futures")
        return None

    try:
        # Safety cap for exiting a position to avoid opening an opposite position
        state = state_manager.get_state(symbol)
        if state.position > 0:
            if (positionSide == "LONG" and side == "SELL") or (positionSide == "SHORT" and side == "BUY"):
                if not is_paper:
                    try:
                        from .binance_client import futures_get_position
                        live_pos = futures_get_position(symbol, positionSide=positionSide)
                        if live_pos is not None:
                            actual_qty = abs(float(live_pos.get('positionAmt', 0)))
                            if actual_qty < qty:
                                log_msg("WARNING", f"📉 Adjusted FUTURES EXIT qty for {symbol} from {qty} to {actual_qty} to match Binance.", market_type="futures")
                                qty = actual_qty
                    except Exception as e:
                        log_msg("ERROR", f"Failed to verify live futures position size before exit: {e}", market_type="futures")
                
                # Double check against local state to prevent over-closing in paper trading
                qty = min(qty, state.position)

                # Fix for Issue 3: Infinite Close Loop on Uncleared State
                if qty <= 0:
                    log_msg("INFO", f"✅ FUTURES {symbol} position already closed externally. Clearing local state.", market_type="futures")
                    from datetime import datetime, timezone
                    state_manager.update_state(symbol, position=0.0, highest_price=0.0, active_strategy="NONE", last_trade_time=datetime.now(timezone.utc), dynamic_sl=0.0, dynamic_tp=0.0, position_side="")
                    return None

        order = futures_place_order(symbol, side, positionSide, qty, is_paper=is_paper)
        avg_price = order.get('parsed_avg_price')
        if not avg_price:
            avg_price = price
        exec_qty = order.get('parsed_exec_qty')
        if not exec_qty:
            exec_qty = qty
        commission = order.get('parsed_commission', 0.0)
        commission_asset = order.get('parsed_commission_asset', 'USDT')
    except Exception as e:
        log_msg("ERROR", f"⚠️ Futures Exchange Execution Failed for {symbol}: {e}", market_type="futures")
        return None
        
    pnl_amount = None
    pnl_percent = None
    
    state = state_manager.get_state(symbol)
    
    # Calculate PNL if closing a position
    if positionSide == "LONG" and side == "SELL" and state.buy_price > 0 and exec_qty > 0:
        pnl_amount, pnl_percent = calculate_pnl(state.buy_price, avg_price, exec_qty, position_side="LONG", market_type="futures")
    elif positionSide == "SHORT" and side == "BUY" and state.buy_price > 0 and exec_qty > 0:
        pnl_amount, pnl_percent = calculate_pnl(state.buy_price, avg_price, exec_qty, position_side="SHORT", market_type="futures")

    trade = TradeRepository.create_trade(
        symbol=symbol, side=side, price=avg_price, quantity=exec_qty, 
        risk_score=ai_risk, reason=reason, is_paper=is_paper,
        fee=commission, fee_asset=commission_asset, 
        pnl_amount=pnl_amount, pnl_percent=pnl_percent, 
        market_type="futures", position_side=positionSide
    )
    if trade:
        log_msg("INFO", f"✅ Futures Trade logged: {side} {positionSide} {exec_qty} {symbol} at {avg_price} (PNL: {pnl_amount})", market_type="futures")
        return trade
    else:
        log_msg("ERROR", f"⚠️ Failed to save futures trade to database for {symbol}", market_type="futures")
        return None
