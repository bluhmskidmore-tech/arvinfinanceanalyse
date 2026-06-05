# Balance Movement Analysis Audit-Readiness Evidence

Status timestamp: 2026-06-05

This packet records audit-readiness evidence for `/balance-movement-analysis`.
It does not approve formal metric use, close the page, capture business-owner
approval, write governance records, or change product behavior.

## Scope

In scope:

- Page/workflow: `/balance-movement-analysis`
- Page ID: `PAGE-BAL-MOVE-001`
- Primary API: `/ui/balance-movement-analysis`
- Supporting APIs: `/ui/balance-movement-analysis/dates`,
  `/ui/balance-movement-analysis/refresh`
- Evidence and handoff documentation for the current page packet

Out of scope:

- Unrelated pages, dashboard work, PnL work, bond analytics work, auth,
  scheduler/cache base, database schema, and repo-wide cleanup
- Global Playwright/MCP tooling repair
- New product behavior unless a page defect is found
- Business-owner approval capture

## Current Decision

The page is ready for audit review, not approved for closure.

Evidence:

- `scripts/codex-page-readiness.ps1` reports
  `Approval: candidate_or_pending; formal_use_allowed=False`.
- The same readiness gate reports `direct_governance_record_ready: pass`,
  `balance_movement_read_model_freshness: pass`, and
  `golden_sample_boundary: pass (missing)`.
- Local MCP fallback reports `audit_review_status: ready_for_audit_review`
  and `closure_approved: false`.
- The local MCP evidence packet reports manual blockers:
  `ui_api_payload_review` and `business_owner_approval`.

Do not read this packet as:

- formal metric approval
- dedicated golden-sample approval
- page closure
- business-owner/UAT signoff

## Fresh Evidence

These commands were run fresh in this packet.

| Evidence | Command | Result |
| --- | --- | --- |
| Page readiness gate | `powershell -ExecutionPolicy Bypass -File scripts/codex-page-readiness.ps1 -PageSlug balance-movement-analysis` | Pass-style static readiness output; page remains `candidate_or_pending`, no dedicated golden sample, owner approval pending |
| Live smoke / freshness | `powershell -ExecutionPolicy Bypass -File scripts/codex-page-smoke.ps1 -PageSlug balance-movement-analysis -CheckLive` | API and route reachable; freshness passed with `read_model=2026-05-31`, `upstream=2026-05-31`, `status=fresh` |
| Frontend page test | `npm run test -- src/test/BalanceMovementAnalysisPage.test.tsx` from `frontend/` | 1 file passed; 17 tests passed |
| Backend service/materialize/core tests | `python -m pytest tests/test_accounting_asset_movement_service.py tests/test_accounting_asset_movement_materialize.py tests/test_accounting_asset_movement_core.py -q` | 26 passed |
| Backend API tests | `python -m pytest tests/test_accounting_asset_movement_api.py -q` | 4 passed |
| Native smoke-script tests | `python -m pytest tests/test_native_dev_scripts.py::test_codex_page_smoke_supports_balance_movement_analysis_checklist_only tests/test_native_dev_scripts.py::test_codex_page_smoke_balance_movement_check_live_fails_when_report_dates_missing tests/test_native_dev_scripts.py::test_codex_page_smoke_balance_movement_check_live_passes_with_fresh_dates_payload -q` | 3 passed |
| Frontend typecheck | `npm run typecheck` from `frontend/` | Passed |
| Narrow ESLint | `npx eslint src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.tsx src/test/BalanceMovementAnalysisPage.test.tsx` from `frontend/` | Passed |
| Frontend debt audit | `npm run debt:audit` from `frontend/` | Passed; no growth over baseline |
| Frontend production build | `npm run build` from `frontend/` | Passed; Vite production build completed |
| Diff whitespace check | `git diff --check` | Exit 0; line-ending warnings only in unrelated dirty files |

## Browser Evidence

Attempted Browser/Playwright MCP page verification.

Result:

- Blocked before navigation by the existing Playwright MCP profile lock:
  `Browser is already in use for C:\Users\arvin\AppData\Local\ms-playwright\mcp-chrome-164b22a, use --isolated to run multiple instances of the same browser`.

Fallback evidence:

- Live route/API evidence comes from `scripts/codex-page-smoke.ps1 -CheckLive`.
- Current freshness is verified by the live smoke output.
- Branch-state rendering for unsupported/no-data/low-coverage states is verified
  by `frontend/src/test/BalanceMovementAnalysisPage.test.tsx`, not by a live
  screenshot.

