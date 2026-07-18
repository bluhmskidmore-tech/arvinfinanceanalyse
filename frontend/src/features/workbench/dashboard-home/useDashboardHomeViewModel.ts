import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { apiQueryKeys } from "../../../api/queryKeys";
import { todayIsoDate } from "../pages/dashboardPageHelpers";
import { mapToHomeBodyView } from "./dashboardHomeBodyView";
import { useDashboardHomeBodyData } from "./useDashboardHomeBodyData";
import { useDashboardHomeMacroReleaseContextQuery } from "./useDashboardHomeMacroReleaseContextQuery";
import type { DashboardHomeSnapshotBoundary } from "./useDashboardHomeFirstScreenViewModel";

type IdleWindow = Window & {
  requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number;
  cancelIdleCallback?: (handle: number) => void;
};

// Each body tier still gates its requests behind the snapshot's supplemental
// report date (so first-screen paint keeps priority), but the per-tier delay
// is kept small: these tiers chain (body detail -> body structure, and event
// feed -> secondary event feed -> bond news feed), and the previous 1000ms-per
// -tier values compounded into multi-second waits before body content (and
// especially bond news) appeared. 150ms still yields a tick to the browser
// between tiers without stacking into a multi-second perceived load time.
const BODY_DETAIL_IDLE_MIN_DELAY_MS = 150;
const BODY_DETAIL_IDLE_TIMEOUT_MS = 250;
const BODY_DETAIL_TIMEOUT_FALLBACK_MS = 200;
const BODY_STRUCTURE_IDLE_MIN_DELAY_MS = 150;
const BODY_STRUCTURE_IDLE_TIMEOUT_MS = 250;
const BODY_STRUCTURE_TIMEOUT_FALLBACK_MS = 200;
const EVENT_FEED_IDLE_MIN_DELAY_MS = 150;
const EVENT_FEED_IDLE_TIMEOUT_MS = 250;
const EVENT_FEED_TIMEOUT_FALLBACK_MS = 200;
const SECONDARY_EVENT_FEED_IDLE_MIN_DELAY_MS = 150;
const SECONDARY_EVENT_FEED_IDLE_TIMEOUT_MS = 250;
const SECONDARY_EVENT_FEED_TIMEOUT_FALLBACK_MS = 200;
const BOND_NEWS_FEED_IDLE_MIN_DELAY_MS = 150;
const BOND_NEWS_FEED_IDLE_TIMEOUT_MS = 250;
const BOND_NEWS_FEED_TIMEOUT_FALLBACK_MS = 200;
const FORMAL_CONTEXT_IDLE_MIN_DELAY_MS = 150;
const FORMAL_CONTEXT_IDLE_TIMEOUT_MS = 250;
const FORMAL_CONTEXT_TIMEOUT_FALLBACK_MS = 200;
const HOME_TOP_HOLDINGS_FETCH_LIMIT = 14;

function useDeferredReportDateGate(
  reportDate: string | undefined,
  timing: {
    minDelayMs: number;
    idleTimeoutMs: number;
    timeoutFallbackMs: number;
  },
) {
  const [readyReportDate, setReadyReportDate] = useState<string | null>(null);

  useEffect(() => {
    setReadyReportDate(null);
    if (!reportDate) {
      return undefined;
    }

    let isActive = true;
    const idleWindow = window as IdleWindow;
    let idleHandle: number | null = null;
    let timeoutHandle: number | null = null;
    let delayHandle: number | null = null;
    const cancelScheduledWork = () => {
      if (idleHandle != null) {
        idleWindow.cancelIdleCallback?.(idleHandle);
        idleHandle = null;
      }
      if (timeoutHandle != null) {
        window.clearTimeout(timeoutHandle);
        timeoutHandle = null;
      }
      if (delayHandle != null) {
        window.clearTimeout(delayHandle);
        delayHandle = null;
      }
    };
    const markReady = () => {
      if (isActive) {
        cancelScheduledWork();
        setReadyReportDate(reportDate);
      }
    };
    const scheduleReady = () => {
      if (!isActive) {
        return;
      }
      if (idleWindow.requestIdleCallback) {
        idleHandle = idleWindow.requestIdleCallback(markReady, {
          timeout: timing.idleTimeoutMs,
        });
        return;
      }
      timeoutHandle = window.setTimeout(markReady, timing.timeoutFallbackMs);
    };
    delayHandle = window.setTimeout(scheduleReady, timing.minDelayMs);

    return () => {
      isActive = false;
      cancelScheduledWork();
    };
  }, [reportDate, timing.idleTimeoutMs, timing.minDelayMs, timing.timeoutFallbackMs]);

  return readyReportDate === reportDate;
}

