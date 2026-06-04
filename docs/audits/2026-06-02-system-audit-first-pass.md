# 2026-06-02 System Audit First Pass

Scope: current dirty worktree in `F:\MOSS-V3`.

This report started as an evidence-first first pass and now includes the 2026-06-03 continuation fixes and verification. The worktree already contained many modified and untracked files before this report was added; this update only records the current evidence and the small fixes made while closing red gates.

## Executive Verdict

Release posture: **core automated quality gates are now green**, but do not call this release-ready until the API authorization policy semantics, direct business MCP evidence gap, formal-calculation boundary drift, and broad backend Ruff debt are addressed or formally accepted.

Current top blockers:

1. **P1 - API authorization boundary still needs policy closure.** Sampled sensitive reads now require explicit read scopes, backend route inventory now guards unclassified read/mutation surfaces and stable resource/action scopes, and production startup rejects the development trusted-header switch, but the intended public/internal/admin policy classification and business-owner naming semantics are not yet complete.
2. **P1 - Formal calculation boundary drift remains in `bond_analytics_service`.** DV01 risk/reconciliation/movement/action-plan pure calculations, action-attribution bond-line shaping, and action-attribution success/placeholder payload rules now live in `core_finance`, but action-attribution orchestration still mixes PnL lookup, analysis-adapter fallback calls, schema validation, and result-envelope assembly in the service layer.
3. **P2 - Broad backend Ruff debt remains high.** Focused Ruff for touched backend/test files passes; the earlier broad backend scan reported 962 existing issues.
4. **P2 - Candidate metric API metadata sampled in this pass is now weakened away from formal-use approval.** Ledger PnL summary/detail, Bond Dashboard headline, Positions list-count, Cashflow Projection, and Concentration Monitor metadata now avoid `formal_use_allowed=true` while preserving source/date evidence. These fields still remain candidate or page-contract-pending until dictionary approval, golden samples, and lineage closure exist.
5. **P2 - Page-level MCP trace bundle coverage now has first-pass closure.** Local MCP fallback evidence now directly reads the MOSS metric-contract, data-catalog, data-quality, and lineage providers. The seeded bundle registry now resolves 28 unique trace IDs after adding `PAGE-PNL-BY-BUSINESS-001` as a dedicated Business Type PnL surface and `GAP-STOCK-ANALYSIS-PAGE` as an observational Stock Analysis GAP surface, including the remaining Agent, Cube Query, and module-home surfaces. This closes the bundle-coverage gap, but it does not replace full data-catalog/date-lineage review for every governed metric page or promote the Stock Analysis GAP to a formal PAGE contract.
6. **P2 - Direct business MCP tools were not exposed in the current Codex App tool surface.** `codex mcp list` confirms the MOSS MCP servers are registered and enabled, and MCP server tests pass. This continuation used the equivalent local JSON-RPC MCP process instead of direct deferred `moss-*` tool calls.
7. **P2 - Full data-catalog/date-lineage review is still incomplete.** Automated tests are green, `PAGE-DASH-001` now resolves to Dashboard Home mixed-source snapshot/source-table anchors, `PAGE-RISK-001` is now bundle-backed/page-evidence checked/lineage-mapped, `PAGE-AGENT-001` now resolves to existing Agent audit records, `PAGE-CUBE-QUERY-001` now resolves to its allowed formal source-table anchors, `PAGE-LEDGER-PNL-001` now resolves to Ledger/QDB source-contract anchors, `PAGE-PROD-CAT-PNL-001` / `PAGE-PROD-CAT-001` now resolve to Product Category PnL formal read-model/golden-sample anchors, `PAGE-PNL-001` now resolves to Formal PnL API/result-kind/fact-table/golden-sample anchors, `PAGE-PNL-BY-BUSINESS-001` now resolves to Business Type PnL YTD/monthly/formal-reconciliation API/result-kind/source-table/precompute anchors without creating `MTR-*` or `GS-*` anchors, `PAGE-BRIDGE-001` now resolves to PnL Bridge API/result-kind/source-surface/fact-table/golden-sample anchors, `PAGE-BALANCE-001` now resolves to Balance Analysis API/result-kind/formal-balance fact-table/golden-sample anchors, `PAGE-PNL-ATTR-WB-001` now resolves to PnL Attribution Workbench API/result-kind/formal-attribution source-table/metric anchors, `PAGE-BAL-MOVE-001` now resolves to Balance Movement accounting-asset movement fact/cache/source anchors, `PAGE-LIAB-ANALYTICS-001` now resolves to Liability Analytics analytical mixed-source API/result-kind/formal-liability/source-table anchors, `PAGE-BOND-001` now resolves to Bond Dashboard candidate API/result-kind/bond-analytics source-table/sample anchors, `PAGE-POS-001` now resolves to Positions candidate API/result-kind/snapshot source-table anchors, `PAGE-MKT-001` now resolves to Market Data mixed-source API/result-kind/table anchors, `GAP-STOCK-ANALYSIS-PAGE` now resolves to observational Livermore read APIs/result kinds/support tables without creating `PAGE-STOCK-*`, `MTR-*`, or golden-sample anchors, `PAGE-OPS-001` now resolves to Operations mixed-source product-category/balance/macro/FX/news anchors, `PAGE-EXEC-OVERVIEW-001` now resolves to Executive Overview analytical-overlay/source-table anchors, `PAGE-EXEC-SUMMARY-001` now resolves to Executive Summary narrative-only anchors, `PAGE-MACRO-TOOLKIT-001` / `PAGE-MACRO-OBS-001` now resolve to macro tooling/read-only observation anchors, and `PAGE-PORTFOLIO-HOME-001` / `PAGE-MARKET-HOME-001` / `PAGE-RISK-HOME-001` / `PAGE-PERFORMANCE-HOME-001` / `PAGE-REPORTS-HOME-001` now resolve to module-home downstream read-chain anchors, but every governed metric page has not yet been re-audited with contract/catalog/lineage evidence.

Closed during this continuation:

- **P1 remediated - Source preview read endpoints no longer rely only on the environment flag.** The HTTP kill switch still fails closed, and read/list/history/status/rows/traces now require `source_preview.source_foundation/read`.
- **P1 remediated - Macro Toolkit read endpoints require explicit read permission.** Scripts, analysis, strategy summaries, adversarial signal, and Choice stock refresh-status now require `macro_toolkit/read`; refresh/run actions keep separate permissions.
- **P1 remediated - Agent Workbench enabled endpoints require explicit read permission.** Enabled query/run/status paths now require `agent/read` before execution or run-state lookup; disabled Agent stubs still fail closed with 503.
- **P1 remediated - Production startup rejects trusted user headers.** `MOSS_ENVIRONMENT=production` now fails closed when `MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST` enables `X-User-Id` / `X-User-Role` trust.
- **P1 remediated - Cube Query read endpoints require explicit read permission.** The query execution and dimensions metadata surfaces now require `cube/read` before reading formal/analytical cube data or metadata.
- **P1 regression guard - Backend route authorization inventory now fails on unclassified surfaces and missing policy scopes.** Route inventory tests require backend GET/read-like POST handlers to reach authorization unless explicitly public/echo, mutation handlers to be authorized unless explicitly reserved, and authorized surfaces to expose stable resource/action policy scopes. The executive reserved-route check now uses an available empty scope store so it proves 403 no-grant behavior instead of accidentally proving scope-store outage behavior.
- **P1 partially remediated - Bond Analytics calculations moved behind core_finance.** DV01 shock parsing/expansion, face-weighted duration, absolute-exposure shares, tenor/bond/issuer payloads, reconciliation payloads, movement attribution payloads, action-plan scenario/tenor/issuer/bond recommendation payloads, action-attribution bond-line shaping, and action-attribution success/placeholder payload rules now live under `backend/app/core_finance/`.

## Audit Health Score

| # | Dimension | Score | Key finding |
|---|---:|---:|---|
| 1 | Accessibility | 3/4 | Critical axe smoke now passes the four covered pages; broader page coverage is still incomplete. |
| 2 | Performance / runtime stability | 4/4 | Frontend build/unit/smoke gates and full backend pytest are green. |
| 3 | Theming | 3/4 | Theme guard now passes after restoring the bond-analysis selector ownership boundary; broad global CSS remains a risk area. |
| 4 | Responsive design | 3/4 | Unit/build gates are green; browser smoke for all modified pages is not yet complete. |
| 5 | Anti-patterns / maintainability | 3/4 | Frontend debt audit passes no-growth baseline and focused Ruff passes; broad backend Ruff debt remains outside this pass. |
| **Total** |  | **16/20** | **Core gates green; security, boundary, and evidence gaps remain** |

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
  - Follow-up fix: add the seeded `stock-analysis` GAP bundle for `GAP-STOCK-ANALYSIS-PAGE` with `/stock-analysis`, `/ui/market-data/livermore`, Livermore signal/stock-detail/candidate-history/strategy/proxy APIs, explicit no-dedicated-golden-sample status, and guardrails that keep the page observational-only with no `PAGE-STOCK-*`, no `MTR-*`, and no trading-instruction promotion.
  - Follow-up fix: add the seeded `executive-summary` bundle for `PAGE-EXEC-SUMMARY-001` with `/ui/home/summary`, `SummaryPayload`, `GS-EXEC-SUMMARY-A`, and narrative-only guardrails.
  - Follow-up fix: add the seeded `macro-toolkit` bundle for `PAGE-MACRO-TOOLKIT-001` with `/macro-toolkit`, `/ui/macro/toolkit/analysis`, strategy summaries, scripts, run/refresh/status endpoints, explicit no-dedicated-golden-sample status, and tooling/non-metric guardrails.
  - Follow-up fix: add the seeded `macro-observation` bundle for `PAGE-MACRO-OBS-001` with `/macro-observation`, the shared analysis and strategy-summary read APIs, explicit no-dedicated-golden-sample status, and read-only/non-metric guardrails that exclude script registry, run, refresh, and operational controls.
  - Follow-up fix: add seeded bundles for `PAGE-AGENT-001`, `PAGE-CUBE-QUERY-001`, `PAGE-PORTFOLIO-HOME-001`, `PAGE-MARKET-HOME-001`, `PAGE-RISK-HOME-001`, `PAGE-PERFORMANCE-HOME-001`, and `PAGE-REPORTS-HOME-001`, closing the then-current first-pass page-contract bundle coverage at 26/26 while preserving tool/query/module-home non-metric guardrails.
  - Follow-up fix: add the seeded `pnl-by-business` bundle for `PAGE-PNL-BY-BUSINESS-001` with `/pnl-by-business`, `/api/pnl/by-business-ytd`, monthly/formal/analysis reads, `/api/adb/comparison`, the no-new-`MTR-*` page contract boundary, and guardrails that keep product-category, Ledger, Formal PnL, PnL Bridge, and manual-adjustment evidence separate.
  - Follow-up fix: add the `PAGE-BALANCE-001` lineage-query expansion for Balance Analysis overview/workbook anchors, formal balance fact tables, balance golden samples, and `MTR-BAL-*` dictionary anchors without crossing into Formal PnL, Product Category PnL, or Ledger source anchors.
  - Follow-up fix: add the `PAGE-PNL-BY-BUSINESS-001` lineage-query expansion for Business Type PnL monthly/YTD/formal/analysis APIs, `pnl.by_business*` result kinds, Formal PnL source tables, ZQTZ balance source table, precompute table, and adjustment audit stream while excluding Product Category truth, Ledger truth, `MTR-*`, and `GS-*` anchors.
  - Follow-up fix: add the `PAGE-PNL-ATTR-WB-001` lineage-query expansion for the `/pnl-attribution` workbench APIs, `pnl_attribution.*` / Campisi result kinds, formal attribution source tables, and `MTR-PAT-*` dictionary anchors without crossing into the executive analytical attribution overlay.
  - Follow-up fix: add the `PAGE-BAL-MOVE-001` lineage-query expansion for Balance Movement APIs, `balance-analysis.movement*` result-kind anchors, accounting asset movement fact/cache/source anchors, payload anchors, and `MTR-BMV-*` dictionary anchors without crossing into Balance Analysis overview/workbook, Formal PnL, or Ledger anchors.
  - Follow-up fix: add the `PAGE-LIAB-ANALYTICS-001` lineage-query expansion for Liability Analytics compatibility APIs, `liability_analytics.*` analytical result kinds, the `formal_liability` source surface, formal balance/snapshot source anchors, payload anchors, and `MTR-LIAB-*` dictionary anchors without crossing into Ledger, PnL Bridge, Balance golden-sample, or Executive golden-sample anchors.
  - Follow-up fix: add the `PAGE-BOND-001` lineage-query expansion for Bond Dashboard APIs, `bond_dashboard.*` result kinds, the `bond_analytics` source surface, `fact_formal_bond_analytics_daily`, `GS-BOND-HEADLINE-A`, and candidate `MTR-BOND-*` anchors without crossing into Balance Analysis, Risk Tensor, or Ledger anchors.
  - Follow-up fix: add the `PAGE-POS-001` lineage-query expansion for Positions APIs, `positions.*` result-kind anchors, the `positions_snapshot` source surface, `zqtz_bond_daily_snapshot` / `tyw_interbank_daily_snapshot`, and candidate `MTR-POS-*` anchors without crossing into Formal PnL, Product Category PnL, Bond Dashboard, or Balance Analysis golden-sample anchors.
  - Follow-up fix: add the `PAGE-MKT-001` lineage-query expansion for Market Data preview/rates/FX/NCD/Livermore/macro-bond-linkage APIs, mixed-source result-kind anchors, market-data support tables, `MTR-MKT-001`, and `GAP-MKT-DATA` without crossing into Formal PnL, Product Category PnL, Balance, Positions, Bond Dashboard, or Bond Analytics anchors.
  - Follow-up fix: add the `GAP-STOCK-ANALYSIS-PAGE` lineage-query expansion for Stock Analysis route aliases, Livermore read APIs, observational result-kind anchors, Livermore support tables, and rule-version anchors without crossing into `PAGE-STOCK-*`, `MTR-*`, `GS-*`, Formal PnL, Product Category PnL, or Bond Dashboard anchors.
  - Follow-up fix: add the `PAGE-OPS-001` lineage-query expansion for Operations Analysis product-category headline, supplemental balance overview, source preview, macro, FX, and Choice news anchors without creating `MTR-OPS-*` or crossing into Formal PnL, Balance workbook/detail, Bond Dashboard, or Positions anchors.
  - Follow-up fix: add the `PAGE-EXEC-OVERVIEW-001` lineage-query expansion for Executive Overview analytical overlay APIs/result-kind/schema/golden-sample/`MTR-EXEC-*` anchors and its formal balance, formal PnL, liability, and bond-analytics source-table dependencies without crossing into Balance/PnL/Risk page IDs, golden samples, or Executive PnL Attribution anchors.
  - Follow-up fix: add the `PAGE-DASH-001` lineage-query expansion for Dashboard Home snapshot API/result-kind/payload/service/date-domain/supplemental KPI/source-table anchors without crossing into child page IDs, child golden samples, Bond Dashboard page/sample anchors, Product Category page/sample anchors, Market Data page anchors, or Executive attribution anchors.
  - Follow-up fix: add the `PAGE-EXEC-SUMMARY-001` lineage-query expansion for Executive Summary narrative-only API/result-kind/payload/point/golden-sample/overview-lineage anchors without crossing into Executive Overview metric IDs, Executive Overview page/sample anchors, or Executive PnL Attribution anchors.
  - Follow-up fix: add `PAGE-MACRO-TOOLKIT-001` and `PAGE-MACRO-OBS-001` lineage-query expansions that keep macro toolkit tooling/operational anchors separate from read-only macro observation anchors and avoid creating `MTR-MACRO-*`, `MTR-*`, or dedicated golden-sample anchors.
  - Follow-up fix: add lineage-query expansions for `PAGE-PORTFOLIO-HOME-001`, `PAGE-MARKET-HOME-001`, `PAGE-RISK-HOME-001`, `PAGE-PERFORMANCE-HOME-001`, and `PAGE-REPORTS-HOME-001` to their actual module-home downstream read APIs/result kinds/source-table anchors while excluding standalone `MTR-*`, `GS-*`, and broad route-fragment anchors.
  - Follow-up fix: align the Reports/Data module-home bundle and lineage anchors to the real health summary endpoint `/health` used by `getHealthSummary`, not `/health/summary`.
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
  - Added regression coverage that `stock-analysis`, `/stock-analysis`, and `GAP-STOCK-ANALYSIS-PAGE` preserve temporary-exception, observational-only, no-dedicated-golden-sample, no-`PAGE-STOCK`, no-`MTR-*`, and no-trading-instruction boundaries.
  - Added regression coverage that `executive-summary`, `/ui/home/summary`, and `PAGE-EXEC-SUMMARY-001` preserve narrative contract, golden-sample, and non-formal metric boundaries.
  - Added regression coverage that `macro-toolkit`, `/macro-toolkit`, `PAGE-MACRO-TOOLKIT-001`, `/ui/macro/toolkit/analysis`, and `/ui/macro/toolkit/scripts` preserve tooling, operational, and non-formal metric boundaries.
  - Added regression coverage that `macro-observation`, `/macro-observation`, and `PAGE-MACRO-OBS-001` preserve read-only, no-script/no-refresh, and non-formal metric boundaries.
  - Added regression coverage that `agent`, `/agent`, and `PAGE-AGENT-001` preserve read-only, formal-use, source-lineage, and no-mutation boundaries.
  - Added regression coverage that `cube-query`, `/cube-query`, and `PAGE-CUBE-QUERY-001` preserve candidate query-surface, allowed-dimension, and no-standalone-metric boundaries.
  - Added regression coverage that `PAGE-CUBE-QUERY-001` lineage lookup expands only to Cube Query API/result-kind anchors and the backend-approved formal source tables, not broad `result_meta` text.
  - Added regression coverage that `PAGE-BALANCE-001` lineage lookup expands only to Balance Analysis overview/workbook, formal balance fact-table, golden-sample, and `MTR-BAL-*` anchors, not PnL, Product Category, or Ledger anchors.
  - Added regression coverage that `PAGE-PNL-ATTR-WB-001` lineage lookup expands only to PnL Attribution Workbench APIs/result-kind/source-table/`MTR-PAT-*` anchors, not executive analytical attribution, executive golden-sample, or Ledger anchors.
  - Added regression coverage that `PAGE-BAL-MOVE-001` lineage lookup expands only to Balance Movement API/result-kind/accounting-movement fact/cache/source/`MTR-BMV-*` anchors, not Balance overview/workbook, Formal PnL, or Ledger anchors.
  - Added regression coverage that `PAGE-LIAB-ANALYTICS-001` lineage lookup expands only to Liability Analytics compatibility API/result-kind/formal-liability/source-table/`MTR-LIAB-*` anchors, not Ledger, PnL Bridge, Balance golden-sample, or Executive golden-sample anchors.
  - Added regression coverage that `PAGE-BOND-001` lineage lookup expands only to Bond Dashboard API/result-kind/bond-analytics source-table/sample/candidate `MTR-BOND-*` anchors, not Balance Analysis, Risk Tensor, or Ledger anchors.
  - Added regression coverage that `PAGE-POS-001` lineage lookup expands only to Positions API/result-kind/snapshot source-table/candidate `MTR-POS-*` anchors, not Formal PnL, Product Category PnL, Bond Dashboard, or Balance Analysis golden-sample anchors.
  - Added regression coverage that `PAGE-MKT-001` lineage lookup expands only to Market Data mixed-source API/result-kind/table/candidate `MTR-MKT-*` and `GAP-MKT-DATA` anchors, not Formal PnL, Product Category PnL, Balance, Positions, Bond Dashboard, or Bond Analytics anchors.
  - Added regression coverage that `GAP-STOCK-ANALYSIS-PAGE`, `stock-analysis`, and `/stock-analysis` lineage lookup expands only to observational Livermore APIs/result kinds/support tables/rule versions and returns `formal_use_allowed=false` Livermore evidence, not `PAGE-STOCK-*`, `MTR-*`, golden samples, Formal PnL, Product Category PnL, or Bond Dashboard anchors.
  - Added regression coverage that `PAGE-OPS-001` lineage lookup expands only to Operations mixed-source product-category/balance-overview/source-preview/macro/FX/news anchors, not new `MTR-OPS-*`, Formal PnL, Balance workbook/detail, Bond Dashboard, or Positions anchors.
  - Added regression coverage that `PAGE-EXEC-OVERVIEW-001` lineage lookup expands only to Executive Overview analytical-overlay/source-table/`MTR-EXEC-*` anchors, not Balance, PnL, Risk, or Executive PnL Attribution page/golden-sample anchors.
  - Added regression coverage that `PAGE-DASH-001` lineage lookup expands only to Dashboard Home mixed-source snapshot/supplemental/source-table anchors, not child page IDs, child golden samples, or downstream child-page truth anchors.
  - Added regression coverage that `PAGE-EXEC-SUMMARY-001` lineage lookup expands only to Executive Summary narrative-only API/result-kind/payload/point/golden-sample/overview-lineage anchors, not Executive Overview metric IDs, Executive Overview page/sample anchors, or Executive PnL Attribution anchors.
  - Added regression coverage that `PAGE-MACRO-TOOLKIT-001` expands to macro toolkit analysis, strategy, scripts, run, refresh, status, and source/version/run_id tooling anchors without `MTR-*` or golden-sample promotion.
  - Added regression coverage that `PAGE-MACRO-OBS-001` expands only to read-only macro analysis/strategy/boundary anchors and explicitly excludes script registry, run, refresh, refresh-status, `MTR-*`, and operational toolkit anchors.
  - Added regression coverage that `portfolio-home`, `market-home`, `risk-home`, `performance-home`, and `reports-home` preserve downstream ownership and module-home non-metric boundaries.
  - Added regression coverage that module-home page lineage queries expand to downstream read records for Portfolio, Market, Risk, Performance, and Reports/Data without creating standalone metric or golden-sample anchors.
  - Added regression coverage that `pnl-by-business`, `/pnl-by-business`, `PAGE-PNL-BY-BUSINESS-001`, `/api/pnl/by-business-ytd`, and `/api/pnl/by-business-analysis` preserve page-level analysis boundaries, no-dedicated-golden-sample status, and Product Category / Ledger / Formal PnL / Bridge ownership boundaries.
  - Added regression coverage that `PAGE-PNL-BY-BUSINESS-001` lineage lookup expands to Business Type PnL API/result-kind/source/precompute/adjustment anchors without crossing into Product Category PnL, Ledger PnL, `MTR-*`, or `GS-*` anchors.
- `docs/audits/2026-06-02-system-audit-first-pass.md`
  - Added the follow-up `risk-tensor` page evidence check: bundle path existence, live service payload, lineage query outcome, and targeted backend/frontend verification results.
  - Added the current page-contract-to-bundle coverage matrix and next-pass priority list, then updated it after the `PAGE-BRIDGE-001`, `PAGE-EXEC-PNL-ATTR-001`, `PAGE-PNL-ATTR-WB-001`, and `PAGE-OPS-001` bundles were seeded.
  - Updated the then-current page-contract-to-bundle coverage to 26/26 after seeding the Agent, Cube Query, and module-home page bundles.
  - Updated the registry note again after adding the Stock Analysis GAP bundle; `product_page_trace_bundles()` now resolves 28 unique seeded trace IDs, including `PAGE-PNL-BY-BUSINESS-001` and `GAP-STOCK-ANALYSIS-PAGE`.

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

### P1 - API authorization boundary is inconsistent on sensitive read surfaces

Evidence from the second-pass security review:

- `backend/app/security/auth_context.py:12-26` defines `anonymous` / `viewer` defaults and accepts `X-User-Id` / `X-User-Role` headers.
- `backend/app/security/auth_context.py:79-86` now fails closed when production startup sees `MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST` enabled.
- `backend/app/main.py:50-52` allows credentials and explicitly allows `Authorization`, `X-User-Id`, and `X-User-Role` CORS headers.
- Sampled business read routes from this pass now have explicit read boundaries; broader route inventory review remains incomplete.
- Remediated in this continuation: `backend/app/api/routes/positions.py` now requires `positions/read` on the sampled positions read surface.
- Remediated in this continuation: `backend/app/api/routes/external_data.py` now requires `external_data/read` on catalog and series-data reads.
- Remediated in this continuation: `backend/app/api/routes/cube_query.py` now requires `cube/read` on query execution and cube dimensions read surfaces.
- Remediated in this continuation: `backend/app/api/routes/research_calendar.py` now requires `research_calendar/read` on supply-auction calendar reads.
- Remediated in this continuation: `backend/app/api/routes/market_data_ncd_proxy.py` now requires `market_data_ncd_proxy/read` on the NCD funding proxy read surface.
- Remediated in this continuation: `backend/app/api/routes/dashboard.py` now requires `dashboard/read` on core-metrics and daily-changes reads.
- Remediated in this continuation: `backend/app/api/routes/executive.py` now requires `executive/read` on active executive overview, summary, and PnL attribution reads.
- Remediated in this continuation: `backend/app/api/routes/bond_dashboard.py` now requires `bond_dashboard/read` on dates, headline, structure, distribution, comparison, spread, maturity, industry, risk, and business-type reads.
- Remediated in this continuation: `backend/app/api/routes/cashflow_projection.py` now requires `cashflow_projection/read` on the cashflow projection read surface.
- Remediated in this continuation: `backend/app/api/routes/ledger_pnl.py` now requires `ledger_pnl/read` on dates, data, summary, and formal financial indicator source-contract reads.
- Remediated in this continuation: `backend/app/api/routes/pnl.py` now requires `pnl/read` on formal PnL, bridge, overview, V1 detail, by-business read models, adjustment audit list, yearly summary, and import-status reads.
- Remediated in this continuation: `backend/app/api/routes/pnl_attribution.py` now requires `pnl_attribution/read` on the workbench's basic and advanced attribution reads.
- Remediated in this continuation: `backend/app/api/routes/balance_analysis.py` now requires `balance_analysis/read` on business reads, exports, advanced attribution, decision-item reads, and refresh-status reads; `/current-user` remains an auth-context echo endpoint.
- Remediated in this continuation: `backend/app/api/routes/bond_analytics.py` now requires `bond_analytics/read` on analytical/formal bond analytics GET routes and refresh-status reads, while refresh remains `bond_analytics/refresh`.
- Remediated in this continuation: `backend/app/api/routes/macro_toolkit.py` now requires `macro_toolkit/read` on scripts, analysis, strategy summaries, adversarial signal, and Choice stock refresh-status reads, while refresh/run actions remain separately scoped.
- Remediated in this continuation: `backend/app/api/routes/agent.py` now requires `agent/read` on enabled Agent query, managed-run creation, and run-status reads before execution or run-state lookup.

Impact: automated metric and page-contract tests can pass while sensitive business data remains readable through unauthenticated GET surfaces if remaining business/governance reads are not inventoried and explicitly classified.

Recommendation: define the intended read-access policy once, then add route-level or router-level read authorization for business/governance surfaces. Keep public liveness endpoints separate. Preserve the production fail-closed guard for any future development-only authentication bypasses.

## Remediated Findings

### P1 remediated - Source preview read endpoints require read permission

Evidence:

- `backend/app/api/routes/source_preview.py:52-64` centralizes source-preview permission checks on `source_preview.source_foundation`.
- `backend/app/api/routes/source_preview.py:67-168` keeps `_require_source_preview_http_enabled()` first and then requires `action="read"` for list, history, refresh-status, rows, and traces.
- `tests/test_source_preview_flow.py:301-342` verifies the five read surfaces return 403 without an explicit read grant, then stop returning 403 after granting `source_preview.source_foundation/read`.
- `tests/test_preview_lineage_rule_trace.py:16-26` and `tests/test_source_preview_worker_e2e.py:82-88` seed read permission only for tests that intentionally exercise the enabled read surface.

Verification:

