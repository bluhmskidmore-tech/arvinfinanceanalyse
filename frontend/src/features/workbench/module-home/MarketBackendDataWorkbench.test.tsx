import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import {
  ApiClientProvider,
  createApiClient,
  type ApiClient,
} from "../../../api/client";
import type {
  ApiEnvelope,
  ChoiceNewsEventsPayload,
  ResultMeta,
} from "../../../api/contracts";
import { EM_DASH } from "../../../utils/format";
import {
  MarketBackendDataWorkbench,
  MarketPayloadNode,
} from "./MarketBackendDataWorkbench";
import type { ModuleHomeSourceQueries } from "./moduleHomeModel";

function meta(sourceVersion: string): ResultMeta {
  return {
    trace_id: `trace-${sourceVersion}`,
    basis: "analytical",
    result_kind: "real",
    formal_use_allowed: false,
    source_version: sourceVersion,
    vendor_version: "vendor-v1",
    rule_version: "rule-v1",
    cache_version: "cache-v1",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    as_of_date: "2026-07-28",
    generated_at: "2026-07-28T09:00:00Z",
    tables_used: ["market_fact"],
    filters_applied: { scope: "all" },
  };
}

function query<T>(data: ApiEnvelope<T>) {
  return {
    data,
    isLoading: false,
    isFetching: false,
    isError: false,
    error: null,
  };
}

function renderWithProviders(children: ReactNode, client: ApiClient) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <ApiClientProvider client={client}>
      <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
    </ApiClientProvider>,
  );
}