function useBodyDetailDataGate(reportDate: string | undefined) {
  return useDeferredReportDateGate(reportDate, {
    minDelayMs: BODY_DETAIL_IDLE_MIN_DELAY_MS,
    idleTimeoutMs: BODY_DETAIL_IDLE_TIMEOUT_MS,
    timeoutFallbackMs: BODY_DETAIL_TIMEOUT_FALLBACK_MS,
  });
}

function useEventFeedDataGate(reportDate: string | undefined) {
  return useDeferredReportDateGate(reportDate, {
    minDelayMs: EVENT_FEED_IDLE_MIN_DELAY_MS,
    idleTimeoutMs: EVENT_FEED_IDLE_TIMEOUT_MS,
    timeoutFallbackMs: EVENT_FEED_TIMEOUT_FALLBACK_MS,
  });
}

function useBodyStructureDataGate(reportDate: string | undefined) {
  return useDeferredReportDateGate(reportDate, {
    minDelayMs: BODY_STRUCTURE_IDLE_MIN_DELAY_MS,
    idleTimeoutMs: BODY_STRUCTURE_IDLE_TIMEOUT_MS,
    timeoutFallbackMs: BODY_STRUCTURE_TIMEOUT_FALLBACK_MS,
  });
}

function useSecondaryEventFeedDataGate(reportDate: string | undefined) {
  return useDeferredReportDateGate(reportDate, {
    minDelayMs: SECONDARY_EVENT_FEED_IDLE_MIN_DELAY_MS,
    idleTimeoutMs: SECONDARY_EVENT_FEED_IDLE_TIMEOUT_MS,
    timeoutFallbackMs: SECONDARY_EVENT_FEED_TIMEOUT_FALLBACK_MS,
  });
}

function useBondNewsFeedDataGate(reportDate: string | undefined) {
  return useDeferredReportDateGate(reportDate, {
    minDelayMs: BOND_NEWS_FEED_IDLE_MIN_DELAY_MS,
    idleTimeoutMs: BOND_NEWS_FEED_IDLE_TIMEOUT_MS,
    timeoutFallbackMs: BOND_NEWS_FEED_TIMEOUT_FALLBACK_MS,
  });
}

function useFormalContextDataGate(reportDate: string | undefined) {
  return useDeferredReportDateGate(reportDate, {
    minDelayMs: FORMAL_CONTEXT_IDLE_MIN_DELAY_MS,
    idleTimeoutMs: FORMAL_CONTEXT_IDLE_TIMEOUT_MS,
    timeoutFallbackMs: FORMAL_CONTEXT_TIMEOUT_FALLBACK_MS,
  });
}