- `python -m pytest tests/test_source_preview_flow.py -q`: `43 passed`.
- `python -m pytest tests/test_preview_lineage_rule_trace.py -q`: `7 passed`.
- `python -m pytest tests/test_pnl_source_preview_flow.py -q`: `3 passed`.
- `python -m pytest tests/test_result_meta_on_all_ui_endpoints.py::test_excluded_ui_surfaces_fail_closed_without_governed_result_meta tests/test_result_meta_on_all_ui_endpoints.py::test_source_preview_surfaces_fail_closed_instead_of_emitting_analytical_meta tests/test_result_meta_on_all_ui_endpoints.py::test_source_preview_refresh_status_now_fails_closed -q`: `9 passed`.
- `python -m pytest tests/test_source_preview_worker_e2e.py::test_source_preview_refresh_real_worker_e2e -q`: `1 passed`.
- `python -m ruff check backend/app/api/routes/source_preview.py tests/test_source_preview_flow.py tests/test_preview_lineage_rule_trace.py tests/test_source_preview_worker_e2e.py`: passed.

Residual risk: this closes the source-preview read surface only. The broader API read-authorization boundary still needs full-route inventory and production startup guardrails.

### P1 remediated - Sampled business dashboard and market-data reads require read permission

Evidence:

- `backend/app/api/routes/market_data_ncd_proxy.py` now checks `market_data_ncd_proxy/read` before returning `/ui/market-data/ncd-funding-proxy`.
- `backend/app/api/routes/dashboard.py` now checks `dashboard/read` before returning `/api/dashboard/core_metrics` and `/api/dashboard/daily-changes`.
- `backend/app/api/routes/executive.py` now checks `executive/read` before returning active executive reads: `/ui/home/overview`, `/ui/home/summary`, and `/ui/pnl/attribution`.
- Route-level regression tests verify 403 without an explicit read grant, while existing payload/golden-sample tests seed only the needed read scope.

Verification:

- `python -m pytest tests/test_market_data_ncd_proxy_api.py -q`: `9 passed`.
- `python -m pytest tests/test_dashboard_api_contract.py -q`: `13 passed`.
- `python -m pytest tests/test_executive_dashboard_endpoints.py -q`: `9 passed`.
- `python -m pytest tests/test_result_meta_on_all_ui_endpoints.py -q`: `26 passed`.
- `python -m pytest tests/test_executive_release_contract.py tests/test_golden_samples_capture_ready.py -k "EXEC or exec" -q`: `7 passed, 15 deselected`.
- `python -m ruff check backend/app/api/routes/market_data_ncd_proxy.py backend/app/api/routes/dashboard.py backend/app/api/routes/executive.py tests/test_market_data_ncd_proxy_api.py tests/test_dashboard_api_contract.py tests/test_executive_dashboard_endpoints.py tests/test_result_meta_on_all_ui_endpoints.py`: passed.

Residual risk: this closes the sampled NCD proxy, dashboard KPI, and active executive read surfaces from the P1 list. It does not prove every business GET route in the application has been inventoried or assigned the correct public/internal/admin policy.

### P1 remediated - Bond Dashboard read endpoints require read permission

Evidence:

- `backend/app/api/routes/bond_dashboard.py` now checks `bond_dashboard/read` before returning all ten Bond Dashboard GET surfaces: dates, headline KPIs, asset structure, yield distribution, portfolio comparison, spread analysis, maturity structure, industry distribution, risk indicators, and business-type metrics.
- `tests/test_bond_dashboard_api_contract.py` verifies the ten Bond Dashboard GET surfaces return 403 without an explicit read grant.
- Existing Bond Dashboard contract and golden-sample tests seed `bond_dashboard/read` before asserting envelope shape, candidate headline metadata, seeded-fact numeric behavior, sub-one-percent display, business-type metrics, and `GS-BOND-HEADLINE-A`.

Verification:

- Red proof before production change: `python -m pytest tests/test_bond_dashboard_api_contract.py::test_bond_dashboard_read_surfaces_require_explicit_read_scope -q` failed because `/api/bond-dashboard/dates` returned 200 instead of 403.
- `python -m pytest tests/test_bond_dashboard_api_contract.py -q`: `12 passed`.
- `python -m pytest tests/test_golden_samples_capture_ready.py -k "BOND or bond" -q`: `1 passed, 17 deselected`.
- `python -m ruff check backend/app/api/routes/bond_dashboard.py tests/test_bond_dashboard_api_contract.py tests/test_golden_samples_capture_ready.py`: passed.

Residual risk: this closes the Bond Dashboard page read surface, but it does not prove every bond-analytics, risk, or portfolio-home consumer route has been inventoried.

### P1 remediated - Cashflow Projection read endpoint requires read permission

Evidence:

- `backend/app/api/routes/cashflow_projection.py` now checks `cashflow_projection/read` before parsing the requested report date or invoking the cashflow projection service.
- `tests/test_cashflow_projection.py` verifies `/api/cashflow-projection` returns 403 without an explicit read grant.
- Existing Cashflow Projection API tests seed `cashflow_projection/read` before asserting the analytical candidate metadata, formal source-table evidence, duration gap payload, and percent-rate duration behavior.

Verification:

- Red proof before production change: `python -m pytest tests/test_cashflow_projection.py::test_cashflow_projection_read_surface_requires_explicit_read_scope -q` failed because `/api/cashflow-projection` returned 200 instead of 403 and reached cashflow calculation.
- `python -m pytest tests/test_cashflow_projection.py -q`: `16 passed`.
- `python -m ruff check backend/app/api/routes/cashflow_projection.py tests/test_cashflow_projection.py`: passed.

Residual risk: this closes the Cashflow Projection read surface, but it does not promote its page metrics to formal-use approval; the candidate metadata and missing lineage/page-contract closure remain separate P2 evidence gaps.

### P1 remediated - Ledger PnL read endpoints require read permission

Evidence:

- `backend/app/api/routes/ledger_pnl.py` now checks `ledger_pnl/read` before returning `/api/ledger-pnl/dates`, `/api/ledger-pnl/data`, `/api/ledger-pnl/summary`, and `/api/ledger-pnl/formal-financial-indicators`.
- `tests/test_ledger_pnl_formal_financial_indicator_golden_sample.py` verifies the four Ledger PnL GET surfaces return 403 without an explicit read grant.
- Existing Ledger PnL API source-contract tests now seed `ledger_pnl/read` before asserting registered and unregistered formal financial indicator source-contract envelopes.

Verification:

- Red proof before production change: `python -m pytest tests/test_ledger_pnl_formal_financial_indicator_golden_sample.py::test_ledger_pnl_read_surfaces_require_explicit_read_scope -q` failed because `/api/ledger-pnl/dates` returned 200 instead of 403.
- Green proof after production change: `python -m pytest tests/test_ledger_pnl_formal_financial_indicator_golden_sample.py::test_ledger_pnl_read_surfaces_require_explicit_read_scope -q`: `1 passed`.
- `python -m pytest tests/test_ledger_pnl_formal_financial_indicator_golden_sample.py tests/test_ledger_pnl_service.py -q`: `14 passed`.
- `python -m ruff check backend/app/api/routes/ledger_pnl.py tests/test_ledger_pnl_formal_financial_indicator_golden_sample.py`: passed.

Residual risk: this closes the Ledger PnL HTTP read surface, but it does not promote `MTR-LPN-*` candidate metrics or replace the separate lineage/golden-sample closure gaps recorded under candidate metric metadata.

### P1 remediated - PnL read endpoints require read permission

Evidence:

- `backend/app/api/routes/pnl.py` now checks `pnl/read` before returning formal PnL dates/data, bridge, overview, V1 detail, by-business, by-business YTD, by-business monthly, by-business analysis, manual-adjustment audit list, yearly summary, and `/api/data/import_status/pnl`.
- Existing mutation boundaries remain separate: manual-adjustment POST routes still use `pnl_by_business.adjustment/write`, and refresh still uses `formal_pnl/refresh`.
- `tests/test_pnl_api_contract.py` verifies the twelve PnL GET surfaces return 403 without an explicit `pnl/read` grant, while the existing PnL contract suite seeds `pnl/read` before asserting formal data, bridge, by-business, manual-adjustment audit, import-status, and refresh follow-up reads.

Verification:

- Red proof before production change: `python -m pytest tests/test_pnl_api_contract.py::test_pnl_read_surfaces_require_explicit_read_scope -q` failed because `/api/pnl/dates` returned 200 instead of 403.
- Green proof after production change: `python -m pytest tests/test_pnl_api_contract.py::test_pnl_read_surfaces_require_explicit_read_scope -q`: `1 passed`.
- `python -m pytest tests/test_pnl_api_contract.py -q`: `73 passed`.
- `python -m ruff check backend/app/api/routes/pnl.py tests/test_pnl_api_contract.py`: passed.
- `git diff --check -- backend/app/api/routes/pnl.py tests/test_pnl_api_contract.py`: passed.

Residual risk: this closes the PnL HTTP read surfaces covered by `tests/test_pnl_api_contract.py`, but it does not prove every PnL-adjacent frontend or executive overlay route has been inventoried; those remain part of the broader P1 route inventory.

### P1 remediated - PnL Attribution workbench read endpoints require read permission

Evidence:

- `backend/app/api/routes/pnl_attribution.py` now checks `pnl_attribution/read` before returning `/api/pnl-attribution/volume-rate`, `/tpl-market`, `/composition`, `/summary`, `/advanced/carry-rolldown`, `/advanced/spread`, `/advanced/krd`, `/advanced/summary`, and `/advanced/campisi`.
- `tests/test_pnl_attribution_api_contract.py` verifies all twelve listed route/parameter combinations return 403 without an explicit read grant.
- Existing PnL Attribution API contract tests seed `pnl_attribution/read` before asserting the empty-DuckDB formal attribution envelopes and volume-rate DTO shape.

Verification:

- Red proof before production change: `python -m pytest tests/test_pnl_attribution_api_contract.py::test_pnl_attribution_read_surfaces_require_explicit_read_scope -q` failed because `/api/pnl-attribution/volume-rate` returned 200 instead of 403.
- Green proof after production change: `python -m pytest tests/test_pnl_attribution_api_contract.py::test_pnl_attribution_read_surfaces_require_explicit_read_scope -q`: `1 passed`.
- `python -m pytest tests/test_pnl_attribution_api_contract.py -q`: `3 passed`.
- `python -m ruff check backend/app/api/routes/pnl_attribution.py tests/test_pnl_attribution_api_contract.py`: passed.
- `git diff --check -- backend/app/api/routes/pnl_attribution.py tests/test_pnl_attribution_api_contract.py`: passed.

Residual risk: this closes the PnL Attribution workbench read surface, but the separate executive PnL attribution overlay and other PnL-adjacent routes remain governed by their own route scopes and inventory evidence.

### P1 remediated - Balance Analysis read endpoints require read permission

Evidence:

- `backend/app/api/routes/balance_analysis.py` now checks `balance_analysis/read` before returning dates, detail, overview, summary, summary-by-basis, advanced attribution, workbook, decision-items, summary export, workbook export, and refresh-status reads.
- `/ui/balance-analysis/current-user` remains an auth-context echo endpoint and was not reclassified as business data.
- Existing mutation boundaries remain separate: decision status updates still require `balance_analysis.decision_status/write`, and refresh still requires `balance_analysis/refresh`.
- `tests/test_balance_analysis_api.py` verifies eleven business/read/export/status GET surfaces return 403 without an explicit read grant. Existing API, decision-status, export, refresh-status, and advanced-attribution tests now seed only `balance_analysis/read` where they intentionally exercise read surfaces.

Verification:

- Red proof before production change: `python -m pytest tests/test_balance_analysis_api.py::test_balance_analysis_read_surfaces_require_explicit_read_scope -q` failed because `/ui/balance-analysis/dates` returned 200 instead of 403.
- Green proof after production change: `python -m pytest tests/test_balance_analysis_api.py::test_balance_analysis_read_surfaces_require_explicit_read_scope -q`: `1 passed`.
- `python -m pytest tests/test_balance_analysis_api.py -q`: `28 passed`.
- `python -m pytest tests/test_advanced_attribution_contract.py tests/test_result_meta_on_all_ui_endpoints.py::test_ui_get_json_envelopes_include_result_meta_and_result -q`: `20 passed`.
- `python -m ruff check backend/app/api/routes/balance_analysis.py tests/test_balance_analysis_api.py tests/test_advanced_attribution_contract.py tests/test_result_meta_on_all_ui_endpoints.py`: passed.
- `git diff --check -- backend/app/api/routes/balance_analysis.py tests/test_balance_analysis_api.py tests/test_advanced_attribution_contract.py tests/test_result_meta_on_all_ui_endpoints.py`: passed.

Residual risk: this closes the Balance Analysis HTTP read surfaces covered here, but it does not prove every balance-analysis-adjacent, workbook-derived, or module-home route has been inventoried.

### P1 remediated - Bond Analytics read endpoints require read permission

Evidence:

- `backend/app/api/routes/bond_analytics.py` now checks `bond_analytics/read` before returning dates, return decomposition, benchmark excess, KRD curve risk, DV01 risk/reconciliation/movement/action-plan/limit-config status, credit-spread migration, yield-curve term structure, portfolio headlines, top holdings, position changes, action attribution, accounting-class audit, and refresh-status reads.
- Existing refresh POST behavior remains under `bond_analytics/refresh`.
- `tests/test_bond_analytics_api.py` verifies seventeen Bond Analytics GET route/parameter combinations return 403 without an explicit read grant. Existing API tests seed `bond_analytics/read` before asserting envelope shape, DV01 numeric payloads, home supplement perf logging, and refresh-status follow-up reads.
- `tests/test_bond_analytics_refresh_contract.py` seeds `bond_analytics/read` for refresh-status contract tests while preserving `bond_analytics/refresh` for POST refresh behavior.

Verification:

- Red proof before production change: `python -m pytest tests/test_bond_analytics_api.py::test_bond_analytics_read_surfaces_require_explicit_read_scope -q` failed because `/api/bond-analytics/dates` returned 200 instead of 403.
- Green proof after production change: `python -m pytest tests/test_bond_analytics_api.py::test_bond_analytics_read_surfaces_require_explicit_read_scope -q`: `1 passed`.
- `python -m pytest tests/test_bond_analytics_api.py -q`: `14 passed`.
- `python -m pytest tests/test_bond_analytics_refresh_contract.py -q`: `8 passed`.
- `python -m ruff check backend/app/api/routes/bond_analytics.py tests/test_bond_analytics_api.py tests/test_bond_analytics_refresh_contract.py`: passed.
- `git diff --check -- backend/app/api/routes/bond_analytics.py tests/test_bond_analytics_api.py tests/test_bond_analytics_refresh_contract.py`: passed.

Residual risk: this closes the sampled Bond Analytics HTTP read surfaces, but it does not address the separate P1/P2 formal-calculation boundary drift in `bond_analytics_service`.

### P1 remediated - Liability Analytics read endpoints require read permission

Evidence:

- `backend/app/api/routes/liability_analytics.py` now checks `liability_analytics/read` before returning risk buckets, yield metrics, yield-by-period, counterparty, monthly liabilities, liability business context, cockpit warnings, and contribution split reads.
- Date and query-parameter validation semantics remain intact: invalid `report_date` and year-bound failures still return 422 before the service read path.
- `tests/test_liability_analytics_api.py` verifies all eight Liability Analytics read surfaces return 403 without an explicit read grant. Existing liability analytics and knowledge-page tests seed only `liability_analytics/read` when intentionally exercising success paths.
- `tests/test_pnl_api_contract.py` now grants `liability_analytics/read` for the existing formal-PnL-backed `/api/analysis/yield-by-period` rollup test, making the cross-route dependency explicit.

Verification:

- Red proof before production change: `python -m pytest tests/test_liability_analytics_api.py::test_liability_analytics_read_surfaces_require_explicit_read_scope -q` failed because `/api/risk/buckets` returned 200 instead of 403.
- Green proof after production change: `python -m pytest tests/test_liability_analytics_api.py tests/test_liability_analytics_envelope_contract.py tests/test_liability_knowledge_api.py tests/test_pnl_api_contract.py::test_yield_by_period_monthly_and_quarterly_rollups_from_formal_pnl -q`: `8 passed`.
- `python -m ruff check backend/app/api/routes/liability_analytics.py tests/test_liability_analytics_api.py tests/test_liability_analytics_envelope_contract.py tests/test_liability_knowledge_api.py tests/test_pnl_api_contract.py`: passed.
- `git diff --check -- backend/app/api/routes/liability_analytics.py tests/test_liability_analytics_api.py tests/test_liability_analytics_envelope_contract.py tests/test_liability_knowledge_api.py tests/test_pnl_api_contract.py`: passed.

Residual risk: this closes the Liability Analytics HTTP read surfaces covered here, but it does not prove every liability-adjacent executive/home/compatibility consumer route has been inventoried or that the broader P1 read-route inventory is complete.

### P1 remediated - QDB GL Monthly Analysis read and refresh endpoints require permission

Evidence:

- `backend/app/api/routes/qdb_gl_monthly_analysis.py` now checks `qdb_gl_monthly_analysis/read` before returning dates, workbook, workbook export, refresh-status, scenario, manual-adjustment list, and manual-adjustment export reads.
- `POST /ui/qdb-gl-monthly-analysis/refresh` now checks `qdb_gl_monthly_analysis/refresh` before rebuilding the analytical workbook payload and writing the governance run record.
- Existing adjustment mutation boundaries remain separate: create/edit/revoke/restore still use `qdb_gl_monthly_analysis.adjustment/write`.
- `tests/test_qdb_gl_monthly_analysis_api.py` verifies the seven QDB GL Monthly Analysis GET route/parameter combinations return 403 without an explicit read grant. Existing API tests now seed `qdb_gl_monthly_analysis/read` for read success paths and retain the adjustment write grant only for mutation setup.
- `tests/test_qdb_gl_monthly_analysis_api.py` also verifies refresh returns 403 without an explicit refresh grant, while the refresh success test now grants `qdb_gl_monthly_analysis/refresh` separately from read.
- `tests/test_qdb_gl_monthly_analysis_excel_export.py` seeds `qdb_gl_monthly_analysis/read` before asserting workbook-export XLSX content and history sheets.

Verification:

- Red proof before production change: `python -m pytest tests/test_qdb_gl_monthly_analysis_api.py::test_qdb_gl_monthly_analysis_read_surfaces_require_explicit_read_scope -q` failed because `/ui/qdb-gl-monthly-analysis/dates` returned 200 instead of 403.
- Red proof before refresh production change: `python -m pytest tests/test_qdb_gl_monthly_analysis_api.py::test_qdb_gl_monthly_analysis_refresh_requires_explicit_refresh_scope -q` failed because `/ui/qdb-gl-monthly-analysis/refresh` returned 200 instead of 403.
- Green proof after production change: `python -m pytest tests/test_qdb_gl_monthly_analysis_api.py tests/test_qdb_gl_monthly_analysis_excel_export.py -q`: `13 passed`.
- `python -m ruff check backend/app/api/routes/qdb_gl_monthly_analysis.py tests/test_qdb_gl_monthly_analysis_api.py tests/test_qdb_gl_monthly_analysis_excel_export.py`: passed. Ruff reported only that it could not write the sandboxed `.ruff_cache`; lint itself passed.
- `git diff --check -- backend/app/api/routes/qdb_gl_monthly_analysis.py tests/test_qdb_gl_monthly_analysis_api.py tests/test_qdb_gl_monthly_analysis_excel_export.py docs/audits/2026-06-02-system-audit-first-pass.md`: passed.

Residual risk: this closes the QDB GL Monthly Analysis GET/read/export/status/list surfaces and refresh POST covered here, but it does not prove every QDB-adjacent frontend/client or downstream consumer route has been inventoried. The broader P1 route inventory remains open.

### P1 remediated - Product Category PnL read endpoints require read permission

Evidence:

- `backend/app/api/routes/product_category_pnl.py` now checks `product_category_pnl/read` before returning dates, detail, attribution, refresh-status, manual-adjustment list, and manual-adjustment export reads.
- Existing mutation boundaries remain separate: `POST /ui/pnl/product-category/refresh` still uses `product_category_pnl/refresh`, and manual-adjustment create/edit/revoke/restore still use `product_category_pnl.adjustment/write`.
- Query validation order remains intact for unsupported product-category `view` and attribution `compare`; those invalid parameter paths still return 422 before the read service path.
- `tests/test_product_category_pnl_flow.py` verifies the six Product Category PnL GET route/parameter combinations return 403 without an explicit read grant. Existing product-category flow, attribution, result-meta, and worker-e2e tests now seed `product_category_pnl/read` only for intended success paths.

Verification:

- Red proof before production change: `python -m pytest tests/test_product_category_pnl_flow.py::test_product_category_read_surfaces_require_explicit_read_scope -q` failed because `/ui/pnl/product-category/dates` returned 200 instead of 403.
- Green proof after production change: `python -m pytest tests/test_product_category_pnl_flow.py tests/test_product_category_pnl_attribution.py tests/test_result_meta_on_all_ui_endpoints.py::test_ui_get_json_envelopes_include_result_meta_and_result tests/test_result_meta_on_all_ui_endpoints.py::test_product_category_scenario_request_sets_scenario_basis tests/test_write_route_auth_contract.py::test_refresh_route_requires_explicit_scope_grant[/ui/pnl/product-category/refresh] tests/test_write_route_auth_contract.py::test_product_category_refresh_returns_503_when_scope_store_unavailable -q`: `61 passed`.
- `python -m ruff check backend/app/api/routes/product_category_pnl.py tests/test_product_category_pnl_flow.py tests/test_product_category_pnl_attribution.py tests/test_result_meta_on_all_ui_endpoints.py tests/test_source_preview_worker_e2e.py tests/conftest.py`: passed. Ruff reported only that it could not write the sandboxed `.ruff_cache`; lint itself passed.
- `git diff --check -- backend/app/api/routes/product_category_pnl.py tests/test_product_category_pnl_flow.py tests/test_product_category_pnl_attribution.py tests/test_result_meta_on_all_ui_endpoints.py tests/test_source_preview_worker_e2e.py tests/conftest.py docs/audits/2026-06-02-system-audit-first-pass.md`: passed.

Residual risk: this closes the Product Category PnL GET/read/export/status/list surfaces covered here, but the Redis-backed `test_product_category_refresh_real_worker_e2e` was not rerun in this pass. The test was updated to grant `product_category_pnl/read`, and the broader P1 route inventory remains open.

### P1 remediated - Risk Tensor read endpoints require read permission

Evidence:

- `backend/app/api/routes/risk_tensor.py` now checks `risk_tensor/read` before returning available risk-tensor dates and formal risk-tensor payloads.
- Invalid `report_date` validation order remains intact: malformed dates still return 422 before the read service path.
- `tests/test_risk_tensor_api.py` verifies both `/api/risk/tensor/dates` and `/api/risk/tensor?report_date=...` return 403 without an explicit read grant. Existing Risk Tensor API success/error-path tests now seed `risk_tensor/read` when intentionally exercising the data path.
- Impact search found no additional backend tests directly calling the live Risk Tensor routes beyond `tests/test_risk_tensor_api.py`; frontend references are client/component mocks or static contract assertions.

Verification:

- Red proof before production change: `python -m pytest tests/test_risk_tensor_api.py::test_risk_tensor_read_surfaces_require_explicit_read_scope -q` failed because `/api/risk/tensor/dates` returned 200 instead of 403.
- Green proof after production change: `python -m pytest tests/test_risk_tensor_api.py::test_risk_tensor_read_surfaces_require_explicit_read_scope -q`: `1 passed`.
- `python -m pytest tests/test_risk_tensor_api.py -q`: `10 passed`.
- `python -m ruff check backend/app/api/routes/risk_tensor.py tests/test_risk_tensor_api.py`: passed. Ruff reported only that it could not write the sandboxed `.ruff_cache`; lint itself passed.

Residual risk: this closes the two live Risk Tensor HTTP read surfaces covered here, but it does not prove the broader P1 read-route inventory is complete.

### P1 remediated - Credit Spread Analysis detail endpoint requires read permission

Evidence:

- `backend/app/api/routes/credit_spread_analysis.py` now checks `credit_spread_analysis/read` before returning the formal credit-spread detail payload.
- `tests/test_credit_spread_analysis.py` verifies `/api/credit-spread-analysis/detail?report_date=...` returns 403 without an explicit read grant.
- The existing real-data API regression now seeds `credit_spread_analysis/read` and passes the trusted test identity through its subprocess request, keeping the intended formal payload success path explicit.

Verification:

- Red proof before production change: `python -m pytest tests/test_credit_spread_analysis.py::test_credit_spread_detail_requires_explicit_read_scope -q` failed because `/api/credit-spread-analysis/detail` returned 200 instead of 403.
- Green proof after production change: `python -m pytest tests/test_credit_spread_analysis.py::test_credit_spread_detail_requires_explicit_read_scope -q`: `1 passed`.
- `python -m pytest tests/test_credit_spread_analysis.py -q`: `6 passed`.

Residual risk: this closes the single live Credit Spread Analysis detail read endpoint covered here, but it does not prove all bond-analytics-adjacent compatibility reads have been inventoried. The broader P1 read-route inventory remains open.

### P1 remediated - Campisi attribution compatibility reads require PnL Attribution read permission

Evidence:

- `backend/app/api/routes/campisi_attribution.py` now checks `pnl_attribution/read` before returning four Campisi compatibility read payloads: four-effects, enhanced, maturity-buckets, and decision-grade.
- The permission resource intentionally matches the main `/api/pnl-attribution/*` workbench read contract instead of introducing a new Campisi-only scope.
- `tests/test_pnl_attribution_api_contract.py` verifies all four Campisi compatibility GET route/parameter combinations return 403 without an explicit `pnl_attribution/read` grant.

Verification:

- Red proof before production change: `python -m pytest tests/test_pnl_attribution_api_contract.py::test_campisi_attribution_read_surfaces_require_explicit_read_scope -q` failed because `/api/pnl-attribution/campisi/four-effects` returned 200 instead of 403.
- Green proof after production change: `python -m pytest tests/test_pnl_attribution_api_contract.py::test_campisi_attribution_read_surfaces_require_explicit_read_scope -q`: `1 passed`.
- `python -m pytest tests/test_pnl_attribution_api_contract.py -q`: `4 passed`.

Residual risk: this closes the four Campisi compatibility GET reads covered here, but it does not prove every PnL-attribution-adjacent frontend/client route has been inventoried. The broader P1 read-route inventory remains open.

### P1 remediated - Balance Movement Analysis read endpoints require read permission

Evidence:

- `backend/app/api/routes/accounting_asset_movement.py` now checks `accounting_asset_movement/read` before returning available dates and detail payloads for `/ui/balance-movement-analysis`.
- The refresh mutation boundary remains separate: `POST /ui/balance-movement-analysis/refresh` still requires `accounting_asset_movement/refresh`.
- `tests/test_accounting_asset_movement_api.py` verifies both Balance Movement GET surfaces return 403 without an explicit read grant. Existing refresh tests continue to verify the independent refresh grant.
- `tests/test_result_meta_on_all_ui_endpoints.py` now grants `accounting_asset_movement/read` for the existing result-meta smoke success path.

Verification:

- Red proof before production change: `python -m pytest tests/test_accounting_asset_movement_api.py::test_balance_movement_read_surfaces_require_explicit_read_scope -q` failed because `/ui/balance-movement-analysis/dates` returned 200 instead of 403.
- Green proof after production change: `python -m pytest tests/test_accounting_asset_movement_api.py::test_balance_movement_read_surfaces_require_explicit_read_scope -q`: `1 passed`.
- `python -m pytest tests/test_accounting_asset_movement_api.py -q`: `4 passed`.
- `python -m pytest tests/test_result_meta_on_all_ui_endpoints.py::test_ui_get_json_envelopes_include_result_meta_and_result -q`: `12 passed`.

