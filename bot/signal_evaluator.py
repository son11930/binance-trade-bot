import threading
from datetime import datetime, timedelta, timezone

from .strategy import apply_indicators, analyze_market
from .ai_engine import analyze_sentiment
from .database import sanitize_text
from .logger import log_msg
from .config import PAPER_TRADING, COOLDOWN_MINUTES
from .trade_executor import execute_trade
from .webhook_notifier import update_bot_state
from .binance_client import get_current_price
from .state import StateManager

def _evaluate_buy_signal(state_manager: StateManager, symbol: str, current_price: float, strategy_used: str, sl_target: float, tp_target: float, time_limit: int, adx_val, rsi_val, macd_histogram_val, atr_val, bb_width_val, dist_sma_200_val, vol_surge_val):
    try:
        # Calculate holding value dynamically at the time of evaluation, not at queue time
        states = state_manager.get_all_states()
        current_holding_value = sum(s.position * (s.last_price if s.last_price > 0 else get_current_price(s.symbol)) for s in states.values() if s.position > 0)
        
        if strategy_used == "SIDEWAYS_RSI_BB":
            from .binance_client import analyze_order_book_walls
            walls = analyze_order_book_walls(symbol)
            log_msg("INFO", f"Order Book Check for {symbol} - Largest Bid: {walls['largest_bid_price']}, Total Bid Vol: {walls.get('total_bid_qty', 0)}")

        tech_data = {
            "strategy_used": strategy_used,
            "adx": adx_val,
            "rsi": rsi_val,
            "macd_histogram": macd_histogram_val,
            "atr": atr_val,
            "bb_width": bb_width_val,
            "dist_sma_200": dist_sma_200_val,
            "vol_surge_multiplier": vol_surge_val
        }
        
        latest_news = state_manager.latest_news
        ai_result = analyze_sentiment(latest_news, symbol, tech_data)
        
        if not isinstance(ai_result, dict):
            log_msg("WARNING", f"⚠️ Invalid AI response for {symbol}. Aborting trade.")
            return
            
        decision = ai_result.get('decision')
        risk_score = ai_result.get('risk_score')
        reason = str(ai_result.get('reason', 'No reason provided'))[:255]
        committee_debate = ai_result.get('committee_debate', {})
        
        if risk_score is None or not isinstance(risk_score, (int, float)):
            risk_score = 100
            
        ai_debate_payload = {
            "symbol": symbol,
            "strategy": strategy_used,
            "bull": sanitize_text(committee_debate.get("bullish_analysis", "")),
            "bear": sanitize_text(committee_debate.get("bearish_analysis", "")),
            "chief_reason": sanitize_text(reason),
            "decision": decision,
            "risk_score": risk_score
        }
            
        update_bot_state(state_manager, f"AI: {decision} {symbol} (Risk: {risk_score})", symbol=symbol, ai_debate=ai_debate_payload)
        
        if decision == "BUY" and risk_score <= 60:
            # --- Slippage Guard (Mitigation 4) ---
            live_price = get_current_price(symbol)
            if live_price is not None:
                slippage = (live_price - current_price) / current_price
                if slippage > 0.005:  # Price drifted more than 0.5% while waiting for AI
                    log_msg("WARNING", f"⚠️ Slippage Guard: Aborting {symbol} trade. Price moved +{slippage*100:.2f}% ({current_price} -> {live_price}) while waiting for AI.")
                    update_bot_state(state_manager, f"Aborted: Slippage >0.5%", symbol=symbol)
                    state_manager.update_state(symbol, last_trade_time=datetime.now(timezone.utc))
                    return
                # Update current_price to live_price for accurate execution tracking
                current_price = live_price
            # -------------------------------------
                
            log_msg("INFO", f"🚀 Executing BUY for {symbol} via {strategy_used} at {current_price}...")
            
            allocation_percentage = ai_result.get('allocation_percentage', 20)
            if not isinstance(allocation_percentage, (int, float)):
                allocation_percentage = 20
            
            if allocation_percentage < 10:
                allocation_percentage = 10
            elif allocation_percentage > 40:
                allocation_percentage = 40
                
            live_usdt_balance = state_manager.live_usdt_balance
            total_equity = live_usdt_balance + current_holding_value
            trade_amount = total_equity * (allocation_percentage / 100.0)
            if trade_amount < 10.0: trade_amount = 10.0
            if trade_amount > live_usdt_balance: trade_amount = live_usdt_balance
            
            if live_usdt_balance < 10.0 or live_usdt_balance < trade_amount:
                log_msg("WARNING", f"⚠️ Insufficient {'Binance' if not PAPER_TRADING else 'Paper'} USDT to buy {symbol}")
                return
                
            safe_trade_amount = trade_amount * 0.999 # 0.1% fee simulation
            qty = safe_trade_amount / current_price 
            
            trade = execute_trade(state_manager, symbol, "BUY", qty, current_price, reason=f"{strategy_used} + AI: {reason}", ai_risk=risk_score, is_paper=PAPER_TRADING)
            if trade:
                state_manager.add_to_balance(-trade_amount)

                state_manager.update_state(symbol, 
                    position=qty, 
                    buy_price=current_price, 
                    highest_price=current_price, 
                    last_trade_time=datetime.now(timezone.utc),
                    trade_entry_time=datetime.now(timezone.utc),
                    active_strategy=strategy_used,
                    dynamic_sl=sl_target,
                    dynamic_tp=tp_target,
                    max_time_in_trade=time_limit
                )
        else:
            log_msg("INFO", f"⚠️ AI aborted BUY for {symbol} (Risk {risk_score}). Applying cooldown.")
            state_manager.update_state(symbol, last_trade_time=datetime.now(timezone.utc))
    except Exception as e:
        log_msg("ERROR", f"❌ Error in _evaluate_buy_signal for {symbol}: {e}")


