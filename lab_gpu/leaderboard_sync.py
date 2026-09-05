"""
leaderboard_sync.py — Database and dashboard JSON progress and leaderboard synchronization.
"""
import os
import json
import time
import threading
import copy
from datetime import datetime, timezone
from typing import Dict, List, Any
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker

from .config import logger, DASHBOARD_DATA_DIR, DATABASE_URL_FUTURES, DATABASE_URL_SPOT
from .gpu_kernel import GPU_AVAILABLE
from .cost_model import cost_model_metadata
from candidate_evidence import attach_candidate_identity
from bot.strategy_contract import strategy_id

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
    parameters_json = Column(Text)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

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


# ---------------------------------------------------------------------
# ASYNC STATE QUEUE FOR NON-BLOCKING GPU WRITES
# ---------------------------------------------------------------------
_async_state = {
    "progress_data": None,
    "leaderboard_data": None,
    "leaderboard_metadata": {},
}
_async_lock = threading.Lock()

def _write_json_atomic(path: str, data: dict):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, path)

def _sync_worker_loop():
    """Background thread that flushes pending JSON and DB updates."""
    last_progress_db_write = 0.0
    last_leaderboard_db_write = 0.0
    last_progress_json_write = 0.0

    while True:
        try:
            time.sleep(1.0)
            now_ts = time.time()

            # Safely extract snapshots
            with _async_lock:
                prog_data = copy.deepcopy(_async_state["progress_data"])
                lb_data = copy.deepcopy(_async_state["leaderboard_data"])
                lb_metadata = copy.deepcopy(_async_state["leaderboard_metadata"])
                _async_state["progress_data"] = None  # Clear dirty flag
                _async_state["leaderboard_data"] = None # Clear dirty flag
                _async_state["leaderboard_metadata"] = {}

            # 1. Process Progress Updates
            if prog_data:
                # 1.1 JSON Progress Update (Fast, throttle to 1.0s)
                if now_ts - last_progress_json_write >= 1.0:
                    prog_path = os.path.join(DASHBOARD_DATA_DIR, "lab_progress.json")
                    os.makedirs(DASHBOARD_DATA_DIR, exist_ok=True)
                    try:
                        _write_json_atomic(prog_path, prog_data)
                        last_progress_json_write = now_ts
                    except Exception as e:
                        logger.error(f"SyncWorker: Failed to write progress JSON: {e}")

                # 1.2 DB Progress Update (Slow, throttle to 3.0s)
                if now_ts - last_progress_db_write >= 3.0 or prog_data["status"] != "running":
                    try:
                        from bot.database import (
                            LabProgressState,
                            ensure_lab_progress_schema,
                        )
                        engine = _get_db_engine()
                        if not ensure_lab_progress_schema(engine):
                            raise RuntimeError("lab progress schema migration failed")
                        Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
                        with Session() as sess:
                            row = sess.query(LabProgressState).filter_by(id=1).first()
                            if not row:
                                row = LabProgressState(id=1); sess.add(row)
                            for k, v in prog_data.items():
                                if hasattr(row, k):
                                    setattr(row, k, v)
                            sess.commit()
                        last_progress_db_write = now_ts
                    except Exception as e:
                        pass # Ignore DB failures silently to avoid spam

            # 2. Process Leaderboard Updates
            if lb_data is not None:
                published_at = datetime.now(timezone.utc).isoformat()
                # 2.1 JSON Leaderboard Update (Atomic)
                lb_path = os.path.join(DASHBOARD_DATA_DIR, "strategy_leaderboard.json")
                os.makedirs(DASHBOARD_DATA_DIR, exist_ok=True)
                try:
                    payload = {
                        "updated_at": published_at,
                        "run_id": lb_metadata.get("run_id", ""),
                        "telemetry_schema_version": 2,
                        "published_leader_count": len(lb_data),
                        "strategies": lb_data
                    }
                    _write_json_atomic(lb_path, payload)
                    # Don't log spam info
                except Exception as e:
                    logger.error(f"SyncWorker: Failed to write leaderboard JSON: {e}")
                
                # 2.2 DB Leaderboard Update (Heavy, throttle to 5.0s)
                db_persisted = False
                if now_ts - last_leaderboard_db_write >= 5.0:
                    try:
                        engine = _get_db_engine()
                        Base.metadata.create_all(bind=engine)
                        Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
                        with Session() as sess:
                            sess.query(StrategyLeaderboard).delete()
                            for idx, item in enumerate(lb_data, 1):
                                stored_item = {
                                    **item,
                                    "run_id": lb_metadata.get("run_id", ""),
                                    "telemetry_schema_version": 2,
                                    "updated_at": published_at,
                                    "published_leader_count": len(lb_data),
                                }
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
                                     parameters_json=json.dumps(stored_item)
                                ))
                            sess.commit()
                        db_persisted = True
                        last_leaderboard_db_write = now_ts
                    except Exception as e:
                        logger.error(f"SyncWorker: Failed to push leaderboard to DB: {e}")

                # Keep the latest update queued until the shared DB has
                # acknowledged it.  The local JSON write is not enough for
                # the server, because the Lab and dashboard run on separate
                # machines and the API uses the shared DB snapshot.
                if not db_persisted:
                    with _async_lock:
                        if _async_state["leaderboard_data"] is None:
                            _async_state["leaderboard_data"] = lb_data
                            _async_state["leaderboard_metadata"] = lb_metadata

        except Exception as e:
            time.sleep(1.0) # Prevent tight loop on critical failure

