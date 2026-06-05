import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

const FRONTEND_ROOT = process.cwd();
const INDEX_HTML_PATH = resolve(FRONTEND_ROOT, "index.html");
const PACKAGE_JSON_PATH = resolve(FRONTEND_ROOT, "package.json");
const HOME_STARTUP_BUNDLE_GUARD_PATH = resolve(
  FRONTEND_ROOT,
  "scripts/verifyHomeStartupBundle.mjs",
);
const VITE_CONFIG_PATH = resolve(FRONTEND_ROOT, "vite.config.ts");
const CLIENT_CONTEXT_PATH = resolve(FRONTEND_ROOT, "src/api/clientContext.ts");
const HOME_MARKET_TICKER_CLIENT_PATH = resolve(
  FRONTEND_ROOT,
  "src/api/homeMarketTickerClient.ts",
);
const DASHBOARD_HOME_PAGE_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/workbench/dashboard-home/DashboardHomePage.tsx",
);
const TERMINAL_HOME_CONTENT_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/workbench/dashboard-home/TerminalHomeContent.tsx",
);
const TERMINAL_HOME_WORK_GRID_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/workbench/dashboard-home/TerminalHomeWorkGrid.tsx",
);
const TERMINAL_HOME_DEFERRED_SECTIONS_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/workbench/dashboard-home/TerminalHomeDeferredSections.tsx",
);
const DEFERRED_TERMINAL_HOME_CONTENT_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/workbench/dashboard-home/DeferredTerminalHomeContent.tsx",
);
const DEFERRED_TERMINAL_HOME_BODY_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/workbench/dashboard-home/DeferredTerminalHomeBody.tsx",
);
const HOME_SUPPLEMENTAL_HYDRATION_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/workbench/dashboard-home/useDashboardHomeSupplementalHydration.ts",
);
const HOME_VIEW_MODEL_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/workbench/dashboard-home/useDashboardHomeViewModel.ts",
);
const HOME_BODY_DATA_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/workbench/dashboard-home/useDashboardHomeBodyData.ts",
);
const DASHBOARD_HOME_VIEW_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/workbench/dashboard-home/dashboardHomeView.ts",
);
const DASHBOARD_HOME_BODY_VIEW_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/workbench/dashboard-home/dashboardHomeBodyView.ts",
);
const DASHBOARD_SNAPSHOT_BOUNDARY_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/workbench/pages/useDashboardSnapshotBoundary.ts",
);
const ROUTES_PATH = resolve(FRONTEND_ROOT, "src/router/routes.tsx");

