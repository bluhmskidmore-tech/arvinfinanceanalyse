from __future__ import annotations

import importlib
from pathlib import Path

import duckdb

from tests.helpers import load_module


def _load_refresh_module():
    return load_module(
        "scripts.run_livermore_daily_pretrade_refresh",
        "scripts/run_livermore_daily_pretrade_refresh.py",
    )


def _create_ready_db(path: Path) -> None:
    conn = duckdb.connect(str(path), read_only=False)
    try:
        conn.execute("create table choice_stock_universe (as_of_date varchar)")
        conn.execute("create table choice_stock_sector_membership (as_of_date varchar)")
        conn.execute("create table choice_stock_daily_observation (trade_date varchar)")
        conn.execute("create table choice_stock_limit_quality (as_of_date varchar)")
        conn.execute("create table choice_stock_factor_snapshot (as_of_date varchar)")
        conn.execute("create table fact_choice_macro_daily (trade_date varchar, series_id varchar)")
        conn.execute("create table fact_livermore_gate_supplement_daily (trade_date varchar)")
        conn.execute("create table livermore_position_snapshot (as_of_date varchar, position_status varchar)")
        conn.execute("create table livermore_candidate_history (snapshot_as_of_date varchar, signal_kind varchar)")
        for table, column in [
            ("choice_stock_universe", "as_of_date"),
            ("choice_stock_sector_membership", "as_of_date"),
            ("choice_stock_daily_observation", "trade_date"),
            ("choice_stock_limit_quality", "as_of_date"),
            ("choice_stock_factor_snapshot", "as_of_date"),
            ("fact_livermore_gate_supplement_daily", "trade_date"),
        ]:
            conn.execute(f"insert into {table} ({column}) values ('2026-06-01')")
        conn.executemany(
            "insert into fact_choice_macro_daily values ('2026-06-01', ?)",
            [("CA.CSI300",), ("CA.CSI300_PCT_CHG",), ("CA.CSI300_PE",)],
        )
        conn.execute("insert into livermore_position_snapshot values ('2026-06-01', 'ACTIVE')")
        conn.execute("insert into livermore_candidate_history values ('2026-06-01', 'factor_screen')")
    finally:
        conn.close()


def _state(*, ready_names: set[str] | None = None) -> dict[str, object]:
    ready_names = ready_names or set()
    checks = {
        name: {"ready": name in ready_names, "row_count": 1 if name in ready_names else 0}
        for name in [
            "choice_stock_inputs",
            "factor_snapshot",
            "csi300_macro",
            "gate_supplement",
            "position_snapshot",
            "candidate_history",
        ]
    }
    missing = [name for name, check in checks.items() if not check["ready"]]
    return {"target_date": "2026-06-01", "ready": not missing, "missing": missing, "checks": checks}


def test_inspect_livermore_daily_refresh_state_reports_ready(tmp_path: Path) -> None:
    module = _load_refresh_module()
    db_path = tmp_path / "moss.duckdb"
    _create_ready_db(db_path)

    state = module.inspect_livermore_daily_refresh_state(
        duckdb_path=db_path,
        target_date="2026-06-01",
    )

    assert state["ready"] is True
    assert state["missing"] == []
    assert state["checks"]["csi300_macro"]["series"] == {
        "CA.CSI300": 1,
        "CA.CSI300_PCT_CHG": 1,
        "CA.CSI300_PE": 1,
    }


