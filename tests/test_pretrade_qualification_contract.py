from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import duckdb
import pytest

from backend.app.services.pretrade_checklist_service import (
    DEFAULT_STOCK_CANDIDATE_POLICY,
    pretrade_checklist_envelope,
)
from backend.app.services.pretrade_qualification import (
    build_completed_pretrade_qualification,
    canonical_pretrade_export_projection_sha256,
    canonical_pretrade_output_sha256,
    capture_pretrade_candidate_identity,
    capture_pretrade_input_snapshot,
    normalize_pretrade_qualification,
    qualify_sealed_pretrade_read,
)
from scripts.export_livermore_pretrade_check import (
    export_livermore_pretrade_check,
)
from tests.test_pretrade_checklist import AS_OF, TODAY_FRESH, _build_synthetic_db

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]


@pytest.mark.unit
def test_checklist_with_old_rows_but_no_completed_provenance_is_unavailable(
    tmp_path: Path,
) -> None:
    db_path = tmp_path / "pretrade.duckdb"
    _build_synthetic_db(db_path)

    envelope = pretrade_checklist_envelope(duckdb_path=db_path, today=TODAY_FRESH)

    assert envelope is not None
    result = envelope["result"]
    assert result["checklist_status"] == "unavailable"
    assert result["qualification"] == {
        "schema": "pretrade_qualification/v1",
        "status": "unavailable",
        "reason": "completed_pretrade_provenance_missing",
    }
    assert result["items"] == []
    assert result["position_size_hint"] is None


@pytest.mark.unit
def test_export_without_completed_provenance_writes_nothing(tmp_path: Path) -> None:
    db_path = tmp_path / "pretrade.duckdb"
    output_dir = tmp_path / "export"
    _build_synthetic_db(db_path)

    with pytest.raises(ValueError, match="Completed pretrade provenance is unavailable"):
        export_livermore_pretrade_check(
            duckdb_path=db_path,
            output_dir=output_dir,
            today=TODAY_FRESH,
        )

    assert not output_dir.exists()


def _add_required_source_inputs(db_path: Path) -> None:
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute("create table choice_stock_universe (as_of_date varchar, stock_code varchar)")
        conn.execute("create table choice_stock_sector_membership (as_of_date varchar, stock_code varchar)")
        conn.execute("create table choice_stock_limit_quality (as_of_date varchar, stock_code varchar)")
        conn.execute("create table choice_stock_factor_snapshot (as_of_date varchar, stock_code varchar)")
        conn.execute(
            "create table fact_livermore_gate_supplement_daily "
            "(trade_date varchar, breadth_5d double, limit_up_quality_ok boolean)"
        )
        conn.execute(
            "create table fact_choice_macro_daily "
            "(trade_date varchar, series_id varchar, value_numeric double)"
        )
        for table in (
            "choice_stock_universe",
            "choice_stock_sector_membership",
            "choice_stock_limit_quality",
            "choice_stock_factor_snapshot",
        ):
            conn.execute(f"insert into {table} values (?, ?)", [AS_OF, "600001.SH"])
        conn.execute(
            "insert into fact_livermore_gate_supplement_daily values (?, 0.2, true)",
            [AS_OF],
        )
        conn.executemany(
            "insert into fact_choice_macro_daily values (?, ?, ?)",
            [
                (AS_OF, "CA.CSI300", 4000.0),
                (AS_OF, "CA.CSI300_PCT_CHG", 0.01),
                (AS_OF, "CA.CSI300_PE", 12.0),
                (AS_OF, "PMI", 50.0),
            ],
        )
    finally:
        conn.close()


def _rule_identity() -> dict[str, object]:
    return {
        "candidate_rule_version": "rv_livermore_candidate_history_v1",
        "checklist_rule_version": "rv_pretrade_checklist_v1",
        "export_rule_version": "rv_livermore_pretrade_export_v1",
        "lookback_days": 90,
        "signal_confluence_contract": "livermore_signal_confluence/v1",
        "stale_calendar_days": 5,
        "stock_candidate_policy": DEFAULT_STOCK_CANDIDATE_POLICY,
        "strategy_calculation_mode": "historical_backfill",
        "top_n": 10,
    }


