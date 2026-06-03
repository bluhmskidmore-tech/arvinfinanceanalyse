# 2026-06-02 System Audit First Pass

Scope: current dirty worktree in `F:\MOSS-V3`.

This report started as an evidence-first first pass and now includes the 2026-06-03 continuation fixes and verification. The worktree already contained many modified and untracked files before this report was added; this update only records the current evidence and the small fixes made while closing red gates.

## Executive Verdict

Release posture: **core automated gates are now green**, but do not call this release-ready until the direct business MCP evidence gap and broad backend Ruff debt are addressed or formally accepted.

Current top blockers:

1. **P2 - Broad backend Ruff debt remains high.** Focused Ruff for touched backend/test files passes; the earlier broad backend scan reported 962 existing issues.
2. **P2 - Direct business MCP evidence tools were not exposed in the current Codex App tool surface.** `codex mcp list` confirms the MOSS MCP servers are registered and enabled, and MCP server tests pass, but direct `moss-*` tool calls were unavailable through this session's deferred tool surface.
3. **P2 - Full data-catalog/date-lineage review is still incomplete.** Automated tests are green, but every governed metric page has not yet been re-audited with direct catalog/lineage/contract evidence.

## Audit Health Score

| # | Dimension | Score | Key finding |
|---|---:|---:|---|
| 1 | Accessibility | 3/4 | Critical axe smoke now passes the four covered pages; broader page coverage is still incomplete. |
| 2 | Performance / runtime stability | 4/4 | Frontend build/unit/smoke gates and full backend pytest are green. |
| 3 | Theming | 3/4 | Theme guard now passes after restoring the bond-analysis selector ownership boundary; broad global CSS remains a risk area. |
| 4 | Responsive design | 3/4 | Unit/build gates are green; browser smoke for all modified pages is not yet complete. |
| 5 | Anti-patterns / maintainability | 3/4 | Frontend debt audit passes no-growth baseline and focused Ruff passes; broad backend Ruff debt remains outside this pass. |
| **Total** |  | **16/20** | **Core gates green; evidence gaps remain** |

## Continuation Changes

Changed during the continuation:

- `frontend/src/features/bond-analytics/utils/formatters.ts`
  - Root cause: bond analytics formatters accepted optional business values, but `coerceRaw()` dereferenced `value.raw` when `value` itself was `null`.
  - Fix: accept `null | undefined` in the formatter input surface and map nullish input to `Number.NaN`, preserving the existing `"-"` missing-value display.
- `frontend/src/test/bondAnalyticsFormatters.test.ts`
  - Added nullish-input regressions for `formatYi`, `formatWan`, `formatPct`, and `formatBp`.
- `frontend/tests/playwright/a11y-visual-smoke.spec.mjs`
  - Root cause: the smoke waited for `networkidle`, but dashboard and ledger-pnl can keep network activity alive after visible content is ready.
  - Fix: navigate on `domcontentloaded`, wait for the page-specific ready selector, then run axe against the intended surface.
- `tests/test_health_endpoints.py`
  - Root cause: the readiness contract test asked the helper to import a non-existent alias module, while the helper intentionally imports `backend.app.api.routes.*` modules by real module name to preserve route package behavior.
  - Fix: load the actual `backend.app.api.routes.health` module.
- `tests/test_commodity_daily_ingest.py`
  - Root cause: the full-suite run could reload the commodity ingest module after the test imported `run_commodity_daily_ingest`, so string-target monkeypatching could miss the function object under test.
  - Fix: patch the imported function's globals directly for the no-row fetch seam.
- `tests/test_market_data_livermore_api.py`
  - Root cause: the macro-environment signal-confluence test depended on whatever macro adversarial overlay files existed in the default local output directory; a blocking local overlay correctly downgraded entries to `observe_only`.
  - Fix: isolate this test to an empty temp overlay directory. Separate smoke coverage still exercises the real adversarial overlay loading path.
- `tests/test_no_finance_logic_in_frontend.py`
  - Root cause: the finance-logic guard flagged module-home labels and backend-field display mappings (`DV01`, `KRD`, `CS01`, `convexity`) as if they were frontend pricing logic.
  - Fix: add narrow file/line-prefix exceptions for display-only module-home copy and risk-tensor field mappings, while keeping the guard active for non-display logic.

Earlier continuation edits verified in this pass:

- `frontend/src/styles/global.css`
  - Restored the dashboard-home compatibility selector to the actual `bond-analysis-overview` owner instead of broadening it to `portfolio-home-overview`.
- `frontend/src/test/MacroToolkitPage.test.tsx`
- `frontend/src/test/RouteRegistry.test.tsx`
  - Test waits were aligned to required UI readiness states without weakening the business assertions.

## Resolved Findings

### Resolved - Frontend production build failure

Evidence:

- Command: `npm run build` from `frontend/`.
- Result: passed.
- Build completed after TypeScript project build and Vite production bundle generation.

