import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";

import { describe, expect, it } from "vitest";

import { createApiClient } from "../api/client";

const clientSource = readFileSync(resolve(process.cwd(), "src/api/client.ts"), "utf8");
const clientContextSource = readFileSync(resolve(process.cwd(), "src/api/clientContext.ts"), "utf8");
const providersSource = readFileSync(resolve(process.cwd(), "src/app/providers.tsx"), "utf8");
const shellSource = readFileSync(resolve(process.cwd(), "src/layouts/WorkbenchShell.tsx"), "utf8");
const dataModeRibbonSource = readFileSync(resolve(process.cwd(), "src/components/DataModeRibbon.tsx"), "utf8");
const marketDataSource = readFileSync(resolve(process.cwd(), "src/api/marketDataClient.ts"), "utf8");
const kpiSource = readFileSync(resolve(process.cwd(), "src/api/kpiClient.ts"), "utf8");
const cubeSource = readFileSync(resolve(process.cwd(), "src/api/cubeClient.ts"), "utf8");
const agentClientSource = readFileSync(resolve(process.cwd(), "src/api/agentClient.ts"), "utf8");
const executiveClientSource = readFileSync(resolve(process.cwd(), "src/api/executiveClient.ts"), "utf8");
const bondAnalyticsClientSource = readFileSync(resolve(process.cwd(), "src/api/bondAnalyticsClient.ts"), "utf8");
const healthClientPath = resolve(process.cwd(), "src/api/healthClient.ts");
const healthClientSource = existsSync(healthClientPath)
  ? readFileSync(healthClientPath, "utf8")
  : "";