# Start Background Worker Thread (Daemon so it dies with main thread)
_worker_thread = threading.Thread(target=_sync_worker_loop, daemon=True, name="SyncWorkerThread")
_worker_thread.start()


# ---------------------------------------------------------------------
# PUBLIC NON-BLOCKING APIS (CALL THESE FROM GPU KERNEL LOOP)
# ---------------------------------------------------------------------

def save_lab_progress_gpu(status: str, current_trial: int, total_trials: int,
                           best_score: float, best_name: str, elapsed_sec: int,
                           total_db_trials: int = 0,
                           best_full_score: float | None = None,
                           best_screen_score: float | None = None,
                           screened_count: int = 0,
                           full_evaluated_count: int = 0,
                           qualified_count: int = 0,
                           rejected_count: int = 0,
                           generated_count: int | None = None,
                           tpe_sampled_count: int = 0,
                           mutant_count: int = 0,
                           exploration_mutant_count: int = 0,
                           retained_leader_count: int = 0,
                           strategy_generated_counts: Dict[str, int] | None = None,
                           strategy_full_evaluated_counts: Dict[str, int] | None = None,
                           strategy_qualified_counts: Dict[str, int] | None = None,
                           strategy_rejected_counts: Dict[str, int] | None = None,
                           strategy_tpe_counts: Dict[str, int] | None = None,
                           strategy_mutant_counts: Dict[str, int] | None = None,
                           strategy_exploration_counts: Dict[str, int] | None = None,
                           published_leader_count: int | None = None,
                           historical_re_evaluated_count: int = 0,
                           run_id: str = "",
                           telemetry_schema_version: int = 2):
    """Puts progress data into the background async queue."""
    pct = round(min(100.0, (current_trial / total_trials) * 100.0), 1) if total_trials and total_trials > 0 else 100.0
    generated = screened_count if generated_count is None else generated_count
    generated_by_strategy = dict(strategy_generated_counts or {})
    full_by_strategy = dict(strategy_full_evaluated_counts or {})
    qualified_by_strategy = dict(strategy_qualified_counts or {})
    rejected_by_strategy = dict(strategy_rejected_counts or {})
    tpe_by_strategy = dict(strategy_tpe_counts or {})
    mutant_by_strategy = dict(strategy_mutant_counts or {})
    exploration_by_strategy = dict(strategy_exploration_counts or {})
    data = {
        "status": status,
        "current_trial": current_trial,
        "total_trials":  total_trials if total_trials and total_trials > 0 else 0,
        "total_db_trials": total_db_trials if total_db_trials > 0 else current_trial,
        "progress_pct":  pct,
        "best_score":    round(float(best_score), 2),
        "best_strategy_name": str(best_name),
        "best_full_score": round(float(best_full_score), 2) if best_full_score is not None else None,
        "best_screen_score": round(float(best_screen_score), 2) if best_screen_score is not None else None,
        "screened_count": int(screened_count),
        "full_evaluated_count": int(full_evaluated_count),
        "qualified_count": int(qualified_count),
        # Rejected means a candidate completed full evaluation but failed the
        # qualification gate; screening-only placeholders are not counted.
        "rejected_count": int(rejected_count),
        "generated_count": int(generated),
        "tpe_sampled_count": int(tpe_sampled_count),
        "mutant_count": int(mutant_count),
        "exploration_mutant_count": int(exploration_mutant_count),
        "retained_leader_count": int(retained_leader_count),
        "strategy_generated_counts": generated_by_strategy,
        "strategy_full_evaluated_counts": full_by_strategy,
        "strategy_qualified_counts": qualified_by_strategy,
        "strategy_rejected_counts": rejected_by_strategy,
        "strategy_tpe_counts": tpe_by_strategy,
        "strategy_mutant_counts": mutant_by_strategy,
        "strategy_exploration_counts": exploration_by_strategy,
        "published_leader_count": int(published_leader_count) if published_leader_count is not None else None,
        "historical_re_evaluated_count": int(historical_re_evaluated_count),
        "run_id": str(run_id or ""),
        "telemetry_schema_version": int(telemetry_schema_version),
        # The DB model stores these as text so existing SQLite/Postgres
        # installations can migrate without relying on a JSON column type.
        "strategy_generated_counts_json": json.dumps(generated_by_strategy, sort_keys=True),
        "strategy_full_evaluated_counts_json": json.dumps(full_by_strategy, sort_keys=True),
        "strategy_qualified_counts_json": json.dumps(qualified_by_strategy, sort_keys=True),
        "strategy_rejected_counts_json": json.dumps(rejected_by_strategy, sort_keys=True),
        "strategy_tpe_counts_json": json.dumps(tpe_by_strategy, sort_keys=True),
        "strategy_mutant_counts_json": json.dumps(mutant_by_strategy, sort_keys=True),
        "strategy_exploration_counts_json": json.dumps(exploration_by_strategy, sort_keys=True),
        "elapsed_seconds": int(elapsed_sec),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "engine": "GPU" if GPU_AVAILABLE else "CPU-MultiCore",
        "cost_model": cost_model_metadata(),
    }
    with _async_lock:
        _async_state["progress_data"] = data

