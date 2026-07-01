import threading
from datetime import datetime, timedelta, timezone

from .strategy import apply_indicators, analyze_market
from .ai_engine import analyze_sentiment
from .database import sanitize_text, TradeRepository
from bot.logger import log_msg
from bot.state import StateManager, SymbolState
from bot.control import get_bot_control
from .config import PAPER_TRADING, COOLDOWN_MINUTES
from .trade_executor import execute_trade
from .webhook_notifier import update_bot_state, send_discord_alert
from .binance_client import get_current_price
from .state import StateManager

def _check_trading_paused(control: dict, market_type: str, symbol: str, state_manager: StateManager) -> bool:
    key = "futures_paused" if market_type == "futures" else "spot_paused"
    if control.get(key):
        log_msg("WARNING", f"⏸️ Trading is Paused for {market_type.capitalize()}. Skipping AI evaluation and order for {symbol}.")
        update_bot_state(state_manager, f"Paused: Skipping {symbol}", symbol=symbol, market_type=market_type)
        state_manager.update_state(symbol, last_trade_time=datetime.now(timezone.utc))
        return True
    return False

def _check_slippage_guard(state_manager: StateManager, symbol: str, current_price: float, market_type: str) -> float | None:
    state = state_manager.get_state(symbol)
    live_price = state.last_price if state.last_price > 0 else current_price
    if live_price > 0:
        slippage = abs(live_price - current_price) / current_price
        if slippage > 0.005:
            log_msg("WARNING", f"⚠️ Slippage Guard: Aborting {market_type.capitalize()} {symbol} trade. Price moved >0.5% ({current_price} -> {live_price}).")
            update_bot_state(state_manager, f"Aborted: Slippage >0.5%", symbol=symbol, market_type=market_type)
            state_manager.update_state(symbol, last_trade_time=datetime.now(timezone.utc))
            return None
        return live_price
    return current_price

def _build_ai_tech_context(state_manager: StateManager, symbol: str, strategy_used: str, adx_val, rsi_val, macd_histogram_val, atr_val, bb_width_val, dist_sma_200_val, vol_surge_val, market_regime_val: str, position_side: str, market_type: str) -> dict:
    from .database import TradeRepository
    lessons_learned = TradeRepository.get_recent_losing_trades(symbol, limit=3, market_type=market_type)
    winning_trades = TradeRepository.get_recent_winning_trades(symbol, limit=2, market_type=market_type)
    return {
        "market_regime": market_regime_val,
        "strategy_used": strategy_used,
        "adx": adx_val,
        "rsi": rsi_val,
        "macd_histogram": macd_histogram_val,
        "atr": atr_val,
        "bb_width": bb_width_val,
        "dist_sma_200": dist_sma_200_val,
        "vol_surge_multiplier": vol_surge_val,
        "funding_rate": state_manager.get_funding_rate(symbol),
        "long_short_ratio": state_manager.get_long_short_ratio(symbol),
        "liquidations": state_manager.get_liquidations(symbol),
        "order_book": state_manager.get_order_book(symbol),
        "fear_greed_index": state_manager.fear_greed_index,
        "lessons_learned": lessons_learned,
        "winning_trades": winning_trades,
        "proposed_direction": position_side
    }

