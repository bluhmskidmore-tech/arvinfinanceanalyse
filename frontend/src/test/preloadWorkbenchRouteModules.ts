const routeModulePreloaders = {
  "themed-route-boundary": () => import("../app/ThemedRouteBoundary"),
  agent: () => import("../features/agent/AgentWorkbenchPage"),
  "average-balance": () => import("../features/average-balance/pages/AverageBalancePage"),
  "balance-movement-analysis": () =>
    import("../features/balance-movement-analysis/pages/BalanceMovementAnalysisPage"),
  "bank-ledger-dashboard": () =>
    import("../features/ledger-dashboard/pages/LedgerDashboardPage"),
  "bond-analysis": () => import("../features/bond-analytics/components/BondAnalyticsView"),
  "bond-trading-desk": () => import("../features/bond-trading-desk/pages/BondTradingDeskPage"),
  "bond-dashboard": () => import("../features/bond-dashboard/pages/BondDashboardPage"),
  "cashflow-projection": () =>
    import("../features/cashflow-projection/pages/CashflowProjectionPage"),
  "concentration-monitor": () =>
    import("../features/concentration-monitor/ConcentrationMonitorPage"),
  "dashboard-home": () => import("../features/workbench/dashboard-home/DashboardHomePage"),
  "decision-items": () => import("../features/decision-items/pages/DecisionItemsPage"),
  kpi: () => import("../features/kpi-performance/pages/KpiPerformancePage"),
  "ledger-pnl": () => import("../features/ledger-pnl/pages/LedgerPnlPage"),
  "liability-analytics": () =>
    import("../features/liability-analytics/pages/LiabilityAnalyticsPage"),
  "macro-toolkit": () => import("../features/macro-toolkit/pages/MacroToolkitPage"),
  "market-overview": () => import("../features/workbench/module-home/MarketHomePage"),
  "module-home": () => import("../features/workbench/module-home/ModuleWorkbenchHomePage"),
  "news-events": () => import("../features/news-events/NewsEventsPage"),
  "operations-analysis": () => import("../features/workbench/pages/OperationsAnalysisPage"),
  "platform-config": () => import("../features/platform-config/PlatformConfigPage"),
  pnl: () => import("../features/pnl/PnlPage"),
  "pnl-attribution": () => import("../features/pnl-attribution/pages/PnlAttributionPage"),
  "pnl-bridge": () => import("../features/pnl/PnlBridgePage"),
  "pnl-by-business": () => import("../features/pnl/PnlByBusinessPage"),
  "product-category-pnl": () =>
    import("../features/product-category-pnl/pages/ProductCategoryPnlPage"),
  "product-category-pnl-audit": () =>
    import("../features/product-category-pnl/pages/ProductCategoryAdjustmentAuditPage"),
  "risk-tensor": () => import("../features/risk-tensor/RiskTensorPage"),
  "risk-overview": () => import("../features/workbench/module-home/RiskOverviewPage"),
  "team-performance": () => import("../features/team-performance/TeamPerformancePage"),
} as const;

type RoutePreloadKey = keyof typeof routeModulePreloaders;

export type WorkbenchRouteModule = Exclude<RoutePreloadKey, "themed-route-boundary">;

export async function preloadWorkbenchRouteModules(
  ...modules: WorkbenchRouteModule[]
): Promise<void> {
  const preloadKeys: RoutePreloadKey[] = ["themed-route-boundary", ...modules];
  await Promise.all([...new Set(preloadKeys)].map((key) => routeModulePreloaders[key]()));
}