The earlier `StockAnalysisPageModel.test.ts` fixture type failure is no longer present in the current worktree.

### Resolved - Frontend unit suite failures

Evidence:

- Command: `npm run test` from `frontend/`.
- Result: `200 passed (200)` test files, `1619 passed (1619)` tests.
- Targeted confirmations:
  - `npm run test -- src/test/bondAnalyticsFormatters.test.ts`: `13 passed`.
  - `npm run test -- src/test/BondAnalyticsInstitutionalCockpit.test.tsx src/test/BondAnalyticsView.test.tsx`: `20 passed`.
  - `npm run test -- src/test/BalanceAnalysisPage.test.tsx`: `24 passed`.

The earlier failures in balance-analysis, bond-analysis initialization, route registry, and theme guard are not reproduced in the current worktree.

### Resolved - Theme ownership guardrail

Evidence:

- Command: `npm run test -- src/test/theme.test.ts`.
- Result from the continuation: `15 passed`.
- Wider confirmation: full `npm run test` passed all frontend tests.

The `dashboard-home` compatibility selector is again rooted only to `[data-testid="bond-analysis-overview"]`.

### Resolved - Frontend debt and static gates

Evidence:

- `npm run typecheck` from `frontend/`: passed.
- `npm run lint` from `frontend/`: passed.
- `npm run debt:audit` from `frontend/`: passed with no growth over baseline.

Debt audit snapshot:

- `api/client.ts` lines: `560/560`
- `api/client.ts` mock occurrences: `55/55`
- frontend TSX style props: `2769/3308`

### Resolved - Playwright a11y smoke readiness

Evidence:

- Command: `MOSS_PLAYWRIGHT_USE_WEB_SERVER=1 MOSS_PLAYWRIGHT_PORT=5890 npm run test:a11y-smoke -- tests/playwright/a11y-visual-smoke.spec.mjs` from `frontend/`.
- Result: `4 passed`.
- Covered pages:
  - `dashboard`
  - `balance-analysis`
  - `product-category-pnl`
  - `ledger-pnl`
- Follow-up lint after the test-script edit: `npm run lint` from `frontend/` passed.

### Resolved - Long backend run exposed five local failures

Evidence from the long run:

- Command: `python -m pytest -q`.
- Result before this continuation: `5 failed, 3638 passed, 6 skipped`.
- Duration: `30011.38s (8:20:11)`.

Failures closed by this continuation:

- `tests/test_health_endpoints.py::test_ready_endpoint_returns_200_and_check_payload`
- `tests/test_commodity_daily_ingest.py::test_completed_ingest_reports_series_id_when_product_has_no_rows`
- `tests/test_market_data_livermore_api.py::test_livermore_signal_confluence_api_uses_real_service_shape_with_macro_environment_score`
- `tests/test_no_finance_logic_in_frontend.py::test_frontend_source_does_not_contain_formal_finance_logic_tokens`
- `tests/test_frontend_playwright_smoke_scaffold.py::test_frontend_playwright_smoke_scaffold_uses_safe_server_probe_and_artifacts` was stale after the Playwright smoke readiness edit and passes in targeted reruns.

Current verification:

- `python -m pytest tests/test_health_endpoints.py tests/test_commodity_daily_ingest.py tests/test_market_data_livermore_api.py::test_livermore_signal_confluence_api_uses_real_service_shape_with_macro_environment_score tests/test_no_finance_logic_in_frontend.py tests/test_frontend_playwright_smoke_scaffold.py -q`: `20 passed`.
- `python -m pytest tests/test_market_data_livermore_api.py tests/test_health_endpoints.py tests/test_commodity_daily_ingest.py tests/test_no_finance_logic_in_frontend.py tests/test_frontend_playwright_smoke_scaffold.py -q`: `53 passed`.
- `python -m ruff check tests/test_health_endpoints.py tests/test_commodity_daily_ingest.py tests/test_market_data_livermore_api.py tests/test_no_finance_logic_in_frontend.py`: passed.
- `python -m pytest --lf --last-failed-no-failures=none -q`: expanded to the full backend suite and passed with `3645 passed, 6 skipped in 1264.95s (0:21:04)`.

## Open Findings

### P2 - Broad backend lint debt remains high

Evidence from the first pass:

- Command: broad `python -m ruff check backend\app ...`.
- Result: failed with 962 errors.
- Dominant categories: import sorting (`I001`), module import position (`E402`), unused imports (`F401`), and pyupgrade (`UP017`, `UP042`).

Current focused evidence:

- Command: focused `python -m ruff check` on touched backend/test files.
- Result: passed. During the check loop, Ruff identified an import-order issue in `backend/app/api/routes/macro_toolkit.py`; the final file matches the repository baseline and has no remaining diff.

Impact: full backend lint is not a usable release gate yet, but the currently touched backend files are not the source of broad failure.

