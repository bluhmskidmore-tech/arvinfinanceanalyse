import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type { ChoiceNewsEvent, ResultMeta } from "../api/contracts";
import { listChoiceNewsTopicFilterOptions } from "../features/agent/lib/choiceNewsTopicDictionary";
import NewsEventsPage from "../features/news-events/NewsEventsPage";

const PAGE_SIZE = 50;

function renderNewsPage(client: ApiClient) {
  function Wrapper({ children }: { children: ReactNode }) {
    const [queryClient] = useState(
      () =>
        new QueryClient({
          defaultOptions: {
            queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
          },
        }),
    );

    return (
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>{children}</ApiClientProvider>
      </QueryClientProvider>
    );
  }

  return render(
    <Wrapper>
      <NewsEventsPage />
    </Wrapper>,
  );
}

function buildMeta(resultKind: string, traceId: string): ResultMeta {
  return {
    trace_id: traceId,
    basis: "analytical",
    result_kind: resultKind,
    formal_use_allowed: false,
    source_version: "sv_news_test",
    vendor_version: "vv_choice",
    rule_version: "rv_news_test",
    cache_version: "cv_news_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-12T08:00:00Z",
  };
}

function makeEvent(partial: Partial<ChoiceNewsEvent> & Pick<ChoiceNewsEvent, "event_key">): ChoiceNewsEvent {
  return {
    received_at: "2026-04-12T10:00:00Z",
    group_id: "g-1",
    content_type: "json",
    serial_id: 1,
    request_id: 1,
    error_code: 0,
    error_msg: "",
    topic_code: "TOPIC_A",
    item_index: 0,
    payload_text: "Headline alpha",
    payload_json: null,
    ...partial,
  };
}

describe("NewsEventsPage", () => {
  it("renders filters, table rows, resets page on topic change, and paginates", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const firstTopic = listChoiceNewsTopicFilterOptions()[0]?.topicCode ?? "FALLBACK_TOPIC";

    const getChoiceNewsEvents = vi.fn(
      async (options: { limit: number; offset: number; topicCode?: string }) => {
        const page1 = options.offset === 0;
        return {
          result_meta: buildMeta("news.choice.events", `tr_news_${options.offset}`),
          result: {
            total_rows: 75,
            limit: options.limit,
            offset: options.offset,
            events: page1
              ? [
                  makeEvent({
                    event_key: "ev-1",
                    topic_code: options.topicCode ?? "ALL",
                    payload_text: "第一页摘要 A",
                  }),
                  makeEvent({
                    event_key: "ev-2",
                    topic_code: "OTHER",
                    payload_text: "第一页摘要 B",
                  }),
                ]
              : [
                  makeEvent({
                    event_key: "ev-3",
                    topic_code: "PAGE2",
                    payload_text: "第二页唯一行",
                  }),
                ],
          },
        };
      },
    );

    renderNewsPage({
      ...base,
      getChoiceNewsEvents,
    });

    expect(await screen.findByTestId("news-events-page-title")).toHaveTextContent("新闻事件");
    expect(screen.getByText("事件概览")).toBeInTheDocument();
    expect(screen.getByText("筛选与事件列表")).toBeInTheDocument();
    expect(screen.getByLabelText("news-events-topic-code")).toBeInTheDocument();
    expect(screen.getByLabelText("news-events-error-only")).toBeInTheDocument();

    expect(await screen.findByText("第一页摘要 A")).toBeInTheDocument();
    expect(screen.getByText("第一页摘要 B")).toBeInTheDocument();
    expect(screen.getByTestId("news-events-total-count")).toHaveTextContent("75");
    expect(screen.getByTestId("news-events-current-page-kpi")).toHaveTextContent("1 / 2");
    expect(screen.getByTestId("news-events-error-count")).toHaveTextContent("0");
    expect(screen.getByTestId("news-events-active-topic")).toHaveTextContent("全部专题");

    expect(screen.getByTestId("news-events-page")).toHaveTextContent("1 / 2");

    await user.click(screen.getByTestId("news-events-next"));

    await waitFor(() => {
      expect(screen.getByTestId("news-events-page")).toHaveTextContent("2 / 2");
    });
    expect(screen.getByText("第二页唯一行")).toBeInTheDocument();

    expect(getChoiceNewsEvents).toHaveBeenCalledWith(
      expect.objectContaining({ offset: PAGE_SIZE, limit: PAGE_SIZE }),
    );

    await user.click(screen.getByTestId("news-events-prev"));

    await waitFor(() => {
      expect(screen.getByTestId("news-events-page")).toHaveTextContent("1 / 2");
      expect(getChoiceNewsEvents).toHaveBeenCalledWith(
        expect.objectContaining({ offset: 0, limit: PAGE_SIZE }),
      );
    });

    await user.click(screen.getByTestId("news-events-next"));
    await waitFor(() =>
      expect(screen.getByTestId("news-events-page")).toHaveTextContent("2 / 2"),
    );

    await user.selectOptions(screen.getByLabelText("news-events-topic-code"), firstTopic);

    await waitFor(() => {
      expect(screen.getByTestId("news-events-page")).toHaveTextContent("1 / 2");
      expect(getChoiceNewsEvents.mock.calls.at(-1)?.[0]).toMatchObject({
        offset: 0,
        topicCode: firstTopic,
        limit: PAGE_SIZE,
      });
    });
    expect(screen.getByTestId("news-events-active-topic")).toHaveTextContent(firstTopic);
  });
});
