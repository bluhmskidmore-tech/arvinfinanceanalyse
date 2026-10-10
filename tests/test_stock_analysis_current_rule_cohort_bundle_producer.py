from __future__ import annotations

import copy
import hashlib
import json
import os
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from backend.app.governance.stock_analysis_calendar_receipt import (
    build_stock_analysis_calendar_receipt,
)
from backend.app.governance.stock_analysis_current_rule_certificate import (
    CURRENT_RULE_COVERAGE_AUTHORITY_MODE,
)
from backend.app.repositories.duckdb_migrations import register_all
from backend.app.repositories.duckdb_schema_registry import DuckDBSchemaRegistry
from backend.app.tasks import stock_analysis_current_rule_cohort_bundle_producer as producer
from backend.app.tasks import stock_analysis_current_rule_cohort_materialize as materialize

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]

NOW = "2026-08-23T12:00:00+08:00"
OWNER_ID = "OWNER-D6B-APPROVAL-001"
EVALUATION_AS_OF_DATE = "2026-08-31"


@pytest.fixture(autouse=True)
def _structural_bundle_fixture_has_no_source_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """Producer contract fixtures omit governed observation rows."""
    monkeypatch.setattr(materialize, "_validate_bundle_source_rows", lambda **_kwargs: None)


def _canonical_sha(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest().upper()


def _write(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    return path


def _base_database(tmp_path: Path, name: str = "target.duckdb") -> Path:
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
            "available_at": "2026-06-30",
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


def _source_receipt() -> dict[str, object]:
    return {
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
                "available_at": "2026-06-30",
            },
            {
                "table": "stock_adjustment_factor",
                "source_version": "sv_factor_proven",
                "vendor_version": "vv_choice",
                "rule_version": "rv_source_v1",
                "run_id": "source-run-factor",
                "available_at": "2026-06-30",
            },
        ],
    }


def _calendar_receipt(trade_dates: list[str]) -> dict[str, object]:
    return build_stock_analysis_calendar_receipt(
        calendar_rows=[
            {
                "exchange": "SSE",
                "cal_date": trade_date,
                "is_open": 1,
                "pretrade_date": None if index == 0 else trade_dates[index - 1],
            }
            for index, trade_date in enumerate(trade_dates)
        ],
        request_start_date=trade_dates[0],
        request_end_date=trade_dates[-1],
        fetched_at=NOW,
        authority_status="approved",
        owner_approval_id=OWNER_ID,
    )


def _runner_result(
    trade_date: str,
    candidate_codes: list[str],
    *,
    status: str,
) -> dict[str, object]:
    return {
        "status": status,
        "status_reason": (
            "current_rule_candidates_present"
            if status == "selection_completed_with_signals"
            else "policy_active_zero_signal"
        ),
        "requested_as_of_date": trade_date,
        "resolved_as_of_date": trade_date,
        "requested_matches_resolved": True,
        "market_state": "WARM",
        "selection_policy": "exp3b",
        "stock_candidate_formula_version": "rv_livermore_stock_candidates_bundle_v7",
        "rule_tuple_matches": True,
        "candidate_count": len(candidate_codes),
        "candidate_item_count": len(candidate_codes),
        "accepted_candidate_count": len(candidate_codes),
        "candidate_count_matches_items": True,
        "candidate_codes": list(candidate_codes),
        "accepted_candidate_codes": list(candidate_codes),
        "unique_candidate_codes": sorted(candidate_codes),
        "duplicate_candidate_codes": [],
        "stock_candidate_block_reason": None,
        "future_business_date_violations": [],
        "future_availability_violations": [],
        "blockers": [],
    }


