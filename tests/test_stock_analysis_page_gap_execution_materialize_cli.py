from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.helpers import load_module

pytestmark = [
    pytest.mark.excluded_surface_acceptance,
    pytest.mark.surface_livermore,
]

CREATED_AT = "2026-08-24T12:00:00Z"


def _load_module():
    return load_module(
        "scripts.stock_analysis_page_gap_execution_materialize",
        "scripts/stock_analysis_page_gap_execution_materialize.py",
    )


def _files(tmp_path: Path) -> tuple[Path, Path]:
    db_path = tmp_path / "cli.duckdb"
    db_path.write_bytes(b"test-duckdb-placeholder")
    trusted_root = tmp_path / "evidence"
    trusted_root.mkdir()
    return db_path, trusted_root


def _plan() -> dict[str, Any]:
    return {
        "status": "ready",
        "canonical_plan_sha256": "A" * 64,
        "approval_scope_sha256": "B" * 64,
        "summary": {
            "target_execution_key_count": 2446,
            "target_gap_horizon_count": 5022,
            "projected_page_gap_view_count_after": 0,
        },
    }


def _receipt(status: str = "materialization_completed") -> dict[str, Any]:
    return {
        "status": status,
        "canonical_materialization_receipt_sha256": "C" * 64,
        "approval_scope_sha256": "B" * 64,
        "verification": {
            "page_gap_view_count_after": 0,
            "row_count_before": 5943,
            "row_count_after": 5943,
        },
    }


