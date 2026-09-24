import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type { ChoiceNewsEvent, ResultMeta } from "../api/contracts";
import NewsEventsPage from "../features/news-events/NewsEventsPage";
import { EM_DASH } from "../utils/format";

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

    // P0 假零防线：请求失败时 KPI 不得冒充 0，必须显示 EM_DASH 加状态注记。
    const totalCard = screen.getByTestId("news-events-total-count");
    expect(totalCard).toHaveTextContent(EM_DASH);
    expect(totalCard).not.toHaveTextContent("0");
    expect(totalCard).toHaveTextContent("查询失败，数值不可用");
    const pageCard = screen.getByTestId("news-events-current-page-kpi");
    expect(pageCard).toHaveTextContent(EM_DASH);
    expect(pageCard).not.toHaveTextContent("1 / 1");
    const errorCountCard = screen.getByTestId("news-events-error-count");
    expect(errorCountCard).toHaveTextContent(EM_DASH);
    expect(errorCountCard).not.toHaveTextContent("0");
    expect(errorCountCard).toHaveTextContent("查询失败，数值不可用");

    await user.click(screen.getByRole("button", { name: "重试" }));

    expect(await screen.findByText("恢复后的第一行")).toBeInTheDocument();
    expect(screen.queryByTestId("page-async-section-error")).not.toBeInTheDocument();
    expect(getChoiceNewsEvents).toHaveBeenCalledTimes(2);
    // 重试成功后 KPI 恢复为服务端返回的真实数值。
    expect(screen.getByTestId("news-events-total-count")).toHaveTextContent("1");
    expect(screen.getByTestId("news-events-error-count")).toHaveTextContent("0");
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

  it("formats received time, extracts payload_json headline, and keeps raw values in title", async () => {
    const base = createApiClient({ mode: "mock" });
    const rawJson =
      '{"headline":"Policy follow-up","summary":"PBOC open-market operation commentary stream."}';
    const getChoiceNewsEvents = vi.fn(async () =>
      eventsEnvelope({
        offset: 0,
        totalRows: 2,
        events: [
          makeEvent({
            event_key: "ev-json",
            received_at: "2026-04-10T09:01:00Z",
            topic_code: "tushare.news.sina",
            payload_text: null,
            payload_json: rawJson,
          }),
          makeEvent({
            event_key: "ev-callback",
            topic_code: "__callback__",
            payload_text: "回调正文",
          }),
        ],
      }),
    );

    renderNewsPage({ ...base, getChoiceNewsEvents });

    // 接收时间列格式化为 MM-DD HH:mm，ISO 原值收 title。
    const timeCell = await screen.findByText("04-10 09:01");
    expect(timeCell).toHaveAttribute("title", "2026-04-10T09:01:00Z");
    // 摘要列提取 headline，未解析 JSON 原文收 title。
    const summaryCell = screen.getByText(/Policy follow-up：PBOC open-market/);
    expect(summaryCell).toHaveAttribute("title", rawJson);
    expect(screen.queryByText(rawJson)).not.toBeInTheDocument();
    // 常见来源 token 中文映射，原始 token 收 title。
    const topicCell = screen.getByText("市场快讯（Tushare·sina）");
    expect(topicCell).toHaveAttribute("title", "tushare.news.sina");
    expect(screen.getByText("供应商回调")).toHaveAttribute("title", "__callback__");
  });

  it("surfaces an amber degradation hint when meta quality/fallback are not clean", async () => {
    const base = createApiClient({ mode: "mock" });
    const envelope = eventsEnvelope({
      offset: 0,
      totalRows: 1,
      events: [makeEvent({ event_key: "ev-degraded", payload_text: "降级样本行" })],
    });
    envelope.result_meta = {
      ...envelope.result_meta,
      quality_flag: "stale",
      fallback_mode: "latest_snapshot",
      requested_report_date: "2026-08-13",
      resolved_report_date: "2026-08-10",
    };
    const getChoiceNewsEvents = vi.fn(async () => envelope);

    renderNewsPage({ ...base, getChoiceNewsEvents });

    const hint = await screen.findByTestId("news-events-quality-hint");
    expect(hint).toHaveTextContent("质量=stale");
    expect(hint).toHaveTextContent("降级=latest_snapshot");
    expect(hint).toHaveTextContent("请求日=2026-08-13");
    expect(hint).toHaveTextContent("实际日=2026-08-10");

    // 元信息条同步露出质量/降级/请求日/实际日字段。
    const meta = screen.getByTestId("news-events-result-meta");
    expect(meta).toHaveTextContent("质量=stale");
    expect(meta).toHaveTextContent("降级=latest_snapshot");
    expect(meta).toHaveTextContent("请求日=2026-08-13");
    expect(meta).toHaveTextContent("实际日=2026-08-10");
  });

  it("hides the degradation hint when meta is ok with no fallback", async () => {
    const base = createApiClient({ mode: "mock" });
    const getChoiceNewsEvents = vi.fn(async () =>
      eventsEnvelope({
        offset: 0,
        totalRows: 1,
        events: [makeEvent({ event_key: "ev-clean", payload_text: "正常样本行" })],
      }),
    );

    renderNewsPage({ ...base, getChoiceNewsEvents });

    expect(await screen.findByText("正常样本行")).toBeInTheDocument();
    expect(screen.queryByTestId("news-events-quality-hint")).not.toBeInTheDocument();
    // 未返回请求日/实际日时元信息条以 EM_DASH 占位。
    const meta = screen.getByTestId("news-events-result-meta");
    expect(meta).toHaveTextContent("质量=ok");
    expect(meta).toHaveTextContent("降级=none");
    expect(meta).toHaveTextContent(`请求日=${EM_DASH}`);
    expect(meta).toHaveTextContent(`实际日=${EM_DASH}`);
  });
});
