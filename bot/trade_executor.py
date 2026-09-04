from .binance_client import place_market_order, get_live_asset_balance, futures_place_order, futures_set_leverage, futures_set_margin_type, sanitize_error
import uuid
from .database import TradeRepository
from .logger import log_msg
from .risk_manager import calculate_pnl
from .state import StateManager
from .context import validate_execution_context
from .control import ControlPersistenceError, execution_control_lock, set_execution_pause
from .config import FUTURES_LEVERAGE, FUTURES_MARGIN_TYPE


def _pause_after_persistence_failure(state_manager: StateManager, market_type: str, is_paper: bool):
    """Stop one lane when an exchange-confirmed fill cannot be journaled."""
    execution_mode = "PAPER" if is_paper else "LIVE"
    reason = f"{market_type} {execution_mode} lane paused: confirmed execution was not persisted"
    try:
        set_execution_pause(market_type, execution_mode, True, reason=reason)
    except Exception as exc:
        log_msg("ERROR", f"Failed to persist fail-closed pause for {market_type} {execution_mode}: {exc}", market_type=market_type)


def _unpersisted_execution(order: dict, avg_price: float, exec_qty: float, commission: float, commission_asset: str, pnl_amount=None, pnl_percent=None) -> dict:
    """Return a truthy fill marker so callers do not reverse a real fill."""
    return {
        **(order if isinstance(order, dict) else {}),
        "status": "FILLED",
        "execution_confirmed": True,
        "trade_persisted": False,
        "parsed_avg_price": avg_price,
        "parsed_exec_qty": exec_qty,
        "parsed_commission": commission,
        "parsed_commission_asset": commission_asset,
        "pnl_amount": pnl_amount,
        "pnl_percent": pnl_percent,
    }

