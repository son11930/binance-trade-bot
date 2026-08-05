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
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from bot.control import get_bot_control, set_bot_control
from typing import Dict, Optional, List, Any
from fastapi.concurrency import run_in_threadpool
from dotenv import load_dotenv

from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware
load_dotenv()

from bot.database import Trade, init_db, SystemLog, SessionLocalSpot, SessionLocalFutures, setup_logging, StrategyLeaderboard

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

def get_stats_for_period(db: Session, start_time=None, market_type: str = 'spot', is_paper: bool = None):
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
    
    if is_paper is not None:
        query = query.filter(Trade.paper_trade == is_paper)
    
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
    
    def fetch_stats(is_paper_val):
        return {
            "1D": get_stats_for_period(db, now - timedelta(days=1), market_type=market_type, is_paper=is_paper_val),
            "7D": get_stats_for_period(db, now - timedelta(days=7), market_type=market_type, is_paper=is_paper_val),
            "1M": get_stats_for_period(db, now - timedelta(days=30), market_type=market_type, is_paper=is_paper_val),
            "ALL": get_stats_for_period(db, None, market_type=market_type, is_paper=is_paper_val)
        }
        
    _stats_cache[market_type] = {
        "PAPER": fetch_stats(True),
        "LIVE": fetch_stats(False)
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
    from bot.strategy_manager import get_active_strategy
    from bot.control import get_bot_control
    
    strat = get_active_strategy()
    ctrl = get_bot_control()
    allow_live = ctrl.get("allow_live", False)
    paper_trading_config = ctrl.get("paper_trading", True)
    spot_paused = ctrl.get("spot_paused", False)
    futures_paused = ctrl.get("futures_paused", False)
    pause_reason = ctrl.get("pause_reason", "")
    
    active_stage = strat.get("stage", "PAPER") if strat else ("PAPER" if paper_trading_config else "LIVE")
    
    # Phase 8: Reconciliation status
    recon_status = "Pending..."
    import os, json
    state_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "bot_state.json")
    if os.path.exists(state_file):
        try:
            with open(state_file, 'r') as f:
                s_data = json.load(f)
                recon_status = s_data.get('reconciliation_status', "Pending...")
        except:
            pass
            
    return {
        "status": "online",
        "symbols": SYMBOLS,
        "paper_trading": str(paper_trading_config),
        "allow_live": allow_live,
        "spot_paused": str(spot_paused),
        "futures_paused": str(futures_paused),
        "pause_reason": pause_reason,
        "active_stage": active_stage,
        "reconciliation_status": recon_status,
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

class TogglePauseRequest(BaseModel):
    market: str
    paused: bool

class ToggleExecutionModeRequest(BaseModel):
    allow_live: Optional[bool] = None
    paper_trading: Optional[bool] = None

@app.get("/api/bot_control")
async def get_bot_control_endpoint():
    return get_bot_control()

def verify_jwt(auth_header: str = Security(APIKeyHeader(name="Authorization", auto_error=False))):
    if not auth_header:
        raise HTTPException(status_code=401, detail="Missing Authorization Header")
    token = auth_header.replace("Bearer ", "")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[ALGORITHM])
        if not secrets.compare_digest(payload.get("sub", ""), USER):
            raise HTTPException(status_code=403, detail="Invalid User")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or Expired Token")
    return True

@app.post("/api/toggle_pause")
async def toggle_pause_endpoint(req: TogglePauseRequest, auth: bool = Depends(verify_jwt)):
    if req.market == "spot":
        set_bot_control(spot_paused=req.paused)
    elif req.market == "futures":
        set_bot_control(futures_paused=req.paused)
    else:
        raise HTTPException(status_code=400, detail="Invalid market. Must be 'spot' or 'futures'")
    
    new_state = get_bot_control()
    await manager.broadcast({"type": "bot_control_update", "data": new_state})
    return {"status": "success", "data": new_state}

