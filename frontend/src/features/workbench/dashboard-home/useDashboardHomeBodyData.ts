import { useMemo } from "react";
import { useQueries, useQuery } from "@tanstack/react-query";

import type { ApiClient } from "../../../api/client";
import { apiQueryKeys } from "../../../api/queryKeys";
import { useDashboardResearchCalendarQuery } from "../pages/useDashboardResearchCalendarQuery";
import { todayIsoDate } from "../pages/dashboardPageHelpers";
import { shouldRequestHomeMacroNewsFallback } from "./adapters/buildHomeMacroBriefingModel";
import {
  DASHBOARD_BOND_NEWS_TOPIC_LIMIT,
  DASHBOARD_BOND_NEWS_TOPICS,
  DASHBOARD_HOME_CONTENT_REFETCH_INTERVAL_MS,
  DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS,
  DASHBOARD_MACRO_NEWS_TOPICS,
  DASHBOARD_MACRO_NEWS_TOPIC_LIMIT,
} from "../dashboard/dashboardMacroNewsTopics";
import {
  getCampisiAttributionContext,
  getCreditRiskOverview,
  getMarketTape,
  getReturnDecompositionContext,
  getYieldCurveContext,
} from "../dashboard/services/dashboardApi";

const CHOICE_NEWS_PERMISSION_ERROR_CODE = 10001012;
const [DASHBOARD_MACRO_NEWS_PROBE_TOPIC, ...DASHBOARD_MACRO_NEWS_REMAINING_TOPICS] =
  DASHBOARD_MACRO_NEWS_TOPICS;
// Direct bond-news reads use stable source groups. They intentionally remain
// independent from the exact-topic macro fallback probes: a fallback topic can
// be absent while another item in the same landed group is available.
const DASHBOARD_BOND_NEWS_DEDUPED_TOPICS = DASHBOARD_BOND_NEWS_TOPICS;
const [DASHBOARD_BOND_NEWS_PROBE_TOPIC, ...DASHBOARD_BOND_NEWS_REMAINING_TOPICS] =
  DASHBOARD_BOND_NEWS_DEDUPED_TOPICS;
const HOME_CONTENT_QUERY_OPTIONS = {
  retry: false,
  staleTime: 60_000,
  refetchInterval: DASHBOARD_HOME_CONTENT_REFETCH_INTERVAL_MS,
  refetchIntervalInBackground: false,
  refetchOnWindowFocus: true,
} as const;

type UseDashboardHomeBodyDataOptions = {
  dataClient: ApiClient;
  supplementalReportDate: string | undefined;
  loadBasicData: boolean;
  loadEventFeeds: boolean;
  loadSecondaryEventFeeds: boolean;
  loadBondNewsFeeds: boolean;
  loadFormalData: boolean;
};