def _completed_evidence(db_path: Path, *, empty_result: bool = False) -> dict[str, object]:
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        snapshot = capture_pretrade_input_snapshot(
            conn,
            target_date=AS_OF,
            stock_candidate_policy=DEFAULT_STOCK_CANDIDATE_POLICY,
        )
        candidate_sha = capture_pretrade_candidate_identity(conn, target_date=AS_OF)
        row_count = int(
            conn.execute(
                "select count(*) from livermore_candidate_history "
                "where snapshot_as_of_date = ?",
                [AS_OF],
            ).fetchone()[0]
        )
    finally:
        conn.close()
    producer_result = {
        "status": "ok",
        "run_id": "livermore_candidate_history:test:new",
        "snapshot_as_of_date": AS_OF,
        "row_count": row_count,
        "empty_result": empty_result,
        "stock_candidate_policy": DEFAULT_STOCK_CANDIDATE_POLICY,
        "rule_version": "rv_livermore_candidate_history_v1",
        "strategy_payload_sha256": canonical_pretrade_output_sha256(
            {"as_of_date": AS_OF, "decision_inputs": "new-run"}
        ),
        "candidate_history_sha256": candidate_sha,
    }
    return build_completed_pretrade_qualification(
        producer_result=producer_result,
        input_snapshot_before=snapshot,
        input_snapshot_after=snapshot,
        confluence_payload={
            "status": "completed",
            "target_date": AS_OF,
            "canonical_output_sha256": "c" * 64,
        },
        export_payload={"status": "completed", "as_of_date": AS_OF, "rows": []},
        rule_identity=_rule_identity(),
    )


@pytest.mark.unit
def test_completed_producer_evidence_restores_ready_checklist(tmp_path: Path) -> None:
    db_path = tmp_path / "pretrade.duckdb"
    _build_synthetic_db(db_path)
    _add_required_source_inputs(db_path)
    evidence = _completed_evidence(db_path)

    envelope = pretrade_checklist_envelope(
        duckdb_path=db_path,
        today=TODAY_FRESH,
        qualification_evidence=evidence,
    )

    assert envelope is not None
    result = envelope["result"]
    assert result["checklist_status"] == "ok"
    assert result["qualification"]["status"] == "ready"
    assert result["qualification"]["producer_run_id"].endswith(":new")
    assert result["items"]
    assert result["position_size_hint"]["items"]


@pytest.mark.unit
def test_completed_empty_producer_evidence_restores_ready_empty(tmp_path: Path) -> None:
    db_path = tmp_path / "pretrade.duckdb"
    _build_synthetic_db(db_path)
    _add_required_source_inputs(db_path)
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute("delete from livermore_candidate_history")
    finally:
        conn.close()
    evidence = _completed_evidence(db_path, empty_result=True)

    envelope = pretrade_checklist_envelope(
        duckdb_path=db_path,
        as_of_date=AS_OF,
        today=TODAY_FRESH,
        qualification_evidence=evidence,
    )

    assert envelope is not None
    result = envelope["result"]
    assert result["checklist_status"] == "empty"
    assert result["qualification"]["status"] == "ready_empty"
    assert result["items"] == []


@pytest.mark.unit
def test_macro_content_change_with_same_candidates_rejects_completion(tmp_path: Path) -> None:
    db_path = tmp_path / "pretrade.duckdb"
    _build_synthetic_db(db_path)
    _add_required_source_inputs(db_path)
    conn = duckdb.connect(str(db_path))
    try:
        before = capture_pretrade_input_snapshot(
            conn,
            target_date=AS_OF,
            stock_candidate_policy=DEFAULT_STOCK_CANDIDATE_POLICY,
        )
        candidate_sha = capture_pretrade_candidate_identity(conn, target_date=AS_OF)
        conn.execute(
            "update fact_choice_macro_daily set value_numeric = 51.0 "
            "where series_id = 'PMI'"
        )
        after = capture_pretrade_input_snapshot(
            conn,
            target_date=AS_OF,
            stock_candidate_policy=DEFAULT_STOCK_CANDIDATE_POLICY,
        )
    finally:
        conn.close()

    with pytest.raises(ValueError, match="source cut changed"):
        build_completed_pretrade_qualification(
            producer_result={
                "status": "ok",
                "run_id": "livermore_candidate_history:test:late-mutation",
                "snapshot_as_of_date": AS_OF,
                "row_count": 7,
                "empty_result": False,
                "stock_candidate_policy": DEFAULT_STOCK_CANDIDATE_POLICY,
                "rule_version": "rv_livermore_candidate_history_v1",
                "strategy_payload_sha256": canonical_pretrade_output_sha256(
                    {"candidate_codes": ["600001.SH"], "market_state": "WARM"}
                ),
                "candidate_history_sha256": candidate_sha,
            },
            input_snapshot_before=before,
            input_snapshot_after=after,
            confluence_payload={
                "status": "completed",
                "target_date": AS_OF,
                "canonical_output_sha256": "c" * 64,
            },
            export_payload={"status": "completed", "as_of_date": AS_OF},
            rule_identity=_rule_identity(),
        )


