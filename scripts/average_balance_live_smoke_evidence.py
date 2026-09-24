from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.codex_page_readiness import build_page_readiness_report  # noqa: E402


DEFAULT_OUTPUT = (
    ROOT / "docs" / "audits" / "2026-06-09-average-balance-live-smoke-evidence.md"
)
SMOKE_COMMAND = "scripts/codex-page-smoke.ps1 -PageSlug average-balance"
VERIFY_COMMAND = "scripts/codex-verify-page.ps1 -PageSlug average-balance -Run"
READINESS_COMMAND = "python scripts/codex_page_readiness.py --page-slug average-balance"
GOLDEN_SAMPLE_PAYLOAD = "tests/golden_samples/GS-AVERAGE-BALANCE-A/response.json"


def build_artifact(
    *,
    output_path: Path = DEFAULT_OUTPUT,
    smoke_status: str,
    verify_status: str,
    created_date: str,
) -> dict[str, Any]:
    readiness = build_page_readiness_report("average-balance")
    approval = readiness["business_owner_approval_status"]
    audit_review = readiness["audit_review"]
    return {
        "artifact_kind": "average_balance_live_smoke_evidence",
        "artifact_path": str(output_path),
        "created_date": created_date,
        "page_id": readiness["page_id"],
        "page_slug": readiness["page_slug"],
        "route": readiness["route"],
        "primary_api": readiness["primary_api"],
        "smoke_execution_status": smoke_status,
        "verify_execution_status": verify_status,
        "overall_status": readiness["overall_status"],
        "audit_review_status": audit_review["status"],
        "formal_use_allowed": bool(readiness["formal_use_allowed"]),
        "closure_approved": bool(audit_review["closure_approved"]),
        "business_owner_approval_captured": bool(
            approval["business_owner_approval_captured"],
        ),
        "approval_status": approval["approval_status"],
        "smoke_command": SMOKE_COMMAND,
        "verify_command": VERIFY_COMMAND,
        "readiness_command": READINESS_COMMAND,
        "golden_sample_payload": GOLDEN_SAMPLE_PAYLOAD,
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


def render_markdown(artifact: dict[str, Any]) -> str:
    evidence_scope = artifact["evidence_scope"]
    return f"""# Average Balance Live Smoke Evidence

Date: {artifact['created_date']}
Page ID: `{artifact['page_id']}`
Page slug: `{artifact['page_slug']}`
frontend_route: {artifact['route']}
primary_api: {artifact['primary_api']}
smoke_execution_status: {artifact['smoke_execution_status']}
verify_execution_status: {artifact['verify_execution_status']}

## Scope

This artifact records the live smoke and page verification evidence reference for the `average-balance` owner-review packet set. It does not approve closure, does not capture business-owner approval, does not write governance records, does not promote ADB metrics to formal use, does not replace PAGE-BALANCE-001 formal balance truth, and does not approve monthly ADB/NIM truth.

Boundary status preserved:

- `formal_use_allowed={str(artifact['formal_use_allowed']).lower()}`
- `closure_approved={str(artifact['closure_approved']).lower()}`
- `business_owner_approval_captured={str(artifact['business_owner_approval_captured']).lower()}`
- `approval_status={artifact['approval_status']}`

## Live Smoke Command

Command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File {artifact['smoke_command']}
```

Reviewer command reference:

- `{artifact['smoke_command']}`

Result: {artifact['smoke_execution_status']}.

Smoke checklist focus:

- `PAGE-ADB-001` remains candidate ADB analysis.
- First screen remains scoped to `/average-balance`.
- Primary API remains `{artifact['primary_api']}`.
- Supporting APIs remain `/api/analysis/adb/comparison`, `/api/analysis/adb/monthly`, `/api/analysis/adb/coverage`, and `/ui/balance-analysis/dates`.
- Candidate, stale, fallback, no-data, low-coverage, denominator, date-range, pending-owner, and `result_meta` states remain manual review targets.
- `MTR-ADB-001` and `MTR-ADB-002` remain daily DTO sample-bound to `GS-AVERAGE-BALANCE-A`; `MTR-ADB-003` remains monthly ADB/NIM pending.

## Page Verification Command

Command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File {artifact['verify_command']}
```

Reviewer command reference:

- `{artifact['verify_command']}`

Result: {artifact['verify_execution_status']}.

Verification focus:

- ADB API and governance tests.
- AverageBalance page/view model tests.
- Browser a11y smoke for `@average-balance`.
- Frontend typecheck, debt audit, and production build.

## Readiness Snapshot

Command:

```powershell
{artifact['readiness_command']}
```

Observed status:

- `overall_status={artifact['overall_status']}`
- `audit_review.status={artifact['audit_review_status']}`
- `formal_use_allowed={str(artifact['formal_use_allowed']).lower()}`
- `closure_approved={str(artifact['closure_approved']).lower()}`
- `business_owner_approval_captured={str(artifact['business_owner_approval_captured']).lower()}`

UI/API payload review remains tied to `{artifact['golden_sample_payload']}`.

## Non-Claims

This artifact:

- does not approve closure
- does not set `closure_approved=true`
- does not capture business-owner approval
- does not mark live smoke review complete in the canonical owner template
- does not approve `GS-AVERAGE-BALANCE-A`
- does not write governance records
- does not certify Average Balance as formal balance truth
- does not approve monthly ADB/NIM truth

## Evidence Scope

- `approves_metric_or_page={str(evidence_scope['approves_metric_or_page']).lower()}`
- `writes_governance_records={str(evidence_scope['writes_governance_records']).lower()}`
- `proves_page_execution={str(evidence_scope['proves_page_execution']).lower()}`
- `captures_business_owner_approval={str(evidence_scope['captures_business_owner_approval']).lower()}`
- `certification_effect={evidence_scope['certification_effect']}`
- `approves_formal_balance_truth={str(evidence_scope['approves_formal_balance_truth']).lower()}`
- `approves_monthly_adb_nim_truth={str(evidence_scope['approves_monthly_adb_nim_truth']).lower()}`

## Owner Review Handling

The owner can use this artifact as the durable live smoke evidence reference for the pending pre-signature review action. The canonical owner-state artifact remains `docs/pnl/average-balance-business-owner-approval-template.md`, and the live smoke action stays pending until the owner marks `Live smoke evidence reviewed: yes` there.
"""


def _payload(artifact: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact_kind": artifact["artifact_kind"],
        "artifact_path": artifact["artifact_path"],
        "page_id": artifact["page_id"],
        "page_slug": artifact["page_slug"],
        "smoke_execution_status": artifact["smoke_execution_status"],
        "verify_execution_status": artifact["verify_execution_status"],
        "formal_use_allowed": artifact["formal_use_allowed"],
        "closure_approved": artifact["closure_approved"],
        "business_owner_approval_captured": artifact[
            "business_owner_approval_captured"
        ],
        "evidence_scope": artifact["evidence_scope"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Build a durable average-balance live smoke evidence artifact.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help="Markdown evidence path to write.",
    )
    parser.add_argument(
        "--smoke-status",
        default="passed",
        choices=("passed", "blocked", "failed"),
        help="Observed smoke execution status to record.",
    )
    parser.add_argument(
        "--verify-status",
        default="passed",
        choices=("passed", "blocked", "failed"),
        help="Observed page verification execution status to record.",
    )
    parser.add_argument(
        "--created-date",
        default=date.today().isoformat(),
        help="Evidence date in YYYY-MM-DD format.",
    )
    args = parser.parse_args(argv)

    output_path = Path(args.output)
    artifact = build_artifact(
        output_path=output_path,
        smoke_status=args.smoke_status,
        verify_status=args.verify_status,
        created_date=args.created_date,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_markdown(artifact), encoding="utf-8")
    print(json.dumps(_payload(artifact), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
