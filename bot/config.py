import os
import hashlib
import hmac
from dotenv import load_dotenv

load_dotenv()

SYMBOLS = ["BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT", "BNBUSDT", "ADAUSDT", "AVAXUSDT", "DOTUSDT", "LINKUSDT", "TRXUSDT", "TONUSDT", "BCHUSDT", "NEARUSDT", "SUIUSDT", "APTUSDT", "ARBUSDT", "OPUSDT", "INJUSDT", "RNDRUSDT", "ATOMUSDT"]
QUANTITY_USDT = float(os.getenv("TRADE_QUANTITY_USDT", "10.0"))
PAPER_TRADING = os.getenv("PAPER_TRADING", "True").lower() == "true"
COOLDOWN_MINUTES = int(os.getenv("COOLDOWN_MINUTES", "15"))
STOP_LOSS_PERCENT = float(os.getenv("STOP_LOSS_PERCENT", "2.5"))
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "http://127.0.0.1:8000/api/internal/broadcast")

USER = os.getenv("DASHBOARD_USER")
PASS = os.getenv("DASHBOARD_PASS")
SECRET_SALT = os.getenv("DASHBOARD_SECRET_SALT")

if not USER or not PASS or not SECRET_SALT:
    raise ValueError("CRITICAL SECURITY ERROR: DASHBOARD_USER, DASHBOARD_PASS, and DASHBOARD_SECRET_SALT must be set in .env")

WEBHOOK_TOKEN = hmac.new(SECRET_SALT.encode(), f"{USER}_webhook".encode(), hashlib.sha256).hexdigest()
