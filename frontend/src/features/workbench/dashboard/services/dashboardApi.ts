import type { ApiClient } from "../../../../api/client";

export type DashboardSupplementPeriod = "day" | "week" | "month" | "ytd";

export type DashboardApiClient = Pick<
  ApiClient,
  | "mode"
  | "getCoreMetrics"
  | "getDailyChanges"
  | "getMarketDataRates"
  | "getBondDashboardHeadlineKpis"
  | "getBondAnalyticsPortfolioHeadlines"
  | "getBondDashboardPortfolioComparison"
  | "getBondAnalyticsCreditSpreadMigration"
  | "getPnlByBusinessAnalysis"
  | "getBalanceAnalysisDecisionItems"
  | "getResearchCalendarEvents"
>;

export function getDashboardOverview(
  client: DashboardApiClient,
  reportDate: string,
) {
  return client.getCoreMetrics({ reportDate });
}

export function getDashboardDailyChanges(
  client: DashboardApiClient,
  reportDate: string,
) {
  return client.getDailyChanges({ reportDate });
}

export function getMarketTape(client: DashboardApiClient) {
  return client.getMarketDataRates();
}

export function getAssetIncomeOverview(
  client: DashboardApiClient,
  reportDate: string,
) {
  return client.getBondDashboardHeadlineKpis(reportDate);
}

export function getPortfolioHeadlines(
  client: DashboardApiClient,
  reportDate: string,
) {
  return client.getBondAnalyticsPortfolioHeadlines(reportDate);
}

export function getExposureSummary(
  client: DashboardApiClient,
  reportDate: string,
) {
  return client.getBondDashboardPortfolioComparison(reportDate);
}

export function getCreditRiskOverview(
  client: DashboardApiClient,
  reportDate: string,
) {
  return client.getBondAnalyticsCreditSpreadMigration(reportDate);
}

export function getBondBucketYield(
  client: DashboardApiClient,
  reportDate: string,
  year: number,
) {
  return client.getPnlByBusinessAnalysis({
    year,
    asOfDate: reportDate,
    dimension: "bond_bucket",
  });
}

export function getProductPnlTrend(
  client: DashboardApiClient,
  reportDate: string,
  year: number,
  _period: DashboardSupplementPeriod,
) {
  return client.getPnlByBusinessAnalysis({
    year,
    asOfDate: reportDate,
    dimension: "bond_bucket_monthly",
  });
}

export function getRiskControlOverview(
  client: DashboardApiClient,
  reportDate: string,
) {
  return client.getBalanceAnalysisDecisionItems({
    reportDate,
    positionScope: "all",
    currencyBasis: "CNY",
  });
}

