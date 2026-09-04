"""Durable recovery journal for confirmed fills that could not be recorded."""

import json
import os
import threading
import uuid
from datetime import datetime, timezone


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOURNAL_DIR = os.path.join(BASE_DIR, "dashboard", "data")
_journal_lock = threading.Lock()


def _journal_path(market_type: str, execution_mode: str) -> str:
    market = str(market_type).strip().lower()
    mode = str(execution_mode).strip().upper()
    if market not in {"spot", "futures"}:
        raise ValueError("market_type must be 'spot' or 'futures'")
    if mode not in {"PAPER", "LIVE"}:
        raise ValueError("execution_mode must be 'PAPER' or 'LIVE'")
    return os.path.join(JOURNAL_DIR, f"execution_journal_{market}_{mode.lower()}.jsonl")


def _read_pending_records(market_type: str, execution_mode: str) -> list[dict] | None:
    path = _journal_path(market_type, execution_mode)
    if not os.path.exists(path):
        return []
    records = []
    malformed = False
    try:
        with _journal_lock:
            with open(path, "r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        record = json.loads(line)
                    except (TypeError, ValueError):
                        malformed = True
                        continue
                    if not isinstance(record, dict) or record.get("status") not in {"PENDING", "RESOLVED"}:
                        malformed = True
                        continue
                    if record.get("status") == "PENDING":
                        records.append(record)
    except OSError:
        # An unreadable journal is unsafe to treat as empty: keep the lane
        # blocked until an operator can reconcile the storage problem.
        return None
    return None if malformed else records


def has_pending_execution(market_type: str, execution_mode: str) -> bool:
    """Return whether a lane has a fill awaiting durable DB reconciliation."""
    records = _read_pending_records(market_type, execution_mode)
    return records is None or bool(records)


def record_pending_execution(record: dict) -> bool:
    """Fsync a minimal fill record before exposing a failed journal write."""
    if not isinstance(record, dict):
        return False
    try:
        market = str(record["market_type"]).strip().lower()
        mode = str(record["execution_mode"]).strip().upper()
        path = _journal_path(market, mode)
        payload = {
            "journal_id": uuid.uuid4().hex,
            "status": "PENDING",
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            "market_type": market,
            "execution_mode": mode,
            "symbol": str(record.get("symbol", "")),
            "side": str(record.get("side", "")),
            "position_side": record.get("position_side"),
            "price": float(record.get("price", 0.0)),
            "quantity": float(record.get("quantity", 0.0)),
            "fee": float(record.get("fee", 0.0) or 0.0),
            "fee_asset": str(record.get("fee_asset", "USDT")),
            "pnl_amount": record.get("pnl_amount"),
            "pnl_percent": record.get("pnl_percent"),
            "reason": str(record.get("reason", "")),
            "deployment_id": record.get("deployment_id"),
            "strategy_id": record.get("strategy_id"),
            "execution_status": str(record.get("execution_status", "FILLED")),
            "partial_fill": bool(record.get("partial_fill", False)),
            "exchange_order_id": record.get("orderId"),
            "client_order_id": record.get("clientOrderId") or record.get("origClientOrderId"),
        }
        if not payload["symbol"] or payload["side"] not in {"BUY", "SELL"} or payload["quantity"] <= 0:
            return False
        if payload["price"] <= 0:
            return False
        encoded = json.dumps(payload, ensure_ascii=True, allow_nan=False)
        with _journal_lock:
            os.makedirs(JOURNAL_DIR, exist_ok=True)
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(encoded + "\n")
                handle.flush()
                os.fsync(handle.fileno())
        return True
    except (OSError, TypeError, ValueError):
        return False


def _as_datetime(value) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)


def _same_fill(row, record: dict, recorded_at: datetime) -> bool:
    try:
        quantity = float(record["quantity"])
        price = float(record["price"])
        row_quantity = float(row.quantity)
        row_price = float(row.price)
    except (TypeError, ValueError):
        return False
    row_timestamp = row.timestamp
    if row_timestamp is not None:
        row_timestamp = row_timestamp if row_timestamp.tzinfo else row_timestamp.replace(tzinfo=timezone.utc)
        if abs((row_timestamp - recorded_at).total_seconds()) > 900:
            return False
    return (
        row.symbol == record.get("symbol")
        and row.side == record.get("side")
        and abs(row_quantity - quantity) <= max(1e-12, abs(quantity) * 1e-6)
        and abs(row_price - price) <= max(1e-8, abs(price) * 1e-6)
        and bool(row.paper_trade) == (record.get("execution_mode") == "PAPER")
        and row.execution_mode == record.get("execution_mode")
    )


def _rewrite_without_journal_ids(market_type: str, execution_mode: str, resolved_ids: set[str]) -> bool:
    path = _journal_path(market_type, execution_mode)
    try:
        with _journal_lock:
            if not os.path.exists(path):
                return True
            remaining = []
            with open(path, "r", encoding="utf-8") as handle:
                for line in handle:
                    try:
                        record = json.loads(line)
                    except (TypeError, ValueError):
                        remaining.append(line)
                        continue
                    if not isinstance(record, dict) or record.get("journal_id") not in resolved_ids:
                        remaining.append(line)
            if remaining:
                tmp_path = f"{path}.tmp"
                with open(tmp_path, "w", encoding="utf-8") as handle:
                    handle.writelines(remaining)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(tmp_path, path)
            else:
                os.remove(path)
        return True
    except OSError:
        return False


def reconcile_pending_executions(market_type: str, execution_mode: str) -> bool:
    """Replay confirmed journal entries, then allow the lane to resume."""
    records = _read_pending_records(market_type, execution_mode)
    if records is None:
        return False
    if not records:
        return True

    mode = str(execution_mode).strip().upper()
    market = str(market_type).strip().lower()
    try:
        from .database import SessionLocalFutures, SessionLocalSpot, Trade
        session_factory = SessionLocalFutures if market == "futures" else SessionLocalSpot
        with session_factory() as db:
            resolved_ids = set()
            for record in records:
                recorded_at = _as_datetime(record.get("recorded_at"))
                query = db.query(Trade).filter(
                    Trade.symbol == record.get("symbol"),
                    Trade.side == record.get("side"),
                    Trade.market_type == market,
                    Trade.paper_trade == (mode == "PAPER"),
                    Trade.execution_mode == mode,
                )
                existing = query.order_by(Trade.timestamp.desc(), Trade.id.desc()).limit(20).all()
                if not any(_same_fill(row, record, recorded_at) for row in existing):
                    db.add(Trade(
                        symbol=record["symbol"],
                        side=record["side"],
                        price=float(record["price"]),
                        quantity=float(record["quantity"]),
                        ai_reasoning=record.get("reason"),
                        paper_trade=(mode == "PAPER"),
                        fee=float(record.get("fee", 0.0) or 0.0),
                        fee_asset=record.get("fee_asset", "USDT"),
                        pnl_amount=record.get("pnl_amount"),
                        pnl_percent=record.get("pnl_percent"),
                        position_side=record.get("position_side"),
                        market_type=market,
                        execution_mode=mode,
                        deployment_id=record.get("deployment_id"),
                        strategy_id=record.get("strategy_id"),
                        timestamp=recorded_at,
                    ))
                resolved_ids.add(str(record.get("journal_id", "")))
            db.commit()
        return _rewrite_without_journal_ids(market, mode, resolved_ids)
    except Exception:
        return False
