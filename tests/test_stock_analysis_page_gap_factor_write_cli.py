from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import stock_analysis_page_gap_factor_write as cli

pytestmark = [
    pytest.mark.excluded_surface_regression,
    pytest.mark.surface_livermore,
]


def _completed_receipt(tmp_path: Path) -> dict[str, object]:
    return {
        "status": cli.write_task.COMPLETED_STATUS,
        "database_write_executed": True,
        "completion_attested": True,
        "historical_availability_proven": False,
        "formal_historical_replay_use_allowed": False,
        "certification_allowed": False,
        "downstream_materialization_executed": False,
        "page_gap_closed": False,
        "canonical_write_receipt_sha256": "A" * 64,
        "backup": {"path": str(tmp_path / "backup.duckdb"), "sha256": "B" * 64},
        "database": {
            "path": str(tmp_path / "moss.duckdb"),
            "sha256_before": "B" * 64,
            "sha256_after": "C" * 64,
        },
        "inserted_row_count": 3,
        "target_cell_count": 3,
        "target_cells_sha256": "D" * 64,
        "target_rows_sha256": "E" * 64,
        "approval_scope_sha256": "F" * 64,
        "source_version": "source-v1",
        "run_id": "run-v1",
    }


def _run_args(tmp_path: Path) -> dict[str, object]:
    evidence = tmp_path / "evidence"
    evidence.mkdir(exist_ok=True)
    return {
        "duckdb_path": tmp_path / "moss.duckdb",
        "trusted_evidence_root": evidence,
        "page_gap_factor_manifest_file": evidence / "factor.json",
        "vendor_receipt_file": evidence / "vendor.json",
        "target_backup_file": tmp_path / "backups" / "backup.duckdb",
        "write_receipt_file": "write.json",
        "executed_at": "2026-08-24T11:00:00Z",
        "approval_reference": "approved scope",
        "expected_approved_scope_sha256": "F" * 64,
        "allow_write": True,
    }


def test_success_returns_compact_receipt_with_persisted_file_hash(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    args = _run_args(tmp_path)
    receipt_path = Path(args["trusted_evidence_root"]) / "write.json"
    receipt_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        cli.write_task,
        "write_stock_analysis_page_gap_factor_cells",
        lambda **kwargs: _completed_receipt(tmp_path),
    )

    result = cli.run_page_gap_factor_write_cli(**args)

    assert result["status"] == cli.write_task.COMPLETED_STATUS
    assert result["database_write_executed"] is True
    assert result["downstream_materialization_executed"] is False
    assert result["page_gap_closed"] is False
    assert result["target_cell_count"] == 3
    assert result["approval_scope_sha256"] == "F" * 64
    assert result["write_receipt"]["path"] == str(receipt_path.resolve())
    assert result["write_receipt"]["file_sha256"]


def test_failure_is_redacted_and_does_not_claim_write(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    args = _run_args(tmp_path)

    def fail(**kwargs: object) -> dict[str, object]:
        raise ValueError("sensitive details must not leak")

    monkeypatch.setattr(
        cli.write_task, "write_stock_analysis_page_gap_factor_cells", fail
    )
    result = cli.run_page_gap_factor_write_cli(**args)

    assert result["status"] == "blocked"
    assert result["blockers"] == ["page_gap_factor_write_failed_ValueError"]
    assert "sensitive" not in json.dumps(result)
    assert result["database_write_executed"] is False
    assert result["downstream_materialization_executed"] is False


def test_pending_intent_reports_unknown_write_state(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    args = _run_args(tmp_path)
    receipt_path = Path(args["trusted_evidence_root"]) / "write.json"
    receipt_path.write_text(
        json.dumps(
            {
                "receipt_kind": cli.write_task.PENDING_INTENT_KIND,
                "status": cli.write_task.PENDING_STATUS,
                "completion_attested": False,
                "canonical_pending_intent_sha256": "A" * 64,
            }
        ),
        encoding="utf-8",
    )

    def fail(**kwargs: object) -> dict[str, object]:
        raise RuntimeError("post-commit finalization failed")

    monkeypatch.setattr(
        cli.write_task, "write_stock_analysis_page_gap_factor_cells", fail
    )
    result = cli.run_page_gap_factor_write_cli(**args)

    assert result["status"] == "blocked"
    assert result["database_write_executed"] is None
    assert result["completion_attested"] is False
    assert result["pending_intent_detected"] is True
    assert result["write_receipt"]["path"] == str(receipt_path.resolve())
    assert result["write_receipt"]["file_sha256"]
    assert result["write_receipt"]["canonical_sha256"] == "A" * 64


def test_pending_probe_rejects_escape_and_does_not_read_outside(tmp_path: Path) -> None:
    evidence = tmp_path / "evidence"
    evidence.mkdir()
    outside = tmp_path / "outside.json"
    outside.write_text(
        json.dumps(
            {
                "receipt_kind": cli.write_task.PENDING_INTENT_KIND,
                "status": cli.write_task.PENDING_STATUS,
                "completion_attested": False,
            }
        ),
        encoding="utf-8",
    )

    assert not cli._has_pending_intent(
        trusted_evidence_root=evidence,
        write_receipt_file=outside,
    )


def test_main_prints_compact_json_and_returns_expected_exit_codes(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    success = _completed_receipt(tmp_path)
    monkeypatch.setattr(cli, "run_page_gap_factor_write_cli", lambda **kwargs: success)
    argv = [
        "--duckdb-path",
        str(tmp_path / "moss.duckdb"),
        "--trusted-evidence-root",
        str(tmp_path),
        "--factor-manifest-file",
        "factor.json",
        "--vendor-receipt-file",
        "vendor.json",
        "--backup-file",
        str(tmp_path / "backups" / "backup.duckdb"),
        "--write-receipt-file",
        "write.json",
        "--approval-reference",
        "approved",
        "--expected-approved-scope-sha256",
        "F" * 64,
        "--executed-at",
        "2026-08-24T11:00:00Z",
        "--allow-write",
    ]

    assert cli.main(argv) == cli.EXIT_SUCCESS
    assert (
        json.loads(capsys.readouterr().out)["status"] == cli.write_task.COMPLETED_STATUS
    )

    monkeypatch.setattr(
        cli,
        "run_page_gap_factor_write_cli",
        lambda **kwargs: {"status": "blocked", "database_write_executed": False},
    )
    assert cli.main(argv) == cli.EXIT_BLOCKED