export function useDashboardHomeViewModel(
  snapshotBoundary: DashboardHomeSnapshotBoundary,
  options: { eagerEventFeeds?: boolean } = {},
) {
  const {
    dataClient,
    snapshotQuery,
    isLiveDataFallback,
    adapterOutput,
    snapshotResult,
    initialEffectiveReportDate,
    supplementalReportDate,
  } = snapshotBoundary;

  const useMockFallback = dataClient.mode !== "real" || isLiveDataFallback;
  const snapshotReportDate = snapshotResult?.report_date?.trim() || "";
  const hasSupplementalReportDate = Boolean(supplementalReportDate);
  const hasDeferredSupplementalReportDate = hasSupplementalReportDate;
  const hasBodyDetailData = useBodyDetailDataGate(
    hasDeferredSupplementalReportDate ? supplementalReportDate : undefined,
  );
  const hasBodyStructureData = useBodyStructureDataGate(
    hasDeferredSupplementalReportDate && hasBodyDetailData
      ? supplementalReportDate
      : undefined,
  );
  const hasEventFeedData = useEventFeedDataGate(
    hasDeferredSupplementalReportDate && !options.eagerEventFeeds
      ? supplementalReportDate
      : undefined,
  );
  const eventFeedsReady = options.eagerEventFeeds || hasEventFeedData;
  const hasSecondaryEventFeedData = useSecondaryEventFeedDataGate(
    hasDeferredSupplementalReportDate && eventFeedsReady
      ? supplementalReportDate
      : undefined,
  );
  const secondaryEventFeedsReady = hasSecondaryEventFeedData;
  // Bond news no longer waits on the macro-fallback tier: the fallback decision
  // (secondaryEventFeedsReady) is a sibling concern, not a prerequisite for the
  // bond news probe, so gating bond news on it only stacked an extra idle-gate
  // tier onto the chain without any data dependency backing it. Running the
  // macro and bond news probe chains off the same event-feed tier lets them
  // fire in parallel instead of serially.
  const shouldLoadBondNewsGate = hasDeferredSupplementalReportDate && eventFeedsReady;
  const hasBondNewsFeedData = useBondNewsFeedDataGate(
    shouldLoadBondNewsGate ? supplementalReportDate : undefined,
  );
  const bondNewsFeedsReady = hasBondNewsFeedData;
  const hasFormalContextData = useFormalContextDataGate(
    hasDeferredSupplementalReportDate ? supplementalReportDate : undefined,
  );
  const hasDeferredIncomeTrendData =
    hasDeferredSupplementalReportDate &&
    hasFormalContextData &&
    Boolean(supplementalReportDate);
  const hasDeferredFormalContext = hasDeferredIncomeTrendData;

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
    loadBasicData: hasDeferredSupplementalReportDate,
    loadEventFeeds: hasDeferredSupplementalReportDate && eventFeedsReady,
    loadSecondaryEventFeeds:
      hasDeferredSupplementalReportDate &&
      eventFeedsReady &&
      secondaryEventFeedsReady,
    loadBondNewsFeeds:
      hasDeferredSupplementalReportDate &&
      eventFeedsReady &&
      bondNewsFeedsReady,
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
    enabled: hasDeferredSupplementalReportDate && hasBodyDetailData && hasBodyStructureData,
  });

  const positionChangesQuery = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsPositionChanges(dataClient.mode, supplementalReportDate, 5),
    queryFn: () => dataClient.getBondAnalyticsPositionChanges(supplementalReportDate ?? "", 5),
    retry: false,
    staleTime: 60_000,
    enabled: hasDeferredSupplementalReportDate && hasBodyDetailData && hasBodyStructureData,
  });

  const researchReportsQuery = useQuery({
    queryKey: apiQueryKeys.homeResearchReports(dataClient.mode, supplementalReportDate, 5),
    queryFn: () => dataClient.getHomeResearchReports(supplementalReportDate ?? "", 5),
    retry: false,
    staleTime: 60_000,
    enabled: hasDeferredSupplementalReportDate && hasBodyDetailData && hasBodyStructureData,
  });

  const incomeTrendQuery = useQuery({
    queryKey: apiQueryKeys.homeIncomeTrend(dataClient.mode, supplementalReportDate, 7),
    queryFn: () => dataClient.getHomeIncomeTrend(supplementalReportDate ?? "", 7),
    retry: false,
    staleTime: 60_000,
    enabled: hasDeferredIncomeTrendData,
  });

  const dashboardTodayIsoDate = useMemo(() => todayIsoDate(), []);
  const { macroReleaseContextQuery } = useDashboardHomeMacroReleaseContextQuery({
    dataClient,
    enabled: hasDeferredSupplementalReportDate,
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
        attribution: adapterOutput.attribution.vm,
        creditSpreadMigration: creditSpreadMigrationQuery.data?.result ?? null,
        returnDecomposition: returnDecompositionQuery.data?.result ?? null,
        campisiFourEffects: campisiFourEffectsQuery.data?.result ?? null,
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
        yieldDistribution: homeSummaryQuery.data?.result.yield_distribution ?? null,
        portfolioComparison: homeSummaryQuery.data?.result.portfolio_comparison ?? null,
        spreadAnalysis: homeSummaryQuery.data?.result.spread ?? null,
        businessType: homeSummaryQuery.data?.result.business_type ?? null,
        riskIndicators: homeSummaryQuery.data?.result.risk ?? null,
        topHoldings: topHoldingsQuery.data?.result ?? null,
        topHoldingsLoading: topHoldingsQuery.isLoading,
        topHoldingsError: topHoldingsQuery.isError,
        positionChanges: positionChangesQuery.data?.result ?? null,
        positionChangesLoading: positionChangesQuery.isLoading,
        positionChangesError: positionChangesQuery.isError,
        researchReports: researchReportsQuery.data?.result ?? null,
        researchReportsLoading: researchReportsQuery.isLoading,
        researchReportsError: researchReportsQuery.isError,
        incomeTrend: incomeTrendQuery.data?.result ?? null,
        incomeTrendLoading: incomeTrendQuery.isLoading,
        incomeTrendError: incomeTrendQuery.isError,
        calendarEvents: researchCalendarQuery.data ?? null,
        calendarLoading: researchCalendarQuery.isLoading,
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
      bondNewsEvents,
      bondNewsPayloads,
      creditSpreadMigrationQuery.data?.result,
      effectiveReportDate,
      marketRatesQuery.data?.result.series,
      returnDecompositionQuery.data?.result,
      campisiFourEffectsQuery.data?.result,
      hasDeferredSupplementalReportDate,
      homeSummaryQuery.data,
      homeSummaryQuery.isError,
      topHoldingsQuery.data?.result,
      topHoldingsQuery.isLoading,
      topHoldingsQuery.isError,
      positionChangesQuery.data?.result,
      positionChangesQuery.isLoading,
      positionChangesQuery.isError,
      researchReportsQuery.data?.result,
      researchReportsQuery.isLoading,
      researchReportsQuery.isError,
      incomeTrendQuery.data?.result,
      incomeTrendQuery.isLoading,
      incomeTrendQuery.isError,
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
      researchCalendarQuery.isLoading,
      useMockFallback,
    ],
  );

  return {
    view,
    snapshotQuery,
    effectiveReportDate,
  };
}
