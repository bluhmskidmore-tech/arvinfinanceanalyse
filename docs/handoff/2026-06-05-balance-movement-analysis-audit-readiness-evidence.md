# Balance Movement Analysis Audit-Readiness Evidence

Status timestamp: 2026-06-06

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
- The local MCP evidence packet previously reported manual blockers:
  `ui_api_payload_review` and `business_owner_approval`. This packet now
  records the UI/API payload review evidence; business-owner approval remains
  pending.

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
| Browser first-screen evidence | Isolated Playwright screenshot for `http://127.0.0.1:5888/balance-movement-analysis` | Captured `docs/handoff/balance-movement-analysis-first-screen-2026-06-05.png`; report date `2026-05-31`, currency `CNX`, freshness strip, evidence strip, and main conclusion visible |
| Live UI/API payload review | `Invoke-RestMethod` for `/ui/balance-movement-analysis/dates` and `/ui/balance-movement-analysis?report_date=2026-05-31&currency_basis=CNX` | Dates/detail payloads returned formal CNX data, `quality_flag=ok`, `fallback_mode=none`, freshness `fresh`, matched buckets `3/3`, `reconciliation_diff_total=0E-8`, `evidence_rows=192` |

## Browser Evidence

Attempted Browser/Playwright MCP page verification and then isolated
Playwright verification.

Result:

- The in-app Browser opened `http://localhost:5888/balance-movement-analysis`
  and confirmed the page route/title/H1, but the screenshot/evaluate path hit a
  CDP `Page.getFrameTree` timeout.
- Independent isolated Playwright succeeded and captured:
  `docs/handoff/balance-movement-analysis-first-screen-2026-06-05.png`.

Captured first-screen state:

- Page: `余额变动分析`.
- Report date selector: `2026-05-31`.
- Currency basis selector: `CNX`.
- Freshness strip: `数据已同步`; upstream and read-model dates both
  `2026-05-31`.
- Evidence strip: `QUALITY_FLAG ok`, trace ID
  `tr_balance_movement_2026-05-31_CNX`, source tables shown, and
  `EVIDENCE_ROWS 192`.
- Main conclusion: `2026-05-31 合计 3,315.74 亿`.
- Branch-state rendering for unsupported/no-data/low-coverage states is verified
  by `frontend/src/test/BalanceMovementAnalysisPage.test.tsx`, not by a live
  screenshot.

Residual risk:

- The in-app Browser screenshot/evaluate tooling still needs separate repair if
  that exact tool path is required. Current first-screen visual evidence is
  covered by isolated Playwright, not by the in-app Browser screenshot path.

## UI/API Payload Evidence

Fresh live payload review was rerun on 2026-06-06 after confirming the backend
API was listening on `127.0.0.1:7888`.

Dates endpoint:

- URL: `http://127.0.0.1:7888/ui/balance-movement-analysis/dates`
- `trace_id`: `tr_balance_movement_dates`
- `result_kind`: `balance-analysis.movement.dates`
- `basis`: `formal`
- `formal_use_allowed`: `true`
- `quality_flag`: `ok`
- `fallback_mode`: `none`
- `currency_basis`: `CNX`
- `latest_read_model_report_date`: `2026-05-31`
- `latest_upstream_control_report_date`: `2026-05-31`
- `freshness_status`: `fresh`
- `tables_used`: `fact_accounting_asset_movement_monthly`,
  `product_category_pnl_canonical_fact`

Detail endpoint:

- URL:
  `http://127.0.0.1:7888/ui/balance-movement-analysis?report_date=2026-05-31&currency_basis=CNX`
- `trace_id`: `tr_balance_movement_2026-05-31_CNX`
- `result_kind`: `balance-analysis.movement.detail`
- `basis`: `formal`
- `formal_use_allowed`: `true`
- `quality_flag`: `ok`
- `fallback_mode`: `none`
- `report_date`: `2026-05-31`
- `currency_basis`: `CNX`
- `row_count`: 3
- `bucket_count`: 3
- `matched_bucket_count`: 3
- `reconciliation_diff_total`: `0E-8`
- `evidence_rows`: 192
- `tables_used`: `fact_accounting_asset_movement_monthly`,
  `product_category_pnl_canonical_fact`,
  `fact_formal_zqtz_balance_daily`
- `source_surface`: `formal_balance`

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
| `moss-lineage-evidence.get_page_governance_audit_evidence_packet` | `audit_review_status=ready_for_audit_review`, `closure_approved=false`, manual blockers previously included `ui_api_payload_review` and `business_owner_approval`; this packet supplies UI/API payload review evidence, but does not write back governance state |

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
- `docs/handoff/balance-movement-analysis-first-screen-2026-06-05.png`

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
- Review the current first-screen screenshot and UI/API payload evidence in this
  packet.
- Record business-owner approval separately before any closure claim.

## Residual Risks

- The in-app Browser screenshot/evaluate path hit a CDP timeout; isolated
  Playwright visual evidence is captured.
- Business-owner approval is not captured.
- The page has no dedicated golden sample.
- The page remains `candidate_or_pending`; formal metric/page approval is not
  granted by this packet.
- The dirty worktree contains many unrelated changes that must stay separated
  during review.

## Next Action

Move to business-owner/UAT review for `/balance-movement-analysis`, using this
packet's first-screen screenshot and UI/API payload evidence. Do not claim page
closure until owner approval and the dedicated golden-sample boundary are
resolved or explicitly waived by the governance process.
