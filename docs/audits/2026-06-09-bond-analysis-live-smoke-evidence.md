# Bond Analysis Live Smoke Evidence

Date: 2026-06-09
Page ID: `PAGE-BOND-ANALYSIS-001`
Page slug: `bond-analysis`
frontend_route: /bond-analysis
primary_api: /api/bond-analytics/action-attribution
execution_status: passed

## Scope

This artifact records the live smoke evidence reference for the `bond-analysis` owner-review packet set. It does not approve closure, does not capture business-owner approval, does not write governance records, and does not certify fixed-income analytical metrics as formal truth.

Boundary status preserved:

- `formal_use_allowed=false`
- `closure_approved=false`
- `business_owner_approval_captured=false`
- `approval_status=pending`

## Live Smoke Command

Command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/codex-page-smoke.ps1 -PageSlug bond-analysis
```

Reviewer command reference:

- `scripts/codex-page-smoke.ps1 -PageSlug bond-analysis`

Result: passed.

Smoke checklist focus:

- Route-specific page contract remains `PAGE-BOND-ANALYSIS-001`.
- First screen remains scoped to `/bond-analysis`.
- Primary API remains `/api/bond-analytics/action-attribution`.
- Candidate fixed-income values keep stale, fallback, warning, no-data, and partial states visible.
- DV01, duration, KRD, yield/YTM, bp movement, credit-spread, holdings, accounting-class, and action-attribution PnL remain manual review targets.
- `result_meta` remains the expected provenance surface for source, rule, cache, generated time, fallback, and stale state review.

## Readiness Snapshot

Command:

```powershell
python scripts/codex_page_readiness.py --page-slug bond-analysis
```

Observed status:

- `overall_status=static-pass`
- `audit_review.status=ready_for_audit_review`
- `formal_use_allowed=false`
- `closure_approved=false`
- `business_owner_approval_captured=false`

UI/API payload review remains tied to `tests/golden_samples/GS-BOND-ANALYSIS-ACTION-ATTR-A/response.json`.

## Non-Claims

This artifact:

- does not approve closure
- does not set `closure_approved=true`
- does not capture business-owner approval
- does not mark live smoke review complete in the canonical owner template
- does not approve `GS-BOND-ANALYSIS-ACTION-ATTR-A`
- does not write governance records
- does not certify Bond Analysis as formal fixed-income truth

## Evidence Scope

- `approves_metric_or_page=false`
- `writes_governance_records=false`
- `proves_page_execution=false`
- `captures_business_owner_approval=false`
- `certification_effect=none`

## Owner Review Handling

The owner can use this artifact as the durable live smoke evidence reference for the pending pre-signature review action. The canonical owner-state artifact remains `docs/pnl/bond-analysis-business-owner-approval-template.md`, and the live smoke action stays pending until the owner marks `Live smoke evidence reviewed: yes` there.
