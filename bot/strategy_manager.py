import os
import json
import logging
import copy
import secrets
from typing import Dict, Any
from candidate_evidence import CANDIDATE_VERSION, candidate_artifact_hash
from .strategy_contract import normalize_strategy_parameters, strategy_id

_MANIFEST_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "dashboard", "data", "strategy_manifest.json")
_cached_strategy = None
_last_mtime = 0


def _validated_active_strategy(active: Any) -> Dict[str, Any]:
    """Validate promotion evidence before a manifest can influence execution."""
    if not isinstance(active, dict):
        return {}
    if active.get("stage") not in {"PAPER", "LIVE"}:
        return {}
    if active.get("candidate_version") not in {CANDIDATE_VERSION}:
        return {}
    candidate_id = str(active.get("candidate_id", ""))
    artifact_hash = str(active.get("artifact_hash", ""))
    evidence = active.get("evidence")
    if not isinstance(evidence, dict) or not evidence.get("full_evaluated") or not evidence.get("qualified"):
        return {}
    try:
        expected_hash = candidate_artifact_hash(evidence)
        if not secrets.compare_digest(artifact_hash, expected_hash):
            return {}
        if not secrets.compare_digest(candidate_id, f"gpu-{expected_hash[:20]}"):
            return {}
        active_parameters = active.get("parameters")
        evidence_parameters = evidence.get("parameters")
        if not isinstance(active_parameters, dict) or not isinstance(evidence_parameters, dict):
            return {}
        parameters = normalize_strategy_parameters(active_parameters)
        evidence_normalized = normalize_strategy_parameters(evidence_parameters)
        if parameters != evidence_normalized:
            return {}
        strategy_id(parameters["strategy_type"])
    except (TypeError, ValueError, KeyError):
        return {}

    # Return copies so callers cannot mutate the cached manifest object.
    return {
        **copy.deepcopy(active),
        "parameters": parameters,
        "evidence": copy.deepcopy(evidence),
    }

def get_active_strategy() -> Dict[str, Any]:
    global _cached_strategy, _last_mtime
    
    if not os.path.exists(_MANIFEST_PATH):
        _cached_strategy = None
        return {}
        
    try:
        current_mtime = os.stat(_MANIFEST_PATH).st_mtime_ns
        if current_mtime != _last_mtime or _cached_strategy is None:
            with open(_MANIFEST_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
                active = data.get("active_strategy", {})
                
                validated = _validated_active_strategy(active)
                if validated:
                    _cached_strategy = validated
                    logging.info(f"Loaded new strategy manifest: {active.get('name')} [{active.get('stage')}]")
                else:
                    logging.error("Rejected strategy manifest: missing or invalid promotion evidence")
                    _cached_strategy = None
                    
            _last_mtime = current_mtime
            
        return _cached_strategy
    except Exception as e:
        logging.error(f"Error reading strategy manifest: {e}")
        # Fail closed. Returning a stale strategy after a parse error could
        # send orders for evidence that no longer matches the manifest.
        _cached_strategy = None
        return {}
