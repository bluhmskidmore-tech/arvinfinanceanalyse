# 2026-06-02 System Audit First Pass

Scope: current dirty worktree in `F:\MOSS-V3`.

This report started as an evidence-first first pass and now includes the 2026-06-03 continuation fixes and verification. The worktree already contained many modified and untracked files before this report was added; this update only records the current evidence and the small fixes made while closing red gates.

## Executive Verdict

Release posture: **core automated gates are now green**, but do not call this release-ready until the direct business MCP evidence gap and broad backend Ruff debt are addressed or formally accepted.

Current top blockers:

1. **P2 - Broad backend Ruff debt remains high.** Focused Ruff for touched backend/test files passes; the earlier broad backend scan reported 962 existing issues.
2. **P2 - Page-level MCP trace bundle coverage is still partial.** Local MCP fallback evidence now directly reads the MOSS metric-contract, data-catalog, data-quality, and lineage providers. Seeded page trace bundles now cover 6 of 26 page-contract IDs: `PAGE-DASH-001`, `PAGE-RISK-001`, `PAGE-BALANCE-001`, `PAGE-PNL-001`, `PAGE-BRIDGE-001`, and `PAGE-PROD-CAT-PNL-001`; 20 page contracts still lack bundles.
3. **P2 - Direct business MCP tools were not exposed in the current Codex App tool surface.** `codex mcp list` confirms the MOSS MCP servers are registered and enabled, and MCP server tests pass. This continuation used the equivalent local JSON-RPC MCP process instead of direct deferred `moss-*` tool calls.
4. **P2 - Full data-catalog/date-lineage review is still incomplete.** Automated tests are green and `PAGE-RISK-001` is now bundle-backed and page-evidence checked, but every governed metric page has not yet been re-audited with contract/catalog/lineage evidence.

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
- `scripts/mcp/moss_project_mcp.py`
  - Root cause: `PAGE-RISK-001` had contract, table, service, frontend, and test evidence, but was not first-class in the MCP page trace bundle workflow.
  - Fix: add the seeded `risk-tensor` bundle with route/API, contract docs, formal table lineage, backend/frontend/test touchpoints, golden samples, warning-quality focus, and guardrails.
  - Follow-up fix: add `PAGE-PROD-CAT-PNL-001` as an alias for the existing `product-category-pnl` bundle so the page-contract namespace and older `PAGE-PROD-CAT-001` namespace both resolve to the same governed surface.
  - Follow-up fix: add the seeded `pnl-bridge` bundle for `PAGE-BRIDGE-001` with `/pnl-bridge`, `/api/pnl/bridge`, contract docs, formal PnL bridge tables, backend/frontend/test touchpoints, `GS-BRIDGE-A`, `GS-BRIDGE-WARN-B`, and warning/fallback guardrails.
- `tests/test_project_mcp_servers.py`
  - Added regression coverage that `risk-tensor`, `/risk-tensor`, and `PAGE-RISK-001` resolve through `get_page_trace_bundle`, while unknown pages still fail with the supported-page list.
  - Added regression coverage that `PAGE-PROD-CAT-PNL-001` resolves through the existing `product-category-pnl` bundle.
  - Added regression coverage that `pnl-bridge`, `/pnl-bridge`, `PAGE-BRIDGE-001`, and `/api/pnl/bridge` resolve through `get_page_trace_bundle`, with bridge warning/source boundaries preserved.
- `docs/audits/2026-06-02-system-audit-first-pass.md`
  - Added the follow-up `risk-tensor` page evidence check: bundle path existence, live service payload, lineage query outcome, and targeted backend/frontend verification results.
  - Added the current page-contract-to-bundle coverage matrix and next-pass priority list, then updated it after the `PAGE-BRIDGE-001` bundle was seeded.

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

### Resolved - `PAGE-RISK-001` risk tensor is now page-bundle seeded

Evidence from the 2026-06-03 local MCP fallback deep dive:

