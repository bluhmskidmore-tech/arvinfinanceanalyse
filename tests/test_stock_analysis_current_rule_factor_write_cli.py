from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from tests.helpers import load_module

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]

EXPECTED_SCOPE_SHA256 = "F" * 64


def _load_module() -> Any:
    return load_module(
        "scripts.stock_analysis_current_rule_factor_write",
        "scripts/stock_analysis_current_rule_factor_write.py",
    )


def test_cli_success_reports_compact_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    receipt_path = tmp_path / "receipt.json"
    monkeypatch.setattr(
        module.write_task,
        "write_stock_analysis_current_rule_factor_cells",
        lambda **kwargs: {
            "status": module.write_task.COMPLETED_STATUS,
            "database_write_executed": True,
            "historical_availability_proven": False,
            "formal_historical_replay_use_allowed": False,
            "certification_allowed": False,
            "write_receipt_path": str(receipt_path),
            "write_receipt_file_sha256": "D" * 64,
            "canonical_write_receipt_sha256": "A" * 64,
            "inserted_row_count": 53,
            "target_cell_count": 53,
            "source_version": "source-v1",
            "run_id": "run-v1",
            "backup": {"path": "backup.duckdb", "sha256": "E" * 64},
            "database": {
                "path": "db.duckdb",
                "sha256_before": "B" * 64,
                "sha256_after": "C" * 64,
            },
        },
    )

    result = module.run_current_rule_factor_write_cli(
        duckdb_path="db.duckdb",
        trusted_evidence_root="evidence",
        reviewed_factor_manifest_file="manifest.json",
        vendor_receipt_file="vendor.json",
        target_backup_file="backup.duckdb",
        write_receipt_file=receipt_path,
        executed_at="2026-08-24T02:00:00Z",
        approval_reference="授权写入这 53 条",
        expected_approved_scope_sha256=EXPECTED_SCOPE_SHA256,
        allow_write=True,
    )

    assert result == {
        "status": module.write_task.COMPLETED_STATUS,
        "blockers": [],
        "database_write_executed": True,
        "historical_availability_proven": False,
        "formal_historical_replay_use_allowed": False,
        "certification_allowed": False,
        "write_receipt": {
            "path": str(receipt_path),
            "file_sha256": "D" * 64,
            "canonical_sha256": "A" * 64,
        },
        "backup": {"path": "backup.duckdb", "sha256": "E" * 64},
        "database": {
            "path": "db.duckdb",
            "sha256_before": "B" * 64,
            "sha256_after": "C" * 64,
        },
        "inserted_row_count": 53,
        "target_cell_count": 53,
        "source_version": "source-v1",
        "run_id": "run-v1",
    }


def test_cli_failure_redacts_to_blocker_code(monkeypatch: pytest.MonkeyPatch) -> None:
    module = _load_module()
    monkeypatch.setattr(
        module.write_task,
        "write_stock_analysis_current_rule_factor_cells",
        lambda **kwargs: (_ for _ in ()).throw(RuntimeError("secret-detail")),
    )

    result = module.run_current_rule_factor_write_cli(
        duckdb_path="db.duckdb",
        trusted_evidence_root="evidence",
        reviewed_factor_manifest_file="manifest.json",
        vendor_receipt_file="vendor.json",
        target_backup_file="backup.duckdb",
        write_receipt_file="receipt.json",
        executed_at="2026-08-24T02:00:00Z",
        approval_reference="授权写入这 53 条",
        expected_approved_scope_sha256=EXPECTED_SCOPE_SHA256,
        allow_write=True,
    )

    assert result["status"] == "blocked"
    assert result["blockers"] == ["factor_write_failed_RuntimeError"]
    assert result["database_write_executed"] is False
    assert "secret-detail" not in json.dumps(result)


