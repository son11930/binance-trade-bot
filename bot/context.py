from dataclasses import dataclass

@dataclass(frozen=True)
class ExecutionContext:
    execution_mode: str  # "PAPER" or "LIVE"
    deployment_id: str
    strategy_id: str
    version: str
    artifact_hash: str = ""

    @property
    def is_paper(self) -> bool:
        return self.execution_mode.upper() == "PAPER"


def _context_matches_active_strategy(context, active_strategy: dict) -> bool:
    """Match a queued context to the exact validated manifest snapshot."""
    if context is None:
        return True

    active_deployment = str(active_strategy.get("id") or active_strategy.get("candidate_id") or "")
    active_strategy_id = str(active_strategy.get("name") or "")
    active_version = str(active_strategy.get("version") or "")
    active_hash = str(active_strategy.get("artifact_hash") or "")
    expected = (
        ("deployment_id", active_deployment),
        ("strategy_id", active_strategy_id),
        ("version", active_version),
        ("artifact_hash", active_hash),
    )
    for field_name, actual in expected:
        requested = str(getattr(context, field_name, "") or "")
        if requested and actual and requested != actual:
            return False
    return True


def validate_execution_context(
    state_manager,
    context,
    is_paper: bool,
    allow_protective_exit: bool = False,
) -> tuple[bool, str]:
    """Validate the execution lane again immediately before an order.

    ``ExecutionContext`` is a snapshot captured when a lane starts work.  The
    control file and manifest can change while an AI task is queued, so the
    executor must revalidate the snapshot at the exchange boundary.  A
    protective close may continue while entry execution is paused or the live
    unlock has been disarmed; it still cannot cross a Paper/Live manager
    boundary.
    """
    if not isinstance(is_paper, bool):
        return False, "execution mode must be a boolean"

    requested_mode = "PAPER" if is_paper else "LIVE"
    manager_mode = str(getattr(state_manager, "execution_mode", "PAPER")).strip().upper()
    if manager_mode != requested_mode:
        return False, f"state manager mode is {manager_mode}, requested {requested_mode}"

    context_mode = str(getattr(context, "execution_mode", requested_mode)).strip().upper() if context else requested_mode
    if context_mode != requested_mode:
        return False, f"execution context mode is {context_mode}, requested {requested_mode}"

    market = str(getattr(state_manager, "market_type", "spot")).strip().lower()
    if market not in {"spot", "futures"}:
        return False, "invalid market type"

    # Imports stay local to avoid a module cycle during bot startup.
    from .control import get_bot_control, is_execution_paused
    from .strategy_manager import get_active_strategy

    control = get_bot_control()
    if is_execution_paused(market, requested_mode, control=control) and not allow_protective_exit:
        return False, f"{requested_mode} {market} execution is paused"

    active_strategy = get_active_strategy()
    if not active_strategy:
        if requested_mode == "LIVE" and not allow_protective_exit:
            return False, "LIVE execution requires a validated strategy manifest"
        return True, ""

    active_stage = str(active_strategy.get("stage", "")).strip().upper()
    if active_stage != requested_mode and not allow_protective_exit:
        return False, f"manifest stage is {active_stage}, requested {requested_mode}"
    if not allow_protective_exit and not _context_matches_active_strategy(context, active_strategy):
        return False, "execution context does not match the active strategy manifest"
    if requested_mode == "LIVE" and not control.get("allow_live", False) and not allow_protective_exit:
        return False, "LIVE execution is locked"
    return True, ""