describe("startup performance guards", () => {
  it("does not block first paint on remote font hosts", () => {
    const indexHtml = readFileSync(INDEX_HTML_PATH, "utf8");

    expect(indexHtml).not.toContain("fonts.googleapis.com");
    expect(indexHtml).not.toContain("fonts.gstatic.com");
  });

  it("keeps home startup methods on deferred fast paths", () => {
    const clientContextSource = readFileSync(CLIENT_CONTEXT_PATH, "utf8");

    expect(clientContextSource).toContain('import("./homeExecutiveClient")');
    expect(clientContextSource).toContain('import("./homeSupplementalClient")');
    expect(clientContextSource).toContain('import("./homeMarketTickerClient")');
    expect(clientContextSource).toContain("HOME_EXECUTIVE_METHODS");
    expect(clientContextSource).toContain("HOME_SUPPLEMENTAL_METHODS");
    expect(clientContextSource).toContain("HOME_MARKET_TICKER_METHODS");
    expect(clientContextSource).not.toContain('import("./marketDataClient")');
    for (const method of [
      "getHomeSnapshot",
      "getHomeResearchReports",
      "getHomeIncomeTrend",
      "getMarketDataRates",
      "getChoiceNewsEvents",
      "getResearchCalendarEvents",
      "getCoreMetrics",
      "getDailyChanges",
      "getBondDashboardHeadlineKpis",
      "getBondAnalyticsPortfolioHeadlines",
      "getBondDashboardPortfolioComparison",
      "getBondAnalyticsCreditSpreadMigration",
      "getBondAnalyticsReturnDecomposition",
      "getPnlCampisiFourEffects",
      "getBondAnalyticsYieldCurveTermStructure",
      "getBalanceAnalysisDecisionItems",
      "getBondDashboardAssetStructure",
      "getBondDashboardMaturityStructure",
      "getBondDashboardIndustryDistribution",
      "getBondDashboardRiskIndicators",
      "getBondAnalyticsTopHoldings",
      "getBondAnalyticsPositionChanges",
      "getCockpitWarnings",
    ]) {
      expect(clientContextSource).toContain(`"${method}"`);
    }
  });

  it("keeps home market ticker methods in a lightweight client", () => {
    const homeMarketTickerSource = readFileSync(HOME_MARKET_TICKER_CLIENT_PATH, "utf8");

    expect(homeMarketTickerSource).toContain("HomeMarketTickerClientMethods");
    expect(homeMarketTickerSource).toContain("createRealHomeMarketTickerClient");
    expect(homeMarketTickerSource).toContain("createMockHomeMarketTickerClient");
    for (const method of [
      "getChoiceMacroLatest",
      "getMarketDataRates",
      "getChoiceNewsEvents",
      "getResearchCalendarEvents",
    ]) {
      expect(homeMarketTickerSource).toContain(method);
    }
    for (const heavyArtifact of [
      "Livermore",
      "SourcePreview",
      "MacroBondLinkage",
      "marketDataClient",
      "materializeLivermore",
      "refreshSourcePreview",
    ]) {
      expect(homeMarketTickerSource).not.toContain(heavyArtifact);
    }
  });

  it("does not statically import ECharts in the terminal home content", () => {
    const terminalHomeContentSource = readFileSync(TERMINAL_HOME_CONTENT_PATH, "utf8");

    expect(terminalHomeContentSource).not.toMatch(
      /from\s+["']\.\.\/\.\.\/\.\.\/lib\/echarts["']/,
    );
  });

  it("keeps the terminal home work grid behind a lazy body split", () => {
    const terminalHomeContentSource = readFileSync(TERMINAL_HOME_CONTENT_PATH, "utf8");

    expect(terminalHomeContentSource).toContain('import("./TerminalHomeWorkGrid")');
    expect(terminalHomeContentSource).not.toContain("function HoldingsPanel");
    expect(terminalHomeContentSource).not.toContain("function IncomeTrendPanel");
    expect(terminalHomeContentSource).not.toContain("function DistributionPanel");
    expect(terminalHomeContentSource).not.toContain("buildIncomeTrendOption");
  });

  it("keeps terminal home secondary sections behind a lazy split", () => {
    const terminalHomeContentSource = readFileSync(TERMINAL_HOME_CONTENT_PATH, "utf8");

    expect(terminalHomeContentSource).toContain('import("./TerminalHomeDeferredSections")');
    expect(terminalHomeContentSource).not.toMatch(
      /import\s+\{\s*BondNewsSection\s*\}\s+from\s+["']\.\/sections\/BondNewsSection["']/,
    );
    expect(terminalHomeContentSource).not.toMatch(
      /import\s+\{\s*ResearchCalendarSection\s*\}\s+from\s+["']\.\/sections\/ResearchCalendarSection["']/,
    );
    expect(terminalHomeContentSource).not.toContain("function QuickDrilldowns");
    expect(terminalHomeContentSource).not.toContain('data-testid="dashboard-home-bottom-grid"');
    expect(terminalHomeContentSource).not.toContain('data-testid="dashboard-home-research-calendar"');
  });

  it("keeps deferred terminal home secondary sections off chart and work-grid code", () => {
    const deferredSectionsSource = readFileSync(TERMINAL_HOME_DEFERRED_SECTIONS_PATH, "utf8");

    expect(deferredSectionsSource).toContain("BondNewsSection");
    expect(deferredSectionsSource).toContain("ResearchCalendarSection");
    expect(deferredSectionsSource).toContain("QuickDrilldowns");
    expect(deferredSectionsSource).not.toContain("TerminalHomeWorkGrid");
    expect(deferredSectionsSource).not.toContain("../../../lib/echarts");
    expect(deferredSectionsSource).not.toContain("buildIncomeTrendOption");
  });

  it("keeps the lazy terminal home work grid scoped to below-fold panels", () => {
    const workGridSource = readFileSync(TERMINAL_HOME_WORK_GRID_PATH, "utf8");

    expect(workGridSource).toContain('data-testid="dashboard-home-work-grid"');
    for (const firstScreenOrShellArtifact of [
      "showFirstScreen",
      "TerminalKpiStrip",
      "RiskStrip",
      "BondNewsSection",
      "ResearchCalendarSection",
      "MarketContextPanel",
      "QuickDrilldowns",
      "dashboard-home-market-context",
      "dashboard-home-bottom-grid",
      "dashboard-home-research-calendar",
    ]) {
      expect(workGridSource).not.toContain(firstScreenOrShellArtifact);
    }
  });

  it("keeps below-fold terminal home content out of the first-screen module", () => {
    const dashboardHomePageSource = readFileSync(DASHBOARD_HOME_PAGE_PATH, "utf8");

    expect(dashboardHomePageSource).toContain('import { TerminalHomeFirstScreen } from "./TerminalHomeFirstScreen"');
    expect(dashboardHomePageSource).toContain('from "./useDashboardHomeFirstScreenViewModel"');
    expect(dashboardHomePageSource).toContain('lazy(() =>');
    expect(dashboardHomePageSource).toContain('import("./DeferredTerminalHomeContent")');
    expect(dashboardHomePageSource).not.toContain('from "./useDashboardHomeViewModel"');
    expect(dashboardHomePageSource).not.toContain('from "./dashboardHomeView"');
    expect(dashboardHomePageSource).not.toMatch(
      /import\s+\{\s*TerminalHomeContent\s*\}\s+from\s+["']\.\/TerminalHomeContent["']/,
    );
  });

  it("keeps below-fold terminal home rendering out of the supplemental data loader", () => {
    const deferredTerminalSource = readFileSync(DEFERRED_TERMINAL_HOME_CONTENT_PATH, "utf8");

    expect(deferredTerminalSource).toMatch(
      /lazy\s*\(\s*\(\)\s*=>\s*import\(["']\.\/DeferredTerminalHomeBody["']\)/,
    );
    expect(deferredTerminalSource).not.toMatch(
      /import\s+\{\s*TerminalHomeContent\s*\}\s+from\s+["']\.\/TerminalHomeContent["']/,
    );
    expect(deferredTerminalSource).not.toContain("useDashboardHomeViewModel");
    expect(deferredTerminalSource).not.toContain("dashboardHomeView");
  });

  it("keeps first-screen supplemental hydration off below-fold home queries", () => {
    const hydrationSource = readFileSync(HOME_SUPPLEMENTAL_HYDRATION_PATH, "utf8");

    expect(hydrationSource).not.toContain("useDashboardData");
    expect(hydrationSource).toContain("getBondDashboardHeadlineKpis");
    expect(hydrationSource).toContain("getBondAnalyticsPortfolioHeadlines");
    for (const belowFoldMethod of [
      "getMarketDataRates",
      "getCoreMetrics",
      "getDailyChanges",
      "getBondDashboardAssetStructure",
      "getBondAnalyticsTopHoldings",
      "getBondAnalyticsPositionChanges",
      "getHomeResearchReports",
      "getHomeIncomeTrend",
      "getCockpitWarnings",
      "getChoiceNewsEvents",
      "getResearchCalendarEvents",
    ]) {
      expect(hydrationSource).not.toContain(belowFoldMethod);
    }
  });

  it("keeps the home body view model off the generic dashboard data hook", () => {
    const homeViewModelSource = readFileSync(HOME_VIEW_MODEL_PATH, "utf8");

    expect(homeViewModelSource).not.toContain("useDashboardData");
    expect(homeViewModelSource).toContain("useDashboardHomeBodyData");
  });

  it("keeps the home body data hook off retired dashboard-panel requests", () => {
    const bodyDataSource = readFileSync(HOME_BODY_DATA_PATH, "utf8");

    expect(bodyDataSource).toContain("loadEventFeeds");
    expect(bodyDataSource).toContain("enabled: loadEventFeeds");
    for (const retiredRequestArtifact of [
      "getDashboardOverview",
      "getDashboardDailyChanges",
      "getRiskControlOverview",
      "getExposureSummary",
      "balanceAnalysisDecisionItems",
      "bondDashboardPortfolioComparison",
      "getCockpitWarnings",
    ]) {
      expect(bodyDataSource).not.toContain(retiredRequestArtifact);
    }
  });

  it("keeps homepage event feeds behind a separate body idle gate", () => {
    const homeViewModelSource = readFileSync(HOME_VIEW_MODEL_PATH, "utf8");
    const bodyDataSource = readFileSync(HOME_BODY_DATA_PATH, "utf8");

    expect(homeViewModelSource).toContain("useEventFeedDataGate");
    expect(homeViewModelSource).toContain("useSecondaryEventFeedDataGate");
    expect(homeViewModelSource).toContain("loadEventFeeds");
    expect(homeViewModelSource).toContain("loadSecondaryEventFeeds");
    expect(homeViewModelSource).toContain("EVENT_FEED_IDLE_MIN_DELAY_MS");
    expect(homeViewModelSource).toContain("SECONDARY_EVENT_FEED_IDLE_MIN_DELAY_MS");
    expect(bodyDataSource).not.toMatch(/getChoiceNewsEvents[\s\S]{0,300}enabled:\s*loadDetailData/);
    expect(bodyDataSource).not.toMatch(/useDashboardResearchCalendarQuery[\s\S]{0,120}enabled:\s*loadDetailData/);
  });

  it("keeps the active home view model off retired homepage panel adapters", () => {
    const dashboardHomeViewSource = readFileSync(DASHBOARD_HOME_VIEW_PATH, "utf8");

    for (const retiredRuntimeArtifact of [
      "DASHBOARD_ATTRIBUTION_NOTE_MOCK",
      "DASHBOARD_ATTRIBUTION_WATERFALL_MOCK",
      "DASHBOARD_BALANCE_METRICS_MOCK",
      "DASHBOARD_EXPOSURE_ROWS_MOCK",
      "DASHBOARD_INTERBANK_MOCK",
      "DASHBOARD_PORTFOLIO_STATS_MOCK",
      "DASHBOARD_RISK_ALERT_COUNTS_MOCK",
      "DASHBOARD_RISK_TODOS_MOCK",
      "DASHBOARD_WATCHLIST_MOCK",
      "buildHomeAttributionTabs",
      "mapAssetStructureToHomeAssetBars",
      "mapCockpitWarningsToRiskCards",
      "mapCockpitWarningsToWatchlist",
      "mapHomeRiskRadar",
      "mapPortfolioComparisonToExposureRows",
    ]) {
      expect(dashboardHomeViewSource).not.toContain(retiredRuntimeArtifact);
    }
  });

  it("keeps the deferred home body off the legacy full home view model", () => {
    const bodyModelSource = readFileSync(DASHBOARD_HOME_BODY_VIEW_PATH, "utf8");
    const bodyPathSources = [
      readFileSync(HOME_VIEW_MODEL_PATH, "utf8"),
      readFileSync(DEFERRED_TERMINAL_HOME_BODY_PATH, "utf8"),
      readFileSync(TERMINAL_HOME_CONTENT_PATH, "utf8"),
      readFileSync(TERMINAL_HOME_WORK_GRID_PATH, "utf8"),
      readFileSync(TERMINAL_HOME_DEFERRED_SECTIONS_PATH, "utf8"),
    ];

    expect(bodyModelSource).toContain("mapToHomeBodyView");
    expect(bodyModelSource).not.toContain("DashboardOverviewMetricVM");
    expect(bodyModelSource).not.toContain("DashboardPnlAttributionVM");
    for (const bodyPathSource of bodyPathSources) {
      expect(bodyPathSource).not.toMatch(/from\s+["']\.\/dashboardHomeView["']/);
    }
  });

  it("keeps the dashboard snapshot boundary off the full API client runtime", () => {
    const snapshotBoundarySource = readFileSync(DASHBOARD_SNAPSHOT_BOUNDARY_PATH, "utf8");

    expect(snapshotBoundarySource).toContain("../../../api/clientContext");
    expect(snapshotBoundarySource).not.toContain("../../../api/client\"");
    expect(snapshotBoundarySource).not.toContain("../../../api/client'");
    expect(snapshotBoundarySource).not.toContain("executiveDashboardAdapter");
  });

  it("keeps the first-screen home mapper off the executive dashboard adapter runtime", () => {
    const firstScreenMapperPath = resolve(
      FRONTEND_ROOT,
      "src/features/workbench/dashboard-home/dashboardHomeFirstScreenView.ts",
    );
    const firstScreenMapperSource = readFileSync(firstScreenMapperPath, "utf8");

    expect(firstScreenMapperSource).not.toContain("executiveDashboardAdapter");
    expect(firstScreenMapperSource).not.toContain("DashboardOverviewMetricVM");
    expect(firstScreenMapperSource).not.toContain("DashboardPnlAttributionVM");
  });

  it("keeps Ant Design providers out of the root route registry", () => {
    const routeSource = readFileSync(ROUTES_PATH, "utf8");

    expect(routeSource).not.toContain("AntdRouteProvider");
    expect(routeSource).not.toContain("antdRouteElement");
    expect(routeSource).not.toMatch(/from\s+["']antd["']/);
    expect(routeSource).not.toMatch(/from\s+["']@ant-design\//);
  });

  it("keeps non-home Ant Design theme boundary lazy", () => {
    const routeSource = readFileSync(ROUTES_PATH, "utf8");

    expect(routeSource).toContain('lazy(() => import("../app/ThemedRouteBoundary"))');
    expect(routeSource).toContain("themedRouteElement(<PnlByBusinessPage />)");
    expect(routeSource).toContain("element: routeElement(<DashboardHomePage />)");
  });

  it("wires the production home startup bundle guard into npm scripts", () => {
    const packageJson = JSON.parse(readFileSync(PACKAGE_JSON_PATH, "utf8")) as {
      scripts?: Record<string, string>;
    };
    const guardSource = readFileSync(HOME_STARTUP_BUNDLE_GUARD_PATH, "utf8");

    expect(packageJson.scripts?.["guard:home-startup"]).toBe(
      "node scripts/verifyHomeStartupBundle.mjs",
    );
    expect(guardSource).toContain("parseHtmlJavaScriptResources");
    expect(guardSource).toContain("DashboardHomePage preload deps");
    expect(guardSource).toContain("isFullClientAsset");
    expect(guardSource).toContain("isEChartsAsset");
    expect(guardSource).toContain("ag-theme-alpine");
    expect(guardSource).toContain("assertNoAgGridImplementation");
    expect(guardSource).toContain("isAntdVendorAsset");
    expect(guardSource).toContain("homeSupplementalClient");
    expect(guardSource).toContain("homeMarketTickerClient");
    expect(guardSource).toContain("/ui/market-data/rates");
    expect(guardSource).toContain("/ui/news/choice-events/latest");
    expect(guardSource).toContain("/ui/calendar/supply-auctions");
  });

  it("keeps manual vendor chunks from pulling their dependencies into each other", () => {
    const viteConfigSource = readFileSync(VITE_CONFIG_PATH, "utf8");

    expect(viteConfigSource).toContain("includeDependenciesRecursively: false");
    expect(viteConfigSource).toContain("isReactVendorModule");
    expect(viteConfigSource).toContain('return "antd-vendor"');
  });
});