def _process_ai_evaluation(state_manager: StateManager, symbol: str, ai_result: dict, position_side: str, strategy_used: str, market_type: str) -> tuple[str, float, str, dict] | None:
    if not isinstance(ai_result, dict):
        log_msg("WARNING", f"⚠️ Invalid AI response for {symbol}. Aborting {market_type} trade.")
        return None
        
    decision = ai_result.get('decision')
    risk_score = ai_result.get('risk_score')
    reason = str(ai_result.get('reason', 'No reason provided'))[:255]
    committee_debate = ai_result.get('committee_debate', {})
    
    if risk_score is None or not isinstance(risk_score, (int, float)):
        risk_score = 100
        
    tech_context = ai_result.get('tech_context', '')
    TradeRepository.save_ai_decision(symbol, position_side, risk_score, decision, reason, tech_context, market_type=market_type)
        
    model_used = ai_result.get('model_used', 'UNKNOWN')
    is_error = ai_result.get('is_error', False)
    
    if is_error:
        log_msg("ERROR", f"🚨 AI API Error [{model_used}]: {reason}", market_type=market_type)
        log_msg("WARNING", f"⚠️ Trade for {symbol} skipped due to AI API Failure. Will retry next signal without cooldown.", market_type=market_type)
        update_bot_state(state_manager, f"AI Error: {reason[:50]}...", thinking=False, symbol=symbol, market_type=market_type)
        state_manager.update_state(symbol, last_trade_time=None)
        return None
        
    log_msg("INFO", f"🤖 AI Evaluation [{model_used}]: {symbol} -> {decision} (Risk: {risk_score}) | Reason: {reason}", market_type=market_type)
        
    ai_debate_payload = {
        "symbol": symbol,
        "strategy": strategy_used,
        "bull": sanitize_text(committee_debate.get("bullish_analysis", "")),
        "bear": sanitize_text(committee_debate.get("bearish_analysis", "")),
        "chief_reason": sanitize_text(reason),
        "decision": decision,
        "risk_score": risk_score
    }
        
    update_bot_state(state_manager, f"AI: {decision} {symbol} {market_type.capitalize()} (Risk: {risk_score})", symbol=symbol, ai_debate=ai_debate_payload, market_type=market_type)
    return decision, risk_score, reason, ai_result

def _calculate_futures_position_size(state_manager: StateManager, symbol: str, allocation_percentage: float, current_price: float) -> tuple[float, float] | None:
    allocation_percentage = max(10.0, min(40.0, float(allocation_percentage)))
    total_margin = state_manager.live_usdt_balance
    if total_margin < 5.0:
        log_msg("WARNING", f"⚠️ Insufficient Futures USDT balance for {symbol} (Balance: {total_margin}). Aborting trade.", market_type="futures")
        return None
        
    trade_margin = total_margin * (allocation_percentage / 100.0)
    if trade_margin < 5.0:
        trade_margin = 5.0
    
    from .config import FUTURES_LEVERAGE
    notional_value = trade_margin * FUTURES_LEVERAGE
    
    if notional_value < 21.0:
        required_margin = 21.0 / max(FUTURES_LEVERAGE, 1)
        if total_margin >= required_margin:
            trade_margin = required_margin
            notional_value = 21.0
        else:
            log_msg("WARNING", f"⚠️ Insufficient Futures USDT balance to meet Binance min notional of 21 USDT for {symbol}. Need {required_margin:.2f} USDT, have {total_margin:.2f}. Aborting.", market_type="futures")
            return None
            
    qty = notional_value / current_price
    return qty, notional_value

def _calculate_spot_position_size(state_manager: StateManager, symbol: str, allocation_percentage: float, current_price: float, current_holding_value: float) -> tuple[float, float] | None:
    allocation_percentage = max(10.0, min(40.0, float(allocation_percentage)))
    live_usdt_balance = state_manager.live_usdt_balance
    total_equity = live_usdt_balance + current_holding_value
    trade_amount = total_equity * (allocation_percentage / 100.0)
    if trade_amount < 10.0: trade_amount = 10.0
    if trade_amount > live_usdt_balance: trade_amount = live_usdt_balance
    
    if live_usdt_balance < 10.0 or live_usdt_balance < trade_amount:
        log_msg("WARNING", f"⚠️ Insufficient {'Binance' if not PAPER_TRADING else 'Paper'} USDT to buy {symbol}")
        return None
        
    safe_trade_amount = trade_amount * 0.98
    qty = safe_trade_amount / current_price 
    return qty, trade_amount

