from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

import duckdb
import pytest

from backend.app.core_finance.livermore_stock_candidates import (
    EXP3B_STOCK_CANDIDATE_POLICY,
)
from backend.app.core_finance.livermore_stock_candidates import (
    FORMULA_VERSION as STOCK_CANDIDATE_FORMULA_VERSION,
)
from backend.app.core_finance.matched_baseline import (
    FORMULA_VERSION as MATCHED_BASELINE_FORMULA_VERSION,
)
from backend.app.governance import (
    stock_analysis_current_rule_factor_vendor_receipt as module,
)
from backend.app.governance import (
    stock_analysis_current_rule_version_tuple as version_module,
)
from backend.app.governance.stock_analysis_current_rule_certificate import (
    ALLOWED_DECISION_METRIC_BASIS,
    CURRENT_RULE_COVERAGE_AUTHORITY_MODE,
)
from backend.app.governance.stock_analysis_source_availability_receipt import (
    build_stock_analysis_source_availability_receipt,
)
from backend.app.services.livermore_signal_confluence_service import (
    LIVERMORE_SIGNAL_CONFLUENCE_RULE_VERSION,
)
from backend.app.tasks import livermore_candidate_history_materialize as execution_task
from backend.app.tasks import (
    stock_analysis_current_rule_factor_manifest as manifest_module,
)

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]

EVALUATION = "2026-01-31"
CAPTURED_AT = "2026-08-24T00:00:00Z"
SOURCE_VERSION = "factor-source-v1"
RUN_ID = "factor-run-v1"
SHA_A = "A" * 64
SHA_B = "B" * 64


def _version_tuple() -> dict[str, object]:
    return {
        "candidate_rule_version": execution_task.RULE_VERSION,
        "stock_candidate_selection_formula_version": STOCK_CANDIDATE_FORMULA_VERSION,
        "candidate_outcome_formula_version": execution_task.FORMULA_VERSION,
        "execution_formula_version": execution_task.EXECUTION_FORMULA_VERSION,
        "matched_baseline_formula_version": MATCHED_BASELINE_FORMULA_VERSION,
        "market_gate_rule_version": version_module._market_gate_contract_fingerprint(),
        "signal_confluence_rule_version": LIVERMORE_SIGNAL_CONFLUENCE_RULE_VERSION,
        "macro_formula_version": version_module._macro_formula_contract_fingerprint(),
        "candidate_source_version": "1" * 64,
        "execution_source_version": "2" * 64,
        "matched_baseline_source_version": "3" * 64,
        "macro_source_version": "4" * 64,
        "theme_overlay_fingerprint": "5" * 64,
        "choice_catalog_fingerprint": "6" * 64,
        "stock_candidate_selection_policy": EXP3B_STOCK_CANDIDATE_POLICY,
        "decision_metric_basis": ALLOWED_DECISION_METRIC_BASIS,
        "coverage_authority_mode": CURRENT_RULE_COVERAGE_AUTHORITY_MODE,
        "strict_coverage": True,
        "fallback_covered": False,
    }


def _runner() -> dict[str, object]:
    return {
        "trade_date": "2026-01-02",
        "status": manifest_module.SIGNAL_STATUS,
        "status_reason": "current_rule_candidates_present",
        "requested_as_of_date": "2026-01-02",
        "resolved_as_of_date": "2026-01-02",
        "requested_matches_resolved": True,
        "selection_policy": EXP3B_STOCK_CANDIDATE_POLICY,
        "stock_candidate_formula_version": STOCK_CANDIDATE_FORMULA_VERSION,
        "rule_tuple_matches": True,
        "accepted_candidate_count": 1,
        "accepted_candidate_codes": ["000001.SZ"],
        "future_business_date_violations": [],
        "future_availability_violations": [],
        "blockers": [],
    }


def _execution() -> dict[str, object]:
    return {
        "entry_date": "2026-01-03",
        "exit_date_1d": "2026-01-03",
        "exit_date_5d": "2026-01-07",
        "exit_date_10d": "2026-01-12",
        "exit_date_20d": "2026-01-22",
        "data_status": "complete",
    }


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


