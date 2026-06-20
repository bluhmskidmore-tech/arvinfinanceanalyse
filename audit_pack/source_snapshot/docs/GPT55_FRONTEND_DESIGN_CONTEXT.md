# GPT-5.5 Pro Frontend Design Context

This file is a single-file handoff for redesigning the MOSS-V3 frontend. It is intentionally written as context for a stronger design agent: it explains the current architecture, visual language, layout system, page inventory, and backend API surface without asking that agent to rediscover the repo from zero.

## Copy-Paste Prompt For GPT-5.5 Pro

```text
You are designing the next frontend pass for MOSS-V3, an internal institutional fixed-income / portfolio analytics web workbench.

Read this handoff as the source of truth for the current frontend structure, visual style, page layout model, and backend API relationships. Your job is to produce a frontend design proposal or implementation plan that preserves business metric correctness and data lineage.

Hard constraints:
- Do not redefine business metrics, units, dates, or financial formulas.
- Do not invent backend fields or endpoints. Use the existing ApiClient methods and backend endpoints listed here unless the user explicitly approves API changes.
- Keep page-level closure: every page should answer one primary business question first.
- Surface no data, stale data, fallback date, loading failure, and pending metric-definition states explicitly.
- Keep changes small and page/workflow scoped. Do not refactor platform architecture, auth, database schema, queues, cache base layers, or global SDK wrappers.
- Do not grow `frontend/src/api/client.ts` for new endpoint work; use domain clients when endpoint work is needed.

Design goals:
- Current product is a dense, audit-friendly business workbench, not a marketing site.
- Improve visual hierarchy, rhythm, and scanability while preserving compact data density.
- Use the existing design token system and Ant Design theme as the base.
- Prefer real page layouts, data tables, KPI rows, evidence panels, and drilldown surfaces over decorative dashboards.

Please output:
1. A page-by-page design direction.
2. A component hierarchy and layout wire structure for each changed page.
3. Token/style changes, if any, with exact target files.
4. API methods consumed by each page, unchanged unless explicitly requested.
5. Risks and validation checks.
```

## Current Product Shape

- Product: internal business web application for fixed-income portfolio, asset/liability, PnL, market, risk, KPI, and governance workflows.
- Users: investment/trading, risk, finance/operations, and management users who need conclusions plus traceable evidence.
- Priority: business metric correctness, page-level closure, traceability, validation, and minimal reviewable changes.
- Not a priority: generic frontend framework rebuild, backend platform refactor, visual novelty, or unrelated performance tuning.

The strongest visual authority in the repo is [DESIGN.md](../DESIGN.md) plus the reference image [frontend/dashboard-reference.png](../frontend/dashboard-reference.png). The current codebase implements a light institutional workbench with a dark left rail, pale gray-blue app background, white data surfaces, compact KPI cards, and explicit data state handling.

## Frontend Directory Map