def test_daily_pretrade_refresh_stops_when_upstream_probe_not_ready(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_refresh_module()
    db_path = tmp_path / "moss.duckdb"
    duckdb.connect(str(db_path), read_only=False).close()
    calls: list[str] = []

    monkeypatch.setattr(module, "inspect_livermore_daily_refresh_state", lambda **_kwargs: _state())
    monkeypatch.setattr(
        module,
        "probe_target_market_data_availability",
        lambda **_kwargs: {"status": "not_ready", "reason": "missing_csi300_daily"},
    )
    choice_module = importlib.import_module("backend.app.tasks.choice_stock_materialize")
    monkeypatch.setattr(
        choice_module,
        "materialize_choice_stock_inputs",
        lambda **_kwargs: calls.append("choice_stock_inputs"),
    )

    result = module.run_livermore_daily_pretrade_refresh(
        duckdb_path=db_path,
        target_date="2026-06-01",
    )

    assert result["status"] == "not_ready"
    assert result["reason"] == "target_market_data_not_landed"
    assert calls == []


def test_daily_pretrade_refresh_runs_full_pipeline_when_probe_ready(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_refresh_module()
    db_path = tmp_path / "moss.duckdb"
    duckdb.connect(str(db_path), read_only=False).close()
    completed: set[str] = set()
    ordered_calls: list[str] = []

    def fake_state(**_kwargs):
        return _state(ready_names=completed)

    def mark(name: str, payload: dict[str, object] | None = None):
        def _inner(*_args, **_kwargs):
            ordered_calls.append(name)
            completed.add(name)
            return payload or {"status": "completed", "name": name}

        return _inner

    monkeypatch.setattr(module, "inspect_livermore_daily_refresh_state", fake_state)
    monkeypatch.setattr(
        module,
        "probe_target_market_data_availability",
        lambda **_kwargs: {"status": "ready"},
    )
    choice_module = importlib.import_module("backend.app.tasks.choice_stock_materialize")
    macro_module = importlib.import_module("backend.app.tasks.choice_macro")
    gate_module = importlib.import_module("scripts.backfill_livermore_gate_supplement")
    position_module = importlib.import_module("scripts.sync_livermore_position_snapshot")
    candidate_module = importlib.import_module("backend.app.tasks.livermore_candidate_history_materialize")
    export_module = importlib.import_module("scripts.export_livermore_pretrade_check")
    monkeypatch.setattr(choice_module, "materialize_choice_stock_inputs", mark("choice_stock_inputs"))
    monkeypatch.setattr(choice_module, "materialize_choice_stock_factor_snapshot", mark("factor_snapshot"))
    monkeypatch.setattr(macro_module, "refresh_public_cross_asset_headlines", mark("csi300_macro"))
    monkeypatch.setattr(gate_module, "backfill_livermore_gate_supplement", mark("gate_supplement"))
    monkeypatch.setattr(position_module, "sync_livermore_position_snapshot", mark("position_snapshot"))
    monkeypatch.setattr(candidate_module, "materialize_livermore_candidate_history", mark("candidate_history"))
    monkeypatch.setattr(
        export_module,
        "export_livermore_pretrade_check",
        mark(
            "pretrade_export",
            {
                "status": "completed",
                "as_of_date": "2026-06-01",
                "candidate_count": 30,
                "decision": {"action": "review_only"},
                "output_paths": {"json": "out.json"},
            },
        ),
    )

    result = module.run_livermore_daily_pretrade_refresh(
        duckdb_path=db_path,
        target_date="2026-06-01",
        skip_upstream_probe=False,
    )

    assert result["status"] == "completed"
    assert ordered_calls == [
        "choice_stock_inputs",
        "factor_snapshot",
        "csi300_macro",
        "gate_supplement",
        "position_snapshot",
        "candidate_history",
        "pretrade_export",
    ]
    assert result["pretrade_output_paths"] == {"json": "out.json"}


def test_daily_pretrade_refresh_dry_run_reports_missing_steps(tmp_path: Path, monkeypatch) -> None:
    module = _load_refresh_module()
    db_path = tmp_path / "moss.duckdb"
    duckdb.connect(str(db_path), read_only=False).close()
    monkeypatch.setattr(
        module,
        "inspect_livermore_daily_refresh_state",
        lambda **_kwargs: _state(ready_names={"choice_stock_inputs"}),
    )

    result = module.run_livermore_daily_pretrade_refresh(
        duckdb_path=db_path,
        target_date="2026-06-01",
        dry_run=True,
    )

    assert result["status"] == "dry_run"
    assert result["would_run_steps"] == [
        "materialize_choice_stock_factor_snapshot",
        "refresh_public_cross_asset_headlines",
        "backfill_livermore_gate_supplement",
        "sync_livermore_position_snapshot",
        "materialize_livermore_candidate_history",
    ]


def test_monitor_livermore_daily_pretrade_refresh_retries_until_completed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_refresh_module()
    db_path = tmp_path / "moss.duckdb"
    duckdb.connect(str(db_path), read_only=False).close()
    attempts = [
        {"status": "not_ready", "reason": "target_market_data_not_landed"},
        {"status": "completed", "pretrade_output_paths": {"json": "out.json"}},
    ]
    calls: list[dict[str, object]] = []
    sleeps: list[float] = []

    def fake_run(**kwargs):
        calls.append(kwargs)
        return attempts.pop(0)

    monkeypatch.setattr(module, "run_livermore_daily_pretrade_refresh", fake_run)

    result = module.monitor_livermore_daily_pretrade_refresh(
        duckdb_path=db_path,
        target_date="2026-06-01",
        max_attempts=3,
        poll_interval_seconds=5,
        sleep_func=sleeps.append,
    )

    assert result["status"] == "completed"
    assert result["attempt_count"] == 2
    assert sleeps == [5]
    assert [call["target_date"] for call in calls] == ["2026-06-01", "2026-06-01"]


def test_monitor_livermore_daily_pretrade_refresh_stops_after_max_attempts(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_refresh_module()
    db_path = tmp_path / "moss.duckdb"
    duckdb.connect(str(db_path), read_only=False).close()
    sleeps: list[float] = []
    calls: list[dict[str, object]] = []

    def fake_run(**kwargs):
        calls.append(kwargs)
        return {"status": "not_ready", "reason": "target_market_data_not_landed"}

    monkeypatch.setattr(module, "run_livermore_daily_pretrade_refresh", fake_run)

    result = module.monitor_livermore_daily_pretrade_refresh(
        duckdb_path=db_path,
        target_date="2026-06-01",
        max_attempts=2,
        poll_interval_seconds=7,
        sleep_func=sleeps.append,
    )

    assert result["status"] == "not_ready"
    assert result["reason"] == "max_attempts_exhausted"
    assert result["attempt_count"] == 2
    assert len(result["attempts"]) == 2
    assert sleeps == [7]
    assert len(calls) == 2