Residual risk: this closes the two Balance Movement Analysis GET reads covered here, but it does not prove every balance-movement-adjacent frontend/client route has been inventoried. The broader P1 read-route inventory remains open.

### P1 remediated - Ledger read endpoints require read permission

Evidence:

- `backend/app/api/routes/ledger.py` now checks `ledger.data/read` before returning ledger import history, available dates, dashboard, positions, and positions export reads.
- The import mutation boundary remains separate: `POST /api/ledger/import` still requires `ledger.data/import`.
- Existing query validation order remains intact: unsupported query parameters and invalid date/filter payloads still return the existing Ledger 400 error envelope before the read service path.
- `tests/test_ledger_analytics_api.py` verifies all five Ledger GET surfaces return 403 without an explicit read grant. Existing Ledger import/analytics success helpers now grant `ledger.data/read` for intended read paths.

Verification:

- Red proof before production change: `python -m pytest tests/test_ledger_analytics_api.py::test_ledger_read_surfaces_require_explicit_read_scope -q` failed because `/api/ledger/imports` returned 200 instead of 403.
- Green proof after production change: `python -m pytest tests/test_ledger_analytics_api.py::test_ledger_read_surfaces_require_explicit_read_scope -q`: `1 passed`.
- `python -m pytest tests/test_ledger_analytics_api.py -q`: `13 passed, 1 skipped`.
- `python -m pytest tests/test_ledger_import_flow.py::test_ledger_import_api_imports_csv_lists_batch_and_preserves_unknown_raw_json -q`: `1 passed`.

Residual risk: this closes the five Ledger GET/read/export surfaces covered here, but it does not prove every Ledger-adjacent frontend/client route has been inventoried. The broader P1 read-route inventory remains open.

### P1 remediated - KPI read endpoints require read permission

Evidence:

- `backend/app/api/routes/kpi.py` now checks `kpi/read` before returning KPI owners, period summaries, metric lists/details, values, and report/export payloads.
- Existing mutation boundaries remain separate: metric create/update/delete still use `kpi.metric/write|delete`, and value create/update/batch/fetch-recalc still use `kpi.value/write`.
- `tests/test_kpi_api.py` verifies the KPI GET/read functions raise 403 without an explicit read grant, while existing write-auth tests continue to cover mutation denial before service calls.

Verification:

- Red proof before production change: `python -m pytest tests/test_kpi_api.py::test_kpi_read_routes_require_explicit_read_scope -q` failed because the GET functions did not accept/enforce an auth context.
- Green proof after production change: `python -m pytest tests/test_kpi_api.py::test_kpi_read_routes_require_explicit_read_scope -q`: `1 passed`.
- `python -m pytest tests/test_kpi_api.py -q`: `9 passed`.

Residual risk: this closes the KPI GET/read functions covered here, but it does not prove every KPI-adjacent frontend/client consumer has been inventoried. The broader P1 read-route inventory remains open.

### P1 remediated - Executive compatibility and home reads require read permission

Evidence:

- `backend/app/api/routes/executive.py` already checked `executive/read` for `/ui/home/overview`, `/ui/home/summary`, and `/ui/pnl/attribution`.
- This continuation extends the same read check to the remaining executive/home GET surfaces: `/ui/risk/overview`, `/ui/home/contribution`, `/ui/home/alerts`, `/ui/home/snapshot`, `/ui/home/research-reports`, and `/ui/home/income-trend`.
- Reserved compatibility routes still fail closed after authorization: with `executive/read`, `/ui/risk/overview`, `/ui/home/contribution`, and `/ui/home/alerts` continue to return the existing 503 reserved boundary.
- `tests/test_executive_dashboard_endpoints.py` verifies the six remaining GET surfaces return 403 without an explicit read grant and preserves the existing landed-vs-reserved route behavior when the read grant is present.
- `tests/test_dashboard_home_backend_blocks.py` now grants explicit read scopes for the existing home-data and bond position-change success paths.

Verification:

- Red proof before production change: `python -m pytest tests/test_executive_dashboard_endpoints.py::test_executive_remaining_read_surfaces_require_explicit_read_scope -q` failed because the reserved routes returned 503 and the home data routes returned 200 instead of 403.
- Green proof after production change: `python -m pytest tests/test_executive_dashboard_endpoints.py::test_executive_remaining_read_surfaces_require_explicit_read_scope -q`: `6 passed`.
- `python -m pytest tests/test_executive_dashboard_endpoints.py -q`: `15 passed`.
- `python -m pytest tests/test_result_meta_on_all_ui_endpoints.py::test_ui_get_json_envelopes_include_result_meta_and_result tests/test_result_meta_on_all_ui_endpoints.py::test_executive_surfaces_are_analytical_placeholder_friendly -q`: `13 passed`.
- `python -m pytest tests/test_dashboard_home_backend_blocks.py -q`: `9 passed`.
- `python -m ruff check backend/app/api/routes/executive.py tests/test_executive_dashboard_endpoints.py tests/test_dashboard_home_backend_blocks.py`: passed, with only the existing `.ruff_cache` access warnings.
- `git diff --check -- backend/app/api/routes/executive.py tests/test_executive_dashboard_endpoints.py tests/test_dashboard_home_backend_blocks.py docs/audits/2026-06-02-system-audit-first-pass.md`: passed.

Residual risk: this closes the six remaining Executive/home GET surfaces covered here, but it does not prove every executive-adjacent frontend/client consumer or future compatibility route has been inventoried. The broader P1 read-route inventory remains open.

### P1 remediated - Livermore market-data reads require read permission

Evidence:

- `backend/app/api/routes/market_data_livermore.py` now checks `market_data.livermore/read` before returning the Livermore strategy, signal confluence, stock detail, candidate history, strategy score, strategy optimization, cycle-proxy backtest, candidate-history portfolio backtest, and sector-rank-series GET payloads.
- The existing Livermore position-snapshot import boundary remains separate: position snapshot imports continue to require `market_data.livermore_position_snapshot/import`.
- `tests/test_market_data_livermore_api.py` verifies all nine Livermore GET surfaces return 403 without an explicit read grant.
- Existing Livermore API, stock-detail, sector-rank, candidate-history, and result-meta smoke success paths now grant `market_data.livermore/read` explicitly before asserting business payload/envelope behavior.
- GitNexus evidence note: `npx.cmd -y gitnexus@latest query market_data_livermore` could not run in this Codex App sandbox because npm was in `only-if-cached` mode and the `gitnexus` package was not cached. Local route/test evidence was used instead.

Verification:

- Red proof before production change: `python -m pytest tests/test_market_data_livermore_api.py::test_livermore_read_surfaces_require_explicit_read_scope -q` failed because all nine Livermore GET paths returned 200 instead of 403.
- Green proof after production change: `python -m pytest tests/test_market_data_livermore_api.py::test_livermore_read_surfaces_require_explicit_read_scope -q`: `9 passed`.
- `python -m pytest tests/test_market_data_livermore_api.py -q`: `43 passed`.
- `python -m pytest tests/test_market_data_livermore_stock_detail.py -q`: `3 passed`.
- `python -m pytest tests/test_market_data_livermore_sector_rank_series.py -q`: `8 passed`.
- `python -m pytest tests/test_market_data_livermore_candidate_history.py::test_api_happy_and_filters tests/test_market_data_livermore_candidate_history.py::test_api_empty_table tests/test_market_data_livermore_candidate_history.py::test_api_limit_validation tests/test_market_data_livermore_candidate_history.py::test_strategy_optimization_api_happy_path_and_query_validation tests/test_market_data_livermore_candidate_history.py::test_strategy_score_api_happy_path_and_query_validation tests/test_market_data_livermore_candidate_history.py::test_cycle_proxy_backtest_api_happy_path_and_query_validation tests/test_market_data_livermore_candidate_history.py::test_candidate_history_portfolio_backtest_api_happy_path_and_query_validation -q`: `7 passed`.
- `python -m pytest tests/test_result_meta_on_all_ui_endpoints.py::test_ui_get_json_envelopes_include_result_meta_and_result -q`: `12 passed`.
- `python -m ruff check backend/app/api/routes/market_data_livermore.py tests/test_market_data_livermore_api.py tests/test_market_data_livermore_stock_detail.py tests/test_market_data_livermore_sector_rank_series.py tests/test_market_data_livermore_candidate_history.py tests/test_result_meta_on_all_ui_endpoints.py`: passed, with only the existing `.ruff_cache` access warning.
- `git diff --check -- backend/app/api/routes/market_data_livermore.py tests/test_market_data_livermore_api.py tests/test_market_data_livermore_stock_detail.py tests/test_market_data_livermore_sector_rank_series.py tests/test_market_data_livermore_candidate_history.py tests/test_result_meta_on_all_ui_endpoints.py`: passed.

Residual risk: this closes the nine Livermore GET/read surfaces covered here, but it does not prove every market-data-adjacent route or frontend consumer has been inventoried. The broader P1 read/write authorization inventory remains open.

### P1 remediated - ADB Analysis reads require read permission

Evidence:

- `backend/app/api/routes/adb_analysis.py` now checks `adb_analysis/read` before returning ADB read payloads for `/api/analysis/adb`, `/api/analysis/adb-comparison`, `/api/analysis/adb/comparison`, `/api/analysis/adb/monthly`, and `/api/analysis/adb/coverage`.
- The existing ADB backfill mutation boundary remains separate: `POST /api/analysis/adb/backfill` continues to require `adb_analysis/backfill`.
- `tests/test_adb_analysis_api.py` verifies all five ADB GET surfaces return 403 without an explicit read grant and do not call the ADB service/DuckDB read path before authorization.
- Existing ADB payload, analytical envelope, date/rate normalization, formal-fact, and fallback behavior tests now grant `adb_analysis/read` explicitly before asserting business payload behavior.
- GitNexus evidence note: `npx.cmd -y gitnexus@latest query adb_analysis --repo MOSS-V3` ran, but returned no symbols and warned that FTS indexes are missing/degraded. Local route/test evidence was used instead; no metric definition or calculation semantics were changed.

Verification:

- Red proof before production change: `python -m pytest tests/test_adb_analysis_api.py::test_adb_read_surfaces_require_explicit_read_scope -q` failed because the five ADB GET paths returned 500 after continuing into service/DuckDB logic instead of returning 403.
- Green proof after production change: `python -m pytest tests/test_adb_analysis_api.py::test_adb_read_surfaces_require_explicit_read_scope -q`: `5 passed`.
- `python -m pytest tests/test_adb_analysis_api.py -q`: `16 passed`.
- `python -m pytest tests/test_write_route_auth_contract.py::test_mutation_route_returns_403_without_scope_grant -q`: `28 passed`.
- `python -m pytest tests/test_write_route_auth_contract.py::test_refresh_route_requires_explicit_scope_grant -q`: `10 passed`.
- `ruff check backend/app/api/routes/adb_analysis.py tests/test_adb_analysis_api.py`: passed, with only the existing `.ruff_cache` access warnings.
- `git diff --check`: passed.

Residual risk: this closes the five ADB GET/read surfaces covered here, but it does not prove every ADB-adjacent frontend/client consumer or analysis route has been inventoried. The broader P1 read/write authorization inventory remains open.

### P1 remediated - Macro Bond Linkage analysis requires read permission

Evidence:

- `backend/app/api/routes/macro_bond_linkage.py` now checks `macro_bond_linkage/read` before returning `GET /api/macro-bond-linkage/analysis`.
- The route still keeps `report_date` as a FastAPI `date` query parameter; this change only adds authorization before the service call and does not change macro-bond linkage calculations, result metadata, or data-source semantics.
- `tests/test_macro_bond_linkage.py` verifies the route returns 403 without an explicit read grant and does not call `get_macro_bond_linkage` before authorization.
- Existing macro-bond linkage HTTP success tests now grant `macro_bond_linkage/read` explicitly; service/core tests remain unchanged because they do not exercise HTTP authorization.
- GitNexus evidence note: `npx.cmd -y gitnexus@latest query macro_bond_linkage --repo MOSS-V3` ran, but returned no symbols and warned that FTS indexes are missing/degraded. Local route/test evidence was used instead.

Verification:

- Red proof before production change: `python -m pytest tests/test_macro_bond_linkage.py::test_macro_bond_linkage_read_requires_explicit_read_scope -q` failed because the route continued into the patched service and returned 500 instead of 403.
- Green proof after production change: `python -m pytest tests/test_macro_bond_linkage.py::test_macro_bond_linkage_read_requires_explicit_read_scope -q`: `1 passed`.
- `python -m pytest tests/test_macro_bond_linkage.py -q`: `41 passed`.
- `ruff check backend/app/api/routes/macro_bond_linkage.py tests/test_macro_bond_linkage.py`: passed, with only the existing `.ruff_cache` access warnings.
- `git diff --check -- backend/app/api/routes/macro_bond_linkage.py tests/test_macro_bond_linkage.py docs/audits/2026-06-02-system-audit-first-pass.md`: passed.

Residual risk: this closes the single Macro Bond Linkage analytical GET surface covered here, but it does not prove every macro/market-data-adjacent route has been inventoried or assigned the intended public/internal/admin policy. The broader P1 read authorization inventory remains open.

### P1 remediated - Macro Vendor reads require read permission

Evidence:

- `backend/app/api/routes/macro_vendor.py` now checks `macro_vendor/read` before returning the seven Macro Vendor GET surfaces: `/ui/market-data/rates`, `/ui/market-data/catalog`, `/ui/preview/macro-foundation`, `/ui/macro/choice-series/latest`, `/ui/market-data/fx/formal-status`, `/ui/market-data/fx/analytical`, and `/ui/macro/choice-series/refresh-status`.
- `POST /ui/macro/choice-series/refresh` remains on the separate `macro_vendor.choice_series/refresh` permission and was not weakened into read permission.
- `tests/test_macro_query_contract_smoke.py` verifies all seven Macro Vendor GET surfaces return 403 without an explicit read grant and do not call the patched service/cache/governance read paths before authorization.
- Existing Macro Vendor envelope, Choice series, category filter, policy metadata, stale/fallback, and catalog compatibility tests now grant `macro_vendor/read` explicitly before asserting business payload behavior.
- `tests/test_result_meta_on_all_ui_endpoints.py` and `tests/test_choice_macro_delivery.py` now grant `macro_vendor/read` for successful Macro Vendor API contract checks.
- GitNexus evidence note: `npx.cmd -y gitnexus@latest query macro_vendor --repo MOSS-V3` ran, but returned no symbols and warned that FTS indexes are missing/degraded. Local route/test evidence was used instead.

Verification:

- Red proof before production change: `python -m pytest tests/test_macro_query_contract_smoke.py::test_macro_vendor_read_surfaces_require_explicit_read_scope -q` failed because all seven Macro Vendor GET paths continued into service/cache/governance logic and returned 500 instead of 403.
- Green proof after production change: `python -m pytest tests/test_macro_query_contract_smoke.py::test_macro_vendor_read_surfaces_require_explicit_read_scope -q`: `7 passed`.
- `python -m pytest tests/test_macro_query_contract_smoke.py -q`: `27 passed`.
- `python -m pytest tests/test_result_meta_on_all_ui_endpoints.py::test_ui_get_json_envelopes_include_result_meta_and_result tests/test_result_meta_on_all_ui_endpoints.py::test_macro_vendor_surfaces_emit_governed_envelopes -q`: `13 passed`.
- `python -m pytest tests/test_choice_macro_delivery.py::test_choice_macro_latest_api_returns_real_fact_rows tests/test_choice_macro_delivery.py::test_choice_macro_latest_api_aggregates_vendor_lineage_across_distinct_batch_versions tests/test_choice_macro_delivery.py::test_choice_macro_latest_api_returns_warning_quality_flag_when_duckdb_has_no_fact_rows tests/test_choice_macro_delivery.py::test_public_cross_asset_tushare_stock_rows_reach_latest_api_with_lineage -q`: `4 passed`.
- `python -m pytest tests/test_write_route_auth_contract.py::test_macro_choice_series_refresh_requires_explicit_refresh_grant -q`: `1 passed`.
- `ruff check backend/app/api/routes/macro_vendor.py tests/test_macro_query_contract_smoke.py tests/test_result_meta_on_all_ui_endpoints.py tests/test_choice_macro_delivery.py`: passed, with only the existing `.ruff_cache` access warnings.
- `git diff --check -- backend/app/api/routes/macro_vendor.py tests/test_macro_query_contract_smoke.py tests/test_result_meta_on_all_ui_endpoints.py tests/test_choice_macro_delivery.py`: passed.

Residual risk: this closes the seven Macro Vendor GET/read surfaces covered here, but it does not prove every macro, market-data, or choice-adjacent route has been inventoried or assigned the intended public/internal/admin policy. The broader P1 read authorization inventory remains open.

### P1 remediated - Macro Toolkit reads require read permission

Evidence:

- `backend/app/api/routes/macro_toolkit.py` now checks `macro_toolkit/read` before returning the five Macro Toolkit GET surfaces: `/ui/macro/toolkit/scripts`, `/ui/macro/toolkit/analysis`, `/ui/macro/toolkit/analysis/strategy-summaries`, `/ui/macro/toolkit/adversarial-signal`, and `/ui/macro/toolkit/choice-stock/refresh-status`.
- Existing Macro Toolkit mutation boundaries remain separate: CFFEX member-rank refresh, Choice stock refresh, source backfill, commodity futures refresh, and script execution still use their existing `refresh` or `execute` permissions rather than `macro_toolkit/read`.
- `tests/test_macro_toolkit_scripts.py` verifies all five Macro Toolkit GET surfaces return 403 without an explicit read grant and do not call patched source/status/analysis/adversarial read paths before authorization.
- Existing Macro Toolkit scripts, analysis, strategy summary, adversarial-signal, factor snapshot date, shadow portfolio, and Choice stock refresh-status success tests now grant `macro_toolkit/read` explicitly before asserting business or operational payload behavior.
- GitNexus evidence note: `npx.cmd -y gitnexus@latest query macro_toolkit --repo MOSS-V3` ran, but returned no symbols and warned that FTS indexes are missing/degraded. Local route/test evidence was used instead; no metric definition, date semantics, or calculation logic was changed.

Verification:

- Red proof before production change: `python -m pytest tests/test_macro_toolkit_scripts.py::test_macro_toolkit_read_surfaces_require_explicit_read_scope -q` failed because all five Macro Toolkit GET paths continued into patched business/read logic and returned 500 instead of 403.
- Green proof after production change: `python -m pytest tests/test_macro_toolkit_scripts.py::test_macro_toolkit_read_surfaces_require_explicit_read_scope -q`: `5 passed`.
- `python -m pytest tests/test_macro_toolkit_scripts.py::test_macro_toolkit_read_surfaces_require_explicit_read_scope tests/test_macro_toolkit_scripts.py::test_macro_toolkit_api_exposes_frontend_payload tests/test_macro_toolkit_scripts.py::test_macro_toolkit_scripts_surfaces_granted_commodity_futures_permission_for_fallback_user tests/test_macro_toolkit_scripts.py::test_macro_toolkit_scripts_surfaces_empty_commodity_futures_status tests/test_macro_toolkit_scripts.py::test_macro_toolkit_api_exposes_analysis_payload tests/test_macro_toolkit_scripts.py::test_macro_toolkit_analysis_core_scope_defers_slow_sections tests/test_macro_toolkit_scripts.py::test_macro_toolkit_strategy_summaries_endpoint_returns_deferred_strategy_payload tests/test_macro_toolkit_scripts.py::test_macro_toolkit_choice_stock_refresh_runs_history_and_full_factor_snapshot -q`: `12 passed`.
- `python -m pytest tests/test_macro_toolkit_scripts.py -q`: `68 passed`.
- `python -m pytest tests/test_macro_toolkit_factor_snapshot_dates.py tests/test_macro_toolkit_shadow_portfolio_report.py tests/test_macro_adversarial_signal_service.py::test_macro_toolkit_adversarial_signal_endpoint_emits_expected_result_meta -q`: `9 passed`.
- `python -m pytest tests/test_result_meta_on_all_ui_endpoints.py::test_ui_get_json_envelopes_include_result_meta_and_result -q`: `16 passed`.
- `python -m pytest tests/test_write_route_auth_contract.py::test_mutation_route_returns_403_without_scope_grant -q`: `28 passed`.
- `ruff check backend/app/api/routes/macro_toolkit.py tests/test_macro_toolkit_scripts.py tests/test_macro_toolkit_factor_snapshot_dates.py tests/test_macro_toolkit_shadow_portfolio_report.py tests/test_macro_adversarial_signal_service.py tests/test_result_meta_on_all_ui_endpoints.py`: passed, with only the existing `.ruff_cache` access warning.
- `git diff --check -- backend/app/api/routes/macro_toolkit.py tests/test_macro_toolkit_scripts.py tests/test_macro_toolkit_factor_snapshot_dates.py tests/test_macro_toolkit_shadow_portfolio_report.py tests/test_macro_adversarial_signal_service.py tests/test_result_meta_on_all_ui_endpoints.py docs/audits/2026-06-02-system-audit-first-pass.md`: passed.

Residual risk: this closes the five Macro Toolkit GET/read surfaces covered here, but it does not prove every macro/tooling/market-data-adjacent route has been inventoried or assigned the intended public/internal/admin policy. The broader P1 read/write authorization inventory remains open.

### P1 remediated - Agent Workbench enabled endpoints require read permission

Evidence:

- `backend/app/api/routes/agent.py` now checks `agent/read` before enabled Agent execution paths return live workbench payloads: `POST /api/agent/query`, `POST /api/agent/runs`, and `GET /api/agent/runs/{run_id}`.
- Disabled Agent behavior remains fail-closed and explicit: when `agent_enabled` is false, the query and run creation endpoints still return the disabled 503 stub instead of a live envelope, and this does not require `agent/read`.
- `tests/test_agent_api_contract.py` verifies the three enabled endpoints return 403 without an explicit read grant and do not call patched execution, run creation, or run-owner lookup paths before authorization.
- Existing Agent query, provider-routing, managed-run, run-status, enabled-path smoke, and disabled-stub tests now grant `agent/read` explicitly when exercising enabled behavior.
- The existing read-only request guard remains separate: mutating Agent action context still returns 403 before execution, and `agent/read` does not grant write/mutation capability.
- GitNexus evidence note: `npx.cmd -y gitnexus@latest query agent --repo MOSS-V3` ran, but returned no symbols and warned that FTS indexes are missing/degraded. Local route/test evidence was used instead; no Agent provider, tool execution, run persistence, metric definition, date semantics, or calculation logic was changed.

Verification:

- Red proof before production change: `python -m pytest tests/test_agent_api_contract.py::test_agent_enabled_endpoints_require_explicit_read_scope -q` failed because `/api/agent/query` entered the patched Agent execution path and returned 500 instead of 403.
- Green proof after production change: `python -m pytest tests/test_agent_api_contract.py::test_agent_enabled_endpoints_require_explicit_read_scope -q`: `1 passed`.
- `python -m pytest tests/test_agent_api_contract.py tests/test_agent_runs_api.py tests/test_agent_enabled_path_smoke.py tests/test_agent_api.py::test_agent_query_is_disabled_without_governed_result_meta tests/test_result_meta_on_all_ui_endpoints.py::test_agent_post_disabled_stub_is_explicit_not_live_envelope -q`: `38 passed`.
- `python -m pytest tests/test_write_route_auth_contract.py::test_mutation_route_returns_403_without_scope_grant -q`: `28 passed`.
- `ruff check backend/app/api/routes/agent.py tests/test_agent_api_contract.py tests/test_agent_runs_api.py tests/test_agent_enabled_path_smoke.py tests/test_agent_api.py tests/test_result_meta_on_all_ui_endpoints.py`: passed, with only the existing `.ruff_cache` access warnings.
- `git diff --check -- backend/app/api/routes/agent.py tests/test_agent_api_contract.py tests/test_agent_runs_api.py tests/test_agent_enabled_path_smoke.py tests/test_agent_api.py tests/test_result_meta_on_all_ui_endpoints.py docs/audits/2026-06-02-system-audit-first-pass.md`: passed.

Residual risk: this closes the enabled Agent Workbench query/run/status HTTP boundary covered here, but it does not prove every Agent-adjacent frontend/client path or future provider capability has the intended public/internal/admin policy. The broader P1 read/write authorization inventory remains open.

### P1 remediated - Production startup rejects trusted user headers

Root cause: `MOSS_AUTH_TRUST_X_USER_ROLE_FOR_DEV_TEST` controlled `X-User-Id` / `X-User-Role` trust solely through environment truthiness, while `backend.app.main` did not reject the switch when `MOSS_ENVIRONMENT=production`.

Fix:

- Added `validate_auth_startup_guardrails()` in `backend/app/security/auth_context.py`.
- Called it from `backend/app/main.py` immediately after settings load, before middleware/router exposure.
- Preserved development/test trusted-header behavior for existing authorization tests.

Verification:

- Red proof before production change: `python -m pytest tests/test_startup_auth_guardrails.py -q` failed because the app import did not raise.
- Green proof after production change: `python -m pytest tests/test_startup_auth_guardrails.py -q`: `1 passed`.
- Regression proof: `python -m pytest tests/test_auth_context.py tests/test_settings_contract.py -q`: `19 passed`.
- Test-isolation proof after adding the production startup guard: `tests/helpers.py` now removes a manually loaded module from `sys.modules` if import execution raises, preventing the expected production-startup `RuntimeError` from leaving a half-initialized `backend.app.main` without included routes.
- Regression proof after test-isolation cleanup: `python -m pytest tests/test_startup_auth_guardrails.py tests/test_write_route_auth_contract.py::test_mutation_route_returns_403_without_scope_grant -q`: `29 passed`.

Residual risk: this closes the production trusted-header misconfiguration path only. The broader GET route authorization inventory remains open.

### P1 remediated - Livermore gate supplement refresh requires refresh permission

Evidence:

- `backend/app/api/routes/market_data_livermore.py` now checks `market_data.livermore_gate_supplement/refresh` before running `POST /ui/market-data/livermore/refresh-gate-supplement`.
- The refresh boundary remains separate from the Livermore read boundary: `market_data.livermore/read` does not grant write access to `fact_livermore_gate_supplement_daily` materialization.
- `tests/test_write_route_auth_contract.py` adds the Livermore gate-supplement refresh route to the scoped-refresh contract: no grant returns 403 without calling the patched refresh service, while an explicit refresh grant allows the call.

Verification:

- Red proof before production change: `python -m pytest tests/test_write_route_auth_contract.py::test_refresh_route_requires_explicit_scope_grant -q` failed because `/ui/market-data/livermore/refresh-gate-supplement` returned 200 and called the refresh service without a scope grant.
- Green proof after production change: `python -m pytest tests/test_write_route_auth_contract.py::test_refresh_route_requires_explicit_scope_grant -q`: `10 passed`.
- `python -m pytest tests/test_market_data_livermore_api.py -q`: `43 passed`.
- `python -m ruff check backend/app/api/routes/market_data_livermore.py tests/test_market_data_livermore_api.py tests/test_market_data_livermore_stock_detail.py tests/test_market_data_livermore_sector_rank_series.py tests/test_market_data_livermore_candidate_history.py tests/test_result_meta_on_all_ui_endpoints.py tests/test_write_route_auth_contract.py`: passed, with only the existing `.ruff_cache` access warnings.
- `git diff --check -- backend/app/api/routes/market_data_livermore.py tests/test_market_data_livermore_api.py tests/test_market_data_livermore_stock_detail.py tests/test_market_data_livermore_sector_rank_series.py tests/test_market_data_livermore_candidate_history.py tests/test_result_meta_on_all_ui_endpoints.py tests/test_write_route_auth_contract.py docs/audits/2026-06-02-system-audit-first-pass.md`: passed.

Residual risk: this closes the Livermore gate-supplement refresh mutation covered here, but it does not prove every market-data or Livermore-adjacent mutation has been inventoried. The broader P1 read/write authorization inventory remains open.

