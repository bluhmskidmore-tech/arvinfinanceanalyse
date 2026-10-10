from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import duckdb
import pytest

from tests.helpers import load_module

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]


def _load_module():
    return load_module(
        "scripts.stock_analysis_current_rule_replay_dry_run",
        "scripts/stock_analysis_current_rule_replay_dry_run.py",
    )


def _ready_readiness(catalog_path: str = "catalog.json") -> SimpleNamespace:
    return SimpleNamespace(
        ready=True,
        status="ready",
        catalog_path=catalog_path,
        message="ready",
        model_dump=lambda mode="json": {
            "ready": True,
            "status": "ready",
            "catalog_path": catalog_path,
            "message": "ready",
        },
    )


def _missing_readiness(catalog_path: str = "missing.json") -> SimpleNamespace:
    return SimpleNamespace(
        ready=False,
        status="missing_catalog",
        catalog_path=catalog_path,
        message="missing",
        model_dump=lambda mode="json": {
            "ready": False,
            "status": "missing_catalog",
            "catalog_path": catalog_path,
            "message": "missing",
        },
    )


def _create_db(path: Path) -> None:
    conn = duckdb.connect(str(path))
    try:
        conn.execute(
            """
            create table choice_stock_daily_observation (
              trade_date varchar,
              stock_code varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_universe (
              as_of_date varchar,
              stock_code varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_sector_membership (
              as_of_date varchar,
              stock_code varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_limit_quality (
              as_of_date varchar,
              stock_code varchar
            )
            """
        )
        conn.execute(
            """
            create table choice_stock_factor_snapshot (
              as_of_date varchar,
              stock_code varchar
            )
            """
        )
        conn.execute(
            """
            create table livermore_candidate_history (
              snapshot_as_of_date varchar,
              stock_code varchar,
              signal_kind varchar,
              selection_policy varchar,
              signal_evidence_json varchar
            )
            """
        )
        conn.executemany(
            "insert into choice_stock_daily_observation values (?, ?)",
            [
                ("2026-05-03", "000003.SZ"),
                ("2026-05-01", "000001.SZ"),
                ("2026-05-02", "000002.SZ"),
            ],
        )
        conn.execute("insert into choice_stock_universe values ('2026-05-01', '000001.SZ')")
        conn.execute("insert into choice_stock_sector_membership values ('2026-04-28', '000001.SZ')")
        conn.execute("insert into choice_stock_limit_quality values ('2026-01-01', '000001.SZ')")
        conn.execute("insert into choice_stock_factor_snapshot values ('2026-04-15', '000001.SZ')")
        conn.execute(
            """
            insert into livermore_candidate_history values (
              '2026-05-01',
              '000001.SZ',
              'stock_candidate',
              'exp3b',
              '{"selection_policy":"exp3b","selection_formula_version":"rv_livermore_stock_candidates_bundle_v7"}'
            )
            """
        )
        conn.execute(
            """
            insert into livermore_candidate_history values (
              '2026-05-02',
              '000002.SZ',
              'stock_candidate',
              null,
              '{"selection_policy":"exp3b","selection_formula_version":"rv_livermore_stock_candidates_bundle_v7"}'
            )
            """
        )
    finally:
        conn.close()


