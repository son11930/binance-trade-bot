"""Stable identity and integrity evidence for strategy candidates."""

import hashlib
import json
import math
from typing import Any, Dict


CANDIDATE_VERSION = "phase39-v1"
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
    "fee_model_version",
    "fee_market_type",
    "taker_fee_rate_per_side",
    "round_trip_fee_rate",
    "atr_slippage_fraction",
    "funding_included",
    "is_fee_paid_1y_pct",
    "oos_fee_paid_1y_pct",
    "fee_paid_1y_pct",
    "fee_paid_1y_dollar",
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


def has_valid_cost_model_evidence(candidate: Dict[str, Any]) -> bool:
    """Require candidate evidence to describe the active fee assumptions."""
    from lab_gpu.cost_model import cost_model_metadata

    expected = cost_model_metadata()
    if candidate.get("fee_model_version") != expected["fee_model_version"]:
        return False
    if candidate.get("fee_market_type") != expected["fee_market_type"]:
        return False
    if candidate.get("funding_included") is not expected["funding_included"]:
        return False
    for key in (
        "taker_fee_rate_per_side",
        "round_trip_fee_rate",
        "atr_slippage_fraction",
    ):
        try:
            if not math.isclose(
                float(candidate.get(key)),
                float(expected[key]),
                rel_tol=1e-9,
                abs_tol=1e-12,
            ):
                return False
        except (TypeError, ValueError, OverflowError):
            return False
    for key in (
        "is_fee_paid_1y_pct",
        "oos_fee_paid_1y_pct",
        "fee_paid_1y_pct",
        "fee_paid_1y_dollar",
    ):
        try:
            value = float(candidate.get(key))
        except (TypeError, ValueError, OverflowError):
            return False
        if not math.isfinite(value) or value < 0.0:
            return False
    return True


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
