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
const HOME_STARTUP_RUNTIME_GUARD_PATH = resolve(
  FRONTEND_ROOT,
  "scripts/verifyHomeStartupRuntime.mjs",
);
const HOME_STARTUP_LIVE_GUARD_PATH = resolve(
  FRONTEND_ROOT,
  "scripts/sampleHomeStartupLive.mjs",
);
const HOME_SNAPSHOT_LIVE_PROFILE_PATH = resolve(
  FRONTEND_ROOT,
  "scripts/profileHomeSnapshotLive.mjs",
);
const VITE_CONFIG_PATH = resolve(FRONTEND_ROOT, "vite.config.ts");
const CLIENT_CONTEXT_PATH = resolve(FRONTEND_ROOT, "src/api/clientContext.ts");
const WORKBENCH_SHELL_PATH = resolve(FRONTEND_ROOT, "src/layouts/WorkbenchShell.tsx");
const WORKBENCH_SHELL_MARKET_TICKER_PATH = resolve(
  FRONTEND_ROOT,
  "src/layouts/WorkbenchShellMarketTicker.tsx",
);
const GLOBAL_CSS_PATH = resolve(FRONTEND_ROOT, "src/styles/global.css");
const DASHBOARD_COCKPIT_CSS_PATH = resolve(
  FRONTEND_ROOT,
  "src/styles/dashboardCockpit.css",
);
const AGENT_WORKBENCH_PAGE_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/agent/AgentWorkbenchPage.tsx",
);
const AGENT_WORKBENCH_CSS_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/agent/AgentWorkbenchPage.css",
);
const HOME_MARKET_TICKER_CLIENT_PATH = resolve(
  FRONTEND_ROOT,
  "src/api/homeMarketTickerClient.ts",
);
const HOME_MARKET_TICKER_MOCK_CLIENT_PATH = resolve(
  FRONTEND_ROOT,
  "src/api/homeMarketTickerMockClient.ts",
);
const HOME_FIRST_SCREEN_MOCK_VIEW_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/workbench/dashboard-home/dashboardHomeFirstScreenMockView.ts",
);
const DASHBOARD_HOME_PAGE_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/workbench/dashboard-home/DashboardHomePage.tsx",
);
const TERMINAL_HOME_FIRST_SCREEN_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/workbench/dashboard-home/TerminalHomeFirstScreen.tsx",
);
const DASHBOARD_HOME_TOOLBAR_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/workbench/dashboard-home/sections/DashboardHomeToolbar.tsx",
);
const DASHBOARD_HOME_DECISION_RAIL_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/workbench/dashboard-home/sections/DecisionRailSection.tsx",
);
const HOME_SPARKLINE_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/workbench/dashboard-home/HomeSparkline.tsx",
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

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

