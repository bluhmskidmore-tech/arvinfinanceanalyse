import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { CSSProperties, FormEvent, HTMLAttributes } from "react";

import { createApiClient, type ApiClient } from "../api/client";
import type {
  ApiEnvelope,
  ConfluenceReplayStatus,
  LivermoreCandidateHistoryPayload,
  LivermoreCandidateHistoryPortfolioBacktestPayload,
  LivermoreCycleProxyBacktestPayload,
  LivermoreOutputKey,
  LivermoreSignalConfluencePayload,
  LivermoreStrategyOptimizationPayload,
  LivermoreStrategyScorePayload,
  LivermoreStrategyPayload,
  StockAnalysisWorkbenchPayload,
} from "../api/contracts";
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import { StockAnalysisCandidateComparison } from "../features/stock-analysis/components/StockAnalysisCandidateComparison";
import { StockAnalysisCandidateLedgerTable } from "../features/stock-analysis/components/StockAnalysisCandidateLedgerTable";
import { StockAnalysisReviewLedgerFirstScreen } from "../features/stock-analysis/components/StockAnalysisReviewLedgerFirstScreen";
import type { StockCandidateReviewQueueItem, WorkbenchDataDigest } from "../features/stock-analysis/lib/stockAnalysisPageModel";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

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

type TestLivermoreModuleState = {
  key: LivermoreOutputKey;
  state: "ready" | "degraded" | "partial" | "blocked" | "unsupported";
  render_mode: "primary" | "evidence_only" | "hidden";
  source_date: string | null;
  lag_days: number | null;
  threshold_days: number | null;
  reasons: string[];
  evidence_scope: "primary" | "detail" | "detail_only" | "none";
  excludes_from_primary: boolean;
};

type TestLivermoreStrategyPayload = Omit<LivermoreStrategyPayload, "module_states"> & {
  module_states: TestLivermoreModuleState[];
};

type TestLivermoreStrategyOverrides = Omit<Partial<LivermoreStrategyPayload>, "module_states"> & {
  module_states?: TestLivermoreModuleState[];
};

function readyModuleStates(asOfDate = "2026-04-29"): TestLivermoreModuleState[] {
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

const STOCK_ANALYSIS_CSS_PATH = resolve(
  process.cwd(),
  "src/features/stock-analysis/pages/StockAnalysisPage.css",
);
const STOCK_ANALYSIS_PAGE_PATH = resolve(
  process.cwd(),
  "src/features/stock-analysis/pages/StockAnalysisPage.tsx",
);
const STOCK_ANALYSIS_CANDIDATE_COMPARISON_CSS_PATH = resolve(
  process.cwd(),
  "src/features/stock-analysis/components/StockAnalysisCandidateComparison.css",
);
const STOCK_ANALYSIS_CANDIDATE_COMPARISON_PATH = resolve(
  process.cwd(),
  "src/features/stock-analysis/components/StockAnalysisCandidateComparison.tsx",
);
const STOCK_ANALYSIS_STRATEGY_LENS_SECTION_PATH = resolve(
  process.cwd(),
  "src/features/stock-analysis/components/StockAnalysisStrategyLensSection.tsx",
);
const STOCK_ANALYSIS_OBSERVATION_PREVIEW_PATH = resolve(
  process.cwd(),
  "src/features/stock-analysis/components/StockAnalysisObservationPreview.tsx",
);
const EQUITY_KPI_CARD_CSS_PATH = resolve(
  process.cwd(),
  "src/features/stock-analysis/components/EquityKpiCard.module.css",
);

vi.mock("../components/charts/BaseChart", () => ({
  BaseChart: function MockBaseChart() {
    return <div data-testid="stock-detail-chart-canvas-stub" />;
  },
}));

vi.mock("../lib/echarts", () => ({
  default: function MockReactECharts({
    className,
    option,
    style,
  }: {
    className?: string;
    option?: unknown;
    style?: CSSProperties;
  }) {
    return (
      <div
        className={className}
        data-testid="stock-analysis-echarts-stub"
        data-option={JSON.stringify(option ?? null)}
        style={style}
      />
    );
  },
}));

vi.mock("@ant-design/icons", () => {
  function MockAntIcon({ "aria-hidden": ariaHidden = true, ...props }: HTMLAttributes<HTMLSpanElement>) {
    return <span aria-hidden={ariaHidden} {...props} />;
  }

  return {
    AlertOutlined: MockAntIcon,
    AppstoreOutlined: MockAntIcon,
    BarChartOutlined: MockAntIcon,
    CheckCircleOutlined: MockAntIcon,
    ClockCircleOutlined: MockAntIcon,
    DatabaseOutlined: MockAntIcon,
    DownOutlined: MockAntIcon,
    FireOutlined: MockAntIcon,
    LineChartOutlined: MockAntIcon,
    ReloadOutlined: MockAntIcon,
    SafetyCertificateOutlined: MockAntIcon,
    SearchOutlined: MockAntIcon,
    StockOutlined: MockAntIcon,
    ThunderboltOutlined: MockAntIcon,
    UpOutlined: MockAntIcon,
  };
});

vi.mock("../features/agent/AgentPanel", () => {
  type MockAgentPanelProps = {
    pageId: string;
    reportDate?: string | null;
    currentFilters?: Record<string, unknown>;
    defaultFilters?: Record<string, unknown>;
    selectedRows?: Array<Record<string, unknown>>;
    contextNote?: string | null;
  };

  return {
    AgentPanel: function MockAgentPanel({
      pageId,
      reportDate = null,
      currentFilters = {},
      defaultFilters = {},
      selectedRows = [],
      contextNote = null,
    }: MockAgentPanelProps) {
      const pageContext = {
        page_id: pageId,
        current_filters:
          reportDate != null
            ? { ...defaultFilters, ...currentFilters, report_date: reportDate }
            : { ...defaultFilters, ...currentFilters },
        selected_rows: selectedRows,
        context_note: contextNote,
      };

      const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();
        const input = event.currentTarget.elements.namedItem("question");
        const question = input instanceof HTMLInputElement ? input.value : "";
        void fetch("/api/agent/query", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            question,
            page_context: pageContext,
          }),
        });
      };

      return (
        <form data-testid="agent-panel" onSubmit={handleSubmit}>
          <code className="agent-page-context__code">{JSON.stringify(pageContext.current_filters)}</code>
          <input data-testid="agent-panel-question" name="question" />
          <button data-testid="agent-panel-submit" type="submit">
            Submit
          </button>
        </form>
      );
    },
  };
});

beforeAll(async () => {
  await import("../features/stock-analysis/pages/StockAnalysisPage");
}, 20_000);

afterEach(() => {
  vi.unstubAllGlobals();
});

function expectElementBefore(first: HTMLElement, second: HTMLElement) {
  expect(first.compareDocumentPosition(second) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
}

async function openReviewQueueTable() {
  const queue = await screen.findByTestId("stock-analysis-review-queue");
  const toggle = within(queue).queryByRole("button", { name: /\u5b8c\u6574\u5019\u9009\u961f\u5217/ });
  if (toggle && toggle.getAttribute("aria-expanded") !== "true") {
    fireEvent.click(toggle);
  }
  return within(queue).findByTestId("stock-analysis-review-queue-table");
}

function buildJsonResponse(payload: unknown, status = 200) {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function buildStockAgentResult() {
  return {
    answer: "Stock embedded Agent answered.",
    cards: [],
    evidence: {
      tables_used: [],
      filters_applied: {
        provider: "local",
        transport: "sync",
      },
      evidence_rows: 0,
      quality_flag: "warning",
    },
    result_meta: {
      trace_id: "tr_stock_analysis_agent",
      basis: "formal",
      result_kind: "agent.analysis_chat",
      formal_use_allowed: false,
    },
    next_drill: [],
    suggested_actions: [],
  };
}

function parseLastAgentQueryRequest(fetchMock: ReturnType<typeof vi.fn>) {
  const agentCall = [...fetchMock.mock.calls]
    .reverse()
    .find(([input]) => String(input) === "/api/agent/query");
  if (!agentCall) {
    throw new Error("Missing /api/agent/query request");
  }
  const [, options] = agentCall;
  return JSON.parse(String((options as RequestInit | undefined)?.body));
}

function buildStrategyPayload(
  overrides: TestLivermoreStrategyOverrides = {},
): TestLivermoreStrategyPayload {
  return {
    as_of_date: "2026-04-29",
    requested_as_of_date: null,
    strategy_name: "Livermore A-Share Defended Trend",
    basis: "analytical",
    market_gate: {
      state: "WARM",
      exposure: 0.4,
      passed_conditions: 2,
      available_conditions: 2,
      required_conditions: 4,
      conditions: [
        {
          key: "csi300_close_gt_ma60",
          label: "CSI300 close > MA60",
          status: "pass",
          evidence: "Close is above MA60.",
          source_series_id: "CA.CSI300",
        },
      ],
    },
    rule_readiness: [
      {
        key: "market_gate",
        title: "Market gate",
        status: "partial",
        summary: "Trend-only market gate is available.",
        required_inputs: ["broad_index_history", "breadth"],
        missing_inputs: ["breadth"],
      },
    ],
    diagnostics: [
      {
        severity: "warning",
        code: "LIVERMORE_BREADTH_MISSING",
        message: "Breadth inputs are unavailable.",
        input_family: "breadth",
      },
    ],
    data_gaps: [
      {
        input_family: "breadth",
        status: "missing",
        evidence: "5-day breadth input family is not landed.",
      },
    ],
    supported_outputs: ["market_gate", "sector_rank", "stock_candidates", "risk_exit"],
    unsupported_outputs: [],
    sector_rank: {
      as_of_date: "2026-04-29",
      formula_version: "rv_livermore_sector_strength_observation_v1",
      is_provisional: false,
      formula_status: "signed_off",
      sector_count: 2,
      excluded_constituent_count: 0,
      excluded_sector_count: 0,
      items: [
        {
          rank: 1,
          sector_code: "801001",
          sector_name: "AI",
          score: 1.25,
          avg_pctchange: 4.8,
          avg_turn: 3,
          avg_amplitude: 3.5,
          constituent_count: 12,
        },
        {
          rank: 2,
          sector_code: "801002",
          sector_name: "新能源车",
          score: 0.8,
          avg_pctchange: -1.2,
          avg_turn: 5.6,
          avg_amplitude: 2,
          constituent_count: 24,
        },
      ],
    },
    stock_candidates: {
      as_of_date: "2026-04-29",
      formula_version: "rv_livermore_stock_candidates_bundle_v1",
      market_state: "WARM",
      input_stock_count: 2,
      candidate_count: 2,
      excluded_stock_count: 0,
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
          ema10: 20.6,
          ma20: 21.05,
          ma60: 19.05,
          ma120: 16.05,
          close_strength: 0.833333,
          gap_norm: -0.114679,
          abnormal_turnover: 1.386294,
          pe: 12.4,
          pb: 1.8,
          ps: 2.6,
          roe: 0.18,
          gross_margin: 0.32,
          three_month_return: 0.11,
          twelve_month_return: 0.24,
          factor_score: 0.4812,
          factor_overlay_rank: 1,
        },
        {
          rank: 2,
          stock_code: "000002.SZ",
          stock_name: "Beta",
          sector_code: "801002",
          sector_name: "新能源车",
          sector_rank: 2,
          close: 10,
          breakout_level: 10,
          ema10: 9.5,
          ma20: 9.8,
          ma60: 9.2,
          ma120: 8.5,
          close_strength: 0.5,
          gap_norm: 0.01,
          abnormal_turnover: 1.0,
        },
      ],
    },
    risk_exit: {
      as_of_date: "2026-04-29",
      formula_version: "rv_livermore_risk_exit_ema10_mvp_v1",
      position_count: 1,
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
      watch_items: [
        {
          stock_code: "000777.SZ",
          stock_name: "Watch Alpha",
          entry_cost: 19.5,
          bars_since_entry: 4,
          latest_close: 19.8,
          latest_ema10: 20.1,
          prior_close: 20.4,
          prior_ema10: 20,
          exit_watch_price: 20.1,
          triggered: false,
        },
      ],
    },
    ...overrides,
    module_states: overrides.module_states ?? readyModuleStates(overrides.as_of_date ?? "2026-04-29"),
  };
}

function buildStockAnalysisWorkbenchPayload(
  strategy: LivermoreStrategyPayload,
): StockAnalysisWorkbenchPayload {
  const reviewQueue = [
    ...(strategy.stock_candidates?.items ?? []),
    ...(strategy.factor_screen_candidates?.items ?? []),
    ...(strategy.hybrid_fusion_candidates?.items ?? []),
  ];
  return {
    page_id: "GAP-STOCK-ANALYSIS-PAGE",
    route: "/stock-analysis",
    basis: "analytical",
    contract_status: "observational_only",
    formal_use_allowed: false,
    requested_as_of_date: strategy.requested_as_of_date,
    as_of_date: strategy.as_of_date,
    fallback_date: null,
    stale: false,
    page_question: {
      question: "Can the stock analysis workbench continue candidate review today?",
      answer_state: reviewQueue.length > 0 ? "review_ready" : "no_data",
      answer_label: reviewQueue.length > 0 ? "review_ready" : "no_data",
      reason: "test",
    },
    decision_summary: {
      gate_state: strategy.market_gate.state,
      gate_label: strategy.market_gate.state,
      can_review_candidates: reviewQueue.length > 0,
      top_review_stock_code: String(reviewQueue[0]?.stock_code ?? "") || null,
      top_review_stock_name: String(reviewQueue[0]?.stock_name ?? "") || null,
      review_queue_count: reviewQueue.length,
      evidence_closure_label: "review_ready",
      primary_blocker: null,
      quality_flag: "ok",
    },
    data_status: {
      quality_flag: "ok",
      vendor_status: "ok",
      fallback_mode: "none",
      source_version: "sv_livermore_test",
      rule_version: "rv_livermore_market_gate_v1",
      cache_version: "cv_livermore_market_gate_v1",
      tables_used: [],
      evidence_rows: 0,
    },
    first_screen: {
      market_gate: strategy.market_gate,
      review_queue: reviewQueue,
      sector_snapshot: strategy.sector_rank?.items ?? [],
      risk_exit_snapshot: [
        ...(strategy.risk_exit?.items ?? []),
        ...(strategy.risk_exit?.watch_items ?? []),
      ],
      data_gaps: strategy.data_gaps,
      diagnostics: strategy.diagnostics,
      supported_outputs: strategy.supported_outputs,
      unsupported_outputs: strategy.unsupported_outputs,
    },
    modules: {
      main: {
        key: "main",
        label: "Livermore strategy snapshot",
        endpoint: "/ui/market-data/livermore",
        status: "ready",
        result: strategy,
        summary: strategy.workbench_summary ?? {},
        meta: {},
        issues: [],
      },
    },
    endpoint_evidence: [
      {
        key: "main",
        label: "Livermore strategy snapshot",
        endpoint: "/ui/market-data/livermore",
        status: "ready",
        as_of_date: strategy.as_of_date,
        rows: 0,
        warning: null,
      },
    ],
    issues: [],
    links: {
      stock_detail: "/ui/market-data/livermore/stock-detail",
      candidate_history: "/ui/market-data/livermore/candidate-history",
      sector_rank_series: "/ui/market-data/livermore/sector-rank-series",
      strategy_score: "/ui/market-data/livermore/strategy-score",
      strategy_optimization: "/ui/market-data/livermore/strategy-optimization",
      cycle_proxy_backtest: "/ui/market-data/livermore/cycle-proxy-backtest",
      portfolio_backtest: "/ui/market-data/livermore/candidate-history-portfolio-backtest",
    },
    include: {
      requested: ["evidence_summary", "main"],
      unknown: [],
      sector_window_days: 20,
      top_k: 10,
    },
  };
}

function buildLedgerCandidate(
  overrides: Partial<StockCandidateReviewQueueItem> = {},
): StockCandidateReviewQueueItem {
  return {
    rank: 1,
    stockCode: "000001.SZ",
    stockName: "Alpha",
    sectorCode: "801001",
    sectorName: "AI",
    headline: "观察候选#1 · Alpha",
    pattern: "突破",
    patternNote: "量价结构仍需人工复核。",
    distanceToBreakoutPct: "MA20 +1.2%",
    reviewFocus: "Alpha · AI · 距观察位 MA20 +1.2%",
    primaryEvidence: [
      { key: "turnover", label: "量比", value: "1.8x" },
      { key: "strength", label: "强度", value: "站上 20 日均线" },
    ],
    supportingEvidence: [{ key: "breadth", label: "扩散", value: "行业扩散 3/5" }],
    boundaryEvidence: ["公告催化尚未核实，边界待复核。"],
    invalidationFocus: "跌回 MA20 下方即降级观察。",
    invalidationRules: ["跌回 MA20 下方即降级观察。"],
    rawFields: [
      { key: "fusion_score", label: "Fusion", value: "0.812345" },
      { key: "cycle_score", label: "Cycle", value: "0.623456" },
      { key: "lifecourt_proxy_score", label: "Lifecourt", value: "0.412345" },
      { key: "confidence", label: "Confidence", value: "medium" },
      { key: "fusion_action", label: "Action", value: "monitor_only" },
    ],
    ...overrides,
  };
}

function buildCycleRotationFramework(): NonNullable<LivermoreStrategyPayload["cycle_rotation_framework"]> {
  return {
    strategy_name: "A-share cycle rotation research framework",
    display_name: "A股景气周期选股与行业轮动",
    observation_only: true,
    implementation_stage: "verification_pending",
    score_formula: "CycleScore = 0.30 Macro + 0.35 Industry + 0.20 MarketFlow + 0.15 ValuationSupport",
    rebalance_cadence: "Monthly core review with weekly satellite monitoring.",
    boundary: "blocked_missing_inputs",
    constraints: ["industry cap 25%", "stock cap 5%", "exclude ST and suspended stocks"],
    layers: [
      {
        key: "macro_direction",
        title: "Macro direction",
        weight: 0.3,
        status: "missing_inputs",
        evidence: "Market gate is available; PMI and credit impulse are not landed.",
        available_inputs: ["market_gate"],
        missing_inputs: ["PMI", "credit_impulse"],
      },
      {
        key: "industry_cycle",
        title: "Industry cycle",
        weight: 0.35,
        status: "provisional",
        evidence: "sector_rank is available.",
        available_inputs: ["sector_rank"],
        missing_inputs: ["profit_cycle"],
      },
    ],
  };
}

function buildConfluencePayload(
  overrides: Partial<LivermoreSignalConfluencePayload> = {},
): LivermoreSignalConfluencePayload {
  return {
    as_of_date: "2026-04-29",
    macro_context: {
      status: "neutral",
      composite_score: 0.05,
      multiplier: 0.5,
    },
    strategy_context: {
      market_gate_state: "WARM",
      market_gate_exposure: 0.4,
      allows_new_entry_observations: true,
    },
    position_size_hint: 0.2,
    entry_observations: [],
    exit_observations: [
      {
        stock_code: "000777.SZ",
        stock_name: "Watch Alpha",
        action: "observe_exit_watch",
        current_price: 19.8,
        exit_watch_price: 20.1,
        triggered: false,
        evidence: ["风险观察价来自 Livermore EMA10。"],
      },
    ],
    diagnostics: [],
    disclaimer: "Observation-only output.",
    ...overrides,
  };
}

function buildReplayStatus(overrides: Partial<ConfluenceReplayStatus> = {}): ConfluenceReplayStatus {
  return {
    window_status: "valid",
    has_decision_usable_completed_stats: true,
    completed_dates: 2,
    pending_dates: 0,
    unsupported_dates: 0,
    proxy_only_dates: 0,
    completed_candidate_rows: 5,
    pending_candidate_rows: 0,
    unsupported_candidate_rows: 0,
    proxy_only_candidate_rows: 0,
    included_completed_stats_dates: ["2026-05-06", "2026-05-07"],
    blocked_dates: [],
    completed_zero_signal_dates: [],
    ...overrides,
  };
}

function buildCandidateHistoryPayload(
  overrides: Partial<LivermoreCandidateHistoryPayload> = {},
): LivermoreCandidateHistoryPayload {
  const payload: LivermoreCandidateHistoryPayload = {
    stock_code: null,
    snapshot_from: "2026-05-03",
    snapshot_to: "2026-05-13",
    limit: 500,
    backtest_window_summary: {
      status: "valid",
      snapshot_from: "2026-05-03",
      snapshot_to: "2026-05-13",
      replay_dates_total: 6,
      replay_dates_completed: 5,
      replay_dates_pending: 1,
      replay_dates_unsupported: 0,
      replay_dates_proxy_only: 0,
      completed_rows: 216,
      pending_rows: 4,
      unsupported_rows: 0,
      proxy_only_rows: 0,
      included_completed_stats_dates: ["2026-05-06", "2026-05-07"],
      excluded_from_completed_stats_dates: ["2026-05-13"],
      date_reasons: [],
    },
    summary: {
      row_count: 220,
      by_signal_kind: {
        stock_candidate: 36,
        factor_screen: 180,
        theme_breakout: 4,
      },
      by_signal_kind_horizon_stats: {
        stock_candidate: {
          return_1d: {
            available_count: 30,
            missing_count: 6,
            positive_count: 15,
            non_positive_count: 15,
            avg_return: 0.014118,
            win_rate: 0.5,
          },
          return_5d: {
            available_count: 6,
            missing_count: 30,
            positive_count: 6,
            non_positive_count: 0,
            avg_return: 0.199863,
            win_rate: 1,
          },
          return_20d: {
            available_count: 0,
            missing_count: 36,
            positive_count: 0,
            non_positive_count: 0,
            avg_return: null,
            win_rate: null,
          },
        },
        factor_screen: {
          return_1d: {
            available_count: 150,
            missing_count: 30,
            positive_count: 56,
            non_positive_count: 94,
            avg_return: -0.00036,
            win_rate: 0.373333,
          },
          return_5d: {
            available_count: 30,
            missing_count: 150,
            positive_count: 17,
            non_positive_count: 13,
            avg_return: 0.029253,
            win_rate: 0.566667,
          },
          return_20d: {
            available_count: 0,
            missing_count: 180,
            positive_count: 0,
            non_positive_count: 0,
            avg_return: null,
            win_rate: null,
          },
        },
      },
      decision_usable_stats: {
        row_count: 216,
        complete_row_count: 180,
        pending_row_count: 36,
        partial_halt_row_count: 0,
        missing_forward_return_count: 186,
        avg_return_1d: 0.002536,
        avg_return_5d: 0.063375,
        avg_return_20d: null,
        win_rate_1d: 0.394444,
        win_rate_5d: 0.633333,
        win_rate_20d: null,
        by_signal_kind: {
          stock_candidate: 36,
          factor_screen: 180,
          theme_breakout: 4,
        },
        by_signal_kind_horizon_stats: {
          stock_candidate: {
            return_1d: {
              available_count: 30,
              missing_count: 6,
              positive_count: 15,
              non_positive_count: 15,
              avg_return: 0.014118,
              win_rate: 0.5,
            },
            return_5d: {
              available_count: 6,
              missing_count: 30,
              positive_count: 6,
              non_positive_count: 0,
              avg_return: 0.199863,
              win_rate: 1,
            },
            return_20d: {
              available_count: 0,
              missing_count: 36,
              positive_count: 0,
              non_positive_count: 0,
              avg_return: null,
              win_rate: null,
            },
          },
          factor_screen: {
            return_1d: {
              available_count: 150,
              missing_count: 30,
              positive_count: 56,
              non_positive_count: 94,
              avg_return: -0.00036,
              win_rate: 0.373333,
            },
            return_5d: {
              available_count: 30,
              missing_count: 150,
              positive_count: 17,
              non_positive_count: 13,
              avg_return: 0.029253,
              win_rate: 0.566667,
            },
            return_20d: {
              available_count: 0,
              missing_count: 180,
              positive_count: 0,
              non_positive_count: 0,
              avg_return: null,
              win_rate: null,
            },
          },
        },
        included_snapshot_dates: ["2026-05-06", "2026-05-07"],
        excluded_snapshot_dates: ["2026-05-13"],
      },
    },
    items: [],
  };
  return { ...payload, ...overrides };
}

function buildStrategyScorePayload(
  overrides: Partial<LivermoreStrategyScorePayload> = {},
): LivermoreStrategyScorePayload {
  const factorRow: LivermoreStrategyScorePayload["rows"][number] = {
    market_state: "OVERHEAT",
    signal_kind: "factor_screen",
    strategy_label: "多因子",
    sample_status: "sufficient",
    priority_score: 62.4,
    priority_rank: 1,
    priority_label: "优先复核",
    reason: "T+5 样本 24，胜率 60.0%，均值 +2.40%，评分 62.40。仅用于优先复核排序。",
    stats: {
      return_1d: {
        available_count: 24,
        missing_count: 0,
        positive_count: 13,
        non_positive_count: 11,
        avg_return: 0.008,
        win_rate: 0.541667,
      },
      return_5d: {
        available_count: 24,
        missing_count: 0,
        positive_count: 14,
        non_positive_count: 10,
        avg_return: 0.024,
        win_rate: 0.6,
      },
      return_20d: {
        available_count: 20,
        missing_count: 4,
        positive_count: 12,
        non_positive_count: 8,
        avg_return: 0.031,
        win_rate: 0.6,
      },
    },
    diagnostics: {
      priority_scope: "rank<=10",
      priority_scope_label: "前10名优先复核",
      priority_scope_stats: {
        return_1d: {
          available_count: 20,
          missing_count: 0,
          positive_count: 11,
          non_positive_count: 9,
          avg_return: 0.0048,
          win_rate: 0.55,
        },
        return_5d: {
          available_count: 20,
          missing_count: 0,
          positive_count: 15,
          non_positive_count: 5,
          avg_return: 0.0421,
          win_rate: 0.75,
        },
        return_20d: {
          available_count: 0,
          missing_count: 20,
          positive_count: 0,
          non_positive_count: 0,
          avg_return: null,
          win_rate: null,
        },
      },
      maturity: {
        status: "narrow",
        label: "样本偏窄",
        reason: "T+5 matured snapshots 2/4, waiting for more mature days.",
        min_mature_snapshot_count: 4,
        mature_snapshot_count: 2,
        snapshot_stats: [
          {
            snapshot_as_of_date: "2026-04-30",
            available_count: 10,
            positive_count: 9,
            non_positive_count: 1,
            avg_return: 0.045477,
            win_rate: 0.9,
          },
          {
            snapshot_as_of_date: "2026-05-06",
            available_count: 10,
            positive_count: 6,
            non_positive_count: 4,
            avg_return: 0.038797,
            win_rate: 0.6,
          },
        ],
        tracked_snapshots: [
          {
            snapshot_as_of_date: "2026-04-30",
            candidate_count: 10,
            horizons: {
              return_1d: {
                status: "complete",
                available_count: 10,
                missing_count: 0,
                positive_count: 7,
                non_positive_count: 3,
                avg_return: 0.0112,
                win_rate: 0.7,
              },
              return_5d: {
                status: "complete",
                available_count: 10,
                missing_count: 0,
                positive_count: 9,
                non_positive_count: 1,
                avg_return: 0.045477,
                win_rate: 0.9,
              },
              return_20d: {
                status: "pending",
                available_count: 0,
                missing_count: 10,
                positive_count: 0,
                non_positive_count: 0,
                avg_return: null,
                win_rate: null,
              },
            },
          },
          {
            snapshot_as_of_date: "2026-05-07",
            candidate_count: 10,
            horizons: {
              return_1d: {
                status: "complete",
                available_count: 10,
                missing_count: 0,
                positive_count: 6,
                non_positive_count: 4,
                avg_return: 0.007,
                win_rate: 0.6,
              },
              return_5d: {
                status: "pending",
                available_count: 0,
                missing_count: 10,
                positive_count: 0,
                non_positive_count: 0,
                avg_return: null,
                win_rate: null,
              },
              return_20d: {
                status: "pending",
                available_count: 0,
                missing_count: 10,
                positive_count: 0,
                non_positive_count: 0,
                avg_return: null,
                win_rate: null,
              },
            },
          },
        ],
        worst_snapshot: {
          snapshot_as_of_date: "2026-05-06",
          available_count: 10,
          positive_count: 6,
          non_positive_count: 4,
          avg_return: 0.038797,
          win_rate: 0.6,
        },
      },
      rank_buckets: [
        {
          label: "1-5",
          rank_from: 1,
          rank_to: 5,
          sample_status: "sufficient",
          priority_label: "优先复核",
          included_in_priority: true,
          reason: "T+5 样本满足阈值且均值为正，仅用于优先复核排序。",
          stats: {
            return_1d: {
              available_count: 5,
              missing_count: 0,
              positive_count: 3,
              non_positive_count: 2,
              avg_return: 0.006,
              win_rate: 0.6,
            },
            return_5d: {
              available_count: 5,
              missing_count: 0,
              positive_count: 4,
              non_positive_count: 1,
              avg_return: 0.02,
              win_rate: 0.8,
            },
            return_20d: {
              available_count: 5,
              missing_count: 0,
              positive_count: 3,
              non_positive_count: 2,
              avg_return: 0.01,
              win_rate: 0.6,
            },
          },
        },
        {
          label: "11-20",
          rank_from: 11,
          rank_to: 20,
          sample_status: "sufficient",
          priority_label: "降权观察",
          included_in_priority: false,
          reason: "OVERHEAT 状态下 rank > 10 的多因子候选降权观察；优先复核仅覆盖前10名。",
          stats: {
            return_1d: {
              available_count: 4,
              missing_count: 0,
              positive_count: 1,
              non_positive_count: 3,
              avg_return: -0.002,
              win_rate: 0.25,
            },
            return_5d: {
              available_count: 4,
              missing_count: 0,
              positive_count: 1,
              non_positive_count: 3,
              avg_return: -0.01,
              win_rate: 0.25,
            },
            return_20d: {
              available_count: 0,
              missing_count: 4,
              positive_count: 0,
              non_positive_count: 0,
              avg_return: null,
              win_rate: null,
            },
          },
        },
      ],
      risk_flags: [],
    },
  };
  const trendRow: LivermoreStrategyScorePayload["rows"][number] = {
    market_state: "OVERHEAT",
    signal_kind: "stock_candidate",
    strategy_label: "趋势突破",
    sample_status: "sufficient",
    priority_score: 43.5,
    priority_rank: 2,
    priority_label: "降权观察",
    reason: "T+5 样本 22，胜率 45.5%，均值 -2.00%，评分 43.50。胜率低于 50% 或均值不为正，降权观察。",
    stats: {
      return_1d: {
        available_count: 22,
        missing_count: 0,
        positive_count: 10,
        non_positive_count: 12,
        avg_return: -0.004,
        win_rate: 0.454545,
      },
      return_5d: {
        available_count: 22,
        missing_count: 0,
        positive_count: 10,
        non_positive_count: 12,
        avg_return: -0.02,
        win_rate: 0.455,
      },
      return_20d: {
        available_count: 12,
        missing_count: 10,
        positive_count: 4,
        non_positive_count: 8,
        avg_return: -0.01,
        win_rate: 0.333333,
      },
    },
    diagnostics: {
      priority_scope: null,
      priority_scope_label: null,
      rank_buckets: [],
      risk_flags: [
        {
          kind: "long_window_risk",
          label: "长窗口风险",
          horizon: "return_20d",
          reason: "T+20 样本 12，胜率 33.3%，均值 -1.00%，仅按短窗口复核。",
          stats: {
            available_count: 12,
            missing_count: 10,
            positive_count: 4,
            non_positive_count: 8,
            avg_return: -0.01,
            win_rate: 0.333333,
          },
        },
      ],
    },
  };
  return {
    as_of_date: "2026-04-29",
    snapshot_from: "2025-10-31",
    snapshot_to: "2026-04-29",
    primary_horizon: "return_5d",
    min_sample: 20,
    current_market_state: "OVERHEAT",
    rows: [factorRow, trendRow],
    current_market_state_rows: [factorRow, trendRow],
    ...overrides,
  };
}

function buildStrategyOptimizationPayload(
  overrides: Partial<LivermoreStrategyOptimizationPayload> = {},
): LivermoreStrategyOptimizationPayload {
  const promotedStats = {
    return_1d: {
      available_count: 30,
      missing_count: 0,
      positive_count: 18,
      non_positive_count: 12,
      avg_return: 0.01,
      win_rate: 0.6,
    },
    return_5d: {
      available_count: 30,
      missing_count: 0,
      positive_count: 20,
      non_positive_count: 10,
      avg_return: 0.023333,
      win_rate: 0.666667,
    },
    return_20d: {
      available_count: 0,
      missing_count: 30,
      positive_count: 0,
      non_positive_count: 0,
      avg_return: null,
      win_rate: null,
    },
  };
  const weakStats = {
    return_1d: {
      available_count: 10,
      missing_count: 0,
      positive_count: 4,
      non_positive_count: 6,
      avg_return: -0.002,
      win_rate: 0.4,
    },
    return_5d: {
      available_count: 10,
      missing_count: 0,
      positive_count: 5,
      non_positive_count: 5,
      avg_return: -0.02,
      win_rate: 0.5,
    },
    return_20d: {
      available_count: 0,
      missing_count: 10,
      positive_count: 0,
      non_positive_count: 0,
      avg_return: null,
      win_rate: null,
    },
  };
  const pendingStats = {
    return_1d: {
      available_count: 2,
      missing_count: 0,
      positive_count: 2,
      non_positive_count: 0,
      avg_return: 0.01,
      win_rate: 1,
    },
    return_5d: {
      available_count: 2,
      missing_count: 0,
      positive_count: 2,
      non_positive_count: 0,
      avg_return: 0.06,
      win_rate: 1,
    },
    return_20d: {
      available_count: 0,
      missing_count: 2,
      positive_count: 0,
      non_positive_count: 0,
      avg_return: null,
      win_rate: null,
    },
  };
  const dateWeighted = {
    return_1d: {
      available_day_count: 1,
      candidate_row_count: 30,
      avg_return: 0.01,
      positive_day_rate: 1,
      worst_day_return: 0.01,
      best_day_return: 0.01,
    },
    return_5d: {
      available_day_count: 1,
      candidate_row_count: 30,
      avg_return: 0.023333,
      positive_day_rate: 1,
      worst_day_return: 0.023333,
      best_day_return: 0.023333,
    },
    return_20d: {
      available_day_count: 0,
      candidate_row_count: 0,
      avg_return: null,
      positive_day_rate: null,
      worst_day_return: null,
      best_day_return: null,
    },
  };

  return {
    as_of_date: "2026-05-13",
    snapshot_from: "2026-05-01",
    snapshot_to: "2026-05-13",
    primary_horizon: "return_5d",
    min_sample: 20,
    current_market_state: "HOT",
    backtest_window_summary: null,
    strategy_summaries: [
      {
        summary_key: "strategy:factor_screen",
        signal_kind: "factor_screen",
        strategy_label: "多因子",
        sample_status: "sufficient",
        stats: promotedStats,
        date_weighted_stats: dateWeighted,
        recommendation: {
          action: "promote",
          priority_label: "优先复核",
          reason: "T+5 sample 30, avg return +2.33%, win rate 66.7%, priority review ranking.",
          primary_horizon: "return_5d",
          available_count: 30,
          min_sample: 20,
          avg_return: 0.023333,
          win_rate: 0.666667,
          score: 69,
        },
      },
      {
        summary_key: "strategy:theme_breakout",
        signal_kind: "theme_breakout",
        strategy_label: "题材突变",
        sample_status: "insufficient",
        stats: pendingStats,
        date_weighted_stats: dateWeighted,
        recommendation: {
          action: "pending_more_history",
          priority_label: "样本不足",
          reason: "T+5 成熟样本 2/20，样本不足，提示不作为调参依据。",
          primary_horizon: "return_5d",
          available_count: 2,
          min_sample: 20,
          avg_return: 0.06,
          win_rate: 1,
          score: 106,
        },
      },
    ],
    slices: [
      {
        slice_key: "factor_screen:rank:21-30",
        signal_kind: "factor_screen",
        strategy_label: "多因子",
        dimension: "rank",
        bucket: "21-30",
        label: "rank 21-30",
        sample_status: "sufficient",
        stats: weakStats,
        date_weighted_stats: dateWeighted,
        recommendation: {
          action: "downgrade",
          priority_label: "降权观察",
          reason: "T+5 样本 10，均值 -2.00%，胜率 50.0%，降权观察。",
          primary_horizon: "return_5d",
          available_count: 10,
          min_sample: 10,
          avg_return: -0.02,
          win_rate: 0.5,
          score: 48,
        },
      },
    ],
    recommendations: [],
    pending_summary: {
      primary_horizon: "return_5d",
      pending_rows: 18,
      pending_dates: ["2026-05-13"],
      latest_pending_date: "2026-05-13",
      message: "T+5 仍有 18 条收益待成熟，最新 pending 日期 2026-05-13。",
    },
    sample_maturity: {
      status: "sufficient",
      primary_horizon: "return_5d",
      min_sample: 20,
      sufficient_count: 2,
      insufficient_count: 1,
    },
    ...overrides,
  };
}

