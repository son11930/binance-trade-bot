from .binance_client import place_market_order
from .database import TradeRepository
from .logger import log_msg
from .risk_manager import calculate_pnl
from .state import StateManager

def execute_trade(state_manager: StateManager, symbol: str, side: str, qty: float, price: float, reason: str = "", ai_risk: float = None, is_paper: bool = True):
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