def _signal_fact(
    *,
    trade_date: str,
    stock_code: str,
    candidate_rank: int,
    base_offset: float,
    matched_alpha_offset_5d: float,
    matched_alpha_offset_20d: float,
) -> dict[str, object]:
    signal = date.fromisoformat(trade_date)
    controls = []
    for control_index in range(20):
        controls.append(
            {
                "control_stock_code": f"C{candidate_rank:02d}{control_index:02d}.SZ",
                "candidate_stock_code": stock_code,
                "signal_date": trade_date,
                "signal_kind": "stock_candidate",
                "control_entry_date": (signal + timedelta(days=1)).isoformat(),
                "control_entry_price": 9.0 + base_offset + control_index / 100.0,
                "control_entry_price_kind": "open",
                "control_entry_executable": True,
                "control_entry_usable": True,
                "control_exit_date_5d": (signal + timedelta(days=5)).isoformat(),
                "control_exit_price_5d": 9.5 + base_offset,
                "control_return_5d_net_adj": 0.02 + control_index / 1000.0,
                "control_return_5d_usable": True,
                "control_exit_date_20d": (signal + timedelta(days=20)).isoformat(),
                "control_exit_price_20d": 10.0 + base_offset,
                "control_return_20d_net_adj": 0.06 + control_index / 1000.0,
                "control_return_20d_usable": True,
                "control_entry_failure_reason": None,
                "control_failure_reason_5d": None,
                "control_failure_reason_20d": None,
                "control_failure_reason": None,
                "formula_version": "fv_livermore_matched_baseline_v4",
                "metric_basis": "net_next_open_adj",
                "price_adjustment_mode": "adj_factor_ratio",
                "evaluation_as_of_date": EVALUATION_AS_OF_DATE,
                "source_evidence": _source_evidence(
                    entry_date=(signal + timedelta(days=1)).isoformat(),
                    exit_date_5d=(signal + timedelta(days=5)).isoformat(),
                    exit_date_20d=(signal + timedelta(days=20)).isoformat(),
                ),
            }
        )
    return {
        "signal_date": trade_date,
        "stock_code": stock_code,
        "stock_name": stock_code,
        "signal_kind": "stock_candidate",
        "candidate_rank": candidate_rank,
        "market_state": "WARM",
        "entry_date": (signal + timedelta(days=1)).isoformat(),
        "entry_price": 10.0 + base_offset,
        "entry_price_kind": "next_open",
        "entry_executable": True,
        "exit_date_5d": (signal + timedelta(days=5)).isoformat(),
        "exit_price_5d": 10.5 + base_offset,
        "return_5d_net_adj": 0.04 + base_offset / 100.0,
        "exit_date_20d": (signal + timedelta(days=20)).isoformat(),
        "exit_price_20d": 11.0 + base_offset,
        "return_20d_net_adj": 0.09 + base_offset / 100.0,
        "price_adjustment_mode": "adj_factor_ratio",
        "candidate_data_status": "usable",
        "execution_data_status": "usable",
        "matched_baseline_status": "usable",
        "matched_baseline_control_count": 20,
        "matched_alpha_5d": matched_alpha_offset_5d,
        "matched_alpha_20d": matched_alpha_offset_20d,
        "control_eval_basis": "net_next_open_adj",
        "candidate_source_evidence": _source_evidence(
            entry_date=(signal + timedelta(days=1)).isoformat(),
            exit_date_5d=(signal + timedelta(days=5)).isoformat(),
            exit_date_20d=(signal + timedelta(days=20)).isoformat(),
        ),
        "control_pit_proof": {"controls": controls},
        "evidence": {"seed": "test"},
    }


def _expected_governed_run_id(
    *,
    trade_dates: list[str],
    calendar_receipt: dict[str, object],
    source_receipts: list[dict[str, object]],
) -> str:
    return producer.derive_expected_stock_analysis_current_rule_governed_run_id(
        calendar_receipt_sha256=str(calendar_receipt["canonical_receipt_sha256"]),
        source_availability_receipt_sha256s=[
            _canonical_sha(receipt) for receipt in source_receipts
        ],
        frozen_version_tuple=_version_tuple(),
        evaluation_as_of_date=EVALUATION_AS_OF_DATE,
        open_dates=trade_dates,
    )


def _create_symlink(*, target: Path, link: Path, is_dir: bool) -> None:
    try:
        os.symlink(target, link, target_is_directory=is_dir)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlink creation unavailable in this environment: {exc}")


def _build_date_evidence(
    *,
    trade_dates: list[str],
    signal_day_count: int,
    per_day_fact_counts: dict[str, int] | None = None,
) -> list[dict[str, object]]:
    per_day_fact_counts = per_day_fact_counts or {}
    payload: list[dict[str, object]] = []
    for index, trade_date in enumerate(trade_dates):
        fact_count = (
            per_day_fact_counts.get(trade_date, 5) if index < signal_day_count else 0
        )
        candidate_codes = [f"{index:03d}{item:03d}.SZ" for item in range(fact_count)]
        facts = [
            _signal_fact(
                trade_date=trade_date,
                stock_code=code,
                candidate_rank=item + 1,
                base_offset=float(index + item),
                matched_alpha_offset_5d=999.0,
                matched_alpha_offset_20d=999.0,
            )
            for item, code in enumerate(candidate_codes)
        ]
        payload.append(
            {
                "trade_date": trade_date,
                "status": "ready",
                "runner_result": _runner_result(
                    trade_date,
                    candidate_codes,
                    status=(
                        "selection_completed_with_signals"
                        if fact_count > 0
                        else "selection_completed_no_signals"
                    ),
                ),
                "signal_facts": facts,
                "blockers": [],
            }
        )
    return payload