# State variable to track global best score so we don't spam leaderboard updates
_last_top1_score = -999999.0
_last_lb_push_time = 0.0

def push_leaderboard_to_db_and_json_gpu(
    leaderboard: List[Dict[str, Any]],
    force: bool = False,
    run_id: str = "",
):
    """Puts leaderboard data into the background async queue only if it's meaningful."""
    global _last_top1_score, _last_lb_push_time
    
    if not leaderboard and not force:
        return
    current_top1 = float(leaderboard[0].get("fitness_score", -99999.0)) if leaderboard else -99999.0
    now_ts = time.time()
    
    # PREDICATE: Only sync if there is a NEW global best OR 10 seconds have passed, OR if forced
    is_new_best = current_top1 > _last_top1_score
    is_interval_reached = (now_ts - _last_lb_push_time) > 10.0
    
    if is_new_best or is_interval_reached or force:
        _last_top1_score = current_top1
        _last_lb_push_time = now_ts
        with _async_lock:
            _async_state["leaderboard_data"] = copy.deepcopy(leaderboard)
            _async_state["leaderboard_metadata"] = {"run_id": str(run_id or "")}

def flush_sync_worker():
    """Synchronously force-flushes the async queue to DB and JSON files. Call this before exiting."""
    logger.info("Flushing sync worker queue to DB/JSON...")
    with _async_lock:
        prog_data = copy.deepcopy(_async_state.get("progress_data"))
        lb_data = copy.deepcopy(_async_state.get("leaderboard_data"))
        lb_metadata = copy.deepcopy(_async_state.get("leaderboard_metadata", {}))
        _async_state["progress_data"] = None
        _async_state["leaderboard_data"] = None
        _async_state["leaderboard_metadata"] = {}

    if prog_data:
        prog_path = os.path.join(DASHBOARD_DATA_DIR, "lab_progress.json")
        try:
            _write_json_atomic(prog_path, prog_data)
        except Exception:
            pass
        try:
            from bot.database import (
                LabProgressState,
                ensure_lab_progress_schema,
            )
            engine = _get_db_engine()
            if not ensure_lab_progress_schema(engine):
                raise RuntimeError("lab progress schema migration failed")
            Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            with Session() as sess:
                row = sess.query(LabProgressState).filter_by(id=1).first()
                if not row:
                    row = LabProgressState(id=1); sess.add(row)
                for k, v in prog_data.items():
                    if hasattr(row, k):
                        setattr(row, k, v)
                sess.commit()
        except Exception as e:
            logger.error(f"Flush failed for progress DB: {e}")

    if lb_data is not None:
        lb_path = os.path.join(DASHBOARD_DATA_DIR, "strategy_leaderboard.json")
        published_at = datetime.now(timezone.utc).isoformat()
        try:
            payload = {
                "updated_at": published_at,
                "run_id": lb_metadata.get("run_id", ""),
                "telemetry_schema_version": 2,
                "published_leader_count": len(lb_data),
                "strategies": lb_data
            }
            _write_json_atomic(lb_path, payload)
        except Exception:
            pass
        try:
            engine = _get_db_engine()
            Base.metadata.create_all(bind=engine)
            Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
            with Session() as sess:
                sess.query(StrategyLeaderboard).delete()
                for idx, item in enumerate(lb_data, 1):
                    stored_item = {
                        **item,
                        "run_id": lb_metadata.get("run_id", ""),
                        "telemetry_schema_version": 2,
                        "updated_at": published_at,
                        "published_leader_count": len(lb_data),
                    }
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
                         parameters_json=json.dumps(stored_item)
                    ))
                sess.commit()
        except Exception as e:
            logger.error(f"Flush failed for leaderboard DB: {e}")


