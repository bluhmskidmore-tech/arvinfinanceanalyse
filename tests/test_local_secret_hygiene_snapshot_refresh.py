from __future__ import annotations

import json
from pathlib import Path

import scripts.refresh_local_secret_hygiene_snapshot as refresh_module


ROOT = Path(__file__).resolve().parents[1]
SNAPSHOT = (
    ROOT / "docs" / "audits" / "2026-06-10-local-secret-hygiene-snapshot.json"
)


def test_local_secret_hygiene_boundary_refresh_preserves_no_value_boundary() -> None:
    snapshot = refresh_module.build_snapshot(
        generated_at="2026-06-10T21:25:00+08:00",
        snapshot_path=SNAPSHOT,
    )

    assert snapshot["report_kind"] == "local_secret_hygiene_snapshot"
    assert snapshot["refresh_command"] == (
        "python scripts\\refresh_local_secret_hygiene_snapshot.py"
    )
    assert snapshot["status"]["fail_closed"] is True
    assert snapshot["status"]["secret_values_captured"] is False
    assert snapshot["status"]["clears_secret_scan"] is False
    assert snapshot["status"]["writes_or_rotates_secrets"] is False
    assert snapshot["value_handling"] == {
        "values_read": False,
        "values_written_to_artifacts": False,
        "values_logged": False,
        "names_only_recorded": True,
    }
    assert snapshot["fresh_scan_results"]["checked_at"] == "2026-06-10T15:45:10+08:00"
    assert snapshot["latest_non_closing_retry"]["checked_at"] == (
        "2026-06-10T17:30:56+08:00"
    )

    latest = snapshot["latest_boundary_only_recheck"]
    assert latest["checked_at"] == "2026-06-10T21:25:00+08:00"
    assert latest["values_read_by_human"] is False
    assert latest["values_written_to_artifacts"] is False
    assert latest["secret_values_captured"] is False
    assert latest["scan_not_rerun"] is True
    assert "did not replace the last full redacted scan evidence" in latest["reason"]
    assert latest["dry_run_plan"]["gitleaks_redaction_enabled"] is True
    assert latest["boundary_checks"]["git_check_ignore"]["matched_rule"] == (
        ".gitignore:4:config/.env"
    )
    assert latest["boundary_checks"]["git_ls_files"]["tracked_path_count"] == 0
    assert latest["boundary_checks"]["git_status_ignored"]["result"] == "!! config/.env"
    assert latest["test_result"] == refresh_module.TEST_RESULT_TEXT
    assert latest["closure_effect"] == "none"


def test_local_secret_hygiene_boundary_refresh_cli_writes_only_output(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "secret-hygiene-snapshot.json"

    exit_code = refresh_module.main(
        [
            "--generated-at",
            "2026-06-10T21:25:00+08:00",
            "--snapshot",
            str(SNAPSHOT),
            "--output",
            str(output_path),
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 0
    assert payload["latest_boundary_only_recheck"]["checked_at"] == (
        "2026-06-10T21:25:00+08:00"
    )
    assert payload["latest_boundary_only_recheck"]["scan_not_rerun"] is True
    assert payload["status"]["clears_secret_scan"] is False
    assert payload["boundary"] == (
        "This snapshot records secret names and Git/file-boundary evidence only. "
        "It does not read, expose, rotate, clear, or approve any secret value."
    )


def test_local_secret_hygiene_boundary_refresh_strict_gate_rejects_current_findings(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "secret-hygiene-snapshot.json"

    exit_code = refresh_module.main(
        [
            "--generated-at",
            "2026-06-10T21:25:00+08:00",
            "--snapshot",
            str(SNAPSHOT),
            "--output",
            str(output_path),
            "--require-clean-boundary",
        ]
    )

    payload = json.loads(output_path.read_text(encoding="utf-8"))
    assert exit_code == 1
    assert payload["latest_boundary_only_recheck"]["secret_values_captured"] is False
    assert payload["status"]["secret_values_captured"] is False
    assert payload["status"]["clears_secret_scan"] is False
    assert payload["latest_boundary_only_recheck"]["boundary_checks"]["git_status_ignored"][
        "result"
    ] == "!! config/.env"
