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
const DASHBOARD_HOME_PAGE_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/workbench/dashboard-home/DashboardHomePage.tsx",
);
const TERMINAL_HOME_CONTENT_PATH = resolve(
  FRONTEND_ROOT,
  "src/features/workbench/dashboard-home/TerminalHomeContent.tsx",
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
    expect(clientContextSource).toContain("HOME_EXECUTIVE_METHODS");
    expect(clientContextSource).toContain("HOME_SUPPLEMENTAL_METHODS");
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

  it("does not statically import ECharts in the terminal home content", () => {
    const terminalHomeContentSource = readFileSync(TERMINAL_HOME_CONTENT_PATH, "utf8");

    expect(terminalHomeContentSource).not.toMatch(
      /from\s+["']\.\.\/\.\.\/\.\.\/lib\/echarts["']/,
    );
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

  it("keeps the dashboard snapshot boundary off the full API client runtime", () => {
    const snapshotBoundarySource = readFileSync(DASHBOARD_SNAPSHOT_BOUNDARY_PATH, "utf8");

    expect(snapshotBoundarySource).toContain("../../../api/clientContext");
    expect(snapshotBoundarySource).not.toContain("../../../api/client\"");
    expect(snapshotBoundarySource).not.toContain("../../../api/client'");
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
  });

  it("keeps manual vendor chunks from pulling their dependencies into each other", () => {
    const viteConfigSource = readFileSync(VITE_CONFIG_PATH, "utf8");

    expect(viteConfigSource).toContain("includeDependenciesRecursively: false");
    expect(viteConfigSource).toContain("isReactVendorModule");
    expect(viteConfigSource).toContain('return "antd-vendor"');
  });
});