def _evaluate_futures_trade_signal(state_manager: StateManager, symbol: str, current_price: float, signal: str, position_side: str, strategy_used: str, sl_target: float, tp_target: float, time_limit: int, adx_val, rsi_val, macd_histogram_val, atr_val, bb_width_val, dist_sma_200_val, vol_surge_val, market_regime_val="UNKNOWN"):
    try:
        control = get_bot_control()
        if _check_trading_paused(control, "futures", symbol, state_manager):
            return

        tech_data = _build_ai_tech_context(state_manager, symbol, strategy_used, adx_val, rsi_val, macd_histogram_val, atr_val, bb_width_val, dist_sma_200_val, vol_surge_val, market_regime_val, position_side, "futures")
        ai_result = analyze_sentiment(state_manager.latest_news, symbol, tech_data, market_type='futures')
        
        eval_res = _process_ai_evaluation(state_manager, symbol, ai_result, position_side, strategy_used, "futures")
        if not eval_res:
            return
        decision, risk_score, reason, ai_result_dict = eval_res
        
        if decision in ("PROCEED", "BUY", "SELL", signal) and risk_score <= 70:
            current_price = _check_slippage_guard(state_manager, symbol, current_price, "futures")
            if current_price is None:
                return
                
            log_msg("INFO", f"🚀 Executing {signal} ({position_side}) for {symbol} via {strategy_used} at {current_price}...")
            
            size_res = _calculate_futures_position_size(state_manager, symbol, ai_result_dict.get('allocation_percentage', 20), current_price)
            if not size_res:
                return
            qty, notional_value = size_res
            
            from .trade_executor import execute_futures_trade
            trade = execute_futures_trade(state_manager, symbol, signal, position_side, qty, current_price, reason=f"{strategy_used} + AI: {reason}", is_paper=PAPER_TRADING)
            
            if trade:
                send_discord_alert(f"🤖 **[FUTURES] Sniper Entry: {signal} {symbol}**\nReason: {reason}")
                state_manager.update_state(symbol, 
                    position=qty, buy_price=current_price, highest_price=current_price, lowest_price=current_price,
                    last_trade_time=datetime.now(timezone.utc), trade_entry_time=datetime.now(timezone.utc),
                    active_strategy=strategy_used, dynamic_sl=sl_target, dynamic_tp=tp_target, max_time_in_trade=time_limit,
                    position_side=position_side, ai_hold_cooldown_until=None
                )
            else:
                log_msg("WARNING", f"⚠️ Trade execution for {symbol} returned None (Aborted internally).", market_type="futures")
                state_manager.update_state(symbol, last_trade_time=None)
        else:
            if decision == "HOLD":
                log_msg("INFO", f"⚠️ AI explicitly requested HOLD for {symbol}. Aborting Futures {signal} and applying 45-Min cooldown.", market_type="futures")
            elif risk_score > 70:
                log_msg("INFO", f"⚠️ AI flagged high risk ({risk_score} > 70) for {symbol}. Aborting Futures {signal} and applying 45-Min cooldown.", market_type="futures")
            else:
                log_msg("INFO", f"⚠️ AI aborted Futures {signal} for {symbol} (Decision: {decision}, Risk: {risk_score}).", market_type="futures")
            state_manager.update_state(symbol, last_trade_time=datetime.now(timezone.utc), ai_hold_cooldown_until=datetime.now(timezone.utc) + timedelta(minutes=45), cooldown_start_price=current_price)
            
    except Exception as e:
        log_msg("ERROR", f"❌ Error in _evaluate_futures_trade_signal for {symbol}: {e}")

