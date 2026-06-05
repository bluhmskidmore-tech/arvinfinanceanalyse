import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { apiQueryKeys } from "../../../api/queryKeys";
import { todayIsoDate } from "../pages/dashboardPageHelpers";
import { mapToHomeBodyView } from "./dashboardHomeBodyView";
import { useDashboardHomeBodyData } from "./useDashboardHomeBodyData";
import type { DashboardHomeSnapshotBoundary } from "./useDashboardHomeFirstScreenViewModel";

type IdleWindow = Window & {
  requestIdleCallback?: (callback: () => void, options?: { timeout: number }) => number;
  cancelIdleCallback?: (handle: number) => void;
};

const BODY_DETAIL_IDLE_MIN_DELAY_MS = 1_000;
const BODY_DETAIL_IDLE_TIMEOUT_MS = 1_200;
const BODY_DETAIL_TIMEOUT_FALLBACK_MS = 900;
const EVENT_FEED_IDLE_MIN_DELAY_MS = 1_000;
const EVENT_FEED_IDLE_TIMEOUT_MS = 1_200;
const EVENT_FEED_TIMEOUT_FALLBACK_MS = 900;
const SECONDARY_EVENT_FEED_IDLE_MIN_DELAY_MS = 1_000;
const SECONDARY_EVENT_FEED_IDLE_TIMEOUT_MS = 1_200;
const SECONDARY_EVENT_FEED_TIMEOUT_FALLBACK_MS = 900;
const BOND_NEWS_FEED_IDLE_MIN_DELAY_MS = 1_000;
const BOND_NEWS_FEED_IDLE_TIMEOUT_MS = 1_200;
const BOND_NEWS_FEED_TIMEOUT_FALLBACK_MS = 900;
const FORMAL_CONTEXT_IDLE_MIN_DELAY_MS = 1_000;
const FORMAL_CONTEXT_IDLE_TIMEOUT_MS = 1_200;
const FORMAL_CONTEXT_TIMEOUT_FALLBACK_MS = 900;

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