def test_cli_failure_with_pending_intent_reports_unknown_write_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(
        json.dumps(
            {
                "receipt_kind": module.write_task.PENDING_INTENT_KIND,
                "status": module.write_task.PENDING_STATUS,
                "completion_attested": False,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        module.write_task,
        "write_stock_analysis_current_rule_factor_cells",
        lambda **kwargs: (_ for _ in ()).throw(OSError("finalize-failed")),
    )

    result = module.run_current_rule_factor_write_cli(
        duckdb_path="db.duckdb",
        trusted_evidence_root=tmp_path,
        reviewed_factor_manifest_file="manifest.json",
        vendor_receipt_file="vendor.json",
        target_backup_file="backup.duckdb",
        write_receipt_file="receipt.json",
        executed_at="2026-08-24T02:00:00Z",
        approval_reference="授权写入这 53 条",
        expected_approved_scope_sha256=EXPECTED_SCOPE_SHA256,
        allow_write=True,
    )

    assert result["status"] == "blocked"
    assert result["database_write_executed"] is None
    assert result["blockers"] == ["factor_write_failed_OSError"]


def test_cli_derives_persisted_receipt_path_and_file_hash(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    module = _load_module()
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text("{}\n", encoding="utf-8")
    monkeypatch.setattr(
        module.write_task,
        "write_stock_analysis_current_rule_factor_cells",
        lambda **kwargs: {
            "status": module.write_task.COMPLETED_STATUS,
            "database_write_executed": True,
            "canonical_write_receipt_sha256": "A" * 64,
        },
    )

    result = module.run_current_rule_factor_write_cli(
        duckdb_path="db.duckdb",
        trusted_evidence_root=tmp_path,
        reviewed_factor_manifest_file="manifest.json",
        vendor_receipt_file="vendor.json",
        target_backup_file="backup.duckdb",
        write_receipt_file="receipt.json",
        executed_at="2026-08-24T02:00:00Z",
        approval_reference="授权写入这 53 条",
        expected_approved_scope_sha256=EXPECTED_SCOPE_SHA256,
        allow_write=True,
    )

    assert result["write_receipt"] == {
        "path": str(receipt_path.resolve()),
        "file_sha256": module._file_sha256(receipt_path),
        "canonical_sha256": "A" * 64,
    }


def test_main_uses_compact_stdout_and_exit_codes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module()
    args = [
        "--duckdb-path",
        "db.duckdb",
        "--trusted-evidence-root",
        "evidence",
        "--factor-manifest-file",
        "manifest.json",
        "--vendor-receipt-file",
        "vendor.json",
        "--backup-file",
        "backup.duckdb",
        "--write-receipt-file",
        "receipt.json",
        "--approval-reference",
        "授权写入这 53 条",
        "--expected-approved-scope-sha256",
        EXPECTED_SCOPE_SHA256,
        "--allow-write",
    ]
    monkeypatch.setattr(
        module,
        "run_current_rule_factor_write_cli",
        lambda **kwargs: {
            "status": module.write_task.COMPLETED_STATUS,
            "blockers": [],
            "database_write_executed": True,
        },
    )
    assert module.main(args) == module.EXIT_SUCCESS
    printed = capsys.readouterr().out
    assert json.loads(printed)["status"] == module.write_task.COMPLETED_STATUS
    assert "\n  " not in printed

    monkeypatch.setattr(
        module,
        "run_current_rule_factor_write_cli",
        lambda **kwargs: {
            "status": module.write_task.COMPLETED_STATUS,
            "blockers": [],
            "database_write_executed": False,
        },
    )
    assert module.main(args) == module.EXIT_BLOCKED
    assert json.loads(capsys.readouterr().out)["database_write_executed"] is False


def test_main_requires_expected_approved_scope_hash(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module()
    called = False

    def unexpected_call(**kwargs: object) -> dict[str, object]:
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(module, "run_current_rule_factor_write_cli", unexpected_call)
    args = [
        "--duckdb-path",
        "db.duckdb",
        "--trusted-evidence-root",
        "evidence",
        "--factor-manifest-file",
        "manifest.json",
        "--vendor-receipt-file",
        "vendor.json",
        "--backup-file",
        "backup.duckdb",
        "--write-receipt-file",
        "receipt.json",
        "--approval-reference",
        "授权写入这 53 条",
        "--allow-write",
    ]

    with pytest.raises(SystemExit) as excinfo:
        module.main(args)

    assert excinfo.value.code == 2
    assert called is False
    assert "--expected-approved-scope-sha256" in capsys.readouterr().err


def test_help_shows_public_and_compat_aliases(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    module = _load_module()

    with pytest.raises(SystemExit) as excinfo:
        module.main(["--help"])

    assert excinfo.value.code == 0
    help_text = capsys.readouterr().out
    assert "--factor-manifest-file" in help_text
    assert "--reviewed-factor-manifest-file" in help_text
    assert "--backup-file" in help_text
    assert "--target-backup-file" in help_text
    assert "--expected-approved-scope-sha256" in help_text
