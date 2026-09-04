"""Atomic, mode-aware bot control state.

The legacy ``spot_paused`` and ``futures_paused`` flags remain as market-wide
kill switches.  Execution controls use the more specific ``*_paper_paused``
and ``*_live_paused`` flags so a paper run cannot resume or stop live trading
as a side effect.
"""

import json
import os
import threading
from contextlib import contextmanager

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTROL_FILE = os.path.join(BASE_DIR, "bot_control.json")
_lock = threading.Lock()
_latch_lock = threading.Lock()
_fail_closed_latches = set()


class ControlPersistenceError(RuntimeError):
    """Raised when a safety-critical control update cannot be persisted."""

VALID_MARKETS = frozenset({"spot", "futures"})
VALID_EXECUTION_MODES = frozenset({"PAPER", "LIVE"})

DEFAULT_CONTROL_STATE = {
    # Legacy market-wide pause flags.  These are retained as a hard kill
    # switch for compatibility and safety automation.
    "spot_paused": False,
    "futures_paused": False,
    # Start paper trading available, while live trading is fail-closed.
    "spot_paper_paused": False,
    "spot_live_paused": True,
    "futures_paper_paused": False,
    "futures_live_paused": True,
    "allow_live": False,
    # Legacy display/promotion snapshot.  It is not an execution authority.
    "paper_trading": True,
    "pause_reason": "",
}


