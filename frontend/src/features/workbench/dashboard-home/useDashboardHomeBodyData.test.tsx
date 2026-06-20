import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { createApiClient, type ApiClient } from "../../../api/client";
import type { ApiEnvelope, ChoiceNewsEvent, ChoiceNewsEventsPayload } from "../../../api/contracts";
import {
  DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS,
  DASHBOARD_MACRO_NEWS_TOPICS,
} from "../dashboard/dashboardMacroNewsTopics";
import { useDashboardHomeBodyData } from "./useDashboardHomeBodyData";

function createWrapper() {
  return function Wrapper({ children }: { children: ReactNode }) {
    const queryClient = new QueryClient({
      defaultOptions: {
        queries: {
          retry: false,
          staleTime: 0,
          gcTime: 0,
          refetchOnWindowFocus: false,
        },
      },
    });

    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

function choiceNewsEnvelope(events: ChoiceNewsEvent[]): ApiEnvelope<ChoiceNewsEventsPayload> {
  return {
    result_meta: {
      basis: "formal",
      trace_id: "tr_home_macro_news_test",
      result_kind: "news.choice.latest",
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
      total_rows: events.length,
      limit: events.length,
      offset: 0,
      events,
    },
  };
}

function choiceEvent(partial: Partial<ChoiceNewsEvent> & Pick<ChoiceNewsEvent, "event_key" | "received_at" | "topic_code" | "payload_text">): ChoiceNewsEvent {
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
    const getChoiceNewsEvents = vi.fn<ApiClient["getChoiceNewsEvents"]>(async () => choiceNewsEnvelope([]));
    const dataClient = createHomeBodyClient({
      getChoiceNewsEvents,
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
      expect(getChoiceNewsEvents).toHaveBeenCalledWith(
        expect.objectContaining({ topicCode: DASHBOARD_MACRO_NEWS_TOPICS[0].code }),
      );
    });
    expect(getChoiceNewsEvents).not.toHaveBeenCalledWith(
      expect.objectContaining({ topicCode: DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS[1].code }),
    );
  });

  it("loads macro fallback feeds after Choice macro news has no usable policy funding rows", async () => {
    const getChoiceNewsEvents = vi.fn<ApiClient["getChoiceNewsEvents"]>(async () => choiceNewsEnvelope([]));
    const dataClient = createHomeBodyClient({
      getChoiceNewsEvents,
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
      expect(getChoiceNewsEvents).toHaveBeenCalledWith(
        expect.objectContaining({ topicCode: DASHBOARD_MACRO_NEWS_TOPICS[0].code }),
      );
    });
    await waitFor(() => {
      expect(getChoiceNewsEvents).toHaveBeenCalledWith(
        expect.objectContaining({ topicCode: DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS[1].code }),
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
    const getChoiceNewsEvents = vi.fn<ApiClient["getChoiceNewsEvents"]>(async (params) =>
      choiceNewsEnvelope(params.topicCode === DASHBOARD_MACRO_NEWS_TOPICS[0].code ? [freshPolicyFundingEvent] : []),
    );
    const dataClient = createHomeBodyClient({
      getChoiceNewsEvents,
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
      expect(getChoiceNewsEvents).toHaveBeenCalledWith(
        expect.objectContaining({ topicCode: DASHBOARD_MACRO_NEWS_TOPICS[0].code }),
      );
    });
    await waitFor(() => {
      expect(
        DASHBOARD_MACRO_NEWS_FALLBACK_TOPICS.some((topic) =>
          getChoiceNewsEvents.mock.calls.some(([params]) => params.topicCode === topic.code),
        ),
      ).toBe(false);
    });
  });
});
