# 2026-06-02 System Audit First Pass

Scope: current dirty worktree in `F:\MOSS-V3`.

This report started as an evidence-first first pass and now includes the 2026-06-03 continuation fixes and verification. The worktree already contained many modified and untracked files before this report was added; this update only records the current evidence and the small fixes made while closing red gates.

## Executive Verdict

Release posture: **core automated gates are now green**, but do not call this release-ready until the direct business MCP evidence gap and broad backend Ruff debt are addressed or formally accepted.

Current top blockers:

1. **P2 - Broad backend Ruff debt remains high.** Focused Ruff for touched backend/test files passes; the earlier broad backend scan reported 962 existing issues.
2. **P2 - Candidate metric API metadata still overstates formal-use readiness on sampled unresolved surfaces.** Ledger PnL summary/detail, Bond Dashboard headline, Positions list-count, and Cashflow Projection metadata have been weakened away from formal-use approval while preserving source/date evidence. Follow-up samples still show the formal metadata pattern on Concentration Monitor candidate/page-contract-pending metrics.
3. **P2 - Page-level MCP trace bundle coverage now has first-pass closure.** Local MCP fallback evidence now directly reads the MOSS metric-contract, data-catalog, data-quality, and lineage providers. Seeded page trace bundles now cover 26 of 26 page-contract IDs, including the remaining Agent, Cube Query, and module-home surfaces. This closes the bundle-coverage gap, but it does not replace full data-catalog/date-lineage review for every governed metric page.
4. **P2 - Direct business MCP tools were not exposed in the current Codex App tool surface.** `codex mcp list` confirms the MOSS MCP servers are registered and enabled, and MCP server tests pass. This continuation used the equivalent local JSON-RPC MCP process instead of direct deferred `moss-*` tool calls.
5. **P2 - Full data-catalog/date-lineage review is still incomplete.** Automated tests are green and `PAGE-RISK-001` is now bundle-backed and page-evidence checked, but every governed metric page has not yet been re-audited with contract/catalog/lineage evidence.

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
  - Follow-up fix: add separate seeded bundles for `PAGE-EXEC-PNL-ATTR-001` and `PAGE-PNL-ATTR-WB-001` so the executive analytical overlay and `/pnl-attribution` workbench do not share a fuzzy attribution boundary.
  - Follow-up fix: add the seeded `operations-analysis` bundle for `PAGE-OPS-001` with product-category headline truth, supplemental balance entry evidence, and `GAP-OPS-MACRO-FX` guardrails.
  - Follow-up fix: add the seeded `executive-overview` bundle for `PAGE-EXEC-OVERVIEW-001` with `/ui/home/overview`, executive overview service/schema/frontend touchpoints, `GS-EXEC-OVERVIEW-A`, and analytical-overlay guardrails.
  - Follow-up fix: add the seeded `balance-movement-analysis` bundle for `PAGE-BAL-MOVE-001` with `/ui/balance-movement-analysis`, dates/refresh APIs, accounting asset movement source lineage anchors, and explicit no-dedicated-golden-sample status.
  - Follow-up fix: add the seeded `ledger-pnl` bundle for `PAGE-LEDGER-PNL-001` with `/api/ledger-pnl/summary`, detail/date APIs, the formal financial indicator source-contract fixture boundary, and candidate-summary guardrails.
  - Follow-up fix: add the seeded `bond-dashboard` bundle for `PAGE-BOND-001` with `/api/bond-dashboard/headline-kpis`, risk and supporting read APIs, `GS-BOND-HEADLINE-A`, and the `GAP-BOND-DASH-*` candidate-metric guardrails.
  - Follow-up fix: add the seeded `positions` bundle for `PAGE-POS-001` with `/api/positions/bonds`, interbank/counterparty/stat/customer APIs, balance-analysis date-source evidence, and `GAP-POS-LIST` candidate-metric guardrails.
  - Follow-up fix: add the seeded `market-data` bundle for `PAGE-MKT-001` with `/ui/preview/macro-foundation`, the formal rates fragment, FX status/analytical APIs, NCD funding proxy, Livermore analytical APIs, explicit no-dedicated-golden-sample status, and `GAP-MKT-DATA` mixed-source guardrails.
  - Follow-up fix: add the seeded `executive-summary` bundle for `PAGE-EXEC-SUMMARY-001` with `/ui/home/summary`, `SummaryPayload`, `GS-EXEC-SUMMARY-A`, and narrative-only guardrails.
  - Follow-up fix: add the seeded `macro-toolkit` bundle for `PAGE-MACRO-TOOLKIT-001` with `/macro-toolkit`, `/ui/macro/toolkit/analysis`, strategy summaries, scripts, run/refresh/status endpoints, explicit no-dedicated-golden-sample status, and tooling/non-metric guardrails.
  - Follow-up fix: add the seeded `macro-observation` bundle for `PAGE-MACRO-OBS-001` with `/macro-observation`, the shared analysis and strategy-summary read APIs, explicit no-dedicated-golden-sample status, and read-only/non-metric guardrails that exclude script registry, run, refresh, and operational controls.
  - Follow-up fix: add seeded bundles for `PAGE-AGENT-001`, `PAGE-CUBE-QUERY-001`, `PAGE-PORTFOLIO-HOME-001`, `PAGE-MARKET-HOME-001`, `PAGE-RISK-HOME-001`, `PAGE-PERFORMANCE-HOME-001`, and `PAGE-REPORTS-HOME-001`, closing first-pass page-contract bundle coverage at 26/26 while preserving tool/query/module-home non-metric guardrails.
