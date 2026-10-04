import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { apiQueryKeys } from "../../../api/queryKeys";
import { todayIsoDate } from "../pages/dashboardPageHelpers";
import { DASHBOARD_HOME_CONTENT_REFETCH_INTERVAL_MS } from "../dashboard/dashboardMacroNewsTopics";
import { mapToHomeBodyView } from "./dashboardHomeBodyView";
import { useDashboardHomeBodyData } from "./useDashboardHomeBodyData";
import { useDashboardHomeMacroReleaseContextQuery } from "./useDashboardHomeMacroReleaseContextQuery";
import type { DashboardHomeSnapshotBoundary } from "./useDashboardHomeFirstScreenViewModel";

export type DashboardHomeSection = "holdings" | "risk" | "market" | "support" | "evidence";
export type DashboardHomeSections = Record<DashboardHomeSection, boolean>;

const ALL_HOME_SECTIONS: DashboardHomeSections = {
  holdings: true, risk: true, market: true, support: true, evidence: true,
};
const HOME_TOP_HOLDINGS_FETCH_LIMIT = 14;

function useLocalTodayIsoDate(): string {
  const [localDate, setLocalDate] = useState(todayIsoDate);

  useEffect(() => {
    let nextDayTimer: number | undefined;
    const refreshDate = () => {
      if (nextDayTimer !== undefined) window.clearTimeout(nextDayTimer);
      const now = new Date();
      setLocalDate(todayIsoDate());
      const nextMidnight = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
      nextDayTimer = window.setTimeout(refreshDate, Math.max(1, nextMidnight.getTime() - now.getTime()));
    };

    refreshDate();
    window.addEventListener("focus", refreshDate);
    document.addEventListener("visibilitychange", refreshDate);
    return () => {
      if (nextDayTimer !== undefined) window.clearTimeout(nextDayTimer);
      window.removeEventListener("focus", refreshDate);
      document.removeEventListener("visibilitychange", refreshDate);
    };
  }, []);

  return localDate;
}