export function useDashboardHomeBodyData({
  dataClient,
  supplementalReportDate,
  loadBasicData,
  loadEventFeeds,
  loadSecondaryEventFeeds,
  loadBondNewsFeeds,
  loadFormalData,
}: UseDashboardHomeBodyDataOptions) {
  const hasSupplementalReportDate = Boolean(supplementalReportDate);
  const loadDatedFormalData = loadFormalData && hasSupplementalReportDate;
  const dashboardTodayIsoDate = useMemo(() => todayIsoDate(), []);

  const marketRatesQuery = useQuery({
    queryKey: apiQueryKeys.marketRates(dataClient.mode),
    queryFn: () => getMarketTape(dataClient),
    retry: false,
    staleTime: 60_000,
    enabled: loadBasicData,
  });

  const researchCalendar = useDashboardResearchCalendarQuery({
    dataClient,
    enabled: loadEventFeeds,
  });

  const macroNewsQueries = useQueries({
    queries: [{
      queryKey: ["dashboard", "macro-news", dataClient.mode, DASHBOARD_MACRO_NEWS_PROBE_TOPIC.code],
      queryFn: () =>
        dataClient.getChoiceNewsEvents({
          limit: DASHBOARD_MACRO_NEWS_TOPIC_LIMIT,
          offset: 0,
          topicCode: DASHBOARD_MACRO_NEWS_PROBE_TOPIC.code,
        }),
      ...HOME_CONTENT_QUERY_OPTIONS,
      enabled: loadEventFeeds,
    }],
  });
  const macroNewsProbeQuery = macroNewsQueries[0];
  const macroNewsProbeHasPermissionError = Boolean(
    macroNewsProbeQuery?.data?.result.events.some(
      (event) => event.error_code === CHOICE_NEWS_PERMISSION_ERROR_CODE,
    ),
  );
  const loadRemainingChoiceMacroNews =
    loadEventFeeds &&
    Boolean(macroNewsProbeQuery?.isSuccess) &&
    !macroNewsProbeHasPermissionError;
  const remainingMacroNewsQueries = useQueries({
    queries: DASHBOARD_MACRO_NEWS_REMAINING_TOPICS.map((topic) => ({
      queryKey: ["dashboard", "macro-news", dataClient.mode, topic.code],
      queryFn: () =>
        dataClient.getChoiceNewsEvents({
          limit: DASHBOARD_MACRO_NEWS_TOPIC_LIMIT,
          offset: 0,
          topicCode: topic.code,
        }),
      ...HOME_CONTENT_QUERY_OPTIONS,
      enabled: loadRemainingChoiceMacroNews,
    })),
  });
  const allMacroNewsQueries = [
    ...macroNewsQueries.slice(0, 1),
    ...remainingMacroNewsQueries,
  ];
  const macroNewsSettled =
    loadEventFeeds &&
    allMacroNewsQueries.length > 0 &&
    (macroNewsProbeHasPermissionError ||
      Boolean(macroNewsProbeQuery?.isError) ||
      allMacroNewsQueries.every((query) => query.isSuccess || query.isError));
  const shouldLoadMacroNewsFallback =
    loadSecondaryEventFeeds &&
    macroNewsSettled &&
    (macroNewsProbeHasPermissionError ||
      Boolean(macroNewsProbeQuery?.isError) ||
      allMacroNewsQueries.every((query) => query.isError) ||
      shouldRequestHomeMacroNewsFallback({
        choiceEvents: allMacroNewsQueries.flatMap((query) => query.data?.result.events ?? []),
        todayIsoDate: dashboardTodayIsoDate,
      }));

  const macroNewsFallbackQueries = useQueries({
    queries: DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS.map((topic) => ({
      queryKey: ["dashboard", "macro-news-fallback", dataClient.mode, topic.code, topic.queryLimit],
      queryFn: () =>
        dataClient.getChoiceNewsEvents({
          limit: topic.queryLimit,
          offset: 0,
          topicCode: topic.code,
      }),
      ...HOME_CONTENT_QUERY_OPTIONS,
      enabled: shouldLoadMacroNewsFallback,
    })),
  });

  const bondNewsProbeQueries = useQueries({
    queries: [{
      queryKey: ["dashboard", "bond-news", dataClient.mode, DASHBOARD_BOND_NEWS_PROBE_TOPIC?.groupId ?? "none"],
      queryFn: () =>
        dataClient.getChoiceNewsEvents({
          limit: DASHBOARD_BOND_NEWS_TOPIC_LIMIT,
          offset: 0,
          groupId: DASHBOARD_BOND_NEWS_PROBE_TOPIC?.groupId ?? "",
        }),
      ...HOME_CONTENT_QUERY_OPTIONS,
      enabled: loadBondNewsFeeds && Boolean(DASHBOARD_BOND_NEWS_PROBE_TOPIC),
    }],
  });
  const bondNewsProbeQuery = bondNewsProbeQueries[0];
  const loadRemainingBondNews =
    loadBondNewsFeeds &&
    Boolean(bondNewsProbeQuery?.isSuccess || bondNewsProbeQuery?.isError);
  const remainingBondNewsQueries = useQueries({
    queries: DASHBOARD_BOND_NEWS_REMAINING_TOPICS.map((topic) => ({
      queryKey: ["dashboard", "bond-news", dataClient.mode, topic.groupId],
      queryFn: () =>
        dataClient.getChoiceNewsEvents({
          limit: DASHBOARD_BOND_NEWS_TOPIC_LIMIT,
          offset: 0,
          groupId: topic.groupId,
      }),
      ...HOME_CONTENT_QUERY_OPTIONS,
      enabled: loadRemainingBondNews,
    })),
  });
  const bondNewsQueries = [
    ...(DASHBOARD_BOND_NEWS_PROBE_TOPIC ? bondNewsProbeQueries : []),
    ...remainingBondNewsQueries,
  ];

  const creditSpreadMigrationQuery = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsCreditSpreadMigration(dataClient.mode, supplementalReportDate),
    queryFn: () => getCreditRiskOverview(dataClient, supplementalReportDate ?? ""),
    retry: false,
    staleTime: 60_000,
    enabled: loadDatedFormalData,
  });

  const returnDecompositionQuery = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsReturnDecomposition(
      dataClient.mode,
      supplementalReportDate,
      "MoM",
      "all",
      "all",
    ),
    queryFn: () => getReturnDecompositionContext(dataClient, supplementalReportDate ?? ""),
    retry: false,
    staleTime: 60_000,
    enabled: loadDatedFormalData,
  });

  const campisiFourEffectsQuery = useQuery({
    queryKey: apiQueryKeys.pnlCampisiFourEffects(
      dataClient.mode,
      supplementalReportDate,
      30,
    ),
    queryFn: () => getCampisiAttributionContext(dataClient, supplementalReportDate ?? ""),
    retry: false,
    staleTime: 60_000,
    enabled: loadDatedFormalData,
  });

  const yieldCurveTermStructureQuery = useQuery({
    queryKey: apiQueryKeys.bondAnalyticsYieldCurveTermStructure(
      dataClient.mode,
      supplementalReportDate,
      "treasury,cdb,aaa_credit",
    ),
    queryFn: () => getYieldCurveContext(dataClient, supplementalReportDate ?? ""),
    retry: false,
    staleTime: 60_000,
    enabled: loadDatedFormalData,
  });

  return {
    marketRatesQuery,
    creditSpreadMigrationQuery,
    returnDecompositionQuery,
    campisiFourEffectsQuery,
    yieldCurveTermStructureQuery,
    researchCalendarQuery: researchCalendar.researchCalendarQuery,
    macroNewsQueries: allMacroNewsQueries,
    macroNewsFallbackQueries,
    bondNewsQueries,
    calendarStartDate: researchCalendar.calendarStartDate,
    calendarEndDate: researchCalendar.calendarEndDate,
  };
}