@app.post("/api/toggle_execution_mode")
async def toggle_execution_mode_endpoint(req: ToggleExecutionModeRequest, auth: bool = Depends(verify_jwt)):
    set_bot_control(allow_live=req.allow_live, paper_trading=req.paper_trading)
    new_state = get_bot_control()
    
    # Broadcast the updated status immediately
    await manager.broadcast({"type": "status_update", "data": get_bot_status()})
    await manager.broadcast({"type": "bot_control_update", "data": new_state})
    
    return {"status": "success", "data": new_state}


def get_db_updates(market_type: str = 'spot', since_trade_id: int = 0, since_log_id: int = 0):
    db = SessionLocalFutures() if market_type == 'futures' else SessionLocalSpot()
    try:
        trades_paper = db.query(Trade).filter(Trade.market_type == market_type, Trade.paper_trade == True).order_by(Trade.timestamp.desc()).limit(50).all()
        trades_live = db.query(Trade).filter(Trade.market_type == market_type, Trade.paper_trade == False).order_by(Trade.timestamp.desc()).limit(50).all()
        trades = trades_paper + trades_live
        trades.sort(key=lambda x: x.timestamp, reverse=True)
        
        logs_query = db.query(SystemLog).filter(SystemLog.market_type == market_type)
        if since_log_id > 0:
            logs = logs_query.filter(SystemLog.id > since_log_id).order_by(SystemLog.id.desc()).limit(100).all()
        else:
            one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(tzinfo=None)
            
            # Fetch last 2000 logs quickly without heavy LIKE filters
            raw_logs = logs_query.order_by(SystemLog.id.desc()).limit(2000).all()
            
            important_logs = []
            noisy_logs = []
            for l in raw_logs:
                msg = l.message
                is_noisy = "Result: HOLD" in msg or "Order Book Check" in msg or "Load shedding" in msg or "in cooldown" in msg
                if is_noisy:
                    if isinstance(l.timestamp, datetime):
                        ts = l.timestamp
                    else:
                        try:
                            ts = datetime.fromisoformat(l.timestamp)
                        except:
                            ts = datetime.now()
                            
                    if ts.tzinfo:
                        ts = ts.replace(tzinfo=None)
                        
                    if ts >= one_hour_ago:
                        noisy_logs.append(l)
                else:
                    important_logs.append(l)
            
            combined_logs = important_logs + noisy_logs
            combined_logs.sort(key=lambda x: x.id, reverse=True)
            logs = combined_logs[:500]
        
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
    dynamic_sl: Optional[float] = None
    dynamic_tp: Optional[float] = None
    holding_time_minutes: Optional[int] = None
    distance_to_liquidation_percent: Optional[float] = None

class BroadcastState(BaseModel):
    market_type: str = 'spot'
    status_message: str
    is_thinking: bool
    symbol_active: Optional[str] = None
    live_usdt: float
    positions: List[PositionModel] = []
    ai_debate: Optional[Dict[str, Any]] = None
    updated_at: Optional[str] = None
    active_stage: Optional[str] = None
    daily_realized_pnl: Optional[float] = None
    daily_trades_count: Optional[int] = None
    consecutive_losses: Optional[int] = None
    max_drawdown: Optional[float] = None
    system_health: Optional[Dict[str, Any]] = None

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


_leaderboard_cache = {"data": None, "expiry": 0}

@app.get("/api/lab/leaderboard")
def get_strategy_leaderboard():
    """Returns Top 10 synthesized strategies from Aiven DB or JSON fallback with 15s TTL cache."""
    now = time.time()
    if _leaderboard_cache["data"] and now < _leaderboard_cache["expiry"]:
        return {"status": "ok", "strategies": _leaderboard_cache["data"]}

    strategies = []
    db = SessionLocalFutures()
    try:
        rows = db.query(StrategyLeaderboard).order_by(StrategyLeaderboard.rank.asc()).limit(10).all()
        for r in rows:
            params = {}
            if r.parameters_json:
                try:
                    import json
                    params = json.loads(r.parameters_json)
                except Exception:
                    pass
            strategies.append({
                "rank": r.rank,
                "name": r.name,
                "net_profit_1m": r.net_profit_1m,
                "net_profit_3m": r.net_profit_3m,
                "net_profit_6m": r.net_profit_6m,
                "net_profit_1y": r.net_profit_1y,
                "win_rate_1y": r.win_rate_1y,
                "max_dd": r.max_drawdown,
                "total_trades_1y": r.total_trades_1y,
                "moonshots_1y": r.moonshots_1y,
                "parameters": params
            })
        if strategies:
            _leaderboard_cache["data"] = strategies
            _leaderboard_cache["expiry"] = now + 15.0
    except Exception as e:
        logging.warning(f"DB Leaderboard query failed ({e}), checking JSON fallback...")
    finally:
        db.close()
        
    if not strategies:
        json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard", "data", "strategy_leaderboard.json")
        if os.path.exists(json_path):
            try:
                import json
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    strategies = data.get("strategies", [])
                    if strategies:
                        _leaderboard_cache["data"] = strategies
                        _leaderboard_cache["expiry"] = now + 15.0
            except Exception as e:
                logging.error(f"Error reading JSON fallback leaderboard: {e}")
                
    return {"status": "ok", "strategies": strategies}