Residual risk:

- Current browser-visible first screen still needs a successful Browser run or
  isolated Playwright MCP session before this packet can be treated as visual
  review complete.

## MCP / Governance Evidence

Direct app tool exposure:

- `tool_search` did not expose callable `moss-metric-contracts`,
  `moss-lineage-evidence`, `moss-data-catalog`, `moss-data-quality`, or
  `gitnexus` tools in this session.

Registration and fallback:

- `codex mcp list` shows `gitnexus`, `moss-data-catalog`,
  `moss-data-quality`, `moss-lineage-evidence`, and
  `moss-metric-contracts` are registered and enabled.
- `.codex/config.toml`, `.mcp.json`, and `scripts/mcp/moss_mcp_launcher.py`
  exist.
- Local JSON-RPC fallback through `scripts/mcp/moss_project_mcp.py` succeeded.

Fallback MCP summary:

| Source | Result |
| --- | --- |
| `moss-metric-contracts.get_page_trace_bundle` | `PAGE-BAL-MOVE-001`, route `/balance-movement-analysis`, primary API `/ui/balance-movement-analysis`, no golden samples, no-dedicated-golden-sample verification focus present |
| `moss-lineage-evidence.get_page_governance_audit_review_checklist` | 1 page ready for audit review, 0 record gaps, 0 closure approved |
| `moss-lineage-evidence.get_page_governance_audit_review_queue` | 1 queue item, 6 remaining manual checks, `closure_approved=false` |
| `moss-lineage-evidence.get_page_governance_audit_evidence_packet` | `audit_review_status=ready_for_audit_review`, `closure_approved=false`, manual blockers `ui_api_payload_review` and `business_owner_approval` |

The MCP evidence packet scope explicitly does not write governance records,
approve metric/page formal use, prove page execution, run UI/API smoke, or
capture business-owner approval.

## Edge-State Evidence

Unsupported/no-data/low-coverage display states are covered by targeted tests,
not by live browser state.

Fresh targeted frontend evidence:

- `frontend/src/test/BalanceMovementAnalysisPage.test.tsx` passed 17 tests.
- The test `renders backend-provided unsupported and no-data drilldown states`
  covers:
  - `basis_movement_decomposition.meta.status = no_data`
  - `zqtz_maturity_structure.meta.status = unsupported_missing_columns`
  - `zqtz_concentration_analysis.meta.status = unsupported_low_coverage`
  - concentration dimensions with missing columns, low coverage, and no data
- Freshness strip tests cover unknown freshness and read-model-lagging states.

## Dirty Worktree Boundary

The repository has extensive unrelated modified and untracked files. This
packet does not normalize, revert, or claim those changes.

Current packet-owned files:

- `docs/handoff/2026-06-05-balance-movement-analysis-audit-readiness-evidence.md`

Related prior in-flight balance-movement test evidence:

- `frontend/src/test/BalanceMovementAnalysisPage.test.tsx`

Planning/context artifacts used for this packet:

- `.omx/context/balance-movement-top-delivery-gap-closure-20260605T102155Z.md`
- `.omx/plans/2026-06-05-balance-movement-top-delivery-gap-closure.md`

All other dirty files observed in `git status --short` are out of scope for
this packet unless separately assigned.

## Business-Owner / UAT Checklist

Pending owner review items:

- Confirm the page conclusion answers the balance movement explanation question
  for the selected report date and CNX basis.
- Confirm candidate `MTR-BMV-*` metrics remain candidate-only and are not
  promoted to formal metric approval.
- Confirm no dedicated golden sample exists yet for this page-level metric
  surface.
- Review current UI/API payload evidence after Browser verification is
  unblocked or rerun in an isolated Playwright MCP session.
- Record business-owner approval separately before any closure claim.

## Residual Risks

- Browser visual verification is blocked by the current Playwright MCP profile
  lock.
- Business-owner approval is not captured.
- The page has no dedicated golden sample.
- The page remains `candidate_or_pending`; formal metric/page approval is not
  granted by this packet.
- The dirty worktree contains many unrelated changes that must stay separated
  during review.

## Next Action

Run an isolated Browser/Playwright verification for
`http://localhost:5888/balance-movement-analysis`, capture current first-screen
state, evidence strip, and freshness strip, then attach that result to this
packet before business-owner/UAT review.

