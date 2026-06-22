import json
import os
import threading

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTROL_FILE = os.path.join(BASE_DIR, "bot_control.json")
_lock = threading.Lock()

def get_bot_control():
    with _lock:
        if not os.path.exists(CONTROL_FILE):
            default_state = {"spot_paused": False, "futures_paused": False}
            try:
                with open(CONTROL_FILE, "w") as f:
                    json.dump(default_state, f)
            except Exception:
                pass
            return default_state
        try:
            with open(CONTROL_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {"spot_paused": False, "futures_paused": False}

def set_bot_control(spot_paused=None, futures_paused=None):
    with _lock:
        current_state = {"spot_paused": False, "futures_paused": False}
        if os.path.exists(CONTROL_FILE):
            try:
                with open(CONTROL_FILE, "r") as f:
                    current_state = json.load(f)
            except Exception:
                pass
        
        if spot_paused is not None:
            current_state["spot_paused"] = spot_paused
        if futures_paused is not None:
            current_state["futures_paused"] = futures_paused
            
        try:
            tmp_file = f"{CONTROL_FILE}.tmp"
            with open(tmp_file, "w") as f:
                json.dump(current_state, f)
            os.replace(tmp_file, CONTROL_FILE)
        except Exception:
            pass
