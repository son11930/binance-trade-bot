import os
import hashlib
import hmac
from dotenv import load_dotenv

load_dotenv()

SYMBOLS = ["WIFUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT", "TRXUSDT", "DOGEUSDT", "BCHUSDT", "NEARUSDT", "SUIUSDT", "APTUSDT", "ARBUSDT", "OPUSDT", "INJUSDT", "RENDERUSDT", "ATOMUSDT"]
QUANTITY_USDT = float(os.getenv("TRADE_QUANTITY_USDT", "10.0"))
FUTURES_QUANTITY_USDT = float(os.getenv("FUTURES_QUANTITY_USDT", "10.0"))
FUTURES_LEVERAGE = int(os.getenv("FUTURES_LEVERAGE", "3"))
FUTURES_MARGIN_TYPE = os.getenv("FUTURES_MARGIN_TYPE", "ISOLATED")

# PAPER_TRADING is now dynamically managed by Web UI (bot_control.json)
def is_paper_trading():
    from .control import get_bot_control
    return get_bot_control().get("paper_trading", True)

# Removed static PAPER_TRADING constant to enforce dynamic evaluation

COOLDOWN_MINUTES = int(os.getenv("COOLDOWN_MINUTES", "15"))
MAX_CONCURRENT_TRADES = int(os.getenv("MAX_CONCURRENT_TRADES", "5"))
STOP_LOSS_PERCENT = float(os.getenv("STOP_LOSS_PERCENT", "2.5"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "http://127.0.0.1:8000/api/internal/broadcast")

# Risk Management Settings (Phase 7)
MAX_RISK_PER_TRADE_PCT = float(os.getenv("MAX_RISK_PER_TRADE_PCT", "0.005"))
MAX_PORTFOLIO_HEAT_PCT = float(os.getenv("MAX_PORTFOLIO_HEAT_PCT", "0.03"))
MAX_DAILY_LOSS_PCT = float(os.getenv("MAX_DAILY_LOSS_PCT", "0.02"))
MAX_WEEKLY_LOSS_PCT = float(os.getenv("MAX_WEEKLY_LOSS_PCT", "0.04"))
HARD_EQUITY_DRAWDOWN_KILL_PCT = float(os.getenv("HARD_EQUITY_DRAWDOWN_KILL_PCT", "0.10"))
MAX_CONSECUTIVE_LOSSES = int(os.getenv("MAX_CONSECUTIVE_LOSSES", "5"))
MAX_DAILY_TRADES = int(os.getenv("MAX_DAILY_TRADES", "15"))

DATABASE_URL_SPOT = os.getenv("DATABASE_URL_SPOT", os.getenv("DATABASE_URL", "sqlite:///./trades_spot.db"))
DATABASE_URL_FUTURES = os.getenv("DATABASE_URL_FUTURES", os.getenv("DATABASE_URL", "sqlite:///./trades_futures.db"))

USER = os.getenv("DASHBOARD_USER")
PASS = os.getenv("DASHBOARD_PASS")
SECRET_SALT = os.getenv("DASHBOARD_SECRET_SALT")

if not USER or not PASS or not SECRET_SALT:
    raise ValueError("CRITICAL SECURITY ERROR: DASHBOARD_USER, DASHBOARD_PASS, and DASHBOARD_SECRET_SALT must be set in .env")

WEBHOOK_TOKEN = hmac.new(SECRET_SALT.encode(), f"{USER}_webhook".encode(), hashlib.sha256).hexdigest()
