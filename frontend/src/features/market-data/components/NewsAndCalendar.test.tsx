import { useState, type ComponentProps, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../../../api/client";
import type { ChoiceNewsEventsPayload, ResearchCalendarEvent } from "../../../api/contracts";
import { NewsAndCalendar } from "./NewsAndCalendar";

function renderNewsCalendar(
  client: ApiClient,
  props: ComponentProps<typeof NewsAndCalendar> = {},
) {
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
      <NewsAndCalendar {...props} />
    </Wrapper>,
  );
}

function buildNewsPayload(events: ChoiceNewsEventsPayload["events"]): ChoiceNewsEventsPayload {
  return {
    total_rows: events.length,
    limit: 12,
    offset: 0,
    as_of_date: "2026-07-29",
    excluded_future_rows: 2,
    payload_json_included: true,
    events,
  };
}

function renderNewsCalendarWithQueryClient(client: ApiClient) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
    },
  });

  const result = render(
    <QueryClientProvider client={queryClient}>
      <ApiClientProvider client={client}>
        <NewsAndCalendar />
      </ApiClientProvider>
    </QueryClientProvider>,
  );

  return { ...result, queryClient };
}

describe("NewsAndCalendar", () => {
  it("renders text, structured JSON, and callback failures as business-safe news rows", () => {
    const base = createApiClient({ mode: "mock" });
    const payload = buildNewsPayload([
      {
        event_key: "text",
        received_at: "2026-07-29T09:01:00Z",
        group_id: "news",
        content_type: "sectornews",
        serial_id: 1,
        request_id: 11,
        error_code: 0,
        error_msg: "",
        topic_code: "raw-topic-code",
        item_index: 0,
        payload_text: "公开市场操作净投放保持平稳。",
        payload_json: null,
      },
      {
        event_key: "json",
        received_at: "2026-07-29T08:58:00Z",
        group_id: "news",
        content_type: "sectornews",
        serial_id: 2,
        request_id: 12,
        error_code: 0,
        error_msg: "",
        topic_code: "another-raw-topic",
        item_index: 0,
        payload_text: null,
        payload_json: '{"headline":"政策跟踪","summary":"央行延续流动性呵护。","internal_id":"secret"}',
      },
      {
        event_key: "error",
        received_at: "2026-07-29T08:50:00Z",
        group_id: "news",
        content_type: "callback",
        serial_id: 3,
        request_id: 13,
        error_code: 101,
        error_msg: "vendor callback timeout",
        topic_code: "__callback__",
        item_index: -1,
        payload_text: null,
        payload_json: null,
      },
    ]);

    renderNewsCalendar(base, {
      newsState: { payload, isLoading: false, isError: false },
      calendarState: { rows: [], isLoading: false, isError: false },
    });

    expect(screen.getByTestId("market-data-news-summary")).toHaveTextContent(
      "返回 3/3 条 · 查询截止 2026-07-29 · 排除未来事件 2 条",
    );
    expect(screen.getByText("公开市场操作净投放保持平稳。")).toBeInTheDocument();
    expect(screen.getByText("政策跟踪 — 央行延续流动性呵护。")).toBeInTheDocument();
    expect(screen.getByText("资讯源回调异常，事件内容暂不可用")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(
      /vendor callback timeout|raw-topic-code|another-raw-topic|__callback__|internal_id|secret/,
    );
  });

  it("renders governed news empty and error states", () => {
    const base = createApiClient({ mode: "mock" });
    const { rerender } = renderNewsCalendar(base, {
      newsState: { payload: buildNewsPayload([]), isLoading: false, isError: false },
      calendarState: { rows: [], isLoading: false, isError: false },
    });

    expect(screen.getByTestId("market-data-news-empty")).toHaveTextContent(
      "当前无资讯事件，请确认数据源或稍后刷新。",
    );

    rerender(
      <QueryClientProvider client={new QueryClient()}>
        <ApiClientProvider client={base}>
          <NewsAndCalendar
            newsState={{ payload: null, isLoading: false, isError: true }}
            calendarState={{ rows: [], isLoading: false, isError: false }}
          />
        </ApiClientProvider>
      </QueryClientProvider>,
    );
    expect(screen.getByTestId("market-data-news-error")).toHaveTextContent(
      "资讯加载失败，请稍后重试。",
    );
  });

  it("renders supply calendar rows when getResearchCalendarEvents returns events", async () => {
    const base = createApiClient({ mode: "mock" });
    const rows: ResearchCalendarEvent[] = [
      {
        id: "e1",
        date: "2026-05-10",
        title: "Mock 供给事件",
        kind: "supply",
        severity: "low",
        amount_label: "100 亿元",
        note: "测试备注",
      },
    ];
    const getResearchCalendarEvents = vi.fn(async () => rows);

    renderNewsCalendar({
      ...base,
      getResearchCalendarEvents,
    });

    fireEvent.click(screen.getByRole("tab", { name: "事件日历" }));
    expect(await screen.findByTestId("market-data-calendar-list")).toBeInTheDocument();
    expect(screen.getByText("Mock 供给事件")).toBeInTheDocument();
    expect(screen.getByText(/类型 供给/)).toBeInTheDocument();
    await waitFor(() => {
      expect(getResearchCalendarEvents).toHaveBeenCalled();
    });
  });

  it("shows calendar empty state when events array is empty", async () => {
    const base = createApiClient({ mode: "mock" });
    const getResearchCalendarEvents = vi.fn(async () => []);

    renderNewsCalendar({
      ...base,
      getResearchCalendarEvents,
    });

    fireEvent.click(screen.getByRole("tab", { name: "事件日历" }));
    expect(await screen.findByTestId("market-data-calendar-empty")).toBeInTheDocument();
    expect(screen.getByText("当前日历区间无供给/招标事件。")).toBeInTheDocument();
  });

  it("shows calendar error state when getResearchCalendarEvents rejects", async () => {
    const base = createApiClient({ mode: "mock" });
    const getResearchCalendarEvents = vi.fn(async () => {
      throw new Error("calendar unavailable");
    });

    renderNewsCalendar({
      ...base,
      getResearchCalendarEvents,
    });

    fireEvent.click(screen.getByRole("tab", { name: "事件日历" }));
    expect(await screen.findByTestId("market-data-calendar-error")).toBeInTheDocument();
    expect(screen.getByText("供给与招标日历加载失败，请稍后重试。")).toBeInTheDocument();
  });
  it("keeps news and calendar on independent stable refresh policies", async () => {
    const base = createApiClient({ mode: "mock" });
    const getChoiceNewsEvents = vi.fn((options) => base.getChoiceNewsEvents(options));
    const getResearchCalendarEvents = vi.fn(async () => []);

    const { queryClient } = renderNewsCalendarWithQueryClient({
      ...base,
      getChoiceNewsEvents,
      getResearchCalendarEvents,
    });

    expect(await screen.findByTestId("market-data-news-calendar")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "事件日历" }));
    expect(await screen.findByTestId("market-data-calendar-empty")).toBeInTheDocument();

    const newsQuery = queryClient.getQueryCache().find({
      queryKey: ["market-data", "headlines", "choice-events", "mock"],
      exact: true,
    });
    const calendarQuery = queryClient.getQueryCache().find({
      queryKey: ["market-data", "calendar", "supply-auctions", "mock"],
      exact: true,
    });

    expect(newsQuery?.observers[0]?.options.refetchIntervalInBackground).toBe(false);
    expect(calendarQuery?.observers[0]?.options.refetchIntervalInBackground).toBe(false);
    expect(
      typeof newsQuery?.observers[0]?.options.refetchInterval === "function"
        ? newsQuery.observers[0].options.refetchInterval(newsQuery)
        : newsQuery?.observers[0]?.options.refetchInterval,
    ).toBe(false);
    expect(getChoiceNewsEvents).toHaveBeenCalledWith({
      limit: 12,
      offset: 0,
      includePayloadJson: false,
    });
    expect(
      typeof calendarQuery?.observers[0]?.options.refetchInterval === "function"
        ? calendarQuery.observers[0].options.refetchInterval(calendarQuery)
        : calendarQuery?.observers[0]?.options.refetchInterval,
    ).toBe(false);
  });
});