function stockClient(options?: {
  strategy?: LivermoreStrategyPayload;
  strategyError?: Error;
  confluence?: LivermoreSignalConfluencePayload;
  confluenceError?: Error;
  candidateHistory?: LivermoreCandidateHistoryPayload;
  candidateHistoryError?: Error;
  candidateHistoryPortfolioBacktest?: LivermoreCandidateHistoryPortfolioBacktestPayload;
  candidateHistoryPortfolioBacktestError?: Error;
  cycleProxyBacktest?: LivermoreCycleProxyBacktestPayload;
  cycleProxyBacktestError?: Error;
  strategyScore?: LivermoreStrategyScorePayload;
  strategyScoreError?: Error;
  strategyOptimization?: LivermoreStrategyOptimizationPayload;
  strategyOptimizationError?: Error;
  metaOverrides?: Partial<ApiEnvelope<LivermoreStrategyPayload>["result_meta"]>;
}): ApiClient {
  return {
    ...createApiClient({ mode: "mock" }),
    getLivermoreStrategy: async (): Promise<ApiEnvelope<LivermoreStrategyPayload>> => {
      if (options?.strategyError) {
        throw options.strategyError;
      }
      return buildMockApiEnvelope(
        "market_data.livermore",
        options?.strategy ?? buildStrategyPayload(),
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_livermore_test",
          vendor_version: "vv_livermore_test",
          rule_version: "rv_livermore_market_gate_v1",
          ...options?.metaOverrides,
        },
      );
    },
    getStockAnalysisWorkbench: async (): Promise<ApiEnvelope<StockAnalysisWorkbenchPayload>> => {
      if (options?.strategyError) {
        throw options.strategyError;
      }
      const strategy = options?.strategy ?? buildStrategyPayload();
      return buildMockApiEnvelope(
        "market_data.stock_analysis.workbench",
        buildStockAnalysisWorkbenchPayload(strategy),
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_livermore_test",
          vendor_version: "vv_livermore_test",
          rule_version: "rv_stock_analysis_workbench_v1",
          ...options?.metaOverrides,
        },
      );
    },
    getLivermoreSignalConfluence: async (): Promise<
      ApiEnvelope<LivermoreSignalConfluencePayload>
    > => {
      if (options?.confluenceError) {
        throw options.confluenceError;
      }
      return buildMockApiEnvelope(
        "market_data.livermore.signal_confluence",
        options?.confluence ?? buildConfluencePayload(),
      );
    },
    getLivermoreCandidateHistory: async (): Promise<ApiEnvelope<LivermoreCandidateHistoryPayload>> => {
      if (options?.candidateHistoryError) {
        throw options.candidateHistoryError;
      }
      return buildMockApiEnvelope(
        "market_data.livermore.candidate_history",
        options?.candidateHistory ?? buildCandidateHistoryPayload(),
      );
    },
    getLivermoreCandidateHistoryPortfolioBacktest: async (): Promise<
      ApiEnvelope<LivermoreCandidateHistoryPortfolioBacktestPayload>
    > => {
      if (options?.candidateHistoryPortfolioBacktestError) {
        throw options.candidateHistoryPortfolioBacktestError;
      }
      return buildMockApiEnvelope(
        "market_data.livermore.candidate_history_portfolio_backtest",
        options?.candidateHistoryPortfolioBacktest ?? {
          status: "portfolio_proxy",
          full_strategy_status: "blocked_missing_inputs",
          signal_kind: "stock_candidate",
          rebalance_rule: "first_available_monthly_snapshot",
          weighting_rule: "equal_weight_top_6",
          snapshot_from: "2024-09-24",
          snapshot_to: "2026-03-02",
          missing_full_strategy_inputs: ["PMI", "credit_impulse"],
          warnings: ["Portfolio proxy only."],
          summary: {
            sample_days: 352,
            candidate_rows: 52,
            rebalance_count: 17,
            invested_rebalance_count: 14,
            cash_rebalance_count: 3,
            gross_turnover: 21.4,
            cost_drag: 0.0206,
            cumulative_return: -0.1842,
            annualized_return: -0.1315,
            max_gain: {
              return: 0.2834,
              start_date: "2024-09-24",
              end_date: "2024-10-08",
            },
            max_drawdown: {
              return: -0.4125,
              peak_date: "2024-10-08",
              trough_date: "2025-04-25",
            },
          },
          nav_series: [],
          rebalance_log: [],
        },
      );
    },
    getLivermoreCycleProxyBacktest: async (): Promise<ApiEnvelope<LivermoreCycleProxyBacktestPayload>> => {
      if (options?.cycleProxyBacktestError) {
        throw options.cycleProxyBacktestError;
      }
      return buildMockApiEnvelope(
        "market_data.livermore.cycle_proxy_backtest",
        options?.cycleProxyBacktest ?? {
          status: "proxy",
          full_strategy_status: "blocked_missing_inputs",
          proxy_signal_kind: "stock_candidate",
          proxy_rule: "Equal-weight non-overlapping T+5 baskets of completed stock_candidate rows.",
          snapshot_from: "2024-09-24",
          snapshot_to: "2026-03-02",
          missing_full_strategy_inputs: ["PMI", "credit_impulse"],
          warnings: ["Proxy only."],
          summary: {
            sample_days: 225,
            candidate_rows: 755,
            cumulative_return: -0.297,
            annualized_return: -0.4801,
            max_gain: {
              return: 0.9185,
              start_date: "2024-09-24",
              end_date: "2024-12-02",
            },
            max_drawdown: {
              return: -0.6342,
              peak_date: "2024-12-02",
              trough_date: "2026-01-21",
            },
          },
          nav_series: [],
        },
      );
    },
    getLivermoreStrategyScore: async (): Promise<ApiEnvelope<LivermoreStrategyScorePayload>> => {
      if (options?.strategyScoreError) {
        throw options.strategyScoreError;
      }
      return buildMockApiEnvelope(
        "market_data.livermore.strategy_score",
        options?.strategyScore ?? buildStrategyScorePayload(),
      );
    },
    getLivermoreStrategyOptimization: async (): Promise<ApiEnvelope<LivermoreStrategyOptimizationPayload>> => {
      if (options?.strategyOptimizationError) {
        throw options.strategyOptimizationError;
      }
      return buildMockApiEnvelope(
        "market_data.livermore.strategy_optimization",
        options?.strategyOptimization ?? buildStrategyOptimizationPayload(),
      );
    },
  };
}

function mockStrategyLatestSnapshotFallback(
  client: ApiClient,
  dates: {
    initialAsOfDate?: string;
    resolvedAsOfDate?: string;
    payloadOverrides?: Partial<LivermoreStrategyPayload>;
  } = {},
) {
  const resolvedAsOfDate = dates.resolvedAsOfDate ?? "2026-04-29";
  const initialAsOfDate = dates.initialAsOfDate ?? resolvedAsOfDate;

  return vi.spyOn(client, "getStockAnalysisWorkbench").mockImplementation(async (options) => {
    const strategy = buildStrategyPayload({
      as_of_date: options?.asOfDate ? resolvedAsOfDate : initialAsOfDate,
      requested_as_of_date: options?.asOfDate ?? null,
      ...dates.payloadOverrides,
    });
    return buildMockApiEnvelope(
      "market_data.stock_analysis.workbench",
      buildStockAnalysisWorkbenchPayload(strategy),
      {
        basis: "analytical",
        formal_use_allowed: false,
        source_version: "sv_livermore_test",
        vendor_version: "vv_livermore_test",
        rule_version: "rv_stock_analysis_workbench_v1",
        fallback_mode: options?.asOfDate ? "latest_snapshot" : "none",
      },
    );
  });
}

async function requestStockAnalysisAsOfDate(
  user: ReturnType<typeof userEvent.setup>,
  strategySpy: ReturnType<typeof mockStrategyLatestSnapshotFallback>,
  requestedAsOfDate = "2026-05-08",
  resolvedAsOfDate = "2026-04-29",
) {
  await screen.findByTestId("stock-analysis-decision-panel");
  const picker = screen.getByTestId("stock-analysis-as-of-picker");
  const pickerInput = picker instanceof HTMLInputElement ? picker : picker.querySelector("input");
  expect(pickerInput).toBeInstanceOf(HTMLInputElement);
  await user.click(pickerInput as HTMLInputElement);
  fireEvent.change(pickerInput as HTMLInputElement, { target: { value: requestedAsOfDate } });
  fireEvent.keyDown(pickerInput as HTMLInputElement, { key: "Enter", code: "Enter" });
  fireEvent.blur(pickerInput as HTMLInputElement);

  await waitFor(() =>
    expect(strategySpy).toHaveBeenCalledWith(expect.objectContaining({ asOfDate: requestedAsOfDate })),
  );
  await waitFor(() =>
    expect(screen.getByTestId("stock-analysis-decision-panel")).toHaveTextContent(resolvedAsOfDate),
  );
}

