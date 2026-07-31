import {
  createRef,
  useState,
  type ComponentProps,
  type ReactNode,
} from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="market-data-echarts-stub" />,
}));

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import type {
  ApiEnvelope,
  ChoiceMacroLatestPayload,
  ChoiceMacroLatestPoint,
  FxFormalStatusPayload,
  LivermoreStrategyPayload,
  MarketDataCoverageSection,
  MarketDataCoverageSummaryPayload,
  NcdFundingProxyPayload,
  ResearchCalendarEvent,
  ResultMeta,
} from "../api/contracts";
import { MarketDataFigmaDesktopView } from "../features/market-data/pages/MarketDataFigmaDesktopView";
import MarketDataPage from "../features/market-data/pages/MarketDataPage";

type FigmaViewProps = ComponentProps<typeof MarketDataFigmaDesktopView>;

function buildResultMeta(partial: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_market_data_figma_test",
    basis: "formal",
    result_kind: "market_data.test",
    formal_use_allowed: true,
    source_version: "sv_market_data_figma_test",
    vendor_version: "vv_market_data_figma_test",
    rule_version: "rv_market_data_figma_test",
    cache_version: "cv_market_data_figma_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-06-30T09:00:00Z",
    ...partial,
  };
}

function buildEnvelope<T>(
  result: T,
  meta: Partial<ResultMeta> = {},
): ApiEnvelope<T> {
  return {
    result_meta: buildResultMeta(meta),
    result,
  };
}

function buildMacroPoint(
  partial: Partial<ChoiceMacroLatestPoint> & Pick<ChoiceMacroLatestPoint, "series_id">,
): ChoiceMacroLatestPoint {
  return {
    series_name: partial.series_id,
    trade_date: "2026-06-30",
    value_numeric: 1.94,
    unit: "%",
    source_version: "sv_market_data_figma_test",
    vendor_version: "vv_market_data_figma_test",
    refresh_tier: "stable",
    fetch_mode: "date_slice",
    fetch_granularity: "batch",
    quality_flag: "ok",
    latest_change: 0.012,
    recent_points: [
      {
        trade_date: "2026-06-27",
        value_numeric: 1.91,
        source_version: "sv_market_data_figma_test",
        vendor_version: "vv_market_data_figma_test",
        quality_flag: "ok",
      },
      {
        trade_date: "2026-06-30",
        value_numeric: partial.value_numeric ?? 1.94,
        source_version: "sv_market_data_figma_test",
        vendor_version: "vv_market_data_figma_test",
        quality_flag: "ok",
      },
    ],
    ...partial,
  };
}

function buildCoverageSection(
  partial: Partial<MarketDataCoverageSection> & Pick<MarketDataCoverageSection, "key">,
): MarketDataCoverageSection {
  return {
    label: partial.key,
    status: "ready",
    basis: "formal",
    formal_use_allowed: true,
    quality_flag: "ok",
    fallback_mode: "none",
    vendor_status: "ok",
    row_count: 1,
    latest_trade_date: "2026-06-30",
    source_pending: false,
    proxy_only: false,
    message: "Visible Figma business contract test.",
    ...partial,
  };
}

function buildCoverageSummary(
  sections: MarketDataCoverageSection[],
): MarketDataCoverageSummaryPayload {
  return {
    read_target: "duckdb",
    as_of_date: "2026-06-30",
    generated_at: "2026-06-30T09:00:00Z",
    headline: {
      readiness_label: "mixed",
      formal_fragment_ready: true,
      formal_use_allowed: false,
      analytical_warning_count: sections.filter((section) => section.status === "warning").length,
      source_pending_count: sections.filter((section) => section.source_pending).length,
      proxy_only_count: sections.filter((section) => section.proxy_only).length,
    },
    sections,
    actions: [],
  };
}

function buildNcdProxy(
  partial: Partial<NcdFundingProxyPayload> = {},
): NcdFundingProxyPayload {
  return {
    as_of_date: "2026-06-27",
    proxy_label: "Shibor funding proxy",
    is_actual_ncd_matrix: false,
    rows: [
      {
        row_key: "shibor",
        label: "Shibor",
        "1M": 1.234,
        "3M": 1.456,
        "6M": 1.678,
        "9M": 1.789,
        "1Y": 1.901,
        quote_count: 5,
      },
    ],
    warnings: ["Proxy only."],
    ...partial,
  };
}