```text
frontend/
  index.html                         # root HTML, Google font links, #root
  vite.config.ts                     # Vite dev/preview proxy and vendor chunking
  package.json                       # React 18, Vite, AntD 5, React Query, ECharts, AG Grid
  src/
    main.tsx                         # React root -> AppProviders -> App
    app/
      App.tsx                        # imports global.css and renders RouteRegistry
      providers.tsx                  # AntD ConfigProvider + ApiClientProvider + QueryClientProvider
    router/
      RouteRegistry.tsx              # createBrowserRouter(workbenchRoutes)
      routes.tsx                     # lazy route map under WorkbenchShell
      routerFuture.ts                # React Router future flags
      WorkbenchRouteFallback.tsx     # lazy route fallback
    layouts/
      WorkbenchShell.tsx             # main app shell, rail, header, section nav, Outlet
      workbenchShellTicker.ts        # shell ticker helpers
    mocks/
      navigation.ts                  # source of navigation groups, routes, readiness, aliases
      workbench.ts                   # workbench mock payloads
      productCategoryPnl.ts          # product PnL mocks near domain
    theme/
      designSystem.ts                # primary design token source
      tokens.ts                      # shell token aliases
      displayTokens.ts               # KPI/section/banner/display tokens
      theme.ts                       # AntD ThemeConfig
      README.md
    styles/
      global.css                     # app-level CSS variables, shell grid, responsive rules
    api/
      client.ts                      # ApiClient composition and legacy shared real/mock methods
      contracts.ts                   # frontend API payload types and Numeric primitives
      balanceAnalysisClient.ts       # type slice
      balanceMovementClient.ts       # real/mock domain client
      bondAnalyticsClient.ts         # type slice
      ledgerClient.ts                # real/mock domain client
      marketDataClient.ts            # real/mock domain client
      pnlClient.ts                   # type slice
      positionsClient.ts             # type slice
    components/
      page/PagePrimitives.tsx        # PageHeader, PageSurfacePanel, PageV2 shell primitives
      page/PagePrimitiveStyles.ts    # page surface style constants
      KpiCard.tsx                    # standard KPI card
      DataSection.tsx                # data state wrapper: ok/loading/error/empty/stale/fallback
      AsyncSection.tsx               # simpler async section wrapper
      FilterBar.tsx                  # standard filter tray
      StatusPill.tsx                 # status badge
      SectionCard.tsx                # repeated section card
      charts/BaseChart.tsx           # chart wrapper
    lib/
      echarts.tsx                    # ECharts modules registered here
      agGridSetup.ts                 # AG Grid setup
    features/
      workbench/                     # dashboard, operations analysis, placeholders
      balance-analysis/
      balance-movement-analysis/
      liability-analytics/
      average-balance/
      positions/
      ledger-dashboard/
      ledger-pnl/
      pnl/
      pnl-attribution/
      product-category-pnl/
      bond-dashboard/
      bond-analytics/
      market-data/
      cross-asset/
      news-events/
      risk-overview/
      risk-tensor/
      concentration-monitor/
      cashflow-projection/
      kpi-performance/
      team-performance/
      platform-config/
      cube-query/
      source-preview/
      agent/
    test/
      *.test.ts(x)                   # Vitest + Testing Library coverage
```

## Runtime And Data Mode

- Frontend dev server: Vite uses port `5888`.
- Backend default proxy target: `http://127.0.0.1:7888`, configured by `MOSS_VITE_API_PROXY`.
- Vite proxies `/ui`, `/api`, and `/health` to the backend in dev/preview.
- `VITE_DATA_SOURCE=real|mock` controls `createApiClient`.
- `VITE_API_BASE_URL` is usually blank in dev so calls use same-origin paths and Vite proxy. If set, trailing slashes are normalized.
- `AppProviders` creates one React Query client with `staleTime: 60000`, `retry: 0`, and `refetchOnWindowFocus: false`.
- AntD theme is injected through `ConfigProvider` with `workbenchTheme`.

Important files:

- `frontend/.env.development`
- `frontend/.env.example`
- `frontend/vite.config.ts`
- `frontend/src/app/providers.tsx`
- `frontend/src/api/client.ts`

## Frontend Execution Chain

```text
index.html
  -> src/main.tsx
    -> <AppProviders>
      -> <ConfigProvider theme={workbenchTheme}>
      -> <ApiClientProvider client={createApiClient()}>
      -> <QueryClientProvider>
        -> <App>
          -> <RouteRegistry>
            -> createBrowserRouter(workbenchRoutes)
              -> <WorkbenchShell>
                -> <Outlet /> feature page
```

Navigation is metadata-driven:

- `frontend/src/mocks/navigation.ts` owns `workbenchNavigation`, `workbenchSectionGroups`, readiness labels, path aliases, and visible navigation groups.
- `frontend/src/router/routes.tsx` maps those paths to lazy-loaded feature pages.
- `WorkbenchShell` reads navigation metadata to render group context, subnavigation, readiness banners, and page chrome.

## Current Layout Model

The main shell is `WorkbenchShell`.

