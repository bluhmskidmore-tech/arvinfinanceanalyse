import { useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { vi } from "vitest";

vi.mock("../lib/echarts", () => ({
  default: () => <div data-testid="market-data-echarts-stub" />,
}));

vi.mock("../app/jobs/polling", () => ({
  runPollingTask: vi.fn(),
}));

import { ApiClientProvider, createApiClient, type ApiClient } from "../api/client";
import { runPollingTask } from "../app/jobs/polling";
import type { ChoiceMacroLatestPoint, LivermoreModuleState, LivermoreOutputKey, ResultMeta } from "../api/contracts";
import { LiveResultMetaStrip } from "../features/market-data/components/LiveResultMetaStrip";
import MarketDataPage from "../features/market-data/pages/MarketDataPage";

const FORMAL_NCD_MATRIX_BLOCKED_STATUS = {
  status: "blocked",
  required_shape: "tenor_rating_matrix",
  current_proxy_basis: "shibor_funding_proxy",
  choice_status: "shibor_landed; formal_ncd_matrix_unconfirmed",
  tushare_status: "shibor_landed; formal_ncd_matrix_unconfirmed",
  missing_requirements: [
    "governed NCD tenor-rating source contract",
    "issuer/rating tenor matrix rows",
    "unit/date semantics and golden sample approval",
  ],
};

const LIVERMORE_OUTPUT_KEYS: LivermoreOutputKey[] = [
  "market_gate",
  "sector_rank",
  "stock_candidates",
  "mean_reversion_candidates",
  "factor_screen_candidates",
  "theme_breakout",
  "hybrid_fusion",
  "risk_exit",
];

function readyLivermoreModuleStates(asOfDate = "2026-04-29"): LivermoreModuleState[] {
  return LIVERMORE_OUTPUT_KEYS.map((key) => ({
    key,
    state: "ready",
    render_mode: "primary",
    source_date: asOfDate,
    lag_days: 0,
    threshold_days: null,
    reasons: [],
    evidence_scope: "primary",
    excludes_from_primary: false,
  }));
}

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

function renderPageWithQueryClient(client: ApiClient) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: { retry: false, staleTime: 0, refetchOnWindowFocus: false },
    },
  });

  const result = render(
    <MemoryRouter>
      <QueryClientProvider client={queryClient}>
        <ApiClientProvider client={client}>
          <MarketDataPage />
        </ApiClientProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );

  return { ...result, queryClient };
}

async function expandMarketDataLivermoreCollapse() {
  const collapse = await screen.findByTestId("market-data-livermore-collapse");
  const header = collapse.querySelector(".ant-collapse-header");
  if (!header) {
    throw new Error("livermore collapse header missing");
  }
  fireEvent.click(header);
}

