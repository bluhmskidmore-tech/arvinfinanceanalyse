import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import type { ApiClient } from "../../../api/client";
import type {
  ApiEnvelope,
  ChoiceNewsEventsBatchPayload,
  ChoiceNewsEventsPayload,
} from "../../../api/contracts";
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
// News/context feeds tolerate a 5-minute staleness window aligned with the
// periodic refetch interval, so a remount inside the window reuses cache
// instead of re-issuing the batch requests. Formal metric queries below keep
// their own staleTime of 60s.
const HOME_CONTENT_QUERY_OPTIONS = {
  retry: false,
  staleTime: DASHBOARD_HOME_CONTENT_REFETCH_INTERVAL_MS,
  refetchInterval: DASHBOARD_HOME_CONTENT_REFETCH_INTERVAL_MS,
  refetchIntervalInBackground: false,
  refetchOnWindowFocus: true,
} as const;

type HomeNewsBatchTopicRequest = { topicCode: string; limit: number };
type HomeNewsBatchGroupRequest = { groupId: string; limit: number };
type HomeNewsDerivedRequest = { key: string; limit: number };

const MACRO_NEWS_BATCH_TOPICS: readonly HomeNewsBatchTopicRequest[] =
  DASHBOARD_MACRO_NEWS_TOPICS.map((topic) => ({
    topicCode: topic.code,
    limit: DASHBOARD_MACRO_NEWS_TOPIC_LIMIT,
  }));
const MACRO_NEWS_FALLBACK_BATCH_TOPICS: readonly HomeNewsBatchTopicRequest[] =
  DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS.map((topic) => ({
    topicCode: topic.code,
    limit: topic.queryLimit,
  }));
// Direct bond-news reads use stable source groups. They intentionally remain
// independent from the exact-topic macro fallback probes: a fallback topic can
// be absent while another item in the same landed group is available.
const BOND_NEWS_BATCH_GROUPS: readonly HomeNewsBatchGroupRequest[] =
  DASHBOARD_BOND_NEWS_TOPICS.map((topic) => ({
    groupId: topic.groupId,
    limit: DASHBOARD_BOND_NEWS_TOPIC_LIMIT,
  }));

function sortedBatchFingerprint(entries: readonly string[]): string {
  return [...entries].sort().join(",");
}

const MACRO_NEWS_BATCH_FINGERPRINT = sortedBatchFingerprint(
  MACRO_NEWS_BATCH_TOPICS.map(({ topicCode, limit }) => `${topicCode}:${limit}`),
);
const MACRO_NEWS_FALLBACK_BATCH_FINGERPRINT = sortedBatchFingerprint(
  MACRO_NEWS_FALLBACK_BATCH_TOPICS.map(({ topicCode, limit }) => `${topicCode}:${limit}`),
);
const BOND_NEWS_BATCH_FINGERPRINT = sortedBatchFingerprint(
  BOND_NEWS_BATCH_GROUPS.map(({ groupId, limit }) => `${groupId}:${limit}`),
);

const MACRO_NEWS_DERIVED_REQUESTS: readonly HomeNewsDerivedRequest[] =
  MACRO_NEWS_BATCH_TOPICS.map(({ topicCode, limit }) => ({
    key: `topic:${topicCode}`,
    limit,
  }));
const MACRO_NEWS_FALLBACK_DERIVED_REQUESTS: readonly HomeNewsDerivedRequest[] =
  MACRO_NEWS_FALLBACK_BATCH_TOPICS.map(({ topicCode, limit }) => ({
    key: `topic:${topicCode}`,
    limit,
  }));
const BOND_NEWS_DERIVED_REQUESTS: readonly HomeNewsDerivedRequest[] =
  BOND_NEWS_BATCH_GROUPS.map(({ groupId, limit }) => ({
    key: `group:${groupId}`,
    limit,
  }));