def _fake_payload(
    *,
    requested: str,
    resolved: str,
    market_state: str,
    candidate_codes: list[str],
    block_reason: str | None = None,
    macro_business_date: str | None = None,
    formula_version: str = "rv_livermore_stock_candidates_bundle_v7",
    selection_policy: str = "exp3b",
    candidate_count_override: int | None = None,
) -> tuple[dict[str, object], dict[str, object]]:
    stock_candidates = {
        "selection_policy": selection_policy,
        "formula_version": formula_version,
        "candidate_count": len(candidate_codes) if candidate_count_override is None else candidate_count_override,
        "insufficient_history_count": 0,
        "input_stock_count": 5,
        "excluded_stock_count": 4,
        "items": [{"stock_code": code} for code in candidate_codes],
    }
    payload: dict[str, object] = {
        "requested_as_of_date": requested,
        "as_of_date": resolved,
        "market_gate": {"state": market_state, "exposure": 0.5},
        "stock_candidates": stock_candidates,
        "cycle_rotation_framework": {
            "macro_layer": {
                "ready": True,
                "macro_score": 0.7,
                "available_inputs": ["pmi", "credit_impulse", "price_spread"],
                "missing_inputs": [],
                "evidence": "ready",
                "lineage": {
                    "pmi": {"series_id": "M0017126", "trade_date": macro_business_date or requested, "value": 49.2},
                    "credit_impulse": {
                        "series_id": "M5525763",
                        "current_reference_date": requested,
                        "prior_reference_date": "2026-04-01",
                        "current_yoy": 7.4,
                        "prior_yoy": 7.2,
                        "impulse_ppt": 0.2,
                        "unit": "ppt",
                    },
                    "price_spread": {"pe_series_id": "CA.CSI300_PE", "cn10y_series_id": "EMM00166466", "spread_ppt": 4.5},
                },
            }
        },
        "data_gaps": [
            {"input_family": "PMI", "status": "ready", "evidence": "ok"},
            {"input_family": "credit_impulse", "status": "ready", "evidence": "ok"},
            {"input_family": "price_spread", "status": "ready", "evidence": "ok"},
        ],
        "module_states": [
            {"key": "stock_candidates", "state": "ready", "source_date": requested, "reasons": []},
        ],
        "unsupported_outputs": [],
    }
    if block_reason is not None:
        payload["unsupported_outputs"] = [{"key": "stock_candidates", "reason": block_reason}]
        if not candidate_codes:
            payload.pop("stock_candidates")
    meta = {
        "quality_flag": "ok",
        "vendor_status": "ok",
        "fallback_mode": "none",
        "source_version": "sv",
        "vendor_version": "vv",
        "tables_used": ["choice_stock_daily_observation"],
        "evidence_rows": 11,
    }
    return payload, meta


