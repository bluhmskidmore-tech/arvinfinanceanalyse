from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
from datetime import date, timedelta
from pathlib import Path

import duckdb
import pytest

from backend.app.governance.stock_analysis_calendar_receipt import (
    build_stock_analysis_calendar_receipt,
)
from backend.app.governance.stock_analysis_current_rule_certificate import (
    CURRENT_RULE_COVERAGE_AUTHORITY_MODE,
)
from backend.app.repositories.duckdb_migrations import register_all
from backend.app.repositories.duckdb_schema_registry import DuckDBSchemaRegistry
from backend.app.tasks import stock_analysis_current_rule_cohort_materialize as task

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]

NOW = "2026-08-22T12:00:00+08:00"
OWNER_ID = "OWNER-D6B-APPROVAL-001"


@pytest.fixture(autouse=True)
def _structural_bundle_fixture_has_no_source_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Legacy bundle fixtures contain contracts only; source-row checks have separate tests."""
    monkeypatch.setattr(task, "_validate_bundle_source_rows", lambda **_kwargs: None)


def _canonical_sha(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest().upper()


def _seal(payload: dict[str, object], field: str) -> dict[str, object]:
    sealed = copy.deepcopy(payload)
    sealed[field] = _canonical_sha(sealed)
    return sealed


def _write(path: Path, payload: object) -> Path:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return path


def _write_oversized_json_stub(
    path: Path, *, max_bytes: int = task.MAX_JSON_INPUT_BYTES
) -> Path:
    with path.open("wb") as handle:
        handle.seek(max_bytes)
        handle.write(b" ")
    return path


def _file_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def _base_database(tmp_path: Path, name: str = "target.duckdb") -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / name
    registry = DuckDBSchemaRegistry(db_path=str(path))
    register_all(registry)
    registry.apply_pending()
    return path


def _version_tuple() -> dict[str, object]:
    return {
        "candidate_rule_version": "rv_candidate_history_current",
        "stock_candidate_selection_formula_version": "rv_livermore_stock_candidates_bundle_v7",
        "candidate_outcome_formula_version": "fv_livermore_candidate_forward_close_dual_adjust_v2",
        "execution_formula_version": "fv_livermore_candidate_execution_dual_adjust_v5",
        "matched_baseline_formula_version": "fv_livermore_matched_baseline_v4",
        "market_gate_rule_version": "rv_market_gate_current_v2",
        "signal_confluence_rule_version": "rv_signal_confluence_current_v4",
        "macro_formula_version": "fv_macro_bundle_current_v1",
        "candidate_source_version": "sv_candidate_current",
        "execution_source_version": "sv_execution_current",
        "matched_baseline_source_version": "sv_matched_baseline_current",
        "macro_source_version": "sv_macro_current",
        "theme_overlay_fingerprint": "overlay-fingerprint-1",
        "choice_catalog_fingerprint": "catalog-fingerprint-1",
        "stock_candidate_selection_policy": "exp3b",
        "decision_metric_basis": "net_next_open_adj",
        "coverage_authority_mode": CURRENT_RULE_COVERAGE_AUTHORITY_MODE,
        "strict_coverage": True,
        "fallback_covered": False,
    }


def _source_evidence(*, entry_date: str, exit_date_5d: str, exit_date_20d: str) -> dict[str, object]:
    def available(*, source_version: str, run_id: str) -> dict[str, object]:
        return {
            "availability_status": "available",
            "available_at": "2025-12-31",
            "source_version": source_version,
            "vendor_version": "vv_choice",
            "rule_version": "rv_source_v1",
            "run_id": run_id,
        }

    return {
        "observation": {
            "table": "choice_stock_daily_observation",
            "entry": {"trade_date": entry_date, **available(
                source_version="sv_obs_proven",
                run_id="source-run-observation",
            )},
            "exit_5d": {"trade_date": exit_date_5d, **available(
                source_version="sv_obs_proven",
                run_id="source-run-observation",
            )},
            "exit_20d": {"trade_date": exit_date_20d, **available(
                source_version="sv_obs_proven",
                run_id="source-run-observation",
            )},
        },
        "adjustment_factor": {
            "table": "stock_adjustment_factor",
            "entry": available(
                source_version="sv_factor_proven",
                run_id="source-run-factor",
            ),
            "exit_5d": available(
                source_version="sv_factor_proven",
                run_id="source-run-factor",
            ),
            "exit_20d": available(
                source_version="sv_factor_proven",
                run_id="source-run-factor",
            ),
        },
        "limit_price": {
            "table": "stock_limit_price_daily",
            "entry": None,
            "entry_source": "observation_cast",
            "exit_5d": None,
            "exit_5d_source": "observation_cast",
            "exit_5d_decisions": [{
                "trade_date": exit_date_5d,
                "decision": "sellable",
                "close_value": 10.5,
                "up_limit": None,
                "down_limit": None,
                "limit_down_flag": False,
                "limit_price_source": "observation_cast",
                "source": None,
                "observation": {"trade_date": exit_date_5d, **available(
                    source_version="sv_obs_proven", run_id="source-run-observation",
                )},
            }],
            "exit_20d": None,
            "exit_20d_source": "observation_cast",
            "exit_20d_decisions": [{
                "trade_date": exit_date_20d,
                "decision": "sellable",
                "close_value": 11.0,
                "up_limit": None,
                "down_limit": None,
                "limit_down_flag": False,
                "limit_price_source": "observation_cast",
                "source": None,
                "observation": {"trade_date": exit_date_20d, **available(
                    source_version="sv_obs_proven", run_id="source-run-observation",
                )},
            }],
        },
    }


def _bundle_artifacts(
    tmp_path: Path,
    *,
    target: Path,
    cohort_id: str = "cohort-d6b-1",
    total_days: int = 20,
) -> dict[str, Path | str]:
    tmp_path.mkdir(parents=True, exist_ok=True)
    start = date(2026, 1, 1)
    signal_dates = [
        (start + timedelta(days=index)).isoformat() for index in range(total_days)
    ]
    version_tuple = _version_tuple()
    row_versions = {field: version_tuple[field] for field in task.ROW_VERSION_FIELDS}
    calendar = build_stock_analysis_calendar_receipt(
        calendar_rows=[
            {
                "exchange": "SSE",
                "cal_date": signal_date,
                "is_open": 1,
                "pretrade_date": None if index == 0 else signal_dates[index - 1],
            }
            for index, signal_date in enumerate(signal_dates)
        ],
        request_start_date=signal_dates[0],
        request_end_date=signal_dates[-1],
        fetched_at=NOW,
        authority_status="approved",
        owner_approval_id=OWNER_ID,
    )
    calendar_path = _write(tmp_path / f"{cohort_id}-calendar.json", calendar)

    source_receipt = {
        "schema_version": 1,
        "receipt_kind": "pit_source_availability_v1",
        "captured_at": NOW,
        "sources": [
            {
                "table": "choice_stock_daily_observation",
                "source_version": "sv_obs_proven",
                "vendor_version": "vv_choice",
                "rule_version": "rv_source_v1",
                "run_id": "source-run-observation",
                "available_at": "2025-12-31",
            },
            {
                "table": "stock_adjustment_factor",
                "source_version": "sv_factor_proven",
                "vendor_version": "vv_choice",
                "rule_version": "rv_source_v1",
                "run_id": "source-run-factor",
                "available_at": "2025-12-31",
            }
        ],
    }
    source_sha = _canonical_sha(source_receipt)
    source_path = _write(tmp_path / f"{cohort_id}-source.json", source_receipt)

    facts: list[dict[str, object]] = []
    certificates: list[dict[str, object]] = []
    for day_index, signal_date in enumerate(signal_dates):
        signal = date.fromisoformat(signal_date)
        for item_index in range(5):
            stock_code = f"{day_index:03d}{item_index:03d}.SZ"
            controls = [
                {
                    "control_stock_code": f"C{day_index:02d}{item_index:02d}{control_index:02d}.SZ",
                    "candidate_stock_code": stock_code,
                    "signal_date": signal_date,
                    "signal_kind": "stock_candidate",
                    "control_entry_date": (signal + timedelta(days=1)).isoformat(),
                    "control_entry_price": 9.0,
                    "control_entry_price_kind": "open",
                    "control_entry_executable": True,
                    "control_entry_usable": True,
                    "control_exit_date_5d": (signal + timedelta(days=5)).isoformat(),
                    "control_exit_price_5d": 9.5,
                    "control_return_5d_net_adj": 0.04,
                    "control_return_5d_usable": True,
                    "control_exit_date_20d": (signal + timedelta(days=20)).isoformat(),
                    "control_exit_price_20d": 10.0,
                    "control_return_20d_net_adj": 0.08,
                    "control_return_20d_usable": True,
                    "control_entry_failure_reason": None,
                    "control_failure_reason_5d": None,
                    "control_failure_reason_20d": None,
                    "control_failure_reason": None,
                    "formula_version": "fv_livermore_matched_baseline_v4",
                    "metric_basis": "net_next_open_adj",
                    "price_adjustment_mode": "adj_factor_ratio",
                    "evaluation_as_of_date": "2026-03-01",
                    "source_evidence": _source_evidence(
                        entry_date=(signal + timedelta(days=1)).isoformat(),
                        exit_date_5d=(signal + timedelta(days=5)).isoformat(),
                        exit_date_20d=(signal + timedelta(days=20)).isoformat(),
                    ),
                }
                for control_index in range(20)
            ]
            facts.append(
                {
                    "signal_date": signal_date,
                    "stock_code": stock_code,
                    "stock_name": stock_code,
                    "signal_kind": "stock_candidate",
                    "candidate_rank": item_index + 1,
                    "market_state": "WARM",
                    "entry_date": (signal + timedelta(days=1)).isoformat(),
                    "entry_price": 10.0,
                    "entry_price_kind": "next_open",
                    "entry_executable": True,
                    "exit_date_5d": (signal + timedelta(days=5)).isoformat(),
                    "exit_price_5d": 10.5,
                    "return_5d_net_adj": 0.04,
                    "exit_date_20d": (signal + timedelta(days=20)).isoformat(),
                    "exit_price_20d": 11.0,
                    "return_20d_net_adj": 0.09,
                    "price_adjustment_mode": "adj_factor_ratio",
                    "candidate_data_status": "usable",
                    "execution_data_status": "usable",
                    "matched_baseline_status": "usable",
                    "matched_baseline_control_count": 20,
                    "matched_alpha_5d": 0.0,
                    "matched_alpha_20d": 0.01,
                    "control_eval_basis": "net_next_open_adj",
                    "control_pit_proof": {
                        "source_availability_receipt_sha256s": [source_sha],
                        "controls": controls,
                    },
                    "evidence": {
                        "current_rule_certified": True,
                        "candidate_source_evidence": _source_evidence(
                            entry_date=(signal + timedelta(days=1)).isoformat(),
                            exit_date_5d=(signal + timedelta(days=5)).isoformat(),
                            exit_date_20d=(signal + timedelta(days=20)).isoformat(),
                        ),
                        "candidate_source_proven": True,
                        "matched_alpha_recomputed": True,
                    },
                    **row_versions,
                }
            )
        candidate_key_rows = [
            {
                "signal_date": signal_date,
                "signal_kind": "stock_candidate",
                "stock_code": f"{day_index:03d}{item_index:03d}.SZ",
            }
            for item_index in range(5)
        ]
        certificates.append(
            {
                "trade_date": signal_date,
                "certificate_status": "completed_with_signals",
                "reason_code": "current_rule_fully_proven",
                "affects_completed_stats": True,
                "candidate_count": 5,
                "executable_candidate_count": 5,
                "t5_usable_count": 5,
                "t20_usable_count": 5,
                "matched_entry_count": 5,
                "stale_execution_row_count": 0,
                "stale_matched_baseline_row_count": 0,
                "unsupported_source_count": 0,
                "proxy_only_evidence_count": 0,
                "blocking_gap_count": 0,
                "control_entry_proven_count": 100,
                "control_exit_proven_5d_count": 100,
                "control_exit_proven_20d_count": 100,
                "control_eval_proof": {"source_availability_receipt_sha256s": [source_sha]},
                "source_coverage": {"strict": True, "fallback": False},
                "blocker_detail": {
                    "runner_candidate_key_proof": {
                        "candidate_keys": candidate_key_rows,
                        "candidate_key_sha256": _canonical_sha(candidate_key_rows),
                        "runner_candidate_count": 5,
                    }
                },
                **row_versions,
            }
        )

    summary = {
        "completed_dates": total_days,
        "completed_with_signals_dates": total_days,
        "completed_no_signal_dates": 0,
        "pending_tail_dates": 0,
        "blocking_pending_dates": 0,
        "unsupported_dates": 0,
        "proxy_only_dates": 0,
        "matched_entry_count": total_days * 5,
        "t5_usable_count": total_days * 5,
        "t20_usable_count": total_days * 5,
        "stale_execution_row_count": 0,
        "stale_matched_baseline_row_count": 0,
    }
    plan = {
        "plan_kind": "stock_analysis_current_rule_cohort_plan",
        "governed_run_id": f"governed-{cohort_id}",
        "control_count": 20,
        "minimum_completed_dates": 20,
        "minimum_matched_entries": 100,
        "decision_metric_basis": "net_next_open_adj",
    }
    plan_sha = _canonical_sha(plan)
    idempotency_key = _canonical_sha(
        {
            "target_database_path": str(target.resolve()),
            "plan_digest_sha256": plan_sha,
            "version_tuple": version_tuple,
            "calendar_receipt_sha256": calendar["canonical_receipt_sha256"],
            "source_availability_receipt_sha256s": [source_sha],
            "control_count": 20,
        }
    )
    bundle = _seal(
        {
            "schema_version": 1,
            "bundle_kind": task.BUNDLE_KIND,
            "cohort_id": cohort_id,
            "page_id": task.PAGE_ID,
            "cohort_mode": task.COHORT_MODE,
            "run_id": f"run-{cohort_id}",
            "idempotency_key": idempotency_key,
            "plan": plan,
            "plan_digest_sha256": plan_sha,
            "evaluation_as_of_date": "2026-03-01",
            "version_tuple": version_tuple,
            "date_bounds": {
                "requested_start_date": signal_dates[0],
                "requested_end_date": signal_dates[-1],
                "observed_start_date": signal_dates[0],
                "observed_end_date": signal_dates[-1],
                "certified_start_date": signal_dates[0],
                "certified_end_date": signal_dates[-1],
                "governed_era_start": signal_dates[0],
                "governed_era_end": signal_dates[-1],
            },
            "source_lineage": {"mode": "persisted_receipts_only"},
            "artifacts": {
                "calendar_receipt": {
                    "path": calendar_path.name,
                    "sha256": calendar["canonical_receipt_sha256"],
                },
                "source_availability_receipts": [
                    {"path": source_path.name, "sha256": source_sha}
                ],
                "zero_signal_certificates": [],
            },
            "facts": facts,
            "date_certificates": certificates,
            "summary": summary,
        },
        "canonical_bundle_sha256",
    )
    bundle_path = _write(tmp_path / f"{cohort_id}-bundle.json", bundle)
    return {
        "bundle_path": bundle_path,
        "bundle_sha": str(bundle["canonical_bundle_sha256"]),
        "source_sha": source_sha,
        "plan_sha": plan_sha,
        "cohort_id": cohort_id,
    }


def _reseal_bundle_payload(
    payload: dict[str, object],
    *,
    target: Path,
) -> dict[str, object]:
    artifacts = payload["artifacts"]
    assert isinstance(artifacts, dict)
    calendar_receipt = artifacts["calendar_receipt"]
    assert isinstance(calendar_receipt, dict)
    source_refs = artifacts["source_availability_receipts"]
    assert isinstance(source_refs, list)
    payload["idempotency_key"] = _canonical_sha(
        {
            "target_database_path": str(target.resolve()),
            "plan_digest_sha256": payload["plan_digest_sha256"],
            "version_tuple": payload["version_tuple"],
            "calendar_receipt_sha256": calendar_receipt["sha256"],
            "source_availability_receipt_sha256s": [
                ref["sha256"] for ref in source_refs
            ],
            "control_count": 20,
        }
    )
    return _seal(
        {
            key: value
            for key, value in payload.items()
            if key != "canonical_bundle_sha256"
        },
        "canonical_bundle_sha256",
    )


def _approval(
    path: Path,
    *,
    operation: str,
    bundle: dict[str, Path | str],
    target_sha: str,
    extra: dict[str, object],
) -> Path:
    return _write(
        path,
        _seal(
            {
                "schema_version": 1,
                "approval_kind": task.APPROVAL_KIND,
                "approval_status": "approved",
                "operation": operation,
                "cohort_id": bundle["cohort_id"],
                "bundle_sha256": bundle["bundle_sha"],
                "plan_digest_sha256": bundle["plan_sha"],
                "owner_approval_id": OWNER_ID,
                "run_id": f"approval-{operation}-{bundle['cohort_id']}",
                "approved_at": NOW,
                "target_database_sha256": target_sha,
                "target_database_path": str(path.parent.joinpath("target.duckdb").resolve()),
                "attested_source_availability_receipt_sha256s": [bundle["source_sha"]],
                "historical_source_availability_attested": True,
                **extra,
            },
            "canonical_approval_sha256",
        ),
    )


def _materialize_ready(tmp_path: Path, *, cohort_id: str = "cohort-d6b-1") -> dict[str, object]:
    target = _base_database(tmp_path)
    bundle = _bundle_artifacts(tmp_path, target=target, cohort_id=cohort_id)
    dry_path = tmp_path / f"{cohort_id}-dry.json"
    task.build_stock_analysis_current_rule_cohort_dry_run(
        duckdb_path=target,
        bundle_path=bundle["bundle_path"],
        receipt_path=dry_path,
        created_at=NOW,
    )
    backup = tmp_path / f"{cohort_id}-before.duckdb"
    shutil.copy2(target, backup)
    dry = json.loads(dry_path.read_text(encoding="utf-8"))
    approval = _approval(
        tmp_path / f"{cohort_id}-materialize-approval.json",
        operation="materialize",
        bundle=bundle,
        target_sha=_file_sha(target),
        extra={"dry_run_receipt_sha256": dry["canonical_receipt_sha256"]},
    )
    material_path = tmp_path / f"{cohort_id}-material.json"
    material = task.materialize_stock_analysis_current_rule_cohort(
        duckdb_path=target,
        bundle_path=bundle["bundle_path"],
        dry_run_receipt_path=dry_path,
        approval_artifact_path=approval,
        target_backup_path=backup,
        receipt_path=material_path,
        allow_write=True,
        created_at=NOW,
    )
    return {
        "target": target,
        "bundle": bundle,
        "dry_path": dry_path,
        "backup": backup,
        "approval": approval,
        "material": material,
        "material_path": material_path,
    }


def test_dry_run_is_read_only_and_materialize_is_inactive(tmp_path: Path) -> None:
    target = _base_database(tmp_path)
    bundle = _bundle_artifacts(tmp_path, target=target)
    before = _file_sha(target)
    receipt = task.build_stock_analysis_current_rule_cohort_dry_run(
        duckdb_path=target,
        bundle_path=bundle["bundle_path"],
        receipt_path=tmp_path / "dry.json",
        created_at=NOW,
    )
    assert receipt["database_unchanged"] is True
    assert _file_sha(target) == before

    ready = _materialize_ready(tmp_path / "materialized")
    material_receipt = ready["material"]
    assert (
        "target_database_sha256_after_materialization_before_receipt_trace"
        in material_receipt
    )
    assert "target_database_sha256_after" not in material_receipt
    conn = duckdb.connect(str(ready["target"]), read_only=True)
    try:
        manifest = conn.execute(
            f"select cohort_status, is_active, matched_entry_count from {task.MANIFEST_TABLE}"
        ).fetchone()
        assert manifest == (task.MATERIALIZED_STATUS, False, 100)
        assert conn.execute(f"select count(*) from {task.FACT_TABLE}").fetchone()[0] == 100
        assert conn.execute(f"select count(*) from {task.CERTIFICATE_TABLE}").fetchone()[0] == 20
        notes = json.loads(
            conn.execute(f"select notes_json from {task.MANIFEST_TABLE}").fetchone()[0]
        )
        assert notes["materialize_receipt_path"] == str(
            Path(ready["material_path"]).resolve()
        )
        assert notes["materialize_receipt_sha256"] == material_receipt[
            "canonical_receipt_sha256"
        ]
        assert notes["materialize_receipt_role"] == (
            "post_commit_external_receipt_linked"
        )
    finally:
        conn.close()


def test_dry_run_rejects_v3_matched_baseline_bundle(tmp_path: Path) -> None:
    target = _base_database(tmp_path)
    bundle = _bundle_artifacts(tmp_path, target=target)
    bundle_path = Path(bundle["bundle_path"])
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    payload["version_tuple"]["matched_baseline_formula_version"] = (
        "fv_livermore_matched_baseline_v3"
    )
    _write(bundle_path, _reseal_bundle_payload(payload, target=target))
    before = _file_sha(target)

    with pytest.raises(
        task.CurrentRuleCohortError,
        match="bundle matched-baseline formula is not current fv_livermore_matched_baseline_v4",
    ):
        task.build_stock_analysis_current_rule_cohort_dry_run(
            duckdb_path=target,
            bundle_path=bundle_path,
            receipt_path=tmp_path / "dry.json",
            created_at=NOW,
        )
    assert _file_sha(target) == before


def test_dry_run_opens_duckdb_in_read_only_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = _base_database(tmp_path)
    bundle = _bundle_artifacts(tmp_path, target=target)
    observed_read_only: list[bool] = []
    original_connect = task.duckdb.connect

    def tracking_connect(database: str, read_only: bool = False):
        observed_read_only.append(read_only)
        return original_connect(database, read_only=read_only)

    monkeypatch.setattr(task.duckdb, "connect", tracking_connect)
    task.build_stock_analysis_current_rule_cohort_dry_run(
        duckdb_path=target,
        bundle_path=bundle["bundle_path"],
        receipt_path=tmp_path / "dry.json",
        created_at=NOW,
    )

    assert observed_read_only == [True]


def test_materialize_fails_closed_for_backup_drift_and_missing_write_switch(tmp_path: Path) -> None:
    target = _base_database(tmp_path)
    bundle = _bundle_artifacts(tmp_path, target=target)
    dry_path = tmp_path / "dry.json"
    dry = task.build_stock_analysis_current_rule_cohort_dry_run(
        duckdb_path=target,
        bundle_path=bundle["bundle_path"],
        receipt_path=dry_path,
        created_at=NOW,
    )
    backup = tmp_path / "bad-backup.duckdb"
    backup.write_bytes(b"not-a-database")
    approval = _approval(
        tmp_path / "approval.json",
        operation="materialize",
        bundle=bundle,
        target_sha=_file_sha(target),
        extra={"dry_run_receipt_sha256": dry["canonical_receipt_sha256"]},
    )
    kwargs = dict(
        duckdb_path=target,
        bundle_path=bundle["bundle_path"],
        dry_run_receipt_path=dry_path,
        approval_artifact_path=approval,
        target_backup_path=backup,
        receipt_path=tmp_path / "material.json",
        created_at=NOW,
    )
    with pytest.raises(task.CurrentRuleCohortError, match="allow_write=True"):
        task.materialize_stock_analysis_current_rule_cohort(**kwargs)
    with pytest.raises(task.CurrentRuleCohortError, match="backup hash"):
        task.materialize_stock_analysis_current_rule_cohort(**kwargs, allow_write=True)


def test_hard_link_cannot_be_used_as_prewrite_backup(tmp_path: Path) -> None:
    target = _base_database(tmp_path)
    bundle = _bundle_artifacts(tmp_path, target=target)
    dry_path = tmp_path / "dry.json"
    dry = task.build_stock_analysis_current_rule_cohort_dry_run(
        duckdb_path=target,
        bundle_path=bundle["bundle_path"],
        receipt_path=dry_path,
        created_at=NOW,
    )
    backup = tmp_path / "hard-link-backup.duckdb"
    try:
        os.link(target, backup)
    except OSError as exc:
        pytest.skip(f"hard links unavailable: {exc}")
    approval = _approval(
        tmp_path / "approval.json",
        operation="materialize",
        bundle=bundle,
        target_sha=_file_sha(target),
        extra={"dry_run_receipt_sha256": dry["canonical_receipt_sha256"]},
    )
    with pytest.raises(task.CurrentRuleCohortError, match="different path"):
        task.materialize_stock_analysis_current_rule_cohort(
            duckdb_path=target,
            bundle_path=bundle["bundle_path"],
            dry_run_receipt_path=dry_path,
            approval_artifact_path=approval,
            target_backup_path=backup,
            receipt_path=tmp_path / "material.json",
            allow_write=True,
            created_at=NOW,
        )


def test_bundle_rejects_non_twenty_controls_and_duplicate_fact_key(tmp_path: Path) -> None:
    target = _base_database(tmp_path)
    artifacts = _bundle_artifacts(tmp_path, target=target)
    bundle_path = Path(artifacts["bundle_path"])
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    bundle["facts"][0]["control_pit_proof"]["controls"].pop()
    bundle = _seal(
        {key: value for key, value in bundle.items() if key != "canonical_bundle_sha256"},
        "canonical_bundle_sha256",
    )
    _write(bundle_path, bundle)
    with pytest.raises(task.CurrentRuleCohortError, match="exactly 20"):
        task.build_stock_analysis_current_rule_cohort_dry_run(
            duckdb_path=target,
            bundle_path=bundle_path,
            receipt_path=tmp_path / "dry.json",
            created_at=NOW,
        )

    duplicate_dir = tmp_path / "duplicate"
    duplicate_dir.mkdir()
    duplicate = _bundle_artifacts(duplicate_dir, target=target)
    duplicate_path = Path(duplicate["bundle_path"])
    payload = json.loads(duplicate_path.read_text(encoding="utf-8"))
    payload["facts"][1]["signal_date"] = payload["facts"][0]["signal_date"]
    payload["facts"][1]["stock_code"] = payload["facts"][0]["stock_code"]
    payload["facts"][1]["signal_kind"] = payload["facts"][0]["signal_kind"]
    payload = _seal(
        {key: value for key, value in payload.items() if key != "canonical_bundle_sha256"},
        "canonical_bundle_sha256",
    )
    _write(duplicate_path, payload)
    with pytest.raises(task.CurrentRuleCohortError, match="duplicate fact key"):
        task.build_stock_analysis_current_rule_cohort_dry_run(
            duckdb_path=target,
            bundle_path=duplicate_path,
            receipt_path=tmp_path / "duplicate-dry.json",
            created_at=NOW,
        )


def test_approval_hash_mismatch_fails_closed(tmp_path: Path) -> None:
    target = _base_database(tmp_path)
    bundle = _bundle_artifacts(tmp_path, target=target)
    dry_path = tmp_path / "dry.json"
    dry = task.build_stock_analysis_current_rule_cohort_dry_run(
        duckdb_path=target,
        bundle_path=bundle["bundle_path"],
        receipt_path=dry_path,
        created_at=NOW,
    )
    backup = tmp_path / "backup.duckdb"
    shutil.copy2(target, backup)
    approval = _approval(
        tmp_path / "approval.json",
        operation="materialize",
        bundle=bundle,
        target_sha=_file_sha(target),
        extra={"dry_run_receipt_sha256": "F" * 64},
    )
    with pytest.raises(task.CurrentRuleCohortError, match="dry-run receipt hash mismatch"):
        task.materialize_stock_analysis_current_rule_cohort(
            duckdb_path=target,
            bundle_path=bundle["bundle_path"],
            dry_run_receipt_path=dry_path,
            approval_artifact_path=approval,
            target_backup_path=backup,
            receipt_path=tmp_path / "material.json",
            allow_write=True,
            created_at=NOW,
        )
    assert dry["database_unchanged"] is True


def test_missing_fact_or_mismatched_certificate_lineage_fails_closed(
    tmp_path: Path,
) -> None:
    target = _base_database(tmp_path)
    artifacts = _bundle_artifacts(tmp_path, target=target)
    bundle_path = Path(artifacts["bundle_path"])
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    payload["facts"][0].pop("candidate_rule_version")
    payload = _seal(
        {key: value for key, value in payload.items() if key != "canonical_bundle_sha256"},
        "canonical_bundle_sha256",
    )
    _write(bundle_path, payload)
    with pytest.raises(task.CurrentRuleCohortError, match="fact version mismatch"):
        task.build_stock_analysis_current_rule_cohort_dry_run(
            duckdb_path=target,
            bundle_path=bundle_path,
            receipt_path=tmp_path / "missing-lineage-dry.json",
            created_at=NOW,
        )

    mismatch_dir = tmp_path / "certificate-mismatch"
    mismatch_dir.mkdir()
    mismatch = _bundle_artifacts(mismatch_dir, target=target)
    mismatch_path = Path(mismatch["bundle_path"])
    mismatch_payload = json.loads(mismatch_path.read_text(encoding="utf-8"))
    mismatch_payload["date_certificates"][0]["execution_source_version"] = "sv_wrong"
    mismatch_payload = _seal(
        {
            key: value
            for key, value in mismatch_payload.items()
            if key != "canonical_bundle_sha256"
        },
        "canonical_bundle_sha256",
    )
    _write(mismatch_path, mismatch_payload)
    with pytest.raises(task.CurrentRuleCohortError, match="date certificate version mismatch"):
        task.build_stock_analysis_current_rule_cohort_dry_run(
            duckdb_path=target,
            bundle_path=mismatch_path,
            receipt_path=tmp_path / "mismatch-lineage-dry.json",
            created_at=NOW,
        )


def test_promotion_is_unique_and_idempotent(tmp_path: Path) -> None:
    ready = _materialize_ready(tmp_path)
    target = Path(ready["target"])
    bundle = ready["bundle"]
    material = ready["material"]
    approval = _approval(
        tmp_path / "promote-approval.json",
        operation="promote",
        bundle=bundle,
        target_sha=_file_sha(target),
        extra={"materialize_receipt_sha256": material["canonical_receipt_sha256"]},
    )
    promotion_path = tmp_path / "promotion.json"
    promoted = task.promote_stock_analysis_current_rule_cohort(
        duckdb_path=target,
        bundle_path=bundle["bundle_path"],
        materialize_receipt_path=ready["material_path"],
        approval_artifact_path=approval,
        receipt_path=promotion_path,
        allow_write=True,
        created_at=NOW,
    )
    assert promoted["status"] == task.CERTIFIED_STATUS
    conn = duckdb.connect(str(target), read_only=True)
    try:
        assert conn.execute(
            f"select count(*) from {task.MANIFEST_TABLE} where is_active = true"
        ).fetchone()[0] == 1
    finally:
        conn.close()

    replay = task.promote_stock_analysis_current_rule_cohort(
        duckdb_path=target,
        bundle_path=bundle["bundle_path"],
        materialize_receipt_path=ready["material_path"],
        approval_artifact_path=approval,
        receipt_path=tmp_path / "promotion-replay.json",
        allow_write=True,
        created_at=NOW,
    )
    assert replay["idempotent_replay"] is True
    with pytest.raises(task.CurrentRuleCohortError, match="lifecycle advancement"):
        task.materialize_stock_analysis_current_rule_cohort(
            duckdb_path=target,
            bundle_path=bundle["bundle_path"],
            dry_run_receipt_path=ready["dry_path"],
            approval_artifact_path=tmp_path
            / "cohort-d6b-1-materialize-approval.json",
            target_backup_path=ready["backup"],
            receipt_path=ready["material_path"],
            allow_write=True,
            created_at=NOW,
        )


def test_materialize_is_idempotent_without_rewriting_rows(tmp_path: Path) -> None:
    ready = _materialize_ready(tmp_path)
    stable = task.materialize_stock_analysis_current_rule_cohort(
        duckdb_path=ready["target"],
        bundle_path=ready["bundle"]["bundle_path"],
        dry_run_receipt_path=ready["dry_path"],
        approval_artifact_path=tmp_path / "cohort-d6b-1-materialize-approval.json",
        target_backup_path=ready["backup"],
        receipt_path=ready["material_path"],
        allow_write=True,
        created_at=NOW,
    )
    assert stable == ready["material"]
    with pytest.raises(task.CurrentRuleCohortError, match="prepared receipt path"):
        task.materialize_stock_analysis_current_rule_cohort(
            duckdb_path=ready["target"],
            bundle_path=ready["bundle"]["bundle_path"],
            dry_run_receipt_path=ready["dry_path"],
            approval_artifact_path=tmp_path / "cohort-d6b-1-materialize-approval.json",
            target_backup_path=ready["backup"],
            receipt_path=tmp_path / "material-replay.json",
            allow_write=True,
            created_at=NOW,
        )
    conn = duckdb.connect(str(ready["target"]), read_only=True)
    try:
        assert conn.execute(f"select count(*) from {task.MANIFEST_TABLE}").fetchone()[0] == 1
        assert conn.execute(f"select count(*) from {task.FACT_TABLE}").fetchone()[0] == 100
    finally:
        conn.close()


def test_materialize_transaction_failure_rolls_back_all_cohort_rows(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = _base_database(tmp_path)
    bundle = _bundle_artifacts(tmp_path, target=target)
    dry_path = tmp_path / "dry.json"
    dry = task.build_stock_analysis_current_rule_cohort_dry_run(
        duckdb_path=target,
        bundle_path=bundle["bundle_path"],
        receipt_path=dry_path,
        created_at=NOW,
    )
    backup = tmp_path / "backup.duckdb"
    shutil.copy2(target, backup)
    approval = _approval(
        tmp_path / "approval.json",
        operation="materialize",
        bundle=bundle,
        target_sha=_file_sha(target),
        extra={"dry_run_receipt_sha256": dry["canonical_receipt_sha256"]},
    )
    original = task._insert_rows
    calls = 0

    def fail_after_manifest(conn, table, rows):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("injected fact write failure")
        return original(conn, table, rows)

    monkeypatch.setattr(task, "_insert_rows", fail_after_manifest)
    with pytest.raises(RuntimeError, match="injected fact write failure"):
        task.materialize_stock_analysis_current_rule_cohort(
            duckdb_path=target,
            bundle_path=bundle["bundle_path"],
            dry_run_receipt_path=dry_path,
            approval_artifact_path=approval,
            target_backup_path=backup,
            receipt_path=tmp_path / "material.json",
            allow_write=True,
            created_at=NOW,
        )
    conn = duckdb.connect(str(target), read_only=True)
    try:
        assert conn.execute(f"select count(*) from {task.MANIFEST_TABLE}").fetchone()[0] == 0
        assert conn.execute(f"select count(*) from {task.FACT_TABLE}").fetchone()[0] == 0
        assert conn.execute(f"select count(*) from {task.CERTIFICATE_TABLE}").fetchone()[0] == 0
    finally:
        conn.close()


def test_materialize_receipt_link_crash_recovers_only_at_prepared_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = _base_database(tmp_path)
    bundle = _bundle_artifacts(tmp_path, target=target)
    dry_path = tmp_path / "dry.json"
    dry = task.build_stock_analysis_current_rule_cohort_dry_run(
        duckdb_path=target,
        bundle_path=bundle["bundle_path"],
        receipt_path=dry_path,
        created_at=NOW,
    )
    backup = tmp_path / "backup.duckdb"
    shutil.copy2(target, backup)
    approval = _approval(
        tmp_path / "approval.json",
        operation="materialize",
        bundle=bundle,
        target_sha=_file_sha(target),
        extra={"dry_run_receipt_sha256": dry["canonical_receipt_sha256"]},
    )
    receipt_path = tmp_path / "material.json"
    original_link = task._link_materialize_receipt_trace

    def crash_before_trace(**_kwargs):
        raise RuntimeError("injected trace-link crash")

    monkeypatch.setattr(task, "_link_materialize_receipt_trace", crash_before_trace)
    with pytest.raises(RuntimeError, match="trace-link crash"):
        task.materialize_stock_analysis_current_rule_cohort(
            duckdb_path=target,
            bundle_path=bundle["bundle_path"],
            dry_run_receipt_path=dry_path,
            approval_artifact_path=approval,
            target_backup_path=backup,
            receipt_path=receipt_path,
            allow_write=True,
            created_at=NOW,
        )
    conn = duckdb.connect(str(target), read_only=True)
    try:
        status, notes_json = conn.execute(
            f"select cohort_status, notes_json from {task.MANIFEST_TABLE}"
        ).fetchone()
        assert status == task.MATERIALIZED_STATUS
        assert "materialize_receipt_sha256" not in json.loads(notes_json)
    finally:
        conn.close()
    assert receipt_path.is_file()

    monkeypatch.setattr(task, "_link_materialize_receipt_trace", original_link)
    recovered = task.materialize_stock_analysis_current_rule_cohort(
        duckdb_path=target,
        bundle_path=bundle["bundle_path"],
        dry_run_receipt_path=dry_path,
        approval_artifact_path=approval,
        target_backup_path=backup,
        receipt_path=receipt_path,
        allow_write=True,
        created_at=NOW,
    )
    conn = duckdb.connect(str(target), read_only=True)
    try:
        notes = json.loads(
            conn.execute(f"select notes_json from {task.MANIFEST_TABLE}").fetchone()[0]
        )
        assert notes["materialize_receipt_sha256"] == recovered[
            "canonical_receipt_sha256"
        ]
    finally:
        conn.close()


def test_preexisting_receipt_with_wrong_stable_bindings_is_rejected(
    tmp_path: Path,
) -> None:
    target = _base_database(tmp_path)
    bundle = _bundle_artifacts(tmp_path, target=target)
    dry_path = tmp_path / "dry.json"
    dry = task.build_stock_analysis_current_rule_cohort_dry_run(
        duckdb_path=target,
        bundle_path=bundle["bundle_path"],
        receipt_path=dry_path,
        created_at=NOW,
    )
    backup = tmp_path / "backup.duckdb"
    shutil.copy2(target, backup)
    approval = _approval(
        tmp_path / "approval.json",
        operation="materialize",
        bundle=bundle,
        target_sha=_file_sha(target),
        extra={"dry_run_receipt_sha256": dry["canonical_receipt_sha256"]},
    )
    receipt_path = tmp_path / "material.json"
    _write(
        receipt_path,
        _seal(
            {
                "schema_version": 1,
                "receipt_kind": task.MATERIALIZE_RECEIPT_KIND,
                "status": task.MATERIALIZED_STATUS,
                "cohort_id": bundle["cohort_id"],
                "bundle_sha256": bundle["bundle_sha"],
                "plan_digest_sha256": bundle["plan_sha"],
                "dry_run_receipt_sha256": "F" * 64,
                "approval_sha256": "E" * 64,
                "created_at": NOW,
            },
            "canonical_receipt_sha256",
        ),
    )
    with pytest.raises(task.CurrentRuleCohortError, match="existing receipt binding mismatch"):
        task.materialize_stock_analysis_current_rule_cohort(
            duckdb_path=target,
            bundle_path=bundle["bundle_path"],
            dry_run_receipt_path=dry_path,
            approval_artifact_path=approval,
            target_backup_path=backup,
            receipt_path=receipt_path,
            allow_write=True,
            created_at=NOW,
        )


def test_dry_run_rejects_bundle_when_zero_signal_date_lacks_persisted_certificate(
    tmp_path: Path,
) -> None:
    target = _base_database(tmp_path)
    artifacts = _bundle_artifacts(tmp_path, target=target)
    bundle_path = Path(artifacts["bundle_path"])
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    zero_date = payload["date_certificates"][0]["trade_date"]
    payload["facts"] = [
        row for row in payload["facts"] if row["signal_date"] != zero_date
    ]
    payload["date_certificates"][0].update(
        {
            "certificate_status": "completed_no_strategy_signals",
            "reason_code": "policy_active_zero_signal",
            "candidate_count": 0,
            "executable_candidate_count": 0,
            "t5_usable_count": 0,
            "t20_usable_count": 0,
            "matched_entry_count": 0,
            "control_entry_proven_count": 0,
            "control_exit_proven_5d_count": 0,
            "control_exit_proven_20d_count": 0,
        }
    )
    payload["summary"].update(
        {
            "completed_with_signals_dates": 19,
            "completed_no_signal_dates": 1,
            "matched_entry_count": 95,
            "t5_usable_count": 95,
            "t20_usable_count": 95,
        }
    )
    payload = _reseal_bundle_payload(payload, target=target)
    _write(bundle_path, payload)

    with pytest.raises(task.CurrentRuleCohortError, match="zero-signal date lacks persisted certificate"):
        task.build_stock_analysis_current_rule_cohort_dry_run(
            duckdb_path=target,
            bundle_path=bundle_path,
            receipt_path=tmp_path / "dry.json",
            created_at=NOW,
        )


def test_dry_run_rejects_duplicate_source_availability_receipt_content(
    tmp_path: Path,
) -> None:
    target = _base_database(tmp_path)
    artifacts = _bundle_artifacts(tmp_path, target=target)
    bundle_path = Path(artifacts["bundle_path"])
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    source_ref = payload["artifacts"]["source_availability_receipts"][0]
    payload["artifacts"]["source_availability_receipts"].append(dict(source_ref))
    payload = _reseal_bundle_payload(payload, target=target)
    _write(bundle_path, payload)

    with pytest.raises(task.CurrentRuleCohortError, match="duplicate source availability key across receipts"):
        task.build_stock_analysis_current_rule_cohort_dry_run(
            duckdb_path=target,
            bundle_path=bundle_path,
            receipt_path=tmp_path / "dry.json",
            created_at=NOW,
        )


def test_dry_run_rejects_source_availability_after_evaluation_date(
    tmp_path: Path,
) -> None:
    target = _base_database(tmp_path)
    artifacts = _bundle_artifacts(tmp_path, target=target)
    bundle_path = Path(artifacts["bundle_path"])
    source_path = bundle_path.with_name("cohort-d6b-1-source.json")
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    source_receipt = json.loads(source_path.read_text(encoding="utf-8"))
    source_receipt["sources"][0]["available_at"] = "2026-03-02"
    _write(source_path, source_receipt)
    new_source_sha = _canonical_sha(source_receipt)
    payload["artifacts"]["source_availability_receipts"][0]["sha256"] = new_source_sha
    payload = _reseal_bundle_payload(payload, target=target)
    _write(bundle_path, payload)

    with pytest.raises(task.CurrentRuleCohortError, match="source availability occurs after evaluation date"):
        task.build_stock_analysis_current_rule_cohort_dry_run(
            duckdb_path=target,
            bundle_path=bundle_path,
            receipt_path=tmp_path / "dry.json",
            created_at=NOW,
        )


def test_second_promotion_and_rollback_restore_prior_active_without_deleting_facts(
    tmp_path: Path,
) -> None:
    first = _materialize_ready(tmp_path, cohort_id="cohort-first")
    target = Path(first["target"])
    first_bundle = first["bundle"]
    first_material = first["material"]
    first_promote_approval = _approval(
        tmp_path / "first-promote-approval.json",
        operation="promote",
        bundle=first_bundle,
        target_sha=_file_sha(target),
        extra={
            "materialize_receipt_sha256": first_material["canonical_receipt_sha256"]
        },
    )
    task.promote_stock_analysis_current_rule_cohort(
        duckdb_path=target,
        bundle_path=first_bundle["bundle_path"],
        materialize_receipt_path=first["material_path"],
        approval_artifact_path=first_promote_approval,
        receipt_path=tmp_path / "first-promotion.json",
        allow_write=True,
        created_at=NOW,
    )

    second_bundle = _bundle_artifacts(tmp_path, target=target, cohort_id="cohort-second")
    second_dry_path = tmp_path / "second-dry.json"
    second_dry = task.build_stock_analysis_current_rule_cohort_dry_run(
        duckdb_path=target,
        bundle_path=second_bundle["bundle_path"],
        receipt_path=second_dry_path,
        created_at=NOW,
    )
    second_backup = tmp_path / "second-backup.duckdb"
    shutil.copy2(target, second_backup)
    second_material_approval = _approval(
        tmp_path / "second-material-approval.json",
        operation="materialize",
        bundle=second_bundle,
        target_sha=_file_sha(target),
        extra={
            "dry_run_receipt_sha256": second_dry["canonical_receipt_sha256"]
        },
    )
    second_material_path = tmp_path / "second-material.json"
    second_material = task.materialize_stock_analysis_current_rule_cohort(
        duckdb_path=target,
        bundle_path=second_bundle["bundle_path"],
        dry_run_receipt_path=second_dry_path,
        approval_artifact_path=second_material_approval,
        target_backup_path=second_backup,
        receipt_path=second_material_path,
        allow_write=True,
        created_at=NOW,
    )
    second_promote_approval = _approval(
        tmp_path / "second-promote-approval.json",
        operation="promote",
        bundle=second_bundle,
        target_sha=_file_sha(target),
        extra={
            "materialize_receipt_sha256": second_material[
                "canonical_receipt_sha256"
            ]
        },
    )
    second_promotion_path = tmp_path / "second-promotion.json"
    second_promotion = task.promote_stock_analysis_current_rule_cohort(
        duckdb_path=target,
        bundle_path=second_bundle["bundle_path"],
        materialize_receipt_path=second_material_path,
        approval_artifact_path=second_promote_approval,
        receipt_path=second_promotion_path,
        allow_write=True,
        created_at=NOW,
    )
    assert second_promotion["promoted_from_cohort_id"] == "cohort-first"

    rollback_approval = _approval(
        tmp_path / "rollback-approval.json",
        operation="rollback_promotion",
        bundle=second_bundle,
        target_sha=_file_sha(target),
        extra={
            "promotion_receipt_sha256": second_promotion[
                "canonical_receipt_sha256"
            ]
        },
    )
    rolled_back = task.rollback_stock_analysis_current_rule_cohort_promotion(
        duckdb_path=target,
        promotion_receipt_path=second_promotion_path,
        approval_artifact_path=rollback_approval,
        receipt_path=tmp_path / "rollback.json",
        allow_write=True,
        created_at=NOW,
    )
    assert rolled_back["restored_cohort_id"] == "cohort-first"
    conn = duckdb.connect(str(target), read_only=True)
    try:
        rows = conn.execute(
            f"select cohort_id, cohort_status, is_active from {task.MANIFEST_TABLE} order by cohort_id"
        ).fetchall()
        assert rows == [
            ("cohort-first", task.CERTIFIED_STATUS, True),
            ("cohort-second", task.ROLLED_BACK_STATUS, False),
        ]
        assert conn.execute(f"select count(*) from {task.FACT_TABLE}").fetchone()[0] == 200
    finally:
        conn.close()


def test_first_promotion_rollback_leaves_no_active_and_retains_facts(
    tmp_path: Path,
) -> None:
    ready = _materialize_ready(tmp_path, cohort_id="cohort-first-only")
    target = Path(ready["target"])
    bundle = ready["bundle"]
    material = ready["material"]
    promote_approval = _approval(
        tmp_path / "promote-approval.json",
        operation="promote",
        bundle=bundle,
        target_sha=_file_sha(target),
        extra={"materialize_receipt_sha256": material["canonical_receipt_sha256"]},
    )
    promotion_path = tmp_path / "promotion.json"
    promotion = task.promote_stock_analysis_current_rule_cohort(
        duckdb_path=target,
        bundle_path=bundle["bundle_path"],
        materialize_receipt_path=ready["material_path"],
        approval_artifact_path=promote_approval,
        receipt_path=promotion_path,
        allow_write=True,
        created_at=NOW,
    )
    assert promotion["promoted_from_cohort_id"] is None
    rollback_approval = _approval(
        tmp_path / "rollback-approval.json",
        operation="rollback_promotion",
        bundle=bundle,
        target_sha=_file_sha(target),
        extra={
            "promotion_receipt_sha256": promotion["canonical_receipt_sha256"]
        },
    )
    rollback_path = tmp_path / "rollback.json"
    rolled_back = task.rollback_stock_analysis_current_rule_cohort_promotion(
        duckdb_path=target,
        promotion_receipt_path=promotion_path,
        approval_artifact_path=rollback_approval,
        receipt_path=rollback_path,
        allow_write=True,
        created_at=NOW,
    )
    assert rolled_back["restored_cohort_id"] is None
    conn = duckdb.connect(str(target), read_only=True)
    try:
        assert conn.execute(
            f"select count(*) from {task.MANIFEST_TABLE} where is_active = true"
        ).fetchone()[0] == 0
        assert conn.execute(
            f"select cohort_status from {task.MANIFEST_TABLE}"
        ).fetchone()[0] == task.ROLLED_BACK_STATUS
        assert conn.execute(f"select count(*) from {task.FACT_TABLE}").fetchone()[0] == 100
    finally:
        conn.close()

    replay = task.rollback_stock_analysis_current_rule_cohort_promotion(
        duckdb_path=target,
        promotion_receipt_path=promotion_path,
        approval_artifact_path=rollback_approval,
        receipt_path=tmp_path / "rollback-replay.json",
        allow_write=True,
        created_at=NOW,
    )
    assert replay["idempotent_replay"] is True


@pytest.mark.parametrize(
    ("field", "replacement", "error"),
    [
        ("plan_digest_sha256", "B" * 64, "plan_digest_sha256"),
        ("idempotency_key", "C" * 64, "idempotency_key"),
    ],
)
def test_plan_and_target_bound_idempotency_tampering_is_rejected(
    tmp_path: Path,
    field: str,
    replacement: str,
    error: str,
) -> None:
    target = _base_database(tmp_path)
    artifacts = _bundle_artifacts(tmp_path, target=target)
    bundle_path = Path(artifacts["bundle_path"])
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    payload[field] = replacement
    payload = _seal(
        {key: value for key, value in payload.items() if key != "canonical_bundle_sha256"},
        "canonical_bundle_sha256",
    )
    _write(bundle_path, payload)
    with pytest.raises(task.CurrentRuleCohortError, match=error):
        task.build_stock_analysis_current_rule_cohort_dry_run(
            duckdb_path=target,
            bundle_path=bundle_path,
            receipt_path=tmp_path / "dry.json",
            created_at=NOW,
        )


def test_dry_run_rejects_bundle_with_only_nineteen_completed_dates(
    tmp_path: Path,
) -> None:
    target = _base_database(tmp_path)
    bundle = _bundle_artifacts(tmp_path, target=target, total_days=19)

    with pytest.raises(task.CurrentRuleCohortError, match="completed_dates must be at least 20"):
        task.build_stock_analysis_current_rule_cohort_dry_run(
            duckdb_path=target,
            bundle_path=bundle["bundle_path"],
            receipt_path=tmp_path / "dry.json",
            created_at=NOW,
        )


def test_dry_run_rejects_bundle_with_only_ninety_nine_matched_entries(
    tmp_path: Path,
) -> None:
    target = _base_database(tmp_path)
    artifacts = _bundle_artifacts(tmp_path, target=target)
    bundle_path = Path(artifacts["bundle_path"])
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    reduced_date = payload["date_certificates"][-1]["trade_date"]
    removed = False
    updated_facts: list[dict[str, object]] = []
    for row in payload["facts"]:
        if row["signal_date"] == reduced_date and not removed:
            removed = True
            continue
        updated_facts.append(row)
    payload["facts"] = updated_facts
    payload["date_certificates"][-1].update(
        {
            "candidate_count": 4,
            "executable_candidate_count": 4,
            "t5_usable_count": 4,
            "t20_usable_count": 4,
            "matched_entry_count": 4,
            "control_entry_proven_count": 80,
            "control_exit_proven_5d_count": 80,
            "control_exit_proven_20d_count": 80,
        }
    )
    candidate_keys = [
        {
            "signal_date": row["signal_date"],
            "signal_kind": row["signal_kind"],
            "stock_code": row["stock_code"],
        }
        for row in payload["facts"]
        if row["signal_date"] == reduced_date
    ]
    payload["date_certificates"][-1]["blocker_detail"]["runner_candidate_key_proof"] = {
        "candidate_keys": candidate_keys,
        "candidate_key_sha256": _canonical_sha(candidate_keys),
        "runner_candidate_count": len(candidate_keys),
    }
    payload["summary"].update(
        {
            "matched_entry_count": 99,
            "t5_usable_count": 99,
            "t20_usable_count": 99,
        }
    )
    payload = _reseal_bundle_payload(payload, target=target)
    _write(bundle_path, payload)

    with pytest.raises(task.CurrentRuleCohortError, match="matched_entry_count must be at least 100"):
        task.build_stock_analysis_current_rule_cohort_dry_run(
            duckdb_path=target,
            bundle_path=bundle_path,
            receipt_path=tmp_path / "dry.json",
            created_at=NOW,
        )


def test_dry_run_rejects_signal_date_with_tampered_runner_candidate_key_proof(
    tmp_path: Path,
) -> None:
    target = _base_database(tmp_path)
    artifacts = _bundle_artifacts(tmp_path, target=target)
    bundle_path = Path(artifacts["bundle_path"])
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    proof = payload["date_certificates"][0]["blocker_detail"]["runner_candidate_key_proof"]
    proof["candidate_keys"] = proof["candidate_keys"][:-1]
    proof["candidate_key_sha256"] = _canonical_sha(proof["candidate_keys"])
    proof["runner_candidate_count"] = len(proof["candidate_keys"])
    payload = _reseal_bundle_payload(payload, target=target)
    _write(bundle_path, payload)

    with pytest.raises(task.CurrentRuleCohortError, match="runner candidate proof does not match fact key set"):
        task.build_stock_analysis_current_rule_cohort_dry_run(
            duckdb_path=target,
            bundle_path=bundle_path,
            receipt_path=tmp_path / "dry.json",
            created_at=NOW,
        )


def test_dry_run_rejects_signal_date_with_tampered_matched_alpha(
    tmp_path: Path,
) -> None:
    target = _base_database(tmp_path)
    artifacts = _bundle_artifacts(tmp_path, target=target)
    bundle_path = Path(artifacts["bundle_path"])
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    payload["facts"][0]["matched_alpha_5d"] = 0.011
    payload = _reseal_bundle_payload(payload, target=target)
    _write(bundle_path, payload)

    with pytest.raises(task.CurrentRuleCohortError, match="matched_alpha_5d must equal candidate minus 20-control mean"):
        task.build_stock_analysis_current_rule_cohort_dry_run(
            duckdb_path=target,
            bundle_path=bundle_path,
            receipt_path=tmp_path / "dry.json",
            created_at=NOW,
        )


def test_approval_cannot_be_reused_for_byte_identical_other_database(
    tmp_path: Path,
) -> None:
    target = _base_database(tmp_path)
    bundle = _bundle_artifacts(tmp_path, target=target)
    dry_path = tmp_path / "dry.json"
    dry = task.build_stock_analysis_current_rule_cohort_dry_run(
        duckdb_path=target,
        bundle_path=bundle["bundle_path"],
        receipt_path=dry_path,
        created_at=NOW,
    )
    backup = tmp_path / "backup.duckdb"
    shutil.copy2(target, backup)
    approval_path = _approval(
        tmp_path / "approval.json",
        operation="materialize",
        bundle=bundle,
        target_sha=_file_sha(target),
        extra={"dry_run_receipt_sha256": dry["canonical_receipt_sha256"]},
    )
    approval = json.loads(approval_path.read_text(encoding="utf-8"))
    approval["target_database_path"] = str((tmp_path / "other.duckdb").resolve())
    approval = _seal(
        {
            key: value
            for key, value in approval.items()
            if key != "canonical_approval_sha256"
        },
        "canonical_approval_sha256",
    )
    _write(approval_path, approval)
    with pytest.raises(task.CurrentRuleCohortError, match="target database path mismatch"):
        task.materialize_stock_analysis_current_rule_cohort(
            duckdb_path=target,
            bundle_path=bundle["bundle_path"],
            dry_run_receipt_path=dry_path,
            approval_artifact_path=approval_path,
            target_backup_path=backup,
            receipt_path=tmp_path / "material.json",
            allow_write=True,
            created_at=NOW,
        )


@pytest.mark.parametrize("case", ["missing_open_date", "wrong_signal_status"])
def test_strict_calendar_coverage_and_signal_certificate_status_are_enforced(
    tmp_path: Path,
    case: str,
) -> None:
    target = _base_database(tmp_path)
    artifacts = _bundle_artifacts(tmp_path, target=target)
    bundle_path = Path(artifacts["bundle_path"])
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    if case == "wrong_signal_status":
        payload["date_certificates"][0]["certificate_status"] = "wrong"
        expected = "signal date certificate status mismatch"
    else:
        missing_date = payload["date_certificates"][-1]["trade_date"]
        payload["date_certificates"].pop()
        payload["facts"] = [
            row for row in payload["facts"] if row["signal_date"] != missing_date
        ]
        payload["summary"].update(
            {
                "completed_dates": 19,
                "completed_with_signals_dates": 19,
                "matched_entry_count": 95,
                "t5_usable_count": 95,
                "t20_usable_count": 95,
            }
        )
        expected = "strict coverage"
    payload = _seal(
        {key: value for key, value in payload.items() if key != "canonical_bundle_sha256"},
        "canonical_bundle_sha256",
    )
    _write(bundle_path, payload)
    with pytest.raises(task.CurrentRuleCohortError, match=expected):
        task.build_stock_analysis_current_rule_cohort_dry_run(
            duckdb_path=target,
            bundle_path=bundle_path,
            receipt_path=tmp_path / "dry.json",
            created_at=NOW,
        )


@pytest.mark.parametrize(
    ("field", "replacement"),
    [
        ("run_id", "wrong-run"),
        ("vendor_version", "wrong-vendor"),
        ("available_at", "2025-12-30"),
    ],
)
def test_control_source_tuple_must_match_persisted_availability_receipt(
    tmp_path: Path,
    field: str,
    replacement: str,
) -> None:
    target = _base_database(tmp_path)
    artifacts = _bundle_artifacts(tmp_path, target=target)
    bundle_path = Path(artifacts["bundle_path"])
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    leaf = payload["facts"][0]["control_pit_proof"]["controls"][0][
        "source_evidence"
    ]["observation"]["entry"]
    leaf[field] = replacement
    payload = _seal(
        {key: value for key, value in payload.items() if key != "canonical_bundle_sha256"},
        "canonical_bundle_sha256",
    )
    _write(bundle_path, payload)
    with pytest.raises(task.CurrentRuleCohortError, match="not attested"):
        task.build_stock_analysis_current_rule_cohort_dry_run(
            duckdb_path=target,
            bundle_path=bundle_path,
            receipt_path=tmp_path / "dry.json",
            created_at=NOW,
        )


def test_candidate_source_evidence_is_required_for_each_signal_fact(
    tmp_path: Path,
) -> None:
    target = _base_database(tmp_path)
    artifacts = _bundle_artifacts(tmp_path, target=target)
    bundle_path = Path(artifacts["bundle_path"])
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    del payload["facts"][0]["evidence"]["candidate_source_evidence"]
    payload = _reseal_bundle_payload(payload, target=target)
    _write(bundle_path, payload)

    with pytest.raises(
        task.CurrentRuleCohortError,
        match="candidate source evidence must be an object",
    ):
        task.build_stock_analysis_current_rule_cohort_dry_run(
            duckdb_path=target,
            bundle_path=bundle_path,
            receipt_path=tmp_path / "dry.json",
            created_at=NOW,
        )


def test_candidate_source_evidence_rejects_leaf_after_evaluation_date(
    tmp_path: Path,
) -> None:
    target = _base_database(tmp_path)
    artifacts = _bundle_artifacts(tmp_path, target=target)
    bundle_path = Path(artifacts["bundle_path"])
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    payload["facts"][0]["evidence"]["candidate_source_evidence"]["adjustment_factor"][
        "exit_20d"
    ]["available_at"] = "2026-03-02"
    payload = _reseal_bundle_payload(payload, target=target)
    _write(bundle_path, payload)

    with pytest.raises(
        task.CurrentRuleCohortError,
        match="candidate source evidence is not attested by persisted availability receipt",
    ):
        task.build_stock_analysis_current_rule_cohort_dry_run(
            duckdb_path=target,
            bundle_path=bundle_path,
            receipt_path=tmp_path / "dry.json",
            created_at=NOW,
        )


def test_candidate_source_evidence_rejects_tuple_drift_from_receipt(
    tmp_path: Path,
) -> None:
    target = _base_database(tmp_path)
    artifacts = _bundle_artifacts(tmp_path, target=target)
    bundle_path = Path(artifacts["bundle_path"])
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    payload["facts"][0]["evidence"]["candidate_source_evidence"]["observation"]["entry"][
        "run_id"
    ] = "wrong-run"
    payload = _reseal_bundle_payload(payload, target=target)
    _write(bundle_path, payload)

    with pytest.raises(
        task.CurrentRuleCohortError,
        match="candidate source evidence is not attested by persisted availability receipt",
    ):
        task.build_stock_analysis_current_rule_cohort_dry_run(
            duckdb_path=target,
            bundle_path=bundle_path,
            receipt_path=tmp_path / "dry.json",
            created_at=NOW,
        )


def test_candidate_limit_down_label_must_match_evidenced_prices(tmp_path: Path) -> None:
    target = _base_database(tmp_path)
    artifacts = _bundle_artifacts(tmp_path, target=target)
    bundle_path = Path(artifacts["bundle_path"])
    payload = json.loads(bundle_path.read_text(encoding="utf-8"))
    decision = payload["facts"][0]["evidence"]["candidate_source_evidence"]["limit_price"][
        "exit_5d_decisions"
    ][0]
    decision.update(decision="limit_down", close_value=9, down_limit=1)
    _write(bundle_path, _reseal_bundle_payload(payload, target=target))

    with pytest.raises(task.CurrentRuleCohortError, match="decision contradicts price"):
        task.build_stock_analysis_current_rule_cohort_dry_run(
            duckdb_path=target,
            bundle_path=bundle_path,
            receipt_path=tmp_path / "dry.json",
            created_at=NOW,
        )


def test_naive_receipt_timestamp_is_rejected(tmp_path: Path) -> None:
    target = _base_database(tmp_path)
    bundle = _bundle_artifacts(tmp_path, target=target)
    with pytest.raises(task.CurrentRuleCohortError, match="timezone"):
        task.build_stock_analysis_current_rule_cohort_dry_run(
            duckdb_path=target,
            bundle_path=bundle["bundle_path"],
            receipt_path=tmp_path / "dry.json",
            created_at="2026-08-22T12:00:00",
        )


def test_bundle_loader_rejects_oversized_json_before_parse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = _base_database(tmp_path)
    oversized = _write_oversized_json_stub(
        tmp_path / "oversized-bundle.json", max_bytes=task.MAX_BUNDLE_JSON_INPUT_BYTES
    )
    oversized_load_seen = False
    original_loads = task.json.loads

    def _guarded_loads(*args: object, **kwargs: object) -> object:
        nonlocal oversized_load_seen
        if args and isinstance(args[0], str) and len(args[0]) > task.MAX_BUNDLE_JSON_INPUT_BYTES:
            oversized_load_seen = True
        return original_loads(*args, **kwargs)

    monkeypatch.setattr(task.json, "loads", _guarded_loads)

    with pytest.raises(task.CurrentRuleCohortError, match="exceeds max JSON input size"):
        task.build_stock_analysis_current_rule_cohort_dry_run(
            duckdb_path=target,
            bundle_path=oversized,
            receipt_path=tmp_path / "dry.json",
            created_at=NOW,
        )

    assert oversized_load_seen is False


def test_approval_loader_rejects_oversized_json_before_parse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ready = _materialize_ready(tmp_path)
    oversized = _write_oversized_json_stub(tmp_path / "oversized-approval.json")
    oversized_load_seen = False
    original_loads = task.json.loads

    def _guarded_loads(*args: object, **kwargs: object) -> object:
        nonlocal oversized_load_seen
        if args and isinstance(args[0], str) and len(args[0]) == task.MAX_JSON_INPUT_BYTES + 1:
            oversized_load_seen = True
        return original_loads(*args, **kwargs)

    monkeypatch.setattr(task.json, "loads", _guarded_loads)

    with pytest.raises(task.CurrentRuleCohortError, match="exceeds max JSON input size"):
        task.materialize_stock_analysis_current_rule_cohort(
            duckdb_path=ready["target"],
            bundle_path=ready["bundle"]["bundle_path"],
            dry_run_receipt_path=ready["dry_path"],
            approval_artifact_path=oversized,
            target_backup_path=ready["backup"],
            receipt_path=tmp_path / "materialize.json",
            created_at=NOW,
            allow_write=True,
        )

    assert oversized_load_seen is False


def test_receipt_loader_rejects_oversized_json_before_parse(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    ready = _materialize_ready(tmp_path)
    oversized = _write_oversized_json_stub(tmp_path / "oversized-dry-run.json")
    oversized_load_seen = False
    original_loads = task.json.loads

    def _guarded_loads(*args: object, **kwargs: object) -> object:
        nonlocal oversized_load_seen
        if args and isinstance(args[0], str) and len(args[0]) == task.MAX_JSON_INPUT_BYTES + 1:
            oversized_load_seen = True
        return original_loads(*args, **kwargs)

    monkeypatch.setattr(task.json, "loads", _guarded_loads)

    with pytest.raises(task.CurrentRuleCohortError, match="exceeds max JSON input size"):
        task.materialize_stock_analysis_current_rule_cohort(
            duckdb_path=ready["target"],
            bundle_path=ready["bundle"]["bundle_path"],
            dry_run_receipt_path=oversized,
            approval_artifact_path=ready["approval"],
            target_backup_path=ready["backup"],
            receipt_path=tmp_path / "materialize.json",
            created_at=NOW,
            allow_write=True,
        )

    assert oversized_load_seen is False