def evaluate_strategy_for_symbol(state_manager: StateManager, symbol: str, df, current_price: float):
    try:
        update_bot_state(state_manager, f"Evaluating {symbol}...", symbol=symbol)
        
        df = apply_indicators(df)
        signal_plan = analyze_market(df)
    
        states = state_manager.get_all_states()
        current_holding_value = sum(s.position * (s.last_price if s.last_price > 0 else get_current_price(s.symbol)) for s in states.values() if s.position > 0)
        
        signal = signal_plan.action
        strategy_used = signal_plan.strategy_used
        sl_target = signal_plan.stop_loss
        tp_target = signal_plan.take_profit
        time_limit = signal_plan.time_in_trade
        
        state = state_manager.get_state(symbol)
        
        if signal == "BUY" and state.position == 0:
            time_since_trade = (datetime.now(timezone.utc) - state.last_trade_time).total_seconds() / 60
            if time_since_trade < COOLDOWN_MINUTES:
                log_msg("DEBUG", f"⏳ {symbol} in cooldown. Skipping BUY signal.")
                return

            update_bot_state(state_manager, f"BUY Signal on {symbol}. AI evaluating...", thinking=True, symbol=symbol)
            
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
            ai_queue_manager.submit(
                vol_surge_val, symbol, _evaluate_buy_signal, 
                state_manager, symbol, current_price, strategy_used, sl_target, tp_target, time_limit, 
                adx_val, rsi_val, macd_histogram_val, atr_val, bb_width_val, dist_sma_200_val, vol_surge_val
            )
            
        elif signal == "SELL" and state.position > 0:
            log_msg("INFO", f"📉 SELL Signal for {symbol} via {strategy_used}. Executing...")
            trade = execute_trade(state_manager, symbol, "SELL", state.position, current_price, reason=f"Strategy SELL: {strategy_used}", is_paper=PAPER_TRADING)
            if trade:
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
        log_msg("ERROR", f"❌ Error processing {symbol}: {e}")
        state_manager.update_state(symbol, last_trade_time=datetime.now(timezone.utc) - timedelta(minutes=COOLDOWN_MINUTES) + timedelta(minutes=5))