- Outer grid: `.workbench-shell-grid`, two columns: `minmax(188px, 212px)` left rail and `minmax(0, 1fr)` main.
- App background: light gray-blue with soft radial accents, anchored around `#f5f7f9`.
- Left rail: sticky, solid dark background `#121d2a`, rounded panel, subtle shadow.
- Main column: header/hero/subnav/readiness banners plus page content.
- Standard main content: white surface, rounded panel, shallow shadow.
- Page-owned chrome: some dense pages opt out of the outer white panel and own their layout directly. Current examples include bond analysis, cross-asset, balance-analysis-style portfolio pages, balance movement, and liability analytics.
- Responsive:
  - `max-width: 1180px`: shell collapses to one column, aside becomes static.
  - `max-width: 900px`: dashboard grids collapse toward one column.
  - `max-width: 720px`: table containers and composer controls adapt for small screens.

Design implication: do not design a marketing landing page. The first screen should be the usable workbench surface, with conclusion-first panels, filters, KPIs, tables, charts, and evidence.

## Visual Language

Source of truth:

- `frontend/src/theme/designSystem.ts`
- `frontend/src/theme/tokens.ts`
- `frontend/src/theme/displayTokens.ts`
- `frontend/src/theme/theme.ts`
- `frontend/src/styles/global.css`
- `DESIGN.md`

Core colors:

| Purpose | Token / value | Notes |
|---|---:|---|
| App background | `neutral[50]` `#f5f7f9` | light gray-blue institutional base |
| Main text | `neutral[900]` `#1f2937` | primary body/headings |
| Secondary text | `neutral[600]` `#6b7280` | descriptions, labels |
| Muted text | `neutral[500]` `#8b95a1` | eyebrows, helper text |
| Primary blue | `primary[600]` `#1850a1` | primary actions, active state |
| Info blue | `info[500]` `#3b82f6` | links and secondary emphasis |
| Success | `success[500]` `#2d8a5e` | positive/profit/ok |
| Warning | `warning[500]` `#d97706` | caution/stale/fallback |
| Danger | `danger[500]` `#ef4444` | negative/loss/error |
| Rail background | `#121d2a` | main navigation rail |
| Surface | `#ffffff` | data cards, panels, tables |

Typography:

- UI/body: `"Plus Jakarta Sans", "PingFang SC", "Microsoft YaHei UI", "Noto Sans SC", system-ui, sans-serif`.
- Numeric/table/KPI values: `"IBM Plex Mono", ui-monospace, "Noto Sans Mono", Menlo, Monaco, Consolas, monospace` plus `fontVariantNumeric: tabular-nums`.
- Typical scale: body `13-14px`, helper `11-12px`, section title `18-20px`, KPI value `20-24px`, page title around `30-32px`.
- Keep compact density; do not shrink data rows below readability.

Spacing, radii, shadows:

- Spacing is 4px based: `4, 8, 12, 16, 20, 24, 32, 40, 48, 64`.
- Common radii: `6`, `12`, `18`, `24`.
- Current generic card radius sometimes reaches `18-24`; the newer frontend design instruction prefers restrained cards around `8px` where possible. If redesigning, explicitly decide whether to preserve current token radii or migrate page-by-page.
- Shadows are shallow: panel `0 20px 44px rgba(22,35,46,.08)`, card `0 10px 24px rgba(22,35,46,.06)`.

UI mood:

- Industrial / utilitarian / audit-friendly.
- Dense but organized, with clear scan paths.
- Pale surfaces, thin borders, shallow shadows.
- Data-state banners are functional, not decorative.
- Avoid purple-heavy gradients, all-blue monotone pages, oversized hero blocks, decorative blobs, and generic dashboard ornament.

## Reusable Display Components

Use these before inventing new primitives:

