import os
import json
import logging
from typing import Dict, Any

_MANIFEST_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard", "data", "strategy_manifest.json")
_cached_strategy = None
_last_mtime = 0

def get_active_strategy() -> Dict[str, Any]:
    global _cached_strategy, _last_mtime
    
    if not os.path.exists(_MANIFEST_PATH):
        return {}
        
    try:
        current_mtime = os.path.getmtime(_MANIFEST_PATH)
        if current_mtime > _last_mtime or _cached_strategy is None:
            with open(_MANIFEST_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                active = data.get("active_strategy", {})
                
                # Check if it has a valid stage and parameters
                if active.get("stage") in ["PAPER", "LIVE"] and active.get("parameters"):
                    _cached_strategy = active
                    logging.info(f"Loaded new strategy manifest: {active.get('name')} [{active.get('stage')}]")
                else:
                    _cached_strategy = {}
                    
            _last_mtime = current_mtime
            
        return _cached_strategy
    except Exception as e:
        logging.error(f"Error reading strategy manifest: {e}")
        return _cached_strategy or {}
