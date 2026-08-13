import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type { ChoiceNewsEvent, ResultMeta } from "../api/contracts";
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

function makeEvent(
  partial: Partial<ChoiceNewsEvent> & Pick<ChoiceNewsEvent, "event_key">,
): ChoiceNewsEvent {
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

function eventsEnvelope(options: {
  offset: number;
  totalRows: number;
  events: ChoiceNewsEvent[];
}) {
  return {
    result_meta: buildMeta("news.choice.events", `tr_news_${options.offset}`),
    result: {
      total_rows: options.totalRows,
      limit: PAGE_SIZE,
      offset: options.offset,
      as_of_date: "2026-04-24",
      excluded_future_rows: 0,
      events: options.events,
    },
  };
}

describe("NewsEventsPage states and filters", () => {
  it("shows the in-page error surface on load failure and recovers via retry", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const getChoiceNewsEvents = vi
      .fn()
      .mockRejectedValueOnce(new Error("choice callback source down"))
      .mockResolvedValue(
        eventsEnvelope({
          offset: 0,
          totalRows: 1,
          events: [makeEvent({ event_key: "ev-recovered", payload_text: "恢复后的第一行" })],
        }),
      );

    renderNewsPage({ ...base, getChoiceNewsEvents });

    const errorSurface = await screen.findByTestId("page-async-section-error");
    expect(errorSurface).toHaveTextContent("数据载入失败。");
    expect(screen.queryByTestId("news-events-table")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "重试" }));

    expect(await screen.findByText("恢复后的第一行")).toBeInTheDocument();
    expect(screen.queryByTestId("page-async-section-error")).not.toBeInTheDocument();
    expect(getChoiceNewsEvents).toHaveBeenCalledTimes(2);
  });

  it("renders the empty state with zeroed KPIs and a disabled pager for an empty page", async () => {
    const base = createApiClient({ mode: "mock" });
    const getChoiceNewsEvents = vi.fn(async () =>
      eventsEnvelope({ offset: 0, totalRows: 0, events: [] }),
    );

    renderNewsPage({ ...base, getChoiceNewsEvents });

    expect(await screen.findByTestId("page-async-section-empty")).toHaveTextContent(
      "当前暂无可展示内容。",
    );
    expect(screen.getByTestId("news-events-total-count")).toHaveTextContent("0");
    expect(screen.getByTestId("news-events-current-page-kpi")).toHaveTextContent("1 / 1");
    // 空结果时不得出现事件表格
    expect(screen.queryByTestId("news-events-table")).not.toBeInTheDocument();
  });

  it("resets the offset to zero when toggling the error-only filter from a later page", async () => {
    const user = userEvent.setup();
    const base = createApiClient({ mode: "mock" });
    const getChoiceNewsEvents = vi.fn(
      async (options: { limit: number; offset: number; errorOnly?: boolean }) =>
        eventsEnvelope({
          offset: options.offset,
          totalRows: 120,
          events: [
            makeEvent({
              event_key: `ev-${options.offset}-${options.errorOnly ? "err" : "all"}`,
              payload_text: `offset=${options.offset} errorOnly=${String(Boolean(options.errorOnly))}`,
            }),
          ],
        }),
    );

    renderNewsPage({ ...base, getChoiceNewsEvents });

    expect(await screen.findByText("offset=0 errorOnly=false")).toBeInTheDocument();

    await user.click(screen.getByTestId("news-events-next"));
    await waitFor(() =>
      expect(getChoiceNewsEvents).toHaveBeenCalledWith(
        expect.objectContaining({ offset: PAGE_SIZE, limit: PAGE_SIZE }),
      ),
    );
    expect(screen.getByTestId("news-events-page")).toHaveTextContent("2 / 3");

    await user.click(screen.getByLabelText("news-events-error-only"));

    // 切换错误筛选后必须回到第一页，并把 error_only 传给服务端
    await waitFor(() =>
      expect(getChoiceNewsEvents.mock.calls.at(-1)?.[0]).toMatchObject({
        offset: 0,
        errorOnly: true,
        limit: PAGE_SIZE,
      }),
    );
    expect(await screen.findByText("offset=0 errorOnly=true")).toBeInTheDocument();
    expect(screen.getByTestId("news-events-page")).toHaveTextContent("1 / 3");
  });

  it("counts error rows on the page and falls back to error_msg in the summary cell", async () => {
    const base = createApiClient({ mode: "mock" });
    const getChoiceNewsEvents = vi.fn(async () =>
      eventsEnvelope({
        offset: 0,
        totalRows: 3,
        events: [
          makeEvent({ event_key: "ev-ok", payload_text: "正常事件正文" }),
          makeEvent({
            event_key: "ev-error",
            error_code: 5,
            error_msg: "供应商错误 E5",
            payload_text: "",
            payload_json: null,
          }),
          makeEvent({
            event_key: "ev-empty",
            error_code: 0,
            payload_text: "",
            payload_json: null,
          }),
        ],
      }),
    );

    renderNewsPage({ ...base, getChoiceNewsEvents });

    expect(await screen.findByText("正常事件正文")).toBeInTheDocument();
    // 当前页错误行 KPI 只统计 error_code != 0 的行
    expect(screen.getByTestId("news-events-error-count")).toHaveTextContent("1");
    // 错误行摘要回退到 error_msg，空信封回退到固定文案
    expect(screen.getByText("供应商错误 E5")).toBeInTheDocument();
    expect(screen.getByText("空回调信封。")).toBeInTheDocument();
  });
});