| Component | File | Use |
|---|---|---|
| `PageHeader` | `frontend/src/components/page/PagePrimitives.tsx` | page-level title, description, badge, actions |
| `PageSectionLead` | `frontend/src/components/page/PagePrimitives.tsx` | section heading/description |
| `PageFilterTray` | `frontend/src/components/page/PagePrimitives.tsx` | filter/control tray |
| `PageSurfacePanel` | `frontend/src/components/page/PagePrimitives.tsx` | white lifted page surface |
| `PageV2Shell` / `PageV2SurfacePanel` | `frontend/src/components/page/PagePrimitives.tsx` | newer simpler page shell/surface |
| `KpiCard` | `frontend/src/components/KpiCard.tsx` | metric card with tone, unit, sparkline, status |
| `DataSection` | `frontend/src/components/DataSection.tsx` | data block with loading/error/empty/stale/fallback states |
| `AsyncSection` | `frontend/src/components/AsyncSection.tsx` | simpler loading/error/empty wrapper |
| `FilterBar` | `frontend/src/components/FilterBar.tsx` | standard control row |
| `StatusPill` | `frontend/src/components/StatusPill.tsx` | readiness/status pill |
| `FormalResultMetaPanel` | `frontend/src/components/page/FormalResultMetaPanel.tsx` | trace/source/result metadata display |
| `BaseChart` / `lib/echarts.tsx` | `frontend/src/components/charts`, `frontend/src/lib/echarts.tsx` | chart wrapper and ECharts registration |

Data states that should be preserved:

- `loading`: skeleton / "正在载入".
- `error`: explicit failure + retry.
- `empty`: explicit no data.
- `vendor_unavailable`: domain unavailable.
- `explicit_miss`: requested report date has no data.
- `stale`: effective date shown.
- `fallback`: fallback date shown.

## API Architecture

Key files:

- `frontend/src/api/client.ts`: ApiClient type, shared real/mock composition, React context.
- `frontend/src/api/contracts.ts`: payload types, `ApiEnvelope<T>`, `ResultMeta`, governed `Numeric`.
- `frontend/src/api/balanceMovementClient.ts`: real/mock `/ui/balance-movement-analysis/*`.
- `frontend/src/api/ledgerClient.ts`: real/mock `/api/ledger/*`.
- `frontend/src/api/marketDataClient.ts`: real/mock market-data and macro endpoints.
- `frontend/src/api/*Client.ts`: domain method type slices.

Important payload conventions:

- Most governed endpoints return `ApiEnvelope<T>`:

```ts
type ApiEnvelope<T> = {
  result_meta: ResultMeta;
  result: T;
};
```

- Governed numeric fields use:

```ts
type Numeric = {
  raw: number | null;
  unit: "yuan" | "pct" | "bp" | "ratio" | "count" | "dv01" | "yi";
  display: string;
  precision: number;
  sign_aware: boolean;
};
```

Design implication: pages should show `display`, unit, source/fallback/stale metadata, and should not recalculate official financial metrics in the browser.

## Route And Backend API Matrix

### Overview Workbench

| Frontend path | Page/component | ApiClient methods | Backend endpoints |
|---|---|---|---|
| `/`, `/dashboard` | `features/workbench/pages/DashboardPage.tsx` | `getHomeSnapshot`, `getResearchCalendarEvents`; child dashboard sections also use market/news/bond/liability endpoints | `/ui/home/snapshot`, `/ui/calendar/supply-auctions`, plus child section endpoints |
| `/operations-analysis` | `features/workbench/pages/OperationsAnalysisPage.tsx` | `getSourceFoundation`, `getMacroFoundation`, `getChoiceMacroLatest`, `getFxFormalStatus`, `getChoiceNewsEvents`, `getBalanceAnalysisDates`, `getProductCategoryDates`, `getBalanceAnalysisOverview`, `getProductCategoryPnl` | `/ui/preview/source-foundation`, `/ui/preview/macro-foundation`, `/ui/macro/choice-series/latest`, `/ui/market-data/fx/formal-status`, `/ui/news/choice-events/latest`, `/ui/balance-analysis/*`, `/ui/pnl/product-category*` |
| `/decision-items` | `features/decision-items/pages/DecisionItemsPage.tsx` | `getBalanceAnalysisDates`, `getBalanceAnalysisCurrentUser`, `getBalanceAnalysisDecisionItems`, `updateBalanceAnalysisDecisionStatus` | `/ui/balance-analysis/dates`, `/ui/balance-analysis/current-user`, `/ui/balance-analysis/decision-items`, `/ui/balance-analysis/decision-items/status` |

### Portfolio Workbench