- `tests/test_project_mcp_servers.py`
  - Added regression coverage that `risk-tensor`, `/risk-tensor`, and `PAGE-RISK-001` resolve through `get_page_trace_bundle`, while unknown pages still fail with the supported-page list.
  - Added regression coverage that `PAGE-PROD-CAT-PNL-001` resolves through the existing `product-category-pnl` bundle.
  - Added regression coverage that `pnl-bridge`, `/pnl-bridge`, `PAGE-BRIDGE-001`, and `/api/pnl/bridge` resolve through `get_page_trace_bundle`, with bridge warning/source boundaries preserved.
  - Added regression coverage that `executive-pnl-attribution`, `/ui/pnl/attribution`, and `PAGE-EXEC-PNL-ATTR-001` preserve analytical-overlay boundaries.
  - Added regression coverage that `pnl-attribution`, `/pnl-attribution`, `PAGE-PNL-ATTR-WB-001`, and `/api/pnl-attribution/volume-rate` preserve workbench/provenance boundaries.
  - Added regression coverage that `operations-analysis`, `/operations-analysis`, `PAGE-OPS-001`, and `/ui/pnl/product-category` preserve temporary-exception and mixed-source boundaries.
  - Added regression coverage that `executive-overview`, `/ui/home/overview`, and `PAGE-EXEC-OVERVIEW-001` preserve executive overlay boundaries and the approved golden sample.
  - Added regression coverage that `balance-movement-analysis`, `/balance-movement-analysis`, `PAGE-BAL-MOVE-001`, and `/ui/balance-movement-analysis` preserve movement-analysis source/date/refresh boundaries.
  - Added regression coverage that `ledger-pnl`, `/ledger-pnl`, `PAGE-LEDGER-PNL-001`, and `/api/ledger-pnl/formal-financial-indicators` preserve candidate-summary and formal-financial-indicator source-contract boundaries.
  - Added regression coverage that `bond-dashboard`, `/bond-dashboard`, `PAGE-BOND-001`, `/api/bond-dashboard/headline-kpis`, and `/api/bond-dashboard/risk-indicators` preserve page-sample and candidate-metric boundaries.
  - Added regression coverage that `positions`, `/positions`, `PAGE-POS-001`, `/api/positions/bonds`, and `/api/positions/interbank` preserve list-candidate and balance-date-source boundaries.
  - Added regression coverage that `market-data`, `/market-data`, `PAGE-MKT-001`, `/ui/preview/macro-foundation`, and `/ui/market-data/rates` preserve mixed-source, candidate, formal-fragment, NCD-proxy, Livermore, and source-pending boundaries.
  - Added regression coverage that `executive-summary`, `/ui/home/summary`, and `PAGE-EXEC-SUMMARY-001` preserve narrative contract, golden-sample, and non-formal metric boundaries.
  - Added regression coverage that `macro-toolkit`, `/macro-toolkit`, `PAGE-MACRO-TOOLKIT-001`, `/ui/macro/toolkit/analysis`, and `/ui/macro/toolkit/scripts` preserve tooling, operational, and non-formal metric boundaries.
  - Added regression coverage that `macro-observation`, `/macro-observation`, and `PAGE-MACRO-OBS-001` preserve read-only, no-script/no-refresh, and non-formal metric boundaries.
  - Added regression coverage that `agent`, `/agent`, and `PAGE-AGENT-001` preserve read-only, formal-use, source-lineage, and no-mutation boundaries.
  - Added regression coverage that `cube-query`, `/cube-query`, and `PAGE-CUBE-QUERY-001` preserve candidate query-surface, allowed-dimension, and no-standalone-metric boundaries.
  - Added regression coverage that `portfolio-home`, `market-home`, `risk-home`, `performance-home`, and `reports-home` preserve downstream ownership and module-home non-metric boundaries.
- `docs/audits/2026-06-02-system-audit-first-pass.md`
  - Added the follow-up `risk-tensor` page evidence check: bundle path existence, live service payload, lineage query outcome, and targeted backend/frontend verification results.
  - Added the current page-contract-to-bundle coverage matrix and next-pass priority list, then updated it after the `PAGE-BRIDGE-001`, `PAGE-EXEC-PNL-ATTR-001`, `PAGE-PNL-ATTR-WB-001`, and `PAGE-OPS-001` bundles were seeded.
  - Updated page-contract-to-bundle coverage to 26/26 after seeding the Agent, Cube Query, and module-home page bundles.

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

### P2 - Candidate metric metadata overstates formal-use readiness on sampled surfaces

Evidence from the 2026-06-03 candidate-metric follow-up:

- Dictionary rule: `docs/metric_dictionary.md` states `status=candidate` means the page field is visible and traceable, but page contract / golden sample / business approval closure is not complete; therefore `pending_confirmation=true` remains in force.
- Candidate rows sampled in the dictionary:
  - `MTR-LPN-001` through `MTR-LPN-003` are `candidate`, `bound_sample_id=none`, and bind to `GET /api/ledger-pnl/summary`.
  - `MTR-BOND-001` through `MTR-BOND-004` are `candidate`, `pending_confirmation=true`; `GS-BOND-HEADLINE-A` freezes a page DTO sample, not dictionary-level approval.
  - `MTR-POS-001` and `MTR-POS-002` are `candidate`, `bound_sample_id=none`.
  - `MTR-CFP-001` through `MTR-CFP-004` are `candidate` and bind to `PAGE-CONTRACT-PENDING:/cashflow-projection`.
  - `MTR-CON-001` through `MTR-CON-004` are `candidate` and bind to `PAGE-CONTRACT-PENDING:/concentration-monitor`.
- Page trace bundle evidence preserves the same boundary:
  - `ledger-pnl` guardrails say to treat `MTR-LPN-*` as candidate display metrics and not to promote summary cards into formal PnL, product-category PnL, PnL bridge, or formal financial indicator truth.
  - `bond-dashboard` guardrails say to treat `MTR-BOND-*` as candidate display metrics and not to use `GS-BOND-HEADLINE-A` as dictionary-level approval.
  - `positions` guardrails say to keep `GAP-POS-LIST` visible and not to promote list/count DTOs into formal metric truth.
  - `risk-home` guardrails say it is only a module home; there is no seeded page bundle yet for the pending `/cashflow-projection` or `/concentration-monitor` page-contract IDs.
- Runtime metadata sample:
  - Before the 2026-06-03 Ledger fix, `ledger_pnl_summary_envelope(..., report_date="2026-03-31")` and `ledger_pnl_data_envelope(..., report_date="2026-03-31")` returned `basis=formal`, `formal_use_allowed=true`, empty `tables_used`, and no requested/resolved/as_of date metadata.
  - After the 2026-06-03 Ledger fix, the same summary/detail envelopes return `basis=ledger`, `formal_use_allowed=false`, `date_basis=ledger_report_date`, `tables_used=["qdb_general_ledger_workbook"]`, requested/resolved/as_of report-date metadata, and evidence-row counts from the ledger rows used by the payload.
  - After the 2026-06-03 Bond Dashboard headline fix, `get_bond_dashboard_headline_kpis(date(2026, 3, 31))` returns `basis=analytical`, `formal_use_allowed=false`, `quality_flag=warning`, `date_basis=bond_dashboard_report_date`, `tables_used=["fact_formal_bond_analytics_daily"]`, report-date metadata, and source fact row counts.
  - After the 2026-06-03 Positions list-count fix, `bonds_list_envelope(report_date="2026-01-10", ...)` and `interbank_list_envelope(report_date="2026-01-10", ...)` return `basis=analytical`, `formal_use_allowed=false`, `quality_flag=warning`, `date_basis=positions_snapshot_report_date`, explicit report-date metadata, snapshot source tables, applied filters, and evidence-row counts from the list totals.
  - After the 2026-06-03 Cashflow Projection fix, `get_cashflow_projection(date(2026, 1, 1))` returns `basis=analytical`, `formal_use_allowed=false`, `quality_flag=warning`, `date_basis=cashflow_projection_report_date`, `source_surface=cashflow`, report-date metadata, formal balance source tables, applied filters, and evidence-row counts from the source rows used by the payload.
  - `get_credit_spread_migration(date(2026, 3, 31))`: `basis=formal`, `formal_use_allowed=true`, `result_kind=bond_analytics.credit_spread_migration`, `source_surface=bond_analytics`.
  - Control sample: `adb_envelope_for_dates("2026-03-01", "2026-03-31")` and `adb_monthly_envelope(2026)` correctly return `basis=analytical` and `formal_use_allowed=false` while using formal tables as inputs. This is the cleaner pattern for candidate/analytical page semantics.