@pytest.fixture
def receipt_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> dict[str, object]:
    db_path = tmp_path / "factor-vendor-receipt.duckdb"
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            create table stock_adjustment_factor (
              stock_code varchar,
              trade_date varchar,
              adj_factor double,
              source_version varchar,
              vendor_version varchar,
              rule_version varchar,
              run_id varchar
            )
            """
        )
        conn.executemany(
            "insert into stock_adjustment_factor values (?, ?, ?, ?, ?, ?, ?)",
            [
                ("000001.SZ", day, 1.0, SOURCE_VERSION, "", "", RUN_ID)
                for day in ("2026-01-02", "2026-01-03", "2026-01-22")
            ],
        )
    finally:
        conn.close()
    source_receipt = build_stock_analysis_source_availability_receipt(
        duckdb_path=db_path,
        table_whitelist={"stock_adjustment_factor": "trade_date"},
        captured_at="2026-01-31T12:00:00Z",
    )
    monkeypatch.setattr(
        manifest_module.execution_task,
        "_execution_returns_for_candidate",
        lambda conn, *, stock_code, snapshot_as_of_date: _execution(),
    )
    manifest = manifest_module.build_stock_analysis_current_rule_factor_manifest(
        duckdb_path=db_path,
        evaluation_as_of_date=EVALUATION,
        governed_run_id="governed-run-1",
        runner_results=[_runner()],
        source_availability_receipts=[source_receipt],
        frozen_version_tuple=_version_tuple(),
        calendar_receipt_sha256=SHA_A,
        replay_plan_digest_version="stock-analysis-current-rule-replay-plan-v1",
        replay_plan_digest=SHA_B,
        created_at="2026-01-31T12:00:00Z",
    )
    assert manifest["status"] == "gaps_found"
    assert manifest["summary"]["missing_unique_cell_count"] == 2
    manifest_path = tmp_path / "adjustment_factor_cell_manifest_reviewed.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )
    returned_cells = [
        {
            "requested_trade_date": "2026-01-12",
            "stock_code": "000001.SZ",
            "trade_date": "2026-01-12",
            "adj_factor": 1.12,
        },
        {
            "requested_trade_date": "2026-01-07",
            "stock_code": "000001.SZ",
            "trade_date": "2026-01-07",
            "adj_factor": 1.07,
        },
    ]
    return {
        "db_path": db_path,
        "database_sha256": manifest["database"]["sha256_before"],
        "manifest": manifest,
        "manifest_path": manifest_path,
        "manifest_file_sha256": _file_sha256(manifest_path),
        "returned_cells": returned_cells,
    }


def _build(context: dict[str, object], **overrides: object) -> dict[str, object]:
    arguments: dict[str, object] = {
        "reviewed_factor_manifest": context["manifest"],
        "reviewed_factor_manifest_path": context["manifest_path"],
        "reviewed_factor_manifest_file_sha256": context["manifest_file_sha256"],
        "returned_cells": context["returned_cells"],
        "captured_at": CAPTURED_AT,
        "database_sha256_before": context["database_sha256"],
        "database_sha256_after": context["database_sha256"],
    }
    arguments.update(overrides)
    return module.build_stock_analysis_current_rule_factor_vendor_receipt(**arguments)


def _validate(
    receipt: dict[str, object],
    context: dict[str, object],
) -> tuple[bool, tuple[str, ...]]:
    return module.validate_stock_analysis_current_rule_factor_vendor_receipt(
        receipt,
        reviewed_factor_manifest=context["manifest"],
        reviewed_factor_manifest_path=context["manifest_path"],
        reviewed_factor_manifest_file_sha256=context["manifest_file_sha256"],
    )


def test_builds_exact_read_only_receipt_with_stable_hashes_and_bindings(
    receipt_context: dict[str, object],
) -> None:
    receipt = _build(receipt_context)

    assert receipt["schema_version"] == module.SCHEMA_VERSION
    assert receipt["receipt_kind"] == module.RECEIPT_KIND
    assert receipt["status"] == module.READY_STATUS
    assert receipt["vendor_endpoint"] == "tushare.pro.adj_factor"
    assert receipt["vendor_version"] is None
    assert receipt["vendor_version_status"] == "not_provided"
    assert receipt["requested_cells_source"].endswith("missing_unique_cells")
    assert receipt["vendor_call_count"] == 2
    assert receipt["database_write_executed"] is False
    assert receipt["write_allowed"] is False
    assert receipt["formal_use_allowed"] is False
    assert receipt["remediation_only"] is True
    assert receipt["strict_exact_cells"] is True
    assert [row["trade_date"] for row in receipt["returned_cells"]] == [
        "2026-01-07",
        "2026-01-12",
    ]
    assert (
        receipt["manifest_binding"]["canonical_manifest_sha256"]
        == (receipt_context["manifest"]["canonical_manifest_sha256"])
    )
    assert receipt["database"]["sha256_before"] == receipt_context["database_sha256"]
    valid, errors = _validate(receipt, receipt_context)
    assert valid, errors

    second = _build(
        receipt_context,
        returned_cells=list(reversed(receipt_context["returned_cells"])),
    )
    assert second["canonical_receipt_sha256"] == receipt["canonical_receipt_sha256"]
    assert second["proposed_source_version"] == receipt["proposed_source_version"]
    assert second["proposed_run_id"] == receipt["proposed_run_id"]


def test_builder_rejects_formally_invalid_reviewed_manifest(
    receipt_context: dict[str, object],
) -> None:
    manifest = copy.deepcopy(receipt_context["manifest"])
    manifest["missing_unique_cells"][0]["trade_date"] = "2026-01-08"

    with pytest.raises(ValueError, match="failed formal validation"):
        _build(receipt_context, reviewed_factor_manifest=manifest)


def test_builder_rejects_missing_returned_cell(
    receipt_context: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="missing=1"):
        _build(
            receipt_context,
            returned_cells=receipt_context["returned_cells"][:1],
        )


def test_builder_rejects_extra_returned_cell(
    receipt_context: dict[str, object],
) -> None:
    extra = {
        "requested_trade_date": "2026-01-08",
        "stock_code": "000001.SZ",
        "trade_date": "2026-01-08",
        "adj_factor": 1.08,
    }
    with pytest.raises(ValueError, match="extra=1"):
        _build(
            receipt_context,
            returned_cells=[*receipt_context["returned_cells"], extra],
        )


def test_builder_rejects_duplicate_natural_key_even_when_values_match(
    receipt_context: dict[str, object],
) -> None:
    duplicate = copy.deepcopy(receipt_context["returned_cells"][0])
    with pytest.raises(ValueError, match="duplicate natural keys"):
        _build(
            receipt_context,
            returned_cells=[*receipt_context["returned_cells"], duplicate],
        )


@pytest.mark.parametrize(
    "invalid_factor", [0, -1, float("nan"), float("inf"), True, "x"]
)
def test_builder_rejects_nonpositive_or_nonfinite_factor(
    receipt_context: dict[str, object],
    invalid_factor: object,
) -> None:
    returned = copy.deepcopy(receipt_context["returned_cells"])
    returned[0]["adj_factor"] = invalid_factor

    with pytest.raises(ValueError, match="positive finite number"):
        _build(receipt_context, returned_cells=returned)


def test_builder_rejects_wrong_or_non_iso_returned_date(
    receipt_context: dict[str, object],
) -> None:
    wrong_date = copy.deepcopy(receipt_context["returned_cells"])
    wrong_date[0]["trade_date"] = "2026-01-11"
    with pytest.raises(ValueError, match="must equal requested_trade_date"):
        _build(receipt_context, returned_cells=wrong_date)

    non_iso = copy.deepcopy(receipt_context["returned_cells"])
    non_iso[0]["trade_date"] = "20260112"
    non_iso[0]["requested_trade_date"] = "20260112"
    with pytest.raises(ValueError, match="ISO date"):
        _build(receipt_context, returned_cells=non_iso)


def test_builder_rejects_database_drift_and_manifest_sha_mismatch(
    receipt_context: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="changed during vendor dry run"):
        _build(receipt_context, database_sha256_after="C" * 64)
    with pytest.raises(ValueError, match="does not match reviewed manifest"):
        _build(
            receipt_context,
            database_sha256_before="C" * 64,
            database_sha256_after="C" * 64,
        )


def test_validator_recomputes_rows_counts_hashes_and_proposed_ids_after_reseal(
    receipt_context: dict[str, object],
) -> None:
    receipt = _build(receipt_context)
    tampered = copy.deepcopy(receipt)
    tampered["returned_cells"][0]["adj_factor"] = 9.9
    tampered["canonical_receipt_sha256"] = module._receipt_sha256(tampered)

    valid, errors = _validate(tampered, receipt_context)

    assert valid is False
    assert "receipt.returned_cells_sha256 mismatch" in errors
    assert "receipt.proposed_source_version mismatch" in errors
    assert "receipt.proposed_run_id mismatch" in errors


def test_validator_fails_closed_on_nonfinite_tamper_and_boolean_count(
    receipt_context: dict[str, object],
) -> None:
    receipt = _build(receipt_context)
    tampered = copy.deepcopy(receipt)
    tampered["returned_cells"][0]["adj_factor"] = float("nan")
    tampered["requested_cell_count"] = True

    valid, errors = _validate(tampered, receipt_context)

    assert valid is False
    assert any("positive finite number" in error for error in errors)
    assert "receipt.requested_cell_count mismatch" in errors
    assert any("canonical JSON" in error for error in errors)


def test_validator_rejects_internally_resealed_request_not_from_manifest(
    receipt_context: dict[str, object],
) -> None:
    receipt = _build(receipt_context)
    tampered = copy.deepcopy(receipt)
    tampered["requested_cells"] = tampered["requested_cells"][:1]
    tampered["returned_cells"] = tampered["returned_cells"][:1]
    tampered["requested_cell_count"] = 1
    tampered["returned_cell_count"] = 1
    tampered["requested_unique_date_count"] = 1
    tampered["vendor_call_count"] = 1
    tampered["manifest_binding"]["missing_unique_cell_count"] = 1
    tampered["requested_cells_sha256"] = module._canonical_json_sha256(
        tampered["requested_cells"]
    )
    tampered["returned_cells_sha256"] = module._canonical_json_sha256(
        tampered["returned_cells"]
    )
    tampered["proposed_source_version"] = module._proposed_source_version(
        requested_cells_sha256=tampered["requested_cells_sha256"],
        returned_cells_sha256=tampered["returned_cells_sha256"],
    )
    tampered["proposed_run_id"] = module._proposed_run_id(
        manifest_sha256=tampered["manifest_binding"]["canonical_manifest_sha256"],
        requested_cells_sha256=tampered["requested_cells_sha256"],
        returned_cells_sha256=tampered["returned_cells_sha256"],
        captured_at=tampered["captured_at"],
        database_sha256=tampered["database"]["sha256_before"],
    )
    tampered["canonical_receipt_sha256"] = module._receipt_sha256(tampered)

    internal_valid, internal_errors = (
        module.validate_stock_analysis_current_rule_factor_vendor_receipt(tampered)
    )
    assert internal_valid, internal_errors
    external_valid, external_errors = _validate(tampered, receipt_context)
    assert external_valid is False
    assert any("do not match reviewed manifest" in error for error in external_errors)


@pytest.mark.parametrize(
    ("field_name", "value", "expected_error"),
    [
        ("canonical_manifest_sha256", "C" * 64, "canonical_manifest_sha256"),
        ("governed_run_id", "other-run", "governed_run_id"),
        ("database_sha256", "C" * 64, "manifest/database SHA binding"),
    ],
)
def test_validator_rejects_resealed_manifest_and_database_binding_tamper(
    receipt_context: dict[str, object],
    field_name: str,
    value: str,
    expected_error: str,
) -> None:
    receipt = _build(receipt_context)
    tampered = copy.deepcopy(receipt)
    tampered["manifest_binding"][field_name] = value
    tampered["canonical_receipt_sha256"] = module._receipt_sha256(tampered)

    valid, errors = _validate(tampered, receipt_context)

    assert valid is False
    assert any(expected_error in error for error in errors)


def test_validator_rejects_resealed_manifest_file_path_or_sha_tamper(
    receipt_context: dict[str, object],
    tmp_path: Path,
) -> None:
    receipt = _build(receipt_context)
    wrong_path = copy.deepcopy(receipt)
    wrong_path["manifest_binding"]["path"] = str(tmp_path / "other.json")
    wrong_path["canonical_receipt_sha256"] = module._receipt_sha256(wrong_path)
    valid, errors = _validate(wrong_path, receipt_context)
    assert valid is False
    assert any("manifest path" in error for error in errors)

    wrong_sha = copy.deepcopy(receipt)
    wrong_sha["manifest_binding"]["file_sha256"] = "C" * 64
    wrong_sha["canonical_receipt_sha256"] = module._receipt_sha256(wrong_sha)
    valid, errors = _validate(wrong_sha, receipt_context)
    assert valid is False
    assert any("manifest file" in error for error in errors)


def test_validator_rejects_authorization_or_capture_semantics_tamper(
    receipt_context: dict[str, object],
) -> None:
    receipt = _build(receipt_context)
    tampered = copy.deepcopy(receipt)
    tampered["write_allowed"] = True
    tampered["formal_use_allowed"] = True
    tampered["database_write_executed"] = True
    tampered["vendor_version"] = "unknown"
    tampered["availability_attestation"]["historical_availability_inferred"] = True
    tampered["canonical_receipt_sha256"] = module._receipt_sha256(tampered)

    valid, errors = _validate(tampered, receipt_context)

    assert valid is False
    assert any("write_allowed must be false" in error for error in errors)
    assert any("formal_use_allowed must be false" in error for error in errors)
    assert any("database_write_executed must be false" in error for error in errors)
    assert "receipt.vendor_version must be null" in errors
    assert any("historical_availability_inferred" in error for error in errors)
