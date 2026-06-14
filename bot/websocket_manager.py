import pandas as pd
from datetime import datetime, timezone
from typing import Dict

from .state import StateManager
from .config import STOP_LOSS_PERCENT, PAPER_TRADING
from .risk_manager import check_risk_management
from .trade_executor import execute_trade
from .signal_evaluator import evaluate_strategy_for_symbol
from .logger import log_msg

class WebSocketManager:
    def __init__(self, state_manager: StateManager):
        self.state_manager = state_manager

    def process_ticker_message(self, msg: Dict):
        if msg.get('e') == '24hrTicker':
            sym = msg['s']
            self.state_manager.update_state(sym, last_price=float(msg['c']))

    def update_kline_buffer(self, symbol: str, k: Dict):
        df = self.state_manager.get_kline_buffer(symbol)
        if df is None:
            return None
        
        msg_timestamp = pd.to_datetime(k['t'], unit='ms')
        last_timestamp = df['timestamp'].iloc[-1]
        
        if msg_timestamp == last_timestamp:
            df.loc[df.index[-1], ['open', 'high', 'low', 'close', 'volume']] = [
                float(k['o']), float(k['h']), float(k['l']), float(k['c']), float(k['v'])
            ]
        elif msg_timestamp > last_timestamp:
            new_row = pd.DataFrame([{
                'timestamp': msg_timestamp,
                'open': float(k['o']),
                'high': float(k['h']),
                'low': float(k['l']),
                'close': float(k['c']),
                'volume': float(k['v'])
            }])
            new_df = pd.concat([df, new_row], ignore_index=True).tail(250)
            self.state_manager.set_kline_buffer(symbol, new_df)
            df = new_df
        return df

    def process_kline_message(self, msg: Dict):
        if msg['e'] != 'kline':
            return
            
        symbol = msg['s']
        k = msg['k']
        is_closed = k['x']
        current_price = float(k['c'])
        
        # Update local buffer
        df = self.update_kline_buffer(symbol, k)
        if df is None:
            return
        
        # 1. Constant Risk Management
        state = self.state_manager.get_state(symbol)
        if state.position > 0:
            highest = max(state.highest_price, current_price)
            self.state_manager.update_state(symbol, last_price=current_price, highest_price=highest)
            state = self.state_manager.get_state(symbol) # Update local ref
            
            atr_value = 2.5
            if not df.empty and 'ATR' in df.columns:
                atr_value = df.iloc[-1]['ATR']
                
            rm_signal = check_risk_management(state, atr_value, STOP_LOSS_PERCENT)
            if rm_signal:
                log_msg("WARNING", f"🚨 {rm_signal} TRIGGERED for {symbol} at {current_price}!")
                trade = execute_trade(self.state_manager, symbol, "SELL", state.position, current_price, reason=rm_signal, is_paper=PAPER_TRADING)
                if trade:
                    gross_return = state.position * current_price
                    fee = gross_return * 0.001
                    net_return = gross_return - fee
                    self.state_manager.add_to_balance(net_return)
                    self.state_manager.update_state(symbol, position=0.0, highest_price=0.0, active_strategy="NONE", last_trade_time=datetime.now(timezone.utc))
                    
        # 2. Strategy evaluation on candle close
        if is_closed:
            evaluate_strategy_for_symbol(self.state_manager, symbol, df, current_price)
