import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="market-data-echarts-stub" />,
}));

vi.mock("../app/jobs/polling", () => ({
  runPollingTask: vi.fn(),
}));

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import { runPollingTask } from "../app/jobs/polling";
import type { ResultMeta } from "../api/contracts";
import MarketDataPage from "../features/market-data/pages/MarketDataPage";

function renderPage(client: ApiClient) {
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
      <MarketDataPage />
    </Wrapper>,
  );
}

describe("MarketDataPage", () => {
  afterEach(() => {
    vi.mocked(runPollingTask).mockReset();
  });

  it("renders macro catalog plus trend and lineage evidence from the API client contract", async () => {
    const base = createApiClient({ mode: "mock" });
    const foundationMeta: ResultMeta = {
      trace_id: "tr_macro_foundation_test",
      basis: "analytical",
      result_kind: "preview.macro-foundation",
      formal_use_allowed: false,
      source_version: "sv_macro_vendor_test",
      vendor_version: "vv_choice_catalog_v1",
      rule_version: "rv_phase1_macro_vendor_v1",
      cache_version: "cv_phase1_macro_vendor_v1",
      quality_flag: "ok",
      vendor_status: "ok",
      fallback_mode: "none",
      scenario_flag: false,
      generated_at: "2026-04-10T09:00:00Z",
    };
    const latestMeta: ResultMeta = {
      trace_id: "tr_choice_macro_latest_test",
      basis: "analytical",
      result_kind: "macro.choice.latest",
      formal_use_allowed: false,
      source_version: "sv_choice_macro_latest_test",
      vendor_version: "vv_choice_macro_20260410",
      rule_version: "rv_choice_macro_thin_slice_v1",
      cache_version: "cv_choice_macro_thin_slice_v1",
      quality_flag: "warning",
      vendor_status: "ok",
      fallback_mode: "none",
      scenario_flag: false,
      generated_at: "2026-04-10T09:05:00Z",
    };
    const getMacroFoundation = vi.fn(async () => ({
      result_meta: foundationMeta,
      result: {
        read_target: "duckdb" as const,
        series: [
          {
            series_id: "M001",
            series_name: "Open Market 7D Reverse Repo",
            vendor_name: "choice",
            vendor_version: "vv_choice_catalog_v1",
            frequency: "daily",
            unit: "%",
            refresh_tier: "stable" as const,
            fetch_mode: "date_slice" as const,
            fetch_granularity: "batch" as const,
            policy_note: "main refresh date-slice lane",
          },
          {
            series_id: "M002",
            series_name: "DR007",
            vendor_name: "choice",
            vendor_version: "vv_choice_catalog_v1",
            frequency: "daily",
            unit: "%",
            refresh_tier: "fallback" as const,
            fetch_mode: "latest" as const,
            fetch_granularity: "single" as const,
            policy_note: "low-frequency latest-only lane",
          },
          {
            series_id: "M003",
            series_name: "RMB Index",
            vendor_name: "choice",
            vendor_version: "vv_choice_catalog_v1",
            frequency: "daily",
            unit: "%",
            refresh_tier: "stable" as const,
            fetch_mode: "date_slice" as const,
            fetch_granularity: "batch" as const,
            policy_note: "main refresh date-slice lane",
          },
        ],
      },
    }));
    const getChoiceMacroLatest = vi.fn(async () => ({
      result_meta: latestMeta,
      result: {
        read_target: "duckdb" as const,
        series: [
          {
            series_id: "M001",
            series_name: "Open Market 7D Reverse Repo",
            trade_date: "2026-04-10",
            value_numeric: 1.75,
            unit: "%",
            source_version: "sv_choice_macro_latest_test",
            vendor_version: "vv_choice_macro_20260410",
            frequency: "daily",
            refresh_tier: "stable" as const,
            fetch_mode: "date_slice" as const,
            fetch_granularity: "batch" as const,
            policy_note: "main refresh date-slice lane",
            quality_flag: "ok" as const,
            latest_change: 0.2,
            recent_points: [
              {
                trade_date: "2026-04-10",
                value_numeric: 1.75,
                source_version: "sv_choice_macro_latest_test",
                vendor_version: "vv_choice_macro_20260410",
                quality_flag: "ok" as const,
              },
              {
                trade_date: "2026-04-09",
                value_numeric: 1.55,
                source_version: "sv_choice_macro_prev_test",
                vendor_version: "vv_choice_macro_20260409",
                quality_flag: "ok" as const,
              },
            ],
          },
          {
            series_id: "M002",
            series_name: "DR007",
            trade_date: "2026-04-10",
            value_numeric: 1.83,
            unit: "%",
            source_version: "sv_choice_macro_latest_test",
            vendor_version: "vv_choice_macro_20260410",
            frequency: "daily",
            refresh_tier: "fallback" as const,
            fetch_mode: "latest" as const,
            fetch_granularity: "single" as const,
            policy_note: "low-frequency latest-only lane",
            quality_flag: "warning" as const,
            latest_change: null,
            recent_points: [
              {
                trade_date: "2026-04-10",
                value_numeric: 1.83,
                source_version: "sv_choice_macro_latest_test",
                vendor_version: "vv_choice_macro_20260410",
                quality_flag: "warning" as const,
              },
            ],
          },
        ],
      },
    }));

    renderPage({
      ...base,
      getMacroFoundation,
      getChoiceMacroLatest,
    });

    expect(await screen.findByTestId("market-data-page-title")).toHaveTextContent("市场数据");
    expect(screen.getByText(/观察日期/)).toBeInTheDocument();
    expect(screen.getByText("市场概览")).toBeInTheDocument();
    expect(screen.getByText("利率、资金、宏观深度与成交观察")).toBeInTheDocument();
    expect(screen.getByText("宏观序列与分析观察")).toBeInTheDocument();
    expect(screen.getByText("目录与结果元数据")).toBeInTheDocument();
    expect(await screen.findAllByText("Open Market 7D Reverse Repo")).toHaveLength(2);
    expect(screen.getAllByText("DR007")).toHaveLength(3);
    expect(screen.getByTestId("market-data-catalog-count")).toHaveTextContent("3");
    expect(screen.getByTestId("market-data-stable-count")).toHaveTextContent("1 / 2");
    expect(screen.getByTestId("market-data-fallback-count")).toHaveTextContent("1");
    expect(screen.getByTestId("market-data-stable-trade-date")).toHaveTextContent(
      "2026-04-10",
    );
    expect(screen.getByTestId("market-data-missing-stable-count")).toHaveTextContent("1");
    expect(screen.getByText("待补齐 stable")).toBeInTheDocument();
    expect(
      within(screen.getByTestId("market-data-missing-stable-section")).getByText("RMB Index"),
    ).toBeInTheDocument();
    expect(screen.getByTestId("market-data-result-meta")).toHaveTextContent(
      "tr_choice_macro_latest_test",
    );
    expect(screen.getByTestId("market-data-result-meta")).toHaveTextContent("vendor_status: ok");
    expect(screen.getByTestId("market-data-result-meta")).toHaveTextContent("fallback_mode: none");
    expect(screen.getByTestId("market-data-macro-readiness")).toHaveTextContent("已返回数据");
    expect(screen.getByTestId("market-data-overview-live-meta")).toHaveTextContent(
      "vv_choice_macro_20260410",
    );
    expect(screen.getByTestId("market-data-curve-live-meta")).toHaveTextContent("vendor_status=ok");
    expect(screen.getByTestId("market-data-macro-section-meta")).toHaveTextContent(
      "tr_choice_macro_latest_test",
    );
    expect(screen.getByText("稳定主链路")).toBeInTheDocument();
    expect(screen.getByText("降级 latest-only")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-series-M001")).toHaveTextContent("tier stable");
    expect(screen.getByTestId("market-data-series-M001")).toHaveTextContent("date_slice / batch");
    expect(screen.getByTestId("market-data-series-M001")).toHaveTextContent("main refresh date-slice lane");
    expect(screen.getByTestId("market-data-series-M001")).toHaveTextContent("+20 bp");
    expect(screen.getByTestId("market-data-series-M001")).toHaveTextContent("2026-04-09");
    expect(screen.getByTestId("market-data-series-M002")).toHaveTextContent("tier fallback");
    expect(screen.getByTestId("market-data-series-M002")).toHaveTextContent("latest / single");
    expect(screen.getByTestId("market-data-series-M002")).toHaveTextContent("low-frequency latest-only lane");
    expect(screen.getByText("宏观序列观察")).toBeInTheDocument();
    expect(screen.getByText("FX analytical 观察")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "结果元数据" })).toBeInTheDocument();

    expect(screen.getByText("收益率曲线")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-rate-quote-table")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-money-market-table")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-rate-trend-empty")).toBeInTheDocument();

    await waitFor(() => {
      expect(getMacroFoundation).toHaveBeenCalledTimes(1);
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
    });
  });

  it("renders rate trend ECharts when Choice macro includes configured yield series", async () => {
    const base = createApiClient({ mode: "mock" });
    const pointMeta = {
      source_version: "sv_rate_test",
      vendor_version: "vv_rate_test",
      frequency: "daily" as const,
      refresh_tier: "stable" as const,
      fetch_mode: "date_slice" as const,
      fetch_granularity: "batch" as const,
      policy_note: "rate lane",
      quality_flag: "ok" as const,
    };
    const recent = [
      {
        trade_date: "2026-04-10",
        value_numeric: 2.85,
        source_version: "sv_rate_test",
        vendor_version: "vv_rate_test",
        quality_flag: "ok" as const,
      },
      {
        trade_date: "2026-04-09",
        value_numeric: 2.83,
        source_version: "sv_rate_test",
        vendor_version: "vv_rate_test",
        quality_flag: "ok" as const,
      },
    ];
    const getChoiceMacroLatest = vi.fn(async () => ({
      result_meta: {
        trace_id: "tr_rate_trend",
        basis: "analytical" as const,
        result_kind: "macro.choice.latest",
        formal_use_allowed: false,
        source_version: "sv_rate_test",
        vendor_version: "vv_rate_test",
        rule_version: "rv_test",
        cache_version: "cv_test",
        quality_flag: "ok" as const,
        vendor_status: "ok" as const,
        fallback_mode: "none" as const,
        scenario_flag: false,
        generated_at: "2026-04-10T09:00:00Z",
      },
      result: {
        read_target: "duckdb" as const,
        series: [
          {
            series_id: "EMM00166466",
            series_name: "国债 10Y 测试",
            trade_date: "2026-04-10",
            value_numeric: 2.85,
            unit: "%",
            latest_change: 0.02,
            recent_points: recent,
            ...pointMeta,
          },
          {
            series_id: "EMM00166462",
            series_name: "国开 5Y 测试",
            trade_date: "2026-04-10",
            value_numeric: 2.92,
            unit: "%",
            latest_change: 0.01,
            recent_points: recent.map((p, i) =>
              i === 0 ? { ...p, value_numeric: 2.92 } : { ...p, value_numeric: 2.9 },
            ),
            ...pointMeta,
          },
          {
            series_id: "EMM00166252",
            series_name: "SHIBOR O/N 测试",
            trade_date: "2026-04-10",
            value_numeric: 1.42,
            unit: "%",
            latest_change: null,
            recent_points: recent.map((p, i) =>
              i === 0 ? { ...p, value_numeric: 1.42 } : { ...p, value_numeric: 1.4 },
            ),
            ...pointMeta,
          },
        ],
      },
    }));

    renderPage({
      ...base,
      getMacroFoundation: vi.fn(async () => ({
        result_meta: {
          trace_id: "tr_foundation_min",
          basis: "analytical" as const,
          result_kind: "preview.macro-foundation",
          formal_use_allowed: false,
          source_version: "sv_f",
          vendor_version: "vv_f",
          rule_version: "rv_f",
          cache_version: "cv_f",
          quality_flag: "ok" as const,
          vendor_status: "ok" as const,
          fallback_mode: "none" as const,
          scenario_flag: false,
          generated_at: "2026-04-10T09:00:00Z",
        },
        result: { read_target: "duckdb" as const, series: [] },
      })),
      getChoiceMacroLatest,
    });

    expect(await screen.findByTestId("market-data-rate-trend-chart")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-echarts-stub")).toBeInTheDocument();

    await waitFor(() => {
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
    });
  });

  it("distinguishes Choice macro latest failures from an empty rate trend", async () => {
    const base = createApiClient({ mode: "mock" });
    const getChoiceMacroLatest = vi.fn(async () => {
      throw new Error("choice latest unavailable");
    });

    renderPage({
      ...base,
      getChoiceMacroLatest,
    });

    const curveError = await screen.findByTestId("market-data-rate-trend-error");
    expect(curveError).toHaveTextContent("宏观 latest 载入失败");
    expect(screen.queryByTestId("market-data-rate-trend-empty")).not.toBeInTheDocument();

    await waitFor(() => {
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
    });
  });

  it("renders analytical FX groups separately from the macro sections", async () => {
    const base = createApiClient({ mode: "mock" });
    const getFxAnalytical = vi.fn(async () => ({
      result_meta: {
        trace_id: "tr_fx_analytical_test",
        basis: "analytical" as const,
        result_kind: "fx.analytical.groups",
        formal_use_allowed: false,
        source_version: "sv_fx_analytical_test",
        vendor_version: "vv_fx_analytical_test",
        rule_version: "rv_fx_analytical_v1",
        cache_version: "cv_fx_analytical_v1",
        quality_flag: "warning" as const,
        vendor_status: "ok" as const,
        fallback_mode: "latest_snapshot" as const,
        scenario_flag: false,
        generated_at: "2026-04-12T09:10:00Z",
      },
      result: {
        read_target: "duckdb" as const,
        groups: [
          {
            group_key: "middle_rate" as const,
            title: "Analytical FX: middle-rates",
            description:
              "Catalog-observed middle-rate series remain analytical views and do not redefine the formal seam.",
            series: [
              {
                group_key: "middle_rate" as const,
                series_id: "FX.USD.CNY",
                series_name: "USD/CNY middle-rate observation",
                trade_date: "2026-04-11",
                value_numeric: 7.21,
                frequency: "daily",
                unit: "CNY",
                source_version: "sv_fx_analytical_test",
                vendor_version: "vv_fx_analytical_test",
                refresh_tier: "stable" as const,
                fetch_mode: "date_slice" as const,
                fetch_granularity: "batch" as const,
                policy_note: "analytical middle-rate observation only",
                quality_flag: "ok" as const,
                latest_change: 0.01,
                recent_points: [
                  {
                    trade_date: "2026-04-11",
                    value_numeric: 7.21,
                    source_version: "sv_fx_analytical_test",
                    vendor_version: "vv_fx_analytical_test",
                    quality_flag: "ok" as const,
                  },
                  {
                    trade_date: "2026-04-10",
                    value_numeric: 7.2,
                    source_version: "sv_fx_analytical_prev",
                    vendor_version: "vv_fx_analytical_prev",
                    quality_flag: "ok" as const,
                  },
                ],
              },
            ],
          },
          {
            group_key: "fx_index" as const,
            title: "Analytical FX: indices",
            description:
              "RMB index / estimate index series stay analytical-only and never flow into formal FX.",
            series: [
              {
                group_key: "fx_index" as const,
                series_id: "FX.RMB.INDEX",
                series_name: "RMB basket index",
                trade_date: "2026-04-11",
                value_numeric: 101.32,
                frequency: "daily",
                unit: "index",
                source_version: "sv_fx_analytical_test",
                vendor_version: "vv_fx_analytical_test",
                refresh_tier: "fallback" as const,
                fetch_mode: "latest" as const,
                fetch_granularity: "single" as const,
                policy_note: "analytical index observation only",
                quality_flag: "warning" as const,
                latest_change: null,
                recent_points: [],
              },
            ],
          },
        ],
      },
    }));

    renderPage({
      ...base,
      getFxAnalytical,
    });

    expect(await screen.findByText("Analytical FX: middle-rates")).toBeInTheDocument();
    expect(screen.getByText("Analytical FX: indices")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-fx-analytical-group-count")).toHaveTextContent("2");
    expect(screen.getByTestId("market-data-fx-analytical-series-count")).toHaveTextContent("2");
    expect(screen.getByTestId("market-data-fx-group-middle_rate")).toHaveTextContent(
      "USD/CNY middle-rate observation",
    );
    expect(screen.getByTestId("market-data-fx-group-middle_rate")).toHaveTextContent(
      "analytical middle-rate observation only",
    );
    expect(screen.getByTestId("market-data-fx-group-fx_index")).toHaveTextContent(
      "RMB basket index",
    );
    expect(screen.getByTestId("market-data-fx-analytical-meta")).toHaveTextContent(
      "tr_fx_analytical_test",
    );
    expect(screen.getByTestId("market-data-fx-section-meta")).toHaveTextContent(
      "fallback_mode=latest_snapshot",
    );

    await waitFor(() => {
      expect(getFxAnalytical).toHaveBeenCalledTimes(1);
    });
  });

  it("renders macro-bond linkage as an analytical estimate with explicit tenor slots", async () => {
    const client = createApiClient({ mode: "mock" });

    renderPage(client);

    expect(await screen.findByTestId("market-data-linkage-caveat")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-linkage-caveat")).toHaveTextContent("analytical");
    expect(screen.getByTestId("market-data-linkage-caveat")).toHaveTextContent("non-formal");
    expect(screen.getByTestId("market-data-linkage-caveat")).toHaveTextContent("分析估算");
    expect(screen.getByTestId("market-data-linkage-warning-list")).toHaveTextContent(
      "Analytical signal only",
    );
    expect(screen.getByTestId("market-data-linkage-composite-score")).toHaveTextContent("-0.11");
    expect(screen.getByTestId("market-data-linkage-rate-direction")).toHaveTextContent("falling");
    expect(screen.getByTestId("market-data-linkage-portfolio-impact")).toHaveTextContent(
      "组合影响估算",
    );
    expect(screen.getByTestId("market-data-linkage-portfolio-impact")).toHaveTextContent(
      "total estimate",
    );
    expect(screen.getByTestId("market-data-linkage-spread-slot-5Y")).toHaveTextContent(
      "10Y treasury yield",
    );
    expect(screen.getByTestId("market-data-linkage-spread-slot-3Y")).toHaveTextContent(
      "unavailable",
    );
    expect(screen.getByTestId("market-data-linkage-spread-slot-10Y")).toHaveTextContent(
      "unavailable",
    );
    expect(screen.getByTestId("market-data-linkage-top-correlations")).toHaveTextContent(
      "CPI YoY",
    );
    expect(screen.getByTestId("market-data-linkage-meta")).toHaveTextContent(
      "formal_use_allowed: false",
    );
    expect(screen.getByTestId("market-data-spreads-live-meta")).toHaveTextContent("联动读面");
  });

  it("runs refresh polling and refetches the market-data queries after completion", async () => {
    const base = createApiClient({ mode: "mock" });
    const getMacroFoundation = vi.fn(() => base.getMacroFoundation());
    const getChoiceMacroLatest = vi.fn(() => base.getChoiceMacroLatest());
    const getFxAnalytical = vi.fn(() => base.getFxAnalytical());
    const getMacroBondLinkageAnalysis = vi.fn((options: { reportDate: string }) =>
      base.getMacroBondLinkageAnalysis(options),
    );
    const refreshChoiceMacro = vi.fn(async () => ({
      status: "queued",
      run_id: "run-market-data-1",
      detail: null,
      error_message: null,
    }));
    const getChoiceMacroRefreshStatus = vi.fn(async () => ({
      status: "completed",
      run_id: "run-market-data-1",
      detail: null,
      error_message: null,
    }));

    let completeRefresh: (() => void) | null = null;
    vi.mocked(runPollingTask).mockImplementation(async ({ start, getStatus, onUpdate }) => {
      const started = await start();
      onUpdate?.(started);
      await new Promise<void>((resolve) => {
        completeRefresh = resolve;
      });
      const completed = await getStatus(started.run_id ?? "");
      onUpdate?.(completed);
      return completed;
    });

    renderPage({
      ...base,
      getMacroFoundation,
      getChoiceMacroLatest,
      getFxAnalytical,
      getMacroBondLinkageAnalysis,
      refreshChoiceMacro,
      getChoiceMacroRefreshStatus,
    });

    expect(await screen.findByTestId("market-data-page-title")).toBeInTheDocument();
    await waitFor(() => {
      expect(getMacroFoundation).toHaveBeenCalledTimes(1);
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
      expect(getFxAnalytical).toHaveBeenCalledTimes(1);
      expect(getMacroBondLinkageAnalysis).toHaveBeenCalledTimes(1);
    });

    fireEvent.click(screen.getByTestId("market-data-refresh-button"));

    await waitFor(() => {
      expect(refreshChoiceMacro).toHaveBeenCalledWith(30);
      expect(screen.getByTestId("market-data-refresh-button")).toBeDisabled();
      expect(screen.getByText("queued · run-market-data-1")).toBeInTheDocument();
    });

    const finishRefresh = completeRefresh as (() => void) | null;
    expect(finishRefresh).not.toBeNull();
    if (!finishRefresh) {
      throw new Error("Expected refresh completer to be registered");
    }
    finishRefresh();

    await waitFor(() => {
      expect(getChoiceMacroRefreshStatus).toHaveBeenCalledWith("run-market-data-1");
      expect(screen.getByText("刷新完成")).toBeInTheDocument();
      expect(screen.getByTestId("market-data-refresh-button")).not.toBeDisabled();
    });

    await waitFor(() => {
      expect(getMacroFoundation).toHaveBeenCalledTimes(2);
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(2);
      expect(getFxAnalytical).toHaveBeenCalledTimes(2);
      expect(getMacroBondLinkageAnalysis).toHaveBeenCalledTimes(2);
    });
  });

  it("updates shell filter state locally without changing the current query contract", async () => {
    const base = createApiClient({ mode: "mock" });
    const getMacroFoundation = vi.fn(() => base.getMacroFoundation());
    const getChoiceMacroLatest = vi.fn(() => base.getChoiceMacroLatest());

    renderPage({
      ...base,
      getMacroFoundation,
      getChoiceMacroLatest,
    });

    expect(await screen.findByTestId("market-data-page-title")).toBeInTheDocument();
    await waitFor(() => {
      expect(getMacroFoundation).toHaveBeenCalledTimes(1);
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
    });

    fireEvent.change(screen.getByLabelText("日期"), { target: { value: "2026-03-01" } });
    expect(screen.getByText("观察日期 2026-03-01")).toBeInTheDocument();

    const curveLabel = screen.getByText("国债 / 国开").closest("label");
    const sourceLabel = screen.getByText("来源").closest("label");
    if (!curveLabel || !sourceLabel) {
      throw new Error("filter label shell not found");
    }

    const curveSelector = curveLabel.querySelector(".ant-select-selector");
    const sourceSelector = sourceLabel.querySelector(".ant-select-selector");
    if (!curveSelector || !sourceSelector) {
      throw new Error("select shell not found");
    }

    fireEvent.mouseDown(curveSelector);
    const curveOption = (await screen.findAllByText("国债")).at(-1);
    if (!curveOption) {
      throw new Error("curve option not found");
    }
    fireEvent.click(curveOption);
    await waitFor(() => {
      expect(curveLabel).toHaveTextContent("国债");
    });

    fireEvent.mouseDown(sourceSelector);
    const sourceOption = (await screen.findAllByText("Choice")).at(-1);
    if (!sourceOption) {
      throw new Error("source option not found");
    }
    fireEvent.click(sourceOption);
    await waitFor(() => {
      expect(sourceLabel).toHaveTextContent("Choice");
    });

    await waitFor(() => {
      expect(getMacroFoundation).toHaveBeenCalledTimes(1);
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
    });
  });

  it("renders the sixth-page market-data cockpit sections from the mockup", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    expect(await screen.findByTestId("market-data-page-title")).toHaveTextContent("市场数据");
    expect(screen.getByText("利率行情")).toBeInTheDocument();
    expect(screen.getByText("收益率曲线")).toBeInTheDocument();
    expect(
      within(screen.getByTestId("market-data-linkage-spread-table")).getByText("信用利差"),
    ).toBeInTheDocument();
    expect(screen.getByText("资金市场")).toBeInTheDocument();
    expect(screen.getByText("国债期货")).toBeInTheDocument();
    expect(screen.getByText("同业存单")).toBeInTheDocument();
    expect(screen.getByText("债券成交明细（现券）")).toBeInTheDocument();
    expect(screen.getByText("信用债成交明细")).toBeInTheDocument();
    expect(screen.getByText("资讯与日历")).toBeInTheDocument();
  });

  it("renders an explicit Shibor proxy in the NCD panel instead of pretending it is a live NCD matrix", async () => {
    const base = createApiClient({ mode: "mock" });
    const getNcdFundingProxy = vi.fn(async () => ({
      result_meta: {
        trace_id: "tr_ncd_proxy_test",
        basis: "analytical" as const,
        result_kind: "market_data.ncd_proxy",
        formal_use_allowed: false,
        source_version: "sv_ncd_proxy_test",
        vendor_version: "vv_tushare_shibor",
        rule_version: "rv_ncd_proxy_v1",
        cache_version: "cv_ncd_proxy_v1",
        quality_flag: "ok" as const,
        vendor_status: "ok" as const,
        fallback_mode: "none" as const,
        scenario_flag: false,
        generated_at: "2026-04-23T10:00:00Z",
      },
      result: {
        as_of_date: "2026-04-23",
        proxy_label: "Tushare Shibor funding proxy",
        is_actual_ncd_matrix: false,
        rows: [
          {
            row_key: "shibor_fixing",
            label: "Shibor fixing",
            "1M": 1.405,
            "3M": 1.4275,
            "6M": 1.4505,
            "9M": 1.464,
            "1Y": 1.478,
            quote_count: null,
          },
        ],
        warnings: [
          "Using landed external warehouse Shibor; quote medians unavailable.",
          "Proxy only; not actual NCD issuance matrix.",
        ],
      },
    }));

    renderPage({
      ...base,
      getNcdFundingProxy,
    });

    expect(await screen.findByTestId("market-data-ncd-matrix")).toBeInTheDocument();
    expect(await screen.findByText("Tushare Shibor funding proxy")).toBeInTheDocument();
    expect(await screen.findByText("Shibor fixing")).toBeInTheDocument();
    expect(screen.queryByText("Quote median")).not.toBeInTheDocument();
    expect(
      await screen.findByText(/quote medians unavailable|not actual NCD issuance matrix/i),
    ).toBeInTheDocument();
    expect(await screen.findByText("1.405")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-ncd-live-meta")).toHaveTextContent("tr_ncd_proxy_test");
    expect(screen.getByTestId("market-data-ncd-live-meta")).toHaveTextContent("vendor_status=ok");
  });
});
