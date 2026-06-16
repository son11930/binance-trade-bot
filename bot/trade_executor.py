from .binance_client import place_market_order, get_live_asset_balance
from .database import TradeRepository
from .logger import log_msg
from .risk_manager import calculate_pnl
from .state import StateManager

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
        avg_price = order.get('parsed_avg_price', price)
        exec_qty = order.get('parsed_exec_qty', qty)
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
        symbol, side, avg_price, exec_qty, ai_risk, reason, is_paper,
        commission, commission_asset, pnl_amount, pnl_percent
    )
    if trade:
        log_msg("INFO", f"✅ Trade logged: {side} {exec_qty} {symbol} at {avg_price} (PNL: {pnl_amount})")
        return trade
    else:
        log_msg("ERROR", f"⚠️ Failed to save trade to database for {symbol}")
        return None