def test_producer_emits_canonical_bundle_and_dry_run_receipt_with_zero_signal_certificate(
    tmp_path: Path,
) -> None:
    target = _base_database(tmp_path)
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    output_root = tmp_path / "bundle-output"
    output_root.mkdir()
    trade_dates = [
        (date(2026, 7, 1) + timedelta(days=index)).isoformat() for index in range(21)
    ]
    calendar_receipt = _calendar_receipt(trade_dates)
    source_receipt = _source_receipt()
    calendar_path = _write(
        trusted_root / "calendar.json",
        calendar_receipt,
    )
    source_path = _write(trusted_root / "source.json", source_receipt)
    date_evidence = _build_date_evidence(trade_dates=trade_dates, signal_day_count=20)
    governed_run_id = _expected_governed_run_id(
        trade_dates=trade_dates,
        calendar_receipt=calendar_receipt,
        source_receipts=[source_receipt],
    )

    produced = producer.produce_stock_analysis_current_rule_cohort_bundle(
        duckdb_path=target,
        approved_calendar_receipt_path=calendar_path,
        source_availability_receipt_paths=[source_path],
        trusted_evidence_root=trusted_root,
            output_root=output_root,
            batch_name="batch-a",
            cohort_id="cohort-a",
            run_id="run-a",
            governed_run_id=governed_run_id,
            evaluation_as_of_date=EVALUATION_AS_OF_DATE,
            frozen_version_tuple=_version_tuple(),
            date_evidence=date_evidence,
            created_at=NOW,
    )

    bundle_path = Path(produced["bundle_path"])
    dry_path = Path(produced["dry_run_receipt_path"])
    assert bundle_path.is_file()
    assert dry_path.is_file()
    assert produced["summary"]["completed_dates"] == 21
    assert produced["summary"]["matched_entry_count"] == 100
    assert len(produced["zero_signal_certificate_paths"]) == 1
    assert produced["governed_run_id"] == governed_run_id

    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    first_fact = bundle["facts"][0]
    control_mean_5d = sum(
        row["control_return_5d_net_adj"]
        for row in first_fact["control_pit_proof"]["controls"]
    ) / 20.0
    control_mean_20d = sum(
        row["control_return_20d_net_adj"]
        for row in first_fact["control_pit_proof"]["controls"]
    ) / 20.0
    assert first_fact["matched_alpha_5d"] == pytest.approx(
        first_fact["return_5d_net_adj"] - control_mean_5d
    )
    assert first_fact["matched_alpha_20d"] == pytest.approx(
        first_fact["return_20d_net_adj"] - control_mean_20d
    )
    assert first_fact["evidence"]["matched_alpha_recomputed"] is True
    assert first_fact["evidence"]["candidate_source_proven"] is True
    assert bundle["plan"]["governed_run_id"] == governed_run_id

    dry_receipt = json.loads(dry_path.read_text(encoding="utf-8"))
    assert dry_receipt["status"] == "dry_run_completed"
    assert dry_receipt["database_unchanged"] is True

    replay = producer.produce_stock_analysis_current_rule_cohort_bundle(
        duckdb_path=target,
        approved_calendar_receipt_path=calendar_path,
        source_availability_receipt_paths=[source_path],
        trusted_evidence_root=trusted_root,
        output_root=output_root,
        batch_name="batch-a",
        cohort_id="cohort-a",
        run_id="run-a",
        governed_run_id=governed_run_id,
        evaluation_as_of_date=EVALUATION_AS_OF_DATE,
        frozen_version_tuple=_version_tuple(),
        date_evidence=date_evidence,
        created_at=NOW,
    )
    assert replay["bundle_sha256"] == produced["bundle_sha256"]
    assert replay["dry_run_receipt_sha256"] == produced["dry_run_receipt_sha256"]


def test_producer_rejects_signal_runner_candidate_mismatch(tmp_path: Path) -> None:
    target = _base_database(tmp_path)
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    output_root = tmp_path / "bundle-output"
    output_root.mkdir()
    trade_dates = [
        (date(2026, 7, 1) + timedelta(days=index)).isoformat() for index in range(20)
    ]
    calendar_receipt = _calendar_receipt(trade_dates)
    source_receipt = _source_receipt()
    calendar_path = _write(trusted_root / "calendar.json", calendar_receipt)
    source_path = _write(trusted_root / "source.json", source_receipt)
    date_evidence = _build_date_evidence(trade_dates=trade_dates, signal_day_count=20)
    broken = copy.deepcopy(date_evidence)
    original_codes = list(broken[0]["runner_result"]["candidate_codes"])
    broken_codes = ["DIFF.SZ", *original_codes[1:]]
    broken[0]["runner_result"]["accepted_candidate_codes"] = broken_codes
    broken[0]["runner_result"]["candidate_codes"] = broken_codes
    broken[0]["runner_result"]["unique_candidate_codes"] = sorted(broken_codes)

    with pytest.raises(
        producer.CurrentRuleCohortError,
        match="runner candidate keys do not match persisted facts",
    ):
        producer.produce_stock_analysis_current_rule_cohort_bundle(
            duckdb_path=target,
            approved_calendar_receipt_path=calendar_path,
            source_availability_receipt_paths=[source_path],
            trusted_evidence_root=trusted_root,
            output_root=output_root,
            batch_name="batch-b",
            cohort_id="cohort-b",
            run_id="run-b",
            governed_run_id=_expected_governed_run_id(
                trade_dates=trade_dates,
                calendar_receipt=calendar_receipt,
                source_receipts=[source_receipt],
            ),
            evaluation_as_of_date=EVALUATION_AS_OF_DATE,
            frozen_version_tuple=_version_tuple(),
            date_evidence=broken,
            created_at=NOW,
        )