def _strict_bool(value, default: bool) -> bool:
    """Parse persisted booleans without treating the string 'false' as true."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    return default


def _execution_pause_key(market: str, execution_mode: str) -> str:
    normalized_market = str(market).strip().lower()
    normalized_mode = str(execution_mode).strip().upper()
    if normalized_market not in VALID_MARKETS:
        raise ValueError("market must be 'spot' or 'futures'")
    if normalized_mode not in VALID_EXECUTION_MODES:
        raise ValueError("execution_mode must be 'PAPER' or 'LIVE'")
    return f"{normalized_market}_{normalized_mode.lower()}_paused"


def _normalise_state(raw_state) -> dict:
    raw = raw_state if isinstance(raw_state, dict) else {}
    state = {**DEFAULT_CONTROL_STATE, **raw}

    # Migrate older control files without accidentally making live available.
    # If an old market-wide pause was set, preserve it for both mode-specific
    # controls.  Otherwise paper keeps the old default and live stays closed.
    for market in VALID_MARKETS:
        legacy_paused = _strict_bool(raw.get(f"{market}_paused"), False)
        paper_key = _execution_pause_key(market, "PAPER")
        live_key = _execution_pause_key(market, "LIVE")
        if paper_key not in raw:
            state[paper_key] = legacy_paused
        if live_key not in raw:
            state[live_key] = True

    for key in (
        "spot_paused",
        "futures_paused",
        "spot_paper_paused",
        "spot_live_paused",
        "futures_paper_paused",
        "futures_live_paused",
        "allow_live",
        "paper_trading",
    ):
        state[key] = _strict_bool(state.get(key), DEFAULT_CONTROL_STATE[key])
    state["pause_reason"] = str(state.get("pause_reason", ""))
    return state


def _read_state_unlocked() -> dict:
    if not os.path.exists(CONTROL_FILE):
        return dict(DEFAULT_CONTROL_STATE)
    try:
        with open(CONTROL_FILE, "r", encoding="utf-8") as handle:
            return _normalise_state(json.load(handle))
    except Exception:
        return dict(DEFAULT_CONTROL_STATE)


def _control_lock_path() -> str:
    return f"{CONTROL_FILE}.lock"


def _fail_closed_path(key: str) -> str:
    return f"{CONTROL_FILE}.fail_closed.{key}"


@contextmanager
def _interprocess_control_lock():
    """Serialize control read/modify/write operations across API and bot processes."""
    lock_path = _control_lock_path()
    try:
        parent = os.path.dirname(lock_path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        handle = open(lock_path, "a+b")
    except Exception as exc:
        raise ControlPersistenceError(f"control lock unavailable: {exc}") from exc

    locked = False
    try:
        # msvcrt.locking requires an existing byte and append mode would
        # otherwise grow the lock file on every control update.
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            locked = True
        except Exception as exc:
            raise ControlPersistenceError(f"control lock unavailable: {exc}") from exc

        # Exceptions raised by the protected operation must propagate as-is;
        # only lock acquisition failures are converted to a persistence error.
        yield
    finally:
        if locked:
            try:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
            finally:
                handle.close()
        else:
            handle.close()


@contextmanager
def execution_control_lock():
    """Hold the shared control lock across an exchange-boundary operation."""
    with _interprocess_control_lock():
        yield


def _set_fail_closed_latch(market: str, execution_mode: str):
    key = _execution_pause_key(market, execution_mode)
    with _latch_lock:
        _fail_closed_latches.add(key)
    try:
        with open(_fail_closed_path(key), "a", encoding="utf-8"):
            pass
    except Exception:
        # The in-process latch still denies execution when the filesystem is
        # unavailable; the durable marker is best effort for the other process.
        pass


def _clear_fail_closed_latch(market: str, execution_mode: str):
    key = _execution_pause_key(market, execution_mode)
    with _latch_lock:
        _fail_closed_latches.discard(key)
    try:
        os.remove(_fail_closed_path(key))
    except FileNotFoundError:
        pass
    except Exception:
        pass


def _has_fail_closed_latch(market: str, execution_mode: str) -> bool:
    key = _execution_pause_key(market, execution_mode)
    with _latch_lock:
        return key in _fail_closed_latches or os.path.exists(_fail_closed_path(key))


def _write_state_unlocked(state: dict) -> bool:
    try:
        tmp_file = f"{CONTROL_FILE}.tmp"
        with open(tmp_file, "w", encoding="utf-8") as handle:
            json.dump(state, handle)
        os.replace(tmp_file, CONTROL_FILE)
        return True
    except Exception:
        # Control updates must never crash the trading process.  Callers still
        # receive the in-memory state they requested on the next read when the
        # filesystem is available again.
        return False


def get_bot_control() -> dict:
    with _lock:
        # Reads must remain side-effect free.  The API and bot run in
        # separate processes, so writing a normalized snapshot during a read
        # could overwrite a concurrent mode-specific pause update.  Writers
        # normalize and persist the complete state atomically instead.
        return dict(_read_state_unlocked())


def set_bot_control(
    spot_paused=None,
    futures_paused=None,
    allow_live=None,
    paper_trading=None,
    pause_reason=None,
    spot_paper_paused=None,
    spot_live_paused=None,
    futures_paper_paused=None,
    futures_live_paused=None,
):
    """Update control state atomically while preserving unrelated flags."""
    updates = {
        key: value
        for key, value in {
            "spot_paused": spot_paused,
            "futures_paused": futures_paused,
            "allow_live": allow_live,
            "paper_trading": paper_trading,
            "pause_reason": pause_reason,
            "spot_paper_paused": spot_paper_paused,
            "spot_live_paused": spot_live_paused,
            "futures_paper_paused": futures_paper_paused,
            "futures_live_paused": futures_live_paused,
        }.items()
        if value is not None
    }

    try:
        with _interprocess_control_lock():
            with _lock:
                current_state = _read_state_unlocked()
                next_state = _normalise_state({**current_state, **updates})
                persisted = _write_state_unlocked(next_state)
    except ControlPersistenceError:
        persisted = False

    if not persisted:
        for market in VALID_MARKETS:
            if updates.get(f"{market}_paused") is True:
                _set_fail_closed_latch(market, "PAPER")
                _set_fail_closed_latch(market, "LIVE")
            for mode in VALID_EXECUTION_MODES:
                if updates.get(_execution_pause_key(market, mode)) is True:
                    _set_fail_closed_latch(market, mode)
                if mode == "LIVE" and updates.get("allow_live") is False:
                    _set_fail_closed_latch(market, mode)
    return persisted


def set_execution_pause(market: str, execution_mode: str, paused: bool, reason=None) -> dict:
    """Pause/resume exactly one market and execution mode."""
    key = _execution_pause_key(market, execution_mode)
    updates = {key: bool(paused)}
    if reason is not None:
        updates["pause_reason"] = str(reason)

    try:
        with _interprocess_control_lock():
            with _lock:
                current_state = _read_state_unlocked()
                next_state = _normalise_state({**current_state, **updates})
                if not _write_state_unlocked(next_state):
                    raise ControlPersistenceError("control state write failed")
    except ControlPersistenceError:
        _set_fail_closed_latch(market, execution_mode)
        raise

    if paused:
        _set_fail_closed_latch(market, execution_mode)
    else:
        _clear_fail_closed_latch(market, execution_mode)
    return dict(next_state)


def is_execution_paused(market: str, execution_mode: str, control: dict | None = None) -> bool:
    """Return the effective pause state, including the market kill switch."""
    key = _execution_pause_key(market, execution_mode)
    state = _normalise_state(control) if control is not None else get_bot_control()
    market_key = f"{str(market).strip().lower()}_paused"
    return bool(state.get(market_key, True) or state.get(key, True) or _has_fail_closed_latch(market, execution_mode))


def get_execution_control(market: str, execution_mode: str, control: dict | None = None) -> dict:
    """Return a stable, serializable view for one execution lane."""
    key = _execution_pause_key(market, execution_mode)
    state = _normalise_state(control) if control is not None else get_bot_control()
    market_key = f"{str(market).strip().lower()}_paused"
    safety_latched = _has_fail_closed_latch(market, execution_mode)
    return {
        "market": str(market).strip().lower(),
        "execution_mode": str(execution_mode).strip().upper(),
        "paused": bool(state.get(key, True)),
        "market_kill_switch": bool(state.get(market_key, True)),
        "effective_paused": bool(state.get(market_key, True) or state.get(key, True) or safety_latched),
        "safety_latched": safety_latched,
        "allow_live": bool(state.get("allow_live", False)),
        "pause_reason": state.get("pause_reason", ""),
    }
