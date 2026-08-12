import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import {
  ApiClientProvider,
  createApiClient,
  type ApiClient,
} from "../../../api/client";
import type {
  ApiEnvelope,
  ChoiceMacroLatestPayload,
  ChoiceNewsEvent,
  ChoiceNewsEventsPayload,
  MacroVendorPayload,
  ResultMeta,
} from "../../../api/contracts";
import type {
  MacroToolkitIndicator,
  MacroToolkitStrategySummariesPayload,
} from "../../../api/macroToolkitClient";
import { MarketOverviewDenseFirstScreen } from "./MarketOverviewDenseFirstScreen";
import type {
  ModuleHomeSourceQueries,
  ModuleHomeView,
} from "./moduleHomeModel";
import { useMarketHomeQueries } from "./useMarketHomeQueries";

vi.mock("../../../lib/echarts", () => ({
  default: ({ option }: { option: unknown }) => (
    <div data-testid="market-overview-dense-chart-canvas">
      {JSON.stringify(option)}
    </div>
  ),
}));

function resultMeta(overrides: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "macro-trace",
    basis: "analytical",
    result_kind: "real",
    formal_use_allowed: false,
    source_version: "macro-source-v1",
    vendor_version: "macro-vendor-v1",
    rule_version: "macro-rule-v1",
    cache_version: "macro-cache-v1",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    as_of_date: "2026-08-03",
    generated_at: "2026-08-03T09:00:00Z",
    ...overrides,
  };
}

function newsEnvelope(): ApiEnvelope<ChoiceNewsEventsPayload> {
  return {
    result: {
      total_rows: 500,
      limit: 500,
      offset: 0,
      as_of_date: "2026-08-03",
      excluded_future_rows: 0,
      payload_json_included: false,
      events: [],
    },
    result_meta: resultMeta(),
  };
}

function emptyChoiceEnvelope(): ApiEnvelope<ChoiceMacroLatestPayload> {
  return {
    result: {
      read_target: "duckdb",
      series: [],
    },
    result_meta: resultMeta(),
  };
}

function emptyCatalogEnvelope(): ApiEnvelope<MacroVendorPayload> {
  return {
    result: {
      read_target: "duckdb",
      series: [],
    },
    result_meta: resultMeta(),
  };
}

function emptyStrategyEnvelope(): ApiEnvelope<MacroToolkitStrategySummariesPayload> {
  return {
    result: {
      strategy_summaries: [],
    },
    result_meta: resultMeta(),
  };
}

function macroResult() {
  return {
    default_data_sources: [],
    as_of_date: "2026-08-03",
    conclusion: {
      stance: "Tight liquidity watch",
      tone: "negative" as const,
      summary: "Funding pressure remains elevated across the latest toolkit cut.",
      recommended_action: "Reduce intraday duration adds until funding normalizes.",
    },
    coverage: {
      indicator_count: 12,
      hit_count: 10,
      hit_rate: 0.833,
      script_count: 4,
      output_file_count: 3,
    },
    indicators: [],
    signal_cards: [],
    capability_results: [],
    strategy_summaries: [],
    output_files: [],
    source_checks: [],
    capabilities: [],
    warnings: [],
  };
}

function macroIndicator(
  overrides: Partial<MacroToolkitIndicator> &
    Pick<MacroToolkitIndicator, "key" | "label" | "latest_value">,
): MacroToolkitIndicator {
  return {
    alias: overrides.key,
    group: "macro",
    unit: "%",
    row_count: 12,
    latest_date: "2026-08-03",
    previous_value: null,
    change: null,
    change_pct: null,
    source: "choice",
    series_id: overrides.key,
    quality: "ok",
    ...overrides,
  };
}

function denseNewsEvent(
  eventKey: string,
  receivedAt: string,
  topicCode: string,
): ChoiceNewsEvent {
  return {
    event_key: eventKey,
    received_at: receivedAt,
    group_id: "macro",
    content_type: "news",
    serial_id: 1,
    request_id: 1,
    error_code: 0,
    error_msg: "",
    topic_code: topicCode,
    item_index: 0,
    payload_text: eventKey,
    payload_json: null,
  };
}