- `moss-metric-contracts` resources were read through the repository's local JSON-RPC MCP process. The provider exposes `page_contracts`, `calc_rules`, `metric_dictionary`, `product_category_truth`, and `golden_sample_catalog`; all five documents exist, and the summary reports 13 golden samples.
- `search_contract_docs` finds `PAGE-RISK-001` in `docs/page_contracts.md` and `GS-RISK-A` / `GS-RISK-WARN-B` in `docs/metric_dictionary.md`.
- Before this continuation, `get_page_trace_bundle({"page_slug": "risk-tensor"})` returned: `Unknown page_slug: risk-tensor. Supported pages: dashboard-home, product-category-pnl`.
- After this continuation, the seeded bundle resolves `risk-tensor`, `/risk-tensor`, and `PAGE-RISK-001`, and the supported-page error path now includes `risk-tensor` while still rejecting unknown pages.
- `moss-data-catalog` confirms `data/moss.duckdb` exists, the catalog has 63 tables, the DuckDB schema registry has 28 files, and `fact_formal_risk_tensor_daily` exists as a base table with 32 columns matching `backend/app/schema_registry/duckdb/04_risk_tensor.sql`.
- Available `fact_formal_risk_tensor_daily.report_date` values include `2026-04-30` through `2026-04-21` in the latest 10-date sample. A direct read-only aggregate found 486 rows and no nulls across the 32 governed columns.
- `moss-data-quality` reports `fact_formal_risk_tensor_daily` as a quality target with 486 rows, date coverage from `2024-01-01` to `2026-04-30`, and zero nulls in the profiled columns.
- A latest-row read for `2026-04-30` shows `quality_flag='warning'`, `bond_count=1740`, `source_version='sv_risk_tensor__sv_9fb22785cd6d__sv_6fc58f4138f3'`, `upstream_source_version='sv_9fb22785cd6d'`, `liability_source_version='sv_6fc58f4138f3'`, `liability_rule_version='rv_snapshot_zqtz_tyw_v1'`, `rule_version='rv_risk_tensor_formal_materialize_v2'`, `cache_version='cv_risk_tensor_formal__rv_risk_tensor_formal_materialize_v2'`, `trace_id='trace_risk_tensor_20260430'`, and non-null `regulatory_dv01`.
- The same row carries explicit warnings: non-standard tenor buckets remapped, unsupported `6M` tenor excluded, 128 market-value rows excluded from the portfolio duration denominator, 123 rows without maturity date excluded from liquidity gap calculation, and 1397 liability rows without maturity date excluded from liquidity gap calculation.
- Code path evidence is present: `/api/risk/tensor/dates` and `/api/risk/tensor` route through `backend/app/api/routes/risk_tensor.py`; `risk_tensor_envelope()` reads `RiskTensorRepository.fetch_risk_tensor_row()`, promotes values into `RiskTensorPayload`, and builds a formal result envelope with lineage metadata; the frontend consumes `getRiskTensorDates()` and `getRiskTensor(reportDate)` through `frontend/src/api/executiveClient.ts` and displays quality/source/rule metadata in `frontend/src/features/risk-tensor/RiskTensorPage.tsx`.
- Fresh verification: `python -m pytest tests/test_project_mcp_servers.py -q` passed with `15 passed`; `python -m ruff check scripts/mcp/moss_project_mcp.py tests/test_project_mcp_servers.py` passed; `git diff --check -- scripts/mcp/moss_project_mcp.py tests/test_project_mcp_servers.py` reported no whitespace errors.
- Follow-up page evidence check after seeding the bundle:
  - The bundle references 25 contract/backend/frontend/test paths, and all 25 exist in the current worktree.
  - Direct service output for `risk_tensor_dates_envelope("data/moss.duckdb", "data/governance")` returns 486 unblocked report dates, latest `2026-04-30`, and formal metadata with `source_surface="risk_tensor"`.
  - Direct service output for `risk_tensor_envelope(..., "2026-04-30")` returns `quality_flag="warning"`, `regulatory_dv01.raw=108230899.46003927`, `duration_excluded_count=128`, `duration_excluded_market_value.raw=47813495391.86`, and the five warning messages listed above. The exclusion count is a service/payload field derived from the rate-risk duration scope path, not a stored column on `fact_formal_risk_tensor_daily`.
  - The formal table currently has 32 columns, 486 rows, date coverage from `2024-01-01` to `2026-04-30`, and no nulls across those stored columns.
  - Local `moss-lineage-evidence` fallback query still returns 0 records for `PAGE-RISK-001`; it returns agent-audit records for `risk_tensor` and `fact_formal_risk_tensor_daily`.

