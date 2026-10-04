from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

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
    stock_analysis_current_rule_factor_vendor_receipt as vendor_receipt_module,
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
from backend.app.tasks import stock_analysis_current_rule_factor_write as module

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]

EVALUATION = "2026-01-31"
MANIFEST_CREATED_AT = "2026-01-31T12:00:00Z"
VENDOR_CAPTURED_AT = "2026-08-24T00:00:00Z"
WRITE_EXECUTED_AT = "2026-08-24T01:23:45Z"
APPROVAL_REFERENCE = "授权写入这 53 条"
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


def _create_db(
    path: Path,
    *,
    duplicate_key: bool = False,
    invalid_factor: bool = False,
    blank_source: bool = False,
    extra_column: bool = False,
) -> None:
    extra = ", extra_note varchar" if extra_column else ""
    conn = duckdb.connect(str(path))
    try:
        conn.execute(
            f"""
            create table stock_adjustment_factor (
              stock_code varchar,
              trade_date varchar,
              adj_factor double,
              source_version varchar,
              run_id varchar
              {extra}
            )
            """
        )
        rows: list[tuple[object, ...]] = [
            ("000001.SZ", "2026-01-02", 1.0, "factor-source-v1", "factor-run-v1"),
            ("000001.SZ", "2026-01-03", 1.0, "factor-source-v1", "factor-run-v1"),
            ("000001.SZ", "2026-01-22", 1.0, "factor-source-v1", "factor-run-v1"),
        ]
        if duplicate_key:
            rows.append(
                ("000001.SZ", "2026-01-02", 1.0, "factor-source-v1", "factor-run-v1")
            )
        if invalid_factor:
            rows.append(
                ("600519.SH", "2026-01-06", 0.0, "factor-source-v1", "factor-run-v1")
            )
        if blank_source:
            rows.append(("600000.SH", "2026-01-06", 1.2, "", "factor-run-v1"))
        if extra_column:
            rows = [(*row, "x") for row in rows]
        conn.executemany(
            f"insert into stock_adjustment_factor values ({', '.join('?' for _ in rows[0])})",
            rows,
        )
    finally:
        conn.close()


def _build_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    duplicate_key: bool = False,
    invalid_factor: bool = False,
    blank_source: bool = False,
    extra_column: bool = False,
) -> dict[str, Any]:
    db_path = tmp_path / "moss.duckdb"
    _create_db(
        db_path,
        duplicate_key=duplicate_key,
        invalid_factor=invalid_factor,
        blank_source=False,
        extra_column=extra_column,
    )
    trusted_root = tmp_path / "evidence"
    trusted_root.mkdir()
    (db_path.parent / "backups").mkdir()

    source_receipt = build_stock_analysis_source_availability_receipt(
        duckdb_path=db_path,
        table_whitelist={"stock_adjustment_factor": "trade_date"},
        captured_at=MANIFEST_CREATED_AT,
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
        created_at=MANIFEST_CREATED_AT,
    )
    assert manifest["status"] == "gaps_found"
    manifest_path = trusted_root / "adjustment_factor_cell_manifest_reviewed.json"
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
    vendor_receipt = (
        vendor_receipt_module.build_stock_analysis_current_rule_factor_vendor_receipt(
            reviewed_factor_manifest=manifest,
            reviewed_factor_manifest_path=manifest_path,
            reviewed_factor_manifest_file_sha256=_file_sha256(manifest_path),
            returned_cells=returned_cells,
            captured_at=VENDOR_CAPTURED_AT,
            database_sha256_before=manifest["database"]["sha256_before"],
            database_sha256_after=manifest["database"]["sha256_before"],
        )
    )
    vendor_receipt_path = trusted_root / "adjustment_factor_vendor_dry_run_receipt.json"
    vendor_receipt_path.write_text(
        json.dumps(
            vendor_receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ),
        encoding="utf-8",
    )
    approved_scope_sha256 = module._approval_scope_sha256(
        manifest_canonical_sha256=manifest["canonical_manifest_sha256"],
        vendor_canonical_sha256=vendor_receipt["canonical_receipt_sha256"],
        database_sha256_before=manifest["database"]["sha256_before"],
        target_rows_sha256=vendor_receipt["returned_cells_sha256"],
        target_cell_count=vendor_receipt["returned_cell_count"],
    )
    if blank_source:
        conn = duckdb.connect(str(db_path))
        try:
            conn.execute(
                "insert into stock_adjustment_factor values ('600000.SH','2026-01-06',1.2,'','factor-run-v1')"
            )
        finally:
            conn.close()
    return {
        "db_path": db_path,
        "trusted_root": trusted_root,
        "manifest": manifest,
        "manifest_path": manifest_path,
        "vendor_receipt": vendor_receipt,
        "vendor_receipt_path": vendor_receipt_path,
        "approved_scope_sha256": approved_scope_sha256,
        "returned_cells": returned_cells,
        "backup_path": db_path.parent / "backups" / "factor-prewrite-backup.duckdb",
        "write_receipt_path": trusted_root / "adjustment_factor_write_receipt.json",
    }


