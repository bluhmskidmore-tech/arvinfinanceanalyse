import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

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

afterEach(() => {
  vi.unstubAllGlobals();
});

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
  it("tracks the section closest to the measured navigation anchor from live section geometry", () => {
    let observerCallback:
      | IntersectionObserverCallback
      | undefined;
    const observe = vi.fn();
    const disconnect = vi.fn();

    vi.stubGlobal(
      "IntersectionObserver",
      class {
        constructor(callback: IntersectionObserverCallback) {
          observerCallback = callback;
        }

        observe = observe;
        disconnect = disconnect;
      },
    );

    renderWorkbench(
      createApiClient({ mode: "mock" }),
      {} as ModuleHomeSourceQueries,
    );

    const nav = screen.getByRole("navigation", {
      name: "金融图表分组导航",
    });
    const sectionButtons = within(nav).getAllByRole("button");
    const ratesSection = document.getElementById(
      "market-financial-section-rates",
    )!;
    const strategySection = document.getElementById(
      "market-financial-section-strategy",
    )!;

    Object.defineProperty(nav, "getBoundingClientRect", {
      configurable: true,
      value: () =>
        ({
          top: 180,
          bottom: 240,
          left: 0,
          right: 0,
          width: 0,
          height: 60,
          x: 0,
          y: 180,
          toJSON: () => ({}),
        }) satisfies DOMRect,
    });

    expect(observerCallback).toBeDefined();

    Object.defineProperty(ratesSection, "getBoundingClientRect", {
      configurable: true,
      value: () =>
        ({
          top: 120,
          bottom: 180,
          left: 0,
          right: 0,
          width: 0,
          height: 60,
          x: 0,
          y: 120,
          toJSON: () => ({}),
        }) satisfies DOMRect,
    });
    Object.defineProperty(strategySection, "getBoundingClientRect", {
      configurable: true,
      value: () =>
        ({
          top: 252,
          bottom: 320,
          left: 0,
          right: 0,
          width: 0,
          height: 68,
          x: 0,
          y: 252,
          toJSON: () => ({}),
        }) satisfies DOMRect,
    });

    expect(sectionButtons[0]).toHaveAttribute("aria-current", "location");

    act(() => {
      observerCallback?.(
        [
          {
            boundingClientRect: { top: 120 },
            intersectionRatio: 0.55,
            isIntersecting: true,
            target: ratesSection,
          },
        ] as unknown as IntersectionObserverEntry[],
        {} as IntersectionObserver,
      );
    });

    expect(sectionButtons[3]).toHaveAttribute("aria-current", "location");
    expect(sectionButtons[0]).not.toHaveAttribute("aria-current");
  });

  it("keeps the user selected focus section during same-frame observer cleanup races", () => {
    let observerCallback:
      | IntersectionObserverCallback
      | undefined;
    const observe = vi.fn();
    const disconnect = vi.fn();

    vi.stubGlobal(
      "IntersectionObserver",
      class {
        constructor(callback: IntersectionObserverCallback) {
          observerCallback = callback;
        }

        observe = observe;
        disconnect = disconnect;
      },
    );

    renderWorkbench(
      createApiClient({ mode: "mock" }),
      {} as ModuleHomeSourceQueries,
    );

    const focusButton = screen.getByRole("button", { name: "重点" });
    const nav = screen.getByRole("navigation", {
      name: "金融图表分组导航",
    });
    const sectionButtons = within(nav).getAllByRole("button");
    const ratesSection = document.getElementById(
      "market-financial-section-rates",
    )!;

    fireEvent.click(sectionButtons[3]!);
    expect(sectionButtons[3]).toHaveAttribute("aria-current", "location");

    const staleObserverCallback = observerCallback;

    act(() => {
      focusButton.click();
      staleObserverCallback?.(
        [
          {
            boundingClientRect: { top: 120 },
            intersectionRatio: 1,
            isIntersecting: true,
            target: ratesSection,
          },
        ] as unknown as IntersectionObserverEntry[],
        {} as IntersectionObserver,
      );
    });

    expect(focusButton).toHaveAttribute("aria-pressed", "true");
    expect(disconnect).toHaveBeenCalled();
    expect(sectionButtons[3]).toHaveAttribute("aria-pressed", "true");
    expect(sectionButtons[0]).toHaveAttribute("aria-pressed", "false");
    expect(sectionButtons[3]).not.toHaveAttribute("aria-current");
  });

  it("uses overview and focus button semantics without removing any chart groups", () => {
    const client = createApiClient({ mode: "mock" });
    const queries = {} as ModuleHomeSourceQueries;

    renderWorkbench(client, queries);

    const workbench = screen.getByTestId("module-home-market-financial-charts");
    const focusButton = screen.getByRole("button", { name: "重点" });
    const overviewButton = screen.getByRole("button", { name: "全览" });
    const nav = screen.getByRole("navigation", {
      name: "金融图表分组导航",
    });
    const sectionButtons = within(nav).getAllByRole("button");

    expect(workbench).toHaveAttribute("data-view-mode", "overview");
    expect(focusButton).toHaveAttribute("aria-pressed", "false");
    expect(overviewButton).toHaveAttribute("aria-pressed", "true");
    expect(sectionButtons).toHaveLength(6);
    expect(sectionButtons[0]).toHaveAttribute("aria-current", "location");
    expect(sectionButtons[0]).not.toHaveAttribute("aria-pressed");
    expect(sectionButtons[3]).not.toHaveAttribute("aria-current");
    expect(
      workbench.querySelectorAll('[data-testid^="module-home-market-chart-"]'),
    ).toHaveLength(12);

    const ratesSection = document.getElementById(
      "market-financial-section-rates",
    )!;
    const ratesRail = ratesSection.querySelector("aside");

    expect(ratesRail).toHaveTextContent("先看曲线形态，再看关键利率的近期走势");
    expect(ratesRail).toContainElement(
      screen.getByTestId("module-home-market-section-status-rates"),
    );
    expect(
      ratesSection.querySelectorAll(
        '[data-testid^="module-home-market-chart-"]',
      ),
    ).toHaveLength(2);

    const strategySection = document.getElementById(
      "market-financial-section-strategy",
    )!;
    const scrollIntoView = vi.fn();
    Object.defineProperty(strategySection, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });

    fireEvent.click(sectionButtons[3]!);

    expect(sectionButtons[3]).toHaveAttribute("aria-current", "location");
    expect(sectionButtons[3]).not.toHaveAttribute("aria-pressed");
    expect(sectionButtons[0]).not.toHaveAttribute("aria-current");
    expect(scrollIntoView).toHaveBeenCalledWith({
      behavior: "smooth",
      block: "start",
    });

    scrollIntoView.mockClear();

    fireEvent.click(focusButton);

    expect(workbench).toHaveAttribute("data-view-mode", "focus");
    expect(focusButton).toHaveAttribute("aria-pressed", "true");
    expect(overviewButton).toHaveAttribute("aria-pressed", "false");
    expect(sectionButtons[3]).toHaveAttribute("aria-pressed", "true");
    expect(sectionButtons[3]).not.toHaveAttribute("aria-current");
    expect(strategySection).toHaveAttribute("data-active", "true");
    expect(scrollIntoView).not.toHaveBeenCalled();
    expect(
      workbench.querySelectorAll('[data-testid^="module-home-market-chart-"]'),
    ).toHaveLength(12);
  });

  it("expands only the first chart group in overview and lets the rest open on demand", () => {
    const client = createApiClient({ mode: "mock" });
    const queries = {} as ModuleHomeSourceQueries;

    renderWorkbench(client, queries);

    const ratesSection = document.getElementById(
      "market-financial-section-rates",
    )!;
    const strategySection = document.getElementById(
      "market-financial-section-strategy",
    )!;

    expect(ratesSection).toHaveAttribute("data-expanded", "true");
    expect(strategySection).toHaveAttribute("data-expanded", "false");

    const strategyToggle = screen.getByTestId(
      "module-home-market-section-toggle-strategy",
    );

    expect(strategyToggle).toHaveAttribute("aria-expanded", "false");
    expect(strategyToggle).toHaveAttribute(
      "aria-controls",
      "market-financial-section-body-strategy",
    );
    expect(strategyToggle).toHaveTextContent("展开");

    fireEvent.click(strategyToggle);

    expect(strategySection).toHaveAttribute("data-expanded", "true");
    expect(strategyToggle).toHaveAttribute("aria-expanded", "true");
    expect(strategyToggle).toHaveTextContent("收起");

    fireEvent.click(strategyToggle);

    expect(strategySection).toHaveAttribute("data-expanded", "false");

    const nav = screen.getByRole("navigation", {
      name: "金融图表分组导航",
    });
    const sectionButtons = within(nav).getAllByRole("button");
    Object.defineProperty(strategySection, "scrollIntoView", {
      configurable: true,
      value: vi.fn(),
    });

    fireEvent.click(sectionButtons[3]!);

    expect(strategySection).toHaveAttribute("data-expanded", "true");

    fireEvent.click(screen.getByRole("button", { name: "重点" }));

    expect(
      document.getElementById("market-financial-section-coverage"),
    ).toHaveAttribute("data-expanded", "true");
  });

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
    const nav = screen.getByRole("navigation", {
      name: "金融图表分组导航",
    });
    const sectionButtons = within(nav).getAllByRole("button");

    expect(workbench).toBeInTheDocument();
    expect(sectionButtons).toHaveLength(6);
    expect(
      workbench.querySelectorAll('[data-testid^="module-home-market-chart-"]'),
    ).toHaveLength(12);

    fireEvent.click(sectionButtons[4]!);

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

  it("renders one returned tenor as a readable comparison rather than a yield curve", async () => {
    const client = createApiClient({ mode: "mock" });
    const ratesEnvelope = await client.getMarketDataRates();
    const sourceRows = ratesEnvelope.result.series.slice(0, 2);
    const queries = {
      marketRates: {
        data: {
          ...ratesEnvelope,
          result: {
            ...ratesEnvelope.result,
            series: sourceRows.map((series, index) => ({
              ...series,
              series_id:
                index === 0 ? "single-gov-10y" : "single-cdb-10y",
              series_name:
                index === 0
                  ? "中债国债到期收益率:10年"
                  : "中债政策性金融债到期收益率(国开行)10年",
              trade_date: "2026-07-30",
              unit: "%",
              value_numeric: index === 0 ? 1.71 : 1.84,
            })),
          },
        },
        isError: false,
      },
    } as unknown as ModuleHomeSourceQueries;

    renderWorkbench(client, queries);

    const curveCard = screen.getByTestId(
      "module-home-market-chart-yield-curve",
    );
    const comparison = within(curveCard).getByTestId(
      "module-home-market-yield-single-tenor",
    );

    expect(curveCard).toHaveAttribute("data-chart-view", "single-tenor");
    expect(within(curveCard).getByRole("note")).toHaveTextContent(
      "怎么看比较同一期限的国债与国开收益率",
    );
    expect(comparison).toHaveTextContent(
      "当前仅返回一个期限，暂不能判断曲线形态。",
    );
    expect(comparison).toHaveTextContent("国债 10Y");
    expect(comparison).toHaveTextContent("1.710%");
    expect(comparison).toHaveTextContent("国开 10Y");
    expect(comparison).toHaveTextContent("1.840%");
    expect(
      within(curveCard).queryByTestId("market-financial-chart-canvas"),
    ).not.toBeInTheDocument();
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