function macroQuery(
  overrides: Partial<NonNullable<ModuleHomeSourceQueries["macroToolkitAnalysis"]>> = {},
): ModuleHomeSourceQueries["macroToolkitAnalysis"] {
  return {
    data: {
      result: macroResult(),
      result_meta: resultMeta(),
    },
    isLoading: false,
    isFetching: false,
    isError: false,
    error: null,
    ...overrides,
  } as ModuleHomeSourceQueries["macroToolkitAnalysis"];
}

function baseView(): ModuleHomeView {
  return {
    kind: "market",
    title: "Market home",
    question: "What changed today?",
    summary: "Review the latest market snapshot.",
    sourceScope: "market",
    stateLabel: "Connected",
    stateDetail: "All market reads returned.",
    kpis: [],
    statuses: [],
    briefings: [
      {
        title: "Rates",
        conclusion: "Front-end copy",
        evidence: "Used only to keep layout stable in the focused test.",
        tone: "ok",
      },
    ],
    detailPanels: [],
    dataNote: {
      title: "Data note",
      lines: [],
      tone: "ok",
    },
    marketCrisisExplain: null,
    marketDeskIntel: null,
  };
}

function renderWithProviders(children: ReactNode, client: ApiClient) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <ApiClientProvider client={client}>
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>{children}</MemoryRouter>
      </QueryClientProvider>
    </ApiClientProvider>,
  );
}