def test_help_exposes_default_dry_run_and_explicit_write_gate(
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module()
    with pytest.raises(SystemExit) as exc_info:
        module.main(["--help"])
    assert exc_info.value.code == 0
    help_text = capsys.readouterr().out
    assert "--page-manifest-file" in help_text
    assert "--factor-write-receipt-file" in help_text
    assert "--allow-write" in help_text
    assert "--expected-materialization-approval-scope-sha256" in help_text
    assert "--backup" not in help_text


def test_default_dry_run_persists_full_plan_without_changing_database(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path, trusted_root = _files(tmp_path)
    expected = _plan()
    monkeypatch.setattr(
        module.materialize_task,
        "build_stock_analysis_page_gap_execution_materialization_plan_from_files",
        lambda **kwargs: expected,
    )

    result = module.run_stock_analysis_page_gap_execution_materialize_cli(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        page_manifest_file="page.json",
        factor_write_receipt_file="factor.json",
        output_file="plan.json",
        executed_at=CREATED_AT,
    )

    output = trusted_root / "plan.json"
    assert result["status"] == "ready"
    assert result["mode"] == "dry_run"
    assert result["database_unchanged"] is True
    assert result["summary"] == expected["summary"]
    assert result["canonical_plan_sha256"] == "A" * 64
    assert json.loads(output.read_text(encoding="utf-8")) == expected
    assert "targets" not in result


def test_live_requires_both_approval_fields_before_writer(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path, trusted_root = _files(tmp_path)
    monkeypatch.setattr(
        module.materialize_task,
        "materialize_stock_analysis_page_gap_execution_history",
        lambda **kwargs: pytest.fail("writer must not run without complete approval"),
    )

    result = module.run_stock_analysis_page_gap_execution_materialize_cli(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        page_manifest_file="page.json",
        factor_write_receipt_file="factor.json",
        output_file="receipt.json",
        executed_at=CREATED_AT,
        allow_write=True,
    )

    assert result["status"] == "blocked"
    assert result["database_unchanged"] is True
    assert (trusted_root / "receipt.json").exists() is False


def test_live_success_delegates_and_reports_compact_receipt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path, trusted_root = _files(tmp_path)
    expected = _receipt()

    def _fake_live(**kwargs: Any) -> dict[str, Any]:
        path = trusted_root / str(kwargs["write_receipt_file"])
        path.write_text(json.dumps(expected), encoding="utf-8")
        assert kwargs["allow_write"] is True
        return expected

    monkeypatch.setattr(
        module.materialize_task,
        "materialize_stock_analysis_page_gap_execution_history",
        _fake_live,
    )

    result = module.run_stock_analysis_page_gap_execution_materialize_cli(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        page_manifest_file="page.json",
        factor_write_receipt_file="factor.json",
        output_file="receipt.json",
        executed_at=CREATED_AT,
        allow_write=True,
        approval_reference="approved",
        expected_materialization_approval_scope_sha256="B" * 64,
    )

    assert result["status"] == "materialization_completed"
    assert result["mode"] == "live"
    assert result["verification"] == expected["verification"]
    assert result["canonical_materialization_receipt_sha256"] == "C" * 64
    assert result["output_file_sha256"] is not None


def test_live_post_pending_failure_reports_and_preserves_reconcile_artifact(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path, trusted_root = _files(tmp_path)
    pending = {
        "intent_kind": "stock_analysis_page_gap_execution_materialization_pending_intent_v1",
        "status": "materialization_pending",
        "database_write_executed": False,
    }

    def _persist_pending_then_fail(**kwargs: Any) -> dict[str, Any]:
        path = trusted_root / str(kwargs["write_receipt_file"])
        path.write_text(json.dumps(pending), encoding="utf-8")
        raise RuntimeError("simulated finalization failure with secret detail")

    monkeypatch.setattr(
        module.materialize_task,
        "materialize_stock_analysis_page_gap_execution_history",
        _persist_pending_then_fail,
    )

    result = module.run_stock_analysis_page_gap_execution_materialize_cli(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        page_manifest_file="page.json",
        factor_write_receipt_file="factor.json",
        output_file="pending.json",
        executed_at=CREATED_AT,
        allow_write=True,
        approval_reference="approved",
        expected_materialization_approval_scope_sha256="B" * 64,
    )

    output = trusted_root / "pending.json"
    assert result["status"] == "error"
    assert result["output_file"] == str(output.resolve())
    assert result["output_file_sha256"] is not None
    assert "secret" not in json.dumps(result).lower()
    assert json.loads(output.read_text(encoding="utf-8")) == pending


def test_output_escape_and_overwrite_are_blocked_before_builder(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path, trusted_root = _files(tmp_path)
    monkeypatch.setattr(
        module.materialize_task,
        "build_stock_analysis_page_gap_execution_materialization_plan_from_files",
        lambda **kwargs: pytest.fail("builder must not run for unsafe output"),
    )

    outside = tmp_path / "outside.json"
    escaped = module.run_stock_analysis_page_gap_execution_materialize_cli(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        page_manifest_file="page.json",
        factor_write_receipt_file="factor.json",
        output_file=outside,
        executed_at=CREATED_AT,
    )
    assert escaped["status"] == "blocked"
    assert outside.exists() is False

    existing = trusted_root / "existing.json"
    existing.write_text("keep", encoding="utf-8")
    overwritten = module.run_stock_analysis_page_gap_execution_materialize_cli(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        page_manifest_file="page.json",
        factor_write_receipt_file="factor.json",
        output_file=existing,
        executed_at=CREATED_AT,
    )
    assert overwritten["status"] == "blocked"
    assert existing.read_text(encoding="utf-8") == "keep"


def test_approval_arguments_are_rejected_in_dry_run(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    db_path, trusted_root = _files(tmp_path)
    monkeypatch.setattr(
        module.materialize_task,
        "build_stock_analysis_page_gap_execution_materialization_plan_from_files",
        lambda **kwargs: pytest.fail("builder must not run with live-only arguments"),
    )

    result = module.run_stock_analysis_page_gap_execution_materialize_cli(
        duckdb_path=db_path,
        trusted_evidence_root=trusted_root,
        page_manifest_file="page.json",
        factor_write_receipt_file="factor.json",
        output_file="plan.json",
        executed_at=CREATED_AT,
        approval_reference="not-valid-in-dry-run",
    )

    assert result["status"] == "blocked"
    assert (trusted_root / "plan.json").exists() is False


def test_main_returns_success_blocked_and_runtime_codes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module()
    db_path, trusted_root = _files(tmp_path)
    base_args = [
        "--duckdb-path",
        str(db_path),
        "--trusted-evidence-root",
        str(trusted_root),
        "--page-manifest-file",
        "page.json",
        "--factor-write-receipt-file",
        "factor.json",
        "--output-file",
        "output.json",
        "--executed-at",
        CREATED_AT,
    ]
    monkeypatch.setattr(
        module,
        "run_stock_analysis_page_gap_execution_materialize_cli",
        lambda **kwargs: {
            "status": "ready",
            "summary": {"target_gap_horizon_count": 5022},
        },
    )
    assert module.main(base_args) == module.EXIT_SUCCESS
    assert json.loads(capsys.readouterr().out)["status"] == "ready"

    monkeypatch.setattr(
        module,
        "run_stock_analysis_page_gap_execution_materialize_cli",
        lambda **kwargs: {"status": "blocked", "blockers": ["x"]},
    )
    assert module.main(base_args) == module.EXIT_BLOCKED
    capsys.readouterr()

    monkeypatch.setattr(
        module,
        "run_stock_analysis_page_gap_execution_materialize_cli",
        lambda **kwargs: {"status": "error", "blockers": ["x"]},
    )
    assert module.main(base_args) == module.EXIT_RUNTIME_ERROR
