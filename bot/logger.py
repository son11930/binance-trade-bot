from .database import LogRepository, sanitize_text

def log_msg(level: str, msg: str, market_type: str = 'spot'):
    safe_msg = sanitize_text(msg)
    prefix = f"[{market_type.upper()}] " if market_type == 'futures' else ""
    print(prefix + safe_msg)
    LogRepository.log_event(level, safe_msg, market_type=market_type)