@pytest.mark.unit
def test_self_consistent_unknown_ready_shape_is_fail_closed() -> None:
    invalid = {
        "schema": "pretrade_qualification/future",
        "status": "ready",
        "evidence_sha256": "0" * 64,
    }

    assert normalize_pretrade_qualification(invalid) == {
        "schema": "pretrade_qualification/v1",
        "status": "unavailable",
        "reason": "pretrade_qualification_schema_unsupported",
    }


@pytest.mark.unit
def test_self_consistent_structural_tampering_remains_unavailable(tmp_path: Path) -> None:
    db_path = tmp_path / "pretrade.duckdb"
    _build_synthetic_db(db_path)
    _add_required_source_inputs(db_path)
    evidence = _completed_evidence(db_path)

    bad_schema = deepcopy(evidence)
    source = bad_schema["input_snapshot"]["sources"][0]
    source["columns"] = []
    snapshot_body = dict(bad_schema["input_snapshot"])
    snapshot_body.pop("sha256")
    bad_schema["input_snapshot"]["sha256"] = canonical_pretrade_output_sha256(
        snapshot_body
    )
    evidence_body = dict(bad_schema)
    evidence_body.pop("evidence_sha256")
    bad_schema["evidence_sha256"] = canonical_pretrade_output_sha256(evidence_body)
    assert normalize_pretrade_qualification(bad_schema)["reason"] == (
        "pretrade_qualification_input_snapshot_invalid"
    )

    bad_count = deepcopy(evidence)
    bad_count["outputs"]["candidate_row_count"] = True
    evidence_body = dict(bad_count)
    evidence_body.pop("evidence_sha256")
    bad_count["evidence_sha256"] = canonical_pretrade_output_sha256(evidence_body)
    assert normalize_pretrade_qualification(bad_count)["reason"] == (
        "pretrade_qualification_candidate_count_invalid"
    )

    bad_rule = deepcopy(evidence)
    bad_rule["rule_identity"]["top_n"] = 1.5
    evidence_body = dict(bad_rule)
    evidence_body.pop("evidence_sha256")
    bad_rule["evidence_sha256"] = canonical_pretrade_output_sha256(evidence_body)
    assert normalize_pretrade_qualification(bad_rule)["reason"] == (
        "pretrade_qualification_rule_identity_invalid"
    )


@pytest.mark.unit
def test_sealed_qualification_accepts_recursively_frozen_evidence(tmp_path: Path) -> None:
    db_path = tmp_path / "pretrade.duckdb"
    _build_synthetic_db(db_path)
    _add_required_source_inputs(db_path)
    evidence = _completed_evidence(db_path)

    def freeze(value: object) -> object:
        if isinstance(value, dict):
            return MappingProxyType({key: freeze(item) for key, item in value.items()})
        if isinstance(value, list):
            return tuple(freeze(item) for item in value)
        return value

    qualified = qualify_sealed_pretrade_read(
        evidence=freeze(evidence),
        target_date=AS_OF,
        stock_candidate_policy=DEFAULT_STOCK_CANDIDATE_POLICY,
    )

    assert qualified["status"] == "ready"
    assert qualified["evidence_sha256"] == evidence["evidence_sha256"]


@pytest.mark.unit
def test_export_projection_identity_excludes_transport_fields() -> None:
    business = {
        "status": "completed",
        "as_of_date": AS_OF,
        "signal_kind": "factor_screen",
        "candidate_count": 1,
        "top_n": 10,
        "market_states": ["WARM"],
        "data_statuses": ["complete"],
        "freshness": {"status": "ready"},
        "sector_distribution": [{"sector": "bank", "count": 1}],
        "portfolio_flags": [],
        "decision": {"action": "review_only"},
        "rows": [{"stock_code": "600001.SH", "rank": 1}],
    }
    first = {
        **business,
        "duckdb_path": "C:/one/moss.duckdb",
        "output_paths": {"json": "C:/one/out.json"},
        "rerun_result": {"run_id": "first"},
    }
    second = {
        **business,
        "duckdb_path": "D:/other/moss.duckdb",
        "output_paths": {"json": "D:/other/out.json"},
        "rerun_result": {"run_id": "second"},
    }

    assert canonical_pretrade_export_projection_sha256(
        first
    ) == canonical_pretrade_export_projection_sha256(second)