function buildViewProps(overrides: Partial<FigmaViewProps> = {}): FigmaViewProps {
  return {
    watchDate: "2026-06-30",
    statusDate: "2026-06-30",
    tickerItems: [],
    rateRows: [],
    moneyRows: [],
    moneySeriesLoading: false,
    moneySeriesError: false,
    analyticalSubstituteCount: 0,
    formalSeriesLoading: false,
    formalSeriesError: false,
    latestSeries: [],
    latestSeriesLoading: false,
    latestSeriesError: false,
    fxFormalStatus: null,
    fxFormalLoading: false,
    fxFormalError: false,
    ncdFundingProxy: undefined,
    ncdLoading: false,
    ncdError: false,
    coverageSummary: null,
    coverageSections: [],
    coverageSummaryState: "ready",
    catalogCount: 0,
    catalogLoading: false,
    catalogError: false,
    livermorePayload: undefined,
    livermoreLoading: false,
    livermoreError: false,
    linkagePayload: undefined,
    linkageLoading: false,
    linkageError: false,
    livermoreRef: createRef<HTMLDivElement>(),
    supplyEvents: [],
    supplyLoading: false,
    supplyError: false,
    ...overrides,
  };
}

function renderPage(client: ApiClient) {
  function Wrapper({ children }: { children: ReactNode }) {
    const [queryClient] = useState(
      () =>
        new QueryClient({
          defaultOptions: {
            queries: {
              retry: false,
              staleTime: Number.POSITIVE_INFINITY,
              refetchOnWindowFocus: false,
            },
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
      <MarketDataPage />
    </Wrapper>,
  );
}

async function selectAntOption(testId: string, label: string) {
  const root = screen.getByTestId(testId);
  const selector = root.querySelector(".ant-select-selector");
  expect(selector).not.toBeNull();
  fireEvent.mouseDown(selector!);
  await screen.findByRole("listbox");
  const option =
    document.querySelector(`.ant-select-item-option[title="${label}"]`) ??
    document.querySelector(`.ant-select-item-option[aria-label="${label}"]`) ??
    document.querySelector(`[role="option"][aria-label="${label}"]`);
  expect(option).not.toBeNull();
  fireEvent.click(option!);
}

function stubIntersectionObserver() {
  const callbacks: IntersectionObserverCallback[] = [];
  const observe = vi.fn();
  const disconnect = vi.fn();
  const unobserve = vi.fn();
  const takeRecords = vi.fn(() => []);
  const MockObserver = vi.fn(function MockIntersectionObserver(
    callback: IntersectionObserverCallback,
  ) {
    callbacks.push(callback);
    return {
      root: null,
      rootMargin: "0px",
      thresholds: [0],
      observe,
      disconnect,
      unobserve,
      takeRecords,
    };
  });
  vi.stubGlobal("IntersectionObserver", MockObserver);

  return {
    triggerAll(isIntersecting: boolean) {
      for (const callback of callbacks) {
        callback(
          [{ isIntersecting } as IntersectionObserverEntry],
          {} as IntersectionObserver,
        );
      }
    },
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  window.history.replaceState(null, "", window.location.pathname);
});

describe("MarketDataPage Figma route contract", () => {
  it("renders the complete Figma surface and removes the legacy/API-facing DOM", async () => {
    stubIntersectionObserver();
    const baseClient = createApiClient({ mode: "mock" });
    const getResearchCalendarEvents =
      vi.fn<ApiClient["getResearchCalendarEvents"]>(baseClient.getResearchCalendarEvents);
    const getChoiceNewsEvents =
      vi.fn<ApiClient["getChoiceNewsEvents"]>(baseClient.getChoiceNewsEvents);
    const client: ApiClient = {
      ...baseClient,
      getResearchCalendarEvents,
      getChoiceNewsEvents,
    };

    renderPage(client);

    expect(await screen.findByTestId("market-data-filter-strip")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-date-picker")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-curve-filter")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-source-filter")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-credit-filter")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-refresh-btn")).toBeInTheDocument();
    const pageTitle = screen.getByTestId("market-data-page-title");
    expect(pageTitle.tagName).toBe("H1");
    expect(pageTitle).toHaveTextContent("市场数据");
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    expect(screen.getByTestId("market-data-active-filter-summary")).toHaveTextContent("观察/请求日期");
    expect(screen.getByTestId("market-data-active-filter-summary")).toHaveTextContent("数据日期");

    expect(await screen.findByTestId("market-data-figma-desktop")).toBeInTheDocument();
    await waitFor(() => {
      expect(within(screen.getByTestId("market-data-figma-curve-panel")).getByRole("img")).toBeInTheDocument();
      expect(within(screen.getByTestId("market-data-figma-macro-panel")).getByText(/个序列的最新值与动量/)).toBeInTheDocument();
    });

    expect(screen.getByTestId("market-data-figma-funding-panel")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-figma-fx-panel")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-figma-strategy-panel")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-figma-supply-panel")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-figma-coverage-matrix")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-figma-freshness-panel")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-figma-volume-panel")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-figma-news-panel")).toBeInTheDocument();
    expect(await screen.findByText(/Policy follow-up.*PBOC open-market operation commentary stream/)).toBeInTheDocument();
    expect(screen.queryByText("????????")).not.toBeInTheDocument();
    expect(screen.getByText("资讯源回调异常，事件内容暂不可用")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/vendor callback timeout|S888010007API|__callback__/i);

    expect(screen.queryByTestId("market-data-deep-workspaces")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-refresh-button")).not.toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/E1000180|trace_id|\/ui\/market-data/i);

    await waitFor(() => {
      expect(getResearchCalendarEvents).toHaveBeenCalledWith({ reportDate: "2026-04-10" });
      expect(getChoiceNewsEvents).toHaveBeenCalledWith({
        limit: 12,
        offset: 0,
        includePayloadJson: false,
      });
    });
  });

  it("routes latest-series failures into funding without marking the formal curve failed", async () => {
    stubIntersectionObserver();
    const baseClient = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...baseClient,
      getMarketDataRates: vi.fn(async () =>
        buildEnvelope<ChoiceMacroLatestPayload>(
          { read_target: "duckdb", series: [] },
          { result_kind: "market_data.rates" },
        ),
      ),
      getChoiceMacroLatest: vi.fn(() => Promise.reject(new Error("latest unavailable"))),
      getNcdFundingProxy: vi.fn(async () =>
        buildEnvelope(
          { ...buildNcdProxy(), rows: [] },
          {
            basis: "analytical",
            formal_use_allowed: false,
            result_kind: "market_data.ncd_proxy",
          },
        ),
      ),
    };

    renderPage(client);

    const funding = await screen.findByTestId("market-data-figma-funding-panel");
    await waitFor(() =>
      expect(
        funding.querySelector(".market-data-figma-empty"),
      ).toHaveTextContent(/\u8bfb\u53d6\u5931\u8d25/),
    );
    const curve = screen.getByTestId("market-data-figma-curve-panel");
    expect(
      curve.querySelector(".market-data-figma-empty"),
    ).not.toHaveTextContent(/\u8bfb\u53d6\u5931\u8d25/);
  });

  it("updates the command strip filters, watch date, and refresh button state", async () => {
    stubIntersectionObserver();
    let resolveRefreshStart: ((value: { status: string; run_id: string }) => void) | undefined;
    const refreshStart = new Promise<{ status: string; run_id: string }>((resolve) => {
      resolveRefreshStart = resolve;
    });
    const baseClient = createApiClient({ mode: "mock" });
    const getResearchCalendarEvents =
      vi.fn<ApiClient["getResearchCalendarEvents"]>(baseClient.getResearchCalendarEvents);
    const refreshChoiceMacro = vi.fn(async () => refreshStart);
    const client: ApiClient = {
      ...baseClient,
      getResearchCalendarEvents,
      refreshChoiceMacro,
    };

    renderPage(client);

    const summary = await screen.findByTestId("market-data-active-filter-summary");
    const datePicker = screen.getByTestId("market-data-date-picker");
    const refreshButton = screen.getByTestId("market-data-refresh-btn");

    fireEvent.change(datePicker, { target: { value: "2026-06-28" } });
    await waitFor(() => {
      expect(datePicker).toHaveValue("2026-06-28");
      expect(summary).toHaveTextContent("观察/请求日期 2026-06-28");
      expect(getResearchCalendarEvents).toHaveBeenLastCalledWith({ reportDate: "2026-06-28" });
    });

    await selectAntOption("market-data-curve-filter", "国债");
    await selectAntOption("market-data-source-filter", "Choice");
    await selectAntOption("market-data-credit-filter", "中票");
    await waitFor(() => {
      expect(summary).toHaveTextContent("曲线 国债");
      expect(summary).toHaveTextContent("来源 Choice");
      expect(summary).toHaveTextContent("信用 中票");
      expect(screen.getByTestId("market-data-detail-credit-spread-filtered")).toHaveAttribute(
        "data-filter",
        "mtn",
      );
    });

    fireEvent.click(refreshButton);
    await waitFor(() => {
      expect(refreshChoiceMacro).toHaveBeenCalledWith(30);
      expect(refreshButton).toBeDisabled();
      expect(refreshButton).toHaveTextContent("刷新中…");
    });

    await act(async () => {
      resolveRefreshStart?.({ status: "completed", run_id: "run-market-data-refresh" });
      await refreshStart;
    });

    await waitFor(() => {
      expect(refreshButton).toBeEnabled();
      expect(refreshButton).toHaveTextContent("刷新数据");
    });
  });

  it("keeps a blocked formal bundle visible as analysis/candidate data", async () => {
    stubIntersectionObserver();
    const baseClient = createApiClient({ mode: "mock" });
    const client: ApiClient = {
      ...baseClient,
      getMarketDataRates: vi.fn(async () =>
        buildEnvelope<ChoiceMacroLatestPayload>(
          {
            read_target: "duckdb",
            series: [
              buildMacroPoint({
                series_id: "blocked-formal-10y",
                series_name: "10年国债收益率",
                refresh_tier: "stable",
              }),
            ],
          },
          {
            basis: "formal",
            formal_use_allowed: false,
            result_kind: "market_data.rates",
          },
        )),
    };

    renderPage(client);

    const summary = await screen.findByTestId("market-data-active-filter-summary");
    expect(summary).toHaveTextContent("formal · blocked");
    expect(summary).toHaveTextContent("禁止作为正式口径");
    expect(screen.getByTestId("market-workbench-topbar")).toHaveTextContent("状态 分析/候选");

    const detailCard = await screen.findByTestId("market-data-detail-formal-rates-card");
    expect(detailCard).toHaveTextContent("formal · blocked");
    expect(detailCard).toHaveTextContent("禁止作为正式口径");
    expect(detailCard).toHaveTextContent("10年国债收益率");
  });

  it("surfaces a missing coverage summary without synthesizing governed section states", async () => {
    stubIntersectionObserver();
    const baseClient = createApiClient({ mode: "mock" });
    const getMarketDataCoverageSummary = vi.fn<ApiClient["getMarketDataCoverageSummary"]>(
      async () => {
        throw new Error("coverage unavailable");
      },
    );
    const client: ApiClient = {
      ...baseClient,
      getMarketDataCoverageSummary,
    };

    renderPage(client);

    await waitFor(() => {
      expect(screen.getByTestId("market-data-figma-coverage-summary-state")).toHaveTextContent(
        "覆盖摘要不可用；不生成替代口径",
      );
    });
    expect(screen.queryByTestId("market-data-figma-coverage-formal_rates")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-figma-coverage-fx_analytical")).not.toBeInTheDocument();
  });

  it("maps governed rate, macro, FX, proxy, coverage, and supply responses into visible finance panels", async () => {
    stubIntersectionObserver();
    const baseClient = createApiClient({ mode: "mock" });
    const rateSeries = [
      buildMacroPoint({
        series_id: "M003",
        series_name: "1年期国债到期收益率",
        value_numeric: 1.55,
        latest_change: 0.01,
      }),
      buildMacroPoint({
        series_id: "EMM00588704",
        series_name: "中债国债到期收益率:2年",
        value_numeric: 1.6,
        latest_change: 0.02,
      }),
      buildMacroPoint({
        series_id: "EMM00166466",
        series_name: "中债国债到期收益率:10年",
        value_numeric: 1.934,
        latest_change: 0.035,
      }),
    ];
    const latestSeries = [
      ...rateSeries,
      buildMacroPoint({
        series_id: "M002",
        series_name: "DR007",
        value_numeric: 1.888,
        latest_change: -0.014,
        refresh_tier: "fallback",
        fetch_mode: "latest",
        fetch_granularity: "single",
      }),
      buildMacroPoint({
        series_id: "EMM00058124",
        series_name: "美元兑人民币中间价",
        value_numeric: 6.7939,
        unit: "CNY/USD",
        latest_change: 0.0033,
      }),
      buildMacroPoint({
        series_id: "CA.CSI300",
        series_name: "沪深300",
        value_numeric: 4012.6,
        unit: "index",
        latest_change: -12.4,
      }),
      buildMacroPoint({
        series_id: "CA.CSI300_PCT_CHG",
        series_name: "沪深300涨跌幅",
        value_numeric: -0.55,
        unit: "%",
        latest_change: null,
      }),
    ];
    const coverageSections = [
      buildCoverageSection({ key: "formal_rates", latest_trade_date: "2026-06-30" }),
      buildCoverageSection({
        key: "macro_latest",
        status: "warning",
        basis: "analytical",
        formal_use_allowed: false,
        quality_flag: "warning",
        fallback_mode: "latest_snapshot",
      }),
      buildCoverageSection({
        key: "fx_formal",
        status: "stale",
        quality_flag: "stale",
        latest_trade_date: "2026-06-27",
      }),
      buildCoverageSection({
        key: "ncd_proxy",
        status: "proxy_only",
        basis: "analytical",
        formal_use_allowed: false,
        quality_flag: "warning",
        proxy_only: true,
        as_of_date: "2026-06-27",
        latest_trade_date: null,
      }),
      buildCoverageSection({
        key: "bond_futures",
        status: "source_pending",
        basis: "analytical",
        formal_use_allowed: false,
        quality_flag: "missing",
        vendor_status: "vendor_unavailable",
        row_count: 0,
        latest_trade_date: null,
        source_pending: true,
      }),
    ];
    const fxPayload: FxFormalStatusPayload = {
      read_target: "duckdb",
      vendor_priority: ["choice"],
      candidate_count: 2,
      materialized_count: 1,
      latest_trade_date: "2026-06-27",
      carry_forward_count: 0,
      rows: [
        {
          base_currency: "USD",
          quote_currency: "CNY",
          pair_label: "USD/CNY",
          series_id: "FX.USD.CNY",
          series_name: "美元兑人民币中间价",
          vendor_series_code: "USD.CNY",
          trade_date: "2026-06-27",
          observed_trade_date: "2026-06-27",
          mid_rate: 7.1234,
          source_name: "choice",
          vendor_name: "choice",
          vendor_version: "vv_fx_test",
          source_version: "sv_fx_test",
          is_business_day: true,
          is_carry_forward: false,
          status: "ok",
        },
        {
          base_currency: "EUR",
          quote_currency: "CNY",
          pair_label: "EUR/CNY",
          series_id: "FX.EUR.CNY",
          series_name: "欧元兑人民币中间价",
          vendor_series_code: "EUR.CNY",
          trade_date: null,
          observed_trade_date: null,
          mid_rate: null,
          source_name: null,
          vendor_name: null,
          vendor_version: null,
          source_version: null,
          is_business_day: null,
          is_carry_forward: null,
          status: "missing",
        },
      ],
    };
    const supplyEvents: ResearchCalendarEvent[] = [
      {
        id: "supply-1",
        date: "2026-06-26",
        title: "国债发行",
        kind: "supply",
        severity: "high",
      },
      {
        id: "supply-2",
        date: "2026-06-27",
        title: "地方债发行",
        kind: "auction",
        severity: "medium",
      },
    ];
    const getResearchCalendarEvents =
      vi.fn<ApiClient["getResearchCalendarEvents"]>(async () => supplyEvents);
    const client: ApiClient = {
      ...baseClient,
      getMarketDataRates: vi.fn(async () =>
        buildEnvelope<ChoiceMacroLatestPayload>(
          { read_target: "duckdb", series: rateSeries },
          {
            result_kind: "market_data.rates",
            resolved_report_date: "2026-06-30",
            as_of_date: "2026-06-30",
          },
        )),
      getChoiceMacroLatest: vi.fn(async () =>
        buildEnvelope<ChoiceMacroLatestPayload>(
          { read_target: "duckdb", series: latestSeries },
          {
            basis: "analytical",
            formal_use_allowed: false,
            result_kind: "macro.choice.latest",
          },
        )),
      getFxFormalStatus: vi.fn(async () =>
        buildEnvelope(fxPayload, {
          result_kind: "market_data.fx_formal",
        })),
      getNcdFundingProxy: vi.fn(async () =>
        buildEnvelope(buildNcdProxy(), {
          basis: "analytical",
          formal_use_allowed: false,
          quality_flag: "warning",
          result_kind: "market_data.ncd_proxy",
        })),
      getMarketDataCoverageSummary: vi.fn(async () =>
        buildEnvelope(buildCoverageSummary(coverageSections), {
          basis: "analytical",
          formal_use_allowed: false,
          quality_flag: "warning",
          result_kind: "market_data.coverage_summary",
        })),
      getResearchCalendarEvents,
    };

    renderPage(client);

    const ticker = await screen.findByTestId("market-data-figma-ticker");
    await waitFor(() => {
      expect(within(ticker).getByText("1.93%")).toBeInTheDocument();
      expect(within(ticker).getByText("+3.5bp")).toBeInTheDocument();
      expect(within(ticker).getByText("6.7939 CNY/USD")).toBeInTheDocument();
      expect(within(ticker).getByText("+0.0033 CNY/USD")).toBeInTheDocument();
    });
    expect(ticker).not.toHaveTextContent("6.7939CNY/USD");

    const funding = screen.getByTestId("market-data-figma-funding-panel");
    expect(within(funding).getByText("DR007")).toBeInTheDocument();
    expect(within(funding).getByText("1.89%")).toBeInTheDocument();
    expect(within(funding).getByText("SHIBOR 1M")).toBeInTheDocument();
    expect(within(funding).getByText("SHIBOR 1Y")).toBeInTheDocument();
    expect(within(funding).getByText("NCD 仅作资金代理，不等于正式期限×评级矩阵")).toBeInTheDocument();

    const fxPanel = screen.getByTestId("market-data-figma-fx-panel");
    expect(within(fxPanel).getByText("7.1234")).toBeInTheDocument();
    expect(within(fxPanel).getByText("缺失")).toBeInTheDocument();

    const supplyPanel = screen.getByTestId("market-data-figma-supply-panel");
    await waitFor(() => {
      expect(within(supplyPanel).getByText("△ 2 条 · 最新 2026-06-27")).toBeInTheDocument();
      expect(getResearchCalendarEvents).toHaveBeenCalledWith({ reportDate: "2026-06-30" });
    });

    expect(screen.getByTestId("market-data-figma-coverage-formal_rates")).toHaveAttribute(
      "data-tone",
      "ready",
    );
    expect(screen.getByTestId("market-data-figma-coverage-macro_latest")).toHaveAttribute(
      "data-tone",
      "watch",
    );
    expect(screen.getByTestId("market-data-figma-coverage-ncd_proxy")).toHaveAttribute(
      "data-tone",
      "proxy",
    );
    expect(screen.getByTestId("market-data-figma-coverage-bond_futures")).toHaveAttribute(
      "data-tone",
      "pending",
    );
    expect(within(screen.getByTestId("market-data-figma-volume-panel")).getByText(/截至 2026-06-30/)).toBeInTheDocument();
  });

  it("defers strategy data until intersection, then exposes loading and backend failure without demo fallback", async () => {
    const observer = stubIntersectionObserver();
    const baseClient = createApiClient({ mode: "mock" });
    let rejectStrategy!: (reason?: unknown) => void;
    const strategyPromise =
      new Promise<Awaited<ReturnType<ApiClient["getLivermoreStrategy"]>>>((_resolve, reject) => {
        rejectStrategy = reject;
      });
    const getLivermoreStrategy =
      vi.fn<ApiClient["getLivermoreStrategy"]>(() => strategyPromise);
    const client: ApiClient = {
      ...baseClient,
      getLivermoreStrategy,
    };

    renderPage(client);

    const strategyPanel = await screen.findByTestId("market-data-figma-strategy-panel");
    expect(getLivermoreStrategy).not.toHaveBeenCalled();

    act(() => {
      observer.triggerAll(true);
    });

    await waitFor(() => {
      expect(getLivermoreStrategy).toHaveBeenCalledWith({ asOfDate: "2026-04-10" });
      expect(within(strategyPanel).getByRole("generic", { busy: true })).toBeInTheDocument();
    });
    expect(within(strategyPanel).getAllByText("…")).toHaveLength(6);

    act(() => {
      rejectStrategy(new Error("strategy unavailable"));
    });

    expect(
      await within(strategyPanel).findByText("策略观察加载失败，未使用演示数据替代。"),
    ).toBeInTheDocument();
  });

  it("defers the heavy detail queries until the detail deck approaches the viewport", async () => {
    const observer = stubIntersectionObserver();
    const baseClient = createApiClient({ mode: "mock" });
    const getTushareSupplement =
      vi.fn<ApiClient["getTushareSupplement"]>(baseClient.getTushareSupplement);
    const getMacroBondLinkageAnalysis =
      vi.fn<ApiClient["getMacroBondLinkageAnalysis"]>(baseClient.getMacroBondLinkageAnalysis);
    const client: ApiClient = {
      ...baseClient,
      getTushareSupplement,
      getMacroBondLinkageAnalysis,
    };

    renderPage(client);

    expect(await screen.findByTestId("market-data-detail-deck")).toBeInTheDocument();
    expect(getTushareSupplement).not.toHaveBeenCalled();
    expect(getMacroBondLinkageAnalysis).not.toHaveBeenCalled();

    act(() => {
      observer.triggerAll(true);
    });

    await waitFor(() => {
      expect(getTushareSupplement).toHaveBeenCalledWith({
        moneySupplyLimit: 120,
        ecoCalLimit: 300,
      });
      expect(getMacroBondLinkageAnalysis).toHaveBeenCalled();
    });
  });
});

describe("MarketDataFigmaDesktopView visible business states", () => {
  it("does not fabricate governed coverage rows when the summary is unavailable", () => {
    render(
      <MarketDataFigmaDesktopView
        {...buildViewProps({
          coverageSummary: null,
          coverageSections: [],
          coverageSummaryState: "error",
        })}
      />,
    );

    expect(screen.getByTestId("market-data-figma-coverage-summary-state")).toHaveTextContent(
      "覆盖摘要不可用；不生成替代口径",
    );
    expect(screen.queryByTestId("market-data-figma-coverage-formal_rates")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-figma-coverage-fx_analytical")).not.toBeInTheDocument();
  });

  it("maps ready, warning, stale, proxy, pending, deferred, and error coverage states", () => {
    const sections = [
      buildCoverageSection({ key: "formal_rates" }),
      buildCoverageSection({
        key: "macro_latest",
        status: "warning",
        basis: "analytical",
        formal_use_allowed: false,
        quality_flag: "warning",
      }),
      buildCoverageSection({
        key: "fx_formal",
        status: "stale",
        quality_flag: "stale",
      }),
      buildCoverageSection({
        key: "ncd_proxy",
        status: "proxy_only",
        basis: "analytical",
        formal_use_allowed: false,
        quality_flag: "warning",
        proxy_only: true,
      }),
      buildCoverageSection({
        key: "bond_futures",
        status: "source_pending",
        basis: "analytical",
        formal_use_allowed: false,
        quality_flag: "missing",
        vendor_status: "vendor_unavailable",
        source_pending: true,
        latest_trade_date: null,
      }),
      buildCoverageSection({
        key: "cash_bond_trades",
        status: "deferred",
        basis: "analytical",
        formal_use_allowed: false,
        quality_flag: "warning",
        latest_trade_date: null,
      }),
      buildCoverageSection({
        key: "credit_trades",
        status: "error",
        basis: "analytical",
        formal_use_allowed: false,
        quality_flag: "error",
        vendor_status: "vendor_unavailable",
        latest_trade_date: null,
      }),
      buildCoverageSection({
        key: "stale_rows",
        status: "ready",
        quality_flag: "stale",
        vendor_status: "vendor_stale",
        fallback_mode: "latest_snapshot",
      }),
      buildCoverageSection({
        key: "failed_rows",
        status: "ready",
        quality_flag: "error",
        vendor_status: "vendor_unavailable",
      }),
    ];

    render(
      <MarketDataFigmaDesktopView
        {...buildViewProps({
          coverageSections: sections,
          coverageSummary: buildCoverageSummary(sections),
        })}
      />,
    );

    const expected = [
      ["formal_rates", "ready", "就绪"],
      ["macro_latest", "watch", "观察"],
      ["fx_formal", "watch", "观察"],
      ["ncd_proxy", "proxy", "代理"],
      ["bond_futures", "pending", "待接入"],
      ["cash_bond_trades", "deferred", "按需"],
      ["credit_trades", "error", "异常"],
      ["stale_rows", "watch", "观察"],
      ["failed_rows", "error", "异常"],
    ] as const;
    for (const [key, tone, label] of expected) {
      const item = screen.getByTestId(`market-data-figma-coverage-${key}`);
      expect(item).toHaveAttribute("data-tone", tone);
      expect(within(item).getByText(label)).toBeInTheDocument();
    }
    expect(screen.getByTestId("market-data-figma-coverage-formal_rates")).toHaveAttribute(
      "title",
      "数据日期 2026-06-30",
    );
    expect(screen.getByTestId("market-data-figma-operational-summary")).toHaveTextContent(
      "截至 2026-06-30 · 就绪 1 · 观察/代理 5 · 待接入 1 · 按需 3 · 异常 2",
    );
  });

  it("keeps degraded strategy and linkage errors out of ready/pending counts", () => {
    const degradedStrategy: LivermoreStrategyPayload = {
      as_of_date: "2026-06-28",
      requested_as_of_date: "2026-06-30",
      strategy_name: "Livermore test",
      basis: "analytical",
      market_gate: {
        state: "WARM",
        exposure: 0.25,
        passed_conditions: 1,
        available_conditions: 4,
        required_conditions: 4,
        conditions: [],
      },
      rule_readiness: [],
      diagnostics: [],
      data_gaps: [],
      supported_outputs: ["market_gate"],
      unsupported_outputs: [],
      module_states: [
        {
          key: "market_gate",
          state: "degraded",
          render_mode: "evidence_only",
          source_date: "2026-06-28",
          lag_days: 2,
          threshold_days: 1,
          reasons: ["stale input"],
          evidence_scope: "detail",
          excludes_from_primary: true,
        },
      ],
    };

    render(
      <MarketDataFigmaDesktopView
        {...buildViewProps({
          statusDate: null,
          watchDate: "2026-07-31",
          livermorePayload: degradedStrategy,
          linkageError: true,
        })}
      />,
    );

    expect(screen.getByTestId("market-data-figma-coverage-strategy_observation")).toHaveAttribute(
      "data-tone",
      "watch",
    );
    expect(screen.getByTestId("market-data-figma-coverage-macro_bond_linkage")).toHaveAttribute(
      "data-tone",
      "error",
    );
    expect(screen.getByTestId("market-data-figma-operational-summary")).toHaveTextContent(
      "截至 2026-06-28 · 就绪 0 · 观察/代理 2 · 待接入 0 · 按需 0 · 异常 1",
    );
  });

  it("does not present the selected watch date as a backend as-of date", () => {
    render(
      <MarketDataFigmaDesktopView
        {...buildViewProps({
          statusDate: null,
          watchDate: "2026-07-31",
        })}
      />,
    );

    expect(screen.getByTestId("market-data-figma-operational-summary")).toHaveTextContent(
      "截至 待返回",
    );
    expect(screen.getByTestId("market-data-figma-operational-summary")).not.toHaveTextContent(
      "2026-07-31",
    );
  });

  it("shows every returned Shibor tenor as an explicitly labeled NCD proxy", () => {
    render(
      <MarketDataFigmaDesktopView
        {...buildViewProps({
          ncdFundingProxy: buildNcdProxy(),
        })}
      />,
    );

    const funding = screen.getByTestId("market-data-figma-funding-panel");
    for (const [tenor, value] of [
      ["1M", "1.234%"],
      ["3M", "1.456%"],
      ["6M", "1.678%"],
      ["9M", "1.789%"],
      ["1Y", "1.901%"],
    ]) {
      expect(within(funding).getByText(`SHIBOR ${tenor}`)).toBeInTheDocument();
      expect(within(funding).getByText(value)).toBeInTheDocument();
    }
    expect(screen.getByTestId("market-data-figma-ncd-proxy-note")).toHaveTextContent(
      "NCD 仅作资金代理，不等于正式期限×评级矩阵",
    );
    expect(funding.querySelectorAll('[data-basis="proxy"]')).toHaveLength(5);
  });

  it("renders explicit empty states instead of inventing rates, macro, funding, or FX data", () => {
    render(<MarketDataFigmaDesktopView {...buildViewProps()} />);

    expect(
      within(screen.getByTestId("market-data-figma-curve-panel")).getByText(
        "当前筛选下暂无可绘制的曲线点位。",
      ),
    ).toBeInTheDocument();
    expect(
      within(screen.getByTestId("market-data-figma-funding-panel")).getByText(
        "资金面数据尚未返回。",
      ),
    ).toBeInTheDocument();
    expect(
      within(screen.getByTestId("market-data-figma-macro-panel")).getByText(
        "宏观与跨资产序列暂未返回。",
      ),
    ).toBeInTheDocument();
    expect(
      within(screen.getByTestId("market-data-figma-fx-panel")).getByText(
        "外汇数据暂未返回。",
      ),
    ).toBeInTheDocument();
    expect(screen.queryByText(/演示行情|示例行情|mock value/i)).not.toBeInTheDocument();
  });

  it("distinguishes direct-query failures from genuine empty market data", () => {
    render(
      <MarketDataFigmaDesktopView
        {...buildViewProps({
          formalSeriesError: true,
          moneySeriesError: true,
          latestSeriesError: true,
          fxFormalError: true,
          ncdError: true,
          catalogError: true,
        })}
      />,
    );

    expect(screen.getByTestId("market-data-figma-curve-panel")).toHaveTextContent(
      "正式市场序列读取失败",
    );
    expect(screen.getByTestId("market-data-figma-funding-panel")).toHaveTextContent(
      "资金面或存单代理读取失败",
    );
    expect(screen.getByTestId("market-data-figma-macro-panel")).toHaveTextContent(
      "市场与宏观观察读取失败",
    );
    expect(screen.getByTestId("market-data-figma-fx-panel")).toHaveTextContent(
      "正式外汇状态读取失败",
    );
    const catalogState = screen.getByTestId("market-data-figma-coverage-macro_catalog");
    expect(catalogState).toHaveAttribute("data-tone", "error");
    expect(within(catalogState).getByText("异常")).toBeInTheDocument();
  });

  it("exposes supply and strategy loading/error states in the visible Figma panels", () => {
    const loadingProps = buildViewProps({
      livermoreLoading: true,
      supplyLoading: true,
    });
    const { rerender } = render(<MarketDataFigmaDesktopView {...loadingProps} />);

    const strategyPanel = screen.getByTestId("market-data-figma-strategy-panel");
    const supplyPanel = screen.getByTestId("market-data-figma-supply-panel");
    expect(within(strategyPanel).getByRole("generic", { busy: true })).toBeInTheDocument();
    expect(within(strategyPanel).getAllByText("…")).toHaveLength(6);
    expect(within(supplyPanel).getByText("供给记录加载中")).toBeInTheDocument();

    rerender(
      <MarketDataFigmaDesktopView
        {...buildViewProps({
          livermoreError: true,
          supplyError: true,
        })}
      />,
    );

    expect(
      within(strategyPanel).getByText("策略观察加载失败，未使用演示数据替代。"),
    ).toBeInTheDocument();
    expect(within(supplyPanel).getByText("供给记录异常")).toBeInTheDocument();
    expect(within(supplyPanel).getByText("⚠ 暂未取得供给日历")).toBeInTheDocument();
  });
});
