import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../../../api/client";
import type { ResearchCalendarEvent } from "../../../api/contracts";
import { MarketDataNewsCalendarSummary } from "./MarketDataNewsCalendarSummary";

function buildEvent(
  partial: Partial<ResearchCalendarEvent> & Pick<ResearchCalendarEvent, "id">,
): ResearchCalendarEvent {
  return {
    date: "2026-04-28",
    title: `事件 ${partial.id}`,
    kind: "supply",
    severity: "medium",
    ...partial,
  };
}

function renderSummary(client: ApiClient, reportDate = "2026-04-30") {
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
      <MemoryRouter>
        <QueryClientProvider client={queryClient}>
          <ApiClientProvider client={client}>{children}</ApiClientProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );
  }

  return render(
    <Wrapper>
      <MarketDataNewsCalendarSummary reportDate={reportDate} />
    </Wrapper>,
  );
}

describe("MarketDataNewsCalendarSummary", () => {
  it("renders the 3 most recent rate/supply events and excludes internal items", async () => {
    const base = createApiClient({ mode: "mock" });
    const getResearchCalendarEvents = vi.fn(async () => [
      buildEvent({ id: "e1", date: "2026-04-25", kind: "macro", title: "MLF 续作" }),
      buildEvent({
        id: "e2",
        date: "2026-04-29",
        kind: "auction",
        title: "国债招标",
        amount_label: "420 亿元",
      }),
      buildEvent({ id: "e3", date: "2026-04-30", kind: "internal", title: "内部合规事项" }),
      buildEvent({ id: "e4", date: "2026-04-28", kind: "supply", title: "地方债供给" }),
      buildEvent({ id: "e5", date: "2026-04-20", kind: "supply", title: "旧供给事件" }),
    ]);

    renderSummary({ ...base, getResearchCalendarEvents });

    const items = await screen.findAllByTestId("market-data-news-calendar-item");
    expect(items).toHaveLength(3);
    // 按事件日期倒序：招标（04-29）→ 供给（04-28）→ 宏观（04-25）；第 4 新的旧事件被截断。
    expect(items[0]).toHaveTextContent("2026-04-29");
    expect(items[0]).toHaveTextContent("国债招标");
    expect(items[0]).toHaveTextContent("发行/招标");
    expect(items[0]).toHaveTextContent("420 亿元");
    expect(items[1]).toHaveTextContent("地方债供给");
    expect(items[1]).toHaveTextContent("供给面");
    expect(items[2]).toHaveTextContent("MLF 续作");
    expect(items[2]).toHaveTextContent("宏观");
    expect(screen.queryByText("内部合规事项")).not.toBeInTheDocument();
    expect(screen.queryByText("旧供给事件")).not.toBeInTheDocument();
    expect(getResearchCalendarEvents).toHaveBeenCalledWith({ reportDate: "2026-04-30" });
  });

  it("shows an explicit empty state instead of demo events when nothing is relevant", async () => {
    const base = createApiClient({ mode: "mock" });
    const getResearchCalendarEvents = vi.fn(async (): Promise<ResearchCalendarEvent[]> => []);

    renderSummary({ ...base, getResearchCalendarEvents });

    expect(await screen.findByTestId("market-data-news-calendar-empty")).toHaveTextContent(
      "暂无覆盖事件",
    );
    expect(screen.queryAllByTestId("market-data-news-calendar-item")).toHaveLength(0);
  });

  it("surfaces the load failure and recovers through the retry button", async () => {
    const base = createApiClient({ mode: "mock" });
    const getResearchCalendarEvents = vi
      .fn<ApiClient["getResearchCalendarEvents"]>()
      .mockRejectedValueOnce(new Error("calendar unavailable"))
      .mockResolvedValueOnce([
        buildEvent({ id: "e1", date: "2026-04-29", kind: "supply", title: "地方债供给" }),
      ]);

    renderSummary({ ...base, getResearchCalendarEvents });

    expect(await screen.findByTestId("market-data-news-calendar-error")).toHaveTextContent(
      "资讯与日历读取失败",
    );
    // antd Button 会在两个 CJK 字符间插入空格（"重 试"）。
    fireEvent.click(screen.getByRole("button", { name: /重\s*试/ }));
    expect(await screen.findByText("地方债供给")).toBeInTheDocument();
    expect(getResearchCalendarEvents).toHaveBeenCalledTimes(2);
  });

  it("labels the card as analytical and links to the news-events page", async () => {
    const base = createApiClient({ mode: "mock" });
    const getResearchCalendarEvents = vi.fn(async (): Promise<ResearchCalendarEvent[]> => []);

    renderSummary({ ...base, getResearchCalendarEvents });

    const card = await screen.findByTestId("market-data-news-calendar-summary");
    expect(card).toHaveTextContent("资讯与日历");
    expect(card).toHaveTextContent("分析口径");
    // result_meta 被客户端剥离，stale 语义以"截至报告日"常驻标注替代。
    expect(await screen.findByTestId("market-data-news-calendar-asof")).toHaveTextContent(
      "截至 2026-04-30",
    );
    const link = screen.getByTestId("market-data-news-calendar-link");
    expect(link).toHaveTextContent("完整日历见新闻事件页");
    expect(link).toHaveAttribute("href", "/news-events");
  });

  it("keeps the skeleton and fires no request while the report date is missing", async () => {
    const base = createApiClient({ mode: "mock" });
    const getResearchCalendarEvents = vi.fn(async (): Promise<ResearchCalendarEvent[]> => []);

    renderSummary({ ...base, getResearchCalendarEvents }, "");

    expect(await screen.findByTestId("market-data-news-calendar-loading")).toBeInTheDocument();
    await waitFor(() => {
      expect(getResearchCalendarEvents).not.toHaveBeenCalled();
    });
  });
});