| Frontend path | Page/component | ApiClient methods | Backend endpoints |
|---|---|---|---|
| `/balance-analysis` | `features/balance-analysis/pages/BalanceAnalysisPage.tsx` | `getBalanceAnalysisDates`, `getBalanceAnalysisOverview`, `getBalanceAnalysisWorkbook`, `getBalanceAnalysisCurrentUser`, `getBalanceAnalysisDecisionItems`, `getBalanceAnalysisDetail`, `getBalanceAnalysisSummary`, `getBalanceAnalysisSummaryByBasis`, `getAdbComparison`, `getBalanceAnalysisAdvancedAttribution`, `refreshBalanceAnalysis`, `getBalanceAnalysisRefreshStatus`, `updateBalanceAnalysisDecisionStatus`, exports | `/ui/balance-analysis/*`, `/api/analysis/adb/comparison` |
| `/balance-movement-analysis` | `features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.tsx` | `getBalanceMovementDates`, `getBalanceMovementAnalysis`, `refreshBalanceMovementAnalysis` | `/ui/balance-movement-analysis/dates`, `/ui/balance-movement-analysis`, `/ui/balance-movement-analysis/refresh` |
| `/liability-analytics` | `features/liability-analytics/pages/LiabilityAnalyticsPage.tsx` | `getBalanceAnalysisDates`, `getBalanceAnalysisOverview`, `getLiabilityRiskBuckets`, `getLiabilityYieldMetrics`, `getLiabilityCounterparty`, `getLiabilitiesMonthly`, `getLiabilityKnowledgeBrief`, `getLiabilityAdbMonthly` | `/ui/balance-analysis/*`, `/api/risk/buckets`, `/api/analysis/yield_metrics`, `/api/analysis/liabilities/counterparty`, `/api/liabilities/monthly`, `/ui/liability/business-context`, `/api/analysis/adb/monthly` |
| `/average-balance` | `features/average-balance/pages/AverageBalancePage.tsx` -> `AverageBalanceView` | `getBalanceAnalysisDates`, `getAdbComparison`, `getAdbMonthly` | `/ui/balance-analysis/dates`, `/api/analysis/adb/comparison`, `/api/analysis/adb/monthly` |
| `/positions` | `features/positions/pages/PositionsPage.tsx` -> `PositionsView` | position lists, subtypes, counterparty splits, rating/industry stats, customer details/trends | `/api/positions/bonds*`, `/api/positions/interbank*`, `/api/positions/counterparty/*`, `/api/positions/stats/*`, `/api/positions/customer/*` |
| `/bank-ledger-dashboard` | `features/ledger-dashboard/pages/LedgerDashboardPage.tsx` | `getLedgerDates`, `getLedgerDashboard`, `getLedgerPositions`, `exportLedgerPositions` | `/api/ledger/dates`, `/api/ledger/dashboard`, `/api/ledger/positions`, `/api/ledger/export/positions` |
| `/ledger-pnl` | `features/ledger-pnl/pages/LedgerPnlPage.tsx` | `getLedgerPnlDates`, `getLedgerPnlSummary`, `getLedgerPnlData` | `/api/ledger-pnl/dates`, `/api/ledger-pnl/summary`, `/api/ledger-pnl/data` |
| `/pnl` | `features/pnl/PnlPage.tsx` | `getFormalPnlDates`, `getFormalPnlOverview`, `getFormalPnlData`, `getLiabilityYieldMetrics`, `refreshFormalPnl`, `getFormalPnlImportStatus` | `/api/pnl/dates`, `/api/pnl/overview`, `/api/pnl/data`, `/api/analysis/yield_metrics`, `/api/data/refresh_pnl`, `/api/data/import_status/pnl` |
| `/pnl-bridge` | `features/pnl/PnlBridgePage.tsx` | `getFormalPnlDates`, `getPnlBridge`, `refreshFormalPnl`, `getFormalPnlImportStatus` | `/api/pnl/dates`, `/api/pnl/bridge`, `/api/data/*` |
| `/pnl-attribution` | `features/pnl-attribution/pages/PnlAttributionPage.tsx` -> `PnlAttributionView` | `getVolumeRateAttribution`, `getPnlAttributionAnalysisSummary`, `getTplMarketCorrelation`, `getPnlCompositionBreakdown`, advanced attribution and Campisi methods | `/api/pnl-attribution/volume-rate`, `/api/pnl-attribution/tpl-market`, `/api/pnl-attribution/composition`, `/api/pnl-attribution/summary`, `/api/pnl-attribution/advanced/*`, `/api/pnl-attribution/campisi/*` |
| `/product-category-pnl` | `features/product-category-pnl/pages/ProductCategoryPnlPage.tsx` | product category dates, main PnL, attribution, manual adjustments, refresh/status, exports | `/ui/pnl/product-category/*` |
| `/product-category-pnl/audit` | `features/product-category-pnl/pages/ProductCategoryAdjustmentAuditPage.tsx` | manual adjustment audit methods | `/ui/pnl/product-category/manual-adjustments*` |
| monthly branch inside product PnL | `MonthlyOperatingAnalysisBranch.tsx`, `MonthlyOperatingAnalysisAuditPage.tsx` | QDB monthly dates/workbook/scenario/adjustments/refresh/export | `/ui/qdb-gl-monthly-analysis/*` |
| `/bond-dashboard` | `features/bond-dashboard/pages/BondDashboardPage.tsx` | bond dashboard dates, headline KPIs, structures, yield distribution, comparisons, spread, maturity, industry, risk | `/api/bond-dashboard/*` |
| `/bond-analysis` | `features/bond-analytics/components/BondAnalyticsView.tsx` and child components | bond analytics dates, return decomposition, benchmark excess, KRD, credit spread, action attribution, accounting audit, portfolio headlines, top holdings, yield curve term structure, refresh/status, calendar, macro ticker | `/api/bond-analytics/*`, `/api/credit-spread-analysis/detail`, `/ui/calendar/supply-auctions`, `/ui/macro/choice-series/latest` |