function countCssSelectorLines(source: string, selector: string): number {
  const escaped = escapeRegExp(selector);
  return source.match(new RegExp(`^${escaped}\\s*(?:,|\\{)`, "gm"))?.length ?? 0;
}
const DASHBOARD_HOME_BODY_VIEW_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/workbench/dashboard-home/dashboardHomeBodyView.ts",
);
const DASHBOARD_SNAPSHOT_BOUNDARY_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/workbench/pages/useDashboardSnapshotBoundary.ts",
);
const ROUTES_PATH = resolve(FRONTEND_ROOT, "src/router/routes.tsx");
const APP_PROVIDERS_PATH = resolve(FRONTEND_ROOT, "src/app/providers.tsx");
const THEMED_ROUTE_BOUNDARY_PATH = resolve(
  FRONTEND_ROOT,
  "src/app/ThemedRouteBoundary.tsx",
);
const STOCK_ANALYSIS_PAGE_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/stock-analysis/pages/StockAnalysisPageImpl.tsx",
);
const STOCK_ANALYSIS_DEEP_ZONE_HEADER_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/stock-analysis/components/StockAnalysisDeepZoneHeader.tsx",
);
const STOCK_ANALYSIS_DEEP_RESEARCH_PRIMITIVES_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/stock-analysis/components/StockAnalysisDeepResearchPrimitives.ts",
);
const STOCK_ANALYSIS_WORKBENCH_CLIENT_PATH = resolve(
  FRONTEND_ROOT,
  "src/api/stockAnalysisWorkbenchClient.ts",
);

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
    expect(clientContextSource).toContain('import("./marketDataClient")');
    expect(clientContextSource).not.toContain('mode === "real" && HOME_MARKET_TICKER_METHODS');
    expect(clientContextSource).toContain("if (HOME_MARKET_TICKER_METHODS.has(");
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

  it("keeps stock analysis off the full API client runtime", () => {
    const stockAnalysisPageSource = readFileSync(STOCK_ANALYSIS_PAGE_PATH, "utf8");

    expect(stockAnalysisPageSource).toContain("../../../api/clientContext");
    expect(stockAnalysisPageSource).not.toContain("../../../api/client\"");
    expect(stockAnalysisPageSource).not.toContain("../../../api/client'");
  });

  it("keeps the first-screen stock workbench off the full market-data runtime", () => {
    const clientContextSource = readFileSync(CLIENT_CONTEXT_PATH, "utf8");
    const stockAnalysisWorkbenchClientSource = readFileSync(
      STOCK_ANALYSIS_WORKBENCH_CLIENT_PATH,
      "utf8",
    );
    const marketMethodSet = clientContextSource.match(
      /const STOCK_ANALYSIS_MARKET_DATA_METHODS[\s\S]*?\]\);/,
    )?.[0];

    expect(clientContextSource).toContain('import("./stockAnalysisWorkbenchClient")');
    expect(marketMethodSet).toBeDefined();
    expect(marketMethodSet).not.toContain("getStockAnalysisWorkbench");
    expect(stockAnalysisWorkbenchClientSource).toContain(
      "/ui/market-data/stock-analysis/workbench",
    );
    expect(stockAnalysisWorkbenchClientSource).not.toContain("marketDataClient");
  });

  it("keeps deep-research scripts and styles behind the lazy stock-analysis boundary", () => {
    const stockAnalysisPageSource = readFileSync(STOCK_ANALYSIS_PAGE_PATH, "utf8");
    const deepZoneHeaderSource = readFileSync(STOCK_ANALYSIS_DEEP_ZONE_HEADER_PATH, "utf8");
    const deepResearchPrimitivesSource = readFileSync(
      STOCK_ANALYSIS_DEEP_RESEARCH_PRIMITIVES_PATH,
      "utf8",
    );

    expect(stockAnalysisPageSource).toContain('import("../components/StockAnalysisDeepZoneHeader")');
    expect(stockAnalysisPageSource).toContain(
      'import("../components/StockAnalysisDeepSelectionOverview")',
    );
    expect(stockAnalysisPageSource).toContain(
      'import("../components/StockAnalysisDeepResearchPrimitives")',
    );
    expect(stockAnalysisPageSource).not.toContain("StockAnalysisDeepResearch.css");
    for (const staticDeepImport of [
      "../components/StockAnalysisBacktestBoundaryChips",
      "../components/StockAnalysisCycleRuleSummary",
      "../components/StockAnalysisTabs",
      "../components/StrategyModuleCard",
      "../components/StrategyPanelResultStrip",
    ]) {
      expect(stockAnalysisPageSource).not.toContain(staticDeepImport);
    }
    expect(deepZoneHeaderSource).toContain('import "../pages/StockAnalysisDeepResearch.css"');
    expect(deepResearchPrimitivesSource).toContain('export { StrategyModuleCard }');
    expect(deepResearchPrimitivesSource).toContain('export { StockAnalysisTab, StockAnalysisTabs }');
  });

  it("keeps home market ticker methods in a lightweight client", () => {
    const homeMarketTickerSource = readFileSync(HOME_MARKET_TICKER_CLIENT_PATH, "utf8");
    const homeMarketTickerMockSource = readFileSync(HOME_MARKET_TICKER_MOCK_CLIENT_PATH, "utf8");

    expect(homeMarketTickerSource).toContain("HomeMarketTickerClientMethods");
    expect(homeMarketTickerSource).toContain("createRealHomeMarketTickerClient");
    expect(homeMarketTickerSource).toContain("createMockHomeMarketTickerClient");
    expect(homeMarketTickerSource).not.toContain('import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope"');
    expect(homeMarketTickerSource).toContain('import("./homeMarketTickerMockClient")');
    expect(homeMarketTickerMockSource).toContain('import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope"');
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

  it("keeps non-home shell market ticker work out of the dashboard shell startup module", () => {
    const shellSource = readFileSync(WORKBENCH_SHELL_PATH, "utf8");
    const tickerSource = readFileSync(WORKBENCH_SHELL_MARKET_TICKER_PATH, "utf8");

    expect(shellSource).toContain('lazy(() => import("./WorkbenchShellMarketTicker"))');
    expect(shellSource).not.toContain("buildShellTickerItems");
    expect(shellSource).not.toContain("choiceMacroFormat");
    expect(shellSource).not.toContain("getChoiceMacroLatest");
    expect(shellSource).not.toContain("useQuery");
    expect(tickerSource).toContain("buildShellTickerItems");
    expect(tickerSource).toContain("getChoiceMacroLatest");
  });

  it("keeps Agent workbench styles out of the global startup stylesheet", () => {
    const globalCss = readFileSync(GLOBAL_CSS_PATH, "utf8");
    const agentPageSource = readFileSync(AGENT_WORKBENCH_PAGE_PATH, "utf8");
    const agentCss = readFileSync(AGENT_WORKBENCH_CSS_PATH, "utf8");

    expect(globalCss).not.toContain(".agent-workbench-shell");
    expect(globalCss).not.toContain(".agent-chat-composer");
    expect(agentPageSource).toContain('import "./AgentWorkbenchPage.css"');
    expect(agentCss).toContain(".agent-workbench-shell");
    expect(agentCss).toContain(".agent-chat-composer");
  });

  it("keeps overridden cockpit rail rules from returning to the global startup stylesheet", () => {
    const globalCss = readFileSync(GLOBAL_CSS_PATH, "utf8");
    const dashboardCockpitCss = readFileSync(DASHBOARD_COCKPIT_CSS_PATH, "utf8");

    expect(globalCss).toContain('@import "./dashboardCockpit.css";');

    for (const selector of [
      ".workbench-shell-grid--cockpit .workbench-shell-aside > div:first-child",
      ".workbench-shell-grid--cockpit .workbench-shell-aside > div:first-child > div",
      ".workbench-shell-grid--cockpit .workbench-shell-aside > div:first-child > div > div:first-child",
      ".workbench-shell-grid--cockpit .workbench-shell-aside > div:first-child span",
      ".workbench-shell-grid--cockpit .workbench-shell-section-label--rail",
      '.workbench-shell-grid--cockpit [data-testid="workbench-group-nav"] a',
      '.workbench-shell-grid--cockpit [data-testid="workbench-group-nav"] a[data-active="true"]',
      '.workbench-shell-grid--cockpit [data-testid="workbench-group-nav"] a[data-active="true"] span:last-child',
    ]) {
      expect(countCssSelectorLines(globalCss, selector)).toBe(0);
      expect(countCssSelectorLines(dashboardCockpitCss, selector)).toBe(1);
    }

    expect(dashboardCockpitCss).toContain(
      '.workbench-shell-grid--cockpit [data-testid="workbench-group-nav"]',
    );
    expect(dashboardCockpitCss).toContain(
      '.workbench-shell-grid--cockpit [data-testid="workbench-support-nav"]',
    );
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

  it("keeps first-screen home modules off the full dashboard home stylesheet", () => {
    const firstScreenSources = [
      readFileSync(DASHBOARD_HOME_PAGE_PATH, "utf8"),
      readFileSync(TERMINAL_HOME_FIRST_SCREEN_PATH, "utf8"),
      readFileSync(DASHBOARD_HOME_TOOLBAR_PATH, "utf8"),
      readFileSync(DASHBOARD_HOME_DECISION_RAIL_PATH, "utf8"),
      readFileSync(HOME_SPARKLINE_PATH, "utf8"),
      readFileSync(DEFERRED_TERMINAL_HOME_CONTENT_PATH, "utf8"),
    ];

    for (const source of firstScreenSources) {
      expect(source).toContain("dashboardHomeShell.module.css");
      expect(source).not.toContain("dashboardHome.module.css");
    }
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

  it("keeps deferred terminal home body off a second timer after first screen settles", () => {
    const deferredTerminalSource = readFileSync(DEFERRED_TERMINAL_HOME_CONTENT_PATH, "utf8");

    expect(deferredTerminalSource).toContain("requestIdleCallback(markReady");
    expect(deferredTerminalSource).not.toContain("BODY_IDLE_MIN_DELAY_MS");
    expect(deferredTerminalSource).not.toContain("delayHandle = window.setTimeout(scheduleBodyLoad");
  });

  it("keeps first-screen supplemental hydration off below-fold home queries", () => {
    const hydrationSource = readFileSync(HOME_SUPPLEMENTAL_HYDRATION_PATH, "utf8");
    const deferredContentSource = readFileSync(DEFERRED_TERMINAL_HOME_CONTENT_PATH, "utf8");

    expect(hydrationSource).not.toContain("useDashboardData");
    expect(hydrationSource).toContain("getBondDashboardHeadlineKpis");
    expect(hydrationSource).toContain("getBondAnalyticsPortfolioHeadlines");
    expect(hydrationSource).toContain("useFirstScreenHydrationGate");
    expect(hydrationSource).toContain("FIRST_SCREEN_HYDRATION_IDLE_MIN_DELAY_MS");
    expect(hydrationSource).toContain(
      "enabled: !useMockFallback && hasDeferredSupplementalReportDate && hasFirstScreenHydrationData",
    );
    expect(deferredContentSource).toContain("loadFirstScreenHydration");
    expect(deferredContentSource).toContain("enabled: loadFirstScreenHydration");
    expect(deferredContentSource).toContain("if (loadBody)");
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
    expect(bodyDataSource).not.toContain("getAssetIncomeOverview");
    expect(bodyDataSource).not.toContain("getPortfolioHeadlines");
    expect(bodyDataSource).not.toContain("bondHeadlineQuery");
    expect(bodyDataSource).not.toContain("portfolioHeadlinesQuery");
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

  it("keeps homepage event feeds behind a separate post-snapshot idle gate", () => {
    const homeViewModelSource = readFileSync(HOME_VIEW_MODEL_PATH, "utf8");
    const bodyDataSource = readFileSync(HOME_BODY_DATA_PATH, "utf8");

    expect(homeViewModelSource).toContain("useBodyStructureDataGate");
    expect(homeViewModelSource).toContain("BODY_STRUCTURE_IDLE_MIN_DELAY_MS");
    expect(homeViewModelSource).toContain("hasBodyStructureData");
    expect(homeViewModelSource).toContain("enabled: hasDeferredSupplementalReportDate && hasBodyDetailData && hasBodyStructureData");
    expect(homeViewModelSource).toContain("useEventFeedDataGate");
    expect(homeViewModelSource).toMatch(
      /const hasEventFeedData = useEventFeedDataGate\(\s*hasDeferredSupplementalReportDate && !options\.eagerEventFeeds\s*\?\s*supplementalReportDate\s*:\s*undefined,\s*\)/,
    );
    expect(homeViewModelSource).toContain("const eventFeedsReady = options.eagerEventFeeds || hasEventFeedData");
    expect(homeViewModelSource).toContain("loadEventFeeds: hasDeferredSupplementalReportDate && eventFeedsReady");
    expect(homeViewModelSource).toContain("useSecondaryEventFeedDataGate");
    expect(homeViewModelSource).toContain("loadEventFeeds");
    expect(homeViewModelSource).toContain("loadSecondaryEventFeeds");
    expect(homeViewModelSource).toContain("EVENT_FEED_IDLE_MIN_DELAY_MS");
    expect(homeViewModelSource).toContain("SECONDARY_EVENT_FEED_IDLE_MIN_DELAY_MS");
    expect(bodyDataSource).toContain("loadSecondaryEventFeeds,");
    expect(bodyDataSource).toMatch(
      /const shouldLoadMacroNewsFallback =\s*loadSecondaryEventFeeds &&\s*macroNewsSettled/,
    );
    expect(bodyDataSource).not.toMatch(/getChoiceNewsEvents[\s\S]{0,300}enabled:\s*loadDetailData/);
    expect(bodyDataSource).not.toMatch(/useDashboardResearchCalendarQuery[\s\S]{0,120}enabled:\s*loadDetailData/);
  });

  it("keeps homepage bond news and formal data behind their own gates", () => {
    const homeViewModelSource = readFileSync(HOME_VIEW_MODEL_PATH, "utf8");
    const bodyDataSource = readFileSync(HOME_BODY_DATA_PATH, "utf8");

    expect(homeViewModelSource).toContain("useBondNewsFeedDataGate");
    expect(homeViewModelSource).toContain("useFormalContextDataGate");
    expect(homeViewModelSource).toContain("loadBondNewsFeeds");
    expect(homeViewModelSource).toContain("loadFormalData: hasDeferredFormalContext");
    expect(homeViewModelSource).not.toContain("heavyBondListsReady");
    expect(homeViewModelSource).not.toContain("formalContextReportDate");
    expect(homeViewModelSource).not.toContain("setFormalContextReportDate");
    expect(bodyDataSource).toContain("loadBondNewsFeeds");
    expect(bodyDataSource).toContain("enabled: loadBondNewsFeeds");
    expect(bodyDataSource).toContain("const loadDatedFormalData = loadFormalData && hasSupplementalReportDate");
    expect(bodyDataSource).toContain("enabled: loadDatedFormalData");
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
    const firstScreenMockSource = readFileSync(HOME_FIRST_SCREEN_MOCK_VIEW_PATH, "utf8");

    expect(firstScreenMapperSource).not.toContain("executiveDashboardAdapter");
    expect(firstScreenMapperSource).not.toContain("DashboardOverviewMetricVM");
    expect(firstScreenMapperSource).not.toContain("DashboardPnlAttributionVM");
    expect(firstScreenMapperSource).not.toContain("../dashboard/dashboardMockData");
    expect(firstScreenMapperSource).not.toContain("./homeFirstScreenFallback");
    expect(firstScreenMapperSource).not.toContain("mockFirstScreenView");
    expect(firstScreenMockSource).toContain("./homeFirstScreenFallback");
    expect(firstScreenMockSource).toContain("createMockHomeFirstScreenView");
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
    const appProvidersSource = readFileSync(APP_PROVIDERS_PATH, "utf8");
    const themedBoundarySource = readFileSync(THEMED_ROUTE_BOUNDARY_PATH, "utf8");

    expect(routeSource).toContain('lazy(() => import("../app/ThemedRouteBoundary"))');
    expect(routeSource).toContain("themedRouteElement(<PnlByBusinessPage />)");
    expect(routeSource).toContain("themedRouteElement(<CrossAssetPage />)");
    expect(routeSource).toContain("element: routeElement(<DashboardHomePage />)");
    expect(appProvidersSource).not.toContain('import("antd")');
    expect(appProvidersSource).not.toContain("ConfigProvider");
    expect(appProvidersSource).not.toContain("loadAntdTheme");
    expect(themedBoundarySource).toMatch(/from\s+["']antd["']/);
    expect(themedBoundarySource).toContain("ConfigProvider");
    expect(themedBoundarySource).toContain("workbenchTheme");
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
    expect(guardSource).toMatch(
      /"DashboardHomePage preload deps",\s*homeRouteAssets,\s*isAntdVendorAsset/,
    );
    expect(guardSource).toContain("homeSupplementalClient");
    expect(guardSource).toContain("homeMarketTickerClient");
    expect(guardSource).toContain("isWorkbenchShellMarketTickerAsset");
    expect(guardSource).toContain("workbench shell market ticker chunk");
    expect(guardSource).toContain("isLightweightHomeShellStylesheetContent");
    expect(guardSource).toContain("readAssetText");
    expect(guardSource).toContain("workbenchInstitutionalConsole");
    expect(guardSource).toContain("workbenchDeferredChrome");
    expect(guardSource).toContain("institutional console stylesheet");
    expect(guardSource).toContain("non-home workbench chrome stylesheet");
    expect(guardSource).toContain("/ui/market-data/rates");
    expect(guardSource).toContain("/ui/news/choice-events/latest");
    expect(guardSource).toContain("/ui/calendar/supply-auctions");
  });

  it("keeps the production runtime startup guard source-backed", () => {
    const guardSource = readFileSync(HOME_STARTUP_RUNTIME_GUARD_PATH, "utf8");

    expect(guardSource).not.toContain('import { preview } from "vite"');
    expect(guardSource).toContain('import { createServer } from "node:http"');
    expect(guardSource).toContain("MOSS_HOME_STARTUP_API_TARGET");
    expect(guardSource).toContain("createProductionStaticServer");
    expect(guardSource).toContain("serveDistRequest");
    expect(guardSource).toContain('mode: "production-preview"');
    expect(guardSource).toContain("assertFreshProductionBundle");
    expect(guardSource).toContain("/assets/client-");
    expect(guardSource).toContain("/assets/homeMarketTickerMockClient-");
    expect(guardSource).toContain("/assets/mockApiEnvelope-");
    expect(guardSource).toContain("/assets/dashboardHomeFirstScreenMockView-");
    expect(guardSource).toContain("home should not load the market ticker mock chunk");
    expect(guardSource).toContain("home should not load the first-screen mock view chunk");
    expect(guardSource).toContain("/assets/antd-vendor-");
    expect(guardSource).toContain("home should not load the Ant Design vendor chunk");
    expect(guardSource).toContain(
      "cross-asset Ant Design vendor chunk should load in the first-screen window",
    );
    expect(guardSource).toContain("src/layouts/WorkbenchShellMarketTicker.tsx");
    expect(guardSource).toContain("src/layouts/workbenchShellTicker.ts");
    expect(guardSource).toContain("/assets/WorkbenchShellMarketTicker-");
    expect(guardSource).toContain("workbench shell market ticker should stay out of the first-screen window");
    expect(guardSource).toContain("home should not load the workbench shell market ticker chunk");
    expect(guardSource).toContain("cross-asset workbench shell market ticker chunk did not load");
    expect(guardSource).toContain("/assets/workbenchInstitutionalConsole-");
    expect(guardSource).toContain("/assets/workbenchDeferredChrome-");
    expect(guardSource).toContain("home should not load the institutional console stylesheet");
    expect(guardSource).toContain("home should not load the non-home workbench chrome stylesheet");
    expect(guardSource).toContain("if (initialCounts.institutionalStylesheet < 1)");
    expect(guardSource).toContain("if (initialCounts.workbenchChromeStylesheet < 1)");
    expect(guardSource).not.toContain("if (allCounts.institutionalStylesheet < 1)");
    expect(guardSource).not.toContain("if (allCounts.workbenchChromeStylesheet < 1)");
    expect(guardSource).toContain("cross-asset institutional console stylesheet did not load in the first-screen window");
    expect(guardSource).toContain("cross-asset workbench chrome stylesheet did not load in the first-screen window");
    expect(guardSource).toContain("HOME_POST_FIRST_SCREEN_MAX_WAIT_MS");
    expect(guardSource).toContain("waitForTrackedRequest");
    expect(guardSource).not.toContain("await page.waitForTimeout(HOME_SETTLE_AFTER_SCROLL_MS);");
    expect(guardSource).toContain("home summary should load after the first-screen window");
    expect(guardSource).toContain("news/calendar should load after the first-screen window");
    expect(guardSource).toContain("income trend should load after the first-screen window");
    expect(guardSource).toContain("browser.newContext");
    expect(guardSource).toContain("createIsolatedPage");
    expect(guardSource).toContain('context.route("**/*"');
    expect(guardSource).toContain("sampleNonHomeShell");
    expect(guardSource).toContain("/cross-asset");
    expect(guardSource).toContain('[data-testid="workbench-group-nav"] a[href="/"]');
    expect(guardSource).toContain("home return from cross-asset");
    expect(guardSource).toContain("home return should leave the institutional console scope");
  });

  it("keeps the live dev startup sampler source-backed", () => {
    const guardSource = readFileSync(HOME_STARTUP_LIVE_GUARD_PATH, "utf8");

    expect(guardSource).toContain("checks.home_snapshot_prewarm");
    expect(guardSource).toContain("API readiness is missing checks.home_snapshot_prewarm");
    expect(guardSource).toContain('[data-testid="dashboard-home-page"]');
    expect(guardSource).toContain('[data-testid="dashboard-home-hero"]');
    expect(guardSource).toContain("/src/api/client.ts");
    expect(guardSource).toContain("/assets/client-");
    expect(guardSource).toContain("/src/api/homeMarketTickerMockClient.ts");
    expect(guardSource).toContain("/src/mocks/mockApiEnvelope.ts");
    expect(guardSource).toContain("/src/features/workbench/dashboard-home/dashboardHomeFirstScreenMockView.ts");
    expect(guardSource).toContain("market ticker mock should stay out of live real-data home");
    expect(guardSource).toContain("first-screen mock view should stay out of live real-data home");
    expect(guardSource).toContain("/ui/market-data/rates");
    expect(guardSource).toContain("/ui/news/choice-events/latest");
    expect(guardSource).toContain("/ui/calendar/supply-auctions");
    expect(guardSource).toContain("ECharts/zrender should stay out of first-screen window");
  });

  it("keeps the live home snapshot profiler source-backed", () => {
    const profileSource = readFileSync(HOME_SNAPSHOT_LIVE_PROFILE_PATH, "utf8");

    expect(profileSource).toContain("checks.home_snapshot_prewarm");
    expect(profileSource).toContain("/ui/home/snapshot");
    expect(profileSource).toContain("MOSS_HOME_SNAPSHOT_PROFILE_SAMPLES");
    expect(profileSource).toContain("MOSS_HOME_SNAPSHOT_SLOW_HIT_MS");
    expect(profileSource).toContain("p50Ms");
    expect(profileSource).toContain("p95Ms");
    expect(profileSource).toContain("last_step_durations_ms");
    expect(profileSource).toContain("slowestPrewarmSteps");
    expect(profileSource).toContain("prewarm status is missing last_step_durations_ms");
    expect(profileSource).toContain("warm snapshot samples exceeded");
  });

  it("keeps manual vendor chunks from pulling their dependencies into each other", () => {
    const viteConfigSource = readFileSync(VITE_CONFIG_PATH, "utf8");

    expect(viteConfigSource).toContain("includeDependenciesRecursively: false");
    expect(viteConfigSource).toContain("isReactVendorModule");
    expect(viteConfigSource).toContain('return "antd-vendor"');
  });
});
