"""Stable identity and integrity evidence for strategy candidates."""

import hashlib
import json
from typing import Any, Dict


CANDIDATE_VERSION = "phase36-v1"
_EVIDENCE_FIELDS = (
    "evaluation_stage",
    "full_evaluated",
    "qualified",
    "fitness_score",
    "net_profit_1m",
    "net_profit_3m",
    "net_profit_6m",
    "net_profit_1y",
    "is_profit_1y",
    "oos_profit_1y",
    "win_rate_1y",
    "max_dd",
    "total_trades_1y",
    "oos_trades_1y",
    "oos_max_dd",
    "profit_factor",
    "oos_profit_factor",
    "oos_expectancy",
    "parameters",
)


def _json_default(value: Any) -> Any:
    if hasattr(value, "item"):
        return value.item()
    raise TypeError(f"Unsupported evidence value: {type(value).__name__}")


def _evidence_payload(candidate: Dict[str, Any]) -> Dict[str, Any]:
    return {key: candidate.get(key) for key in _EVIDENCE_FIELDS}


def candidate_artifact_hash(candidate: Dict[str, Any]) -> str:
    """Hash only evaluation evidence and parameters, never mutable rank/name."""
    encoded = json.dumps(
        _evidence_payload(candidate),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        allow_nan=False,
        default=_json_default,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def attach_candidate_identity(candidate: Dict[str, Any]) -> Dict[str, Any]:
    """Return a copy with stable candidate identity and version evidence."""
    if not candidate.get("full_evaluated", False):
        raise ValueError("Only full-evaluated candidates can receive promotion evidence")
    artifact_hash = candidate_artifact_hash(candidate)
    result = dict(candidate)
    result.update({
        "candidate_id": f"gpu-{artifact_hash[:20]}",
        "candidate_version": CANDIDATE_VERSION,
        "artifact_hash": artifact_hash,
        "candidate_status": "qualified" if candidate.get("qualified", False) else "full_evaluated",
    })
    return result