### Market Workbench

| Frontend path | Page/component | ApiClient methods | Backend endpoints |
|---|---|---|---|
| `/market-data` | `features/market-data/pages/MarketDataPage.tsx` | `getMacroFoundation`, `getChoiceMacroLatest`, `getFxAnalytical`, `getNcdFundingProxy`, `getLivermoreStrategy`, `getMacroBondLinkageAnalysis`, `refreshChoiceMacro`, `getChoiceMacroRefreshStatus`, child news/calendar calls | `/ui/preview/macro-foundation`, `/ui/macro/choice-series/latest`, `/ui/market-data/fx/analytical`, `/ui/market-data/ncd-funding-proxy`, `/ui/market-data/livermore`, `/api/macro-bond-linkage/analysis`, `/ui/macro/choice-series/refresh*`, `/ui/news/choice-events/latest` |
| `/cross-asset`, `/cross-asset-drivers` | `features/cross-asset/pages/CrossAssetPage.tsx` / `CrossAssetDriversPage.tsx` | `getChoiceMacroLatest`, `getResearchCalendarEvents`, `getMacroBondLinkageAnalysis`, `getNcdFundingProxy` | `/ui/macro/choice-series/latest`, `/ui/calendar/supply-auctions`, `/api/macro-bond-linkage/analysis`, `/ui/market-data/ncd-funding-proxy` |
| `/news-events` | `features/news-events/NewsEventsPage.tsx` | `getChoiceNewsEvents` | `/ui/news/choice-events/latest` |

### Risk Workbench

