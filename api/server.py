from fastapi import FastAPI, Depends, HTTPException, Security
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
import os
import json
import hashlib

from bot.database import get_db, Trade
from bot.binance_client import get_live_asset_balance

app = FastAPI(title="AI Trading Dashboard")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

api_key_header = APIKeyHeader(name="Authorization", auto_error=False)

def get_auth_token():
    user = os.getenv("DASHBOARD_USER", "admin")
    pwd = os.getenv("DASHBOARD_PASS", "admin")
    return hashlib.sha256(f"{user}:{pwd}:AI_SECRET".encode()).hexdigest()

def verify_token(api_key_header: str = Security(api_key_header)):
    if not api_key_header or api_key_header != f"Bearer {get_auth_token()}":
        raise HTTPException(status_code=401, detail="Invalid token")
    return True

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/api/login")
def login(req: LoginRequest):
    if req.username == os.getenv("DASHBOARD_USER") and req.password == os.getenv("DASHBOARD_PASS"):
        return {"token": get_auth_token()}
    raise HTTPException(status_code=401, detail="Invalid credentials")

class TradeSchema(BaseModel):
    id: int
    symbol: str
    side: str
    price: float
    quantity: float
    timestamp: str
    ai_risk_score: float | None = None
    ai_reasoning: str | None = None
    paper_trade: bool

    class Config:
        from_attributes = True

@app.on_event("startup")
def on_startup():
    from bot.database import Base, engine
    Base.metadata.create_all(bind=engine)

@app.get("/api/trades", response_model=List[TradeSchema])
def read_trades(skip: int = 0, limit: int = 50, db: Session = Depends(get_db), auth: bool = Depends(verify_token)):
    trades = db.query(Trade).order_by(Trade.timestamp.desc()).offset(skip).limit(limit).all()
    # Ensure correct dict/object format for pydantic
    formatted_trades = []
    for t in trades:
        t_dict = {
            "id": t.id,
            "symbol": t.symbol,
            "side": t.side,
            "price": t.price,
            "quantity": t.quantity,
            "timestamp": t.timestamp.isoformat(),
            "ai_risk_score": t.ai_risk_score,
            "ai_reasoning": t.ai_reasoning,
            "paper_trade": t.paper_trade
        }
        formatted_trades.append(t_dict)
    return formatted_trades

@app.get("/api/status")
def get_status(auth: bool = Depends(verify_token)):
    bot_state = {"status_message": "Waiting for bot to start...", "is_thinking": False, "live_usdt": 0.0}
    try:
        if os.path.exists("bot_state.json"):
            with open("bot_state.json", "r", encoding="utf-8") as f:
                bot_state = json.load(f)
    except (OSError, json.JSONDecodeError):
        pass
        
    return {
        "status": "online",
        "symbols": ["BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT", "BNBUSDT"],
        "paper_trading": os.getenv("PAPER_TRADING", "True"),
        "live_usdt": bot_state.get("live_usdt", 0.0),
        "ai_status": bot_state
    }

# Mount dashboard static files
app.mount("/", StaticFiles(directory="dashboard", html=True), name="dashboard")

# Run with: uvicorn api.server:app --reload
