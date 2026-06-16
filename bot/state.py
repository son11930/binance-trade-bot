import threading
import json
import os
from dataclasses import dataclass, replace, asdict
from datetime import datetime
from typing import Dict, Optional

from .config import SYMBOLS, PAPER_TRADING
from .binance_client import get_live_asset_balance, get_current_price
from .database import TradeRepository
from .logger import log_msg

@dataclass(frozen=True)
class SymbolState:
    symbol: str
    position: float = 0.0
    buy_price: float = 0.0
    last_trade_time: datetime | None = None
    trade_entry_time: datetime | None = None
    active_strategy: str = "NONE"
    dynamic_sl: float = 0.0
    dynamic_tp: float = 0.0
    max_time_in_trade: int = 0
    last_price: float = 0.0
    highest_price: float = 0.0

class StateManager:
    def __init__(self):
        self._lock = threading.Lock()
        self._states: Dict[str, SymbolState] = {sym: SymbolState(sym) for sym in SYMBOLS}
        self._live_usdt_balance = 1000.0 if PAPER_TRADING else 0.0
        self._kline_buffers = {}
        self._latest_news = "No recent news available."
        self._state_file = "bot_internal_state.json"
        self._load_state()

    def _load_state(self):
        if os.path.exists(self._state_file):
            try:
                with open(self._state_file, "r") as f:
                    data = json.load(f)
                    for sym, s_data in data.items():
                        if sym in self._states:
                            if s_data.get("last_trade_time"):
                                s_data["last_trade_time"] = datetime.fromisoformat(s_data["last_trade_time"])
                            if s_data.get("trade_entry_time"):
                                s_data["trade_entry_time"] = datetime.fromisoformat(s_data["trade_entry_time"])
                            self._states[sym] = replace(self._states[sym], **s_data)
                log_msg("INFO", "✅ Successfully loaded internal bot state.")
            except Exception as e:
                log_msg("ERROR", f"Failed to load internal state: {e}")

    def _save_state(self):
        try:
            data = {}
            for sym, state in self._states.items():
                s_dict = asdict(state)
                if s_dict["last_trade_time"]:
                    s_dict["last_trade_time"] = s_dict["last_trade_time"].isoformat()
                if s_dict["trade_entry_time"]:
                    s_dict["trade_entry_time"] = s_dict["trade_entry_time"].isoformat()
                data[sym] = s_dict
            with open(self._state_file, "w") as f:
                json.dump(data, f)
        except Exception as e:
            log_msg("ERROR", f"Failed to save internal state: {e}")

    def get_state(self, symbol: str) -> SymbolState:
        with self._lock:
            return self._states.get(symbol, SymbolState(symbol))

    def update_state(self, symbol: str, **kwargs):
        with self._lock:
            if symbol in self._states:
                self._states[symbol] = replace(self._states[symbol], **kwargs)
                self._save_state()

    def get_all_states(self) -> Dict[str, SymbolState]:
        with self._lock:
            return self._states.copy()

    @property
    def live_usdt_balance(self) -> float:
        with self._lock:
            return self._live_usdt_balance

    @live_usdt_balance.setter
    def live_usdt_balance(self, value: float):
        with self._lock:
            self._live_usdt_balance = value

    def add_to_balance(self, amount: float):
        with self._lock:
            self._live_usdt_balance += amount

    @property
    def latest_news(self) -> str:
        with self._lock:
            return self._latest_news

    @latest_news.setter
    def latest_news(self, value: str):
        with self._lock:
            self._latest_news = value
            
    def get_kline_buffer(self, symbol: str):
        with self._lock:
            return self._kline_buffers.get(symbol)
            
    def set_kline_buffer(self, symbol: str, df):
        with self._lock:
            self._kline_buffers[symbol] = df
            
    def get_all_kline_buffers(self):
        with self._lock:
            return self._kline_buffers.copy()

    def sync_state_with_binance(self, calculate_pnl_func):
        with self._lock:
            if not PAPER_TRADING:
                bal = get_live_asset_balance("USDT")
                if bal is not None:
                    self._live_usdt_balance = bal

            if PAPER_TRADING:
                return
                
            for symbol in SYMBOLS:
                state = self._states[symbol]
                asset = symbol.replace("USDT", "")
                real_bal = get_live_asset_balance(asset)
                
                if real_bal is None:
                    log_msg("WARNING", f"⚠️ Skipping sync for {symbol} due to API error.")
                    continue
                    
                current_price = state.last_price if state.last_price > 0 else get_current_price(symbol)
                    
                if real_bal * current_price < 2.0:
                    if state.position > 0:
                        log_msg("WARNING", f"⚠️ Detected manual SELL for {symbol}. Syncing state.")
                        pnl_amount, pnl_percent = calculate_pnl_func(state.buy_price, current_price, state.position)
                        TradeRepository.create_trade(
                            symbol, "SELL", current_price, state.position, None, "Manual SELL", PAPER_TRADING,
                            0.0, "USDT", pnl_amount, pnl_percent
                        )
                    self._states[symbol] = replace(state, position=0.0, buy_price=0.0, highest_price=0.0)
                else:
                    if state.buy_price == 0.0:
                        db_price = TradeRepository.get_last_buy_price(symbol)
                        bp = db_price if db_price > 0 else current_price
                        if db_price == 0:
                            log_msg("WARNING", f"⚠️ Manual BUY detected for {symbol} or DB missing. Using current price as baseline.")
                        self._states[symbol] = replace(state, position=real_bal, buy_price=bp)
                    else:
                        self._states[symbol] = replace(state, position=real_bal)
