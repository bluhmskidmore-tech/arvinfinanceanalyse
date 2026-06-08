export type LiveRouteReadinessContract = {
  sourceFiles: readonly string[];
  sourceAnchors: readonly string[];
  verificationFiles: readonly string[];
};

export const liveRouteReadinessContracts = {
  "/": {
    sourceFiles: [
      "src/features/workbench/dashboard-home/DashboardHomePage.tsx",
      "src/features/workbench/dashboard-home/TerminalHomeFirstScreen.tsx",
    ],
    sourceAnchors: ["dashboard-home-page", "dashboard-home-hero"],
    verificationFiles: [
      "src/test/DashboardHomePage.test.tsx",
      "src/test/DeferredTerminalHomeContent.test.tsx",
    ],
  },
  "/operations-analysis": {
    sourceFiles: ["src/features/workbench/pages/OperationsAnalysisPage.tsx"],
    sourceAnchors: ["operations-layout-preview", "operations-hero-provenance"],
    verificationFiles: [
      "src/test/OperationsAnalysisPage.test.tsx",
      "src/test/OperationsAnalysisPage.governed.test.tsx",
    ],
  },
  "/portfolio": {
    sourceFiles: [
      "src/features/workbench/module-home/PortfolioHomePage.tsx",
      "src/features/workbench/module-home/PortfolioHomeLayout.tsx",
    ],
    sourceAnchors: ["module-workbench-home", "module-home-kpi-strip"],
    verificationFiles: ["src/test/ModuleWorkbenchHomePage.test.tsx"],
  },
  "/bond-analysis": {
    sourceFiles: ["src/features/bond-analytics/components/BondAnalyticsViewContent.tsx"],
    sourceAnchors: ["bond-analysis-overview", "bond-analysis-toolbar"],
    verificationFiles: [
      "src/test/BondAnalyticsView.test.tsx",
      "src/test/BondAnalyticsViewContent.test.tsx",
    ],
  },
  "/cross-asset": {
    sourceFiles: ["src/features/cross-asset/pages/CrossAssetDriversPage.tsx"],
    sourceAnchors: ["cross-asset-drivers-page", "cross-asset-research-views"],
    verificationFiles: [
      "src/test/CrossAssetDriversRoute.test.tsx",
      "src/test/CrossAssetPage.test.tsx",
    ],
  },
  "/team-performance": {
    sourceFiles: ["src/features/team-performance/TeamPerformancePage.tsx"],
    sourceAnchors: ["team-performance-page", "team-performance-summary-cards"],
    verificationFiles: ["src/test/TeamPerformancePage.test.tsx"],
  },
  "/decision-items": {
    sourceFiles: ["src/features/decision-items/pages/DecisionItemsPage.tsx"],
    sourceAnchors: ["decision-items-page", "decision-items-list"],
    verificationFiles: [
      "src/test/DecisionItemsPage.test.tsx",
      "src/test/DecisionItemsRoute.test.tsx",
    ],
  },
  "/balance-analysis": {
    sourceFiles: ["src/features/balance-analysis/pages/BalanceAnalysisPage.tsx"],
    sourceAnchors: ["balance-analysis-page", "balance-analysis-table"],
    verificationFiles: ["src/test/BalanceAnalysisPage.test.tsx"],
  },
  "/balance-movement-analysis": {
    sourceFiles: [
      "src/features/balance-movement-analysis/pages/BalanceMovementAnalysisPage.tsx",
    ],
    sourceAnchors: ["balance-movement-analysis-page", "balance-movement-analysis-conclusion"],
    verificationFiles: ["src/test/BalanceMovementAnalysisPage.test.tsx"],
  },
  "/liability-analytics": {
    sourceFiles: ["src/features/liability-analytics/pages/LiabilityAnalyticsPage.tsx"],
    sourceAnchors: ["liability-analytics-page", "liability-conclusion"],
    verificationFiles: ["src/test/LiabilityAnalyticsPage.test.tsx"],
  },
  "/market-overview": {
    sourceFiles: [
      "src/features/workbench/module-home/MarketHomePage.tsx",
      "src/features/workbench/module-home/MarketHomeLayout.tsx",
    ],
    sourceAnchors: ["module-workbench-home", "module-home-kpi-strip"],
    verificationFiles: ["src/test/ModuleWorkbenchHomePage.test.tsx"],
  },
  "/market-data": {
    sourceFiles: ["src/features/market-data/pages/MarketDataPage.tsx"],
    sourceAnchors: ["market-data-page", "market-data-readiness-verdict"],
    verificationFiles: ["src/test/MarketDataPage.test.tsx"],
  },
  "/macro-observation": {
    sourceFiles: ["src/features/macro-toolkit/pages/MacroToolkitPage.tsx"],
    sourceAnchors: ["macro-observation-readonly-boundary", "macro-toolkit-page"],
    verificationFiles: ["src/test/MacroToolkitPage.test.tsx"],
  },
  "/macro-toolkit": {
    sourceFiles: ["src/features/macro-toolkit/pages/MacroToolkitPage.tsx"],
    sourceAnchors: ["macro-toolkit-page", "macro-toolkit-tailwind-cockpit"],
    verificationFiles: ["src/test/MacroToolkitPage.test.tsx"],
  },
  "/stock-analysis": {
    sourceFiles: ["src/features/stock-analysis/pages/StockAnalysisPage.tsx"],
    sourceAnchors: ["stock-analysis-toolbar", "stock-analysis-first-screen-main"],
    verificationFiles: ["src/test/StockAnalysisPage.test.tsx"],
  },
  "/platform-config": {
    sourceFiles: ["src/features/platform-config/PlatformConfigPage.tsx"],
    sourceAnchors: ["platform-config-page-title", "platform-config-sources-table"],
    verificationFiles: ["src/test/PlatformConfigPage.test.tsx"],
  },
  "/reports": {
    sourceFiles: ["src/features/workbench/module-home/ModuleWorkbenchHomePage.tsx"],
    sourceAnchors: ["module-workbench-home", "module-home-data-note"],
    verificationFiles: ["src/test/ModuleWorkbenchHomePage.test.tsx"],
  },
  "/bond-dashboard": {
    sourceFiles: ["src/features/bond-dashboard/pages/BondDashboardPage.tsx"],
    sourceAnchors: ["bond-dashboard-page", "bond-dashboard-conclusion"],
    verificationFiles: ["src/test/BondDashboardPage.test.tsx"],
  },
  "/positions": {
    sourceFiles: ["src/features/positions/components/PositionsView.tsx"],
    sourceAnchors: ["positions-page", "positions-list-candidate-boundary"],
    verificationFiles: ["src/test/PositionsView.test.tsx"],
  },
  "/average-balance": {
    sourceFiles: ["src/features/average-balance/components/AverageBalanceView.tsx"],
    sourceAnchors: ["average-balance-page", "average-balance-page-title"],
    verificationFiles: [
      "src/test/AverageBalancePage.test.tsx",
      "src/test/AverageBalanceView.test.tsx",
    ],
  },
  "/ledger-pnl": {
    sourceFiles: ["src/features/ledger-pnl/pages/LedgerPnlPage.tsx"],
    sourceAnchors: ["ledger-pnl-page", "ledger-pnl-summary-cards"],
    verificationFiles: [
      "src/test/LedgerPnlPage.test.tsx",
      "src/test/LedgerPnlRoutesSmoke.test.tsx",
    ],
  },
  "/bank-ledger-dashboard": {
    sourceFiles: ["src/features/ledger-dashboard/pages/LedgerDashboardPage.tsx"],
    sourceAnchors: ["ledger-dashboard-page", "ledger-dashboard-kpis"],
    verificationFiles: ["src/test/LedgerDashboardPage.test.tsx"],
  },
  "/risk-overview": {
    sourceFiles: ["src/features/workbench/module-home/ModuleWorkbenchHomePage.tsx"],
    sourceAnchors: ["module-workbench-home", "module-home-risk-evidence"],
    verificationFiles: ["src/test/ModuleWorkbenchHomePage.test.tsx"],
  },
  "/risk-tensor": {
    sourceFiles: ["src/features/risk-tensor/RiskTensorPage.tsx"],
    sourceAnchors: ["risk-tensor-brief", "risk-tensor-kpi-grid"],
    verificationFiles: ["src/test/RiskTensorPage.test.tsx"],
  },
  "/concentration-monitor": {
    sourceFiles: ["src/features/concentration-monitor/ConcentrationMonitorPage.tsx"],
    sourceAnchors: ["concentration-monitor-contract-status", "concentration-monitor-kpi-grid"],
    verificationFiles: ["src/test/ConcentrationMonitorPage.test.tsx"],
  },
  "/cashflow-projection": {
    sourceFiles: ["src/features/cashflow-projection/pages/CashflowProjectionPage.tsx"],
    sourceAnchors: ["cashflow-projection-page", "cashflow-conclusion"],
    verificationFiles: ["src/test/CashflowProjectionPage.test.tsx"],
  },
  "/performance": {
    sourceFiles: ["src/features/workbench/module-home/ModuleWorkbenchHomePage.tsx"],
    sourceAnchors: ["module-workbench-home", "module-home-kpi-strip"],
    verificationFiles: ["src/test/ModuleWorkbenchHomePage.test.tsx"],
  },
  "/kpi": {
    sourceFiles: ["src/features/kpi-performance/pages/KpiPerformancePage.tsx"],
    sourceAnchors: ["kpi-performance-page", "kpi-performance-main-grid"],
    verificationFiles: ["src/test/KpiPerformancePage.test.tsx"],
  },
  "/news-events": {
    sourceFiles: ["src/features/news-events/NewsEventsPage.tsx"],
    sourceAnchors: ["news-events-page-title", "news-events-table"],
    verificationFiles: ["src/test/NewsEventsPage.test.tsx"],
  },
  "/product-category-pnl": {
    sourceFiles: ["src/features/product-category-pnl/pages/ProductCategoryPnlPage.tsx"],
    sourceAnchors: ["product-category-page", "product-category-table"],
    verificationFiles: ["src/test/ProductCategoryPnlPage.test.tsx"],
  },
  "/pnl": {
    sourceFiles: ["src/features/pnl/YieldAnalysisPage.tsx"],
    sourceAnchors: ["yield-analysis-page", "yield-analysis-pnl-readout"],
    verificationFiles: ["src/test/PnlPage.test.tsx", "src/test/PnlRoutesSmoke.test.tsx"],
  },
  "/pnl-bridge": {
    sourceFiles: ["src/features/pnl/PnlBridgePage.tsx"],
    sourceAnchors: ["pnl-bridge-page", "pnl-bridge-detail-table"],
    verificationFiles: [
      "src/test/PnlBridgePage.test.tsx",
      "src/test/PnlRoutesSmoke.test.tsx",
    ],
  },
  "/pnl-attribution": {
    sourceFiles: [
      "src/features/pnl-attribution/pages/PnlAttributionPage.tsx",
      "src/features/pnl-attribution/components/PnlAttributionView.tsx",
    ],
    sourceAnchors: ["pnl-attribution-page-title", "pnl-attribution-tab-product-category"],
    verificationFiles: ["src/test/PnlAttributionPage.test.tsx"],
  },
  "/cube-query": {
    sourceFiles: ["src/features/cube-query/pages/CubeQueryPage.tsx"],
    sourceAnchors: ["cube-query-page", "cube-dimensions"],
    verificationFiles: ["src/test/CubeQueryPage.test.tsx"],
  },
  "/pnl-by-business": {
    sourceFiles: ["src/features/pnl/PnlByBusinessPage.tsx"],
    sourceAnchors: ["pnl-by-business-page", "pnl-by-business-state-surfaces"],
    verificationFiles: ["src/test/PnlRoutesSmoke.test.tsx"],
  },
  "/agent": {
    sourceFiles: ["src/features/agent/AgentWorkbenchPage.tsx"],
    sourceAnchors: ["agent-workbench-shell", "agent-conversation-bottom"],
    verificationFiles: [
      "src/test/AgentPlaceholderPage.test.tsx",
      "src/test/AgentWorkbenchPage.test.tsx",
    ],
  },
} satisfies Record<string, LiveRouteReadinessContract>;