export function useDashboardHomeViewModel(snapshotBoundary: DashboardHomeSnapshotBoundary) {
  const [supplementalDataReportDate, setSupplementalDataReportDate] = useState<string | null>(null);
  const [formalContextReportDate, setFormalContextReportDate] = useState<string | null>(null);

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
  const hasInitialEffectiveReportDate = Boolean(initialEffectiveReportDate);
  const hasDeferredSupplementalData =
    hasInitialEffectiveReportDate &&
    supplementalDataReportDate === initialEffectiveReportDate;
  const hasSupplementalReportDate = Boolean(supplementalReportDate);
  const hasDeferredSupplementalReportDate =
    hasDeferredSupplementalData && hasSupplementalReportDate;
  const hasBodyDetailData = useBodyDetailDataGate(
    hasDeferredSupplementalReportDate ? supplementalReportDate : undefined,
  );
  const hasEventFeedData = useEventFeedDataGate(
    hasDeferredSupplementalReportDate && hasBodyDetailData ? supplementalReportDate : undefined,
  );
  const hasSecondaryEventFeedData = useSecondaryEventFeedDataGate(
    hasDeferredSupplementalReportDate && hasBodyDetailData && hasEventFeedData
      ? supplementalReportDate
      : undefined,
  );
  const hasBondNewsFeedData = useBondNewsFeedDataGate(
    hasDeferredSupplementalReportDate &&
      hasBodyDetailData &&
      hasEventFeedData &&
      hasSecondaryEventFeedData
      ? supplementalReportDate
      : undefined,
  );
  const hasFormalContextData = useFormalContextDataGate(
    hasDeferredSupplementalReportDate &&
      hasBodyDetailData &&
      hasEventFeedData &&
      hasSecondaryEventFeedData &&
      hasBondNewsFeedData
      ? supplementalReportDate
      : undefined,
  );
  const hasDeferredFormalContext =
    hasDeferredSupplementalReportDate &&
    hasBodyDetailData &&
    hasEventFeedData &&
    hasSecondaryEventFeedData &&
    hasBondNewsFeedData &&
    hasFormalContextData &&
    Boolean(supplementalReportDate) &&
    formalContextReportDate === supplementalReportDate;

  useEffect(() => {
    setSupplementalDataReportDate(null);
    setFormalContextReportDate(null);
    if (!initialEffectiveReportDate) {
      return;
    }

    setSupplementalDataReportDate(initialEffectiveReportDate);
  }, [initialEffectiveReportDate]);

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
    loadBasicData: hasDeferredSupplementalData,
    loadEventFeeds: hasDeferredSupplementalReportDate && hasBodyDetailData && hasEventFeedData,
    loadSecondaryEventFeeds:
      hasDeferredSupplementalReportDate &&
      hasBodyDetailData &&
      hasEventFeedData &&
      hasSecondaryEventFeedData,
    loadBondNewsFeeds:
      hasDeferredSupplementalReportDate &&
      hasBodyDetailData &&
      hasEventFeedData &&
      hasSecondaryEventFeedData &&
      hasBondNewsFeedData,
    loadFormalData: hasDeferredFormalContext,
  });

  const homeSummaryQuery = useQuery({
    queryKey: apiQueryKeys.bondDashboardHomeSummary(dataClient.mode, supplementalReportDate),
    queryFn: () => dataClient.getBondDashboardHomeSummary(supplementalReportDate ?? ""),
    retry: false,
    staleTime: 60_000,
    enabled: hasDeferredSupplementalReportDate && hasBodyDetailData,
  });

  const topHoldingsQuery = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsTopHoldings(dataClient.mode, supplementalReportDate, 8),
    queryFn: () => dataClient.getBondAnalyticsTopHoldings(supplementalReportDate ?? "", 8),
    retry: false,
    staleTime: 60_000,
    enabled: hasDeferredSupplementalReportDate && hasBodyDetailData,
  });

  const positionChangesQuery = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsPositionChanges(dataClient.mode, supplementalReportDate, 5),
    queryFn: () => dataClient.getBondAnalyticsPositionChanges(supplementalReportDate ?? "", 5),
    retry: false,
    staleTime: 60_000,
    enabled: hasDeferredSupplementalReportDate && hasBodyDetailData,
  });
  const heavyBondListsReady =
    hasDeferredSupplementalReportDate &&
    hasBodyDetailData &&
    (topHoldingsQuery.isSuccess || topHoldingsQuery.isError) &&
    (positionChangesQuery.isSuccess || positionChangesQuery.isError);

  useEffect(() => {
    if (!hasDeferredSupplementalReportDate || !hasBodyDetailData || !supplementalReportDate) {
      setFormalContextReportDate(null);
      return;
    }
    if (heavyBondListsReady) {
      setFormalContextReportDate(supplementalReportDate);
    }
  }, [
    hasDeferredSupplementalReportDate,
    hasBodyDetailData,
    heavyBondListsReady,
    supplementalReportDate,
  ]);

  const researchReportsQuery = useQuery({
    queryKey: apiQueryKeys.homeResearchReports(dataClient.mode, supplementalReportDate, 5),
    queryFn: () => dataClient.getHomeResearchReports(supplementalReportDate ?? "", 5),
    retry: false,
    staleTime: 60_000,
    enabled: hasDeferredSupplementalReportDate && hasBodyDetailData,
  });

  const incomeTrendQuery = useQuery({
    queryKey: apiQueryKeys.homeIncomeTrend(dataClient.mode, supplementalReportDate, 7),
    queryFn: () => dataClient.getHomeIncomeTrend(supplementalReportDate ?? "", 7),
    retry: false,
    staleTime: 60_000,
    enabled: hasDeferredFormalContext,
  });

  const dashboardTodayIsoDate = useMemo(() => todayIsoDate(), []);
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
  const macroNewsLoading =
    macroNewsQueries.some((query) => query.isLoading) ||
    macroNewsFallbackQueries.some((query) => query.isLoading);
  const macroNewsError =
    macroNewsQueries.length > 0 &&
    macroNewsFallbackQueries.length > 0 &&
    macroNewsQueries.every((query) => query.isError) &&
    macroNewsFallbackQueries.every((query) => query.isError);

  const effectiveReportDate =
    snapshotReportDate || initialEffectiveReportDate;
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
        macroNewsLoading,
        macroNewsError,
      }),
    [
      adapterOutput.attribution.vm,
      bondNewsEvents,
      creditSpreadMigrationQuery.data?.result,
      effectiveReportDate,
      marketRatesQuery.data?.result.series,
      returnDecompositionQuery.data?.result,
      campisiFourEffectsQuery.data?.result,
      homeSummaryQuery.data?.result.asset_type,
      homeSummaryQuery.data?.result.asset_rating,
      homeSummaryQuery.data?.result.maturity,
      homeSummaryQuery.data?.result.industry,
      homeSummaryQuery.data?.result.risk,
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
