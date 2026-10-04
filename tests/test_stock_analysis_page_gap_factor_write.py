from __future__ import annotations

import copy
import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import duckdb
import pytest

from backend.app.governance import (
    stock_analysis_current_rule_factor_vendor_receipt as exact_receipt_helpers,
)
from backend.app.governance import (
    stock_analysis_page_gap_factor_vendor_receipt as vendor_task,
)
from backend.app.tasks import stock_analysis_page_gap_factor_write as module

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]


def _file_sha(path: Path) -> str:
    return module._write_helpers._file_sha256(path)


def _create_db(path: Path, *, invalid_existing: bool = False) -> None:
    with duckdb.connect(str(path)) as conn:
        conn.execute(
            """
            create table stock_adjustment_factor (
              stock_code varchar,
              trade_date varchar,
              adj_factor double,
              source_version varchar,
              run_id varchar
            )
            """
        )
        conn.execute(
            "insert into stock_adjustment_factor values (?, ?, ?, ?, ?)",
            [
                "600519.SH",
                "2026-01-02",
                0.0 if invalid_existing else 1.0,
                "existing-source",
                "existing-run",
            ],
        )


def _build_context(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    invalid_existing: bool = False,
) -> dict[str, Any]:
    db_path = tmp_path / "moss.duckdb"
    _create_db(db_path, invalid_existing=invalid_existing)
    (tmp_path / "backups").mkdir()
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    db_sha = _file_sha(db_path)
    target_cells = [
        {"stock_code": "000001.SZ", "trade_date": "2026-01-05"},
        {"stock_code": "600000.SH", "trade_date": "2026-01-06"},
    ]
    page = {
        "manifest_kind": "stock_analysis_page_gap_manifest_v1",
        "status": "gaps_found",
        "blockers": [],
        "canonical_manifest_sha256": "A" * 64,
        "page_id": "GAP-STOCK-ANALYSIS-PAGE",
        "page_route": "/stock-analysis",
        "page_metric_key": "data_health.adjustment_factor_gap",
        "summary": {
            "page_gap_view_count_before": 3,
            "unique_missing_factor_cell_count": 2,
        },
        "database": {
            "path": str(db_path.resolve()),
            "sha256_before": db_sha,
            "sha256_after": db_sha,
            "unchanged": True,
            "read_only": True,
        },
        "missing_factor_cells": target_cells,
    }
    page_path = evidence / "page.json"
    page_path.write_text(json.dumps(page), encoding="utf-8")
    target_sha = exact_receipt_helpers._canonical_json_sha256(target_cells)
    factor_manifest = {
        "manifest_kind": "stock_analysis_page_gap_factor_manifest_v1",
        "status": "gaps_found",
        "remediation_only": True,
        "strict_exact_date_lookup": True,
        "carry_forward_allowed": False,
        "fallback_allowed": False,
        "write_allowed": False,
        "historical_availability_proven": False,
        "certification_allowed": False,
        "downstream_materialization_allowed": False,
        "blockers": [],
        "target_cells": target_cells,
        "target_cell_count": 2,
        "target_cells_sha256": target_sha,
        "requested_unique_date_count": 2,
        "canonical_manifest_sha256": "B" * 64,
        "database": dict(page["database"]),
        "page_manifest_binding": {
            "path": str(page_path.resolve()),
            "file_sha256": _file_sha(page_path),
            "canonical_manifest_sha256": "A" * 64,
            "manifest_kind": "stock_analysis_page_gap_manifest_v1",
            "page_id": "GAP-STOCK-ANALYSIS-PAGE",
            "page_route": "/stock-analysis",
            "page_metric_key": "data_health.adjustment_factor_gap",
            "database_path": str(db_path.resolve()),
            "database_sha256": db_sha,
            "page_gap_view_count": 3,
            "missing_factor_cell_count": 2,
        },
    }
    factor_path = evidence / "factor.json"
    factor_path.write_text(json.dumps(factor_manifest), encoding="utf-8")
    monkeypatch.setattr(
        module.factor_manifest_task,
        "validate_stock_analysis_page_gap_factor_manifest",
        lambda manifest: (True, ()),
    )
    monkeypatch.setattr(
        vendor_task.factor_manifest_task,
        "validate_stock_analysis_page_gap_factor_manifest",
        lambda manifest: (True, ()),
    )
    monkeypatch.setattr(
        module.page_manifest_task,
        "validate_stock_analysis_page_gap_manifest",
        lambda manifest: (True, ()),
    )
    returned_cells = [
        {
            "requested_trade_date": "2026-01-05",
            "stock_code": "000001.SZ",
            "trade_date": "2026-01-05",
            "adj_factor": 1.05,
        },
        {
            "requested_trade_date": "2026-01-06",
            "stock_code": "600000.SH",
            "trade_date": "2026-01-06",
            "adj_factor": 2.06,
        },
    ]
    vendor_receipt = vendor_task.build_stock_analysis_page_gap_factor_vendor_receipt(
        reviewed_factor_manifest=factor_manifest,
        reviewed_factor_manifest_path=factor_path,
        reviewed_factor_manifest_file_sha256=_file_sha(factor_path),
        returned_cells=returned_cells,
        captured_at="2026-08-24T10:00:00Z",
        database_sha256_before=db_sha,
        database_sha256_after=db_sha,
    )
    vendor_path = evidence / "vendor.json"
    vendor_path.write_text(json.dumps(vendor_receipt), encoding="utf-8")
    approval_scope_sha256 = vendor_task.factor_approval_scope_sha256(
        factor_manifest_file_sha256=_file_sha(factor_path),
        factor_manifest_canonical_sha256=str(
            factor_manifest["canonical_manifest_sha256"]
        ),
        page_manifest_file_sha256=_file_sha(page_path),
        page_manifest_canonical_sha256=str(page["canonical_manifest_sha256"]),
        vendor_receipt_file_sha256=_file_sha(vendor_path),
        vendor_receipt_canonical_sha256=str(vendor_receipt["canonical_receipt_sha256"]),
        database_sha256_before=db_sha,
        returned_cells_sha256=str(vendor_receipt["returned_cells_sha256"]),
        target_cell_count=2,
        source_version=str(vendor_receipt["proposed_source_version"]),
        run_id=str(vendor_receipt["proposed_run_id"]),
    )
    return {
        "db_path": db_path,
        "evidence": evidence,
        "page": page,
        "page_path": page_path,
        "factor_manifest": factor_manifest,
        "factor_path": factor_path,
        "vendor_receipt": vendor_receipt,
        "vendor_path": vendor_path,
        "returned_cells": returned_cells,
        "approval_scope_sha256": approval_scope_sha256,
        "backup_path": tmp_path / "backups" / "page-factor-prewrite.duckdb",
        "write_receipt_path": evidence / "write.json",
    }