- Local MCP fallback lineage evidence found zero records for `positions.bonds.list`, `cashflow_projection.overview`, `bond_analytics.credit_spread_migration`, `MTR-CFP-001`, and `MTR-CON-001`, so the remaining formal-use metadata is not backed by page/metric lineage closure in the current governance streams. `bond_dashboard.headline_kpis` still lacks dictionary-level lineage closure, so its new analytical metadata should remain until a full promotion package exists.
- Frontend evidence already shows user-facing boundary copy for two sampled surfaces:
  - `frontend/src/features/bond-dashboard/pages/BondDashboardPage.tsx` renders `bond-dashboard-headline-candidate-boundary`.
  - `frontend/src/features/positions/components/PositionsView.tsx` renders `positions-list-candidate-boundary`.

Impact: users and downstream consumers can still receive a formal-use signal from sampled unresolved APIs while the dictionary/page contract says the displayed metric is candidate or page-contract-pending. The Ledger PnL summary/detail, Bond Dashboard headline, Positions list-count, and Cashflow Projection endpoint risks are now mitigated at the API metadata boundary, but those fields still remain candidate display metrics until dictionary-level approval, golden samples, and lineage closure exist. For Concentration Monitor, the page contract itself is still pending, so the formal-use flag is stronger than the current governance state supports.

Recommendation: keep the new Ledger, Bond Dashboard headline, Positions, and Cashflow Projection regression tests as the baseline, then add equivalent page-contract-pending endpoint tests for Concentration Monitor. These tests should assert outward metadata cannot imply full formal metric approval unless the metric dictionary rows, page contract, golden sample, and lineage evidence are upgraded together. Prefer an `analytical`, `ledger`, or candidate-specific basis for page-level candidate summaries, or add separate metadata fields that distinguish "formal source table used" from "this page metric is formal-use approved."

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

### Resolved - Page-contract trace bundle coverage has first-pass closure

Evidence from the 2026-06-03 page-contract coverage matrix:

- `docs/page_contracts.md` currently exposes 26 `PAGE-*` page-contract IDs.
- `product_page_trace_bundles()` now resolves all 26 page-contract IDs:
  - `PAGE-DASH-001` -> `dashboard-home`
  - `PAGE-RISK-001` -> `risk-tensor`
  - `PAGE-BALANCE-001` -> `balance-analysis`
  - `PAGE-BAL-MOVE-001` -> `balance-movement-analysis`
  - `PAGE-BOND-001` -> `bond-dashboard`
  - `PAGE-POS-001` -> `positions`
  - `PAGE-MKT-001` -> `market-data`
  - `PAGE-MACRO-TOOLKIT-001` -> `macro-toolkit`
  - `PAGE-MACRO-OBS-001` -> `macro-observation`
  - `PAGE-AGENT-001` -> `agent`
  - `PAGE-CUBE-QUERY-001` -> `cube-query`
  - `PAGE-PORTFOLIO-HOME-001` -> `portfolio-home`
  - `PAGE-MARKET-HOME-001` -> `market-home`
  - `PAGE-RISK-HOME-001` -> `risk-home`
  - `PAGE-PERFORMANCE-HOME-001` -> `performance-home`
  - `PAGE-REPORTS-HOME-001` -> `reports-home`
  - `PAGE-PNL-001` -> `pnl`
  - `PAGE-LEDGER-PNL-001` -> `ledger-pnl`
  - `PAGE-EXEC-OVERVIEW-001` -> `executive-overview`
  - `PAGE-EXEC-SUMMARY-001` -> `executive-summary`
  - `PAGE-EXEC-PNL-ATTR-001` -> `executive-pnl-attribution`
  - `PAGE-PNL-ATTR-WB-001` -> `pnl-attribution`
  - `PAGE-OPS-001` -> `operations-analysis`
  - `PAGE-LIAB-ANALYTICS-001` -> `liability-analytics`
  - `PAGE-BRIDGE-001` -> `pnl-bridge`
  - `PAGE-PROD-CAT-PNL-001` -> `product-category-pnl`