@app.get("/api/lab/progress")
def get_strategy_lab_progress():
    """Returns live real-time progress of the AI Strategy Synthesizer Lab from Aiven DB or local file fallback."""
    try:
        from bot.database import LabProgressState
        db = SessionLocalFutures()
        row = db.query(LabProgressState).filter_by(id=1).first()
        if row and row.status and row.status != "idle":
            res = {
                "status": row.status,
                "current_trial": row.current_trial or 0,
                "total_trials": row.total_trials or 0,
                "progress_pct": row.progress_pct or 0.0,
                "best_score": row.best_score or 0.0,
                "best_strategy_name": row.best_strategy_name or "N/A",
                "elapsed_seconds": row.elapsed_seconds or 0,
                "updated_at": row.updated_at or ""
            }
            db.close()
            return {"status": "ok", "progress": res}
        db.close()
    except Exception:
        pass

    json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard", "data", "lab_progress.json")
    if os.path.exists(json_path):
        try:
            import json
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {"status": "ok", "progress": data}
        except Exception as e:
            logging.error(f"Error reading lab progress: {e}")
    return {"status": "ok", "progress": {"status": "idle"}}


@app.post("/api/lab/upload_results")
async def upload_strategy_results(data: Dict[str, Any], request: Request):
    """Webhook endpoint for local AI Synthesizer Lab to push Top 10 results."""
    _leaderboard_cache["expiry"] = 0  # Invalidate cache instantly on new results
    auth_header = request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "").strip() if auth_header else ""
    if not token or (token != WEBHOOK_TOKEN and token != os.getenv("BOT_TOKEN", "")):
        # Allow internal localhost loopback without auth token if token not provided
        client_ip = get_remote_address(request)
        if client_ip not in ("127.0.0.1", "localhost", "::1"):
            raise HTTPException(status_code=401, detail="Unauthorized upload")
            
    strategies = data.get("strategies", [])
    if not strategies:
        return {"status": "error", "message": "No strategies provided"}
        
    json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard", "data", "strategy_leaderboard.json")
    os.makedirs(os.path.dirname(json_path), exist_ok=True)
    try:
        import json
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump({"updated_at": datetime.now(timezone.utc).isoformat(), "strategies": strategies}, f, indent=2)
    except Exception as e:
        logging.error(f"Failed to save JSON leaderboard: {e}")
        
    db = SessionLocalFutures()
    try:
        db.query(StrategyLeaderboard).delete()
        for idx, item in enumerate(strategies[:10], 1):
            import json
            row = StrategyLeaderboard(
                rank=int(idx),
                name=str(item.get("name", f"Blueprint #{idx}")),
                net_profit_1m=float(item.get("net_profit_1m", 0.0)),
                net_profit_3m=float(item.get("net_profit_3m", 0.0)),
                net_profit_6m=float(item.get("net_profit_6m", 0.0)),
                net_profit_1y=float(item.get("net_profit_1y", 0.0)),
                win_rate_1y=float(item.get("win_rate_1y", 0.0)),
                max_drawdown=float(item.get("max_dd", 0.0)),
                total_trades_1y=int(item.get("total_trades_1y", 0)),
                moonshots_1y=int(item.get("moonshots_1y", 0)),
                parameters_json=json.dumps(item.get("parameters", {}))
            )
            db.add(row)
        db.commit()
    except Exception as e:
        db.rollback()
        logging.error(f"Failed DB insert for leaderboard: {e}")
    finally:
        db.close()
        
    return {"status": "ok", "message": f"Successfully updated Top {len(strategies[:10])} strategies"}

