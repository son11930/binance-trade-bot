import os
import json
import hashlib
import asyncio
import logging
import secrets
import time
from datetime import timezone
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Security, WebSocket
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List, Dict
from dotenv import load_dotenv

from bot.database import get_db, Trade, init_db, SystemLog, SessionLocal

load_dotenv()

USER = os.getenv("DASHBOARD_USER", "admin")
PASS = os.getenv("DASHBOARD_PASS", "admin")
SECRET_SALT = os.getenv("DASHBOARD_SECRET_SALT", "AI_SECRET_DEFAULT")
AUTH_TOKEN = hashlib.sha256(f"{USER}:{PASS}:{SECRET_SALT}".encode()).hexdigest()

class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[WebSocket, bool] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[websocket] = False # Unauthenticated initially

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            del self.active_connections[websocket]

    async def authenticate(self, websocket: WebSocket, token: str) -> bool:
        if token and secrets.compare_digest(token, AUTH_TOKEN):
            self.active_connections[websocket] = True
            return True
        return False

    async def broadcast(self, message: dict):
        for ws, is_auth in list(self.active_connections.items()):
            if is_auth:
                try:
                    await ws.send_json(message)
                except Exception:
                    self.disconnect(ws)

manager = ConnectionManager()

def get_trade_stats(db: Session):
    trades = db.query(Trade).filter(Trade.side == 'SELL').all()
    cumulative_pnl = 0.0
    wins = 0
    losses = 0
    total_closed = 0
    for t in trades:
        if t.pnl_amount is not None:
            cumulative_pnl += t.pnl_amount
            if t.pnl_amount > 0:
                wins += 1
            elif t.pnl_amount < 0:
                losses += 1
            total_closed += 1
    win_rate = (wins / total_closed * 100) if total_closed > 0 else 0.0
    return {
        "cumulative_pnl": cumulative_pnl,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate
    }

def format_trade(t):
    return {
        "id": t.id,
        "symbol": t.symbol,
        "side": t.side,
        "price": t.price,
        "quantity": t.quantity,
        "timestamp": t.timestamp.replace(tzinfo=timezone.utc).isoformat() if hasattr(t.timestamp, 'isoformat') else t.timestamp,
        "ai_risk_score": t.ai_risk_score,
        "ai_reasoning": t.ai_reasoning,
        "paper_trade": t.paper_trade,
        "fee": getattr(t, 'fee', None),
        "fee_asset": getattr(t, 'fee_asset', None),
        "pnl_amount": getattr(t, 'pnl_amount', None),
        "pnl_percent": getattr(t, 'pnl_percent', None)
    }

def format_log(l):
    return {
        "id": l.id,
        "timestamp": l.timestamp.replace(tzinfo=timezone.utc).isoformat() if hasattr(l.timestamp, 'isoformat') else l.timestamp,
        "level": l.level,
        "message": l.message
    }

def get_bot_status():
    bot_state = {"status_message": "Bot is offline (Not running)", "is_thinking": False, "live_usdt": 0.0}
    try:
        if os.path.exists("tmp/bot_state.json"):
            # Check if file is older than 3 minutes (180 seconds)
            if time.time() - os.path.getmtime("tmp/bot_state.json") < 180:
                with open("tmp/bot_state.json", "r", encoding="utf-8") as f:
                    bot_state = json.load(f)
            else:
                bot_state["status_message"] = "Bot is offline (Not running)"
    except (OSError, json.JSONDecodeError):
        pass
        
    return {
        "status": "online",
        "symbols": ["BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT", "BNBUSDT"],
        "paper_trading": os.getenv("PAPER_TRADING", "True"),
        "live_usdt": bot_state.get("live_usdt", 0.0),
        "ai_status": bot_state
    }

