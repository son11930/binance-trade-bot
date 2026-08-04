import json
import os
import threading

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTROL_FILE = os.path.join(BASE_DIR, "bot_control.json")
_lock = threading.Lock()

def get_bot_control():
    with _lock:
        if not os.path.exists(CONTROL_FILE):
            default_state = {"spot_paused": False, "futures_paused": False, "allow_live": False, "paper_trading": True}
            try:
                with open(CONTROL_FILE, "w") as f:
                    json.dump(default_state, f)
            except Exception:
                pass
            return default_state
        try:
            with open(CONTROL_FILE, "r") as f:
                state = json.load(f)
                # Apply defaults for old files
                if "allow_live" not in state: state["allow_live"] = False
                if "paper_trading" not in state: state["paper_trading"] = True
                return state
        except Exception:
            return {"spot_paused": False, "futures_paused": False, "allow_live": False, "paper_trading": True}

def set_bot_control(spot_paused=None, futures_paused=None, allow_live=None, paper_trading=None):
    with _lock:
        current_state = {"spot_paused": False, "futures_paused": False, "allow_live": False, "paper_trading": True}
        if os.path.exists(CONTROL_FILE):
            try:
                with open(CONTROL_FILE, "r") as f:
                    data = json.load(f)
                    current_state.update(data)
            except Exception:
                pass
        
        if spot_paused is not None:
            current_state["spot_paused"] = spot_paused
        if futures_paused is not None:
            current_state["futures_paused"] = futures_paused
        if allow_live is not None:
            current_state["allow_live"] = allow_live
        if paper_trading is not None:
            current_state["paper_trading"] = paper_trading
            
        try:
            tmp_file = f"{CONTROL_FILE}.tmp"
            with open(tmp_file, "w") as f:
                json.dump(current_state, f)
            os.replace(tmp_file, CONTROL_FILE)
        except Exception:
            pass