def test_producer_rejects_untrusted_source_receipt_path(tmp_path: Path) -> None:
    target = _base_database(tmp_path)
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    output_root = tmp_path / "bundle-output"
    output_root.mkdir()
    outside_root = tmp_path / "outside"
    outside_root.mkdir()
    trade_dates = [
        (date(2026, 7, 1) + timedelta(days=index)).isoformat() for index in range(20)
    ]
    calendar_receipt = _calendar_receipt(trade_dates)
    calendar_path = _write(trusted_root / "calendar.json", calendar_receipt)
    source_receipt = _source_receipt()
    outside_source = _write(outside_root / "source.json", source_receipt)

    with pytest.raises(
        producer.CurrentRuleCohortError,
        match="source_availability_receipt_paths\\[0\\] must stay within its governed root",
    ):
        producer.produce_stock_analysis_current_rule_cohort_bundle(
            duckdb_path=target,
            approved_calendar_receipt_path=calendar_path,
            source_availability_receipt_paths=[outside_source],
            trusted_evidence_root=trusted_root,
            output_root=output_root,
            batch_name="batch-c",
            cohort_id="cohort-c",
            run_id="run-c",
            governed_run_id=_expected_governed_run_id(
                trade_dates=trade_dates,
                calendar_receipt=calendar_receipt,
                source_receipts=[source_receipt],
            ),
            evaluation_as_of_date=EVALUATION_AS_OF_DATE,
            frozen_version_tuple=_version_tuple(),
            date_evidence=_build_date_evidence(trade_dates=trade_dates, signal_day_count=20),
            created_at=NOW,
        )


def test_producer_fails_closed_on_nineteen_completed_dates(tmp_path: Path) -> None:
    target = _base_database(tmp_path)
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    output_root = tmp_path / "bundle-output"
    output_root.mkdir()
    trade_dates = [
        (date(2026, 7, 1) + timedelta(days=index)).isoformat() for index in range(19)
    ]
    calendar_receipt = _calendar_receipt(trade_dates)
    source_receipt = _source_receipt()
    calendar_path = _write(trusted_root / "calendar.json", calendar_receipt)
    source_path = _write(trusted_root / "source.json", source_receipt)

    with pytest.raises(
        producer.CurrentRuleCohortError,
        match="completed_dates must be at least 20",
    ):
        producer.produce_stock_analysis_current_rule_cohort_bundle(
            duckdb_path=target,
            approved_calendar_receipt_path=calendar_path,
            source_availability_receipt_paths=[source_path],
            trusted_evidence_root=trusted_root,
            output_root=output_root,
            batch_name="batch-d",
            cohort_id="cohort-d",
            run_id="run-d",
            governed_run_id=_expected_governed_run_id(
                trade_dates=trade_dates,
                calendar_receipt=calendar_receipt,
                source_receipts=[source_receipt],
            ),
            evaluation_as_of_date=EVALUATION_AS_OF_DATE,
            frozen_version_tuple=_version_tuple(),
            date_evidence=_build_date_evidence(
                trade_dates=trade_dates,
                signal_day_count=19,
                per_day_fact_counts={trade_dates[0]: 6},
            ),
            created_at=NOW,
        )


def test_producer_fails_closed_on_ninety_nine_matched_entries(tmp_path: Path) -> None:
    target = _base_database(tmp_path)
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    output_root = tmp_path / "bundle-output"
    output_root.mkdir()
    trade_dates = [
        (date(2026, 7, 1) + timedelta(days=index)).isoformat() for index in range(20)
    ]
    calendar_receipt = _calendar_receipt(trade_dates)
    source_receipt = _source_receipt()
    calendar_path = _write(trusted_root / "calendar.json", calendar_receipt)
    source_path = _write(trusted_root / "source.json", source_receipt)
    per_day_fact_counts = {trade_dates[-1]: 4}

    with pytest.raises(
        producer.CurrentRuleCohortError,
        match="matched_entry_count must be at least 100",
    ):
        producer.produce_stock_analysis_current_rule_cohort_bundle(
            duckdb_path=target,
            approved_calendar_receipt_path=calendar_path,
            source_availability_receipt_paths=[source_path],
            trusted_evidence_root=trusted_root,
            output_root=output_root,
            batch_name="batch-e",
            cohort_id="cohort-e",
            run_id="run-e",
            governed_run_id=_expected_governed_run_id(
                trade_dates=trade_dates,
                calendar_receipt=calendar_receipt,
                source_receipts=[source_receipt],
            ),
            evaluation_as_of_date=EVALUATION_AS_OF_DATE,
            frozen_version_tuple=_version_tuple(),
            date_evidence=_build_date_evidence(
                trade_dates=trade_dates,
                signal_day_count=20,
                per_day_fact_counts=per_day_fact_counts,
            ),
            created_at=NOW,
        )


