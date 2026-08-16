import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { createApiClient, type ApiClient } from "../../../api/client";
import type {
  ApiEnvelope,
  ChoiceNewsEvent,
  ChoiceNewsEventsBatchPayload,
} from "../../../api/contracts";
import {
  DASHBOARD_BOND_NEWS_TOPICS,
  DASHBOARD_HOME_CONTENT_REFETCH_INTERVAL_MS,
  DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS,
  DASHBOARD_MACRO_NEWS_TOPICS,
} from "../dashboard/dashboardMacroNewsTopics";
import { useDashboardHomeBodyData } from "./useDashboardHomeBodyData";

type ChoiceNewsBatchOptions = Parameters<ApiClient["getChoiceNewsEventsBatch"]>[0];

function createQueryClient() {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        staleTime: 0,
        gcTime: 0,
        refetchOnWindowFocus: false,
      },
    },
  });
}

function createWrapper(queryClient = createQueryClient()) {
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

function choiceEvent(
  partial: Partial<ChoiceNewsEvent> &
    Pick<ChoiceNewsEvent, "event_key" | "received_at" | "topic_code" | "payload_text">,
): ChoiceNewsEvent {
  return {
    group_id: "news_cmd1",
    content_type: "sectornews",
    serial_id: 1,
    request_id: 1,
    error_code: 0,
    error_msg: "",
    item_index: 0,
    payload_json: null,
    ...partial,
  };
}

/** 按契约回放批量响应：batches 顺序与请求顺序一致（先 topics 后 groups）。 */
function choiceNewsBatchEnvelope(
  options: ChoiceNewsBatchOptions,
  eventsForTopic: (topicCode: string) => ChoiceNewsEvent[] = () => [],
  eventsForGroup: (groupId: string) => ChoiceNewsEvent[] = () => [],
): ApiEnvelope<ChoiceNewsEventsBatchPayload> {
  return {
    result_meta: {
      basis: "formal",
      trace_id: "tr_home_macro_news_test",
      result_kind: "news.choice.latest_batch",
      formal_use_allowed: true,
      source_version: "sv_test",
      vendor_version: "vv_test",
      rule_version: "rv_test",
      cache_version: "cv_test",
      quality_flag: "ok",
      vendor_status: "ok",
      fallback_mode: "none",
      scenario_flag: false,
      generated_at: "2026-06-04T00:00:00Z",
    },
    result: {
      batches: [
        ...(options.topics ?? []).map(({ topicCode }) => ({
          key: `topic:${topicCode}`,
          topic_code: topicCode,
          group_id: null,
          events: eventsForTopic(topicCode),
        })),
        ...(options.groups ?? []).map(({ groupId }) => ({
          key: `group:${groupId}`,
          topic_code: null,
          group_id: groupId,
          events: eventsForGroup(groupId),
        })),
      ],
    },
  };
}

function requestedTopicCodes(spy: { mock: { calls: Array<[ChoiceNewsBatchOptions]> } }): string[] {
  return spy.mock.calls.flatMap(([options]) =>
    (options.topics ?? []).map(({ topicCode }) => topicCode),
  );
}

function requestedGroupIds(spy: { mock: { calls: Array<[ChoiceNewsBatchOptions]> } }): string[] {
  return spy.mock.calls.flatMap(([options]) =>
    (options.groups ?? []).map(({ groupId }) => groupId),
  );
}

function createHomeBodyClient(overrides: Partial<ApiClient>): ApiClient {
  const base = createApiClient({ mode: "mock" });
  return {
    ...base,
    mode: "real",
    ...overrides,
  };
}

describe("useDashboardHomeBodyData", () => {
  it("waits for the secondary event feed gate before loading macro fallback feeds", async () => {
    const getChoiceNewsEventsBatch = vi.fn<ApiClient["getChoiceNewsEventsBatch"]>(async (options) =>
      choiceNewsBatchEnvelope(options),
    );
    const dataClient = createHomeBodyClient({
      getChoiceNewsEventsBatch,
      getResearchCalendarEvents: vi.fn(async () => []),
    });

    renderHook(
      () =>
        useDashboardHomeBodyData({
          dataClient,
          supplementalReportDate: "2026-05-31",
          loadBasicData: false,
          loadEventFeeds: true,
          loadSecondaryEventFeeds: false,
          loadBondNewsFeeds: false,
          loadFormalData: false,
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(requestedTopicCodes(getChoiceNewsEventsBatch)).toEqual(
        expect.arrayContaining(DASHBOARD_MACRO_NEWS_TOPICS.map((topic) => topic.code)),
      );
    });
    expect(requestedTopicCodes(getChoiceNewsEventsBatch)).not.toEqual(
      expect.arrayContaining(DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS.map((topic) => topic.code)),
    );
  });

  it("loads macro fallback feeds after Choice macro news has no usable policy funding rows", async () => {
    const getChoiceNewsEventsBatch = vi.fn<ApiClient["getChoiceNewsEventsBatch"]>(async (options) =>
      choiceNewsBatchEnvelope(options),
    );
    const dataClient = createHomeBodyClient({
      getChoiceNewsEventsBatch,
      getResearchCalendarEvents: vi.fn(async () => []),
    });

    renderHook(
      () =>
        useDashboardHomeBodyData({
          dataClient,
          supplementalReportDate: "2026-05-31",
          loadBasicData: false,
          loadEventFeeds: true,
          loadSecondaryEventFeeds: true,
          loadBondNewsFeeds: false,
          loadFormalData: false,
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(requestedTopicCodes(getChoiceNewsEventsBatch)).toEqual(
        expect.arrayContaining(DASHBOARD_MACRO_NEWS_TOPICS.map((topic) => topic.code)),
      );
    });
    await waitFor(() => {
      expect(requestedTopicCodes(getChoiceNewsEventsBatch)).toEqual(
        expect.arrayContaining(DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS.map((topic) => topic.code)),
      );
    });
  });

  it("does not load fallback feeds when Choice has a fresh json title over an html payload", async () => {
    const freshPolicyFundingEvent = choiceEvent({
      event_key: "choice-html-json-title",
      received_at: "2026-06-04T09:00:00+08:00",
      topic_code: DASHBOARD_MACRO_NEWS_TOPICS[0].code,
      payload_text: '<div class="main-text">央行开展逆回购操作，资金面平稳</div>',
      payload_json: JSON.stringify({ title: "央行开展逆回购操作，资金面平稳" }),
    });
    const getChoiceNewsEventsBatch = vi.fn<ApiClient["getChoiceNewsEventsBatch"]>(async (options) =>
      choiceNewsBatchEnvelope(options, (topicCode) =>
        topicCode === DASHBOARD_MACRO_NEWS_TOPICS[0].code ? [freshPolicyFundingEvent] : [],
      ),
    );
    const dataClient = createHomeBodyClient({
      getChoiceNewsEventsBatch,
      getResearchCalendarEvents: vi.fn(async () => []),
    });

    renderHook(
      () =>
        useDashboardHomeBodyData({
          dataClient,
          supplementalReportDate: "2026-05-31",
          loadBasicData: false,
          loadEventFeeds: true,
          loadSecondaryEventFeeds: true,
          loadBondNewsFeeds: false,
          loadFormalData: false,
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(requestedTopicCodes(getChoiceNewsEventsBatch)).toEqual(
        expect.arrayContaining(DASHBOARD_MACRO_NEWS_TOPICS.map((topic) => topic.code)),
      );
    });
    await waitFor(() => {
      expect(
        DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS.some((topic) =>
          requestedTopicCodes(getChoiceNewsEventsBatch).includes(topic.code),
        ),
      ).toBe(false);
    });
  });

  it("queries each direct bond-news feed by stable group id in one batch", async () => {
    const getChoiceNewsEventsBatch = vi.fn<ApiClient["getChoiceNewsEventsBatch"]>(async (options) =>
      choiceNewsBatchEnvelope(
        options,
        () => [],
        (groupId) => [
          choiceEvent({
            event_key: `bond-${groupId}`,
            received_at: "2026-07-27T09:00:00+08:00",
            group_id: groupId,
            topic_code: "tushare.news.sina",
            payload_text: "国债收益率曲线今日小幅下行",
          }),
        ],
      ),
    );
    const dataClient = createHomeBodyClient({
      getChoiceNewsEventsBatch,
      getResearchCalendarEvents: vi.fn(async () => []),
    });

    const { result } = renderHook(
      () =>
        useDashboardHomeBodyData({
          dataClient,
          supplementalReportDate: "2026-05-31",
          loadBasicData: false,
          loadEventFeeds: false,
          loadSecondaryEventFeeds: false,
          loadBondNewsFeeds: true,
          loadFormalData: false,
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(requestedGroupIds(getChoiceNewsEventsBatch)).toEqual(
        DASHBOARD_BOND_NEWS_TOPICS.map((topic) => topic.groupId),
      );
    });
    expect(getChoiceNewsEventsBatch).toHaveBeenCalledTimes(1);
    await waitFor(() => {
      expect(result.current.bondNewsQueries).toHaveLength(DASHBOARD_BOND_NEWS_TOPICS.length);
      expect(result.current.bondNewsQueries.every((query) => query.isSuccess)).toBe(true);
    });
  });

  it("derives per-group bond-news query state from an empty probe group batch", async () => {
    const remainingTopic = DASHBOARD_BOND_NEWS_TOPICS[1]!;
    const remainingEvent = choiceEvent({
      event_key: `bond-${remainingTopic.groupId}`,
      received_at: "2026-07-27T09:00:00+08:00",
      group_id: remainingTopic.groupId,
      topic_code: remainingTopic.code,
      payload_text: "债券市场有效新闻",
    });
    const getChoiceNewsEventsBatch = vi.fn<ApiClient["getChoiceNewsEventsBatch"]>(async (options) =>
      choiceNewsBatchEnvelope(
        options,
        () => [],
        (groupId) => (groupId === remainingTopic.groupId ? [remainingEvent] : []),
      ),
    );
    const dataClient = createHomeBodyClient({
      getChoiceNewsEventsBatch,
      getResearchCalendarEvents: vi.fn(async () => []),
    });

    const { result } = renderHook(
      () =>
        useDashboardHomeBodyData({
          dataClient,
          supplementalReportDate: "2026-05-31",
          loadBasicData: false,
          loadEventFeeds: false,
          loadSecondaryEventFeeds: false,
          loadBondNewsFeeds: true,
          loadFormalData: false,
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(requestedGroupIds(getChoiceNewsEventsBatch)).toEqual(
        DASHBOARD_BOND_NEWS_TOPICS.map((topic) => topic.groupId),
      );
    });
    await waitFor(() => {
      expect(result.current.bondNewsQueries[1]?.data?.result.events).toEqual([remainingEvent]);
      expect(result.current.bondNewsQueries[0]?.data?.result.events).toEqual([]);
    });
  });

  it("keeps homepage news reads active every five minutes without background polling", async () => {
    const queryClient = createQueryClient();
    const getChoiceNewsEventsBatch = vi.fn<ApiClient["getChoiceNewsEventsBatch"]>(async (options) =>
      choiceNewsBatchEnvelope(options),
    );
    const dataClient = createHomeBodyClient({
      getChoiceNewsEventsBatch,
      getResearchCalendarEvents: vi.fn(async () => []),
    });

    renderHook(
      () =>
        useDashboardHomeBodyData({
          dataClient,
          supplementalReportDate: "2026-05-31",
          loadBasicData: false,
          loadEventFeeds: true,
          loadSecondaryEventFeeds: true,
          loadBondNewsFeeds: true,
          loadFormalData: false,
        }),
      { wrapper: createWrapper(queryClient) },
    );

    await waitFor(() => {
      expect(getChoiceNewsEventsBatch).toHaveBeenCalled();
    });
    const queryPrefixes = [
      ["dashboard", "macro-news"],
      ["dashboard", "macro-news-fallback"],
      ["dashboard", "bond-news"],
    ] as const;
    for (const prefix of queryPrefixes) {
      const query = queryClient
        .getQueryCache()
        .getAll()
        .find((candidate) =>
          prefix.every((part, index) => candidate.queryKey[index] === part),
        );
      expect(query?.observers[0]?.options.refetchInterval).toBe(
        DASHBOARD_HOME_CONTENT_REFETCH_INTERVAL_MS,
      );
      expect(query?.observers[0]?.options.staleTime).toBe(
        DASHBOARD_HOME_CONTENT_REFETCH_INTERVAL_MS,
      );
      expect(query?.observers[0]?.options.refetchIntervalInBackground).toBe(false);
      expect(query?.observers[0]?.options.refetchOnWindowFocus).toBe(true);
    }
  });

  it("requests return-decomposition and campisi with detail=summary", async () => {
    const getBondAnalyticsReturnDecomposition = vi.fn(
      async () =>
        ({
          result_meta: {
            basis: "formal",
            trace_id: "tr_rd",
            result_kind: "bond.return_decomposition",
            formal_use_allowed: true,
            source_version: "sv",
            vendor_version: "vv",
            rule_version: "rv",
            cache_version: "cv",
            quality_flag: "ok",
            vendor_status: "ok",
            fallback_mode: "none",
            scenario_flag: false,
            generated_at: "2026-06-04T00:00:00Z",
          },
          result: {},
        }) as never,
    );
    const getPnlCampisiFourEffects = vi.fn(
      async () =>
        ({
          result_meta: {
            basis: "formal",
            trace_id: "tr_campisi",
            result_kind: "campisi.four_effects",
            formal_use_allowed: true,
            source_version: "sv",
            vendor_version: "vv",
            rule_version: "rv",
            cache_version: "cv",
            quality_flag: "ok",
            vendor_status: "ok",
            fallback_mode: "none",
            scenario_flag: false,
            generated_at: "2026-06-04T00:00:00Z",
          },
          result: { by_bond: [], totals: {} },
        }) as never,
    );
    const dataClient = createHomeBodyClient({
      getBondAnalyticsReturnDecomposition,
      getPnlCampisiFourEffects,
      getChoiceNewsEventsBatch: vi.fn(async (options) => choiceNewsBatchEnvelope(options)),
      getResearchCalendarEvents: vi.fn(async () => []),
      getBondAnalyticsCreditSpreadMigration: vi.fn(async () => ({}) as never),
      getBondAnalyticsYieldCurveTermStructure: vi.fn(async () => ({}) as never),
    });

    renderHook(
      () =>
        useDashboardHomeBodyData({
          dataClient,
          supplementalReportDate: "2026-05-31",
          loadBasicData: false,
          loadEventFeeds: false,
          loadSecondaryEventFeeds: false,
          loadBondNewsFeeds: false,
          loadFormalData: true,
        }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => {
      expect(getBondAnalyticsReturnDecomposition).toHaveBeenCalledWith(
        "2026-05-31",
        "MoM",
        expect.objectContaining({ detail: "summary" }),
      );
      expect(getPnlCampisiFourEffects).toHaveBeenCalledWith(
        expect.objectContaining({ endDate: "2026-05-31", lookbackDays: 30, detail: "summary" }),
      );
    });
  });
});
