import json
import os
from types import SimpleNamespace

os.environ.setdefault("DASHBOARD_USER", "admin")
os.environ.setdefault(
    "DASHBOARD_PASS",
    "$2b$12$YAS0OpE/Cbn6z9QfTsmIsu7ZQRWt4ZLFRV9raRw4Tt9phonCHb01y",
)
os.environ.setdefault("DASHBOARD_SECRET_SALT", "paper-promotion-test-salt")
os.environ.setdefault("PAPER_TRADING", "True")

from candidate_evidence import attach_candidate_identity, candidate_artifact_hash


def _candidate():
    from lab_gpu.cost_model import cost_model_metadata

    return attach_candidate_identity({
        "evaluation_stage": "full_evaluated",
        "full_evaluated": True,
        "qualified": True,
        "fitness_score": 500.1,
        "net_profit_1m": 0.28,
        "net_profit_3m": 34.25,
        "net_profit_6m": 25.61,
        "net_profit_1y": 62.61,
        "is_profit_1y": 62.61,
        "oos_profit_1y": 35.28,
        "win_rate_1y": 50.4,
        "max_dd": 26.2,
        "total_trades_1y": 252,
        "oos_trades_1y": 62,
        "oos_max_dd": 11.2,
        "profit_factor": 1.84,
        "oos_profit_factor": 1.84,
        "oos_expectancy": 0.511,
        "is_fee_paid_1y_pct": 40.0,
        "oos_fee_paid_1y_pct": 21.2346,
        "fee_paid_1y_pct": 61.2346,
        "fee_paid_1y_dollar": 612.346,
        "parameters": {"strategy_type": "bb_squeeze", "sl_atr_mult": 1.6},
        **cost_model_metadata(),
    })


def test_db_backed_candidate_can_be_staged_to_paper(monkeypatch, tmp_path):
    """Paper promotion must survive the DB row round-trip without hash drift."""
    import api.server as server

    candidate = _candidate()
    db_row = SimpleNamespace(
        rank=1,
        name="🏆 #1 [bb_squeeze] ALPHA GENOME",
        # SQL float adapters can return a representation that is numerically
        # equivalent for display but different to the hash-bound JSON value.
        net_profit_1m=0.28000000000000003,
        net_profit_3m=34.25,
        net_profit_6m=25.61,
        net_profit_1y=62.61000000000001,
        win_rate_1y=50.4,
        max_drawdown=26.200000000000003,
        total_trades_1y=252,
        moonshots_1y=1,
        parameters_json=json.dumps({
            **candidate,
            "run_id": "run-1",
            "telemetry_schema_version": 2,
            "updated_at": "2026-09-04T00:00:00+00:00",
            "published_leader_count": 1,
        }),
    )

    manifest_dir = tmp_path / "dashboard" / "data"
    real_abspath = os.path.abspath

    def fake_abspath(path):
        if path == server.__file__:
            return str(tmp_path / "api" / "server.py")
        return real_abspath(path)

    control_state = {
        "paper_trading": True,
        "allow_live": False,
        "spot_paused": True,
        "futures_paused": True,
        "spot_paper_paused": True,
        "futures_paper_paused": True,
        "spot_live_paused": True,
        "futures_live_paused": True,
    }
    monkeypatch.setattr(server.os.path, "abspath", fake_abspath)
    monkeypatch.setattr(server, "get_bot_control", lambda: dict(control_state))
    monkeypatch.setattr(
        server,
        "set_bot_control",
        lambda **updates: (control_state.update(updates) or True),
    )
    monkeypatch.setattr(server, "is_execution_paused", lambda *args, **kwargs: True)
    monkeypatch.setattr(server, "_read_lab_progress_db_run_id", lambda: "run-1")
    monkeypatch.setattr(server, "_read_lab_progress_run_id", lambda: "")
    monkeypatch.setattr(server, "_read_leaderboard_snapshot", lambda: {
        "strategies": [server._format_leaderboard_row(db_row)],
        "telemetry_schema_version": 2,
        "run_id": "run-1",
        "updated_at": "2026-09-04T00:00:00+00:00",
        "published_leader_count": 1,
    })

    request = server.PromoteRequest(
        rank=1,
        stage="PAPER",
        candidate_id=candidate["candidate_id"],
        artifact_hash=candidate["artifact_hash"],
    )
    result = server.promote_strategy(request, True)

    assert result["status"] == "success"
    assert result["data"]["stage"] == "PAPER"
    assert candidate_artifact_hash(result["data"]["evidence"]) == candidate["artifact_hash"]
    assert (manifest_dir / "strategy_manifest.json").exists()


def test_deployment_status_does_not_leak_manifest_errors(monkeypatch, tmp_path):
    """Manifest read failures must remain generic for authenticated clients."""
    import api.server as server

    manifest_dir = tmp_path / "dashboard" / "data"
    manifest_dir.mkdir(parents=True)
    (manifest_dir / "strategy_manifest.json").write_text("{not-json", encoding="utf-8")
    real_abspath = os.path.abspath

    def fake_abspath(path):
        if path == server.__file__:
            return str(tmp_path / "api" / "server.py")
        return real_abspath(path)

    monkeypatch.setattr(server.os.path, "abspath", fake_abspath)

    result = server.get_strategy_deployment(True)

    assert result == {
        "active_strategy": None,
        "error": "Strategy manifest is unavailable",
    }
    assert str(tmp_path) not in result["error"]