/**
 * Per-topic query-shaped state derived from one batch request. Mirrors the
 * subset of the TanStack query result consumed downstream
 * (`data.result.events` / `data.result` / `isLoading` / `isError` /
 * `isSuccess`), so view models and sections keep their original per-topic
 * contract while the network layer collapses to one request per wave.
 */
export type DashboardHomeNewsQueryState = {
  data: ApiEnvelope<ChoiceNewsEventsPayload> | undefined;
  error: unknown;
  isLoading: boolean;
  isError: boolean;
  isSuccess: boolean;
};

type HomeNewsBatchQueryState = {
  data: ApiEnvelope<ChoiceNewsEventsBatchPayload> | undefined;
  error: unknown;
  isLoading: boolean;
  isError: boolean;
  isSuccess: boolean;
};

function deriveHomeNewsQueries(
  batch: HomeNewsBatchQueryState,
  requests: readonly HomeNewsDerivedRequest[],
): DashboardHomeNewsQueryState[] {
  const batchAsOfDate = batch.data?.result_meta.as_of_date ?? null;
  const rawFutureRowsExcluded = batch.data?.result_meta.filters_applied?.future_rows_excluded;
  const batchFutureRowsExcluded =
    typeof rawFutureRowsExcluded === "number" ? rawFutureRowsExcluded : 0;
  return requests.map(({ key, limit }, index) => {
    const events =
      batch.data?.result.batches.find((item) => item.key === key)?.events ?? [];
    return {
      // The batch contract only carries per-topic events, so the derived
      // envelope synthesizes the single-query payload shape around them.
      // as_of_date is shared by every sub-query; the future-rows count is a
      // batch-level aggregate, so it goes onto the first payload only —
      // downstream sums payloads and would otherwise multiply it.
      data: batch.data
        ? {
            result_meta: batch.data.result_meta,
            result: {
              total_rows: events.length,
              limit,
              offset: 0,
              as_of_date: batchAsOfDate,
              excluded_future_rows: index === 0 ? batchFutureRowsExcluded : 0,
              events,
            },
          }
        : undefined,
      error: batch.error,
      isLoading: batch.isLoading,
      isError: batch.isError,
      isSuccess: batch.isSuccess,
    };
  });
}

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

  const macroNewsBatchQuery = useQuery({
    queryKey: [
      "dashboard",
      "macro-news",
      dataClient.mode,
      "batch",
      MACRO_NEWS_BATCH_FINGERPRINT,
    ],
    queryFn: () =>
      dataClient.getChoiceNewsEventsBatch({ topics: MACRO_NEWS_BATCH_TOPICS }),
    ...HOME_CONTENT_QUERY_OPTIONS,
    enabled: loadEventFeeds,
  });
  const macroNewsQueries = useMemo(
    () =>
      deriveHomeNewsQueries(
        {
          data: macroNewsBatchQuery.data,
          error: macroNewsBatchQuery.error,
          isLoading: macroNewsBatchQuery.isLoading,
          isError: macroNewsBatchQuery.isError,
          isSuccess: macroNewsBatchQuery.isSuccess,
        },
        MACRO_NEWS_DERIVED_REQUESTS,
      ),
    [
      macroNewsBatchQuery.data,
      macroNewsBatchQuery.error,
      macroNewsBatchQuery.isLoading,
      macroNewsBatchQuery.isError,
      macroNewsBatchQuery.isSuccess,
    ],
  );
  // Permission probing keeps the original first-topic semantics: the batch
  // endpoint returns permission-error events inside each topic's events, so
  // the first topic acts as the representative probe.
  const macroNewsProbeQuery = macroNewsQueries[0];
  const macroNewsProbeHasPermissionError = Boolean(
    macroNewsProbeQuery?.data?.result.events.some(
      (event) => event.error_code === CHOICE_NEWS_PERMISSION_ERROR_CODE,
    ),
  );
  const macroNewsSettled =
    loadEventFeeds &&
    macroNewsQueries.length > 0 &&
    (macroNewsProbeHasPermissionError ||
      Boolean(macroNewsProbeQuery?.isError) ||
      macroNewsQueries.every((query) => query.isSuccess || query.isError));
  const shouldLoadMacroNewsFallback =
    loadSecondaryEventFeeds &&
    macroNewsSettled &&
    (macroNewsProbeHasPermissionError ||
      Boolean(macroNewsProbeQuery?.isError) ||
      macroNewsQueries.every((query) => query.isError) ||
      shouldRequestHomeMacroNewsFallback({
        choiceEvents: macroNewsQueries.flatMap((query) => query.data?.result.events ?? []),
        todayIsoDate: dashboardTodayIsoDate,
      }));

  const macroNewsFallbackBatchQuery = useQuery({
    queryKey: [
      "dashboard",
      "macro-news-fallback",
      dataClient.mode,
      "batch",
      MACRO_NEWS_FALLBACK_BATCH_FINGERPRINT,
    ],
    queryFn: () =>
      dataClient.getChoiceNewsEventsBatch({
        topics: MACRO_NEWS_FALLBACK_BATCH_TOPICS,
      }),
    ...HOME_CONTENT_QUERY_OPTIONS,
    enabled: shouldLoadMacroNewsFallback,
  });
  const macroNewsFallbackQueries = useMemo(
    () =>
      deriveHomeNewsQueries(
        {
          data: macroNewsFallbackBatchQuery.data,
          error: macroNewsFallbackBatchQuery.error,
          isLoading: macroNewsFallbackBatchQuery.isLoading,
          isError: macroNewsFallbackBatchQuery.isError,
          isSuccess: macroNewsFallbackBatchQuery.isSuccess,
        },
        MACRO_NEWS_FALLBACK_DERIVED_REQUESTS,
      ),
    [
      macroNewsFallbackBatchQuery.data,
      macroNewsFallbackBatchQuery.error,
      macroNewsFallbackBatchQuery.isLoading,
      macroNewsFallbackBatchQuery.isError,
      macroNewsFallbackBatchQuery.isSuccess,
    ],
  );

  const bondNewsBatchQuery = useQuery({
    queryKey: [
      "dashboard",
      "bond-news",
      dataClient.mode,
      "batch",
      BOND_NEWS_BATCH_FINGERPRINT,
    ],
    queryFn: () =>
      dataClient.getChoiceNewsEventsBatch({ groups: BOND_NEWS_BATCH_GROUPS }),
    ...HOME_CONTENT_QUERY_OPTIONS,
    enabled: loadBondNewsFeeds,
  });
  const bondNewsQueries = useMemo(
    () =>
      deriveHomeNewsQueries(
        {
          data: bondNewsBatchQuery.data,
          error: bondNewsBatchQuery.error,
          isLoading: bondNewsBatchQuery.isLoading,
          isError: bondNewsBatchQuery.isError,
          isSuccess: bondNewsBatchQuery.isSuccess,
        },
        BOND_NEWS_DERIVED_REQUESTS,
      ),
    [
      bondNewsBatchQuery.data,
      bondNewsBatchQuery.error,
      bondNewsBatchQuery.isLoading,
      bondNewsBatchQuery.isError,
      bondNewsBatchQuery.isSuccess,
    ],
  );

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
      "summary",
    ),
    queryFn: () =>
      getReturnDecompositionContext(dataClient, supplementalReportDate ?? "", {
        detail: "summary",
      }),
    retry: false,
    staleTime: 60_000,
    enabled: loadDatedFormalData,
  });

  const campisiFourEffectsQuery = useQuery({
    queryKey: apiQueryKeys.pnlCampisiFourEffects(
      dataClient.mode,
      supplementalReportDate,
      30,
      "summary",
    ),
    queryFn: () =>
      getCampisiAttributionContext(dataClient, supplementalReportDate ?? "", {
        detail: "summary",
      }),
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
    macroNewsQueries,
    macroNewsFallbackQueries,
    bondNewsQueries,
    calendarStartDate: researchCalendar.calendarStartDate,
    calendarEndDate: researchCalendar.calendarEndDate,
  };
}