Impact: `risk-tensor` now has a canonical MCP page trace bundle containing route, API, source lineage anchors, metrics, golden samples, code touchpoints, tests, and guardrails. The latest sampled data still has `warning` quality, so release messaging must preserve warning visibility.

Remaining risk: direct `PAGE-RISK-001` lineage search still did not produce a page-level lineage hit, and every governed metric page has not yet received the same contract/catalog/lineage/bundle audit.

### P2 - Page-contract trace bundle coverage remains sparse

Evidence from the 2026-06-03 page-contract coverage matrix:

- `docs/page_contracts.md` currently exposes 26 `PAGE-*` page-contract IDs.
- `product_page_trace_bundles()` now resolves 6 page-contract IDs:
  - `PAGE-DASH-001` -> `dashboard-home`
  - `PAGE-RISK-001` -> `risk-tensor`
  - `PAGE-BALANCE-001` -> `balance-analysis`
  - `PAGE-PNL-001` -> `pnl`
  - `PAGE-BRIDGE-001` -> `pnl-bridge`
  - `PAGE-PROD-CAT-PNL-001` -> `product-category-pnl`
- The `product-category-pnl` bundle also keeps the older `PAGE-PROD-CAT-001` alias. A red/green MCP regression was run for the page-contract ID: before the alias fix, `PAGE-PROD-CAT-PNL-001` failed as unknown with `1 failed, 14 passed`; after the alias fix, `tests/test_project_mcp_servers.py` passed with `15 passed`.
- The `pnl-bridge` bundle covers `/pnl-bridge`, `/api/pnl/bridge`, `PnlBridgePayload`, formal bridge tables, backend/frontend/test touchpoints, and both bridge golden samples. A red/green MCP regression was run: before the bundle, `pnl-bridge` failed as unknown with `2 failed, 15 passed`; after the bundle, `tests/test_project_mcp_servers.py` passed with `17 passed`.
- The `balance-analysis` bundle covers `/balance-analysis`, `/ui/balance-analysis/overview`, formal balance fact tables, workbook and decision-item touchpoints, and both balance golden samples. A red/green MCP regression was run: before the bundle, `balance-analysis` failed as unknown with `2 failed, 17 passed`; after the bundle, `tests/test_project_mcp_servers.py` passed with `19 passed`.
- The `pnl` bundle covers `/pnl`, `/api/pnl/overview`, `/api/pnl/data`, formal PnL fact tables, overview/data DTOs, and both formal PnL golden samples. A red/green MCP regression was run: before the bundle, `pnl` failed as unknown with `2 failed, 19 passed`; after the bundle, `tests/test_project_mcp_servers.py` passed with `21 passed`.
- 20 page-contract IDs still lack a seeded bundle. Highest metric-count missing pages:
  - `PAGE-LIAB-ANALYTICS-001` (`/liability-analytics`, 7 metrics)
  - `PAGE-EXEC-PNL-ATTR-001` and `PAGE-PNL-ATTR-WB-001` (6 metrics each)
  - `PAGE-OPS-001` (5 metrics)
  - `PAGE-EXEC-OVERVIEW-001` and `PAGE-BAL-MOVE-001` (4 metrics each)
  - `PAGE-LEDGER-PNL-001` (3 metrics)
- Additional page contracts without seeded bundles have no current `MTR-*` bindings or only low-count bindings, but still need explicit governance boundaries before release claims: `PAGE-EXEC-SUMMARY-001`, `PAGE-BOND-001`, `PAGE-POS-001`, `PAGE-MKT-001`, `PAGE-MACRO-TOOLKIT-001`, `PAGE-MACRO-OBS-001`, `PAGE-AGENT-001`, `PAGE-CUBE-QUERY-001`, `PAGE-PORTFOLIO-HOME-001`, `PAGE-MARKET-HOME-001`, `PAGE-RISK-HOME-001`, `PAGE-PERFORMANCE-HOME-001`, and `PAGE-REPORTS-HOME-001`.