def test_producer_rejects_missing_candidate_source_evidence(tmp_path: Path) -> None:
    target = _base_database(tmp_path)
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    output_root = tmp_path / "bundle-output"
    output_root.mkdir()
    trade_dates = [
        (date(2026, 7, 1) + timedelta(days=index)).isoformat() for index in range(20)
    ]
    calendar_receipt = _calendar_receipt(trade_dates)
    source_receipt = _source_receipt()
    calendar_path = _write(trusted_root / "calendar.json", calendar_receipt)
    source_path = _write(trusted_root / "source.json", source_receipt)
    broken = _build_date_evidence(trade_dates=trade_dates, signal_day_count=20)
    del broken[0]["signal_facts"][0]["candidate_source_evidence"]

    with pytest.raises(
        producer.CurrentRuleCohortError,
        match="signal_fact.candidate_source_evidence must be an object",
    ):
        producer.produce_stock_analysis_current_rule_cohort_bundle(
            duckdb_path=target,
            approved_calendar_receipt_path=calendar_path,
            source_availability_receipt_paths=[source_path],
            trusted_evidence_root=trusted_root,
            output_root=output_root,
            batch_name="batch-f",
            cohort_id="cohort-f",
            run_id="run-f",
            governed_run_id=_expected_governed_run_id(
                trade_dates=trade_dates,
                calendar_receipt=calendar_receipt,
                source_receipts=[source_receipt],
            ),
            evaluation_as_of_date=EVALUATION_AS_OF_DATE,
            frozen_version_tuple=_version_tuple(),
            date_evidence=broken,
            created_at=NOW,
        )


def test_governed_run_id_is_stable_and_mismatch_is_rejected(tmp_path: Path) -> None:
    target = _base_database(tmp_path)
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    output_root = tmp_path / "bundle-output"
    output_root.mkdir()
    trade_dates = [
        (date(2026, 7, 1) + timedelta(days=index)).isoformat() for index in range(20)
    ]
    calendar_receipt = _calendar_receipt(trade_dates)
    source_receipt = _source_receipt()
    calendar_path = _write(trusted_root / "calendar.json", calendar_receipt)
    source_path = _write(trusted_root / "source.json", source_receipt)
    expected = _expected_governed_run_id(
        trade_dates=trade_dates,
        calendar_receipt=calendar_receipt,
        source_receipts=[source_receipt],
    )
    assert expected == _expected_governed_run_id(
        trade_dates=trade_dates,
        calendar_receipt=calendar_receipt,
        source_receipts=[source_receipt],
    )

    with pytest.raises(
        producer.CurrentRuleCohortError,
        match="governed_run_id does not match the stable derived current-rule identity",
    ):
        producer.produce_stock_analysis_current_rule_cohort_bundle(
            duckdb_path=target,
            approved_calendar_receipt_path=calendar_path,
            source_availability_receipt_paths=[source_path],
            trusted_evidence_root=trusted_root,
            output_root=output_root,
            batch_name="batch-g",
            cohort_id="cohort-g",
            run_id="run-g",
            governed_run_id=expected + "-mismatch",
            evaluation_as_of_date=EVALUATION_AS_OF_DATE,
            frozen_version_tuple=_version_tuple(),
            date_evidence=_build_date_evidence(trade_dates=trade_dates, signal_day_count=20),
            created_at=NOW,
        )


def test_governed_run_id_helper_rejects_empty_source_receipt_hashes() -> None:
    with pytest.raises(
        producer.CurrentRuleCohortError,
        match="source_availability_receipt_sha256s must contain at least one receipt hash",
    ):
        producer.derive_expected_stock_analysis_current_rule_governed_run_id(
            calendar_receipt_sha256="A" * 64,
            source_availability_receipt_sha256s=[],
            frozen_version_tuple=_version_tuple(),
            evaluation_as_of_date=EVALUATION_AS_OF_DATE,
            open_dates=["2026-07-01"],
        )


