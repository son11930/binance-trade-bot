import os
import hashlib
import asyncio
import logging
import secrets
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Security, WebSocket, WebSocketDisconnect
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from pydantic import BaseModel
from typing import Dict
from fastapi.concurrency import run_in_threadpool
from dotenv import load_dotenv

from bot.database import Trade, init_db, SystemLog, SessionLocal, setup_logging

load_dotenv()
setup_logging()

USER = os.getenv("DASHBOARD_USER")
PASS = os.getenv("DASHBOARD_PASS")
SECRET_SALT = os.getenv("DASHBOARD_SECRET_SALT")

if not USER or not PASS or not SECRET_SALT:
    raise ValueError("CRITICAL SECURITY ERROR: DASHBOARD_USER, DASHBOARD_PASS, and DASHBOARD_SECRET_SALT must be set in .env")

AUTH_TOKEN = hashlib.sha256(f"{USER}:{PASS}:{SECRET_SALT}".encode()).hexdigest()
WEBHOOK_TOKEN = hashlib.sha256(f"{USER}:{PASS}:{SECRET_SALT}_webhook".encode()).hexdigest()

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

def get_stats_for_period(db: Session, start_time=None):
    query = db.query(
        func.sum(Trade.pnl_amount).label('cumulative_pnl'),
        func.sum(case((Trade.pnl_amount > 0, 1), else_=0)).label('wins'),
        func.sum(case((Trade.pnl_amount < 0, 1), else_=0)).label('losses'),
        func.count(Trade.id).label('total_closed'),
        func.sum(case((Trade.pnl_amount != None, (Trade.price * Trade.quantity) - Trade.pnl_amount), else_=0)).label('cumulative_capital')
    ).filter(Trade.side == 'SELL')
    
    if start_time:
        query = query.filter(Trade.timestamp >= start_time)
        
    result = query.first()
    
    cumulative_pnl = result.cumulative_pnl or 0.0
    wins = int(result.wins or 0)
    losses = int(result.losses or 0)
    total_closed = int(result.total_closed or 0)
    cumulative_capital = result.cumulative_capital or 0.0
    
    win_rate = (wins / total_closed * 100) if total_closed > 0 else 0.0
    pnl_percent = (cumulative_pnl / cumulative_capital * 100) if cumulative_capital > 0 else 0.0
    
    return {
        "cumulative_pnl": cumulative_pnl,
        "pnl_percent": pnl_percent,
        "wins": wins,
        "losses": losses,
        "win_rate": win_rate
    }

def get_trade_stats(db: Session):
    now = datetime.now(timezone.utc)
    return {
        "1D": get_stats_for_period(db, now - timedelta(days=1)),
        "7D": get_stats_for_period(db, now - timedelta(days=7)),
        "1M": get_stats_for_period(db, now - timedelta(days=30)),
        "ALL": get_stats_for_period(db, None)
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

latest_bot_state = {"status_message": "Bot is offline (Not running)", "is_thinking": False, "live_usdt": 0.0, "positions": []}

def get_bot_status():
    return {
        "status": "online",
        "symbols": ["BTCUSDT", "ETHUSDT", "XRPUSDT", "SOLUSDT", "BNBUSDT"],
        "paper_trading": os.getenv("PAPER_TRADING", "True"),
        "live_usdt": latest_bot_state.get("live_usdt", 0.0),
        "ai_status": latest_bot_state
    }

@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield

app = FastAPI(title="AI Trading Dashboard", lifespan=lifespan)

def get_db_updates():
    db = SessionLocal()
    try:
        trades = db.query(Trade).order_by(Trade.timestamp.desc()).limit(50).all()
        logs = db.query(SystemLog).order_by(SystemLog.timestamp.desc()).limit(50).all()
        
        trades_data = [format_trade(t) for t in trades]
        logs_data = [format_log(l) for l in logs]
        stats_data = get_trade_stats(db)
        
        return trades_data, logs_data, stats_data
    except Exception:
        logging.exception("Broadcast DB error")
        return [], [], {}
    finally:
        db.close()

def verify_token(api_key_header: str = Security(APIKeyHeader(name="Authorization", auto_error=False))):
    if not api_key_header or not secrets.compare_digest(api_key_header, f"Bearer {WEBHOOK_TOKEN}"):
        raise HTTPException(status_code=401, detail="Invalid token")
    return True

@app.post("/api/internal/broadcast")
async def receive_broadcast(state: dict, auth: bool = Depends(verify_token)):
    global latest_bot_state
    latest_bot_state = state
    
    # Push state update
    await manager.broadcast({"type": "status_update", "data": get_bot_status()})
    
    # Push DB updates without blocking the event loop
    trades_data, logs_data, stats_data = await run_in_threadpool(get_db_updates)
    
    if trades_data or logs_data or stats_data:
        await manager.broadcast({"type": "trades_update", "data": trades_data})
        await manager.broadcast({"type": "logs_update", "data": logs_data})
        await manager.broadcast({"type": "stats_update", "data": stats_data})
    
    return {"status": "ok"}


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

class LoginRequest(BaseModel):
    username: str
    password: str

login_attempts = {}

@app.post("/api/login")
def login(req: LoginRequest, request: Request):
    import time
    client_ip = request.client.host
    now = time.time()
    
    if client_ip in login_attempts:
        attempts = [t for t in login_attempts[client_ip] if now - t < 60]
        if len(attempts) >= 5:
            raise HTTPException(status_code=429, detail="Too many login attempts. Please try again later.")
        login_attempts[client_ip] = attempts
    else:
        login_attempts[client_ip] = []
        
    login_attempts[client_ip].append(now)
    
    if secrets.compare_digest(req.username, USER) and secrets.compare_digest(req.password, PASS):
        return {"token": AUTH_TOKEN}
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        auth_msg = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
        if auth_msg.get("type") == "auth" and await manager.authenticate(websocket, auth_msg.get("token")):
            await websocket.send_json({"type": "status_update", "data": get_bot_status()})
            trades_data, logs_data, stats_data = await run_in_threadpool(get_db_updates)
            
            await websocket.send_json({"type": "trades_update", "data": trades_data})
            await websocket.send_json({"type": "logs_update", "data": logs_data})
            await websocket.send_json({"type": "stats_update", "data": stats_data})
            
            while True:
                msg = await websocket.receive_text()
                if len(msg) > 1024:
                    await websocket.close(code=1009, reason="Payload too large")
                    break
        else:
            await websocket.close(code=1008)
    except (WebSocketDisconnect, asyncio.exceptions.CancelledError):
        manager.disconnect(websocket)
    except Exception as e:
        manager.disconnect(websocket)
        
app.mount("/", StaticFiles(directory="dashboard", html=True), name="dashboard")
