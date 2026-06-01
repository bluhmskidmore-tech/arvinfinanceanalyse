import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../../../api/client";
import type { ResearchCalendarEvent } from "../../../api/contracts";
import { NewsAndCalendar } from "./NewsAndCalendar";

function renderNewsCalendar(client: ApiClient) {
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
      <NewsAndCalendar />
    </Wrapper>,
  );
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
    expect(
      typeof calendarQuery?.observers[0]?.options.refetchInterval === "function"
        ? calendarQuery.observers[0].options.refetchInterval(calendarQuery)
        : calendarQuery?.observers[0]?.options.refetchInterval,
    ).toBe(false);
  });
});