def get_deduplicated_top10_gpu(lb_map: dict) -> list:
    from .config import REVERSE_STRAT_MAP
    
    # Screening-only placeholders are progress telemetry, not leaderboard or
    # promotion artifacts. Keep only candidates with complete metrics here.
    all_items = sorted(
        [item for item in lb_map.values() if item.get("full_evaluated", False)],
        # Qualification remains an OOS gate, but ordering among qualified
        # candidates uses the independent IS search score to reduce repeated
        # selection pressure on the same OOS observations.
        key=lambda x: (
            bool(x.get("qualified", False)),
            float(x.get("search_score", x.get("fitness_score", -1e9))),
            float(x.get("fitness_score", -1e9)),
        ),
        reverse=True,
    )
    unique, seen = [], set()
    strat_counts = {}  # Niche preservation: max 2 phenotypes per strategy
    
    for source_item in all_items:
        item = dict(source_item)
        params = item.get("parameters", {})
        key = tuple(sorted([(k, round(v, 4) if isinstance(v, float) else v) for k, v in params.items()]))
        
        strat_val = params.get("strategy_type", 0)
        try:
            strat_key = strategy_id(strat_val)
        except (TypeError, ValueError):
            # Malformed historical candidates must never silently become RSI
            # strategy 0 or reach the deployment UI.
            continue

        if key not in seen and strat_counts.get(strat_key, 0) < 2:
            seen.add(key)
            unique.append(attach_candidate_identity(item))
            strat_counts[strat_key] = strat_counts.get(strat_key, 0) + 1
            if len(unique) >= 10:
                break
                
    for idx, item in enumerate(unique, 1):
        item["rank"] = idx
        strat_val = item.get("parameters", {}).get("strategy_type", 0)
        try:
            strat_numeric_id = strategy_id(strat_val)
        except (TypeError, ValueError):
            strat_numeric_id = -1
        strat_name = REVERSE_STRAT_MAP.get(strat_numeric_id, f"Strat-{strat_numeric_id}")
        
        item["name"] = f"🏆 #{idx} [{strat_name}] ALPHA GENOME" if idx == 1 else f"#{idx} [{strat_name}] BLUEPRINT"
        
        t = item.get("total_trades_1y", 0)
        np_1y = item.get("net_profit_1y", 0.0)
        np_1y_dollar = item.get("net_profit_1y_dollar", np_1y * 10.0)
        if "avg_profit_per_trade_pct" not in item:
            item["avg_profit_per_trade_pct"] = round(np_1y / t, 3) if t > 0 else 0.0
        if "avg_profit_per_trade_dollar" not in item:
            item["avg_profit_per_trade_dollar"] = round(np_1y_dollar / t, 2) if t > 0 else 0.0
    return unique