Recommendation: keep backend release checks targeted for current changes, and open a separate bounded cleanup plan for full Ruff adoption.

### P2 - Development/default credentials need boundary clarity

Evidence from the first pass:

- `backend/app/governance/settings.py:112-113` defaults MinIO access and secret keys to `minioadmin`.
- `scripts/dev_postgres_cluster.py:18-19` defaults local dev user/password to `moss`.
- Tushare token resolution uses environment/config fallback (`backend/app/repositories/tushare_adapter.py:34-42`), not a hardcoded token.
- Pattern scan found no AWS-style access keys or private keys in the searched source surface.

Impact: no evidence of a real leaked production secret in this pass, but default credentials should remain explicitly development-only and must not be accepted for production.

Recommendation: ensure deployment docs and startup validation reject default credentials outside local/dev mode.

## Positive Evidence

- `codex mcp list` confirms `gitnexus`, `moss-data-catalog`, `moss-data-quality`, `moss-lineage-evidence`, and `moss-metric-contracts` are registered and enabled.
- `python -m pytest tests/test_project_mcp_servers.py -q`: included in the API/MCP run below and passed.
- Frontend gates:
  - `npm run build`: passed.
  - `npm run test`: `200 passed`, `1619 tests passed`.
  - `npm run typecheck`: passed.
  - `npm run lint`: passed.
  - `npm run debt:audit`: passed with no growth over baseline.
  - `npm run test:a11y-smoke -- tests/playwright/a11y-visual-smoke.spec.mjs` with `MOSS_PLAYWRIGHT_USE_WEB_SERVER=1` and `MOSS_PLAYWRIGHT_PORT=5890`: `4 passed`.
- Backend targeted business tests:
  - `python -m pytest tests/test_commodity_daily_ingest.py tests/test_macro_equity_strategies.py tests/test_macro_toolkit_scripts.py tests/test_agent_eval_spec.py tests/test_product_category_mapping_contract.py -q`
  - Result: `108 passed`.
- Backend API/MCP boundary tests:
  - `python -m pytest tests/test_agent_api.py tests/test_agent_api_contract.py tests/test_agent_runs_api.py tests/test_auth_context.py tests/test_api_route_boundaries.py tests/test_project_mcp_servers.py -q`
  - Result: `43 passed`.
- Post-import-order macro confirmation:
  - `python -m pytest tests/test_macro_toolkit_scripts.py tests/test_macro_equity_strategies.py -q`
  - Result: `70 passed`.
- Full backend suite after this continuation:
  - `python -m pytest --lf --last-failed-no-failures=none -q`
  - Result: `3645 passed, 6 skipped in 1264.95s (0:21:04)`.
- Focused Ruff check for touched backend/test files: passed.
- Failure-closure suite after this continuation:
  - `python -m pytest tests/test_health_endpoints.py tests/test_commodity_daily_ingest.py tests/test_market_data_livermore_api.py::test_livermore_signal_confluence_api_uses_real_service_shape_with_macro_environment_score tests/test_no_finance_logic_in_frontend.py tests/test_frontend_playwright_smoke_scaffold.py -q`
  - Result: `20 passed`.
- Affected-file backend/frontend-guard suite after this continuation:
  - `python -m pytest tests/test_market_data_livermore_api.py tests/test_health_endpoints.py tests/test_commodity_daily_ingest.py tests/test_no_finance_logic_in_frontend.py tests/test_frontend_playwright_smoke_scaffold.py -q`
  - Result: `53 passed`.
- Focused Ruff check after this continuation:
  - `python -m ruff check tests/test_health_endpoints.py tests/test_commodity_daily_ingest.py tests/test_market_data_livermore_api.py tests/test_no_finance_logic_in_frontend.py`
  - Result: passed.

## Evidence Gaps

- Direct `moss-*` MCP tools were not exposed in the current Codex App tool surface, although MCP registration and MCP server tests passed. `tool_search` exposed Playwright/GitHub/Canva/Node tools, but not `moss-metric-contracts`, `moss-lineage-evidence`, `moss-data-catalog`, or `gitnexus` callable tools. This pass used local commands, tests, docs, and generated Playwright evidence instead of direct MCP resource reads.
- No full data-catalog/date lineage review was completed for every metric page.
- Browser axe now completes for the four covered smoke pages, but broader page coverage is not complete.

## Recommended Next Pass

1. Use direct MOSS MCP contract/lineage/catalog tools when exposed, or invoke the equivalent project scripts, to audit source lineage and date semantics for ledger-pnl, stock-analysis, risk-tensor, agent workbench, and commodity ingest.
2. Decide whether the broad backend Ruff backlog is a release blocker or a separately tracked cleanup stream.
3. Continue page-specific business evidence checks for the modified business surfaces before considering release.
4. Keep the updated a11y smoke in the release gate, and add page-specific ready selectors as new browser smoke pages are covered.
