from __future__ import annotations

import hashlib
import importlib
import json
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from tests.helpers import load_module

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_livermore,
]



def _load_refresh_module():
    return load_module(
        "scripts.run_livermore_daily_pretrade_refresh",
        "scripts/run_livermore_daily_pretrade_refresh.py",
    )


@pytest.mark.parametrize("explicit", [False, True])
def test_cli_database_uses_settings_without_overriding_explicit_path(monkeypatch, tmp_path, explicit):
    module = _load_refresh_module()
    settings_module = importlib.import_module("backend.app.governance.settings")
    configured = str(tmp_path / "external storage" / "moss.duckdb")
    override = str(tmp_path / "explicit.duckdb")
    observed = {}

    def fake_run(**kwargs):
        observed.update(kwargs)
        return {"status": "dry_run"}

    monkeypatch.setattr(settings_module, "get_settings", lambda: SimpleNamespace(duckdb_path=configured))
    monkeypatch.setattr(module, "run_livermore_daily_pretrade_refresh", fake_run)
    monkeypatch.setattr(sys, "argv", ["daily-pretrade", "--dry-run", *(["--duckdb-path", override] if explicit else [])])

    assert module.main() == 0
    assert observed["duckdb_path"] == (override if explicit else configured)
    assert not (tmp_path / "external storage").exists()