### P1 partially remediated - Positions read endpoints require read permission

Evidence:

- `backend/app/api/routes/positions.py:17-31` centralizes `positions/read` enforcement.
- `backend/app/api/routes/positions.py:34-207` applies that read check before all positions read handlers: bond sub-types/list, counterparty bonds, interbank product-types/list/split, rating/industry stats, customer details, and customer trend.
- `tests/test_positions_api_contract.py:288-316` verifies the ten positions GET surfaces return 403 without an explicit read grant.
- Existing positions contract tests now seed `positions/read` explicitly before asserting envelope shape, pagination, date fallback, rate normalization, customer details, and interbank split behavior.

Verification:

- Red proof before production change: `python -m pytest tests/test_positions_api_contract.py::test_positions_read_surfaces_require_explicit_read_scope -q` failed because `/api/positions/bonds/sub_types` returned 200 instead of 403.
- Green proof after production change: `python -m pytest tests/test_positions_api_contract.py::test_positions_read_surfaces_require_explicit_read_scope -q`: `1 passed`.
- `python -m pytest tests/test_positions_api_contract.py -q`: `13 passed`.
- `python -m pytest tests/test_result_meta_on_all_ui_endpoints.py -q`: `26 passed`.
- `python -m pytest tests/test_backend_release_suite.py::test_backend_release_suite_declares_bounded_phase2_gate -q`: `1 passed`.
- `python -m ruff check backend/app/api/routes/positions.py tests/test_positions_api_contract.py`: passed.

Residual risk: this narrows the global API-read P1, but it does not prove every positions-adjacent or downstream consumer route has been inventoried.

### P1 partially remediated - External-data read endpoints require read permission

Evidence:

- `backend/app/api/routes/external_data.py:26-37` centralizes `external_data/read` enforcement.
- `backend/app/api/routes/external_data.py:40-122` applies that read check before catalog, catalog entry, domain catalog, series data, and recent series data handlers.
- `tests/test_external_data_api.py:54-99` verifies the five external-data GET surfaces return 403 without an explicit read grant.
- Existing external-data API tests now seed `external_data/read` explicitly before validating catalog listing, domain filtering, series data, recent series data, and missing-series 404 behavior.

Verification:

- Red proof before production change: `python -m pytest tests/test_external_data_api.py::test_external_data_read_surfaces_require_explicit_read_scope -q` failed because `/api/external-data/catalog` returned 200 instead of 403 after the catalog table was seeded.
- `python -m pytest tests/test_external_data_api.py tests/test_external_data_api_m2b.py -q`: `3 passed`.
- `python -m pytest tests/test_result_meta_on_all_ui_endpoints.py -q`: `26 passed`.
- `python -m ruff check backend/app/api/routes/external_data.py tests/test_external_data_api.py tests/test_external_data_api_m2b.py`: passed.

Residual risk: this narrows the global API-read P1, but it does not prove every external-data consumer route has been inventoried.

### P1 remediated - Cube Query read endpoints require read permission

Evidence:

- `backend/app/api/routes/cube_query.py:24-35` centralizes `cube/read` enforcement for cube read metadata.
- `backend/app/api/routes/cube_query.py:38-46` now applies the read check before `POST /api/cube/query` executes the analytical bridge against formal/analytical cube data.
- `backend/app/api/routes/cube_query.py:54-59` applies the read check before `/api/cube/dimensions/{fact_table}` describes promoted dimensions and measures.
- `tests/test_cube_query_api.py` verifies the query endpoint returns 403 without an explicit read grant and does not enter the analytical bridge first.
- Existing query and dimensions contract tests now seed `cube/read` explicitly before asserting formal response, invalid request, unavailable storage, promoted dimensions, and unknown fact-table behavior.
- GitNexus evidence note: `npx.cmd -y gitnexus@latest query cube_query` could not run because the restricted npm cache did not contain `gitnexus` (`ENOTCACHED`). Local AST route inventory, route code, and focused tests were used instead.

Verification:

- Red proof before production change: `python -m pytest tests/test_cube_query_api.py::test_cube_dimensions_route_requires_explicit_read_scope -q` failed because `/api/cube/dimensions/bond_analytics` returned 200 instead of 403.
- Red proof before query production change: `python -m pytest tests/test_cube_query_api.py::test_cube_query_route_requires_explicit_read_scope -q` failed because `/api/cube/query` reached the patched analytical bridge and returned 503 instead of 403.
- Green proof after query production change: `python -m pytest tests/test_cube_query_api.py::test_cube_query_route_requires_explicit_read_scope -q`: `1 passed`.
- `python -m pytest tests/test_cube_query_api.py -q`: `7 passed`.
- `python -m pytest tests/test_write_route_auth_contract.py::test_mutation_route_returns_403_without_scope_grant -q`: `28 passed`.
- `python -m ruff check backend/app/api/routes/cube_query.py tests/test_cube_query_api.py`: passed, with only the existing `.ruff_cache` access warnings.
- `git diff --check -- backend/app/api/routes/cube_query.py tests/test_cube_query_api.py docs/audits/2026-06-02-system-audit-first-pass.md`: passed.

Residual risk: this closes the current Cube Query HTTP read surfaces, but it does not prove every future cube/query-adjacent route or frontend consumer has the intended public/internal/admin policy. The broader P1 read/write authorization inventory remains open.

### P1 regression guard - Backend route authorization inventory covers read-like and mutation surfaces

Evidence:

- `tests/test_boundary_surface_inventory.py` now parses `backend/app/api/routes/*.py` route decorators and records method/path/function authorization surfaces plus reachable `authz_scopes`.
- The inventory extracts direct `ensure_user_allowed(resource=..., action=...)` scopes and parameterized helper calls such as source-preview's shared read helper.
- Backend GET routes and read-like POST routes must reach `ensure_user_allowed`, except explicitly public health/current-user echo surfaces.
- Backend POST/PUT/PATCH/DELETE routes must reach `ensure_user_allowed`, except explicitly reserved Tushare NPR ingest boundaries.
- Authorized backend surfaces must expose at least one stable resource/action scope.
- Read-like authorized backend surfaces must include a `read` action; mutation-like authorized backend surfaces must include a non-read action unless explicitly read-like or reserved.
- The inventory also locks the current executive compatibility behavior: without `executive/read`, `/ui/risk/overview`, `/ui/home/contribution`, and `/ui/home/alerts` now fail at authorization with 403 before reaching the reserved 503 boundary.
- 2026-06-04 follow-up: `tests/test_boundary_surface_inventory.py` now creates an available empty SQLite scope store for boundary cases expected to return 403. This keeps the executive compatibility assertion on the intended "scope store available, no grant" path rather than the separate 503 "scope store unavailable" path.
- `tests/helpers.py` now cleans up failed manual module loads, so expected startup import failures cannot poison later route-registration tests with a half-initialized app module.

Verification:

- Failure proof before empty-scope-store test fixture: `python -m pytest tests/test_boundary_surface_inventory.py tests/test_write_route_auth_contract.py::test_mutation_route_returns_403_without_scope_grant -q` failed with `3 failed, 46 passed` because `/ui/risk/overview`, `/ui/home/alerts`, and `/ui/home/contribution` returned `503 {"detail":"User scope store is unavailable."}` instead of proving the expected no-grant `403`.
- Green proof after empty-scope-store test fixture: `python -m pytest tests/test_boundary_surface_inventory.py tests/test_write_route_auth_contract.py::test_mutation_route_returns_403_without_scope_grant -q`: `49 passed`.
- Failure proof before test-isolation cleanup: `python -m pytest tests/test_boundary_surface_inventory.py tests/test_cube_query_api.py tests/test_startup_auth_guardrails.py tests/test_write_route_auth_contract.py::test_mutation_route_returns_403_without_scope_grant -q` failed with `28 failed, 27 passed` because the expected startup guardrail import failure left a half-initialized `backend.app.main` cached; later mutation-route checks saw 404 instead of authorized route handlers.
- Green proof after test-isolation cleanup: `python -m pytest tests/test_startup_auth_guardrails.py tests/test_write_route_auth_contract.py::test_mutation_route_returns_403_without_scope_grant -q`: `29 passed`.
- Combined authorization proof after cleanup: `python -m pytest tests/test_boundary_surface_inventory.py tests/test_cube_query_api.py tests/test_startup_auth_guardrails.py tests/test_write_route_auth_contract.py::test_mutation_route_returns_403_without_scope_grant -q`: `55 passed`.
- Route inventory policy-scope proof: `python -m pytest tests/test_boundary_surface_inventory.py -q`: `21 passed`.
- `python -m ruff check backend/app/api/routes/cube_query.py backend/app/main.py backend/app/security/auth_context.py tests/helpers.py tests/test_cube_query_api.py tests/test_startup_auth_guardrails.py tests/test_boundary_surface_inventory.py`: passed, with only the existing `.ruff_cache` access warnings.
- `git diff --check -- backend/app/api/routes/cube_query.py backend/app/main.py backend/app/security/auth_context.py tests/helpers.py tests/test_cube_query_api.py tests/test_startup_auth_guardrails.py tests/test_boundary_surface_inventory.py docs/audits/2026-06-02-system-audit-first-pass.md`: passed.

Residual risk: the AST inventory now proves reachable stable resource/action scopes and basic read/mutation action class for authorized routes, but not the final intended public/internal/admin classification or business-owner naming semantics. Policy classification and consumer-level review remain open.

### P1 partially remediated - Research calendar endpoint requires read permission

Evidence:

- `backend/app/api/routes/research_calendar.py:16-27` centralizes `research_calendar/read` enforcement.
- `backend/app/api/routes/research_calendar.py:30-38` applies the read check before `/ui/calendar/supply-auctions` returns supply and auction calendar events.
- `tests/test_supply_auction_calendar_api.py` verifies the route returns 403 without an explicit read grant and continues to return the analytical supply-auction envelope with `research_calendar/read`.

Verification:

- Red proof before production change: `python -m pytest tests/test_supply_auction_calendar_api.py::test_supply_auction_calendar_route_requires_explicit_read_scope -q` failed because `/ui/calendar/supply-auctions` returned 200 instead of 403.
- `python -m pytest tests/test_supply_auction_calendar_api.py -q`: `3 passed`.
- `python -m ruff check backend/app/api/routes/research_calendar.py tests/test_supply_auction_calendar_api.py`: passed.

Residual risk: this narrows the global API-read P1, but it does not prove every calendar or research-adjacent route has been inventoried.

### P1 partially remediated - Formal calculation boundary drift remains in `bond_analytics_service`

Evidence:

- `backend/app/core_finance/bond_analytics/dv01.py` now owns DV01 shock parsing/expansion, face-weighted modified duration, absolute-exposure share denominator logic, tenor/bond/issuer payload calculations, reconciliation payload calculations, movement bond payloads, movement attribution payloads, action-plan risk levels, action-plan scenario payloads, action-plan tenor/issuer/bond recommendation payloads, and DV01 scope summaries.
- `backend/app/core_finance/action_attribution.py` now owns the bond analytics row -> action-attribution core input line mapping via `bond_analytics_action_line_payload(...)`, action-attribution success payload rules via `build_action_attribution_success_payload(...)`, and placeholder payload shaping via `build_action_attribution_placeholder_payload(...)`, including status/default propagation, available/missing/blocked component lists, computed-at fallback, warning de-duplication, and warning detail rows.
- `backend/app/services/bond_analytics_service.py` now calls `dv01_core` for `get_dv01_risk`, `get_dv01_reconciliation`, `get_dv01_movement`, shared DV01 movement summaries, and `get_dv01_action_plan` recommendation payloads, and calls `bond_analytics_action_line_payload(...)`, `compute_action_attribution_bonds(...)`, `build_action_attribution_success_payload(...)`, and `build_action_attribution_placeholder_payload(...)` for action-attribution payload shaping, while keeping repository access, limit-config resolution, PnL lookup, analysis-adapter fallback calls, schema validation, sorting, and result metadata/envelope assembly in the service layer.
- `tests/core_finance/test_bond_analytics_dv01.py` locks the core DV01 share denominator, face-weighted duration, shock parsing/expansion order, sorted tenor/bond/issuer payload behavior, movement row calculations, classification transfer labels, movement attribution residual reconciliation, action-plan risk levels, bp scenario losses, and suggested DV01 reduction shares.
- Remaining drift: `backend/app/services/bond_analytics_service.py` still defines `_build_action_attribution_pnl_by_key`, `_build_action_attribution_placeholder_response`, `_build_action_attribution_success_response`, and `get_action_attribution`, while `get_action_attribution` still orchestrates PnL lookup, analysis-adapter fallback calls, schema validation, formal metadata, and result-envelope assembly.

Impact: the project contract says formal finance calculations should live under `backend/app/core_finance/`, while services should orchestrate repositories, schemas, and metadata. The highest-volume DV01 risk/reconciliation/movement/action-plan helpers are now behind `core_finance`, reducing duplicate/drifting logic risk, but action-attribution orchestration can still diverge if left service-bound.

Verification:

- Red proof before core module addition: `python -m pytest tests/core_finance/test_bond_analytics_dv01.py -q` failed with `ModuleNotFoundError: No module named 'backend.app.core_finance.bond_analytics.dv01'`.
- Green proof after risk/reconciliation migration: `python -m pytest tests/core_finance/test_bond_analytics_dv01.py -q`: `2 passed`.
- Green proof after movement migration: `python -m pytest tests/core_finance/test_bond_analytics_dv01.py -q`: `3 passed`.
- Red proof before action-plan migration: `python -m pytest tests/core_finance/test_bond_analytics_dv01.py -q` failed with `ImportError: cannot import name 'build_dv01_action_bond_payloads'`.
- Green proof after action-plan migration: `python -m pytest tests/core_finance/test_bond_analytics_dv01.py -q`: `4 passed`.
- Red proof before action-attribution bond-line migration: `python -m pytest tests/core_finance/test_action_attribution.py -q` failed with `ImportError: cannot import name 'bond_analytics_action_line_payload'`.
- Green proof after action-attribution bond-line migration: `python -m pytest tests/core_finance/test_action_attribution.py -q`: `2 passed`.
- Red proof before action-attribution success-payload migration: `python -m pytest tests/core_finance/test_action_attribution.py -q` failed with `ImportError: cannot import name 'build_action_attribution_success_payload'`.
- Green proof after action-attribution success-payload migration: `python -m pytest tests/core_finance/test_action_attribution.py -q`: `3 passed`.
- Service success-path proof after action-attribution success-payload migration: `python -m pytest tests/test_bond_analytics_service.py::test_action_attribution_success_response_uses_core_payload_builder -q`: `1 passed`.
- Red proof before action-attribution placeholder-payload migration: `python -m pytest tests/core_finance/test_action_attribution.py -q` failed with `ImportError: cannot import name 'build_action_attribution_placeholder_payload'`.
- Focused proof after action-attribution placeholder-payload migration: `python -m pytest tests/core_finance/test_action_attribution.py tests/test_analysis_service_adapters.py::test_bond_action_service_uses_placeholder_envelope_builder tests/test_analysis_service_adapters.py::test_bond_action_service_uses_schema_default_status_when_summary_omits_it tests/test_bond_analytics_service.py::test_action_attribution_success_response_uses_core_payload_builder -q`: `7 passed`.
- Focused DV01 movement service proof: `python -m pytest tests/test_bond_analytics_service.py::test_bond_analytics_dv01_movement_explains_oci_delta_with_prior_report_date tests/test_bond_analytics_service.py::test_bond_analytics_dv01_movement_without_prior_returns_warning -q`: `2 passed`.
- Focused DV01 action-plan service proof: `python -m pytest tests/test_bond_analytics_service.py::test_bond_analytics_dv01_action_plan_flags_risk_and_hedge_size tests/test_bond_analytics_service.py::test_bond_analytics_dv01_action_plan_uses_formal_limit_config tests/test_bond_analytics_service.py::test_bond_analytics_dv01_action_plan_marks_page_threshold_fallback tests/test_bond_analytics_service.py::test_bond_analytics_dv01_action_plan_empty_scope_returns_warning -q`: `4 passed`.
- Focused action-attribution service proof: `python -m pytest tests/test_bond_action_attribution_unavailable.py tests/test_analysis_service_adapters.py::test_bond_action_service_uses_placeholder_envelope_builder tests/test_analysis_service_adapters.py::test_bond_action_service_uses_schema_default_status_when_summary_omits_it -q`: `3 passed`.
- Focused DV01 service proof: `python -m pytest tests/test_bond_analytics_service.py::test_bond_analytics_dv01_risk_defaults_to_oci_scope_and_parallel_shocks tests/test_bond_analytics_service.py::test_bond_analytics_dv01_risk_all_scope_groups_tenors_and_sorts_by_abs_dv01 tests/test_bond_analytics_service.py::test_bond_analytics_dv01_reconciliation_all_scope_and_abs_share tests/test_bond_analytics_service.py::test_bond_analytics_dv01_movement_explains_oci_delta_with_prior_report_date tests/test_bond_analytics_service.py::test_bond_analytics_dv01_action_plan_flags_risk_and_hedge_size -q`: `5 passed`.
- `python -m pytest tests/test_bond_analytics_service.py -q`: `39 passed`.
- API envelope proof: `python -m pytest tests/test_bond_analytics_api.py::test_bond_analytics_dv01_risk_returns_numeric_payload tests/test_bond_analytics_api.py::test_bond_analytics_dv01_reconciliation_returns_numeric_payload tests/test_bond_analytics_api.py::test_bond_analytics_dv01_movement_returns_numeric_payload tests/test_bond_analytics_api.py::test_bond_analytics_dv01_action_plan_returns_numeric_payload -q`: `4 passed`.
- Combined proof after action-plan migration: `python -m pytest tests/core_finance/test_bond_analytics_dv01.py tests/test_bond_analytics_service.py tests/test_bond_analytics_api.py::test_bond_analytics_dv01_risk_returns_numeric_payload tests/test_bond_analytics_api.py::test_bond_analytics_dv01_reconciliation_returns_numeric_payload tests/test_bond_analytics_api.py::test_bond_analytics_dv01_movement_returns_numeric_payload tests/test_bond_analytics_api.py::test_bond_analytics_dv01_action_plan_returns_numeric_payload -q`: `47 passed`.
- Combined proof after action-attribution bond-line migration: `python -m pytest tests/core_finance/test_action_attribution.py tests/core_finance/test_bond_analytics_dv01.py tests/test_bond_action_attribution_unavailable.py tests/test_analysis_service_adapters.py::test_bond_action_service_uses_placeholder_envelope_builder tests/test_analysis_service_adapters.py::test_bond_action_service_uses_schema_default_status_when_summary_omits_it tests/test_bond_analytics_service.py tests/test_bond_analytics_api.py::test_bond_analytics_dv01_risk_returns_numeric_payload tests/test_bond_analytics_api.py::test_bond_analytics_dv01_reconciliation_returns_numeric_payload tests/test_bond_analytics_api.py::test_bond_analytics_dv01_movement_returns_numeric_payload tests/test_bond_analytics_api.py::test_bond_analytics_dv01_action_plan_returns_numeric_payload -q`: `52 passed`.
- Combined proof after action-attribution success-payload migration: `python -m pytest tests/core_finance/test_action_attribution.py tests/core_finance/test_bond_analytics_dv01.py tests/test_bond_action_attribution_unavailable.py tests/test_analysis_service_adapters.py::test_bond_action_service_uses_placeholder_envelope_builder tests/test_analysis_service_adapters.py::test_bond_action_service_uses_schema_default_status_when_summary_omits_it tests/test_bond_analytics_service.py::test_action_attribution_success_response_uses_core_payload_builder tests/test_bond_analytics_api.py::test_bond_analytics_dv01_risk_returns_numeric_payload tests/test_bond_analytics_api.py::test_bond_analytics_dv01_reconciliation_returns_numeric_payload tests/test_bond_analytics_api.py::test_bond_analytics_dv01_movement_returns_numeric_payload tests/test_bond_analytics_api.py::test_bond_analytics_dv01_action_plan_returns_numeric_payload -q`: `15 passed`.
- Residual-helper search after action-plan migration: `rg -n "def _parse_dv01_shocks|def _expand_parallel_shocks|def _face_weighted_modified_duration|def _total_abs_dv01|def _dv01_share|def _build_dv01_tenor_buckets|def _build_dv01_top_bonds|def _build_dv01_top_issuers|def _build_dv01_reconciliation_rows|def _dv01_scope_summary|def _estimated_dv01_from_face_duration|def _dv01_movement_reason|def _build_dv01_movement_bond_rows|def _build_dv01_movement_attribution|def _dv01_action_risk_level|def _dv01_action_scenario_level|def _build_dv01_action_scenarios|def _suggested_reduction_for_share|def _build_dv01_action_tenors|def _build_dv01_action_issuers|def _build_dv01_action_bonds|_build_dv01_tenor_buckets\\(|_total_abs_dv01\\(|_build_dv01_movement_bond_rows\\(|_build_dv01_movement_attribution\\(|_build_dv01_action_scenarios\\(|_build_dv01_action_tenors\\(|_build_dv01_action_issuers\\(|_build_dv01_action_bonds\\(" backend/app/services/bond_analytics_service.py tests/test_bond_analytics_service.py`: no matches.
- `python -m ruff check backend/app/core_finance/action_attribution.py backend/app/core_finance/bond_analytics/dv01.py backend/app/services/bond_analytics_service.py tests/core_finance/test_action_attribution.py tests/core_finance/test_bond_analytics_dv01.py tests/test_bond_analytics_service.py tests/test_bond_action_attribution_unavailable.py tests/test_analysis_service_adapters.py`: passed, with only the existing `.ruff_cache` access warnings.
- `python -m ruff check backend/app/core_finance/action_attribution.py backend/app/services/bond_analytics_service.py tests/core_finance/test_action_attribution.py tests/test_bond_analytics_service.py`: passed, with only the existing `.ruff_cache` access warnings.
- `python -m ruff check backend/app/core_finance/action_attribution.py backend/app/services/bond_analytics_service.py tests/core_finance/test_action_attribution.py`: passed.
- `git diff --check -- backend/app/core_finance/action_attribution.py backend/app/core_finance/bond_analytics/dv01.py backend/app/services/bond_analytics_service.py tests/core_finance/test_bond_analytics_dv01.py docs/audits/2026-06-02-system-audit-first-pass.md`: passed; `rg -n "[ \\t]+$" tests/core_finance/test_action_attribution.py`: no matches for the new untracked test file.
- `git diff --check -- backend/app/core_finance/action_attribution.py backend/app/services/bond_analytics_service.py tests/core_finance/test_action_attribution.py tests/test_bond_analytics_service.py docs/audits/2026-06-02-system-audit-first-pass.md`: passed.

Recommendation: continue with a bounded follow-up for the remaining action-attribution orchestration, or document a temporary exception that keeps PnL/repository lookup, analysis-adapter fallback calls, schema validation, and result-envelope assembly in the service layer. Until then, treat the residual as an architectural watch item rather than fully closed.

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

### P2 - Test governance lacks explicit coverage gates

Evidence:

- `.github/workflows/ci.yml:33` runs `python scripts/backend_release_suite.py --governance-audit-output governance-lineage-audit.json`, not a coverage-measured pytest job.
- `.github/workflows/ci.yml:68` runs `npx vitest run`, `.github/workflows/ci.yml:71` runs `npm run debt:audit`, and `.github/workflows/ci.yml:74` runs `npm run build`.
- `.github/workflows/ci.yml:112` runs `npx eslint .` as a separate lint job.
- `pytest.ini:1-15` defines test roots and ignore globs, but no `--cov` or coverage threshold.
- `frontend/package.json:15` maps `test` to `vitest run`; no coverage command or threshold is present in the sampled scripts.

Positive counter-evidence: the current targeted and full test suites are broad and green, including `3645 passed, 6 skipped` for the backend suite and `1619` frontend tests passed in the recorded full frontend run.

Impact: CI proves many regressions are covered, but it does not quantify whether a changed business page or service has enough test coverage. This matters most for page-level metric correctness, stale/fallback paths, and formal/candidate metadata boundaries.

Recommendation: add a non-blocking coverage report first, then promote focused coverage gates for high-risk business display paths. Avoid one huge global threshold until generated/legacy surfaces are separated.

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
  - After the 2026-06-03 Concentration Monitor fix, `get_credit_spread_migration(date(2026, 3, 31))` returns `basis=analytical`, `formal_use_allowed=false`, `quality_flag=warning`, `date_basis=bond_analytics_report_date`, `source_surface=bond_analytics`, report-date metadata, formal bond-analytics source table evidence, applied spread-scenario filters, and evidence-row counts from the fact rows used by the payload. Existing curve fallback metadata (`vendor_stale` / `vendor_unavailable`) is preserved.
  - Control sample: `adb_envelope_for_dates("2026-03-01", "2026-03-31")` and `adb_monthly_envelope(2026)` correctly return `basis=analytical` and `formal_use_allowed=false` while using formal tables as inputs. This is the cleaner pattern for candidate/analytical page semantics.
- Local MCP fallback lineage evidence found zero records for `positions.bonds.list`, `cashflow_projection.overview`, `bond_analytics.credit_spread_migration`, `MTR-CFP-001`, and `MTR-CON-001`, so the remaining formal-use metadata is not backed by page/metric lineage closure in the current governance streams. `bond_dashboard.headline_kpis` still lacks dictionary-level lineage closure, so its new analytical metadata should remain until a full promotion package exists.
- Frontend evidence already shows user-facing boundary copy for two sampled surfaces:
  - `frontend/src/features/bond-dashboard/pages/BondDashboardPage.tsx` renders `bond-dashboard-headline-candidate-boundary`.
  - `frontend/src/features/positions/components/PositionsView.tsx` renders `positions-list-candidate-boundary`.

Impact: the sampled candidate/page-contract-pending API metadata no longer sends a formal-use approval signal, reducing the risk that users or downstream consumers treat these page fields as approved formal metrics. The fields still remain candidate display metrics until dictionary-level approval, golden samples, and lineage closure exist.

Recommendation: keep the new Ledger, Bond Dashboard headline, Positions, Cashflow Projection, and Concentration Monitor regression tests as the baseline. Future promotion must update the metric dictionary rows, page contracts, golden samples, lineage records, and tests together before any of these page-level candidate fields can return `formal_use_allowed=true`.

### Resolved - `PAGE-RISK-001` risk tensor is now page-bundle seeded and lineage-mapped

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
  - Local `moss-lineage-evidence` fallback query now expands `PAGE-RISK-001` to `fact_formal_risk_tensor_daily`, `agent.risk_tensor`, `risk_tensor`, `risk.tensor`, and `risk-tensor`, returning existing `agent_audit` records for the formal risk tensor table and result surface. This is an explicit query mapping, not a new governance stream record.
  - Real local MCP query proof: `find_lineage_records({"query":"PAGE-RISK-001","max_results":3})` returns `expanded_queries=["PAGE-RISK-001","fact_formal_risk_tensor_daily","agent.risk_tensor","risk_tensor","risk.tensor","risk-tensor"]`, with the first records matched on `fact_formal_risk_tensor_daily`, `stream="agent_audit"`, `result_kind="agent.risk_tensor"`, and `tables_used=["fact_formal_risk_tensor_daily"]`.
  - Regression proof: `python -m pytest tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_page_risk_contract_to_risk_tensor_records tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_reads_governance_stream_status -q`: `2 passed`.
  - `python -m ruff check scripts/mcp/moss_project_mcp.py tests/test_project_mcp_servers.py`: passed, with only the existing `.ruff_cache` access warnings.
  - `git diff --check -- scripts/mcp/moss_project_mcp.py tests/test_project_mcp_servers.py`: passed.

Impact: `risk-tensor` now has a canonical MCP page trace bundle containing route, API, source lineage anchors, metrics, golden samples, code touchpoints, tests, and guardrails. The latest sampled data still has `warning` quality, so release messaging must preserve warning visibility.

