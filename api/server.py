import os
import time
import hashlib
import asyncio
import logging
import secrets
import jwt
import bcrypt
from datetime import datetime, timezone, timedelta
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, Security, WebSocket, WebSocketDisconnect, Request
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func, case
from pydantic import BaseModel, Field
from typing import Dict, Optional, List, Any
from fastapi.concurrency import run_in_threadpool
from dotenv import load_dotenv
load_dotenv()

from bot.database import Trade, init_db, SystemLog, SessionLocal, setup_logging

setup_logging()

USER = os.getenv("DASHBOARD_USER")
PASS = os.getenv("DASHBOARD_PASS")
SECRET_SALT = os.getenv("DASHBOARD_SECRET_SALT")

if not USER or not PASS or not SECRET_SALT:
    raise ValueError("CRITICAL SECURITY ERROR: DASHBOARD_USER, DASHBOARD_PASS, and DASHBOARD_SECRET_SALT must be set in .env")

import hmac

WEBHOOK_TOKEN = hmac.new(SECRET_SALT.encode(), f"{USER}_webhook".encode(), hashlib.sha256).hexdigest()
JWT_SECRET = hmac.new(SECRET_SALT.encode(), b"jwt", hashlib.sha256).hexdigest()
ALGORITHM = "HS256"

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
        if not token:
            return False
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
            if secrets.compare_digest(payload.get("sub", ""), USER):
                self.active_connections[websocket] = True
                return True
        except jwt.ExpiredSignatureError:
            pass
        except jwt.InvalidTokenError:
            pass
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

def format_logs(logs):
    formatted_logs = []
    for l in logs:
        ts = l.timestamp
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts)
            except ValueError:
                pass
        
        if hasattr(ts, 'isoformat'):
            # Force UTC if naive
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            ts_str = ts.isoformat()
        else:
            ts_str = ts

        formatted_logs.append({
            "id": l.id,
            "timestamp": ts_str,
            "level": l.level,
            "message": l.message
        })
    return formatted_logs

latest_bot_state = {"status_message": "Bot is offline (Not running)", "is_thinking": False, "live_usdt": 0.0, "positions": []}

from bot.config import SYMBOLS

def get_bot_status():
    return {
        "status": "online",
        "symbols": SYMBOLS,
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
        trades = db.query(Trade).order_by(Trade.id.desc()).limit(50).all()
        logs = db.query(SystemLog).order_by(SystemLog.id.desc()).limit(500).all()
        
        trades_data = [format_trade(t) for t in trades]
        logs_data = format_logs(logs)
        stats_data = get_trade_stats(db)
        
        return trades_data, logs_data, stats_data
    except Exception as e:
        import traceback
        err_msg = str(e)
        logging.error(f"Broadcast DB error: {err_msg}")
        traceback.print_exc()
        
        # Return the error as a fake log so it appears on the dashboard
        from datetime import datetime, timezone
        error_log = [{
            "id": 999999,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "ERROR",
            "message": f"CRITICAL DB ERROR: {err_msg}"
        }]
        return [], error_log, {}
    finally:
        db.close()

def verify_token(api_key_header: str = Security(APIKeyHeader(name="Authorization", auto_error=False))):
    if not api_key_header or not secrets.compare_digest(api_key_header, f"Bearer {WEBHOOK_TOKEN}"):
        raise HTTPException(status_code=401, detail="Invalid token")
    return True

class PositionModel(BaseModel):
    symbol: str
    quantity: float
    buy_price: float
    current_price: float
    pnl_amount: float
    pnl_percent: float

class BroadcastState(BaseModel):
    status_message: str
    is_thinking: bool
    symbol_active: Optional[str] = None
    live_usdt: float
    positions: List[PositionModel] = []
    ai_debate: Optional[Dict[str, Any]] = None
    updated_at: Optional[str] = None

@app.post("/api/internal/broadcast")
async def receive_broadcast(state: BroadcastState, auth: bool = Depends(verify_token)):
    global latest_bot_state
    latest_bot_state = state.model_dump()
    
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
    username: str = Field(..., max_length=50)
    password: str = Field(..., max_length=72)

login_attempts = {}

@app.post("/api/login")
def login(req: LoginRequest, request: Request):
    client_ip = request.client.host
    now = time.time()
    
    # Cleanup old entries to prevent memory leak DoS
    if len(login_attempts) > 1000:
        keys_to_delete = [ip for ip, times in login_attempts.items() if not times or now - times[-1] >= 60]
        for k in keys_to_delete:
            del login_attempts[k]
        # If still too large, clear completely to save memory
        if len(login_attempts) > 1000:
            login_attempts.clear()
            
    if client_ip in login_attempts:
        attempts = [t for t in login_attempts[client_ip] if now - t < 60]
        if len(attempts) >= 5:
            raise HTTPException(status_code=429, detail="Too many login attempts. Please try again later.")
        login_attempts[client_ip] = attempts
    else:
        login_attempts[client_ip] = []
        
    login_attempts[client_ip].append(now)
    
    try:
        password_matches = bcrypt.checkpw(req.password.encode('utf-8'), PASS.encode('utf-8'))
    except Exception:
        # If PASS is not a valid bcrypt hash, this will catch the exception
        password_matches = False

    if secrets.compare_digest(req.username, USER) and password_matches:
        expire = datetime.now(timezone.utc) + timedelta(minutes=60)
        token = jwt.encode({"sub": USER, "exp": expire}, JWT_SECRET, algorithm=ALGORITHM)
        return {"token": token}
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