def _evaluate_buy_signal(state_manager: StateManager, symbol: str, current_price: float, strategy_used: str, sl_target: float, tp_target: float, time_limit: int, adx_val, rsi_val, macd_histogram_val, atr_val, bb_width_val, dist_sma_200_val, vol_surge_val, market_regime_val="UNKNOWN"):
    try:
        control = get_bot_control()
        if _check_trading_paused(control, "spot", symbol, state_manager):
            return

        states = state_manager.get_all_states()
        current_holding_value = sum(s.position * (s.last_price if s.last_price > 0 else s.buy_price) for s in states.values() if s.position > 0)
        
        if strategy_used == "SIDEWAYS_RSI_BB":
            from .binance_client import analyze_order_book_walls
            walls = analyze_order_book_walls(symbol)
            log_msg("INFO", f"Order Book Check for {symbol} - Largest Bid: {walls['largest_bid_price']}, Total Bid Vol: {walls.get('total_bid_qty', 0)}")

        tech_data = _build_ai_tech_context(state_manager, symbol, strategy_used, adx_val, rsi_val, macd_histogram_val, atr_val, bb_width_val, dist_sma_200_val, vol_surge_val, market_regime_val, "BUY", "spot")
        ai_result = analyze_sentiment(state_manager.latest_news, symbol, tech_data, market_type='spot')
        
        eval_res = _process_ai_evaluation(state_manager, symbol, ai_result, "BUY", strategy_used, "spot")
        if not eval_res:
            return
        decision, risk_score, reason, ai_result_dict = eval_res
        
        if decision in ("PROCEED", "BUY") and risk_score <= 60:
            current_price = _check_slippage_guard(state_manager, symbol, current_price, "spot")
            if current_price is None:
                return
                
            log_msg("INFO", f"🚀 Executing BUY for {symbol} via {strategy_used} at {current_price}...")
            
            size_res = _calculate_spot_position_size(state_manager, symbol, ai_result_dict.get('allocation_percentage', 20), current_price, current_holding_value)
            if not size_res:
                return
            qty, trade_amount = size_res
            
            trade = execute_trade(state_manager, symbol, "BUY", qty, current_price, reason=f"{strategy_used} + AI: {reason}", ai_risk=risk_score, is_paper=PAPER_TRADING)
            if trade:
                send_discord_alert(f"🤖 **[SPOT] Sniper Entry: BUY {symbol}**\nReason: {reason}")
                state_manager.add_to_balance(-trade_amount)
                state_manager.update_state(symbol, 
                    position=qty, buy_price=current_price, highest_price=current_price, lowest_price=current_price,
                    last_trade_time=datetime.now(timezone.utc), trade_entry_time=datetime.now(timezone.utc),
                    active_strategy=strategy_used, dynamic_sl=sl_target, dynamic_tp=tp_target, max_time_in_trade=time_limit
                )
            else:
                log_msg("WARNING", f"⚠️ Trade execution for {symbol} returned None (Aborted internally).", market_type="spot")
                state_manager.update_state(symbol, last_trade_time=None)
        else:
            if decision == "HOLD":
                log_msg("INFO", f"⚠️ AI explicitly requested HOLD for {symbol}. Aborting Spot BUY and applying Cooldown.", market_type="spot")
            elif risk_score > 60:
                log_msg("INFO", f"⚠️ AI flagged high risk ({risk_score} > 60) for {symbol}. Aborting Spot BUY and applying Cooldown.", market_type="spot")
            else:
                log_msg("INFO", f"⚠️ AI aborted Spot BUY for {symbol} (Risk {risk_score}, Decision: {decision}). Applying Cooldown.", market_type="spot")
            state_manager.update_state(symbol, last_trade_time=datetime.now(timezone.utc))
    except Exception as e:
        log_msg("ERROR", f"❌ Error in _evaluate_buy_signal for {symbol}: {sanitize_text(str(e))}")