describe("ApiClient composition boundary", () => {
  it("keeps the public market-data source preview surface available from createApiClient", () => {
    const client = createApiClient({ mode: "mock" });

    expect(typeof client.getSourceFoundation).toBe("function");
    expect(typeof client.refreshSourcePreview).toBe("function");
    expect(typeof client.getSourcePreviewRefreshStatus).toBe("function");
    expect(typeof client.getSourceFoundationHistory).toBe("function");
    expect(typeof client.getSourceFoundationRows).toBe("function");
    expect(typeof client.getSourceFoundationTraces).toBe("function");
    expect(typeof client.getChoiceNewsEvents).toBe("function");
    expect(typeof client.ingestTushareNprNews).toBe("function");
    expect(typeof client.getResearchCalendarEvents).toBe("function");
    expect(typeof client.getKpiOwners).toBe("function");
    expect(typeof client.fetchAndRecalcKpi).toBe("function");
    expect(typeof client.getCubeDimensions).toBe("function");
    expect(typeof client.executeCubeQuery).toBe("function");
  });

  it("keeps the public Bond Dashboard surface available from createApiClient", () => {
    const client = createApiClient({ mode: "mock" });

    expect(typeof client.getBondDashboardDates).toBe("function");
    expect(typeof client.getBondDashboardHeadlineKpis).toBe("function");
    expect(typeof client.getBondDashboardAssetStructure).toBe("function");
    expect(typeof client.getBondDashboardYieldDistribution).toBe("function");
    expect(typeof client.getBondDashboardPortfolioComparison).toBe("function");
    expect(typeof client.getBondDashboardSpreadAnalysis).toBe("function");
    expect(typeof client.getBondDashboardMaturityStructure).toBe("function");
    expect(typeof client.getBondDashboardIndustryDistribution).toBe("function");
    expect(typeof client.getBondDashboardRiskIndicators).toBe("function");
  });

  it("keeps the public Bond Analytics surface available from createApiClient", () => {
    const client = createApiClient({ mode: "mock" });

    expect(typeof client.refreshBondAnalytics).toBe("function");
    expect(typeof client.getBondAnalyticsRefreshStatus).toBe("function");
    expect(typeof client.getBondAnalyticsDates).toBe("function");
    expect(typeof client.getBondAnalyticsReturnDecomposition).toBe("function");
    expect(typeof client.getBondAnalyticsBenchmarkExcess).toBe("function");
    expect(typeof client.getBondAnalyticsKrdCurveRisk).toBe("function");
    expect(typeof client.getBondAnalyticsActionAttribution).toBe("function");
    expect(typeof client.getBondAnalyticsAccountingClassAudit).toBe("function");
    expect(typeof client.getBondAnalyticsCreditSpreadMigration).toBe("function");
    expect(typeof client.getBondAnalyticsPortfolioHeadlines).toBe("function");
    expect(typeof client.getBondAnalyticsTopHoldings).toBe("function");
    expect(typeof client.getBondAnalyticsYieldCurveTermStructure).toBe("function");
    expect(typeof client.getCreditSpreadAnalysisDetail).toBe("function");
  });

  it("keeps extracted domain implementation out of client.ts", () => {
    expect(clientSource).not.toContain("MOCK_SOURCE_FOUNDATION_SUMMARIES");
    expect(clientSource).not.toContain("MOCK_CHOICE_NEWS_EVENTS");
    expect(clientSource).not.toContain("buildMockResearchCalendarEvents");
    expect(clientSource).not.toContain("buildMockChoiceNewsEnvelope");
    expect(clientSource).not.toContain("requestKpiJson");
    expect(clientSource).not.toContain("kpiQueryString");
    expect(clientSource).not.toContain("dimensionMap");
    expect(clientSource).not.toContain("buildStableDemoAgentEnvelope");
    expect(clientSource).not.toContain("/api/agent/query");
    expect(clientSource).not.toContain("/ui/home/overview");
    expect(clientSource).not.toContain("/ui/home/summary");
    expect(clientSource).not.toContain("/ui/risk/overview");
    expect(clientSource).not.toContain("/ui/home/contribution");
    expect(clientSource).not.toContain("/ui/home/alerts");
    expect(clientSource).not.toContain("/api/risk/tensor");
    expect(clientSource).not.toContain("risk.tensor");
    expect(clientSource).not.toContain("/api/bond-dashboard/");
    expect(clientSource).not.toContain("bond_dashboard.dates");
    expect(clientSource).not.toContain("bond_dashboard.headline_kpis");
    expect(clientSource).not.toContain("bond_dashboard.asset_structure");
    expect(clientSource).not.toContain("bond_dashboard.yield_distribution");
    expect(clientSource).not.toContain("bond_dashboard.portfolio_comparison");
    expect(clientSource).not.toContain("bond_dashboard.spread_analysis");
    expect(clientSource).not.toContain("bond_dashboard.maturity_structure");
    expect(clientSource).not.toContain("bond_dashboard.industry_distribution");
    expect(clientSource).not.toContain("bond_dashboard.risk_indicators");
    expect(clientSource).not.toContain("/api/bond-analytics/");
    expect(clientSource).not.toContain("/api/credit-spread-analysis/detail");
    expect(clientSource).not.toContain("bond_analytics.dates");
    expect(clientSource).not.toContain("bond_analytics.return_decomposition");
    expect(clientSource).not.toContain("bond_analytics.benchmark_excess");
    expect(clientSource).not.toContain("bond_analytics.krd_curve_risk");
    expect(clientSource).not.toContain("bond_analytics.action_attribution");
    expect(clientSource).not.toContain("bond_analytics.accounting_class_audit");
    expect(clientSource).not.toContain("bond_analytics.credit_spread_migration");
    expect(clientSource).not.toContain("bond_analytics.portfolio_headlines");
    expect(clientSource).not.toContain("bond_analytics.top_holdings");
    expect(clientSource).not.toContain("credit_spread_analysis.detail");
    expect(clientSource).not.toMatch(/async getSourceFoundation\(/);
    expect(clientSource).not.toMatch(/async refreshSourcePreview\(/);
    expect(clientSource).not.toMatch(/async getSourcePreviewRefreshStatus\(/);
    expect(clientSource).not.toMatch(/async getSourceFoundationHistory\(/);
    expect(clientSource).not.toMatch(/async getSourceFoundationRows\(/);
    expect(clientSource).not.toMatch(/async getSourceFoundationTraces\(/);
    expect(clientSource).not.toMatch(/async getChoiceNewsEvents\(/);
    expect(clientSource).not.toMatch(/async getResearchCalendarEvents\(/);
    expect(clientSource).not.toMatch(/async ingestTushareNprNews\(/);
    expect(clientSource).not.toMatch(/async getKpiOwners\(/);
    expect(clientSource).not.toMatch(/async fetchAndRecalcKpi\(/);
    expect(clientSource).not.toMatch(/async getCubeDimensions\(/);
    expect(clientSource).not.toMatch(/async executeCubeQuery\(/);
    expect(clientSource).not.toMatch(/async queryAgent\(/);
    expect(clientSource).not.toMatch(/async getOverview\(/);
    expect(clientSource).not.toMatch(/async getHomeSnapshot\(/);
    expect(clientSource).not.toMatch(/async getSummary\(/);
    expect(clientSource).not.toMatch(/async getRiskOverview\(/);
    expect(clientSource).not.toMatch(/async getRiskTensorDates\(/);
    expect(clientSource).not.toMatch(/async getRiskTensor\(/);
    expect(clientSource).not.toMatch(/async getContribution\(/);
    expect(clientSource).not.toMatch(/async getAlerts\(/);
    expect(clientSource).not.toMatch(/async getPlaceholderSnapshot\(/);
    expect(clientSource).not.toMatch(/async getBondDashboardDates\(/);
    expect(clientSource).not.toMatch(/async getBondDashboardHeadlineKpis\(/);
    expect(clientSource).not.toMatch(/async getBondDashboardAssetStructure\(/);
    expect(clientSource).not.toMatch(/async getBondDashboardYieldDistribution\(/);
    expect(clientSource).not.toMatch(/async getBondDashboardPortfolioComparison\(/);
    expect(clientSource).not.toMatch(/async getBondDashboardSpreadAnalysis\(/);
    expect(clientSource).not.toMatch(/async getBondDashboardMaturityStructure\(/);
    expect(clientSource).not.toMatch(/async getBondDashboardIndustryDistribution\(/);
    expect(clientSource).not.toMatch(/async getBondDashboardRiskIndicators\(/);
    expect(clientSource).not.toMatch(/async refreshBondAnalytics\(/);
    expect(clientSource).not.toMatch(/async getBondAnalyticsRefreshStatus\(/);
    expect(clientSource).not.toMatch(/async getBondAnalyticsDates\(/);
    expect(clientSource).not.toMatch(/async getBondAnalyticsReturnDecomposition\(/);
    expect(clientSource).not.toMatch(/async getBondAnalyticsBenchmarkExcess\(/);
    expect(clientSource).not.toMatch(/async getBondAnalyticsKrdCurveRisk\(/);
    expect(clientSource).not.toMatch(/async getBondAnalyticsActionAttribution\(/);
    expect(clientSource).not.toMatch(/async getBondAnalyticsAccountingClassAudit\(/);
    expect(clientSource).not.toMatch(/async getBondAnalyticsCreditSpreadMigration\(/);
    expect(clientSource).not.toMatch(/async getBondAnalyticsPortfolioHeadlines\(/);
    expect(clientSource).not.toMatch(/async getBondAnalyticsTopHoldings\(/);
    expect(clientSource).not.toMatch(/async getBondAnalyticsYieldCurveTermStructure\(/);
    expect(clientSource).not.toMatch(/async getCreditSpreadAnalysisDetail\(/);
  });

  it("requires marketDataClient.ts to own the extracted market-data composition slice", () => {
    expect(marketDataSource).toMatch(/async getSourceFoundation\(/);
    expect(marketDataSource).toMatch(/async refreshSourcePreview\(/);
    expect(marketDataSource).toMatch(/async getSourcePreviewRefreshStatus\(/);
    expect(marketDataSource).toMatch(/async getSourceFoundationHistory\(/);
    expect(marketDataSource).toMatch(/async getSourceFoundationRows\(/);
    expect(marketDataSource).toMatch(/async getSourceFoundationTraces\(/);
    expect(marketDataSource).toMatch(/async getChoiceNewsEvents\(/);
    expect(marketDataSource).toMatch(/async getResearchCalendarEvents\(/);
    expect(marketDataSource).toMatch(/async ingestTushareNprNews\(/);
  });

  it("requires KPI and cube clients to own their extracted composition slices", () => {
    expect(kpiSource).toContain("requestKpiJson");
    expect(kpiSource).toMatch(/async getKpiOwners\(/);
    expect(kpiSource).toMatch(/async fetchAndRecalcKpi\(/);
    expect(cubeSource).toMatch(/async getCubeDimensions\(/);
    expect(cubeSource).toMatch(/async executeCubeQuery\(/);
  });

  it("requires agentClient.ts to own agent query implementations", () => {
    expect(agentClientSource).toContain("buildStableDemoAgentEnvelope");
    expect(agentClientSource).toContain("/api/agent/query");
    expect(agentClientSource).toMatch(/async queryAgent\(/);
    expect(agentClientSource).toMatch(/create(Mock|Demo)AgentClient/);
  });

  it("requires executiveClient.ts to own executive and home thin implementations", () => {
    expect(executiveClientSource).toContain("createDemoExecutiveClient");
    expect(executiveClientSource).toContain("createRealExecutiveClient");
    expect(executiveClientSource).toContain("/ui/home/overview");
    expect(executiveClientSource).toContain("/ui/home/summary");
    expect(executiveClientSource).toContain("/ui/risk/overview");
    expect(executiveClientSource).toContain("/ui/home/contribution");
    expect(executiveClientSource).toContain("/ui/home/alerts");
    expect(executiveClientSource).toContain("/api/risk/tensor/dates");
    expect(executiveClientSource).toContain("risk.tensor");
    expect(executiveClientSource).toMatch(/async getOverview\(/);
    expect(executiveClientSource).toMatch(/async getHomeSnapshot\(/);
    expect(executiveClientSource).toMatch(/async getSummary\(/);
    expect(executiveClientSource).toMatch(/async getRiskOverview\(/);
    expect(executiveClientSource).toMatch(/async getRiskTensorDates\(/);
    expect(executiveClientSource).toMatch(/async getRiskTensor\(/);
    expect(executiveClientSource).toMatch(/async getContribution\(/);
    expect(executiveClientSource).toMatch(/async getAlerts\(/);
    expect(executiveClientSource).toMatch(/async getPlaceholderSnapshot\(/);
  });

  it("requires bondAnalyticsClient.ts to own Bond Dashboard API implementations", () => {
    expect(bondAnalyticsClientSource).toContain("createDemoBondDashboardClient");
    expect(bondAnalyticsClientSource).toContain("createRealBondDashboardClient");
    expect(bondAnalyticsClientSource).toContain("/api/bond-dashboard/dates");
    expect(bondAnalyticsClientSource).toContain("/api/bond-dashboard/headline-kpis");
    expect(bondAnalyticsClientSource).toContain("/api/bond-dashboard/asset-structure");
    expect(bondAnalyticsClientSource).toContain("/api/bond-dashboard/yield-distribution");
    expect(bondAnalyticsClientSource).toContain("/api/bond-dashboard/portfolio-comparison");
    expect(bondAnalyticsClientSource).toContain("/api/bond-dashboard/spread-analysis");
    expect(bondAnalyticsClientSource).toContain("/api/bond-dashboard/maturity-structure");
    expect(bondAnalyticsClientSource).toContain("/api/bond-dashboard/industry-distribution");
    expect(bondAnalyticsClientSource).toContain("/api/bond-dashboard/risk-indicators");
    expect(bondAnalyticsClientSource).toContain("bond_dashboard.headline_kpis");
    expect(bondAnalyticsClientSource).toContain("bond_dashboard.risk_indicators");
    expect(bondAnalyticsClientSource).toMatch(/async getBondDashboardDates\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondDashboardHeadlineKpis\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondDashboardAssetStructure\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondDashboardYieldDistribution\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondDashboardPortfolioComparison\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondDashboardSpreadAnalysis\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondDashboardMaturityStructure\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondDashboardIndustryDistribution\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondDashboardRiskIndicators\(/);
  });

  it("requires bondAnalyticsClient.ts to own Bond Analytics API implementations", () => {
    expect(bondAnalyticsClientSource).toContain("createDemoBondAnalyticsClient");
    expect(bondAnalyticsClientSource).toContain("createRealBondAnalyticsClient");
    expect(bondAnalyticsClientSource).toContain("/api/bond-analytics/dates");
    expect(bondAnalyticsClientSource).toContain("/api/bond-analytics/refresh");
    expect(bondAnalyticsClientSource).toContain("/api/bond-analytics/refresh-status");
    expect(bondAnalyticsClientSource).toContain("/api/bond-analytics/return-decomposition");
    expect(bondAnalyticsClientSource).toContain("/api/bond-analytics/benchmark-excess");
    expect(bondAnalyticsClientSource).toContain("/api/bond-analytics/krd-curve-risk");
    expect(bondAnalyticsClientSource).toContain("/api/bond-analytics/action-attribution");
    expect(bondAnalyticsClientSource).toContain("/api/bond-analytics/accounting-class-audit");
    expect(bondAnalyticsClientSource).toContain("/api/bond-analytics/credit-spread-migration");
    expect(bondAnalyticsClientSource).toContain("/api/bond-analytics/portfolio-headlines");
    expect(bondAnalyticsClientSource).toContain("/api/bond-analytics/top-holdings");
    expect(bondAnalyticsClientSource).toContain("/api/bond-analytics/yield-curve-term-structure");
    expect(bondAnalyticsClientSource).toContain("/api/credit-spread-analysis/detail");
    expect(bondAnalyticsClientSource).toContain("bond_analytics.return_decomposition");
    expect(bondAnalyticsClientSource).toContain("bond_analytics.credit_spread_migration");
    expect(bondAnalyticsClientSource).toMatch(/async refreshBondAnalytics\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondAnalyticsRefreshStatus\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondAnalyticsDates\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondAnalyticsReturnDecomposition\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondAnalyticsBenchmarkExcess\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondAnalyticsKrdCurveRisk\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondAnalyticsActionAttribution\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondAnalyticsAccountingClassAudit\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondAnalyticsCreditSpreadMigration\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondAnalyticsPortfolioHeadlines\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondAnalyticsTopHoldings\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getBondAnalyticsYieldCurveTermStructure\(/);
    expect(bondAnalyticsClientSource).toMatch(/async getCreditSpreadAnalysisDetail\(/);
  });

  it("requires healthClient.ts to own health endpoint implementations", () => {
    expect(clientSource).not.toContain("/health/ready");
    expect(clientSource).not.toContain("/health/live");
    expect(clientSource).not.toMatch(/async getHealthLive\(/);
    expect(healthClientSource).toContain("/health/ready");
    expect(healthClientSource).toContain("/health/live");
    expect(healthClientSource).toContain("/health");
  });

  it("keeps first-screen providers and shell on the lightweight API context boundary", () => {
    expect(providersSource).toMatch(/from\s+["']\.\.\/api\/clientContext["']/);
    expect(providersSource).not.toMatch(/from\s+["']\.\.\/api\/client["']/);
    expect(shellSource).toMatch(/from\s+["']\.\.\/api\/clientContext["']/);
    expect(shellSource).not.toMatch(/from\s+["']\.\.\/api\/client["']/);
    expect(dataModeRibbonSource).toMatch(/from\s+["']\.\.\/api\/clientContext["']/);
    expect(dataModeRibbonSource).not.toMatch(/from\s+["']\.\.\/api\/client["']/);
    expect(clientContextSource).toContain("createDeferredApiClient");
    expect(clientContextSource).not.toMatch(/import\s+\{[^}]*createApiClient/);
    expect(clientSource).toContain("from \"./clientContext\"");
  });
});