| Frontend path | Page/component | ApiClient methods | Backend endpoints |
|---|---|---|---|
| `/risk-overview` | `features/risk-overview/RiskOverviewPage.tsx` | `getRiskTensorDates`, `getRiskTensor`, `getBondAnalyticsKrdCurveRisk`, `getBondAnalyticsCreditSpreadMigration` | `/api/risk/tensor/dates`, `/api/risk/tensor`, `/api/bond-analytics/krd-curve-risk`, `/api/bond-analytics/credit-spread-migration` |
| `/risk-tensor` | `features/risk-tensor/RiskTensorPage.tsx` | `getRiskTensorDates`, `getRiskTensor` | `/api/risk/tensor/dates`, `/api/risk/tensor` |
| `/concentration-monitor` | `features/concentration-monitor/ConcentrationMonitorPage.tsx` | `getBondAnalyticsDates`, `getBondAnalyticsCreditSpreadMigration` | `/api/bond-analytics/dates`, `/api/bond-analytics/credit-spread-migration` |
| `/cashflow-projection` | `features/cashflow-projection/pages/CashflowProjectionPage.tsx` | `getBalanceAnalysisDates`, `getCashflowProjection` | `/ui/balance-analysis/dates`, `/api/cashflow-projection` |

### Performance And Governance

| Frontend path | Page/component | ApiClient methods | Backend endpoints |
|---|---|---|---|
| `/kpi` | `features/kpi-performance/pages/KpiPerformancePage.tsx` plus KPI modals | owners, metrics, values, summary, create/update/delete metric/value, batch update, fetch/recalc, report CSV | `/api/kpi/*` |
| `/team-performance` | `features/team-performance/TeamPerformancePage.tsx` | `getProductCategoryDates`, `getProductCategoryPnl` | `/ui/pnl/product-category*` |
| `/platform-config` | `features/platform-config/PlatformConfigPage.tsx` | `getHealth`, `getHealthLive`, `getHealthSummary`, `getSourceFoundation` | `/health/ready`, `/health/live`, `/health`, `/ui/preview/source-foundation` |
| `/cube-query` | `features/cube-query/pages/CubeQueryPage.tsx` | `getCubeDimensions`, `executeCubeQuery` | `/api/cube/dimensions/{fact_table}`, `/api/cube/query` |
| `/source-preview` | `features/source-preview/pages/SourcePreviewPage.tsx` | source foundation list/history/rows/traces, refresh/status | `/ui/preview/source-foundation*` |
| `/agent` | `features/agent/AgentWorkbenchPage.tsx` | direct `fetch("/api/agent/query")` | `/api/agent/query` |

## Backend Route Files

Backend API route aggregation:

- `backend/app/api/__init__.py` imports and includes all route modules.
- Frontend dev proxy forwards `/ui`, `/api`, and `/health` to the FastAPI backend.

Important route prefixes:

| Backend file | Prefix / endpoint family |
|---|---|
| `backend/app/api/routes/executive.py` | `/ui/home/*`, `/ui/pnl/attribution`, `/ui/risk/overview` |
| `backend/app/api/routes/balance_analysis.py` | `/ui/balance-analysis/*` |
| `backend/app/api/routes/accounting_asset_movement.py` | `/ui/balance-movement-analysis/*` |
| `backend/app/api/routes/positions.py` | `/api/positions/*` |
| `backend/app/api/routes/ledger.py` | `/api/ledger/*` |
| `backend/app/api/routes/ledger_pnl.py` | `/api/ledger-pnl/*` |
| `backend/app/api/routes/pnl.py` | `/api/pnl/*`, `/api/data/refresh_pnl`, `/api/data/import_status/pnl` |
| `backend/app/api/routes/pnl_attribution.py` | `/api/pnl-attribution/*` |
| `backend/app/api/routes/campisi_attribution.py` | `/api/pnl-attribution/campisi/*` |
| `backend/app/api/routes/product_category_pnl.py` | `/ui/pnl/product-category/*` |
| `backend/app/api/routes/qdb_gl_monthly_analysis.py` | `/ui/qdb-gl-monthly-analysis/*` |
| `backend/app/api/routes/bond_dashboard.py` | `/api/bond-dashboard/*` |
| `backend/app/api/routes/bond_analytics.py` | `/api/bond-analytics/*` |
| `backend/app/api/routes/credit_spread_analysis.py` | `/api/credit-spread-analysis/detail` |
| `backend/app/api/routes/risk_tensor.py` | `/api/risk/tensor*` |
| `backend/app/api/routes/cashflow_projection.py` | `/api/cashflow-projection` |
| `backend/app/api/routes/macro_vendor.py` | `/ui/preview/macro-foundation`, `/ui/macro/choice-series/*`, `/ui/market-data/fx/*` |
| `backend/app/api/routes/macro_bond_linkage.py` | `/api/macro-bond-linkage/analysis` |
| `backend/app/api/routes/market_data_livermore.py` | `/ui/market-data/livermore` |
| `backend/app/api/routes/market_data_ncd_proxy.py` | `/ui/market-data/ncd-funding-proxy` |
| `backend/app/api/routes/choice_news.py` | `/ui/news/choice-events/latest`, `/api/news/tushare-npr/ingest` |
| `backend/app/api/routes/research_calendar.py` | `/ui/calendar/supply-auctions` |
| `backend/app/api/routes/source_preview.py` | `/ui/preview/source-foundation*` |
| `backend/app/api/routes/liability_analytics.py` | `/api/risk/buckets`, `/api/analysis/yield_metrics`, `/api/analysis/liabilities/counterparty`, `/api/liabilities/monthly`, `/ui/liability/business-context` |
| `backend/app/api/routes/kpi.py` | `/api/kpi/*` |
| `backend/app/api/routes/cube_query.py` | `/api/cube/*` |
| `backend/app/api/routes/agent.py` | `/api/agent/query` |
| `backend/app/api/routes/health.py` | `/health`, `/health/live`, `/health/ready` |

