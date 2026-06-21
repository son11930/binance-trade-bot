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

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
load_dotenv()

from bot.database import Trade, init_db, SystemLog, SessionLocalSpot, SessionLocalFutures, setup_logging

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
                    import asyncio
                    await asyncio.wait_for(ws.send_json(message), timeout=1.0)
                except Exception:
                    self.disconnect(ws)

manager = ConnectionManager()

def get_stats_for_period(db: Session, start_time=None, market_type: str = 'spot'):
    query = db.query(
        func.sum(Trade.pnl_amount).label('cumulative_pnl'),
        func.sum(case((Trade.pnl_amount > 0, 1), else_=0)).label('wins'),
        func.sum(case((Trade.pnl_amount < 0, 1), else_=0)).label('losses'),
        func.count(Trade.id).label('total_closed'),
        func.sum(case(
            (Trade.pnl_amount.isnot(None), 
                case((Trade.market_type == 'futures', ((Trade.price * Trade.quantity) / 3) - Trade.pnl_amount), 
                else_=((Trade.price * Trade.quantity) - Trade.pnl_amount))
            ), else_=0
        )).label('cumulative_capital')
    ).filter(Trade.pnl_amount.isnot(None), Trade.market_type == market_type)
    
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

import time

_stats_cache = {'spot': None, 'futures': None}
_stats_cache_expiry = {'spot': 0, 'futures': 0}

def get_trade_stats(db: Session, market_type: str = 'spot'):
    global _stats_cache, _stats_cache_expiry
    now_ts = time.time()
    if _stats_cache_expiry.get(market_type, 0) > now_ts and _stats_cache.get(market_type) is not None:
        return _stats_cache[market_type]

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    _stats_cache[market_type] = {
        "1D": get_stats_for_period(db, now - timedelta(days=1), market_type=market_type),
        "7D": get_stats_for_period(db, now - timedelta(days=7), market_type=market_type),
        "1M": get_stats_for_period(db, now - timedelta(days=30), market_type=market_type),
        "ALL": get_stats_for_period(db, None, market_type=market_type)
    }
    _stats_cache_expiry[market_type] = now_ts + 5 # Cache for 5 seconds
    return _stats_cache[market_type]

def format_trade(t):
    from bot.config import FUTURES_LEVERAGE
    market_type = getattr(t, 'market_type', 'spot')
    notional = t.price * t.quantity
    
    margin = notional / FUTURES_LEVERAGE if market_type == 'futures' else notional
    fee = getattr(t, 'fee', 0.0)
    fee_asset = getattr(t, 'fee_asset', 'USDT')
    
    if not fee or fee == 0.0:
        fee = notional * 0.0005 if market_type == 'futures' else notional * 0.001
        fee_asset = 'USDT'
        
    if fee < 0.01 and fee_asset == 'USDT':
        fee = 0.01
        
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
        "fee": fee,
        "fee_asset": fee_asset,
        "margin": margin,
        "pnl_amount": getattr(t, 'pnl_amount', None),
        "pnl_percent": getattr(t, 'pnl_percent', None),
        "position_side": getattr(t, 'position_side', None),
        "market_type": market_type
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

latest_bot_state_spot = {"status_message": "Bot is offline (Not running)", "is_thinking": False, "live_usdt": 0.0, "positions": []}
latest_bot_state_futures = {"status_message": "Bot is offline (Not running)", "is_thinking": False, "live_usdt": 0.0, "positions": []}

from bot.config import SYMBOLS

def get_bot_status():
    return {
        "status": "online",
        "symbols": SYMBOLS,
        "paper_trading": os.getenv("PAPER_TRADING", "True"),
        "spot": latest_bot_state_spot,
        "futures": latest_bot_state_futures
    }

db_poll_event = None

