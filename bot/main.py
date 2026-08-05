import time
import threading

from .config import SYMBOLS, is_paper_trading, FUTURES_LEVERAGE, FUTURES_MARGIN_TYPE
from .state import StateManager
from .database import setup_logging
from .logger import log_msg
from .binance_client import get_historical_klines, futures_get_klines, twm, futures_set_leverage, futures_set_margin_type, futures_set_position_mode
from .market_context_worker import market_context_updater_loop
from .websocket_manager import WebSocketManager
from .webhook_notifier import update_bot_state
from .risk_manager import calculate_pnl
from .opportunity_tracker import track_opportunities
from .global_memory_agent import generate_global_memory
from .context import ExecutionContext
from .strategy_manager import get_active_strategy
from .control import get_bot_control, set_bot_control

setup_logging()

def main():
    log_msg("INFO", "Starting Multi-Coin Dual-Engine Bot (Spot & Futures)...")
    
    # Configure Futures settings on real account
    if not is_paper_trading():
        log_msg("INFO", f"Setting up Futures Margin ({FUTURES_MARGIN_TYPE}) and Leverage ({FUTURES_LEVERAGE}x)...", market_type='futures')
        futures_set_position_mode(is_paper=False)
        for sym in SYMBOLS:
            futures_set_margin_type(sym, FUTURES_MARGIN_TYPE, is_paper=False)
            futures_set_leverage(sym, FUTURES_LEVERAGE, is_paper=False)
            
    # Initialize Spot States
    state_manager_spot_paper = StateManager(market_type='spot', execution_mode='PAPER')
    state_manager_spot_live = StateManager(market_type='spot', execution_mode='LIVE')
    state_manager_spot_paper.sync_state_with_binance(calculate_pnl)
    state_manager_spot_live.sync_state_with_binance(calculate_pnl)
    
    # Initialize Futures States
    state_manager_futures_paper = StateManager(market_type='futures', execution_mode='PAPER')
    state_manager_futures_live = StateManager(market_type='futures', execution_mode='LIVE')
    state_manager_futures_paper.sync_state_with_binance(calculate_pnl)
    state_manager_futures_live.sync_state_with_binance(calculate_pnl)
    
    all_managers = [state_manager_spot_paper, state_manager_spot_live, state_manager_futures_paper, state_manager_futures_live]
    
    # Clear any stuck evaluating states from previous crashes
    for sym in SYMBOLS:
        for sm in all_managers:
            st = sm.get_state(sym)
            if st.active_strategy in ["EVALUATING", "CLOSING"]:
                sm.update_state(sym, active_strategy="NONE")
    
    # Fetch initial history for Spot
    log_msg("INFO", "Fetching initial Spot 30m history...")
    for sym in SYMBOLS:
        klines = get_historical_klines(sym, "30m", limit=250)
        state_manager_spot_paper.set_kline_buffer(sym, klines)
        state_manager_spot_live.set_kline_buffer(sym, klines)
        
    # Fetch initial history for Futures
    log_msg("INFO", "Fetching initial Futures 30m history...", market_type='futures')
    for sym in SYMBOLS:
        f_klines = futures_get_klines(sym, "30m", limit=250)
        state_manager_futures_paper.set_kline_buffer(sym, f_klines)
        state_manager_futures_live.set_kline_buffer(sym, f_klines)
        
    # Start background threads (Shared news)
    threading.Thread(target=market_context_updater_loop, args=(all_managers,), daemon=True).start()
    
    # Start auto-sync background thread
    def auto_sync_loop():
        import time
        from .binance_client import client
        from .control import set_bot_control
        
        while True:
            time.sleep(60) # Sync every 1 minute
            try:
                # 1. API Clock Drift Kill Switch
                server_time_ms = client.time().get('serverTime', 0)
                local_time_ms = int(time.time() * 1000)
                drift_ms = abs(server_time_ms - local_time_ms)
                
                if drift_ms > 3000: # 3 seconds drift
                    reason = f"🚨 FATAL: Clock drift detected ({drift_ms}ms). System time is out of sync with Binance. Halting to prevent signature errors."
                    log_msg("ERROR", reason)
                    set_bot_control(spot_paused=True, futures_paused=True, pause_reason=reason)
                    continue
                    
                # 2. Sync positions
                for sm in all_managers:
                    sm.sync_state_with_binance(calculate_pnl)
            except Exception as e:
                log_msg("ERROR", f"Auto-sync failed: {e}")
                
    threading.Thread(target=auto_sync_loop, daemon=True).start()
    
    # Phase 8: Reconciliation Loop
    def reconciliation_loop():
        import time
        from .binance_client import futures_account_balance
        from .discord import send_discord_alert
        from .config import is_paper_trading
        
        while True:
            # Reconcile every 4 hours (14400 seconds)
            time.sleep(14400)
            if is_paper_trading():
                continue
                
            try:
                actual_balance = futures_account_balance()
                if actual_balance is None:
                    continue
                
                # Compare with Futures state manager
                f_sm = next((sm for sm in all_managers if sm.market_type == 'futures'), None)
                if not f_sm:
                    continue
                    
                local_balance = f_sm.get_balance()
                diff = abs(actual_balance - local_balance)
                
                status_str = f"OK (Local: ${local_balance:.2f} | Binance: ${actual_balance:.2f})"
                if diff > max(1.0, 0.001 * local_balance):
                    status_str = f"MISMATCH: ${diff:.2f} diff (Local: ${local_balance:.2f} | Binance: ${actual_balance:.2f})"
                    log_msg("ERROR", f"🚨 RECONCILIATION {status_str}", market_type="futures")
                    send_discord_alert(f"🚨 **RECONCILIATION MISMATCH**\n{status_str}\nPossible missing fills, slippage drift, or unaccounted funding fees.")
                else:
                    log_msg("INFO", f"✅ Reconciliation {status_str}", market_type="futures")
                    
                # Update global bot state via f_sm or direct json
                import json
                from .config import DATA_DIR
                import os
                state_file = os.path.join(DATA_DIR, 'bot_state.json')
                if os.path.exists(state_file):
                    try:
                        with open(state_file, 'r') as f:
                            state_data = json.load(f)
                        state_data['reconciliation_status'] = status_str
                        with open(state_file, 'w') as f:
                            json.dump(state_data, f, indent=4)
                    except Exception as json_e:
                        log_msg("ERROR", f"Failed to save reconciliation status: {json_e}")
                        
            except Exception as e:
                log_msg("ERROR", f"Reconciliation loop failed: {e}")
                
    threading.Thread(target=reconciliation_loop, daemon=True).start()
    
    # Start AI Learning background threads
    def opportunity_tracker_loop():
        import time
        while True:
            # Sleep 1 hour between checks
            time.sleep(3600)
            try:
                log_msg("INFO", "Running AI Opportunity Tracker...")
                track_opportunities()
            except Exception as e:
                log_msg("ERROR", f"Opportunity Tracker failed: {e}")

    def global_memory_loop():
        import time
        from datetime import datetime, timezone, timedelta
        
        log_msg("INFO", "AI Market Briefing scheduler started. Will trigger at 00:00 and 12:00 BKK time.")
        while True:
            now_utc = datetime.now(timezone.utc)
            now_local = now_utc + timedelta(hours=7)
            
            # Check if it is exactly 12:00 or 00:00 (allowing a 1-minute window)
            if (now_local.hour == 0 or now_local.hour == 12) and now_local.minute == 0:
                try:
                    log_msg("INFO", "Triggering AI Market Briefing...")
                    generate_global_memory()
                except Exception as e:
                    log_msg("ERROR", f"Global Memory generation failed: {e}")
                
                # Sleep for 65 seconds to ensure we don't trigger twice in the same minute
                time.sleep(65)
            else:
                # Poll every 30 seconds
                time.sleep(30)

    threading.Thread(target=opportunity_tracker_loop, daemon=True).start()
    threading.Thread(target=global_memory_loop, daemon=True).start()
    
    def central_trading_loop():
        import time
        from datetime import datetime
        from .signal_evaluator import evaluate_all_spot_strategies_single_pass, evaluate_all_futures_strategies_single_pass
        
        log_msg("INFO", "Central Trading Clock started. Evaluates at xx:00:02 and xx:30:02")
        while True:
            now = datetime.now()
            if now.minute in (0, 30) and now.second == 2:
                log_msg("INFO", f"⏰ Central Clock Triggered at {now.strftime('%H:%M:%S')}. Running Single-Pass evaluations...")
                
                from .config import SYMBOLS, is_paper_trading
                
                # Phase 0A: Build ExecutionContext and validate state
                strat = get_active_strategy()
                ctrl = get_bot_control()
                
                if strat:
                    manifest_stage = strat.get("stage", "PAPER")
                    exec_mode = "PAPER" if is_paper_trading() else "LIVE"
                    
                    if manifest_stage != exec_mode:
                        log_msg("ERROR", f"CRITICAL SECURITY ALERT: Config execution mode ({exec_mode}) does not match Manifest stage ({manifest_stage}). Failsafe triggered: PAUSING bot.")
                        set_bot_control(spot_paused=True, futures_paused=True)
                        time.sleep(2)
                        continue
                        
                    context = ExecutionContext(
                        execution_mode=exec_mode,
                        deployment_id=strat.get("id", "unknown_deployment"),
                        strategy_id=strat.get("name", "unknown_strategy"),
                        version=strat.get("version", "1.0.0")
                    )
                else:
                    exec_mode = "PAPER" if is_paper_trading() else "LIVE"
                    context = ExecutionContext(
                        execution_mode=exec_mode,
                        deployment_id="default_deployment",
                        strategy_id="default_strategy",
                        version="1.0.0"
                    )
                
                if exec_mode == "PAPER":
                    active_spot_manager = state_manager_spot_paper
                    active_futures_manager = state_manager_futures_paper
                else:
                    active_spot_manager = state_manager_spot_live
                    active_futures_manager = state_manager_futures_live
                
                # Run evaluations in separate threads so we don't block the clock
                threading.Thread(target=evaluate_all_futures_strategies_single_pass, args=(active_futures_manager, SYMBOLS, context), daemon=True).start()
                threading.Thread(target=evaluate_all_spot_strategies_single_pass, args=(active_spot_manager, SYMBOLS, context), daemon=True).start()
                
                # Sleep for 2 seconds to avoid triggering multiple times within the same second
                time.sleep(2)
            else:
                # Sleep 0.5s to be precise and not miss the 2nd second mark
                time.sleep(0.5)

    threading.Thread(target=central_trading_loop, daemon=True).start()
    
    # Initialize WebSocket Managers
    ws_manager_spot_paper = WebSocketManager(state_manager_spot_paper, market_type='spot')
    ws_manager_spot_live = WebSocketManager(state_manager_spot_live, market_type='spot')
    ws_manager_futures_paper = WebSocketManager(state_manager_futures_paper, market_type='futures')
    ws_manager_futures_live = WebSocketManager(state_manager_futures_live, market_type='futures')
    
    # Start ThreadedWebsocketManager
    twm.start()
    
    # Subscribe to streams using multiplexing
    spot_streams = []
    futures_streams = []
    for sym in SYMBOLS:
        sym_lower = sym.lower()
        spot_streams.append(f"{sym_lower}@ticker")
        spot_streams.append(f"{sym_lower}@kline_30m")
        futures_streams.append(f"{sym_lower}@ticker")
        futures_streams.append(f"{sym_lower}@kline_30m")
    
    # Start Spot Multiplex Streams
    def route_spot_message(msg):
        ws_manager_spot_paper.process_ticker_message(msg)
        ws_manager_spot_paper.process_kline_message(msg)
        ws_manager_spot_live.process_ticker_message(msg)
        ws_manager_spot_live.process_kline_message(msg)
        
    twm.start_multiplex_socket(callback=route_spot_message, streams=spot_streams)
    
    # Start Futures Multiplex Streams
    def route_futures_message(msg):
        ws_manager_futures_paper.process_ticker_message(msg)
        ws_manager_futures_paper.process_kline_message(msg)
        ws_manager_futures_live.process_ticker_message(msg)
        ws_manager_futures_live.process_kline_message(msg)
        
    try:
        if hasattr(twm, 'start_futures_multiplex_socket'):
            twm.start_futures_multiplex_socket(callback=route_futures_message, streams=futures_streams)
        else:
            log_msg("ERROR", "python-binance ThreadedWebsocketManager does not support start_futures_multiplex_socket", market_type='futures')
    except Exception as e:
        log_msg("ERROR", f"Failed to start futures multiplex socket: {e}", market_type='futures')
        
    log_msg("INFO", "WebSocket streams active. Waiting for candle closes...")
    # Initial state broadcast
    update_bot_state(state_manager_spot_paper, "Waiting for next candle close...", symbol="All", market_type='spot')
    update_bot_state(state_manager_futures_paper, "Waiting for next candle close...", symbol="All", market_type='futures')
    
    import signal
    import sys

    def shutdown_handler(signum, frame):
        log_msg("INFO", "Shutting down bot safely, saving states...")
        for sm in all_managers:
            sm._save_state()
        log_msg("INFO", "States saved. Stopping WebSocket...")
        twm.stop()
        log_msg("INFO", "Bot stopped safely.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)
    
    reconnect_attempt = 0
    reconnect_time = 0.0
    while True:
        time.sleep(2)
        
        last_msgs = [
            ws_manager_spot_paper.last_message_time, ws_manager_spot_live.last_message_time,
            ws_manager_futures_paper.last_message_time, ws_manager_futures_live.last_message_time
        ]
        time_since_last_msg = time.time() - min(last_msgs)
        if reconnect_time > 0 and time.time() - reconnect_time < 45.0 and time_since_last_msg > 45.0:
            pass
        elif not twm.is_alive() or time_since_last_msg > 45.0:
            reconnect_attempt += 1
            backoff_delay = min(60, 5 * (2 ** min(reconnect_attempt, 5)))
            log_msg("WARNING", f"WebSocket stream unhealthy (alive={twm.is_alive()}, silence={time_since_last_msg:.1f}s). Reconnecting in {backoff_delay}s (Attempt {reconnect_attempt})...")
            
            try:
                twm.stop()
            except Exception:
                pass
            
            time.sleep(backoff_delay)
            
            try:
                from binance import ThreadedWebsocketManager
                import bot.binance_client as bc
                twm = ThreadedWebsocketManager()
                bc.twm = twm
                twm.start()
                twm.start_multiplex_socket(callback=route_spot_message, streams=spot_streams)
                if hasattr(twm, 'start_futures_multiplex_socket'):
                    twm.start_futures_multiplex_socket(callback=route_futures_message, streams=futures_streams)
                reconnect_time = time.time()
                log_msg("INFO", "WebSocket re-connected cleanly.")
            except Exception as e:
                log_msg("ERROR", f"Failed to re-initialize WebSocket: {e}")
                if reconnect_attempt >= 6:
                    log_msg("ERROR", "CRITICAL: Multiple reconnect attempts failed. Restarting bot process...")
                    import os
                    os.execv(sys.executable, ['python'] + sys.argv)
        else:
            if reconnect_attempt > 0 and min(last_msgs) > reconnect_time and time_since_last_msg < 15.0:
                reconnect_attempt = 0
                reconnect_time = 0.0

        try:
            from .config import is_paper_trading
            if is_paper_trading():
                update_bot_state(state_manager_spot_paper, "Monitoring Spot markets...", symbol="All", market_type='spot')
                update_bot_state(state_manager_futures_paper, "Monitoring Futures markets...", symbol="All", market_type='futures')
            else:
                update_bot_state(state_manager_spot_live, "Monitoring Spot markets...", symbol="All", market_type='spot')
                update_bot_state(state_manager_futures_live, "Monitoring Futures markets...", symbol="All", market_type='futures')
        except Exception as e:
            log_msg("ERROR", f"Error updating bot state: {e}")

if __name__ == "__main__":
    main()
