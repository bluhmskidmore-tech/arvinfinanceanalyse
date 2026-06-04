const routeModulePreloaders = {
  "themed-route-boundary": () => import("../app/ThemedRouteBoundary"),
  agent: () => import("../features/agent/AgentWorkbenchPage"),
  "balance-movement-analysis": () =>
    import("../features/balance-movement-analysis/pages/BalanceMovementAnalysisPage"),
  "bank-ledger-dashboard": () =>
    import("../features/ledger-dashboard/pages/LedgerDashboardPage"),
  "dashboard-home": () => import("../features/workbench/dashboard-home/DashboardHomePage"),
  "decision-items": () => import("../features/decision-items/pages/DecisionItemsPage"),
  kpi: () => import("../features/kpi-performance/pages/KpiPerformancePage"),
  "ledger-pnl": () => import("../features/ledger-pnl/pages/LedgerPnlPage"),
  "macro-toolkit": () => import("../features/macro-toolkit/pages/MacroToolkitPage"),
  "market-overview": () => import("../features/workbench/module-home/MarketHomePage"),
  "module-home": () => import("../features/workbench/module-home/ModuleWorkbenchHomePage"),
  "news-events": () => import("../features/news-events/NewsEventsPage"),
  pnl: () => import("../features/pnl/PnlPage"),
  "pnl-bridge": () => import("../features/pnl/PnlBridgePage"),
  "pnl-by-business": () => import("../features/pnl/PnlByBusinessPage"),
  "product-category-pnl": () =>
    import("../features/product-category-pnl/pages/ProductCategoryPnlPage"),
  "product-category-pnl-audit": () =>
    import("../features/product-category-pnl/pages/ProductCategoryAdjustmentAuditPage"),
  "risk-tensor": () => import("../features/risk-tensor/RiskTensorPage"),
} as const;

type RoutePreloadKey = keyof typeof routeModulePreloaders;

export type WorkbenchRouteModule = Exclude<RoutePreloadKey, "themed-route-boundary">;

export async function preloadWorkbenchRouteModules(
  ...modules: WorkbenchRouteModule[]
): Promise<void> {
  const preloadKeys: RoutePreloadKey[] = ["themed-route-boundary", ...modules];
  await Promise.all([...new Set(preloadKeys)].map((key) => routeModulePreloaders[key]()));
}