def evaluate_strategy_for_symbol(state_manager: StateManager, symbol: str, df, current_price: float):
    try:
        update_bot_state(state_manager, f"Evaluating {symbol}...", symbol=symbol, market_type='spot')
        
        df = apply_indicators(df)
        signal_plan = analyze_market(df)
        
        signal = signal_plan.action
        strategy_used = signal_plan.strategy_used
        sl_target = signal_plan.stop_loss
        tp_target = signal_plan.take_profit
        time_limit = signal_plan.time_in_trade
        
        state = state_manager.get_state(symbol)
        
        if signal == "BUY" and state.position == 0:
            from .config import MAX_CONCURRENT_TRADES
            active_positions = sum(1 for s in state_manager.get_all_states().values() if s.position > 0)
            if active_positions >= MAX_CONCURRENT_TRADES:
                log_msg("DEBUG", f"🔒 Max Concurrent Trades ({MAX_CONCURRENT_TRADES}) reached. Skipping Spot {signal} for {symbol}.", market_type='spot')
                return

            if state.last_trade_time:
                time_since_trade = (datetime.now(timezone.utc) - state.last_trade_time).total_seconds() / 60
                if time_since_trade < COOLDOWN_MINUTES:
                    log_msg("DEBUG", f"⏳ {symbol} in cooldown. Skipping BUY signal.")
                    return

            if state_manager.live_usdt_balance < 10.0:
                log_msg("WARNING", f"⚠️ Insufficient Spot balance ({state_manager.live_usdt_balance}) to buy {symbol}. Skipping AI Evaluation.", market_type='spot')
                return

            update_bot_state(state_manager, f"BUY Signal on {symbol}. AI evaluating...", thinking=True, symbol=symbol, market_type='spot')
            
            latest_kline = df.iloc[-1]
            adx_val = latest_kline.get('ADX', 'N/A')
            rsi_val = latest_kline.get('RSI', 'N/A')
            macd_histogram_val = latest_kline.get('MACD_Histogram', 'N/A')
            atr_val = latest_kline.get('ATR', 'N/A')
            bb_width_val = latest_kline.get('Bollinger_Band_Width', 'N/A')
            dist_sma_200_val = latest_kline.get('Distance_to_SMA_200', 'N/A')
            vol_sma = latest_kline.get('SMA_20_Vol', 0)
            vol_surge_val = (latest_kline.get('volume', 0) / vol_sma) if vol_sma > 0 else 1.0
            
            # Dispatch to Priority Queue to prevent blocking websocket and prioritize explosive breakouts
            from .ai_queue import ai_queue_manager
            from .strategy import detect_regime
            market_regime_val = detect_regime(df)
            
            # Prevent Pyramiding: Lock the symbol by updating last_trade_time before async AI evaluation
            state_manager.update_state(symbol, last_trade_time=datetime.now(timezone.utc))
            
            ai_queue_manager.submit(
                vol_surge_val, symbol, _evaluate_buy_signal, 
                state_manager, symbol, current_price, strategy_used, sl_target, tp_target, time_limit, 
                adx_val, rsi_val, macd_histogram_val, atr_val, bb_width_val, dist_sma_200_val, vol_surge_val, market_regime_val
            )
            
        elif signal == "SELL" and state.position > 0:
            log_msg("INFO", f"📉 SELL Signal for {symbol} via {strategy_used}. Executing...")
            trade = execute_trade(state_manager, symbol, "SELL", state.position, current_price, reason=f"Strategy SELL: {strategy_used}", is_paper=PAPER_TRADING)
            if trade:
                pnl_pct = (trade.get("pnl_percent") if isinstance(trade, dict) else getattr(trade, "pnl_percent", 0.0)) or 0.0
                pnl_amt = (trade.get("pnl_amount") if isinstance(trade, dict) else getattr(trade, "pnl_amount", 0.0)) or 0.0
                if pnl_pct > 0:
                    send_discord_alert(f"🟢💰 **[TAKE PROFIT - WIN! 🏆] SPOT {symbol}** 🎯✨\n📉 Closed position via {strategy_used}\n💵 **Net Profit: +{pnl_pct:.2f}% (+{pnl_amt:.2f} USDT)** 🟢🚀")
                gross_return = state.position * current_price
                fee = gross_return * 0.001
                net_return = gross_return - fee
                state_manager.add_to_balance(net_return)
                state_manager.update_state(symbol, position=0.0, highest_price=0.0, active_strategy="NONE", last_trade_time=datetime.now(timezone.utc))
        else:
            # Added to give the user visual feedback that the bot is alive and evaluating
            if getattr(signal_plan, 'near_miss_reason', ""):
                log_msg("NEAR_MISS", f"[{symbol}] Near Miss ({strategy_used}): {signal_plan.near_miss_reason}")
            else:
                log_msg("INFO", f"🕯️ Evaluated {symbol} at {current_price:.4f} -> Result: HOLD")
    except Exception as e:
        log_msg("ERROR", f"❌ Error processing {symbol}: {sanitize_text(str(e))}")
        state_manager.update_state(symbol, last_trade_time=datetime.now(timezone.utc) - timedelta(minutes=COOLDOWN_MINUTES) + timedelta(minutes=5))