@pytest.fixture
def context(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> dict[str, Any]:
    return _build_context(monkeypatch, tmp_path)


def _write(context: dict[str, Any], **overrides: object) -> dict[str, Any]:
    arguments: dict[str, object] = {
        "duckdb_path": context["db_path"],
        "trusted_evidence_root": context["evidence"],
        "page_gap_factor_manifest_file": context["factor_path"],
        "vendor_receipt_file": context["vendor_path"],
        "target_backup_file": context["backup_path"],
        "write_receipt_file": context["write_receipt_path"],
        "executed_at": "2026-08-24T11:00:00Z",
        "approval_reference": "授权 page-gap exact factor scope",
        "expected_approved_scope_sha256": context["approval_scope_sha256"],
        "allow_write": True,
    }
    arguments.update(overrides)
    return module.write_stock_analysis_page_gap_factor_cells(**arguments)


def test_success_inserts_exact_rows_and_persists_final_receipt(
    context: dict[str, Any],
) -> None:
    before = _file_sha(context["db_path"])

    receipt = _write(context)

    assert receipt["receipt_kind"] == module.WRITE_RECEIPT_KIND
    assert receipt["status"] == module.COMPLETED_STATUS
    assert receipt["inserted_row_count"] == 2
    assert receipt["existing_target_row_count"] == 0
    assert receipt["target_cell_count"] == 2
    assert receipt["approval_scope_sha256"] == context["approval_scope_sha256"]
    assert receipt["database"]["sha256_before"] == before
    assert receipt["database"]["sha256_after"] != before
    assert receipt["backup"]["sha256"] == before
    assert receipt["downstream_materialization_executed"] is False
    assert receipt["page_gap_closed"] is False
    valid, errors = module.validate_stock_analysis_page_gap_factor_write_receipt(
        receipt,
        page_gap_factor_manifest=context["factor_manifest"],
        vendor_receipt=context["vendor_receipt"],
    )
    assert valid, errors
    with duckdb.connect(str(context["db_path"]), read_only=True) as conn:
        rows = conn.execute(
            """
            select stock_code, trade_date, adj_factor, source_version, run_id
            from stock_adjustment_factor
            where (stock_code, trade_date) in (
              ('000001.SZ', '2026-01-05'), ('600000.SH', '2026-01-06')
            )
            order by trade_date, stock_code
            """
        ).fetchall()
    assert rows == [
        (
            "000001.SZ",
            "2026-01-05",
            1.05,
            context["vendor_receipt"]["proposed_source_version"],
            context["vendor_receipt"]["proposed_run_id"],
        ),
        (
            "600000.SH",
            "2026-01-06",
            2.06,
            context["vendor_receipt"]["proposed_source_version"],
            context["vendor_receipt"]["proposed_run_id"],
        ),
    ]


def test_requires_allow_write_and_exact_approval_scope(context: dict[str, Any]) -> None:
    with pytest.raises(ValueError, match="allow_write"):
        _write(context, allow_write=False)
    with pytest.raises(ValueError, match="approved_scope"):
        _write(context, expected_approved_scope_sha256="F" * 64)
    assert not context["backup_path"].exists()
    assert not context["write_receipt_path"].exists()


def test_external_page_manifest_tamper_blocks_before_backup(
    context: dict[str, Any],
) -> None:
    page = json.loads(context["page_path"].read_text(encoding="utf-8"))
    page["missing_factor_cells"] = page["missing_factor_cells"][:-1]
    context["page_path"].write_text(json.dumps(page), encoding="utf-8")

    with pytest.raises(ValueError, match="page manifest file SHA"):
        _write(context)

    assert not context["backup_path"].exists()
    assert not context["write_receipt_path"].exists()


def test_database_drift_and_existing_target_are_rejected(
    context: dict[str, Any],
) -> None:
    with duckdb.connect(str(context["db_path"])) as conn:
        conn.execute(
            "insert into stock_adjustment_factor values ('000001.SZ','2026-01-05',9.9,'other','other')"
        )
    with pytest.raises(ValueError, match="database SHA"):
        _write(context)
    assert not context["backup_path"].exists()


def test_global_quality_failure_blocks_without_backup(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    context = _build_context(monkeypatch, tmp_path, invalid_existing=True)
    with pytest.raises(ValueError, match="nonpositive or nonfinite"):
        _write(context)
    assert not context["backup_path"].exists()
    assert not context["write_receipt_path"].exists()


def test_transaction_failure_rolls_back_and_leaves_pending_intent(
    monkeypatch: pytest.MonkeyPatch, context: dict[str, Any]
) -> None:
    original_insert = module._write_helpers._insert_target_rows

    def fail_after_insert(*args: object, **kwargs: object) -> None:
        original_insert(*args, **kwargs)
        raise RuntimeError("synthetic transaction failure")

    monkeypatch.setattr(module._write_helpers, "_insert_target_rows", fail_after_insert)
    with pytest.raises(RuntimeError, match="synthetic transaction failure"):
        _write(context)
    with duckdb.connect(str(context["db_path"]), read_only=True) as conn:
        observed = conn.execute(
            "select count(*) from stock_adjustment_factor where trade_date in ('2026-01-05','2026-01-06')"
        ).fetchone()[0]
    assert observed == 0
    pending = json.loads(context["write_receipt_path"].read_text(encoding="utf-8"))
    assert pending["receipt_kind"] == module.PENDING_INTENT_KIND
    assert pending["completion_attested"] is False
    assert pending["database_write_executed"] is None


def test_unmerged_sidecar_blocks_before_backup(context: dict[str, Any]) -> None:
    sidecar = context["db_path"].with_name(context["db_path"].name + ".wal")
    sidecar.write_bytes(b"pending")
    with pytest.raises(ValueError, match="sidecar"):
        _write(context)
    assert not context["backup_path"].exists()


def test_final_receipt_tamper_detected(context: dict[str, Any]) -> None:
    receipt = _write(context)
    tampered = copy.deepcopy(receipt)
    tampered["downstream_materialization_executed"] = True
    tampered["canonical_write_receipt_sha256"] = module._write_receipt_sha256(tampered)

    valid, errors = module.validate_stock_analysis_page_gap_factor_write_receipt(
        tampered
    )

    assert not valid
    assert any("downstream_materialization_executed" in error for error in errors)


def test_shared_write_safety_dependencies_are_locked() -> None:
    assert module._write_helpers._assert_exact_factor_schema is not None
    assert module._write_helpers._assert_global_table_quality is not None
    assert module._create_prewrite_backup_hardened is not None
    assert module._write_json_exclusive_hardened is not None
    assert module._replace_json_atomically_hardened is not None


def test_writer_acquires_path_lock_then_livermore_lock(
    monkeypatch: pytest.MonkeyPatch, context: dict[str, Any]
) -> None:
    entered: list[str] = []

    @contextmanager
    def record_lock(definition: object, **kwargs: object):
        entered.append(str(getattr(definition, "key")))
        yield Path("lock")

    monkeypatch.setattr(module, "acquire_lock", record_lock)

    _write(context)

    assert entered[0].startswith("lock:duckdb:materialize:")
    assert entered[1] == module._history_task.LIVERMORE_CANDIDATE_HISTORY_LOCK.key


def test_evidence_drift_after_lock_blocks_before_backup(
    monkeypatch: pytest.MonkeyPatch, context: dict[str, Any]
) -> None:
    entered = 0

    @contextmanager
    def mutate_on_second_lock(definition: object, **kwargs: object):
        nonlocal entered
        entered += 1
        if entered == 2:
            context["factor_path"].write_text("{}", encoding="utf-8")
        yield Path("lock")

    monkeypatch.setattr(module, "acquire_lock", mutate_on_second_lock)

    with pytest.raises(ValueError, match="factor manifest changed"):
        _write(context)

    assert not context["backup_path"].exists()
    assert not context["write_receipt_path"].exists()


def test_postcommit_evidence_drift_preserves_pending_for_reconciliation(
    monkeypatch: pytest.MonkeyPatch, context: dict[str, Any]
) -> None:
    original = module._assert_evidence_files_unchanged
    calls = 0

    def mutate_on_second_check(**kwargs: object) -> None:
        nonlocal calls
        calls += 1
        if calls == 2:
            context["vendor_path"].write_text("{}", encoding="utf-8")
        original(**kwargs)

    monkeypatch.setattr(
        module, "_assert_evidence_files_unchanged", mutate_on_second_check
    )

    with pytest.raises(ValueError, match="vendor receipt changed"):
        _write(context)

    pending = json.loads(context["write_receipt_path"].read_text(encoding="utf-8"))
    assert pending["receipt_kind"] == module.PENDING_INTENT_KIND
    assert pending["completion_attested"] is False
    with duckdb.connect(str(context["db_path"]), read_only=True) as conn:
        inserted = conn.execute(
            "select count(*) from stock_adjustment_factor where trade_date in ('2026-01-05','2026-01-06')"
        ).fetchone()[0]
    assert inserted == 2


def test_backup_parent_swap_is_rejected_before_creation(tmp_path: Path) -> None:
    target = tmp_path / "source.duckdb"
    target.write_bytes(b"database-bytes")
    backup_parent = tmp_path / "backups"
    backup_parent.mkdir()
    backup_path = backup_parent / "backup.duckdb"
    parent_identity = module._capture_directory_identity(
        backup_parent,
        field_name="target_backup_file.parent",
    )
    moved_parent = tmp_path / "backups-original"
    backup_parent.rename(moved_parent)
    backup_parent.mkdir()

    with pytest.raises(ValueError, match="identity changed"):
        module._create_prewrite_backup_hardened(
            target=target,
            backup_path=backup_path,
            backup_parent_identity=parent_identity,
        )

    assert not backup_path.exists()


def test_receipt_parent_swap_is_rejected_before_pending_creation(
    tmp_path: Path,
) -> None:
    trusted_root = tmp_path / "evidence"
    trusted_root.mkdir()
    receipt_parent = trusted_root / "receipts"
    receipt_parent.mkdir()
    receipt_path = receipt_parent / "write.json"
    root_identity = module._capture_directory_identity(
        trusted_root,
        field_name="trusted_evidence_root",
    )
    parent_identity = module._capture_directory_identity(
        receipt_parent,
        field_name="write_receipt_file.parent",
    )
    moved_parent = trusted_root / "receipts-original"
    receipt_parent.rename(moved_parent)
    receipt_parent.mkdir()

    with pytest.raises(ValueError, match="identity changed"):
        module._write_json_exclusive_hardened(
            path=receipt_path,
            payload={"status": "write_pending"},
            trusted_root=trusted_root,
            trusted_root_identity=root_identity,
            parent_identity=parent_identity,
        )

    assert not receipt_path.exists()


def test_pending_leaf_swap_is_rejected_before_final_replace(tmp_path: Path) -> None:
    trusted_root = tmp_path / "evidence"
    trusted_root.mkdir()
    receipt_path = trusted_root / "write.json"
    root_identity = module._capture_directory_identity(
        trusted_root,
        field_name="trusted_evidence_root",
    )
    parent_identity = root_identity
    pending = {"status": "write_pending"}
    pending_identity = module._write_json_exclusive_hardened(
        path=receipt_path,
        payload=pending,
        trusted_root=trusted_root,
        trusted_root_identity=root_identity,
        parent_identity=parent_identity,
    )
    replacement = trusted_root / "replacement.json"
    replacement.write_text("replacement", encoding="utf-8")
    replacement.replace(receipt_path)

    with pytest.raises(ValueError, match="identity changed"):
        module._replace_json_atomically_hardened(
            path=receipt_path,
            payload={"status": "completed"},
            expected_existing=pending,
            expected_pending_identity=pending_identity,
            trusted_root=trusted_root,
            trusted_root_identity=root_identity,
            parent_identity=parent_identity,
        )

    assert receipt_path.read_text(encoding="utf-8") == "replacement"
    assert not list(trusted_root.glob("*.completed.tmp"))


def test_identity_cleanup_never_deletes_a_replacement_leaf(tmp_path: Path) -> None:
    parent = tmp_path / "evidence"
    parent.mkdir()
    leaf = parent / "write.json"
    leaf.write_text("created-by-run", encoding="utf-8")
    parent_identity = module._capture_directory_identity(
        parent,
        field_name="write_receipt_file.parent",
    )
    with leaf.open("rb") as handle:
        created_identity = module._identity_from_fstat(handle.fileno())
    replacement = parent / "replacement.json"
    replacement.write_text("replacement", encoding="utf-8")
    replacement.replace(leaf)

    removed = module._safe_unlink_created_leaf(
        path=leaf,
        expected_leaf_identity=created_identity,
        parent_identity=parent_identity,
    )

    assert removed is False
    assert leaf.read_text(encoding="utf-8") == "replacement"
