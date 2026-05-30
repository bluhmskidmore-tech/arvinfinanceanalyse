import { useQuery } from "@tanstack/react-query";

import type { ApiClient } from "../../../../api/client";
import { apiQueryKeys } from "../../../../api/queryKeys";
import type { DashboardResearchCalendarQueryResult } from "../../pages/useDashboardResearchCalendarQuery";
import { useDashboardResearchCalendarQuery } from "../../pages/useDashboardResearchCalendarQuery";
import {
  getAssetIncomeOverview,
  getBondBucketYield,
  getCreditRiskOverview,
  getDashboardDailyChanges,
  getDashboardOverview,
  getExposureSummary,
  getMarketTape,
  getPortfolioHeadlines,
  getProductPnlTrend,
  getRiskControlOverview,
  type DashboardSupplementPeriod,
} from "../services/dashboardApi";

export type UseDashboardDataOptions = {
  dataClient: ApiClient;
  supplementalReportDate: string | undefined;
  effectiveReportDate: string;
  loadCalendarData: boolean;
  loadBondBucketYieldData: boolean;
  loadBondBucketMonthlyData: boolean;
  loadPortfolioSupplementData: boolean;
  loadDecisionItemsData: boolean;
  productPnlPeriod?: DashboardSupplementPeriod;
};

export function useDashboardData({
  dataClient,
  supplementalReportDate,
  effectiveReportDate,
  loadCalendarData,
  loadBondBucketYieldData,
  loadBondBucketMonthlyData,
  loadPortfolioSupplementData,
  loadDecisionItemsData,
  productPnlPeriod = "month",
}: UseDashboardDataOptions) {
  const bondBucketAnalysisYear = Number.parseInt((supplementalReportDate ?? "").slice(0, 4), 10);
  const hasSupplementalReportDate = Boolean(supplementalReportDate);
  const hasBondBucketYear = Number.isFinite(bondBucketAnalysisYear);

  const coreMetricsQuery = useQuery({
    queryKey: ["dashboard", "core-metrics", dataClient.mode, supplementalReportDate ?? "pending-snapshot"],
    queryFn: () => getDashboardOverview(dataClient, supplementalReportDate ?? ""),
    retry: false,
    staleTime: 60_000,
    enabled: hasSupplementalReportDate,
  });

  const dailyChangesQuery = useQuery({
    queryKey: ["dashboard", "daily-changes", dataClient.mode, supplementalReportDate ?? "pending-snapshot"],
    queryFn: () => getDashboardDailyChanges(dataClient, supplementalReportDate ?? ""),
    retry: false,
    staleTime: 60_000,
    enabled: hasSupplementalReportDate,
  });

  const marketRatesQuery = useQuery({
    queryKey: apiQueryKeys.marketRates(dataClient.mode, supplementalReportDate),
    queryFn: () => getMarketTape(dataClient),
    retry: false,
    staleTime: 60_000,
  });

  const bondHeadlineQuery = useQuery({
    queryKey: apiQueryKeys.bondDashboardHeadline(dataClient.mode, supplementalReportDate),
    queryFn: () => getAssetIncomeOverview(dataClient, supplementalReportDate ?? ""),
    retry: false,
    staleTime: 60_000,
    enabled: hasSupplementalReportDate,
  });

  const portfolioHeadlinesQuery = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsPortfolioHeadlines(dataClient.mode, supplementalReportDate),
    queryFn: () => getPortfolioHeadlines(dataClient, supplementalReportDate ?? ""),
    retry: false,
    staleTime: 60_000,
    enabled: hasSupplementalReportDate,
  });

  const portfolioComparisonQuery = useQuery({
    queryKey: apiQueryKeys.bondDashboardPortfolioComparison(dataClient.mode, supplementalReportDate),
    queryFn: () => getExposureSummary(dataClient, supplementalReportDate ?? ""),
    retry: false,
    staleTime: 60_000,
    enabled: loadPortfolioSupplementData && hasSupplementalReportDate,
  });

  const creditSpreadMigrationQuery = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsCreditSpreadMigration(dataClient.mode, supplementalReportDate),
    queryFn: () => getCreditRiskOverview(dataClient, supplementalReportDate ?? ""),
    retry: false,
    staleTime: 60_000,
    enabled: loadPortfolioSupplementData && hasSupplementalReportDate,
  });

  const bondBucketYieldQuery = useQuery({
    queryKey: apiQueryKeys.pnlByBusinessAnalysis(
      dataClient.mode,
      hasBondBucketYear ? bondBucketAnalysisYear : "pending-year",
      supplementalReportDate,
      "bond_bucket",
    ),
    queryFn: () =>
      getBondBucketYield(dataClient, supplementalReportDate ?? "", bondBucketAnalysisYear),
    retry: false,
    staleTime: 60_000,
    enabled: loadBondBucketYieldData && hasSupplementalReportDate && hasBondBucketYear,
  });

  const bondBucketMonthlyTrendQuery = useQuery({
    queryKey: [
      ...apiQueryKeys.pnlByBusinessAnalysis(
        dataClient.mode,
        hasBondBucketYear ? bondBucketAnalysisYear : "pending-year",
        supplementalReportDate,
        "bond_bucket_monthly",
      ),
      productPnlPeriod,
    ],
    queryFn: () =>
      getProductPnlTrend(
        dataClient,
        supplementalReportDate ?? "",
        bondBucketAnalysisYear,
        productPnlPeriod,
      ),
    retry: false,
    staleTime: 60_000,
    enabled:
      hasSupplementalReportDate &&
      hasBondBucketYear &&
      loadBondBucketMonthlyData &&
      dataClient.mode === "real",
  });

  const decisionItemsQuery = useQuery({
    queryKey: apiQueryKeys.balanceAnalysisDecisionItems(
      dataClient.mode,
      effectiveReportDate,
      "all",
      "CNY",
    ),
    queryFn: () => getRiskControlOverview(dataClient, effectiveReportDate),
    retry: false,
    staleTime: 60_000,
    enabled: loadDecisionItemsData && Boolean(effectiveReportDate),
  });

  const researchCalendar = useDashboardResearchCalendarQuery({
    dataClient,
    enabled: loadCalendarData,
  });

  return {
    coreMetricsQuery,
    dailyChangesQuery,
    marketRatesQuery,
    bondHeadlineQuery,
    portfolioHeadlinesQuery,
    portfolioComparisonQuery,
    creditSpreadMigrationQuery,
    bondBucketYieldQuery,
    bondBucketMonthlyTrendQuery,
    decisionItemsQuery,
    researchCalendarQuery: researchCalendar.researchCalendarQuery,
    calendarStartDate: researchCalendar.calendarStartDate,
    calendarEndDate: researchCalendar.calendarEndDate,
  } satisfies DashboardResearchCalendarQueryResult & {
    coreMetricsQuery: typeof coreMetricsQuery;
    dailyChangesQuery: typeof dailyChangesQuery;
    marketRatesQuery: typeof marketRatesQuery;
    bondHeadlineQuery: typeof bondHeadlineQuery;
    portfolioHeadlinesQuery: typeof portfolioHeadlinesQuery;
    portfolioComparisonQuery: typeof portfolioComparisonQuery;
    creditSpreadMigrationQuery: typeof creditSpreadMigrationQuery;
    bondBucketYieldQuery: typeof bondBucketYieldQuery;
    bondBucketMonthlyTrendQuery: typeof bondBucketMonthlyTrendQuery;
    decisionItemsQuery: typeof decisionItemsQuery;
  };
}