def evaluate_futures_strategy_for_symbol(state_manager: StateManager, symbol: str, df, current_price: float):
    try:
        from .strategy import analyze_futures_market
        from .trade_executor import execute_futures_trade
        
        update_bot_state(state_manager, f"Evaluating {symbol}...", symbol=symbol, market_type='futures')
        
        df = apply_indicators(df)
        signal_plan = analyze_futures_market(df)
        
        signal = signal_plan.action
        position_side = signal_plan.position_side
        strategy_used = signal_plan.strategy_used
        
        state = state_manager.get_state(symbol)
        
        # Futures logic now uses AI Council to prevent whipsaws
        if signal in ["BUY", "SELL"] and position_side:
            # Check if opening new position
            is_reversal = False
            if "LONG" in strategy_used or "SHORT" in strategy_used:
                if state.position > 0:
                    # Fix: Handle reversals - if we get an opposite signal, close the current position.
                    if ("SHORT" in strategy_used and state.position_side == "LONG") or \
                       ("LONG" in strategy_used and state.position_side == "SHORT"):
                        log_msg("INFO", f"📉 FUTURES REVERSAL EXIT for {symbol} via {strategy_used}...", market_type="futures")
                        exit_side = "SELL" if state.position_side == "LONG" else "BUY"
                        trade = execute_futures_trade(state_manager, symbol, exit_side, state.position_side, state.position, current_price, reason=f"Reversal: {strategy_used}", is_paper=PAPER_TRADING)
                        if trade:
                            from .binance_client import futures_cancel_all_orders
                            futures_cancel_all_orders(symbol)
                            profit_pct = (trade.get("pnl_percent") if isinstance(trade, dict) else getattr(trade, "pnl_percent", 0.0)) or 0.0
                            profit_amt = (trade.get("pnl_amount") if isinstance(trade, dict) else getattr(trade, "pnl_amount", 0.0)) or 0.0
                            if profit_pct > 0:
                                send_discord_alert(f"🟢💰 **[TAKE PROFIT - WIN! 🏆] FUTURES {symbol}** 🎯✨\n📉 Closed **{state.position_side}** via Reversal Exit\n💵 **Net Profit: +{profit_pct:.2f}% (+{profit_amt:.2f} USDT)** 🟢🚀")
                            if profit_amt:
                                state_manager.add_to_balance(profit_amt)
                            state_manager.update_state(symbol, position=0.0, highest_price=0.0, lowest_price=0.0, active_strategy="NONE", last_trade_time=datetime.now(timezone.utc), position_side="")
                            update_bot_state(state_manager, f"Reversal {exit_side} executed for {symbol}", symbol=symbol, market_type='futures')
                            is_reversal = True
                        else:
                            log_msg("ERROR", f"Reversal exit failed for {symbol}. Aborting new position.")
                            return
                            
                        # Now that the old position is closed, we MUST drop into the AI Council evaluation to open the new position.
                        # Do not return here. Allow it to fall through to the AI queue submission below.
                    else:
                        # We are already in a position in the SAME direction. Skip the new signal to prevent pyramiding.
                        log_msg("DEBUG", f"⏳ {symbol} already in {state.position_side} position. Skipping {signal} signal.", market_type='futures')
                        return
                        
                # OPENING a NEW position - Evaluate with AI Council
                # (Reversals also reach here after closing the old position above)
                from .config import MAX_CONCURRENT_TRADES
                active_positions = sum(1 for s in state_manager.get_all_states().values() if s.position > 0)
                if active_positions >= MAX_CONCURRENT_TRADES:
                    log_msg("DEBUG", f"🔒 Max Concurrent Trades ({MAX_CONCURRENT_TRADES}) reached. Skipping Futures {signal} for {symbol}.", market_type='futures')
                    return

                latest_kline = df.iloc[-1]
                vol_sma = latest_kline.get('SMA_20_Vol', 0)
                vol_surge_val = (latest_kline.get('volume', 0) / vol_sma) if vol_sma > 0 else 1.0
                atr_val = latest_kline.get('ATR', 0)
                
                if state.ai_hold_cooldown_until and datetime.now(timezone.utc) < state.ai_hold_cooldown_until:
                    price_diff = abs(current_price - state.cooldown_start_price)
                    if vol_surge_val > 3.0 or (atr_val > 0 and price_diff > 1.5 * atr_val):
                        log_msg("INFO", f"💥 Breakout Override! Bypassing {symbol} AI HOLD cooldown.", market_type='futures')
                    else:
                        log_msg("DEBUG", f"⏳ {symbol} in AI HOLD cooldown. Skipping Futures {signal} signal.", market_type='futures')
                        return
                        
                if state.last_trade_time and state.position == 0 and not is_reversal:
                    time_since_trade = (datetime.now(timezone.utc) - state.last_trade_time).total_seconds() / 60
                    if time_since_trade < COOLDOWN_MINUTES:
                        log_msg("DEBUG", f"⏳ {symbol} in execution cooldown. Skipping Futures {signal} signal.")
                        return

                if state_manager.live_usdt_balance < 5.0:
                    log_msg("WARNING", f"⚠️ Insufficient Futures balance ({state_manager.live_usdt_balance}) for {symbol}. Skipping AI Evaluation.", market_type='futures')
                    return

                update_bot_state(state_manager, f"{signal} {position_side} Signal on {symbol}. AI evaluating...", thinking=True, symbol=symbol, market_type='futures')
                
                latest_kline = df.iloc[-1]
                adx_val = latest_kline.get('ADX', 'N/A')
                rsi_val = latest_kline.get('RSI', 'N/A')
                macd_histogram_val = latest_kline.get('MACD_Histogram', 'N/A')
                bb_width_val = latest_kline.get('Bollinger_Band_Width', 'N/A')
                dist_sma_200_val = latest_kline.get('Distance_to_SMA_200', 'N/A')
                
                from .ai_queue import ai_queue_manager
                from .strategy import detect_regime
                market_regime_val = detect_regime(df)
                
                # Prevent Pyramiding: Lock the symbol by updating last_trade_time before async AI evaluation
                state_manager.update_state(symbol, last_trade_time=datetime.now(timezone.utc))
                
                ai_queue_manager.submit(
                    vol_surge_val, symbol, _evaluate_futures_trade_signal, 
                    state_manager, symbol, current_price, signal, position_side, strategy_used, 
                    signal_plan.stop_loss, signal_plan.take_profit, signal_plan.time_in_trade, 
                    adx_val, rsi_val, macd_histogram_val, atr_val, bb_width_val, dist_sma_200_val, vol_surge_val, market_regime_val
                )

            # Check if exiting position
            elif "EXIT" in strategy_used:
                if state.position > 0 and state.position_side == position_side:
                    log_msg("INFO", f"📉 FUTURES EXIT {signal} {position_side} for {symbol} via {strategy_used}...", market_type="futures")
                    trade = execute_futures_trade(state_manager, symbol, signal, position_side, state.position, current_price, reason=strategy_used, is_paper=PAPER_TRADING)
                    if trade:
                        from .binance_client import futures_cancel_all_orders
                        futures_cancel_all_orders(symbol)
                        profit_pct = (trade.get("pnl_percent") if isinstance(trade, dict) else getattr(trade, "pnl_percent", 0.0)) or 0.0
                        profit_amt = (trade.get("pnl_amount") if isinstance(trade, dict) else getattr(trade, "pnl_amount", 0.0)) or 0.0
                        if profit_pct > 0:
                            send_discord_alert(f"🟢💰 **[TAKE PROFIT - WIN! 🏆] FUTURES {symbol}** 🎯✨\n📉 Closed **{state.position_side}** via {strategy_used}\n💵 **Net Profit: +{profit_pct:.2f}% (+{profit_amt:.2f} USDT)** 🟢🚀")
                        if profit_amt:
                            state_manager.add_to_balance(profit_amt)
                        state_manager.update_state(symbol, position=0.0, highest_price=0.0, lowest_price=0.0, active_strategy="NONE", last_trade_time=datetime.now(timezone.utc), position_side="")
                        update_bot_state(state_manager, f"FUTURES EXIT executed for {symbol}", symbol=symbol, market_type='futures')
        else:
            if getattr(signal_plan, 'near_miss_reason', ""):
                log_msg("NEAR_MISS", f"[{symbol}] Futures Near Miss ({strategy_used}): {signal_plan.near_miss_reason}", market_type="futures")
            else:
                log_msg("INFO", f"🕯️ Evaluated Futures {symbol} at {current_price:.4f} -> Result: HOLD", market_type="futures")
            
            # Broadcast hold state explicitly so UI updates
            update_bot_state(state_manager, f"HOLD {symbol} (No Signal)", symbol=symbol, market_type='futures')
                
    except Exception as e:
        log_msg("ERROR", f"❌ Error processing futures {symbol}: {sanitize_text(str(e))}", market_type="futures")
