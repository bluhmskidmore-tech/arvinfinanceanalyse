from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

import scripts.portfolio_home_score_blocker_consistency_check as consistency_check
from scripts.portfolio_home_score_blocker_consistency_check import build_report


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "portfolio_home_score_blocker_consistency_check.py"
CURRENT_SCORE_BLOCKERS = [
    "risk_tensor_quality_warning",
    "krd_contract_decision_required",
    "bond_maturity_date_remediation_required",
    "tyw_liability_maturity_date_remediation_required",
    "duration_exclusion_warning_mismatch",
    "risk_tensor_warning_mismatch",
    "business_owner_approval",
    "owner_decision_intake_blocked",
]


def _copy_portfolio_docs(tmp_path: Path) -> Path:
    docs_root = tmp_path / "docs"
    shutil.copytree(ROOT / "docs" / "portfolio", docs_root / "portfolio")
    audits_root = docs_root / "audits"
    audits_root.mkdir()
    shutil.copy2(
        ROOT / "docs" / "audits" / "2026-06-05-portfolio-readiness-gate-audit.md",
        audits_root / "2026-06-05-portfolio-readiness-gate-audit.md",
    )
    return docs_root


def _run_check(*args: str) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    return completed.returncode, json.loads(completed.stdout)


def test_portfolio_home_score_blocker_consistency_check_reports_current_artifacts() -> None:
    report = build_report(docs_root=ROOT / "docs")

    assert report["status"] == "consistent"
    assert report["blockers"] == []
    assert report["report_date"] == "2026-05-31"
    assert report["scorecard_status"] == "blocked"
    assert report["scorecard_full_score_ready"] is False
    assert report["expected_score_blockers"] == CURRENT_SCORE_BLOCKERS
    assert [artifact["name"] for artifact in report["artifacts"]] == [
        "evidence_snapshot",
        "business_owner_approval_packet",
        "owner_action_packet",
        "owner_input_needed_summary",
        "owner_handoff_packet",
        "option_b_execution_note",
        "full_closure_signoff_packet",
        "readiness_gate_audit",
    ]
    for artifact in report["artifacts"]:
        assert artifact["status"] == "consistent"
        assert artifact["score_blockers"] == CURRENT_SCORE_BLOCKERS


def test_portfolio_home_score_blocker_consistency_check_cli_require_consistent() -> None:
    returncode, payload = _run_check("--require-consistent")

    assert returncode == 0
    assert payload["status"] == "consistent"
    assert payload["expected_score_blockers"] == CURRENT_SCORE_BLOCKERS


def test_portfolio_home_score_blocker_consistency_check_blocks_drift(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    portfolio = docs_root / "portfolio"

    snapshot = portfolio / "portfolio-home-evidence-snapshot.json"
    payload = json.loads(snapshot.read_text(encoding="utf-8"))
    payload["score_blockers"] = payload["score_blockers"][:-1]
    snapshot.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert report["blockers"] == ["evidence_snapshot_score_blockers_mismatch"]
    assert report["artifacts"][0]["missing_blockers"] == ["owner_decision_intake_blocked"]


def test_portfolio_home_score_blocker_consistency_check_rejects_missing_section(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    handoff = docs_root / "portfolio" / "portfolio-home-owner-handoff-packet.md"
    handoff.write_text(
        handoff.read_text(encoding="utf-8").replace("## Current Blockers", "## Blockers"),
        encoding="utf-8",
    )

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert "owner_handoff_packet_score_blockers_missing" in report["blockers"]


def test_portfolio_home_score_blocker_consistency_check_blocks_audit_drift(
    tmp_path: Path,
) -> None:
    docs_root = _copy_portfolio_docs(tmp_path)
    audit = docs_root / "audits" / "2026-06-05-portfolio-readiness-gate-audit.md"
    audit.write_text(
        audit.read_text(encoding="utf-8").replace(
            ", `duration_exclusion_warning_mismatch`, `risk_tensor_warning_mismatch`",
            "",
        ),
        encoding="utf-8",
    )

    report = build_report(docs_root=docs_root)

    assert report["status"] == "blocked"
    assert "readiness_gate_audit_score_blockers_mismatch" in report["blockers"]
    audit_artifact = next(
        artifact for artifact in report["artifacts"] if artifact["name"] == "readiness_gate_audit"
    )
    assert audit_artifact["missing_blockers"] == [
        "duration_exclusion_warning_mismatch",
        "risk_tensor_warning_mismatch",
    ]


def test_portfolio_home_score_blocker_consistency_check_uses_scorecard_as_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def scorecard_with_new_blocker(**_: object) -> dict[str, object]:
        return {
            "page_id": "PAGE-PORTFOLIO-HOME-001",
            "page_slug": "portfolio",
            "report_date": "2026-05-31",
            "score_status": "blocked",
            "full_score_ready": False,
            "score_blockers": [*CURRENT_SCORE_BLOCKERS, "new_scorecard_blocker"],
        }

    monkeypatch.setattr(consistency_check, "build_scorecard", scorecard_with_new_blocker)

    report = build_report(docs_root=ROOT / "docs", limit=1)

    assert report["status"] == "blocked"
    assert report["expected_score_blockers"] == [
        *CURRENT_SCORE_BLOCKERS,
        "new_scorecard_blocker",
    ]
    assert report["blockers"] == ["evidence_snapshot_score_blockers_mismatch"]
    assert report["artifacts"][0]["missing_blockers"] == ["new_scorecard_blocker"]


def test_portfolio_home_score_blocker_consistency_check_rejects_negative_limit() -> None:
    with pytest.raises(ValueError) as error:
        build_report(docs_root=ROOT / "docs", limit=-1)

    assert str(error.value) == "Portfolio-home score blocker consistency limit must be non-negative: -1"

    completed = subprocess.run(
        [sys.executable, str(SCRIPT), "--limit", "-1"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )

    assert completed.returncode == 2
    assert "Portfolio-home score blocker consistency limit must be non-negative: -1" in completed.stderr