def _create_ready_db(path: Path) -> None:
    conn = duckdb.connect(str(path), read_only=False)
    try:
        conn.execute("create table choice_stock_universe (as_of_date varchar)")
        conn.execute("create table choice_stock_sector_membership (as_of_date varchar)")
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar,
              open_value double,
              close_value double
            )
            """
        )
        conn.execute("create table choice_stock_limit_quality (as_of_date varchar)")
        conn.execute("create table choice_stock_factor_snapshot (as_of_date varchar)")
        conn.execute(
            "create table stock_adjustment_factor (stock_code varchar, trade_date varchar, adj_factor double)"
        )
        conn.execute("create table fact_choice_macro_daily (trade_date varchar, series_id varchar)")
        conn.execute(
            "create table fact_livermore_gate_supplement_daily "
            "(trade_date varchar, breadth_5d double, limit_up_quality_ok boolean)"
        )
        conn.execute("create table livermore_position_snapshot (as_of_date varchar, position_status varchar)")
        conn.execute("create table livermore_candidate_history (snapshot_as_of_date varchar, signal_kind varchar)")
        for table, column in [
            ("choice_stock_universe", "as_of_date"),
            ("choice_stock_sector_membership", "as_of_date"),
            ("choice_stock_limit_quality", "as_of_date"),
            ("choice_stock_factor_snapshot", "as_of_date"),
        ]:
            conn.execute(f"insert into {table} ({column}) values ('2026-06-01')")
        conn.execute(
            "insert into choice_stock_daily_observation values ('2026-06-01', '000001.SZ', 10.0, 10.5)"
        )
        conn.execute("insert into stock_adjustment_factor values ('000001.SZ', '2026-06-01', 1.0)")
        conn.execute(
            "insert into fact_livermore_gate_supplement_daily values ('2026-06-01', 0.2, false)"
        )
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
        name: {
            "ready": name in ready_names,
            "row_count": (1 if name in ready_names else 0),
        }
        for name in [
            "choice_stock_inputs",
            "factor_snapshot",
            "adjustment_factor",
            "csi300_macro",
            "gate_supplement",
            "position_snapshot",
            "candidate_history",
        ]
    }
    missing = [name for name, check in checks.items() if not check["ready"]]
    return {"target_date": "2026-06-01", "ready": not missing, "missing": missing, "checks": checks}


def _external_identity_profiles() -> list[dict[str, object]]:
    return [
        {"name": "choice_stock_catalog", "present": True, "content_sha256": "1" * 64},
        {
            "name": "cycle_rotation_macro_official_availability",
            "present": True,
            "content_sha256": "2" * 64,
        },
        {
            "name": "cycle_rotation_macro_official_releases",
            "present": True,
            "content_sha256": "3" * 64,
        },
        {
            "name": "macro_adversarial_signal_payload",
            "present": True,
            "content_sha256": "4" * 64,
        },
    ]


def _patch_external_input_capture(monkeypatch: pytest.MonkeyPatch) -> None:
    service = importlib.import_module("backend.app.services.market_data_livermore_service")
    profiles = _external_identity_profiles()
    monkeypatch.setattr(
        service,
        "capture_livermore_external_inputs",
        lambda _catalog: {"identity_profiles": profiles},
    )
    monkeypatch.setattr(
        service,
        "livermore_external_input_identities_match",
        lambda *_args, **_kwargs: True,
    )


def _verified_signal_confluence_result(
    *,
    status: str = "completed",
    reason: str | None = None,
    resolved_as_of_date: str = "2026-06-01",
    quality_flag: str = "ok",
    vendor_status: str = "ok",
    fallback_mode: str = "none",
    macro_authority_status: str = "ready",
    lineage_status: str = "complete",
    replay_maturity_status: str = "ready",
    replay_ready: bool = True,
    closed_loop_status: str = "blocked_by_adversarial",
    entry_gate: str = "blocked",
    adversarial_risk_gate: str = "block",
    allows_new_entry_observations: bool = True,
) -> dict[str, object]:
    payload = {
        "status": status,
        "target_date": "2026-06-01",
        "canonical_output_sha256": "c" * 64,
        "resolved_as_of_date": resolved_as_of_date,
        "meta": {
            "quality_flag": quality_flag,
            "vendor_status": vendor_status,
            "fallback_mode": fallback_mode,
        },
        "macro": {
            "status": "neutral",
            "authority_status": macro_authority_status,
            "authority_reasons": [],
        },
        "lineage_status": lineage_status,
        "replay": {
            "window_status": "ready" if replay_ready else "partial",
            "maturity_status": replay_maturity_status,
            "has_decision_usable_completed_stats": replay_ready,
            "completed_dates": 20 if replay_ready else 10,
            "blocking_pending_date_count": 0 if replay_ready else 2,
            "unsupported_dates": 0 if replay_ready else 3,
            "proxy_only_dates": 0 if replay_ready else 1,
            "matched_entry_count": 5 if replay_ready else 0,
            "has_required_horizon_stats": replay_ready,
        },
        "business_state": {
            "closed_loop_status": closed_loop_status,
            "entry_gate": entry_gate,
            "adversarial_risk_gate": adversarial_risk_gate,
            "adversarial_status": "ok",
            "allows_new_entry_observations": allows_new_entry_observations,
        },
    }
    if reason is not None:
        payload["reason"] = reason
    return payload


def test_confluence_uses_captured_external_content_without_reloading(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = importlib.import_module(
        "backend.app.services.livermore_signal_confluence_service"
    )
    conn = duckdb.connect(":memory:")
    captured = {
        "stock_readiness": object(),
        "availability_manifest_payload": {"manifest_version": "captured-A"},
        "releases_manifest_payload": {"manifest_version": "captured-A"},
        "adversarial_payload": {"status": "ok", "risk_gate": "block"},
        "adversarial_meta": {
            "source_version": "captured-A",
            "quality_flag": "ok",
            "vendor_version": "captured-A",
            "vendor_status": "ok",
            "fallback_mode": "none",
            "tables_used": [],
            "evidence_rows": 1,
        },
    }
    strategy_calls: list[dict[str, object]] = []

    def fake_strategy(_conn, **kwargs):
        assert _conn is conn
        strategy_calls.append(kwargs)
        return {
            "result": {
                "as_of_date": "2026-06-01",
                "market_gate": {"state": "HOT", "exposure": 0.6},
                "stock_candidates": {"items": []},
            },
            "result_meta": {
                "source_version": "strategy-A",
                "quality_flag": "ok",
                "vendor_version": "strategy-A",
                "vendor_status": "ok",
                "fallback_mode": "none",
                "tables_used": [],
                "evidence_rows": 0,
            },
        }

    monkeypatch.setattr(
        service,
        "livermore_strategy_envelope_from_catalog_from_connection",
        fake_strategy,
    )
    monkeypatch.setattr(
        service,
        "get_macro_environment_context",
        lambda *_args, **_kwargs: {"result": {}, "result_meta": {}},
    )
    monkeypatch.setattr(
        service,
        "livermore_candidate_history_backtest_window_summary",
        lambda **_kwargs: {},
    )
    monkeypatch.setattr(service, "_attach_replay_evidence", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(
        service,
        "load_macro_adversarial_signal_payload",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("the changed external loader must not be reopened")
        ),
    )
    try:
        envelope = service.livermore_signal_confluence_envelope(
            duckdb_path=":memory:",
            as_of_date="2026-06-01",
            choice_stock_catalog_file="changed-B.json",
            _conn=conn,
            _captured_external_inputs=captured,
        )
    finally:
        conn.close()

    assert strategy_calls[0]["captured_external_inputs"] is captured
    assert envelope["result"]["adversarial_context"]["risk_gate"] == "block"
    assert envelope["result_meta"]["source_version"].endswith("captured-A")


def test_actual_materializer_and_maturity_bind_final_candidate_identity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from backend.app.services import market_data_livermore_service as livermore_service
    from backend.app.services.pretrade_qualification import qualify_pretrade_read_view
    from backend.app.tasks import livermore_candidate_history_materialize as candidate_task
    from backend.app.tasks.livermore_candidate_outcome_maturity import (
        mature_livermore_candidate_outcomes,
    )
    from tests.test_market_data_livermore_api import (
        _ready_choice_stock_readiness,
        _seed_choice_macro_history,
        _seed_minimal_factor_snapshot,
    )

    module = _load_refresh_module()
    db_path = tmp_path / "actual-producer.duckdb"
    target_date = "2026-04-06"
    _seed_choice_macro_history(
        str(db_path),
        start=date(2026, 2, 1),
        closes=[3200.0 + day * 8 for day in range(65)],
    )
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        _seed_minimal_factor_snapshot(conn, as_of_date=target_date)
        for column, definition in (
            ("turn", "double"),
            ("highlimit", "double"),
            ("lowlimit", "double"),
            ("pctchange", "double"),
            ("volume", "double"),
        ):
            conn.execute(
                f"alter table choice_stock_daily_observation add column {column} {definition}"
            )
        conn.execute(
            "create table choice_stock_universe (as_of_date varchar, stock_code varchar)"
        )
        conn.execute(
            "create table choice_stock_sector_membership "
            "(as_of_date varchar, stock_code varchar)"
        )
        conn.execute(
            "create table choice_stock_limit_quality "
            "(as_of_date varchar, stock_code varchar, field_key varchar, "
            "issurgedlimit boolean, isdeclinelimit boolean, "
            "hlimitedays integer, llimitedays integer)"
        )
        conn.execute(
            "create table fact_livermore_gate_supplement_daily "
            "(trade_date varchar, breadth_5d double, limit_up_quality_ok boolean)"
        )
        for table in ("choice_stock_universe", "choice_stock_sector_membership"):
            conn.execute(
                f"insert into {table} values (?, ?)",
                [target_date, "688001.SH"],
            )
        conn.execute(
            "insert into choice_stock_limit_quality values "
            "(?, ?, 'daily_limit_flags', false, false, 0, 0)",
            [target_date, "688001.SH"],
        )
        conn.execute(
            "insert into fact_livermore_gate_supplement_daily values (?, 0.2, true)",
            [target_date],
        )
    finally:
        conn.close()
    readiness = _ready_choice_stock_readiness()
    monkeypatch.setattr(
        candidate_task,
        "_load_configured_stock_readiness",
        lambda: readiness,
    )
    monkeypatch.setattr(
        livermore_service,
        "load_choice_stock_readiness",
        lambda _catalog_file: readiness,
    )
    producer_result = candidate_task.materialize_livermore_candidate_history(
        str(db_path),
        as_of_date=target_date,
    )
    maturity_result = mature_livermore_candidate_outcomes(
        db_path,
        evaluation_as_of_date=target_date,
    )
    monkeypatch.setattr(
        module,
        "_verify_signal_confluence_closure",
        lambda **_kwargs: _verified_signal_confluence_result(
            resolved_as_of_date=target_date
        ),
    )

    candidate_status = (
        "ready_empty" if producer_result["empty_result"] is True else "ready"
    )
    qualified_view = module._build_completed_pretrade_view(
        duckdb_path=db_path,
        target_date=target_date,
        candidate_payload=producer_result,
        input_snapshot_before=producer_result["input_snapshot_before"],
        candidate_history_status=candidate_status,
        stock_candidate_policy=str(producer_result["stock_candidate_policy"]),
        top_n=10,
        lookback_days=90,
    )
    evidence = qualified_view["qualification"]
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        requalified = qualify_pretrade_read_view(
            conn,
            evidence=evidence,
            target_date=target_date,
            stock_candidate_policy=str(producer_result["stock_candidate_policy"]),
        )
    finally:
        conn.close()

    assert producer_result["status"] in {"ok", "completed"}
    assert maturity_result["status"] == "completed"
    assert evidence["outputs"]["candidate_history_sha256"] != producer_result[
        "candidate_history_sha256"
    ] or maturity_result.get("updated_row_count") == 0
    assert requalified["status"] == candidate_status


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
    assert state["checks"]["adjustment_factor"]["row_count"] == 1
    assert state["checks"]["csi300_macro"]["series"] == {
        "CA.CSI300": 1,
        "CA.CSI300_PCT_CHG": 1,
        "CA.CSI300_PE": 1,
    }


def test_inspect_refresh_state_requires_adjustment_factor_for_target_date(tmp_path: Path) -> None:
    module = _load_refresh_module()
    db_path = tmp_path / "moss.duckdb"
    _create_ready_db(db_path)
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute("delete from stock_adjustment_factor")
    finally:
        conn.close()

    state = module.inspect_livermore_daily_refresh_state(
        duckdb_path=db_path,
        target_date="2026-06-01",
    )

    assert state["ready"] is False
    assert "adjustment_factor" in state["missing"]
    assert state["checks"]["adjustment_factor"] == {
        "ready": False,
        "row_count": 0,
        "required_code_count": 1,
        "missing_code_count": 1,
    }


def test_inspect_refresh_state_rejects_null_limit_up_quality(tmp_path: Path) -> None:
    module = _load_refresh_module()
    db_path = tmp_path / "moss.duckdb"
    _create_ready_db(db_path)
    conn = duckdb.connect(str(db_path), read_only=False)
    try:
        conn.execute(
            "update fact_livermore_gate_supplement_daily set limit_up_quality_ok = null"
        )
    finally:
        conn.close()

    state = module.inspect_livermore_daily_refresh_state(
        duckdb_path=db_path,
        target_date="2026-06-01",
    )

    assert state["ready"] is False
    assert "gate_supplement" in state["missing"]
    assert state["checks"]["gate_supplement"] == {
        "ready": False,
        "row_count": 1,
        "usable_row_count": 0,
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
    _patch_external_input_capture(monkeypatch)
    db_path = tmp_path / "moss.duckdb"
    duckdb.connect(str(db_path), read_only=False).close()
    completed: set[str] = {"adjustment_factor"}
    ordered_calls: list[str] = []
    verifier_calls: list[dict[str, object]] = []

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
    maturity_module = importlib.import_module("backend.app.tasks.livermore_candidate_outcome_maturity")
    overlay_module = importlib.import_module("backend.app.tasks.choice_stock_theme_overlay_refresh")
    export_module = importlib.import_module("scripts.export_livermore_pretrade_check")
    monkeypatch.setattr(choice_module, "materialize_choice_stock_inputs", mark("choice_stock_inputs"))
    monkeypatch.setattr(choice_module, "materialize_choice_stock_factor_snapshot", mark("factor_snapshot"))
    monkeypatch.setattr(macro_module, "refresh_public_cross_asset_headlines", mark("csi300_macro"))
    monkeypatch.setattr(gate_module, "backfill_livermore_gate_supplement", mark("gate_supplement"))
    monkeypatch.setattr(position_module, "sync_livermore_position_snapshot", mark("position_snapshot"))
    monkeypatch.setattr(
        candidate_module,
        "materialize_livermore_candidate_history",
        mark(
            "candidate_history",
            {
                "status": "completed",
                "run_id": "candidate:test",
                "snapshot_as_of_date": "2026-06-01",
                "row_count": 30,
                "empty_result": False,
                "stock_candidate_policy": "fixture-policy",
                "rule_version": "fixture-rule",
                "strategy_payload_sha256": "a" * 64,
                "candidate_history_sha256": "b" * 64,
                "input_snapshot_before": {"fixture": True},
                "external_input_identity_profiles": _external_identity_profiles(),
            },
        ),
    )
    monkeypatch.setattr(
        maturity_module,
        "mature_livermore_candidate_outcomes",
        mark("candidate_outcome_maturity"),
    )
    monkeypatch.setattr(
        overlay_module,
        "refresh_choice_stock_theme_overlay",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("off overlay must not run")),
    )
    monkeypatch.setattr(
        export_module,
        "_build_livermore_pretrade_payload_from_connection",
        mark(
            "pretrade_export",
            {
                "status": "completed",
                "as_of_date": "2026-06-01",
                    "candidate_count": 30,
                    "decision": {"action": "review_only"},
                    "output_paths": {"json": "out.json"},
                    "rows": [],
            },
        ),
    )
    monkeypatch.setattr(
        export_module,
        "_write_outputs",
        lambda **_kwargs: {"json": "out.json"},
    )
    monkeypatch.setattr(
        module,
        "capture_pretrade_input_snapshot",
        lambda *_args, **_kwargs: {"fixture": True},
    )
    monkeypatch.setattr(
        module,
        "capture_pretrade_candidate_identity",
        lambda *_args, **_kwargs: "d" * 64,
    )
    monkeypatch.setattr(
        module,
        "build_completed_pretrade_qualification",
        lambda **_kwargs: {
            "schema": "pretrade_qualification/v1",
            "status": "ready",
            "producer_run_id": "candidate:test",
        },
    )
    monkeypatch.setattr(
        module,
        "_verify_signal_confluence_closure",
        lambda **kwargs: (
            ordered_calls.append("signal_confluence_closure")
            or verifier_calls.append(dict(kwargs))
            or _verified_signal_confluence_result()
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
        "candidate_outcome_maturity",
        "signal_confluence_closure",
        "pretrade_export",
    ]
    assert len(verifier_calls) == 1
    assert verifier_calls[0]["duckdb_path"] == db_path.resolve()
    assert verifier_calls[0]["target_date"] == "2026-06-01"
    assert isinstance(verifier_calls[0]["conn"], duckdb.DuckDBPyConnection)
    assert result["pretrade_output_paths"] == {"json": "out.json"}


def test_daily_pretrade_refresh_accepts_ready_empty_candidate_materialization_without_export(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_refresh_module()
    db_path = tmp_path / "moss.duckdb"
    duckdb.connect(str(db_path), read_only=False).close()
    completed = {
        "choice_stock_inputs",
        "factor_snapshot",
        "adjustment_factor",
        "csi300_macro",
        "gate_supplement",
        "position_snapshot",
    }
    ordered_calls: list[str] = []

    monkeypatch.setattr(
        module,
        "inspect_livermore_daily_refresh_state",
        lambda **_kwargs: _state(ready_names=completed),
    )
    candidate_module = importlib.import_module(
        "backend.app.tasks.livermore_candidate_history_materialize"
    )
    maturity_module = importlib.import_module(
        "backend.app.tasks.livermore_candidate_outcome_maturity"
    )
    export_module = importlib.import_module("scripts.export_livermore_pretrade_check")
    monkeypatch.setattr(
        candidate_module,
        "materialize_livermore_candidate_history",
        lambda *_args, **_kwargs: {
            "status": "ok",
            "row_count": 0,
            "empty_result": True,
            "snapshot_as_of_date": "2026-06-01",
            "skipped": ["no_strategy_signals"],
        },
    )
    monkeypatch.setattr(
        maturity_module,
        "mature_livermore_candidate_outcomes",
        lambda *_args, **_kwargs: {"status": "completed", "updated_row_count": 0},
    )
    monkeypatch.setattr(
        export_module,
        "export_livermore_pretrade_check",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("backend closure must not export operator files")
        ),
    )
    monkeypatch.setattr(
        module,
        "_verify_signal_confluence_closure",
        lambda *_args, **_kwargs: (
            ordered_calls.append("signal_confluence_closure")
            or _verified_signal_confluence_result()
        ),
    )

    result = module.run_livermore_daily_pretrade_refresh(
        duckdb_path=db_path,
        target_date="2026-06-01",
        skip_upstream_probe=True,
        export_pretrade=False,
    )

    assert result["status"] == "completed"
    assert result["candidate_history_status"] == "ready_empty"
    assert "pretrade_output_paths" not in result


def test_daily_pretrade_refresh_final_receipt_preserves_ready_empty_completion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = _load_refresh_module()
    db_path = tmp_path / "moss.duckdb"
    duckdb.connect(str(db_path), read_only=False).close()
    ready_except_candidate = {
        "choice_stock_inputs",
        "factor_snapshot",
        "adjustment_factor",
        "csi300_macro",
        "gate_supplement",
        "position_snapshot",
    }
    monkeypatch.setattr(
        module,
        "inspect_livermore_daily_refresh_state",
        lambda **_kwargs: _state(ready_names=ready_except_candidate),
    )
    monkeypatch.setattr(
        module,
        "probe_target_market_data_availability",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("derived candidate history must not require a vendor probe")
        ),
    )
    candidate_module = importlib.import_module(
        "backend.app.tasks.livermore_candidate_history_materialize"
    )
    maturity_module = importlib.import_module(
        "backend.app.tasks.livermore_candidate_outcome_maturity"
    )
    export_module = importlib.import_module("scripts.export_livermore_pretrade_check")
    monkeypatch.setattr(
        candidate_module,
        "materialize_livermore_candidate_history",
        lambda *_args, **_kwargs: {
            "status": "ok",
            "row_count": 0,
            "empty_result": True,
            "snapshot_as_of_date": "2026-06-01",
            "stock_candidate_policy": "fixture-policy",
            "input_snapshot_before": {"fixture": True},
        },
    )
    monkeypatch.setattr(
        maturity_module,
        "mature_livermore_candidate_outcomes",
        lambda *_args, **_kwargs: {"status": "completed", "updated_row_count": 0},
    )
    monkeypatch.setattr(
        module,
        "_build_completed_pretrade_view",
        lambda **_kwargs: {
            "signal_confluence": _verified_signal_confluence_result(),
            "pretrade_payload": {
                "status": "completed",
                "as_of_date": "2026-06-01",
                "rows": [],
                "decision": {"action": "no_candidates"},
            },
            "qualification": {
                "schema": "pretrade_qualification/v1",
                "status": "ready_empty",
            },
        },
    )
    monkeypatch.setattr(
        export_module,
        "_write_outputs",
        lambda **_kwargs: {"json": "out.json"},
    )

    result = module.run_livermore_daily_pretrade_refresh(
        duckdb_path=db_path,
        target_date="2026-06-01",
    )

    assert result["status"] == "completed"
    assert result["candidate_history_status"] == "ready_empty"
    assert result["pretrade_qualification"]["status"] == "ready_empty"
    assert result["local_state"]["ready"] is True
    assert result["local_state"]["checks"]["candidate_history"] == {
        "ready": True,
        "row_count": 0,
        "status": "ready_empty",
    }


def test_candidate_completion_does_not_hide_another_missing_dependency() -> None:
    module = _load_refresh_module()
    state = _state(
        ready_names={
            "choice_stock_inputs",
            "factor_snapshot",
            "adjustment_factor",
            "csi300_macro",
            "position_snapshot",
        }
    )

    result = module._with_candidate_history_completion(state, ready=True, row_count=0)

    assert result["ready"] is False
    assert result["missing"] == ["gate_supplement"]
    assert result["checks"]["candidate_history"]["status"] == "ready_empty"


def test_daily_pretrade_refresh_stops_when_gate_remains_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_refresh_module()
    db_path = tmp_path / "moss.duckdb"
    duckdb.connect(str(db_path), read_only=False).close()
    ready_without_gate = {
        "choice_stock_inputs",
        "factor_snapshot",
        "adjustment_factor",
        "csi300_macro",
        "position_snapshot",
        "candidate_history",
    }
    monkeypatch.setattr(
        module,
        "inspect_livermore_daily_refresh_state",
        lambda **_kwargs: _state(ready_names=ready_without_gate),
    )
    monkeypatch.setattr(
        module,
        "probe_target_market_data_availability",
        lambda **_kwargs: (_ for _ in ()).throw(
            AssertionError("derived gate supplement must not require a vendor probe")
        ),
    )
    gate_module = importlib.import_module("scripts.backfill_livermore_gate_supplement")
    monkeypatch.setattr(
        gate_module,
        "backfill_livermore_gate_supplement",
        lambda **_kwargs: {"status": "limit_price_incomplete"},
    )
    candidate_module = importlib.import_module(
        "backend.app.tasks.livermore_candidate_history_materialize"
    )
    maturity_module = importlib.import_module(
        "backend.app.tasks.livermore_candidate_outcome_maturity"
    )
    export_module = importlib.import_module("scripts.export_livermore_pretrade_check")
    forbidden_calls: list[str] = []
    monkeypatch.setattr(
        candidate_module,
        "materialize_livermore_candidate_history",
        lambda *_args, **_kwargs: forbidden_calls.append("candidate_history"),
    )
    monkeypatch.setattr(
        maturity_module,
        "mature_livermore_candidate_outcomes",
        lambda *_args, **_kwargs: forbidden_calls.append("candidate_outcome_maturity"),
    )
    monkeypatch.setattr(
        export_module,
        "export_livermore_pretrade_check",
        lambda **_kwargs: forbidden_calls.append("pretrade_export"),
    )

    result = module.run_livermore_daily_pretrade_refresh(
        duckdb_path=db_path,
        target_date="2026-06-01",
    )

    assert result["status"] == "not_ready"
    assert result["reason"] == "gate_supplement_not_landed_after_refresh"
    assert result["local_state"]["checks"]["gate_supplement"]["ready"] is False
    assert forbidden_calls == []


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
        "mature_livermore_candidate_outcomes",
        "verify_signal_confluence_closure",
    ]


def test_daily_pretrade_refresh_rejects_trailing_target_date_characters(tmp_path: Path) -> None:
    module = _load_refresh_module()
    db_path = tmp_path / "moss.duckdb"
    duckdb.connect(str(db_path), read_only=False).close()

    with pytest.raises(ValueError, match="valid YYYY-MM-DD"):
        module.run_livermore_daily_pretrade_refresh(
            duckdb_path=db_path,
            target_date="2026-06-01junk",
            dry_run=True,
        )


def test_daily_pretrade_refresh_global_dry_run_never_calls_requested_theme_overlay(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_refresh_module()
    db_path = tmp_path / "moss.duckdb"
    duckdb.connect(str(db_path), read_only=False).close()
    monkeypatch.setattr(
        module, "inspect_livermore_daily_refresh_state", lambda **_kwargs: _state()
    )
    overlay_module = importlib.import_module(
        "backend.app.tasks.choice_stock_theme_overlay_refresh"
    )
    monkeypatch.setattr(
        overlay_module,
        "refresh_choice_stock_theme_overlay",
        lambda **_kwargs: (_ for _ in ()).throw(AssertionError("overlay must not run")),
    )

    result = module.run_livermore_daily_pretrade_refresh(
        duckdb_path=db_path,
        target_date="2026-06-01",
        dry_run=True,
        theme_overlay_mode="archive",
    )

    assert result["status"] == "dry_run"
    assert result["theme_overlay_mode"] == "archive"
    assert result["would_run_steps"] == [
        "materialize_choice_stock_inputs",
        "materialize_choice_stock_factor_snapshot",
        "refresh_choice_stock_theme_overlay",
        "refresh_public_cross_asset_headlines",
        "backfill_livermore_gate_supplement",
        "sync_livermore_position_snapshot",
        "materialize_livermore_candidate_history",
        "mature_livermore_candidate_outcomes",
        "verify_signal_confluence_closure",
    ]


def test_daily_pretrade_refresh_keeps_core_output_when_requested_theme_overlay_fails(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_refresh_module()
    _patch_external_input_capture(monkeypatch)
    db_path = tmp_path / "moss.duckdb"
    governance_path = tmp_path / "governance"
    archive_root = tmp_path / "archive"
    duckdb.connect(str(db_path), read_only=False).close()
    parent_run_id = "choice_stock_materialize:2026-06-01:fixture"
    ordered_calls: list[str] = []
    overlay_calls: list[dict[str, object]] = []
    ready = {
        "choice_stock_inputs",
        "factor_snapshot",
        "adjustment_factor",
        "csi300_macro",
        "gate_supplement",
        "position_snapshot",
        "candidate_history",
    }
    monkeypatch.setattr(
        module,
        "inspect_livermore_daily_refresh_state",
        lambda **_kwargs: _state(ready_names=ready),
    )
    settings_module = importlib.import_module("backend.app.governance.settings")
    monkeypatch.setattr(
        settings_module,
        "get_settings",
            lambda: SimpleNamespace(
                governance_path=governance_path,
                local_archive_path=archive_root,
                choice_stock_catalog_file="tests/fixtures/choice-stock.json",
            ),
    )
    observation_module = importlib.import_module(
        "backend.app.tasks.choice_stock_observation_manifest"
    )
    monkeypatch.setattr(
        observation_module,
        "resolve_latest_committed_choice_stock_observation",
        lambda **_kwargs: SimpleNamespace(materialization_run_id=parent_run_id),
    )
    overlay_module = importlib.import_module(
        "backend.app.tasks.choice_stock_theme_overlay_refresh"
    )

    def fake_overlay(**kwargs: object) -> dict[str, object]:
        ordered_calls.append("theme_overlay")
        overlay_calls.append(dict(kwargs))
        return {
            "mode": "archive",
            "status": "source_failed",
            "overlay_status": "source_failed",
            "member_count": 0,
            "message": "THS unavailable",
            "run_id": kwargs["run_id"],
        }

    monkeypatch.setattr(
        overlay_module, "refresh_choice_stock_theme_overlay", fake_overlay
    )
    candidate_module = importlib.import_module("backend.app.tasks.livermore_candidate_history_materialize")
    maturity_module = importlib.import_module("backend.app.tasks.livermore_candidate_outcome_maturity")
    export_module = importlib.import_module("scripts.export_livermore_pretrade_check")
    monkeypatch.setattr(
        candidate_module,
        "materialize_livermore_candidate_history",
        lambda *_args, **_kwargs: (
            ordered_calls.append("candidate_history")
            or {
                "status": "completed",
                "run_id": "candidate:test",
                "snapshot_as_of_date": "2026-06-01",
                "row_count": 1,
                "empty_result": False,
                "stock_candidate_policy": "fixture-policy",
                "rule_version": "fixture-rule",
                "strategy_payload_sha256": "a" * 64,
                    "candidate_history_sha256": "b" * 64,
                    "input_snapshot_before": {"fixture": True},
                    "external_input_identity_profiles": _external_identity_profiles(),
            }
        ),
    )
    monkeypatch.setattr(
        maturity_module,
        "mature_livermore_candidate_outcomes",
        lambda *_args, **_kwargs: (
            ordered_calls.append("candidate_outcome_maturity")
            or {"status": "completed"}
        ),
    )
    monkeypatch.setattr(
        export_module,
        "_build_livermore_pretrade_payload_from_connection",
        lambda *_args, **_kwargs: (
            ordered_calls.append("pretrade_export")
            or {
                "status": "completed",
                "output_paths": {"json": "out.json"},
                "decision": {"action": "review_only"},
                "rows": [],
            }
        ),
    )
    monkeypatch.setattr(
        export_module,
        "_write_outputs",
        lambda **_kwargs: {"json": "out.json"},
    )
    monkeypatch.setattr(
        module,
        "capture_pretrade_input_snapshot",
        lambda *_args, **_kwargs: {"fixture": True},
    )
    monkeypatch.setattr(
        module,
        "capture_pretrade_candidate_identity",
        lambda *_args, **_kwargs: "d" * 64,
    )
    monkeypatch.setattr(
        module,
        "build_completed_pretrade_qualification",
        lambda **_kwargs: {
            "schema": "pretrade_qualification/v1",
            "status": "ready",
            "producer_run_id": "candidate:test",
        },
    )
    monkeypatch.setattr(
        module,
        "_verify_signal_confluence_closure",
        lambda **_kwargs: (
            ordered_calls.append("signal_confluence_closure")
            or _verified_signal_confluence_result()
        ),
    )

    result = module.run_livermore_daily_pretrade_refresh(
        duckdb_path=db_path,
        target_date="2026-06-01",
        skip_upstream_probe=True,
        theme_overlay_mode="archive",
    )

    digest = hashlib.sha256(f"{parent_run_id}|2026-06-01".encode()).hexdigest()[:16]
    assert overlay_calls == [
        {
            "mode": "archive",
            "duckdb_path": str(db_path.resolve()),
            "governance_dir": str(governance_path),
            "archive_root": str(archive_root),
            "expected_report_date": "2026-06-01",
            "run_id": f"{parent_run_id}:theme-overlay",
            "source_version": f"sv_choice_stock_theme_overlay_{digest}",
            "vendor_version": "vv_tushare_ths_current_overlay_v1",
        }
    ]
    assert ordered_calls == [
        "theme_overlay",
        "candidate_history",
        "candidate_outcome_maturity",
        "signal_confluence_closure",
        "pretrade_export",
    ]
    assert result["status"] == "partial"
    assert result["reason"] == "theme_overlay_failed"
    assert result["theme_overlay"]["status"] == "source_failed"
    assert result["pretrade_output_paths"] == {"json": "out.json"}


def test_daily_pretrade_refresh_surfaces_outcome_maturity_failure_and_skips_export(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_refresh_module()
    db_path = tmp_path / "moss.duckdb"
    duckdb.connect(str(db_path), read_only=False).close()
    export_calls: list[str] = []

    monkeypatch.setattr(
        module,
        "inspect_livermore_daily_refresh_state",
        lambda **_kwargs: _state(
            ready_names={
                "choice_stock_inputs",
                "factor_snapshot",
                "adjustment_factor",
                "csi300_macro",
                "gate_supplement",
                "position_snapshot",
                "candidate_history",
            }
        ),
    )
    candidate_module = importlib.import_module(
        "backend.app.tasks.livermore_candidate_history_materialize"
    )
    maturity_module = importlib.import_module(
        "backend.app.tasks.livermore_candidate_outcome_maturity"
    )
    export_module = importlib.import_module("scripts.export_livermore_pretrade_check")
    monkeypatch.setattr(
        candidate_module,
        "materialize_livermore_candidate_history",
        lambda *_args, **_kwargs: {"status": "completed"},
    )

    def fail_maturity(*_args, **_kwargs):
        raise RuntimeError("maturity write failed")

    monkeypatch.setattr(maturity_module, "mature_livermore_candidate_outcomes", fail_maturity)
    monkeypatch.setattr(
        export_module,
        "export_livermore_pretrade_check",
        lambda **_kwargs: export_calls.append("export"),
    )

    result = module.run_livermore_daily_pretrade_refresh(
        duckdb_path=db_path,
        target_date="2026-06-01",
        skip_upstream_probe=True,
    )

    assert result["status"] == "partial"
    assert result["reason"] == "candidate_outcome_maturity_failed"
    assert result["steps"][-1]["name"] == "candidate_outcome_maturity"
    assert result["steps"][-1]["result"]["status"] == "failed"
    assert "maturity write failed" in result["steps"][-1]["result"]["error"]
    assert export_calls == []


def test_daily_pretrade_refresh_fail_closes_noncompleted_outcome_maturity(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_refresh_module()
    db_path = tmp_path / "moss.duckdb"
    duckdb.connect(str(db_path), read_only=False).close()
    export_calls: list[str] = []
    ready = {
        "choice_stock_inputs",
        "factor_snapshot",
        "adjustment_factor",
        "csi300_macro",
        "gate_supplement",
        "position_snapshot",
        "candidate_history",
    }
    monkeypatch.setattr(
        module,
        "inspect_livermore_daily_refresh_state",
        lambda **_kwargs: _state(ready_names=ready),
    )
    candidate_module = importlib.import_module("backend.app.tasks.livermore_candidate_history_materialize")
    maturity_module = importlib.import_module("backend.app.tasks.livermore_candidate_outcome_maturity")
    export_module = importlib.import_module("scripts.export_livermore_pretrade_check")
    monkeypatch.setattr(
        candidate_module,
        "materialize_livermore_candidate_history",
        lambda *_args, **_kwargs: {"status": "completed"},
    )
    monkeypatch.setattr(
        maturity_module,
        "mature_livermore_candidate_outcomes",
        lambda *_args, **_kwargs: {
            "status": "not_ready",
            "reason": "missing_observation_table",
        },
    )
    monkeypatch.setattr(
        export_module,
        "export_livermore_pretrade_check",
        lambda **_kwargs: export_calls.append("export"),
    )

    result = module.run_livermore_daily_pretrade_refresh(
        duckdb_path=db_path,
        target_date="2026-06-01",
        skip_upstream_probe=True,
    )

    assert result["status"] == "partial"
    assert result["reason"] == "candidate_outcome_maturity_not_completed"
    assert result["steps"][-1] == {
        "name": "candidate_outcome_maturity",
        "result": {"status": "not_ready", "reason": "missing_observation_table"},
    }
    assert export_calls == []


def test_verify_signal_confluence_closure_fail_closes_as_of_mismatch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_refresh_module()
    db_path = tmp_path / "moss.duckdb"
    duckdb.connect(str(db_path), read_only=False).close()
    service_module = importlib.import_module(
        "backend.app.services.livermore_signal_confluence_service"
    )
    monkeypatch.setattr(
        service_module,
        "livermore_signal_confluence_envelope",
        lambda **_kwargs: {
            "result": {
                "as_of_date": "2026-05-30",
                "macro_context": {"authority_status": "ready"},
                "closed_loop_state": {
                    "status": "open",
                    "lineage_status": "complete",
                    "replay_status": {
                        "maturity_status": "ready",
                        "has_decision_usable_completed_stats": True,
                    },
                },
                "adversarial_context": {"risk_gate": "pass", "status": "ok"},
                "strategy_context": {"allows_new_entry_observations": True},
            },
            "result_meta": {
                "quality_flag": "ok",
                "vendor_status": "ok",
                "fallback_mode": "none",
            },
        },
    )

    result = module._verify_signal_confluence_closure(
        duckdb_path=db_path,
        target_date="2026-06-01",
        choice_stock_catalog_file="tests/fixtures/choice-stock.json",
    )

    assert result["status"] == "partial"
    assert result["reason"] == "signal_confluence_as_of_mismatch"
    assert result["resolved_as_of_date"] == "2026-05-30"


def test_verify_signal_confluence_closure_fail_closes_meta_unhealthy(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_refresh_module()
    db_path = tmp_path / "moss.duckdb"
    duckdb.connect(str(db_path), read_only=False).close()
    service_module = importlib.import_module(
        "backend.app.services.livermore_signal_confluence_service"
    )
    monkeypatch.setattr(
        service_module,
        "livermore_signal_confluence_envelope",
        lambda **_kwargs: {
            "result": {
                "as_of_date": "2026-06-01",
                "macro_context": {"authority_status": "ready"},
                "closed_loop_state": {
                    "status": "open",
                    "lineage_status": "complete",
                    "replay_status": {
                        "maturity_status": "ready",
                        "has_decision_usable_completed_stats": True,
                    },
                },
                "adversarial_context": {"risk_gate": "pass", "status": "ok"},
                "strategy_context": {"allows_new_entry_observations": True},
            },
            "result_meta": {
                "quality_flag": "warning",
                "vendor_status": "vendor_stale",
                "fallback_mode": "latest_snapshot",
            },
        },
    )

    result = module._verify_signal_confluence_closure(
        duckdb_path=db_path,
        target_date="2026-06-01",
        choice_stock_catalog_file="tests/fixtures/choice-stock.json",
    )

    assert result["status"] == "partial"
    assert result["reason"] == "signal_confluence_meta_unhealthy"
    assert result["meta_issues"] == [
        "quality_flag=warning",
        "vendor_status=vendor_stale",
        "fallback_mode=latest_snapshot",
    ]


def test_verify_signal_confluence_closure_fail_closes_lineage_incomplete(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_refresh_module()
    db_path = tmp_path / "moss.duckdb"
    duckdb.connect(str(db_path), read_only=False).close()
    service_module = importlib.import_module(
        "backend.app.services.livermore_signal_confluence_service"
    )
    monkeypatch.setattr(
        service_module,
        "livermore_signal_confluence_envelope",
        lambda **_kwargs: {
            "result": {
                "as_of_date": "2026-06-01",
                "macro_context": {"authority_status": "ready"},
                "closed_loop_state": {
                    "status": "open",
                    "lineage_status": "degraded",
                    "replay_status": {
                        "maturity_status": "ready",
                        "has_decision_usable_completed_stats": True,
                    },
                },
                "adversarial_context": {"risk_gate": "pass", "status": "ok"},
                "strategy_context": {"allows_new_entry_observations": True},
            },
            "result_meta": {
                "quality_flag": "ok",
                "vendor_status": "ok",
                "fallback_mode": "none",
            },
        },
    )

    result = module._verify_signal_confluence_closure(
        duckdb_path=db_path,
        target_date="2026-06-01",
        choice_stock_catalog_file="tests/fixtures/choice-stock.json",
    )

    assert result["status"] == "partial"
    assert result["reason"] == "signal_confluence_lineage_incomplete"


def test_daily_pretrade_refresh_fail_closes_when_signal_confluence_replay_not_ready(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_refresh_module()
    _patch_external_input_capture(monkeypatch)
    db_path = tmp_path / "moss.duckdb"
    duckdb.connect(str(db_path), read_only=False).close()
    ready = {
        "choice_stock_inputs",
        "factor_snapshot",
        "adjustment_factor",
        "csi300_macro",
        "gate_supplement",
        "position_snapshot",
        "candidate_history",
    }
    export_calls: list[str] = []
    monkeypatch.setattr(
        module,
        "inspect_livermore_daily_refresh_state",
        lambda **_kwargs: _state(ready_names=ready),
    )
    candidate_module = importlib.import_module(
        "backend.app.tasks.livermore_candidate_history_materialize"
    )
    maturity_module = importlib.import_module(
        "backend.app.tasks.livermore_candidate_outcome_maturity"
    )
    export_module = importlib.import_module("scripts.export_livermore_pretrade_check")
    monkeypatch.setattr(
        candidate_module,
        "materialize_livermore_candidate_history",
        lambda *_args, **_kwargs: {
            "status": "completed",
            "snapshot_as_of_date": "2026-06-01",
            "input_snapshot_before": {"fixture": True},
            "external_input_identity_profiles": _external_identity_profiles(),
        },
    )
    monkeypatch.setattr(
        maturity_module,
        "mature_livermore_candidate_outcomes",
        lambda *_args, **_kwargs: {"status": "completed"},
    )
    monkeypatch.setattr(
        export_module,
        "export_livermore_pretrade_check",
        lambda **_kwargs: export_calls.append("export"),
    )
    monkeypatch.setattr(
        module,
        "_verify_signal_confluence_closure",
        lambda **_kwargs: _verified_signal_confluence_result(
            status="partial",
            reason="signal_confluence_replay_not_ready",
            replay_maturity_status="partial",
            replay_ready=False,
        ),
    )

    result = module.run_livermore_daily_pretrade_refresh(
        duckdb_path=db_path,
        target_date="2026-06-01",
        skip_upstream_probe=True,
    )

    assert result["status"] == "partial"
    assert result["reason"] == "signal_confluence_replay_not_ready"
    assert result["steps"][-1]["name"] == "signal_confluence_closure"
    assert result["steps"][-1]["result"]["replay"]["maturity_status"] == "partial"
    assert export_calls == []


def test_daily_pretrade_refresh_fail_closes_when_signal_confluence_macro_authority_blocked(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_refresh_module()
    _patch_external_input_capture(monkeypatch)
    db_path = tmp_path / "moss.duckdb"
    duckdb.connect(str(db_path), read_only=False).close()
    ready = {
        "choice_stock_inputs",
        "factor_snapshot",
        "adjustment_factor",
        "csi300_macro",
        "gate_supplement",
        "position_snapshot",
        "candidate_history",
    }
    export_calls: list[str] = []
    monkeypatch.setattr(
        module,
        "inspect_livermore_daily_refresh_state",
        lambda **_kwargs: _state(ready_names=ready),
    )
    candidate_module = importlib.import_module(
        "backend.app.tasks.livermore_candidate_history_materialize"
    )
    maturity_module = importlib.import_module(
        "backend.app.tasks.livermore_candidate_outcome_maturity"
    )
    export_module = importlib.import_module("scripts.export_livermore_pretrade_check")
    monkeypatch.setattr(
        candidate_module,
        "materialize_livermore_candidate_history",
        lambda *_args, **_kwargs: {
            "status": "completed",
            "snapshot_as_of_date": "2026-06-01",
            "input_snapshot_before": {"fixture": True},
            "external_input_identity_profiles": _external_identity_profiles(),
        },
    )
    monkeypatch.setattr(
        maturity_module,
        "mature_livermore_candidate_outcomes",
        lambda *_args, **_kwargs: {"status": "completed"},
    )
    monkeypatch.setattr(
        export_module,
        "export_livermore_pretrade_check",
        lambda **_kwargs: export_calls.append("export"),
    )
    monkeypatch.setattr(
        module,
        "_verify_signal_confluence_closure",
        lambda **_kwargs: _verified_signal_confluence_result(
            status="partial",
            reason="signal_confluence_macro_authority_blocked",
            macro_authority_status="blocked",
        ),
    )

    result = module.run_livermore_daily_pretrade_refresh(
        duckdb_path=db_path,
        target_date="2026-06-01",
        skip_upstream_probe=True,
    )

    assert result["status"] == "partial"
    assert result["reason"] == "signal_confluence_macro_authority_blocked"
    assert result["steps"][-1]["result"]["macro"]["authority_status"] == "blocked"
    assert export_calls == []


def test_verify_signal_confluence_closure_accepts_business_blocked_when_data_is_complete(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_refresh_module()
    db_path = tmp_path / "moss.duckdb"
    duckdb.connect(str(db_path), read_only=False).close()
    service_module = importlib.import_module(
        "backend.app.services.livermore_signal_confluence_service"
    )
    monkeypatch.setattr(
        service_module,
        "livermore_signal_confluence_envelope",
        lambda **_kwargs: {
            "result": {
                "as_of_date": "2026-06-01",
                "macro_context": {"status": "neutral", "authority_status": "ready"},
                "closed_loop_state": {
                    "status": "blocked_by_adversarial",
                    "entry_gate": "blocked",
                    "lineage_status": "complete",
                    "replay_status": {
                        "window_status": "ready",
                        "maturity_status": "ready",
                        "has_decision_usable_completed_stats": True,
                        "completed_dates": 20,
                        "blocking_pending_date_count": 0,
                        "unsupported_dates": 0,
                        "proxy_only_dates": 0,
                        "matched_entry_count": 5,
                        "has_required_horizon_stats": True,
                    },
                },
                "adversarial_context": {"risk_gate": "block", "status": "ok"},
                "strategy_context": {"allows_new_entry_observations": True},
            },
            "result_meta": {
                "quality_flag": "ok",
                "vendor_status": "ok",
                "fallback_mode": "none",
            },
        },
    )

    result = module._verify_signal_confluence_closure(
        duckdb_path=db_path,
        target_date="2026-06-01",
        choice_stock_catalog_file="tests/fixtures/choice-stock.json",
    )

    assert result["status"] == "completed"
    assert result["business_state"]["closed_loop_status"] == "blocked_by_adversarial"
    assert result["business_state"]["adversarial_risk_gate"] == "block"


def test_verify_signal_confluence_closure_fail_closes_on_envelope_exception(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _load_refresh_module()
    db_path = tmp_path / "moss.duckdb"
    duckdb.connect(str(db_path), read_only=False).close()
    service_module = importlib.import_module(
        "backend.app.services.livermore_signal_confluence_service"
    )
    monkeypatch.setattr(
        service_module,
        "livermore_signal_confluence_envelope",
        lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("confluence read timeout")),
    )

    result = module._verify_signal_confluence_closure(
        duckdb_path=db_path,
        target_date="2026-06-01",
        choice_stock_catalog_file="tests/fixtures/choice-stock.json",
    )

    assert result == {
        "status": "partial",
        "reason": "signal_confluence_read_failed",
        "target_date": "2026-06-01",
        "error": "confluence read timeout",
    }


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
    assert [call["theme_overlay_mode"] for call in calls] == ["off", "off"]


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


def test_daily_pretrade_refresh_main_passes_theme_overlay_mode(monkeypatch, capsys) -> None:
    module = _load_refresh_module()
    calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        module,
        "run_livermore_daily_pretrade_refresh",
        lambda **kwargs: calls.append(dict(kwargs))
        or {
            "status": "completed",
            "theme_overlay_mode": kwargs["theme_overlay_mode"],
        },
    )
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_livermore_daily_pretrade_refresh.py",
            "--duckdb-path",
            "tmp/moss.duckdb",
            "--target-date",
            "2026-06-01",
            "--theme-overlay-mode",
            "archive",
        ],
    )

    exit_code = module.main()

    assert exit_code == 0
    assert calls[0]["theme_overlay_mode"] == "archive"
    assert json.loads(capsys.readouterr().out)["theme_overlay_mode"] == "archive"
