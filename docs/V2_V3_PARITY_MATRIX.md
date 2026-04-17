# V2 -> V3 Parity Matrix

## Goal

This document records which V2 consumer surfaces already have a V3 landing path, which ones are only partially landed, and which ones remain explicitly outside the current repo-wide `Phase 2` cutover.

It complements, but does not replace:

- `docs/V2_TO_V3_MIGRATION_INVENTORY.md`
- `docs/REPO_WIDE_PHASE2_CUTOVER_DEFINITION.md`
- `docs/EXECUTIVE_CUTOVER_EVALUATION_2026-04-17.md`

## Status Labels

| Label | Meaning |
| --- | --- |
| `landed` | V3 already has a concrete route/page and primary backend read path. |
| `partial` | V3 has part of the surface, but consumer shape, page coverage, or data-plane completeness is still missing. |
| `analytical-only` | V3 has a usable route, but it is not part of the governed formal mainline. |
| `excluded` | The surface is explicitly outside the current repo-wide `Phase 2` cutover. |
| `missing` | No meaningful V3 consumer surface is currently landed. |

## Snapshot

| Metric | V2 | V3 |
| --- | --- | --- |
| Frontend page components | 37 | 28 |
| Backend route files | 35 | 24 |
| Default posture | broader consumer rollout | governed formal-compute cutover with explicit exclusions |

Interpretation:

- V2 is broader at the consumer layer.
- V3 is narrower by design, because the current default boundary is `repo-wide Phase 2` for the governed formal mainline, plus `executive-consumer cutover v1`.

## Matrix