@pytest.mark.unit
def test_external_catalog_content_change_rejects_completion(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "pretrade.duckdb"
    catalog_path = tmp_path / "choice-stock-catalog.json"
    _build_synthetic_db(db_path)
    _add_required_source_inputs(db_path)
    settings_module = __import__(
        "backend.app.governance.settings", fromlist=["get_settings"]
    )
    confluence_module = __import__(
        "backend.app.services.livermore_signal_confluence_service",
        fromlist=["load_macro_adversarial_signal_payload"],
    )
    monkeypatch.setattr(
        settings_module,
        "get_settings",
        lambda: SimpleNamespace(choice_stock_catalog_file=catalog_path),
    )
    monkeypatch.setattr(
        confluence_module,
        "load_macro_adversarial_signal_payload",
        lambda **_kwargs: ({"status": "missing", "items": []}, {}),
    )
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        catalog_path.write_text('{"version":"A"}', encoding="utf-8")
        before = capture_pretrade_input_snapshot(
            conn,
            target_date=AS_OF,
            stock_candidate_policy=DEFAULT_STOCK_CANDIDATE_POLICY,
        )
        catalog_path.write_text('{"version":"B"}', encoding="utf-8")
        after = capture_pretrade_input_snapshot(
            conn,
            target_date=AS_OF,
            stock_candidate_policy=DEFAULT_STOCK_CANDIDATE_POLICY,
        )
        candidate_sha = capture_pretrade_candidate_identity(conn, target_date=AS_OF)
    finally:
        conn.close()

    assert before["external_sources"][0]["content_sha256"] != after[
        "external_sources"
    ][0]["content_sha256"]
    with pytest.raises(ValueError, match="source cut changed"):
        build_completed_pretrade_qualification(
            producer_result={
                "status": "completed",
                "run_id": "candidate:external-mutation",
                "snapshot_as_of_date": AS_OF,
                "row_count": 7,
                "empty_result": False,
                "stock_candidate_policy": DEFAULT_STOCK_CANDIDATE_POLICY,
                "rule_version": "rv_livermore_candidate_history_v1",
                "strategy_payload_sha256": "a" * 64,
                "candidate_history_sha256": candidate_sha,
            },
            input_snapshot_before=before,
            input_snapshot_after=after,
            confluence_payload={
                "status": "completed",
                "target_date": AS_OF,
                "canonical_output_sha256": "c" * 64,
            },
            export_payload={"status": "completed", "as_of_date": AS_OF},
            rule_identity=_rule_identity(),
        )


@pytest.mark.unit
def test_input_snapshot_uses_captured_external_identities_without_rereading(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "pretrade.duckdb"
    _build_synthetic_db(db_path)
    _add_required_source_inputs(db_path)
    captured_profiles = [
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
    qualification_module = __import__(
        "backend.app.services.pretrade_qualification",
        fromlist=["_external_source_profiles"],
    )
    monkeypatch.setattr(
        qualification_module,
        "_external_source_profiles",
        lambda: (_ for _ in ()).throw(AssertionError("external inputs were reread")),
    )
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        snapshot = capture_pretrade_input_snapshot(
            conn,
            target_date=AS_OF,
            stock_candidate_policy=DEFAULT_STOCK_CANDIDATE_POLICY,
            external_identity_profiles=captured_profiles,
        )
    finally:
        conn.close()

    assert snapshot["external_sources"] == captured_profiles


@pytest.mark.unit
def test_input_snapshot_rejects_unknown_captured_external_source(tmp_path: Path) -> None:
    db_path = tmp_path / "pretrade.duckdb"
    _build_synthetic_db(db_path)
    _add_required_source_inputs(db_path)
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        with pytest.raises(ValueError, match="external input source set"):
            capture_pretrade_input_snapshot(
                conn,
                target_date=AS_OF,
                stock_candidate_policy=DEFAULT_STOCK_CANDIDATE_POLICY,
                external_identity_profiles=[
                    {"name": "unknown", "present": True, "content_sha256": "1" * 64}
                ],
            )
    finally:
        conn.close()


@pytest.mark.unit
def test_sealed_read_rechecks_small_external_identities(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db_path = tmp_path / "pretrade.duckdb"
    _build_synthetic_db(db_path)
    _add_required_source_inputs(db_path)
    evidence = _completed_evidence(db_path)
    changed_profiles = deepcopy(evidence["input_snapshot"]["external_sources"])
    changed_profiles[0]["content_sha256"] = "f" * 64
    qualification_module = __import__(
        "backend.app.services.pretrade_qualification",
        fromlist=["_external_source_profiles"],
    )
    monkeypatch.setattr(
        qualification_module,
        "_external_source_profiles",
        lambda: changed_profiles,
    )

    result = qualify_sealed_pretrade_read(
        evidence=evidence,
        target_date=AS_OF,
        stock_candidate_policy=DEFAULT_STOCK_CANDIDATE_POLICY,
    )

    assert result == {
        "schema": "pretrade_qualification/v1",
        "status": "unavailable",
        "reason": "pretrade_qualification_external_inputs_changed",
    }
