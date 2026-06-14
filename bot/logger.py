from .database import LogRepository, sanitize_text

def log_msg(level: str, msg: str):
    safe_msg = sanitize_text(msg)
    print(safe_msg)
    LogRepository.log_event(level, safe_msg)