Remaining risk: `PAGE-RISK-001` now has explicit query-level mapping to existing risk tensor lineage evidence, but not a separate governance stream row whose primary key is the page contract ID. Every governed metric page has not yet received the same contract/catalog/lineage/bundle audit.

### Resolved - Page-contract trace bundle coverage has first-pass closure

Evidence from the 2026-06-03 page-contract coverage matrix and the 2026-06-04 Business Type PnL continuation:

- `docs/page_contracts.md` currently exposes 26 `PAGE-*` page-contract IDs.
- `product_page_trace_bundles()` now resolves 28 unique seeded trace IDs after adding `PAGE-PNL-BY-BUSINESS-001` and the observational `GAP-STOCK-ANALYSIS-PAGE`; the Product Category bundle still keeps the older `PAGE-PROD-CAT-001` as its canonical `page_id` while accepting `PAGE-PROD-CAT-PNL-001` as an alias:
  - `PAGE-DASH-001` -> `dashboard-home`
  - `PAGE-RISK-001` -> `risk-tensor`
  - `PAGE-BALANCE-001` -> `balance-analysis`
  - `PAGE-BAL-MOVE-001` -> `balance-movement-analysis`
  - `PAGE-BOND-001` -> `bond-dashboard`
  - `PAGE-POS-001` -> `positions`
  - `PAGE-MKT-001` -> `market-data`
  - `GAP-STOCK-ANALYSIS-PAGE` -> `stock-analysis`
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
  - `PAGE-PNL-BY-BUSINESS-001` -> `pnl-by-business`
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
- The `pnl-by-business` bundle covers `/pnl-by-business`, `/api/pnl/by-business-ytd`, monthly/formal/analysis reads, `/api/adb/comparison`, Formal PnL and ZQTZ balance source anchors, `fact_pnl_by_business_precompute`, adjustment audit evidence, and explicit no-dedicated-golden-sample / no-new-`MTR-*` status.
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
- The `stock-analysis` GAP bundle covers `/stock-analysis`, `/ui/market-data/livermore`, Livermore signal confluence, stock detail, candidate-history, strategy score/optimization, proxy backtest, sector-series APIs, frontend StockAnalysisPage/model touchpoints, and guardrails that keep the surface observational-only with no standalone `PAGE-STOCK-*`, no `MTR-*`, no dedicated golden sample, and no trading-instruction promotion.
- The `executive-summary` bundle covers `/ui/home/summary`, `SummaryPayload`, `GS-EXEC-SUMMARY-A`, endpoint/service/frontend/test touchpoints, and guardrails that keep narrative-only summary text out of the business metric dictionary main table.
- The `macro-toolkit` bundle covers `/macro-toolkit`, `/ui/macro/toolkit/analysis`, strategy summaries, script registry, script run, refresh/status endpoints, and guardrails that keep analysis, strategy, script, refresh, source/version/run_id, and coverage evidence out of formal metric truth.
- The `macro-observation` bundle covers `/macro-observation`, shared read-only analysis and strategy-summary APIs, `macro-observation-readonly-boundary`, and guardrails that keep script registry, run, refresh, and operational controls off the observation route.
- The `agent` bundle covers `/agent`, managed runs, compatibility query, AgentEnvelope, evidence/result_meta display, read-only request enforcement, and guardrails that keep agent answers from replacing formal metrics or source lineage.
- The `cube-query` bundle covers `/cube-query`, `/api/cube/query`, cube dimensions lookup, CubeQueryResult, candidate query-surface semantics, and guardrails that keep query results scoped to returned result_meta.
- The `portfolio-home`, `market-home`, `risk-home`, `performance-home`, and `reports-home` bundles cover live module-home routes, frontend aggregation through `ModuleWorkbenchHomePage` / `moduleHomeModel`, downstream page ownership, explicit no-dedicated-golden-sample status, and guardrails that prevent module summaries from becoming standalone formal metric pages.

Impact: the bundle workflow can now return first-pass trace bundles for the seeded page surfaces, including the newly separated Business Type PnL page and the Stock Analysis GAP surface. This is not a full system-wide release claim because most page-level data-catalog/date reviews and broader browser/a11y coverage remain incomplete, and the Stock Analysis bundle is explicitly a GAP trace boundary rather than formal PAGE contract closure.

Recommendation: keep the bundle workflow as the entry point for future page audits, and use it to drive the remaining lineage/catalog/browser audit work instead of continuing bundle seeding.

## Positive Evidence

- Second-pass front-end review checks:
  - `frontend/src/test/StockAnalysisPage.test.tsx` exists and contains active `/stock-analysis` coverage for layout, boundary summary, stale banner, decision panel, agent bridge, backtest, sector, risk, and closed-loop states. The page still remains `temporary-exception` in `docs/live_route_maturity.md`, but the earlier "no same-page test" risk is not present in the current worktree.
  - `frontend/src/features/team-performance/TeamPerformancePage.tsx:485-486` now states that `汇兑损益及衍生` is only a pending split reference, not a direct attribution.
  - `frontend/src/test/TeamPerformancePage.test.tsx:534`, `:540`, and `:574` assert the Q1 boundary copy.
  - `frontend/src/mocks/productCategoryPnl.test.ts:63` locks the `derivatives` mock row as the aggregate business-net-income reference with `category_name="汇兑损益及衍生"`.
  - Frontend unsafe-rendering scan found no `dangerouslySetInnerHTML`, `innerHTML=`, `eval()`, `new Function()`, `srcDoc`, or `DOMParser` hits in `frontend/src`.
- `codex mcp list` confirms `gitnexus`, `moss-data-catalog`, `moss-data-quality`, `moss-lineage-evidence`, and `moss-metric-contracts` are registered and enabled.
- `python -m pytest tests/test_project_mcp_servers.py -q`: latest focused MCP continuation run passed with `84 passed`.
- Local MCP fallback evidence:
  - `moss-metric-contracts`: resources and tools are callable through the repository's JSON-RPC MCP process; contract docs exist; seeded trace bundles now resolve 28 unique trace IDs, including `PAGE-PNL-BY-BUSINESS-001`, `GAP-STOCK-ANALYSIS-PAGE`, `agent`, `cube-query`, `portfolio-home`, `market-home`, `risk-home`, `performance-home`, and `reports-home`.
  - `moss-data-catalog`: `data/moss.duckdb` exists; 63 tables were inventoried; `fact_formal_risk_tensor_daily` is present with latest sampled dates through `2026-04-30`; Product Category PnL formal and canonical tables have latest sampled `report_date` values through `2026-05-31`; Formal PnL `fact_formal_pnl_fi` and `fact_nonstd_pnl_bridge` also have latest sampled `report_date` values through `2026-05-31`; Business Type PnL `fact_pnl_by_business_precompute.as_of_date` reaches `2026-05-31`; Dashboard Home source-table dependencies sampled in this pass include formal balance, formal PnL, position snapshot, bond analytics, product-category PnL, and FX tables with latest sampled dates through `2026-05-31`.
  - `moss-data-quality`: `fact_formal_risk_tensor_daily` is a quality target with 486 rows and date coverage from `2024-01-01` to `2026-04-30`; `product_category_pnl_formal_read_model` has 2,204 rows / 24 columns / `report_date` coverage from `2024-01-31` to `2026-05-31` with 0 sampled key nulls; `product_category_pnl_canonical_fact` has 233,673 rows / 12 columns / the same date coverage with 0 sampled key nulls; Formal PnL `fact_formal_pnl_fi` has 24,474 rows / 16 columns / `report_date` coverage from `2025-01-31` to `2026-05-31` with 0 sampled key nulls; `fact_nonstd_pnl_bridge` has 2,438 rows / 13 columns / the same date coverage with 0 sampled key nulls; Business Type PnL `fact_pnl_by_business_precompute` has 1,666 rows / 9 columns / `as_of_date` coverage from `2025-01-31` to `2026-05-31` with 0 sampled nulls. Dashboard Home source-table quality samples include formal balance (`fact_formal_zqtz_balance_daily` 1,539,536 rows; `fact_formal_tyw_balance_daily` 2,075,852 rows), position snapshots (`zqtz_bond_daily_snapshot` 769,768 rows; `tyw_interbank_daily_snapshot` 1,037,926 rows), bond analytics (`fact_formal_bond_analytics_daily` 711,479 rows), product-category PnL (2,204-row read model and 233,673-row canonical fact), and FX (`fx_daily_mid` 1,104 rows).
  - `moss-lineage-evidence`: governance streams exist and are readable; `PAGE-DASH-001` now expands to Dashboard Home snapshot API/result-kind/payload/service/date-domain/supplemental KPI/source-table anchors without crossing into child page IDs or child golden samples; `PAGE-RISK-001` now expands to risk tensor lineage anchors and returns `fact_formal_risk_tensor_daily` / `agent.risk_tensor` records from `agent_audit`; `PAGE-AGENT-001` now expands to Agent audit anchors and returns existing `agent_audit` records without promoting Agent answers to formal metric evidence; `PAGE-CUBE-QUERY-001` now expands to `/api/cube/query`, `cube_query.`, and the four Cube service approved formal table anchors; `PAGE-LEDGER-PNL-001` now expands to Ledger API/result-kind anchors, `qdb_general_ledger_workbook`, and the formal financial indicator source-contract fixture anchors without mapping to formal PnL fact tables; `PAGE-PROD-CAT-PNL-001` and the older `PAGE-PROD-CAT-001` now expand to Product Category PnL page/API/result-kind/formal-model/canonical/golden-sample/metric anchors without mapping to Formal PnL or Ledger source anchors; `PAGE-PNL-001` now expands to Formal PnL overview/data API, result-kind, fact-table, golden-sample, and `MTR-PNL-*` anchors without mapping to Ledger or Product Category source anchors; `PAGE-BRIDGE-001` now expands to PnL Bridge API/result-kind/source-surface/fact-table/golden-sample and `MTR-BRG-*` anchors without mapping to Ledger or Product Category source anchors; `PAGE-BALANCE-001` now expands to Balance Analysis overview/workbook, formal balance fact-table, golden-sample, and `MTR-BAL-*` anchors without mapping to Formal PnL, Product Category, or Ledger source anchors; `PAGE-PNL-ATTR-WB-001` now expands to PnL Attribution Workbench API/result-kind/payload/formal-attribution source-table and `MTR-PAT-*` anchors without mapping to `executive.pnl-attribution` or executive golden-sample anchors; `PAGE-BAL-MOVE-001` now expands to Balance Movement API/result-kind/accounting-asset movement fact/cache/source/payload and `MTR-BMV-*` anchors without mapping to Balance overview/workbook, Formal PnL, or Ledger anchors; `PAGE-LIAB-ANALYTICS-001` now expands to Liability Analytics compatibility APIs, `liability_analytics.*` analytical result kinds, `formal_liability`, formal balance/snapshot source anchors, payload anchors, and `MTR-LIAB-*` anchors without mapping to Ledger, Bridge, Balance golden-sample, or Executive golden-sample anchors; `GAP-STOCK-ANALYSIS-PAGE` now expands to `/stock-analysis`, Livermore read APIs, observational Livermore result-kind anchors, Livermore support tables, and rule-version anchors without creating `PAGE-STOCK-*`, `MTR-*`, or golden-sample anchors; `PAGE-EXEC-OVERVIEW-001` now expands to Executive Overview analytical-overlay API/result-kind/schema/golden-sample/`MTR-EXEC-*` anchors and its formal balance, formal PnL, liability, and bond-analytics source-table dependencies without mapping to Balance/PnL/Risk page IDs, page result kinds, or golden samples; `PAGE-EXEC-SUMMARY-001` now expands to Executive Summary narrative-only API/result-kind/payload/point/golden-sample/overview-lineage anchors without mapping to Executive Overview metric IDs, Executive Overview page/sample anchors, or Executive PnL Attribution anchors; `PAGE-MACRO-TOOLKIT-001` now expands to macro toolkit analysis, strategy, scripts, run, refresh, status, payload, and source/version/run_id anchors without creating `MTR-*` or golden-sample anchors; `PAGE-MACRO-OBS-001` now expands only to read-only macro analysis, strategy, payload, and boundary anchors without mapping to script registry, run, refresh, refresh-status, or operational toolkit anchors.
  - `moss-lineage-evidence` module-home follow-up: `PAGE-PORTFOLIO-HOME-001`, `PAGE-MARKET-HOME-001`, `PAGE-RISK-HOME-001`, `PAGE-PERFORMANCE-HOME-001`, and `PAGE-REPORTS-HOME-001` now expand to module-home boundary anchors plus their actual downstream read APIs/result kinds/source-table anchors. These mappings intentionally avoid standalone `MTR-*` and `GS-*` anchors, and Reports/Data uses the real `/health` summary read path plus `/health/live`, source foundation, and cube dimensions anchors.
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
  - Product Category lineage-query follow-up: local `moss-lineage-evidence` fallback now expands both `PAGE-PROD-CAT-PNL-001` and the older `PAGE-PROD-CAT-001` to `product-category-pnl`, `/ui/pnl/product-category`, `product_category_pnl.detail`, `product_category_pnl_formal_read_model`, `product_category_pnl_canonical_fact`, `GS-PROD-CAT-PNL-A`, and `MTR-PCP-001` through `MTR-PCP-003`, while intentionally not expanding to `fact_formal_pnl_fi` or `qdb_general_ledger_workbook`.
  - Product Category red/green proof: before the mapping, `python -m pytest tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_product_category_page_aliases_to_formal_model_records -q` failed because `expanded_queries` only contained `PAGE-PROD-CAT-PNL-001`; after the mapping, the Product Category focused test passed with `1 passed`, the Product Category/Ledger/Cube/Agent/Risk focused lineage set passed with `5 passed`, and the full project MCP suite passed with `62 passed`.
  - Real local MCP query proof: `find_lineage_records({"query":"PAGE-PROD-CAT-PNL-001","max_results":8})` and the same query for `PAGE-PROD-CAT-001` return the expanded Product Category anchors above and sampled `cache_build_run` records matched on `product-category-pnl`. A 100-record governance sample for `product-category-pnl` / `product_category_pnl.formal` contains `completed`, `queued`, `running`, and `failed` cache-build statuses, while a direct `product_category_pnl_formal_read_model` lineage query currently returns zero records.
  - Product Category data-catalog/date proof: `list_available_dates(..., report_date, limit=5)` shows `2026-05-31`, `2026-04-30`, `2026-03-31`, `2026-02-28`, and `2026-01-31` for both `product_category_pnl_formal_read_model` and `product_category_pnl_canonical_fact`; `product_category_pnl_scenario_read_model` returns no sampled report dates.
  - Product Category data-quality proof: `get_quality_summary` reports `product_category_pnl_formal_read_model` at 2,204 rows / 24 columns and `product_category_pnl_canonical_fact` at 233,673 rows / 12 columns, both with `report_date` coverage from `2024-01-31` to `2026-05-31`, 29 distinct non-null report dates, and 0 nulls in the profiled key columns.
- PnL Bridge page-contract bundle check:
  - Red check before implementation: `python -m pytest tests/test_project_mcp_servers.py -q` failed with `2 failed, 15 passed` because `pnl-bridge` was unknown.
  - Green check after implementation: `python -m pytest tests/test_project_mcp_servers.py -q` passed with `17 passed`.
  - Focused bridge logic/service boundary check: `python -m pytest tests/test_pnl_bridge_core.py tests/test_pnl_bridge_curve_effects.py tests/test_pnl_bridge_fx_translation.py tests/test_pnl_bridge_with_curve.py tests/test_pnl_bridge_numeric_migration.py tests/test_pnl_bridge_service_boundaries.py -q` passed with `39 passed`.
  - API contract and golden-sample check: `python -m pytest tests/test_pnl_api_contract.py tests/test_golden_samples_capture_ready.py -q` passed with `90 passed`.
  - Frontend page check: `npm run test -- src/test/PnlBridgePage.test.tsx` from `frontend/` passed with `1` test file and `6` tests.
  - PnL Bridge lineage-query follow-up: local `moss-lineage-evidence` fallback now expands `PAGE-BRIDGE-001` to `PAGE-BRIDGE-001`, `/api/pnl/bridge`, `pnl.bridge`, `pnl_bridge`, `fact_formal_pnl_fi`, `fact_nonstd_pnl_bridge`, `GS-BRIDGE-A`, `GS-BRIDGE-WARN-B`, and `MTR-BRG-001` through `MTR-BRG-014` / `MTR-BRG-101` through `MTR-BRG-105`, while intentionally not expanding to `product_category_pnl_formal_read_model` or `qdb_general_ledger_workbook`.
  - PnL Bridge red/green proof: before the mapping, `python -m pytest tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_pnl_bridge_page_to_bridge_records -q` failed because `expanded_queries` only contained `PAGE-BRIDGE-001`; after the mapping, the PnL Bridge focused test passed with `1 passed`.
  - Real local MCP query proof: `find_lineage_records({"query":"PAGE-BRIDGE-001","max_results":100})` returns the expanded PnL Bridge anchors above and 32 sampled records: 4 from `agent_audit` and 28 from `cache_manifest`, currently matched through `pnl_bridge` / underlying PnL fact-table references rather than direct `pnl.bridge` or `/api/pnl/bridge` records.
  - PnL Bridge data-catalog/date proof: the underlying `fact_formal_pnl_fi` and `fact_nonstd_pnl_bridge` source tables both describe successfully and list latest sampled `report_date` values through `2026-05-31`.
  - PnL Bridge data-quality proof: because this bridge is built from the Formal PnL facts, the sampled source-table quality is the same as the Formal PnL chain: `fact_formal_pnl_fi` has 24,474 rows / 16 columns and `fact_nonstd_pnl_bridge` has 2,438 rows / 13 columns, both with `report_date` coverage from `2025-01-31` to `2026-05-31` and 0 nulls in profiled key columns.
- Balance Analysis page-contract bundle check:
  - Red check before implementation: `python -m pytest tests/test_project_mcp_servers.py -q` failed with `2 failed, 17 passed` because `balance-analysis` was unknown.
  - Green check after implementation: `python -m pytest tests/test_project_mcp_servers.py -q` passed with `19 passed`.
  - Focused balance backend/API/contract/workbook check: `python -m pytest tests/test_balance_analysis_api.py tests/test_balance_analysis_contracts.py tests/test_balance_analysis_core.py tests/test_balance_analysis_materialize_flow.py tests/test_balance_analysis_service.py tests/test_balance_analysis_boundary_guards.py tests/test_balance_analysis_workbook_contract.py tests/test_balance_analysis_module_registration_flow.py tests/test_golden_samples_capture_ready.py -q` passed with `112 passed`.
  - Frontend page check: `npm run test -- src/test/BalanceAnalysisPage.test.tsx` from `frontend/` passed with `1` test file and `24` tests.
  - Balance Analysis lineage-query follow-up: local `moss-lineage-evidence` fallback now expands `PAGE-BALANCE-001` to `PAGE-BALANCE-001`, `/ui/balance-analysis/overview`, `/ui/balance-analysis/workbook`, `balance-analysis.overview`, `balance-analysis.workbook`, `balance_analysis`, `fact_formal_zqtz_balance_daily`, `fact_formal_tyw_balance_daily`, `GS-BAL-OVERVIEW-A`, `GS-BAL-WORKBOOK-A`, and `MTR-BAL-001` through `MTR-BAL-006` / `MTR-BAL-101` through `MTR-BAL-105` / `MTR-BAL-201` through `MTR-BAL-203`, while intentionally not expanding to Formal PnL, Product Category PnL, or Ledger anchors.
  - Balance Analysis red/green proof: before the mapping, `python -m pytest tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_balance_analysis_page_to_formal_balance_records -q` failed because `expanded_queries` only contained `PAGE-BALANCE-001`; after the mapping, the Balance focused test passed with `1 passed`, and the Balance/Bridge/PnL/Product Category/Ledger/Cube/Agent/Risk focused lineage set passed with `8 passed`.
  - Real local MCP query proof: `find_lineage_records({"query":"PAGE-BALANCE-001","max_results":20})` returns the expanded Balance anchors above and 20 sampled records, currently matched through `balance_analysis` / underlying formal balance fact-table references in `agent_audit` rather than direct `PAGE-BALANCE-001`, `/ui/balance-analysis/overview`, `/ui/balance-analysis/workbook`, `balance-analysis.overview`, or `balance-analysis.workbook` rows.
  - Balance data-catalog/date proof: `describe_table` succeeds for `fact_formal_zqtz_balance_daily` and `fact_formal_tyw_balance_daily`; `list_available_dates(..., report_date, limit=5)` shows latest dates through `2026-05-31` for both tables.
  - Balance data-quality proof: `get_quality_summary` reports `fact_formal_zqtz_balance_daily` has 1,539,536 rows / 35 columns / `report_date` coverage `2024-01-01` to `2026-05-31` / sampled key nulls 0, and `fact_formal_tyw_balance_daily` has 2,075,852 rows / 21 columns / `report_date` coverage `2025-01-01` to `2026-05-31` / sampled key nulls 0; both summaries link `GS-BAL-WORKBOOK-A` to the formal balance source section.
- Formal PnL page-contract bundle check:
  - Red check before implementation: `python -m pytest tests/test_project_mcp_servers.py -q` failed with `2 failed, 19 passed` because `pnl` was unknown.
  - Green check after implementation: `python -m pytest tests/test_project_mcp_servers.py -q` passed with `21 passed`.
  - Focused formal PnL backend/API/core/materialize check: `python -m pytest tests/test_pnl_api_contract.py tests/test_pnl_formal_semantics_contract.py tests/test_pnl_core_finance_contract.py tests/test_pnl_materialize_flow.py tests/test_golden_samples_capture_ready.py -q` passed with `107 passed`.
  - Frontend page/routes check: `npm run test -- src/test/PnlPage.test.tsx src/test/PnlRoutesSmoke.test.tsx` from `frontend/` passed with `2` test files and `17` tests.
  - Formal PnL lineage-query follow-up: local `moss-lineage-evidence` fallback now expands `PAGE-PNL-001` to `PAGE-PNL-001`, `/api/pnl/overview`, `/api/pnl/data`, `pnl.overview`, `pnl.data`, `fact_formal_pnl_fi`, `fact_nonstd_pnl_bridge`, `GS-PNL-OVERVIEW-A`, `GS-PNL-DATA-A`, and `MTR-PNL-001` through `MTR-PNL-005` / `MTR-PNL-101` through `MTR-PNL-104`, while intentionally not expanding to `product_category_pnl_formal_read_model` or `qdb_general_ledger_workbook`.
  - Formal PnL red/green proof: before the mapping, `python -m pytest tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_formal_pnl_page_to_formal_fact_records -q` failed because `expanded_queries` only contained `PAGE-PNL-001`; after the mapping, the Formal PnL focused test passed with `1 passed`, and the Formal PnL/Product Category/Ledger/Cube/Agent/Risk focused lineage set passed with `6 passed`.
  - Real local MCP query proof: `find_lineage_records({"query":"PAGE-PNL-001","max_results":100})` returns the expanded Formal PnL anchors above and 32 sampled records: 4 from `agent_audit` matched through `fact_formal_pnl_fi` / `fact_nonstd_pnl_bridge` with `result_kind="agent.pnl_summary"`, and 28 from `cache_manifest` for `pnl:phase2:materialize:formal`; direct `pnl.overview` and `pnl.data` lineage queries currently return zero records.
  - Formal PnL data-catalog/date proof: `describe_table` succeeds for `fact_formal_pnl_fi` and `fact_nonstd_pnl_bridge`; `list_available_dates(..., report_date, limit=5)` shows `2026-05-31`, `2026-04-30`, `2026-03-31`, `2026-02-28`, and `2026-01-31` for both tables.
  - Formal PnL data-quality proof: `get_quality_summary` reports `fact_formal_pnl_fi` at 24,474 rows / 16 columns and `fact_nonstd_pnl_bridge` at 2,438 rows / 13 columns, both with `report_date` coverage from `2025-01-31` to `2026-05-31`, 17 distinct non-null report dates, and 0 nulls in the profiled key columns.
- Business Type PnL page-contract bundle check:
  - Red check before implementation: `python -m pytest tests/test_project_mcp_servers.py::test_business_pnl_trace_bundle_preserves_page_level_analysis_boundaries tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_business_pnl_page_to_page_level_read_records -q` failed with `2 failed` because `pnl-by-business` was unknown and `expanded_queries` only contained `PAGE-PNL-BY-BUSINESS-001`.
  - Green check after implementation: the same focused test passed with `2 passed`; the full MCP server suite passed with `python -m pytest tests/test_project_mcp_servers.py -q` -> `84 passed`.
  - Business Type PnL lineage-query follow-up: local `moss-lineage-evidence` fallback now expands `PAGE-PNL-BY-BUSINESS-001` to `/api/pnl/by-business-ytd`, `/api/pnl/by-business-monthly`, `/api/pnl/by-business`, `/api/pnl/by-business-analysis`, `/api/adb/comparison`, `pnl.by_business_ytd`, `pnl.by_business_monthly`, `pnl.by_business`, `pnl.by_business_analysis`, `fact_formal_pnl_fi`, `fact_nonstd_pnl_bridge`, `fact_formal_zqtz_balance_daily`, `fact_pnl_by_business_precompute`, `pnl_by_business_adjustments`, `pnl-by-business`, `/pnl-by-business`, and the page-level no-new-`MTR` boundary, while intentionally not expanding to Product Category truth, Ledger truth, `MTR-*`, or `GS-*` anchors.
  - Real local MCP query proof: `find_lineage_records({"query":"PAGE-PNL-BY-BUSINESS-001","max_results":8})` returns the expanded anchors above and currently samples only `agent_audit` records matched on `fact_formal_pnl_fi` / `fact_formal_zqtz_balance_daily`; direct queries for `/api/pnl/by-business-ytd`, `/api/pnl/by-business-monthly`, `/api/pnl/by-business`, `/api/pnl/by-business-analysis`, `pnl.by_business_ytd`, `pnl.by_business_monthly`, `pnl.by_business`, `pnl.by_business_analysis`, `fact_pnl_by_business_precompute`, and `pnl_by_business_adjustments` return zero lineage records in this pass.
  - Business Type PnL data-catalog/date proof: `describe_table` succeeds for `fact_pnl_by_business_precompute` (9 columns), `fact_formal_pnl_fi` (16 columns), `fact_nonstd_pnl_bridge` (13 columns), and `fact_formal_zqtz_balance_daily` (35 columns). `list_available_dates` shows `fact_pnl_by_business_precompute.as_of_date` and the Formal PnL fact tables through `2026-05-31`; `fact_formal_zqtz_balance_daily.report_date` reaches `2026-05-31` with daily dates in the latest sample.
  - Business Type PnL data-quality proof: `get_quality_summary` reports `fact_pnl_by_business_precompute` at 1,666 rows / 9 columns / `as_of_date` coverage `2025-01-31` to `2026-05-31` / 17 distinct dates / 0 nulls across profiled columns. The same pass reports `fact_formal_pnl_fi` at 24,474 rows / 16 columns and `fact_nonstd_pnl_bridge` at 2,438 rows / 13 columns with `report_date` coverage `2025-01-31` to `2026-05-31`, and `fact_formal_zqtz_balance_daily` at 1,539,536 rows / 35 columns with `report_date` coverage `2024-01-01` to `2026-05-31`; sampled key/profile columns have 0 nulls.
  - Current residual evidence note: `PAGE-PNL-BY-BUSINESS-001` has no dedicated golden sample and no newly approved `MTR-*` binding. The mapping is query-level traceability to page APIs/result kinds/source/precompute/adjustment anchors; it must not be read as a direct page/API execution proof, Product Category truth, Ledger truth, Formal PnL overview truth, PnL Bridge truth, or approval to mix formal reconciliation rows into YTD/monthly business conclusions.