async def db_polling_task():
    global db_poll_event
    
    # Poll database for new logs and trades every 2 seconds to decouple from status broadcasts
    last_ids = {
        'spot': {'trade': 0, 'log': 0},
        'futures': {'trade': 0, 'log': 0}
    }
    
    # Initialize last_ids
    for m in ['spot', 'futures']:
        db = None
        try:
            db = SessionLocalFutures() if m == 'futures' else SessionLocalSpot()
            t = db.query(Trade).order_by(Trade.id.desc()).first()
            if t: last_ids[m]['trade'] = t.id
            l = db.query(SystemLog).order_by(SystemLog.id.desc()).first()
            if l: last_ids[m]['log'] = l.id
        except:
            pass
        finally:
            if db:
                db.close()

    while True:
        try:
            try:
                await asyncio.wait_for(db_poll_event.wait(), timeout=2.0)
                db_poll_event.clear()
            except asyncio.TimeoutError:
                pass
            
            if not manager.active_connections:
                continue # Don't poll if no one is listening
                
            for market in ['spot', 'futures']:
                trades_data, logs_data, stats_data = await run_in_threadpool(
                    get_db_updates, market, last_ids[market]['trade'], last_ids[market]['log']
                )
                
                if trades_data:
                    last_ids[market]['trade'] = max([t['id'] for t in trades_data])
                    await manager.broadcast({"type": "trades_update", "market_type": market, "is_delta": False, "data": trades_data})
                if logs_data:
                    last_ids[market]['log'] = max([l['id'] for l in logs_data])
                    await manager.broadcast({"type": "logs_update", "market_type": market, "is_delta": True, "data": logs_data})
                
                # Send stats update occasionally since it's cached anyway
                await manager.broadcast({"type": "stats_update", "market_type": market, "data": stats_data})
        except Exception as e:
            logging.error(f"Error in db_polling_task: {e}")
            await asyncio.sleep(5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global db_poll_event
    db_poll_event = asyncio.Event()
    init_db()
    asyncio.create_task(db_polling_task())
    yield

app = FastAPI(title="AI Trading Dashboard", lifespan=lifespan)
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(ProxyHeadersMiddleware, trusted_hosts=["127.0.0.1", "localhost", "::1", "45.136.254.62"])


def get_db_updates(market_type: str = 'spot', since_trade_id: int = 0, since_log_id: int = 0):
    db = SessionLocalFutures() if market_type == 'futures' else SessionLocalSpot()
    try:
        trades_query = db.query(Trade).filter(Trade.market_type == market_type)
        trades = trades_query.order_by(Trade.timestamp.desc()).limit(50).all()
        
        logs_query = db.query(SystemLog).filter(SystemLog.market_type == market_type)
        if since_log_id > 0:
            logs = logs_query.filter(SystemLog.id > since_log_id).order_by(SystemLog.id.desc()).limit(100).all()
        else:
            twenty_four_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=24)).replace(tzinfo=None)
            one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(tzinfo=None)
            
            important_logs = db.query(SystemLog).filter(
                SystemLog.market_type == market_type,
                SystemLog.timestamp >= twenty_four_hours_ago,
                ~SystemLog.message.like('%Result: HOLD%'),
                ~SystemLog.message.like('%Order Book Check%'),
                ~SystemLog.message.like('%Load shedding%'),
                ~SystemLog.message.like('%in cooldown%')
            ).all()
            
            recent_noisy_logs = db.query(SystemLog).filter(
                SystemLog.market_type == market_type,
                SystemLog.timestamp >= one_hour_ago,
                (SystemLog.message.like('%Result: HOLD%')) | 
                (SystemLog.message.like('%Order Book Check%')) | 
                (SystemLog.message.like('%Load shedding%')) |
                (SystemLog.message.like('%in cooldown%'))
            ).all()
            
            combined_logs = important_logs + recent_noisy_logs
            combined_logs.sort(key=lambda x: x.id, reverse=True)
            logs = combined_logs[:1000]
        
        trades_data = [format_trade(t) for t in trades]
        logs_data = format_logs(logs)
        stats_data = get_trade_stats(db, market_type=market_type)
        
        return trades_data, logs_data, stats_data
    except Exception as e:
        import traceback
        logging.error(f"Broadcast DB error: {e}")
        error_log = [{
            "id": 999999,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": "ERROR",
            "message": "CRITICAL DB ERROR: Database operation failed. Please check server logs."
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
    position_side: Optional[str] = None
    margin: Optional[float] = None

class BroadcastState(BaseModel):
    market_type: str = 'spot'
    status_message: str
    is_thinking: bool
    symbol_active: Optional[str] = None
    live_usdt: float
    positions: List[PositionModel] = []
    ai_debate: Optional[Dict[str, Any]] = None
    updated_at: Optional[str] = None

@app.post("/api/internal/broadcast")
@limiter.limit("120/minute")
async def receive_broadcast(state: BroadcastState, request: Request, auth: bool = Depends(verify_token)):
    global latest_bot_state_spot, latest_bot_state_futures
    
    if state.market_type == 'futures':
        latest_bot_state_futures = state.model_dump()
    else:
        latest_bot_state_spot = state.model_dump()
    
    # Push ONLY state update
    await manager.broadcast({"type": "status_update", "data": get_bot_status()})
    
    if db_poll_event:
        db_poll_event.set()
    
    return {"status": "ok"}


allowed_origins_str = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000,http://45.136.254.62")
allowed_origins = [origin.strip() for origin in allowed_origins_str.split(",") if origin.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

class LoginRequest(BaseModel):
    username: str = Field(..., max_length=50)
    password: str = Field(..., max_length=72)

@app.post("/api/login")
@limiter.limit("5/minute")
def login(req: LoginRequest, request: Request):
    try:
        password_matches = bcrypt.checkpw(req.password.encode('utf-8'), PASS.encode('utf-8'))
    except ValueError:
        # Prevent downgrade attacks if PASS is misconfigured
        password_matches = False
    except Exception:
        password_matches = False

    if secrets.compare_digest(req.username, USER) and password_matches:
        expire = datetime.now(timezone.utc) + timedelta(minutes=60)
        token = jwt.encode({"sub": USER, "exp": expire}, JWT_SECRET, algorithm=ALGORITHM)
        return {"token": token}
    raise HTTPException(status_code=401, detail="Invalid credentials")

@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    # WS rate limit & stale connection purge (tracked via ip)
    client_ip = websocket.client.host if websocket.client else "unknown"
    if not hasattr(app.state, "ws_connections"):
        app.state.ws_connections = {}
    
    now = time.time()
    
    # Periodic cleanup of stale IPs to prevent memory leak
    if len(app.state.ws_connections) > 1000:
        app.state.ws_connections = {ip: times for ip, times in app.state.ws_connections.items() if times and (now - times[-1]) < 60}
        # Hard cap at 1000 most recently active IPs to prevent DoS
        if len(app.state.ws_connections) > 1000:
            sorted_items = sorted(app.state.ws_connections.items(), key=lambda x: x[1][-1], reverse=True)
            app.state.ws_connections = dict(sorted_items[:1000])
        
    if client_ip in app.state.ws_connections:
        conns = [t for t in app.state.ws_connections[client_ip] if now - t < 60]
        if len(conns) >= 20:
            await websocket.close(code=1008, reason="Too many connections")
            return
        conns.append(now)
        app.state.ws_connections[client_ip] = conns
    else:
        app.state.ws_connections[client_ip] = [now]

    await manager.connect(websocket)
    try:
        auth_msg = await asyncio.wait_for(websocket.receive_json(), timeout=5.0)
        if auth_msg.get("type") == "auth" and await manager.authenticate(websocket, auth_msg.get("token")):
            await websocket.send_json({"type": "status_update", "data": get_bot_status()})
            
            # Send initial spot data
            spot_trades, spot_logs, spot_stats = await run_in_threadpool(get_db_updates, 'spot')
            await websocket.send_json({"type": "trades_update", "market_type": "spot", "data": spot_trades})
            await websocket.send_json({"type": "logs_update", "market_type": "spot", "data": spot_logs})
            await websocket.send_json({"type": "stats_update", "market_type": "spot", "data": spot_stats})
            
            # Send initial futures data
            fut_trades, fut_logs, fut_stats = await run_in_threadpool(get_db_updates, 'futures')
            await websocket.send_json({"type": "trades_update", "market_type": "futures", "data": fut_trades})
            await websocket.send_json({"type": "logs_update", "market_type": "futures", "data": fut_logs})
            await websocket.send_json({"type": "stats_update", "market_type": "futures", "data": fut_stats})
            
            while True:
                msg = await websocket.receive_text()
                if len(msg) > 1024:
                    await websocket.close(code=1009, reason="Payload too large")
                    break
        else:
            await websocket.close(code=1008)
    except (WebSocketDisconnect, asyncio.exceptions.CancelledError):
        pass
    except Exception as e:
        pass
    finally:
        manager.disconnect(websocket)
        
app.mount("/", StaticFiles(directory="dashboard", html=True), name="dashboard")