class PromoteRequest(BaseModel):
    rank: int
    stage: str

@app.post("/api/strategy/promote")
def promote_strategy(req: PromoteRequest, auth: bool = Depends(verify_jwt)):
    if req.stage not in ["PAPER", "LIVE"]:
        raise HTTPException(status_code=400, detail="Stage must be PAPER or LIVE")
        
    ctrl = get_bot_control()
    if req.stage == "LIVE" and not ctrl.get("allow_live", False):
        raise HTTPException(status_code=403, detail="LIVE deployment is disabled. Enable 'Allow Live Trading' first.")
        
    if not ctrl.get("spot_paused", False) or not ctrl.get("futures_paused", False):
        raise HTTPException(status_code=400, detail="Cannot deploy strategy while bot is running. Please PAUSE the bot first.")
        
    try:
        from bot.binance_client import client
        positions_res = client.futures_position_information()
        open_positions = [p for p in positions_res if float(p['positionAmt']) != 0]
        if open_positions:
            raise HTTPException(status_code=400, detail="Cannot deploy strategy while there are open exchange positions.")
    except HTTPException:
        raise
    except Exception as e:
        logging.warning(f"Could not check open positions: {e}")
        
    json_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard", "data", "strategy_leaderboard.json")
    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail="Leaderboard not found")
        
    try:
        import json
        with open(json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            strategies = data.get("strategies", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading leaderboard: {e}")
        
    target_strat = next((s for s in strategies if s.get("rank") == req.rank), None)
    if not target_strat:
        raise HTTPException(status_code=404, detail=f"Strategy with rank {req.rank} not found")
        
    manifest_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard", "data", "strategy_manifest.json")
    
    manifest_data = {"active_strategy": {}, "history": []}
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
        except Exception:
            pass
            
    active_strat = manifest_data.get("active_strategy", {})
    
    if req.stage in ["CANARY", "LIVE"]:
        if active_strat.get("rank") != req.rank:
            raise HTTPException(status_code=403, detail="Governance Violation: Strategy must be deployed to PAPER first before promoting to LIVE/CANARY.")
        if active_strat.get("stage") not in ["PAPER", "CANARY"]:
            raise HTTPException(status_code=403, detail="Governance Violation: Strategy must currently be in PAPER stage to be promoted.")
            
    if manifest_data.get("active_strategy", {}).get("name"):
        manifest_data["history"].append(manifest_data["active_strategy"])
        manifest_data["history"] = manifest_data["history"][-10:]
        
    new_strategy = {
        "version": "1.0.0",
        "id": f"strat_{req.rank}_{int(time.time())}",
        "name": target_strat.get("name", "Unknown"),
        "stage": req.stage,
        "promoted_at": datetime.now(timezone.utc).isoformat(),
        "promoted_by": USER,
        "parameters": target_strat.get("parameters", {})
    }
    manifest_data["active_strategy"] = new_strategy
    
    try:
        tmp_manifest = f"{manifest_path}.tmp"
        with open(tmp_manifest, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)
        os.replace(tmp_manifest, manifest_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to write manifest: {e}")
        
    return {"status": "success", "message": f"Successfully promoted {new_strategy['name']} to {req.stage}", "data": new_strategy}

@app.get("/api/strategy/deployment")
def get_strategy_deployment(auth: bool = Depends(verify_jwt)):
    manifest_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard", "data", "strategy_manifest.json")
    if os.path.exists(manifest_path):
        try:
            import json
            with open(manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            return {"active_strategy": None, "error": str(e)}
    return {"active_strategy": None}


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
    remember_me: bool = False

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
        if req.remember_me:
            expire = datetime.now(timezone.utc) + timedelta(days=30)
        else:
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