def test_producer_rejects_raw_symlink_paths_even_within_governed_roots(
    tmp_path: Path,
) -> None:
    target = _base_database(tmp_path)
    trusted_real = tmp_path / "trusted-real"
    trusted_real.mkdir()
    output_real = tmp_path / "output-real"
    output_real.mkdir()
    trusted_root = tmp_path / "trusted-link"
    output_root = tmp_path / "output-link"
    _create_symlink(target=trusted_real, link=trusted_root, is_dir=True)
    _create_symlink(target=output_real, link=output_root, is_dir=True)
    trade_dates = [
        (date(2026, 7, 1) + timedelta(days=index)).isoformat() for index in range(20)
    ]
    calendar_receipt = _calendar_receipt(trade_dates)
    source_receipt = _source_receipt()
    calendar_path = _write(trusted_real / "calendar.json", calendar_receipt)
    source_real = _write(trusted_real / "source-real.json", source_receipt)
    source_link = trusted_real / "source-link.json"
    _create_symlink(target=source_real, link=source_link, is_dir=False)

    with pytest.raises(
        producer.CurrentRuleCohortError,
        match="trusted_evidence_root contains forbidden symlink/junction component",
    ):
        producer.produce_stock_analysis_current_rule_cohort_bundle(
            duckdb_path=target,
            approved_calendar_receipt_path=calendar_path,
            source_availability_receipt_paths=[source_link],
            trusted_evidence_root=trusted_root,
            output_root=output_real,
            batch_name="batch-h",
            cohort_id="cohort-h",
            run_id="run-h",
            governed_run_id=_expected_governed_run_id(
                trade_dates=trade_dates,
                calendar_receipt=calendar_receipt,
                source_receipts=[source_receipt],
            ),
            evaluation_as_of_date=EVALUATION_AS_OF_DATE,
            frozen_version_tuple=_version_tuple(),
            date_evidence=_build_date_evidence(trade_dates=trade_dates, signal_day_count=20),
            created_at=NOW,
        )


