import type { ApiClient } from "./client";
import type { BalanceCurrencyBasis, BalancePositionScope } from "./contracts";

type PnlByBusinessAnalysisDimension =
  Parameters<ApiClient["getPnlByBusinessAnalysis"]>[0]["dimension"];

const normalizeReportDate = (reportDate: string | null | undefined) =>
  reportDate?.trim() || "pending-snapshot";

export const apiQueryKeys = {
  marketRates: (mode: string) => ["market-data", "formal-rates", mode] as const,
  bondDashboardHeadline: (mode: string, reportDate: string | null | undefined) =>
    ["bond-dashboard", "headline", mode, normalizeReportDate(reportDate)] as const,
  bondAnalyticsPortfolioHeadlines: (mode: string, reportDate: string | null | undefined) =>
    ["bond-analytics", "portfolio-headlines", mode, normalizeReportDate(reportDate)] as const,
  bondDashboardPortfolioComparison: (mode: string, reportDate: string | null | undefined) =>
    ["bond-dashboard", "portfolio-comparison", mode, normalizeReportDate(reportDate)] as const,
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