describe("StockAnalysisPage", () => {
  it("renders first-screen fact cards with Chinese group labels and optional interaction state", async () => {
    const digest: WorkbenchDataDigest = {
      primaryFacts: [
        {
          id: "candidate-depth",
          label: "候选深度",
          value: "1 / 1",
          subValue: "已落地",
          sourcePath: "strategy.result.stock_candidates.items",
          tone: "read",
          isPrimary: true,
        },
      ],
      candidateFacts: [
        {
          id: "factor-candidates",
          label: "多因子候选",
          value: "3",
          sourcePath: "strategy.result.factor_screen_candidates.items",
          tone: "warning",
        },
      ],
      evidenceFacts: [
        {
          id: "hybrid-candidates",
          label: "融合候选",
          value: "rv_hybrid_fusion_candidates_v3",
          sourcePath: "strategy.result.hybrid_fusion_candidates.formula_version",
          tone: "read",
        },
      ],
      slowFacts: [
        {
          id: "strategy-score",
          label: "优先级补证",
          value: "读取中",
          subValue: "首屏不阻塞",
          sourcePath: "strategy_score.status",
          tone: "slow",
        },
      ],
    };

    const baseProps = {
      asOfLabel: "2026-04-29",
      kicker: "复核工作台",
      headline: "首屏供数",
      lead: "供数事实卡片",
      metrics: [],
      conditionCells: [],
      sourceCells: [],
      railRows: [],
      digest,
    };

    const { unmount } = render(<StockAnalysisReviewLedgerFirstScreen {...baseProps} />);
    const detailShell = screen.getByTestId("stock-analysis-evidence-detail-shell");
    expect(detailShell).not.toHaveAttribute("open");
    expect(within(detailShell).getByText("证据与口径明细")).toBeInTheDocument();
    await userEvent.click(within(detailShell).getByText("证据与口径明细"));
    const digestRegion = screen.getByLabelText("首屏供数摘要");
    expect(within(digestRegion).getByText("核心口径")).toBeInTheDocument();
    expect(within(digestRegion).getByText("完整证据账本 / 审计明细")).toBeInTheDocument();
    expect(within(digestRegion).queryByTestId("stock-analysis-workbench-fact-factor-candidates")).not.toBeInTheDocument();
    expect(within(digestRegion).queryByTestId("stock-analysis-workbench-fact-strategy-score")).not.toBeInTheDocument();
    const staticFact = screen.getByTestId("stock-analysis-workbench-fact-candidate-depth");
    expect(staticFact.tagName).toBe("ARTICLE");
    expect(staticFact).not.toHaveAttribute("title");
    expect(staticFact).not.toHaveTextContent("strategy.result.stock_candidates.items");
    expect(staticFact).toHaveAttribute("data-tone", "read");
    expect(staticFact).toHaveAttribute("data-primary", "true");
    expect(staticFact).toHaveAttribute("data-active", "false");
    unmount();

    const onFactSelect = vi.fn();
    render(
      <StockAnalysisReviewLedgerFirstScreen
        {...baseProps}
        onFactSelect={onFactSelect}
        activeFactId="factor-candidates"
        factControlsId="stock-analysis-fact-evidence-panel"
      />,
    );

    const activeFact = screen.getByTestId("stock-analysis-workbench-fact-factor-candidates");
    expect(screen.getByTestId("stock-analysis-evidence-detail-shell")).toHaveAttribute("open");
    const interactiveDigest = screen.getByLabelText("首屏供数摘要");
    expect(within(interactiveDigest).queryByRole("listbox")).not.toBeInTheDocument();
    expect(screen.getByTestId("stock-analysis-workbench-audit-details")).toBeInTheDocument();
    expect(within(interactiveDigest).getByRole("button", { name: /多因子候选/ })).toBe(activeFact);
    expect(activeFact.tagName).toBe("BUTTON");
    expect(activeFact).toHaveAttribute("aria-current", "true");
    expect(activeFact).not.toHaveAttribute("aria-selected");
    expect(activeFact).not.toHaveAttribute("aria-pressed");
    expect(activeFact).toHaveAttribute("aria-controls", "stock-analysis-fact-evidence-panel");
    expect(activeFact).toHaveAttribute("data-active", "true");
    expect(activeFact).not.toHaveAttribute("title");
    expect(activeFact).not.toHaveTextContent("strategy.result.factor_screen_candidates.items");
    await userEvent.click(activeFact);
    expect(onFactSelect).toHaveBeenCalledWith(digest.candidateFacts[0]);
  });

  it("shows a dashboard skeleton while the stock analysis payload is loading", async () => {
    const client = {
      ...stockClient(),
      getStockAnalysisWorkbench: vi.fn(() => new Promise<ApiEnvelope<StockAnalysisWorkbenchPayload>>(() => undefined)),
    };

    renderWorkbenchApp(["/stock-analysis"], { client });

    const loading = await screen.findByTestId("stock-analysis-loading-workbench");
    expect(loading).toBeInTheDocument();
    expect(screen.queryByText("正在加载股票分析结果。")).not.toBeInTheDocument();
    expect(screen.getByText("股票分析加载中")).toBeInTheDocument();
  });

  it("loads the first screen through the stock-analysis workbench contract", async () => {
    const client = stockClient();
    const workbenchSpy = vi.spyOn(client, "getStockAnalysisWorkbench");
    const strategySpy = vi.spyOn(client, "getLivermoreStrategy");

    renderWorkbenchApp(["/stock-analysis"], { client });

    await waitFor(() => expect(workbenchSpy).toHaveBeenCalled());
    await screen.findByTestId("stock-analysis-first-screen-workbench");
    expect(workbenchSpy.mock.calls[0]?.[0]).toEqual({ topK: 3 });
    expect(strategySpy).not.toHaveBeenCalled();
  });

  it("marks the backend-supply cockpit without changing the stock data path", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        metaOverrides: {
          tables_used: ["choice_stock_a", "choice_stock_b"],
          evidence_rows: 12345,
          rule_version: "rv_custom_stock_v1",
          trace_id: "tr_api_01",
        },
      }),
    });

    const page = await screen.findByTestId("stock-analysis-page");
    expect(page).toHaveAttribute("data-layout-rev", "2026-05-31e");
    expect(page).toHaveAttribute("data-data-viz-rev", "2026-05-31e");
    const cockpit = await screen.findByTestId("stock-analysis-tailwind-cockpit");
    expect(cockpit.className).toContain("stock-analysis-page__dh-hero");
    expect(cockpit).toHaveTextContent("观测闭环总控");
    expect(cockpit).toHaveTextContent("数据日期");
    expect(cockpit).toHaveTextContent("门控 温和");
    expect(cockpit).toHaveTextContent("条件 2/4");
    expect(cockpit).toHaveTextContent("缺口 1");
    expect(cockpit).toHaveTextContent("风险 触发 1");
    expect(cockpit).not.toHaveTextContent("查看今日门控、候选队列与证据是否齐全");
    expect(cockpit).not.toHaveTextContent("TAILWIND");
    expect(cockpit).not.toHaveTextContent("后台供数");
    expect(cockpit).toHaveTextContent("门控 WARM");
    expect(cockpit).not.toHaveTextContent("Livermore");
    expect(cockpit).not.toHaveTextContent("rv_custom_stock_v1");
    await userEvent.click(within(cockpit).getByText("证据与口径明细"));
    await userEvent.click(within(cockpit).getByRole("button", { name: /供数与链路/ }));
    const apiEvidence = await screen.findByTestId("stock-analysis-api-evidence-strip");
    expect(apiEvidence).toHaveTextContent("来源覆盖");
    expect(apiEvidence).toHaveTextContent("证据覆盖");
    expect(apiEvidence).toHaveTextContent("规则状态");
    expect(apiEvidence).toHaveTextContent("追踪状态");
    expect(apiEvidence).toHaveTextContent("已追踪");
    expect(apiEvidence).toHaveTextContent("12,345");
    expect(apiEvidence).not.toHaveTextContent("rv_custom_stock_v1");
    expect(apiEvidence).not.toHaveTextContent("tr_api_01");

    const kpiSection = await screen.findByTestId("stock-analysis-kpi-section");
    expect(kpiSection).toHaveTextContent("市场状态");
    expect(kpiSection).toHaveTextContent("温和");
    expect(kpiSection).not.toHaveTextContent("WARM");
    expect(screen.getByTestId("stock-analysis-kpi-market-state")).toHaveAttribute("data-equity-kpi-card");
    expect(screen.getByTestId("stock-analysis-kpi-review-queue")).toHaveAttribute("data-equity-kpi-card");
    expect(screen.queryByTestId("stock-analysis-functional-kpi-section")).not.toBeInTheDocument();

    const sectorPanel = await screen.findByTestId("stock-analysis-sector-strength-panel");
    const sectorStrip = within(sectorPanel).getByTestId("stock-analysis-sector-workbench-strip");
    expect(sectorStrip).toHaveTextContent("板块");
    expect(sectorStrip).toHaveTextContent("首位");
    expect(sectorStrip).toHaveTextContent("尾部");
    expect(sectorStrip).toHaveTextContent("成分");
    expect(within(sectorPanel).getByTestId("stock-analysis-sector-strength-chart")).toBeInTheDocument();

    const selection = await screen.findByTestId("stock-analysis-stock-selection");
    expect(selection).toHaveTextContent("复核队列");
    expect(selection).toHaveTextContent("策略共振选股");
    expect(screen.getByTestId("stock-analysis-review-workbench-strip")).toHaveTextContent("队列");
    expect(screen.getByTestId("stock-analysis-review-workbench-strip")).toHaveTextContent("距观察");
    expect(screen.getByTestId("stock-analysis-consensus-workbench-strip")).toHaveTextContent("共振");
    expect(screen.getByTestId("stock-analysis-consensus-workbench-strip")).toHaveTextContent("多因子");
    expect(await screen.findByTestId("stock-analysis-observation-preview")).toHaveTextContent("多策略观察池");
    const strategyLens = await screen.findByTestId("stock-analysis-strategy-lens");
    expect(strategyLens).toHaveTextContent("核心选股策略");
    expect(strategyLens).toHaveTextContent("4 策略台账");
    expect(strategyLens).toHaveTextContent("趋势突破");
    expect(strategyLens).toHaveTextContent("融合策略");
    expect(strategyLens).toHaveTextContent("多因子");
    expect(strategyLens).toHaveTextContent("超跌反弹");
    expect(strategyLens).toHaveTextContent("阻断");
    expect(strategyLens).toHaveTextContent("关注");
    expect(strategyLens).toHaveTextContent("入口");
    expect(strategyLens).toHaveTextContent("查看观察池");
    expect(within(strategyLens).getByTestId("stock-analysis-strategy-lens-livermore")).toHaveTextContent("2");
    const hybridStrategyMeta = within(strategyLens).getByTestId("stock-analysis-strategy-lens-hybrid-meta");
    expect(hybridStrategyMeta.tagName).toBe("DETAILS");
    expect(hybridStrategyMeta).not.toHaveAttribute("open");
    expect(hybridStrategyMeta.querySelector(".stock-analysis-page__strategy-lens-ledger")).not.toBeNull();
    expect(hybridStrategyMeta.querySelector(".stock-analysis-page__strategy-lens-version")).not.toBeNull();
    expect(hybridStrategyMeta.querySelector(".stock-analysis-page__strategy-lens-evidence")).not.toBeNull();
    expect(await screen.findByTestId("stock-analysis-candidate-comparison")).toHaveTextContent("观察位");
    expect(screen.queryByTestId("stock-analysis-review-queue-ranking-chart")).not.toBeInTheDocument();
    expect(await screen.findByTestId("stock-analysis-risk-section")).toBeInTheDocument();
    expect(await screen.findByTestId("stock-analysis-deep-zone")).toBeInTheDocument();
    expect(await screen.findByTestId("stock-analysis-deep-zone-gate-summary")).toBeInTheDocument();
    expect(page).not.toHaveTextContent("策略池暂无候选");
    expect(page).not.toHaveTextContent("当前状态样本不足");
    expect(page).not.toHaveTextContent("暂无优化诊断结果");

    expect(screen.queryByTestId("stock-analysis-supply-details-toggle")).not.toBeInTheDocument();
    expect(screen.queryByTestId("stock-analysis-sector-mini-chart")).not.toBeInTheDocument();
    expect(screen.queryByTestId("stock-analysis-review-mini-chart")).not.toBeInTheDocument();
    expect(screen.queryByTestId("stock-analysis-event-mini-chart")).not.toBeInTheDocument();
    expect(screen.queryByTestId("stock-analysis-risk-mini-chart")).not.toBeInTheDocument();

    const evidenceLedger = await screen.findByTestId("stock-analysis-evidence-ledger");
    expect(within(evidenceLedger).getByTestId("stock-analysis-closed-loop-summary")).toBeInTheDocument();
    expect(within(evidenceLedger).getByTestId("stock-analysis-boundary-rail")).toBeInTheDocument();
    expect(await screen.findByTestId("stock-analysis-historical-review-section")).toHaveTextContent("历史复核");
    expect(await screen.findByTestId("stock-analysis-consensus-panel-summary")).toBeInTheDocument();
    expect(await screen.findByTestId("stock-analysis-theme-panel-summary")).toBeInTheDocument();
    expect(await screen.findByTestId("stock-analysis-events-panel-summary")).toBeInTheDocument();
  });

  it("shows first-screen workbench data digest and non-blocking slow evidence slots", async () => {
    const client = stockClient({
      strategy: buildStrategyPayload({
        factor_screen_candidates: {
          as_of_date: "2026-04-29",
          formula_version: "rv_factor_screen_candidates_v2",
          market_state: "WARM",
          input_stock_count: 1,
          candidate_count: 1,
          coverage_note: "ok",
          items: [
            {
              rank: 1,
              stock_code: "600000.SH",
              stock_name: "浦发银行",
              sector_code: "801780",
              sector_name: "閾惰",
              industry: "閾惰",
              score: 0.82,
              pe: 5.2,
              pb: 0.6,
              roe: 0.12,
              gross_margin: 0.31,
              three_month_return: 0.08,
              twelve_month_return: 0.18,
              dividend_yield: 0.04,
            },
          ],
        },
        hybrid_fusion_candidates: {
          as_of_date: "2026-04-29",
          formula_version: "rv_hybrid_fusion_candidates_v3",
          market_state: "WARM",
          observation_only: true,
          candidate_count: 1,
          items: [
            {
              rank: 1,
              stock_code: "000001.SZ",
              stock_name: "平安银行",
              sector_code: "801780",
              sector_name: "閾惰",
              fusion_score: 0.8,
              cycle_score: 0.7,
              lifecourt_proxy_score: 0.6,
              attention_score: 0.5,
              price_confirm_score: 0.4,
              crowding_penalty: 0.1,
              confidence: "medium",
              reason: "Observation-only fusion candidate.",
              evidence: {},
            },
          ],
        },
      }),
    });
    const candidateHistorySpy = vi
      .spyOn(client, "getLivermoreCandidateHistory")
      .mockImplementation(() => new Promise<ApiEnvelope<LivermoreCandidateHistoryPayload>>(() => undefined));
    const strategyScoreSpy = vi
      .spyOn(client, "getLivermoreStrategyScore")
      .mockImplementation(() => new Promise<ApiEnvelope<LivermoreStrategyScorePayload>>(() => undefined));

    renderWorkbenchApp(["/stock-analysis"], { client });

    const digest = await screen.findByTestId("stock-analysis-workbench-digest");
    expect(within(digest).getByTestId("stock-analysis-workbench-fact-candidate-depth")).toHaveTextContent("1 / 1");
    expect(within(digest).queryByTestId("stock-analysis-workbench-fact-factor-candidates")).not.toBeInTheDocument();
    await userEvent.click(screen.getByText("证据与口径明细"));
    await userEvent.click(within(digest).getByRole("button", { name: /完整证据账本/ }));
    expect(within(digest).getByTestId("stock-analysis-workbench-fact-factor-candidates")).not.toHaveAttribute("title");
    expect(within(digest).getByTestId("stock-analysis-workbench-fact-factor-candidates")).not.toHaveTextContent(
      "strategy.result.factor_screen_candidates.items",
    );
    expect(within(digest).getByTestId("stock-analysis-workbench-fact-hybrid-candidates")).toHaveTextContent(
      "rv_hybrid_fusion_candidates_v3",
    );
    expect(digest).not.toHaveTextContent("来源待确认");
    expect(digest).not.toHaveTextContent("position_size_hint");

    await screen.findByTestId("stock-analysis-first-screen-analytics");
    await userEvent.click(screen.getByRole("tab", { name: "策略优先级" }));

    await waitFor(() => expect(strategyScoreSpy).toHaveBeenCalled());
    await waitFor(() => expect(candidateHistorySpy).toHaveBeenCalledWith(expect.objectContaining({ snapshotTo: "2026-04-29" })));
    expect(screen.getByTestId("stock-analysis-workbench-fact-strategy-score")).toHaveTextContent("读取中");
  });

  it("links first-screen fact cards to endpoint evidence and diagnostics", async () => {
    const user = userEvent.setup();
    renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });

    const digest = await screen.findByTestId("stock-analysis-workbench-digest");
    await user.click(screen.getByText("证据与口径明细"));
    await user.click(within(digest).getByRole("button", { name: /完整证据账本/ }));

    const replayFact = await screen.findByTestId("stock-analysis-workbench-fact-replay-evidence");
    await user.click(replayFact);

    expect(replayFact).toHaveAttribute("data-active", "true");
    expect(await screen.findByTestId("stock-analysis-endpoint-evidence-signal-confluence")).toHaveAttribute(
      "data-active",
      "true",
    );

    const candidateHistoryEndpoint = await screen.findByTestId(
      "stock-analysis-endpoint-evidence-candidate-history",
    );
    await user.click(within(candidateHistoryEndpoint).getByRole("button"));
    expect(candidateHistoryEndpoint).toHaveAttribute("data-active", "true");
    expect(replayFact).toHaveAttribute("data-active", "false");
    expect(candidateHistoryEndpoint).not.toHaveAttribute("aria-current");
    expect(within(candidateHistoryEndpoint).getByRole("button")).toHaveAttribute("aria-current", "true");
    expect(screen.getByTestId("stock-analysis-endpoint-evidence-signal-confluence")).toHaveAttribute(
      "data-active",
      "false",
    );

    const representativeFactMappings = [
      ["candidate-history", "candidate-history"],
      ["strategy-score", "strategy-score"],
      ["sector-series", "sector-series"],
      ["proxy-backtest", "cycle-proxy"],
      ["proxy-warnings", "portfolio-proxy"],
      ["optimization-depth", "strategy-optimization"],
    ] as const;

    for (const [factId, endpointKey] of representativeFactMappings) {
      const fact = screen.getByTestId(`stock-analysis-workbench-fact-${factId}`);
      const endpoint = screen.getByTestId(`stock-analysis-endpoint-evidence-${endpointKey}`);

      await user.click(fact);

      expect(fact).toHaveAttribute("data-active", "true");
      expect(endpoint).toHaveAttribute("data-active", "true");
      expect(within(endpoint).getByRole("button")).toHaveAttribute("aria-current", "true");
    }

    const firstScreen = await screen.findByTestId("stock-analysis-first-screen-workbench");
    const diagnosticsEntry = within(firstScreen).getByTestId("stock-analysis-home-rail-diagnostic-entry");
    expect(diagnosticsEntry).toHaveAttribute("aria-expanded", "false");

    const openIssuesFact = screen.getByTestId("stock-analysis-workbench-fact-open-issues");
    await user.click(openIssuesFact);

    expect(openIssuesFact).toHaveAttribute("data-active", "true");
    expect(screen.getByTestId("stock-analysis-endpoint-evidence-strategy")).toHaveAttribute("data-active", "true");
    expect(diagnosticsEntry).toHaveAttribute("aria-expanded", "true");
  });

  it("keeps first-screen content limited to decision, KPI, review summary, and trust rail", async () => {
    renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });

    const firstScreen = await screen.findByTestId("stock-analysis-first-screen-workbench");
    const firstScreenMain = await screen.findByTestId("stock-analysis-first-screen-main");
    const deepZone = await screen.findByTestId("stock-analysis-deep-zone");
    const apiReadinessShell = await screen.findByTestId("stock-analysis-api-readiness-shell");

    expect(within(firstScreenMain).getByTestId("stock-analysis-tailwind-cockpit")).toBeInTheDocument();
    expect(within(firstScreenMain).getByTestId("stock-analysis-kpi-section")).toBeInTheDocument();
    expect(within(firstScreenMain).getByTestId("stock-analysis-review-queue")).toBeInTheDocument();
    const evidenceDetailShell = within(firstScreenMain).getByTestId("stock-analysis-evidence-detail-shell");
    expect(evidenceDetailShell).not.toHaveAttribute("open");
    expect(within(evidenceDetailShell).getByText("证据与口径明细")).toBeInTheDocument();
    const closurePanel = within(evidenceDetailShell).getByTestId("stock-analysis-observation-closure-panel");
    expect(closurePanel).toHaveTextContent("观测闭环总控");
    expect(closurePanel).toHaveTextContent("正式用途：否");
    expect(closurePanel).toHaveTextContent("证据读取覆盖");
    expect(within(closurePanel).getByTestId("stock-analysis-observation-closure-reasons")).toBeInTheDocument();
    expect(within(closurePanel).getByTestId("stock-analysis-observation-closure-actions")).toBeInTheDocument();
    expect(closurePanel).not.toHaveTextContent("闭环完成");
    expect(closurePanel).not.toHaveTextContent("正式通过");
    expect(closurePanel).not.toHaveTextContent("策略通过");
    const firstScreenRail = within(firstScreen).getByTestId("stock-analysis-first-screen-rail");
    expect(firstScreenRail).toBeInTheDocument();
    const diagnosticsEntry = within(firstScreenRail).getByTestId("stock-analysis-home-rail-diagnostic-entry");
    expect(diagnosticsEntry.tagName).toBe("BUTTON");
    expect(diagnosticsEntry).toHaveAttribute("aria-expanded", "false");
    const boundaryRail = within(firstScreenRail).getByTestId("stock-analysis-boundary-rail");
    expect(within(boundaryRail).queryByRole("button")).not.toBeInTheDocument();

    expect(within(firstScreenMain).queryByTestId("stock-analysis-consensus-first-screen")).not.toBeInTheDocument();
    expect(within(firstScreenMain).queryByTestId("stock-analysis-observation-preview")).not.toBeInTheDocument();
    expect(within(firstScreenMain).queryByTestId("stock-analysis-theme-leaders-first-screen")).not.toBeInTheDocument();
    expect(within(firstScreenMain).queryByTestId("stock-analysis-sector-heavyweights-first-screen")).not.toBeInTheDocument();
    expect(within(firstScreenMain).queryByTestId("stock-analysis-sector-strength-panel")).not.toBeInTheDocument();
    expect(within(firstScreenMain).queryByTestId("stock-analysis-first-screen-analytics")).not.toBeInTheDocument();

    expect(apiReadinessShell.tagName).toBe("DETAILS");
    expect(apiReadinessShell).not.toHaveAttribute("open");
    expect(within(apiReadinessShell).getByTestId("stock-analysis-api-readiness-strip")).toBeInTheDocument();
    const deepZoneDetailShell = within(deepZone).getByTestId("stock-analysis-deep-zone-detail-shell");
    expect(deepZoneDetailShell.tagName).toBe("DETAILS");
    expect(deepZoneDetailShell).not.toHaveAttribute("open");
    expect(within(deepZoneDetailShell).getByTestId("stock-analysis-deep-zone-audit-strip")).toBeInTheDocument();
    expect(within(deepZoneDetailShell).getByTestId("stock-analysis-deep-zone-status-flow")).toBeInTheDocument();

    expect(within(deepZone).getByTestId("stock-analysis-consensus-first-screen")).toBeInTheDocument();
    expect(within(deepZone).getByTestId("stock-analysis-observation-preview")).toBeInTheDocument();
    expect(within(deepZone).getByTestId("stock-analysis-theme-leaders-first-screen")).toBeInTheDocument();
    expect(within(deepZone).getByTestId("stock-analysis-sector-heavyweights-first-screen")).toBeInTheDocument();
    expect(within(deepZone).getByTestId("stock-analysis-sector-strength-panel")).toBeInTheDocument();
  });

  it("keeps policy pauses out of first-screen missing evidence reasons", async () => {
    const base = buildStrategyPayload();
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          market_gate: {
            ...base.market_gate,
            state: "OVERHEAT",
            exposure: 0.8,
          },
          diagnostics: [
            {
              severity: "info",
              code: "LIVERMORE_STOCK_PIVOT_PAUSED_BY_POLICY",
              message: "Stock candidate policy exp3b is inactive in OVERHEAT; active market states are HOT/WARM.",
              input_family: "stock_candidate_policy",
            },
          ],
          data_gaps: [
            {
              input_family: "breadth",
              status: "ready",
              evidence: "5-day breadth 0.6000 landed.",
            },
          ],
          unsupported_outputs: [
            {
              key: "stock_candidates",
              reason: "Stock candidate policy exp3b is inactive in OVERHEAT; active market states are HOT/WARM.",
            },
            {
              key: "mean_reversion_candidates",
              reason:
                "Mean reversion watchlist is paused when the market gate is HOT or OVERHEAT because the defended-trend candidate bundle already covers overheated tape.",
            },
            {
              key: "theme_breakout",
              reason: "Theme breakout execution is paused in OVERHEAT; historical replay showed this bucket is draggy.",
            },
            {
              key: "hybrid_fusion",
              reason:
                "Hybrid fusion is observation-only and only emits candidates in WARM/HOT market states; current state is OVERHEAT.",
            },
          ],
          supported_outputs: ["market_gate", "sector_rank", "factor_screen_candidates", "risk_exit"],
          stock_candidates: undefined,
          mean_reversion_candidates: undefined,
          theme_breakout: undefined,
          hybrid_fusion_candidates: undefined,
        }),
      }),
    });

    const closurePanel = await screen.findByTestId("stock-analysis-observation-closure-panel");
    const reasonList = within(closurePanel).getByTestId("stock-analysis-observation-closure-reasons");

    expect(closurePanel).toHaveTextContent("待复核项 0");
    expect(reasonList).toHaveTextContent("暂无新增待复核项");
    expect(reasonList).not.toHaveTextContent("趋势突破策略");
    expect(reasonList).not.toHaveTextContent("融合策略");
  });

  it("renders the first screen as a decision memo with four decision status tiles", async () => {
    renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });

    const memo = await screen.findByTestId("stock-analysis-decision-memo");
    const statusGrid = within(memo).getByTestId("stock-analysis-decision-memo-status-grid");

    expect(within(statusGrid).getByTestId("stock-analysis-decision-gate-tile")).toHaveTextContent("门控");
    expect(within(statusGrid).getByTestId("stock-analysis-decision-closed-loop-tile")).toHaveTextContent("闭环");
    expect(within(statusGrid).getByTestId("stock-analysis-decision-boundary-tile")).toHaveTextContent("边界");
    expect(within(statusGrid).getByTestId("stock-analysis-decision-risk-tile")).toHaveTextContent("风险");

    const ledger = await screen.findByTestId("stock-analysis-evidence-ledger");
    expect(ledger).toHaveTextContent("证据账本");
    expect(ledger.compareDocumentPosition(memo) & Node.DOCUMENT_POSITION_PRECEDING).toBeTruthy();

    const marketContext = await screen.findByTestId("stock-analysis-market-context-strip");
    expect(within(marketContext).getByTestId("stock-analysis-market-context-gate")).toBeInTheDocument();
    expect(within(marketContext).getByTestId("stock-analysis-market-context-exposure")).toBeInTheDocument();
    expect(within(marketContext).getByTestId("stock-analysis-market-context-strong-sector")).toBeInTheDocument();
    expect(within(marketContext).getByTestId("stock-analysis-market-context-weak-sector")).toBeInTheDocument();
    expect(within(marketContext).getByTestId("stock-analysis-market-context-confluence")).toBeInTheDocument();
    expect(within(marketContext).getByTestId("stock-analysis-market-context-risk")).toBeInTheDocument();

    const sourceGate = await screen.findByTestId("stock-analysis-source-gate-strip");
    expect(sourceGate).toHaveTextContent("来源核验");
  });

  it("uses business states for first-screen gate and source tones", async () => {
    const cleanHotPayload = buildStrategyPayload();
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: {
          ...cleanHotPayload,
          market_gate: {
            ...cleanHotPayload.market_gate,
            state: "HOT",
          },
          diagnostics: [],
          data_gaps: [],
          rule_readiness: cleanHotPayload.rule_readiness.map((row) => ({
            ...row,
            status: "ready",
            missing_inputs: [],
          })),
        },
        metaOverrides: {
          quality_flag: "ok",
          vendor_status: "ok",
          fallback_mode: "none",
        },
      }),
    });

    expect(await screen.findByTestId("stock-analysis-decision-gate-tile")).toHaveAttribute("data-tone", "watch");
    expect(screen.getByTestId("stock-analysis-market-context-gate")).toHaveAttribute("data-tone", "watch");
  });

  it("shows degraded source quality as a review state in the first-screen trust strip", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        metaOverrides: {
          quality_flag: "warning",
          vendor_status: "ok",
          fallback_mode: "latest_snapshot",
        },
      }),
    });

    const sourceGate = await screen.findByTestId("stock-analysis-source-gate-strip");
    expect(sourceGate).toHaveAttribute("data-tone", "watch");
    expect(sourceGate).toHaveTextContent("来源需复核");
    expect(sourceGate).toHaveTextContent("数据延迟");
    expect(sourceGate).toHaveTextContent("仅分析使用");
    expect(sourceGate).not.toHaveTextContent("latest_snapshot");
  });

  it("keeps the full review queue folded behind the decision board", async () => {
    renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });

    const queue = await screen.findByTestId("stock-analysis-review-queue");
    const comparison = within(queue).getByTestId("stock-analysis-candidate-comparison");
    const details = within(queue).getByTestId("stock-analysis-review-queue-details");
    const detailsToggle = within(details).getByRole("button", { name: /完整候选队列/ });
    expectElementBefore(comparison, details);
    expect(details).toHaveAttribute("data-open", "false");
    expect(detailsToggle).toHaveAttribute("aria-expanded", "false");
    expect(details).toHaveTextContent("展开看排序明细");
    expect(within(queue).queryByTestId("stock-analysis-review-queue-table")).not.toBeInTheDocument();

    const table = await openReviewQueueTable();
    const sectorFilters = within(queue).getByTestId("stock-sector-filter-chips");
    const headers = within(table)
      .getAllByRole("columnheader")
      .map((header) => header.textContent ?? "");

    expect(details).toHaveAttribute("data-open", "true");
    expect(detailsToggle).toHaveAttribute("aria-expanded", "true");
    expectElementBefore(table, sectorFilters);
    expect(headers).toEqual(
      expect.arrayContaining(["排名", "股票", "行业", "形态", "距观察", "证据", "边界", "失效", "复核"]),
    );
    expect(within(table).getByTestId("stock-candidate-000001.SZ")).toHaveTextContent("Alpha");
    expect(within(table).getByTestId("stock-candidate-review-chart-000001.SZ")).toHaveTextContent("K 线");
    expect(within(queue).getByTestId("stock-analysis-review-queue-table-footer")).toHaveTextContent(
      "显示 1-2 / 2",
    );
    expect(within(queue).queryByTestId("stock-analysis-review-queue-ranking-chart")).not.toBeInTheDocument();
  });

  it("surfaces a short candidate comparison before the detailed review ledger", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    const detailSpy = vi.spyOn(client, "getLivermoreStockDetail");

    renderWorkbenchApp(["/stock-analysis"], { client });

    const queue = await screen.findByTestId("stock-analysis-review-queue");
    const comparison = within(queue).getByTestId("stock-analysis-candidate-comparison");
    const details = within(queue).getByTestId("stock-analysis-review-queue-details");

    expectElementBefore(comparison, details);
    expect(within(queue).queryByTestId("stock-analysis-review-queue-table")).not.toBeInTheDocument();
    expect(within(comparison).getByText("候选横向比较")).toBeInTheDocument();
    expect(within(comparison).getByText("先做取舍，再看单只详情")).toBeInTheDocument();
    expect(within(comparison).getByTestId("stock-analysis-candidate-alternates")).toBeInTheDocument();
    expect(within(comparison).getByTestId("stock-comparison-candidate-row-000001.SZ")).toHaveTextContent("优先复核");
    expect(within(comparison).getByTestId("stock-comparison-candidate-row-000001.SZ")).toHaveTextContent("Alpha");
    expect(within(comparison).getByTestId("stock-comparison-candidate-row-000001.SZ")).toHaveTextContent("0.46%");
    expect(within(comparison).getByTestId("stock-comparison-candidate-row-000001.SZ")).toHaveTextContent("11 条");
    expect(within(comparison).getByTestId("stock-comparison-candidate-row-000001.SZ")).toHaveTextContent("优先理由");
    expect(within(comparison).getByTestId("stock-comparison-candidate-row-000001.SZ")).toHaveTextContent("行业排名第 1");
    expect(within(comparison).getByTestId("stock-comparison-candidate-row-000002.SZ")).toHaveTextContent("Beta");
    const leadCriteria = within(comparison).getByTestId("stock-candidate-criteria-000001.SZ");
    expect(leadCriteria).toHaveTextContent("数据日");
    expect(leadCriteria).toHaveTextContent("2026-04-29");
    expect(leadCriteria).toHaveTextContent("口径");
    expect(leadCriteria).not.toHaveTextContent("证据");
    expect(leadCriteria).not.toHaveTextContent("边界");
    expect(leadCriteria).not.toHaveTextContent("置信度");
    expect(leadCriteria).not.toHaveTextContent("动作");
    expect(comparison).not.toHaveTextContent("边界 边界");

    await user.click(within(comparison).getByTestId("stock-comparison-candidate-review-000001.SZ"));

    await waitFor(() =>
      expect(detailSpy).toHaveBeenCalledWith(
        expect.objectContaining({ stockCode: "000001.SZ" }),
      ),
    );
    expect(await screen.findByTestId("stock-detail-drawer")).toBeInTheDocument();
  });

  it("limits candidate comparison to the first five review candidates", async () => {
    const basePayload = buildStrategyPayload();
    const baseStockCandidates = basePayload.stock_candidates!;
    const baseItems = baseStockCandidates.items;
    const expandedItems = Array.from({ length: 6 }, (_, index) => ({
      ...baseItems[index % baseItems.length],
      rank: index + 1,
      stock_code: `00000${index + 1}.SZ`,
      stock_name: `Candidate ${index + 1}`,
      sector_code: index % 2 === 0 ? "801001" : "801002",
      sector_name: index % 2 === 0 ? "AI" : "新能源车",
      close: 20 + index,
      breakout_level: 19 + index,
    }));

    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          stock_candidates: {
            ...baseStockCandidates,
            input_stock_count: 6,
            candidate_count: 6,
            items: expandedItems,
          },
        }),
      }),
    });

    const comparison = await screen.findByTestId("stock-analysis-candidate-comparison");

    expect(within(comparison).getAllByTestId(/^stock-comparison-candidate-row-/)).toHaveLength(5);
    expect(within(comparison).getByTestId("stock-comparison-candidate-row-000005.SZ")).toBeInTheDocument();
    expect(within(comparison).queryByTestId("stock-comparison-candidate-row-000006.SZ")).not.toBeInTheDocument();
  });

  it("keeps later comparison alternates behind a compact disclosure", () => {
    const component = readFileSync(STOCK_ANALYSIS_CANDIDATE_COMPARISON_PATH, "utf8");
    const css = readFileSync(STOCK_ANALYSIS_CANDIDATE_COMPARISON_CSS_PATH, "utf8");
    const disclosureCssStart = css.indexOf("Candidate comparison alternate disclosure pass");
    const disclosureCss = css.slice(disclosureCssStart);

    expect(disclosureCssStart).toBeGreaterThan(-1);
    expect(component).toContain("const DEFAULT_ALTERNATE_PREVIEW_COUNT = 0;");
    expect(component).toContain("alternateCandidates.slice(0, DEFAULT_ALTERNATE_PREVIEW_COUNT)");
    expect(component).toContain("alternateCandidates.slice(DEFAULT_ALTERNATE_PREVIEW_COUNT)");
    expect(component).toContain('data-testid="stock-analysis-candidate-more-alternates"');
    expect(component.indexOf("visibleAlternateCandidates.map")).toBeLessThan(
      component.indexOf('data-testid="stock-analysis-candidate-more-alternates"'),
    );
    expect(disclosureCss).toContain(".stock-analysis-page__candidate-more-alternates");
    expect(disclosureCss).toMatch(
      /\.stock-analysis-page__candidate-more-alternates-summary\s*\{[\s\S]*?min-height:\s*32px/,
    );
    expect(disclosureCss).toMatch(
      /\.stock-analysis-page__candidate-more-alternates:not\(\[open\]\)[\s\S]*?>\s*\.stock-analysis-page__candidate-more-alternates-grid\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(css).toContain("Candidate comparison mobile density pass");
    expect(css).toContain("Candidate comparison first-choice compact pass");
    expect(css).toMatch(
      /\.stock-analysis-page__candidate-comparison-head\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(css).toMatch(
      /\.stock-analysis-page__candidate-decision-board\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)\s*!important/,
    );
    expect(css).toMatch(
      /\.stock-analysis-page__candidate-lead-main\s*>\s*\.stock-analysis-page__candidate-criteria\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(css).toMatch(
      /@media \(max-width:\s*720px\)[\s\S]*?\.stock-analysis-page__candidate-comparison-rules\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(css).toMatch(
      /\.stock-analysis-page__candidate-more-alternates-summary\s*\{[\s\S]*?min-height:\s*28px/,
    );
    expect(css).toMatch(
      /\.stock-analysis-page__queue-ledger-details\s*>\s*button\s*\{[\s\S]*?display:\s*grid[\s\S]*?min-height:\s*34px/,
    );
    expect(css).toMatch(
      /\.stock-analysis-page__queue-ledger-details\s*>\s*button small\s*\{[\s\S]*?display:\s*none/,
    );
  });

  it("keeps the review queue section header from competing with the lead stock", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const compactStart = css.indexOf("Review queue first-choice compact pass");
    const compactCss = css.slice(compactStart);

    expect(compactStart).toBeGreaterThan(-1);
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-review-queue"\]\s*>\s*\.stock-analysis-page__dh-section-head\s*\{[\s\S]*?min-height:\s*40px\s*!important[\s\S]*?padding:\s*8px 12px\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__dh-section-eyebrow,[\s\S]*?\.stock-analysis-page__dh-section-desc\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(compactCss).toMatch(
      /@media \(max-width:\s*720px\)[\s\S]*?\[data-testid="stock-analysis-review-queue"\]\s*>\s*\.stock-analysis-page__dh-section-head\s*\{[\s\S]*?min-height:\s*34px\s*!important/,
    );
    expect(compactCss).toMatch(
      /@media \(max-width:\s*720px\)[\s\S]*?\.stock-analysis-page__dh-pill\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
  });

  it("explains candidate decision labels with stable review rules", () => {
    render(
      <StockAnalysisCandidateComparison
        candidates={[
          buildLedgerCandidate({
            rank: 1,
            stockCode: "000001.SZ",
            stockName: "Priority Alpha",
            primaryEvidence: [{ key: "turnover", label: "量比", value: "1.8x" }],
            supportingEvidence: [
              { key: "strength", label: "强度", value: "站上 20 日均线" },
              { key: "breadth", label: "扩散", value: "行业扩散 3/5" },
            ],
            boundaryEvidence: [],
          }),
          buildLedgerCandidate({
            rank: 2,
            stockCode: "000002.SZ",
            stockName: "Boundary Beta",
            boundaryEvidence: ["公告催化尚未核实，边界待复核。"],
          }),
          buildLedgerCandidate({
            rank: 3,
            stockCode: "000003.SZ",
            stockName: "Thin Gamma",
            primaryEvidence: [],
            supportingEvidence: [],
            boundaryEvidence: [],
          }),
        ]}
        usesHybridFusion={false}
        asOfLabel="2026-04-29"
        onReviewCandidate={vi.fn()}
      />,
    );

    const comparison = screen.getByTestId("stock-analysis-candidate-comparison");

    expect(within(comparison).getByTestId("stock-analysis-candidate-comparison-rules")).toHaveTextContent(
      "口径：首位优先；边界/事件待核实先等待；证据不足降级观察",
    );
    expect(screen.getByTestId("stock-comparison-candidate-row-000001.SZ")).toHaveTextContent("优先复核");
    expect(screen.getByTestId("stock-comparison-candidate-row-000001.SZ")).toHaveTextContent("首位候选");
    expect(screen.getByTestId("stock-comparison-candidate-row-000001.SZ")).toHaveTextContent("优先理由");
    expect(screen.getByTestId("stock-comparison-candidate-row-000001.SZ")).toHaveTextContent("量比 1.8x");
    expect(screen.getByTestId("stock-comparison-candidate-row-000001.SZ")).toHaveTextContent("强度 站上 20 日均线");
    expect(screen.getByTestId("stock-comparison-candidate-row-000001.SZ")).not.toHaveTextContent("Fusion");
    expect(screen.getByTestId("stock-comparison-candidate-row-000002.SZ")).toHaveTextContent("等待确认");
    expect(screen.getByTestId("stock-comparison-candidate-row-000002.SZ")).toHaveTextContent("边界待核实");
    expect(screen.getByTestId("stock-comparison-candidate-row-000002.SZ")).toHaveTextContent("待核 1 条");
    expect(screen.getByTestId("stock-comparison-candidate-row-000003.SZ")).toHaveTextContent("降级观察");
    expect(screen.getByTestId("stock-comparison-candidate-row-000003.SZ")).toHaveTextContent("证据不足");
    expect(screen.getByTestId("stock-comparison-candidate-row-000003.SZ")).toHaveTextContent("等待证据补齐");
    expect(screen.getByTestId("stock-analysis-candidate-more-alternates")).toHaveTextContent("余 2 只");
    const priorityCriteria = screen.getByTestId("stock-candidate-criteria-000001.SZ");
    expect(priorityCriteria).toHaveTextContent("口径");
    expect(priorityCriteria).toHaveTextContent("2026-04-29");
    expect(priorityCriteria).toHaveTextContent("突破");
    expect(priorityCriteria).not.toHaveTextContent("证据");
    expect(priorityCriteria).not.toHaveTextContent("边界");
    expect(priorityCriteria).not.toHaveTextContent("medium");
    expect(priorityCriteria).not.toHaveTextContent("monitor_only");
  });

  it("shows hybrid confidence and action only for actual hybrid review queues", () => {
    render(
      <StockAnalysisCandidateComparison
        candidates={[
          buildLedgerCandidate({
            stockCode: "000012.SZ",
            stockName: "Core Fusion",
            rawFields: [
              { key: "fusion_score", label: "Fusion", value: "0.365449" },
              { key: "cycle_score", label: "Cycle", value: "0.463321" },
              { key: "lifecourt_proxy_score", label: "Lifecourt", value: "0.183686" },
              { key: "confidence", label: "Confidence", value: "low" },
              { key: "fusion_action", label: "Action", value: "core_plus_trading" },
            ],
          }),
        ]}
        usesHybridFusion
        asOfLabel="2026-06-26"
        onReviewCandidate={vi.fn()}
      />,
    );

    const criteria = screen.getByTestId("stock-candidate-criteria-000012.SZ");
    expect(criteria).toHaveTextContent("置信度");
    expect(criteria).toHaveTextContent("低");
    expect(criteria).toHaveTextContent("动作");
    expect(criteria).toHaveTextContent("重点复核");
    expect(criteria).not.toHaveTextContent("core_plus_trading");
    expect(criteria).not.toHaveTextContent("low");
  });

  it("renders evidence-first narrative in always-visible ledger slots", () => {
    const candidate = buildLedgerCandidate({ sectorCode: "tushare:e4f21ba2b8" });

    render(
      <StockAnalysisCandidateLedgerTable
        candidates={[candidate]}
        usesHybridFusion={false}
        selectedSectorCode={null}
        onReviewCandidate={vi.fn()}
      />,
    );

    const row = screen.getByTestId("stock-candidate-000001.SZ");
    const cells = within(row).getAllByRole("cell");
    const boundaryDetail = cells[2].querySelector(".stock-analysis-page__candidate-ledger-detail");

    expect(cells).toHaveLength(9);
    expect(cells[1]).toHaveTextContent("Alpha");
    expect(row).toHaveTextContent("优先理由");
    expect(row).toHaveTextContent("量比 1.8x");
    expect(row).toHaveTextContent("边界 1 待核");
    expect(cells[1]).toHaveTextContent("复核焦点");
    expect(cells[2]).toHaveTextContent("AI");
    expect(cells[2]).toHaveTextContent("边界");
    expect(cells[2]).toHaveTextContent("公告催化尚未核实");
    expect(cells[2]).not.toHaveTextContent("tushare:e4f21ba2b8");
    expect(cells[3]).toHaveTextContent("证据");
    expect(cells[4]).toHaveTextContent("失效");
    expect(cells[5]).toHaveTextContent("支持");
    expect(cells[8]).toHaveTextContent("K 线");
    expect(cells[8]).toHaveTextContent("待复核");
    expect(boundaryDetail).toHaveAttribute("title", "边界：公告催化尚未核实，边界待复核。");
  });

  it("keeps normal sector codes visible while hiding source traces", () => {
    render(
      <StockAnalysisCandidateLedgerTable
        candidates={[buildLedgerCandidate({ sectorCode: "CS:801001" })]}
        usesHybridFusion={false}
        selectedSectorCode={null}
        onReviewCandidate={vi.fn()}
      />,
    );

    const row = screen.getByTestId("stock-candidate-000001.SZ");
    const cells = within(row).getAllByRole("cell");

    expect(cells[2]).toHaveTextContent("AI");
    expect(cells[2]).toHaveTextContent("CS:801001");
    expect(cells[2]).toHaveTextContent("边界");
  });

  it("shows hybrid F/C/L fallback without leaking vendor placeholders", () => {
    const candidate = buildLedgerCandidate({
      stockCode: "000009.SZ",
      stockName: "Fusion Alpha",
      sectorCode: "801009",
      sectorName: "机器",
      pattern: "待补",
      distanceToBreakoutPct: "融合优先",
      reviewFocus: "Fusion Alpha · 机器 · 距观察位 融合优先",
      boundaryEvidence: [],
      rawFields: [
        { key: "fusion_score", label: "Fusion", value: "pending" },
        { key: "cycle_score", label: "Cycle", value: "NaN" },
        { key: "lifecourt_proxy_score", label: "Lifecourt", value: "" },
        { key: "confidence", label: "Confidence", value: "high" },
        { key: "fusion_action", label: "Action", value: "monitor_only" },
      ],
    });

    render(
      <StockAnalysisCandidateLedgerTable
        candidates={[candidate]}
        usesHybridFusion
        selectedSectorCode={null}
        onReviewCandidate={vi.fn()}
      />,
    );

    const row = screen.getByTestId("stock-candidate-000009.SZ");
    const cells = within(row).getAllByRole("cell");

    expect(cells).toHaveLength(9);
    expect(cells[1]).toHaveTextContent("Fusion Alpha");
    expect(cells[1]).toHaveTextContent("复核焦点");
    expect(cells[2]).toHaveTextContent("机器");
    expect(cells[2]).toHaveTextContent("边界");
    expect(cells[3]).toHaveTextContent("待补");
    expect(cells[3]).toHaveTextContent("证据");
    expect(cells[4]).toHaveTextContent("待补");
    expect(cells[4]).toHaveTextContent("失效");
    expect(cells[5]).toHaveTextContent("待补");
    expect(cells[5]).toHaveTextContent("支持");
    expect(cells[8]).toHaveTextContent("K 线");
    expect(cells[8]).toHaveTextContent("观察");
    expect(cells[8]).not.toHaveTextContent("待复核");
    expect(within(row).getByTestId("stock-candidate-review-chart-000009.SZ")).toHaveAttribute("data-tone", "neutral");
    expect(row).toHaveTextContent("高");
    expect(row).not.toHaveTextContent("high");
    expect(row).not.toHaveTextContent("NaN");
    expect(row).not.toHaveTextContent("monitor_only");
  });

  it("localizes hybrid fusion action enums as review states", () => {
    const candidate = buildLedgerCandidate({
      stockCode: "000012.SZ",
      stockName: "Core Fusion",
      boundaryEvidence: [],
      rawFields: [
        { key: "fusion_score", label: "Fusion", value: "0.365449" },
        { key: "cycle_score", label: "Cycle", value: "0.463321" },
        { key: "lifecourt_proxy_score", label: "Lifecourt", value: "0.183686" },
        { key: "confidence", label: "Confidence", value: "low" },
        { key: "fusion_action", label: "Action", value: "core_plus_trading" },
      ],
    });

    render(
      <StockAnalysisCandidateLedgerTable
        candidates={[candidate]}
        usesHybridFusion
        selectedSectorCode={null}
        onReviewCandidate={vi.fn()}
      />,
    );

    const row = screen.getByTestId("stock-candidate-000012.SZ");
    expect(row).toHaveTextContent("重点复核");
    expect(row).toHaveTextContent("低");
    expect(row).not.toHaveTextContent("core_plus_trading");
    expect(row).not.toHaveTextContent("low");
    expect(within(row).getByTestId("stock-candidate-review-chart-000012.SZ")).toHaveAttribute("data-tone", "positive");
  });

  it("does not escalate hybrid observation rows for generic boundary copy", () => {
    const candidate = buildLedgerCandidate({
      stockCode: "000010.SZ",
      stockName: "Generic Boundary",
      boundaryEvidence: ["仅作观察与复核，不作为执行依据。", "来源命中：待确认"],
      rawFields: [
        { key: "fusion_score", label: "Fusion", value: "0.212345" },
        { key: "cycle_score", label: "Cycle", value: "0.123456" },
        { key: "lifecourt_proxy_score", label: "Lifecourt", value: "0.012345" },
        { key: "confidence", label: "Confidence", value: "低" },
        { key: "fusion_action", label: "Action", value: "observation_only" },
      ],
    });

    render(
      <StockAnalysisCandidateLedgerTable
        candidates={[candidate]}
        usesHybridFusion
        selectedSectorCode={null}
        onReviewCandidate={vi.fn()}
      />,
    );

    const row = screen.getByTestId("stock-candidate-000010.SZ");
    const cells = within(row).getAllByRole("cell");

    expect(cells[2]).toHaveTextContent("边界：观察口径");
    expect(cells[8]).toHaveTextContent("观察");
    expect(cells[8]).not.toHaveTextContent("边界 2");
    expect(within(row).getByTestId("stock-candidate-review-chart-000010.SZ")).toHaveAttribute("data-tone", "neutral");
    expect(row).not.toHaveTextContent("observation_only");
  });

  it("upgrades hybrid rows when meaningful boundary evidence exists", () => {
    const candidate = buildLedgerCandidate({
      stockCode: "000011.SZ",
      stockName: "Boundary Alpha",
      boundaryEvidence: ["公告催化尚未核实，边界待复核。", "仅作观察与复核，不作为执行依据。"],
      rawFields: [
        { key: "fusion_score", label: "Fusion", value: "0.312345" },
        { key: "cycle_score", label: "Cycle", value: "0.223456" },
        { key: "lifecourt_proxy_score", label: "Lifecourt", value: "0.112345" },
        { key: "confidence", label: "Confidence", value: "低" },
        { key: "fusion_action", label: "Action", value: "monitor_only" },
      ],
    });

    render(
      <StockAnalysisCandidateLedgerTable
        candidates={[candidate]}
        usesHybridFusion
        selectedSectorCode={null}
        onReviewCandidate={vi.fn()}
      />,
    );

    const row = screen.getByTestId("stock-candidate-000011.SZ");
    const cells = within(row).getAllByRole("cell");

    expect(cells[2]).toHaveTextContent("公告催化尚未核实");
    expect(cells[7]).toHaveTextContent("观察");
    expect(cells[8]).toHaveTextContent("待复核");
    expect(cells[8]).toHaveTextContent("边界 1");
    expect(within(row).getByTestId("stock-candidate-review-chart-000011.SZ")).toHaveAttribute("data-tone", "warning");
    expect(row).not.toHaveTextContent("monitor_only");
  });

  it("preserves full ledger detail text in titles while truncating inline previews", () => {
    const longReviewFocus =
      "Alpha · AI · 距观察位 MA20 +1.2% · 量价共振已经出现但公告催化、盘口成交顺序和题材扩散仍需人工复核。";
    const candidate = buildLedgerCandidate({
      reviewFocus: longReviewFocus,
    });

    render(
      <StockAnalysisCandidateLedgerTable
        candidates={[candidate]}
        usesHybridFusion={false}
        selectedSectorCode={null}
        onReviewCandidate={vi.fn()}
      />,
    );

    const detail = screen
      .getByTestId("stock-candidate-000001.SZ")
      .querySelector(".stock-analysis-page__candidate-ledger-detail");

    expect(detail).not.toBeNull();
    expect(detail?.textContent).toContain("…");
    expect(detail?.textContent).not.toBe(`复核焦点：${longReviewFocus}`);
    expect(detail).toHaveAttribute("title", `复核焦点：${longReviewFocus}`);
  });

  it("uses the home-style queue screen controls and filters candidates locally", async () => {
    const user = userEvent.setup();
    renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });

    await screen.findByTestId("stock-comparison-candidate-row-000001.SZ");

    const topbar = await screen.findByTestId("market-workbench-topbar");
    const search = within(topbar).getByTestId("stock-analysis-queue-search");
    expect(within(topbar).getByTestId("stock-analysis-complete-evidence-toggle")).toBeInTheDocument();
    expect(within(topbar).getByTestId("stock-analysis-toolbar-data-status")).toHaveTextContent("主包 ready");
    expect(within(topbar).getByTestId("stock-analysis-toolbar-gate-status")).toHaveTextContent("门控");
    expect(within(topbar).getByTestId("stock-analysis-toolbar-loop-status")).toHaveTextContent("闭环");

    const decisionPanel = await screen.findByTestId("stock-analysis-decision-panel");
    expect(await screen.findByTestId("stock-analysis-first-screen-workbench")).toHaveAttribute(
      "data-design-target",
      "product-design-option-1",
    );
    expect(decisionPanel).toHaveTextContent("观测闭环总控");
    expect(decisionPanel).toHaveTextContent("缺口");
    expect(decisionPanel).toHaveTextContent("供数");
    expect(decisionPanel).not.toHaveTextContent("今日复核队列");
    expect(decisionPanel).not.toHaveTextContent("已有候选，进入只读复核队列");
    expect(decisionPanel).not.toHaveTextContent("首位");

    const evidenceLedger = await screen.findByTestId("stock-analysis-evidence-ledger");
    expect(evidenceLedger).toHaveTextContent("补证清单");
    expect(evidenceLedger).toHaveTextContent("关键证据");
    expect(evidenceLedger).toHaveTextContent("风险");
    expect(evidenceLedger).toHaveTextContent("数据口径");

    const queue = await screen.findByTestId("stock-analysis-review-queue");
    const comparison = within(queue).getByTestId("stock-analysis-candidate-comparison");
    expect(within(comparison).getByTestId("stock-comparison-candidate-row-000001.SZ")).toBeInTheDocument();

    await user.type(search, "Beta");

    await waitFor(() => {
      expect(within(comparison).getByTestId("stock-comparison-candidate-row-000002.SZ")).toBeInTheDocument();
    });
    expect(within(comparison).queryByTestId("stock-comparison-candidate-row-000001.SZ")).not.toBeInTheDocument();
    await waitFor(() => {
      expect(decisionPanel).toHaveTextContent(/1.*Beta/);
    });
    expect(decisionPanel).toHaveTextContent("1/2");
    expect(decisionPanel).not.toHaveTextContent("Alpha");
    expect(within(queue).getByTestId("stock-review-filter-status")).toHaveTextContent("显示 1 / 2 个候选");
  });

  it("keeps the first-screen source summarized without exposing the full source trace", async () => {
    const sourceVersion = "choice_stock_vendor_snapshot_20260615_v001";
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        metaOverrides: { source_version: sourceVersion },
      }),
    });

    expect(screen.queryByText(sourceVersion)).not.toBeInTheDocument();
    fireEvent.click(await screen.findByText("证据与口径明细"));
    fireEvent.click(await screen.findByRole("button", { name: /供数与链路/ }));
    expect(await screen.findByText("来源状态")).toBeInTheDocument();
    expect(screen.getByTestId("stock-analysis-api-evidence-strip")).toHaveTextContent("完整来源见诊断");
    expect(screen.queryByText(sourceVersion)).not.toBeInTheDocument();
    expect(screen.queryByTitle(sourceVersion)).not.toBeInTheDocument();
    expect(screen.getByTestId("stock-analysis-source-gate-strip")).not.toHaveAttribute("title");
  });

  it("keeps decision memo tones and mobile review queue readable without horizontal table overflow", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const candidateComparisonCss = readFileSync(STOCK_ANALYSIS_CANDIDATE_COMPARISON_CSS_PATH, "utf8");
    const decisionMemoCss = css.slice(css.indexOf("Investment-bank decision memo pass"));
    const densityCss = css.slice(css.indexOf("Stock-analysis information-density and semantic color pass"));
    const mobileCss = decisionMemoCss.slice(decisionMemoCss.indexOf("@media (max-width: 720px)"));
    const candidateMobileCss = candidateComparisonCss.slice(
      candidateComparisonCss.indexOf("@media (max-width: 720px)"),
    );

    expect(decisionMemoCss).toContain('.stock-analysis-page__decision-memo-tile[data-tone="positive"]');
    expect(densityCss).toContain(".stock-analysis-page__market-context-strip");
    expect(densityCss).toContain('.stock-analysis-page__market-context-strip > div[data-tone="positive"]');
    expect(densityCss).toContain('.stock-analysis-page__market-context-strip > div[data-tone="watch"]');
    expect(densityCss).toContain(".stock-analysis-page__source-gate-strip");
    expect(densityCss).toContain('.stock-analysis-page__source-gate-strip[data-tone="watch"]');
    expect(densityCss).toContain('.stock-analysis-page__source-gate-strip[data-tone="negative"]');
    expect(css).toContain('.stock-analysis-page__endpoint-evidence li[data-active="true"][data-tone="positive"]');
    expect(css).toContain('.stock-analysis-page__endpoint-evidence li[data-active="true"][data-tone="warning"]');
    expect(css).toContain('.stock-analysis-page__endpoint-evidence li[data-active="true"][data-tone="negative"]');
    expect(densityCss).toMatch(
      /@media \(max-width:\s*720px\)[\s\S]*?\.stock-analysis-page__market-context-strip\s*\{[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/,
    );
    expect(densityCss).toMatch(
      /@media \(max-width:\s*720px\)[\s\S]*?\.stock-analysis-page__source-gate-strip small\s*\{[\s\S]*?white-space:\s*normal/,
    );
    expect(mobileCss).toMatch(
      /\.stock-analysis-page__review-table-wrap\s*\{[^}]*overflow-x:\s*hidden/s,
    );
    expect(mobileCss).toMatch(
      /\.stock-analysis-page__review-queue-table\s*\{[^}]*min-width:\s*0/s,
    );
    expect(mobileCss).toMatch(
      /\.stock-analysis-page__review-queue-table thead\s*\{[^}]*display:\s*none/s,
    );
    expect(mobileCss).toMatch(
      /\[data-testid="stock-analysis-review-queue-table"\] tbody\s*\{[\s\S]*?max-height:\s*520px/,
    );
    expect(mobileCss).toMatch(
      /\[data-testid="stock-analysis-review-queue-table"\] tbody tr,[\s\S]*?tbody tr:nth-child\(n \+ 3\)\s*\{[\s\S]*?background:\s*#ffffff\s*!important/,
    );
    expect(mobileCss).toMatch(
      /\[data-testid="stock-analysis-review-queue-table"\] td:nth-child\(7\)\s*\{[\s\S]*?grid-area:\s*confidence\s*!important/,
    );
    expect(mobileCss).toMatch(
      /\[data-testid="stock-analysis-review-queue-table"\]\[data-mode="trend"\] tbody tr,[\s\S]*?grid-template-areas:[\s\S]*?"rank stock review"/,
    );
    expect(mobileCss).toMatch(
      /\[data-testid="stock-analysis-review-queue-table"\]\[data-mode="trend"\] td:nth-child\(3\),[\s\S]*?td:nth-child\(6\)\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(mobileCss).toMatch(
      /\.stock-analysis-page__candidate-ledger-priority\s*\{[\s\S]*?display:\s*-webkit-box\s*!important/,
    );
    expect(candidateMobileCss).toMatch(
      /\.stock-analysis-page__candidate-lead-card\s*\{[\s\S]*?grid-template-columns:\s*44px\s+minmax\(0,\s*1fr\)/,
    );
    expect(candidateMobileCss).toMatch(
      /\.stock-analysis-page__candidate-priority-reason\s*\{[\s\S]*?white-space:\s*nowrap/,
    );
    expect(candidateMobileCss).toMatch(
      /\.stock-analysis-page__candidate-criteria > div:first-child\s*\{[\s\S]*?display:\s*none/,
    );
    expect(candidateMobileCss).toMatch(
      /\.stock-analysis-page__candidate-alternate-card\s*\{[\s\S]*?padding:\s*8px\s+70px\s+8px\s+8px/,
    );
  });

  it("keeps strategy modules summarized by default and opens details on demand", async () => {
    const user = userEvent.setup();
    renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });

    const researchMore = await screen.findByTestId("stock-analysis-strategy-research-more");
    expect(researchMore).not.toHaveAttribute("open");
    await user.click(within(researchMore).getByTestId("stock-analysis-strategy-research-more-summary"));
    expect(researchMore).toHaveAttribute("open");

    const moduleCard = await screen.findByTestId("stock-analysis-market-priority-summary");
    const toggle = within(moduleCard).getByTestId("stock-analysis-strategy-card-market-priority-toggle");
    const detail = within(moduleCard).getByTestId("stock-analysis-strategy-card-market-priority-detail");

    expect(toggle).toHaveAttribute("aria-expanded", "false");
    expect(detail).not.toBeVisible();

    await user.click(toggle);

    expect(toggle).toHaveAttribute("aria-expanded", "true");
    expect(detail).toBeVisible();
  });

  it("does not fan out lower-page diagnostics before the first screen", async () => {
    const client = stockClient();
    const workbenchSpy = vi.spyOn(client, "getStockAnalysisWorkbench");
    const confluenceSpy = vi.spyOn(client, "getLivermoreSignalConfluence");
    const strategyScoreSpy = vi.spyOn(client, "getLivermoreStrategyScore");
    const strategyOptimizationSpy = vi.spyOn(client, "getLivermoreStrategyOptimization");
    const candidateHistorySpy = vi.spyOn(client, "getLivermoreCandidateHistory");
    const cycleProxySpy = vi.spyOn(client, "getLivermoreCycleProxyBacktest");
    const portfolioBacktestSpy = vi.spyOn(client, "getLivermoreCandidateHistoryPortfolioBacktest");

    renderWorkbenchApp(["/stock-analysis"], { client });

    expect(await screen.findByTestId("stock-analysis-tailwind-cockpit")).toBeInTheDocument();
    await waitFor(() => expect(workbenchSpy).toHaveBeenCalledTimes(1));
    await waitFor(() => expect(confluenceSpy).toHaveBeenCalledTimes(1));
    expect(workbenchSpy.mock.calls[0]?.[0]).toEqual({ topK: 3 });
    expect(confluenceSpy).toHaveBeenCalledWith({ asOfDate: "2026-04-29" });
    expect(strategyScoreSpy).not.toHaveBeenCalled();
    expect(strategyOptimizationSpy).not.toHaveBeenCalled();
    expect(candidateHistorySpy).not.toHaveBeenCalled();
    expect(cycleProxySpy).not.toHaveBeenCalled();
    expect(portfolioBacktestSpy).not.toHaveBeenCalled();
  });

  it("shows first-screen empty states when no stock candidates or sectors are available", async () => {
    const emptyStrategy = buildStrategyPayload({
      sector_rank: {
        as_of_date: "2026-04-29",
        formula_version: "rv_livermore_sector_strength_observation_v1",
        is_provisional: false,
        formula_status: "signed_off",
        sector_count: 0,
        excluded_constituent_count: 0,
        excluded_sector_count: 0,
        items: [],
      },
      stock_candidates: {
        as_of_date: "2026-04-29",
        formula_version: "rv_livermore_stock_candidates_bundle_v1",
        market_state: "WARM",
        input_stock_count: 0,
        candidate_count: 0,
        excluded_stock_count: 0,
        insufficient_history_count: 0,
        items: [],
      },
      mean_reversion_candidates: {
        as_of_date: "2026-04-29",
        formula_version: "rv_mean_reversion_candidates_v1",
        market_state: "WARM",
        input_stock_count: 0,
        candidate_count: 0,
        excluded_stock_count: 0,
        insufficient_history_count: 0,
        items: [],
      },
      factor_screen_candidates: {
        as_of_date: "2026-04-29",
        formula_version: "rv_factor_screen_candidates_v1",
        market_state: "WARM",
        input_stock_count: 0,
        candidate_count: 0,
        coverage_note: "factor snapshot no data",
        items: [],
      },
      theme_breakout: {
        as_of_date: "2026-04-29",
        formula_version: "rv_theme_breakout_v1",
        is_proxy: true,
        theme_count: 0,
        items: [],
      },
    });

    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({ strategy: emptyStrategy }),
    });

    expect(await screen.findByTestId("stock-analysis-review-queue-empty")).toBeInTheDocument();
    expect(screen.getByTestId("stock-analysis-review-queue-empty")).toHaveTextContent("0");
    expect(screen.queryByTestId("stock-analysis-review-workbench-strip")).not.toBeInTheDocument();
    expect(screen.queryByTestId("stock-candidate-000001.SZ")).not.toBeInTheDocument();
    expect(screen.queryByTestId("stock-analysis-sector-review-link")).not.toBeInTheDocument();
    expect(screen.getByTestId("stock-analysis-factor-preview-empty")).toHaveTextContent("0");
    expect(screen.getByTestId("stock-analysis-mean-reversion-preview-empty")).toHaveTextContent("0");
    expect(screen.getByTestId("stock-analysis-theme-leader-empty")).toHaveTextContent("0");
    expect(screen.getByTestId("stock-analysis-sector-heavyweight-empty")).toBeInTheDocument();
    expect(screen.getByTestId("stock-analysis-consensus-first-screen-empty")).toHaveTextContent("0");
  });

  it("scopes shell compression to the stock-analysis route", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");

    expect(css).toContain("@media (min-width: 721px)");
    expect(css).toContain(
      '.workbench-shell-grid--desktop-aligned:has([data-testid="stock-analysis-page"])',
    );
    expect(css).toContain(".workbench-shell-grid--stock-analysis");
    expect(css).toContain('[data-testid="workbench-section-subnav"]');
    expect(css).toContain('[data-testid="workbench-governance-banner"]');
    expect(css).toContain(".stock-analysis-page__dh-topbar");
    expect(css).toContain("box-shadow: none");
    expect(css).toContain(".stock-analysis-page__toolbar-title");
    expect(css).toContain(".stock-analysis-page__toolbar-pill");
  });

  it("keeps the stock-analysis toolbar title from breaking on tablet width", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");

    expect(css).toContain(".stock-analysis-page__header h1");
    expect(css).toContain("white-space: nowrap");
  });

  it("keeps tablet toolbar dates readable and commands icon-led", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const tabletTopbarStart = css.indexOf("Tablet topbar pass");
    const tabletTopbarCss = css.slice(tabletTopbarStart);

    expect(tabletTopbarStart).toBeGreaterThan(-1);
    expect(tabletTopbarCss).toMatch(
      /\.stock-analysis-page__toolbar-info\s*\{[\s\S]*?grid-template-columns:\s*minmax\(176px,\s*2fr\)\s*minmax\(104px,\s*1fr\)\s*minmax\(92px,\s*1fr\)/,
    );
    expect(tabletTopbarCss).toMatch(
      /\.stock-analysis-page__toolbar-pill:nth-of-type\(2\)\s*\{[\s\S]*?min-width:\s*176px/,
    );
    expect(tabletTopbarCss).toMatch(
      /\.stock-analysis-page__header-controls\s*\{[\s\S]*?grid-template-columns:\s*42px\s*minmax\(132px,\s*1fr\)\s*42px/,
    );
    expect(tabletTopbarCss).toMatch(
      /\.stock-analysis-page__dh-topbar-btn\.ant-btn\s*>\s*span:not\(\.ant-btn-icon\):not\(\.anticon\)\s*\{[\s\S]*?clip:\s*rect\(0 0 0 0\)/,
    );
    expect(tabletTopbarCss).toMatch(
      /\.stock-analysis-page__toolbar-pill:nth-of-type\(5\),[\s\S]*?\.stock-analysis-page__generated-at\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
  });

  it("keeps narrow hero status strip short and numeric", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const narrowHeroStart = css.indexOf("Narrow hero pass");
    const narrowHeroCss = css.slice(narrowHeroStart);

    expect(narrowHeroStart).toBeGreaterThan(-1);
    expect(narrowHeroCss).toMatch(
      /\.stock-analysis-page__dh-hero-status-strip\s*\{[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/,
    );
    expect(narrowHeroCss).toMatch(
      /\.stock-analysis-page__dh-hero-status-strip span:nth-child\(n \+ 5\)\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
  });

  it("keeps narrow decision verdict compact instead of sentence-led", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const narrowRailStart = css.indexOf("Narrow decision rail pass");
    const narrowRailCss = css.slice(narrowRailStart);

    expect(narrowRailStart).toBeGreaterThan(-1);
    expect(narrowRailCss).toMatch(
      /\.stock-analysis-page__rail-verdict\s*\{[\s\S]*?grid-template-columns:\s*22px\s*minmax\(0,\s*1fr\)\s*auto/,
    );
    expect(narrowRailCss).toMatch(
      /\.stock-analysis-page__rail-verdict\s*\{[\s\S]*?align-items:\s*center/,
    );
    expect(narrowRailCss).toMatch(
      /\.stock-analysis-page__rail-verdict-body strong\s*\{[\s\S]*?display:\s*none/,
    );
    expect(narrowRailCss).toMatch(
      /\.stock-analysis-page__rail-verdict-kpis\s*\{[\s\S]*?grid-template-columns:\s*repeat\(2,\s*46px\)/,
    );
  });

  it("keeps narrow KPI strip from repeating hero and decision states", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const narrowKpiStart = css.indexOf("Narrow KPI pass");
    const narrowKpiCss = css.slice(narrowKpiStart);

    expect(narrowKpiStart).toBeGreaterThan(-1);
    expect(narrowKpiCss).toMatch(
      /\[data-testid="stock-analysis-kpi-market-state"\],[\s\S]*?\[data-testid="stock-analysis-kpi-closed-loop"\]\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(narrowKpiCss).toMatch(
      /\.stock-analysis-page__dh-kpi-strip\s*\{[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/,
    );
  });

  it("removes repeated rail chrome on narrow screens", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const narrowRailChromeStart = css.indexOf("Narrow rail chrome pass");
    const narrowRailChromeCss = css.slice(narrowRailChromeStart);

    expect(narrowRailChromeStart).toBeGreaterThan(-1);
    expect(narrowRailChromeCss).toMatch(
      /\[data-testid="stock-analysis-first-screen-rail"\]\s*>\s*\.stock-analysis-page__dh-section-eyebrow\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
  });

  it("keeps the first screen focused on decision, KPI, review summary, and trust rail", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const consolidationStart = css.indexOf("Stock-analysis first-screen consolidation");
    const consolidationCss = css.slice(consolidationStart);

    expect(consolidationStart).toBeGreaterThan(-1);
    expect(consolidationCss).toMatch(
      /\.stock-analysis-page__uses-home-shell\.stock-analysis-page__first-screen\s*\{[\s\S]*?display:\s*grid\s*!important[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)\s*316px\s*!important/,
    );
    expect(consolidationCss).toMatch(
      /\.stock-analysis-page__uses-home-shell\s*>\s*\.stock-analysis-page__first-screen-main\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)\s*!important/,
    );
    expect(consolidationCss).toMatch(/\.stock-analysis-page__review-summary-stack\s*\{[\s\S]*?display:\s*grid/);
    expect(consolidationCss).toMatch(
      /\.stock-analysis-page__uses-home-shell\s*\[data-testid="stock-analysis-review-queue"\]\s*\{[\s\S]*?max-height:\s*none\s*!important[\s\S]*?overflow:\s*visible\s*!important/,
    );
    expect(consolidationCss).toMatch(
      /@media \(max-width:\s*1130px\)[\s\S]*?\.stock-analysis-page__uses-home-shell\.stock-analysis-page__first-screen\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)\s*!important/,
    );
  });

  it("compresses the stock-analysis toolbar, rail, and queue footer on the first screen", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const loopPassStart = css.indexOf("IB queue desk loop pass 2");
    const loopPassCss = css.slice(loopPassStart);

    expect(loopPassStart).toBeGreaterThan(-1);
    expect(loopPassCss).toMatch(
      /\[data-testid="market-workbench-frame"\]\[data-page-key="stock-analysis"\][\s\S]*?\[data-testid="market-workbench-topbar"\]\s*>\s*div:first-child\s*>\s*div:first-child\s*>\s*span,[\s\S]*?display:\s*none\s*!important/,
    );
    expect(loopPassCss).toMatch(/\.stock-analysis-page__stale-banner--compressed\s*\{[\s\S]*?clip:\s*rect\(0 0 0 0\)/);
    expect(loopPassCss).toMatch(/\.stock-analysis-page__review-table-footer\s*\{/);
    expect(loopPassCss).toMatch(
      /@media \(min-width:\s*721px\)[\s\S]*?\.stock-analysis-page__review-queue-table tbody tr:nth-child\(n \+ 6\)\s*\{[\s\S]*?display:\s*none/,
    );
    expect(loopPassCss).toMatch(
      /@media \(max-width:\s*720px\)[\s\S]*?max-height:\s*160px/,
    );
  });

  it("keeps the mobile stock toolbar tight enough to leave room for the queue", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const mobileToolbarStart = css.indexOf("Mobile stock toolbar density pass");
    const mobileToolbarCss = css.slice(mobileToolbarStart);

    expect(mobileToolbarStart).toBeGreaterThan(-1);
    expect(mobileToolbarCss).toMatch(
      /@media \(max-width:\s*720px\)[\s\S]*?\[data-testid="market-workbench-topbar"\]\s*\{[\s\S]*?padding:\s*8px 10px\s*!important/,
    );
    expect(mobileToolbarCss).toMatch(
      /\.stock-analysis-page__workbench-actions\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)\s*30px\s*30px\s*30px\s*!important[\s\S]*?grid-template-rows:\s*30px\s*30px\s*!important/,
    );
    expect(mobileToolbarCss).toMatch(
      /\.stock-analysis-page__queue-search\s*\{[\s\S]*?height:\s*30px\s*!important[\s\S]*?padding:\s*0 8px\s*!important/,
    );
  });

  it("keeps lower supply diagnostics behind disclosures so stock selection moves up", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const disclosureStart = css.indexOf("Lower audit disclosure pass");
    const disclosureCss = css.slice(disclosureStart);

    expect(disclosureStart).toBeGreaterThan(-1);
    expect(disclosureCss).toContain(".stock-analysis-page__api-readiness-disclosure");
    expect(disclosureCss).toContain(".stock-analysis-page__deep-zone-detail-shell");
    expect(disclosureCss).toMatch(
      /\.stock-analysis-page__api-readiness-disclosure\s*\{[\s\S]*?order:\s*2;/,
    );
    expect(disclosureCss).toMatch(/\.stock-analysis-page__workspace\s*\{[\s\S]*?order:\s*1;/);
    expect(disclosureCss).toMatch(
      /\.stock-analysis-page__deep-zone-header--compact\s*\{[\s\S]*?padding:\s*10px 12px\s*!important/,
    );
    expect(disclosureCss).toContain("Deep-zone supply header compact pass");
    expect(disclosureCss).toMatch(
      /\.stock-analysis-page__deep-zone\s*>\s*\.stock-analysis-page__deep-zone-header--compact\s*\{[\s\S]*?margin-bottom:\s*8px\s*!important[\s\S]*?padding:\s*6px 8px\s*!important/,
    );
    expect(disclosureCss).toMatch(
      /\.stock-analysis-page__deep-zone\s*>\s*\.stock-analysis-page__deep-zone-header--compact h2\s*\{[\s\S]*?clip-path:\s*inset\(50%\)\s*!important/,
    );
    expect(disclosureCss).toMatch(
      /\.stock-analysis-page__deep-zone\s*>\s*\.stock-analysis-page__deep-zone-header--compact \[data-testid="stock-analysis-deep-zone-gate-summary"\]\s*\{[\s\S]*?min-height:\s*22px\s*!important[\s\S]*?background:\s*var\(--ib-surface\)\s*!important[\s\S]*?white-space:\s*nowrap\s*!important/,
    );
    expect(disclosureCss).toMatch(
      /\.stock-analysis-page__deep-zone\s*>\s*\.stock-analysis-page__deep-zone-header--compact \.stock-analysis-page__deep-zone-detail-summary\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)\s*auto\s*!important[\s\S]*?min-height:\s*26px\s*!important/,
    );
    expect(disclosureCss).toMatch(
      /\.stock-analysis-page__deep-zone\s*>\s*\[data-testid="stock-analysis-stock-selection"\]\s*\{[\s\S]*?grid-row:\s*auto\s*!important[\s\S]*?order:\s*1\s*!important/,
    );
    expect(disclosureCss).toMatch(
      /\.stock-analysis-page__deep-zone\s*>\s*\.stock-analysis-page__strategy-research-more\s*\{[\s\S]*?grid-row:\s*auto\s*!important[\s\S]*?order:\s*2\s*!important/,
    );
    expect(disclosureCss).toMatch(
      /\.stock-analysis-page__api-readiness-summary,[\s\S]*?\.stock-analysis-page__deep-zone-detail-summary\s*\{[\s\S]*?min-height:\s*38px/,
    );
    expect(disclosureCss).toMatch(
      /\.stock-analysis-page__api-readiness-disclosure:not\(\[open\]\)\s*>\s*\.stock-analysis-page__api-readiness-detail,[\s\S]*?display:\s*none\s*!important/,
    );
    expect(disclosureCss).toContain("Mobile supply diagnostics compact pass");
    expect(disclosureCss).toMatch(
      /\.stock-analysis-page__api-readiness-disclosure:not\(\[open\]\)\s*\{[\s\S]*?max-height:\s*30px\s*!important[\s\S]*?margin-top:\s*4px\s*!important[\s\S]*?margin-bottom:\s*0\s*!important[\s\S]*?overflow:\s*hidden\s*!important/,
    );
    expect(disclosureCss).toMatch(
      /\.stock-analysis-page__api-readiness-disclosure:not\(\[open\]\)\s*\+\s*\.stock-analysis-page__workspace\s*\{[\s\S]*?margin-top:\s*-8px\s*!important/,
    );
    expect(disclosureCss).toMatch(
      /\.stock-analysis-page__api-readiness-summary\s*\{[\s\S]*?min-height:\s*28px\s*!important[\s\S]*?padding:\s*3px 8px\s*!important/,
    );
    expect(disclosureCss).toMatch(
      /\.stock-analysis-page__deep-zone:not\(:has\(\.stock-analysis-page__deep-zone-detail-shell\[open\]\)\)\s*\{[\s\S]*?gap:\s*2px\s*!important/,
    );
    expect(disclosureCss).toMatch(
      /\.stock-analysis-page__deep-zone\s*>\s*\.stock-analysis-page__deep-zone-header--compact:not\(:has\(\.stock-analysis-page__deep-zone-detail-shell\[open\]\)\)\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)\s*28px\s*!important[\s\S]*?max-height:\s*32px\s*!important[\s\S]*?margin-bottom:\s*0\s*!important/,
    );
    expect(disclosureCss).toMatch(
      /\.stock-analysis-page__deep-zone-detail-summary small\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
  });

  it("keeps strategy lens evidence metadata behind a compact disclosure", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const strategyMetaStart = css.indexOf("Strategy lens metadata disclosure pass");
    const strategyMetaCss = css.slice(strategyMetaStart);

    expect(strategyMetaStart).toBeGreaterThan(-1);
    expect(strategyMetaCss).toContain(".stock-analysis-page__strategy-lens-meta");
    expect(strategyMetaCss).toMatch(
      /\.stock-analysis-page__strategy-lens-meta-summary\s*\{[\s\S]*?min-height:\s*30px/,
    );
    expect(strategyMetaCss).toMatch(
      /\.stock-analysis-page__strategy-lens-meta:not\(\[open\]\)\s*>\s*\.stock-analysis-page__strategy-lens-ledger,[\s\S]*?\.stock-analysis-page__strategy-lens-meta:not\(\[open\]\)\s*>\s*\.stock-analysis-page__strategy-lens-evidence\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
  });

  it("keeps strategy lens candidate lists to the top item by default", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const component = readFileSync(STOCK_ANALYSIS_STRATEGY_LENS_SECTION_PATH, "utf8");
    const candidateDisclosureStart = css.indexOf("Strategy lens candidate disclosure pass");
    const candidateDisclosureCss = css.slice(candidateDisclosureStart);

    expect(candidateDisclosureStart).toBeGreaterThan(-1);
    expect(component).toContain("const STRATEGY_LENS_DEFAULT_CANDIDATE_COUNT = 1;");
    expect(component).toContain("item.candidates.slice(0, STRATEGY_LENS_DEFAULT_CANDIDATE_COUNT).map");
    expect(component).toContain("item.candidates.slice(STRATEGY_LENS_DEFAULT_CANDIDATE_COUNT).map");
    expect(candidateDisclosureCss).toContain(".stock-analysis-page__strategy-lens-candidates-more");
    expect(candidateDisclosureCss).toMatch(
      /\.stock-analysis-page__strategy-lens-candidates-more-summary\s*\{[\s\S]*?min-height:\s*28px/,
    );
    expect(candidateDisclosureCss).toMatch(
      /\.stock-analysis-page__strategy-lens-candidates-more:not\(\[open\]\)\s*>\s*\.stock-analysis-page__strategy-lens-candidates--extra\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
  });

  it("keeps later strategy lenses behind a compact disclosure by default", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const component = readFileSync(STOCK_ANALYSIS_STRATEGY_LENS_SECTION_PATH, "utf8");
    const strategyDisclosureStart = css.indexOf("Strategy lens candidate-strategy disclosure pass");
    const strategyDisclosureCss = css.slice(strategyDisclosureStart);

    expect(strategyDisclosureStart).toBeGreaterThan(-1);
    expect(component).toContain("const STRATEGY_LENS_DEFAULT_CARD_COUNT = 1;");
    expect(component).toContain("candidateItems.slice(0, STRATEGY_LENS_DEFAULT_CARD_COUNT)");
    expect(component).toContain("candidateItems.slice(STRATEGY_LENS_DEFAULT_CARD_COUNT)");
    expect(component).toContain('data-testid="stock-analysis-strategy-lens-more-strategies"');
    expect(component.indexOf("visibleItems.map(renderStrategyCard)")).toBeLessThan(
      component.indexOf('data-testid="stock-analysis-strategy-lens-more-strategies"'),
    );
    expect(strategyDisclosureCss).toContain(".stock-analysis-page__strategy-lens-more-strategies");
    expect(strategyDisclosureCss).toMatch(
      /\.stock-analysis-page__strategy-lens-more-strategies-summary\s*\{[\s\S]*?min-height:\s*32px/,
    );
    expect(strategyDisclosureCss).toMatch(
      /\.stock-analysis-page__strategy-lens-more-strategies:not\(\[open\]\)\s*>\s*\.stock-analysis-page__strategy-lens-more-strategies-grid\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
  });

  it("keeps default strategy lens cards as compact stock-picking entries", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const compactStart = css.indexOf("Strategy lens default-entry compact pass");
    const compactCss = css.slice(compactStart);

    expect(compactStart).toBeGreaterThan(-1);
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-strategy-lens"\]\s*\.stock-analysis-page__strategy-lens-card\s*\{[\s\S]*?gap:\s*5px;[\s\S]*?min-height:\s*0;[\s\S]*?padding:\s*8px;[\s\S]*?background:\s*var\(--ib-paper\)\s*!important;/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-strategy-lens"\]\s*\.stock-analysis-page__strategy-lens-subtitle\s*\{[\s\S]*?display:\s*none;/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-strategy-lens"\]\s*\.stock-analysis-page__strategy-lens-grid:has\(>\s*\.stock-analysis-page__strategy-lens-card:only-child\)\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\);/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-strategy-lens"\]\s*\.stock-analysis-page__strategy-lens-detail\s*\{[\s\S]*?-webkit-line-clamp:\s*1;/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-strategy-lens"\]\s*\.stock-analysis-page__strategy-lens-candidates li > span:not\(\.stock-analysis-page__strategy-lens-rank\),[\s\S]*?\.stock-analysis-page__strategy-lens-candidates em\s*\{[\s\S]*?display:\s*none;/,
    );
    expect(compactCss).toContain("Strategy lens first-candidate row pass");
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-strategy-lens"\]\s*\.stock-analysis-page__strategy-lens-card\s*\{[\s\S]*?grid-template-columns:\s*minmax\(116px,\s*0\.9fr\)[\s\S]*?minmax\(168px,\s*1\.4fr\)[\s\S]*?align-items:\s*center;[\s\S]*?gap:\s*4px\s*8px;/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-strategy-lens"\]\s*\.stock-analysis-page__strategy-lens-eyebrow\s*\{[\s\S]*?display:\s*none;/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-strategy-lens"\]\s*\.stock-analysis-page__strategy-lens-detail\s*\{[\s\S]*?display:\s*none;/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-strategy-lens"\]\s*\.stock-analysis-page__strategy-lens-meta-summary span\s*\{[\s\S]*?display:\s*none;/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-strategy-lens"\]\s*\.stock-analysis-page__strategy-lens-meter\s*\{[\s\S]*?grid-column:\s*1\s*\/\s*-1;[\s\S]*?height:\s*3px;/,
    );
    expect(compactCss).toContain("Strategy lens mobile-decision row pass");
    expect(compactCss).toMatch(
      /@media\s*\(max-width:\s*720px\)\s*\{[\s\S]*?\[data-testid="stock-analysis-strategy-lens"\]\s*\.stock-analysis-page__strategy-lens-header\s*\{[\s\S]*?flex-direction:\s*row;/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-strategy-lens"\]\s*\.stock-analysis-page__strategy-lens-card\s*\{[\s\S]*?grid-template-areas:[\s\S]*?"head candidate main"[\s\S]*?"meta more more"[\s\S]*?"meter meter meter";/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-strategy-lens"\]\s*\.stock-analysis-page__strategy-lens-meta-summary small\s*\{[\s\S]*?display:\s*none\s*!important;/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-strategy-lens"\]\s*\.stock-analysis-page__strategy-lens-card:has\(\.stock-analysis-page__strategy-lens-meta\[open\]\),[\s\S]*?grid-template-areas:[\s\S]*?"head main"[\s\S]*?"meta meta"[\s\S]*?"candidate candidate"[\s\S]*?"more more"[\s\S]*?"meter meter";[\s\S]*?overflow:\s*visible;/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-strategy-lens"\]\s*\.stock-analysis-page__strategy-lens-card:has\(\.stock-analysis-page__strategy-lens-meta\[open\]\)\s*\.stock-analysis-page__strategy-lens-meta-summary small,[\s\S]*?display:\s*block\s*!important;/,
    );
  });

  it("keeps zero-hit consensus scans compact in the deep-review workspace", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const compactStart = css.indexOf("Consensus empty scan compact pass");
    const compactCss = css.slice(compactStart);

    expect(compactStart).toBeGreaterThan(-1);
    expect(compactCss).toMatch(
      /\.stock-analysis-page__deep-review-workspace\s*\[data-testid="stock-analysis-consensus-first-screen"\]\s*\[data-testid="stock-analysis-consensus-empty-scan"\]\s*\{[\s\S]*?display:\s*grid\s*!important[\s\S]*?grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__deep-review-workspace\s*\[data-testid="stock-analysis-consensus-first-screen"\]\s*\[data-testid="stock-analysis-consensus-empty-scan"\]\s*\[role="status"\]\s*\{[\s\S]*?min-height:\s*42px\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__deep-review-workspace\s*\[data-testid="stock-analysis-consensus-first-screen"\]\s*\[data-testid="stock-analysis-consensus-empty-scan"\]\s*\.stock-analysis-page__compact-status-tile__label,[\s\S]*?\.stock-analysis-page__compact-status-tile__value\s*\{[\s\S]*?white-space:\s*nowrap\s*!important/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-consensus-first-screen"\]\s*\{[\s\S]*?min-height:\s*156px\s*!important/,
    );
    expect(compactCss).toContain("Consensus zero-state background-entry compact pass");
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-consensus-first-screen"\]:has\(\[data-testid="stock-analysis-consensus-empty-scan"\]\)\s*\{[\s\S]*?min-height:\s*0\s*!important[\s\S]*?max-height:\s*92px\s*!important[\s\S]*?padding:\s*8px 10px\s*!important/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-consensus-first-screen"\]:has\(\[data-testid="stock-analysis-consensus-empty-scan"\]\)\s*>\s*\.stock-analysis-page__dh-section-head\s*\{[\s\S]*?min-height:\s*24px\s*!important[\s\S]*?border-bottom:\s*0\s*!important/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-consensus-first-screen"\]:has\(\[data-testid="stock-analysis-consensus-empty-scan"\]\)\s*\.stock-analysis-page__consensus-workbench-strip\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-consensus-first-screen"\]:has\(\[data-testid="stock-analysis-consensus-empty-scan"\]\)[\s\S]*?\[data-testid="stock-analysis-consensus-empty-scan"\]\s*\{[\s\S]*?grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)\s*!important[\s\S]*?min-height:\s*28px\s*!important/,
    );
    expect(compactCss).toMatch(
      /@media\s*\(max-width:\s*720px\)\s*\{[\s\S]*?\[data-testid="stock-analysis-consensus-first-screen"\]:has\(\[data-testid="stock-analysis-consensus-empty-scan"\]\)\s*\{[\s\S]*?max-height:\s*84px\s*!important/,
    );
  });

  it("keeps zero-candidate strategy cards behind a collapsed background disclosure", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const component = readFileSync(STOCK_ANALYSIS_STRATEGY_LENS_SECTION_PATH, "utf8");
    const emptyStrategyDisclosureStart = css.indexOf("Strategy lens empty-strategy disclosure pass");
    const emptyStrategyDisclosureCss = css.slice(emptyStrategyDisclosureStart);

    expect(emptyStrategyDisclosureStart).toBeGreaterThan(-1);
    expect(component).toContain("const candidateItems = items.filter((item) => item.candidates.length > 0);");
    expect(component).toContain("const emptyCandidateItems = items.filter((item) => item.candidates.length === 0);");
    expect(component).toContain("const backgroundItems = candidateItems.length > 0 ? emptyCandidateItems : [];");
    expect(component).toContain("visibleItems.map(renderStrategyCard)");
    expect(component).toContain('data-testid="stock-analysis-strategy-lens-empty-strategies"');
    expect(component).toContain("backgroundItems.map(renderStrategyCard)");
    expect(component.indexOf("visibleItems.map(renderStrategyCard)")).toBeLessThan(
      component.indexOf('data-testid="stock-analysis-strategy-lens-empty-strategies"'),
    );
    expect(emptyStrategyDisclosureCss).toContain(".stock-analysis-page__strategy-lens-empty-strategies");
    expect(emptyStrategyDisclosureCss).toMatch(
      /\.stock-analysis-page__strategy-lens-empty-strategies-summary\s*\{[\s\S]*?min-height:\s*32px/,
    );
    expect(emptyStrategyDisclosureCss).toMatch(
      /\.stock-analysis-page__strategy-lens-empty-strategies:not\(\[open\]\)\s*>\s*\.stock-analysis-page__strategy-lens-empty-strategies-grid\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
  });

  it("keeps observation preview candidates to the top item by default", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const component = readFileSync(STOCK_ANALYSIS_OBSERVATION_PREVIEW_PATH, "utf8");
    const disclosureStart = css.indexOf("Observation preview candidate disclosure pass");
    const disclosureCss = css.slice(disclosureStart);

    expect(disclosureStart).toBeGreaterThan(-1);
    expect(component).toContain("const OBSERVATION_PREVIEW_DEFAULT_COUNT = 1;");
    expect(component).toContain("factorPreviewItems.slice(0, OBSERVATION_PREVIEW_DEFAULT_COUNT)");
    expect(component).toContain("factorPreviewItems.slice(OBSERVATION_PREVIEW_DEFAULT_COUNT)");
    expect(component).toContain("meanReversionPreviewItems.slice(0, OBSERVATION_PREVIEW_DEFAULT_COUNT)");
    expect(component).toContain("meanReversionPreviewItems.slice(OBSERVATION_PREVIEW_DEFAULT_COUNT)");
    expect(component).toContain('data-testid="stock-analysis-factor-preview-more"');
    expect(component).toContain('data-testid="stock-analysis-mean-reversion-preview-more"');
    expect(css).not.toContain(
      '[data-testid="stock-analysis-observation-preview"] .stock-analysis-page__table-wrap,\n  [data-testid="stock-analysis-theme-leaders-first-screen"]',
    );
    expect(css).not.toContain(
      '[data-testid="stock-analysis-observation-preview"] .stock-analysis-page__list li:nth-child(n + 3)',
    );
    expect(css).not.toContain(
      '[data-testid="stock-analysis-observation-preview"] .stock-analysis-page__list li:nth-child(n + 2)',
    );
    expect(disclosureCss).toContain(".stock-analysis-page__observation-preview-more");
    expect(disclosureCss).toMatch(
      /\.stock-analysis-page__observation-preview-more-summary\s*\{[\s\S]*?min-height:\s*28px/,
    );
    expect(disclosureCss).toMatch(
      /\.stock-analysis-page__observation-preview-more:not\(\[open\]\)\s*>\s*\.stock-analysis-page__observation-preview-extra\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(disclosureCss).toContain("Observation pool secondary compact pass");
    expect(disclosureCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]\s*\{[\s\S]*?min-height:\s*188px\s*!important/,
    );
    expect(disclosureCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]\s*>\s*\.stock-analysis-page__dh-section-head h2\s*\{[\s\S]*?color:\s*#0f172a\s*!important/,
    );
    expect(disclosureCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]\s*\.stock-analysis-page__observation-preview-panel\s*\{[\s\S]*?padding:\s*8px\s*!important/,
    );
    expect(disclosureCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]\s*\.stock-analysis-page__observation-preview-more-summary\s*\{[\s\S]*?min-height:\s*24px\s*!important[\s\S]*?padding:\s*3px 7px\s*!important/,
    );
    expect(disclosureCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]:has\(\.stock-analysis-page__observation-preview-more\[open\]\)\s*\{[\s\S]*?min-height:\s*0\s*!important[\s\S]*?overflow:\s*visible\s*!important/,
    );
    expect(disclosureCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]:has\(\.stock-analysis-page__observation-preview-more\[open\]\)\s*\.stock-analysis-page__observation-preview-grid\s*\{[\s\S]*?flex:\s*0 0 auto\s*!important[\s\S]*?overflow:\s*visible\s*!important/,
    );
    expect(disclosureCss).toContain("Observation pool default-entry compact pass");
    expect(disclosureCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]\s*>\s*\.stock-analysis-page__dh-section-head\s*\{[\s\S]*?min-height:\s*32px\s*!important[\s\S]*?border-bottom:\s*0\s*!important/,
    );
    expect(disclosureCss).toMatch(
      /\.stock-analysis-page__dh-section-eyebrow,[\s\S]*?\.stock-analysis-page__lower-signal-strip\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(disclosureCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]\s*\.stock-analysis-page__observation-preview-grid\s*\{[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)\s*!important/,
    );
    expect(disclosureCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]\s*\.stock-analysis-page__observation-preview-panel\s*\{[\s\S]*?grid-template-columns:\s*minmax\(58px,\s*72px\)\s*minmax\(0,\s*1fr\)\s*auto/,
    );
    expect(disclosureCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]\s*\.stock-analysis-page__table thead\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(disclosureCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]\s*\.stock-analysis-page__mean-reversion-metrics span:first-child\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(disclosureCss).toMatch(
      /@media\s*\(max-width:\s*720px\)\s*\{[\s\S]*?\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]\s*\.stock-analysis-page__observation-preview-grid\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)\s*!important/,
    );
    expect(disclosureCss).toContain("Observation pool mobile-entry compact pass");
    expect(disclosureCss).toMatch(
      /@media\s*\(max-width:\s*720px\)\s*\{[\s\S]*?\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]\s*>\s*\.stock-analysis-page__dh-section-head\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(disclosureCss).toMatch(
      /@media\s*\(max-width:\s*720px\)\s*\{[\s\S]*?\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]\s*\.stock-analysis-page__observation-preview-panel\s*\{[\s\S]*?min-height:\s*46px\s*!important[\s\S]*?padding:\s*5px 6px\s*!important/,
    );
    expect(disclosureCss).toContain("Observation pool desktop-entry compact pass");
    expect(disclosureCss).toMatch(
      /@media\s*\(min-width:\s*721px\)\s*\{[\s\S]*?\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]\s*\{[\s\S]*?min-height:\s*112px\s*!important[\s\S]*?padding:\s*7px 9px\s*!important/,
    );
    expect(disclosureCss).toMatch(
      /@media\s*\(min-width:\s*721px\)\s*\{[\s\S]*?\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]\s*>\s*\.stock-analysis-page__dh-section-head\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
  });

  it("keeps sector strength background detail collapsed by default", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const page = readFileSync(STOCK_ANALYSIS_PAGE_PATH, "utf8");

    expect(page).toContain('data-testid="stock-analysis-sector-detail-more"');
    expect(page).toContain("const [sectorDetailOpen, setSectorDetailOpen] = useState(false)");
    expect(page).toContain("const SECTOR_STRENGTH_DEFAULT_TOP_COUNT = 3;");
    expect(page).toContain("const visibleSectorTopBars = topBars.slice(0, SECTOR_STRENGTH_DEFAULT_TOP_COUNT);");
    expect(page).toContain("const backgroundSectorTopBars = topBars.slice(SECTOR_STRENGTH_DEFAULT_TOP_COUNT);");
    expect(page).toContain("visibleSectorTopBars.map");
    expect(page).toContain("backgroundSectorTopBars.map");
    expect(page).toContain("setSectorDetailOpen(event.currentTarget.open)");
    expect(page).toContain("sectorDetailOpen ? (");
    expect(page).toContain("stock-analysis-page__sector-detail-more-body");
    expect(page).toContain('data-testid="stock-analysis-sector-bars-secondary"');
    expect(page.indexOf('data-testid="stock-analysis-sector-bars"')).toBeLessThan(
      page.indexOf('data-testid="stock-analysis-sector-detail-more"'),
    );
    expect(css).toContain(".stock-analysis-page__sector-detail-more");
    expect(css).toMatch(
      /\.stock-analysis-page__sector-detail-more-summary\s*\{[\s\S]*?min-height:\s*32px/,
    );
    expect(css).toMatch(
      /\.stock-analysis-page__sector-detail-more:not\(\[open\]\)\s*>\s*\.stock-analysis-page__sector-detail-more-body\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(css).toMatch(
      /\.stock-analysis-page__sector-rank-grid--secondary\s*\{[\s\S]*?grid-template-columns:\s*repeat\(auto-fit,\s*minmax\(220px,\s*1fr\)\)/,
    );
  });

  it("keeps empty theme leader radar as a compact background cue", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const page = readFileSync(STOCK_ANALYSIS_PAGE_PATH, "utf8");
    const compactStart = css.indexOf("Theme leader empty-state compact pass");
    const compactCss = css.slice(compactStart);

    expect(compactStart).toBeGreaterThan(-1);
    expect(page).toContain('testId="stock-analysis-theme-leader-empty"');
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-theme-leaders-first-screen"\]:has\(\[data-testid="stock-analysis-theme-leader-empty"\]\)\s*\{[\s\S]*?gap:\s*5px\s*!important;[\s\S]*?min-height:\s*0\s*!important;[\s\S]*?padding:\s*8px 10px\s*!important;/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-theme-leaders-first-screen"\]:has\(\[data-testid="stock-analysis-theme-leader-empty"\]\)[\s\S]*?>\s*\.stock-analysis-page__dh-section-head\s*\{[\s\S]*?min-height:\s*24px\s*!important;[\s\S]*?border-bottom:\s*0\s*!important;/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-theme-leaders-first-screen"\]:has\(\[data-testid="stock-analysis-theme-leader-empty"\]\)[\s\S]*?\.stock-analysis-page__dh-section-head h2\s*\{[\s\S]*?color:\s*#0f172a\s*!important;/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__dh-section-eyebrow,[\s\S]*?\.stock-analysis-page__lower-signal-strip\s*\{[\s\S]*?display:\s*none\s*!important;/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-theme-leader-empty"\]\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)\s*auto;[\s\S]*?min-height:\s*28px\s*!important;/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-theme-leader-empty"\][\s\S]*?> span:first-child\s*\{[\s\S]*?display:\s*none\s*!important;/,
    );
  });

  it("keeps sector heavyweight evidence compact in the stock-selection default flow", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const compactStart = css.indexOf("Sector heavyweight compact pass");
    const compactCss = css.slice(compactStart);

    expect(compactStart).toBeGreaterThan(-1);
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-sector-heavyweights-first-screen"\]\s*\{[\s\S]*?min-height:\s*112px\s*!important[\s\S]*?max-height:\s*148px\s*!important[\s\S]*?overflow:\s*hidden\s*!important/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-sector-heavyweights-first-screen"\]\s*\.stock-analysis-page__lower-signal-strip,[\s\S]*?\.stock-analysis-page__dh-pill,[\s\S]*?\.stock-analysis-page__sector-heavyweight-list\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__dh-section-head h2\s*\{[\s\S]*?color:\s*#0f172a\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__sector-heavyweight-coverage\s*\{[\s\S]*?display:\s*inline-flex\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__sector-heavyweight-grid\s*\{[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)\s*!important[\s\S]*?min-height:\s*48px\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__sector-heavyweight-card:nth-child\(n \+ 3\)\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(compactCss).toContain("Sector heavyweight stock-entry compact pass");
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-sector-heavyweights-first-screen"\]\s*\{[\s\S]*?min-height:\s*0\s*!important[\s\S]*?max-height:\s*108px\s*!important[\s\S]*?padding:\s*7px 9px\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__sector-heavyweight-list\s*\{[\s\S]*?display:\s*flex\s*!important[\s\S]*?background:\s*transparent\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__sector-heavyweight-head span\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__sector-heavyweight-metrics,[\s\S]*?\.stock-analysis-page__sector-heavyweight-row em\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(compactCss).toMatch(
      /@media\s*\(max-width:\s*720px\)\s*\{[\s\S]*?\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-sector-heavyweights-first-screen"\]\s*\{[\s\S]*?max-height:\s*100px\s*!important/,
    );
  });

  it("keeps sector strength background compact inside stock selection", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const compactStart = css.indexOf("Sector strength background compact pass");
    const compactCss = css.slice(compactStart);

    expect(compactStart).toBeGreaterThan(-1);
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-sector-strength-panel"\]\s*\{[\s\S]*?gap:\s*6px\s*!important[\s\S]*?padding:\s*10px 12px\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__dh-section-head h2\s*\{[\s\S]*?color:\s*#0f172a\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__sector-workbench-strip\s*>\s*div:nth-child\(4\)\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__sector-rank-grid\s*\{[\s\S]*?max-height:\s*92px\s*!important[\s\S]*?overflow:\s*hidden\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__sector-rank-list\s*>\s*\.stock-analysis-page__sector-rank-row:nth-child\(n \+ 3\)\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__sector-detail-more-summary\s*\{[\s\S]*?min-height:\s*30px\s*!important[\s\S]*?padding:\s*4px 7px\s*!important/,
    );
    expect(compactCss).toContain("Sector strength default-entry compact pass");
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-sector-strength-panel"\]\s*>\s*\.stock-analysis-page__dh-section-head\s*\{[\s\S]*?min-height:\s*28px\s*!important[\s\S]*?border-bottom:\s*0\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__dh-section-eyebrow,[\s\S]*?\.stock-analysis-page__dh-section-desc,[\s\S]*?\.stock-analysis-page__dh-pill\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__sector-workbench-strip\s*\{[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__sector-workbench-strip\s*>\s*div:nth-child\(n \+ 3\)\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-sector-strength-panel"\]:not\(:has\(\.stock-analysis-page__sector-detail-more\[open\]\)\)\s*\.stock-analysis-page__sector-tabs\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-sector-strength-panel"\]:not\(:has\(\.stock-analysis-page__sector-detail-more\[open\]\)\)\s*\.stock-analysis-page__sector-rank-grid\s*\{[\s\S]*?max-height:\s*30px\s*!important/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-sector-strength-panel"\]:not\(:has\(\.stock-analysis-page__sector-detail-more\[open\]\)\)\s*\.stock-analysis-page__sector-rank-bar\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-sector-strength-panel"\]:not\(:has\(\.stock-analysis-page__sector-detail-more\[open\]\)\)\s*\.stock-analysis-page__sector-rank-list\s*>\s*\.stock-analysis-page__sector-rank-row:nth-child\(n \+ 2\)\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-sector-strength-panel"\]:has\(\.stock-analysis-page__sector-detail-more\[open\]\)\s*\.stock-analysis-page__sector-rank-grid\s*\{[\s\S]*?max-height:\s*none\s*!important[\s\S]*?overflow:\s*visible\s*!important/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-sector-strength-panel"\]:has\(\.stock-analysis-page__sector-detail-more\[open\]\)\s*\.stock-analysis-page__sector-workbench-strip\s*\{[\s\S]*?grid-template-columns:\s*repeat\(4,\s*minmax\(0,\s*1fr\)\)\s*!important/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-sector-strength-panel"\]:has\(\.stock-analysis-page__sector-detail-more\[open\]\)\s*\.stock-analysis-page__sector-workbench-strip\s*>\s*div\s*\{[\s\S]*?display:\s*grid\s*!important/,
    );
    expect(compactCss).toContain("Sector strength triage-entry compact pass");
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-sector-strength-panel"\]:not\(:has\(\.stock-analysis-page__sector-detail-more\[open\]\)\)\s*\{[\s\S]*?max-height:\s*108px\s*!important[\s\S]*?padding:\s*7px 9px\s*!important[\s\S]*?overflow:\s*hidden\s*!important/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-sector-strength-panel"\]:not\(:has\(\.stock-analysis-page__sector-detail-more\[open\]\)\)[\s\S]*?\.stock-analysis-page__sector-workbench-strip\s*\{[\s\S]*?grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__sector-workbench-strip\s*>\s*div:first-child\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__sector-workbench-strip\s*>\s*div:nth-child\(n \+ 2\)\s*\{[\s\S]*?display:\s*grid\s*!important[\s\S]*?min-height:\s*26px\s*!important/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-sector-strength-panel"\]:not\(:has\(\.stock-analysis-page__sector-detail-more\[open\]\)\)[\s\S]*?\.stock-analysis-page__sector-rank-grid\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__sector-detail-more-summary\s*\{[\s\S]*?min-height:\s*24px\s*!important[\s\S]*?padding:\s*2px 7px\s*!important/,
    );
    expect(compactCss).toMatch(
      /@media\s*\(max-width:\s*720px\)\s*\{[\s\S]*?\[data-testid="stock-analysis-sector-strength-panel"\]:not\(:has\(\.stock-analysis-page__sector-detail-more\[open\]\)\)\s*\{[\s\S]*?max-height:\s*100px\s*!important/,
    );
    expect(compactCss).toContain("Sector strength label-fold compact pass");
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-sector-strength-panel"\]:not\(:has\(\.stock-analysis-page__sector-detail-more\[open\]\)\)\s*\{[\s\S]*?max-height:\s*82px\s*!important[\s\S]*?padding:\s*6px 8px\s*!important/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-sector-strength-panel"\]:not\(:has\(\.stock-analysis-page__sector-detail-more\[open\]\)\)[\s\S]*?>\s*\.stock-analysis-page__dh-section-head\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(compactCss).toMatch(
      /@media\s*\(max-width:\s*720px\)\s*\{[\s\S]*?\[data-testid="stock-analysis-sector-strength-panel"\]:not\(:has\(\.stock-analysis-page__sector-detail-more\[open\]\)\)\s*\{[\s\S]*?max-height:\s*78px\s*!important/,
    );
  });

  it("keeps first-screen analytics compact until a diagnostic tab is opened", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const compactStart = css.indexOf("First-screen analytics compact pass");
    const compactCss = css.slice(compactStart);

    expect(compactStart).toBeGreaterThan(-1);
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-first-screen-analytics"\]\s*\{[\s\S]*?min-height:\s*118px\s*!important[\s\S]*?max-height:\s*128px\s*!important[\s\S]*?overflow:\s*hidden\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__analytics-tabs\s*\.ant-tabs-content-holder\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__signal-pill:nth-child\(2\)\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__dh-section-head h2\s*\{[\s\S]*?color:\s*var\(--ib-ink\)\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__analytics-tabs\s*\.ant-tabs-tab-btn\s*\{[\s\S]*?color:\s*var\(--ib-ink-secondary\)\s*!important/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-first-screen-analytics"\]:has\(\.ant-tabs-tab\[data-node-key="priority"\]\.ant-tabs-tab-active\),[\s\S]*?\[data-testid="stock-analysis-first-screen-analytics"\]:has\(\.ant-tabs-tab\[data-node-key="optimization"\]\.ant-tabs-tab-active\)\s*\{[\s\S]*?max-height:\s*none\s*!important[\s\S]*?overflow:\s*visible\s*!important/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-first-screen-analytics"\]:has\(\.ant-tabs-tab\[data-node-key="priority"\]\.ant-tabs-tab-active\)\s*\.stock-analysis-page__analytics-tabs\s*\.ant-tabs-content-holder,[\s\S]*?\[data-testid="stock-analysis-first-screen-analytics"\]:has\(\.ant-tabs-tab\[data-node-key="optimization"\]\.ant-tabs-tab-active\)\s*\.stock-analysis-page__analytics-tabs\s*\.ant-tabs-content-holder\s*\{[\s\S]*?display:\s*block\s*!important/,
    );
    expect(compactCss).toContain("First-screen analytics background-entry compact pass");
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-first-screen-analytics"\]:not\(:has\(\.ant-tabs-tab\[data-node-key="priority"\]\.ant-tabs-tab-active\)\):not\([\s\S]*?data-node-key="optimization"[\s\S]*?\)\s*\{[\s\S]*?min-height:\s*82px\s*!important[\s\S]*?max-height:\s*92px\s*!important[\s\S]*?padding:\s*7px 10px\s*!important/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-first-screen-analytics"\]:not\(:has\(\.ant-tabs-tab\[data-node-key="priority"\]\.ant-tabs-tab-active\)\):not\([\s\S]*?data-node-key="optimization"[\s\S]*?\)\s*>\s*\.stock-analysis-page__dh-section-head\s*\{[\s\S]*?min-height:\s*24px\s*!important[\s\S]*?border-bottom:\s*0\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__dh-section-eyebrow,[\s\S]*?\.stock-analysis-page__dh-pill\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__signal-pill\s*\{[\s\S]*?min-height:\s*20px\s*!important[\s\S]*?font-size:\s*10\.5px\s*!important/,
    );
    expect(compactCss).toMatch(
      /@media\s*\(max-width:\s*720px\)\s*\{[\s\S]*?\[data-testid="stock-analysis-first-screen-analytics"\]:not\(:has\(\.ant-tabs-tab\[data-node-key="priority"\]\.ant-tabs-tab-active\)\):not\([\s\S]*?data-node-key="optimization"[\s\S]*?\)\s*\{[\s\S]*?min-height:\s*76px\s*!important[\s\S]*?max-height:\s*86px\s*!important/,
    );
  });

  it("keeps the evidence ledger to decision-critical rows in the first-screen rail", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const compactStart = css.indexOf("Evidence ledger compact pass");
    const compactCss = css.slice(compactStart);

    expect(compactStart).toBeGreaterThan(-1);
    expect(compactCss).toContain(
      '[data-testid="stock-analysis-first-screen-rail"].stock-analysis-page__decision-rail > [data-testid="stock-analysis-evidence-ledger"]',
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-evidence-ledger"\]\s*\{[\s\S]*?max-height:\s*292px\s*!important[\s\S]*?overflow:\s*hidden\s*!important/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-evidence-ledger"\]\s*>\s*div:first-child\s*\{[\s\S]*?min-height:\s*38px\s*!important[\s\S]*?padding:\s*9px 10px\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__home-rail-list\s*\{[\s\S]*?grid-template-rows:\s*repeat\(4,\s*1fr\)\s*!important[\s\S]*?height:\s*auto\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__home-rail-list\s*>\s*div:nth-child\(3\),[\s\S]*?\.stock-analysis-page__home-rail-list\s*>\s*div:nth-child\(5\)\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
  });

  it("keeps the mobile decision rail compact before stock selection", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const compactStart = css.indexOf("Mobile decision rail compact pass");
    const compactCss = css.slice(compactStart);

    expect(compactStart).toBeGreaterThan(-1);
    expect(compactCss).toMatch(
      /@media \(max-width:\s*720px\)[\s\S]*?\[data-testid="stock-analysis-first-screen-rail"\]\.stock-analysis-page__decision-rail\s*\{[\s\S]*?max-height:\s*124px\s*!important[\s\S]*?overflow:\s*hidden\s*!important/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-evidence-ledger"\]\s*\{[\s\S]*?max-height:\s*118px\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__home-rail-list\s*\{[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)\s*!important[\s\S]*?grid-template-rows:\s*none\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__home-rail-list\s*>\s*div:nth-child\(2\)\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
  });

  it("keeps the evidence closure strip compact until audit details are opened", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const compactStart = css.indexOf("Evidence closure strip compact pass");
    const compactCss = css.slice(compactStart);

    expect(compactStart).toBeGreaterThan(-1);
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-tailwind-cockpit"\]:not\(:has\(\[data-testid="stock-analysis-evidence-detail-shell"\]\[open\]\)\)\s*\{[\s\S]*?max-height:\s*112px\s*!important[\s\S]*?overflow:\s*hidden\s*!important[\s\S]*?padding:\s*0\s*!important/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-tailwind-cockpit"\]:has\(\[data-testid="stock-analysis-evidence-detail-shell"\]\[open\]\)\s*\{[\s\S]*?max-height:\s*none\s*!important[\s\S]*?overflow:\s*visible\s*!important/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-queue-report-head"\]\s*\{[\s\S]*?display:\s*grid\s*!important[\s\S]*?min-height:\s*76px\s*!important[\s\S]*?padding:\s*9px 12px 8px\s*!important/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-decision-supplement-strip"\],[\s\S]*?\[data-testid="stock-analysis-queue-report-head"\]\s*>\s*dl\[aria-label="首屏复核摘要"\]\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-evidence-detail-shell"\]\s*>\s*summary\s*\{[\s\S]*?min-height:\s*25px\s*!important/,
    );
  });

  it("keeps first-screen KPI cards compact and icon-led", () => {
    const css = readFileSync(EQUITY_KPI_CARD_CSS_PATH, "utf8");

    expect(css).toContain("height: 76px");
    expect(css).toContain("min-height: 76px");
    expect(css).toContain(".icon");
    expect(css).not.toContain("min-height: 104px");
  });

  it("keeps backend supply mini charts readable instead of squeezing canvas dimensions", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");

    expect(css).toContain("grid-template-columns: repeat(auto-fit, minmax(150px, 1fr))");
    expect(css).toContain("grid-template-columns: repeat(auto-fit, minmax(160px, 1fr))");
    expect(css).toMatch(
      /\.stock-analysis-page__mini-chart\s*>\s*\.stock-analysis-page__echart,[\s\S]*?\.stock-analysis-page__mini-chart canvas\s*\{[\s\S]*?height:\s*100%\s*!important/,
    );
    expect(css).toMatch(
      /\.stock-analysis-page__mini-chart\s*>\s*\.stock-analysis-page__echart\s*>\s*div\s*\{[\s\S]*?height:\s*100%\s*!important/,
    );
  });

  it("removes section-head accent bars and widens first-screen grid gap on desktop", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const densityStart = css.indexOf("Final density polish");
    const densityCss = css.slice(densityStart);

    expect(densityStart).toBeGreaterThan(-1);
    expect(css).toMatch(
      /\.stock-analysis-page__dh-section-head h2::before,[\s\S]*?display:\s*none\s*!important/,
    );
    expect(css).toMatch(
      /\.stock-analysis-page__dh-section-head h2,[\s\S]*?color:\s*var\(--ib-ink\)/,
    );
    expect(densityCss).toMatch(/\.stock-analysis-page__first-screen\s*\{[\s\S]*?gap:\s*28px\s*!important/);
  });

  it("keeps the stock dashboard aligned to a summary-first deep-review layout", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const consolidationStart = css.indexOf("Stock-analysis first-screen consolidation");
    const consolidationCss = css.slice(consolidationStart);

    expect(consolidationStart).toBeGreaterThan(-1);
    expect(consolidationCss).toContain(".stock-analysis-page__workspace");
    expect(consolidationCss).toContain(".stock-analysis-page__deep-zone");
    expect(consolidationCss).toMatch(
      /\.stock-analysis-page__deep-review-workspace\s*\{[\s\S]*?grid-template-columns:\s*repeat\(auto-fit,\s*minmax\(280px,\s*1fr\)\)\s*!important/,
    );
    expect(consolidationCss).toMatch(
      /\.stock-analysis-page__deep-review-workspace\s*\[data-testid="stock-analysis-sector-strength-panel"\],[\s\S]*?\.stock-analysis-page__deep-review-workspace\s*\[data-testid="stock-analysis-first-screen-analytics"\]\s*\{[\s\S]*?grid-column:\s*1\s*\/\s*-1\s*!important/,
    );
    expect(consolidationCss).toMatch(
      /\.stock-analysis-page__deep-review-workspace\s*\[data-testid="stock-analysis-consensus-first-screen"\],[\s\S]*?\.stock-analysis-page__deep-review-workspace\s*\[data-testid="stock-analysis-first-screen-analytics"\]\s*\{[\s\S]*?max-height:\s*none\s*!important[\s\S]*?overflow:\s*visible\s*!important/,
    );
    expect(consolidationCss).toMatch(
      /\.stock-analysis-page__deep-review-workspace\s*\.stock-analysis-page__table-wrap,[\s\S]*?\.stock-analysis-page__deep-review-workspace\s*\.stock-analysis-page__sector-heavyweight-list\s*\{[\s\S]*?max-height:\s*320px[\s\S]*?overflow:\s*auto/,
    );
    expect(consolidationCss).toMatch(
      /\.stock-analysis-strategy-card-grid\s*\{[\s\S]*?grid-template-columns:\s*repeat\(auto-fit,\s*minmax\(280px,\s*1fr\)\)/,
    );
  });

  it("keeps collapsed strategy research cards as compact entry points", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const page = readFileSync(STOCK_ANALYSIS_PAGE_PATH, "utf8");
    const compactStart = css.indexOf("Strategy research cards compact pass");
    const compactCss = css.slice(compactStart);

    expect(compactStart).toBeGreaterThan(-1);
    expect(page).toContain('data-testid="stock-analysis-strategy-research-more"');
    expect(page).toContain('className="stock-analysis-page__strategy-research-more-summary"');
    expect(page).toContain('data-testid="stock-analysis-strategy-card-grid"');
    expect(compactCss).toMatch(
      /\.stock-analysis-page__deep-zone\s*\.stock-analysis-strategy-card-grid\s*>\s*\.stock-analysis-strategy-module-card:not\(:has\(\.stock-analysis-strategy-module-card__detail:not\(\.stock-analysis-strategy-module-card__detail--collapsed\)\)\)\s*\{[\s\S]*?min-height:\s*82px\s*!important[\s\S]*?max-height:\s*92px\s*!important[\s\S]*?overflow:\s*hidden\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-strategy-module-card__subtitle,[\s\S]*?>\s*\.stock-analysis-strategy-module-card__kpi-grid\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-strategy-module-card__title\s*\{[\s\S]*?color:\s*var\(--ib-ink\)\s*!important/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-strategy-module-card__headline\s*\{[\s\S]*?color:\s*var\(--ib-ink-secondary\)\s*!important[\s\S]*?-webkit-line-clamp:\s*1\s*!important/,
    );
    expect(compactCss).toContain("Strategy research disclosure pass");
    expect(compactCss).toMatch(
      /\.stock-analysis-page__strategy-research-more-summary\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)\s*auto[\s\S]*?min-height:\s*34px/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__strategy-research-more:not\(\[open\]\)\s*>\s*\.stock-analysis-strategy-card-grid\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(compactCss).toMatch(
      /@media\s*\(max-width:\s*720px\)\s*\{[\s\S]*?\.stock-analysis-page__strategy-research-more-summary\s*\{[\s\S]*?min-height:\s*30px/,
    );
  });

  it("keeps the desktop first screen in one main column plus a fixed-width trust rail", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const consolidationStart = css.indexOf("Stock-analysis first-screen consolidation");
    const consolidationCss = css.slice(consolidationStart);

    expect(consolidationStart).toBeGreaterThan(-1);
    expect(consolidationCss).toMatch(
      /\.stock-analysis-page__uses-home-shell\.stock-analysis-page__first-screen\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)\s*316px\s*!important/,
    );
    expect(consolidationCss).toMatch(
      /\.stock-analysis-page__uses-home-shell\s*>\s*\.stock-analysis-page__first-screen-main\s*\{[\s\S]*?grid-column:\s*1\s*\/\s*2\s*!important[\s\S]*?grid-row:\s*1\s*!important/,
    );
    expect(consolidationCss).toMatch(
      /\.stock-analysis-page__uses-home-shell\s*>\s*\[data-testid="stock-analysis-first-screen-rail"\]\s*\{[\s\S]*?grid-column:\s*2\s*\/\s*3\s*!important[\s\S]*?grid-row:\s*1\s*!important[\s\S]*?max-height:\s*none\s*!important[\s\S]*?overflow:\s*visible\s*!important/,
    );
    expect(consolidationCss).not.toMatch(/grid-row:\s*1\s*\/\s*span\s*7\s*!important/);
    expect(consolidationCss).not.toMatch(/max-height:\s*106px/);
    expect(consolidationCss).not.toMatch(/max-height:\s*126px/);
  });

  it("keeps the trust rail compact on desktop and full-width inside narrow single-column flow", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const polishStart = css.indexOf("Trust rail responsive polish");
    const polishCss = css.slice(polishStart);

    expect(polishStart).toBeGreaterThan(-1);
    expect(polishCss).toMatch(
      /\.stock-analysis-page__decision-rail\s*>\s*article\s*\{[\s\S]*?grid-column:\s*1\s*\/\s*-1/,
    );
    expect(polishCss).toMatch(
      /@media \(min-width:\s*1131px\)[\s\S]*?\.stock-analysis-page__decision-rail\s*\.stock-analysis-page__rail-check-list\s*\{[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)\s*!important/,
    );
    expect(polishCss).toMatch(
      /@media \(max-width:\s*1130px\)[\s\S]*?\.stock-analysis-page__uses-home-shell\s*>\s*\[data-testid="stock-analysis-first-screen-rail"\]\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)\s*!important/,
    );
    expect(polishCss).toMatch(
      /@media \(min-width:\s*721px\) and \(max-width:\s*1130px\)[\s\S]*?\.stock-analysis-page__decision-rail\s*>\s*article\s*\{[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/,
    );
    expect(polishCss).toMatch(
      /@media \(max-width:\s*720px\)[\s\S]*?\.stock-analysis-page__decision-rail\s*>\s*article\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)/,
    );
  });

  it("keeps narrow screens single-column without clipping review or deep modules", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const mobileStart = css.indexOf("Mobile first-screen readability pass");
    const consolidationStart = css.indexOf("Stock-analysis first-screen consolidation");
    const observationMobileStart = css.indexOf("Mobile observation ledger no-scroll pass");
    const mobileCss = css.slice(mobileStart);
    const consolidationCss = css.slice(consolidationStart);
    const observationMobileCss = css.slice(observationMobileStart);

    expect(mobileStart).toBeGreaterThan(-1);
    expect(consolidationStart).toBeGreaterThan(-1);
    expect(observationMobileStart).toBeGreaterThan(-1);
    expect(mobileCss).toMatch(
      /@media \(max-width:\s*720px\)[\s\S]*?\.stock-analysis-page__dh-hero-status-strip\s*\{[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/,
    );
    expect(mobileCss).toMatch(
      /\.stock-analysis-page__dh-hero-status-strip span\s*\{[\s\S]*?white-space:\s*normal\s*!important/,
    );
    expect(mobileCss).toMatch(
      /\.stock-analysis-page__dh-details summary \.stock-analysis-page__dh-pill\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(mobileCss).toMatch(
      /\.stock-analysis-page__supply-kpi-row\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)/,
    );
    expect(mobileCss).toMatch(
      /\.stock-analysis-page__supply-kpi-card,[\s\S]*?\.stock-analysis-page__mini-chart\s*\{[\s\S]*?max-width:\s*100%/,
    );
    expect(mobileCss).toMatch(
      /\.stock-analysis-page__candidate-ledger-table td:nth-child\(7\),[\s\S]*?\.stock-analysis-page__candidate-ledger-table td:nth-child\(8\)\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(consolidationCss).toMatch(
      /@media \(max-width:\s*1130px\)[\s\S]*?\.stock-analysis-page__uses-home-shell\.stock-analysis-page__first-screen\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)\s*!important/,
    );
    expect(consolidationCss).toMatch(
      /@media \(max-width:\s*1130px\)[\s\S]*?\.stock-analysis-page__deep-review-workspace\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)\s*!important/,
    );
    expect(consolidationCss).toMatch(
      /\.stock-analysis-page__deep-review-workspace\s*\[data-testid="stock-analysis-observation-preview"\],[\s\S]*?\.stock-analysis-page__deep-review-workspace\s*\[data-testid="stock-analysis-first-screen-analytics"\]\s*\{[\s\S]*?max-height:\s*none\s*!important[\s\S]*?overflow:\s*visible\s*!important/,
    );
    expect(observationMobileCss).toMatch(
      /\[data-testid="stock-analysis-observation-preview"\]\s*\.stock-analysis-page__table-wrap\s*\{[\s\S]*?overflow-x:\s*hidden\s*!important/,
    );
    expect(observationMobileCss).toMatch(
      /\[data-testid="stock-analysis-observation-preview"\]\s*\.stock-analysis-page__table\s*\{[\s\S]*?min-width:\s*0\s*!important/,
    );
    expect(observationMobileCss).toMatch(
      /\[data-testid="stock-analysis-observation-preview"\]\s*\.stock-analysis-page__table tbody\s*\{[\s\S]*?display:\s*grid\s*!important/,
    );
    expect(observationMobileCss).toMatch(
      /\[data-testid="stock-analysis-observation-preview"\]\s*\.stock-analysis-page__observation-preview-more:not\(\[open\]\)\s*>\s*\.stock-analysis-page__observation-preview-extra\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
  });

  it("keeps narrow stock trust evidence on the first screen before deep chart exploration", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const consolidationStart = css.indexOf("Stock-analysis first-screen consolidation");
    const consolidationCss = css.slice(consolidationStart);

    expect(consolidationStart).toBeGreaterThan(-1);
    expect(consolidationCss).toMatch(
      /\.stock-analysis-page__uses-home-shell\s*>\s*\.stock-analysis-page__first-screen-main\s*>\s*\*\s*\{[\s\S]*?order:\s*initial\s*!important/,
    );
    expect(consolidationCss).toMatch(
      /\.stock-analysis-page__uses-home-shell\s*>\s*\[data-testid="stock-analysis-first-screen-rail"\]\s*\{[\s\S]*?max-height:\s*none\s*!important[\s\S]*?overflow:\s*visible\s*!important/,
    );
    expect(consolidationCss).toMatch(
      /\.stock-analysis-page__deep-review-workspace\s*>\s*\*\s*\{[\s\S]*?order:\s*initial\s*!important/,
    );
    expect(consolidationCss).toMatch(
      /\.stock-analysis-page__deep-review-workspace\s*\[data-testid="stock-analysis-strategy-lens"\],[\s\S]*?\.stock-analysis-page__deep-review-workspace\s*\[data-testid="stock-analysis-first-screen-analytics"\]\s*\{[\s\S]*?grid-column:\s*1\s*\/\s*-1\s*!important/,
    );
  });

  it("keeps stock trust evidence and review controls before deep analysis", async () => {
    renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });

    const decisionPanel = await screen.findByTestId("stock-analysis-decision-panel");
    const reviewQueue = await screen.findByTestId("stock-analysis-review-queue");
    const reviewStrip = await screen.findByTestId("stock-analysis-review-workbench-strip");
    const consensus = await screen.findByTestId("stock-analysis-consensus-first-screen");
    const consensusStrip = await screen.findByTestId("stock-analysis-consensus-workbench-strip");
    const closedLoop = await screen.findByTestId("stock-analysis-closed-loop-summary");
    const verdict = await screen.findByTestId("stock-analysis-closed-loop-verdict");
    const boundary = await screen.findByTestId("stock-analysis-boundary-summary");
    const sector = await screen.findByTestId("stock-analysis-sector-strength-panel");
    const deepZone = await screen.findByTestId("stock-analysis-deep-zone");

    expect(decisionPanel).toBeInTheDocument();
    expect(reviewStrip).toBeInTheDocument();
    expect(consensusStrip).toBeInTheDocument();
    expect(verdict).toBeInTheDocument();
    expect(boundary).toBeInTheDocument();
    expect(within(closedLoop).getByTestId("stock-analysis-rail-check-matrix")).toBeInTheDocument();

    expectElementBefore(decisionPanel, reviewQueue);
    expectElementBefore(reviewQueue, deepZone);
    expectElementBefore(closedLoop, deepZone);
    expectElementBefore(consensus, sector);
  });

  it("surfaces backend supply status and stock selection on the first screen", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({ metaOverrides: { quality_flag: "warning" } }),
    });

    const decisionPanel = await screen.findByTestId("stock-analysis-decision-panel");
    expect(decisionPanel).toHaveTextContent("数据日");
    expect(decisionPanel).toHaveTextContent("门控 温和");
    expect(decisionPanel).toHaveTextContent("条件 2/4");
    expect(decisionPanel).toHaveTextContent("候选队列");
    expect(decisionPanel).toHaveTextContent("风险 触发 1");
    expect(decisionPanel).toHaveTextContent("部分缺失");
    expect(decisionPanel).not.toHaveTextContent("后台供数");
    expect(decisionPanel).toHaveTextContent("门控 WARM");

    const supplyStatus = await screen.findByTestId("stock-analysis-backend-supply-status");
    expect(supplyStatus).toHaveTextContent("市场门控");
    expect(supplyStatus).toHaveTextContent("部分");
    expect(supplyStatus).toHaveTextContent("市场宽度");
    expect(supplyStatus).not.toHaveTextContent("Market gate");
    expect(supplyStatus).not.toHaveTextContent("partial");
    expect(supplyStatus).not.toHaveTextContent("breadth");

    expect(screen.queryByTestId("stock-analysis-supply-details-toggle")).not.toBeInTheDocument();
    const evidenceLedger = await screen.findByTestId("stock-analysis-evidence-ledger");
    expect(evidenceLedger).toHaveTextContent("补证清单");
    expect(evidenceLedger).toHaveTextContent("数据口径与边界");
    expect(evidenceLedger).not.toHaveTextContent("partial");
    expect(evidenceLedger).not.toHaveTextContent("events");

    const selection = await screen.findByTestId("stock-analysis-stock-selection");
    expect(selection).toHaveTextContent("多因子");
    expect(selection).toHaveTextContent("策略共振选股");

    const queue = await screen.findByTestId("stock-analysis-review-queue");
    expect(queue).toHaveTextContent("复核队列");
    expect(queue).toHaveTextContent("候选/ 复核队列");
    expect(queue).toHaveTextContent("距观察");
    expect(queue).not.toHaveTextContent("为什么先看");
    expect(queue).not.toHaveTextContent("反证与待补");
    expect(within(queue).getByTestId("stock-comparison-candidate-review-000001.SZ")).toHaveTextContent("复核");
  });

  it("keeps unknown supply quality and vendor statuses off the first screen", async () => {
    const unknownSupplyMeta = {
      quality_flag: "quality_vendor_unknown",
      vendor_status: "vendor_paused",
      fallback_mode: "external_vendor_snapshot",
    } as Record<string, unknown> as Partial<ApiEnvelope<LivermoreStrategyPayload>["result_meta"]>;

    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        metaOverrides: unknownSupplyMeta,
      }),
    });

    const decisionPanel = await screen.findByTestId("stock-analysis-decision-panel");
    expect(decisionPanel).toHaveTextContent("质量待确认");
    expect(decisionPanel).toHaveTextContent("供数待确认");
    expect(decisionPanel).not.toHaveTextContent("通道待确认");
    expect(decisionPanel).toHaveTextContent("待确认");
    expect(decisionPanel).not.toHaveTextContent("quality_vendor_unknown");
    expect(decisionPanel).not.toHaveTextContent("vendor_paused");
    expect(decisionPanel).not.toHaveTextContent("external_vendor_snapshot");
  });

  it("localizes unknown strategy basis before showing supply details", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        metaOverrides: { basis: "external_vendor_basis" } as unknown as Partial<
          ApiEnvelope<LivermoreStrategyPayload>["result_meta"]
        >,
      }),
    });

    const decisionPanel = await screen.findByTestId("stock-analysis-decision-panel");
    expect(decisionPanel).toHaveTextContent("口径待确认");
    expect(decisionPanel).not.toHaveTextContent("external_vendor_basis");
    expect(screen.queryByTestId("stock-analysis-supply-details-toggle")).not.toBeInTheDocument();
  });

  it("does not show a requested date as the backend supply data date when no data date is resolved", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          as_of_date: null,
          requested_as_of_date: "2026-05-08",
        }),
      }),
    });

    const decisionPanel = await screen.findByTestId("stock-analysis-decision-panel");
    const dataDateTile = within(decisionPanel).getByTitle(/数据日期/);
    const requestedDateTile = within(decisionPanel).getByTitle(/请求日期/);

    expect(dataDateTile).toHaveTextContent("日期待补");
    expect(dataDateTile).not.toHaveTextContent("2026-05-08");
    expect(requestedDateTile).toHaveTextContent("2026-05-08");
  });

  it("does not show a requested date as the toolbar observation date when no data date is resolved", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          as_of_date: null,
          requested_as_of_date: "2026-05-08",
        }),
      }),
    });

    const page = await screen.findByTestId("stock-analysis-page");
    const toolbar = page.querySelector(".stock-analysis-page__toolbar-info");

    await waitFor(() => expect(toolbar).not.toHaveTextContent("默认"));

    expect(toolbar).toHaveTextContent("观察日");
    expect(toolbar).toHaveTextContent("日期待补");
    expect(toolbar).not.toHaveTextContent("2026-05-08");
  });

  it("renders first-screen theme leaders and analytics tabs", async () => {
    const user = userEvent.setup();
    const fetchMock = vi.fn().mockResolvedValueOnce(buildJsonResponse(buildStockAgentResult()));
    vi.stubGlobal("fetch", fetchMock);

    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          supported_outputs: ["market_gate", "sector_rank", "stock_candidates", "theme_breakout", "risk_exit"],
          theme_breakout: {
            as_of_date: "2026-05-08",
            formula_version: "rv_livermore_theme_breakout_proxy_v1",
            is_proxy: true,
            theme_count: 1,
            items: [
              {
                rank: 1,
                as_of_date: "2026-05-08",
                theme_key: "semiconductor_proxy",
                theme_name: "Semiconductor proxy",
                parent_sector_code: "801080",
                parent_sector_name: "Electronic",
                parent_sector_rank: 9,
                member_count: 3,
                advance_count: 3,
                advance_ratio: 1,
                strong_stock_count: 3,
                limit_stock_count: 2,
                avg_pctchange: 9.766667,
                avg_turn: 4.4,
                avg_amplitude: 7.3,
                observation_only: true,
                reason: "Observation-only proxy cluster: leaders 688001.SH, 688002.SH.",
                items: [
                  {
                    stock_code: "688001.SH",
                    stock_name: "Alpha Semiconductor",
                    sector_code: "801001",
                    sector_name: "AI",
                    sector_rank: 1,
                    open: 9.6,
                    high: 10.1,
                    low: 9.4,
                    close: 10,
                    pctchange: 12.1,
                    turn: 4.2,
                    amplitude: 7,
                    close_strength: 0.86,
                    closed_up_limit: true,
                    strong: true,
                  },
                ],
              },
            ],
          },
        }),
      }),
    });

    const themeLeaders = await screen.findByTestId("stock-analysis-theme-leaders-first-screen");
    expect(themeLeaders).toHaveTextContent("题材突破领涨股");
    expect(screen.getByTestId("theme-leader-first-row-688001.SH")).toHaveTextContent("Alpha Semiconductor");

    const sectorHeavyweights = await screen.findByTestId("stock-analysis-sector-heavyweights-first-screen");
    expect(sectorHeavyweights).toHaveTextContent("权重股摘要");
    expect(screen.getByTestId("sector-heavyweight-row-801001-688001.SH")).toHaveTextContent("Alpha Semiconductor");

    const themeHeavyweightSidebar = await screen.findByTestId("stock-analysis-theme-heavyweights-sidebar");
    expect(themeHeavyweightSidebar).toHaveTextContent("权重股侧栏");
    expect(screen.getByTestId("theme-heavyweight-sidebar-category-801001")).toHaveTextContent("AI");
    expect(screen.getByTestId("theme-heavyweight-sidebar-stock-801001-688001.SH")).toHaveTextContent(
      "Alpha Semiconductor",
    );
    await user.click(screen.getByTestId("theme-heavyweight-sidebar-stock-801001-688001.SH"));
    const detailDrawer = await screen.findByTestId("stock-detail-drawer");
    expect(detailDrawer).toHaveTextContent("题材强势");

    await user.click(screen.getByTestId("stock-analysis-agent-open"));
    await user.type(screen.getByTestId("agent-panel-question"), "check selected theme source");
    await user.click(screen.getByTestId("agent-panel-submit"));
    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const submitted = parseLastAgentQueryRequest(fetchMock);
    expect(submitted?.page_context?.selected_rows?.[0]).toMatchObject({
      stock_code: "688001.SH",
      stock_name: "Alpha Semiconductor",
      sector_code: "801001",
      sector_name: "AI",
      source: "theme_breakout",
    });

    const analytics = await screen.findByTestId("stock-analysis-first-screen-analytics");
    expect(analytics).toHaveTextContent("回测诊断");
    expect(analytics).not.toHaveTextContent("历史共振 / 策略优先级/ 优化诊断");
    expect(analytics).toHaveTextContent("历史共振");
    expect(screen.getByRole("tab", { name: "策略优先级" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "优化诊断" })).toBeInTheDocument();
  });

  it("loads strategy diagnostics when first-screen analytics priority tab is opened", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    const strategyScoreSpy = vi.spyOn(client, "getLivermoreStrategyScore");
    const strategyOptimizationSpy = vi.spyOn(client, "getLivermoreStrategyOptimization");
    const candidateHistorySpy = vi.spyOn(client, "getLivermoreCandidateHistory");

    renderWorkbenchApp(["/stock-analysis"], { client });

    await screen.findByTestId("stock-analysis-first-screen-analytics");
    expect(strategyScoreSpy).not.toHaveBeenCalled();

    await user.click(screen.getByRole("tab", { name: "策略优先级" }));
    await waitFor(() => {
      expect(strategyScoreSpy).toHaveBeenCalled();
    });
    expect(strategyOptimizationSpy).toHaveBeenCalled();
    expect(candidateHistorySpy).toHaveBeenCalledWith(
      expect.objectContaining({ snapshotTo: "2026-04-29" }),
    );
  });

  it("loads strategy diagnostics when first-screen analytics optimization tab is opened", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    const strategyScoreSpy = vi.spyOn(client, "getLivermoreStrategyScore");
    const strategyOptimizationSpy = vi.spyOn(client, "getLivermoreStrategyOptimization");
    const candidateHistorySpy = vi.spyOn(client, "getLivermoreCandidateHistory");

    renderWorkbenchApp(["/stock-analysis"], { client });

    await screen.findByTestId("stock-analysis-first-screen-analytics");
    expect(strategyOptimizationSpy).not.toHaveBeenCalled();

    await user.click(screen.getByRole("tab", { name: "优化诊断" }));
    await waitFor(() => {
      expect(strategyOptimizationSpy).toHaveBeenCalled();
    });
    expect(strategyScoreSpy).toHaveBeenCalled();
    expect(candidateHistorySpy).toHaveBeenCalledWith(
      expect.objectContaining({ snapshotTo: "2026-04-29" }),
    );
  });

  it("renders core sections and candidate evidence", async () => {
    renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });

    expect(await screen.findByTestId("market-workbench-topbar")).toHaveTextContent("股票分析");
    expect(await screen.findByTestId("stock-analysis-decision-panel")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "板块强弱" })).toBeInTheDocument();
    const pagePurpose = await screen.findByTestId("stock-analysis-page-purpose");
    expect(pagePurpose).toHaveTextContent("股票策略复核台");
    expect(pagePurpose).not.toHaveTextContent("查看今日门控、候选队列与证据是否齐全");
    expect(await screen.findByTestId("stock-analysis-deep-zone")).toHaveTextContent("供数 / 回放 / 候选 / 事件明细");
    expect(await screen.findByRole("heading", { name: "题材突变观察" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "复核队列" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "风险退出观察" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "数据口径与边界" })).toBeInTheDocument();

    const candidate = screen.getByTestId("stock-comparison-candidate-row-000001.SZ");
    expect(candidate).toHaveTextContent("Alpha");
    expect(candidate).toHaveTextContent("待核 2 条");
    expect(candidate).toHaveTextContent("11 条");
    expect(candidate).toHaveTextContent("复核");
    expect(candidate).not.toHaveTextContent("进入依据");
    expect(candidate).not.toHaveTextContent("10EMA 失效观察");
    expect(candidate).not.toHaveTextContent("基本面因子已纳入候选排序");
    expect(candidate).not.toHaveTextContent("基本面 overlay");
    expect(candidate).not.toHaveTextContent("overlay #");
  });

  it("renders the cycle rotation framework as research-only evidence", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          cycle_rotation_framework: {
            strategy_name: "A-share cycle rotation research framework",
            display_name: "A股景气周期选股与行业轮动",
            observation_only: true,
            implementation_stage: "verification_pending",
            score_formula:
              "CycleScore = 0.30 Macro + 0.35 Industry + 0.20 MarketFlow + 0.15 ValuationSupport",
            rebalance_cadence: "Monthly core review with weekly satellite monitoring.",
            constraints: [
              "industry cap 25%",
              "stock cap 5%",
              "exclude ST and suspended stocks",
            ],
            layers: [
              {
                key: "macro_direction",
                title: "Macro direction",
                weight: 0.3,
                status: "missing_inputs",
                evidence: "Market gate is available; PMI and credit impulse are not landed.",
                available_inputs: ["market_gate"],
                missing_inputs: ["PMI", "credit_impulse"],
              },
              {
                key: "industry_cycle",
                title: "Industry cycle",
                weight: 0.35,
                status: "provisional",
                evidence: "sector_rank is available.",
                available_inputs: ["sector_rank"],
                missing_inputs: ["profit_cycle"],
              },
            ],
          },
        } as Partial<LivermoreStrategyPayload>),
      }),
    });

    const framework = await screen.findByTestId("stock-analysis-cycle-rotation-framework");
    expect(framework).toHaveTextContent("A股景气周期选股与行业轮动");
    expect(framework).toHaveTextContent("轮动规则");
    expect(framework).toHaveTextContent("宏观方向 30%");
    expect(framework).toHaveTextContent("行业景气 35%");
    expect(framework).toHaveTextContent("宏观");
    expect(framework).toHaveTextContent("PMI");
    expect(framework).toHaveTextContent("信用脉冲");
    expect(framework).toHaveTextContent("行业上限 25%");
    expect(framework).toHaveTextContent("证据待齐");
    expect(framework).toHaveTextContent("输入待补");
    expect(framework).toHaveTextContent("市场门控已有可用证据");
    expect(framework).toHaveTextContent("板块强弱已有可用证据");
    expect(framework).not.toHaveTextContent("市场门控已接入");
    expect(framework).not.toHaveTextContent("板块强弱已接入");
    expect(framework).not.toHaveTextContent("CycleScore");
    expect(framework).not.toHaveTextContent("Available:");
    expect(framework).not.toHaveTextContent("Missing:");
    expect(framework).not.toHaveTextContent("missing_inputs");
    expect(framework).not.toHaveTextContent("industry cap 25%");
    expect(framework).not.toHaveTextContent("Market gate is available");
    expect(framework).not.toHaveTextContent("sector_rank is available");
    expect(within(framework).getByTestId("stock-analysis-candidate-history-portfolio-backtest")).toHaveTextContent("组合回测");
    expect(within(framework).getByTestId("stock-analysis-cycle-proxy-backtest")).toHaveTextContent("代理回测");
    await waitFor(() =>
      expect(within(framework).getByTestId("stock-analysis-portfolio-backtest-boundary")).toHaveTextContent("代理口径"),
    );
    const portfolioBoundary = within(framework).getByTestId("stock-analysis-portfolio-backtest-boundary");
    expect(portfolioBoundary).toHaveTextContent("代理口径");
    expect(portfolioBoundary).toHaveTextContent("缺口 2");
    expect(portfolioBoundary).toHaveTextContent("PMI");
    expect(portfolioBoundary).toHaveTextContent("信用脉冲");
    await waitFor(() =>
      expect(within(framework).getByTestId("stock-analysis-cycle-proxy-boundary")).toHaveTextContent("代理口径"),
    );
    const cycleBoundary = within(framework).getByTestId("stock-analysis-cycle-proxy-boundary");
    expect(cycleBoundary).toHaveTextContent("代理口径");
    expect(cycleBoundary).toHaveTextContent("缺口 2");
    expect(cycleBoundary).toHaveTextContent("PMI");
    expect(cycleBoundary).toHaveTextContent("信用脉冲");
    expect(framework).not.toHaveTextContent("missing_full_strategy_inputs");
    expect(framework).not.toHaveTextContent("credit_impulse");
    await waitFor(() => expect(framework).toHaveTextContent("-18.42%"));
    expect(framework).toHaveTextContent("2024-09-24 至 2024-10-08");
    expect(framework).toHaveTextContent("2024-10-08 至 2025-04-25");
    await waitFor(() => expect(framework).toHaveTextContent("-29.70%"));
    expect(framework).toHaveTextContent("-29.70%");
    expect(framework).toHaveTextContent("2024-09-24 至 2024-12-02");
    expect(framework).toHaveTextContent("2024-12-02 至 2026-01-21");
    expect(framework).not.toHaveTextContent("买入");
    expect(framework).not.toHaveTextContent("下单");
    expect(framework).not.toHaveTextContent("调仓");
  });

  it("localizes portfolio backtest source-table failures without exposing backend tables", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          cycle_rotation_framework: buildCycleRotationFramework(),
        }),
        candidateHistoryPortfolioBacktestError: new Error(
          "Failed to fetch portfolio backtest because source_table choice_stock_portfolio_backtest is missing.",
        ),
      }),
    });

    const section = await screen.findByTestId("stock-analysis-candidate-history-portfolio-backtest");
    await waitFor(() => expect(section).toHaveTextContent("暂不可用"), { timeout: 3_000 });
    expect(section).toHaveTextContent("数据源缺失");
    expect(section).not.toHaveTextContent("Failed to fetch");
    expect(section).not.toHaveTextContent("source_table");
    expect(section).not.toHaveTextContent("choice_stock_portfolio_backtest");
  });

  it("localizes cycle proxy backtest source-table failures without exposing backend tables", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          cycle_rotation_framework: buildCycleRotationFramework(),
        }),
        cycleProxyBacktestError: new Error(
          "Failed to fetch cycle proxy backtest because source_table choice_stock_cycle_proxy_backtest is missing.",
        ),
      }),
    });

    const section = await screen.findByTestId("stock-analysis-cycle-proxy-backtest");
    await waitFor(() => expect(section).toHaveTextContent("暂不可用"), { timeout: 3_000 });
    expect(section).toHaveTextContent("数据源缺失");
    expect(section).not.toHaveTextContent("Failed to fetch");
    expect(section).not.toHaveTextContent("source_table");
    expect(section).not.toHaveTextContent("choice_stock_cycle_proxy_backtest");
  });

  it("renders unknown cycle rotation inputs as pending boundaries instead of raw backend codes", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          cycle_rotation_framework: {
            ...buildCycleRotationFramework(),
            layers: [
              {
                key: "macro_direction",
                title: "Macro direction",
                weight: 0.3,
                status: "missing_inputs",
                evidence: "external_vendor_cycle_feed is not landed.",
                available_inputs: ["market_gate"],
                missing_inputs: ["external_vendor_cycle_feed"],
              },
            ],
          },
        }),
      }),
    });

    const framework = await screen.findByTestId("stock-analysis-cycle-rotation-framework");
    expect(framework).toHaveTextContent("输入待确认");
    expect(framework).toHaveTextContent("证据待确认");
    expect(framework).not.toHaveTextContent("external_vendor_cycle_feed");
    expect(framework).not.toHaveTextContent("external vendor cycle feed");
  });

  it("renders unknown cycle rotation cadence as a pending cadence boundary", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          cycle_rotation_framework: {
            ...buildCycleRotationFramework(),
            rebalance_cadence: "external_vendor_daily_rotation",
          },
        }),
      }),
    });

    const framework = await screen.findByTestId("stock-analysis-cycle-rotation-framework");
    expect(framework).toHaveTextContent("节奏待确认");
    expect(framework).not.toHaveTextContent("external_vendor_daily_rotation");
    expect(framework).not.toHaveTextContent("external vendor daily rotation");
  });

  it("renders unknown cycle rotation constraints as pending boundaries instead of raw backend codes", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          cycle_rotation_framework: {
            ...buildCycleRotationFramework(),
            constraints: ["external_vendor_position_guard"],
          },
        }),
      }),
    });

    const framework = await screen.findByTestId("stock-analysis-cycle-rotation-framework");
    expect(framework).toHaveTextContent("约束待确认");
    expect(framework).not.toHaveTextContent("external_vendor_position_guard");
    expect(framework).not.toHaveTextContent("external vendor position guard");
  });

  it("renders unknown cycle rotation boundary text as a pending boundary instead of raw backend codes", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          cycle_rotation_framework: {
            ...buildCycleRotationFramework(),
            lifecourt_overlay: {
              display_name: "生命法庭代理",
              observation_only: true,
              implementation_stage: "verification_pending",
              rebalance_cadence: "Monthly core review with weekly satellite monitoring.",
              boundary: "external_vendor_boundary_guard",
              available_inputs: ["market_gate"],
              missing_inputs: [],
              life_long_gates: [],
            },
          },
        }),
      }),
    });

    const framework = await screen.findByTestId("stock-analysis-cycle-rotation-framework");
    expect(framework).toHaveTextContent("边界待确认");
    expect(framework).not.toHaveTextContent("external_vendor_boundary_guard");
    expect(framework).not.toHaveTextContent("external vendor boundary guard");
  });

  it("renders unknown cycle rotation evidence text as pending evidence instead of raw backend codes", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          cycle_rotation_framework: {
            ...buildCycleRotationFramework(),
            layers: [
              {
                key: "macro_direction",
                title: "Macro direction",
                weight: 0.3,
                status: "missing_inputs",
                evidence: "vendor_quality_signal_pending",
                available_inputs: ["market_gate"],
                missing_inputs: [],
              },
            ],
          },
        }),
      }),
    });

    const framework = await screen.findByTestId("stock-analysis-cycle-rotation-framework");
    expect(framework).toHaveTextContent("证据待确认");
    expect(framework).not.toHaveTextContent("vendor_quality_signal_pending");
    expect(framework).not.toHaveTextContent("vendor quality signal pending");
  });

  it("renders theme breakout radar as observation-only proxy evidence", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          supported_outputs: ["market_gate", "sector_rank", "stock_candidates", "theme_breakout", "risk_exit"],
          theme_breakout: {
            as_of_date: "2026-05-08",
            formula_version: "rv_livermore_theme_breakout_proxy_v1",
            is_proxy: true,
            theme_count: 1,
            evidence_state: {
              concept_membership: {
                input_family: "concept_membership",
                status: "catalog_unconfirmed",
                row_count: 0,
                matched_row_count: 0,
                message: "Optional concept membership is not confirmed in the Choice stock catalog.",
              },
              intraday_movement: {
                input_family: "intraday_movement",
                status: "table_missing",
                table: "choice_stock_intraday_movement_event",
                row_count: 0,
                matched_row_count: 0,
                message: "Intraday movement table is not landed for this environment.",
              },
            },
            review_items: [
              {
                rank: 1,
                as_of_date: "2026-05-08",
                theme_key: "semiconductor_proxy_review",
                theme_name: "Semiconductor proxy",
                source_kind: "proxy",
                parent_sector_code: "801080",
                parent_sector_name: "Electronic",
                parent_sector_rank: 9,
                member_count: 2,
                advance_count: 2,
                advance_ratio: 1,
                strong_stock_count: 2,
                limit_stock_count: 0,
                avg_pctchange: 6.25,
                avg_turn: 4.1,
                avg_amplitude: 6.8,
                movement_event_count: 0,
                failed_gates: ["insufficient_cluster_strength"],
                observation_only: true,
                reason: "Observation-only near-miss: failed gates insufficient_cluster_strength.",
                items: [],
              },
            ],
            items: [
              {
                rank: 1,
                as_of_date: "2026-05-08",
                theme_key: "semiconductor_proxy",
                theme_name: "Semiconductor proxy",
                parent_sector_code: "801080",
                parent_sector_name: "Electronic",
                parent_sector_rank: 9,
                member_count: 3,
                advance_count: 3,
                advance_ratio: 1,
                strong_stock_count: 3,
                limit_stock_count: 2,
                avg_pctchange: 9.766667,
                avg_turn: 4.4,
                avg_amplitude: 7.3,
                observation_only: true,
                reason: "Observation-only proxy cluster: leaders 688001.SH, 688002.SH.",
                items: [
                  {
                    stock_code: "688001.SH",
                    stock_name: "Alpha Semiconductor",
                    sector_code: "801080",
                    sector_name: "Electronic",
                    sector_rank: 9,
                    open: 9.6,
                    high: 10.1,
                    low: 9.4,
                    close: 10,
                    pctchange: 12.1,
                    turn: 4.2,
                    amplitude: 7,
                    close_strength: 0.86,
                    closed_up_limit: true,
                    strong: true,
                  },
                ],
              },
            ],
          },
        }),
      }),
    });

    const section = await screen.findByTestId("stock-analysis-theme-breakout");
    expect(section).toHaveTextContent("题材突变观察");
    expect(section).toHaveTextContent("半导体领先");
    expect(section).toHaveTextContent("电子 #9");
    expect(section).toHaveTextContent("代理题材观察");
    expect(section).toHaveTextContent("Alpha Semiconductor");
    expect(section).not.toHaveTextContent("Semiconductor proxy");
    expect(screen.getByTestId("stock-analysis-theme-evidence-state")).toHaveTextContent("题材证据就绪");
    expect(screen.getByTestId("stock-analysis-theme-evidence-state")).toHaveTextContent("数据源缺失");
    expect(screen.getByTestId("stock-analysis-theme-evidence-state")).not.toHaveTextContent("数据表缺失");
    const reviewItems = screen.getByTestId("stock-analysis-theme-review-items");
    expect(reviewItems).toHaveTextContent("簇强度不足");
    expect(reviewItems).toHaveTextContent("强势样本未过门槛，保留观察");
    expect(screen.getByTestId("stock-analysis-theme-evidence-state")).not.toHaveTextContent("catalog_unconfirmed");
    expect(reviewItems).not.toHaveTextContent("insufficient_cluster_strength");
    expect(reviewItems).not.toHaveTextContent("Observation-only near-miss");
    expect(reviewItems).not.toHaveTextContent("failed gates");
    expect(section).not.toHaveTextContent("Observation-only proxy cluster");
    expect(section).not.toHaveTextContent("买入");
  });

  it("keeps theme evidence extras absent when optional payload fields are missing", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          supported_outputs: ["market_gate", "sector_rank", "stock_candidates", "theme_breakout", "risk_exit"],
          theme_breakout: {
            as_of_date: "2026-05-08",
            formula_version: "rv_livermore_theme_breakout_proxy_v1",
            is_proxy: true,
            theme_count: 0,
            items: [],
          },
        }),
      }),
    });

    await screen.findByTestId("stock-analysis-theme-breakout");
    expect(screen.queryByTestId("stock-analysis-theme-evidence-state")).not.toBeInTheDocument();
    expect(screen.queryByTestId("stock-analysis-theme-review-items")).not.toBeInTheDocument();
  });

  it("renders factor screen candidates with coverage boundaries and no trading action copy", async () => {
    const user = userEvent.setup();
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          supported_outputs: [
            "market_gate",
            "sector_rank",
            "stock_candidates",
            "factor_screen_candidates",
            "risk_exit",
          ],
          factor_screen_candidates: {
            as_of_date: "2026-04-30",
            formula_version: "rv_factor_screen_candidates_v1",
            market_state: "WARM",
            input_stock_count: 643,
            candidate_count: 1,
            coverage_note: "因子数据覆盖 643/5201 只，仅在有因子数据的股票里排序",
            items: [
              {
                rank: 1,
                stock_code: "600000.SH",
                stock_name: "Factor Alpha",
                sector_code: "801730",
                sector_name: "电力设备",
                industry: "电力设备",
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
        }),
      }),
    });

    const poolsCard = await screen.findByTestId("stock-analysis-mean-reversion");
    await user.click(within(poolsCard).getByTestId("stock-analysis-strategy-card-observation-pools-toggle"));

    expect(await screen.findByTestId("factor-preview-row-600000.SH")).toHaveTextContent("Factor Alpha");
    expect(screen.getByTestId("factor-preview-row-600000.SH")).toHaveTextContent("600000.SH");
    expect(screen.getAllByText(/因子数据覆盖 643\/5201 只/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("得分 0.812")).toBeInTheDocument();

    const page = screen.getByTestId("stock-analysis-page");
    expect(page).not.toHaveTextContent("买入");
    expect(page).not.toHaveTextContent("卖出");
    expect(page).not.toHaveTextContent("下单");
    expect(page).not.toHaveTextContent("调仓指令");
  });

  it("localizes factor screen coverage notes on the observation preview", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          supported_outputs: [
            "market_gate",
            "sector_rank",
            "stock_candidates",
            "factor_screen_candidates",
            "risk_exit",
          ],
          factor_screen_candidates: {
            as_of_date: "2026-04-30",
            formula_version: "rv_factor_screen_candidates_v1",
            market_state: "WARM",
            input_stock_count: 0,
            candidate_count: 0,
            coverage_note: "factor_snapshot 无数据",
            items: [],
          },
        }),
      }),
    });

    const preview = await screen.findByTestId("stock-analysis-observation-preview");
    expect(preview).toHaveTextContent("因子快照无数据");
    expect(preview).not.toHaveTextContent("factor_snapshot");
  });

  it("renders hybrid fusion candidates as the primary review queue", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          supported_outputs: [
            "market_gate",
            "sector_rank",
            "stock_candidates",
            "factor_screen_candidates",
            "hybrid_fusion",
            "risk_exit",
          ],
          hybrid_fusion_candidates: {
            as_of_date: "2026-04-29",
            formula_version: "rv_hybrid_fusion_candidates_v1",
            market_state: "WARM",
            observation_only: true,
            candidate_count: 1,
            coverage_note: "Hybrid fusion uses existing proxy inputs.",
            items: [
              {
                rank: 1,
                stock_code: "000009.SZ",
                stock_name: "Fusion Alpha",
                sector_code: "801009",
                sector_name: "机器",
                fusion_score: 0.812345,
                cycle_score: 0.7,
                lifecourt_proxy_score: 0.6,
                attention_score: 0.55,
                price_confirm_score: 0.8,
                crowding_penalty: 0.1,
                confidence: "medium",
                reason: "Fusion observation-only candidate",
                evidence: { source_kinds: ["factor_screen", "theme_breakout"] },
              },
            ],
          },
        }),
      }),
    });

    const queue = await screen.findByTestId("stock-analysis-review-queue");
    expect(queue).toHaveTextContent("融合策略 / 复核队列");
    expect(queue).toHaveTextContent("Fusion Alpha");
    expect(queue).toHaveTextContent("Fusion");
    expect(queue).toHaveTextContent("0.812345");
    expect(queue).toHaveTextContent("0.700000");
    expect(queue).toHaveTextContent("0.600000");
    expect(queue).toHaveTextContent("复核");
    expect(queue).not.toHaveTextContent("代理信号");
    expect(queue).not.toHaveTextContent("生命法庭代理");
    expect(queue).not.toHaveTextContent("关注代理");
    expect(queue).not.toHaveTextContent("代理信号");
    expect(queue).not.toHaveTextContent("买入");
  });

  it("does not label the review queue as hybrid when hybrid output is evidence-only", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          supported_outputs: [
            "market_gate",
            "sector_rank",
            "stock_candidates",
            "factor_screen_candidates",
            "hybrid_fusion",
            "risk_exit",
          ],
          hybrid_fusion_candidates: {
            as_of_date: "2026-04-29",
            formula_version: "rv_hybrid_fusion_candidates_v1",
            market_state: "WARM",
            observation_only: true,
            candidate_count: 1,
            coverage_note: "Hybrid fusion uses existing proxy inputs.",
            items: [
              {
                rank: 1,
                stock_code: "000009.SZ",
                stock_name: "Fusion Alpha",
                sector_code: "801009",
                sector_name: "机器",
                fusion_score: 0.812345,
                cycle_score: 0.7,
                lifecourt_proxy_score: 0.6,
                attention_score: 0.55,
                price_confirm_score: 0.8,
                crowding_penalty: 0.1,
                fusion_action: "core_plus_trading",
                confidence: "low",
                reason: "Fusion observation-only candidate",
                evidence: { source_kinds: ["factor_screen", "theme_breakout"] },
              },
            ],
          },
          module_states: readyModuleStates().map((state) =>
            state.key === "hybrid_fusion"
              ? {
                  ...state,
                  render_mode: "evidence_only",
                  evidence_scope: "detail",
                  excludes_from_primary: true,
                }
              : state,
          ),
        }),
      }),
    });

    const queue = await screen.findByTestId("stock-analysis-review-queue");
    const comparison = within(queue).getByTestId("stock-analysis-candidate-comparison");
    const criteria = within(comparison).getByTestId("stock-candidate-criteria-000001.SZ");
    expect(queue).toHaveTextContent("候选/ 复核队列");
    expect(queue).not.toHaveTextContent("融合策略 / 复核队列");
    expect(criteria).toHaveTextContent("口径");
    expect(criteria).not.toHaveTextContent("证据");
    expect(criteria).not.toHaveTextContent("边界");
    expect(criteria).not.toHaveTextContent("置信度");
    expect(criteria).not.toHaveTextContent("动作");
  });

  it("shows staleness banner when quality_flag is not ok", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({ metaOverrides: { quality_flag: "warning" } }),
    });

    const staleBanner = await screen.findByTestId("stock-analysis-stale-banner");
    expect(staleBanner).toHaveTextContent("供数异常");
    expect(staleBanner).toHaveTextContent("仅供复核参考");
    expect(staleBanner).not.toHaveTextContent("通道异常");
  });

  it("shows fallback snapshots as data that needs review", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({ metaOverrides: { fallback_mode: "latest_snapshot" } }),
    });

    const purpose = await screen.findByTestId("stock-analysis-page-purpose");
    const decisionPanel = await screen.findByTestId("stock-analysis-decision-panel");
    expect(purpose).toHaveTextContent("数据延迟");
    expect(purpose).not.toHaveTextContent("latest_snapshot");
    expect(decisionPanel).toHaveTextContent("数据延迟");
    expect(decisionPanel).toHaveTextContent("仅分析使用");
    expect(decisionPanel).not.toHaveTextContent("latest_snapshot");
    expect(await screen.findByTestId("stock-analysis-stale-banner")).toHaveTextContent(
      "仅供复核参考",
    );
  });

  it("renders closed-loop summary pass states on the first decision surface", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        confluence: buildConfluencePayload({
          adversarial_context: {
            status: "complete",
            mode: "anti_crowding_v1",
            risk_gate: "pass",
            position_scale: 0.75,
          },
          closed_loop_state: {
            entry_gate: "open",
            exit_gate: "watch",
            replay_status: "available",
            lineage_status: "complete",
          },
          replay_evidence: {
            status: "available",
            snapshot_as_of_date: "2026-04-29",
            row_count: 2,
            matched_entry_count: 1,
            sample_items: [
              {
                stock_code: "000001.SZ",
                stock_name: "Alpha",
                candidate_rank: 1,
                signal_kind: "stock_candidate",
                data_status: "complete",
              },
            ],
          },
        }),
      }),
    });

    const summary = await screen.findByTestId("stock-analysis-closed-loop-summary");
    const verdict = await screen.findByTestId("stock-analysis-closed-loop-verdict");
    await waitFor(() => expect(verdict).toHaveTextContent("可进入人工复核队列"), {
      timeout: 3_000,
    });
    expect(verdict).toHaveTextContent("可进入人工复核队列");
    expect(verdict).toHaveTextContent("边界");
    expect(verdict).toHaveTextContent("依据");
    expect(verdict).toHaveTextContent("依据明细");
    expect(verdict).not.toHaveTextContent("不推导策略收益");
    await userEvent.click(within(verdict).getByText("依据明细"));
    expect(verdict).toHaveTextContent("不推导策略收益");
    expect(summary).toHaveTextContent("闭环摘要");
    expect(summary).toHaveTextContent("触发");
    expect(summary).toHaveTextContent("入场观察门");
    expect(summary).toHaveTextContent("风险");
    expect(summary).toHaveTextContent("反拥挤拦截");
    expect(summary).toHaveTextContent("通过");
    expect(summary).toHaveTextContent("风险退出");
    expect(summary).toHaveTextContent("观察中");
    expect(summary).toHaveTextContent("回放证据");
    expect(summary).toHaveTextContent("已接通");
    expect(screen.getByTestId("stock-analysis-rail-check-matrix")).toBeInTheDocument();
    expect(summary).not.toHaveTextContent("2 条快照 / 覆盖 1 个当前候选");
    await userEvent.click(within(screen.getByTestId("stock-analysis-replay-status")).getByText("明细"));
    expect(summary).toHaveTextContent("2 条快照 / 覆盖 1 个当前候选");
    expect(summary).toHaveTextContent("血缘状态");
    expect(summary).toHaveTextContent("完整");
  });

  it("renders closed-loop blockers without turning them into trading advice", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        confluence: buildConfluencePayload({
          adversarial_context: {
            status: "complete",
            mode: "anti_crowding_v1",
            risk_gate: "block",
            position_scale: null,
            strongest_block_reason: "crowded leaders without breadth confirmation",
          },
          closed_loop_state: {
            entry_gate: "blocked",
            exit_gate: "triggered",
            replay_status: "available",
            lineage_status: "degraded",
          },
        }),
      }),
    });

    const summary = await screen.findByTestId("stock-analysis-closed-loop-summary");
    const decisionPanel = await screen.findByTestId("stock-analysis-decision-panel");
    const verdict = await screen.findByTestId("stock-analysis-closed-loop-verdict");
    await waitFor(() => expect(verdict).toHaveTextContent("闭环阻断，先复核约束项"), {
      timeout: 3_000,
    });
    expect(verdict).toHaveTextContent("闭环阻断，先复核约束项");
    expect(verdict).not.toHaveTextContent("保持仅观察输出");
    expect(decisionPanel).toHaveTextContent("展开供数与链路明细");
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).toHaveTextContent("门控 WARM");
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).not.toHaveTextContent("今日市场状态");
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).not.toHaveTextContent("闭环阻断，先复核约束项");
    expect(summary).toHaveTextContent("拦截");
    expect(summary).toHaveTextContent("阻断");
    expect(summary).toHaveTextContent("已触发");
    expect(summary).toHaveTextContent("降级");
    expect(summary).toHaveTextContent("依据明细");
    expect(summary).not.toHaveTextContent("crowded leaders without breadth confirmation");
    await userEvent.click(within(verdict).getByText("依据明细"));
    expect(summary).toHaveTextContent("强势样本拥挤，市场宽度未确认");
    expect(summary).not.toHaveTextContent("crowded leaders without breadth confirmation");
    expect(summary).not.toHaveTextContent("买入");
    expect(summary).not.toHaveTextContent("卖出");
  });

  it("renders missing closed-loop evidence as boundary-to-fill, not neutral proof", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        metaOverrides: {
          quality_flag: "warning",
          vendor_status: "vendor_unavailable",
          fallback_mode: "latest_snapshot",
        },
      }),
    });

    const summary = await screen.findByTestId("stock-analysis-closed-loop-summary");
    const decisionPanel = await screen.findByTestId("stock-analysis-decision-panel");
    const verdict = await screen.findByTestId("stock-analysis-closed-loop-verdict");
    expect(verdict).toHaveTextContent("数据不足");
    expect(verdict).toHaveTextContent("证据不足，不形成有效观察结论");
    expect(verdict).toHaveTextContent("依据明细");
    expect(verdict).not.toHaveTextContent("先补齐宏观反拥挤");
    await userEvent.click(within(verdict).getByText("依据明细"));
    expect(verdict).toHaveTextContent("先补齐宏观反拥挤");
    expect(decisionPanel).toHaveTextContent("展开供数与链路明细");
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).toHaveTextContent("门控 WARM");
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).not.toHaveTextContent("今日市场状态");
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).not.toHaveTextContent("证据不足，不形成有效观察结论");
    expect(summary).toHaveTextContent("数据不足");
    expect(summary).toHaveTextContent("待补");
    expect(summary).not.toHaveTextContent("不能视为有效证据");
    await userEvent.click(within(screen.getByTestId("stock-analysis-closed-loop-adversarial_gate")).getByText("明细"));
    expect(summary).toHaveTextContent("不能视为中性证明");
    expect(summary).not.toHaveTextContent("latest_snapshot");
    expect(screen.getByTestId("stock-analysis-boundary-summary")).toHaveTextContent("边界");
    expect(summary).not.toHaveTextContent("latest_snapshot");
  });

  it("renders degraded closed-loop evidence as pause on the first decision surface", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        confluence: buildConfluencePayload({
          adversarial_context: {
            status: "degraded",
            mode: "crowding_latest",
            risk_gate: "degraded",
            position_scale: 0,
          },
          closed_loop_state: {
            entry_gate: "open",
            exit_gate: "watch",
            replay_status: "available",
            lineage_status: "degraded",
          },
        }),
      }),
    });

    const summary = await screen.findByTestId("stock-analysis-closed-loop-summary");
    const decisionPanel = await screen.findByTestId("stock-analysis-decision-panel");
    const verdict = await screen.findByTestId("stock-analysis-closed-loop-verdict");
    await waitFor(() => expect(verdict).toHaveTextContent("暂缓复核，存在降级边界"), {
      timeout: 3_000,
    });
    expect(verdict).toHaveTextContent("暂缓复核，存在降级边界");
    expect(verdict).not.toHaveTextContent("保留观察队列");
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).toHaveTextContent("门控 WARM");
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).not.toHaveTextContent("暂缓复核，存在降级边界");
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).not.toHaveTextContent("今日市场状态");
    expect(summary).toHaveTextContent("暂缓");
    expect(summary).toHaveTextContent("降级");
    expect(summary).toHaveTextContent("依据明细");
    expect(summary).not.toHaveTextContent("仍有降级或仅观察边界");
    await userEvent.click(within(verdict).getByText("依据明细"));
    expect(summary).toHaveTextContent("保留观察队列");
  });

  it("renders replay window exclusions, counts, and proxy-only coverage without implying efficacy", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        confluence: buildConfluencePayload({
          adversarial_context: {
            status: "complete",
            mode: "anti_crowding_v1",
            risk_gate: "pass",
            position_scale: 0.5,
          },
          closed_loop_state: {
            entry_gate: "open",
            exit_gate: "watch",
            replay_status: buildReplayStatus({
              window_status: "partial",
              completed_dates: 1,
              pending_dates: 1,
              unsupported_dates: 1,
              proxy_only_dates: 1,
              completed_candidate_rows: 0,
              pending_candidate_rows: 17,
              unsupported_candidate_rows: 0,
              proxy_only_candidate_rows: 2,
              included_completed_stats_dates: ["2026-05-06"],
              blocked_dates: [
                {
                  trade_date: "2026-04-30",
                  status: "unsupported",
                  reason_code: "missing_daily_limit_flags",
                  signal_kinds: ["stock_candidate", "theme_breakout"],
                },
                {
                  trade_date: "2026-05-08",
                  status: "pending",
                  reason_code: "forward_returns_pending",
                  signal_kinds: ["stock_candidate", "theme_breakout"],
                },
                {
                  trade_date: "2026-05-07",
                  status: "proxy_only",
                  reason_code: "proxy_theme_only",
                  signal_kinds: ["theme_breakout"],
                },
              ],
              completed_zero_signal_dates: ["2026-05-06"],
            }),
            lineage_status: "complete",
          },
        }),
      }),
    });

    const replayStatus = await screen.findByTestId("stock-analysis-replay-status");
    await waitFor(() => expect(replayStatus).toHaveTextContent("明细"), {
      timeout: 3_000,
    });
    expect(replayStatus).not.toHaveTextContent("2026-04-30");
    await userEvent.click(within(replayStatus).getByText("明细"));
    expect(replayStatus).toHaveTextContent("涨跌停标记缺失");
    expect(replayStatus).toHaveTextContent("2026-05-08");
    expect(replayStatus).toHaveTextContent("远期收益待成熟");
    expect(replayStatus).toHaveTextContent("2026-05-07");
    expect(replayStatus).toHaveTextContent("仅代理题材");
    expect(replayStatus).toHaveTextContent("完成但无信号日期：2026-05-06");
    expect(replayStatus).toHaveTextContent("仅作观察，不推导策略有效性");
    expect(replayStatus).toHaveTextContent("完成 1日");
    expect(replayStatus).toHaveTextContent("待成熟 1日");
    expect(replayStatus).toHaveTextContent("不可用 1日");
    expect(replayStatus).toHaveTextContent("代理观察 1日");
    expect(replayStatus).not.toHaveTextContent("proxy_theme_only");
    expect(replayStatus).not.toHaveTextContent("do not infer strategy efficacy");
    expect(replayStatus).not.toHaveTextContent("unsupported dates");
    expect(replayStatus).not.toHaveTextContent("proxy-only dates");
  });

  it("renders refresh control and exposes as-of picker", async () => {
    renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });

    expect(await screen.findByTestId("stock-analysis-refresh")).toBeInTheDocument();
    expect(screen.getByTestId("stock-analysis-as-of-picker")).toBeInTheDocument();
  });

  it("recomputes choice-stock inputs before refetching the review queue", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    const workbenchSpy = vi.spyOn(client, "getStockAnalysisWorkbench");
    const refreshSpy = vi.spyOn(client, "refreshChoiceStock");
    const refreshStatusSpy = vi.spyOn(client, "getChoiceStockRefreshStatus");

    renderWorkbenchApp(["/stock-analysis"], { client });

    await screen.findByTestId("stock-comparison-candidate-row-000001.SZ");
    const initialWorkbenchCalls = workbenchSpy.mock.calls.length;

    await user.click(screen.getByTestId("stock-analysis-refresh"));

    await waitFor(() => {
      expect(refreshSpy).toHaveBeenCalledWith({
        asOfDate: "2026-04-29",
        refreshHistory: true,
        refreshFactors: true,
        factorMaxStockCount: null,
      });
    });
    await waitFor(() => {
      expect(refreshStatusSpy).toHaveBeenCalledWith("choice_stock_refresh:mock");
    });
    await waitFor(() => {
      expect(workbenchSpy.mock.calls.length).toBeGreaterThan(initialWorkbenchCalls);
    });
    expect(screen.getByTestId("stock-analysis-refresh-feedback")).toHaveTextContent("选股已重新计算");
  });

  it("keeps failed choice-stock recompute auditable and retryable", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    vi.spyOn(client, "refreshChoiceStock").mockResolvedValue(
      buildMockApiEnvelope("macro_toolkit.choice_stock_refresh", {
        refresh: {
          status: "queued",
          run_id: "choice_stock_refresh:failed",
          trigger_mode: "async",
        },
        choice_stock_refresh: {
          permission: {
            mode: "scoped_refresh",
            allowed: true,
            resource: "macro_toolkit.choice_stock",
            actions: ["history", "factor_snapshot"],
          },
        },
      }),
    );
    vi.spyOn(client, "getChoiceStockRefreshStatus").mockResolvedValue(
      buildMockApiEnvelope("macro_toolkit.choice_stock_refresh_status", {
        refresh: {
          status: "failed",
          run_id: "choice_stock_refresh:failed",
          trigger_mode: "terminal",
          error_message: "vendor snapshot unavailable",
          failure_category: "source_unavailable",
        },
        choice_stock_refresh: {
          permission: {
            mode: "scoped_refresh",
            allowed: true,
            resource: "macro_toolkit.choice_stock",
            actions: ["history", "factor_snapshot"],
          },
        },
      }),
    );

    renderWorkbenchApp(["/stock-analysis"], { client });

    await screen.findByTestId("stock-comparison-candidate-row-000001.SZ");
    await user.click(screen.getByTestId("stock-analysis-refresh"));

    const feedback = await screen.findByTestId("stock-analysis-refresh-feedback");
    await waitFor(() => expect(feedback).toHaveTextContent("选股刷新失败"));
    expect(feedback).toHaveTextContent("vendor snapshot unavailable");
    expect(feedback).toHaveTextContent("choice_stock_refresh:failed");
    expect(feedback).toHaveAttribute("data-tone", "negative");
    expect(screen.getByTestId("stock-analysis-refresh")).not.toBeDisabled();
  });

  it("filters candidates when industry chip clicked", async () => {
    const user = userEvent.setup();
    renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });

    expect(await screen.findByTestId("stock-comparison-candidate-row-000001.SZ")).toBeInTheDocument();
    expect(screen.getByTestId("stock-analysis-sector-review-link")).toHaveTextContent("全部行业");
    expect(screen.getByTestId("stock-analysis-sector-review-link")).toHaveTextContent("2 个候选");
    expect(screen.getByTestId("stock-review-filter-status")).toHaveTextContent("全部行业");
    expect(screen.getByTestId("stock-review-filter-status")).toHaveTextContent("显示 2 / 2 个候选");
    await user.click(screen.getByTestId("sector-filter-chip-801002"));

    await waitFor(() => {
      expect(screen.queryByTestId("stock-comparison-candidate-row-000001.SZ")).not.toBeInTheDocument();
      expect(screen.getByTestId("stock-comparison-candidate-row-000002.SZ")).toBeInTheDocument();
    });
    expect(screen.getByTestId("sector-filter-chip-801002")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "全部行业" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByTestId("stock-review-filter-status")).toHaveTextContent("新能源车");
    expect(screen.getByTestId("stock-review-filter-status")).toHaveTextContent("显示 1 / 2 个候选");
    expect(screen.getByTestId("stock-analysis-sector-review-link")).toHaveTextContent("新能源车");
    expect(screen.getByTestId("stock-analysis-sector-review-link")).toHaveTextContent("1 个候选");
    expect(screen.getByTestId("stock-analysis-sector-review-link")).toHaveTextContent("Beta");
    expect(screen.getByTestId("stock-comparison-candidate-row-000002.SZ")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "全部行业" }));
    await screen.findByTestId("stock-comparison-candidate-row-000001.SZ");
    expect(screen.getByRole("button", { name: "全部行业" })).toHaveAttribute("aria-pressed", "true");
  });

  it("keeps the review queue ordered by candidate rank instead of pattern label", async () => {
    const strategy = buildStrategyPayload();
    const rankedByBackend = strategy.stock_candidates?.items ?? [];
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: {
          ...strategy,
          stock_candidates: {
            ...strategy.stock_candidates!,
            items: [
              {
                ...rankedByBackend[1],
                rank: 1,
                stock_code: "000101.SZ",
                stock_name: "Rank One Consolidation",
                close: 10,
                breakout_level: 10,
                abnormal_turnover: 1,
                gap_norm: 0.01,
              },
              {
                ...rankedByBackend[0],
                rank: 2,
                stock_code: "000202.SZ",
                stock_name: "Rank Two Breakout",
                close: 10.08,
                breakout_level: 10,
                abnormal_turnover: 1.3,
                gap_norm: 0.08,
              },
            ],
          },
        },
      }),
    });

    const queue = await screen.findByTestId("stock-analysis-review-queue");
    await openReviewQueueTable();

    const cards = Array.from(queue.querySelectorAll("tr[data-testid^='stock-candidate-']")).map((node) =>
      node.getAttribute("data-testid"),
    );
    expect(cards).toEqual(["stock-candidate-000101.SZ", "stock-candidate-000202.SZ"]);
    expect(screen.getByTestId("stock-analysis-review-queue-table")).toHaveTextContent("#1");
    expect(screen.getByTestId("stock-analysis-review-queue-table")).toHaveTextContent("Rank One Consolidation");
  });

  it("shows an empty review queue state when a sector bar has no candidates", async () => {
    const user = userEvent.setup();
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          sector_rank: {
            ...buildStrategyPayload().sector_rank!,
            sector_count: 3,
            items: [
              ...buildStrategyPayload().sector_rank!.items,
              {
                rank: 3,
                sector_code: "801003",
                sector_name: "无候选风险",
                score: 0.7,
                avg_pctchange: 0.1,
                avg_turn: 1.2,
                avg_amplitude: 1.5,
                constituent_count: 5,
              },
            ],
          },
        }),
      }),
    });

    expect(await screen.findByTestId("stock-comparison-candidate-row-000001.SZ")).toBeInTheDocument();
    await user.click(screen.getByTestId("sector-bar-801003"));

    await waitFor(() => {
      expect(screen.queryByTestId("stock-comparison-candidate-row-000001.SZ")).not.toBeInTheDocument();
      expect(screen.queryByTestId("stock-comparison-candidate-row-000002.SZ")).not.toBeInTheDocument();
    });
    expect(screen.getByTestId("stock-review-filter-status")).toHaveTextContent("无候选风险");
    expect(screen.getByTestId("stock-review-filter-status")).toHaveTextContent("显示 0 / 2 个候选");
    expect(screen.getByTestId("stock-analysis-sector-review-link")).toHaveTextContent("无候选风险");
    expect(screen.getByTestId("stock-analysis-sector-review-link")).toHaveTextContent("无候选");
    expect(screen.getByTestId("stock-analysis-sector-review-link")).toHaveTextContent("该行业暂无线索");
    expect(screen.getByTestId("stock-analysis-review-queue-filter-empty")).toHaveTextContent("行业筛选");
    expect(screen.getByTestId("stock-analysis-review-queue-filter-empty")).toHaveTextContent("0 候选");
    expect(screen.queryByTestId("stock-analysis-review-queue-ranking-chart")).not.toBeInTheDocument();
  });

  it("connects the boundary summary to the full diagnostics drawer", async () => {
    const user = userEvent.setup();
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          data_gaps: [
            {
              input_family: "external_vendor_factor_feed",
              status: "vendor_sync_delayed",
              evidence: "external_vendor_factor_feed 未落地。",
            },
          ],
          supported_outputs: ["market_gate", "external_vendor_alpha_output"],
          unsupported_outputs: [
            {
              key: "external_vendor_alpha_output",
              reason: "external_vendor_alpha_output pending.",
            },
          ],
        } as unknown as Partial<LivermoreStrategyPayload>),
      }),
    });

    const decisionPanel = await screen.findByTestId("stock-analysis-decision-panel");
    expect(decisionPanel).toHaveTextContent("边界");

    const boundarySummary = screen.getByTestId("stock-analysis-boundary-summary");
    expect(boundarySummary).toHaveTextContent("3 条边界");
    expect(boundarySummary).toHaveTextContent("诊断 1 / 缺口 1 / 阻断 1");
    expect(boundarySummary).not.toHaveTextContent("边界 1");
    const boundaryRail = screen.getByTestId("stock-analysis-boundary-rail");
    expect(boundaryRail).toHaveTextContent("数据日期");
    expect(boundaryRail).toHaveTextContent("规则版本");
    expect(boundaryRail).toHaveTextContent("数据质量");
    expect(boundaryRail).toHaveTextContent("例外状态");
    expect(boundaryRail).not.toHaveTextContent("sv_livermore_test");
    expect(boundaryRail).not.toHaveTextContent("trace");
    expect(boundaryRail).not.toHaveTextContent("Breadth inputs are unavailable.");

    const firstScreen = await screen.findByTestId("stock-analysis-first-screen-workbench");
    const diagnosticsEntry = within(firstScreen).getByTestId("stock-analysis-home-rail-diagnostic-entry");
    expect(within(boundaryRail).queryByRole("button")).not.toBeInTheDocument();
    expect(diagnosticsEntry).toHaveAttribute("aria-expanded", "false");

    await user.click(diagnosticsEntry);

    await waitFor(() => {
      expect(diagnosticsEntry).toHaveAttribute("aria-expanded", "true");
    });

    expect(await screen.findByText("数据口径诊断")).toBeInTheDocument();
    expect(screen.getByText("警告")).toBeInTheDocument();
    expect(screen.queryByText("严重 / Error")).not.toBeInTheDocument();
    expect(screen.queryByText("警告 / Warning")).not.toBeInTheDocument();
    expect(screen.queryByText("信息 / Info")).not.toBeInTheDocument();
    expect(screen.getAllByText("市场宽度输入不可用。").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("数据缺口")).toBeInTheDocument();
    expect(screen.getAllByText("输入待确认").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("状态待确认")).toBeInTheDocument();
    expect(screen.queryAllByText(/breadth/)).toHaveLength(0);
    expect(screen.queryByText(/vendor_sync_delayed/)).not.toBeInTheDocument();
    expect(screen.queryByText(/external_vendor_factor_feed/)).not.toBeInTheDocument();
    expect(screen.getByText("阻断输出")).toBeInTheDocument();
    expect(screen.getAllByText("输出待确认").length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText(/external_vendor_alpha_output/)).not.toBeInTheDocument();
    expect(screen.queryByText(/external vendor alpha output/)).not.toBeInTheDocument();
    expect(screen.queryByText("data_gaps")).not.toBeInTheDocument();
    expect(screen.queryByText("unsupported_outputs")).not.toBeInTheDocument();
  });

  it("renders event monitoring with business labels instead of raw backend fields", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          unsupported_outputs: [
            {
              key: "theme_breakout",
              reason: "concept membership table pending",
            },
          ],
        }),
      }),
    });

    const section = await screen.findByTestId("stock-analysis-events-monitoring");
    expect(section).toHaveTextContent("诊断");
    expect(section).toHaveTextContent("缺口");
    expect(section).toHaveTextContent("题材观察阻断");
    expect(section).toHaveTextContent("概念归属待确认");
    expect(section).not.toHaveTextContent("概念归属表待补");
    expect(section).toHaveTextContent("低");
    expect(section).toHaveTextContent("低");
    expect(section).toHaveTextContent("市场宽度");
    expect(section).toHaveTextContent("市场宽度诊断");
    expect(section).not.toHaveTextContent("LIVERMORE_BREADTH_MISSING");
    expect(section).not.toHaveTextContent("data_gap");
    expect(section).not.toHaveTextContent("concept membership table pending");
    expect(section).not.toHaveTextContent("risk_exit");
    expect(section).not.toHaveTextContent("warning");
    expect(section).not.toHaveTextContent("missing");
  });

  it("renders unknown event diagnostics as pending business copy instead of raw backend codes", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          diagnostics: [
            {
              severity: "warning",
              code: "VENDOR_QUALITY_SIGNAL_PENDING",
              message: "vendor_quality_signal_pending",
              input_family: "external_vendor_quality_signal",
            },
          ],
          data_gaps: [],
          unsupported_outputs: [],
        } as Partial<LivermoreStrategyPayload>),
      }),
    });

    const section = await screen.findByTestId("stock-analysis-events-monitoring");
    expect(section).toHaveTextContent("输入待确认诊断");
    expect(section).toHaveTextContent("说明待确认");
    expect(section).not.toHaveTextContent("external_vendor_quality_signal");
    expect(section).not.toHaveTextContent("vendor_quality_signal_pending");
    expect(section).not.toHaveTextContent("VENDOR_QUALITY_SIGNAL_PENDING");
  });

  it("localizes unknown vendor data-gap evidence in event monitoring", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          diagnostics: [],
          data_gaps: [
            {
              input_family: "breadth",
              status: "missing",
              evidence: "external_vendor_breadth_signal_ready",
            },
          ],
          unsupported_outputs: [],
        } as Partial<LivermoreStrategyPayload>),
      }),
    });

    const section = await screen.findByTestId("stock-analysis-events-monitoring");
    expect(section).toHaveTextContent("市场宽度");
    expect(section).toHaveTextContent("说明待确认");
    expect(section).not.toHaveTextContent("external_vendor_breadth_signal_ready");
    expect(section).not.toHaveTextContent("external vendor breadth signal ready");
  });

  it("shows localized theme breakout blockers in the first-screen empty tile", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          unsupported_outputs: [
            {
              key: "theme_breakout",
              reason:
                "Theme breakout execution is paused in OVERHEAT; historical replay showed this bucket is draggy.",
            },
          ],
        }),
      }),
    });

    const themeLeaders = await screen.findByTestId("stock-analysis-theme-leaders-first-screen");
    const blocker = within(themeLeaders).getByTestId("stock-analysis-theme-leader-empty");
    expect(blocker).toHaveTextContent("门控暂停");
    expect(blocker).toHaveAttribute("title", expect.stringContaining("市场过热门控下暂停题材观察"));
    expect(blocker).toHaveAttribute("title", expect.stringContaining("历史回放显示该桶拖累"));
    expect(themeLeaders).not.toHaveTextContent("Theme breakout execution is paused");
    expect(themeLeaders).not.toHaveTextContent("theme_breakout");
  });

  it("avoids forbidden trading copy", async () => {
    renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });

    expect(await screen.findByTestId("market-workbench-topbar")).toHaveTextContent("股票分析");

    await waitFor(() => {
      expect(screen.queryByText(/买入建议/)).not.toBeInTheDocument();
      expect(screen.queryByText(/卖出建议/)).not.toBeInTheDocument();
      expect(screen.queryByText(/下单/)).not.toBeInTheDocument();
      expect(screen.queryByText(/调仓指令/)).not.toBeInTheDocument();
    });
  });

  it("shows strategy API failure state", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({ strategyError: new Error("strategy unavailable") }),
    });

    const errorPanel = await screen.findByTestId("stock-analysis-error-workbench");
    expect(errorPanel).toHaveTextContent("股票分析暂不可用");
    expect(screen.getByText("策略服务暂不可用，请稍后重试。")).toBeInTheDocument();
    expect(within(errorPanel).getByTestId("stock-analysis-error-decision-panel")).toHaveTextContent("第一屏结论");
    expect(errorPanel).toHaveTextContent("后端供数没通，今天先不做个股复核");
    expect(errorPanel).toHaveTextContent("供数");
    expect(errorPanel).toHaveTextContent("待恢复");
    expect(errorPanel).toHaveTextContent("结论");
    expect(errorPanel).toHaveTextContent("暂停");
    expect(screen.queryByText("strategy unavailable")).not.toBeInTheDocument();
    expect(screen.queryByText("股票分析结果加载失败。")).not.toBeInTheDocument();
  });

  it("localizes permission failures without exposing backend table names", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategyError: new Error("User is not allowed to read market_data.livermore."),
      }),
    });

    const errorPanel = await screen.findByTestId("stock-analysis-error-workbench");
    expect(errorPanel).toHaveTextContent("数据权限待确认，请联系管理员。");
    expect(errorPanel).not.toHaveTextContent("User is not allowed");
    expect(errorPanel).not.toHaveTextContent("market_data.livermore");
  });

  it("localizes transport failures without exposing backend routes", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategyError: new Error("Request failed: /ui/market-data/livermore (502)"),
      }),
    });

    const errorPanel = await screen.findByTestId("stock-analysis-error-workbench");
    expect(errorPanel).toHaveTextContent("供数暂不可用，请稍后复核。");
    expect(errorPanel).not.toHaveTextContent("Request failed");
    expect(errorPanel).not.toHaveTextContent("/ui/market-data/livermore");
    expect(errorPanel).not.toHaveTextContent("livermore");
  });

  it("localizes not found failures without leaving the first screen empty", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategyError: new Error("Not Found"),
      }),
    });

    const errorPanel = await screen.findByTestId("stock-analysis-error-workbench");
    expect(errorPanel).toHaveTextContent("供数暂不可用，请稍后复核。");
    expect(errorPanel).toHaveTextContent("第一屏结论");
    expect(errorPanel).toHaveTextContent("后端供数没通，今天先不做个股复核");
    expect(errorPanel).not.toHaveTextContent("Not Found");
  });

  it("localizes strategy source-table failures without exposing backend tables", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategyError: new Error(
          "Request failed: /ui/market-data/livermore because source_table choice_stock_strategy_payload is missing.",
        ),
      }),
    });

    const errorPanel = await screen.findByTestId("stock-analysis-error-workbench");
    expect(errorPanel).toHaveTextContent("数据源缺失");
    expect(errorPanel).not.toHaveTextContent("Request failed");
    expect(errorPanel).not.toHaveTextContent("/ui/market-data/livermore");
    expect(errorPanel).not.toHaveTextContent("source_table");
    expect(errorPanel).not.toHaveTextContent("choice_stock_strategy_payload");
  });

  it("keeps the page usable when signal confluence fails", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({ confluenceError: new Error("confluence unavailable") }),
    });

    expect(await screen.findByRole("heading", { name: "风险退出观察" })).toBeInTheDocument();
    expect(await screen.findByText("联动观察暂不可用。")).toBeInTheDocument();
  });

  it("shows the risk exit blocker when the strategy marks risk_exit unsupported", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          supported_outputs: ["market_gate", "sector_rank", "stock_candidates"],
          unsupported_outputs: [
            {
              key: "risk_exit",
              reason: "livermore_position_snapshot has no ACTIVE A-share rows.",
            },
          ],
          risk_exit: undefined,
        }),
      }),
    });

    const section = await screen.findByTestId("stock-analysis-risk-section");
    expect(within(section).getByText("风险退出待补")).toBeInTheDocument();
    expect(section).toHaveTextContent("持仓快照缺失");
    expect(section).not.toHaveTextContent("livermore_position_snapshot has no ACTIVE A-share rows.");

    await userEvent.click(within(section).getByText("供数原因"));

    expect(section).toHaveTextContent("持仓快照缺失");
    expect(section).not.toHaveTextContent("livermore_position_snapshot has no ACTIVE A-share rows.");
  });

  it("localizes unknown risk exit blocker reasons before showing the first-screen rail", async () => {
    const sourceTableRiskExitSignal = "sourceTableRiskExitSignal";
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          supported_outputs: ["market_gate", "sector_rank", "stock_candidates"],
          unsupported_outputs: [
            {
              key: "risk_exit",
              reason: sourceTableRiskExitSignal,
            },
          ],
          risk_exit: undefined,
        }),
      }),
    });

    const section = await screen.findByTestId("stock-analysis-risk-section");
    expect(section).toHaveTextContent("风险退出待补");
    expect(section).toHaveTextContent("风险退出待确认");
    expect(section).not.toHaveTextContent(sourceTableRiskExitSignal);

    await userEvent.click(within(section).getByText("供数原因"));

    expect(section).toHaveTextContent("风险退出待确认");
    expect(section).not.toHaveTextContent(sourceTableRiskExitSignal);
  });

  it("shows a business pending label when risk exit is blocked without a backend reason", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          supported_outputs: ["market_gate", "sector_rank", "stock_candidates"],
          unsupported_outputs: [
            {
              key: "risk_exit",
              reason: "",
            },
          ],
          risk_exit: undefined,
        }),
      }),
    });

    const section = await screen.findByTestId("stock-analysis-risk-section");
    expect(section).toHaveTextContent("风险退出待补");
    expect(section).toHaveTextContent("供数状态待确认");
    expect(section).not.toHaveTextContent("后端原因待补");
  });

  it("keeps risk rows compact until backend reason is requested", async () => {
    renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });

    const section = await screen.findByTestId("stock-analysis-risk-section");
    const riskStrip = within(section).getByTestId("stock-analysis-risk-strip");
    expect(riskStrip).toHaveTextContent("触发");
    expect(riskStrip).toHaveTextContent("观察");
    expect(riskStrip).toHaveTextContent("供数");
    expect(section).toHaveTextContent("1 触发");
    expect(section).toHaveTextContent("1 观察");
    expect(section).toHaveTextContent("收 9.10");
    expect(section).toHaveTextContent("距 -10.78%");
    expect(section).toHaveTextContent("供数原因");
    expect(section).not.toHaveTextContent("触发复核d_below_ema10");
    expect(section).not.toHaveTextContent("连续 2 日收盘低于 10 日均线");

    await userEvent.click(within(section).getAllByText("供数原因")[0]);

    expect(section).toHaveTextContent("触发复核：连续 2 日收盘低于 10 日均线");
    expect(section).not.toHaveTextContent("触发复核d_below_ema10");
  });

  it("surfaces blocked backend outputs in the hero supply details", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          data_gaps: [
            {
              input_family: "position_risk",
              status: "missing",
              evidence: "Position snapshot is missing.",
            },
          ],
          supported_outputs: ["market_gate", "sector_rank", "stock_candidates"],
          unsupported_outputs: [
            {
              key: "risk_exit",
              reason: "livermore_position_snapshot has no ACTIVE A-share rows.",
            },
          ],
          risk_exit: undefined,
        }),
      }),
    });

    expect(screen.queryByTestId("stock-analysis-supply-details-toggle")).not.toBeInTheDocument();

    const riskSection = await screen.findByTestId("stock-analysis-risk-section");
    expect(riskSection).toHaveTextContent("风险退出待补");
    expect(riskSection).toHaveTextContent("持仓快照缺失");
    expect(riskSection).not.toHaveTextContent("risk_exit");
    expect(riskSection).not.toHaveTextContent("livermore_position_snapshot");
    expect(riskSection).not.toHaveTextContent("Position snapshot");
  });

  it("loads sector rank series when multi-day collapse opens", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    const spy = vi.spyOn(client, "getLivermoreSectorRankSeries");

    renderWorkbenchApp(["/stock-analysis"], { client });

    expect(await screen.findByTestId("stock-analysis-sector-bars")).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();
    expect(screen.getByTestId("stock-analysis-sector-strength-panel")).not.toHaveTextContent("avg_pctchange");
    expect(screen.getByTestId("stock-analysis-sector-strength-panel")).not.toHaveTextContent("unsupported_notes");

    await user.click(screen.getByRole("button", { name: /多日强弱/ }));

    await waitFor(() => {
      expect(spy).toHaveBeenCalled();
    });

    await screen.findByTestId("sector-series-row-801001");
    expect(screen.getByTestId("sector-series-row-801001")).toHaveTextContent("AI");
    expect(screen.getByTestId("stock-analysis-sector-series-chart")).toBeInTheDocument();
    expect(screen.getByTestId("stock-analysis-sector-series-pending")).toHaveTextContent("动量持续度");
    expect(screen.getByTestId("stock-analysis-sector-series-pending")).toHaveTextContent("板块资金流向");
    expect(screen.getByTestId("stock-analysis-sector-series-panel")).not.toHaveTextContent("cum_pctchange_window");
    spy.mockRestore();
  });

  it("keeps multi-day sector series available when the main sector snapshot is missing", async () => {
    const user = userEvent.setup();
    const client = stockClient({
      strategy: buildStrategyPayload({
        supported_outputs: ["market_gate", "factor_screen_candidates", "hybrid_fusion"],
        unsupported_outputs: [
          {
            key: "sector_rank",
            reason: "sector_rank snapshot is unavailable for this observation date.",
          },
        ],
        sector_rank: undefined,
      }),
    });
    const spy = vi.spyOn(client, "getLivermoreSectorRankSeries");

    renderWorkbenchApp(["/stock-analysis"], { client });

    await waitFor(() =>
      expect(spy).toHaveBeenCalledWith(
        expect.objectContaining({ asOfDate: "2026-04-29", windowDays: 5, topK: 10 }),
      ),
    );
    const sectorPanel = await screen.findByTestId("stock-analysis-sector-strength-panel");
    expect(await screen.findByTestId("stock-analysis-sector-bars")).toBeInTheDocument();
    expect(await screen.findByTestId("sector-bar-801001")).toHaveTextContent("AI");
    expect(sectorPanel).not.toHaveTextContent("板块待补");

    await user.click(screen.getByText("多日强弱"));

    expect(await screen.findByTestId("stock-analysis-sector-series-panel")).toBeInTheDocument();
    expect(await screen.findByTestId("sector-series-row-801001")).toHaveTextContent("AI");
    spy.mockRestore();
  });

  it("does not use the requested date for sector rank series when a requested date falls back", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    const strategySpy = mockStrategyLatestSnapshotFallback(client);
    const seriesSpy = vi.spyOn(client, "getLivermoreSectorRankSeries");

    renderWorkbenchApp(["/stock-analysis"], { client });

    await requestStockAnalysisAsOfDate(user, strategySpy);
    const sectorSeriesButton = screen.getByRole("button", { name: /多日强弱/ });
    await user.click(sectorSeriesButton);
    await waitFor(() => expect(sectorSeriesButton).toHaveAttribute("aria-expanded", "true"));
    expect(seriesSpy).not.toHaveBeenCalledWith(
      expect.objectContaining({ asOfDate: "2026-05-08" }),
    );
  });

  it("does not load sector rank series with only the requested date when no data date is resolved", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    const strategySpy = vi.spyOn(client, "getStockAnalysisWorkbench").mockImplementation(async (options) => {
      const strategy = buildStrategyPayload({
        as_of_date: options?.asOfDate ? null : "2026-04-29",
        requested_as_of_date: options?.asOfDate ?? null,
      });
      return buildMockApiEnvelope(
        "market_data.stock_analysis.workbench",
        buildStockAnalysisWorkbenchPayload(strategy),
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_livermore_test",
          vendor_version: "vv_livermore_test",
          rule_version: "rv_stock_analysis_workbench_v1",
          fallback_mode: options?.asOfDate ? "latest_snapshot" : "none",
        },
      );
    });
    const legacyStrategySpy = vi.spyOn(client, "getLivermoreStrategy").mockImplementation(async (options) =>
      buildMockApiEnvelope(
        "market_data.livermore",
        buildStrategyPayload({
          as_of_date: options?.asOfDate ? null : "2026-04-29",
          requested_as_of_date: options?.asOfDate ?? null,
        }),
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_livermore_test",
          vendor_version: "vv_livermore_test",
          rule_version: "rv_livermore_market_gate_v1",
          fallback_mode: options?.asOfDate ? "latest_snapshot" : "none",
        },
      ),
    );
    const seriesSpy = vi.spyOn(client, "getLivermoreSectorRankSeries");

    renderWorkbenchApp(["/stock-analysis"], { client });

    expect(await screen.findByTestId("stock-analysis-sector-bars")).toBeInTheDocument();
    await requestStockAnalysisAsOfDate(user, strategySpy, "2026-05-08", "2026-05-08");
    await user.click(screen.getByText("多日强弱"));

    await waitFor(() => expect(screen.getByTestId("stock-analysis-sector-series-panel")).toBeInTheDocument());
    expect(legacyStrategySpy).not.toHaveBeenCalled();
    expect(seriesSpy).not.toHaveBeenCalled();
  });

  it("shows sector series failure alert without breaking sector bars", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    vi.spyOn(client, "getLivermoreSectorRankSeries").mockRejectedValue(
      new Error(
        "Failed to fetch sector rank series from /ui/market-data/livermore/sector-rank-series because source_table choice_stock_sector_rank_series is missing.",
      ),
    );

    renderWorkbenchApp(["/stock-analysis"], { client });

    expect(await screen.findByTestId("stock-analysis-sector-bars")).toBeInTheDocument();
    await user.click(screen.getByText("多日强弱"));

    expect(await screen.findByText("多日板块序列加载失败")).toBeInTheDocument();
    const panel = screen.getByTestId("stock-analysis-sector-series-panel");
    expect(panel).toHaveTextContent("数据源缺失");
    expect(panel).not.toHaveTextContent("Failed to fetch");
    expect(panel).not.toHaveTextContent("/ui/market-data/livermore/sector-rank-series");
    expect(panel).not.toHaveTextContent("source_table");
    expect(panel).not.toHaveTextContent("choice_stock_sector_rank_series");
    expect(screen.getByTestId("stock-analysis-sector-bars")).toBeInTheDocument();
  });

  it("opens stock detail drawer when 复核 K 线is clicked", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    const spy = vi.spyOn(client, "getLivermoreStockDetail");

    renderWorkbenchApp(["/stock-analysis"], { client });

    await screen.findByTestId("stock-comparison-candidate-row-000001.SZ");
    await user.click(screen.getByTestId("stock-comparison-candidate-review-000001.SZ"));

    await waitFor(() =>
      expect(spy).toHaveBeenCalledWith(
        expect.objectContaining({ stockCode: "000001.SZ" }),
      ),
    );
    expect(await screen.findByTestId("stock-detail-drawer")).toBeInTheDocument();
    expect(screen.getByTestId("stock-detail-review-context")).toHaveTextContent("复核队列");
    expect(screen.getByTestId("stock-detail-review-context")).toHaveTextContent("#1");
    expect(screen.getByTestId("stock-detail-review-context")).toHaveTextContent("AI");
  });

  it("opens stock detail with the resolved data date when a requested date falls back", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    const strategySpy = mockStrategyLatestSnapshotFallback(client);
    const detailSpy = vi.spyOn(client, "getLivermoreStockDetail");

    renderWorkbenchApp(["/stock-analysis"], { client });

    await requestStockAnalysisAsOfDate(user, strategySpy);
    const decisionPanel = screen.getByTestId("stock-analysis-decision-panel");
    expect(decisionPanel).toHaveTextContent("数据日期");
    expect(decisionPanel).toHaveTextContent("2026-04-29");
    expect(decisionPanel).toHaveTextContent("请求日期");
    expect(decisionPanel).toHaveTextContent("2026-05-08");

    await user.click(screen.getByTestId("stock-comparison-candidate-review-000001.SZ"));

    await waitFor(() =>
      expect(detailSpy).toHaveBeenCalledWith(
        expect.objectContaining({ stockCode: "000001.SZ", asOfDate: "2026-04-29" }),
      ),
    );
    expect(detailSpy).not.toHaveBeenCalledWith(
      expect.objectContaining({ stockCode: "000001.SZ", asOfDate: "2026-05-08" }),
    );
  });

  it("loads first-screen strategy diagnostics with the resolved data date when a requested date falls back", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    const strategySpy = mockStrategyLatestSnapshotFallback(client, {
      initialAsOfDate: "2026-04-28",
      resolvedAsOfDate: "2026-04-29",
    });
    const strategyScoreSpy = vi.spyOn(client, "getLivermoreStrategyScore");
    const strategyOptimizationSpy = vi.spyOn(client, "getLivermoreStrategyOptimization");

    renderWorkbenchApp(["/stock-analysis"], { client });

    await requestStockAnalysisAsOfDate(user, strategySpy);
    const analytics = await screen.findByTestId("stock-analysis-first-screen-analytics");
    const [, priorityTab, optimizationTab] = within(analytics).getAllByRole("tab");
    await user.click(priorityTab);

    await waitFor(() =>
      expect(strategyScoreSpy).toHaveBeenCalledWith(
        expect.objectContaining({ snapshotTo: "2026-04-29", currentMarketState: "WARM" }),
      ),
    );
    await user.click(optimizationTab);
    await waitFor(() =>
      expect(strategyOptimizationSpy).toHaveBeenCalledWith(
        expect.objectContaining({ snapshotTo: "2026-04-29", currentMarketState: "WARM" }),
      ),
    );
    expect(strategyScoreSpy).not.toHaveBeenCalledWith(
      expect.objectContaining({ snapshotTo: "2026-05-08" }),
    );
    expect(strategyOptimizationSpy).not.toHaveBeenCalledWith(
      expect.objectContaining({ snapshotTo: "2026-05-08" }),
    );
  });

  it("loads strategy backtest with the resolved data date when a requested date falls back", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    const strategySpy = mockStrategyLatestSnapshotFallback(client, {
      initialAsOfDate: "2026-04-28",
      resolvedAsOfDate: "2026-04-29",
    });
    const candidateHistorySpy = vi.spyOn(client, "getLivermoreCandidateHistory");

    renderWorkbenchApp(["/stock-analysis"], { client });

    await requestStockAnalysisAsOfDate(user, strategySpy);
    await screen.findByTestId("stock-analysis-strategy-backtest");

    await waitFor(
      () =>
        expect(candidateHistorySpy).toHaveBeenCalledWith(
          expect.objectContaining({
            snapshotFrom: "2026-04-19",
            snapshotTo: "2026-04-29",
            limit: 500,
          }),
        ),
      { timeout: 6_000 },
    );
    expect(candidateHistorySpy).not.toHaveBeenCalledWith(
      expect.objectContaining({ snapshotTo: "2026-05-08", limit: 500 }),
    );
  });

  it("loads cycle rotation backtests with the resolved data date when a requested date falls back", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    const strategySpy = mockStrategyLatestSnapshotFallback(client, {
      initialAsOfDate: "2026-04-28",
      resolvedAsOfDate: "2026-04-29",
      payloadOverrides: {
        cycle_rotation_framework: buildCycleRotationFramework(),
      },
    });
    const cycleProxySpy = vi.spyOn(client, "getLivermoreCycleProxyBacktest");
    const portfolioBacktestSpy = vi.spyOn(client, "getLivermoreCandidateHistoryPortfolioBacktest");

    renderWorkbenchApp(["/stock-analysis"], { client });

    await requestStockAnalysisAsOfDate(user, strategySpy);
    await screen.findByTestId("stock-analysis-cycle-rotation-framework");

    await waitFor(
      () =>
        expect(cycleProxySpy).toHaveBeenCalledWith(
          expect.objectContaining({ snapshotTo: "2026-04-29" }),
        ),
      { timeout: 6_000 },
    );
    await waitFor(
      () =>
        expect(portfolioBacktestSpy).toHaveBeenCalledWith(
          expect.objectContaining({ snapshotTo: "2026-04-29" }),
        ),
      { timeout: 6_000 },
    );
    expect(cycleProxySpy).not.toHaveBeenCalledWith(
      expect.objectContaining({ snapshotTo: "2026-05-08" }),
    );
    expect(portfolioBacktestSpy).not.toHaveBeenCalledWith(
      expect.objectContaining({ snapshotTo: "2026-05-08" }),
    );
  });

  it("opens Agent drawer and submits page_context.page_id stock-analysis + filters", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    const fetchMock = vi.fn().mockResolvedValueOnce(buildJsonResponse(buildStockAgentResult()));
    vi.stubGlobal("fetch", fetchMock);

    renderWorkbenchApp(["/stock-analysis"], { client });

    await screen.findByTestId("stock-comparison-candidate-row-000001.SZ");
    await user.click(screen.getByTestId("stock-analysis-agent-open"));

    const drawer = await screen.findByTestId("stock-analysis-agent-drawer");
    expect(drawer).toBeInTheDocument();
    expect(within(drawer).getByText("复核助手")).toBeInTheDocument();
    expect(screen.queryByText("Agent 复核当前观察")).not.toBeInTheDocument();
    expect(screen.getByTestId("agent-panel")).toBeInTheDocument();

    await user.type(screen.getByTestId("agent-panel-question"), "please judge current risk");
    await user.click(screen.getByTestId("agent-panel-submit"));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const submitted = parseLastAgentQueryRequest(fetchMock);
    expect(submitted?.page_context?.page_id).toBe("stock-analysis");
    expect(submitted?.page_context?.current_filters).toMatchObject({
      research_domain: "stock",
      as_of_date: "2026-04-29",
      sector_filter: null,
      sector_filter_label: null,
      sector_view: "score",
      current_view: "decision",
    });
    expect(Array.isArray(submitted?.page_context?.selected_rows)).toBe(true);
    expect(submitted?.page_context?.selected_rows ?? []).toEqual([]);
  });

  it("uses the resolved data date in Agent page_context when a requested date falls back", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    const strategySpy = vi.spyOn(client, "getStockAnalysisWorkbench").mockImplementation(async (options) => {
      const strategy = buildStrategyPayload(
        options?.asOfDate
          ? {
              as_of_date: "2026-04-29",
              requested_as_of_date: options.asOfDate,
            }
          : undefined,
      );
      return buildMockApiEnvelope(
        "market_data.stock_analysis.workbench",
        buildStockAnalysisWorkbenchPayload(strategy),
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_livermore_test",
          vendor_version: "vv_livermore_test",
          rule_version: "rv_stock_analysis_workbench_v1",
          fallback_mode: options?.asOfDate ? "latest_snapshot" : "none",
        },
      );
    });
    const legacyStrategySpy = vi.spyOn(client, "getLivermoreStrategy").mockImplementation(async (options) =>
      buildMockApiEnvelope(
        "market_data.livermore",
        buildStrategyPayload(
          options?.asOfDate
            ? {
                as_of_date: "2026-04-29",
                requested_as_of_date: options.asOfDate,
              }
            : undefined,
        ),
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_livermore_test",
          vendor_version: "vv_livermore_test",
          rule_version: "rv_livermore_market_gate_v1",
          fallback_mode: options?.asOfDate ? "latest_snapshot" : "none",
        },
      ),
    );
    const fetchMock = vi.fn().mockResolvedValueOnce(buildJsonResponse(buildStockAgentResult()));
    vi.stubGlobal("fetch", fetchMock);

    renderWorkbenchApp(["/stock-analysis"], { client });

    await requestStockAnalysisAsOfDate(user, strategySpy);
    expect(legacyStrategySpy).not.toHaveBeenCalled();
    const decisionPanel = screen.getByTestId("stock-analysis-decision-panel");
    expect(decisionPanel).toHaveTextContent("数据日期");
    expect(decisionPanel).toHaveTextContent("2026-04-29");
    expect(decisionPanel).toHaveTextContent("请求日期");
    expect(decisionPanel).toHaveTextContent("2026-05-08");

    await user.click(screen.getByTestId("stock-analysis-agent-open"));
    await waitFor(() => {
      const contextSummary = screen.getByText((content, element) => {
        return element?.classList.contains("agent-page-context__code") === true && content.includes("2026-04-29");
      });
      expect(contextSummary).toHaveTextContent('"as_of_date":"2026-04-29"');
      expect(contextSummary).toHaveTextContent('"requested_as_of_date":"2026-05-08"');
    });
    await user.type(screen.getByTestId("agent-panel-question"), "please judge fallback date");
    await user.click(screen.getByTestId("agent-panel-submit"));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const submitted = parseLastAgentQueryRequest(fetchMock);
    expect(submitted?.page_context?.current_filters?.as_of_date).toBe("2026-04-29");
    expect(submitted?.page_context?.current_filters?.requested_as_of_date).toBe("2026-05-08");
    expect(submitted?.page_context?.current_filters?.as_of_date).not.toBe("2026-05-08");
  });

  it("reflects sector filter and drawer selection in Agent page_context", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    const fetchMock = vi.fn().mockResolvedValueOnce(buildJsonResponse(buildStockAgentResult()));
    vi.stubGlobal("fetch", fetchMock);

    renderWorkbenchApp(["/stock-analysis"], { client });

    await screen.findByTestId("stock-comparison-candidate-row-000001.SZ");

    await user.click(screen.getByTestId("sector-filter-chip-801002"));
    await screen.findByTestId("stock-comparison-candidate-row-000002.SZ");

    await user.click(screen.getByTestId("stock-comparison-candidate-review-000002.SZ"));
    await screen.findByTestId("stock-detail-drawer");

    await user.click(screen.getByTestId("stock-analysis-agent-open"));
    await user.type(screen.getByTestId("agent-panel-question"), "please judge current risk");
    await user.click(screen.getByTestId("agent-panel-submit"));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const submitted = parseLastAgentQueryRequest(fetchMock);
    expect(submitted?.page_context?.current_filters?.sector_filter).toBe("801002");
    expect(submitted?.page_context?.current_filters?.sector_filter_label).toBe("新能源车");
    expect(submitted?.page_context?.current_filters?.sector_view).toBe("score");
    expect(submitted?.page_context?.current_filters?.current_view).toBe("stock_detail");
    expect(submitted?.page_context?.current_filters?.research_domain).toBe("stock");
    expect(submitted?.page_context?.selected_rows).toEqual([
      {
        stock_code: "000002.SZ",
        stock_name: "Beta",
        livermore_rank: 2,
        review_rank: 2,
        sector_code: "801002",
        sector_name: "新能源车",
        source: "review_queue",
      },
    ]);
  });

  it("renders strategy replay rows from legacy per-strategy horizon stats", async () => {
    renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });

    const panel = await screen.findByTestId("stock-analysis-strategy-backtest");
    await waitFor(() => expect(panel).toHaveTextContent(/180 条/), { timeout: 3_000 });
    const trend = within(await screen.findByTestId("stock-analysis-strategy-backtest-stock_candidate"));
    expect(panel).toHaveTextContent(/策略回溯表现/);
    expect(panel).toHaveTextContent(/回溯胜率/);
    expect(await screen.findByTestId("stock-analysis-strategy-backtest-panel-summary")).toBeInTheDocument();
    expect(panel).toHaveTextContent(/有效样本/);
    expect(panel).toHaveTextContent(/完成日期 5/);

    expect(trend.getByText("趋势突破")).toBeInTheDocument();
    expect(trend.getByText("36")).toBeInTheDocument();
    expect(trend.getByText("50.0% / +1.41% / 30条")).toBeInTheDocument();
    expect(trend.getByText("100.0% / +19.99% / 6条")).toBeInTheDocument();

    const factor = within(screen.getByTestId("stock-analysis-strategy-backtest-factor_screen"));
    expect(factor.getByText("多因子")).toBeInTheDocument();
    expect(factor.getByText("37.3% / -0.04% / 150条")).toBeInTheDocument();
    expect(factor.getByText("56.7% / +2.93% / 30条")).toBeInTheDocument();
  });

  it("localizes strategy backtest source-table failures without exposing backend tables", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        candidateHistoryError: new Error(
          "Failed to fetch strategy backtest because source_table choice_stock_candidate_history is missing.",
        ),
      }),
    });

    const panel = await screen.findByTestId("stock-analysis-strategy-backtest");
    await waitFor(() => expect(panel).toHaveTextContent("暂不可用"), { timeout: 3_000 });
    expect(panel).toHaveTextContent("数据源缺失");
    expect(panel).not.toHaveTextContent("Failed to fetch");
    expect(panel).not.toHaveTextContent("source_table");
    expect(panel).not.toHaveTextContent("choice_stock_candidate_history");
  });

  it("renders current market strategy priority from the score API without trading action copy", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          market_gate: {
            ...buildStrategyPayload().market_gate,
            state: "OVERHEAT",
          },
        }),
        candidateHistory: buildCandidateHistoryPayload({
          items: [
            {
              snapshot_as_of_date: "2026-05-07",
              stock_code: "688001.SH",
              stock_name: "候选一",
              signal_kind: "factor_screen",
              candidate_rank: 1,
              sector_code: "S270000",
              sector_name: "电子",
              selection_close: 10,
              forward_trade_date_1d: "2026-05-08",
              forward_trade_date_5d: null,
              forward_trade_date_20d: null,
              return_1d: 0.021,
              return_5d: null,
              return_20d: null,
              data_status: "pending",
            },
            {
              snapshot_as_of_date: "2026-05-07",
              stock_code: "688011.SH",
              stock_name: "候选十一",
              signal_kind: "factor_screen",
              candidate_rank: 11,
              sector_code: "S270000",
              sector_name: "电子",
              selection_close: 10,
              forward_trade_date_1d: "2026-05-08",
              forward_trade_date_5d: null,
              forward_trade_date_20d: null,
              return_1d: 0.011,
              return_5d: null,
              return_20d: null,
              data_status: "pending",
            },
            {
              snapshot_as_of_date: "2026-05-07",
              stock_code: "300001.SZ",
              stock_name: "趋势候选",
              signal_kind: "stock_candidate",
              candidate_rank: 1,
              sector_code: "S270000",
              sector_name: "电子",
              selection_close: 10,
              forward_trade_date_1d: "2026-05-08",
              forward_trade_date_5d: null,
              forward_trade_date_20d: null,
              return_1d: 0.031,
              return_5d: null,
              return_20d: null,
              data_status: "pending",
            },
          ],
        }),
      }),
    });

    const summary = await screen.findByTestId("stock-analysis-market-priority-summary");
    await waitFor(() => expect(summary).toHaveTextContent("优先复核"));
    await screen.findByTestId("stock-analysis-market-priority-row-OVERHEAT-factor_screen");
    expect(summary).toHaveTextContent("当前市场策略优先级");
    expect(await screen.findByTestId("stock-analysis-deep-zone-gate-summary")).toHaveTextContent("过热");
    expect(summary).toHaveTextContent("T+5");
    expect(summary).toHaveTextContent("优先复核");
    expect(summary).toHaveTextContent("多因子");
    expect(summary).toHaveTextContent("62.4");

    const factorRowElement = screen.getByTestId("stock-analysis-market-priority-row-OVERHEAT-factor_screen");
    const factorRow = within(factorRowElement);
    expect(factorRow.getByText("多因子")).toBeInTheDocument();
    expect(factorRow.getByText("优先复核")).toBeInTheDocument();
    expect(factorRow.getByText("54.2% / +0.80% / 24条")).toBeInTheDocument();
    expect(factorRow.getByText("60.0% / +2.40% / 24条")).toBeInTheDocument();
    expect(factorRow.getByText("60.0% / +3.10% / 20条")).toBeInTheDocument();
    expect(factorRowElement).toHaveTextContent("前10名优先复核");
    expect(factorRowElement).toHaveTextContent("75.0% / +4.21% / 20条");
    expect(factorRow.getByText("第 11-20 名 降权观察")).toBeInTheDocument();
    expect(factorRowElement).not.toHaveTextContent("11-20 降权观察");

    const trendRow = within(screen.getByTestId("stock-analysis-market-priority-row-OVERHEAT-stock_candidate"));
    expect(trendRow.getByText("长窗口风险")).toBeInTheDocument();
    expect(summary).toHaveTextContent("优先观察：多因子");
    expect(summary).not.toHaveTextContent("优先复核：多因子、趋势突破");
    expect(summary).toHaveTextContent("样本偏窄");
    expect(summary).toHaveTextContent("T+5 已成熟快照 2/4");
    expect(summary).not.toHaveTextContent("matured snapshots");
    expect(summary).not.toHaveTextContent("waiting for more mature days");
    expect(summary).toHaveTextContent("当前候选成熟进度");
    expect(summary).toHaveTextContent("还差 2 个成熟快照");
    expect(summary).toHaveTextContent("2026-05-07");
    expect(summary).toHaveTextContent("T+5 待成熟");
    expect(summary).toHaveTextContent("候选明细");
    expect(summary).toHaveTextContent("候选一");
    expect(summary).toHaveTextContent("688001.SH");
    expect(summary).toHaveTextContent("#1");
    expect(summary).not.toHaveTextContent("候选十一");
    expect(summary).not.toHaveTextContent("趋势候选");

    const page = screen.getByTestId("stock-analysis-page");
    expect(page).not.toHaveTextContent("买入");
    expect(page).not.toHaveTextContent("卖出");
    expect(page).not.toHaveTextContent("下单");
    expect(page).not.toHaveTextContent("调仓");
  });

  it("localizes candidate maturity detail source-table failures without exposing backend tables", async () => {
    const client = stockClient({
      strategy: buildStrategyPayload({
        market_gate: {
          ...buildStrategyPayload().market_gate,
          state: "OVERHEAT",
        },
      }),
    });
    vi.spyOn(client, "getLivermoreCandidateHistory").mockImplementation(async (options) => {
      if (options?.snapshotFrom === "2026-04-30" && options.snapshotTo === "2026-05-07") {
        throw new Error(
          "Failed to fetch candidate maturity detail because source_table choice_stock_candidate_history is missing.",
        );
      }
      return buildMockApiEnvelope("market_data.livermore.candidate_history", buildCandidateHistoryPayload());
    });

    renderWorkbenchApp(["/stock-analysis"], { client });

    const section = await screen.findByTestId("stock-analysis-candidate-maturity");
    await waitFor(() => expect(section).toHaveTextContent("候选明细暂不可用"), { timeout: 3_000 });
    expect(section).toHaveTextContent("数据源缺失");
    expect(section).not.toHaveTextContent("Failed to fetch");
    expect(section).not.toHaveTextContent("source_table");
    expect(section).not.toHaveTextContent("choice_stock_candidate_history");
  });

  it("renders unknown strategy priority risk labels as pending business copy", async () => {
    const scorePayload = buildStrategyScorePayload();
    const rowsWithVendorRisk: LivermoreStrategyScorePayload["rows"] = scorePayload.rows.map((row) => {
      if (row.signal_kind !== "stock_candidate") {
        return row;
      }

      const diagnostics = row.diagnostics ?? {
        priority_scope: null,
        priority_scope_label: null,
        rank_buckets: [],
        risk_flags: [],
      };

      return {
        ...row,
        diagnostics: {
          ...diagnostics,
          risk_flags: [
            {
              kind: "source_table_risk_guard",
              label: "sourceTableRiskGuard",
              horizon: "return_20d",
              reason: "source_table risk guard pending.",
              stats: row.diagnostics?.risk_flags[0]?.stats,
            },
          ],
        },
      };
    });

    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategyScore: buildStrategyScorePayload({
          rows: rowsWithVendorRisk,
          current_market_state_rows: rowsWithVendorRisk,
        }),
      }),
    });

    const row = await screen.findByTestId("stock-analysis-market-priority-row-OVERHEAT-stock_candidate");
    expect(row).toHaveTextContent("风险待确认");
    expect(row).not.toHaveTextContent("sourceTableRiskGuard");
    expect(row).not.toHaveTextContent("source table risk guard");
  });

  it("renders unknown strategy priority statuses as pending business copy", async () => {
    const scorePayload = buildStrategyScorePayload();
    const rowsWithVendorStatus: LivermoreStrategyScorePayload["rows"] = scorePayload.rows.map((row) =>
      row.signal_kind === "factor_screen"
        ? {
            ...row,
            strategy_label: "sourceTableAlphaSignal",
            priority_label: "external_vendor_priority_state",
          }
        : row,
    );

    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategyScore: buildStrategyScorePayload({
          rows: rowsWithVendorStatus,
          current_market_state_rows: rowsWithVendorStatus,
        }),
      }),
    });

    const row = await screen.findByTestId("stock-analysis-market-priority-row-OVERHEAT-factor_screen");
    expect(row).toHaveTextContent("状态待确认");
    expect(row).toHaveTextContent("策略待确认");
    expect(row).not.toHaveTextContent("sourceTableAlphaSignal");
    expect(row).not.toHaveTextContent("external_vendor_priority_state");
  });

  it("renders unknown strategy priority rank bucket statuses as pending business copy", async () => {
    const scorePayload = buildStrategyScorePayload();
    const rowsWithVendorBucketStatus: LivermoreStrategyScorePayload["rows"] = scorePayload.rows.map((row) => {
      if (row.signal_kind !== "factor_screen") {
        return row;
      }

      return {
        ...row,
        diagnostics: row.diagnostics
          ? {
              ...row.diagnostics,
              rank_buckets: row.diagnostics.rank_buckets.map((bucket) =>
                !bucket.included_in_priority && bucket.priority_label === "降权观察"
                  ? {
                      ...bucket,
                      priority_label: "sourceTableBucketState",
                    }
                  : bucket,
              ),
            }
          : row.diagnostics,
      };
    });

    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategyScore: buildStrategyScorePayload({
          rows: rowsWithVendorBucketStatus,
          current_market_state_rows: rowsWithVendorBucketStatus,
        }),
      }),
    });

    const row = await screen.findByTestId("stock-analysis-market-priority-row-OVERHEAT-factor_screen");
    expect(row).toHaveTextContent("第 11-20 名 状态待确认");
    expect(row).not.toHaveTextContent("sourceTableBucketState");
  });

  it("renders unknown strategy priority scope labels as pending business copy", async () => {
    const scorePayload = buildStrategyScorePayload();
    const rowsWithVendorScope: LivermoreStrategyScorePayload["rows"] = scorePayload.rows.map((row) => {
      if (row.signal_kind !== "factor_screen") {
        return row;
      }

      return {
        ...row,
        diagnostics: row.diagnostics
          ? {
              ...row.diagnostics,
              priority_scope_label: "sourceTableScopeLabel",
            }
          : row.diagnostics,
      };
    });

    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategyScore: buildStrategyScorePayload({
          rows: rowsWithVendorScope,
          current_market_state_rows: rowsWithVendorScope,
        }),
      }),
    });

    const row = await screen.findByTestId("stock-analysis-market-priority-row-OVERHEAT-factor_screen");
    expect(row).toHaveTextContent("排序范围待确认");
    expect(row).not.toHaveTextContent("sourceTableScopeLabel");

    const maturity = await screen.findByTestId("stock-analysis-candidate-maturity");
    expect(maturity).toHaveTextContent("排序范围待确认");
    expect(maturity).not.toHaveTextContent("sourceTableScopeLabel");
  });

  it("localizes strategy priority source-table failures without exposing backend tables", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategyScoreError: new Error(
          "Failed to fetch priority from /ui/market-data/livermore/strategy-score because source_table choice_stock_strategy_score is missing.",
        ),
      }),
    });

    const section = await screen.findByTestId("stock-analysis-market-priority-summary");
    await waitFor(() => expect(section).toHaveTextContent("暂不可用"), { timeout: 3_000 });
    expect(section).toHaveTextContent("数据源缺失");
    expect(section).not.toHaveTextContent("Failed to fetch");
    expect(section).not.toHaveTextContent("source_table");
    expect(section).not.toHaveTextContent("choice_stock_strategy_score");
    expect(section).not.toHaveTextContent("/ui/market-data/livermore/strategy-score");
    const detail = within(section).getByTestId("stock-analysis-strategy-card-market-priority-detail");
    const summaryDetail = detail.querySelector(".stock-analysis-strategy-module-card__detail-line");
    expect(summaryDetail).toHaveTextContent("必需数据源缺失");
    expect(summaryDetail).not.toHaveTextContent("无法连接策略分析服务");
  });

  it("renders enriched strategy family payloads without surfacing family contract labels", async () => {
    const hiddenFamilyLabel = "Family contract label should stay hidden";
    const baseScorePayload = buildStrategyScorePayload();
    const enrichedScoreRows: LivermoreStrategyScorePayload["rows"] = baseScorePayload.rows.map((row) => ({
      ...row,
      family_key: row.signal_kind === "stock_candidate" ? "trend_core" : row.signal_kind,
      family_label: hiddenFamilyLabel,
      family_contract_version: "rv_livermore_strategy_family_contract_v1",
      primary_sample_size: row.stats.return_5d.available_count,
    }));
    const baseOptimizationPayload = buildStrategyOptimizationPayload();
    const enrichedOptimizationPayload: LivermoreStrategyOptimizationPayload = {
      ...baseOptimizationPayload,
      strategy_summaries: baseOptimizationPayload.strategy_summaries.map((row) => ({
        ...row,
        family_key: row.signal_kind === "stock_candidate" ? "trend_core" : row.signal_kind,
        family_label: hiddenFamilyLabel,
        family_contract_version: "rv_livermore_strategy_family_contract_v1",
        primary_sample_size: row.stats.return_5d.available_count,
      })),
      slices: baseOptimizationPayload.slices.map((row) => ({
        ...row,
        family_key: row.signal_kind === "stock_candidate" ? "trend_core" : row.signal_kind,
        family_label: hiddenFamilyLabel,
        family_contract_version: "rv_livermore_strategy_family_contract_v1",
        primary_sample_size: row.stats.return_5d.available_count,
      })),
      recommendations: [
        {
          ...baseOptimizationPayload.strategy_summaries[0].recommendation,
          target_type: "strategy",
          target_key: baseOptimizationPayload.strategy_summaries[0].summary_key,
          signal_kind: baseOptimizationPayload.strategy_summaries[0].signal_kind,
          label: baseOptimizationPayload.strategy_summaries[0].strategy_label,
          family_key: "factor_screen",
          family_label: hiddenFamilyLabel,
          family_contract_version: "rv_livermore_strategy_family_contract_v1",
          primary_sample_size: baseOptimizationPayload.strategy_summaries[0].stats.return_5d.available_count,
        },
      ],
    };

    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategyScore: buildStrategyScorePayload({
          rows: enrichedScoreRows,
          current_market_state_rows: enrichedScoreRows,
        }),
        strategyOptimization: enrichedOptimizationPayload,
      }),
    });

    const summary = await screen.findByTestId("stock-analysis-market-priority-summary");
    const optimization = await screen.findByTestId("stock-analysis-strategy-optimization");
    await waitFor(() => expect(summary).toHaveTextContent("T+5"), { timeout: 3_000 });
    await waitFor(() => expect(optimization).toHaveTextContent("T+5"), { timeout: 3_000 });
    expect(summary).not.toHaveTextContent(hiddenFamilyLabel);
    expect(summary).not.toHaveTextContent("rv_livermore_strategy_family_contract_v1");
    expect(optimization).not.toHaveTextContent(hiddenFamilyLabel);
    expect(optimization).not.toHaveTextContent("rv_livermore_strategy_family_contract_v1");
  });

  it("shows the T+5 optimization diagnosis without turning it into trading rules", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          market_gate: {
            ...buildStrategyPayload().market_gate,
            state: "HOT",
          },
        }),
        strategyOptimization: buildStrategyOptimizationPayload({
          slices: [
            {
              ...buildStrategyOptimizationPayload().slices[0],
              slice_key: "factor_screen:vendor:alpha",
              dimension: "external_vendor_dimension",
              bucket: "external_vendor_alpha_bucket",
              label: "external_vendor_alpha_bucket",
            },
          ],
        }),
      }),
    });

    const card = await screen.findByTestId("stock-analysis-strategy-optimization");
    await waitFor(() => expect(card).toHaveTextContent("多因子"), { timeout: 3_000 });
    expect(card).toHaveTextContent("三策略 T+5 排名");
    expect(card).toHaveTextContent("多因子");
    expect(card).toHaveTextContent("复核状态");
    expect(card).not.toHaveTextContent("建议");
    expect(card).toHaveTextContent("优先复核");
    expect(card).toHaveTextContent("T+5 样本 30");
    expect(card).not.toHaveTextContent("sample 30");
    expect(card).not.toHaveTextContent("priority review ranking");
    expect(card).toHaveTextContent("题材突变");
    expect(card).toHaveTextContent("样本不足");
    expect(card).toHaveTextContent("切片待确认");
    expect(card).not.toHaveTextContent("rank 21-30");
    expect(card).not.toHaveTextContent("external_vendor_alpha_bucket");
    expect(card).toHaveTextContent("降权观察");
    expect(card).toHaveTextContent("当前最新日期收益");
    expect(card).toHaveTextContent("待成熟");
    expect(card).toHaveTextContent("最新待成熟日期 2026-05-13");
    expect(card).not.toHaveTextContent("pending");
    expect(card).toHaveTextContent("复核排序 · 不改规则");
    expect(card).not.toHaveTextContent("建议只用于复核排序，不自动改交易规则");
    expect(card).not.toHaveTextContent("买入");
    expect(card).not.toHaveTextContent("下单");
  });

  it("localizes optimization request source-table failures without exposing backend tables", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategyOptimizationError: new Error(
          "Failed to fetch optimization because source_table choice_stock_strategy_optimization is missing.",
        ),
      }),
    });

    const card = await screen.findByTestId("stock-analysis-strategy-optimization");
    await waitFor(() => expect(card).toHaveTextContent("暂不可用"), { timeout: 3_000 });
    expect(card).toHaveTextContent("数据源缺失");
    expect(card).not.toHaveTextContent("Failed to fetch");
    expect(card).not.toHaveTextContent("source_table");
    expect(card).not.toHaveTextContent("choice_stock_strategy_optimization");
  });

  it("shows current market sample insufficiency instead of a strategy recommendation", async () => {
    const insufficientRows: LivermoreStrategyScorePayload["rows"] = [
      {
        market_state: "OVERHEAT",
        signal_kind: "stock_candidate",
        strategy_label: "趋势突破",
        sample_status: "insufficient",
        priority_score: null,
        priority_rank: null,
        priority_label: "样本不足",
        reason: "Current market sample is insufficient: T+5 available 6/20, observation only.",
        stats: {
          return_1d: {
            available_count: 8,
            missing_count: 0,
            positive_count: 4,
            non_positive_count: 4,
            avg_return: 0.001,
            win_rate: 0.5,
          },
          return_5d: {
            available_count: 6,
            missing_count: 2,
            positive_count: 3,
            non_positive_count: 3,
            avg_return: 0.002,
            win_rate: 0.5,
          },
          return_20d: {
            available_count: 0,
            missing_count: 8,
            positive_count: 0,
            non_positive_count: 0,
            avg_return: null,
            win_rate: null,
          },
        },
      },
    ];
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          market_gate: {
            ...buildStrategyPayload().market_gate,
            state: "OVERHEAT",
          },
        }),
        strategyScore: buildStrategyScorePayload({
          rows: insufficientRows,
          current_market_state_rows: insufficientRows,
        }),
      }),
    });

    const summary = await screen.findByTestId("stock-analysis-market-priority-summary");
    await waitFor(() => expect(summary).toHaveTextContent("T+1"), { timeout: 3_000 });
    expect(summary).toHaveTextContent("样本不足");
    expect(summary).toHaveTextContent("样本不足");
    expect(summary).toHaveTextContent("样本不足 T+5 6/20");
    expect(summary).not.toHaveTextContent("Current market sample is insufficient");
    expect(summary).not.toHaveTextContent("observation only");
    expect(summary).not.toHaveTextContent("优先复核");
    expect(summary).toHaveTextContent("T+1");
    expect(summary).toHaveTextContent("T+5");
    expect(summary).toHaveTextContent("T+20");
  });

  it("prefers horizon-usable stats and renders market-state replay rows", async () => {
    const candidateHistory = buildCandidateHistoryPayload();
    const summary = candidateHistory.summary!;
    const decisionUsableStats = summary.decision_usable_stats!;

    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        candidateHistory: {
          ...candidateHistory,
          summary: {
            ...summary,
            decision_usable_stats: {
              ...decisionUsableStats,
              by_signal_kind_horizon_stats: {
                stock_candidate: {
                  return_1d: {
                    available_count: 0,
                    missing_count: 36,
                    positive_count: 0,
                    non_positive_count: 0,
                    avg_return: null,
                    win_rate: null,
                  },
                  return_5d: {
                    available_count: 0,
                    missing_count: 36,
                    positive_count: 0,
                    non_positive_count: 0,
                    avg_return: null,
                    win_rate: null,
                  },
                  return_20d: {
                    available_count: 0,
                    missing_count: 36,
                    positive_count: 0,
                    non_positive_count: 0,
                    avg_return: null,
                    win_rate: null,
                  },
                },
              },
              by_signal_kind_horizon_usable_stats: {
                stock_candidate: {
                  return_1d: {
                    available_count: 12,
                    missing_count: 24,
                    positive_count: 9,
                    non_positive_count: 3,
                    avg_return: 0.0321,
                    win_rate: 0.75,
                  },
                  return_5d: {
                    available_count: 4,
                    missing_count: 32,
                    positive_count: 2,
                    non_positive_count: 2,
                    avg_return: -0.0111,
                    win_rate: 0.5,
                  },
                  return_20d: {
                    available_count: 0,
                    missing_count: 36,
                    positive_count: 0,
                    non_positive_count: 0,
                    avg_return: null,
                    win_rate: null,
                  },
                },
                external_vendor_alpha_signal: {
                  return_1d: {
                    available_count: 3,
                    missing_count: 0,
                    positive_count: 2,
                    non_positive_count: 1,
                    avg_return: 0.0123,
                    win_rate: 0.666667,
                  },
                  return_5d: {
                    available_count: 2,
                    missing_count: 1,
                    positive_count: 1,
                    non_positive_count: 1,
                    avg_return: -0.004,
                    win_rate: 0.5,
                  },
                  return_20d: {
                    available_count: 0,
                    missing_count: 3,
                    positive_count: 0,
                    non_positive_count: 0,
                    avg_return: null,
                    win_rate: null,
                  },
                },
              },
              by_market_state_signal_kind_horizon_stats: {
                WARM: {
                  stock_candidate: {
                    return_1d: {
                      available_count: 12,
                      missing_count: 24,
                      positive_count: 9,
                      non_positive_count: 3,
                      avg_return: 0.0321,
                      win_rate: 0.75,
                    },
                    return_5d: {
                      available_count: 4,
                      missing_count: 32,
                      positive_count: 2,
                      non_positive_count: 2,
                      avg_return: -0.0111,
                      win_rate: 0.5,
                    },
                    return_20d: {
                      available_count: 0,
                      missing_count: 36,
                      positive_count: 0,
                      non_positive_count: 0,
                      avg_return: null,
                      win_rate: null,
                    },
                  },
                  external_vendor_alpha_signal: {
                    return_1d: {
                      available_count: 3,
                      missing_count: 0,
                      positive_count: 2,
                      non_positive_count: 1,
                      avg_return: 0.0123,
                      win_rate: 0.666667,
                    },
                    return_5d: {
                      available_count: 2,
                      missing_count: 1,
                      positive_count: 1,
                      non_positive_count: 1,
                      avg_return: -0.004,
                      win_rate: 0.5,
                    },
                    return_20d: {
                      available_count: 0,
                      missing_count: 3,
                      positive_count: 0,
                      non_positive_count: 0,
                      avg_return: null,
                      win_rate: null,
                    },
                  },
                },
                HOT: {
                  factor_screen: {
                    return_1d: {
                      available_count: 8,
                      missing_count: 12,
                      positive_count: 2,
                      non_positive_count: 6,
                      avg_return: -0.021,
                      win_rate: 0.25,
                    },
                    return_5d: {
                      available_count: 6,
                      missing_count: 14,
                      positive_count: 3,
                      non_positive_count: 3,
                      avg_return: 0.014,
                      win_rate: 0.5,
                    },
                    return_20d: {
                      available_count: 0,
                      missing_count: 20,
                      positive_count: 0,
                      non_positive_count: 0,
                      avg_return: null,
                      win_rate: null,
                    },
                  },
                },
              },
            },
          },
        },
      }),
    });

    const panel = await screen.findByTestId("stock-analysis-strategy-backtest");
    await waitFor(() => expect(panel).toHaveTextContent("75.0% / +3.21% / 12条"), {
      timeout: 5_000,
    });
    const stockCandidateRow = screen.getByTestId("stock-analysis-strategy-backtest-stock_candidate");
    expect(stockCandidateRow).toHaveTextContent("50.0% / -1.11% / 4条");
    expect(stockCandidateRow).toHaveTextContent("待补");
    const externalSignalRow = screen.getByTestId("stock-analysis-strategy-backtest-external_vendor_alpha_signal");
    expect(externalSignalRow).toHaveTextContent("策略待确认");
    expect(externalSignalRow).not.toHaveTextContent("external_vendor_alpha_signal");

    const marketStateTable = await screen.findByTestId("stock-analysis-strategy-backtest-market-state");
    expect(marketStateTable).toHaveTextContent(/市场状态/);
    expect(marketStateTable).toHaveTextContent(/策略/);

    const warmRow = within(screen.getByTestId("stock-analysis-strategy-backtest-market-state-WARM-stock_candidate"));
    expect(warmRow.getByText(/温和/)).toBeInTheDocument();
    expect(warmRow.getByText("趋势突破")).toBeInTheDocument();
    expect(warmRow.getByText("75.0% / +3.21% / 12条")).toBeInTheDocument();
    expect(warmRow.getByText("50.0% / -1.11% / 4条")).toBeInTheDocument();
    const externalWarmRow = within(
      screen.getByTestId("stock-analysis-strategy-backtest-market-state-WARM-external_vendor_alpha_signal"),
    );
    expect(externalWarmRow.getByText("策略待确认")).toBeInTheDocument();
    expect(externalWarmRow.queryByText("external_vendor_alpha_signal")).not.toBeInTheDocument();

    const hotRow = within(screen.getByTestId("stock-analysis-strategy-backtest-market-state-HOT-factor_screen"));
    expect(hotRow.getByText(/偏热/)).toBeInTheDocument();
    expect(hotRow.getByText("多因子")).toBeInTheDocument();
    expect(hotRow.getByText("25.0% / -2.10% / 8条")).toBeInTheDocument();
    expect(hotRow.getByText("50.0% / +1.40% / 6条")).toBeInTheDocument();
  });
});