def execute_trade(state_manager: StateManager, symbol: str, side: str, qty: float, price: float, reason: str = "", ai_risk: float = None, is_paper: bool = True, context=None):
    state = state_manager.get_state(symbol)
    is_protective_exit = str(side).upper() == "SELL" and state.position > 0
    allowed, guard_reason = validate_execution_context(
        state_manager,
        context,
        is_paper,
        allow_protective_exit=is_protective_exit,
    )
    if not allowed:
        log_msg("WARNING", f"Execution refused for {symbol}: {guard_reason}")
        return None

    if side == "SELL" and not is_paper:
        base_asset = symbol.replace("USDT", "")
        actual_balance = get_live_asset_balance(base_asset)
        if actual_balance is None:
            log_msg("ERROR", f"Live SELL refused for {symbol}: Binance balance could not be verified")
            return None
        if actual_balance is not None:
            safe_qty = min(qty, actual_balance)
            if safe_qty < qty:
                log_msg("INFO", f"📉 Adjusted SELL qty for {symbol} from {qty} to {safe_qty} to prevent -2010 Insufficient Balance error.")
            qty = safe_qty

    if qty <= 0:
        log_msg("WARNING", f"⚠️ Skipped {side} for {symbol} because quantity is <= 0.")
        state = state_manager.get_state(symbol)
        if side == "SELL" and state.position > 0:
            log_msg("INFO", f"✅ SPOT {symbol} position already closed externally. Clearing local state.")
            from datetime import datetime, timezone
            state_manager.update_state(symbol, position=0.0, buy_price=0.0, highest_price=0.0, lowest_price=0.0, active_strategy="NONE", last_trade_time=datetime.now(timezone.utc), dynamic_sl=0.0, dynamic_tp=0.0)
        return None

    client_oid = f"agy_spot_{uuid.uuid4().hex[:16]}"
    
    try:
        if is_paper:
            from .paper_engine import PaperSimulator
            order = PaperSimulator.execute_spot_trade(state_manager, symbol, side, qty)
            if not order:
                return None
        else:
            # Recheck immediately before the exchange call so a pause or
            # manifest change during AI/queue work invalidates the order.
            with execution_control_lock():
                allowed, guard_reason = validate_execution_context(
                    state_manager,
                    context,
                    is_paper,
                    allow_protective_exit=is_protective_exit,
                )
                if not allowed:
                    log_msg("WARNING", f"Live order refused for {symbol}: {guard_reason}")
                    return None
                from .binance_client import place_market_order
                order = place_market_order(symbol, side, qty, is_paper=False, client_order_id=client_oid)
        avg_price = order.get('parsed_avg_price')
        if not avg_price:
            avg_price = price
        exec_qty = order.get('parsed_exec_qty')
        if not exec_qty:
            exec_qty = qty
        commission = order.get('parsed_commission', 0.0)
        commission_asset = order.get('parsed_commission_asset', 'USDT')
        if is_paper or commission == 0.0:
            from .binance_client import get_cached_spot_fee
            commission = (exec_qty * avg_price) * get_cached_spot_fee(symbol)
            commission_asset = "USDT"
        if commission < 0.01 and commission_asset == "USDT" and not is_paper:
            commission = 0.01
    except ControlPersistenceError as e:
        _pause_after_persistence_failure(state_manager, "spot", is_paper)
        log_msg("ERROR", f"Live execution boundary unavailable for {symbol}: {e}")
        return None
    except Exception as e:
        err_msg = sanitize_error(e)
        log_msg("ERROR", f"⚠️ Exchange Execution Failed for {symbol}: {err_msg}")
        if ("-1013" in err_msg or "-2010" in err_msg) and side == "SELL":
            log_msg("WARNING", f"🧹 Unsellable dust or insufficient balance for {symbol}. Clearing local state to prevent infinite loop.")
            from datetime import datetime, timezone
            state_manager.update_state(symbol, position=0.0, buy_price=0.0, highest_price=0.0, lowest_price=0.0, active_strategy="NONE", last_trade_time=datetime.now(timezone.utc), dynamic_sl=0.0, dynamic_tp=0.0)
        return None
    pnl_amount = None
    pnl_percent = None
    
    if side == "SELL" and state.buy_price > 0 and exec_qty > 0:
        pnl_amount, pnl_percent = calculate_pnl(state.buy_price, avg_price, exec_qty, symbol=symbol)
            
    trade = TradeRepository.create_trade(
        symbol=symbol, side=side, price=avg_price, quantity=exec_qty, 
        risk_score=ai_risk, reason=reason, is_paper=is_paper,
        fee=commission, fee_asset=commission_asset, 
        pnl_amount=pnl_amount, pnl_percent=pnl_percent,
        market_type='spot',
        execution_mode=context.execution_mode if context else ("PAPER" if is_paper else "LIVE"),
        deployment_id=context.deployment_id if context else None,
        strategy_id=context.strategy_id if context else None
    )
    if not trade:
        _pause_after_persistence_failure(state_manager, "spot", is_paper)
        return _unpersisted_execution(order, avg_price, exec_qty, commission, commission_asset, pnl_amount, pnl_percent)
    if trade:
        log_msg("INFO", f"✅ Trade logged: {side} {exec_qty} {symbol} at {avg_price} (PNL: {pnl_amount})")
        return trade
    else:
        log_msg("ERROR", f"⚠️ Failed to save trade to database for {symbol}")
        return None