- Liability Analytics page-contract bundle check:
  - Red check before implementation: `python -m pytest tests/test_project_mcp_servers.py -q` failed with `2 failed, 21 passed` because `liability-analytics` was unknown.
  - Green check after implementation: `python -m pytest tests/test_project_mcp_servers.py -q` passed with `23 passed`.
  - Focused liability backend/compat/result-meta check: `python -m pytest tests/test_liability_analytics_api.py tests/test_liability_analytics_envelope_contract.py tests/test_liability_analytics_compat_contract.py tests/test_liability_analytics_unit_semantics.py tests/test_liability_analytics_numeric_migration.py tests/test_result_meta_on_all_ui_endpoints.py tests/test_result_meta_source_surface_followup.py tests/test_live_route_page_contract_completeness.py -q` passed with `68 passed`.
  - Frontend page/adapter/model check: `npm run test -- src/test/LiabilityAnalyticsPage.test.tsx src/features/liability-analytics/adapters/liabilityAdapter.test.ts src/features/liability-analytics/pages/liabilityAnalyticsPageModel.test.ts` from `frontend/` passed with `3` test files and `12` tests.
  - Liability Analytics lineage-query follow-up: local `moss-lineage-evidence` fallback now expands `PAGE-LIAB-ANALYTICS-001` to `/api/risk/buckets`, `/api/analysis/yield_metrics`, `/api/analysis/yield-by-period`, `/api/analysis/liabilities/counterparty`, `/api/liabilities/monthly`, `/ui/liability/business-context`, `/api/analysis/liabilities/cockpit-warnings`, `/api/analysis/liabilities/contribution-split`, `liability_analytics.risk_buckets`, `liability_analytics.yield_metrics`, `liability_analytics.yield_by_period`, `liability_analytics.counterparty`, `liability_analytics.monthly`, `liability_analytics.cockpit_warnings`, `liability_analytics.contribution_split`, `formal_liability`, `fact_formal_zqtz_balance_daily`, `fact_formal_tyw_balance_daily`, `zqtz_bond_daily_snapshot`, `tyw_interbank_daily_snapshot`, `rv_liability_analytics_compat_v1`, `cv_liability_analytics_v1`, liability payload classes, and `MTR-LIAB-001` through `MTR-LIAB-007`, while intentionally not expanding to Ledger, PnL Bridge, Balance golden-sample, or Executive golden-sample anchors.
  - Liability Analytics red/green proof: before the mapping, `python -m pytest tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_liability_analytics_page_to_mixed_source_records -q` failed because `expanded_queries` only contained `PAGE-LIAB-ANALYTICS-001`; after the mapping, the Liability focused test passed with `1 passed`, and the Liability/Workbench/Balance Movement/Balance/Bridge/PnL/Product Category/Ledger/Cube/Agent/Risk focused lineage set passed with `11 passed`.
  - Real local MCP query proof: `find_lineage_records({"query":"PAGE-LIAB-ANALYTICS-001","max_results":20})` returns the expanded Liability anchors above and 20 sampled records, currently matched through underlying formal balance fact-table references in `agent_audit`; direct `/api/risk/buckets`, `liability_analytics.risk_buckets`, and `formal_liability` lineage queries still return zero records, while direct `fact_formal_tyw_balance_daily`, `zqtz_bond_daily_snapshot`, and `tyw_interbank_daily_snapshot` queries return existing governance records.
  - Liability data-catalog/date proof: `describe_table` and `list_available_dates` succeed for `fact_formal_zqtz_balance_daily` (35 columns), `fact_formal_tyw_balance_daily` (21 columns), `zqtz_bond_daily_snapshot` (32 columns), `tyw_interbank_daily_snapshot` (18 columns), and the `yield_by_period` dependency `fact_formal_pnl_fi` (16 columns). Latest sampled `report_date` values reach `2026-05-31` for all five tables; Formal PnL uses month-end dates, while balance/snapshot sources also carry daily dates such as `2026-04-29`, `2026-04-28`, and `2026-04-27`.
  - Liability data-quality proof: `get_quality_summary` reports `fact_formal_zqtz_balance_daily` at 1,539,536 rows / 35 columns / `report_date` coverage `2024-01-01` to `2026-05-31` / 487 distinct non-null dates / 0 nulls in the first 8 profiled key columns; `fact_formal_tyw_balance_daily` at 2,075,852 rows / 21 columns / `report_date` coverage `2025-01-01` to `2026-05-31` / 486 distinct non-null dates / 0 nulls in the first 8 profiled key columns; `zqtz_bond_daily_snapshot` at 769,768 rows / 32 columns / the same 487-date coverage / 0 nulls in the first 8 profiled key columns; `tyw_interbank_daily_snapshot` at 1,037,926 rows / 18 columns / 486-date coverage with no nulls in `report_date`, `position_id`, `product_type`, `position_side`, and `counterparty_name`, but nulls in some classification fields such as `account_type`, `special_account_type`, and `core_customer_type`; `fact_formal_pnl_fi` at 24,474 rows / 16 columns / `report_date` coverage `2025-01-31` to `2026-05-31` / 17 distinct non-null dates / 0 nulls in the first 8 profiled columns.
  - Current residual evidence note: no dedicated golden sample exists for `PAGE-LIAB-ANALYTICS-001`; the bundle intentionally records this and preserves the governed-mixed-source / compatibility boundary. The new mapping is query-level traceability to mixed formal-liability, snapshot, and Formal PnL period-rollup dependencies, and must not be read as a direct page/API execution proof or a promotion from analytical compatibility to formal balance/PnL truth.
- Executive PnL Attribution and PnL Attribution Workbench page-contract bundle check:
  - Red check before implementation: `python -m pytest tests/test_project_mcp_servers.py -q` failed with `4 failed, 23 passed` because `executive-pnl-attribution` and `pnl-attribution` were unknown.
  - Green check after implementation: `python -m pytest tests/test_project_mcp_servers.py -q` passed with `27 passed`.
  - Focused backend/API/service/golden-sample check: `python -m pytest tests/test_pnl_attribution_api_contract.py tests/test_pnl_attribution_workbench_contract.py tests/test_pnl_attribution_service_explicit_numeric.py tests/test_pnl_attribution_numeric_migration.py tests/test_advanced_attribution_contract.py tests/test_result_meta_source_surface.py backend/tests/services/test_pnl_attribution_campisi.py tests/test_executive_dashboard_endpoints.py tests/test_executive_service_contract.py tests/test_executive_release_contract.py tests/test_golden_samples_capture_ready.py -q` passed with `145 passed`.
  - Frontend attribution surface check: `npm run test -- src/test/PnlAttributionPage.test.tsx src/test/PnlAttributionSection.test.tsx src/test/PnlCompositionChart.test.tsx src/test/TPLMarketChart.test.tsx src/test/AdvancedAttributionChart.test.tsx src/test/CampisiAttributionPanel.test.tsx` from `frontend/` passed with `6` test files and `19` tests.
  - PnL Attribution Workbench lineage-query follow-up: local `moss-lineage-evidence` fallback now expands `PAGE-PNL-ATTR-WB-001` to `/api/pnl-attribution/volume-rate`, `/api/pnl-attribution/tpl-market`, `/api/pnl-attribution/composition`, `/api/pnl-attribution/summary`, advanced and Campisi workbench APIs, `pnl_attribution.*` / `campisi.*` result-kind anchors, `VolumeRateAttributionPayload`, `TPLMarketCorrelationPayload`, `PnlCompositionPayload`, `AdvancedAttributionSummary`, `fact_formal_pnl_fi`, `fact_nonstd_pnl_bridge`, `fact_formal_zqtz_balance_daily`, `fact_formal_bond_analytics_daily`, `yield_curve_daily`, and `MTR-PAT-001` through `MTR-PAT-006` / `MTR-PAT-101` through `MTR-PAT-103` / `MTR-PAT-201` through `MTR-PAT-205` / `MTR-PAT-301` through `MTR-PAT-304`, while intentionally not expanding to `executive.pnl-attribution`, `GS-EXEC-PNL-ATTR-A`, `MTR-EXEC-*`, or Ledger anchors.
  - PnL Attribution Workbench red/green proof: before the mapping, `python -m pytest tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_pnl_attribution_workbench_to_formal_attribution_records -q` failed because `expanded_queries` only contained `PAGE-PNL-ATTR-WB-001`; after the mapping, the Workbench focused test passed with `1 passed`, and the Workbench/Balance/Bridge/PnL/Product Category/Ledger/Cube/Agent/Risk focused lineage set passed with `9 passed`.
  - Real local MCP query proof: `find_lineage_records({"query":"PAGE-PNL-ATTR-WB-001","max_results":30})` returns the expanded Workbench anchors above and 30 sampled records, currently matched through underlying table references in `agent_audit` (`fact_formal_pnl_fi` / `fact_nonstd_pnl_bridge` and `fact_formal_zqtz_balance_daily`) rather than direct `PAGE-PNL-ATTR-WB-001`, `/api/pnl-attribution/*`, or `pnl_attribution.*` rows.
  - PnL Attribution Workbench data-catalog/date proof: `list_available_dates(..., report_date, limit=3)` shows latest dates through `2026-05-31` for `fact_formal_pnl_fi`, `fact_nonstd_pnl_bridge`, `fact_formal_zqtz_balance_daily`, and `fact_formal_bond_analytics_daily`.
  - PnL Attribution Workbench data-quality proof: sampled source-table quality remains the same as the Formal PnL / Balance / Bond Analytics chains already recorded above: `fact_formal_pnl_fi` has 24,474 rows / 16 columns, `fact_nonstd_pnl_bridge` has 2,438 rows / 13 columns, `fact_formal_zqtz_balance_daily` has 1,539,536 rows / 35 columns, and `fact_formal_bond_analytics_daily` has 711,479 rows / 38 columns, all with `report_date` coverage through `2026-05-31` and 0 nulls in sampled key columns.
  - Current residual evidence note: `PAGE-EXEC-PNL-ATTR-001` has `GS-EXEC-PNL-ATTR-A`; `PAGE-PNL-ATTR-WB-001` intentionally records no dedicated golden sample and still has no direct governance record keyed by the workbench page ID, API route, or `pnl_attribution.*` result kind. The new mapping is query-level traceability and must not be read as a specific workbench API execution proof.
- Operations Analysis page-contract bundle check:
  - Red check before implementation: `python -m pytest tests/test_project_mcp_servers.py -q` failed with `2 failed, 27 passed` because `operations-analysis` was unknown.
  - Green check after implementation: `python -m pytest tests/test_project_mcp_servers.py -q` passed with `29 passed`.
  - Focused doc/API/golden-sample check: `python -m pytest tests/test_governance_doc_contract.py::test_operations_analysis_contract_matches_current_product_category_headline_binding tests/test_live_route_page_contract_completeness.py tests/test_product_category_pnl_flow.py tests/test_balance_analysis_api.py tests/test_golden_samples_capture_ready.py -q` passed with `87 passed`.
  - Frontend operations route check: `npm run test -- src/test/OperationsAnalysisPage.test.tsx src/test/OperationsAnalysisPage.governed.test.tsx src/test/navigation.test.ts src/test/RouteRegistry.test.tsx src/test/WorkbenchShell.test.tsx` from `frontend/` passed with `5` test files and `104` tests.
  - Operations lineage-query follow-up: local `moss-lineage-evidence` fallback now expands `PAGE-OPS-001` to `/ui/pnl/product-category`, `/ui/pnl/product-category/dates`, `/ui/balance-analysis/overview`, `/ui/balance-analysis/dates`, `/ui/preview/source-foundation`, `/ui/preview/macro-foundation`, `/ui/macro/choice-series/latest`, `/ui/market-data/fx/formal-status`, `/ui/news/choice-events/latest`, `product_category_pnl.detail`, `product_category_pnl.dates`, `product_category_pnl_formal_read_model`, `product_category_pnl_canonical_fact`, `GS-PROD-CAT-PNL-A`, `MTR-PCP-001` through `MTR-PCP-003`, `balance-analysis.overview`, `formal_balance`, `fact_formal_zqtz_balance_daily`, `fact_formal_tyw_balance_daily`, `GS-BAL-OVERVIEW-A`, `MTR-BAL-001` through `MTR-BAL-003`, `MTR-BAL-101`, `MTR-BAL-102`, source/macro/FX/news anchors, `fact_choice_macro_daily`, `fx_daily_mid`, `choice_news_event`, and `GAP-OPS-MACRO-FX`, while intentionally not expanding to new `MTR-OPS-*`, Formal PnL, Balance workbook/detail, Bond Dashboard, or Positions anchors.
  - Operations red/green proof: before the mapping, `python -m pytest tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_operations_page_to_mixed_source_records -q` failed because `expanded_queries` only contained `PAGE-OPS-001`; after the mapping, the Operations focused test passed with `1 passed`, and the Operations/Market Data/Positions/Bond/Liability/Balance Movement/Balance/Formal PnL/Product Category/Ledger focused lineage set passed with `8 passed`.
  - Real local MCP query proof: `find_lineage_records({"query":"PAGE-OPS-001","max_results":10})` returns the expanded Operations anchors above and sampled records through product-category headline, supplemental balance overview, source preview, macro preview, FX formal status, and Choice news governance rows in the test fixture. Against the current repository governance stream, `PAGE-OPS-001` expands and samples existing records through `fact_formal_zqtz_balance_daily` in `agent_audit`; direct `/ui/pnl/product-category`, `product_category_pnl.detail`, `product_category_pnl_formal_read_model`, `/ui/balance-analysis/overview`, `balance-analysis.overview`, preview/macro/FX/news page-result queries still return zero direct records.
  - Operations data-catalog/date proof: `describe_table` succeeds for `product_category_pnl_formal_read_model` (24 columns), `product_category_pnl_canonical_fact` (12 columns), `fact_formal_zqtz_balance_daily` (35 columns), `fact_formal_tyw_balance_daily` (21 columns), `fact_choice_macro_daily` (11 columns), `fx_daily_mid` (12 columns), and `choice_news_event`. Sampled latest source dates reach `2026-05-31` for product-category and formal balance tables, `2026-06-01` for `fact_choice_macro_daily`, and `2026-05-31` for `fx_daily_mid`; `choice_news_event` has `received_at` rather than an `event_date` column.
  - Operations data-quality proof: `get_quality_summary` reports `product_category_pnl_formal_read_model` at 2,204 rows / `report_date` coverage `2024-01-31` to `2026-05-31` / 29 distinct report dates; `product_category_pnl_canonical_fact` at 233,673 rows with the same date range; `fact_formal_zqtz_balance_daily` at 1,539,536 rows with latest `report_date` `2026-05-31`; `fact_formal_tyw_balance_daily` at 2,075,852 rows with latest `report_date` `2026-05-31`; `fact_choice_macro_daily` at 4,066 rows with latest `trade_date` `2026-06-01`; `fx_daily_mid` at 1,104 rows with latest `trade_date` `2026-05-31`; and `choice_news_event` at 2,308 rows with no `event_date` column in the sampled schema.
  - Current residual evidence note: `PAGE-OPS-001` remains a temporary-exception mixed-source page; product-category headline truth is governed, balance overview is supplemental, and macro/FX/news/static sections remain bounded by `GAP-OPS-MACRO-FX`.
- Dashboard Home page-contract bundle check:
  - Existing bundle evidence: `get_page_trace_bundle` resolves `dashboard-home`, `/`, and `/dashboard` to `PAGE-DASH-001`, with primary API `/ui/home/snapshot` and guardrails that mark the page as an analytical/mixed-source snapshot rather than a full-page formal sample.
  - Dashboard Home lineage-query follow-up: local `moss-lineage-evidence` fallback now expands `PAGE-DASH-001` to `/ui/home/snapshot`, `home.snapshot`, `dashboard-home`, `HomeSnapshotPayload`, `home_snapshot_envelope`, `executive_analytical`, `domains_effective_date`, `domains_missing`, `product_category_ytd`, `product_category_monthly`, `dashboard.core_metrics`, `dashboard.daily_changes`, `bond_dashboard.headline_kpis`, `bond_analytics.portfolio_headlines`, `market_data.rates`, `calendar.supply_auctions`, `fact_formal_zqtz_balance_daily`, `fact_formal_tyw_balance_daily`, `fact_formal_pnl_fi`, `fact_nonstd_pnl_bridge`, `zqtz_bond_daily_snapshot`, `tyw_interbank_daily_snapshot`, `fact_formal_bond_analytics_daily`, `product_category_pnl_formal_read_model`, `product_category_pnl_canonical_fact`, and `fx_daily_mid`, while intentionally not expanding to child page IDs or child golden samples such as `PAGE-EXEC-OVERVIEW-001`, `GS-EXEC-OVERVIEW-A`, `PAGE-BOND-001`, `GS-BOND-HEADLINE-A`, `PAGE-PROD-CAT-PNL-001`, `GS-PROD-CAT-PNL-A`, or `PAGE-MKT-001`.
  - Dashboard Home red/green proof: before the mapping, `python -m pytest tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_dashboard_home_page_to_mixed_snapshot_records -q` failed because `expanded_queries` only contained `PAGE-DASH-001`; after the mapping, the Dashboard Home lineage test passed with `1 passed`, and the Dashboard Home / Executive Overview / Operations / Market Data / Positions / Bond Dashboard focused lineage set passed with `7 passed`.
  - Real local MCP query proof: `find_lineage_records({"query":"PAGE-DASH-001","max_results":8})` returns the expanded Dashboard Home anchors above and 8 sampled records, currently matched through `fact_formal_zqtz_balance_daily` records in `agent_audit` with `tables_used=["fact_formal_zqtz_balance_daily","fact_formal_tyw_balance_daily"]`. Direct `/ui/home/snapshot`, `home.snapshot`, `dashboard.core_metrics`, and `bond_dashboard.headline_kpis` lineage queries still return zero records in the current governance streams.
  - Dashboard Home data-catalog/date proof: `describe_table` succeeds for `fact_formal_zqtz_balance_daily` (35 columns), `fact_formal_tyw_balance_daily` (21 columns), `fact_formal_pnl_fi` (16 columns), `fact_nonstd_pnl_bridge` (13 columns), `zqtz_bond_daily_snapshot` (32 columns), `tyw_interbank_daily_snapshot` (18 columns), `fact_formal_bond_analytics_daily` (38 columns), `product_category_pnl_formal_read_model` (24 columns), `product_category_pnl_canonical_fact` (12 columns), and `fx_daily_mid` (12 columns). Latest sampled dates reach `2026-05-31` across these Dashboard source tables using `report_date` for business facts and `trade_date` for FX.
  - Dashboard Home data-quality proof: `get_quality_summary` reports `fact_formal_zqtz_balance_daily` at 1,539,536 rows; `fact_formal_tyw_balance_daily` at 2,075,852 rows; `fact_formal_pnl_fi` at 24,474 rows; `fact_nonstd_pnl_bridge` at 2,438 rows; `zqtz_bond_daily_snapshot` at 769,768 rows; `tyw_interbank_daily_snapshot` at 1,037,926 rows, with known nulls in `account_type`, `special_account_type`, and `core_customer_type`; `fact_formal_bond_analytics_daily` at 711,479 rows; `product_category_pnl_formal_read_model` at 2,204 rows; `product_category_pnl_canonical_fact` at 233,673 rows; and `fx_daily_mid` at 1,104 rows. The first 8 profiled columns are otherwise non-null for the sampled source tables.
  - Current residual evidence note: `PAGE-DASH-001` remains an analytical mixed-source homepage snapshot. The new mapping is query-level traceability to source tables and same-date supplemental anchors; it still does not create direct governance rows keyed by `PAGE-DASH-001`, `/ui/home/snapshot`, `home.snapshot`, `dashboard.core_metrics`, or `bond_dashboard.headline_kpis`, and it must not be read as child page closure, full-page formal truth, or dictionary-level approval for downstream candidate metrics.
- Executive Overview and Balance Movement Analysis page-contract bundle check:
  - Red check before implementation: `python -m pytest tests/test_project_mcp_servers.py -q` failed with `4 failed, 29 passed` because `executive-overview` and `balance-movement-analysis` were unknown.
  - Green check after implementation: `python -m pytest tests/test_project_mcp_servers.py -q` passed with `33 passed`.
  - Focused backend/API/service/golden/sample/accounting-movement check: `python -m pytest tests/test_executive_dashboard_endpoints.py tests/test_executive_service_contract.py tests/test_executive_release_contract.py tests/test_executive_dashboard_numeric_migration.py tests/test_golden_samples_capture_ready.py tests/test_accounting_asset_movement_api.py tests/test_accounting_asset_movement_service.py tests/test_accounting_asset_movement_core.py tests/test_accounting_asset_movement_materialize.py tests/test_result_meta_on_all_ui_endpoints.py tests/test_live_route_page_contract_completeness.py tests/test_write_route_auth_contract.py -q` passed with `177 passed`.
  - Frontend executive overview and balance movement check: `npm run test -- src/test/OverviewSection.test.tsx src/features/executive-dashboard/components/OverviewSection.states.test.tsx src/features/executive-dashboard/selectors/executiveDashboardSelectors.test.ts src/features/executive-dashboard/adapters/executiveDashboardAdapter.test.ts src/test/BalanceMovementAnalysisPage.test.tsx src/test/RouteRegistry.test.tsx` from `frontend/` passed with `6` test files and `91` tests.
  - Executive Overview lineage-query follow-up: local `moss-lineage-evidence` fallback now expands `PAGE-EXEC-OVERVIEW-001` to `/ui/home/overview`, `executive.overview`, `executive_overview`, `OverviewPayload`, `ExecutiveMetric`, `ExecutiveMetric.caliber_label`, `GS-EXEC-OVERVIEW-A`, `MTR-EXEC-001` through `MTR-EXEC-004`, `MTR-EXEC-004A` through `MTR-EXEC-004C`, `formal_balance`, `fact_formal_zqtz_balance_daily`, `fact_formal_tyw_balance_daily`, `fact_formal_pnl_fi`, `fact_nonstd_pnl_bridge`, `liability_analytics.yield_metrics`, `zqtz_bond_daily_snapshot`, `tyw_interbank_daily_snapshot`, `bond_analytics`, and `fact_formal_bond_analytics_daily`, while intentionally not expanding to `PAGE-BALANCE-001`, `balance-analysis.overview`, `GS-BAL-OVERVIEW-A`, `PAGE-PNL-001`, `pnl.overview`, `GS-PNL-OVERVIEW-A`, `PAGE-RISK-001`, `risk.tensor`, `GS-RISK-A`, `executive.pnl-attribution`, or `GS-EXEC-PNL-ATTR-A`.
  - Executive Overview red/green proof: before the mapping, `python -m pytest tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_executive_overview_page_to_overlay_records -q` failed because `expanded_queries` only contained `PAGE-EXEC-OVERVIEW-001`; after the mapping, the focused Executive Overview lineage test passed with `1 passed`, and the Executive Overview / Executive trace bundle / Workbench / Balance / Formal PnL / Operations / Bond / Liability focused lineage set passed with `8 passed`.
  - Real local MCP query proof: `find_lineage_records({"query":"PAGE-EXEC-OVERVIEW-001","max_results":8})` returns the expanded Executive Overview anchors above and 8 sampled records, currently matched through `fact_formal_zqtz_balance_daily` records in `agent_audit` with `result_kind="agent.portfolio_overview"`. Direct `/ui/home/overview`, `executive.overview`, `GS-EXEC-OVERVIEW-A`, and `MTR-EXEC-001` lineage queries still return zero records in the current governance streams.
  - Executive Overview data-catalog/date proof: `describe_table` succeeds for `fact_formal_zqtz_balance_daily` (35 columns), `fact_formal_tyw_balance_daily` (21 columns), `fact_formal_pnl_fi` (16 columns), `fact_nonstd_pnl_bridge` (13 columns), `zqtz_bond_daily_snapshot` (32 columns), `tyw_interbank_daily_snapshot` (18 columns), and `fact_formal_bond_analytics_daily` (38 columns). `list_available_dates` for `fact_formal_bond_analytics_daily.report_date` returns latest values including `2026-05-31`, `2026-04-30`, `2026-04-29`, `2026-04-28`, and `2026-04-27`; quality coverage shows the other source tables also reach `2026-05-31`.
  - Executive Overview data-quality proof: `get_quality_summary` reports `fact_formal_zqtz_balance_daily` at 1,539,536 rows / `report_date` coverage `2024-01-01` to `2026-05-31` / 487 distinct dates; `fact_formal_tyw_balance_daily` at 2,075,852 rows / `2025-01-01` to `2026-05-31` / 486 dates; `fact_formal_pnl_fi` at 24,474 rows / `2025-01-31` to `2026-05-31` / 17 dates; `fact_nonstd_pnl_bridge` at 2,438 rows / `2025-01-31` to `2026-05-31` / 17 dates; `zqtz_bond_daily_snapshot` at 769,768 rows / `2024-01-01` to `2026-05-31` / 487 dates; `tyw_interbank_daily_snapshot` at 1,037,926 rows / `2025-01-01` to `2026-05-31` / 486 dates, with existing nulls in `account_type`, `special_account_type`, and `core_customer_type`; and `fact_formal_bond_analytics_daily` at 711,479 rows / `2024-01-01` to `2026-05-31` / 487 dates. The PnL source-table quality summaries also report `GS-EXEC-OVERVIEW-A` matches for the annual PnL detail text.
  - Balance Movement lineage-query follow-up: local `moss-lineage-evidence` fallback now expands `PAGE-BAL-MOVE-001` to `/ui/balance-movement-analysis`, `/ui/balance-movement-analysis/dates`, `/ui/balance-movement-analysis/refresh`, `balance-analysis.movement`, `balance-analysis.movement.detail`, `balance-analysis.movement.dates`, `accounting_asset_movement`, `fact_accounting_asset_movement_monthly`, `fact_formal_zqtz_balance_daily`, `rv_accounting_asset_movement_v2`, `cv_accounting_asset_movement_v1`, `AccountingAssetMovementPayload`, `AccountingAssetMovementSummaryPayload`, and `MTR-BMV-001` through `MTR-BMV-004`, while intentionally not expanding to `MTR-BAL-*`, `GS-BAL-OVERVIEW-A`, Formal PnL, or Ledger anchors.
  - Balance Movement red/green proof: before the mapping, `python -m pytest tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_balance_movement_page_to_movement_records -q` failed because `expanded_queries` only contained `PAGE-BAL-MOVE-001`; after the mapping, the Balance Movement focused test passed with `1 passed`, and the Balance Movement/Workbench/Balance/Bridge/PnL/Product Category/Ledger/Cube/Agent/Risk focused lineage set passed with `10 passed`.
  - Real local MCP query proof: `find_lineage_records({"query":"PAGE-BAL-MOVE-001","max_results":30})` returns the expanded Balance Movement anchors above and 30 sampled records. The current top sample is matched through underlying table references in `agent_audit`, and direct `/ui/balance-movement-analysis` / `balance-analysis.movement.detail` queries still return zero records; direct `fact_accounting_asset_movement_monthly` and `rv_accounting_asset_movement_v2` queries return cache manifest/build records.
  - Balance Movement data-catalog/date proof: `describe_table` succeeds for `fact_accounting_asset_movement_monthly`; the table has 16 columns including `report_date`, `report_month`, `currency_basis`, `basis_bucket`, `previous_balance`, `current_balance`, `balance_change`, `reconciliation_diff`, `source_version`, and `rule_version`; latest sampled `report_date` values include `2026-04-30`, `2026-03-31`, `2026-02-28`, `2026-01-31`, and `2025-12-31`.
  - Balance Movement data-quality proof: `get_quality_summary` reports `fact_accounting_asset_movement_monthly` has 84 rows / 16 columns / `report_date` coverage `2024-01-31` to `2026-04-30` / 28 distinct non-null report dates / 0 nulls in sampled key/profiled columns. No dedicated golden sample match is currently reported.
  - Current residual evidence note: `PAGE-EXEC-OVERVIEW-001` has `GS-EXEC-OVERVIEW-A` and remains an analytical management overlay; the new mapping is query-level traceability to the overlay's source tables and still does not create direct governance rows keyed by `PAGE-EXEC-OVERVIEW-001`, `/ui/home/overview`, `executive.overview`, `GS-EXEC-OVERVIEW-A`, or `MTR-EXEC-*`. `PAGE-BAL-MOVE-001` intentionally records no dedicated golden sample and still has no direct governance row keyed by the page ID, page API, or movement result kind. These mappings must not be read as proof of a specific Executive Overview or Balance Movement page/API execution.
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
  - Ledger lineage-query follow-up: local `moss-lineage-evidence` fallback now expands `PAGE-LEDGER-PNL-001` to `PAGE-LEDGER-PNL-001`, `/api/ledger-pnl/summary`, `/api/ledger-pnl/data`, `/api/ledger-pnl/formal-financial-indicators`, `ledger_pnl.`, `qdb_general_ledger_workbook`, `formal_financial_indicator_source_contract`, and `GS-LEDGER-PNL-FIN-IND-202603-B`, while intentionally not expanding to `fact_formal_pnl_fi` or `fact_nonstd_pnl_bridge`.
  - Ledger red/green proof: before the mapping, `python -m pytest tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_ledger_pnl_page_to_ledger_source_contracts -q` failed because `expanded_queries` only contained `PAGE-LEDGER-PNL-001`; after the mapping, the Ledger/Cube/Agent/Risk focused lineage set passed with `5 passed`.
  - Real local MCP query proof: `find_lineage_records({"query":"PAGE-LEDGER-PNL-001","max_results":8})` returns the expanded Ledger anchors above and no records in the current governance streams. This is now an explicit query mapping with a remaining evidence-record gap, not a missing page-to-anchor route.
  - Fresh Ledger boundary proof after the mapping: `python -m pytest tests/test_ledger_pnl_service.py tests/test_ledger_pnl_formal_financial_indicator_golden_sample.py -q` passed with `14 passed`, verifying summary/detail and formal financial indicator source-contract envelopes remain `basis=ledger` / `formal_use_allowed=false`.