- The `product-category-pnl` bundle also keeps the older `PAGE-PROD-CAT-001` alias. A red/green MCP regression was run for the page-contract ID: before the alias fix, `PAGE-PROD-CAT-PNL-001` failed as unknown with `1 failed, 14 passed`; after the alias fix, `tests/test_project_mcp_servers.py` passed with `15 passed`.
- The `pnl-bridge` bundle covers `/pnl-bridge`, `/api/pnl/bridge`, `PnlBridgePayload`, formal bridge tables, backend/frontend/test touchpoints, and both bridge golden samples. A red/green MCP regression was run: before the bundle, `pnl-bridge` failed as unknown with `2 failed, 15 passed`; after the bundle, `tests/test_project_mcp_servers.py` passed with `17 passed`.
- The `balance-analysis` bundle covers `/balance-analysis`, `/ui/balance-analysis/overview`, formal balance fact tables, workbook and decision-item touchpoints, and both balance golden samples. A red/green MCP regression was run: before the bundle, `balance-analysis` failed as unknown with `2 failed, 17 passed`; after the bundle, `tests/test_project_mcp_servers.py` passed with `19 passed`.
- The `pnl` bundle covers `/pnl`, `/api/pnl/overview`, `/api/pnl/data`, formal PnL fact tables, overview/data DTOs, and both formal PnL golden samples. A red/green MCP regression was run: before the bundle, `pnl` failed as unknown with `2 failed, 19 passed`; after the bundle, `tests/test_project_mcp_servers.py` passed with `21 passed`.
- The `liability-analytics` bundle covers `/liability-analytics`, current compatibility APIs, mixed-source guardrails, and explicit no-dedicated-golden-sample status. A red/green MCP regression was run: before the bundle, `liability-analytics` failed as unknown with `2 failed, 21 passed`; after the bundle, `tests/test_project_mcp_servers.py` passed with `23 passed`.
- The `executive-pnl-attribution` bundle covers `/ui/pnl/attribution`, `PnlAttributionPayload`, `GS-EXEC-PNL-ATTR-A`, executive service/route touchpoints, and the analytical-overlay guardrails that prevent replacing formal PnL or bridge truth.
- The `pnl-attribution` bundle covers `/pnl-attribution`, `/api/pnl-attribution/*`, workbench DTOs, advanced/Campisi touchpoints, frontend workbench tests, and explicit no-dedicated-golden-sample status.
- The `operations-analysis` bundle covers `/operations-analysis`, `/ui/pnl/product-category`, product-category headline samples, supplemental balance overview samples, source/macro/FX/news supporting APIs, and `GAP-OPS-MACRO-FX` guardrails.
- The `executive-overview` bundle covers `/ui/home/overview`, executive overview payload/schema/service/frontend adapter and selector touchpoints, `GS-EXEC-OVERVIEW-A`, and the analytical-overlay guardrails that prevent management summary cards from replacing formal page truth.
- The `balance-movement-analysis` bundle covers `/balance-movement-analysis`, `/ui/balance-movement-analysis`, dates/refresh APIs, accounting asset movement schema/service/core/materialize touchpoints, and explicit no-dedicated-golden-sample status.
- The `ledger-pnl` bundle covers `/ledger-pnl`, `/api/ledger-pnl/summary`, `/api/ledger-pnl/data`, `/api/ledger-pnl/dates`, `/api/ledger-pnl/formal-financial-indicators`, the `GS-LEDGER-PNL-FIN-IND-202603-B` source-contract fixture, and guardrails that keep `MTR-LPN-*` candidate metrics separate from formal PnL, product-category PnL, and formal financial indicator truth.
- The `bond-dashboard` bundle covers `/bond-dashboard`, `/api/bond-dashboard/headline-kpis`, supporting bond dashboard APIs, `GS-BOND-HEADLINE-A`, and guardrails that keep `MTR-BOND-*` candidate metrics separate from balance-analysis truth and risk-tensor truth.
- The `positions` bundle covers `/positions`, `/api/positions/bonds`, `/api/positions/interbank`, counterparty/stat/customer APIs, balance-analysis default date evidence, and guardrails that keep `MTR-POS-*` candidate metrics and filter context separate from formal business metric truth.
- The `market-data` bundle covers `/market-data`, `/ui/preview/macro-foundation`, `/ui/market-data/rates`, FX status/analytical APIs, NCD funding proxy, macro-bond linkage, Livermore APIs, and guardrails that keep `MTR-MKT-001` candidate, `GAP-MKT-DATA`, formal rates fragments, NCD proxy, Livermore `risk_exit`, and source-pending terminal panels separate from full-page formal truth.
- The `executive-summary` bundle covers `/ui/home/summary`, `SummaryPayload`, `GS-EXEC-SUMMARY-A`, endpoint/service/frontend/test touchpoints, and guardrails that keep narrative-only summary text out of the business metric dictionary main table.
- The `macro-toolkit` bundle covers `/macro-toolkit`, `/ui/macro/toolkit/analysis`, strategy summaries, script registry, script run, refresh/status endpoints, and guardrails that keep analysis, strategy, script, refresh, source/version/run_id, and coverage evidence out of formal metric truth.
- The `macro-observation` bundle covers `/macro-observation`, shared read-only analysis and strategy-summary APIs, `macro-observation-readonly-boundary`, and guardrails that keep script registry, run, refresh, and operational controls off the observation route.
- The `agent` bundle covers `/agent`, managed runs, compatibility query, AgentEnvelope, evidence/result_meta display, read-only request enforcement, and guardrails that keep agent answers from replacing formal metrics or source lineage.
- The `cube-query` bundle covers `/cube-query`, `/api/cube/query`, cube dimensions lookup, CubeQueryResult, candidate query-surface semantics, and guardrails that keep query results scoped to returned result_meta.
- The `portfolio-home`, `market-home`, `risk-home`, `performance-home`, and `reports-home` bundles cover live module-home routes, frontend aggregation through `ModuleWorkbenchHomePage` / `moduleHomeModel`, downstream page ownership, explicit no-dedicated-golden-sample status, and guardrails that prevent module summaries from becoming standalone formal metric pages.

Impact: the bundle workflow can now return first-pass trace bundles for every page contract, but this is not a full system-wide release claim because direct page-level lineage, data-catalog/date review, and broader browser/a11y coverage remain incomplete.

Recommendation: keep the bundle workflow as the entry point for future page audits, and use it to drive the remaining lineage/catalog/browser audit work instead of continuing bundle seeding.

## Positive Evidence

- `codex mcp list` confirms `gitnexus`, `moss-data-catalog`, `moss-data-quality`, `moss-lineage-evidence`, and `moss-metric-contracts` are registered and enabled.
- `python -m pytest tests/test_project_mcp_servers.py -q`: latest focused MCP continuation run passed with `57 passed`.
- Local MCP fallback evidence:
  - `moss-metric-contracts`: resources and tools are callable through the repository's JSON-RPC MCP process; contract docs exist; seeded trace bundles are available for all 26 page-contract IDs, including `agent`, `cube-query`, `portfolio-home`, `market-home`, `risk-home`, `performance-home`, and `reports-home`.
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
- Liability Analytics page-contract bundle check:
  - Red check before implementation: `python -m pytest tests/test_project_mcp_servers.py -q` failed with `2 failed, 21 passed` because `liability-analytics` was unknown.
  - Green check after implementation: `python -m pytest tests/test_project_mcp_servers.py -q` passed with `23 passed`.
  - Focused liability backend/compat/result-meta check: `python -m pytest tests/test_liability_analytics_api.py tests/test_liability_analytics_envelope_contract.py tests/test_liability_analytics_compat_contract.py tests/test_liability_analytics_unit_semantics.py tests/test_liability_analytics_numeric_migration.py tests/test_result_meta_on_all_ui_endpoints.py tests/test_result_meta_source_surface_followup.py tests/test_live_route_page_contract_completeness.py -q` passed with `68 passed`.
  - Frontend page/adapter/model check: `npm run test -- src/test/LiabilityAnalyticsPage.test.tsx src/features/liability-analytics/adapters/liabilityAdapter.test.ts src/features/liability-analytics/pages/liabilityAnalyticsPageModel.test.ts` from `frontend/` passed with `3` test files and `12` tests.
  - Current residual evidence note: no dedicated golden sample exists for `PAGE-LIAB-ANALYTICS-001`; the bundle intentionally records this and preserves the governed-mixed-source / compatibility boundary.