Impact: the bundle workflow is now useful for the six seeded pages, but cannot yet support a full system-wide page-level closure claim. The next bundle work should prioritize pages with the most formal metrics and highest business-decision impact.

Recommendation: continue seeding bundles in descending business-risk order, starting with `PAGE-LIAB-ANALYTICS-001`, `PAGE-EXEC-PNL-ATTR-001`, and `PAGE-PNL-ATTR-WB-001`, then validate each with contract/API/service/frontend/test/golden-sample evidence before moving to lower-metric or navigation/home surfaces.

## Positive Evidence

- `codex mcp list` confirms `gitnexus`, `moss-data-catalog`, `moss-data-quality`, `moss-lineage-evidence`, and `moss-metric-contracts` are registered and enabled.
- `python -m pytest tests/test_project_mcp_servers.py -q`: latest focused MCP continuation run passed with `21 passed`.
- Local MCP fallback evidence:
  - `moss-metric-contracts`: resources and tools are callable through the repository's JSON-RPC MCP process; contract docs exist; seeded trace bundles are available for `product-category-pnl`, `dashboard-home`, `balance-analysis`, `pnl`, `pnl-bridge`, and `risk-tensor`.
  - `moss-data-catalog`: `data/moss.duckdb` exists; 63 tables were inventoried; `fact_formal_risk_tensor_daily` is present with latest sampled dates through `2026-04-30`.
  - `moss-data-quality`: `fact_formal_risk_tensor_daily` is a quality target with 486 rows and date coverage from `2024-01-01` to `2026-04-30`.
  - `moss-lineage-evidence`: governance streams exist and are readable; direct search found `risk_tensor` / `fact_formal_risk_tensor_daily` agent-audit records, but no `PAGE-RISK-001` page-level lineage record.
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
- Focused MCP bundle check after the `risk-tensor` trace-bundle continuation:
  - `python -m ruff check scripts/mcp/moss_project_mcp.py tests/test_project_mcp_servers.py`
  - Result: passed.
  - `git diff --check -- scripts/mcp/moss_project_mcp.py tests/test_project_mcp_servers.py`
  - Result: passed.
- Product-category page-contract alias check:
  - Red check before implementation: `python -m pytest tests/test_project_mcp_servers.py -q` failed with `1 failed, 14 passed` because `PAGE-PROD-CAT-PNL-001` was unknown.
  - Green check after implementation: `python -m pytest tests/test_project_mcp_servers.py -q` passed with `15 passed`.
- PnL Bridge page-contract bundle check:
  - Red check before implementation: `python -m pytest tests/test_project_mcp_servers.py -q` failed with `2 failed, 15 passed` because `pnl-bridge` was unknown.
  - Green check after implementation: `python -m pytest tests/test_project_mcp_servers.py -q` passed with `17 passed`.
  - Focused bridge logic/service boundary check: `python -m pytest tests/test_pnl_bridge_core.py tests/test_pnl_bridge_curve_effects.py tests/test_pnl_bridge_fx_translation.py tests/test_pnl_bridge_with_curve.py tests/test_pnl_bridge_numeric_migration.py tests/test_pnl_bridge_service_boundaries.py -q` passed with `39 passed`.
  - API contract and golden-sample check: `python -m pytest tests/test_pnl_api_contract.py tests/test_golden_samples_capture_ready.py -q` passed with `90 passed`.
  - Frontend page check: `npm run test -- src/test/PnlBridgePage.test.tsx` from `frontend/` passed with `1` test file and `6` tests.
