from bot.state import StateManager
from bot.logger import log_msg
from bot.binance_client import get_step_size, futures_get_step_size, round_step_size

class PaperSimulator:
    @staticmethod
    def _apply_slippage(price: float, side: str, is_futures: bool = False) -> float:
        """
        Applies a basic constant slippage for paper trading simulation.
        In a real high-frequency setup, we would read the orderbook depth.
        For Phase 6, we use 0.05% slippage on top of Bid/Ask.
        """
        slippage_pct = 0.0005
        if side.upper() == 'BUY':
            return price * (1.0 + slippage_pct)
        else:
            return price * (1.0 - slippage_pct)

    @staticmethod
    def execute_spot_trade(state_manager: StateManager, symbol: str, side: str, qty: float):
        state = state_manager.get_state(symbol)
        
        # Use live Bid/Ask if available, fallback to last_price
        if side.upper() == 'BUY':
            base_price = state.best_ask if state.best_ask > 0 else state.last_price
        else:
            base_price = state.best_bid if state.best_bid > 0 else state.last_price
            
        if base_price == 0.0:
            log_msg("ERROR", f"[PAPER SPOT] Failed to execute {side} for {symbol}. Price is 0.0.", market_type="spot")
            return None
            
        executed_price = PaperSimulator._apply_slippage(base_price, side, is_futures=False)
        
        step_size = get_step_size(symbol)
        executed_qty = round_step_size(qty, step_size)
        
        if executed_qty <= 0:
            log_msg("WARNING", f"[PAPER SPOT] Executed qty for {symbol} is <= 0 after step size rounding.", market_type="spot")
            return None
            
        # Spot fees: Assume 0.1% for market orders
        fee = (executed_qty * executed_price) * 0.001
        
        log_msg("INFO", f"[PAPER SPOT] Executed {side} {executed_qty} of {symbol} at {executed_price:.6f} (Fee: {fee:.4f} USDT)", market_type="spot")
        
        return {
            "status": "FILLED",
            "price": executed_price,
            "executedQty": executed_qty,
            "side": side,
            "symbol": symbol,
            "type": "MARKET",
            "parsed_avg_price": executed_price,
            "parsed_exec_qty": executed_qty,
            "parsed_commission": fee,
            "parsed_commission_asset": "USDT"
        }

    @staticmethod
    def execute_futures_trade(state_manager: StateManager, symbol: str, side: str, positionSide: str, qty: float):
        state = state_manager.get_state(symbol)
        
        # Use live Bid/Ask if available, fallback to last_price
        if side.upper() == 'BUY':
            base_price = state.best_ask if state.best_ask > 0 else state.last_price
        else:
            base_price = state.best_bid if state.best_bid > 0 else state.last_price
            
        if base_price == 0.0:
            log_msg("ERROR", f"[PAPER FUTURES] Failed to execute {side} {positionSide} for {symbol}. Price is 0.0.", market_type="futures")
            return None
            
        executed_price = PaperSimulator._apply_slippage(base_price, side, is_futures=True)
        
        step_size = futures_get_step_size(symbol)
        executed_qty = round_step_size(qty, step_size)
        
        if executed_qty <= 0:
            log_msg("WARNING", f"[PAPER FUTURES] Executed qty for {symbol} is <= 0 after step size rounding.", market_type="futures")
            return None
            
        # Futures fees: Assume 0.05% for market orders
        fee = (executed_qty * executed_price) * 0.0005
        
        log_msg("INFO", f"[PAPER FUTURES] Executed {side} {positionSide} {executed_qty} of {symbol} at {executed_price:.6f} (Fee: {fee:.4f} USDT)", market_type="futures")
        
        return {
            "status": "FILLED",
            "price": executed_price,
            "executedQty": executed_qty,
            "side": side,
            "positionSide": positionSide,
            "symbol": symbol,
            "type": "MARKET",
            "parsed_avg_price": executed_price,
            "parsed_exec_qty": executed_qty,
            "parsed_commission": fee,
            "parsed_commission_asset": "USDT"
        }
