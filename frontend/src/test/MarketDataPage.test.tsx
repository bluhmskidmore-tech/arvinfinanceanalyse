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
import type { ChoiceMacroLatestPoint, ResultMeta } from "../api/contracts";
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

function buildResultMeta(partial: Partial<ResultMeta> = {}): ResultMeta {
  return {
    trace_id: "tr_market_data_test",
    basis: "formal",
    result_kind: "market_data.rates",
    formal_use_allowed: true,
    source_version: "sv_market_data_test",
    vendor_version: "vv_market_data_test",
    rule_version: "rv_market_data_test",
    cache_version: "cv_market_data_test",
    quality_flag: "ok",
    vendor_status: "ok",
    fallback_mode: "none",
    scenario_flag: false,
    generated_at: "2026-04-30T09:00:00Z",
    ...partial,
  };
}

function buildMacroPoint(
  partial: Partial<ChoiceMacroLatestPoint> & Pick<ChoiceMacroLatestPoint, "series_id">,
): ChoiceMacroLatestPoint {
  return {
    series_name: partial.series_id,
    trade_date: "2026-04-30",
    value_numeric: 1.94,
    unit: "%",
    source_version: "sv_market_data_test",
    vendor_version: "vv_market_data_test",
    refresh_tier: "stable",
    fetch_mode: "date_slice",
    fetch_granularity: "batch",
    quality_flag: "ok",
    latest_change: 0.012,
    recent_points: [],
    ...partial,
  };
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
    const getLivermoreStrategy = vi.fn(async (options?: { asOfDate?: string }) => ({
      result_meta: {
        trace_id: "tr_livermore_page_test",
        basis: "analytical" as const,
        result_kind: "market_data.livermore",
        formal_use_allowed: false,
        source_version: "sv_livermore_page_test",
        vendor_version: "vv_livermore_page_test",
        rule_version: "rv_livermore_page_test",
        cache_version: "cv_livermore_page_test",
        quality_flag: "ok" as const,
        vendor_status: "ok" as const,
        fallback_mode: "none" as const,
        scenario_flag: false,
        generated_at: "2026-04-29T09:00:00Z",
      },
      result: {
        as_of_date: options?.asOfDate ?? "2026-04-29",
        requested_as_of_date: options?.asOfDate ?? null,
        strategy_name: "Livermore A股趋势门控",
        basis: "analytical" as const,
        market_gate: {
          state: "WARM" as const,
          exposure: 0.4,
          passed_conditions: 2,
          available_conditions: 2,
          required_conditions: 4,
          conditions: [
            {
              key: "csi300_close_gt_ma60",
              label: "CSI300 close > MA60",
              status: "pass" as const,
              evidence: "收盘价高于 MA60。",
              source_series_id: "CA.CSI300",
            },
            {
              key: "csi300_ma20_gt_ma60",
              label: "CSI300 MA20 > MA60",
              status: "pass" as const,
              evidence: "MA20 高于 MA60。",
              source_series_id: "CA.CSI300",
            },
            {
              key: "breadth_5d_positive",
              label: "5-day breadth > 0",
              status: "missing" as const,
              evidence: "Breadth inputs are not landed for the Phase 1 slice.",
              source_series_id: null,
            },
            {
              key: "limit_up_quality_positive",
              label: "Limit-up seal/break quality positive",
              status: "missing" as const,
              evidence: "Limit-up quality inputs are not landed for the Phase 1 slice.",
              source_series_id: null,
            },
          ],
        },
        rule_readiness: [
          {
            key: "market_gate" as const,
            title: "Market gate",
            status: "partial" as const,
            summary: "Trend-only market gate is available; breadth and limit-up quality remain missing.",
            required_inputs: ["broad_index_history", "breadth", "limit_up_quality"],
            missing_inputs: ["breadth", "limit_up_quality"],
          },
          {
            key: "sector_rank" as const,
            title: "Sector ranking",
            status: "missing" as const,
            summary: "Sector membership and sector-strength inputs are not landed yet.",
            required_inputs: ["sector_membership", "sector_strength"],
            missing_inputs: ["sector_membership", "sector_strength"],
          },
          {
            key: "stock_pivot" as const,
            title: "Stock pivot filters",
            status: "blocked" as const,
            summary: "Stock pivot output is blocked until sector rank and stock-universe inputs land.",
            required_inputs: ["stock_ohlcv", "stock_status", "sector_rank"],
            missing_inputs: ["stock_ohlcv", "stock_status", "sector_rank"],
          },
          {
            key: "risk_exit" as const,
            title: "Risk and exit rules",
            status: "ready" as const,
            summary: "Risk and exit output is available from landed position snapshots and close history.",
            required_inputs: ["positions", "entry_cost", "bars_since_entry", "close_history"],
            missing_inputs: [],
          },
        ],
        diagnostics: [
          {
            severity: "warning" as const,
            code: "LIVERMORE_BREADTH_MISSING",
            message: "Breadth inputs are unavailable; the market gate is capped at the trend-only slice.",
            input_family: "breadth",
          },
          {
            severity: "warning" as const,
            code: "LIVERMORE_LIMIT_UP_QUALITY_MISSING",
            message: "Limit-up quality inputs are unavailable; the market gate is capped at the trend-only slice.",
            input_family: "limit_up_quality",
          },
          {
            severity: "warning" as const,
            code: "LIVERMORE_SECTOR_INPUTS_MISSING",
            message: "Sector membership and sector-strength inputs are unavailable.",
            input_family: "sector_strength",
          },
          {
            severity: "warning" as const,
            code: "LIVERMORE_STOCK_INPUTS_MISSING",
            message: "Stock-universe inputs are unavailable, so no candidates are produced.",
            input_family: "stock_universe",
          },
          {
            severity: "warning" as const,
            code: "LIVERMORE_RISK_INPUTS_MISSING",
            message:
              "The defended-bundle 10EMA invalidation MVP is implemented, but position, entry-cost, bars-since-entry, and close-history inputs are unavailable, so risk/exit output remains blocked.",
            input_family: "position_risk",
          },
        ],
        data_gaps: [
          {
            input_family: "breadth",
            status: "missing" as const,
            evidence: "5-day breadth input family is not landed in DuckDB for this slice.",
          },
          {
            input_family: "limit_up_quality",
            status: "missing" as const,
            evidence: "Limit-up seal/break quality input family is not landed in DuckDB for this slice.",
          },
          {
            input_family: "sector_strength",
            status: "missing" as const,
            evidence: "Sector membership and ranking inputs are not landed in DuckDB for this slice.",
          },
          {
            input_family: "stock_universe",
            status: "missing" as const,
            evidence: "Stock OHLCV, status, and candidate-filter inputs are not landed in DuckDB for this slice.",
          },
          {
            input_family: "position_risk",
            status: "missing" as const,
            evidence:
              "Position, entry-cost, bars-since-entry, and close-history inputs are not landed in DuckDB for the defended-bundle 10EMA invalidation MVP.",
          },
        ],
        supported_outputs: ["market_gate" as const],
        unsupported_outputs: [
          {
            key: "sector_rank" as const,
            reason: "Sector membership and sector-strength inputs are not landed yet.",
          },
          {
            key: "stock_candidates" as const,
            reason: "Stock-level OHLCV, status, and candidate filters are not landed yet.",
          },
          {
            key: "risk_exit" as const,
            reason:
              "The defended-bundle 10EMA invalidation MVP remains blocked until position, entry-cost, bars-since-entry, and close-history inputs land.",
          },
        ],
      },
    }));

    renderPage({
      ...base,
      getMacroFoundation,
      getChoiceMacroLatest,
      getLivermoreStrategy,
    });

    expect(await screen.findByTestId("market-data-page-title")).toHaveTextContent("市场数据");
    expect(screen.getByText(/观察日期/)).toBeInTheDocument();
    expect(screen.getByText("市场概览")).toBeInTheDocument();
    expect(screen.getByText("利率、资金、宏观深度与成交观察")).toBeInTheDocument();
    expect(screen.getByText("Livermore 趋势门控")).toBeInTheDocument();
    expect(screen.queryByText("宏观序列与分析观察")).not.toBeInTheDocument();
    expect(screen.queryByText("目录与结果元数据")).not.toBeInTheDocument();
    expect(await screen.findByTestId("livermore-market-state")).toHaveTextContent("WARM");
    expect(screen.getByTestId("market-data-livermore-panel")).toHaveTextContent(
      "分析口径 · 不生成交易指令",
    );
    expect(screen.getByTestId("livermore-rule-readiness")).toHaveTextContent("Sector ranking");
    expect(screen.getByTestId("livermore-rule-readiness")).toHaveTextContent("Stock pivot filters");
    expect(screen.getByTestId("livermore-rule-readiness")).toHaveTextContent("Risk and exit rules");
    expect(screen.getByTestId("livermore-diagnostics")).toHaveTextContent("LIVERMORE_STOCK_INPUTS_MISSING");
    const dataGaps = screen.getByTestId("livermore-data-gaps");
    expect(dataGaps).toHaveTextContent("sector_strength");
    expect(dataGaps).toHaveTextContent("stock_universe");
    expect(dataGaps).toHaveTextContent("position_risk");
    expect(dataGaps).toHaveTextContent("Stock OHLCV, status, and candidate-filter inputs are not landed");
    expect(screen.getByTestId("livermore-unsupported-outputs")).toHaveTextContent("板块排序");
    expect(screen.getByTestId("livermore-unsupported-outputs")).toHaveTextContent("个股候选");
    expect(screen.getByTestId("livermore-unsupported-outputs")).toHaveTextContent("风险退出");
    expect(screen.getByTestId("livermore-unsupported-outputs")).not.toHaveTextContent("推荐标的");
    expect(screen.getByTestId("market-data-catalog-count")).toHaveTextContent("3");
    expect(screen.getByTestId("market-data-stable-count")).toHaveTextContent("1 / 2");
    expect(screen.getByTestId("market-data-fallback-count")).toHaveTextContent("1");
    expect(screen.getByTestId("market-data-stable-trade-date")).toHaveTextContent(
      "2026-04-10",
    );
    expect(screen.getByTestId("market-data-missing-stable-count")).toHaveTextContent("1");
    expect(screen.queryByTestId("market-data-missing-stable-section")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-result-meta")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-macro-readiness")).not.toBeInTheDocument();
    expect(screen.getByTestId("market-data-overview-live-meta")).toHaveTextContent(
      "vv_choice_macro_20260410",
    );
    expect(screen.getByTestId("market-data-curve-live-meta")).toHaveTextContent("供应商状态=正常");
    expect(screen.queryByTestId("market-data-macro-section-meta")).not.toBeInTheDocument();
    expect(screen.queryByText("稳定主链路")).not.toBeInTheDocument();
    expect(screen.queryByText("仅取最新降级")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-series-M001")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-series-M002")).not.toBeInTheDocument();
    expect(screen.queryByText("宏观序列观察")).not.toBeInTheDocument();
    expect(screen.queryByText("外汇分析观察")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "结果元数据" })).not.toBeInTheDocument();

    expect(screen.getByText("收益率曲线")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-rate-quote-table")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-money-market-table")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-rate-trend-empty")).toBeInTheDocument();

    await waitFor(() => {
      expect(getMacroFoundation).toHaveBeenCalledTimes(1);
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
      expect(getLivermoreStrategy).toHaveBeenCalledWith({
        asOfDate: expect.any(String),
      });
    });
  });

  it("drives terminal market panels from formal/latest data and source-pending states", async () => {
    const base = createApiClient({ mode: "mock" });
    const rateSeries = [
      buildMacroPoint({
        series_id: "EMM00166466",
        series_name: "中债国债到期收益率:10年",
        value_numeric: 1.94,
        latest_change: -0.012,
      }),
      buildMacroPoint({
        series_id: "EMM00166502",
        series_name: "中债政策性金融债到期收益率(国开行)10年",
        value_numeric: 2.05,
        latest_change: 0.004,
      }),
      buildMacroPoint({
        series_id: "M001",
        series_name: "公开市场7天逆回购利率",
        value_numeric: 1.75,
        latest_change: 0.001,
      }),
      buildMacroPoint({
        series_id: "CA.DR007",
        series_name: "存款类机构质押式回购加权利率:DR007",
        value_numeric: 1.82,
        latest_change: -0.006,
        fetch_mode: "latest",
      }),
    ];
    const getMarketDataRates = vi.fn(async () => ({
      result_meta: buildResultMeta({
        trace_id: "tr_formal_rates_terminal_test",
        source_version: "sv_formal_rates_terminal_test",
      }),
      result: {
        read_target: "duckdb" as const,
        series: rateSeries,
      },
    }));
    const getChoiceMacroLatest = vi.fn(async () => ({
      result_meta: buildResultMeta({
        basis: "analytical" as const,
        result_kind: "macro.choice.latest",
        formal_use_allowed: false,
      }),
      result: {
        read_target: "duckdb" as const,
        series: rateSeries,
      },
    }));

    renderPage({
      ...base,
      getMarketDataRates,
      getChoiceMacroLatest,
    });

    const rateTable = await screen.findByTestId("market-data-rate-quote-table");
    await within(rateTable).findByText("EMM00166466");
    expect(rateTable).toHaveTextContent("EMM00166466");
    expect(rateTable).toHaveTextContent("中债国债到期收益率:10年");
    expect(rateTable).toHaveTextContent("1.94%");
    expect(rateTable).toHaveTextContent("-1bp");
    expect(rateTable).toHaveTextContent("2026-04-30");
    expect(rateTable).toHaveTextContent("sv_formal_rates_terminal_test");
    expect(rateTable).not.toHaveTextContent("4,856");

    const moneyTable = screen.getByTestId("market-data-money-market-table");
    expect(moneyTable).toHaveTextContent("公开市场7天逆回购利率");
    expect(moneyTable).toHaveTextContent("CA.DR007");
    expect(moneyTable).toHaveTextContent("-0.6bp");
    expect(moneyTable).not.toHaveTextContent("24,331");

    expect(screen.getByTestId("market-data-bond-futures-source-pending")).toHaveTextContent("source-pending");
    expect(screen.getByTestId("market-data-bond-trades-source-pending")).toHaveTextContent("source-pending");
    expect(screen.getByTestId("market-data-credit-trades-source-pending")).toHaveTextContent("source-pending");

    await waitFor(() => {
      expect(getMarketDataRates).toHaveBeenCalledTimes(1);
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
    });
  });

  it("renders emitted Livermore sector rank and stock candidates from the backend contract", async () => {
    const base = createApiClient({ mode: "mock" });
    const getMacroFoundation = vi.fn(async () => base.getMacroFoundation());
    const getChoiceMacroLatest = vi.fn(async () => base.getChoiceMacroLatest());
    const getLivermoreStrategy = vi.fn(async () => ({
      result_meta: {
        trace_id: "tr_livermore_supported_test",
        basis: "analytical" as const,
        result_kind: "market_data.livermore",
        formal_use_allowed: false,
        source_version: "sv_livermore_supported_test",
        vendor_version: "vv_livermore_supported_test",
        rule_version: "rv_livermore_supported_test",
        cache_version: "cv_livermore_supported_test",
        quality_flag: "ok" as const,
        vendor_status: "ok" as const,
        fallback_mode: "none" as const,
        scenario_flag: false,
        generated_at: "2026-04-29T09:00:00Z",
      },
      result: {
        as_of_date: "2026-04-29",
        requested_as_of_date: "2026-04-29",
        strategy_name: "Livermore A股趋势门控",
        basis: "analytical" as const,
        market_gate: {
          state: "WARM" as const,
          exposure: 0.4,
          passed_conditions: 2,
          available_conditions: 2,
          required_conditions: 4,
          conditions: [
            {
              key: "csi300_close_gt_ma60",
              label: "CSI300 close > MA60",
              status: "pass" as const,
              evidence: "收盘价高于 MA60。",
              source_series_id: "CA.CSI300",
            },
          ],
        },
        rule_readiness: [
          {
            key: "market_gate" as const,
            title: "Market gate",
            status: "partial" as const,
            summary: "Trend-only market gate is available; breadth and limit-up quality remain missing.",
            required_inputs: ["broad_index_history", "breadth", "limit_up_quality"],
            missing_inputs: ["breadth", "limit_up_quality"],
          },
          {
            key: "sector_rank" as const,
            title: "Sector ranking",
            status: "ready" as const,
            summary: "Sector ranking is available from landed Choice sector inputs.",
            required_inputs: ["sector_membership", "sector_strength"],
            missing_inputs: [],
          },
          {
            key: "stock_pivot" as const,
            title: "Stock pivot filters",
            status: "ready" as const,
            summary: "Stock pivot candidate screening is available for landed Choice stock inputs.",
            required_inputs: [
              "stock_universe",
              "stock_ohlcv",
              "stock_status",
              "limit_up_quality",
              "sector_rank",
              "market_gate",
            ],
            missing_inputs: [],
          },
          {
            key: "risk_exit" as const,
            title: "Risk and exit rules",
            status: "blocked" as const,
            summary:
              "The defended-bundle 10EMA invalidation exit kernel is implemented, but output stays blocked until position, entry-cost, bars-since-entry, and close-history inputs land.",
            required_inputs: ["positions", "entry_cost", "bars_since_entry"],
            missing_inputs: ["positions", "entry_cost", "bars_since_entry"],
          },
        ],
        diagnostics: [
          {
            severity: "warning" as const,
            code: "LIVERMORE_SECTOR_RANK_PROVISIONAL_FORMULA",
            message: "Sector rank currently uses the provisional percentile formula over pctchange, turn, and amplitude.",
            input_family: "sector_strength",
          },
        ],
        data_gaps: [
          {
            input_family: "breadth",
            status: "missing" as const,
            evidence: "5-day breadth input family is not landed in DuckDB for this slice.",
          },
          {
            input_family: "limit_up_quality",
            status: "missing" as const,
            evidence: "Choice limit-up quality catalog is confirmed, but landed inputs are unavailable; the market gate is capped at the trend-only slice.",
          },
        ],
        supported_outputs: ["market_gate" as const, "sector_rank" as const, "stock_candidates" as const, "risk_exit" as const],
        unsupported_outputs: [],
        sector_rank: {
          as_of_date: "2026-04-29",
          formula_version: "rv_livermore_sector_rank_provisional_v1",
          is_provisional: true,
          sector_count: 3,
          excluded_constituent_count: 0,
          excluded_sector_count: 0,
          items: [
            {
              rank: 1,
              sector_code: "801001",
              sector_name: "AI",
              score: 1,
              avg_pctchange: 4.8,
              avg_turn: 3,
              avg_amplitude: 3.5,
              constituent_count: 12,
            },
          ],
        },
        stock_candidates: {
          as_of_date: "2026-04-29",
          formula_version: "rv_livermore_stock_candidates_bundle_v1",
          market_state: "WARM" as const,
          input_stock_count: 4,
          candidate_count: 2,
          excluded_stock_count: 2,
          insufficient_history_count: 0,
          items: [
            {
              rank: 1,
              stock_code: "000001.SZ",
              stock_name: "Alpha",
              sector_code: "801001",
              sector_name: "AI",
              sector_rank: 1,
              close: 21.9,
              breakout_level: 21.8,
              ma20: 21.05,
              ma60: 19.05,
              ma120: 16.05,
              close_strength: 0.833333,
              gap_norm: -0.114679,
              abnormal_turnover: 1.386294,
            },
          ],
        },
        risk_exit: {
          as_of_date: "2026-04-29",
          formula_version: "rv_livermore_risk_exit_ema10_mvp_v1",
          position_count: 2,
          signal_count: 1,
          excluded_position_count: 0,
          insufficient_history_count: 0,
          items: [
            {
              stock_code: "000001.SZ",
              stock_name: "Alpha",
              reason: "2d_below_ema10",
              entry_cost: 10.5,
              bars_since_entry: 6,
              latest_close: 9.1,
              latest_ema10: 10.2,
              prior_close: 9.8,
              prior_ema10: 10.4,
            },
          ],
        },
      },
    }));

    renderPage({
      ...base,
      getMacroFoundation,
      getChoiceMacroLatest,
      getLivermoreStrategy,
    });

    expect(await screen.findByTestId("livermore-market-state")).toHaveTextContent("WARM");
    expect(screen.getByTestId("market-data-livermore-panel")).toHaveTextContent("801001");
    expect(screen.getByTestId("market-data-livermore-panel")).toHaveTextContent("000001.SZ");
    expect(screen.getByTestId("market-data-livermore-panel")).toHaveTextContent(
      "rv_livermore_stock_candidates_bundle_v1",
    );
    expect(screen.getByTestId("market-data-livermore-panel")).toHaveTextContent(
      "rv_livermore_risk_exit_ema10_mvp_v1",
    );
    expect(screen.getByTestId("livermore-unsupported-outputs")).not.toHaveTextContent("个股候选");
    expect(screen.getByTestId("livermore-unsupported-outputs")).not.toHaveTextContent("风险退出");
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
    expect(curveError).toHaveTextContent("宏观最新载入失败");
    expect(screen.queryByTestId("market-data-rate-trend-empty")).not.toBeInTheDocument();

    await waitFor(() => {
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
    });
  });

  it("hides fx analysis subsection while still fetching FX payloads for KPIs", async () => {
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

    await waitFor(() => {
      expect(screen.getByTestId("market-data-fx-analytical-group-count")).toHaveTextContent("2");
      expect(screen.getByTestId("market-data-fx-analytical-series-count")).toHaveTextContent("2");
      expect(getFxAnalytical).toHaveBeenCalledTimes(1);
    });

    expect(screen.queryByText("外汇分析观察")).not.toBeInTheDocument();
    expect(screen.queryByText("外汇分析：中间价")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-fx-group-middle_rate")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-fx-section-meta")).not.toBeInTheDocument();
  });

  it("renders macro-bond linkage as an analytical estimate with explicit tenor slots", async () => {
    const client = createApiClient({ mode: "mock" });

    renderPage(client);

    fireEvent.click(await screen.findByRole("tab", { name: "信用利差" }));
    expect(await screen.findByTestId("market-data-spreads-live-meta")).toHaveTextContent("联动读面");

    fireEvent.click(screen.getByText("宏观-债市联动（分析口径，点击展开）"));
    expect(await screen.findByTestId("market-data-linkage-caveat")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-linkage-caveat")).toHaveTextContent("分析口径");
    expect(screen.getByTestId("market-data-linkage-caveat")).toHaveTextContent("非正式口径");
    expect(screen.getByTestId("market-data-linkage-caveat")).toHaveTextContent("分析估算");
    expect(screen.getByTestId("market-data-linkage-warning-list")).toHaveTextContent(
      "仅为分析信号",
    );
    expect(screen.getByTestId("market-data-linkage-composite-score")).toHaveTextContent("-0.11");
    expect(screen.getByTestId("market-data-linkage-rate-direction")).toHaveTextContent("falling");
    expect(screen.getByTestId("market-data-linkage-portfolio-impact")).toHaveTextContent(
      "组合影响估算",
    );
    expect(screen.getByTestId("market-data-linkage-portfolio-impact")).toHaveTextContent(
      "合计估算",
    );
    expect(screen.getByTestId("market-data-linkage-spread-slot-5Y")).toHaveTextContent(
      "10Y treasury yield",
    );
    expect(screen.getByTestId("market-data-linkage-spread-slot-3Y")).toHaveTextContent(
      "不可用",
    );
    expect(screen.getByTestId("market-data-linkage-spread-slot-10Y")).toHaveTextContent(
      "不可用",
    );
    expect(screen.getByTestId("market-data-linkage-top-correlations")).toHaveTextContent(
      "CPI YoY",
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
    const getLivermoreStrategy = vi.fn((options?: { asOfDate?: string }) =>
      base.getLivermoreStrategy(options),
    );

    renderPage({
      ...base,
      getMacroFoundation,
      getChoiceMacroLatest,
      getLivermoreStrategy,
    });

    expect(await screen.findByTestId("market-data-page-title")).toBeInTheDocument();
    await waitFor(() => {
      expect(getMacroFoundation).toHaveBeenCalledTimes(1);
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
      expect(getLivermoreStrategy).toHaveBeenCalledTimes(1);
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
      expect(getLivermoreStrategy).toHaveBeenLastCalledWith({ asOfDate: "2026-03-01" });
    });
  });

  it("renders stale Livermore diagnostics from the backend contract", async () => {
    const base = createApiClient({ mode: "mock" });
    const getLivermoreStrategy = vi.fn(async () => ({
      result_meta: {
        trace_id: "tr_livermore_stale_test",
        basis: "analytical" as const,
        result_kind: "market_data.livermore",
        formal_use_allowed: false,
        source_version: "sv_livermore_stale_test",
        vendor_version: "vv_livermore_stale_test",
        rule_version: "rv_livermore_stale_test",
        cache_version: "cv_livermore_stale_test",
        quality_flag: "stale" as const,
        vendor_status: "ok" as const,
        fallback_mode: "latest_snapshot" as const,
        scenario_flag: false,
        generated_at: "2026-04-29T09:00:00Z",
      },
      result: {
        as_of_date: "2026-04-28",
        requested_as_of_date: "2026-04-29",
        strategy_name: "Livermore A股趋势门控",
        basis: "analytical" as const,
        market_gate: {
          state: "STALE" as const,
          exposure: 0.4,
          passed_conditions: 2,
          available_conditions: 2,
          required_conditions: 4,
          conditions: [],
        },
        rule_readiness: [],
        diagnostics: [
          {
            severity: "warning" as const,
            code: "LIVERMORE_BROAD_INDEX_STALE",
            message: "Latest CA.CSI300 input is marked stale and cannot be treated as current.",
            input_family: "broad_index_history",
          },
        ],
        data_gaps: [],
        supported_outputs: ["market_gate" as const],
        unsupported_outputs: [],
      },
    }));

    renderPage({
      ...base,
      getLivermoreStrategy,
    });

    expect(await screen.findByTestId("livermore-market-state")).toHaveTextContent("STALE");
    expect(screen.getByTestId("livermore-status-notes")).toHaveTextContent("请求日期 2026-04-29");
    expect(screen.getByTestId("livermore-status-notes")).toHaveTextContent("最新快照降级");
    expect(screen.getByTestId("livermore-diagnostics")).toHaveTextContent("LIVERMORE_BROAD_INDEX_STALE");
  });

  it("shows reserved-surface copy when Livermore fetch fails with backend reserved detail", async () => {
    const base = createApiClient({ mode: "mock" });
    const reservedDetail =
      "Livermore analytical surface is reserved by the current boundary and is not available in this wave.";
    const getLivermoreStrategy = vi.fn(async () => {
      throw new Error(reservedDetail);
    });

    renderPage({
      ...base,
      getLivermoreStrategy,
    });

    const panel = screen.getByTestId("market-data-livermore-panel");
    await waitFor(() => {
      expect(panel).toHaveTextContent("本轮不可用");
    });
    expect(panel).toHaveTextContent("接口保留");
    expect(panel).not.toHaveTextContent("Livermore 分析结果加载失败。");
  });

  it("renders the sixth-page market-data cockpit sections from the mockup", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    expect(await screen.findByTestId("market-data-page-title")).toHaveTextContent("市场数据");
    expect(screen.getByText("利率行情")).toBeInTheDocument();
    expect(screen.getByText("收益率曲线")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "信用利差" }));
    expect(
      within(await screen.findByTestId("market-data-linkage-spread-table")).getByText("信用利差"),
    ).toBeInTheDocument();
    expect(screen.getByText("资金市场")).toBeInTheDocument();
    expect(screen.getByText("国债期货")).toBeInTheDocument();
    expect(screen.getByText("同业存单")).toBeInTheDocument();
    expect(screen.getByText("债券成交明细（现券）")).toBeInTheDocument();
    expect(screen.getByText("信用债成交明细")).toBeInTheDocument();
    expect(screen.getByText("资讯与日历")).toBeInTheDocument();
  });

  it("loads supply-auction calendar events in the NewsAndCalendar calendar tab", async () => {
    const base = createApiClient({ mode: "mock" });
    const getResearchCalendarEvents = vi.fn(base.getResearchCalendarEvents);

    renderPage({
      ...base,
      getResearchCalendarEvents,
    });

    expect(await screen.findByTestId("market-data-page-title")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("tab", { name: "事件日历" }));
    expect(await screen.findByTestId("market-data-calendar-list")).toBeInTheDocument();
    expect(screen.getByText("国债净融资节奏")).toBeInTheDocument();
    expect(screen.getByText("政策性金融债招标")).toBeInTheDocument();
    await waitFor(() => {
      expect(getResearchCalendarEvents).toHaveBeenCalled();
    });
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
    expect(screen.getByTestId("market-data-ncd-live-meta")).toHaveTextContent("供应商状态=正常");
  });
});