export function useDashboardHomeViewModel(
  snapshotBoundary: DashboardHomeSnapshotBoundary,
  options: { sections?: DashboardHomeSections } = {},
) {
  const {
    dataClient,
    snapshotQuery,
    adapterOutput,
    snapshotResult,
    initialEffectiveReportDate,
    supplementalReportDate,
  } = snapshotBoundary;

  // real 模式不允许任何 mock UI 可达路径：useMockFallback 只看数据源模式，
  // 不再挂接 isLiveDataFallback 之类的运行时回退信号。
  const useMockFallback = dataClient.mode !== "real";
  const snapshotReportDate = snapshotResult?.report_date?.trim() || "";
  const hasSupplementalReportDate = Boolean(supplementalReportDate);
  const sections = options.sections ?? ALL_HOME_SECTIONS;
  // Body queries follow the section the reader has reached, not elapsed idle
  // timers. The snapshot report date still owns every dated query key.
  const hasDeferredSupplementalReportDate = hasSupplementalReportDate;
  const hasHoldingsData = hasSupplementalReportDate && sections.holdings;
  const hasMarketData = hasSupplementalReportDate && (sections.market || sections.support);
  const hasEvidenceData = hasSupplementalReportDate && sections.evidence;
  const hasDeferredFormalContext = hasSupplementalReportDate && sections.support;
  const dashboardTodayIsoDate = useLocalTodayIsoDate();

  const {
    marketRatesQuery,
    creditSpreadMigrationQuery,
    returnDecompositionQuery,
    campisiFourEffectsQuery,
    yieldCurveTermStructureQuery,
    researchCalendarQuery,
    macroNewsQueries,
    macroNewsFallbackQueries,
    bondNewsQueries,
    calendarStartDate,
    calendarEndDate,
  } = useDashboardHomeBodyData({
    dataClient,
    supplementalReportDate,
    loadBasicData: hasMarketData,
    loadEventFeeds: hasEvidenceData,
    loadSecondaryEventFeeds: hasEvidenceData,
    loadBondNewsFeeds: hasEvidenceData,
    loadFormalData: hasDeferredFormalContext,
  });

  const homeSummaryQuery = useQuery({
    queryKey: apiQueryKeys.bondDashboardHomeSummary(dataClient.mode, supplementalReportDate),
    queryFn: () => dataClient.getBondDashboardHomeSummary(supplementalReportDate ?? ""),
    retry: false,
    staleTime: 60_000,
    enabled: hasDeferredSupplementalReportDate,
  });

  const topHoldingsQuery = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsTopHoldings(dataClient.mode, supplementalReportDate, HOME_TOP_HOLDINGS_FETCH_LIMIT),
    queryFn: () => dataClient.getBondAnalyticsTopHoldings(supplementalReportDate ?? "", HOME_TOP_HOLDINGS_FETCH_LIMIT),
    retry: false,
    staleTime: 60_000,
    enabled: hasHoldingsData,
  });

  const positionChangesQuery = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsPositionChanges(dataClient.mode, supplementalReportDate, 5),
    queryFn: () => dataClient.getBondAnalyticsPositionChanges(supplementalReportDate ?? "", 5),
    retry: false,
    staleTime: 60_000,
    enabled: hasHoldingsData,
  });

  const researchReportsQuery = useQuery({
    queryKey: apiQueryKeys.homeResearchReports(dataClient.mode, dashboardTodayIsoDate, 5),
    queryFn: () => dataClient.getHomeResearchReports(dashboardTodayIsoDate, 5),
    retry: false,
    staleTime: 60_000,
    refetchInterval: DASHBOARD_HOME_CONTENT_REFETCH_INTERVAL_MS,
    refetchIntervalInBackground: false,
    // Focus after midnight must not refetch yesterday's cache key before the date state updates.
    refetchOnWindowFocus: () => todayIsoDate() === dashboardTodayIsoDate,
    enabled: hasSupplementalReportDate && sections.market,
  });

  const incomeTrendQuery = useQuery({
    queryKey: apiQueryKeys.homeIncomeTrend(dataClient.mode, supplementalReportDate, 7),
    queryFn: () => dataClient.getHomeIncomeTrend(supplementalReportDate ?? "", 7),
    // 保留对后端重启/代理瞬断的重试；可见区块失败后仍展示错误态。
    // 两次指数退避重试吸收瞬态失败，持续失败仍诚实落错误态。
    retry: 2,
    retryDelay: (attempt) => Math.min(1_000 * 2 ** attempt, 8_000),
    refetchOnWindowFocus: true,
    staleTime: 60_000,
    enabled: hasHoldingsData,
  });

  const krdCurveRiskQuery = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsKrdCurveRisk(dataClient.mode, supplementalReportDate),
    queryFn: () => dataClient.getBondAnalyticsKrdCurveRisk(supplementalReportDate ?? ""),
    retry: false,
    staleTime: 60_000,
    enabled: hasDeferredFormalContext,
  });

  // 待复核事项走余额分析域：日期取该域最新报告日，与债券报告日分属两个口径。
  const decisionItemsGateOpen = hasSupplementalReportDate && sections.risk;
  const balanceDatesQuery = useQuery({
    queryKey: apiQueryKeys.balanceAnalysisDates(dataClient.mode),
    queryFn: () => dataClient.getBalanceAnalysisDates(),
    retry: false,
    staleTime: 60_000,
    enabled: decisionItemsGateOpen,
  });
  const latestBalanceReportDate = useMemo(() => {
    const dates = balanceDatesQuery.data?.result?.report_dates ?? [];
    return dates.length > 0 ? [...dates].sort((a, b) => a.localeCompare(b)).at(-1) ?? null : null;
  }, [balanceDatesQuery.data?.result?.report_dates]);
  const decisionItemsQuery = useQuery({
    queryKey: apiQueryKeys.balanceAnalysisDecisionItems(
      dataClient.mode,
      latestBalanceReportDate,
      "all",
      "CNY",
    ),
    queryFn: () =>
      dataClient.getBalanceAnalysisDecisionItems({
        reportDate: latestBalanceReportDate ?? "",
        positionScope: "all",
        currencyBasis: "CNY",
      }),
    retry: false,
    staleTime: 60_000,
    enabled: decisionItemsGateOpen && Boolean(latestBalanceReportDate),
  });

  const { macroReleaseContextQuery } = useDashboardHomeMacroReleaseContextQuery({
    dataClient,
    enabled: hasEvidenceData,
  });

  const macroNewsEvents = useMemo(
    () => macroNewsQueries.flatMap((query) => query.data?.result.events ?? []),
    [macroNewsQueries],
  );
  const macroNewsFallbackEvents = useMemo(
    () => macroNewsFallbackQueries.flatMap((query) => query.data?.result.events ?? []),
    [macroNewsFallbackQueries],
  );
  const bondNewsEvents = useMemo(
    () => [
      ...macroNewsFallbackEvents,
      ...bondNewsQueries.flatMap((query) => query.data?.result.events ?? []),
    ],
    [bondNewsQueries, macroNewsFallbackEvents],
  );
  const bondNewsPayloads = useMemo(
    () => [
      ...macroNewsFallbackQueries.flatMap((query) =>
        query.data?.result ? [query.data.result] : [],
      ),
      ...bondNewsQueries.flatMap((query) =>
        query.data?.result ? [query.data.result] : [],
      ),
    ],
    [bondNewsQueries, macroNewsFallbackQueries],
  );
  const macroNewsLoading =
    (hasSupplementalReportDate && !hasEvidenceData) ||
    macroNewsQueries.some((query) => query.isLoading) ||
    macroNewsFallbackQueries.some((query) => query.isLoading);
  const macroNewsError =
    macroNewsQueries.length > 0 &&
    macroNewsFallbackQueries.length > 0 &&
    macroNewsQueries.every((query) => query.isError) &&
    macroNewsFallbackQueries.every((query) => query.isError);

  const effectiveReportDate = snapshotReportDate || initialEffectiveReportDate;
  const view = useMemo(
    () =>
      mapToHomeBodyView({
        reportDate: effectiveReportDate,
        useMockFallback,
        overviewMetrics: adapterOutput.overview?.vm?.metrics ?? null,
        attribution: adapterOutput.attribution.vm,
        creditSpreadMigration: creditSpreadMigrationQuery.data?.result ?? null,
        returnDecomposition: returnDecompositionQuery.data?.result ?? null,
        campisiFourEffects: campisiFourEffectsQuery.data?.result ?? null,
        campisiRequested: hasDeferredFormalContext,
        campisiLoading: campisiFourEffectsQuery.isLoading,
        campisiError: campisiFourEffectsQuery.isError,
        campisiFormalUseAllowed:
          campisiFourEffectsQuery.data?.result_meta.formal_use_allowed ?? null,
        campisiResultMeta: campisiFourEffectsQuery.data?.result_meta ?? null,
        yieldCurveTermStructure: yieldCurveTermStructureQuery.data?.result ?? null,
        marketPoints: marketRatesQuery.data?.result.series ?? null,
        assetStructure: homeSummaryQuery.data?.result.asset_type ?? null,
        ratingStructure: homeSummaryQuery.data?.result.asset_rating ?? null,
        maturityStructure: homeSummaryQuery.data?.result.maturity ?? null,
        industryDistribution: homeSummaryQuery.data?.result.industry ?? null,
        homeSummaryMeta: homeSummaryQuery.data?.result_meta ?? null,
        homeSummaryLoading:
          hasDeferredSupplementalReportDate &&
          !homeSummaryQuery.data &&
          !homeSummaryQuery.isError,
        homeSummaryError: homeSummaryQuery.isError,
        yieldDistribution: homeSummaryQuery.data?.result.yield_distribution ?? null,
        portfolioComparison: homeSummaryQuery.data?.result.portfolio_comparison ?? null,
        spreadAnalysis: homeSummaryQuery.data?.result.spread ?? null,
        businessType: homeSummaryQuery.data?.result.business_type ?? null,
        riskIndicators: homeSummaryQuery.data?.result.risk ?? null,
        topHoldings: topHoldingsQuery.data?.result ?? null,
        topHoldingsLoading: hasSupplementalReportDate && topHoldingsQuery.isPending,
        topHoldingsError: topHoldingsQuery.isError,
        positionChanges: positionChangesQuery.data?.result ?? null,
        positionChangesLoading: hasSupplementalReportDate && positionChangesQuery.isPending,
        positionChangesError: positionChangesQuery.isError,
        researchReports: researchReportsQuery.data?.result ?? null,
        researchReportsLoading: hasSupplementalReportDate && researchReportsQuery.isPending,
        researchReportsError: researchReportsQuery.isError,
        incomeTrend: incomeTrendQuery.data?.result ?? null,
        incomeTrendLoading: hasSupplementalReportDate && incomeTrendQuery.isPending,
        incomeTrendError: incomeTrendQuery.isError,
        krdCurveRisk: krdCurveRiskQuery.data?.result ?? null,
        krdLoading: hasSupplementalReportDate && krdCurveRiskQuery.isPending,
        krdError: krdCurveRiskQuery.isError,
        decisionItems: decisionItemsQuery.data?.result ?? null,
        decisionItemsLoading:
          hasSupplementalReportDate && (balanceDatesQuery.isPending ||
            (Boolean(latestBalanceReportDate) && decisionItemsQuery.isPending)),
        decisionItemsError:
          balanceDatesQuery.isError || decisionItemsQuery.isError,
        calendarEvents: researchCalendarQuery.data ?? null,
        calendarLoading: hasSupplementalReportDate && researchCalendarQuery.isPending,
        calendarError: researchCalendarQuery.isError,
        calendarStartDate,
        calendarEndDate,
        todayIsoDate: dashboardTodayIsoDate,
        macroNewsEvents,
        macroNewsFallbackEvents,
        bondNewsEvents,
        bondNewsPayloads,
        macroNewsLoading,
        macroNewsError,
        macroReleaseContext: macroReleaseContextQuery.data?.result ?? null,
        macroReleaseContextLoading:
          hasDeferredSupplementalReportDate && !macroReleaseContextQuery.data && !macroReleaseContextQuery.isError,
        macroReleaseContextError: macroReleaseContextQuery.isError,
      }),
    [
      adapterOutput.attribution.vm,
      adapterOutput.overview?.vm?.metrics,
      bondNewsEvents,
      bondNewsPayloads,
      creditSpreadMigrationQuery.data?.result,
      effectiveReportDate,
      marketRatesQuery.data?.result.series,
      returnDecompositionQuery.data?.result,
      campisiFourEffectsQuery.data?.result,
      campisiFourEffectsQuery.data?.result_meta,
      campisiFourEffectsQuery.isLoading,
      campisiFourEffectsQuery.isError,
      hasDeferredFormalContext,
      hasDeferredSupplementalReportDate,
      hasSupplementalReportDate,
      latestBalanceReportDate,
      homeSummaryQuery.data,
      homeSummaryQuery.isError,
      topHoldingsQuery.data?.result,
      topHoldingsQuery.isPending,
      topHoldingsQuery.isError,
      positionChangesQuery.data?.result,
      positionChangesQuery.isPending,
      positionChangesQuery.isError,
      researchReportsQuery.data?.result,
      researchReportsQuery.isPending,
      researchReportsQuery.isError,
      incomeTrendQuery.data?.result,
      incomeTrendQuery.isPending,
      incomeTrendQuery.isError,
      krdCurveRiskQuery.data?.result,
      krdCurveRiskQuery.isPending,
      krdCurveRiskQuery.isError,
      balanceDatesQuery.isPending,
      balanceDatesQuery.isError,
      decisionItemsQuery.data?.result,
      decisionItemsQuery.isPending,
      decisionItemsQuery.isError,
      yieldCurveTermStructureQuery.data?.result,
      calendarEndDate,
      calendarStartDate,
      dashboardTodayIsoDate,
      macroNewsError,
      macroNewsEvents,
      macroNewsFallbackEvents,
      macroNewsLoading,
      macroReleaseContextQuery.data,
      macroReleaseContextQuery.isError,
      researchCalendarQuery.data,
      researchCalendarQuery.isError,
      researchCalendarQuery.isPending,
      useMockFallback,
    ],
  );

  return {
    view,
    newsLoading: {
      macro: macroNewsLoading,
      bond: (hasSupplementalReportDate && !hasEvidenceData) ||
        bondNewsQueries.some((query) => query.isLoading),
    },
    snapshotQuery,
    effectiveReportDate,
  };
}
