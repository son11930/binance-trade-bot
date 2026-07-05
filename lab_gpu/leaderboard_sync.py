"""
leaderboard_sync.py — Database and dashboard JSON progress and leaderboard synchronization.
"""
import os
import json
import time
import threading
from datetime import datetime, timezone
from typing import Dict, List, Any
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import logger, DASHBOARD_DATA_DIR, DATABASE_URL_FUTURES, DATABASE_URL_SPOT
from .gpu_kernel import GPU_AVAILABLE

Base = declarative_base()

class StrategyLeaderboard(Base):
    __tablename__ = "strategy_leaderboard"
    id = Column(Integer, primary_key=True, index=True)
    rank = Column(Integer)
    name = Column(String(100))
    net_profit_1m = Column(Float)
    net_profit_3m = Column(Float)
    net_profit_6m = Column(Float)
    net_profit_1y = Column(Float)
    win_rate_1y = Column(Float)
    max_drawdown = Column(Float)
    total_trades_1y = Column(Integer)
    moonshots_1y = Column(Integer)
    parameters_json = Column(String(2000))
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

_last_progress_write = 0.0
_last_db_progress_write = 0.0
_progress_lock = threading.Lock()
_db_engine_singleton = None

def _get_db_engine():
    global _db_engine_singleton
    if _db_engine_singleton is not None:
        return _db_engine_singleton
    from sqlalchemy.pool import NullPool
    db_url = DATABASE_URL_FUTURES or DATABASE_URL_SPOT or "sqlite:///./trades_futures.db"
    if db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql://", 1)
    _db_engine_singleton = create_engine(
        db_url,
        poolclass=NullPool,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 10} if "postgresql" in db_url else {}
    )
    return _db_engine_singleton

def save_lab_progress_gpu(status: str, current_trial: int, total_trials: int,
                           best_score: float, best_name: str, elapsed_sec: int,
                           total_db_trials: int = 0):
    global _last_progress_write, _last_db_progress_write
    with _progress_lock:
        now_ts = time.time()
        if status == "running" and (now_ts - _last_progress_write < 1.0):
            return
        _last_progress_write = now_ts

    pct = round(min(100.0, (current_trial / total_trials) * 100.0), 1) if total_trials and total_trials > 0 else 100.0
    data = {
        "status": status,
        "current_trial": current_trial,
        "total_trials":  total_trials if total_trials and total_trials > 0 else 0,
        "total_db_trials": total_db_trials if total_db_trials > 0 else current_trial,
        "progress_pct":  pct,
        "best_score":    round(float(best_score), 2),
        "best_strategy_name": str(best_name),
        "elapsed_seconds": int(elapsed_sec),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "engine": "GPU" if GPU_AVAILABLE else "CPU-MultiCore",
    }
    prog_path = os.path.join(DASHBOARD_DATA_DIR, "lab_progress.json")
    os.makedirs(DASHBOARD_DATA_DIR, exist_ok=True)
    try:
        tmp = prog_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, prog_path)
    except Exception as e:
        logger.error(f"Failed to write progress: {e}")

    if status != "running" or (now_ts - _last_db_progress_write >= 3.0):
        _last_db_progress_write = now_ts
        try:
            from bot.database import LabProgressState, Base as BotBase
            engine = _get_db_engine()
            BotBase.metadata.create_all(bind=engine)
            Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            sess = Session()
            row = sess.query(LabProgressState).filter_by(id=1).first()
            if not row:
                row = LabProgressState(id=1); sess.add(row)
            for k, v in data.items():
                if hasattr(row, k):
                    setattr(row, k, v)
            sess.commit(); sess.close()
        except Exception:
            pass

def push_leaderboard_to_db_and_json_gpu(leaderboard: List[Dict[str, Any]]):
    """Push Top 10 to Aiven DB + dashboard JSON."""
    os.makedirs(DASHBOARD_DATA_DIR, exist_ok=True)
    json_path = os.path.join(DASHBOARD_DATA_DIR, "strategy_leaderboard.json")
    try:
        tmp = json_path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"updated_at": datetime.now(timezone.utc).isoformat(),
                       "strategies": leaderboard}, f, indent=2)
        os.replace(tmp, json_path)
        logger.info(f"Saved GPU Top 10 Leaderboard → {json_path}")
    except Exception as e:
        logger.error(f"Failed to write leaderboard JSON: {e}")
    try:
        engine = _get_db_engine()
        Base.metadata.create_all(bind=engine)
        Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        sess = Session()
        sess.query(StrategyLeaderboard).delete()
        for idx, item in enumerate(leaderboard, 1):
            sess.add(StrategyLeaderboard(
                rank=int(idx), name=str(item["name"]),
                net_profit_1m=float(item["net_profit_1m"]),
                net_profit_3m=float(item["net_profit_3m"]),
                net_profit_6m=float(item["net_profit_6m"]),
                net_profit_1y=float(item["net_profit_1y"]),
                win_rate_1y=float(item["win_rate_1y"]),
                max_drawdown=float(item["max_dd"]),
                total_trades_1y=int(item["total_trades_1y"]),
                moonshots_1y=int(item["moonshots_1y"]),
                parameters_json=json.dumps(item["parameters"])
            ))
        sess.commit(); sess.close()
        logger.info("✅ Pushed GPU Top 10 Leaderboard → Aiven DB!")
    except Exception as e:
        logger.error(f"Failed to push leaderboard to DB: {e}")

def get_deduplicated_top10_gpu(lb_map: dict) -> list:
    all_items = sorted(lb_map.values(), key=lambda x: x.get("fitness_score", -9999), reverse=True)
    unique, seen = [], set()
    for item in all_items:
        params = item.get("parameters", {})
        key = tuple(sorted([(k, round(v, 4) if isinstance(v, float) else v) for k, v in params.items()]))
        if key not in seen:
            seen.add(key); unique.append(item)
            if len(unique) >= 10:
                break
    for idx, item in enumerate(unique, 1):
        item["rank"] = idx
        raw = item.get("name", "").split(": ")[-1]
        item["name"] = f"🏆 #{idx} ALPHA GENOME: {raw}" if idx == 1 else f"#{idx} BLUEPRINT: {raw}"
    return unique
