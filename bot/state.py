import threading
import json
import os
from dataclasses import dataclass, replace, asdict, fields
from datetime import datetime, timezone
from typing import Dict, Optional

from .config import SYMBOLS, PAPER_TRADING, FUTURES_LEVERAGE
from .binance_client import get_live_asset_balance, get_current_price, futures_get_position, futures_get_live_balance, get_all_spot_balances, client
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
    lowest_price: float = 0.0
    position_side: str = "" # "LONG" or "SHORT" for futures
    ai_hold_cooldown_until: datetime | None = None
    cooldown_start_price: float = 0.0

class StateManager:
    def __init__(self, market_type: str = 'spot'):
        self.market_type = market_type
        self._lock = threading.Lock()
        self._states: Dict[str, SymbolState] = {sym: SymbolState(sym) for sym in SYMBOLS}
        self._live_usdt_balance = 1000.0 if PAPER_TRADING else 0.0
        self._kline_buffers = {}
        self._latest_news = "No recent news available."
        self._funding_rates: Dict[str, float] = {}
        self._long_short_ratios: Dict[str, float] = {}
        self._liquidations: Dict[str, dict] = {}
        self._order_book_walls: Dict[str, dict] = {}
        self._fear_greed_index: str = "Neutral (50)"
        self._state_file = f"bot_internal_state_{market_type}.json"
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
                            if s_data.get("ai_hold_cooldown_until"):
                                s_data["ai_hold_cooldown_until"] = datetime.fromisoformat(s_data["ai_hold_cooldown_until"])
                            valid_keys = {f.name for f in fields(self._states[sym])}
                            filtered_data = {k: v for k, v in s_data.items() if k in valid_keys}
                            self._states[sym] = replace(self._states[sym], **filtered_data)
                log_msg("INFO", f"Successfully loaded internal {self.market_type} state.")
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
                if s_dict.get("ai_hold_cooldown_until"):
                    s_dict["ai_hold_cooldown_until"] = s_dict["ai_hold_cooldown_until"].isoformat()
                data[sym] = s_dict
            tmp_file = f"{self._state_file}.tmp"
            with open(tmp_file, "w") as f:
                json.dump(data, f)
            os.replace(tmp_file, self._state_file)
        except Exception as e:
            log_msg("ERROR", f"Failed to save internal state: {e}")

    def get_state(self, symbol: str) -> SymbolState:
        with self._lock:
            if symbol not in self._states:
                self._states[symbol] = SymbolState(symbol)
            return self._states[symbol]

    def update_state(self, symbol: str, **kwargs):
        with self._lock:
            if symbol not in self._states:
                self._states[symbol] = SymbolState(symbol)
            self._states[symbol] = replace(self._states[symbol], **kwargs)
            if any(k not in ['last_price', 'highest_price', 'lowest_price'] for k in kwargs):
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

    @property
    def fear_greed_index(self) -> str:
        with self._lock:
            return self._fear_greed_index

    @fear_greed_index.setter
    def fear_greed_index(self, value: str):
        with self._lock:
            self._fear_greed_index = value

    def get_funding_rate(self, symbol: str) -> float:
        with self._lock:
            return self._funding_rates.get(symbol, 0.0)

    def set_funding_rate(self, symbol: str, rate: float):
        with self._lock:
            self._funding_rates[symbol] = rate

    def get_long_short_ratio(self, symbol: str) -> float:
        with self._lock:
            return self._long_short_ratios.get(symbol, 1.0)

    def set_long_short_ratio(self, symbol: str, ratio: float):
        with self._lock:
            self._long_short_ratios[symbol] = ratio

    def get_liquidations(self, symbol: str) -> dict:
        with self._lock:
            return self._liquidations.get(symbol, {})

    def set_liquidations(self, symbol: str, liq: dict):
        with self._lock:
            self._liquidations[symbol] = liq

    def get_order_book(self, symbol: str) -> dict:
        with self._lock:
            return self._order_book_walls.get(symbol, {})

    def set_order_book(self, symbol: str, ob: dict):
        with self._lock:
            self._order_book_walls[symbol] = ob
            
    def get_kline_buffer(self, symbol: str):
        with self._lock:
            return self._kline_buffers.get(symbol)
            
    def set_kline_buffer(self, symbol: str, df):
        with self._lock:
            self._kline_buffers[symbol] = df
            
    def get_all_kline_buffers(self):
        with self._lock:
            return self._kline_buffers.copy()

    def sync_spot_state_with_binance(self, calculate_pnl_func):
        if PAPER_TRADING:
            return

        all_spot_balances = get_all_spot_balances() or {}
        usdt_bal = all_spot_balances.get("USDT", get_live_asset_balance("USDT"))
        
        new_states = {}
        
        for symbol in list(self._states.keys()):
            with self._lock:
                state = self._states[symbol]
                
            current_price = state.last_price if state.last_price > 0 else get_current_price(symbol)
            asset = symbol.replace("USDT", "")
            
            real_bal = all_spot_balances.get(asset, 0.0)
            value = real_bal * current_price
            is_manual_sell = (state.position > 0 and real_bal < state.position * 0.5)
            is_dust = (value < 5.0 and state.position == 0)
            
            if is_dust or is_manual_sell:
                if state.position > 0 and is_manual_sell:
                    log_msg("WARNING", f"Detected manual SELL or dust for {symbol} (Spot). Syncing state.", market_type='spot')
                    pnl_amount, pnl_percent = calculate_pnl_func(state.buy_price, current_price, state.position, market_type='spot')
                    from .database import TradeRepository
                    TradeRepository.create_trade(
                        symbol, "SELL", current_price, state.position, None, "Startup Sync / Manual Sell", PAPER_TRADING,
                        0.0, "USDT", pnl_amount, pnl_percent, market_type='spot'
                    )
                new_states[symbol] = replace(state, position=0.0, buy_price=0.0, highest_price=0.0, lowest_price=0.0, position_side="")
            else:
                if state.buy_price == 0.0:
                    from .database import TradeRepository
                    db_price = TradeRepository.get_last_buy_price(symbol, market_type='spot')
                    if db_price > 0:
                        new_states[symbol] = replace(state, position=real_bal, buy_price=db_price, position_side="")
                    else:
                        new_states[symbol] = replace(state, position=real_bal, buy_price=current_price, position_side="")
                else:
                    new_states[symbol] = replace(state, position=real_bal, position_side="")
                    
        with self._lock:
            if usdt_bal is not None:
                self._live_usdt_balance = usdt_bal
            for symbol, st in new_states.items():
                current = self._states[symbol]
                if st.position == 0.0:
                    self._states[symbol] = replace(
                        current, position=0.0, buy_price=0.0, highest_price=0.0, lowest_price=0.0, position_side=""
                    )
                else:
                    self._states[symbol] = replace(
                        current, position=st.position, buy_price=st.buy_price, position_side=""
                    )
            self._save_state()

    def sync_futures_state_with_binance(self, calculate_pnl_func):
        if PAPER_TRADING:
            return

        usdt_bal = futures_get_live_balance("USDT")
        all_futures_positions = {}
        
        try:
            positions_res = client.futures_position_information()
            for pos in positions_res:
                all_futures_positions[pos['symbol']] = pos
        except Exception as e:
            log_msg("ERROR", f"Failed to fetch futures positions: {e}", market_type='futures')
            
        new_states = {}
        
        for symbol in list(self._states.keys()):
            with self._lock:
                state = self._states[symbol]
                
            current_price = state.last_price if state.last_price > 0 else get_current_price(symbol)
            
            pos_info = all_futures_positions.get(symbol)
            if pos_info is None:
                pos_info = {"positionAmt": "0", "entryPrice": "0", "positionSide": ""}
                
            amt = float(pos_info.get("positionAmt", "0"))
            entry_price = float(pos_info.get("entryPrice", "0"))
            pos_side = pos_info.get("positionSide", "LONG" if amt > 0 else ("SHORT" if amt < 0 else ""))
            
            real_bal = abs(amt)
            
            if real_bal < 0.0001:
                from .database import SessionLocalFutures, Trade
                db = SessionLocalFutures()
                try:
                    last_trade = db.query(Trade).filter(Trade.symbol == symbol, Trade.market_type == 'futures').order_by(Trade.timestamp.desc(), Trade.id.desc()).first()
                    
                    is_open = False
                    if last_trade:
                        is_open = (last_trade.position_side == "LONG" and last_trade.side == "BUY") or \
                                  (last_trade.position_side == "SHORT" and last_trade.side == "SELL")
                                  
                    if is_open:
                        log_msg("WARNING", f"Missing native close trade detected for {symbol} (Futures). Syncing state.", market_type='futures')
                        b_trades = client.futures_account_trades(symbol=symbol, limit=100)
                        close_side = "SELL" if last_trade.position_side == "LONG" else "BUY"
                        
                        agg_qty = 0.0
                        agg_pnl = 0.0
                        agg_fee = 0.0
                        last_price = 0.0
                        fee_asset = "USDT"
                        ts = None
                        
                        for bt in reversed(b_trades):
                            bt_ts = datetime.fromtimestamp(bt['time'] / 1000.0, timezone.utc)
                            last_trade_ts = last_trade.timestamp
                            if last_trade_ts.tzinfo is None:
                                last_trade_ts = last_trade_ts.replace(tzinfo=timezone.utc)
                            if bt['side'] == close_side and bt_ts > last_trade_ts:
                                agg_qty += float(bt['qty'])
                                agg_pnl += float(bt.get('realizedPnl', 0))
                                agg_fee += float(bt['commission'])
                                last_price = float(bt['price'])
                                fee_asset = bt['commissionAsset']
                                if ts is None or bt_ts > ts:
                                    ts = bt_ts
                                
                        if agg_qty > 0:
                            margin = (last_trade.price * agg_qty) / FUTURES_LEVERAGE
                            pnl_pct = (agg_pnl / margin * 100) if margin > 0 else 0.0
                            
                            new_t = Trade(
                                symbol=symbol, side=close_side, price=last_price, quantity=agg_qty, market_type='futures',
                                position_side=last_trade.position_side, ai_reasoning="Binance Native SL/TP (Auto-Sync)",
                                pnl_amount=agg_pnl, pnl_percent=pnl_pct, fee=agg_fee, fee_asset=fee_asset, timestamp=ts
                            )
                            db.add(new_t)
                            db.commit()
                            log_msg("INFO", f"Synced missing close trade for {symbol} at avg price ~{last_price}", market_type='futures')
                        else:
                            log_msg("ERROR", f"Could not find matching close trade on Binance for {symbol}! Inserting fallback to prevent loop.", market_type='futures')
                            new_t = Trade(
                                symbol=symbol, side=close_side, price=last_trade.price, quantity=last_trade.quantity, market_type='futures',
                                position_side=last_trade.position_side, ai_reasoning="Binance Native SL/TP (Fallback - Not Found)",
                                pnl_amount=0.0, pnl_percent=0.0, fee=0.0, fee_asset='USDT', timestamp=datetime.now(timezone.utc)
                            )
                            db.add(new_t)
                            db.commit()
                except Exception as e:
                    log_msg("ERROR", f"Error syncing missing trade for {symbol}: {e}", market_type='futures')
                finally:
                    db.close()
                    
                new_states[symbol] = replace(state, position=0.0, buy_price=0.0, highest_price=0.0, lowest_price=0.0, position_side="")
            elif real_bal * current_price < 5.0 and state.position == 0:
                new_states[symbol] = replace(state, position=0.0, buy_price=0.0, highest_price=0.0, lowest_price=0.0, position_side="")
            else:
                new_states[symbol] = replace(state, position=real_bal, buy_price=entry_price, position_side=pos_side)
                
        with self._lock:
            if usdt_bal is not None:
                self._live_usdt_balance = usdt_bal
            for symbol, st in new_states.items():
                current = self._states[symbol]
                if st.position == 0.0:
                    self._states[symbol] = replace(
                        current, position=0.0, buy_price=0.0, highest_price=0.0, lowest_price=0.0, position_side=""
                    )
                else:
                    self._states[symbol] = replace(
                        current, position=st.position, buy_price=st.buy_price, position_side=st.position_side
                    )
            self._save_state()

    def sync_state_with_binance(self, calculate_pnl_func):
        """Legacy dispatcher."""
        if self.market_type == "futures":
            self.sync_futures_state_with_binance(calculate_pnl_func)
        else:
            self.sync_spot_state_with_binance(calculate_pnl_func)