async def background_broadcaster():
    last_mtime = 0
    last_trade_id = -1
    last_log_id = -1
    
    while True:
        try:
            if not any(manager.active_connections.values()):
                await asyncio.sleep(2)
                continue

            current_mtime = 0
            if os.path.exists("tmp/bot_state.json"):
                current_mtime = os.path.getmtime("tmp/bot_state.json")
            
            db = SessionLocal()
            try:
                trades = db.query(Trade).order_by(Trade.timestamp.desc()).limit(50).all()
                logs = db.query(SystemLog).order_by(SystemLog.timestamp.desc()).limit(50).all()
                
                current_trade_id = trades[0].id if trades else 0
                current_log_id = logs[0].id if logs else 0
                
                trades_data = [format_trade(t) for t in trades]
                logs_data = [format_log(l) for l in logs]
            finally:
                db.close()
                
            # Broadcast if status changed
            if current_mtime != last_mtime:
                last_mtime = current_mtime
                await manager.broadcast({"type": "status_update", "data": get_bot_status()})
                
            # Broadcast if trades changed
            if current_trade_id != last_trade_id:
                last_trade_id = current_trade_id
                await manager.broadcast({"type": "trades_update", "data": trades_data})
                db_stats = SessionLocal()
                try:
                    stats_data = get_trade_stats(db_stats)
                    await manager.broadcast({"type": "stats_update", "data": stats_data})
                finally:
                    db_stats.close()
                
            # Broadcast if logs changed
            if current_log_id != last_log_id:
                last_log_id = current_log_id
                await manager.broadcast({"type": "logs_update", "data": logs_data})
            
        except Exception:
            logging.exception("Background broadcaster error")
            
        await asyncio.sleep(2)

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    task = asyncio.create_task(background_broadcaster())
    yield
    task.cancel()

app = FastAPI(title="AI Trading Dashboard", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

class LoginRequest(BaseModel):
    username: str
    password: str

@app.post("/api/login")
def login(req: LoginRequest):
    user = os.getenv("DASHBOARD_USER", "admin")
    pwd = os.getenv("DASHBOARD_PASS", "admin")
    if secrets.compare_digest(req.username, user) and secrets.compare_digest(req.password, pwd):
        return {"token": AUTH_TOKEN}
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        auth_msg = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
        if auth_msg.get("type") == "auth" and await manager.authenticate(websocket, auth_msg.get("token")):
            await websocket.send_json({"type": "status_update", "data": get_bot_status()})
            db = SessionLocal()
            try:
                trades = db.query(Trade).order_by(Trade.timestamp.desc()).limit(50).all()
                logs = db.query(SystemLog).order_by(SystemLog.timestamp.desc()).limit(50).all()
                
                trades_data = [format_trade(t) for t in trades]
                logs_data = [format_log(l) for l in logs]
            finally:
                db.close()
                
            await websocket.send_json({"type": "trades_update", "data": trades_data})
            await websocket.send_json({"type": "logs_update", "data": logs_data})
            
            db_stats = SessionLocal()
            try:
                stats_data = get_trade_stats(db_stats)
                await websocket.send_json({"type": "stats_update", "data": stats_data})
            finally:
                db_stats.close()
            
            while True:
                await websocket.receive_text()
        else:
            await websocket.close(code=1008)
    except Exception:
        manager.disconnect(websocket)
        
def verify_token(api_key_header: str = Security(APIKeyHeader(name="Authorization", auto_error=False))):
    if not api_key_header or not secrets.compare_digest(api_key_header, f"Bearer {AUTH_TOKEN}"):
        raise HTTPException(status_code=401, detail="Invalid token")
    return True

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
    fee: float | None = None
    fee_asset: str | None = None
    pnl_amount: float | None = None
    pnl_percent: float | None = None

    class Config:
        from_attributes = True

@app.get("/api/trades", response_model=List[TradeSchema])
def read_trades(skip: int = 0, limit: int = 50, db: Session = Depends(get_db), auth: bool = Depends(verify_token)):
    trades = db.query(Trade).order_by(Trade.timestamp.desc()).offset(skip).limit(limit).all()
    result = []
    for t in trades:
        t_dict = t.__dict__.copy()
        if hasattr(t.timestamp, 'isoformat'):
            t_dict['timestamp'] = t.timestamp.replace(tzinfo=timezone.utc).isoformat()
        result.append(t_dict)
    return result

@app.get("/api/status")
def status(auth: bool = Depends(verify_token)):
    return get_bot_status()

app.mount("/", StaticFiles(directory="dashboard", html=True), name="dashboard")