def test_producer_rejects_junction_like_path_components(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = _base_database(tmp_path)
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    output_root = tmp_path / "output"
    output_root.mkdir()
    trade_dates = [
        (date(2026, 7, 1) + timedelta(days=index)).isoformat() for index in range(20)
    ]
    calendar_receipt = _calendar_receipt(trade_dates)
    source_receipt = _source_receipt()
    calendar_path = _write(trusted_root / "calendar.json", calendar_receipt)
    source_path = _write(trusted_root / "source.json", source_receipt)
    junction_dir = trusted_root / "junction-dir"
    junction_dir.mkdir()

    path_type = type(junction_dir)

    def fake_is_junction(self: Path) -> bool:
        return self == junction_dir

    with monkeypatch.context() as junction_patch:
        junction_patch.setattr(path_type, "is_junction", fake_is_junction, raising=False)
        with pytest.raises(
            producer.CurrentRuleCohortError,
            match="trusted_evidence_root contains forbidden symlink/junction component",
        ):
            producer.produce_stock_analysis_current_rule_cohort_bundle(
                duckdb_path=target,
                approved_calendar_receipt_path=calendar_path,
                source_availability_receipt_paths=[source_path],
                trusted_evidence_root=junction_dir,
                output_root=output_root,
                batch_name="batch-h2",
                cohort_id="cohort-h2",
                run_id="run-h2",
                governed_run_id=_expected_governed_run_id(
                    trade_dates=trade_dates,
                    calendar_receipt=calendar_receipt,
                    source_receipts=[source_receipt],
                ),
                evaluation_as_of_date=EVALUATION_AS_OF_DATE,
                frozen_version_tuple=_version_tuple(),
                date_evidence=_build_date_evidence(
                    trade_dates=trade_dates,
                    signal_day_count=20,
                ),
                created_at=NOW,
            )


def test_producer_rejects_internal_symlinked_source_receipt_within_trusted_root(
    tmp_path: Path,
) -> None:
    target = _base_database(tmp_path)
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    output_root = tmp_path / "output"
    output_root.mkdir()
    trade_dates = [
        (date(2026, 7, 1) + timedelta(days=index)).isoformat() for index in range(20)
    ]
    calendar_receipt = _calendar_receipt(trade_dates)
    source_receipt = _source_receipt()
    calendar_path = _write(trusted_root / "calendar.json", calendar_receipt)
    source_real = _write(trusted_root / "source-real.json", source_receipt)
    source_link = trusted_root / "source-link.json"
    _create_symlink(target=source_real, link=source_link, is_dir=False)

    with pytest.raises(
        producer.CurrentRuleCohortError,
        match="source_availability_receipt_paths\\[0\\] contains forbidden symlink/junction component",
    ):
        producer.produce_stock_analysis_current_rule_cohort_bundle(
            duckdb_path=target,
            approved_calendar_receipt_path=calendar_path,
            source_availability_receipt_paths=[source_link],
            trusted_evidence_root=trusted_root,
            output_root=output_root,
            batch_name="batch-i",
            cohort_id="cohort-i",
            run_id="run-i",
            governed_run_id=_expected_governed_run_id(
                trade_dates=trade_dates,
                calendar_receipt=calendar_receipt,
                source_receipts=[source_receipt],
            ),
            evaluation_as_of_date=EVALUATION_AS_OF_DATE,
            frozen_version_tuple=_version_tuple(),
            date_evidence=_build_date_evidence(trade_dates=trade_dates, signal_day_count=20),
            created_at=NOW,
        )


def test_producer_rejects_parent_link_swap_before_zero_signal_write(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = _base_database(tmp_path)
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    output_root = tmp_path / "output"
    output_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("keep-me", encoding="utf-8")
    trade_dates = [
        (date(2026, 7, 1) + timedelta(days=index)).isoformat() for index in range(21)
    ]
    calendar_receipt = _calendar_receipt(trade_dates)
    source_receipt = _source_receipt()
    calendar_path = _write(trusted_root / "calendar.json", calendar_receipt)
    source_path = _write(trusted_root / "source.json", source_receipt)
    zero_signal_dir = output_root / "batch-toctou" / "zero-signal"

    path_type = type(zero_signal_dir)
    original_mkdir = path_type.mkdir
    original_is_symlink = path_type.is_symlink
    swapped = {"value": False}

    def fake_mkdir(self: Path, *args: object, **kwargs: object) -> None:
        original_mkdir(self, *args, **kwargs)
        if self == zero_signal_dir and not swapped["value"]:
            swapped["value"] = True

    def fake_is_symlink(self: Path) -> bool:
        if self == zero_signal_dir and swapped["value"]:
            return True
        return original_is_symlink(self)

    monkeypatch.setattr(path_type, "mkdir", fake_mkdir, raising=True)
    monkeypatch.setattr(path_type, "is_symlink", fake_is_symlink, raising=True)

    with pytest.raises(
        producer.CurrentRuleCohortError,
        match="output_path.parent contains forbidden symlink/junction component",
    ):
        producer.produce_stock_analysis_current_rule_cohort_bundle(
            duckdb_path=target,
            approved_calendar_receipt_path=calendar_path,
            source_availability_receipt_paths=[source_path],
            trusted_evidence_root=trusted_root,
            output_root=output_root,
            batch_name="batch-toctou",
            cohort_id="cohort-toctou",
            run_id="run-toctou",
            governed_run_id=_expected_governed_run_id(
                trade_dates=trade_dates,
                calendar_receipt=calendar_receipt,
                source_receipts=[source_receipt],
            ),
            evaluation_as_of_date=EVALUATION_AS_OF_DATE,
            frozen_version_tuple=_version_tuple(),
            date_evidence=_build_date_evidence(trade_dates=trade_dates, signal_day_count=20),
            created_at=NOW,
        )

    assert sentinel.read_text(encoding="utf-8") == "keep-me"
    assert not (outside / "2026-07-21.json").exists()


def test_producer_rejects_non_ready_date_evidence(
    tmp_path: Path,
) -> None:
    target = _base_database(tmp_path)
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    output_root = tmp_path / "output"
    output_root.mkdir()
    trade_dates = [
        (date(2026, 7, 1) + timedelta(days=index)).isoformat() for index in range(20)
    ]
    calendar_receipt = _calendar_receipt(trade_dates)
    source_receipt = _source_receipt()
    calendar_path = _write(trusted_root / "calendar.json", calendar_receipt)
    source_path = _write(trusted_root / "source.json", source_receipt)
    broken = _build_date_evidence(trade_dates=trade_dates, signal_day_count=20)
    broken[0]["status"] = "blocked"
    broken[0]["blockers"] = ["runner_blockers_present"]

    with pytest.raises(
        producer.CurrentRuleCohortError,
        match=r"date_evidence\[2026-07-01\]\.status must equal ready",
    ):
        producer.produce_stock_analysis_current_rule_cohort_bundle(
            duckdb_path=target,
            approved_calendar_receipt_path=calendar_path,
            source_availability_receipt_paths=[source_path],
            trusted_evidence_root=trusted_root,
            output_root=output_root,
            batch_name="batch-non-ready",
            cohort_id="cohort-non-ready",
            run_id="run-non-ready",
            governed_run_id=_expected_governed_run_id(
                trade_dates=trade_dates,
                calendar_receipt=calendar_receipt,
                source_receipts=[source_receipt],
            ),
            evaluation_as_of_date=EVALUATION_AS_OF_DATE,
            frozen_version_tuple=_version_tuple(),
            date_evidence=broken,
            created_at=NOW,
        )

    assert not (output_root / "batch-non-ready" / "bundle.json").exists()


def test_producer_rejects_temporary_link_swap_before_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    governed_root = tmp_path / "output"
    governed_root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    sentinel = outside / "sentinel.txt"
    sentinel.write_text("keep-me", encoding="utf-8")
    bundle_path = governed_root / "bundle.json"
    temporary_path = governed_root / ".bundle.json.fixed-temp.tmp"

    monkeypatch.setattr(producer.uuid, "uuid4", lambda: SimpleNamespace(hex="fixed-temp"))
    original_link = producer.os.link
    path_type = type(bundle_path)
    original_is_symlink = path_type.is_symlink
    swapped = {"value": False}

    def fake_link(src: os.PathLike[str] | str, dst: os.PathLike[str] | str) -> None:
        swapped["value"] = True
        original_link(src, dst)

    def fake_is_symlink(self: Path) -> bool:
        if self == temporary_path and swapped["value"]:
            return True
        return original_is_symlink(self)

    monkeypatch.setattr(producer.os, "link", fake_link)
    monkeypatch.setattr(path_type, "is_symlink", fake_is_symlink, raising=True)

    with pytest.raises(
        producer.CurrentRuleCohortError,
        match="output_path.temporary contains forbidden symlink/junction component",
    ):
        producer._write_new_or_identical_json(
            bundle_path,
            {"value": 1},
            governed_root=governed_root,
        )

    assert bundle_path.is_file()
    assert temporary_path.exists()
    assert sentinel.read_text(encoding="utf-8") == "keep-me"


def test_producer_rejects_ready_date_evidence_with_non_empty_blockers(
    tmp_path: Path,
) -> None:
    target = _base_database(tmp_path)
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    output_root = tmp_path / "output"
    output_root.mkdir()
    trade_dates = [
        (date(2026, 7, 1) + timedelta(days=index)).isoformat() for index in range(20)
    ]
    calendar_receipt = _calendar_receipt(trade_dates)
    source_receipt = _source_receipt()
    calendar_path = _write(trusted_root / "calendar.json", calendar_receipt)
    source_path = _write(trusted_root / "source.json", source_receipt)
    broken = _build_date_evidence(trade_dates=trade_dates, signal_day_count=20)
    broken[0]["blockers"] = ["selection_loader_error:ValueError:test"]

    with pytest.raises(
        producer.CurrentRuleCohortError,
        match=r"date_evidence\[2026-07-01\]\.blockers must be empty",
    ):
        producer.produce_stock_analysis_current_rule_cohort_bundle(
            duckdb_path=target,
            approved_calendar_receipt_path=calendar_path,
            source_availability_receipt_paths=[source_path],
            trusted_evidence_root=trusted_root,
            output_root=output_root,
            batch_name="batch-blocked",
            cohort_id="cohort-blocked",
            run_id="run-blocked",
            governed_run_id=_expected_governed_run_id(
                trade_dates=trade_dates,
                calendar_receipt=calendar_receipt,
                source_receipts=[source_receipt],
            ),
            evaluation_as_of_date=EVALUATION_AS_OF_DATE,
            frozen_version_tuple=_version_tuple(),
            date_evidence=broken,
            created_at=NOW,
        )

    assert not (output_root / "batch-blocked" / "bundle.json").exists()


@pytest.mark.parametrize(
    ("evidence", "message"),
    [
        (
            {"trade_date": "2026-07-01", "status": "ready"},
            r"date_evidence\[2026-07-01\]\.blockers must be an explicit array",
        ),
        (
            {"trade_date": "2026-07-01", "status": " ready ", "blockers": []},
            r"date_evidence\[2026-07-01\]\.status must equal ready",
        ),
    ],
)
def test_date_evidence_requires_exact_ready_contract(
    evidence: dict[str, object],
    message: str,
) -> None:
    with pytest.raises(producer.CurrentRuleCohortError, match=message):
        producer._normalize_date_evidence([evidence])


def test_producer_rejects_oversized_json_inputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    target = _base_database(tmp_path)
    trusted_root = tmp_path / "trusted"
    trusted_root.mkdir()
    output_root = tmp_path / "output"
    output_root.mkdir()
    trade_dates = [
        (date(2026, 7, 1) + timedelta(days=index)).isoformat() for index in range(20)
    ]
    calendar_receipt = _calendar_receipt(trade_dates)
    source_receipt = _source_receipt()
    calendar_path = _write(trusted_root / "calendar.json", calendar_receipt)
    source_path = trusted_root / "source.json"
    source_path.write_text(
        (" " * 4096)
        + json.dumps(
            source_receipt,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        producer,
        "MAX_JSON_INPUT_BYTES",
        calendar_path.stat().st_size + 128,
    )

    with pytest.raises(
        producer.CurrentRuleCohortError,
        match="source_availability_receipt_paths\\[0\\] exceeds max JSON input size",
    ):
        producer.produce_stock_analysis_current_rule_cohort_bundle(
            duckdb_path=target,
            approved_calendar_receipt_path=calendar_path,
            source_availability_receipt_paths=[source_path],
            trusted_evidence_root=trusted_root,
            output_root=output_root,
            batch_name="batch-j",
            cohort_id="cohort-j",
            run_id="run-j",
            governed_run_id=_expected_governed_run_id(
                trade_dates=trade_dates,
                calendar_receipt=calendar_receipt,
                source_receipts=[source_receipt],
            ),
            evaluation_as_of_date=EVALUATION_AS_OF_DATE,
            frozen_version_tuple=_version_tuple(),
            date_evidence=_build_date_evidence(trade_dates=trade_dates, signal_day_count=20),
            created_at=NOW,
        )