- Executive PnL Attribution and PnL Attribution Workbench page-contract bundle check:
  - Red check before implementation: `python -m pytest tests/test_project_mcp_servers.py -q` failed with `4 failed, 23 passed` because `executive-pnl-attribution` and `pnl-attribution` were unknown.
  - Green check after implementation: `python -m pytest tests/test_project_mcp_servers.py -q` passed with `27 passed`.
  - Focused backend/API/service/golden-sample check: `python -m pytest tests/test_pnl_attribution_api_contract.py tests/test_pnl_attribution_workbench_contract.py tests/test_pnl_attribution_service_explicit_numeric.py tests/test_pnl_attribution_numeric_migration.py tests/test_advanced_attribution_contract.py tests/test_result_meta_source_surface.py backend/tests/services/test_pnl_attribution_campisi.py tests/test_executive_dashboard_endpoints.py tests/test_executive_service_contract.py tests/test_executive_release_contract.py tests/test_golden_samples_capture_ready.py -q` passed with `145 passed`.
  - Frontend attribution surface check: `npm run test -- src/test/PnlAttributionPage.test.tsx src/test/PnlAttributionSection.test.tsx src/test/PnlCompositionChart.test.tsx src/test/TPLMarketChart.test.tsx src/test/AdvancedAttributionChart.test.tsx src/test/CampisiAttributionPanel.test.tsx` from `frontend/` passed with `6` test files and `19` tests.
  - Current residual evidence note: `PAGE-EXEC-PNL-ATTR-001` has `GS-EXEC-PNL-ATTR-A`; `PAGE-PNL-ATTR-WB-001` intentionally records no dedicated golden sample and relies on contract/API/service/result-meta/frontend evidence until a workbench sample is approved.
- Operations Analysis page-contract bundle check:
  - Red check before implementation: `python -m pytest tests/test_project_mcp_servers.py -q` failed with `2 failed, 27 passed` because `operations-analysis` was unknown.
  - Green check after implementation: `python -m pytest tests/test_project_mcp_servers.py -q` passed with `29 passed`.
  - Focused doc/API/golden-sample check: `python -m pytest tests/test_governance_doc_contract.py::test_operations_analysis_contract_matches_current_product_category_headline_binding tests/test_live_route_page_contract_completeness.py tests/test_product_category_pnl_flow.py tests/test_balance_analysis_api.py tests/test_golden_samples_capture_ready.py -q` passed with `87 passed`.
  - Frontend operations route check: `npm run test -- src/test/OperationsAnalysisPage.test.tsx src/test/OperationsAnalysisPage.governed.test.tsx src/test/navigation.test.ts src/test/RouteRegistry.test.tsx src/test/WorkbenchShell.test.tsx` from `frontend/` passed with `5` test files and `104` tests.
  - Current residual evidence note: `PAGE-OPS-001` remains a temporary-exception mixed-source page; product-category headline truth is governed, balance overview is supplemental, and macro/FX/news/static sections remain bounded by `GAP-OPS-MACRO-FX`.
- Executive Overview and Balance Movement Analysis page-contract bundle check:
  - Red check before implementation: `python -m pytest tests/test_project_mcp_servers.py -q` failed with `4 failed, 29 passed` because `executive-overview` and `balance-movement-analysis` were unknown.
  - Green check after implementation: `python -m pytest tests/test_project_mcp_servers.py -q` passed with `33 passed`.
  - Focused backend/API/service/golden/sample/accounting-movement check: `python -m pytest tests/test_executive_dashboard_endpoints.py tests/test_executive_service_contract.py tests/test_executive_release_contract.py tests/test_executive_dashboard_numeric_migration.py tests/test_golden_samples_capture_ready.py tests/test_accounting_asset_movement_api.py tests/test_accounting_asset_movement_service.py tests/test_accounting_asset_movement_core.py tests/test_accounting_asset_movement_materialize.py tests/test_result_meta_on_all_ui_endpoints.py tests/test_live_route_page_contract_completeness.py tests/test_write_route_auth_contract.py -q` passed with `177 passed`.
  - Frontend executive overview and balance movement check: `npm run test -- src/test/OverviewSection.test.tsx src/features/executive-dashboard/components/OverviewSection.states.test.tsx src/features/executive-dashboard/selectors/executiveDashboardSelectors.test.ts src/features/executive-dashboard/adapters/executiveDashboardAdapter.test.ts src/test/BalanceMovementAnalysisPage.test.tsx src/test/RouteRegistry.test.tsx` from `frontend/` passed with `6` test files and `91` tests.
  - Current residual evidence note: `PAGE-EXEC-OVERVIEW-001` has `GS-EXEC-OVERVIEW-A` and remains an analytical management overlay; `PAGE-BAL-MOVE-001` intentionally records no dedicated golden sample and relies on page-contract, service/materialize/result-meta/frontend evidence until a sample is approved.
- Ledger PnL page-contract bundle check:
  - Red check before implementation: `python -m pytest tests/test_project_mcp_servers.py -q` failed with `2 failed, 33 passed` because `ledger-pnl` was unknown.
  - Green check after implementation: `python -m pytest tests/test_project_mcp_servers.py -q` passed with `35 passed`.
  - Focused backend/API/source-contract check: `python -m pytest tests/test_ledger_pnl_service.py tests/test_ledger_pnl_formal_financial_indicator_golden_sample.py tests/test_governance_doc_contract.py::test_ledger_pnl_candidate_metrics_bind_existing_page_contract_without_formal_promotion tests/test_live_route_page_contract_completeness.py -q` passed with `15 passed`.
  - Frontend ledger page/route check: `npm run test -- src/test/LedgerPnlPage.test.tsx src/test/LedgerPnlRoutesSmoke.test.tsx` from `frontend/` passed with `2` test files and `13` tests.
  - Focused Ruff check: `python -m ruff check scripts/mcp/moss_project_mcp.py tests/test_project_mcp_servers.py` passed.
  - Current residual evidence note: `PAGE-LEDGER-PNL-001` has no dedicated capture-ready summary golden sample; `GS-LEDGER-PNL-FIN-IND-202603-B` is a source-contract fixture and must not promote formal-pending or candidate QDB values into formal financial indicator truth. Follow-up audit evidence found a metadata mismatch: the metric dictionary keeps `MTR-LPN-001` through `MTR-LPN-003` as candidate / `pending_confirmation=true`, while the live summary and detail envelopes reported `result_meta.basis=formal` and `formal_use_allowed=true`.
  - 2026-06-03 local MCP follow-up evidence: `get_page_trace_bundle("ledger-pnl")` records candidate-summary guardrails and no dedicated summary golden sample; `find_lineage_records` returned zero records for `ledger_pnl`, `PAGE-LEDGER-PNL-001`, `sv_ledger`, `formal_financial_indicators`, and `GS-LEDGER-PNL-FIN-IND-202603-B`; data catalog found no matching ledger summary table and data-quality targets only expose `ledger_import_batch` / `ledger_raw_row` plus unrelated formal tables.
  - 2026-06-03 runtime evidence before the fix: direct service calls for `ledger_pnl_summary_envelope(..., report_date="2026-03-31")` and `ledger_pnl_data_envelope(..., report_date="2026-03-31")` returned `basis=formal`, `formal_use_allowed=true`, empty `tables_used`, and no requested/resolved/as_of date metadata, while `ledger_pnl_formal_financial_indicator_contract_envelope(report_month="202603")` correctly returned `basis=ledger`, `formal_use_allowed=false`, `date_basis=report_month_end`, and `evidence_rows=21`.
  - 2026-06-03 Ledger metadata fix: summary/detail envelopes now use `basis=ledger`, which forces `formal_use_allowed=false`; they also carry requested/resolved/as_of report-date metadata, `date_basis=ledger_report_date`, `tables_used=["qdb_general_ledger_workbook"]`, currency/report-date filters, and evidence-row counts. The summary evidence-row regression covers duplicate source facts under the same account so the count remains source-row based rather than aggregated-account based.
  - Fresh focused checks for this follow-up: `python -m pytest tests/test_ledger_pnl_service.py tests/test_ledger_pnl_formal_financial_indicator_golden_sample.py tests/test_governance_doc_contract.py::test_ledger_pnl_candidate_metrics_bind_existing_page_contract_without_formal_promotion tests/test_live_route_page_contract_completeness.py -q` passed with `17 passed`; `npm run test -- src/test/LedgerPnlPage.test.tsx` passed with `1` file and `13` tests; `python -m ruff check backend/app/services/ledger_pnl_service.py tests/test_ledger_pnl_service.py` passed; `npm run debt:audit` passed with no growth over baseline. These checks verify the summary/detail metadata weakening and preserve the formal financial indicator source-contract boundary.