describe("MarketBackendDataWorkbench", () => {
  it("preserves quote precision, per-row dates, zero and missing values while retaining exact raw evidence", async () => {
    const series = [
      { series_id: "rate", series_name: "original", display_name: "10年国债", value_numeric: 1.6804, latest_change: 0.0005999999999999339, unit: "%", trade_date: "2026-09-04", quality_flag: "stale" },
      { series_id: "zero", series_name: "真实零", value_numeric: 0, latest_change: 0, unit: "bp", trade_date: "2026-09-01", quality_flag: "ok" },
      { series_id: "missing", series_name: "缺失值", value_numeric: null, latest_change: null, unit: "%", trade_date: null, quality_flag: "missing" },
    ];
    const queries = {
      choiceLatest: query({ result: { series }, result_meta: meta("precise") }),
    } as unknown as ModuleHomeSourceQueries;
    renderWithProviders(<MarketBackendDataWorkbench queries={queries} />, createApiClient({ mode: "mock" }));
    const table = screen.getByRole("table", { name: "最新行情" });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows[0]).toHaveTextContent("10年国债1.6804%+0.00062026-09-04数据过期");
    expect(rows[1]).toHaveTextContent("真实零0bp02026-09-01质量正常");
    expect(rows[2]).toHaveTextContent(`缺失值${EM_DASH}%${EM_DASH}${EM_DASH}数据缺失`);
    await userEvent.click(within(rows[0]!).getByRole("button", { name: "核验 10年国债" }));
    const detail = screen.getByRole("dialog");
    expect(detail).toHaveTextContent("0.0005999999999999339");
    expect(detail).toHaveTextContent("original");
    expect(detail).toHaveTextContent("1.6804");
  });

  it("shows business columns first and keeps every source field accessible in record details", async () => {
    const base = createApiClient({ mode: "mock" });
    const queries = {
      choiceLatest: query({
        result: {
          read_target: "duckdb",
          series: [
            {
              series_id: "series.alpha",
              series_name: "测试序列",
              trade_date: "2026-07-28",
              value_numeric: 1.25,
              frequency: "daily",
              unit: "%",
              latest_change: 0.05,
              quality_flag: "ok",
              source_version: "choice-source-v1",
              vendor_version: "choice-vendor-v1",
              vendor_name: "Choice",
              refresh_tier: "stable",
              fetch_mode: "latest",
              fetch_granularity: "single",
              policy_note: "authoritative",
              recent_points: [
                {
                  trade_date: "2026-07-27",
                  value_numeric: 1.2,
                  source_version: "choice-source-v1",
                  vendor_version: "choice-vendor-v1",
                  quality_flag: "ok",
                },
              ],
            },
          ],
        },
        result_meta: meta("choice-meta-v1"),
      }),
      marketRates: query({
        result: { series: [{ series_id: "rate-1", series_name: "rate", value_numeric: 1 }] },
        result_meta: meta("rates-meta-v1"),
      }),
      marketCatalog: query({
        result: { series: [{ series_id: "catalog-1", series_name: "catalog" }] },
        result_meta: meta("catalog-meta-v1"),
      }),
      macroToolkitAnalysis: query({
        result: { alpha: 1, beta: 2 },
        result_meta: meta("macro-meta-v1"),
      }),
      macroToolkitStrategySummaries: query({
        result: { strategies: [], shadow_portfolio_report: null },
        result_meta: meta("strategy-meta-v1"),
      }),
      newsEvents: query({
        result: { total_rows: 11_108 },
        result_meta: meta("news-meta-v1"),
      }),
    } as unknown as ModuleHomeSourceQueries;

    renderWithProviders(<MarketBackendDataWorkbench queries={queries} />, base);

    const workbench = screen.getByTestId("module-home-market-backend-data");
    expect(workbench).toBeInTheDocument();
    expect(screen.getAllByRole("tab")).toHaveLength(6);
    expect(workbench).toHaveTextContent("6");
    expect(workbench).toHaveTextContent("11,108");
    expect(workbench).toHaveTextContent("6 / 6");
    expect(
      screen.getByTestId("module-home-market-backend-audit-summary"),
    ).toBeInTheDocument();
    for (const key of [
      "choice",
      "rates",
      "catalog",
      "macro",
      "strategies",
      "news",
    ]) {
      expect(
        screen.getByTestId(`module-home-market-backend-source-status-${key}`),
      ).toBeInTheDocument();
    }
    const table = screen.getByRole("table", { name: "最新行情" });
    expect(within(table).getAllByRole("columnheader").map((cell) => cell.textContent)).toEqual([
      "指标", "最新值", "单位", "较前值变化", "数据日期", "质量", "详情",
    ]);
    expect(table).not.toHaveTextContent("series.alpha");
    expect(table).not.toHaveTextContent("policy_note");
    await userEvent.click(screen.getByRole("button", { name: "核验 测试序列" }));
    const detail = await screen.findByRole("dialog");
    expect(detail).toHaveTextContent("series.alpha");
    expect(detail).toHaveTextContent("policy_note");
    expect(detail).toHaveTextContent("choice-source-v1");
    await userEvent.click(within(detail).getByRole("button", { name: /close/i }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(workbench).toHaveTextContent("choice-meta-v1");
    expect(workbench).not.toHaveTextContent("filters_applied");
    await userEvent.click(screen.getByText("结果口径与来源"));
    await userEvent.click(screen.getByText("其余来源与口径字段"));
    await waitFor(() => expect(workbench).toHaveTextContent("filters_applied"));
  });

  it("renders an em dash instead of a date-missing sentence in the 04 header", () => {
    const base = createApiClient({ mode: "mock" });
    const queries = {
      choiceLatest: query({
        result: { read_target: "duckdb", series: [] },
        result_meta: { ...meta("choice-meta-v1"), as_of_date: null },
      }),
    } as unknown as ModuleHomeSourceQueries;

    renderWithProviders(<MarketBackendDataWorkbench queries={queries} />, base);

    const workbench = screen.getByTestId("module-home-market-backend-data");
    const header = workbench.querySelector("header")!;

    expect(header).toHaveTextContent(`数据日期${EM_DASH}`);
    expect(workbench).not.toHaveTextContent("日期未返回");
  });

  it("does not downgrade a quality error when the vendor is stale", () => {
    const base = createApiClient({ mode: "mock" });
    const abnormalMeta: ResultMeta = {
      ...meta("choice-meta-error"),
      quality_flag: "error",
      vendor_status: "vendor_stale",
    };
    const queries = {
      choiceLatest: query({
        result: { series: [] },
        result_meta: abnormalMeta,
      }),
    } as unknown as ModuleHomeSourceQueries;

    renderWithProviders(<MarketBackendDataWorkbench queries={queries} />, base);

    const sourceState = screen.getByTestId(
      "module-home-market-backend-source-status-choice",
    );
    expect(sourceState).toHaveAttribute("data-tone", "error");
    expect(sourceState).toHaveTextContent("质量异常");
    expect(sourceState).toHaveTextContent("供应方数据过期");
  });

  it("loads paged news data with payload json and keeps result_meta visible", async () => {
    const base = createApiClient({ mode: "mock" });
    const newsEnvelope: ApiEnvelope<ChoiceNewsEventsPayload> = {
      result: {
        total_rows: 11_108,
        limit: 50,
        offset: 0,
        as_of_date: "2026-07-28",
        excluded_future_rows: 0,
        payload_json_included: true,
        compare: {
          basis: "analytical",
          rule_version: "news-rule-v1",
          same_direction: [],
          conflicting: [],
          review_needed: [],
          candidate_scenarios: [],
        },
        events: [
          {
            event_key: "event-1",
            received_at: "2026-07-28T08:00:00Z",
            group_id: "market",
            content_type: "news",
            serial_id: 1,
            request_id: 2,
            error_code: 0,
            error_msg: "",
            topic_code: "rates",
            item_index: 0,
            payload_text: "完整新闻正文",
            payload_json: '{"headline":"完整新闻正文"}',
          },
        ],
      },
      result_meta: meta("news-meta-v1"),
    };
    const getChoiceNewsEvents = vi.fn(async () => newsEnvelope);
    const client: ApiClient = { ...base, getChoiceNewsEvents };

    renderWithProviders(
      <MarketBackendDataWorkbench queries={{} as ModuleHomeSourceQueries} />,
      client,
    );
    fireEvent.click(screen.getAllByRole("tab")[5]!);

    await waitFor(() => {
      expect(getChoiceNewsEvents).toHaveBeenCalledWith({
        limit: 50,
        offset: 0,
        includePayloadJson: true,
      });
    });
    expect(
      (await screen.findAllByText(/完整新闻正文/)).length,
    ).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(/后端共 11,108 条/)).toBeInTheDocument();
    expect(screen.getByText("news-meta-v1")).toBeInTheDocument();
  });

  it("mounts unknown nested fields on expansion and releases them on collapse", async () => {
    render(
      <MarketPayloadNode
        path="custom"
        value={{
          custom_backend_block: {
            unknown_metric: 42,
            nested_records: [{ raw_field: "kept" }],
          },
        }}
      />,
    );

    expect(screen.getByText("custom_backend_block")).toBeInTheDocument();
    expect(screen.getByText("unknown_metric")).toBeInTheDocument();
    expect(screen.getByText("42")).toBeInTheDocument();
    expect(screen.queryByText("raw_field")).not.toBeInTheDocument();
    const nestedSummary = screen.getByText("nested_records");
    await userEvent.click(nestedSummary);
    await screen.findByText("raw_field");
    expect(screen.getByText("kept")).toBeInTheDocument();
    await userEvent.click(nestedSummary);
    await waitFor(() => expect(screen.queryByText("raw_field")).not.toBeInTheDocument());
    await userEvent.click(nestedSummary);
    expect(await screen.findByText("kept")).toBeInTheDocument();
  });

  it("keeps cached rows compact and mounts history only for the expanded row", async () => {
    const series = Array.from({ length: 25 }, (_, row) => ({
      series_id: `series-${row}`,
      series_name: `报价 ${row}`,
      trade_date: "2026-09-04",
      value_numeric: 1.25,
      unit: "%",
      recent_points: Array.from({ length: 20 }, (_, point) => ({
        trade_date: "2026-09-03",
        value_numeric: point,
        quality_flag: "ok",
        source_version: `history-source-${row}-${point}`,
        vendor_version: `history-vendor-${row}-${point}`,
      })),
    }));
    const queries = {
      choiceLatest: query({ result: { read_target: "duckdb", series }, result_meta: meta("history-meta") }),
    } as unknown as ModuleHomeSourceQueries;
    renderWithProviders(<MarketBackendDataWorkbench queries={queries} />, createApiClient({ mode: "mock" }));
    const workbench = screen.getByTestId("module-home-market-backend-data");
    const initialNodeCount = workbench.querySelectorAll("*").length;
    expect(initialNodeCount).toBeLessThan(1000);
    expect(screen.queryByText("history-source-0-0")).not.toBeInTheDocument();
    const historyButton = screen.getByRole("button", { name: "核验 报价 0" });
    await userEvent.click(historyButton);
    expect(await screen.findByText("history-source-0-0")).toBeInTheDocument();
    expect(screen.queryByText("history-source-1-0")).not.toBeInTheDocument();
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: /close/i }));
    await waitFor(() => expect(screen.queryByText("history-source-0-0")).not.toBeInTheDocument());
    expect(workbench.querySelectorAll("*").length).toBe(initialNodeCount);
    await userEvent.click(historyButton);
    expect(await screen.findByText("history-source-0-0")).toBeInTheDocument();
  });

  it("keeps long lineage values compact while allowing expand and copy", async () => {
    const writeText = vi.fn(async () => undefined);
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    const longVersion = `source-${"v".repeat(120)}`;

    render(
      <MarketPayloadNode
        path="lineage"
        value={{ source_version: longVersion }}
      />,
    );

    const expandButton = screen.getByRole("button", { name: /展开|expand/i });
    expect(expandButton).toHaveAttribute("aria-expanded", "false");
    fireEvent.click(expandButton);
    expect(screen.getByRole("button", { name: /收起|collapse/i })).toHaveAttribute(
      "aria-expanded",
      "true",
    );

    fireEvent.click(screen.getByRole("button", { name: /复制|copy/i }));
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(longVersion));
  });

  it("filters the active series table without dropping returned fields", () => {
    const base = createApiClient({ mode: "mock" });
    const queries = {
      choiceLatest: query({
        result: {
          read_target: "duckdb",
          series: [
            {
              series_id: "series.alpha",
              series_name: "Alpha 利率",
              value_numeric: 1.25,
            },
            {
              series_id: "series.beta",
              series_name: "Beta 商品",
              value_numeric: 86.9,
            },
          ],
        },
        result_meta: meta("choice-meta-v1"),
      }),
    } as unknown as ModuleHomeSourceQueries;

    renderWithProviders(<MarketBackendDataWorkbench queries={queries} />, base);
    fireEvent.change(
      screen.getByPlaceholderText("指标名称、代码或来源"),
      { target: { value: "beta" } },
    );

    expect(screen.getByText("Beta 商品")).toBeInTheDocument();
    expect(screen.queryByText("Alpha 利率")).not.toBeInTheDocument();
    expect(screen.getByText(/1\s*\/\s*2/)).toBeInTheDocument();
  });
});
