# Balance Analysis Live Smoke Evidence

Date: 2026-06-07
Page ID: `PAGE-BALANCE-001`
Page slug: `balance-analysis`
frontend_route: /balance-analysis
primary_api: /ui/balance-analysis/overview
execution_status: pass

## Scope

This artifact records the live smoke evidence captured for the `balance-analysis` owner-review packet set. It does not approve closure, does not capture business-owner approval, does not write governance records, and does not certify downstream analytical balance surfaces.

Boundary status preserved:

- `formal_use_allowed=true`
- `closure_approved=false`
- `business_owner_approval_captured=false`
- `approval_status=pending`

## Live Smoke Command

Command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/codex-page-smoke.ps1 -PageSlug balance-analysis -CheckLive
```

Reviewer command reference:

- `scripts/codex-page-smoke.ps1 -PageSlug balance-analysis -CheckLive`

Result: passed.

Observed live checks:

- API health reachable.
- Frontend route reachable: `/balance-analysis`.
- Page API reachable: `/ui/balance-analysis/dates`.
- Page API reachable: `/ui/balance-analysis/overview`.
- Supporting APIs that may require parameters, external data, or mutation were skipped by the smoke helper as designed.

Smoke checklist focus:

- First screen answers the formal balance truth question.
- Report date selector, position scope, currency basis, overview totals, formal meta panel, and workbook navigation remain the review focus.
- No-data, stale-data, fallback, and loading-failure states remain owner-review targets.
- `result_meta` remains the expected provenance surface for basis, quality flag, fallback mode, trace id, source version, rule version, cache version, and generated time.
- Overview totals remain tied to `fact_formal_zqtz_balance_daily` and `fact_formal_tyw_balance_daily`.

## Readiness Snapshot

Command:

```powershell
python scripts/codex_page_readiness.py --page-slug balance-analysis
```

Observed status:

- `approval_status=formal_or_governed`
- `formal_use_allowed=true`
- `overall_status=static-pass`
- `audit_review.status=ready_for_audit_review`
- `audit_review.closure_approved=false`
- `business_owner_approval_captured=false`
- `approval_action_item_count=11`

## Full Verify Status

Command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/codex-verify-page.ps1 -PageSlug balance-analysis -Run
```

Result: blocked before page-specific checks completed.

Blocking evidence:

- `tests/test_project_mcp_servers.py` reported `187 passed` and `9 failed`.
- The failures show `balance-analysis` is now present in ready-for-audit-review rows where older assertions still expected it in record-gap routing. This is a global MCP expectation mismatch, not a live smoke reachability failure.

Follow-up isolation command:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/codex-verify-page.ps1 -PageSlug balance-analysis -Run -SkipMcpContracts
```

Result: blocked in the page backend test slice.

Blocking evidence:

- `tests/test_balance_analysis_api.py tests/test_balance_analysis_consumer_surface.py` reported `33 passed` and `1 failed`.
- Failing test: `test_balance_analysis_read_surface_allows_development_fallback_without_explicit_scope`.
- Observed failure: expected HTTP `200`, received HTTP `403`.
- This appears tied to the current auth/route-policy state and remains outside this live-smoke evidence-linking lane.

## Non-Claims

This artifact:

- does not approve closure
- does not set `closure_approved=true`
- does not capture business-owner approval
- does not mark live smoke review complete in the canonical owner template
- does not approve `GS-BAL-OVERVIEW-A`
- does not write governance records
- does not resolve the full verify blockers listed above

## Owner Review Handling

The owner can use this artifact as the durable live smoke evidence reference for the pending pre-signature review action. The canonical owner-state artifact remains `docs/pnl/balance-analysis-business-owner-approval-template.md`, and the live smoke action stays pending until the owner marks `Live smoke evidence reviewed: yes` there.
