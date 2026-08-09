import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
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
import { MarketFinancialChartsWorkbench } from "./MarketFinancialChartsWorkbench";
import type { ModuleHomeSourceQueries } from "./moduleHomeModel";

vi.mock("../../../lib/echarts", () => ({
  default: ({ option }: { option: unknown }) => (
    <div data-testid="market-financial-chart-canvas">
      {JSON.stringify(option)}
    </div>
  ),
}));

function meta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "chart-trace",
    basis: "analytical",
    result_kind: "real",
    formal_use_allowed: false,
    source_version: "chart-source",
    vendor_version: "chart-vendor",
    rule_version: "chart-rule",
    cache_version: "chart-cache",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    as_of_date: "2026-07-28",
    generated_at: "2026-07-28T09:00:00Z",
    ...overrides,
  };
}

function renderWorkbench(
  client: ApiClient,
  queries: ModuleHomeSourceQueries,
) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <ApiClientProvider client={client}>
      <QueryClientProvider client={queryClient}>
        <MarketFinancialChartsWorkbench queries={queries} />
      </QueryClientProvider>
    </ApiClientProvider>,
  );
}

describe("MarketFinancialChartsWorkbench", () => {
  it("uses the shared news query and keeps error quality above fallback/stale badges", () => {
    const base = createApiClient({ mode: "mock" });
    const getChoiceNewsEvents = vi.fn();
    const client: ApiClient = { ...base, getChoiceNewsEvents };
    const newsEnvelope: ApiEnvelope<ChoiceNewsEventsPayload> = {
      result: {
        total_rows: 11_108,
        limit: 500,
        offset: 0,
        as_of_date: "2026-07-28",
        excluded_future_rows: 0,
        payload_json_included: false,
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
            payload_text: "利率新闻",
            payload_json: null,
          },
        ],
      },
      result_meta: meta(),
    };
    const queries = {
      marketRates: {
        data: {
          result: { read_target: "duckdb", series: [] },
          result_meta: meta({
            quality_flag: "error",
            fallback_mode: "latest_snapshot",
            vendor_status: "vendor_stale",
          }),
        },
        isError: false,
      },
      newsEvents: {
        data: newsEnvelope,
        isError: false,
      },
    } as unknown as ModuleHomeSourceQueries;

    renderWorkbench(client, queries);

    const workbench = screen.getByTestId("module-home-market-financial-charts");
    const sectionTabs = screen.getAllByRole("tab");

    expect(workbench).toBeInTheDocument();
    expect(sectionTabs).toHaveLength(6);
    expect(
      workbench.querySelectorAll('[data-testid^="module-home-market-chart-"]'),
    ).toHaveLength(12);

    fireEvent.click(sectionTabs[4]!);

    expect(getChoiceNewsEvents).not.toHaveBeenCalled();
    expect(
      screen.getByTestId("module-home-market-chart-news-topic"),
    ).toBeInTheDocument();
    expect(
      screen.getByTestId("module-home-market-chart-news-date"),
    ).toBeInTheDocument();
    expect(workbench).toHaveTextContent("500");
    expect(
      screen.getByTestId("module-home-market-section-status-rates"),
    ).toHaveAttribute("data-tone", "error");
    expect(
      screen.getByTestId("module-home-market-section-status-rates"),
    ).toHaveTextContent("质量异常");
  });

  it("discloses failed reads and refresh failures with retained data", () => {
    const client = createApiClient({ mode: "mock" });
    const queries = {
      marketRates: {
        data: undefined,
        isError: true,
      },
      marketCatalog: {
        data: {
          result: { series: [] },
          result_meta: meta(),
        },
        isError: true,
      },
    } as unknown as ModuleHomeSourceQueries;

    renderWorkbench(client, queries);

    expect(
      screen.getByTestId("module-home-market-section-status-rates"),
    ).toHaveAttribute("data-tone", "error");
    expect(
      screen.getByTestId("module-home-market-section-status-rates"),
    ).toHaveTextContent("读取失败");
    expect(
      screen.getByTestId("module-home-market-section-status-coverage"),
    ).toHaveAttribute("data-tone", "error");
    expect(
      screen.getByTestId("module-home-market-section-status-coverage"),
    ).toHaveTextContent("刷新失败 · 保留旧数据");
  });
});