async function expandMarketDataLinkageCollapse() {
  const collapse = await screen.findByTestId("market-data-linkage-collapse");
  const header = collapse.querySelector(".ant-collapse-header");
  if (!header) {
    throw new Error("linkage collapse header missing");
  }
  fireEvent.click(header);
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

  it("keeps the page stylesheet on tokens instead of raw color or shadow debt", () => {
    const css = readFileSync(join(process.cwd(), "src/features/market-data/pages/MarketDataPage.css"), "utf8");
    // 2026-06-23 visual upgrade introduces a paper/ink palette via CSS custom
    // properties and subtle rgba shadows. Only flag non-standard shadow patterns.
    const privateShadowLines = css
      .split(/\r?\n/)
      .filter((line) => /box-shadow\s*:/.test(line))
      .filter((line) => !/rgba\(/.test(line))
      .filter((line) => !/box-shadow\s*:\s*(?:none|var\()/.test(line));

    expect(privateShadowLines).toEqual([]);
    const externalMapStatusRule = css.match(/\.market-data-overview-external-map__rows b\s*{(?<body>[^}]*)}/)
      ?.groups?.body;
    expect(externalMapStatusRule).toContain("white-space: normal");
    expect(externalMapStatusRule).toContain("overflow: visible");
    expect(externalMapStatusRule).not.toContain("text-overflow: ellipsis");

    const endpointStatusRule = css.match(
      /\.market-data-overview-board\[data-variant="data-overview"\] \.market-data-overview-api-surface article b\s*{(?<body>[^}]*)}/,
    )?.groups?.body;
    expect(endpointStatusRule).toContain("white-space: normal");
    expect(endpointStatusRule).toContain("overflow: visible");
    expect(endpointStatusRule).not.toContain("text-overflow: ellipsis");
    const endpointNoteRule = css.match(
      /\.market-data-overview-board\[data-variant="data-overview"\] \.market-data-overview-api-surface article p\s*{(?<body>[^}]*)}/,
    )?.groups?.body;
    expect(endpointNoteRule).toContain("display: block");
  });

  it("renders the market data page as an institutional terminal cockpit", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    const kpiBand = await screen.findByTestId("market-data-kpi-band");

    const formalRatesBoard = screen.getByTestId("market-data-formal-rates-board");

    expect(screen.getByTestId("market-data-page")).toHaveAttribute("data-layout-rev", "2026-07-01-redesign");
    expect(screen.getByTestId("market-data-supply-evidence-rail")).toBeInTheDocument();
    expect(formalRatesBoard).toBeInTheDocument();
    expect(screen.queryByTestId("market-data-coverage-command")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-analyst-split")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-contract-hero")).not.toBeInTheDocument();
    const supplyEvidence = screen.getByTestId("market-data-supply-evidence-rail");
    expect(within(supplyEvidence).getByText("供给证据")).toBeInTheDocument();
    expect(within(supplyEvidence).getByText("下一步动作")).toBeInTheDocument();
    expect(within(formalRatesBoard).getByText("正式利率")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-formal-rates-table")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-formal-rates-curve")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-key-rate-list")).toBeInTheDocument();
    expect(kpiBand).toBeInTheDocument();
    expect(screen.getByTestId("market-data-coverage-bucket-analytical-usable")).toHaveTextContent("分析口径");
    expect(screen.getByTestId("market-data-coverage-bucket-proxy-only")).toHaveTextContent("代理数据");
    expect(screen.getByTestId("market-data-coverage-bucket-source-pending")).toHaveTextContent("未接入");
    expect(screen.queryByTestId("market-data-terminal-decision-rail")).not.toBeInTheDocument();
    expect(screen.getByTestId("market-workbench-nav")).toHaveAttribute("data-density", "compact");
  });

  it("renders external comparison stale and fallback lineage in map rows", async () => {
    const base = createApiClient({ mode: "mock" });
    const getChoiceMacroLatest = vi.fn(async () => ({
      result_meta: buildResultMeta({
        basis: "analytical",
        result_kind: "macro.choice.latest",
        formal_use_allowed: false,
        quality_flag: "stale",
        vendor_status: "vendor_stale",
      }),
      result: {
        read_target: "duckdb" as const,
        series: [
          buildMacroPoint({
            series_id: "CA.CSI300",
            series_name: "CSI300",
            trade_date: "2026-04-10",
            value_numeric: 4102.25,
            unit: "index",
            quality_flag: "stale",
          }),
          buildMacroPoint({
            series_id: "CA.COPPER",
            series_name: "Copper",
            trade_date: "2026-04-10",
            value_numeric: 81234.5,
            unit: "CNY/t",
          }),
        ],
      },
    }));
    const getTushareSupplement = vi.fn(async () => {
      const envelope = await base.getTushareSupplement();
      return {
        ...envelope,
        result_meta: buildResultMeta({
          basis: "analytical",
          result_kind: "market_data.tushare_supplement",
          formal_use_allowed: false,
          quality_flag: "stale",
          vendor_status: "vendor_stale",
          fallback_mode: "latest_snapshot",
        }),
      };
    });

    renderPage({
      ...base,
      getChoiceMacroLatest,
      getTushareSupplement,
    });

    await waitFor(() => {
      const evidenceRail = screen.getByTestId("market-data-macro-evidence-rail");
      expect(evidenceRail).toHaveTextContent("数据延迟");
      expect(evidenceRail).toHaveTextContent("来源需复核");
    });
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
        module_states: readyLivermoreModuleStates(),
      },
    }));
    const getMarketDataCoverageSummary = vi.fn(() => base.getMarketDataCoverageSummary());

    renderPage({
      ...base,
      getMacroFoundation,
      getChoiceMacroLatest,
      getLivermoreStrategy,
      getMarketDataCoverageSummary,
    });

    expect(await screen.findByTestId("market-data-hero")).toHaveTextContent("市场数据");
    expect(screen.getByTestId("market-data-page")).toHaveAttribute("data-layout-rev", "2026-07-01-redesign");
    expect(screen.getByTestId("market-data-page")).toHaveAttribute("data-view-mode", "default");
    await waitFor(() => {
      expect(getMarketDataCoverageSummary).toHaveBeenCalledTimes(1);
    });
    const statusStrip = screen.getByTestId("market-data-status-strip");
    expect(statusStrip).toBeInTheDocument();
    expect(screen.getByText(/数据日期/)).toBeInTheDocument();
    expect(statusStrip).not.toHaveTextContent("目录 3");
    expect(statusStrip).not.toHaveTextContent("稳定回收 1 / 2");
    expect(statusStrip).not.toHaveTextContent("口径 正式");
    expect(statusStrip).not.toHaveTextContent("口径 分析");
    expect(screen.getByText("利率曲线与宏观深度")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-rate-quote-card")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-macro-depth-card")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-rate-quote-view-toggle")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-macro-evidence-rail")).toHaveTextContent("正式利率");
    expect(screen.getByTestId("market-data-macro-evidence-rail")).toHaveTextContent("查看数据诊断");
    expect(screen.getByTestId("market-data-macro-evidence-rail")).toHaveTextContent("外汇分析");
    expect(screen.getByTestId("market-data-macro-evidence-rail")).toHaveTextContent("利弗莫尔");
    expect(screen.getByTestId("market-data-macro-evidence-rail")).toHaveTextContent("宏观债券联动");
    expect(screen.getByTestId("market-data-source-pending-deck")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-extended-terminal-collapse")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-source-pending-contract-note")).toHaveTextContent(
      "国债期货",
    );
    expect(screen.getByTestId("market-data-fx-formal-collapse")).toBeInTheDocument();
    expect(screen.queryByTestId("market-data-fx-formal-panel")).not.toBeInTheDocument();
    expect(screen.getByTestId("market-data-livermore-collapse")).toBeInTheDocument();
    expect(screen.queryByTestId("market-data-livermore-panel")).not.toBeInTheDocument();
    expect(screen.queryByText("宏观序列与分析观察")).not.toBeInTheDocument();
    expect(screen.getByTestId("market-data-supplementary-series-section")).toBeInTheDocument();
    expect(await screen.findByTestId("market-data-supplementary-panel")).toBeInTheDocument();
    expect(screen.queryByText("目录与结果元数据")).not.toBeInTheDocument();
    await expandMarketDataLivermoreCollapse();
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
    expect(screen.queryByTestId("market-data-missing-stable-section")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-result-meta")).not.toBeInTheDocument();
    const macroReadiness = await screen.findByTestId("market-data-macro-readiness");
    await waitFor(() => {
      expect(macroReadiness).toHaveTextContent("DR007");
      expect(macroReadiness).toHaveTextContent("T+48");
      expect(macroReadiness).toHaveTextContent("stale");
      expect(macroReadiness).toHaveTextContent("2026-04-10T09:05:00Z");
    });
    expect(macroReadiness).not.toHaveTextContent("Brent crude oil futures close");
    expect(macroReadiness).not.toHaveTextContent("USD/CNY spot 数据 T+");
    expect(screen.queryByTestId("market-data-overview-live-meta")).not.toBeInTheDocument();
    expect(statusStrip).toHaveTextContent("数据正常");
    expect(screen.getByTestId("market-data-macro-evidence-rail")).toHaveTextContent(
      "宏观最新：仅分析使用 / 部分缺失 / 暂不可用于正式决策",
    );
    expect(screen.queryByTestId("market-data-curve-live-meta")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-macro-section-meta")).not.toBeInTheDocument();
    expect(screen.queryByText("仅取最新降级")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-macro-section-meta")).not.toBeInTheDocument();
    expect(screen.getByText("外汇分析：中间价")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "结果元数据" })).not.toBeInTheDocument();

    expect(screen.getByText("收益率曲线")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-rate-quote-table")).toBeInTheDocument();
    const liquidityDeck = screen.getByTestId("market-data-liquidity-deck");
    expect(liquidityDeck).toContainElement(screen.getByTestId("market-data-money-market-card"));
    expect(liquidityDeck).toContainElement(screen.getByTestId("market-data-ncd-card"));
    expect(screen.getByTestId("market-data-money-market-table")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-ncd-view-toggle")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-rate-trend-chart")).toHaveTextContent("无法绘制走势图");

    await waitFor(() => {
      expect(getMacroFoundation).toHaveBeenCalledTimes(1);
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
      expect(getLivermoreStrategy).toHaveBeenCalledWith({
        asOfDate: expect.any(String),
      });
    });
  });

  it("keeps KPI band available in the hero section", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    const kpiBand = await screen.findByTestId("market-data-kpi-band");
    expect(kpiBand).toBeInTheDocument();
    const hero = screen.getByTestId("market-data-hero");
    expect(hero).toContainElement(kpiBand);
  });

  it("keeps FX formal status collapsed by default and renders rows after expand", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    expect(await screen.findByTestId("market-data-fx-formal-collapse")).toBeInTheDocument();
    expect(screen.queryByTestId("market-data-fx-formal-panel")).not.toBeInTheDocument();

    const collapse = screen.getByTestId("market-data-fx-formal-collapse");
    const header = collapse.querySelector(".ant-collapse-header");
    if (!header) {
      throw new Error("fx formal collapse header missing");
    }
    fireEvent.click(header);

    expect(await screen.findByTestId("market-data-fx-formal-panel")).toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("market-data-fx-formal-table")).toHaveTextContent("USD/CNY");
    });
    expect(screen.queryByTestId("market-data-fx-formal-meta")).not.toBeInTheDocument();
  });

  it("defers macro-bond linkage until spreads tab or linkage collapse is opened", async () => {
    const base = createApiClient({ mode: "mock" });
    const getMacroBondLinkageAnalysis = vi.fn((options: { reportDate: string }) =>
      base.getMacroBondLinkageAnalysis(options),
    );

    renderPage({
      ...base,
      getMacroBondLinkageAnalysis,
    });

    expect(await screen.findByTestId("market-data-hero")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-linkage-collapse")).toBeInTheDocument();
    expect(screen.queryByTestId("market-data-linkage-caveat")).not.toBeInTheDocument();
    expect(getMacroBondLinkageAnalysis).not.toHaveBeenCalled();

    fireEvent.click(await screen.findByTestId("market-data-macro-tab-trigger-spreads"));
    await waitFor(() => expect(getMacroBondLinkageAnalysis).toHaveBeenCalledTimes(1));
    expect(await screen.findByTestId("market-data-spreads-live-meta")).toHaveTextContent("联动读面");

    await expandMarketDataLinkageCollapse();
    expect(await screen.findByTestId("market-data-linkage-caveat")).toBeInTheDocument();
    expect(await screen.findByTestId("market-data-linkage-composite-score")).toHaveTextContent(
      "综合计算中流动性取反",
    );
    expect(screen.getByTestId("market-data-linkage-liquidity-score")).toHaveTextContent("进入综合分时取反");
  });

  it("keeps Livermore deferred until the collapse is expanded", async () => {
    const base = createApiClient({ mode: "mock" });
    const getLivermoreStrategy = vi.fn(() => base.getLivermoreStrategy());

    renderPage({
      ...base,
      getLivermoreStrategy,
    });

    expect(await screen.findByTestId("market-data-hero")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-livermore-collapse")).toBeInTheDocument();
    expect(screen.queryByTestId("market-data-livermore-panel")).not.toBeInTheDocument();
    expect(getLivermoreStrategy).not.toHaveBeenCalled();

    await expandMarketDataLivermoreCollapse();
    await waitFor(() => expect(getLivermoreStrategy).toHaveBeenCalledTimes(1));
    expect(await screen.findByTestId("market-data-livermore-panel")).toBeInTheDocument();
  });

  it("renders only the active macro depth tab panel", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    expect(await screen.findByTestId("market-data-hero")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-macro-tab-curve")).toBeInTheDocument();
    expect(screen.queryByTestId("market-data-macro-tab-spreads")).not.toBeInTheDocument();
    expect(screen.queryByTestId("market-data-macro-tab-linkage")).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("market-data-macro-tab-trigger-linkage"));
    const linkageTab = await screen.findByTestId("market-data-macro-tab-linkage");
    expect(linkageTab).toHaveTextContent("综合计算中流动性取反");
    expect(linkageTab).toHaveTextContent("进入综合分时取反");
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
        resolved_report_date: "2026-04-30",
        as_of_date: "2026-04-30",
        fallback_date: null,
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
    const getBondFuturesRankings = vi.fn(async () => ({
      result_meta: buildResultMeta({
        basis: "analytical" as const,
        result_kind: "market_data.bond_futures_rankings",
        formal_use_allowed: false,
        source_version: "sv_test_cffex_rank",
        vendor_version: "vv_test_tushare",
        rule_version: "rv_cffex_member_rank_choice_tushare_v1",
        cache_version: "cv_market_data_bond_futures_rankings_v1",
        source_surface: "market_data",
        tables_used: ["fact_cffex_member_rank_daily", "vw_cffex_member_rank_daily"],
        evidence_rows: 1,
      }),
      result: {
        read_target: "duckdb" as const,
        as_of_date: "2026-06-11",
        requested_trade_date: null,
        contract: "T.CFE",
        rows: [
          {
            trade_date: "2026-06-11",
            contract: "T.CFE",
            product_code: "T",
            exchange: "CFFEX",
            member_name: "中信期货",
            source_vendor: "tushare",
            source_row_no: 1,
            volume: 12345,
            volume_change: 101,
            long_holding: 23456,
            long_change: 202,
            short_holding: 21000,
            short_change: -50,
            source_version: "sv_test_cffex_rank",
            vendor_version: "vv_test_tushare",
            rule_version: "rv_cffex_member_rank_choice_tushare_v1",
          },
        ],
        warnings: [],
      },
    }));
    const getMarketDataCoverageSummary = vi.fn(async () => {
      const envelope = await base.getMarketDataCoverageSummary();
      return {
        ...envelope,
        result: {
          ...envelope.result,
          headline: {
            ...envelope.result.headline,
            source_pending_count: 2,
          },
          sections: envelope.result.sections.map((section) =>
            section.key === "bond_futures"
              ? {
                  ...section,
                  status: "ready" as const,
                  row_count: 1,
                  source_pending: false,
                  vendor_status: "ok" as const,
                }
              : section,
          ),
        },
      };
    });

    renderPage({
      ...base,
      getMarketDataRates,
      getChoiceMacroLatest,
      getBondFuturesRankings,
      getMarketDataCoverageSummary,
    } as ApiClient);

    const ticker = await screen.findByTestId("market-data-terminal-ticker");
    expect(ticker).toHaveTextContent("10年国债");
    expect(ticker).toHaveTextContent("1.94%");
    expect(ticker).toHaveTextContent("-1bp");
    expect(screen.getByTestId("market-data-terminal-kpi-cgb10y")).toHaveTextContent("1.94%");
    expect(screen.getByTestId("market-data-kpi-band")).toBeInTheDocument();
    expect(screen.queryByTestId("market-data-terminal-kpi-strip")).not.toBeInTheDocument();

    const rateTable = await screen.findByTestId("market-data-rate-quote-table");
    expect(within(rateTable).getAllByText("10Y").length).toBeGreaterThan(0);
    expect(rateTable).toHaveTextContent("1.94%");
    expect(rateTable).toHaveTextContent("-1bp");
    expect(rateTable).not.toHaveTextContent("4,856");
    const sharedMeta = screen.getByTestId("market-data-workbench-shared-meta");
    expect(sharedMeta).toHaveTextContent("口径摘要 正式");
    expect(sharedMeta).not.toHaveTextContent("供应商");
    expect(screen.queryByTestId("market-data-overview-live-meta")).not.toBeInTheDocument();

    const evidenceRail = screen.getByTestId("market-data-macro-evidence-rail");
    expect(evidenceRail).toHaveTextContent("正式利率");
    expect(evidenceRail).toHaveTextContent("正式利率：正式可用 / 数据正常 / 可正式使用");
    expect(evidenceRail).not.toHaveTextContent("formal_use_allowed");
    expect(evidenceRail).not.toHaveTextContent("sv_formal_rates_terminal_test");
    expect(evidenceRail).toHaveTextContent("外汇分析");
    expect(evidenceRail).toHaveTextContent("利弗莫尔");
    expect(evidenceRail).toHaveTextContent("宏观债券联动");
    expect(screen.getByTestId("market-data-source-pending-summary")).toHaveTextContent(
      "未接入",
    );

    const moneyTable = screen.getByTestId("market-data-money-market-table");
    expect(moneyTable).toHaveTextContent("公开市场7天逆回购利率");
    expect(moneyTable).toHaveTextContent("CA.DR007");
    expect(moneyTable).toHaveTextContent("-0.6bp");
    expect(moneyTable).not.toHaveTextContent("24,331");

    const bondFuturesTable = screen.getByTestId("market-data-bond-futures-table");
    expect(bondFuturesTable).toHaveTextContent("中信期货");
    expect(bondFuturesTable).toHaveTextContent("T.CFE");
    expect(bondFuturesTable).toHaveTextContent("23,456");
    expect(screen.getByTestId("market-data-source-pending-summary")).toHaveTextContent("未接入 2");
    expect(screen.queryByTestId("market-data-bond-futures-source-pending")).not.toBeInTheDocument();
    expect(screen.getByTestId("market-data-bond-trades-source-pending")).toHaveTextContent("未接入");
    expect(screen.getByTestId("market-data-credit-trades-source-pending")).toHaveTextContent("未接入");

    await waitFor(() => {
      expect(getMarketDataRates).toHaveBeenCalledTimes(1);
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
      expect(getBondFuturesRankings).toHaveBeenCalledTimes(1);
      expect(getMarketDataCoverageSummary).toHaveBeenCalledTimes(1);
    });
  });

  it("surfaces a visible warning when formal-labeled rates are not allowed for formal use", async () => {
    const base = createApiClient({ mode: "mock" });
    const rateSeries = [
      buildMacroPoint({
        series_id: "EMM00166466",
        series_name: "中债国债到期收益率:10年",
        value_numeric: 1.94,
        latest_change: -0.012,
      }),
    ];
    const getMarketDataRates = vi.fn(async () => ({
      result_meta: buildResultMeta({
        trace_id: "tr_formal_blocked_rates_test",
        basis: "formal",
        formal_use_allowed: false,
        source_version: "sv_candidate_rates_test",
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
    await waitFor(() => {
      expect(within(rateTable).getByText("1.94%")).toBeInTheDocument();
    });

    const sharedMeta = await screen.findByTestId("market-data-workbench-shared-meta");
    expect(sharedMeta).toHaveTextContent("口径摘要 暂不可正式使用");
    expect(sharedMeta).toHaveTextContent("禁止作为正式口径");
    expect(screen.queryByTestId("market-data-overview-live-meta")).not.toBeInTheDocument();
    const statusStrip = screen.getByTestId("market-data-status-strip");
    expect(statusStrip).toHaveTextContent("仅分析使用");
    expect(statusStrip).toHaveTextContent("暂不可正式使用");
    expect(screen.getByTestId("market-data-macro-evidence-rail")).toHaveTextContent("暂不可用于正式决策");
  });

  it("labels mock basis and falls back from blank resolved report date", () => {
    render(
      <LiveResultMetaStrip
        lead="测试读面"
        testId="market-data-live-meta-unit"
        meta={buildResultMeta({
          basis: "mock",
          formal_use_allowed: false,
          resolved_report_date: "",
          requested_report_date: "2026-04-30",
        })}
      />,
    );

    const meta = screen.getByTestId("market-data-live-meta-unit");
    expect(meta).toHaveTextContent("口径=模拟口径");
    expect(meta).toHaveTextContent("正式可用=否");
    expect(meta).toHaveTextContent("报告日=2026-04-30");
  });

  it("renders explicit empty states for missing rate and money sources instead of demo rows", async () => {
    const base = createApiClient({ mode: "mock" });
    const getMarketDataRates = vi.fn(async () => ({
      result_meta: buildResultMeta({
        trace_id: "tr_empty_terminal_test",
        source_version: "sv_empty_terminal_test",
      }),
      result: {
        read_target: "duckdb" as const,
        series: [],
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
        series: [],
      },
    }));

    renderPage({
      ...base,
      getMarketDataRates,
      getChoiceMacroLatest,
    });

    expect(await screen.findByTestId("market-data-rate-quotes-empty")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-rate-quotes-empty")).toHaveTextContent(/\S/);
    expect(screen.getByTestId("market-data-money-market-empty")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-money-market-empty")).toHaveTextContent(/\S/);
    expect(screen.queryByText("EMM00166466")).not.toBeInTheDocument();
    expect(screen.queryByText("公开市场7天逆回购利率")).not.toBeInTheDocument();
    expect(screen.queryByText("4,856")).not.toBeInTheDocument();
    expect(screen.queryByText("24,331")).not.toBeInTheDocument();

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
        diagnostics: [],
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
        supported_outputs: [
          "market_gate" as const,
          "sector_rank" as const,
          "stock_candidates" as const,
          "mean_reversion_candidates" as const,
          "factor_screen_candidates" as const,
          "theme_breakout" as const,
          "risk_exit" as const,
        ],
        unsupported_outputs: [],
        module_states: readyLivermoreModuleStates(),
        sector_rank: {
          as_of_date: "2026-04-29",
          formula_version: "rv_livermore_sector_strength_observation_v1",
          is_provisional: false,
          formula_status: "signed_off",
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
        mean_reversion_candidates: {
          as_of_date: "2026-04-29",
          formula_version: "rv_mean_reversion_candidates_v2",
          market_state: "WARM" as const,
          input_stock_count: 4,
          candidate_count: 1,
          excluded_stock_count: 3,
          insufficient_history_count: 0,
          items: [
            {
              rank: 1,
              stock_code: "000003.SZ",
              stock_name: "Gamma",
              sector_code: "801003",
              sector_name: "医药",
              close: 8.2,
              drawdown_20d: -0.18,
              drawdown_60d: -0.28,
              ma5: 8,
              ma10: 8.1,
              close_strength: 0.62,
              vol_ratio: 1.8,
              score: 0.74,
            },
          ],
        },
        factor_screen_candidates: {
          as_of_date: "2026-04-29",
          formula_version: "rv_factor_screen_candidates_v1",
          market_state: "WARM" as const,
          input_stock_count: 4,
          candidate_count: 1,
          coverage_note: "因子数据覆盖 4/4 只",
          items: [
            {
              rank: 1,
              stock_code: "000004.SZ",
              stock_name: "Factor Delta",
              sector_code: "801004",
              sector_name: "电子",
              industry: "电子",
              score: 0.8123,
              pe: 12.4,
              pb: 1.6,
              roe: 0.143,
              gross_margin: 0.32,
              three_month_return: 0.056,
              twelve_month_return: 0.184,
              dividend_yield: 0.021,
            },
          ],
        },
        theme_breakout: {
          as_of_date: "2026-04-29",
          formula_version: "rv_livermore_theme_breakout_proxy_v1",
          is_proxy: true,
          theme_count: 1,
          items: [
            {
              rank: 1,
              as_of_date: "2026-04-29",
              theme_key: "ai_proxy",
              theme_name: "AI proxy",
              parent_sector_code: "801001",
              parent_sector_name: "AI",
              parent_sector_rank: 1,
              member_count: 3,
              advance_count: 3,
              advance_ratio: 1,
              strong_stock_count: 3,
              limit_stock_count: 1,
              avg_pctchange: 8.35,
              avg_turn: 4.2,
              avg_amplitude: 6.1,
              observation_only: true,
              reason: "Observation-only proxy cluster.",
              items: [],
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

    await expandMarketDataLivermoreCollapse();
    expect(await screen.findByTestId("livermore-market-state")).toHaveTextContent("WARM");
    expect(screen.getByTestId("market-data-livermore-panel")).toHaveTextContent("801001");
    expect(screen.getByTestId("market-data-livermore-panel")).toHaveTextContent("000001.SZ");
    expect(screen.getByTestId("market-data-livermore-panel")).toHaveTextContent(
      "rv_livermore_stock_candidates_bundle_v1",
    );
    expect(screen.getByTestId("market-data-livermore-panel")).toHaveTextContent(
      "rv_livermore_risk_exit_ema10_mvp_v1",
    );
    expect(screen.getByTestId("livermore-mean-reversion-candidates")).toHaveTextContent("Gamma");
    expect(screen.getByTestId("livermore-factor-screen-candidates")).toHaveTextContent("Factor Delta");
    expect(screen.getByTestId("livermore-theme-breakout")).toHaveTextContent("AI proxy");
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
    await waitFor(() => {
      expect(screen.getAllByTestId("market-data-echarts-stub").length).toBeGreaterThan(0);
    });

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

    const curveError = await screen.findByTestId("market-data-rate-trend-chart");
    await waitFor(() => {
      expect(curveError).toHaveTextContent("图表数据载入失败");
    });
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
      expect(screen.getByTestId("market-data-fx-tier-rail")).toHaveTextContent("2 组");
      expect(getFxAnalytical).toHaveBeenCalledTimes(1);
    });

    expect(screen.getByText("外汇分析：中间价")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-fx-group-card-middle_rate")).toBeInTheDocument();
    expect(screen.queryByTestId("market-data-fx-section-meta")).not.toBeInTheDocument();
  });

  it("renders macro-bond linkage as an analytical estimate with explicit tenor slots", async () => {
    const client = createApiClient({ mode: "mock" });

    renderPage(client);

    fireEvent.click(await screen.findByTestId("market-data-macro-tab-trigger-spreads"));
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
    expect(screen.getByTestId("market-data-macro-spread-slot-5Y")).toHaveTextContent(
      "10Y treasury yield",
    );
    expect(screen.getByTestId("market-data-macro-spread-slot-3Y")).toHaveTextContent(
      "—",
    );
    expect(screen.getByTestId("market-data-macro-spread-slot-10Y")).toHaveTextContent(
      "—",
    );
    expect(screen.getByTestId("market-data-linkage-spreads-audit")).toBeInTheDocument();
    expect(screen.getByTestId("market-data-linkage-spreads-audit-count")).toHaveTextContent(
      "已覆盖 1 / 3 个期限槽位",
    );
    expect(screen.getByTestId("market-data-linkage-spreads-audit-slot-5Y")).toHaveTextContent(
      "10Y treasury yield",
    );
    expect(screen.getByTestId("market-data-linkage-spreads-audit-slot-3Y")).toHaveTextContent(
      "无数据",
    );
    expect(screen.getByTestId("market-data-linkage-spreads-audit-slot-10Y")).toHaveTextContent(
      "无数据",
    );
    expect(screen.queryByTestId("market-data-linkage-spread-slot-5Y")).not.toBeInTheDocument();
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
    const getNcdFundingProxy = vi.fn(() => base.getNcdFundingProxy());
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
      getNcdFundingProxy,
      getMacroBondLinkageAnalysis,
      refreshChoiceMacro,
      getChoiceMacroRefreshStatus,
    });

    expect(await screen.findByTestId("market-data-hero")).toBeInTheDocument();
    await waitFor(() => {
      expect(getMacroFoundation).toHaveBeenCalledTimes(1);
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
      expect(getFxAnalytical).toHaveBeenCalledTimes(1);
      expect(getNcdFundingProxy).toHaveBeenCalledTimes(1);
      expect(getMacroBondLinkageAnalysis).not.toHaveBeenCalled();
    });

    fireEvent.click(screen.getByTestId("market-data-refresh-btn"));

    await waitFor(() => {
      expect(refreshChoiceMacro).toHaveBeenCalledWith(30);
      expect(screen.getByTestId("market-data-refresh-btn")).toBeDisabled();
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
      expect(screen.getByTestId("market-data-refresh-btn")).not.toBeDisabled();
    });

    await waitFor(() => {
      expect(getMacroFoundation).toHaveBeenCalledTimes(2);
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(2);
      expect(getFxAnalytical).toHaveBeenCalledTimes(2);
      expect(getNcdFundingProxy).toHaveBeenCalledTimes(2);
      expect(getMacroBondLinkageAnalysis).toHaveBeenCalledTimes(1);
    });
  });

  it("registers section-level refresh policy without pulling stable/date-slice sections into fallback polling", async () => {
    const base = createApiClient({ mode: "mock" });
    const getMacroFoundation = vi.fn(() => base.getMacroFoundation());
    const getChoiceMacroLatest = vi.fn(async () => ({
      result_meta: buildResultMeta({
        basis: "analytical",
        result_kind: "macro.choice.latest",
        formal_use_allowed: false,
        quality_flag: "warning",
        vendor_status: "vendor_stale",
        fallback_mode: "latest_snapshot",
      }),
      result: {
        read_target: "duckdb" as const,
        series: [
          buildMacroPoint({
            series_id: "M002",
            series_name: "DR007",
            refresh_tier: "fallback",
            fetch_mode: "latest",
            quality_flag: "warning",
          }),
        ],
      },
    }));
    const getMarketDataRates = vi.fn(async () => ({
      result_meta: buildResultMeta({
        result_kind: "market_data.rates",
        vendor_status: "ok",
        fallback_mode: "none",
        quality_flag: "ok",
      }),
      result: {
        read_target: "duckdb" as const,
        series: [
          buildMacroPoint({
            series_id: "M001",
            series_name: "Open Market 7D Reverse Repo",
            refresh_tier: "stable",
            fetch_mode: "date_slice",
            quality_flag: "ok",
          }),
        ],
      },
    }));
    const getFxAnalytical = vi.fn(async () => ({
      result_meta: buildResultMeta({
        basis: "analytical",
        result_kind: "fx.analytical.groups",
        formal_use_allowed: false,
      }),
      result: {
        read_target: "duckdb" as const,
        groups: [],
      },
    }));
    const getNcdFundingProxy = vi.fn(async () => ({
      result_meta: buildResultMeta({
        basis: "analytical",
        result_kind: "market_data.ncd_proxy",
        formal_use_allowed: false,
      }),
      result: {
        as_of_date: "2026-05-21",
        proxy_label: "test ncd proxy",
        is_actual_ncd_matrix: false,
        formal_ncd_matrix_status: FORMAL_NCD_MATRIX_BLOCKED_STATUS,
        rows: [],
        warnings: [],
      },
    }));
    const getMacroBondLinkageAnalysis = vi.fn(async (options: { reportDate: string }) => ({
      result_meta: buildResultMeta({
        basis: "analytical",
        result_kind: "macro_bond_linkage.analysis",
        formal_use_allowed: false,
        quality_flag: "warning",
      }),
      result: {
        report_date: options.reportDate,
        environment_score: {},
        top_correlations: [],
        portfolio_impact: {},
        warnings: [],
        computed_at: "2026-05-21T09:00:00Z",
      },
    }));
    const getLivermoreStrategy = vi.fn(async (options?: { asOfDate?: string }) => ({
      result_meta: buildResultMeta({
        basis: "analytical",
        result_kind: "market_data.livermore",
        formal_use_allowed: false,
      }),
      result: {
        as_of_date: options?.asOfDate ?? "2026-05-21",
        requested_as_of_date: options?.asOfDate ?? null,
        strategy_name: "test strategy",
        basis: "analytical" as const,
        market_gate: {
          state: "OFF" as const,
          exposure: 0,
          passed_conditions: 0,
          available_conditions: 0,
          required_conditions: 4,
          conditions: [],
        },
        rule_readiness: [],
        diagnostics: [],
        data_gaps: [],
        supported_outputs: ["market_gate" as const],
        unsupported_outputs: [],
        module_states: readyLivermoreModuleStates(),
        warnings: [],
      },
    }));

    const { queryClient } = renderPageWithQueryClient({
      ...base,
      getMacroFoundation,
      getChoiceMacroLatest,
      getMarketDataRates,
      getFxAnalytical,
      getNcdFundingProxy,
      getMacroBondLinkageAnalysis,
      getLivermoreStrategy,
    });

    expect(await screen.findByTestId("market-data-hero")).toBeInTheDocument();
    await waitFor(() => {
      expect(getMacroFoundation).toHaveBeenCalledTimes(1);
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
      expect(getMarketDataRates).toHaveBeenCalledTimes(1);
    });

    const macroLatest = queryClient.getQueryCache().find({
      queryKey: ["market-data", "choice-macro-latest", "mock"],
      exact: true,
    });
    const formalRates = queryClient.getQueryCache().find({
      queryKey: ["market-data", "formal-rates", "mock"],
      exact: false,
    });
    const catalog = queryClient.getQueryCache().find({
      queryKey: ["market-data", "macro-foundation", "mock"],
      exact: true,
    });

    expect(
      typeof macroLatest?.observers[0]?.options.refetchInterval === "function"
        ? macroLatest.observers[0].options.refetchInterval(macroLatest)
        : macroLatest?.observers[0]?.options.refetchInterval,
    ).toBe(3 * 60 * 1000);
    expect(
      typeof formalRates?.observers[0]?.options.refetchInterval === "function"
        ? formalRates.observers[0].options.refetchInterval(formalRates)
        : formalRates?.observers[0]?.options.refetchInterval,
    ).toBe(false);
    expect(
      typeof catalog?.observers[0]?.options.refetchInterval === "function"
        ? catalog.observers[0].options.refetchInterval(catalog)
        : catalog?.observers[0]?.options.refetchInterval,
    ).toBe(false);
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

    expect(await screen.findByTestId("market-data-hero")).toBeInTheDocument();
    await waitFor(() => {
      expect(getMacroFoundation).toHaveBeenCalledTimes(1);
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
    });

    fireEvent.change(screen.getByTestId("market-data-date-picker"), { target: { value: "2026-03-01" } });
    expect(screen.getByTestId("market-data-date-picker")).toHaveValue("2026-03-01");

    const curveFilter = screen.getByTestId("market-data-curve-filter");
    const curveSelector = curveFilter.querySelector(".ant-select-selector");
    if (!curveSelector) {
      throw new Error("curve select shell not found");
    }
    fireEvent.mouseDown(curveSelector);
    const curveOption = (await screen.findAllByText("国债")).at(-1);
    if (!curveOption) {
      throw new Error("curve option not found");
    }
    fireEvent.click(curveOption);
    await waitFor(() => {
      expect(screen.getByTestId("market-data-rate-curve-lock")).toHaveTextContent("国债曲线");
    });

    const sourceFilter = screen.getByTestId("market-data-source-filter");
    const sourceSelector = sourceFilter.querySelector(".ant-select-selector");
    if (!sourceSelector) {
      throw new Error("source select shell not found");
    }
    fireEvent.mouseDown(sourceSelector);
    const sourceOption = (await screen.findAllByText("Choice")).at(-1);
    if (!sourceOption) {
      throw new Error("source option not found");
    }
    fireEvent.click(sourceOption);
    await waitFor(() => {
      expect(sourceFilter).toHaveTextContent("Choice");
    });

    fireEvent.click(screen.getByTestId("market-data-macro-tab-trigger-spreads"));
    await waitFor(() => {
      expect(screen.getByTestId("market-data-macro-tab-spreads")).toBeInTheDocument();
      expect(screen.getByRole("tab", { name: "信用利差" })).toHaveAttribute("aria-selected", "true");
    });

    await waitFor(() => {
      expect(getMacroFoundation).toHaveBeenCalledTimes(1);
      expect(getChoiceMacroLatest).toHaveBeenCalledTimes(1);
      expect(getLivermoreStrategy).toHaveBeenCalledTimes(1);
      expect(getLivermoreStrategy).toHaveBeenCalledWith({ asOfDate: "2026-03-01" });
    });
  });

  it("keeps the compact ticker status date tied to the formal rates result date instead of the selected watch date", async () => {
    const base = createApiClient({ mode: "mock" });
    const getMarketDataRates = vi.fn(async () => ({
      result_meta: buildResultMeta({
        trace_id: "tr_formal_rates_status_date_test",
        resolved_report_date: "2026-04-30",
        as_of_date: "2026-04-30",
        fallback_date: null,
      }),
      result: {
        read_target: "duckdb" as const,
        series: [
          buildMacroPoint({
            series_id: "EMM00166466",
            series_name: "中债国债到期收益率:10年",
            trade_date: "2026-04-30",
            value_numeric: 1.94,
          }),
          buildMacroPoint({
            series_id: "EMM00166502",
            series_name: "中债政策性金融债到期收益率(国开行)10年",
            trade_date: "2026-04-30",
            value_numeric: 2.05,
          }),
        ],
      },
    }));

    renderPage({
      ...base,
      getMarketDataRates,
    });

    expect(await screen.findByTestId("market-data-hero")).toBeInTheDocument();
    await waitFor(() => {
      expect(getMarketDataRates).toHaveBeenCalledTimes(1);
    });

    fireEvent.change(screen.getByTestId("market-data-date-picker"), { target: { value: "2026-03-01" } });
    expect(screen.getByTestId("market-data-date-picker")).toHaveValue("2026-03-01");

    await waitFor(() => {
      expect(screen.getByTestId("market-data-terminal-ticker-status")).toHaveTextContent("2026-04-30");
      expect(screen.getByTestId("market-data-terminal-ticker-status")).not.toHaveTextContent("2026-03-01");
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
        module_states: readyLivermoreModuleStates("2026-04-29"),
      },
    }));

    renderPage({
      ...base,
      getLivermoreStrategy,
    });

    await expandMarketDataLivermoreCollapse();
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

    await expandMarketDataLivermoreCollapse();
    const panel = await screen.findByTestId("market-data-livermore-panel");
    await waitFor(() => {
      expect(panel).toHaveTextContent("本轮不可用");
    });
    expect(panel).toHaveTextContent("接口保留");
    expect(panel).not.toHaveTextContent("Livermore 分析结果加载失败。");
  });

  it("renders the sixth-page market-data cockpit sections from the mockup", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    expect(await screen.findByTestId("market-data-hero")).toHaveTextContent("市场数据");
    expect(screen.getByText("利率行情")).toBeInTheDocument();
    expect(screen.getByText("收益率曲线")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("market-data-macro-tab-trigger-spreads"));
    expect(
      within(await screen.findByTestId("market-data-linkage-spread-table")).getByText("信用利差"),
    ).toBeInTheDocument();
    expect(screen.getByText("资金市场")).toBeInTheDocument();
    expect(screen.getAllByText("国债期货").length).toBeGreaterThan(0);
    expect(screen.getByText("同业存单")).toBeInTheDocument();
    expect(screen.getByText("债券成交明细（现券）")).toBeInTheDocument();
    expect(screen.getByText("信用债成交明细")).toBeInTheDocument();
  });

  it("loads supply-auction calendar events into the first-screen event tape", async () => {
    const base = createApiClient({ mode: "mock" });
    const getResearchCalendarEvents = vi.fn(base.getResearchCalendarEvents);

    renderPage({
      ...base,
      getResearchCalendarEvents,
    });

    expect(await screen.findByTestId("market-data-hero")).toBeInTheDocument();
    expect(screen.queryByRole("tab", { name: "事件日历", hidden: true })).not.toBeInTheDocument();
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
        as_of_date: "2026-06-09",
        proxy_label: "Choice/Tushare Shibor funding proxy",
        is_actual_ncd_matrix: false,
        formal_ncd_matrix_status: FORMAL_NCD_MATRIX_BLOCKED_STATUS,
        rows: [
          {
            row_key: "shibor_fixing",
            label: "Shibor fixing",
            "1M": 1.427,
            "3M": 1.4144,
            "6M": 1.4299,
            "9M": 1.45,
            "1Y": 1.43,
            quote_count: null,
          },
        ],
        warnings: [
          "Using landed Choice Shibor with Tushare fallback for 9M; fallback date 2026-05-28; quote medians unavailable.",
          "Proxy only; not actual NCD issuance matrix.",
        ],
      },
    }));

    const { queryClient } = renderPageWithQueryClient({
      ...base,
      getNcdFundingProxy,
    });

    const ncdPanel = await screen.findByTestId("market-data-ncd-matrix");
    await waitFor(() => {
      expect(getNcdFundingProxy).toHaveBeenCalled();
      expect(
        queryClient.getQueryState(["market-data", "ncd-funding-proxy", "mock"])?.status,
      ).toBe("success");
    });
    await waitFor(() => {
      expect(within(ncdPanel).getByText(/Choice\/Tushare Shibor funding proxy/)).toBeInTheDocument();
    });
    expect(within(ncdPanel).getByText("Shibor fixing")).toBeInTheDocument();
    expect(screen.queryByText("Quote median")).not.toBeInTheDocument();
    expect(
      await screen.findByText(/报价中位数不可用|不是真实存单发行矩阵/),
    ).toBeInTheDocument();
    expect(await screen.findByText("1.427")).toBeInTheDocument();
    expect(await screen.findByText(/回退日期 2026-05-28/)).toBeInTheDocument();
    const evidenceRail = screen.getByTestId("market-data-macro-evidence-rail");
    expect(evidenceRail).toHaveTextContent("存单代理");
    expect(evidenceRail).toHaveTextContent("仅分析使用");
    expect(evidenceRail).not.toHaveTextContent("sv_ncd_proxy_test");
    expect(screen.queryByTestId("market-data-ncd-live-meta")).not.toBeInTheDocument();
  });

  it("exposes chart view toggles for rate quotes and ncd proxy", async () => {
    renderPage(createApiClient({ mode: "mock" }));

    expect(await screen.findByTestId("market-data-rate-quote-view-toggle")).toBeInTheDocument();
    expect(await screen.findByTestId("market-data-ncd-view-toggle")).toBeInTheDocument();
    expect(await screen.findByTestId("market-data-term-structure-chart")).toBeInTheDocument();
    expect(await screen.findByTestId("market-data-ncd-heatmap")).toBeInTheDocument();
    expect(await screen.findByTestId("market-data-rate-trend-chart")).toBeInTheDocument();
  });
});