## Page Design Rules For Future Work

- Every page should open with the business conclusion or operating question, not a generic title-only banner.
- Keep filters close to the data they affect.
- Preserve current source metadata and fallback/stale disclosure.
- Prefer table and chart pairings that explain the same conclusion from two angles.
- Do not hide failed loads behind empty panels.
- Do not present mock or fallback values as formal facts.
- Do not duplicate official calculations in React components; use backend payloads/adapters/selectors.
- Use `ApiEnvelope.result_meta` where available to show basis, quality, source, vendor/cache/rule version, fallback mode, and stale status.
- For business metric pages, design around this trace path:

```text
API response -> adapter/transformer -> store/state -> selector/computed -> component -> chart/table
```

## Files GPT-5.5 Pro Should Read First

1. `DESIGN.md`
2. `frontend/src/theme/designSystem.ts`
3. `frontend/src/theme/tokens.ts`
4. `frontend/src/theme/displayTokens.ts`
5. `frontend/src/theme/theme.ts`
6. `frontend/src/styles/global.css`
7. `frontend/src/layouts/WorkbenchShell.tsx`
8. `frontend/src/mocks/navigation.ts`
9. `frontend/src/router/routes.tsx`
10. `frontend/src/components/page/PagePrimitives.tsx`
11. `frontend/src/components/DataSection.tsx`
12. `frontend/src/components/KpiCard.tsx`
13. The target page under `frontend/src/features/<domain>/`
14. The matching API client method in `frontend/src/api/`
15. The matching backend route file in `backend/app/api/routes/`

## Known Design Debt / Caution Areas

- Some pages still use large inline style blocks. New repeated layout should move toward page primitives, tokens, or page-local style modules.
- `frontend/src/api/client.ts` is already large. New endpoint implementations should go into the relevant domain client module.
- Several pages own their own chrome. A redesign should decide whether to normalize page shells or preserve page-owned dense layouts.
- Some routes are marked `temporary-exception` in navigation metadata even though they are visible; do not interpret that as full governance completion.
- Product-category PnL has project memory constraints: treat user-provided page structure and borrowed ledger/daily-average rule material as source of truth. Do not infer product rows from unrelated ZQTZ or holdings-side categories.

## Validation Expectations For Design Implementation

Before claiming a frontend design implementation is complete:

- Run targeted component/model/adapter tests for touched page paths.
- Run `npm run typecheck` and the narrowest relevant Vitest suite.
- If touching pages, API clients, mocks, adapters, formatters, or selectors, run `npm run debt:audit` from `frontend/`.
- For visible frontend changes, run browser-level verification and capture desktop/mobile screenshots.
- Confirm no text overlap, no table overflow regressions, and no loss of no-data/stale/fallback/error states.
