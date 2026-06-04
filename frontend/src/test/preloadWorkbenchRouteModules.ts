const routeModulePreloaders = {
  "themed-route-boundary": () => import("../app/ThemedRouteBoundary"),
  agent: () => import("../features/agent/AgentWorkbenchPage"),
  "balance-movement-analysis": () =>
    import("../features/balance-movement-analysis/pages/BalanceMovementAnalysisPage"),
  "bank-ledger-dashboard": () =>
    import("../features/ledger-dashboard/pages/LedgerDashboardPage"),
  "balance-analysis": () => import("../features/balance-analysis/pages/BalanceAnalysisPage"),
  "bond-analysis": () => import("../features/bond-analytics/components/BondAnalyticsView"),
  "bond-dashboard": () => import("../features/bond-dashboard/pages/BondDashboardPage"),
  "cashflow-projection": () =>
    import("../features/cashflow-projection/pages/CashflowProjectionPage"),
  "concentration-monitor": () =>
    import("../features/concentration-monitor/ConcentrationMonitorPage"),
  "cross-asset": () => import("../features/cross-asset/pages/CrossAssetPage"),
  "dashboard-home": () => import("../features/workbench/dashboard-home/DashboardHomePage"),
  "decision-items": () => import("../features/decision-items/pages/DecisionItemsPage"),
  "formal-pnl-v1": () => import("../features/pnl/FormalPnlV1Page"),
  kpi: () => import("../features/kpi-performance/pages/KpiPerformancePage"),
  "ledger-pnl": () => import("../features/ledger-pnl/pages/LedgerPnlPage"),
  "liability-analytics": () =>
    import("../features/liability-analytics/pages/LiabilityAnalyticsPage"),
  "macro-toolkit": () => import("../features/macro-toolkit/pages/MacroToolkitPage"),
  "market-data": () => import("../features/market-data/pages/MarketDataPage"),
  "news-events": () => import("../features/news-events/NewsEventsPage"),
  pnl: () => import("../features/pnl/PnlPage"),
  "pnl-attribution": () => import("../features/pnl-attribution/pages/PnlAttributionPage"),
  "pnl-bridge": () => import("../features/pnl/PnlBridgePage"),
  "pnl-by-business": () => import("../features/pnl/PnlByBusinessPage"),
  positions: () => import("../features/positions/pages/PositionsPage"),
  "product-category-pnl": () =>
    import("../features/product-category-pnl/pages/ProductCategoryPnlPage"),
  "product-category-pnl-audit": () =>
    import("../features/product-category-pnl/pages/ProductCategoryAdjustmentAuditPage"),
  "risk-tensor": () => import("../features/risk-tensor/RiskTensorPage"),
  "stock-analysis": () => import("../features/stock-analysis/pages/StockAnalysisPage"),
  "team-performance": () => import("../features/team-performance/TeamPerformancePage"),
  "platform-config": () => import("../features/platform-config/PlatformConfigPage"),
  "cube-query": () => import("../features/cube-query/pages/CubeQueryPage"),
} as const;

type RoutePreloadKey = keyof typeof routeModulePreloaders;

export type WorkbenchRouteModule = Exclude<RoutePreloadKey, "themed-route-boundary">;

export async function preloadWorkbenchRouteModules(
  ...modules: WorkbenchRouteModule[]
): Promise<void> {
  const preloadKeys: RoutePreloadKey[] = ["themed-route-boundary", ...modules];
  await Promise.all([...new Set(preloadKeys)].map((key) => routeModulePreloaders[key]()));
}
