import type { ApiClient } from "./client";
import type { BalanceCurrencyBasis, BalancePositionScope } from "./contracts";

type PnlByBusinessAnalysisDimension =
  Parameters<ApiClient["getPnlByBusinessAnalysis"]>[0]["dimension"];

const normalizeReportDate = (reportDate: string | null | undefined) =>
  reportDate?.trim() || "pending-snapshot";

export const apiQueryKeys = {
  marketRates: (mode: string, reportDate?: string | null) =>
    ["market-data", "formal-rates", mode, normalizeReportDate(reportDate)] as const,
  bondDashboardHeadline: (mode: string, reportDate: string | null | undefined) =>
    ["bond-dashboard", "headline", mode, normalizeReportDate(reportDate)] as const,
  bondAnalyticsPortfolioHeadlines: (mode: string, reportDate: string | null | undefined) =>
    ["bond-analytics", "portfolio-headlines", mode, normalizeReportDate(reportDate)] as const,
  bondAnalyticsDv01Risk: (
    mode: string,
    reportDate: string | null | undefined,
    accountingClass: string,
    topN: number,
    shockBps: string,
  ) =>
    [
      "bond-analytics",
      "dv01-risk",
      mode,
      normalizeReportDate(reportDate),
      accountingClass,
      topN,
      shockBps,
    ] as const,
  bondDashboardPortfolioComparison: (mode: string, reportDate: string | null | undefined) =>
    ["bond-dashboard", "portfolio-comparison", mode, normalizeReportDate(reportDate)] as const,
  bondDashboardAssetStructure: (
    mode: string,
    reportDate: string | null | undefined,
    groupBy: string,
  ) =>
    [
      "bond-dashboard",
      "asset-structure",
      mode,
      normalizeReportDate(reportDate),
      groupBy,
    ] as const,
  bondAnalyticsTopHoldings: (
    mode: string,
    reportDate: string | null | undefined,
    topN: number,
  ) =>
    [
      "bond-analytics",
      "top-holdings",
      mode,
      normalizeReportDate(reportDate),
      topN,
    ] as const,
  bondAnalyticsPositionChanges: (
    mode: string,
    reportDate: string | null | undefined,
    topN: number,
  ) =>
    [
      "bond-analytics",
      "position-changes",
      mode,
      normalizeReportDate(reportDate),
      topN,
    ] as const,
  homeResearchReports: (
    mode: string,
    reportDate: string | null | undefined,
    limit: number,
  ) =>
    [
      "home",
      "research-reports",
      mode,
      normalizeReportDate(reportDate),
      limit,
    ] as const,
  homeIncomeTrend: (
    mode: string,
    reportDate: string | null | undefined,
    window: number,
  ) =>
    [
      "home",
      "income-trend",
      mode,
      normalizeReportDate(reportDate),
      window,
    ] as const,
  bondDashboardMaturityStructure: (mode: string, reportDate: string | null | undefined) =>
    ["bond-dashboard", "maturity-structure", mode, normalizeReportDate(reportDate)] as const,
  bondDashboardIndustryDistribution: (mode: string, reportDate: string | null | undefined) =>
    ["bond-dashboard", "industry-distribution", mode, normalizeReportDate(reportDate)] as const,
  bondDashboardRiskIndicators: (mode: string, reportDate: string | null | undefined) =>
    ["bond-dashboard", "risk-indicators", mode, normalizeReportDate(reportDate)] as const,
  bondAnalyticsCreditSpreadMigration: (
    mode: string,
    reportDate: string | null | undefined,
    spreadScenarios = "10,25,50",
  ) =>
    [
      "bond-analytics",
      "credit-spread-migration",
      mode,
      normalizeReportDate(reportDate),
      spreadScenarios,
    ] as const,
  balanceAnalysisDecisionItems: (
    mode: string,
    reportDate: string | null | undefined,
    positionScope: BalancePositionScope,
    currencyBasis: BalanceCurrencyBasis,
  ) =>
    [
      "balance-analysis",
      "decision-items",
      mode,
      normalizeReportDate(reportDate),
      positionScope,
      currencyBasis,
    ] as const,
  pnlByBusinessAnalysis: (
    mode: string,
    year: number | string,
    reportDate: string | null | undefined,
    dimension: PnlByBusinessAnalysisDimension,
    businessKey?: string | null,
  ) =>
    [
      "pnl-by-business",
      "analysis",
      mode,
      year,
      normalizeReportDate(reportDate),
      businessKey ?? null,
      dimension,
    ] as const,
};