- Bond Dashboard page-contract bundle check:
  - Red check before implementation: `python -m pytest tests/test_project_mcp_servers.py -q` failed with `2 failed, 35 passed` because `bond-dashboard` was unknown.
  - Green check after implementation: `python -m pytest tests/test_project_mcp_servers.py -q` passed with `37 passed`.
  - Focused backend/API/golden-sample check: `python -m pytest tests/test_bond_dashboard_api_contract.py tests/test_bond_dashboard_headlines_contract.py tests/test_bond_analytics_api.py tests/test_result_meta_source_surface_followup.py tests/test_golden_samples_capture_ready.py -q` passed with `49 passed`.
  - Frontend bond dashboard check: `npm run test -- src/test/BondDashboardPage.test.tsx` from `frontend/` passed with `1` test file and `11` tests.
  - Focused Ruff check: `python -m ruff check scripts/mcp/moss_project_mcp.py tests/test_project_mcp_servers.py` passed.
  - Current residual evidence note: `PAGE-BOND-001` has `GS-BOND-HEADLINE-A` as a capture-ready page DTO sample, but `MTR-BOND-001` through `MTR-BOND-004` remain `candidate` with `pending_confirmation=true`; bond dashboard headline and risk fields must not be treated as `MTR-BAL-*` or `PAGE-RISK-001` equivalents without a separate approved contract.
  - 2026-06-03 candidate-metadata follow-up: direct service output for `get_bond_dashboard_headline_kpis(date(2026, 3, 31))` previously returned `basis=formal` / `formal_use_allowed=true`, while the page trace bundle and frontend `bond-dashboard-headline-candidate-boundary` copy kept `MTR-BOND-*` as candidate.
  - 2026-06-03 Bond Dashboard headline metadata fix: `/api/bond-dashboard/headline-kpis` now returns `basis=analytical`, `formal_use_allowed=false`, `quality_flag=warning`, explicit report-date metadata, `date_basis=bond_dashboard_report_date`, `tables_used=["fact_formal_bond_analytics_daily"]`, and source fact row counts. Fresh checks: `python -m pytest tests/test_bond_dashboard_api_contract.py -q` passed with `11 passed`; `python -m ruff check --ignore UP042 backend/app/services/bond_dashboard_service.py tests/test_bond_dashboard_api_contract.py` passed.
  - Bond Dashboard lineage-query follow-up: local `moss-lineage-evidence` fallback now expands `PAGE-BOND-001` to Bond Dashboard APIs (`headline-kpis`, `dates`, `asset-structure`, `yield-distribution`, `portfolio-comparison`, `spread-analysis`, `maturity-structure`, `industry-distribution`, `risk-indicators`, `business-type-metrics`), `bond_dashboard.*` result-kind anchors, `bond_analytics`, `fact_formal_bond_analytics_daily`, `GS-BOND-HEADLINE-A`, and `MTR-BOND-001` through `MTR-BOND-004`, while intentionally not expanding to `MTR-BAL-*`, `GS-BAL-OVERVIEW-A`, `PAGE-RISK-001`, `GS-RISK-A`, or Ledger anchors.
  - Bond Dashboard red/green proof: before the mapping, `python -m pytest tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_bond_dashboard_page_to_candidate_bond_analytics_records -q` failed because `expanded_queries` only contained `PAGE-BOND-001`; after the mapping, the Bond focused test passed with `1 passed`, and the Bond/Liability/Workbench/Balance Movement/Balance/Bridge/PnL/Product Category/Ledger/Cube/Agent/Risk focused lineage set passed with `12 passed`.
  - Real local MCP query proof: `find_lineage_records({"query":"PAGE-BOND-001","max_results":20})` returns the expanded Bond anchors above and 20 sampled records, currently matched through `bond_analytics` / `fact_formal_bond_analytics_daily` records in `agent_audit`; direct `/api/bond-dashboard/headline-kpis` and `bond_dashboard.headline_kpis` lineage queries still return zero records, while direct `fact_formal_bond_analytics_daily` returns existing governance records.
  - Bond Dashboard data-catalog/date proof: `describe_table` succeeds for `fact_formal_bond_analytics_daily` with 38 columns including `report_date`, `instrument_code`, `instrument_name`, `portfolio_name`, `cost_center`, `asset_class_raw`, `asset_class_std`, `bond_type`, `issuer_name`, `industry_name`, `rating`, `accounting_class`, `currency_code`, `face_value`, and `market_value`; latest sampled `report_date` values include `2026-05-31`, `2026-04-30`, `2026-04-29`, `2026-04-28`, `2026-04-27`, `2026-04-26`, `2026-04-25`, and `2026-04-24`.
  - Bond Dashboard data-quality proof: `get_quality_summary` reports `fact_formal_bond_analytics_daily` has 711,479 rows / 38 columns / `report_date` coverage `2024-01-01` to `2026-05-31` / 487 distinct non-null dates / 0 nulls in the first 12 profiled key/classification columns. Golden-sample matches point to `GS-BOND-HEADLINE-A`, including its assertion that the page-level headline remains analytical/candidate metadata even though the source rows come from `fact_formal_bond_analytics_daily`.
  - Current residual evidence note after lineage mapping: the new mapping is query-level traceability to Bond Analytics source-table and page-sample evidence. It still does not create direct governance rows keyed by `PAGE-BOND-001`, `/api/bond-dashboard/headline-kpis`, or `bond_dashboard.headline_kpis`, and it must not be read as dictionary-level approval for `MTR-BOND-*` or equivalence to Balance Analysis or Risk Tensor truth.
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
  - Positions lineage-query follow-up: local `moss-lineage-evidence` fallback now expands `PAGE-POS-001` to `/api/positions/bonds`, `/api/positions/bonds/sub_types`, `/api/positions/interbank`, `/api/positions/interbank/product_types`, `/api/positions/counterparty/bonds`, `/api/positions/counterparty/interbank/split`, `/api/positions/stats/rating`, `/api/positions/stats/industry`, `/api/positions/customer/details`, `/api/positions/customer/trend`, `positions.bonds.list`, `positions.bonds.sub_types`, `positions.interbank.list`, `positions.interbank.product_types`, `positions.counterparty.bonds`, `positions.counterparty.interbank.split`, `positions.stats.rating`, `positions.stats.industry`, `positions.customer.details`, `positions.customer.trend`, `positions_snapshot`, `zqtz_bond_daily_snapshot`, `tyw_interbank_daily_snapshot`, `rv_positions_snapshot_read_v1`, `MTR-POS-001`, and `MTR-POS-002`, while intentionally not expanding to Formal PnL, Product Category PnL, Bond Dashboard headline, Bond Analytics formal fact, Balance Analysis golden sample, or `MTR-BAL-*` anchors.
  - Positions red/green proof: before the mapping, `python -m pytest tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_positions_page_to_candidate_snapshot_records -q` failed because `expanded_queries` only contained `PAGE-POS-001`; after the mapping, the Positions focused test passed with `1 passed`, and the Positions/Bond/Liability/Balance Movement/Balance/Formal PnL/Product Category/Ledger focused lineage set passed with `8 passed`.
  - Real local MCP query proof: `find_lineage_records({"query":"PAGE-POS-001","max_results":8})` returns the expanded Positions anchors above and 8 sampled records, currently matched through underlying `zqtz_bond_daily_snapshot` governance records. Direct `/api/positions/bonds`, `positions.bonds.list`, and `positions.interbank.list` lineage queries still return zero records, while direct `zqtz_bond_daily_snapshot` and `tyw_interbank_daily_snapshot` queries return existing governance records.
  - Positions data-catalog/date proof: `describe_table` succeeds for `zqtz_bond_daily_snapshot` (32 columns) and `tyw_interbank_daily_snapshot` (18 columns). `list_available_dates` shows both snapshot tables have latest sampled `report_date` values through `2026-05-31`, with daily dates such as `2026-04-30`, `2026-04-29`, `2026-04-28`, `2026-04-27`, `2026-04-26`, `2026-04-25`, and `2026-04-24`.
  - Positions data-quality proof: `get_quality_summary` reports `zqtz_bond_daily_snapshot` at 769,768 rows / 32 columns / `report_date` coverage `2024-01-01` to `2026-05-31` / 487 distinct non-null dates / 0 nulls in the first 8 profiled columns; `tyw_interbank_daily_snapshot` at 1,037,926 rows / 18 columns / `report_date` coverage `2025-01-01` to `2026-05-31` / 486 distinct non-null dates / 0 nulls in `report_date`, `position_id`, `product_type`, `position_side`, and `counterparty_name`, with existing nulls in classification fields such as `account_type`, `special_account_type`, and `core_customer_type`.
  - Current residual evidence note after lineage mapping: the new mapping is query-level traceability to Positions snapshot source-table evidence. It still does not create direct governance rows keyed by `PAGE-POS-001`, `/api/positions/bonds`, `/api/positions/interbank`, `positions.bonds.list`, or `positions.interbank.list`; those records must not be read as proof of a specific Positions page/API execution, formal metric approval for `MTR-POS-*`, or equivalence to Formal PnL, Product Category PnL, Bond Dashboard, or Balance Analysis truth.
- Market Data page-contract bundle check:
  - Red check before implementation: `python -m pytest tests/test_project_mcp_servers.py -q` failed with `2 failed, 39 passed` because `market-data` was unknown.
  - Green check after implementation: `python -m pytest tests/test_project_mcp_servers.py -q` passed with `41 passed`.
  - Focused backend/API/mixed-source check: `python -m pytest tests/test_result_meta_on_all_ui_endpoints.py tests/test_market_data_ncd_proxy_api.py tests/test_market_data_livermore_risk_exit_source.py tests/test_fx_analytical_view_api.py tests/test_macro_bond_linkage.py -q` passed with `78 passed`.
  - Focused Livermore API check: `python -m pytest tests/test_market_data_livermore_api.py -q` passed with `34 passed`.
  - Frontend market-data page/model/route check: `npm run test -- src/test/MarketDataPage.test.tsx src/features/market-data/pages/marketDataPageModel.test.ts src/test/RouteRegistry.test.tsx` from `frontend/` passed with `3` test files and `56` tests.
  - Focused Ruff check: `python -m ruff check scripts/mcp/moss_project_mcp.py tests/test_project_mcp_servers.py` passed.
  - Current residual evidence note: `PAGE-MKT-001` has no full-page capture-ready golden sample; `MTR-MKT-001` remains `candidate` with `pending_confirmation=true` and `bound_sample_id=none`; `/ui/market-data/rates` is only a formal rates fragment; NCD is a Shibor/funding proxy; Livermore `risk_exit` remains backend-owned and gated by unsupported outputs/readiness/data gaps.
  - Market Data lineage-query follow-up: local `moss-lineage-evidence` fallback now expands `PAGE-MKT-001` to `/ui/preview/macro-foundation`, `/ui/market-data/rates`, `/ui/market-data/fx/formal-status`, `/ui/market-data/fx/analytical`, `/ui/market-data/ncd-funding-proxy`, `/api/macro-bond-linkage`, `/ui/macro/choice-series/latest`, `/ui/market-data/livermore`, `/ui/market-data/livermore/stock-detail`, `/ui/market-data/livermore/candidate-history`, `/ui/market-data/livermore/sector-rank-series`, `preview.macro-foundation`, `market_data.rates`, `market_data.catalog`, `macro.choice.latest`, `fx.formal.status`, `fx.analytical.groups`, `market_data.ncd_proxy`, `market_data.livermore`, `market_data.livermore.stock_detail`, `market_data.livermore.candidate_history`, `market_data.livermore.sector_rank_series`, `macro_bond_linkage.analysis`, `macro_bond_linkage.environment_context`, `fact_choice_macro_daily`, `market_data_series_category`, `fx_daily_mid`, `livermore_position_snapshot`, `choice_stock_daily_observation`, `fact_livermore_gate_supplement_daily`, market-data rule-version anchors, `MTR-MKT-001`, and `GAP-MKT-DATA`, while intentionally not expanding to Formal PnL, Product Category PnL, Balance, Positions, Bond Dashboard, Bond Analytics, or related golden-sample anchors.
  - Market Data red/green proof: before the mapping, `python -m pytest tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_market_data_page_to_mixed_source_records -q` failed because `expanded_queries` only contained `PAGE-MKT-001`; after the mapping, the Market Data focused test passed with `1 passed`, and the Market Data/Positions/Bond/Liability/Balance Movement/Balance/Formal PnL/Product Category/Ledger focused lineage set passed with `9 passed`.
  - Real local MCP query proof: `find_lineage_records({"query":"PAGE-MKT-001","max_results":8})` returns the expanded Market Data anchors above and 8 sampled records, currently matched only through `fx_daily_mid` records in balance-analysis governance streams. Direct `/ui/preview/macro-foundation`, `/ui/market-data/rates`, `market_data.rates`, `preview.macro-foundation`, `fx.formal.status`, `fx.analytical.groups`, `market_data.ncd_proxy`, and `market_data.livermore` lineage queries still return zero records; direct `fact_choice_macro_daily`, `livermore_position_snapshot`, `choice_stock_daily_observation`, and `fact_livermore_gate_supplement_daily` also return zero lineage-stream records in this pass.
  - Market Data data-catalog/date proof: `describe_table` succeeds for `fact_choice_macro_daily` (11 columns), `fx_daily_mid` (12 columns), `market_data_series_category` (11 columns), `livermore_position_snapshot` (15 columns), `choice_stock_daily_observation` (19 columns), and `fact_livermore_gate_supplement_daily` (7 columns). Date columns are not uniform: macro/FX/stock/gate tables use `trade_date`, while Livermore positions use `as_of_date`; latest sampled dates reach `2026-06-01` for `fact_choice_macro_daily`, `2026-05-31` for `fx_daily_mid`, and `2026-05-29` for the Livermore/Choice-stock tables.
  - Market Data data-quality proof: `get_quality_summary` reports `fact_choice_macro_daily` at 4,066 rows with 0 nulls in the first 8 profiled columns; `fx_daily_mid` at 1,104 rows with 0 nulls in the first 8 profiled columns; `market_data_series_category` at 143 rows with 0 nulls in the first 8 profiled columns; `livermore_position_snapshot` at 3 rows / `as_of_date` coverage `2026-05-13` to `2026-05-29` with 3 null `entry_date` values but no nulls in the other first 8 profiled fields; `choice_stock_daily_observation` at 2,973,951 rows with 5,907 nulls each in price/volume/amount fields among the first 8 profiled fields; and `fact_livermore_gate_supplement_daily` at 737 rows with 0 nulls in all 7 profiled columns.
  - Current residual evidence note after lineage mapping: the new mapping is query-level traceability to mixed-source Market Data anchors and currently samples only `fx_daily_mid` governance records. It still does not create direct governance rows keyed by `PAGE-MKT-001`, the Market Data page APIs, or the Market Data result kinds; it must not be read as full-page formal truth, formal approval for `MTR-MKT-001`, proof of an actual NCD term-rating matrix, or proof that Livermore `risk_exit` is unblocked.
- Executive Summary page-contract bundle check:
  - Red check before implementation: `python -m pytest tests/test_project_mcp_servers.py -q` failed with `2 failed, 41 passed` because `executive-summary` was unknown.
  - Green check after implementation: `python -m pytest tests/test_project_mcp_servers.py -q` passed with `43 passed`.
  - Focused backend/endpoint/release/golden-sample check: `python -m pytest tests/test_executive_service_contract.py tests/test_executive_dashboard_endpoints.py tests/test_executive_release_contract.py tests/test_golden_samples_capture_ready.py -q` passed with `65 passed`.
  - Frontend summary section check: `npm run test -- src/test/SummarySection.test.tsx` from `frontend/` passed with `1` test file and `3` tests.
  - Focused Ruff check: `python -m ruff check scripts/mcp/moss_project_mcp.py tests/test_project_mcp_servers.py` passed.
  - Executive Summary lineage-query follow-up: local `moss-lineage-evidence` fallback now expands `PAGE-EXEC-SUMMARY-001` to `/ui/home/summary`, `executive.summary`, `executive-summary`, `executive_summary`, `SummaryPayload`, `SummaryPoint`, `GS-EXEC-SUMMARY-A`, `narrative-only`, and `executive.overview`, while intentionally not expanding to `PAGE-EXEC-OVERVIEW-001`, `GS-EXEC-OVERVIEW-A`, `MTR-EXEC-*`, `PAGE-EXEC-PNL-ATTR-001`, or `GS-EXEC-PNL-ATTR-A`.
  - Executive Summary red/green proof: before the mapping, `python -m pytest tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_executive_summary_page_to_narrative_records -q` failed because `expanded_queries` only contained `PAGE-EXEC-SUMMARY-001`; after the mapping, the focused Executive Summary lineage test passed with `1 passed`, and the Summary bundle / Summary lineage / Executive Overview / Dashboard Home / Workbench focused lineage set passed with `5 passed`.
  - Real local MCP query proof: `find_lineage_records({"query":"PAGE-EXEC-SUMMARY-001","max_results":8})` now returns the expanded Executive Summary narrative-only anchors above, but it returns zero records in the current governance streams. Direct `/ui/home/summary`, `executive.summary`, `GS-EXEC-SUMMARY-A`, and `executive.overview` lineage queries also return zero direct records in this pass.
  - Golden-sample/service proof: `GS-EXEC-SUMMARY-A` asserts `/ui/home/summary`, `result_meta.basis="analytical"`, `formal_use_allowed=false`, `result_kind="executive.summary"`, `report_date="2026-02-28"`, `points.length == 3`, and the frozen point labels. Service tests verify `executive_summary()` carries the requested report date and reuses overview lineage source/rule versions when `executive_overview()` resolves with `vendor_status="ok"`.
  - Current residual evidence note: `PAGE-EXEC-SUMMARY-001` is a narrative-only contract; `GS-EXEC-SUMMARY-A` freezes title, points length, point labels, and result metadata for `/ui/home/summary`, but does not promote narrative text into formal business metrics or cover upstream no-data/fallback/stale states.
- Macro Toolkit and Macro Observation page-contract bundle check:
  - Red check before implementation: `python -m pytest tests/test_project_mcp_servers.py -q` failed with `4 failed, 43 passed` because `macro-toolkit` and `macro-observation` were unknown.
  - Green check after implementation: `python -m pytest tests/test_project_mcp_servers.py -q` passed with `47 passed`.
  - Focused backend/doc/API/auth check: `python -m pytest tests/test_governance_doc_contract.py::test_macro_toolkit_page_contract_closes_tooling_route_without_metric_promotion tests/test_page_contract_metric_dictionary_completeness.py tests/test_live_route_page_contract_completeness.py tests/test_macro_toolkit_scripts.py tests/test_macro_toolkit_choice_stock_refresh_overview.py tests/test_macro_toolkit_factor_snapshot_dates.py tests/test_macro_toolkit_a_share_risk.py tests/test_macro_query_contract_smoke.py tests/test_write_route_auth_contract.py -q` passed with `136 passed`.
  - Frontend macro route/page/client check: `npm run test -- src/test/MacroToolkitPage.test.tsx src/test/RouteRegistry.test.tsx src/test/navigation.test.ts src/test/macroToolkitClient.test.ts` from `frontend/` passed with `4` test files and `113` tests.
  - Focused Ruff check: `python -m ruff check scripts/mcp/moss_project_mcp.py tests/test_project_mcp_servers.py` passed.
  - Focused whitespace check: `git diff --check -- docs/audits/2026-06-02-system-audit-first-pass.md scripts/mcp/moss_project_mcp.py tests/test_project_mcp_servers.py` passed.
  - Macro Toolkit lineage-query follow-up: local `moss-lineage-evidence` fallback now expands `PAGE-MACRO-TOOLKIT-001` to `/ui/macro/toolkit/analysis`, `/ui/macro/toolkit/analysis/strategy-summaries`, `/ui/macro/toolkit/scripts`, script-run prefix, Choice stock refresh/status, CFFEX member-rank refresh, source-backfill refresh, commodity-futures refresh, `macro_toolkit.analysis`, `macro_toolkit.analysis.strategy_summaries`, `macro_toolkit.scripts`, `macro_toolkit.choice_stock_refresh`, `macro_toolkit.cffex_member_rank_refresh`, Macro Toolkit payload/response classes, `candidate tooling surface`, and `source/version/run_id`, while intentionally not expanding to `MTR-*`, `MTR-MACRO-*`, or a dedicated golden sample.
  - Macro Observation lineage-query follow-up: local `moss-lineage-evidence` fallback now expands `PAGE-MACRO-OBS-001` only to `/ui/macro/toolkit/analysis`, `/ui/macro/toolkit/analysis/strategy-summaries`, `macro-observation`, `macro_observation`, `macro_toolkit.analysis`, `macro_toolkit.analysis.strategy_summaries`, `MacroToolkitAnalysisPayload`, `macro-observation-readonly-boundary`, and `read-only macro observation`, while intentionally not expanding to script registry, script-run, refresh, refresh-status, operational toolkit anchors, `MTR-*`, or a dedicated golden sample.
  - Macro Toolkit / Observation red/green proof: before the mappings, `python -m pytest tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_macro_toolkit_page_to_tooling_records tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_macro_observation_page_to_readonly_records -q` failed because `expanded_queries` only contained the page IDs; after the mappings, those two lineage tests passed with `2 passed`, and the Macro Toolkit / Macro Observation bundle plus lineage focused set passed with `4 passed`.
  - Real local MCP query proof: `find_lineage_records({"query":"PAGE-MACRO-TOOLKIT-001","max_results":8})` and `find_lineage_records({"query":"PAGE-MACRO-OBS-001","max_results":8})` now return the expanded anchors above, but both return zero records in the current governance streams. Direct `/ui/macro/toolkit/analysis`, `macro_toolkit.analysis`, `/ui/macro/toolkit/scripts`, `macro-observation`, and `macro_toolkit.analysis.strategy_summaries` lineage queries also return zero direct records in this pass.
  - Current residual evidence note: `PAGE-MACRO-TOOLKIT-001` and `PAGE-MACRO-OBS-001` have no dedicated golden samples and no `MTR-MACRO-*`; macro toolkit analysis, strategy, script, refresh, source/version/run_id, and coverage outputs are tooling/tracing evidence only, while macro observation remains read-only and must not expose script registry, run, refresh, or operational controls.
- Agent, Cube Query, and module-home page-contract bundle check:
  - Red check before implementation: `python -m pytest tests/test_project_mcp_servers.py -q` failed with `10 failed, 47 passed` because `agent`, `cube-query`, `portfolio-home`, `market-home`, `risk-home`, `performance-home`, and `reports-home` were unknown.
  - Green check after implementation: `python -m pytest tests/test_project_mcp_servers.py -q` passed with `57 passed`.
  - Frontend focused page/tool check: `npm run test -- src/test/ModuleWorkbenchHomeModel.test.ts src/test/ModuleWorkbenchHomePage.test.tsx src/test/CubeQueryPage.test.tsx src/test/AgentWorkbenchPage.test.tsx src/test/AgentPlaceholderPage.test.tsx src/test/AgentClient.test.ts src/test/RouteRegistry.test.tsx` from `frontend/` passed with `7` test files and `180` tests after a transient earlier failure in the Agent restore-status case was not reproducible in isolation or on fresh suite rerun.
  - Agent lineage-query follow-up: local `moss-lineage-evidence` fallback now expands `PAGE-AGENT-001` to `agent.`, `AgentEnvelope`, `agent_audit`, `/api/agent/runs`, and `/api/agent/query`.
  - Real local MCP query proof: `find_lineage_records({"query":"PAGE-AGENT-001","max_results":5})` returns `expanded_queries=["PAGE-AGENT-001","agent.","AgentEnvelope","agent_audit","/api/agent/runs","/api/agent/query"]`, with sampled records from `stream="agent_audit"` matched on `agent.`, `result_kind` values such as `agent.pnl_summary` / `agent.disabled`, `formal_use_allowed=false`, and `tables_used=[]` or unset.
  - Focused lineage regression check: `python -m pytest tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_agent_page_contract_to_agent_audit_records tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_page_risk_contract_to_risk_tensor_records tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_reads_governance_stream_status -q` passed with `3 passed`.
  - Focused Ruff and whitespace checks for the Agent/Risk lineage mapping files passed: `python -m ruff check scripts/mcp/moss_project_mcp.py tests/test_project_mcp_servers.py`; `git diff --check -- scripts/mcp/moss_project_mcp.py tests/test_project_mcp_servers.py`.
  - Cube Query lineage-query follow-up: local `moss-lineage-evidence` fallback now expands `PAGE-CUBE-QUERY-001` to `PAGE-CUBE-QUERY-001`, `/api/cube/query`, `cube_query.`, `fact_formal_bond_analytics_daily`, `fact_formal_pnl_fi`, `fact_formal_zqtz_balance_daily`, and `product_category_pnl_formal_read_model`.
  - Cube Query red/green proof: before the mapping, `python -m pytest tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_cube_query_page_to_allowed_source_tables -q` failed because `expanded_queries` only contained `PAGE-CUBE-QUERY-001`; after the mapping, the Agent/Risk/Cube focused lineage set passed with `4 passed`.
  - Real local MCP query proof: `find_lineage_records({"query":"PAGE-CUBE-QUERY-001","max_results":8})` returns the expanded Cube anchors above and sampled `cache_manifest` / `agent_audit` records matched on `fact_formal_bond_analytics_daily`; no sampled record is keyed directly by `PAGE-CUBE-QUERY-001` or `cube_query.*`.
  - Cube Query data-catalog/date proof: `describe_table` succeeds for all four backend-approved Cube source tables. `list_available_dates(..., report_date, limit=5)` shows latest dates through `2026-05-31` for all four tables.
  - Cube Query data-quality proof: `get_quality_summary` reports `report_date_nulls=0` for all four source tables, with row/date coverage of `fact_formal_bond_analytics_daily` 711,479 rows / `2024-01-01` to `2026-05-31`, `fact_formal_pnl_fi` 24,474 rows / `2025-01-31` to `2026-05-31`, `fact_formal_zqtz_balance_daily` 1,539,536 rows / `2024-01-01` to `2026-05-31`, and `product_category_pnl_formal_read_model` 2,204 rows / `2024-01-31` to `2026-05-31`.
  - Module-home lineage-query follow-up: local `moss-lineage-evidence` fallback now expands `PAGE-PORTFOLIO-HOME-001` to `module-home/portfolio`, balance overview/date, Bond Dashboard, Positions, PnL Attribution, formal balance, bond analytics, position snapshot, and Formal PnL source-table anchors; `PAGE-MARKET-HOME-001` to `module-home/market`, Choice latest, market rates/catalog, macro toolkit analysis/strategy, macro/market/FX support-table anchors; `PAGE-RISK-HOME-001` to `module-home/risk`, risk tensor dates/detail, cashflow projection, formal risk tensor, and formal balance source-table anchors; `PAGE-PERFORMANCE-HOME-001` to `module-home/performance`, KPI owners/summary, business PnL YTD, product-category PnL, Formal PnL, and product-category source-table anchors; and `PAGE-REPORTS-HOME-001` to `module-home/governance`, `/health/live`, `/health`, source foundation, cube dimensions, cube query, bond analytics, and source-foundation diagnostic anchors.
  - Module-home red/green proof: before the mapping, `python -m pytest tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_module_home_pages_to_downstream_read_records -q` failed for all five module-home page IDs because `expanded_queries` only contained the page ID; after the mapping and health-path alignment, `python -m pytest tests/test_project_mcp_servers.py::test_module_home_trace_bundles_preserve_downstream_truth_boundaries tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_module_home_pages_to_downstream_read_records -q` passed with `6 passed`.
  - Real local MCP query proof: `find_lineage_records({"query":"PAGE-PORTFOLIO-HOME-001","max_results":8})` currently samples only `agent_audit` records matched on `fact_formal_zqtz_balance_daily` with `result_kind="agent.portfolio_overview"`; `PAGE-MARKET-HOME-001` samples only `fx_daily_mid` cache/build records from balance materialization; `PAGE-RISK-HOME-001` samples `agent.risk_tensor` records matched on `fact_formal_risk_tensor_daily`; `PAGE-PERFORMANCE-HOME-001` samples `agent.pnl_summary` records matched on `fact_formal_pnl_fi`; and `PAGE-REPORTS-HOME-001` samples Agent duration/risk records matched on `fact_formal_bond_analytics_daily`.
  - Direct module-home anchor proof: direct `find_lineage_records` queries for `module-home/portfolio`, `module-home/market`, `module-home/risk`, `module-home/performance`, and `module-home/governance` return zero records in the current governance streams. Direct `/api/kpi/owners`, `kpi.owners`, `/health/live`, and `health.live` queries also return zero records in this pass.
  - Current residual evidence note: these seven page contracts intentionally have no dedicated golden samples and no standalone `MTR-*` bindings; Agent answers remain read-only/formal-use gated, Cube Query remains scoped to returned query `result_meta`, and module-home pages remain navigation/aggregation surfaces whose formal claims stay on downstream pages.