- Balance Analysis page-contract bundle check:
  - Red check before implementation: `python -m pytest tests/test_project_mcp_servers.py -q` failed with `2 failed, 17 passed` because `balance-analysis` was unknown.
  - Green check after implementation: `python -m pytest tests/test_project_mcp_servers.py -q` passed with `19 passed`.
  - Focused balance backend/API/contract/workbook check: `python -m pytest tests/test_balance_analysis_api.py tests/test_balance_analysis_contracts.py tests/test_balance_analysis_core.py tests/test_balance_analysis_materialize_flow.py tests/test_balance_analysis_service.py tests/test_balance_analysis_boundary_guards.py tests/test_balance_analysis_workbook_contract.py tests/test_balance_analysis_module_registration_flow.py tests/test_golden_samples_capture_ready.py -q` passed with `112 passed`.
  - Frontend page check: `npm run test -- src/test/BalanceAnalysisPage.test.tsx` from `frontend/` passed with `1` test file and `24` tests.
- Formal PnL page-contract bundle check:
  - Red check before implementation: `python -m pytest tests/test_project_mcp_servers.py -q` failed with `2 failed, 19 passed` because `pnl` was unknown.
  - Green check after implementation: `python -m pytest tests/test_project_mcp_servers.py -q` passed with `21 passed`.
  - Focused formal PnL backend/API/core/materialize check: `python -m pytest tests/test_pnl_api_contract.py tests/test_pnl_formal_semantics_contract.py tests/test_pnl_core_finance_contract.py tests/test_pnl_materialize_flow.py tests/test_golden_samples_capture_ready.py -q` passed with `107 passed`.
  - Frontend page/routes check: `npm run test -- src/test/PnlPage.test.tsx src/test/PnlRoutesSmoke.test.tsx` from `frontend/` passed with `2` test files and `17` tests.
- Focused `risk-tensor` page evidence verification after the bundle check:
  - `python -m pytest tests/test_risk_tensor_api.py tests/test_risk_tensor_service.py tests/test_risk_tensor_repo.py tests/test_risk_tensor_core.py tests/test_risk_tensor_materialize.py tests/test_risk_tensor_numeric_migration.py tests/test_risk_tensor_liquidity.py tests/test_golden_samples_capture_ready.py -q`
  - Result: `82 passed`.
  - `npm run test -- src/test/RiskTensorPage.test.tsx` from `frontend/`
  - Result: `1 passed` test file, `40 passed` tests.

## Evidence Gaps

- Direct `moss-*` MCP tools were not exposed in the current Codex App deferred tool surface. `tool_search` exposed Playwright/GitHub/Canva/Node tools, but not `moss-metric-contracts`, `moss-lineage-evidence`, `moss-data-catalog`, `moss-data-quality`, or `gitnexus` callable tools. This continuation used the local JSON-RPC MCP process as a read-only fallback and records that distinction.
- `PAGE-RISK-001` / `risk-tensor` now has sampled contract/catalog/data-quality evidence, a seeded MCP page trace bundle, and a focused page evidence check, but it still lacks a direct `PAGE-RISK-001` lineage hit.
- Page-level MCP bundle coverage is 6 of 26 page-contract IDs; 20 page contracts still need seeded bundles or explicit approved non-bundle rationale.
- No full data-catalog/date lineage review was completed for every metric page.
- Browser axe now completes for the four covered smoke pages, but broader page coverage is not complete.

## Recommended Next Pass

1. Add a direct `PAGE-RISK-001` lineage record or an explicit approved mapping from `PAGE-RISK-001` to the existing `risk_tensor` / `fact_formal_risk_tensor_daily` lineage records.
2. Seed and verify page trace bundles for `PAGE-LIAB-ANALYTICS-001`, `PAGE-EXEC-PNL-ATTR-001`, and `PAGE-PNL-ATTR-WB-001`; these are the highest metric-count missing governed pages after `PAGE-BRIDGE-001`, `PAGE-BALANCE-001`, and `PAGE-PNL-001`.
3. Decide whether the broad backend Ruff backlog is a release blocker or a separately tracked cleanup stream.
4. Use direct MOSS MCP contract/lineage/catalog tools when exposed, or invoke the equivalent project scripts, to audit source lineage and date semantics for ledger-pnl, stock-analysis, agent workbench, commodity ingest, and the remaining governed metric pages; add page bundles where those audits find gaps.
5. Keep the updated a11y smoke in the release gate, and add page-specific ready selectors as new browser smoke pages are covered.
