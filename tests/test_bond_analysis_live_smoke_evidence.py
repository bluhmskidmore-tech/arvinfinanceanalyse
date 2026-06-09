from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts.bond_analysis_live_smoke_evidence import build_artifact, render_markdown


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "bond_analysis_live_smoke_evidence.py"
STATIC_ARTIFACT = ROOT / "docs" / "audits" / "2026-06-09-bond-analysis-live-smoke-evidence.md"


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


def test_bond_analysis_live_smoke_evidence_cli_writes_durable_artifact(
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "bond-analysis-live-smoke-evidence.md"

    returncode, payload = _run_generator(
        "--output",
        str(output_path),
        "--smoke-status",
        "passed",
        "--created-date",
        "2026-06-09",
    )

    assert returncode == 0
    assert payload == {
        "artifact_kind": "bond_analysis_live_smoke_evidence",
        "artifact_path": str(output_path),
        "page_id": "PAGE-BOND-ANALYSIS-001",
        "page_slug": "bond-analysis",
        "execution_status": "passed",
        "formal_use_allowed": False,
        "closure_approved": False,
        "business_owner_approval_captured": False,
        "evidence_scope": {
            "approves_metric_or_page": False,
            "writes_governance_records": False,
            "proves_page_execution": False,
            "captures_business_owner_approval": False,
            "certification_effect": "none",
        },
    }

    text = output_path.read_text(encoding="utf-8")
    assert "# Bond Analysis Live Smoke Evidence" in text
    assert "Page ID: `PAGE-BOND-ANALYSIS-001`" in text
    assert "Page slug: `bond-analysis`" in text
    assert "frontend_route: /bond-analysis" in text
    assert "primary_api: /api/bond-analytics/action-attribution" in text
    assert "execution_status: passed" in text
    assert "`formal_use_allowed=false`" in text
    assert "`closure_approved=false`" in text
    assert "`business_owner_approval_captured=false`" in text
    assert "scripts/codex-page-smoke.ps1 -PageSlug bond-analysis" in text
    assert "python scripts/codex_page_readiness.py --page-slug bond-analysis" in text
    assert "`overall_status=static-pass`" in text
    assert "`audit_review.status=ready_for_audit_review`" in text
    assert "UI/API payload review remains tied to `tests/golden_samples/GS-BOND-ANALYSIS-ACTION-ATTR-A/response.json`." in text
    assert "does not approve closure" in text
    assert "does not capture business-owner approval" in text


def test_static_bond_analysis_live_smoke_evidence_matches_generator() -> None:
    expected = render_markdown(
        build_artifact(
            output_path=STATIC_ARTIFACT,
            smoke_status="passed",
            created_date="2026-06-09",
        ),
    )
    actual = STATIC_ARTIFACT.read_text(encoding="utf-8")

    assert actual == expected