- Bond Dashboard page-contract bundle check:
  - Red check before implementation: `python -m pytest tests/test_project_mcp_servers.py -q` failed with `2 failed, 35 passed` because `bond-dashboard` was unknown.
  - Green check after implementation: `python -m pytest tests/test_project_mcp_servers.py -q` passed with `37 passed`.
  - Focused backend/API/golden-sample check: `python -m pytest tests/test_bond_dashboard_api_contract.py tests/test_bond_dashboard_headlines_contract.py tests/test_bond_analytics_api.py tests/test_result_meta_source_surface_followup.py tests/test_golden_samples_capture_ready.py -q` passed with `49 passed`.
  - Frontend bond dashboard check: `npm run test -- src/test/BondDashboardPage.test.tsx` from `frontend/` passed with `1` test file and `11` tests.
  - Focused Ruff check: `python -m ruff check scripts/mcp/moss_project_mcp.py tests/test_project_mcp_servers.py` passed.
  - Current residual evidence note: `PAGE-BOND-001` has `GS-BOND-HEADLINE-A` as a capture-ready page DTO sample, but `MTR-BOND-001` through `MTR-BOND-004` remain `candidate` with `pending_confirmation=true`; bond dashboard headline and risk fields must not be treated as `MTR-BAL-*` or `PAGE-RISK-001` equivalents without a separate approved contract.
  - 2026-06-03 candidate-metadata follow-up: direct service output for `get_bond_dashboard_headline_kpis(date(2026, 3, 31))` previously returned `basis=formal` / `formal_use_allowed=true`, while the page trace bundle and frontend `bond-dashboard-headline-candidate-boundary` copy kept `MTR-BOND-*` as candidate.
  - 2026-06-03 Bond Dashboard headline metadata fix: `/api/bond-dashboard/headline-kpis` now returns `basis=analytical`, `formal_use_allowed=false`, `quality_flag=warning`, explicit report-date metadata, `date_basis=bond_dashboard_report_date`, `tables_used=["fact_formal_bond_analytics_daily"]`, and source fact row counts. Fresh checks: `python -m pytest tests/test_bond_dashboard_api_contract.py -q` passed with `11 passed`; `python -m ruff check --ignore UP042 backend/app/services/bond_dashboard_service.py tests/test_bond_dashboard_api_contract.py` passed.
- Positions page-contract bundle check:
  - Red check before implementation: `python -m pytest tests/test_project_mcp_servers.py -q` failed with `2 failed, 37 passed` because `positions` was unknown.
  - Green check after implementation: `python -m pytest tests/test_project_mcp_servers.py -q` passed with `39 passed`.
  - Focused backend/API/live-route check: `python -m pytest tests/test_positions_api_contract.py tests/test_live_route_page_contract_completeness.py -q` passed with `15 passed`.
  - Page contract / metric dictionary binding check: `python -m pytest tests/test_page_contract_metric_dictionary_completeness.py -q` passed with `1 passed`.
  - Frontend positions route/page/customer check: `npm run test -- src/test/PositionsView.test.tsx src/test/CustomerDetailModal.test.tsx src/test/RouteRegistry.test.tsx` from `frontend/` passed with `3` test files and `38` tests.
  - Focused Ruff and whitespace checks passed for `scripts/mcp/moss_project_mcp.py`, `tests/test_project_mcp_servers.py`, and this audit report.
  - Current residual evidence note: `PAGE-POS-001` has no dedicated golden sample; `MTR-POS-001` and `MTR-POS-002` remain `candidate` with `pending_confirmation=true` and `bound_sample_id=none`; list filters/date ranges/search fields remain excluded context rather than standalone metrics.
  - 2026-06-03 Positions list-count metadata fix: `/api/positions/bonds` and `/api/positions/interbank` list envelopes now return `basis=analytical`, `formal_use_allowed=false`, `quality_flag=warning`, `date_basis=positions_snapshot_report_date`, explicit requested/resolved/as_of report-date metadata, `tables_used=["zqtz_bond_daily_snapshot"]` / `["tyw_interbank_daily_snapshot"]`, applied list filters, and evidence-row counts from the list totals. The frontend mock client now mirrors the same candidate metadata for both list endpoints.
  - Fresh candidate-metadata checks: `python -m pytest tests/test_positions_api_contract.py -q` passed with `12 passed`; `python -m pytest tests/test_page_contract_metric_dictionary_completeness.py tests/test_project_mcp_servers.py -q` passed with `58 passed`; `npm run test -- src/test/ApiClient.test.ts -t "keeps mock positions list count envelopes at candidate analytical boundary"` passed; `npm run test -- src/test/PositionsView.test.tsx` passed with `3 passed`; `python -m ruff check backend/app/services/positions_service.py tests/test_positions_api_contract.py` passed.
