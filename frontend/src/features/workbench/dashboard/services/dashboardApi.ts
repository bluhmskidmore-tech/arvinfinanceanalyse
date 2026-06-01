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
  | "getBondAnalyticsReturnDecomposition"
  | "getBondAnalyticsYieldCurveTermStructure"
  | "getPnlCampisiFourEffects"
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

export function getReturnDecompositionContext(
  client: DashboardApiClient,
  reportDate: string,
) {
  return client.getBondAnalyticsReturnDecomposition(reportDate, "MoM", {
    assetClass: "all",
    accountingClass: "all",
  });
}

export function getCampisiAttributionContext(
  client: DashboardApiClient,
  reportDate: string,
) {
  return client.getPnlCampisiFourEffects({
    endDate: reportDate,
    lookbackDays: 30,
  });
}

export function getYieldCurveContext(
  client: DashboardApiClient,
  reportDate: string,
) {
  return client.getBondAnalyticsYieldCurveTermStructure(reportDate, {
    curveTypes: "treasury,cdb,aaa_credit",
  });
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