| V2 surface | V2 route/page | V3 current landing | V3 primary backend path | Status | Notes |
| --- | --- | --- | --- | --- | --- |
| Dashboard / cockpit | `/dashboard` / `Dashboard.tsx` | `/` / `DashboardPage.tsx` | `backend/app/api/routes/executive.py` | `landed` | Backed by current executive consumer overlay for overview and summary. |
| Operations summary | `FinancialAnalysis.tsx` / overview-style summary | `/operations-analysis` / `OperationsAnalysisPage.tsx` | `macro_vendor.py`, `choice_news.py`, `macro_bond_linkage.py` | `partial` | V3 consolidates operating views, but not as a one-to-one V2 replacement. |
| Management report | `ManagementReport.tsx` | no dedicated V3 page; closest is executive summary plus report placeholder | no dedicated management-report route in V3 | `missing` | High-value parity gap. V2 had a dedicated report consumer; V3 does not. |
| ALCO cockpit | `AlcoCockpit.tsx` | no dedicated page | no dedicated ALCO route | `missing` | Some underlying metrics exist, but there is no V3 ALCO consumer surface. |
| Market overview | `MarketOverview.tsx` | `/market-data` / `MarketDataPage.tsx` | `macro_vendor.py`, `macro_bond_linkage.py` | `partial` | Usable analytical workbench exists, but vendor/preview/analytical surfaces remain outside the governed formal cutover. |
| Macro analysis | `MacroAnalysis.tsx` | `/market-data`, `/cross-asset`, `/operations-analysis` | `macro_vendor.py`, `macro_bond_linkage.py` | `analytical-only` | Present as analytical consumers, not as a promoted governed formal family. |
| Positions | `Positions.tsx` | `/positions` / `PositionsPage.tsx` | `backend/app/api/routes/positions.py` | `landed` | Concrete route and API exist, though V2 had a broader page family around it. |
| Asset analytics | `AssetAnalytics.tsx` | folded into `/balance-analysis` and `/bond-analysis` | `balance_analysis.py`, `bond_analytics.py` | `partial` | V3 covers the governed read surfaces, but not the same page split as V2. |
| Bond analytics | `BondAnalytics.tsx` | `/bond-analysis` / `BondAnalyticsView` | `backend/app/api/routes/bond_analytics.py` | `landed` | Included in current formal read-surface boundary. |
| Bond analytics advanced | `BondAnalyticsAdvanced.tsx` | `/bond-analysis` cockpit modules | `bond_analytics.py`, `campisi_attribution.py` | `partial` | Several advanced slices exist, but not as a V2-style separate full page. |
| Bond dashboard | `BondBookAi.tsx` plus bond overview surfaces | `/bond-dashboard` / `BondDashboardPage.tsx` | `backend/app/api/routes/bond_dashboard.py` | `landed` | V3 has a dedicated bond dashboard landing page. |
| Liability analytics | `LiabilityAnalytics.tsx` | `/liability-analytics` / `LiabilityAnalyticsPage.tsx` | `backend/app/api/routes/liability_analytics.py` | `analytical-only` | Wired end-to-end in V3, but `liability_analytics_compat` is still excluded from the current formal cutover. |
| Average balance / ADB | `AverageBalance.tsx` | `/average-balance` / `AverageBalancePage.tsx` | `backend/app/api/routes/adb_analysis.py` | `analytical-only` | Present and routable, but explicitly framed as compatibility/analytical. |
| PnL main page | `PnlAnalysis.tsx` | `/pnl` / `PnlPage.tsx` | `backend/app/api/routes/pnl.py` | `landed` | Formal PnL chain is included in the current cutover. |
| PnL bridge | V2 had bridge-like decomposition across multiple pages | `/pnl-bridge` / `PnlBridgePage.tsx` | `backend/app/api/routes/pnl.py` | `landed` | V3 has a cleaner dedicated bridge surface. |
| PnL attribution | `PnLAttribution.tsx` | `/pnl-attribution` / `PnlAttributionPage.tsx` | `backend/app/api/routes/pnl_attribution.py` | `landed` | Also included in `executive-consumer cutover v1`. |
| Product category PnL | `ProductCategory.tsx` | `/product-category-pnl` / `ProductCategoryPnlPage.tsx` | `backend/app/api/routes/product_category_pnl.py` | `landed` | Feature is implemented, but current live snapshot has no available report dates. |
| Product category audit | not first-class in V2 | `/product-category-pnl/audit` / `ProductCategoryAdjustmentAuditPage.tsx` | `product_category_pnl.py` | `landed` | V3 adds a stronger adjustment audit surface. |
| PnL by business | `PnlByBusiness.tsx` | no dedicated V3 page | no dedicated route | `missing` | Candidate follow-up after main PnL parity. |
| Balance analysis | `BalanceAnalysis.tsx` | `/balance-analysis` / `BalanceAnalysisPage.tsx` | `backend/app/api/routes/balance_analysis.py` | `landed` | One of the clearest governed formal chains in V3. |
| Reconciliation | `Reconciliation.tsx` | no dedicated V3 page | no dedicated reconciliation route | `missing` | Important parity gap. |
| Risk analysis | `RiskAnalysis.tsx` | `/risk-overview`, `/risk-tensor` | `backend/app/api/routes/risk_tensor.py`, `executive.py` | `partial` | Formal tensor exists; management-layer overview/alerts are still uneven. |
| Risk alerts | `RiskAlerts.tsx` | executive alerts panel only | `backend/app/api/routes/executive.py` | `excluded` | Explicitly excluded from current executive cutover. |
| Agent tools | `AgentTools.tsx` | `/agent` / `AgentWorkbenchPage.tsx` | `backend/app/api/routes/agent.py` | `partial` | Page exists, but Agent MVP and real `/api/agent/query` enablement remain excluded. |
| Agent chat | `AgentChat.tsx` | no dedicated V3 chat page | `agent.py` stub path only | `missing` | Current V3 keeps Agent as foundation, not a fully landed consumer. |
| KPI performance | `KPIPerformance.tsx` | `/kpi` / `KpiPerformancePage.tsx` | `backend/app/api/routes/kpi.py` | `landed` | V3 preserves a concrete KPI workbench. |
| Scenario | `Scenario.tsx` | no dedicated V3 scenario page | no dedicated scenario route | `excluded` | Current boundary keeps scenario outside promoted consumer rollout. |
| Import / task monitor | `DataImport.tsx`, `TaskMonitor.tsx` | no dedicated V3 import/task page | task-like refresh APIs exist, but no task center route | `missing` | V2 consumer coverage is broader here. |
| Utils / diagnostics | `UtilsTest.tsx` | `/platform-config` and shell diagnostics | `health.py`, governance-backed status readers | `partial` | V3 has platform/config health, but not a direct V2-style utilities page. |
| Cube query | V2 had no equivalent first-class page | `/cube-query` / `CubeQueryPage.tsx` | `backend/app/api/routes/cube_query.py` | `excluded` | Implemented in repo, but still outside current broad rollout. |

## Main Gaps Relative to V2

1. V3 still lacks dedicated consumer pages for:
   - management report
   - ALCO
   - reconciliation
   - import/task monitor
   - pnl-by-business
2. Executive rollout is intentionally narrower than V2.
3. Agent remains a foundation surface, not a promoted landed product surface.
4. Several analytical workbenches exist in V3, but are not yet promoted into the current governed cutover.

## Recommended Follow-ups

1. Add a dedicated V3 management-report consumer page before widening executive rollout.
2. Add a V3 reconciliation consumer page; this is the clearest missing parity item after management reporting.
3. Decide whether `liability-analytics`, `market-data`, and `cube-query` should stay analytical-only or move into a later named cutover.
4. Replace route-by-route ambiguity with a maintained parity table in the same style as V2 whenever a new consumer surface lands.