- Market Data page-contract bundle check:
  - Red check before implementation: `python -m pytest tests/test_project_mcp_servers.py -q` failed with `2 failed, 39 passed` because `market-data` was unknown.
  - Green check after implementation: `python -m pytest tests/test_project_mcp_servers.py -q` passed with `41 passed`.
  - Focused backend/API/mixed-source check: `python -m pytest tests/test_result_meta_on_all_ui_endpoints.py tests/test_market_data_ncd_proxy_api.py tests/test_market_data_livermore_risk_exit_source.py tests/test_fx_analytical_view_api.py tests/test_macro_bond_linkage.py -q` passed with `78 passed`.
  - Focused Livermore API check: `python -m pytest tests/test_market_data_livermore_api.py -q` passed with `34 passed`.
  - Frontend market-data page/model/route check: `npm run test -- src/test/MarketDataPage.test.tsx src/features/market-data/pages/marketDataPageModel.test.ts src/test/RouteRegistry.test.tsx` from `frontend/` passed with `3` test files and `56` tests.
  - Focused Ruff check: `python -m ruff check scripts/mcp/moss_project_mcp.py tests/test_project_mcp_servers.py` passed.
  - Current residual evidence note: `PAGE-MKT-001` has no full-page capture-ready golden sample; `MTR-MKT-001` remains `candidate` with `pending_confirmation=true` and `bound_sample_id=none`; `/ui/market-data/rates` is only a formal rates fragment; NCD is a Shibor/funding proxy; Livermore `risk_exit` remains backend-owned and gated by unsupported outputs/readiness/data gaps.
- Executive Summary page-contract bundle check:
  - Red check before implementation: `python -m pytest tests/test_project_mcp_servers.py -q` failed with `2 failed, 41 passed` because `executive-summary` was unknown.
  - Green check after implementation: `python -m pytest tests/test_project_mcp_servers.py -q` passed with `43 passed`.
  - Focused backend/endpoint/release/golden-sample check: `python -m pytest tests/test_executive_service_contract.py tests/test_executive_dashboard_endpoints.py tests/test_executive_release_contract.py tests/test_golden_samples_capture_ready.py -q` passed with `65 passed`.
  - Frontend summary section check: `npm run test -- src/test/SummarySection.test.tsx` from `frontend/` passed with `1` test file and `3` tests.
  - Focused Ruff check: `python -m ruff check scripts/mcp/moss_project_mcp.py tests/test_project_mcp_servers.py` passed.
  - Current residual evidence note: `PAGE-EXEC-SUMMARY-001` is a narrative-only contract; `GS-EXEC-SUMMARY-A` freezes title, points length, point labels, and result metadata for `/ui/home/summary`, but does not promote narrative text into formal business metrics or cover upstream no-data/fallback/stale states.
- Macro Toolkit and Macro Observation page-contract bundle check:
  - Red check before implementation: `python -m pytest tests/test_project_mcp_servers.py -q` failed with `4 failed, 43 passed` because `macro-toolkit` and `macro-observation` were unknown.
  - Green check after implementation: `python -m pytest tests/test_project_mcp_servers.py -q` passed with `47 passed`.
  - Focused backend/doc/API/auth check: `python -m pytest tests/test_governance_doc_contract.py::test_macro_toolkit_page_contract_closes_tooling_route_without_metric_promotion tests/test_page_contract_metric_dictionary_completeness.py tests/test_live_route_page_contract_completeness.py tests/test_macro_toolkit_scripts.py tests/test_macro_toolkit_choice_stock_refresh_overview.py tests/test_macro_toolkit_factor_snapshot_dates.py tests/test_macro_toolkit_a_share_risk.py tests/test_macro_query_contract_smoke.py tests/test_write_route_auth_contract.py -q` passed with `136 passed`.
  - Frontend macro route/page/client check: `npm run test -- src/test/MacroToolkitPage.test.tsx src/test/RouteRegistry.test.tsx src/test/navigation.test.ts src/test/macroToolkitClient.test.ts` from `frontend/` passed with `4` test files and `113` tests.
  - Focused Ruff check: `python -m ruff check scripts/mcp/moss_project_mcp.py tests/test_project_mcp_servers.py` passed.
  - Focused whitespace check: `git diff --check -- docs/audits/2026-06-02-system-audit-first-pass.md scripts/mcp/moss_project_mcp.py tests/test_project_mcp_servers.py` passed.
  - Current residual evidence note: `PAGE-MACRO-TOOLKIT-001` and `PAGE-MACRO-OBS-001` have no dedicated golden samples and no `MTR-MACRO-*`; macro toolkit analysis, strategy, script, refresh, source/version/run_id, and coverage outputs are tooling/tracing evidence only, while macro observation remains read-only and must not expose script registry, run, refresh, or operational controls.
- Agent, Cube Query, and module-home page-contract bundle check:
  - Red check before implementation: `python -m pytest tests/test_project_mcp_servers.py -q` failed with `10 failed, 47 passed` because `agent`, `cube-query`, `portfolio-home`, `market-home`, `risk-home`, `performance-home`, and `reports-home` were unknown.
  - Green check after implementation: `python -m pytest tests/test_project_mcp_servers.py -q` passed with `57 passed`.
  - Frontend focused page/tool check: `npm run test -- src/test/ModuleWorkbenchHomeModel.test.ts src/test/ModuleWorkbenchHomePage.test.tsx src/test/CubeQueryPage.test.tsx src/test/AgentWorkbenchPage.test.tsx src/test/AgentPlaceholderPage.test.tsx src/test/AgentClient.test.ts src/test/RouteRegistry.test.tsx` from `frontend/` passed with `7` test files and `180` tests after a transient earlier failure in the Agent restore-status case was not reproducible in isolation or on fresh suite rerun.
  - Current residual evidence note: these seven page contracts intentionally have no dedicated golden samples and no standalone `MTR-*` bindings; Agent answers remain read-only/formal-use gated, Cube Query remains scoped to returned query `result_meta`, and module-home pages remain navigation/aggregation surfaces whose formal claims stay on downstream pages.
- Stock Analysis observation-surface follow-up:
  - Contract evidence: `docs/live_route_maturity.md` still marks `/stock-analysis` as `temporary-exception` / `GAP-STOCK-ANALYSIS-PAGE`; `search_contract_docs` found no `PAGE-STOCK-*` or `MTR-STOCK-*` bindings.
  - Local MCP lineage/catalog evidence: `find_lineage_records` returned zero records for `stock-analysis`, `choice_stock_daily_observation`, `market_data.livermore`, `stock_candidate`, and `GAP-STOCK-ANALYSIS-PAGE`; data catalog found no stock/livermore tables in the current `data/moss.duckdb` inventory.
  - Code/test evidence: Livermore strategy, signal confluence, stock detail, and candidate-history paths are tested as `basis=analytical` / `formal_use_allowed=false`, with observation-only / no-trading-instruction copy present in API and frontend tests.
  - Focused backend checks: `python -m pytest tests/test_market_data_livermore_api.py tests/test_market_data_livermore_stock_detail.py -q` passed with `37 passed`; `python -m pytest tests/test_market_data_livermore_candidate_history.py -q` passed with `48 passed`.
  - Frontend check: `npm run test -- src/test/StockAnalysisPage.test.tsx src/features/stock-analysis/lib/buildConsensusSummary.test.ts` from `frontend/` passed with `2` test files and `53` tests.
  - Current residual evidence note: no formal-metadata promotion was found in this sampled pass, but `/stock-analysis` still lacks a standalone PAGE contract, seeded trace bundle, golden sample, and MCP lineage/catalog closure. It should remain observational-only until `GAP-STOCK-ANALYSIS-PAGE` is closed.
