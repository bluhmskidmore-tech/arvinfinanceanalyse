from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.average_balance_live_smoke_evidence import build_artifact, render_markdown


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "average_balance_live_smoke_evidence.py"
STATIC_ARTIFACT = ROOT / "docs" / "audits" / "2026-06-09-average-balance-live-smoke-evidence.md"


def _run_generator(*args: str) -> tuple[int, dict[str, object]]:
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    return completed.returncode, json.loads(completed.stdout)


def test_average_balance_live_smoke_evidence_cli_writes_durable_artifact(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "average-balance-live-smoke-evidence.md"

    returncode, payload = _run_generator(
        "--output",
        str(output_path),
        "--smoke-status",
        "passed",
        "--verify-status",
        "passed",
        "--created-date",
        "2026-06-09",
    )

    assert returncode == 0
    assert payload == {
        "artifact_kind": "average_balance_live_smoke_evidence",
        "artifact_path": str(output_path),
        "page_id": "PAGE-ADB-001",
        "page_slug": "average-balance",
        "smoke_execution_status": "passed",
        "verify_execution_status": "passed",
        "formal_use_allowed": False,
        "closure_approved": False,
        "business_owner_approval_captured": False,
        "evidence_scope": {
            "approves_metric_or_page": False,
            "writes_governance_records": False,
            "proves_page_execution": False,
            "captures_business_owner_approval": False,
            "certification_effect": "none",
            "approves_formal_balance_truth": False,
            "approves_monthly_adb_nim_truth": False,
        },
    }

    text = output_path.read_text(encoding="utf-8")
    assert "# Average Balance Live Smoke Evidence" in text
    assert "Page ID: `PAGE-ADB-001`" in text
    assert "Page slug: `average-balance`" in text
    assert "frontend_route: /average-balance" in text
    assert "primary_api: /api/analysis/adb" in text
    assert "smoke_execution_status: passed" in text
    assert "verify_execution_status: passed" in text
    assert "`formal_use_allowed=false`" in text
    assert "`closure_approved=false`" in text
    assert "`business_owner_approval_captured=false`" in text
    assert "scripts/codex-page-smoke.ps1 -PageSlug average-balance" in text
    assert "scripts/codex-verify-page.ps1 -PageSlug average-balance -Run" in text
    assert "python scripts/codex_page_readiness.py --page-slug average-balance" in text
    assert "`overall_status=static-pass`" in text
    assert "`audit_review.status=ready_for_audit_review`" in text
    assert "UI/API payload review remains tied to `tests/golden_samples/GS-AVERAGE-BALANCE-A/response.json`." in text
    assert "MTR-ADB-003` remains monthly ADB/NIM pending" in text
    assert "does not approve closure" in text
    assert "does not capture business-owner approval" in text
    assert "does not approve monthly ADB/NIM truth" in text


def test_static_average_balance_live_smoke_evidence_matches_generator() -> None:
    expected = render_markdown(
        build_artifact(
            output_path=STATIC_ARTIFACT,
            smoke_status="passed",
            verify_status="passed",
            created_date="2026-06-09",
        ),
    )
    actual = STATIC_ARTIFACT.read_text(encoding="utf-8")

    assert actual == expected