- Stock Analysis observation-surface follow-up:
  - Contract evidence: `docs/live_route_maturity.md` still marks `/stock-analysis` as `temporary-exception` / `GAP-STOCK-ANALYSIS-PAGE`; `search_contract_docs` found no `PAGE-STOCK-*` or `MTR-STOCK-*` bindings.
  - Stock Analysis trace-bundle follow-up: local `moss-metric-contracts` fallback now resolves `stock-analysis`, `/stock-analysis`, and `GAP-STOCK-ANALYSIS-PAGE` to a seeded GAP bundle whose `page_id` remains `GAP-STOCK-ANALYSIS-PAGE`, `primary_api` is `/ui/market-data/livermore`, `golden_samples=[]`, and guardrails explicitly forbid trading instructions, formal metric truth, `MTR-*` promotion, and hidden readiness failures.
  - Stock Analysis lineage-query follow-up: local `moss-lineage-evidence` fallback now expands `GAP-STOCK-ANALYSIS-PAGE`, `stock-analysis`, and `/stock-analysis` to Livermore read APIs (`/ui/market-data/livermore`, signal confluence, stock detail, candidate history, strategy score/optimization, proxy backtests, sector series), observational result kinds (`market_data.livermore*`), support tables (`livermore_position_snapshot`, `livermore_candidate_history`, `choice_stock_daily_observation`, `fact_livermore_gate_supplement_daily`), and Livermore rule-version anchors while intentionally not expanding to `PAGE-STOCK-*`, `MTR-*`, `GS-*`, Formal PnL, Product Category PnL, or Bond Dashboard anchors.
  - Local MCP lineage/catalog evidence: the new synthetic regression stream returns Livermore records with `formal_use_allowed=false` and `full_strategy_status="blocked_missing_inputs"` where applicable. The real current governance streams still lack direct rows keyed by `GAP-STOCK-ANALYSIS-PAGE`, `/stock-analysis`, `/ui/market-data/livermore`, or `market_data.livermore*`, so this is query-level traceability rather than page-run proof. Earlier catalog/date sampling found no stock/livermore tables in the then-current `data/moss.duckdb` inventory; Market Data later sampled Livermore support-table catalog/date/quality evidence, but Stock Analysis still needs a route-specific catalog/date review.
  - Code/test evidence: Livermore strategy, signal confluence, stock detail, and candidate-history paths are tested as `basis=analytical` / `formal_use_allowed=false`, with observation-only / no-trading-instruction copy present in API and frontend tests.
  - Focused backend checks: `python -m pytest tests/test_market_data_livermore_api.py tests/test_market_data_livermore_stock_detail.py -q` passed with `37 passed`; `python -m pytest tests/test_market_data_livermore_candidate_history.py -q` passed with `48 passed`.
  - Frontend check: `npm run test -- src/test/StockAnalysisPage.test.tsx src/features/stock-analysis/lib/buildConsensusSummary.test.ts` from `frontend/` passed with `2` test files and `53` tests.
  - Stock Analysis MCP red/green proof: before the bundle/lineage mapping, `python -m pytest tests/test_project_mcp_servers.py::test_stock_analysis_trace_bundle_preserves_observational_livermore_boundaries tests/test_project_mcp_servers.py::test_lineage_evidence_mcp_maps_stock_analysis_gap_to_observational_livermore_records -q` failed because `stock-analysis` was an unknown page slug and `GAP-STOCK-ANALYSIS-PAGE` expanded only to itself; after the mapping, the two Stock Analysis MCP tests passed with `2 passed`, and the Market Data / module-home / Stock Analysis focused MCP regression set passed with `10 passed`.
  - Current residual evidence note: no formal-metadata promotion was found in this sampled pass, and the seeded GAP bundle narrows the previous missing-bundle risk. `/stock-analysis` still lacks a standalone formal PAGE contract, dedicated golden sample, direct page-keyed governance records, route-specific catalog/date closure, and full MCP catalog/date review. It should remain observational-only until `GAP-STOCK-ANALYSIS-PAGE` is closed through explicit contract/sample/lineage work.
- Focused `risk-tensor` page evidence verification after the bundle check:
  - `python -m pytest tests/test_risk_tensor_api.py tests/test_risk_tensor_service.py tests/test_risk_tensor_repo.py tests/test_risk_tensor_core.py tests/test_risk_tensor_materialize.py tests/test_risk_tensor_numeric_migration.py tests/test_risk_tensor_liquidity.py tests/test_golden_samples_capture_ready.py -q`
  - Result: `82 passed`.
  - `npm run test -- src/test/RiskTensorPage.test.tsx` from `frontend/`
  - Result: `1 passed` test file, `40 passed` tests.
- Cashflow Projection and Concentration Monitor candidate-metadata follow-up:
  - Contract evidence: `docs/metric_dictionary.md` keeps `MTR-CFP-001` through `MTR-CFP-004` bound to `PAGE-CONTRACT-PENDING:/cashflow-projection`, `bound_sample_id=none`, and `pending_confirmation=true`; it keeps `MTR-CON-001` through `MTR-CON-004` bound to `PAGE-CONTRACT-PENDING:/concentration-monitor`, `bound_sample_id=none`, and `pending_confirmation=true`.
  - 2026-06-03 Cashflow Projection metadata fix: `/api/cashflow-projection` now returns `basis=analytical`, `formal_use_allowed=false`, `quality_flag=warning`, `date_basis=cashflow_projection_report_date`, explicit requested/resolved/as_of report-date metadata, `source_surface=cashflow`, `tables_used=["fact_formal_zqtz_balance_daily", "fact_formal_tyw_balance_daily"]`, applied filters, and evidence-row counts from the source rows used by the payload. The frontend mock client now mirrors the same candidate metadata.
  - 2026-06-03 Concentration Monitor metadata fix: `/api/bond-analytics/credit-spread-migration` now returns `basis=analytical`, `formal_use_allowed=false`, `quality_flag=warning`, `date_basis=bond_analytics_report_date`, explicit requested/resolved/as_of report-date metadata, `source_surface=bond_analytics`, `tables_used=["fact_formal_bond_analytics_daily"]`, applied spread-scenario filters, and evidence-row counts from the source rows used by the payload. The frontend mock client now mirrors the same candidate metadata.
  - Local MCP fallback evidence: `search_contract_docs` finds the pending candidate dictionary rows, but `find_lineage_records` returns zero records for `cashflow_projection.overview`, `bond_analytics.credit_spread_migration`, `MTR-CFP-001`, and `MTR-CON-001`.
  - Fresh Cashflow checks: `python -m pytest tests/test_cashflow_projection.py tests/test_result_meta_source_surface_followup.py tests/test_cashflow_projection_numeric_migration.py tests/test_wave5_service_explicit_numeric.py -q` passed with `28 passed`; `npm run test -- src/test/ApiClientCompositionBoundary.test.ts src/test/CashflowProjectionPage.test.tsx src/features/cashflow-projection/adapters/cashflowProjectionAdapter.test.ts src/features/cashflow-projection/pages/cashflowProjectionPageModel.test.ts` passed with `64 passed`; `python -m ruff check backend/app/services/cashflow_projection_service.py tests/test_cashflow_projection.py tests/test_result_meta_source_surface_followup.py` passed; `npm run debt:audit` passed.
  - Fresh Concentration checks: `python -m pytest tests/test_bond_analytics_service.py::test_bond_analytics_credit_spread_migration_uses_credit_subset_and_concentration tests/test_bond_analytics_curve_effects.py::test_credit_spread_migration_marks_result_meta_stale_when_curve_fallback_used tests/test_bond_analytics_curve_effects.py::test_credit_spread_migration_marks_result_meta_unavailable_when_curves_missing tests/test_bond_analytics_api.py::test_bond_analytics_home_supplement_routes_log_api_perf -q` passed with `4 passed`; `npm run test -- src/test/ApiClientCompositionBoundary.test.ts src/test/BondAnalyticsClient.test.ts src/test/ConcentrationMonitorPage.test.tsx src/test/CreditSpreadView.test.tsx src/test/RiskOverviewPage.test.tsx` passed with `58 passed`; `python -m ruff check backend/app/services/bond_analytics_service.py tests/test_bond_analytics_service.py tests/test_bond_analytics_api.py` passed; `npm run debt:audit` passed.
  - Current residual evidence note: Cashflow Projection and Concentration Monitor may use formal source tables internally, but their page-level metrics are still pending confirmation. They need a full contract/sample/lineage upgrade before the API can safely imply page-metric formal-use approval.
- Candidate metadata follow-up verification:
  - `python -m pytest tests/test_project_mcp_servers.py tests/test_ledger_pnl_service.py tests/test_bond_dashboard_api_contract.py tests/test_positions_api_contract.py tests/test_result_meta_source_surface_followup.py tests/test_bond_analytics_api.py tests/test_adb_analysis_api.py -q`
  - Result after the Ledger metadata fix: `114 passed in 93.84s (0:01:33)`.
  - This verifies the current contract/service behavior, the Ledger metadata weakening, and the control analytical ADB boundary. The additional Bond Dashboard headline, Positions, Cashflow, and Concentration checks above close the sampled candidate/page-contract-pending outward metadata mismatches.

## Evidence Gaps

- This pass did not dynamically prove unauthenticated route exploitability with a running backend. The code-level evidence is enough to classify the authorization boundary as high-risk, but endpoint-level runtime validation should be part of the fix pass.
- Python dependency security was not fully audited with a locked Python environment. Frontend production dependency audit had no reported prod vulnerabilities in the delegated scan, but Python CVE coverage remains incomplete.
- Direct `moss-*` MCP tools were not exposed in the current Codex App deferred tool surface. `tool_search` exposed Playwright/GitHub/Canva/Node tools, but not `moss-metric-contracts`, `moss-lineage-evidence`, `moss-data-catalog`, `moss-data-quality`, or `gitnexus` callable tools. This continuation used the local JSON-RPC MCP process as a read-only fallback and records that distinction.
- `PAGE-RISK-001` / `risk-tensor` now has sampled contract/catalog/data-quality evidence, a seeded MCP page trace bundle, a focused page evidence check, and an explicit lineage-query mapping to existing `fact_formal_risk_tensor_daily` / `agent.risk_tensor` records. It still does not create a separate governance stream row keyed directly by the page contract ID.
- `PAGE-AGENT-001` / `agent` now has an explicit lineage-query mapping to existing `agent_audit` records. This is query-level traceability only: it does not create a page-keyed governance stream row, dedicated golden sample, standalone `MTR-*`, or permission to treat Agent answers as formal metric evidence.
- `PAGE-CUBE-QUERY-001` / `cube-query` now has an explicit query-level mapping to the Cube Query API/result-kind anchors and the four backend-approved formal source tables, plus sampled catalog/date/quality evidence. It still lacks a Cube-query-run governance record keyed by `PAGE-CUBE-QUERY-001`, `/api/cube/query`, or `cube_query.*`; table-level lineage must not be read as proof of a specific Cube Query run.
- `PAGE-LEDGER-PNL-001` / `ledger-pnl` now has an explicit query-level mapping to Ledger API/result-kind anchors, the QDB general ledger workbook source, and the formal financial indicator source-contract fixture. The current governance streams still return no records for those Ledger-specific anchors, and the mapping intentionally does not point at `fact_formal_pnl_fi` / `fact_nonstd_pnl_bridge`; candidate Ledger summary lineage remains incomplete until a Ledger-specific governance record or approved summary sample exists.
- `PAGE-PROD-CAT-PNL-001` / `PAGE-PROD-CAT-001` now has an explicit query-level mapping to Product Category PnL API/result-kind/formal read-model/canonical/golden-sample/metric anchors, plus sampled catalog/date/quality evidence for the formal and canonical tables. The current governance sample still mixes completed/queued/running/failed cache-build records and has no direct record keyed by the page contract ID or `product_category_pnl_formal_read_model`; cache-build lineage must not be read as proof of a successful page-level run.
- `PAGE-PNL-001` / `pnl` now has an explicit query-level mapping to Formal PnL API/result-kind/fact-table/golden-sample/metric anchors, plus sampled catalog/date/quality evidence for `fact_formal_pnl_fi` and `fact_nonstd_pnl_bridge`. The current governance sample still returns source-table/cache-level and Agent summary records rather than direct rows keyed by `PAGE-PNL-001`, `pnl.overview`, or `pnl.data`; those records must not be read as proof of a specific page/API execution.
- `PAGE-PNL-BY-BUSINESS-001` / `pnl-by-business` now has an explicit query-level mapping to Business Type PnL YTD/monthly/formal/analysis API anchors, `pnl.by_business*` result-kind anchors, Formal PnL source tables, ZQTZ balance source table, `fact_pnl_by_business_precompute`, and `pnl_by_business_adjustments`, plus sampled catalog/date/quality evidence for the precompute and source tables. The current governance sample still returns only Agent/source-table records rather than direct rows keyed by the page ID, Business Type PnL APIs, `pnl.by_business*`, the precompute table, or adjustment stream; those records must not be read as proof of a specific Business Type PnL page/API execution, newly approved `MTR-*`, dedicated golden sample, Product Category truth, Ledger truth, Formal PnL overview truth, PnL Bridge truth, or permission to mix formal reconciliation rows into monthly/YTD business conclusions.
- `PAGE-BRIDGE-001` / `pnl-bridge` now has an explicit query-level mapping to PnL Bridge API/result-kind/source-surface/fact-table/golden-sample/metric anchors, plus sampled catalog/date/quality evidence for the underlying Formal PnL source tables. The current governance sample still returns source-surface/source-table/cache-level and Agent summary records rather than direct rows keyed by `PAGE-BRIDGE-001`, `/api/pnl/bridge`, or `pnl.bridge`; those records must not be read as proof of a specific bridge page/API execution.
- `PAGE-BALANCE-001` / `balance-analysis` now has an explicit query-level mapping to Balance Analysis overview/workbook API/result-kind/formal-balance fact-table/golden-sample/metric anchors, plus sampled catalog/date/quality evidence for `fact_formal_zqtz_balance_daily` and `fact_formal_tyw_balance_daily`. The current governance sample still returns Agent/table-level records rather than direct rows keyed by `PAGE-BALANCE-001`, `/ui/balance-analysis/overview`, `/ui/balance-analysis/workbook`, `balance-analysis.overview`, or `balance-analysis.workbook`; those records must not be read as proof of a specific Balance page/API execution.
- `PAGE-PNL-ATTR-WB-001` / `pnl-attribution` now has an explicit query-level mapping to Workbench API/result-kind/payload/formal-attribution source-table/metric anchors, plus sampled catalog/date/quality evidence for the underlying Formal PnL, Balance, and Bond Analytics source tables. The current governance sample still returns Agent/table-level records rather than direct rows keyed by `PAGE-PNL-ATTR-WB-001`, `/api/pnl-attribution/*`, or `pnl_attribution.*`; those records must not be read as proof of a specific Workbench page/API execution, and this mapping intentionally excludes the executive analytical attribution overlay.
- `PAGE-BAL-MOVE-001` / `balance-movement-analysis` now has an explicit query-level mapping to Balance Movement API/result-kind/accounting-asset movement fact/cache/source/payload/metric anchors, plus sampled catalog/date/quality evidence for `fact_accounting_asset_movement_monthly`. The current governance sample still returns table/cache-level and Agent summary records rather than direct rows keyed by `PAGE-BAL-MOVE-001`, `/ui/balance-movement-analysis`, or `balance-analysis.movement.*`; those records must not be read as proof of a specific Balance Movement page/API execution, and the page still has no dedicated golden sample.
- `PAGE-LIAB-ANALYTICS-001` / `liability-analytics` now has an explicit query-level mapping to Liability Analytics compatibility API/result-kind/formal-liability/source-table/payload/metric anchors, plus sampled catalog/date/quality evidence for formal balance, snapshot, and the `yield_by_period` Formal PnL dependency. The current governance sample still returns table/cache-level and Agent summary records rather than direct rows keyed by `PAGE-LIAB-ANALYTICS-001`, `/api/risk/buckets`, or `liability_analytics.*`; those records must not be read as proof of a specific Liability page/API execution, and the page remains analytical mixed-source with no dedicated golden sample.
- `PAGE-BOND-001` / `bond-dashboard` now has an explicit query-level mapping to Bond Dashboard API/result-kind/bond-analytics source-table/page-sample/candidate-metric anchors, plus sampled catalog/date/quality evidence for `fact_formal_bond_analytics_daily`. The current governance sample still returns table-level and Agent summary records rather than direct rows keyed by `PAGE-BOND-001`, `/api/bond-dashboard/headline-kpis`, or `bond_dashboard.headline_kpis`; those records must not be read as proof of a specific Bond Dashboard page/API execution, dictionary-level approval for `MTR-BOND-*`, or equivalence to Balance Analysis / Risk Tensor truth.
- `PAGE-POS-001` / `positions` now has an explicit query-level mapping to Positions API/result-kind/snapshot source-table/candidate-metric anchors, plus sampled catalog/date/quality evidence for `zqtz_bond_daily_snapshot` and `tyw_interbank_daily_snapshot`. The current governance sample still returns snapshot/source-table records rather than direct rows keyed by `PAGE-POS-001`, `/api/positions/bonds`, `/api/positions/interbank`, `positions.bonds.list`, or `positions.interbank.list`; those records must not be read as proof of a specific Positions page/API execution, dictionary-level approval for `MTR-POS-*`, or equivalence to Formal PnL / Product Category PnL / Bond Dashboard / Balance Analysis truth.
- `PAGE-MKT-001` / `market-data` now has an explicit query-level mapping to Market Data preview/rates/FX/NCD/Livermore/macro-bond-linkage API/result-kind/table anchors, plus sampled catalog/date/quality evidence for market macro, FX, and Livermore support tables. The current governance sample still returns only `fx_daily_mid` records through Balance materialization lineage rather than direct rows keyed by `PAGE-MKT-001`, `/ui/preview/macro-foundation`, `/ui/market-data/rates`, `market_data.rates`, `preview.macro-foundation`, `fx.formal.status`, `fx.analytical.groups`, `market_data.ncd_proxy`, or `market_data.livermore`; those records must not be read as proof of full-page formal truth, dictionary-level approval for `MTR-MKT-001`, an actual NCD matrix, or unblocked Livermore risk-exit.
- `GAP-STOCK-ANALYSIS-PAGE` / `stock-analysis` now has an explicit GAP trace bundle and query-level mapping to observational Livermore read APIs/result kinds/support tables/rule versions. The current governance sample still lacks direct rows keyed by `GAP-STOCK-ANALYSIS-PAGE`, `/stock-analysis`, `/ui/market-data/livermore`, or `market_data.livermore*`; those mappings and synthetic regression records must not be read as formal PAGE contract closure, a dedicated golden sample, route-specific catalog/date closure, trading-instruction approval, `PAGE-STOCK-*` creation, or `MTR-*` creation.
- `PAGE-OPS-001` / `operations-analysis` now has an explicit query-level mapping to product-category headline truth, supplemental balance overview, source preview, macro preview, FX status, and Choice news anchors, plus sampled catalog/date/quality evidence for product-category, formal balance, macro, FX, and news support tables. The current governance sample still returns table/Agent-level records rather than direct rows keyed by `PAGE-OPS-001`, `/ui/pnl/product-category`, `product_category_pnl.detail`, `/ui/balance-analysis/overview`, `balance-analysis.overview`, preview/macro/FX/news result kinds, or a dedicated `MTR-OPS-*`; those records must not be read as proof of a specific Operations page/API execution, Balance workbook closure, Formal PnL equivalence, Bond Dashboard equivalence, Positions equivalence, or retirement of `GAP-OPS-MACRO-FX`.
- `PAGE-DASH-001` / `dashboard-home` now has an explicit query-level mapping to the Dashboard Home mixed-source snapshot API/result-kind/payload/date-domain/supplemental/source-table anchors, plus sampled catalog/date/quality evidence for formal balance, Formal PnL, snapshot, bond analytics, product-category PnL, and FX source tables. The current governance sample still returns source-table records rather than direct rows keyed by `PAGE-DASH-001`, `/ui/home/snapshot`, `home.snapshot`, `dashboard.core_metrics`, or `bond_dashboard.headline_kpis`; those records must not be read as proof of a specific Dashboard Home page/API execution, child page closure, full-page formal truth, or downstream candidate-metric promotion.
- `PAGE-EXEC-OVERVIEW-001` / `executive-overview` now has an explicit query-level mapping to Executive Overview analytical-overlay API/result-kind/schema/golden-sample/metric anchors, plus sampled catalog/date/quality evidence for formal balance, formal PnL, liability snapshot, and bond-analytics source tables. The current governance sample still returns Agent/table-level records rather than direct rows keyed by `PAGE-EXEC-OVERVIEW-001`, `/ui/home/overview`, `executive.overview`, `GS-EXEC-OVERVIEW-A`, or `MTR-EXEC-*`; those records must not be read as proof of a specific Executive Overview page/API execution, full formal metric truth, Balance page closure, PnL page closure, Risk Tensor page closure, or Executive PnL Attribution closure.
- `PAGE-EXEC-SUMMARY-001` / `executive-summary` now has an explicit query-level mapping to Executive Summary narrative-only API/result-kind/payload/point/golden-sample/overview-lineage anchors. The current governance stream still returns zero records keyed by `PAGE-EXEC-SUMMARY-001`, `/ui/home/summary`, `executive.summary`, or `GS-EXEC-SUMMARY-A`; the mapping and `GS-EXEC-SUMMARY-A` must not be read as formal metric approval, evidence of upstream metric availability, or permission to hide upstream no-data/fallback/stale states behind narrative text.
- `PAGE-MACRO-TOOLKIT-001` / `macro-toolkit` and `PAGE-MACRO-OBS-001` / `macro-observation` now have explicit query-level mappings to macro tooling and read-only observation anchors. The current governance stream still returns zero records keyed by the page IDs, macro toolkit APIs, or `macro_toolkit.*` result kinds; these mappings must not be read as formal macro metric approval, `MTR-MACRO-*` creation, investment signal approval, or evidence that operational script/run/refresh outputs are governed business metrics. Macro Observation intentionally excludes script registry, run, refresh, refresh-status, and operational toolkit anchors.
- `PAGE-PORTFOLIO-HOME-001`, `PAGE-MARKET-HOME-001`, `PAGE-RISK-HOME-001`, `PAGE-PERFORMANCE-HOME-001`, and `PAGE-REPORTS-HOME-001` now have explicit query-level mappings to module-home downstream read APIs/result kinds/source-table anchors. The current governance sample still returns only downstream table/cache/Agent records, while direct `module-home/*` anchors and sampled direct KPI/health diagnostic anchors return zero records; these mappings must not be read as module-home page execution proof, standalone `MTR-*` creation, dedicated golden-sample coverage, or permission to hide downstream missing/stale/fallback/error state.
- Page-level MCP bundle coverage now resolves 28 unique seeded trace IDs in `product_page_trace_bundles()`, including `PAGE-PNL-BY-BUSINESS-001` and the observational `GAP-STOCK-ANALYSIS-PAGE`. This coverage is first-pass traceability only; it does not prove every page's data lineage, date semantics, browser state, golden-sample coverage, or Stock Analysis formal PAGE closure.
- Sampled candidate/page-contract-pending metadata is now separated from formal source-table usage for Ledger PnL summary/detail, Bond Dashboard headline, Positions list counts, Cashflow Projection, and Concentration Monitor. These fields remain candidate/pending and should not be promoted without dictionary, page-contract, golden-sample, and lineage closure.
- No full data-catalog/date lineage review was completed for every metric page.
- Browser axe now completes for the four covered smoke pages, but broader page coverage is not complete.

## Recommended Next Pass

1. Finish the authorization policy semantics closure: classify every business/governance route as public/internal/admin, have business owners confirm resource/action names and permission grouping, and keep future development-only auth bypasses behind production startup guardrails.
2. Continue the bounded architecture remediation for `bond_analytics_service` calculation drift: decide whether remaining action-attribution orchestration belongs in the service layer as an explicit exception, while leaving PnL/repository lookup, analysis-adapter fallback calls, schema validation, and result-envelope assembly clearly outside `core_finance`.
3. Audit the next highest-risk governed metric pages for data-catalog/date-lineage gaps using the 28 seeded trace bundles as the routing map, starting with pages that mix formal source tables with candidate or tooling display fields and keeping `GAP-STOCK-ANALYSIS-PAGE` separate from formal PAGE closure.
4. Decide whether the broad backend Ruff backlog is a release blocker or a separately tracked cleanup stream.
5. Add coverage reporting first, then focused coverage gates for high-risk business display paths.
6. Use direct MOSS MCP contract/lineage/catalog tools when exposed, or invoke the equivalent project scripts, to audit source lineage and date semantics for ledger-pnl, stock-analysis, Agent Workbench formal-use/date boundaries, commodity ingest, and governed metric pages.
7. Keep the updated a11y smoke in the release gate, and add page-specific ready selectors as new browser smoke pages are covered.