describe("MarketOverviewDenseFirstScreen", () => {
  it("shows clean macro output as a non-formal review-only observation", () => {
    const client = createApiClient({ mode: "mock" });
    const queries = {
      macroToolkitAnalysis: macroQuery(),
      newsEvents: {
        data: newsEnvelope(),
        isLoading: false,
        isFetching: false,
        isError: false,
        error: null,
      },
    } as unknown as ModuleHomeSourceQueries;

    renderWithProviders(
      <MarketOverviewDenseFirstScreen
        view={baseView()}
        queries={queries}
        latestTradeDate="2026-08-03"
        searchValue=""
      />,
      client,
    );

    // 章节导航已上移到页壳层，组件内只保留分区头一处标题。
    expect(screen.getAllByText("分析观察")).toHaveLength(1);
    expect(screen.getByText("仅供复核 · 非正式")).toBeInTheDocument();
    expect(
      screen.getByTestId("module-home-market-dense-observation-title"),
    ).toHaveTextContent(
      "Tight liquidity watch",
    );
    expect(
      screen.getByTestId("module-home-market-dense-observation-summary"),
    ).toHaveTextContent("非正式观察，仅供复核。");
    expect(
      screen.getByTestId("module-home-market-dense-observation-basis"),
    ).toHaveTextContent("analytical");
    expect(
      screen.getByTestId("module-home-market-dense-observation-formal"),
    ).toHaveTextContent("false");
    expect(
      screen.getByTestId("module-home-market-dense-observation-quality"),
    ).toHaveTextContent("质量 正常 / 供应方 正常 / 回退 none");
    expect(
      screen.getByTestId("module-home-market-dense-observation-gate"),
    ).toHaveTextContent("仅供复核（非正式观察）");
    expect(
      screen.getByTestId("module-home-market-dense-observation-action"),
    ).toHaveTextContent(
      "待复核事项：Reduce intraday duration adds until funding normalizes.",
    );
    expect(
      screen.queryByText(
        "建议动作：Reduce intraday duration adds until funding normalizes.",
      ),
    ).not.toBeInTheDocument();
  });

  it("holds title, summary, and action when macro source quality is not clean", () => {
    const client = createApiClient({ mode: "mock" });
    const queries = {
      macroToolkitAnalysis: macroQuery({
        data: {
          result: macroResult(),
          result_meta: resultMeta({
            quality_flag: "stale",
            vendor_status: "vendor_stale",
            fallback_mode: "latest_snapshot",
            fallback_date: "2026-08-02",
          }),
        },
        isError: true,
        error: new Error("refresh failed"),
      }),
      newsEvents: {
        data: newsEnvelope(),
        isLoading: false,
        isFetching: false,
        isError: false,
        error: null,
      },
    } as unknown as ModuleHomeSourceQueries;

    renderWithProviders(
      <MarketOverviewDenseFirstScreen
        view={baseView()}
        queries={queries}
        latestTradeDate="2026-08-03"
        searchValue=""
      />,
      client,
    );

    expect(
      screen.getByTestId("module-home-market-dense-observation-title"),
    ).toHaveTextContent(
      "暂停形成今日判断",
    );
    expect(
      screen.getByTestId("module-home-market-dense-observation-summary"),
    ).toHaveTextContent(
      "本页不展示来源结论摘要",
    );
    expect(
      screen.getByTestId("module-home-market-dense-observation-summary"),
    ).toHaveTextContent(
      "请先核验来源证据，再形成判断。",
    );
    expect(
      screen.getByTestId("module-home-market-dense-observation-summary"),
    ).not.toHaveTextContent(
      "Funding pressure remains elevated across the latest toolkit cut.",
    );
    expect(
      screen.getByTestId("module-home-market-dense-observation-quality"),
    ).toHaveTextContent(
      "质量 过期 / 供应方 数据过期 / 回退 latest_snapshot/2026-08-02 / 刷新失败且保留缓存数据",
    );
    expect(
      screen.getByTestId("module-home-market-dense-observation-gate"),
    ).toHaveTextContent(
      "暂停判断：数据质量过期；供应方数据过期；使用回退数据（2026-08-02）；刷新失败且保留缓存数据",
    );
    expect(
      screen.getByTestId("module-home-market-dense-observation-action"),
    ).toHaveTextContent(
      "操作边界：不得将当前保留数据用于今日判断或建议动作。",
    );
    expect(
      screen.getByTestId("module-home-market-dense-observation-action"),
    ).not.toHaveTextContent(
      "Reduce intraday duration adds until funding normalizes.",
    );
  });

  it("explains how to read the E/F evidence and the D liquidity comparison", () => {
    const client = createApiClient({ mode: "mock" });
    const macro = {
      ...macroResult(),
      indicators: [
        macroIndicator({
          key: "pmi",
          label: "PMI（制造业）",
          latest_value: 49.3,
          previous_value: 49.4,
          change: -0.1,
          unit: "index",
        }),
      ],
    };
    const news = newsEnvelope();
    news.result.total_rows = 11108;
    news.result.excluded_future_rows = 2;
    news.result.events = [
      denseNewsEvent("event-a", "2026-08-03T08:15:00", "major news"),
      denseNewsEvent("event-b", "2026-08-03T10:15:00", "vendor.topic_1"),
    ];
    const queries = {
      macroToolkitAnalysis: macroQuery({
        data: { result: macro, result_meta: resultMeta() },
      }),
      newsEvents: {
        data: news,
        isLoading: false,
        isFetching: false,
        isError: false,
        error: null,
      },
    } as unknown as ModuleHomeSourceQueries;

    renderWithProviders(
      <MarketOverviewDenseFirstScreen
        view={baseView()}
        queries={queries}
        latestTradeDate="2026-08-03"
        searchValue=""
      />,
      client,
    );

    expect(screen.getByText("前值 → 最新值")).toBeInTheDocument();
    expect(screen.getByText("49.4 index")).toBeInTheDocument();
    expect(screen.getByText("49.3 index")).toBeInTheDocument();
    expect(screen.getByText("-0.1 index")).toBeInTheDocument();
    expect(
      screen.queryByLabelText("PMI（制造业）前值与最新值比较"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByText(
        "DR007 看市场资金利率；7D逆回购看政策操作利率；SHIBOR 看期限报价。",
      ),
    ).toBeInTheDocument();
    expect(
      screen.getByText("最新有效样本 2 / 当前查询总记录 11,108"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("等待同一报告日的有效收益率报价；不补点、不插值。"),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText("颜色图例：无、较少、较多"),
    ).toBeInTheDocument();
    expect(
      screen.getByLabelText(
        "主要新闻（原码 major news）· received_at 08:00–09:59 · 1 条",
      ),
    ).toBeInTheDocument();
    expect(screen.getAllByText("主要新闻")).not.toHaveLength(0);
    expect(screen.getAllByText("vendor.topic_1")).not.toHaveLength(0);
    expect(
      screen.getByText(
        "有效样本区间 2026-08-03–2026-08-03 · 按 received_at 两小时分桶 · 颜色仅代表样本内相对接收密度，不代表重要性、情绪或影响 · 已排除未来记录 2 条",
      ),
    ).toBeInTheDocument();
  });

  it("states when news rows have no valid received_at bucket", () => {
    const client = createApiClient({ mode: "mock" });
    const news = newsEnvelope();
    news.result.events = [
      denseNewsEvent("event-without-time", "日期未返回", "vendor.topic_1"),
    ];
    const queries = {
      macroToolkitAnalysis: macroQuery(),
      newsEvents: {
        data: news,
        isLoading: false,
        isFetching: false,
        isError: false,
        error: null,
      },
    } as unknown as ModuleHomeSourceQueries;

    renderWithProviders(
      <MarketOverviewDenseFirstScreen
        view={baseView()}
        queries={queries}
        latestTradeDate="2026-08-03"
        searchValue=""
      />,
      client,
    );

    expect(screen.getByText("无可分桶事件")).toBeInTheDocument();
  });

  it("renders a dash as the tape report date when a series is missing", () => {
    const client = createApiClient({ mode: "mock" });
    const queries = {
      macroToolkitAnalysis: macroQuery(),
      newsEvents: {
        data: newsEnvelope(),
        isLoading: false,
        isFetching: false,
        isError: false,
        error: null,
      },
    } as unknown as ModuleHomeSourceQueries;

    renderWithProviders(
      <MarketOverviewDenseFirstScreen
        view={baseView()}
        queries={queries}
        latestTradeDate="2026-08-03"
        searchValue=""
      />,
      client,
    );

    const tape = screen.getByLabelText("市场行情带");
    const reportDates = [...tape.querySelectorAll("time")].map(
      (node) => node.textContent,
    );

    expect(reportDates).toHaveLength(8);
    expect(reportDates.every((text) => text === "—")).toBe(true);
    expect(
      screen.queryByText("10Y国债：后端未返回匹配序列"),
    ).not.toBeInTheDocument();
    expect(
      screen.getByTitle("10Y国债：后端未返回匹配序列"),
    ).toBeInTheDocument();
  });
});

describe("useMarketHomeQueries", () => {
  it("requests the shared latest-500 compact news sample without payload_json", async () => {
    const base = createApiClient({ mode: "mock" });
    const getChoiceNewsEvents = vi.fn(async () => newsEnvelope());
    const client: ApiClient = {
      ...base,
      getChoiceMacroLatest: vi.fn(async () => emptyChoiceEnvelope()),
      getMarketDataRates: vi.fn(async () => emptyChoiceEnvelope()),
      getMarketDataCatalog: vi.fn(async () => emptyCatalogEnvelope()),
      getMacroToolkitAnalysis: vi.fn(async () => ({
        result: macroResult(),
        result_meta: resultMeta(),
      })),
      getMacroToolkitStrategySummaries: vi.fn(async () => emptyStrategyEnvelope()),
      getChoiceNewsEvents,
    };

    function HookProbe() {
      useMarketHomeQueries();
      return null;
    }

    renderWithProviders(<HookProbe />, client);

    await waitFor(() => {
      expect(getChoiceNewsEvents).toHaveBeenCalledWith({
        limit: 500,
        offset: 0,
        includePayloadJson: false,
      });
    });
  });
});