- Focused `risk-tensor` page evidence verification after the bundle check:
  - `python -m pytest tests/test_risk_tensor_api.py tests/test_risk_tensor_service.py tests/test_risk_tensor_repo.py tests/test_risk_tensor_core.py tests/test_risk_tensor_materialize.py tests/test_risk_tensor_numeric_migration.py tests/test_risk_tensor_liquidity.py tests/test_golden_samples_capture_ready.py -q`
  - Result: `82 passed`.
  - `npm run test -- src/test/RiskTensorPage.test.tsx` from `frontend/`
  - Result: `1 passed` test file, `40 passed` tests.
- Cashflow Projection and Concentration Monitor candidate-metadata follow-up:
  - Contract evidence: `docs/metric_dictionary.md` keeps `MTR-CFP-001` through `MTR-CFP-004` bound to `PAGE-CONTRACT-PENDING:/cashflow-projection`, `bound_sample_id=none`, and `pending_confirmation=true`; it keeps `MTR-CON-001` through `MTR-CON-004` bound to `PAGE-CONTRACT-PENDING:/concentration-monitor`, `bound_sample_id=none`, and `pending_confirmation=true`.
  - 2026-06-03 Cashflow Projection metadata fix: `/api/cashflow-projection` now returns `basis=analytical`, `formal_use_allowed=false`, `quality_flag=warning`, `date_basis=cashflow_projection_report_date`, explicit requested/resolved/as_of report-date metadata, `source_surface=cashflow`, `tables_used=["fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"]`, applied filters, and evidence-row counts from the source rows used by the payload. The frontend mock client now mirrors the same candidate metadata.
  - Runtime evidence: direct service output for `get_credit_spread_migration(date(2026, 3, 31))` returns `basis=formal`, `formal_use_allowed=true`, `result_kind=bond_analytics.credit_spread_migration`, and result fields including `concentration_by_issuer`, `concentration_by_industry`, `concentration_by_rating`, and `concentration_by_tenor`.
  - Local MCP fallback evidence: `search_contract_docs` finds the pending candidate dictionary rows, but `find_lineage_records` returns zero records for `cashflow_projection.overview`, `bond_analytics.credit_spread_migration`, `MTR-CFP-001`, and `MTR-CON-001`.
  - Fresh Cashflow checks: `python -m pytest tests/test_cashflow_projection.py tests/test_result_meta_source_surface_followup.py tests/test_cashflow_projection_numeric_migration.py tests/test_wave5_service_explicit_numeric.py -q` passed with `28 passed`; `npm run test -- src/test/ApiClientCompositionBoundary.test.ts src/test/CashflowProjectionPage.test.tsx src/features/cashflow-projection/adapters/cashflowProjectionAdapter.test.ts src/features/cashflow-projection/pages/cashflowProjectionPageModel.test.ts` passed with `64 passed`; `python -m ruff check backend/app/services/cashflow_projection_service.py tests/test_cashflow_projection.py tests/test_result_meta_source_surface_followup.py` passed; `npm run debt:audit` passed.
  - Current residual evidence note: Concentration Monitor may use formal source tables internally, but its page-level metrics are still pending confirmation. It needs either metadata weakening or a full contract/sample/lineage upgrade before the API can safely imply page-metric formal-use approval.
- Candidate metadata follow-up verification:
  - `python -m pytest tests/test_project_mcp_servers.py tests/test_ledger_pnl_service.py tests/test_bond_dashboard_api_contract.py tests/test_positions_api_contract.py tests/test_result_meta_source_surface_followup.py tests/test_bond_analytics_api.py tests/test_adb_analysis_api.py -q`
  - Result after the Ledger metadata fix: `114 passed in 93.84s (0:01:33)`.
  - This verifies the current contract/service behavior, the Ledger metadata weakening, and the control analytical ADB boundary. The additional Bond Dashboard headline, Positions, and Cashflow checks above close those endpoints' outward metadata mismatches; Concentration Monitor remains open.

## Evidence Gaps

- Direct `moss-*` MCP tools were not exposed in the current Codex App deferred tool surface. `tool_search` exposed Playwright/GitHub/Canva/Node tools, but not `moss-metric-contracts`, `moss-lineage-evidence`, `moss-data-catalog`, `moss-data-quality`, or `gitnexus` callable tools. This continuation used the local JSON-RPC MCP process as a read-only fallback and records that distinction.
- `PAGE-RISK-001` / `risk-tensor` now has sampled contract/catalog/data-quality evidence, a seeded MCP page trace bundle, and a focused page evidence check, but it still lacks a direct `PAGE-RISK-001` lineage hit.
- Page-level MCP bundle coverage is 26 of 26 page-contract IDs. This coverage is first-pass traceability only; it does not prove every page's data lineage, date semantics, browser state, or golden-sample coverage.
- Candidate/page-contract-pending metadata is not consistently separated from formal source-table usage. Ledger PnL summary/detail, Bond Dashboard headline, Positions list counts, and Cashflow Projection are now weakened away from formal-use approval, but the sampled endpoint for Concentration Monitor still returns `basis=formal` / `formal_use_allowed=true` even where dictionary/page-contract state remains candidate or pending.
- No full data-catalog/date lineage review was completed for every metric page.
- Browser axe now completes for the four covered smoke pages, but broader page coverage is not complete.

## Recommended Next Pass

1. Resolve candidate metric metadata semantics for Concentration Monitor: either weaken outward page-level metadata, or promote the affected metrics only with updated dictionary rows, page contracts, golden samples, lineage records, and tests. Use the Ledger PnL summary/detail, Bond Dashboard headline, Positions list-count, and Cashflow Projection fixes as the regression pattern.
2. Add a direct `PAGE-RISK-001` lineage record or an explicit approved mapping from `PAGE-RISK-001` to the existing `risk_tensor` / `fact_formal_risk_tensor_daily` lineage records.
3. Use the 26/26 page trace bundles as the routing map for the next audit pass: data-catalog/date-lineage review by page, starting with the highest-risk governed metric pages and known mixed-source surfaces.
4. Decide whether the broad backend Ruff backlog is a release blocker or a separately tracked cleanup stream.
5. Use direct MOSS MCP contract/lineage/catalog tools when exposed, or invoke the equivalent project scripts, to audit source lineage and date semantics for ledger-pnl, stock-analysis, agent workbench, commodity ingest, and governed metric pages.
6. Keep the updated a11y smoke in the release gate, and add page-specific ready selectors as new browser smoke pages are covered.