@pytest.fixture
def context(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    return _build_context(monkeypatch, tmp_path)


def _write(context: dict[str, Any], **overrides: object) -> dict[str, Any]:
    arguments: dict[str, object] = {
        "duckdb_path": context["db_path"],
        "trusted_evidence_root": context["trusted_root"],
        "reviewed_factor_manifest_file": context["manifest_path"],
        "vendor_receipt_file": context["vendor_receipt_path"],
        "target_backup_file": context["backup_path"],
        "write_receipt_file": context["write_receipt_path"],
        "executed_at": WRITE_EXECUTED_AT,
        "approval_reference": APPROVAL_REFERENCE,
        "expected_approved_scope_sha256": context["approved_scope_sha256"],
        "allow_write": True,
    }
    arguments.update(overrides)
    return module.write_stock_analysis_current_rule_factor_cells(**arguments)


def test_success_writes_exact_rows_backup_and_receipt(context: dict[str, Any]) -> None:
    before = _file_sha256(context["db_path"])

    receipt = _write(context)

    assert receipt["receipt_kind"] == module.WRITE_RECEIPT_KIND
    assert receipt["status"] == module.COMPLETED_STATUS
    assert receipt["database_write_executed"] is True
    assert receipt["downstream_materialization_executed"] is False
    assert receipt["touched_tables"] == ["stock_adjustment_factor"]
    assert receipt["approval_reference"] == APPROVAL_REFERENCE
    assert receipt["approval_scope_sha256"] == context["approved_scope_sha256"]
    assert receipt["database"]["sha256_before"] == before
    assert receipt["database"]["sha256_after"] != before
    assert receipt["backup"]["sha256"] == before
    assert Path(receipt["backup"]["path"]).is_file()
    assert context["write_receipt_path"].is_file()
    valid, errors = module.validate_stock_analysis_current_rule_factor_write_receipt(
        receipt,
        reviewed_factor_manifest=context["manifest"],
        vendor_receipt=context["vendor_receipt"],
    )
    assert valid, errors

    conn = duckdb.connect(str(context["db_path"]), read_only=True)
    try:
        rows = conn.execute(
            """
            select stock_code, trade_date, adj_factor, source_version, run_id
            from stock_adjustment_factor
            where trade_date in ('2026-01-07', '2026-01-12')
            order by trade_date, stock_code
            """
        ).fetchall()
    finally:
        conn.close()
    assert rows == [
        (
            "000001.SZ",
            "2026-01-07",
            1.07,
            context["vendor_receipt"]["proposed_source_version"],
            context["vendor_receipt"]["proposed_run_id"],
        ),
        (
            "000001.SZ",
            "2026-01-12",
            1.12,
            context["vendor_receipt"]["proposed_source_version"],
            context["vendor_receipt"]["proposed_run_id"],
        ),
    ]


def test_write_requires_explicit_allow_switch(context: dict[str, Any]) -> None:
    with pytest.raises(
        module.CurrentRuleFactorWriteError, match="allow_write must be explicitly true"
    ):
        _write(context, allow_write=False)


def test_write_requires_exact_preapproved_scope_hash(context: dict[str, Any]) -> None:
    before = _file_sha256(context["db_path"])

    with pytest.raises(
        module.CurrentRuleFactorWriteError,
        match="expected_approved_scope_sha256 does not match",
    ):
        _write(context, expected_approved_scope_sha256="F" * 64)

    assert _file_sha256(context["db_path"]) == before
    assert not context["backup_path"].exists()
    assert not context["write_receipt_path"].exists()


def test_receipt_tamper_is_detected_after_success(context: dict[str, Any]) -> None:
    receipt = _write(context)
    tampered = copy.deepcopy(receipt)
    tampered["source_version"] = "other"
    tampered["canonical_write_receipt_sha256"] = module._receipt_sha256(tampered)

    valid, errors = module.validate_stock_analysis_current_rule_factor_write_receipt(
        tampered,
        reviewed_factor_manifest=context["manifest"],
        vendor_receipt=context["vendor_receipt"],
    )

    assert valid is False
    assert any("source_version must match vendor receipt" in error for error in errors)


def test_validator_requires_manifest_and_vendor_together(
    context: dict[str, Any],
) -> None:
    receipt = _write(context)

    valid, errors = module.validate_stock_analysis_current_rule_factor_write_receipt(
        receipt,
        vendor_receipt=context["vendor_receipt"],
    )

    assert valid is False
    assert (
        "reviewed_factor_manifest and vendor_receipt must be supplied together"
        in errors
    )


def test_vendor_receipt_tamper_blocks_before_write(context: dict[str, Any]) -> None:
    tampered = copy.deepcopy(context["vendor_receipt"])
    tampered["returned_cells"][0]["adj_factor"] = 9.9
    context["vendor_receipt_path"].write_text(
        json.dumps(tampered, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )

    with pytest.raises(
        module.CurrentRuleFactorWriteError,
        match="vendor_receipt failed formal validation",
    ):
        _write(context)


def test_database_drift_blocks_when_sha_no_longer_matches_receipts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _build_context(monkeypatch, tmp_path)
    conn = duckdb.connect(str(context["db_path"]))
    try:
        conn.execute(
            "insert into stock_adjustment_factor values ('600519.SH','2026-01-09',1.3,'factor-source-v1','factor-run-v1')"
        )
    finally:
        conn.close()

    with pytest.raises(
        module.CurrentRuleFactorWriteError,
        match="reviewed manifest database SHA does not match current DuckDB",
    ):
        _write(context)


def test_existing_target_cell_blocks_without_overwrite(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _build_context(monkeypatch, tmp_path)
    original_db_sha = _file_sha256(context["db_path"])
    conn = duckdb.connect(str(context["db_path"]))
    try:
        conn.execute(
            "insert into stock_adjustment_factor values ('000001.SZ','2026-01-07',1.07,'manual-source','manual-run')"
        )
    finally:
        conn.close()
    real_file_sha = module._file_sha256

    def fake_file_sha(path: Path) -> str:
        if Path(path) == context["db_path"]:
            return original_db_sha
        return real_file_sha(path)

    monkeypatch.setattr(module, "_file_sha256", fake_file_sha)
    with pytest.raises(
        module.CurrentRuleFactorWriteError, match="target factor cells already exist"
    ):
        _write(context)


@pytest.mark.parametrize(
    ("kwargs", "expected_error"),
    [
        ({"duplicate_key": True}, "duplicate natural keys"),
        ({"invalid_factor": True}, "nonpositive or nonfinite factors"),
        ({"extra_column": True}, "exact five-column governed shape"),
    ],
)
def test_global_table_quality_and_schema_drift_block_write(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    kwargs: dict[str, bool],
    expected_error: str,
) -> None:
    context = _build_context(monkeypatch, tmp_path, **kwargs)

    with pytest.raises(module.CurrentRuleFactorWriteError, match=expected_error):
        _write(context)


def test_blank_required_fields_block_write_after_receipt_binding(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _build_context(monkeypatch, tmp_path)
    original_db_sha = _file_sha256(context["db_path"])
    conn = duckdb.connect(str(context["db_path"]))
    try:
        conn.execute(
            "insert into stock_adjustment_factor values ('600000.SH','2026-01-06',1.2,'','factor-run-v1')"
        )
    finally:
        conn.close()
    real_file_sha = module._file_sha256

    def fake_file_sha(path: Path) -> str:
        if Path(path) == context["db_path"]:
            return original_db_sha
        return real_file_sha(path)

    monkeypatch.setattr(module, "_file_sha256", fake_file_sha)

    with pytest.raises(
        module.CurrentRuleFactorWriteError, match="blank required fields"
    ):
        _write(context)


def test_transaction_failure_rolls_back_inserted_targets(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _build_context(monkeypatch, tmp_path)
    before = _file_sha256(context["db_path"])

    def fail_after_insert(*args: object, **kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(module, "_verify_transaction_postconditions", fail_after_insert)

    with pytest.raises(RuntimeError, match="boom"):
        _write(context)

    conn = duckdb.connect(str(context["db_path"]), read_only=True)
    try:
        count = conn.execute(
            """
            select count(*)
            from stock_adjustment_factor
            where trade_date in ('2026-01-07', '2026-01-12')
            """
        ).fetchone()[0]
    finally:
        conn.close()
    assert count == 0
    assert _file_sha256(context["db_path"]) == before
    pending = json.loads(context["write_receipt_path"].read_text(encoding="utf-8"))
    assert pending["receipt_kind"] == module.PENDING_INTENT_KIND
    assert pending["status"] == module.PENDING_STATUS
    assert pending["database_write_executed"] is None
    assert pending["completion_attested"] is False
    assert pending["approval_scope_sha256"] == context["approved_scope_sha256"]
    assert pending["canonical_pending_intent_sha256"] == module._pending_intent_sha256(
        pending
    )


@pytest.mark.parametrize("sidecar_suffix", [".wal", ".wal.incomplete"])
def test_unmerged_duckdb_sidecar_blocks_before_backup_or_write(
    context: dict[str, Any],
    sidecar_suffix: str,
) -> None:
    before = _file_sha256(context["db_path"])
    sidecar = Path(f"{context['db_path']}{sidecar_suffix}")
    sidecar.write_bytes(b"unmerged")

    with pytest.raises(
        module.CurrentRuleFactorWriteError,
        match="unmerged DuckDB WAL/sidecar",
    ):
        _write(context)

    assert _file_sha256(context["db_path"]) == before
    assert sidecar.read_bytes() == b"unmerged"
    assert not context["backup_path"].exists()
    assert not context["write_receipt_path"].exists()


def test_final_receipt_replace_failure_preserves_pending_intent_after_commit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _build_context(monkeypatch, tmp_path)

    def fail_replace(source: object, destination: object) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(module.os, "replace", fail_replace)

    with pytest.raises(OSError, match="replace failed"):
        _write(context)

    conn = duckdb.connect(str(context["db_path"]), read_only=True)
    try:
        rows = conn.execute(
            """
            select stock_code, trade_date, source_version, run_id
            from stock_adjustment_factor
            where trade_date in ('2026-01-07', '2026-01-12')
            order by trade_date, stock_code
            """
        ).fetchall()
    finally:
        conn.close()
    assert rows == [
        (
            "000001.SZ",
            "2026-01-07",
            context["vendor_receipt"]["proposed_source_version"],
            context["vendor_receipt"]["proposed_run_id"],
        ),
        (
            "000001.SZ",
            "2026-01-12",
            context["vendor_receipt"]["proposed_source_version"],
            context["vendor_receipt"]["proposed_run_id"],
        ),
    ]
    pending = json.loads(context["write_receipt_path"].read_text(encoding="utf-8"))
    assert pending["receipt_kind"] == module.PENDING_INTENT_KIND
    assert pending["status"] == module.PENDING_STATUS
    assert pending["completion_attested"] is False
    assert pending["database_write_executed"] is None
    assert pending["approval_scope_sha256"] == context["approved_scope_sha256"]
    assert (
        pending["target_rows_sha256"]
        == context["vendor_receipt"]["returned_cells_sha256"]
    )
    assert pending["canonical_pending_intent_sha256"] == module._pending_intent_sha256(
        pending
    )
    assert not list(context["trusted_root"].glob("*.completed.tmp"))


def test_backup_path_escape_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _build_context(monkeypatch, tmp_path)
    outside_backup = tmp_path / "outside.duckdb"
    with pytest.raises(
        module.CurrentRuleFactorWriteError, match="<duckdb parent>/backups"
    ):
        _write(context, target_backup_file=outside_backup)


def test_existing_write_receipt_is_rejected_without_overwrite(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _build_context(monkeypatch, tmp_path)
    context["write_receipt_path"].write_text("keep", encoding="utf-8")
    with pytest.raises(module.CurrentRuleFactorWriteError, match="must be new"):
        _write(context)
    assert context["write_receipt_path"].read_text(encoding="utf-8") == "keep"


def test_symlinked_write_receipt_parent_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _build_context(monkeypatch, tmp_path)
    outside = tmp_path / "outside"
    outside.mkdir()
    linked = context["trusted_root"] / "linked"
    try:
        linked.symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is unavailable")
    with pytest.raises(
        module.CurrentRuleFactorWriteError, match="forbidden symlink/junction"
    ):
        _write(context, write_receipt_file=linked / "receipt.json")


def test_noncanonical_key_row_blocks_write_after_receipt_binding(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    context = _build_context(monkeypatch, tmp_path)
    original_db_sha = _file_sha256(context["db_path"])
    conn = duckdb.connect(str(context["db_path"]))
    try:
        conn.execute(
            "insert into stock_adjustment_factor values (' 600000.sz ','2026-01-06 ',1.2,'factor-source-v1','factor-run-v1')"
        )
    finally:
        conn.close()
    real_file_sha = module._file_sha256

    def fake_file_sha(path: Path) -> str:
        if Path(path) == context["db_path"]:
            return original_db_sha
        return real_file_sha(path)

    monkeypatch.setattr(module, "_file_sha256", fake_file_sha)

    with pytest.raises(
        module.CurrentRuleFactorWriteError,
        match="noncanonical stock_code or trade_date keys",
    ):
        _write(context)


def test_existing_backup_file_is_not_overwritten(context: dict[str, Any]) -> None:
    context["backup_path"].write_text("do-not-touch", encoding="utf-8")

    with pytest.raises(
        module.CurrentRuleFactorWriteError, match="target_backup_file must be new"
    ):
        _write(context)

    assert context["backup_path"].read_text(encoding="utf-8") == "do-not-touch"