def execute_futures_trade(state_manager: StateManager, symbol: str, side: str, positionSide: str, qty: float, price: float, reason: str = "", ai_risk: float = None, is_paper: bool = True, context=None):
    state = state_manager.get_state(symbol)
    is_protective_exit = (
        state.position > 0
        and ((positionSide == "LONG" and side == "SELL") or (positionSide == "SHORT" and side == "BUY"))
    )
    allowed, guard_reason = validate_execution_context(
        state_manager,
        context,
        is_paper,
        allow_protective_exit=is_protective_exit,
    )
    if not allowed:
        log_msg("WARNING", f"Futures execution refused for {symbol}: {guard_reason}", market_type="futures")
        return None

    if qty <= 0:
        log_msg("WARNING", f"⚠️ Skipped {side} {positionSide} for {symbol} because quantity is <= 0.", market_type="futures")
        return None

    try:
        # Safety cap for exiting a position to avoid opening an opposite position
        if state.position > 0:
            if (positionSide == "LONG" and side == "SELL") or (positionSide == "SHORT" and side == "BUY"):
                if not is_paper:
                    try:
                        from .binance_client import futures_get_position
                        live_pos = futures_get_position(symbol, positionSide=positionSide)
                        if live_pos is None:
                            log_msg("ERROR", f"Futures exit refused for {symbol}: Binance position could not be verified", market_type="futures")
                            return None
                        remote_side = str(live_pos.get("positionSide", "")).strip().upper()
                        if remote_side and remote_side != str(positionSide).strip().upper():
                            log_msg("ERROR", f"Futures exit refused for {symbol}: remote position side is {remote_side}, expected {positionSide}", market_type="futures")
                            return None
                        if live_pos is not None:
                            actual_qty = abs(float(live_pos.get('positionAmt', 0)))
                            if actual_qty <= 0:
                                log_msg("INFO", f"Futures position already closed externally for {symbol}; clearing local state.", market_type="futures")
                                from datetime import datetime, timezone
                                state_manager.update_state(symbol, position=0.0, buy_price=0.0, highest_price=0.0, lowest_price=0.0, active_strategy="NONE", last_trade_time=datetime.now(timezone.utc), dynamic_sl=0.0, dynamic_tp=0.0, position_side="")
                                return None
                            if actual_qty < qty:
                                log_msg("WARNING", f"📉 Adjusted FUTURES EXIT qty for {symbol} from {qty} to {actual_qty} to match Binance.", market_type="futures")
                                qty = actual_qty
                    except Exception as e:
                        log_msg("ERROR", f"Failed to verify live futures position size before exit: {e}", market_type="futures")
                        return None
                
                # Double check against local state to prevent over-closing in paper trading
                qty = min(qty, state.position)

                # Fix for Issue 3: Infinite Close Loop on Uncleared State
                if qty <= 0:
                    log_msg("INFO", f"✅ FUTURES {symbol} position already closed externally. Clearing local state.", market_type="futures")
                    from datetime import datetime, timezone
                    state_manager.update_state(symbol, position=0.0, buy_price=0.0, highest_price=0.0, lowest_price=0.0, active_strategy="NONE", last_trade_time=datetime.now(timezone.utc), dynamic_sl=0.0, dynamic_tp=0.0, position_side="")
                    return None

        client_oid = f"agy_fut_{uuid.uuid4().hex[:16]}"
        if is_paper:
            from .paper_engine import PaperSimulator
            order = PaperSimulator.execute_futures_trade(state_manager, symbol, side, positionSide, qty)
            if not order:
                return None
        else:
            # Recheck immediately before the exchange call so a pause or
            # manifest change during AI/queue work invalidates the order.
            with execution_control_lock():
                allowed, guard_reason = validate_execution_context(
                    state_manager,
                    context,
                    is_paper,
                    allow_protective_exit=is_protective_exit,
                )
                if not allowed:
                    log_msg("WARNING", f"Live futures order refused for {symbol}: {guard_reason}", market_type="futures")
                    return None
                from .binance_client import futures_place_order
                order = futures_place_order(symbol, side, positionSide, qty, is_paper=False, client_order_id=client_oid)
        avg_price = order.get('parsed_avg_price')
        if not avg_price:
            avg_price = price
            
        exec_qty = order.get('parsed_exec_qty')
        if not exec_qty:
            exec_qty = qty
            
        # Phase 8: Slippage Auditing
        if not is_paper and avg_price and price > 0:
            slippage_pct = abs(avg_price - price) / price * 100
            slip_str = f"Slippage: {slippage_pct:.3f}%"
            if slippage_pct > 0.5:
                log_msg("WARNING", f"⚠️ HIGH SLIPPAGE detected on {symbol}: {slip_str} (Expected: {price}, Filled: {avg_price})", market_type="futures")
            reason = f"{reason} | {slip_str}"
            
        commission = order.get('parsed_commission', 0.0)
        commission_asset = order.get('parsed_commission_asset', 'USDT')
        if is_paper or commission == 0.0:
            from .binance_client import get_cached_futures_fee
            commission = (exec_qty * avg_price) * get_cached_futures_fee(symbol)
            commission_asset = "USDT"
        if commission < 0.01 and commission_asset == "USDT" and not is_paper:
            commission = 0.01
    except ControlPersistenceError as e:
        _pause_after_persistence_failure(state_manager, "futures", is_paper)
        log_msg("ERROR", f"Futures execution boundary unavailable for {symbol}: {e}", market_type="futures")
        return None
    except Exception as e:
        err_msg = sanitize_error(e)
        is_closing = (positionSide == "LONG" and side == "SELL") or (positionSide == "SHORT" and side == "BUY")
        is_opening = (positionSide == "LONG" and side == "BUY") or (positionSide == "SHORT" and side == "SELL")
        
        if ("-1013" in err_msg or "-2019" in err_msg or "Margin is insufficient" in err_msg) and is_closing:
            log_msg("WARNING", f"🧹 Uncloseable position for {symbol} due to locked margin. Canceling all open orders to attempt close on next tick.", market_type="futures")
            from .binance_client import futures_cancel_all_orders
            futures_cancel_all_orders(symbol, is_paper=is_paper, state_manager=state_manager, context=context)
            return None
            
        if "MarginError" in err_msg or (("-2019" in err_msg or "Margin is insufficient" in err_msg) and is_opening):
            # Already logged in binance_client, no need to spam
            return None
            
        log_msg("ERROR", f"⚠️ Futures Exchange Execution Failed for {symbol}: {err_msg}", market_type="futures")
        return None
        
    pnl_amount = None
    pnl_percent = None
    
    # Calculate PNL if closing a position
    if positionSide == "LONG" and side == "SELL" and state.buy_price > 0 and exec_qty > 0:
        pnl_amount, pnl_percent = calculate_pnl(state.buy_price, avg_price, exec_qty, position_side="LONG", market_type="futures", symbol=symbol)
    elif positionSide == "SHORT" and side == "BUY" and state.buy_price > 0 and exec_qty > 0:
        pnl_amount, pnl_percent = calculate_pnl(state.buy_price, avg_price, exec_qty, position_side="SHORT", market_type="futures", symbol=symbol)

    trade = TradeRepository.create_trade(
        symbol=symbol, side=side, price=avg_price, quantity=exec_qty, 
        risk_score=ai_risk, reason=reason, is_paper=is_paper,
        fee=commission, fee_asset=commission_asset, 
        pnl_amount=pnl_amount, pnl_percent=pnl_percent, 
        market_type="futures", position_side=positionSide,
        execution_mode=context.execution_mode if context else ("PAPER" if is_paper else "LIVE"),
        deployment_id=context.deployment_id if context else None,
        strategy_id=context.strategy_id if context else None
    )
    if not trade:
        _pause_after_persistence_failure(state_manager, "futures", is_paper)
        return _unpersisted_execution(order, avg_price, exec_qty, commission, commission_asset, pnl_amount, pnl_percent)
    if trade:
        log_msg("INFO", f"✅ Futures Trade logged: {side} {positionSide} {exec_qty} {symbol} at {avg_price} (PNL: {pnl_amount})", market_type="futures")
        return trade
    else:
        log_msg("ERROR", f"⚠️ Failed to save futures trade to database for {symbol}", market_type="futures")
        return None