def test_runner_replays_sorted_dates_and_preserves_db_hash(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    _create_db(db_path)
    before = hashlib.sha256(db_path.read_bytes()).hexdigest().upper()
    clear_calls: list[str] = []
    loader_calls: list[dict[str, object]] = []

    def fake_loader(*, duckdb_path: str, as_of_date, **_kwargs):
        loader_calls.append(_kwargs)
        trade_date = as_of_date.isoformat()
        if trade_date == "2026-05-01":
            return _fake_payload(
                requested=trade_date,
                resolved=trade_date,
                market_state="WARM",
                candidate_codes=["000001.SZ"],
            )
        if trade_date == "2026-05-02":
            return _fake_payload(
                requested=trade_date,
                resolved=trade_date,
                market_state="WARM",
                candidate_codes=[],
            )
        return _fake_payload(
            requested=trade_date,
            resolved=trade_date,
            market_state="OVERHEAT",
            candidate_codes=[],
            block_reason="Stock candidate policy exp3b is inactive in OVERHEAT; active market states are HOT/WARM.",
        )

    monkeypatch.setattr(module, "load_choice_stock_readiness", lambda path: _ready_readiness(path))
    monkeypatch.setattr(module, "load_livermore_strategy_payload", fake_loader)
    monkeypatch.setattr(module, "clear_runtime_cache", lambda name: clear_calls.append(name))

    report = module.build_current_rule_replay_dry_run(
        duckdb_path=db_path,
        start_date="2026-05-01",
        end_date="2026-05-03",
        choice_stock_catalog_file="catalog.json",
        max_workers=3,
    )

    assert [row["trade_date"] for row in report["date_results"]] == [
        "2026-05-01",
        "2026-05-02",
        "2026-05-03",
    ]
    assert [row["status"] for row in report["date_results"]] == [
        "selection_completed_with_signals",
        "selection_completed_no_signals",
        "selection_policy_inactive",
    ]
    assert report["summary"]["candidate_rows_total"] == 1
    assert report["summary"]["candidate_signal_date_count"] == 1
    assert report["legacy_as_produced_compare"]["observed_row_count"] == 1
    assert report["legacy_as_produced_compare"]["overlap_row_count"] == 1
    assert report["date_results"][0]["module_states"][0]["state"] == "ready"
    assert report["date_results"][0]["macro_components"]["PMI"]["lineage"]["series_id"] == "M0017126"
    assert report["db_sha256_before"] == before
    assert report["db_sha256_before"] == report["db_sha256_after"]
    assert report["summary"]["db_hash_unchanged"] is True
    assert report["plan_digest_version"] == "stock_analysis_current_rule_replay_plan_v2"
    assert (
        report["coverage_policy"]["observed_date_axis_sha256"]
        == "F0220DAD5BF23691297C32B3976A50D730FB9D52CFC730D6BC67CA70971FF393"
    )
    assert report["replay_closure_evaluation"]["status"] == "not_evaluated"
    assert report["formal_use_allowed"] is False
    assert report["blockers"] == []
    assert report["diagnostic_limitations"] == list(module.BASE_BLOCKERS)
    assert clear_calls == [module.PAYLOAD_CACHE_NAME] * 3
    assert all(call["stock_readiness"].ready for call in loader_calls)
    assert all(call["backfill_mode"] is True for call in loader_calls)
    assert all(call["stock_candidate_policy"] == "exp3b" for call in loader_calls)
    assert all(call["theme_overlay_reader"] is None for call in loader_calls)


def test_runner_parallel_and_sequential_results_match(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    _create_db(db_path)

    def fake_loader(*, duckdb_path: str, as_of_date, **_kwargs):
        trade_date = as_of_date.isoformat()
        return _fake_payload(
            requested=trade_date,
            resolved=trade_date,
            market_state="WARM",
            candidate_codes=[trade_date.replace("-", "")],
        )

    monkeypatch.setattr(module, "load_choice_stock_readiness", lambda path: _ready_readiness(path))
    monkeypatch.setattr(module, "load_livermore_strategy_payload", fake_loader)
    monkeypatch.setattr(module, "clear_runtime_cache", lambda name: None)

    sequential = module.build_current_rule_replay_dry_run(
        duckdb_path=db_path,
        start_date="2026-05-01",
        end_date="2026-05-03",
        choice_stock_catalog_file="catalog.json",
        max_workers=1,
    )
    parallel = module.build_current_rule_replay_dry_run(
        duckdb_path=db_path,
        start_date="2026-05-01",
        end_date="2026-05-03",
        choice_stock_catalog_file="catalog.json",
        max_workers=4,
    )

    assert sequential["summary"] == parallel["summary"]
    assert sequential["date_results"] == parallel["date_results"]
    assert sequential["plan_digest"] == parallel["plan_digest"]


def test_runner_rejects_non_current_rule_policy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    _create_db(db_path)

    for invalid_policy in ("default", "exp3c", "EXP3B"):
        with pytest.raises(
            ValueError,
            match="current-rule replay requires stock_candidate_policy='exp3b'",
        ):
            module.build_current_rule_replay_dry_run(
                duckdb_path=db_path,
                start_date="2026-05-01",
                end_date="2026-05-01",
                stock_candidate_policy=invalid_policy,
                choice_stock_catalog_file="catalog.json",
            )

    with pytest.raises(SystemExit) as exc_info:
        module.main(
            [
                "--start-date",
                "2026-05-01",
                "--end-date",
                "2026-05-01",
                "--stock-candidate-policy",
                "exp3c",
            ]
        )
    assert exc_info.value.code == 2


def test_catalog_fingerprint_and_plan_digest_use_content_not_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    _create_db(db_path)
    catalog_path = tmp_path / "catalog.json"
    catalog_content = b'{"catalog_version":"test-v1"}\n'
    catalog_path.write_bytes(catalog_content)

    def fake_loader(*, duckdb_path: str, as_of_date, **_kwargs):
        trade_date = as_of_date.isoformat()
        return _fake_payload(
            requested=trade_date,
            resolved=trade_date,
            market_state="WARM",
            candidate_codes=[],
        )

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(module, "load_choice_stock_readiness", lambda path: _ready_readiness(path))
    monkeypatch.setattr(module, "load_livermore_strategy_payload", fake_loader)
    monkeypatch.setattr(module, "clear_runtime_cache", lambda name: None)

    relative = module.build_current_rule_replay_dry_run(
        duckdb_path=db_path,
        start_date="2026-05-01",
        end_date="2026-05-03",
        choice_stock_catalog_file="catalog.json",
        max_workers=1,
    )
    absolute = module.build_current_rule_replay_dry_run(
        duckdb_path=db_path,
        start_date="2026-05-01",
        end_date="2026-05-03",
        choice_stock_catalog_file=catalog_path.resolve(),
        max_workers=1,
    )

    expected_fingerprint = hashlib.sha256(catalog_content).hexdigest().upper()
    assert relative["choice_stock_catalog"]["fingerprint"] == expected_fingerprint
    assert absolute["choice_stock_catalog"]["fingerprint"] == expected_fingerprint
    assert relative["plan_digest_version"] == "stock_analysis_current_rule_replay_plan_v2"
    assert absolute["plan_digest_version"] == "stock_analysis_current_rule_replay_plan_v2"
    assert relative["plan_digest"] == absolute["plan_digest"]


def test_runner_flags_requested_resolved_mismatch_and_future_business_date(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    _create_db(db_path)

    def fake_loader(*, duckdb_path: str, as_of_date, **_kwargs):
        trade_date = as_of_date.isoformat()
        return _fake_payload(
            requested=trade_date,
            resolved="2026-05-02",
            market_state="WARM",
            candidate_codes=["000001.SZ"],
            macro_business_date="2026-05-02",
        )

    monkeypatch.setattr(module, "load_choice_stock_readiness", lambda path: _ready_readiness(path))
    monkeypatch.setattr(module, "load_livermore_strategy_payload", fake_loader)
    monkeypatch.setattr(module, "clear_runtime_cache", lambda name: None)

    report = module.build_current_rule_replay_dry_run(
        duckdb_path=db_path,
        start_date="2026-05-01",
        end_date="2026-05-01",
        choice_stock_catalog_file="catalog.json",
        max_workers=1,
    )

    row = report["date_results"][0]
    assert row["status"] == "selection_unsupported"
    assert row["requested_matches_resolved"] is False
    assert {
        "path": "payload.cycle_rotation_framework.macro_layer.lineage.pmi.trade_date",
        "key": "trade_date",
        "value": "2026-05-02",
    } in row["future_business_date_violations"]
    assert {
        "path": "payload.as_of_date",
        "key": "as_of_date",
        "value": "2026-05-02",
    } in row["future_business_date_violations"]
    assert report["summary"]["requested_resolved_mismatch_count"] == 1
    assert report["summary"]["future_business_date_violation_count"] == 2
    assert report["summary"]["future_input_date_violation_date_count"] == 1
    assert "requested_resolved_date_mismatch_detected" in report["blockers"]
    assert "future_business_date_violation_detected" in report["blockers"]


def test_runner_fails_closed_when_choice_catalog_not_ready(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    _create_db(db_path)
    calls: list[str] = []

    monkeypatch.setattr(module, "load_choice_stock_readiness", lambda path: _missing_readiness(path))
    monkeypatch.setattr(
        module,
        "load_livermore_strategy_payload",
        lambda **kwargs: calls.append("called"),
    )

    report = module.build_current_rule_replay_dry_run(
        duckdb_path=db_path,
        start_date="2026-05-01",
        end_date="2026-05-03",
        choice_stock_catalog_file="missing.json",
        max_workers=2,
    )

    assert calls == []
    assert report["summary"]["attempted_dates"] == 0
    assert report["summary"]["status_counts"] == {"selection_unsupported": 3}
    assert report["choice_stock_catalog"]["ready"] is False
    assert report["choice_stock_catalog"]["fingerprint"] is None
    assert "choice_stock_catalog_not_ready" in report["blockers"]


def test_runner_reports_missing_calendar_receipt_hash_in_diagnostic_mode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    _create_db(db_path)

    monkeypatch.setattr(module, "load_choice_stock_readiness", lambda path: _missing_readiness(path))
    monkeypatch.setattr(module, "load_livermore_strategy_payload", lambda **kwargs: pytest.fail("loader must not run"))

    report = module.build_current_rule_replay_dry_run(
        duckdb_path=db_path,
        start_date="2026-05-01",
        end_date="2026-05-03",
        choice_stock_catalog_file="missing.json",
        max_workers=1,
    )

    assert report["coverage_policy"]["calendar_authority"] == "choice_stock_daily_observation_only"
    assert report["coverage_policy"]["calendar_receipt_sha256"] is None
    assert report["coverage_policy"]["audit_bypass_approved"] is False
    assert report["coverage_policy"]["carry_forward_approved"] is False
    assert report["calendar_verifiable"] is False
    assert report["blockers"] == ["choice_stock_catalog_not_ready"]
    assert "calendar_authority_unavailable" in report["diagnostic_limitations"]


def test_runner_does_not_treat_rejected_future_macro_availability_as_consumed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    _create_db(db_path)

    def fake_loader(*, duckdb_path: str, as_of_date, **_kwargs):
        trade_date = as_of_date.isoformat()
        payload, meta = _fake_payload(
            requested=trade_date,
            resolved=trade_date,
            market_state="HOT",
            candidate_codes=["000001.SZ"],
        )
        payload["data_gaps"] = [
            {
                "input_family": "PMI",
                "status": "missing",
                "evidence": (
                    "M0017126 availability date 2026-07-13 is after evaluation date "
                    "2025-09-24.; M0017126 availability date 2026-07-13 is after "
                    "evaluation date 2025-09-24."
                ),
            }
        ]
        return payload, meta

    monkeypatch.setattr(module, "load_choice_stock_readiness", lambda path: _ready_readiness(path))
    monkeypatch.setattr(module, "load_livermore_strategy_payload", fake_loader)
    monkeypatch.setattr(module, "clear_runtime_cache", lambda name: None)

    report = module.build_current_rule_replay_dry_run(
        duckdb_path=db_path,
        start_date="2026-05-01",
        end_date="2026-05-01",
        choice_stock_catalog_file="catalog.json",
        max_workers=1,
    )

    row = report["date_results"][0]
    assert row["macro_components"]["PMI"]["status"] == "missing"
    assert "availability date 2026-07-13 is after evaluation date" in row["macro_components"]["PMI"]["evidence"]
    assert row["future_availability_violations"] == []
    assert report["summary"]["future_availability_violation_count"] == 0
    assert report["summary"]["future_input_date_violation_date_count"] == 0
    assert "future_availability_date_violation_detected" not in report["blockers"]


def test_runner_marks_loader_errors_fail_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    _create_db(db_path)

    def fake_loader(*, duckdb_path: str, as_of_date, **_kwargs):
        raise RuntimeError(f"boom:{as_of_date.isoformat()}")

    monkeypatch.setattr(module, "load_choice_stock_readiness", lambda path: _ready_readiness(path))
    monkeypatch.setattr(module, "load_livermore_strategy_payload", fake_loader)
    monkeypatch.setattr(module, "clear_runtime_cache", lambda name: None)

    report = module.build_current_rule_replay_dry_run(
        duckdb_path=db_path,
        start_date="2026-05-01",
        end_date="2026-05-01",
        choice_stock_catalog_file="catalog.json",
        max_workers=1,
    )

    row = report["date_results"][0]
    assert row["status"] == "loader_error"
    assert row["status_reason"] == "loader_exception"
    assert row["requested_matches_resolved"] is None
    assert "boom:2026-05-01" in row["stock_candidate_block_reason"]
    assert report["summary"]["status_counts"]["loader_error"] == 1
    assert report["summary"]["requested_resolved_mismatch_count"] == 0
    assert "loader_errors_present" in report["blockers"]
    assert "requested_resolved_date_mismatch_detected" not in report["blockers"]


def test_post_processing_errors_are_fail_closed_in_serial_and_parallel(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    _create_db(db_path)

    def fake_loader(*, duckdb_path: str, as_of_date, **_kwargs):
        trade_date = as_of_date.isoformat()
        return _fake_payload(
            requested=trade_date,
            resolved=trade_date,
            market_state="WARM",
            candidate_codes=[],
        )

    def fail_post_processing(**_kwargs):
        raise RuntimeError("post-processing boom")

    monkeypatch.setattr(module, "load_choice_stock_readiness", lambda path: _ready_readiness(path))
    monkeypatch.setattr(module, "load_livermore_strategy_payload", fake_loader)
    monkeypatch.setattr(module, "clear_runtime_cache", lambda name: None)
    monkeypatch.setattr(module, "_build_date_result", fail_post_processing)

    sequential = module.build_current_rule_replay_dry_run(
        duckdb_path=db_path,
        start_date="2026-05-01",
        end_date="2026-05-03",
        choice_stock_catalog_file="catalog.json",
        max_workers=1,
    )
    parallel = module.build_current_rule_replay_dry_run(
        duckdb_path=db_path,
        start_date="2026-05-01",
        end_date="2026-05-03",
        choice_stock_catalog_file="catalog.json",
        max_workers=3,
    )

    assert sequential["date_results"] == parallel["date_results"]
    assert sequential["summary"] == parallel["summary"]
    assert {row["status"] for row in sequential["date_results"]} == {"loader_error"}
    assert {row["status_reason"] for row in sequential["date_results"]} == {
        "processing_exception"
    }
    assert sequential["summary"]["requested_resolved_mismatch_count"] == 0
    assert "loader_errors_present" in sequential["blockers"]
    assert "requested_resolved_date_mismatch_detected" not in sequential["blockers"]


def test_runner_fails_closed_on_tuple_mismatch_and_duplicate_candidates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    _create_db(db_path)

    def fake_loader(*, duckdb_path: str, as_of_date, **_kwargs):
        trade_date = as_of_date.isoformat()
        return _fake_payload(
            requested=trade_date,
            resolved=trade_date,
            market_state="WARM",
            candidate_codes=["000001.SZ", "000001.SZ"],
            formula_version="rv_wrong_formula",
            candidate_count_override=1,
        )

    monkeypatch.setattr(module, "load_choice_stock_readiness", lambda path: _ready_readiness(path))
    monkeypatch.setattr(module, "load_livermore_strategy_payload", fake_loader)
    monkeypatch.setattr(module, "clear_runtime_cache", lambda name: None)

    report = module.build_current_rule_replay_dry_run(
        duckdb_path=db_path,
        start_date="2026-05-01",
        end_date="2026-05-01",
        choice_stock_catalog_file="catalog.json",
        max_workers=1,
    )

    row = report["date_results"][0]
    assert row["status"] == "selection_unsupported"
    assert row["status_reason"] == "current_rule_tuple_mismatch"
    assert row["candidate_duplicate_count"] == 1
    assert row["candidate_count_matches_items"] is False
    assert "duplicate_candidate_key_detected" in report["blockers"]
    assert "candidate_count_items_mismatch_detected" in report["blockers"]
    assert "current_rule_tuple_mismatch_detected" in report["blockers"]


def test_runner_requires_explicit_policy_inactive_reason_for_policy_zero_signal(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path = tmp_path / "moss.duckdb"
    _create_db(db_path)

    def fake_loader(*, duckdb_path: str, as_of_date, **_kwargs):
        trade_date = as_of_date.isoformat()
        return _fake_payload(
            requested=trade_date,
            resolved=trade_date,
            market_state="OVERHEAT",
            candidate_codes=[],
            block_reason="stock candidates unavailable for another reason",
        )

    monkeypatch.setattr(module, "load_choice_stock_readiness", lambda path: _ready_readiness(path))
    monkeypatch.setattr(module, "load_livermore_strategy_payload", fake_loader)
    monkeypatch.setattr(module, "clear_runtime_cache", lambda name: None)

    report = module.build_current_rule_replay_dry_run(
        duckdb_path=db_path,
        start_date="2026-05-01",
        end_date="2026-05-01",
        choice_stock_catalog_file="catalog.json",
        max_workers=1,
    )

    assert report["date_results"][0]["status"] == "selection_unsupported"


def test_runner_cli_supports_json_summary_and_markdown_detail(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys,
) -> None:
    module = _load_module()
    payload = {
        "page_route": "/stock-analysis",
        "duckdb_path": "F:/db.duckdb",
        "requested_range": {
            "start_date": "2026-05-01",
            "end_date": "2026-05-01",
            "requested_date_count": 1,
        },
        "certification_status": "diagnostic_only",
        "calendar_verifiable": False,
        "frozen_tuple": {"selection_policy": "exp3b"},
        "choice_stock_catalog": {"ready": True},
        "summary": {
            "attempted_dates": 1,
            "status_counts": {"selection_completed_with_signals": 1},
            "candidate_rows_total": 1,
            "candidate_signal_date_count": 1,
            "duplicate_candidate_rows": 0,
            "requested_resolved_mismatch_count": 0,
            "future_business_date_violation_count": 0,
            "future_availability_violation_count": 1,
            "db_hash_unchanged": True,
            "snapshot_age_summary": {
                "universe": {"age_gt_30_count": 0, "age_gt_90_count": 0, "missing_count": 0},
                "membership": {"age_gt_30_count": 0, "age_gt_90_count": 0, "missing_count": 0},
                "limit": {"age_gt_30_count": 0, "age_gt_90_count": 0, "missing_count": 0},
                "factor": {"age_gt_30_count": 0, "age_gt_90_count": 0, "missing_count": 0},
            },
        },
        "legacy_as_produced_compare": {
            "reference_row_count": 778,
            "observed_row_count": 1,
            "overlap_row_count": 1,
            "overlap_date_count": 1,
        },
        "blockers": ["future_availability_date_violation_detected"],
        "diagnostic_limitations": ["calendar_authority_unavailable"],
        "plan_digest_version": "stock_analysis_current_rule_replay_plan_v2",
        "plan_digest": "abc",
        "db_sha256_before": "same",
        "db_sha256_after": "same",
        "date_results": [{"trade_date": "2026-05-01", "status": "selection_completed_with_signals", "market_state": "WARM", "candidate_count": 1, "resolved_as_of_date": "2026-05-01"}],
    }

    monkeypatch.setattr(module, "build_current_rule_replay_dry_run", lambda **kwargs: payload)

    json_exit = module.main(
        [
            "--start-date",
            "2026-05-01",
            "--end-date",
            "2026-05-01",
            "--format",
            "json",
            "--detail",
            "summary",
        ]
    )
    json_output = capsys.readouterr().out
    assert json_exit == 0
    parsed = json.loads(json_output)
    assert parsed["page_route"] == "/stock-analysis"
    assert parsed["date_results"] == []

    markdown_exit = module.main(
        [
            "--start-date",
            "2026-05-01",
            "--end-date",
            "2026-05-01",
            "--format",
            "markdown",
            "--detail",
            "dates",
        ]
    )
    markdown_output = capsys.readouterr().out
    assert markdown_exit == 0
    assert "# Stock Analysis Current-Rule Replay Dry Run" in markdown_output
    assert "selection_completed_with_signals: 1" in markdown_output
    assert "## Blockers\n\n- future_availability_date_violation_detected" in markdown_output
    assert "## Diagnostic Limitations\n\n- calendar_authority_unavailable" in markdown_output
    assert "2026-05-01: status=selection_completed_with_signals" in markdown_output


def test_runner_cli_returns_nonzero_for_operational_failures(
    monkeypatch: pytest.MonkeyPatch,
    capsys,
) -> None:
    module = _load_module()
    base_report = {
        "choice_stock_catalog": {"ready": True},
        "summary": {
            "status_counts": {},
            "db_hash_unchanged": True,
        },
        "blockers": ["calendar_authority_unavailable"],
        "date_results": [],
    }
    reports = []
    catalog_not_ready = json.loads(json.dumps(base_report))
    catalog_not_ready["choice_stock_catalog"]["ready"] = False
    reports.append(catalog_not_ready)
    loader_error = json.loads(json.dumps(base_report))
    loader_error["summary"]["status_counts"] = {"loader_error": 1}
    reports.append(loader_error)
    database_changed = json.loads(json.dumps(base_report))
    database_changed["summary"]["db_hash_unchanged"] = False
    reports.append(database_changed)

    for report in reports:
        monkeypatch.setattr(
            module,
            "build_current_rule_replay_dry_run",
            lambda **kwargs: report,
        )
        exit_code = module.main(
            [
                "--start-date",
                "2026-05-01",
                "--end-date",
                "2026-05-01",
                "--format",
                "json",
            ]
        )
        capsys.readouterr()
        assert exit_code != 0
