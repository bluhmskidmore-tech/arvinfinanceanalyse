import { fireEvent, screen, waitFor, within } from "@testing-library/react";
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
  StockAnalysisReplayClosure,
  StockAnalysisWorkbenchPayload,
} from "../api/contracts";

vi.mock("../app/navigation", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../app/navigation")>()),
  isAgentFrontendEnabled: () => true,
}));

import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import * as dataHealthClient from "../api/dataHealthClient";
import * as systemReadInteraction from "../router/systemReadInteractionContext";
import * as stockAnalysisKlineRadarModel from "../features/stock-analysis/lib/stockAnalysisKlineRadarModel";
import * as stockAnalysisDeepResearchPanelsModel from "../features/stock-analysis/lib/stockAnalysisDeepResearchPanelsModel";
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
const STOCK_ANALYSIS_EDITORIAL_CSS_PATH = resolve(
  process.cwd(),
  "src/features/stock-analysis/pages/StockAnalysisEditorialLedger.css",
);
const STOCK_ANALYSIS_DEEP_CSS_PATH = resolve(
  process.cwd(),
  "src/features/stock-analysis/pages/StockAnalysisDeepResearch.css",
);

function readStockAnalysisCss() {
  return [STOCK_ANALYSIS_CSS_PATH, STOCK_ANALYSIS_EDITORIAL_CSS_PATH, STOCK_ANALYSIS_DEEP_CSS_PATH]
    .map((cssPath) => readFileSync(cssPath, "utf8"))
    .join("\n");
}
const STOCK_ANALYSIS_PAGE_PATH = resolve(
  process.cwd(),
  "src/features/stock-analysis/pages/StockAnalysisPage.tsx",
);
const STOCK_ANALYSIS_PAGE_IMPL_PATH = resolve(
  process.cwd(),
  "src/features/stock-analysis/pages/StockAnalysisPageImpl.tsx",
);
const STOCK_ANALYSIS_DEEP_RESEARCH_ZONE_PATH = resolve(
  process.cwd(),
  "src/features/stock-analysis/components/StockAnalysisDeepResearchZone.tsx",
);
const STOCK_ANALYSIS_DEEP_SELECTION_OVERVIEW_PATH = resolve(
  process.cwd(),
  "src/features/stock-analysis/components/StockAnalysisDeepSelectionOverview.tsx",
);
const STOCK_ANALYSIS_STRATEGY_LENS_SECTION_PATH = resolve(
  process.cwd(),
  "src/features/stock-analysis/components/StockAnalysisStrategyLensSection.tsx",
);
const STOCK_ANALYSIS_OBSERVATION_PREVIEW_PATH = resolve(
  process.cwd(),
  "src/features/stock-analysis/components/StockAnalysisObservationPreview.tsx",
);
function readStockAnalysisPageSource() {
  return [
    STOCK_ANALYSIS_PAGE_PATH,
    STOCK_ANALYSIS_PAGE_IMPL_PATH,
    STOCK_ANALYSIS_DEEP_RESEARCH_ZONE_PATH,
    STOCK_ANALYSIS_DEEP_SELECTION_OVERVIEW_PATH,
  ]
    .map((path) => readFileSync(path, "utf8"))
    .join("\n");
}

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
    RightOutlined: MockAntIcon,
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

type StockAnalysisStrategyCardId =
  | "cycle-rotation"
  | "theme-breakout"
  | "market-priority"
  | "strategy-backtest"
  | "strategy-optimization"
  | "events-monitoring";


async function openEvidenceDisclosure(user?: ReturnType<typeof userEvent.setup>) {
  const disclosure = await screen.findByTestId("stock-analysis-evidence-disclosure");
  if (!(disclosure as HTMLDetailsElement).open) {
    const actor = user ?? userEvent;
    await actor.click(screen.getByTestId("stock-analysis-evidence-disclosure-summary"));
  }
  return disclosure;
}

async function openDeepResearch() {
  const user = userEvent.setup();
  const deepResearch = await screen.findByTestId("stock-analysis-deep-research");
  if (!(deepResearch as HTMLDetailsElement).open) {
    await user.click(within(deepResearch).getByTestId("stock-analysis-deep-research-summary"));
  }
  await within(deepResearch).findByTestId("stock-analysis-deep-zone");
  return deepResearch;
}

async function openStrategyModuleDetail(id: StockAnalysisStrategyCardId) {
  const user = userEvent.setup();
  const deepResearch = await screen.findByTestId("stock-analysis-deep-research");
  if (!(deepResearch as HTMLDetailsElement).open) {
    await user.click(within(deepResearch).getByTestId("stock-analysis-deep-research-summary"));
  }

  const researchMore = await screen.findByTestId("stock-analysis-strategy-research-more");
  if (!(researchMore as HTMLDetailsElement).open) {
    await user.click(within(researchMore).getByTestId("stock-analysis-strategy-research-more-summary"));
  }

  const toggle = await screen.findByTestId(`stock-analysis-strategy-card-${id}-toggle`);
  if (toggle.getAttribute("aria-expanded") !== "true") {
    await user.click(toggle);
  }

  return screen.findByTestId(`stock-analysis-strategy-card-${id}-detail`);
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
          // 观察位几何由后端统一返回，页面不本地重算（见 formatDistanceToBreakoutPct）。
          distance_to_breakout_pct: 0.4587,
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

type PageReplayClosureOverrides = Omit<
  Partial<StockAnalysisReplayClosure>,
  "counts" | "thresholds" | "versions" | "sources" | "receipt"
> & {
  counts?: Partial<StockAnalysisReplayClosure["counts"]>;
  thresholds?: Partial<StockAnalysisReplayClosure["thresholds"]>;
};

function buildStockAnalysisReplayClosure(
  overrides: PageReplayClosureOverrides = {},
): StockAnalysisReplayClosure {
  const base: StockAnalysisReplayClosure = {
    cohort_mode: "current_rule_certified",
    selection_status: "unique_active_certified",
    data_availability: "fresh",
    status: "ready",
    active_cohort_count: 1,
    cohort_id: "cohort-current-rule-20260429",
    requested_start_date: "2026-03-01",
    requested_end_date: "2026-04-29",
    observed_start_date: "2026-03-02",
    observed_end_date: "2026-04-29",
    certified_start_date: "2026-03-02",
    certified_end_date: "2026-04-29",
    evaluation_as_of_date: "2026-04-29",
    governed_era_start: "2026-03-02",
    governed_era_end: "2026-04-29",
    stock_candidate_selection_policy: "current_rule_pit",
    decision_metric_basis: "net_next_open_adj",
    coverage_authority_mode: "strict_certified_calendar",
    strict_coverage: true,
    fallback_covered: false,
    versions: {
      candidate_rule_version: "rv_candidate_v1",
      stock_candidate_selection_formula_version: "fv_selection_v1",
      candidate_outcome_formula_version: "fv_outcome_v1",
      execution_formula_version: "fv_execution_v1",
      matched_baseline_formula_version: "fv_baseline_v1",
      market_gate_rule_version: "rv_gate_v1",
      signal_confluence_rule_version: "rv_confluence_v1",
      macro_formula_version: "fv_macro_v1",
    },
    sources: {
      candidate_source_version: "sv_candidate_v1",
      execution_source_version: "sv_execution_v1",
      matched_baseline_source_version: "sv_baseline_v1",
      macro_source_version: "sv_macro_v1",
      calendar_source_id: "exchange_calendar",
      calendar_source_version: "calendar_sha",
      theme_overlay_fingerprint: "theme_sha",
      choice_catalog_fingerprint: "catalog_sha",
    },
    counts: {
      completed_dates: 20,
      completed_with_signals_dates: 18,
      completed_no_signal_dates: 2,
      pending_tail_dates: 3,
      blocking_pending_dates: 0,
      unsupported_dates: 0,
      proxy_only_dates: 0,
      matched_entry_count: 100,
      t5_usable_count: 100,
      t20_usable_count: 100,
      stale_execution_row_count: 0,
      stale_matched_baseline_row_count: 0,
    },
    thresholds: {
      completed_dates: 20,
      matched_entry_count: 100,
    },
    primary_blocker_code: null,
    reason_codes: [],
    run_id: "materialize:current-rule-20260429",
    promotion_run_id: "promote:current-rule-20260429",
    receipt: {
      path: "receipts/current-rule.json",
      sha256: "receipt_sha",
      calendar_path: "receipts/calendar.json",
      calendar_sha256: "calendar_sha",
    },
    tables_used: [
      "stock_analysis_current_rule_cohort_manifest",
      "stock_analysis_current_rule_replay_fact",
      "stock_analysis_current_rule_date_certificate",
    ],
  };
  return {
    ...base,
    ...overrides,
    counts: { ...base.counts, ...overrides.counts },
    thresholds: { ...base.thresholds, ...overrides.thresholds },
  };
}

function buildStockAnalysisWorkbenchPayload(
  strategy: LivermoreStrategyPayload,
  replayClosure?: StockAnalysisReplayClosure | null,
): StockAnalysisWorkbenchPayload {
  const reviewQueue = [
    ...(strategy.stock_candidates?.items ?? []).map((item) => ({
      ...item,
      source_module: "stock_candidates",
    })),
    ...(strategy.factor_screen_candidates?.items ?? []).map((item) => ({
      ...item,
      source_module: "factor_screen_candidates",
    })),
    ...(strategy.hybrid_fusion_candidates?.items ?? []).map((item) => ({
      ...item,
      source_module: "hybrid_fusion_candidates",
    })),
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
    ...(replayClosure !== undefined ? { replay_closure: replayClosure } : {}),
    pretrade_qualification: {
      schema: "pretrade_qualification/v1",
      status: "ready",
      reason: null,
      producer_run_id: "pretrade:test",
      target_date: strategy.as_of_date,
      stock_candidate_policy: "factor_screen_exp3b",
      evidence_sha256: "a".repeat(64),
      input_snapshot_sha256: "b".repeat(64),
      attested_strategy_payload_sha256: "c".repeat(64),
      strategy_payload_sha256: "c".repeat(64),
      workbench_projection_sha256: "d".repeat(64),
    },
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
      data_gaps: strategy.data_gaps.map((gap) => ({
        ...gap,
        blocks_review:
          ([
            "broad_index_history",
            "breadth",
            "limit_up_quality",
            "sector_strength",
            "stock_universe",
            "position_risk",
          ].includes(gap.input_family) &&
            gap.status !== "ready") ||
          gap.status === "stale" ||
          gap.status === "look_ahead" ||
          gap.tier === "stale" ||
          gap.tier === "expired",
      })),
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
      kline_analysis: "/ui/market-data/stock-analysis/kline-analysis",
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
      authority_status: "ready",
      authority_reasons: [],
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
    snapshot_from: "2026-04-30",
    snapshot_to: "2026-05-08",
    requested_snapshot_from: "2026-04-30",
    requested_snapshot_to: "2026-05-08",
    observed_snapshot_from: "2026-05-02",
    observed_snapshot_to: "2026-05-07",
    metric_basis: "net_next_open_adj",
    maturity_status: "ready",
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

function buildReviewableConfluencePayload(
  replayStatus: ConfluenceReplayStatus | string = buildReplayStatus(),
): LivermoreSignalConfluencePayload {
  return buildConfluencePayload({
    entry_observations: [
      {
        stock_code: "000001.SZ",
        stock_name: "Alpha",
        action: "observe_entry_setup",
        trigger_price: 10.5,
        current_price: 10.2,
        invalidation_reference_price: 9.8,
        evidence: ["仅观察候选。"],
      },
    ],
    adversarial_context: {
      status: "complete",
      mode: "anti_crowding_v1",
      risk_gate: "pass",
      position_scale: 0.75,
    },
    closed_loop_state: {
      entry_gate: "open",
      exit_gate: "watch",
      replay_status: replayStatus,
      lineage_status: "complete",
    },
  });
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
          return_10d: {
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
          return_10d: {
            available_count: 0,
            missing_count: 180,
            positive_count: 0,
            non_positive_count: 0,
            avg_return: null,
            win_rate: null,
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
            return_10d: {
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
            return_10d: {
              available_count: 0,
              missing_count: 180,
              positive_count: 0,
              non_positive_count: 0,
              avg_return: null,
              win_rate: null,
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
      return_10d: {
        available_count: 0,
        missing_count: 24,
        positive_count: 0,
        non_positive_count: 0,
        avg_return: null,
        win_rate: null,
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
        return_10d: {
          available_count: 0,
          missing_count: 20,
          positive_count: 0,
          non_positive_count: 0,
          avg_return: null,
          win_rate: null,
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
              return_10d: {
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
              return_10d: {
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
            return_10d: {
              available_count: 0,
              missing_count: 5,
              positive_count: 0,
              non_positive_count: 0,
              avg_return: null,
              win_rate: null,
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
            return_10d: {
              available_count: 0,
              missing_count: 4,
              positive_count: 0,
              non_positive_count: 0,
              avg_return: null,
              win_rate: null,
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
      return_10d: {
        available_count: 0,
        missing_count: 22,
        positive_count: 0,
        non_positive_count: 0,
        avg_return: null,
        win_rate: null,
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
    return_10d: {
      available_count: 0,
      missing_count: 30,
      positive_count: 0,
      non_positive_count: 0,
      avg_return: null,
      win_rate: null,
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
    return_10d: {
      available_count: 0,
      missing_count: 10,
      positive_count: 0,
      non_positive_count: 0,
      avg_return: null,
      win_rate: null,
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
    return_10d: {
      available_count: 0,
      missing_count: 2,
      positive_count: 0,
      non_positive_count: 0,
      avg_return: null,
      win_rate: null,
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
    return_10d: {
      available_day_count: 0,
      candidate_row_count: 0,
      avg_return: null,
      positive_day_rate: null,
      worst_day_return: null,
      best_day_return: null,
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
  replayClosure?: StockAnalysisReplayClosure | null;
  confluence?: LivermoreSignalConfluencePayload;
  confluenceError?: Error;
  confluenceMetaOverrides?: Partial<ApiEnvelope<LivermoreSignalConfluencePayload>["result_meta"]>;
  candidateHistory?: LivermoreCandidateHistoryPayload;
  candidateHistoryError?: Error;
  candidateHistoryPortfolioBacktest?: LivermoreCandidateHistoryPortfolioBacktestPayload;
  candidateHistoryPortfolioBacktestError?: Error;
  cycleProxyBacktest?: LivermoreCycleProxyBacktestPayload;
  cycleProxyBacktestError?: Error;
  strategyScore?: LivermoreStrategyScorePayload;
  strategyScoreError?: Error;
  strategyOptimization?: LivermoreStrategyOptimizationPayload;
  strategyOptimizationResultNull?: boolean;
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
        buildStockAnalysisWorkbenchPayload(strategy, options?.replayClosure),
        {
          basis: "analytical",
          formal_use_allowed: false,
          source_version: "sv_livermore_test",
          vendor_version: "vv_livermore_test",
          rule_version: "rv_stock_analysis_workbench_v2",
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
        options?.confluenceMetaOverrides,
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
          formula_version: "fv_livermore_cycle_proxy_backtest_execution_first_v4",
          proxy_signal_kind: "stock_candidate",
          proxy_rule: "Equal-weight non-overlapping T+5 baskets of completed stock_candidate rows.",
          execution_blocked_rows_in_window: 40,
          snapshot_from: "2024-09-24",
          snapshot_to: "2026-03-02",
          missing_full_strategy_inputs: ["PMI", "credit_impulse"],
          warnings: ["Executable next-open return_5d_net_adj is preferred; close-return fallbacks remain disclosed."],
          summary: {
            sample_days: 225,
            candidate_rows: 546,
            return_field_used: "return_5d_net_adj",
            return_field_fallback: "return_5d_adj",
            return_field_second_fallback: "return_5d",
            execution_return_costs_already_applied: true,
            return_rows_execution_net_adjusted: 433,
            return_rows_adjusted: 23,
            return_rows_adjusted_fallback: 23,
            return_rows_gross_fallback: 90,
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
        options?.strategyOptimizationResultNull
          ? (null as unknown as LivermoreStrategyOptimizationPayload)
          : options?.strategyOptimization ?? buildStrategyOptimizationPayload(),
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
        rule_version: "rv_stock_analysis_workbench_v2",
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
  await screen.findByTestId("stock-analysis-first-screen-workbench");
  await screen.findByTestId("stock-analysis-as-of-picker");
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
    expect(screen.getByTestId("stock-analysis-page-compact-chrome")).toHaveTextContent(resolvedAsOfDate),
  );
}

function expectResearchDeskShell() {
  expect(screen.getByTestId("stock-analysis-first-screen-workbench")).toBeInTheDocument();
  expect(screen.getByTestId("stock-analysis-research-desk")).toBeInTheDocument();
  expect(screen.getByTestId("stock-analysis-review-queue")).toBeInTheDocument();
  expect(screen.getByTestId("stock-analysis-research-dossier")).toBeInTheDocument();
  expect(screen.getByTestId("stock-analysis-action-rail")).toBeInTheDocument();
  expect(screen.getByTestId("stock-analysis-research-audit")).toBeInTheDocument();
}

describe("StockAnalysisPage workbench contract", () => {
  it("shows an explicit recovery state when a successful workbench response has no usable main module", async () => {
    const user = userEvent.setup();
    const workbench = buildStockAnalysisWorkbenchPayload(buildStrategyPayload());
    workbench.modules.main = {
      ...workbench.modules.main,
      status: "missing",
      result: null,
      issues: [
        {
          severity: "blocking",
          code: "main_module_missing",
          message: "main module missing",
          source_module: "main",
        },
      ],
    };
    const workbenchSpy = vi.fn(async () =>
      buildMockApiEnvelope("market_data.stock_analysis.workbench", workbench, {
        basis: "analytical",
        formal_use_allowed: false,
        source_version: "sv_livermore_test",
        rule_version: "rv_stock_analysis_workbench_v2",
      }),
    );
    const client: ApiClient = {
      ...stockClient(),
      getStockAnalysisWorkbench: workbenchSpy,
    };

    renderWorkbenchApp(["/stock-analysis"], { client });

    const boundary = await screen.findByTestId("stock-analysis-error-workbench");
    expect(boundary).toHaveTextContent("主策略模块状态为缺数据");
    expect(boundary).toHaveTextContent("接口已返回，但没有可展示的策略主包");
    expect(screen.queryByTestId("stock-analysis-first-screen-workbench")).not.toBeInTheDocument();

    await user.click(within(boundary).getByRole("button", { name: "重新读取" }));
    await waitFor(() => expect(workbenchSpy).toHaveBeenCalledTimes(2));
  });

  it("does not expose backend candidates when the research review authority is blocked", async () => {
    const strategy = buildStrategyPayload({
      module_states: readyModuleStates().map((state) => ({
        ...state,
        state: "partial",
        render_mode: "evidence_only",
        evidence_scope: "detail",
        excludes_from_primary: true,
      })),
    });
    const workbench = buildStockAnalysisWorkbenchPayload(strategy);
    workbench.page_question = {
      ...workbench.page_question,
      answer_state: "blocked",
      answer_label: "blocked",
      reason: "Data gap status is missing.",
    };
    workbench.decision_summary = {
      ...workbench.decision_summary,
      can_review_candidates: false,
      primary_blocker: "Data gap status is missing.",
    };
    const client: ApiClient = {
      ...stockClient({ strategy }),
      getStockAnalysisWorkbench: vi.fn(async () =>
        buildMockApiEnvelope("market_data.stock_analysis.workbench", workbench, {
          basis: "analytical",
          formal_use_allowed: false,
        }),
      ),
    };

    renderWorkbenchApp(["/stock-analysis"], { client });

    const queue = await screen.findByTestId("stock-analysis-review-queue");
    expect(queue).not.toHaveTextContent("Alpha");
    expect(queue).not.toHaveTextContent("000001.SZ");
    expect(queue).toHaveTextContent("0 / 0");
    await openEvidenceDisclosure();
    expect(screen.getByTestId("stock-analysis-evidence-ledger")).toHaveTextContent("工作台依据 阻断");
  });

  it("keeps authoritative observation research usable when pretrade qualification is unavailable", async () => {
    const user = userEvent.setup();
    vi.spyOn(dataHealthClient, "fetchDataHealth").mockResolvedValue({
      kind: "ok",
      payload: {
        as_of_date: "2026-04-30",
        overall_status: "missing",
        sections: [{ key: "concept_interval_staleness", label: "概念区间", status: "missing", metric: "0 行" }],
      },
    });
    const client = stockClient();
    const baseStrategy = buildStrategyPayload();
    const strategy = buildStrategyPayload({
      supported_outputs: [
        "market_gate",
        "sector_rank",
        "stock_candidates",
        "factor_screen_candidates",
        "risk_exit",
      ],
      stock_candidates: {
        ...baseStrategy.stock_candidates!,
        candidate_count: 0,
        items: [],
      },
      factor_screen_candidates: {
        as_of_date: "2026-04-29",
        formula_version: "rv_factor_screen_candidates_v1",
        market_state: "WARM",
        input_stock_count: 5220,
        candidate_count: 2,
        coverage_note: "当日因子研究池有效，突破策略为真实零值。",
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
          {
            rank: 2,
            stock_code: "600001.SH",
            stock_name: "Factor Beta",
            sector_code: "801730",
            sector_name: "电力设备",
            industry: "电力设备",
            score: 0.744,
            pe: 15.2,
            pb: 1.9,
            roe: 0.121,
            gross_margin: 0.28,
            three_month_return: 0.041,
            twelve_month_return: 0.152,
            dividend_yield: 0.018,
          },
        ],
      },
    });
    const workbench = buildStockAnalysisWorkbenchPayload(strategy);
    const strippedMain = { ...strategy } as Partial<LivermoreStrategyPayload>;
    for (const key of [
      "stock_candidates",
      "factor_screen_candidates",
      "hybrid_fusion_candidates",
      "uptrend_momentum_candidates",
      "fresh_trend_watchlist",
      "mean_reversion_candidates",
      "theme_breakout",
      "risk_exit",
    ] as const) {
      delete strippedMain[key];
    }
    workbench.modules.main = {
      ...workbench.modules.main,
      result: strippedMain as LivermoreStrategyPayload,
    };
    workbench.first_screen.risk_exit_snapshot = [];
    workbench.pretrade_qualification = {
      ...workbench.pretrade_qualification,
      status: "unavailable",
      reason: "completed_pretrade_provenance_missing",
    };
    workbench.decision_summary = {
      ...workbench.decision_summary,
      can_review_candidates: true,
    };
    vi.spyOn(client, "getStockAnalysisWorkbench").mockResolvedValue(
      buildMockApiEnvelope("market_data.stock_analysis.workbench", workbench, {
        basis: "analytical",
        formal_use_allowed: false,
        source_version: "sv_livermore_test",
        rule_version: "rv_stock_analysis_workbench_v2",
      }),
    );
    const detailSpy = vi.spyOn(client, "getLivermoreStockDetail");
    const klineSpy = vi.spyOn(client, "getStockKlineAnalysis");
    const newsSpy = vi.spyOn(client, "getChoiceNewsEvents");
    const confluenceSpy = vi.spyOn(client, "getLivermoreSignalConfluence");
    const candidateHistorySpy = vi.spyOn(client, "getLivermoreCandidateHistory");

    renderWorkbenchApp(["/stock-analysis"], { client });

    const boundary = await screen.findByTestId("stock-analysis-pretrade-qualification-boundary");
    expect(boundary).toHaveTextContent("未找到已闭合的盘前来源资格证据");
    expect(within(boundary).getByRole("button", { name: "重新检查" })).toBeEnabled();
    expect(screen.queryByTestId("stock-analysis-qualification-workbench")).not.toBeInTheDocument();
    expectResearchDeskShell();
    const queue = screen.getByTestId("stock-analysis-review-queue");
    expect(queue).toHaveTextContent("Factor Alpha");
    expect(queue).toHaveTextContent("Factor Beta");
    expect(queue).toHaveTextContent("2 / 2");
    expect(queue).not.toHaveTextContent("突破策略");
    expect(screen.getByTestId("stock-analysis-research-dossier")).toHaveTextContent("Factor Alpha");
    const search = within(queue).getByRole("textbox", { name: "搜索标的" });
    await user.type(search, "Factor Beta");
    await user.click(within(queue).getByRole("button", { name: /600001\.SH.*Factor Beta/ }));
    const dossier = screen.getByTestId("stock-analysis-research-dossier");
    expect(dossier).toHaveTextContent("Factor Beta");
    await user.click(within(dossier).getByRole("button", { name: "基本面" }));
    expect(within(dossier).getByRole("button", { name: "基本面" })).toHaveAttribute("aria-pressed", "true");
    const actionRail = screen.getByTestId("stock-analysis-action-rail");
    const deepResearchButton = within(actionRail).getByRole("button", { name: "开始深度研究" });
    expect(deepResearchButton).toBeEnabled();
    await user.click(deepResearchButton);
    await waitFor(() => expect(screen.getByTestId("stock-analysis-deep-research")).toHaveAttribute("open"));
    const readOnlyResearch = await screen.findByTestId("stock-analysis-readonly-research");
    expect(readOnlyResearch).toHaveTextContent("Factor Beta");
    expect(readOnlyResearch).toHaveTextContent("600001.SH");
    expect(readOnlyResearch).toHaveTextContent("正式评分与代理回测");
    expect(readOnlyResearch).toHaveTextContent("风险与执行保持关闭");
    expect(screen.getAllByTestId("stock-analysis-data-health")).toHaveLength(1);
    for (const name of ["加入自选", "回溯该信号历史表现", "打开原始详情抽屉"]) {
      expect(within(actionRail).getByRole("button", { name })).toBeEnabled();
    }
    const note = within(actionRail).getByRole("textbox", { name: "研究备注" });
    await user.type(note, "盘前资格未闭合，保留观察。");
    await user.click(within(actionRail).getByRole("button", { name: "保存" }));
    expect(actionRail).toHaveTextContent("Factor Beta 600001.SH：盘前资格未闭合，保留观察。");
    await user.click(within(actionRail).getByRole("button", { name: "打开原始详情抽屉" }));
    expect(await screen.findByTestId("stock-detail-drawer")).toHaveTextContent("Factor Beta");
    expect(actionRail).toHaveTextContent("盘前资格尚未闭合，风险退出结论未读取");
    expect(screen.getByTestId("stock-analysis-page-compact-chrome")).toHaveTextContent("2026-04-29");
    expect(screen.queryByTestId("stock-analysis-agent-open")).not.toBeInTheDocument();
    await waitFor(() =>
      expect(detailSpy).toHaveBeenCalledWith({
        stockCode: "600001.SH",
        asOfDate: "2026-04-29",
        lookback: 60,
      }),
    );
    await waitFor(() =>
      expect(klineSpy).toHaveBeenCalledWith({
        stockCode: "600001.SH",
        asOfDate: "2026-04-29",
        lookback: 60,
      }),
    );
    await waitFor(() =>
      expect(newsSpy).toHaveBeenCalledWith(
        expect.objectContaining({ stockCode: "600001.SH", receivedTo: "2026-04-29T23:59:59Z" }),
      ),
    );
    await user.click(within(actionRail).getByRole("button", { name: "回溯该信号历史表现" }));
    await waitFor(() =>
      expect(candidateHistorySpy).toHaveBeenCalledWith(expect.objectContaining({ snapshotTo: "2026-04-29" })),
    );
    expect(confluenceSpy).not.toHaveBeenCalled();
  });

  it("does not treat ready-empty pretrade qualification as an empty research projection", async () => {
    const client = stockClient();
    const workbench = buildStockAnalysisWorkbenchPayload(buildStrategyPayload());
    workbench.pretrade_qualification = {
      ...workbench.pretrade_qualification,
      status: "ready_empty",
      reason: null,
    };
    vi.spyOn(client, "getStockAnalysisWorkbench").mockResolvedValue(
      buildMockApiEnvelope("market_data.stock_analysis.workbench", workbench, {
        basis: "analytical",
        formal_use_allowed: false,
        source_version: "sv_livermore_test",
        rule_version: "rv_stock_analysis_workbench_v2",
      }),
    );
    const detailSpy = vi.spyOn(client, "getLivermoreStockDetail");
    const confluenceSpy = vi.spyOn(client, "getLivermoreSignalConfluence");

    renderWorkbenchApp(["/stock-analysis"], { client });

    const boundary = await screen.findByTestId("stock-analysis-pretrade-qualification-boundary");
    expect(boundary).toHaveTextContent("当日研究数据可用；盘前资格尚未闭合");
    expect(boundary).toHaveTextContent("权威研究候选 2 个");
    expect(screen.queryByTestId("stock-analysis-qualification-workbench")).not.toBeInTheDocument();
    expectResearchDeskShell();
    const queue = screen.getByTestId("stock-analysis-review-queue");
    expect(queue).toHaveTextContent("2 / 2");
    expect(queue).toHaveTextContent("Alpha");
    expect(screen.getByTestId("stock-analysis-research-dossier")).toHaveTextContent("Alpha");
    expect(screen.queryByTestId("stock-analysis-agent-open")).not.toBeInTheDocument();
    await waitFor(() => expect(detailSpy).toHaveBeenCalled());
    expect(confluenceSpy).not.toHaveBeenCalled();
  });

  it("keeps valid research but clears execution data when qualification changes to unavailable", async () => {
      const user = userEvent.setup();
      const client = stockClient();
      const strategy = buildStrategyPayload();
      const readyWorkbench = buildStockAnalysisWorkbenchPayload(strategy);
      const restrictedWorkbench = buildStockAnalysisWorkbenchPayload(strategy);
      restrictedWorkbench.requested_as_of_date = "2026-05-08";
      restrictedWorkbench.pretrade_qualification = {
        ...restrictedWorkbench.pretrade_qualification,
        status: "unavailable",
        reason: "completed_pretrade_provenance_missing",
      };
      restrictedWorkbench.decision_summary = {
        ...restrictedWorkbench.decision_summary,
        can_review_candidates: true,
      };
      const workbenchSpy = vi
        .spyOn(client, "getStockAnalysisWorkbench")
        .mockImplementation(async (options) =>
          buildMockApiEnvelope(
            "market_data.stock_analysis.workbench",
            options?.asOfDate ? restrictedWorkbench : readyWorkbench,
          ),
        );
      const detailSpy = vi.spyOn(client, "getLivermoreStockDetail");
      const confluenceSpy = vi.spyOn(client, "getLivermoreSignalConfluence");

      renderWorkbenchApp(["/stock-analysis"], { client });

      const readyQueue = await screen.findByTestId("stock-analysis-review-queue");
      expect(within(readyQueue).getByRole("button", { name: /000001\.SZ.*Alpha/ })).toBeInTheDocument();
      await waitFor(() => expect(detailSpy).toHaveBeenCalled());
      await waitFor(() => expect(confluenceSpy).toHaveBeenCalledTimes(1));
      expect(screen.getByTestId("stock-analysis-action-rail")).toHaveTextContent(
        "连续 2 日收盘低于 10 日均线",
      );

      await requestStockAnalysisAsOfDate(user, workbenchSpy);
      await waitFor(() =>
        expect(screen.getByTestId("stock-analysis-pretrade-qualification-boundary")).toHaveTextContent(
          "未找到已闭合的盘前来源资格证据",
        ),
      );

      expectResearchDeskShell();
      const restrictedQueue = screen.getByTestId("stock-analysis-review-queue");
      expect(restrictedQueue).toHaveTextContent("2 / 2");
      expect(restrictedQueue).toHaveTextContent("Alpha");
      expect(screen.getByTestId("stock-analysis-research-dossier")).toHaveTextContent("Alpha");
      expect(screen.getByTestId("stock-analysis-action-rail")).toHaveTextContent(
        "盘前资格尚未闭合，风险退出结论未读取",
      );
      expect(screen.getByTestId("stock-analysis-action-rail")).not.toHaveTextContent(
        "连续 2 日收盘低于 10 日均线",
      );
      expect(screen.queryByTestId("stock-analysis-agent-open")).not.toBeInTheDocument();
      expect(detailSpy).toHaveBeenCalled();
      expect(confluenceSpy).toHaveBeenCalledTimes(1);
  });

  it.each([null, "system-read-test"])("keeps fallback dates and source status visible when reads are retried (%s)", async (generation) => {
    const user = userEvent.setup();
    const refreshInteraction = vi.fn();
    vi.spyOn(systemReadInteraction, "useSystemReadInteraction").mockReturnValue({
      generation,
      coverageDates: {},
      refresh: refreshInteraction,
    });
    const client = stockClient();
    const workbench = buildStockAnalysisWorkbenchPayload(buildStrategyPayload());
    workbench.requested_as_of_date = "2026-05-08";
    workbench.as_of_date = "2026-04-29";
    workbench.fallback_date = "2026-04-29";
    workbench.stale = true;
    workbench.pretrade_qualification = {
      ...workbench.pretrade_qualification,
      status: "unavailable",
      reason: "system_read_generation_missing",
      target_date: null,
    };
    workbench.data_status = {
      ...workbench.data_status,
      quality_flag: "warning",
      vendor_status: "degraded",
      fallback_mode: "latest_snapshot",
      source_version: "sv_qualification_fallback_source",
    };
    const workbenchSpy = vi.spyOn(client, "getStockAnalysisWorkbench").mockResolvedValue(
      buildMockApiEnvelope("market_data.stock_analysis.workbench", workbench, {
        basis: "analytical",
        formal_use_allowed: false,
      }),
    );
    const detailSpy = vi.spyOn(client, "getLivermoreStockDetail");
    const confluenceSpy = vi.spyOn(client, "getLivermoreSignalConfluence");
    const choiceRefreshSpy = vi.spyOn(client, "refreshChoiceStock");
    renderWorkbenchApp(["/stock-analysis"], { client });

    const boundary = await screen.findByTestId("stock-analysis-pretrade-qualification-boundary");
    expect(boundary).toHaveTextContent("2026-05-08");
    expect(boundary).toHaveTextContent("2026-04-29");
    expect(boundary).toHaveTextContent("system_read_generation_missing");
    expect(boundary).toHaveTextContent("latest_snapshot");
    expect(boundary).toHaveTextContent("sv_qualification_fallback_source");
    expectResearchDeskShell();
    const picker = screen.getByTestId("stock-analysis-as-of-picker");
    const input = picker instanceof HTMLInputElement ? picker : picker.querySelector("input")!;
    fireEvent.change(input, { target: { value: "2026-05-08" } });
    await waitFor(() => expect(workbenchSpy).toHaveBeenLastCalledWith({ asOfDate: "2026-05-08", topK: 10 }));
    await waitFor(() => expect(screen.getByTestId("stock-analysis-qualification-retry")).toBeEnabled());
    const callsBeforeRetry = workbenchSpy.mock.calls.length;
    fireEvent.click(screen.getByTestId("stock-analysis-qualification-retry"));
    await waitFor(() => expect(workbenchSpy).toHaveBeenCalledTimes(callsBeforeRetry + 1));
    expect(workbenchSpy).toHaveBeenLastCalledWith({ asOfDate: "2026-05-08", topK: 10 });
    expect(screen.getByTestId("stock-analysis-research-desk")).toBeInTheDocument();
    await waitFor(() =>
      expect(detailSpy).toHaveBeenCalledWith({
        stockCode: "000001.SZ",
        asOfDate: "2026-04-29",
        lookback: 60,
      }),
    );
    expect(confluenceSpy).not.toHaveBeenCalled();
    await user.click(screen.getByTestId("stock-analysis-refresh"));
    await waitFor(() =>
      expect(choiceRefreshSpy).toHaveBeenCalledWith(expect.objectContaining({ asOfDate: "2026-04-29" })),
    );
    expect(choiceRefreshSpy).not.toHaveBeenCalledWith(expect.objectContaining({ asOfDate: "2026-05-08" }));
    expect(refreshInteraction).not.toHaveBeenCalled();
  });

  it("shows an unavailable boundary for legacy qualification gaps and excludes mismatched observations", async () => {
    const client = stockClient();
    const workbench = buildStockAnalysisWorkbenchPayload(buildStrategyPayload());
    delete (workbench as Partial<StockAnalysisWorkbenchPayload>).pretrade_qualification;
    workbench.as_of_date = "2026-05-08";
    workbench.decision_summary = {
      ...workbench.decision_summary,
      can_review_candidates: true,
    };
    vi.spyOn(client, "getStockAnalysisWorkbench").mockResolvedValue(
      buildMockApiEnvelope("market_data.stock_analysis.workbench", workbench, {
        basis: "analytical",
        formal_use_allowed: false,
      }),
    );
    renderWorkbenchApp(["/stock-analysis"], { client });

    const boundary = await screen.findByTestId("stock-analysis-pretrade-qualification-boundary");
    expect(boundary).toHaveTextContent("工作台实际日 2026-05-08 与研究主包日期未对齐");
    expectResearchDeskShell();
    expect(screen.getByTestId("stock-analysis-review-queue")).not.toHaveTextContent("Alpha");
    expect(screen.getByTestId("stock-analysis-research-dossier")).toHaveTextContent("暂无研究档案");
    expect(screen.getByTestId("stock-analysis-page")).not.toHaveTextContent("4.80%");
    expect(screen.getByTestId("stock-analysis-page")).not.toHaveTextContent("沪深300收盘价 > MA60");
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
              sector_name: "银行",
              industry: "银行",
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
          formula_version: "rv_hybrid_fusion_candidates_v4",
          market_state: "WARM",
          observation_only: true,
          candidate_count: 1,
          items: [
            {
              rank: 1,
              stock_code: "000001.SZ",
              stock_name: "平安银行",
              sector_code: "801780",
              sector_name: "银行",
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
    const qualificationBoundary = await screen.findByTestId("stock-analysis-pretrade-qualification-boundary");
    expect(qualificationBoundary).toHaveTextContent("来源资格已闭合");
    expect(qualificationBoundary).toHaveTextContent("候选仅供复核，策略门禁仍独立生效");
    await openDeepResearch();
    await openEvidenceDisclosure();

    const digest = await screen.findByTestId("stock-analysis-workbench-digest");
    expect(within(digest).getByTestId("stock-analysis-workbench-fact-candidate-depth")).toHaveTextContent("1 / 1");
    expect(within(digest).queryByTestId("stock-analysis-workbench-fact-factor-candidates")).not.toBeInTheDocument();
    await userEvent.click(within(digest).getByRole("button", { name: /完整证据账本/ }));
    expect(within(digest).getByTestId("stock-analysis-workbench-fact-factor-candidates")).not.toHaveAttribute("title");
    expect(within(digest).getByTestId("stock-analysis-workbench-fact-factor-candidates")).not.toHaveTextContent(
      "strategy.result.factor_screen_candidates.items",
    );
    expect(within(digest).getByTestId("stock-analysis-workbench-fact-hybrid-candidates")).toHaveTextContent(
      "rv_hybrid_fusion_candidates_v4",
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

    await openEvidenceDisclosure(user);
    const digest = await screen.findByTestId("stock-analysis-workbench-digest");
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
    expect(screen.queryByText("数据口径诊断")).not.toBeInTheDocument();
    await waitFor(() => {
      expect(screen.getByTestId("stock-analysis-deep-research")).toHaveAttribute("open");
    });
    expect(
      screen.getByTestId("stock-analysis-strategy-card-strategy-backtest-toggle"),
    ).toHaveAttribute("aria-expanded", "true");
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
    expect(
      within(firstScreen).queryByTestId("stock-analysis-home-rail-diagnostic-entry"),
    ).not.toBeInTheDocument();
    const diagnosticsEntry = within(
      screen.getByTestId("stock-analysis-validation-evidence"),
    ).getByTestId("stock-analysis-home-rail-diagnostic-entry");
    expect(diagnosticsEntry).toHaveAttribute("aria-expanded", "false");

    const openIssuesFact = screen.getByTestId("stock-analysis-workbench-fact-open-issues");
    await user.click(openIssuesFact);

    expect(openIssuesFact).toHaveAttribute("data-active", "true");
    expect(screen.getByTestId("stock-analysis-endpoint-evidence-strategy")).toHaveAttribute("data-active", "true");
    expect(diagnosticsEntry).toHaveAttribute("aria-expanded", "true");
  });

  it("loads and reveals a deferred business panel from the full endpoint diagnostics", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    const candidateHistorySpy = vi.spyOn(client, "getLivermoreCandidateHistory");
    const originalScrollIntoView = Object.getOwnPropertyDescriptor(
      HTMLElement.prototype,
      "scrollIntoView",
    );
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });

    try {
      renderWorkbenchApp(["/stock-analysis"], { client });

      const endpointRail = await screen.findByTestId("stock-analysis-endpoint-evidence-rail");
      expect(candidateHistorySpy).not.toHaveBeenCalled();
      await user.click(
        within(endpointRail).getByRole("button", { name: /打开完整证据诊断/ }),
      );

      const endpointList = await screen.findByTestId("stock-analysis-endpoint-diagnostics-list");
      expect(within(endpointList).getAllByRole("button")).toHaveLength(8);
      await user.click(
        within(endpointList).getByRole("button", { name: "查看策略回溯窗口数据" }),
      );

      await waitFor(
        () =>
          expect(candidateHistorySpy).toHaveBeenCalledWith(
            expect.objectContaining({ snapshotTo: "2026-04-29" }),
          ),
        { timeout: 500 },
      );
      const deepResearch = screen.getByTestId("stock-analysis-deep-research");
      const strategyResearch = screen.getByTestId("stock-analysis-strategy-research-more");
      const backtestPanel = screen.getByTestId("stock-analysis-strategy-backtest");
      expect(deepResearch).toHaveAttribute("open");
      expect(strategyResearch).toHaveAttribute("open");
      expect(
        within(backtestPanel).getByTestId("stock-analysis-strategy-card-strategy-backtest-toggle"),
      ).toHaveAttribute("aria-expanded", "true");
      expect(backtestPanel).toHaveAttribute("data-expanded", "true");
      expect(scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "start" });
      expect(scrollIntoView.mock.instances.at(-1)).toBe(backtestPanel);
    } finally {
      if (originalScrollIntoView) {
        Object.defineProperty(HTMLElement.prototype, "scrollIntoView", originalScrollIntoView);
      } else {
        Reflect.deleteProperty(HTMLElement.prototype, "scrollIntoView");
      }
    }
  });

  it("loads only strategy score evidence when its endpoint entry is selected", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    const strategyScoreSpy = vi.spyOn(client, "getLivermoreStrategyScore");
    const strategyOptimizationSpy = vi.spyOn(client, "getLivermoreStrategyOptimization");
    const candidateHistorySpy = vi.spyOn(client, "getLivermoreCandidateHistory");

    renderWorkbenchApp(["/stock-analysis"], { client });

    const endpoint = await screen.findByTestId("stock-analysis-endpoint-evidence-strategy-score");
    expect(strategyScoreSpy).not.toHaveBeenCalled();
    await user.click(within(endpoint).getByRole("button"));

    await waitFor(() => {
      expect(strategyScoreSpy).toHaveBeenCalledWith({
        snapshotTo: "2026-04-29",
        currentMarketState: "WARM",
        minSample: 20,
        primaryHorizon: "return_5d",
      });
    });
    expect(screen.getByRole("tab", { name: "策略优先级" })).toHaveAttribute("aria-selected", "true");
    expect(strategyOptimizationSpy).not.toHaveBeenCalled();
    expect(candidateHistorySpy).not.toHaveBeenCalled();
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

    await openEvidenceDisclosure();
    const closurePanel = await screen.findByTestId("stock-analysis-observation-closure-panel");
    const reasonList = within(closurePanel).getByTestId("stock-analysis-observation-closure-reasons");

    expect(closurePanel).toHaveTextContent("待复核项 0");
    expect(reasonList).toHaveTextContent("暂无新增待复核项");
    expect(reasonList).not.toHaveTextContent("趋势突破策略");
    expect(reasonList).not.toHaveTextContent("融合策略");
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

    await openEvidenceDisclosure();
    const sourceGate = await screen.findByTestId("stock-analysis-api-evidence-strip");
    expect(sourceGate).toHaveTextContent("来源覆盖");
    expect(sourceGate).toHaveTextContent("证据覆盖");
    expect(sourceGate).not.toHaveTextContent("latest_snapshot");
  });

  // 旧断言锁的是「巨卡 + 更多备选折叠」形态，已被密表取代；这里改锁密度契约本身，
  // 防止队列区回退成单卡 + 多层折叠。
  it("keeps strategy modules summarized by default and opens details on demand", async () => {
    const user = userEvent.setup();
    renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });

    const deepResearch = await screen.findByTestId("stock-analysis-deep-research");
    await user.click(within(deepResearch).getByTestId("stock-analysis-deep-research-summary"));

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

  it("renders the workbench certified replay closure as the page authority", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        confluence: buildReviewableConfluencePayload("available"),
        replayClosure: buildStockAnalysisReplayClosure({
          status: "ready",
          counts: { completed_dates: 1, matched_entry_count: 1 },
        }),
      }),
    });

    const replayStatus = await screen.findByTestId("stock-analysis-replay-status");
    expect(replayStatus).toHaveTextContent("当前规则回放已认证");
    await userEvent.click(within(replayStatus).getByText("明细"));
    expect(replayStatus).toHaveTextContent("模式：当前规则认证批次");
    expect(replayStatus).toHaveTextContent("认证范围：2026-03-02 至 2026-04-29");
    expect(replayStatus).toHaveTextContent("完成日：1/20");
    expect(replayStatus).toHaveTextContent("匹配样本：1/100");
    expect(replayStatus).toHaveTextContent("待成熟尾部：3 日");
    expect(replayStatus).toHaveTextContent("批次：cohort-current-rule-20260429");
    expect(replayStatus).not.toHaveTextContent("候选历史回放已接通");
  });

  it("does not fall back to legacy available when a successful workbench omits replay_closure", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        confluence: buildReviewableConfluencePayload("available"),
      }),
    });

    const replayStatus = await screen.findByTestId("stock-analysis-replay-status");
    expect(replayStatus).toHaveTextContent("当前规则回放新契约缺失 / 证据不足");
    await userEvent.click(within(replayStatus).getByText("明细"));
    expect(replayStatus).toHaveTextContent("replay_closure 未返回");
    expect(replayStatus).toHaveTextContent("不能把旧回放状态视为当前规则认证证据");
    expect(replayStatus).not.toHaveTextContent("候选历史回放已接通");
    expect(screen.getByTestId("stock-analysis-closed-loop-summary")).toHaveTextContent("数据不足");
  });

  it("pauses a certified replay closure when backend marks its availability stale", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        confluence: buildReviewableConfluencePayload("available"),
        replayClosure: buildStockAnalysisReplayClosure({
          status: "ready",
          data_availability: "stale",
        }),
      }),
    });

    const replayStatus = await screen.findByTestId("stock-analysis-replay-status");
    expect(replayStatus).toHaveTextContent("当前规则回放已认证");
    await userEvent.click(within(replayStatus).getByText("明细"));
    expect(replayStatus).toHaveTextContent("供数：陈旧");
    expect(screen.getByTestId("stock-analysis-closed-loop-summary")).toHaveTextContent("暂缓");
  });

  it("shows zero active certified cohort as insufficient despite 20/100 display counts", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        confluence: buildReviewableConfluencePayload("available"),
        replayClosure: buildStockAnalysisReplayClosure({
          selection_status: "no_active_certified",
          data_availability: "no_data",
          status: "insufficient",
          active_cohort_count: 0,
          cohort_id: null,
          certified_start_date: null,
          certified_end_date: null,
          primary_blocker_code: "no_active_certified_cohort",
          reason_codes: ["no_active_certified_cohort"],
          run_id: null,
          promotion_run_id: null,
        }),
      }),
    });

    const replayStatus = await screen.findByTestId("stock-analysis-replay-status");
    expect(replayStatus).toHaveTextContent("无已生效认证批次");
    await userEvent.click(within(replayStatus).getByText("明细"));
    expect(replayStatus).toHaveTextContent("完成日：20/20");
    expect(replayStatus).toHaveTextContent("匹配样本：100/100");
    expect(replayStatus).toHaveTextContent("主要阻断：无已生效认证批次");
    expect(screen.getByTestId("stock-analysis-closed-loop-summary")).toHaveTextContent("数据不足");
  });

  it("shows multiple active certified cohorts as a governance block", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        confluence: buildReviewableConfluencePayload("available"),
        replayClosure: buildStockAnalysisReplayClosure({
          selection_status: "governance_conflict",
          data_availability: "unsupported",
          status: "blocked",
          active_cohort_count: 2,
          cohort_id: null,
          primary_blocker_code: "multiple_active_certified_cohorts",
          reason_codes: ["multiple_active_certified_cohorts"],
          run_id: null,
          promotion_run_id: null,
        }),
      }),
    });

    const replayStatus = await screen.findByTestId("stock-analysis-replay-status");
    expect(replayStatus).toHaveTextContent("治理冲突/阻断");
    await userEvent.click(within(replayStatus).getByText("明细"));
    expect(replayStatus).toHaveTextContent("生效认证批次：2");
    expect(replayStatus).toHaveTextContent("存在多个已生效认证批次");
    expect(screen.getByTestId("stock-analysis-closed-loop-summary")).toHaveTextContent("拦截");
  });

  it("scopes shell compression to the stock-analysis route", () => {
    const css = readStockAnalysisCss();

    expect(css).toContain(".stock-analysis-page__compact-chrome");
    expect(css).toContain(".stock-analysis-page__compact-status-strip");
    expect(css).toContain(".stock-analysis-page__compact-toolbar");
    expect(css).toContain(".stock-analysis-page__workbench-actions");
    expect(css).not.toContain('[data-testid="market-workbench-topbar"]');
    expect(css).not.toContain(".stock-analysis-page__toolbar-title");
    expect(css).not.toContain(".stock-analysis-page__toolbar-pill");
  });

  it("keeps tablet toolbar dates readable and commands icon-led", () => {
    const css = readStockAnalysisCss();
    expect(css).toContain(".stock-analysis-page__workbench-actions");
    expect(css).toContain(".stock-analysis-page__compact-toolbar");
    expect(css).not.toContain(".stock-analysis-page__toolbar-pill:nth-of-type(2)");
    expect(css).not.toContain(".stock-analysis-page__header-controls");
    expect(css).toMatch(
      /\.stock-analysis-page__compact-toolbar[\s\S]*?> span:not\(\.ant-btn-icon\):not\(\.anticon\)[\s\S]*?clip:\s*auto;/,
    );
    expect(css).not.toContain(".stock-analysis-page__toolbar-pill:nth-of-type(5)");
  });

  it("keeps the stock cockpit shell single-column while the rail is hidden", () => {
    const css = readStockAnalysisCss();
    const conflictingDesktopRule = css.indexOf("@media (min-width: 721px)");
    const containmentOverride = css.indexOf("Intermediate stock cockpit containment");

    expect(conflictingDesktopRule).toBeGreaterThan(-1);
    expect(containmentOverride).toBeGreaterThan(conflictingDesktopRule);
    expect(css.slice(containmentOverride)).toMatch(
      /@media \(min-width:\s*721px\) and \(max-width:\s*1180px\)[\s\S]*?\.workbench-shell-grid--cockpit\.workbench-shell-grid--stock-analysis\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s*!important/,
    );
  });

  it("keeps essential stock toolbar controls touch-sized while redundant captions stay quiet", () => {
    const css = readStockAnalysisCss();
    expect(css).not.toContain('[data-testid="market-workbench-topbar"]');
    expect(css).toMatch(
      /\.stock-analysis-page__workbench-actions\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s*auto/,
    );
    expect(css).toMatch(
      /\.stock-analysis-page__workbench-actions-row--context\s*\{[^}]*grid-template-columns:\s*minmax\(136px,\s*148px\)\s*minmax\(0,\s*1fr\)/,
    );
    expect(css).toMatch(
      /\.stock-analysis-page__compact-toolbar\s*\[data-testid="stock-analysis-as-of-picker"\]\s*\{[^}]*min-height:\s*34px;/,
    );
    expect(css).toMatch(
      /\.stock-analysis-page__compact-toolbar\s+\.stock-analysis-page__queue-search\s*\{[^}]*display:\s*flex;[^}]*min-height:\s*34px;/,
    );
    expect(css).toMatch(
      /@container stock-analysis-compact \(max-width:\s*560px\)[\s\S]*?\.stock-analysis-page__workbench-actions-row--context\s*\{[^}]*grid-template-columns:\s*minmax\(0,\s*1fr\)/,
    );
    expect(css).toMatch(
      /@container stock-analysis-compact \(max-width:\s*390px\)[\s\S]*?\.stock-analysis-page__compact-toolbar \.stock-analysis-page__agent-entry--quiet\.ant-btn,[\s\S]*?\[data-testid="stock-analysis-refresh"\]\.ant-btn\s*\{[^}]*min-height:\s*44px;/,
    );
    expect(css).toMatch(
      /@container stock-analysis-compact \(max-width:\s*390px\)[\s\S]*?\[data-testid="stock-analysis-as-of-picker"\][^}]*min-height:\s*44px;/,
    );
    expect(css).toMatch(
      /@container stock-analysis-compact \(max-width:\s*390px\)[\s\S]*?\.stock-analysis-page__queue-search[^}]*min-height:\s*44px;/,
    );
    expect(css).toMatch(
      /@container stock-analysis-compact \(max-width:\s*390px\)[\s\S]*?\.stock-analysis-page__queue-search input\s*\{[^}]*height:\s*42px;[^}]*min-height:\s*42px;/,
    );
    expect(css).not.toContain(".stock-analysis-page__toolbar-route-chip");
    expect(css).not.toContain(".stock-analysis-page__complete-evidence-toggle");
    expect(css).toMatch(
      /\.stock-analysis-page__compact-toolbar[\s\S]*?\.stock-analysis-page__agent-entry--quiet\.ant-btn[\s\S]*?> span:not\(\.ant-btn-icon\):not\(\.anticon\)[\s\S]*?clip:\s*auto;/,
    );
    expect(css).toMatch(
      /\.stock-analysis-page__compact-toolbar[\s\S]*?\[data-testid="stock-analysis-refresh"\]\.ant-btn[\s\S]*?> span:not\(\.ant-btn-icon\):not\(\.anticon\)[\s\S]*?clip:\s*auto;/,
    );
  });

  it("keeps lower supply diagnostics behind disclosures so stock selection moves up", () => {
    const css = readStockAnalysisCss();
    const disclosureStart = css.indexOf("Lower audit disclosure pass");
    const disclosureCss = css.slice(disclosureStart);

    expect(disclosureStart).toBeGreaterThan(-1);
    expect(disclosureCss).not.toContain(".stock-analysis-page__api-readiness-disclosure");
    expect(disclosureCss).toContain(".stock-analysis-page__deep-zone-detail-shell");
    expect(disclosureCss).not.toMatch(
      /\.stock-analysis-page__api-readiness-disclosure\s*\{[^}]*\n\s*order\s*:/,
    );
    expect(disclosureCss).not.toMatch(/\.stock-analysis-page__workspace\s*\{[^}]*\n\s*order\s*:/);
    expect(disclosureCss).not.toMatch(/\.stock-analysis-page__v6-audit-disclosure\s*\{[^}]*\n\s*order\s*:/);
    expect(disclosureCss).toMatch(
      /\.stock-analysis-page__deep-zone-header--compact\s*\{[\s\S]*?padding:\s*10px 12px/,
    );
    expect(disclosureCss).toContain("Deep-zone supply header compact pass");
    expect(disclosureCss).not.toMatch(
      /\.stock-analysis-page__deep-zone\s*>\s*\.stock-analysis-page__deep-zone-header--compact\s*\{[\s\S]*?margin-bottom:\s*8px[\s\S]*?padding:\s*6px 8px/,
    );
    expect(disclosureCss).not.toMatch(
      /\.stock-analysis-page__deep-zone\s*>\s*\.stock-analysis-page__deep-zone-header--compact h2\s*\{[\s\S]*?clip-path:\s*inset\(50%\)/,
    );
    expect(disclosureCss).not.toMatch(
      /\.stock-analysis-page__deep-zone\s*>\s*\.stock-analysis-page__deep-zone-header--compact \[data-testid="stock-analysis-deep-zone-gate-summary"\]\s*\{[\s\S]*?min-height:\s*22px[\s\S]*?background:\s*var\(--ib-surface\)[\s\S]*?white-space:\s*nowrap/,
    );
    expect(disclosureCss).not.toMatch(
      /\.stock-analysis-page__deep-zone\s*>\s*\.stock-analysis-page__deep-zone-header--compact \.stock-analysis-page__deep-zone-detail-summary\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)\s*auto[\s\S]*?min-height:\s*26px/,
    );
    expect(disclosureCss).toMatch(
      /\.stock-analysis-page__deep-zone\s*>\s*\[data-testid="stock-analysis-stock-selection"\]\s*\{[\s\S]*?grid-row:\s*auto[\s\S]*?order:\s*1/,
    );
    expect(disclosureCss).toMatch(
      /\.stock-analysis-page__deep-zone\s*>\s*\.stock-analysis-page__strategy-research-more\s*\{[\s\S]*?grid-row:\s*auto[\s\S]*?order:\s*2/,
    );
    expect(disclosureCss).not.toMatch(
      /\.stock-analysis-page__api-readiness-summary,[\s\S]*?\.stock-analysis-page__deep-zone-detail-summary\s*\{[\s\S]*?min-height:\s*38px/,
    );
    expect(disclosureCss).not.toMatch(
      /\.stock-analysis-page__api-readiness-disclosure:not\(\[open\]\)\s*>\s*\.stock-analysis-page__api-readiness-detail,[\s\S]*?display:\s*none/,
    );
    expect(disclosureCss).not.toContain("Mobile supply diagnostics compact pass");
    expect(disclosureCss).not.toMatch(
      /\.stock-analysis-page__api-readiness-disclosure:not\(\[open\]\)\s*\{[\s\S]*?max-height:\s*30px[\s\S]*?margin-top:\s*4px[\s\S]*?margin-bottom:\s*0[\s\S]*?overflow:\s*hidden/,
    );
    expect(disclosureCss).not.toMatch(
      /\.stock-analysis-page__api-readiness-disclosure:not\(\[open\]\)\s*\+\s*\.stock-analysis-page__workspace\s*\{[\s\S]*?margin-top:\s*-8px/,
    );
    expect(disclosureCss).not.toMatch(
      /\.stock-analysis-page__api-readiness-summary\s*\{[\s\S]*?min-height:\s*28px[\s\S]*?padding:\s*3px 8px/,
    );
    expect(disclosureCss).toMatch(
      /\.stock-analysis-page__deep-zone:not\(:has\(\.stock-analysis-page__deep-zone-detail-shell\[open\]\)\)\s*\{[\s\S]*?gap:\s*2px/,
    );
    expect(disclosureCss).toMatch(
      /\.stock-analysis-page__deep-zone\s*>\s*\.stock-analysis-page__deep-zone-header--compact:not\(:has\(\.stock-analysis-page__deep-zone-detail-shell\[open\]\)\)\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)\s*28px[\s\S]*?max-height:\s*32px[\s\S]*?margin-bottom:\s*0/,
    );
    expect(disclosureCss).toMatch(
      /\.stock-analysis-page__deep-zone-detail-summary small\s*\{[\s\S]*?display:\s*none/,
    );
  });

  it("keeps strategy lens evidence metadata behind a compact disclosure", () => {
    const css = readStockAnalysisCss();
    const strategyMetaStart = css.indexOf("Strategy lens metadata disclosure pass");
    const strategyMetaCss = css.slice(strategyMetaStart);

    expect(strategyMetaStart).toBeGreaterThan(-1);
    expect(strategyMetaCss).toContain(".stock-analysis-page__strategy-lens-meta");
    expect(strategyMetaCss).toMatch(
      /\.stock-analysis-page__strategy-lens-meta-summary\s*\{[\s\S]*?min-height:\s*30px/,
    );
    expect(strategyMetaCss).toMatch(
      /\.stock-analysis-page__strategy-lens-meta:not\(\[open\]\)\s*>\s*\.stock-analysis-page__strategy-lens-ledger,[\s\S]*?\.stock-analysis-page__strategy-lens-meta:not\(\[open\]\)\s*>\s*\.stock-analysis-page__strategy-lens-evidence\s*\{[\s\S]*?display:\s*none/,
    );
  });

  it("keeps strategy lens candidate lists to the top item by default", () => {
    const css = readStockAnalysisCss();
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
    expect(candidateDisclosureCss).not.toMatch(
      /\.stock-analysis-page__strategy-lens-candidates-more:not\(\[open\]\)\s*>\s*\.stock-analysis-page__strategy-lens-candidates--extra\s*\{[\s\S]*?display:\s*none/,
    );
  });

  it("keeps later strategy lenses behind a compact disclosure by default", () => {
    const css = readStockAnalysisCss();
    const component = readFileSync(STOCK_ANALYSIS_STRATEGY_LENS_SECTION_PATH, "utf8");
    const strategyDisclosureStart = css.indexOf("Strategy lens candidate-strategy disclosure pass");
    const strategyDisclosureCss = css.slice(strategyDisclosureStart);

    expect(strategyDisclosureStart).toBeGreaterThan(-1);
    expect(component).toContain("const STRATEGY_LENS_DEFAULT_CARD_COUNT = 1;");
    // 主卡位取 walk-forward 判定最强的一张（削弱池不占首屏，见 A3），其余全部进折叠区。
    expect(component).toContain("primaryCandidateItems.slice(0, STRATEGY_LENS_DEFAULT_CARD_COUNT)");
    expect(component).toContain("candidateItems.filter((item) => !visibleKeys.has(item.key))");
    expect(component).toContain('data-testid="stock-analysis-strategy-lens-more-strategies"');
    expect(component.indexOf("visibleItems.map(renderStrategyCard)")).toBeLessThan(
      component.indexOf('data-testid="stock-analysis-strategy-lens-more-strategies"'),
    );
    expect(strategyDisclosureCss).toContain(".stock-analysis-page__strategy-lens-more-strategies");
    expect(strategyDisclosureCss).toMatch(
      /\.stock-analysis-page__strategy-lens-more-strategies-summary\s*\{[\s\S]*?min-height:\s*32px/,
    );
    expect(strategyDisclosureCss).not.toMatch(
      /\.stock-analysis-page__strategy-lens-more-strategies:not\(\[open\]\)\s*>\s*\.stock-analysis-page__strategy-lens-more-strategies-grid\s*\{[\s\S]*?display:\s*none/,
    );
  });

  it("keeps default strategy lens cards as compact stock-picking entries", () => {
    const css = readStockAnalysisCss();
    const compactStart = css.indexOf("Strategy lens default-entry compact pass");
    const compactCss = css.slice(compactStart);

    expect(compactStart).toBeGreaterThan(-1);
    expect(compactCss).not.toMatch(
      /\[data-testid="stock-analysis-strategy-lens"\]\s*\.stock-analysis-page__strategy-lens-card\s*\{[\s\S]*?gap:\s*5px;[\s\S]*?min-height:\s*0;[\s\S]*?padding:\s*8px;[\s\S]*?background:\s*var\(--ib-paper\);/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-strategy-lens"\]\s*\.stock-analysis-page__strategy-lens-subtitle\s*\{[\s\S]*?display:\s*none;/,
    );
    expect(compactCss).not.toMatch(
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
    expect(compactCss).not.toMatch(
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
      /\[data-testid="stock-analysis-strategy-lens"\]\s*\.stock-analysis-page__strategy-lens-meta-summary small\s*\{[\s\S]*?display:\s*none;/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-strategy-lens"\]\s*\.stock-analysis-page__strategy-lens-card:has\(\.stock-analysis-page__strategy-lens-meta\[open\]\),[\s\S]*?grid-template-areas:[\s\S]*?"head main"[\s\S]*?"meta meta"[\s\S]*?"candidate candidate"[\s\S]*?"more more"[\s\S]*?"meter meter";[\s\S]*?overflow:\s*visible;/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-strategy-lens"\]\s*\.stock-analysis-page__strategy-lens-card:has\(\.stock-analysis-page__strategy-lens-meta\[open\]\)\s*\.stock-analysis-page__strategy-lens-meta-summary small,[\s\S]*?display:\s*block;/,
    );
  });

  it("keeps zero-hit consensus scans compact in the deep-review workspace", () => {
    const css = readStockAnalysisCss();
    const compactStart = css.indexOf("Consensus empty scan compact pass");
    const compactCss = css.slice(compactStart);

    expect(compactStart).toBeGreaterThan(-1);
    expect(compactCss).toMatch(
      /\.stock-analysis-page__deep-review-workspace\s*\[data-testid="stock-analysis-consensus-first-screen"\]\s*\[data-testid="stock-analysis-consensus-empty-scan"\]\s*\{[\s\S]*?display:\s*grid[\s\S]*?grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)/,
    );
    expect(compactCss).not.toMatch(
      /\.stock-analysis-page__deep-review-workspace\s*\[data-testid="stock-analysis-consensus-first-screen"\]\s*\[data-testid="stock-analysis-consensus-empty-scan"\]\s*\[role="status"\]\s*\{[\s\S]*?min-height:\s*42px/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__deep-review-workspace\s*\[data-testid="stock-analysis-consensus-first-screen"\]\s*\[data-testid="stock-analysis-consensus-empty-scan"\]\s*\.stock-analysis-page__compact-status-tile__label,[\s\S]*?\.stock-analysis-page__compact-status-tile__value\s*\{[\s\S]*?white-space:\s*nowrap/,
    );
    expect(compactCss).not.toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-consensus-first-screen"\]\s*\{[\s\S]*?min-height:\s*156px/,
    );
    expect(compactCss).toContain("Consensus zero-state background-entry compact pass");
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-consensus-first-screen"\]:has\(\[data-testid="stock-analysis-consensus-empty-scan"\]\)\s*\{[\s\S]*?min-height:\s*0[\s\S]*?padding:\s*8px 10px/,
    );
    // The zero-hit panel must stay compact by sizing its own content, not by a
    // fixed clamp: a 92px cap cut the scan tile values off at the bottom edge
    // once the tiles grew to 96px.
    expect(compactCss).not.toMatch(
      /\[data-testid="stock-analysis-consensus-first-screen"\]:has\(\[data-testid="stock-analysis-consensus-empty-scan"\]\)\s*\{[^}]*max-height:/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-consensus-first-screen"\]:has\(\[data-testid="stock-analysis-consensus-empty-scan"\]\)\s*>\s*\.stock-analysis-page__dh-section-head\s*\{[\s\S]*?min-height:\s*24px[\s\S]*?border-bottom:\s*0/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-consensus-first-screen"\]:has\(\[data-testid="stock-analysis-consensus-empty-scan"\]\)\s*\.stock-analysis-page__consensus-workbench-strip\s*\{[\s\S]*?display:\s*none/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-consensus-first-screen"\]:has\(\[data-testid="stock-analysis-consensus-empty-scan"\]\)[\s\S]*?\[data-testid="stock-analysis-consensus-empty-scan"\]\s*\{[\s\S]*?grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)[\s\S]*?min-height:\s*28px/,
    );
    expect(compactCss).toMatch(
      /@media\s*\(max-width:\s*720px\)\s*\{[\s\S]*?\[data-testid="stock-analysis-consensus-first-screen"\]:has\(\[data-testid="stock-analysis-consensus-empty-scan"\]\)\s*\{[\s\S]*?padding:\s*7px 8px/,
    );
  });

  it("keeps zero-candidate strategy cards behind a collapsed background disclosure", () => {
    const css = readStockAnalysisCss();
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
      /\.stock-analysis-page__strategy-lens-empty-strategies:not\(\[open\]\)\s*>\s*\.stock-analysis-page__strategy-lens-empty-strategies-grid\s*\{[\s\S]*?display:\s*none/,
    );
  });

  it("keeps observation preview candidates to the top item by default", () => {
    const css = readStockAnalysisCss();
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
      /\.stock-analysis-page__observation-preview-more:not\(\[open\]\)\s*>\s*\.stock-analysis-page__observation-preview-extra\s*\{[\s\S]*?display:\s*none/,
    );
    expect(disclosureCss).toContain("Observation pool secondary compact pass");
    expect(disclosureCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]\s*>\s*\.stock-analysis-page__dh-section-head h2\s*\{[\s\S]*?color:\s*var\(--sa-dh-ink\)/,
    );
    expect(disclosureCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]\s*\.stock-analysis-page__observation-preview-panel\s*\{[\s\S]*?padding:\s*6px 8px/,
    );
    expect(disclosureCss).not.toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]\s*\.stock-analysis-page__observation-preview-more-summary\s*\{[\s\S]*?min-height:\s*20px[\s\S]*?padding:\s*1px 5px/,
    );
    expect(disclosureCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]:has\(\.stock-analysis-page__observation-preview-more\[open\]\)\s*\{[\s\S]*?min-height:\s*0[\s\S]*?overflow:\s*visible/,
    );
    expect(disclosureCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]:has\(\.stock-analysis-page__observation-preview-more\[open\]\)\s*\.stock-analysis-page__observation-preview-grid\s*\{[\s\S]*?flex:\s*0 0 auto[\s\S]*?overflow:\s*visible/,
    );
    expect(disclosureCss).toContain("Observation pool default-entry compact pass");
    expect(disclosureCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]\s*>\s*\.stock-analysis-page__dh-section-head\s*\{[\s\S]*?min-height:\s*32px[\s\S]*?border-bottom:\s*0/,
    );
    expect(disclosureCss).toMatch(
      /\.stock-analysis-page__dh-section-eyebrow,[\s\S]*?\.stock-analysis-page__lower-signal-strip\s*\{[\s\S]*?display:\s*none/,
    );
    expect(disclosureCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]\s*\.stock-analysis-page__observation-preview-grid\s*\{[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/,
    );
    expect(disclosureCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]\s*\.stock-analysis-page__observation-preview-panel\s*\{[\s\S]*?grid-template-columns:\s*minmax\(58px,\s*72px\)\s*minmax\(0,\s*1fr\)\s*auto/,
    );
    expect(disclosureCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]\s*\.stock-analysis-page__table thead\s*\{[\s\S]*?display:\s*none/,
    );
    expect(disclosureCss).not.toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]\s*\.stock-analysis-page__mean-reversion-metrics span:first-child\s*\{[\s\S]*?display:\s*none/,
    );
    expect(disclosureCss).toMatch(
      /@media\s*\(max-width:\s*720px\)\s*\{[\s\S]*?\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]\s*\.stock-analysis-page__observation-preview-grid\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)/,
    );
    expect(disclosureCss).toContain("Observation pool mobile-entry compact pass");
    expect(disclosureCss).toMatch(
      /@media\s*\(max-width:\s*720px\)\s*\{[\s\S]*?\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]\s*>\s*\.stock-analysis-page__dh-section-head\s*\{[\s\S]*?display:\s*none/,
    );
    expect(disclosureCss).not.toMatch(
      /@media\s*\(max-width:\s*720px\)\s*\{[\s\S]*?\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]\s*\.stock-analysis-page__observation-preview-panel\s*\{[\s\S]*?min-height:\s*46px[\s\S]*?padding:\s*5px 6px/,
    );
    expect(disclosureCss).toContain("Observation pool desktop-entry compact pass");
    expect(disclosureCss).not.toMatch(
      /@media\s*\(min-width:\s*721px\)\s*\{[\s\S]*?\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]\s*\{[\s\S]*?min-height:\s*112px[\s\S]*?padding:\s*7px 9px/,
    );
    expect(disclosureCss).toMatch(
      /@media\s*\(min-width:\s*721px\)\s*\{[\s\S]*?\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-observation-preview"\]\s*>\s*\.stock-analysis-page__dh-section-head\s*\{[\s\S]*?display:\s*none/,
    );
  });

  it("keeps sector strength background detail collapsed by default", () => {
    const css = readStockAnalysisCss();
    const page = readStockAnalysisPageSource();

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
      /\.stock-analysis-page__sector-detail-more:not\(\[open\]\)\s*>\s*\.stock-analysis-page__sector-detail-more-body\s*\{[\s\S]*?display:\s*none/,
    );
    expect(css).toMatch(
      /\.stock-analysis-page__sector-rank-grid--secondary\s*\{[\s\S]*?grid-template-columns:\s*repeat\(auto-fit,\s*minmax\(220px,\s*1fr\)\)/,
    );
  });

  it("keeps empty theme leader radar as a compact background cue", () => {
    const css = readStockAnalysisCss();
    const page = readStockAnalysisPageSource();
    const compactStart = css.indexOf("Theme leader empty-state compact pass");
    const compactCss = css.slice(compactStart);

    expect(compactStart).toBeGreaterThan(-1);
    expect(page).toContain('testId="stock-analysis-theme-leader-empty"');
    expect(compactCss).not.toMatch(
      /\[data-testid="stock-analysis-theme-leaders-first-screen"\]:has\(\[data-testid="stock-analysis-theme-leader-empty"\]\)\s*\{[\s\S]*?gap:\s*5px;[\s\S]*?min-height:\s*0;[\s\S]*?padding:\s*8px 10px;/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-theme-leaders-first-screen"\]:has\(\[data-testid="stock-analysis-theme-leader-empty"\]\)[\s\S]*?>\s*\.stock-analysis-page__dh-section-head\s*\{[\s\S]*?min-height:\s*24px;[\s\S]*?border-bottom:\s*0;/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-theme-leaders-first-screen"\]:has\(\[data-testid="stock-analysis-theme-leader-empty"\]\)[\s\S]*?\.stock-analysis-page__dh-section-head h2\s*\{[\s\S]*?color:\s*var\(--sa-dh-ink\);/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__dh-section-eyebrow,[\s\S]*?\.stock-analysis-page__lower-signal-strip\s*\{[\s\S]*?display:\s*none;/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-theme-leader-empty"\]\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)\s*auto;[\s\S]*?min-height:\s*28px;/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-theme-leader-empty"\][\s\S]*?> span:first-child\s*\{[\s\S]*?display:\s*none;/,
    );
  });

  it("keeps sector heavyweight evidence compact in the stock-selection default flow", () => {
    const css = readStockAnalysisCss();
    const compactStart = css.indexOf("Sector heavyweight compact pass");
    const compactCss = css.slice(compactStart);

    expect(compactStart).toBeGreaterThan(-1);
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-sector-heavyweights-first-screen"\]\s*\.stock-analysis-page__lower-signal-strip,[\s\S]*?\.stock-analysis-page__dh-pill,[\s\S]*?\.stock-analysis-page__sector-heavyweight-list\s*\{[\s\S]*?display:\s*none/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__dh-section-head h2\s*\{[\s\S]*?color:\s*var\(--sa-dh-ink\)/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__sector-heavyweight-coverage\s*\{[\s\S]*?display:\s*inline-flex/,
    );
    expect(compactCss).not.toMatch(
      /\.stock-analysis-page__sector-heavyweight-grid\s*\{[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)[\s\S]*?min-height:\s*46px/,
    );
    // 权重股走势上线后：8 张板块卡全量可见（不允许 nth-child 截断），区块不设 max-height 钳位。
    expect(compactCss).not.toMatch(
      /\.stock-analysis-page__sector-heavyweight-card:nth-child\(n \+ 3\)\s*\{[^}]*display:\s*none/,
    );
    expect(compactCss).toContain("Sector heavyweight stock-entry compact pass");
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-sector-heavyweights-first-screen"\]\s*\{[\s\S]*?min-height:\s*0[\s\S]*?padding:\s*7px 9px/,
    );
    expect(compactCss).not.toMatch(
      /\[data-testid="stock-analysis-sector-heavyweights-first-screen"\]\s*\{[^}]*max-height:\s*108px/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__sector-heavyweight-list\s*\{[\s\S]*?display:\s*flex[\s\S]*?background:\s*transparent/,
    );
    expect(compactCss).not.toMatch(
      /\.stock-analysis-page__sector-heavyweight-head span\s*\{[^}]*display:\s*none/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__sector-heavyweight-metrics,[\s\S]*?\.stock-analysis-page__sector-heavyweight-row em\s*\{[\s\S]*?display:\s*none/,
    );
    expect(compactCss).toMatch(
      /@media\s*\(max-width:\s*720px\)\s*\{[\s\S]*?\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-sector-heavyweights-first-screen"\]\s*\{[\s\S]*?max-height:\s*100px/,
    );
  });

  it("keeps sector strength background compact inside stock selection", () => {
    const css = readStockAnalysisCss();
    const compactStart = css.indexOf("Sector strength background compact pass");
    const compactCss = css.slice(compactStart);

    expect(compactStart).toBeGreaterThan(-1);
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-sector-strength-panel"\]\s*\{[\s\S]*?gap:\s*4px[\s\S]*?padding:\s*8px 10px/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__dh-section-head h2\s*\{[\s\S]*?color:\s*var\(--sa-dh-ink\)/,
    );
    expect(compactCss).not.toMatch(
      /\.stock-analysis-page__sector-workbench-strip\s*>\s*div:nth-child\(4\)\s*\{[\s\S]*?display:\s*none/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__sector-rank-grid\s*\{[\s\S]*?max-height:\s*92px[\s\S]*?overflow:\s*hidden/,
    );
    expect(compactCss).not.toMatch(
      /\.stock-analysis-page__sector-rank-list\s*>\s*\.stock-analysis-page__sector-rank-row:nth-child\(n \+ 3\)\s*\{[\s\S]*?display:\s*none/,
    );
    expect(compactCss).toContain("Sector strength default-entry compact pass");
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-sector-strength-panel"\]\s*>\s*\.stock-analysis-page__dh-section-head\s*\{[\s\S]*?min-height:\s*28px[\s\S]*?border-bottom:\s*0/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__dh-section-eyebrow,[\s\S]*?\.stock-analysis-page__dh-section-desc,[\s\S]*?\.stock-analysis-page__dh-pill\s*\{[\s\S]*?display:\s*none/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__sector-workbench-strip\s*\{[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/,
    );
    expect(compactCss).not.toMatch(
      /\.stock-analysis-page__sector-workbench-strip\s*>\s*div:nth-child\(n \+ 3\)\s*\{[\s\S]*?display:\s*none/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-sector-strength-panel"\]:not\(:has\(\.stock-analysis-page__sector-detail-more\[open\]\)\)\s*\.stock-analysis-page__sector-tabs\s*\{[\s\S]*?display:\s*none/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-sector-strength-panel"\]:not\(:has\(\.stock-analysis-page__sector-detail-more\[open\]\)\)\s*\.stock-analysis-page__sector-rank-grid\s*\{[\s\S]*?max-height:\s*30px/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-sector-strength-panel"\]:not\(:has\(\.stock-analysis-page__sector-detail-more\[open\]\)\)\s*\.stock-analysis-page__sector-rank-bar\s*\{[\s\S]*?display:\s*none/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-sector-strength-panel"\]:not\(:has\(\.stock-analysis-page__sector-detail-more\[open\]\)\)\s*\.stock-analysis-page__sector-rank-list\s*>\s*\.stock-analysis-page__sector-rank-row:nth-child\(n \+ 2\)\s*\{[\s\S]*?display:\s*none/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-sector-strength-panel"\]:has\(\.stock-analysis-page__sector-detail-more\[open\]\)\s*\.stock-analysis-page__sector-rank-grid\s*\{[\s\S]*?max-height:\s*none[\s\S]*?overflow:\s*visible/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-sector-strength-panel"\]:has\(\.stock-analysis-page__sector-detail-more\[open\]\)\s*\.stock-analysis-page__sector-workbench-strip\s*\{[\s\S]*?grid-template-columns:\s*repeat\(4,\s*minmax\(0,\s*1fr\)\)/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-sector-strength-panel"\]:has\(\.stock-analysis-page__sector-detail-more\[open\]\)\s*\.stock-analysis-page__sector-workbench-strip\s*>\s*div\s*\{[\s\S]*?display:\s*grid/,
    );
    expect(compactCss).toContain("Sector strength triage-entry compact pass");
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-sector-strength-panel"\]:not\(:has\(\.stock-analysis-page__sector-detail-more\[open\]\)\)\s*\{[\s\S]*?max-height:\s*82px[\s\S]*?padding:\s*6px 8px/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-sector-strength-panel"\]:not\(:has\(\.stock-analysis-page__sector-detail-more\[open\]\)\)[\s\S]*?\.stock-analysis-page__sector-workbench-strip\s*\{[\s\S]*?grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__sector-workbench-strip\s*>\s*div:first-child\s*\{[\s\S]*?display:\s*none/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__sector-workbench-strip\s*>\s*div:nth-child\(n \+ 2\)\s*\{[\s\S]*?display:\s*grid[\s\S]*?min-height:\s*24px/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-sector-strength-panel"\]:not\(:has\(\.stock-analysis-page__sector-detail-more\[open\]\)\)[\s\S]*?\.stock-analysis-page__sector-rank-grid\s*\{[\s\S]*?display:\s*none/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__sector-detail-more-summary\s*\{[\s\S]*?min-height:\s*22px[\s\S]*?padding:\s*1px 6px/,
    );
    expect(compactCss).toMatch(
      /@media\s*\(max-width:\s*720px\)\s*\{[\s\S]*?\[data-testid="stock-analysis-sector-strength-panel"\]:not\(:has\(\.stock-analysis-page__sector-detail-more\[open\]\)\)\s*\{[\s\S]*?max-height:\s*78px/,
    );
    expect(compactCss).toContain("Sector strength label-fold compact pass");
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-sector-strength-panel"\]:not\(:has\(\.stock-analysis-page__sector-detail-more\[open\]\)\)\s*\{[\s\S]*?max-height:\s*82px[\s\S]*?padding:\s*6px 8px/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-sector-strength-panel"\]:not\(:has\(\.stock-analysis-page__sector-detail-more\[open\]\)\)[\s\S]*?>\s*\.stock-analysis-page__dh-section-head\s*\{[\s\S]*?display:\s*none/,
    );
    expect(compactCss).toMatch(
      /@media\s*\(max-width:\s*720px\)\s*\{[\s\S]*?\[data-testid="stock-analysis-sector-strength-panel"\]:not\(:has\(\.stock-analysis-page__sector-detail-more\[open\]\)\)\s*\{[\s\S]*?max-height:\s*78px/,
    );
  });

  it("keeps first-screen analytics compact until a diagnostic tab is opened", () => {
    const css = readStockAnalysisCss();
    const compactStart = css.indexOf("First-screen analytics compact pass");
    const compactCss = css.slice(compactStart);

    expect(compactStart).toBeGreaterThan(-1);
    expect(compactCss).not.toMatch(
      /\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-first-screen-analytics"\]\s*\{[\s\S]*?min-height:\s*118px[\s\S]*?max-height:\s*128px[\s\S]*?overflow:\s*hidden/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__analytics-tabs\s*\.ant-tabs-content-holder\s*\{[\s\S]*?display:\s*none/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__signal-pill:nth-child\(2\)\s*\{[\s\S]*?display:\s*none/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__dh-section-head h2\s*\{[\s\S]*?color:\s*var\(--ib-ink\)/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__analytics-tabs\s*\.ant-tabs-tab-btn\s*\{[\s\S]*?color:\s*var\(--ib-ink-secondary\)/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-first-screen-analytics"\]:has\(\.ant-tabs-tab\[data-node-key="priority"\]\.ant-tabs-tab-active\),[\s\S]*?\[data-testid="stock-analysis-first-screen-analytics"\]:has\(\.ant-tabs-tab\[data-node-key="optimization"\]\.ant-tabs-tab-active\)\s*\{[\s\S]*?max-height:\s*none[\s\S]*?overflow:\s*visible/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-first-screen-analytics"\]:has\(\.ant-tabs-tab\[data-node-key="priority"\]\.ant-tabs-tab-active\)\s*\.stock-analysis-page__analytics-tabs\s*\.ant-tabs-content-holder,[\s\S]*?\[data-testid="stock-analysis-first-screen-analytics"\]:has\(\.ant-tabs-tab\[data-node-key="optimization"\]\.ant-tabs-tab-active\)\s*\.stock-analysis-page__analytics-tabs\s*\.ant-tabs-content-holder\s*\{[\s\S]*?display:\s*block/,
    );
    expect(compactCss).toContain("First-screen analytics background-entry compact pass");
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-first-screen-analytics"\]:not\(:has\(\.ant-tabs-tab\[data-node-key="priority"\]\.ant-tabs-tab-active\)\):not\([\s\S]*?data-node-key="optimization"[\s\S]*?\)\s*\{[\s\S]*?min-height:\s*82px[\s\S]*?max-height:\s*92px[\s\S]*?padding:\s*7px 10px/,
    );
    expect(compactCss).toMatch(
      /\[data-testid="stock-analysis-first-screen-analytics"\]:not\(:has\(\.ant-tabs-tab\[data-node-key="priority"\]\.ant-tabs-tab-active\)\):not\([\s\S]*?data-node-key="optimization"[\s\S]*?\)\s*>\s*\.stock-analysis-page__dh-section-head\s*\{[\s\S]*?min-height:\s*24px[\s\S]*?border-bottom:\s*0/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__dh-section-eyebrow,[\s\S]*?\.stock-analysis-page__dh-pill\s*\{[\s\S]*?display:\s*none/,
    );
    expect(compactCss).not.toMatch(
      /\.stock-analysis-page__signal-pill\s*\{[\s\S]*?min-height:\s*20px[\s\S]*?font-size:\s*11px/,
    );
    expect(compactCss).toMatch(
      /@media\s*\(max-width:\s*720px\)\s*\{[\s\S]*?\[data-testid="stock-analysis-first-screen-analytics"\]:not\(:has\(\.ant-tabs-tab\[data-node-key="priority"\]\.ant-tabs-tab-active\)\):not\([\s\S]*?data-node-key="optimization"[\s\S]*?\)\s*\{[\s\S]*?min-height:\s*76px[\s\S]*?max-height:\s*86px/,
    );
  });

  it("keeps backend supply mini charts readable instead of squeezing canvas dimensions", () => {
    const css = readStockAnalysisCss();

    expect(css).not.toContain("grid-template-columns: repeat(auto-fit, minmax(150px, 1fr))");
    expect(css).not.toContain("grid-template-columns: repeat(auto-fit, minmax(160px, 1fr))");
    expect(css).not.toMatch(
      /\.stock-analysis-page__mini-chart\s*>\s*\.stock-analysis-page__echart,[\s\S]*?\.stock-analysis-page__mini-chart canvas\s*\{[\s\S]*?height:\s*100%/,
    );
    expect(css).not.toMatch(
      /\.stock-analysis-page__mini-chart\s*>\s*\.stock-analysis-page__echart\s*>\s*div\s*\{[\s\S]*?height:\s*100%/,
    );
  });

  it("removes section-head accent bars on desktop", () => {
    const css = readStockAnalysisCss();

    expect(css).toMatch(
      /\.stock-analysis-page__dh-section-head h2::before,[\s\S]*?display:\s*none/,
    );
    expect(css).toMatch(
      /\.stock-analysis-page__dh-section-head h2,[\s\S]*?color:\s*var\(--ib-ink\)/,
    );
  });

  it("keeps the stock dashboard aligned to a summary-first deep-review layout", () => {
    const css = readStockAnalysisCss();
    expect(css).toContain(".stock-analysis-page__workspace");
    expect(css).toContain(".stock-analysis-page__deep-zone");
    expect(css).toMatch(
      /\.stock-analysis-page__deep-review-workspace\s*\{[\s\S]*?grid-template-columns:\s*repeat\(12,\s*minmax\(0,\s*1fr\)\)/,
    );
    expect(css).toMatch(
      /\.stock-analysis-page__deep-review-workspace\s*\[data-testid="stock-analysis-sector-strength-panel"\]\s*\{[\s\S]*?grid-column:\s*1\s*\/\s*-1[\s\S]*?\[data-testid="stock-analysis-stock-selection"\]\.stock-analysis-page__deep-review-workspace\s*>\s*\[data-testid="stock-analysis-first-screen-analytics"\]\s*\{[\s\S]*?grid-column:\s*1\s*\/\s*-1/,
    );
    expect(css).toMatch(
      /\.stock-analysis-page__deep-review-workspace\s*\[data-testid="stock-analysis-consensus-first-screen"\],[\s\S]*?\.stock-analysis-page__deep-review-workspace\s*\[data-testid="stock-analysis-first-screen-analytics"\]\s*\{[\s\S]*?max-height:\s*none[\s\S]*?overflow:\s*visible/,
    );
    expect(css).toMatch(
      /\.stock-analysis-page__deep-review-workspace\s*\.stock-analysis-page__table-wrap,[\s\S]*?\.stock-analysis-page__deep-review-workspace\s*\.stock-analysis-page__sector-heavyweight-list\s*\{[\s\S]*?max-height:\s*320px[\s\S]*?overflow:\s*auto/,
    );
    expect(css).toMatch(
      /\.stock-analysis-page__deep-zone\s*\.stock-analysis-strategy-card-grid\s*\{[\s\S]*?grid-template-columns:\s*repeat\(4,\s*minmax\(0,\s*1fr\)\)/,
    );
  });

  it("keeps collapsed strategy research cards as compact entry points", () => {
    const css = readStockAnalysisCss();
    const page = readStockAnalysisPageSource();
    const compactStart = css.indexOf("Strategy research cards compact pass");
    const compactCss = css.slice(compactStart);

    expect(compactStart).toBeGreaterThan(-1);
    expect(page).toContain('data-testid="stock-analysis-strategy-research-more"');
    expect(page).toContain('className="stock-analysis-page__strategy-research-more-summary"');
    expect(page).toContain('data-testid="stock-analysis-strategy-card-grid"');
    expect(compactCss).toMatch(
      /\.stock-analysis-page__deep-zone\s*\.stock-analysis-strategy-card-grid\s*>\s*\.stock-analysis-strategy-module-card:not\(:has\(\.stock-analysis-strategy-module-card__detail:not\(\.stock-analysis-strategy-module-card__detail--collapsed\)\)\)\s*\{[\s\S]*?min-height:\s*82px[\s\S]*?max-height:\s*92px[\s\S]*?overflow:\s*hidden/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-strategy-module-card__subtitle,[\s\S]*?>\s*\.stock-analysis-strategy-module-card__kpi-grid\s*\{[\s\S]*?display:\s*none/,
    );
    expect(compactCss).not.toMatch(
      /\.stock-analysis-strategy-module-card__title\s*\{[\s\S]*?color:\s*var\(--ib-ink\)/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-strategy-module-card__headline\s*\{[\s\S]*?color:\s*var\(--ib-ink-secondary\)[\s\S]*?-webkit-line-clamp:\s*1/,
    );
    expect(compactCss).toContain("Strategy research disclosure pass");
    expect(compactCss).toMatch(
      /\.stock-analysis-page__strategy-research-more-summary\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)\s*auto[\s\S]*?min-height:\s*34px/,
    );
    expect(compactCss).toMatch(
      /\.stock-analysis-page__strategy-research-more:not\(\[open\]\)\s*>\s*\.stock-analysis-strategy-card-grid\s*\{[\s\S]*?display:\s*none/,
    );
    expect(compactCss).toMatch(
      /@media\s*\(max-width:\s*720px\)\s*\{[\s\S]*?\.stock-analysis-page__strategy-research-more-summary\s*\{[\s\S]*?min-height:\s*30px/,
    );
  });

  it("lets an expanded strategy panel span the full research grid", () => {
    const css = readStockAnalysisCss();

    expect(css).toMatch(
      /\.stock-analysis-strategy-card-grid\s*>\s*\.stock-analysis-strategy-module-card\[data-expanded="true"\]\s*\{[\s\S]*?grid-column:\s*1\s*\/\s*-1/,
    );
  });

  it("keeps the trust rail compact on desktop and full-width inside narrow single-column flow", () => {
    const css = readStockAnalysisCss();
    expect(css).toMatch(
      /\.stock-analysis-page__decision-rail\s*>\s*\.stock-analysis-page__ev-panel\s*\{[\s\S]*?display:\s*block[\s\S]*?grid-template-columns:\s*none/,
    );
    expect(css).toMatch(
      /\.stock-analysis-page__decision-rail\s*>\s*\.stock-analysis-page__ev-panel\s*>\s*section\s*\{[\s\S]*?display:\s*block[\s\S]*?border-top:\s*1px solid var\(--dh-api-line-soft\)/,
    );
    expect(css).toMatch(
      /@media\s*\(max-width:\s*1130px\)\s*\{[\s\S]*?\.stock-analysis-page__ev-panel\s*\[aria-label="首屏决策指标"\],[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/,
    );
    expect(css).toMatch(
      /@media\s*\(max-width:\s*719px\)\s*\{[\s\S]*?\.stock-analysis-page__ev-panel\s*\[aria-label="首屏决策指标"\],[\s\S]*?\.stock-analysis-page__ev-panel\s*\.stock-analysis-page__boundary-summary\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)/,
    );
    expect(css).not.toMatch(
      /@media\s*\(min-width:\s*1131px\)[\s\S]*?\.stock-analysis-page__decision-rail[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)\s*!important/,
    );
  });

  it("keeps the dark decision desk readable without fixed-height clipping", () => {
    const css = readStockAnalysisCss();
    const initialCss = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    expect(css).toMatch(
      /\.stock-analysis-page__deep-research[\s\S]*?\.stock-analysis-page__deep-review-workspace[\s\S]*?\.stock-analysis-page__kline-radar-decision\s*\{[^}]*display:\s*none/,
    );
    const closureCss = css.slice(css.lastIndexOf("Stock-analysis page closure"));
    expect(closureCss).toMatch(
      /@media\s*\(min-width:\s*721px\)[\s\S]*?\[data-testid="stock-analysis-theme-leaders-first-screen"\][\s\S]*?\.stock-analysis-page__theme-leaders-table\s*\{[^}]*min-width:\s*0\s*!important/,
    );
    expect(css).toMatch(
      /\.stock-analysis-page__deep-research-summary:focus-visible\s*\{[^}]*outline:\s*2px\s+solid\s+var\(--ib-accent\)/,
    );
    expect(css).not.toMatch(/__gate-ledger-/);
    const mobileClosureCss = initialCss.slice(initialCss.lastIndexOf("@media (max-width: 720px)"));
    expect(mobileClosureCss).toMatch(
      /\.stock-analysis-page__deep-research-summary > small\s*\{[^}]*display:\s*none/,
    );
    expect(mobileClosureCss).not.toMatch(
      /\.stock-analysis-page__deep-research-summary > span\s*\{[^}]*display:\s*none/,
    );
    expect(mobileClosureCss).not.toMatch(
      /\.stock-analysis-page__theme-leaders-table\s*\{[^}]*min-width:\s*0\s*!important/,
    );
  });

  it("keeps narrow screens single-column without clipping review or deep modules", () => {
    const css = readStockAnalysisCss();
    const mobileStart = css.indexOf("Mobile first-screen readability pass");
    const observationMobileStart = css.indexOf("Mobile observation ledger no-scroll pass");
    const mobileCss = css.slice(mobileStart);
    const observationMobileCss = css.slice(observationMobileStart);

    expect(mobileStart).toBeGreaterThan(-1);
    expect(observationMobileStart).toBeGreaterThan(-1);
    expect(mobileCss).not.toMatch(
      /@media \(max-width:\s*720px\)[\s\S]*?\.stock-analysis-page__dh-hero-status-strip\s*\{[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/,
    );
    expect(mobileCss).not.toMatch(
      /\.stock-analysis-page__dh-hero-status-strip span\s*\{[\s\S]*?white-space:\s*normal\s*!important/,
    );
    expect(mobileCss).not.toMatch(
      /\.stock-analysis-page__dh-details summary \.stock-analysis-page__dh-pill\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(mobileCss).not.toMatch(
      /\.stock-analysis-page__supply-kpi-row\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)/,
    );
    expect(mobileCss).not.toMatch(
      /\.stock-analysis-page__supply-kpi-card,[\s\S]*?\.stock-analysis-page__mini-chart\s*\{[\s\S]*?max-width:\s*100%/,
    );
    expect(observationMobileCss).not.toMatch(
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

  it("keeps deep research unmounted when the closed disclosure enters the viewport", async () => {
    const user = userEvent.setup();
    const observeNode = vi.fn();

    vi.stubGlobal(
      "IntersectionObserver",
      class IntersectingIntersectionObserver {
        constructor(private readonly callback: IntersectionObserverCallback) {}

        observe = (node: Element) => {
          observeNode(node);
          this.callback(
            [{ isIntersecting: true, target: node } as IntersectionObserverEntry],
            this as unknown as IntersectionObserver,
          );
        };
        unobserve = vi.fn();
        disconnect = vi.fn();
        takeRecords = () => [];
      },
    );

    renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });

    const deepResearch = await screen.findByTestId("stock-analysis-deep-research");
    expect(observeNode).not.toHaveBeenCalledWith(deepResearch);

    expect(
      within(deepResearch).queryByTestId("stock-analysis-deep-zone"),
    ).not.toBeInTheDocument();

    await user.click(
      within(deepResearch).getByTestId("stock-analysis-deep-research-summary"),
    );

    expect(
      await within(deepResearch).findByTestId("stock-analysis-deep-zone"),
    ).toBeVisible();
  });

  it("defers deep-research data shaping until the disclosure is requested", async () => {
    const user = userEvent.setup();
    const observeNode = vi.fn();
    const deepGateBuilder = vi.spyOn(stockAnalysisDeepResearchPanelsModel, "buildDeepAnalysisGateSummary");
    const deepAuditBuilder = vi.spyOn(stockAnalysisDeepResearchPanelsModel, "buildDeepZoneAuditRows");
    const klineRadarBuilder = vi.spyOn(
      stockAnalysisKlineRadarModel,
      "buildStockAnalysisKlineRadar",
    );
    const themeCardsBuilder = vi.spyOn(stockAnalysisDeepResearchPanelsModel, "buildThemeBreakoutCards");
    const themeLeadersBuilder = vi.spyOn(stockAnalysisDeepResearchPanelsModel, "buildThemeLeaderPreviewItems");
    const themeEvidenceBuilder = vi.spyOn(stockAnalysisDeepResearchPanelsModel, "buildThemeEvidenceStateRows");
    const themeReviewBuilder = vi.spyOn(stockAnalysisDeepResearchPanelsModel, "buildThemeBreakoutReviewItems");
    const themePanelBuilder = vi.spyOn(stockAnalysisDeepResearchPanelsModel, "buildThemeBreakoutPanelSummary");

    vi.stubGlobal(
      "IntersectionObserver",
      class IdleIntersectionObserver {
        observe = observeNode;
        unobserve = vi.fn();
        disconnect = vi.fn();
        takeRecords = () => [];
      },
    );

    try {
      renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });
      const deepResearch = await screen.findByTestId("stock-analysis-deep-research");
      expect(observeNode).not.toHaveBeenCalledWith(deepResearch);

      expect(deepGateBuilder).not.toHaveBeenCalled();
      expect(deepAuditBuilder).not.toHaveBeenCalled();
      expect(klineRadarBuilder).not.toHaveBeenCalled();
      expect(themeCardsBuilder).not.toHaveBeenCalled();
      expect(themeLeadersBuilder).not.toHaveBeenCalled();
      expect(themeEvidenceBuilder).not.toHaveBeenCalled();
      expect(themeReviewBuilder).not.toHaveBeenCalled();
      expect(themePanelBuilder).not.toHaveBeenCalled();

      await user.click(within(deepResearch).getByTestId("stock-analysis-deep-research-summary"));
      expect(await within(deepResearch).findByTestId("stock-analysis-deep-zone")).toBeVisible();
      expect(deepGateBuilder).toHaveBeenCalled();
      expect(deepAuditBuilder).toHaveBeenCalled();
      expect(klineRadarBuilder).toHaveBeenCalled();
      expect(themeCardsBuilder).toHaveBeenCalled();
      expect(themeLeadersBuilder).toHaveBeenCalled();
      expect(themeEvidenceBuilder).toHaveBeenCalled();
      expect(themeReviewBuilder).toHaveBeenCalled();
      expect(themePanelBuilder).toHaveBeenCalled();
    } finally {
      deepGateBuilder.mockRestore();
      deepAuditBuilder.mockRestore();
      klineRadarBuilder.mockRestore();
      themeCardsBuilder.mockRestore();
      themeLeadersBuilder.mockRestore();
      themeEvidenceBuilder.mockRestore();
      themeReviewBuilder.mockRestore();
      themePanelBuilder.mockRestore();
    }
  });

  // 「门禁速览」折叠层已并入密表，只剩排序明细一层折叠，断言随之改为排序明细。
  it("opens deep research before scrolling from a strategy review shortcut", async () => {
    const user = userEvent.setup();
    const originalScrollIntoView = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "scrollIntoView");
    const scrollIntoView = vi.fn();
    Object.defineProperty(HTMLElement.prototype, "scrollIntoView", {
      configurable: true,
      value: scrollIntoView,
    });

    try {
      renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });
      await openDeepResearch();

      const deepResearch = await screen.findByTestId("stock-analysis-deep-research");
      const moreStrategies = await screen.findByTestId("stock-analysis-strategy-lens-more-strategies");
      expect(deepResearch).toHaveAttribute("open");

      await user.click(within(moreStrategies).getByText("更多候选策略"));
      await user.click(screen.getByRole("button", { name: "前往多因子复核区" }));

      const target = await screen.findByTestId("stock-analysis-observation-preview");
      expect(deepResearch).toHaveAttribute("open");
      await waitFor(() => expect(scrollIntoView).toHaveBeenCalledWith({ behavior: "smooth", block: "start" }));
      expect(scrollIntoView.mock.instances.at(-1)).toBe(target);
    } finally {
      if (originalScrollIntoView) {
        Object.defineProperty(HTMLElement.prototype, "scrollIntoView", originalScrollIntoView);
      } else {
        Reflect.deleteProperty(HTMLElement.prototype, "scrollIntoView");
      }
    }
  });

  it("keeps the review queue ahead of the deep-research and evidence zones", async () => {
    renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });

    const reviewQueue = await screen.findByTestId("stock-analysis-review-queue");
    const evidenceDisclosure = await screen.findByTestId("stock-analysis-evidence-disclosure");
    const deepResearch = screen.getByTestId("stock-analysis-deep-research");

    expectElementBefore(reviewQueue, deepResearch);
    expectElementBefore(reviewQueue, evidenceDisclosure);
  });

  it("keeps secondary V6 and K-line audit evidence in closed disclosures", async () => {
    const user = userEvent.setup();
    renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });

    const evidenceDisclosure = await screen.findByTestId("stock-analysis-evidence-disclosure");
    expect(evidenceDisclosure.tagName).toBe("DETAILS");
    expect(evidenceDisclosure).not.toHaveAttribute("open");
    expect(within(evidenceDisclosure).getByTestId("stock-analysis-v6-endpoint-ledger-section")).toBeInTheDocument();
    expect(within(evidenceDisclosure).getByTestId("stock-analysis-v6-state-variants-section")).toBeInTheDocument();
    expect(within(evidenceDisclosure).getByTestId("stock-analysis-api-readiness-shell")).toBeInTheDocument();

    await openDeepResearch();

    const radar = await screen.findByTestId("stock-analysis-kline-radar");
    expect(within(radar).getByTestId("stock-analysis-kline-radar-decision")).toBeInTheDocument();
    expect(within(radar).getByTestId("stock-analysis-kline-radar-buckets")).toBeInTheDocument();
    expect(within(radar).getByTestId("stock-analysis-kline-radar-focus-table")).toBeInTheDocument();

    const radarDetails = within(radar).getByTestId("stock-analysis-kline-radar-details");
    expect(radarDetails.tagName).toBe("DETAILS");
    expect(radarDetails).not.toHaveAttribute("open");
    expect(within(radarDetails).getByTestId("stock-analysis-kline-radar-state-strip")).not.toBeVisible();
    expect(within(radarDetails).getByTestId("stock-analysis-kline-radar-state-strip")).toBeInTheDocument();
    expect(within(radarDetails).getByTestId("stock-analysis-kline-radar-explanation")).toBeInTheDocument();
    expect(within(radarDetails).getByTestId("stock-analysis-kline-radar-queue-breakout")).toBeInTheDocument();

    await user.click(within(radarDetails).getByText("完整队列、页面状态与来源拓扑"));
    expect(radarDetails).toHaveAttribute("open");
    expect(within(radarDetails).getByTestId("stock-analysis-kline-radar-state-strip")).toBeVisible();
    const moduleStates = within(radarDetails).getByTestId("stock-analysis-kline-radar-module-states");
    expect(moduleStates).toHaveTextContent("后端 module_states 1:1 映射");
    expect(moduleStates).toHaveTextContent("已登记 10 项");
    expect(moduleStates.querySelectorAll("[data-module-state-key]")).toHaveLength(10);
    expect(
      within(moduleStates).getByTestId(
        "stock-analysis-kline-radar-module-state-uptrend_momentum_candidates",
      ),
    ).toHaveTextContent("上行动量");
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

    const compactChrome = await screen.findByTestId("stock-analysis-page-compact-chrome");
    const toolbar = compactChrome.querySelector(".stock-analysis-page__compact-chrome-meta");

    await waitFor(() => expect(toolbar).not.toHaveTextContent("默认"));

    expect(toolbar).toHaveTextContent("日期待补");
    expect(toolbar).not.toHaveTextContent("2026-05-08");
  });

  it("renders first-screen theme leaders and analytics tabs", async () => {
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
    await openDeepResearch();

    const themeLeaders = await screen.findByTestId("stock-analysis-theme-leaders-first-screen");
    expect(themeLeaders).toHaveTextContent("题材突破领涨股");
    expect(screen.getByTestId("theme-leader-first-row-688001.SH")).toHaveTextContent("Alpha Semiconductor");

    await openDeepResearch();
    const sectorHeavyweights = await screen.findByTestId("stock-analysis-sector-heavyweights-first-screen");
    expect(sectorHeavyweights).toHaveTextContent("权重股摘要");
    expect(screen.getByTestId("sector-heavyweight-row-801001-688001.SH")).toHaveTextContent("Alpha Semiconductor");

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
    await openDeepResearch();

    await screen.findByTestId("stock-analysis-first-screen-analytics");
    expect(strategyScoreSpy).not.toHaveBeenCalled();

    await user.click(screen.getByRole("tab", { name: "策略优先级" }));
    await waitFor(() => {
      expect(strategyScoreSpy).toHaveBeenCalled();
    });
    expect(strategyOptimizationSpy).not.toHaveBeenCalled();
    expect(candidateHistorySpy).not.toHaveBeenCalled();
  });

  it("loads strategy diagnostics when first-screen analytics optimization tab is opened", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    const strategyScoreSpy = vi.spyOn(client, "getLivermoreStrategyScore");
    const strategyOptimizationSpy = vi.spyOn(client, "getLivermoreStrategyOptimization");
    const candidateHistorySpy = vi.spyOn(client, "getLivermoreCandidateHistory");

    renderWorkbenchApp(["/stock-analysis"], { client });
    await openDeepResearch();

    await screen.findByTestId("stock-analysis-first-screen-analytics");
    expect(strategyOptimizationSpy).not.toHaveBeenCalled();

    await user.click(screen.getByRole("tab", { name: "优化诊断" }));
    await waitFor(() => {
      expect(strategyOptimizationSpy).toHaveBeenCalled();
    });
    expect(strategyScoreSpy).not.toHaveBeenCalled();
    expect(candidateHistorySpy).not.toHaveBeenCalled();
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

    await openStrategyModuleDetail("cycle-rotation");
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
    const cycleProxyBacktest = within(framework).getByTestId("stock-analysis-cycle-proxy-backtest");
    expect(cycleProxyBacktest).toBeInTheDocument();
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
    await waitFor(() =>
      expect(cycleProxyBacktest).toHaveTextContent(
        "入场口径：优先字段 return_5d_net_adj（次日开盘净收益）；可执行入场覆盖 433/546（79%）。回退构成：return_5d_adj 23 行；return_5d 90 行。阻断剔除 40 行；公式版本 fv_livermore_cycle_proxy_backtest_execution_first_v4。",
      ),
    );
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

  it("renders the caliber disclosure sourced from the cycle-proxy and portfolio-proxy backtest payloads", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          cycle_rotation_framework: buildCycleRotationFramework(),
        }),
        cycleProxyBacktest: {
          status: "proxy",
          full_strategy_status: "blocked_missing_inputs",
          formula_version: "fv_livermore_cycle_proxy_backtest_execution_first_v4",
          proxy_signal_kind: "stock_candidate",
          proxy_rule: "Equal-weight non-overlapping T+5 baskets of completed stock_candidate rows.",
          execution_blocked_rows_in_window: 40,
          snapshot_from: "2024-09-24",
          snapshot_to: "2026-03-02",
          missing_full_strategy_inputs: ["PMI", "credit_impulse"],
          warnings: ["Executable next-open return_5d_net_adj is preferred; close-return fallbacks remain disclosed."],
          summary: {
            sample_days: 225,
            candidate_rows: 546,
            return_field_used: "return_5d_net_adj",
            return_field_fallback: "return_5d_adj",
            return_field_second_fallback: "return_5d",
            execution_return_costs_already_applied: true,
            return_rows_execution_net_adjusted: 433,
            return_rows_adjusted: 23,
            return_rows_adjusted_fallback: 23,
            return_rows_gross_fallback: 90,
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
          caliber_disclosure: {
            entry_price_warning: "旧代际样本入场价为近似值，非真实成交价。",
            return_field_stats: {
              return_rows_execution_net_adjusted: 433,
              return_rows_adjusted: 23,
              return_rows_adjusted_fallback: 23,
              return_rows_gross_fallback: 90,
            },
            sample_generation: { tushare_era_rows: 0, native_era_rows: 546 },
            basis_notes: ["旧代际样本入场价为近似值，非真实成交价。", "新源按 T+1 开盘价计算。"],
          },
        },
        candidateHistoryPortfolioBacktest: {
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
          caliber_disclosure: {
            entry_price_warning: null,
            return_field_stats: {
              price_rows_adjusted: 48,
              price_rows_raw_fallback: 4,
            },
            sample_generation: { tushare_era_rows: 0, native_era_rows: 52 },
            basis_notes: ["组合回测样本按月度再平衡快照聚合。"],
          },
        },
      }),
    });

    await openStrategyModuleDetail("cycle-rotation");
    const framework = await screen.findByTestId("stock-analysis-cycle-rotation-framework");
    const cycleProxyBacktest = within(framework).getByTestId("stock-analysis-cycle-proxy-backtest");
    const portfolioBacktest = within(framework).getByTestId("stock-analysis-candidate-history-portfolio-backtest");

    await waitFor(() =>
      expect(
        within(cycleProxyBacktest).getByTestId("stock-analysis-strategy-backtest-caliber-warning"),
      ).toHaveTextContent("旧代际样本入场价为近似值，非真实成交价。"),
    );
    expect(
      within(cycleProxyBacktest).getByTestId("stock-analysis-strategy-backtest-caliber-sample"),
    ).toHaveTextContent("样本构成：旧源 0 笔 / 新源 546 笔");
    expect(
      within(cycleProxyBacktest).getByTestId("stock-analysis-strategy-backtest-caliber-notes"),
    ).toHaveTextContent("新源按 T+1 开盘价计算。");

    await waitFor(() =>
      expect(
        within(portfolioBacktest).getByTestId("stock-analysis-strategy-backtest-caliber-sample"),
      ).toHaveTextContent("样本构成：旧源 0 笔 / 新源 52 笔"),
    );
    expect(
      within(portfolioBacktest).queryByTestId("stock-analysis-strategy-backtest-caliber-warning"),
    ).not.toBeInTheDocument();
    expect(
      within(portfolioBacktest).getByTestId("stock-analysis-strategy-backtest-caliber-notes"),
    ).toHaveTextContent("组合回测样本按月度再平衡快照聚合。");
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

    await openStrategyModuleDetail("cycle-rotation");
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

    await openStrategyModuleDetail("cycle-rotation");
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

    await openStrategyModuleDetail("cycle-rotation");
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

    await openStrategyModuleDetail("cycle-rotation");
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

    await openStrategyModuleDetail("cycle-rotation");
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

    await openStrategyModuleDetail("cycle-rotation");
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

    await openStrategyModuleDetail("cycle-rotation");
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

    await openStrategyModuleDetail("theme-breakout");
    const section = await screen.findByTestId("stock-analysis-theme-breakout");
    expect(
      within(section).getByTestId("stock-analysis-theme-group-semiconductor_proxy"),
    ).toBeInTheDocument();
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

  it("mounts the walk-forward report inside cycle diagnostics", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      if (String(input) !== "/api/strategy-reports/walk-forward") {
        return buildJsonResponse({}, 404);
      }
      return buildJsonResponse({
        result: {
          generated_at: "2026-08-24T12:00:00+08:00",
          schedules: [
            {
              label: "primary_6t_2v_2s",
              train_months: 6,
              valid_months: 2,
              step_months: 2,
              window_count: 4,
              min_windows_for_verdict: 3,
              strategies: [
                {
                  strategy: "factor_screen",
                  verdict: "oos_supported",
                  in_sample_excess: 0.12,
                  oos_excess_median: 0.04,
                  excess_sign_consistency: {
                    positive_windows: 3,
                    observed_windows: 4,
                    positive_ratio: 0.75,
                  },
                },
              ],
            },
          ],
        },
      });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          cycle_rotation_framework: buildCycleRotationFramework(),
        }),
      }),
    });
    const detail = await openStrategyModuleDetail("cycle-rotation");
    const panel = await within(detail).findByTestId("stock-analysis-walk-forward");

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/strategy-reports/walk-forward",
      expect.objectContaining({ headers: { Accept: "application/json" } }),
    );
    expect(panel).toHaveTextContent("样本外验证");
    expect(panel).toHaveTextContent("多因子");
    expect(panel).toHaveTextContent("样本外支持");
    expect(panel).toHaveTextContent("报告 2026-08-24");
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
    await openDeepResearch();

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
    await openDeepResearch();

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
    await openDeepResearch();

    const preview = await screen.findByTestId("stock-analysis-observation-preview");
    expect(preview).toHaveTextContent("因子快照无数据");
    expect(preview).not.toHaveTextContent("factor_snapshot");
  });

  it("does not inject an evidence-only hybrid candidate that the backend omitted from the authoritative queue", async () => {
    const strategy = buildStrategyPayload({
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
          module_states: readyModuleStates().map((state) =>
            state.key === "hybrid_fusion"
              ? {
                  ...state,
                  state: "blocked",
                  render_mode: "evidence_only",
                  evidence_scope: "detail",
                  excludes_from_primary: true,
                }
              : state,
          ),
        });
    const workbench = buildStockAnalysisWorkbenchPayload(strategy);
    workbench.first_screen.review_queue = workbench.first_screen.review_queue.filter(
      (row) => row.source_module !== "hybrid_fusion_candidates",
    );
    workbench.decision_summary = {
      ...workbench.decision_summary,
      review_queue_count: workbench.first_screen.review_queue.length,
    };
    const client = stockClient({ strategy });
    vi.spyOn(client, "getStockAnalysisWorkbench").mockResolvedValue(
      buildMockApiEnvelope("market_data.stock_analysis.workbench", workbench),
    );

    renderWorkbenchApp(["/stock-analysis"], {
      client,
    });

    const queue = await screen.findByTestId("stock-analysis-review-queue");
    const queueText = queue.textContent ?? "";
    expect(queueText).not.toContain("Fusion Alpha");
    expect(queueText.indexOf("000001.SZ")).toBeGreaterThanOrEqual(0);
    expect(queueText.indexOf("000001.SZ")).toBeLessThan(queueText.indexOf("000002.SZ"));
    expect(queue).toHaveTextContent("2 / 2");
  });

  it("does not cross-enrich an authoritative factor row from a same-code hybrid candidate", async () => {
    const strategy = buildStrategyPayload({
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
        coverage_note: "Different-source evidence must not enrich the factor queue row.",
        items: [
          {
            rank: 1,
            stock_code: "000001.SZ",
            stock_name: "Alpha",
            sector_code: "801001",
            sector_name: "AI",
            fusion_score: 0.812345,
            cycle_score: 0.7,
            lifecourt_proxy_score: 0.6,
            attention_score: 0.55,
            price_confirm_score: 0.8,
            crowding_penalty: 0.1,
            confidence: "medium",
            reason: "Hybrid evidence only for this authoritative factor row.",
            evidence: { source_kinds: ["factor_screen"] },
          },
        ],
      },
    });
    const workbench = buildStockAnalysisWorkbenchPayload(strategy);
    workbench.first_screen.review_queue = [
      {
        rank: 1,
        stock_code: "000001.SZ",
        stock_name: "Alpha",
        sector_code: "801001",
        sector_name: "AI",
        source_module: "factor_screen_candidates",
        factor_score: 0.91,
      },
    ];
    workbench.decision_summary.review_queue_count = 1;
    workbench.decision_summary.top_review_stock_code = "000001.SZ";
    workbench.decision_summary.top_review_stock_name = "Alpha";
    const client = stockClient({ strategy });
    vi.spyOn(client, "getStockAnalysisWorkbench").mockResolvedValue(
      buildMockApiEnvelope("market_data.stock_analysis.workbench", workbench),
    );

    renderWorkbenchApp(["/stock-analysis"], { client });

    const queue = await screen.findByTestId("stock-analysis-review-queue");
    expect(queue).toHaveTextContent("Alpha");
    expect(queue).toHaveTextContent("多因子");
    expect(queue).toHaveTextContent("0.910");
    expect(queue).not.toHaveTextContent("0.812");
    expect(queue).not.toHaveTextContent("融合分");
    expect(queue).not.toHaveTextContent("factor_screen_candidates");
  });

  it("keeps optional data gaps visible as supplemental warnings when review is allowed", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          data_gaps: [
            {
              input_family: "PMI",
              status: "missing",
              evidence: "Optional macro component is not landed.",
            },
            {
              input_family: "credit_impulse",
              status: "missing",
              evidence: "Optional credit component is not landed.",
            },
            {
              input_family: "macro_score",
              status: "partial",
              evidence: "Macro evidence is partial.",
            },
          ],
        }),
      }),
    });

    await openEvidenceDisclosure();
    expect(await screen.findByTestId("stock-analysis-workbench-contract")).toHaveTextContent("可复核");
    const gapReleasePanel = await screen.findByRole("region", { name: "数据缺口与补证条件" });
    expect(gapReleasePanel).toHaveAttribute("aria-label", "数据缺口与补证条件");
    expect(gapReleasePanel).toHaveTextContent("数据缺口与补证条件");
    expect(gapReleasePanel).not.toHaveTextContent("阻断项与释放条件");
    expect(gapReleasePanel).toHaveTextContent("明确缺口影响，以及补齐证据后的复核边界");
    expect(within(gapReleasePanel).getAllByText("缺数据，补证警告")).toHaveLength(2);
    expect(gapReleasePanel).toHaveTextContent("部分，补证警告");
    expect(gapReleasePanel).not.toHaveTextContent("阻断复核释放");
    expect(gapReleasePanel.querySelectorAll('[data-tone="negative"]')).toHaveLength(0);
    expect(gapReleasePanel.querySelectorAll('[data-tone="warning"]')).toHaveLength(2);
    expect(gapReleasePanel.querySelectorAll('[data-tone="neutral"]')).toHaveLength(1);
  });

  it("does not mislabel an unrelated partial gap as a theme-taxonomy warning", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          data_gaps: [
            {
              input_family: "PMI",
              status: "partial",
              evidence: "PMI evidence is partial.",
            },
          ],
        }),
      }),
    });

    await openEvidenceDisclosure();
    const endpointLedger = await screen.findByTestId("stock-analysis-v6-endpoint-ledger-section");
    const dataCatalogCard = within(endpointLedger).getByText("数据目录").closest("article");

    expect(dataCatalogCard).toHaveTextContent("目录状态随主包返回");
    expect(dataCatalogCard).not.toHaveTextContent("theme_taxonomy");
    expect(dataCatalogCard).not.toHaveTextContent("题材分类部分覆盖");
  });

  it("shows theme-taxonomy partial as limited non-blocking evidence", async () => {
    const strategy = buildStrategyPayload({
      data_gaps: [
        {
          input_family: "theme_taxonomy",
          status: "partial",
          evidence: "Current overlay is non-point-in-time.",
        },
      ],
    });
    const workbench = buildStockAnalysisWorkbenchPayload(strategy);
    workbench.page_question = {
      ...workbench.page_question,
      answer_state: "limited_review",
      answer_label: "limited_review",
    };
    workbench.decision_summary = {
      ...workbench.decision_summary,
      can_review_candidates: true,
      primary_blocker: null,
    };
    const client: ApiClient = {
      ...stockClient({ strategy }),
      getStockAnalysisWorkbench: vi.fn(async () =>
        buildMockApiEnvelope("market_data.stock_analysis.workbench", workbench, {
          basis: "analytical",
          formal_use_allowed: false,
        }),
      ),
    };

    renderWorkbenchApp(["/stock-analysis"], { client });

    await openEvidenceDisclosure();
    const contract = await screen.findByTestId("stock-analysis-workbench-contract");
    expect(contract).toHaveTextContent("有限复核");
    expect(contract).toHaveTextContent("仅供观察");
    const endpointLedger = await screen.findByTestId("stock-analysis-v6-endpoint-ledger-section");
    const dataCatalogCard = within(endpointLedger).getByText("数据目录").closest("article");
    expect(dataCatalogCard).toHaveTextContent("题材分类部分覆盖");
    expect(dataCatalogCard).toHaveTextContent("不阻断只读复核");
  });

  it("prioritizes a later blocking gap without marking optional gaps as blockers", async () => {
    const strategy = buildStrategyPayload({
      data_gaps: [
        {
          input_family: "PMI",
          status: "missing",
          evidence: "Optional macro component is not landed.",
        },
        {
          input_family: "credit_impulse",
          status: "missing",
          evidence: "Optional credit component is not landed.",
        },
        {
          input_family: "position_risk",
          status: "missing",
          evidence: "No ACTIVE A-share position snapshot is available.",
        },
      ],
    });
    const workbench = buildStockAnalysisWorkbenchPayload(strategy);
    workbench.first_screen.data_gaps = [
      { ...strategy.data_gaps[0], blocks_review: false },
      { ...strategy.data_gaps[1], blocks_review: false },
      { ...strategy.data_gaps[2], blocks_review: true },
    ];
    workbench.page_question = {
      ...workbench.page_question,
      answer_state: "blocked",
      answer_label: "blocked",
      reason: "Risk exit requires an ACTIVE A-share position snapshot.",
    };
    workbench.decision_summary = {
      ...workbench.decision_summary,
      can_review_candidates: false,
      primary_blocker: "Risk exit requires an ACTIVE A-share position snapshot.",
    };
    const client: ApiClient = {
      ...stockClient({ strategy }),
      getStockAnalysisWorkbench: vi.fn(async () =>
        buildMockApiEnvelope("market_data.stock_analysis.workbench", workbench, {
          basis: "analytical",
          formal_use_allowed: false,
        }),
      ),
    };

    renderWorkbenchApp(["/stock-analysis"], { client });

    const gapReleasePanel = await screen.findByRole("region", { name: "数据缺口与补证条件" });
    const gapCards = gapReleasePanel.querySelectorAll(".stock-analysis-page__v6-gap-release-card");
    expect(gapCards).toHaveLength(3);
    expect(gapCards[0]).toHaveTextContent("持仓风险");
    expect(gapCards[0]).toHaveTextContent("缺数据，阻断复核释放");
    expect(gapCards[0]).toHaveAttribute("data-tone", "negative");
    expect(gapReleasePanel.querySelectorAll('[data-tone="negative"]')).toHaveLength(1);
    expect(within(gapReleasePanel).getAllByText("缺数据，补证警告")).toHaveLength(2);
    expect(gapReleasePanel).toHaveTextContent("PMI");
    expect(gapReleasePanel).toHaveTextContent("信用脉冲");
  });

  it("keeps mixed workbench gaps fail-closed when a required row omits blocks_review", async () => {
    const strategy = buildStrategyPayload({
      data_gaps: [
        {
          input_family: "PMI",
          status: "missing",
          evidence: "Optional macro component is not landed.",
        },
        {
          input_family: "position_risk",
          status: "missing",
          evidence: "No ACTIVE A-share position snapshot is available.",
        },
      ],
    });
    const workbench = buildStockAnalysisWorkbenchPayload(strategy);
    workbench.first_screen.data_gaps = [
      {
        input_family: "PMI",
        status: "missing",
        evidence: "Optional macro component is not landed.",
        blocks_review: false,
      },
      {
        input_family: "position_risk",
        status: "missing",
        evidence: "No ACTIVE A-share position snapshot is available.",
      },
    ] as unknown as StockAnalysisWorkbenchPayload["first_screen"]["data_gaps"];
    workbench.page_question = {
      ...workbench.page_question,
      answer_state: "blocked",
      answer_label: "blocked",
      reason: "Risk exit requires an ACTIVE A-share position snapshot.",
    };
    workbench.decision_summary = {
      ...workbench.decision_summary,
      can_review_candidates: false,
      primary_blocker: "Risk exit requires an ACTIVE A-share position snapshot.",
    };
    const client: ApiClient = {
      ...stockClient({ strategy }),
      getStockAnalysisWorkbench: vi.fn(async () =>
        buildMockApiEnvelope("market_data.stock_analysis.workbench", workbench, {
          basis: "analytical",
          formal_use_allowed: false,
        }),
      ),
    };

    renderWorkbenchApp(["/stock-analysis"], { client });

    const gapReleasePanel = await screen.findByRole("region", { name: "数据缺口与补证条件" });
    const gapCards = gapReleasePanel.querySelectorAll(".stock-analysis-page__v6-gap-release-card");
    expect(gapCards).toHaveLength(2);
    expect(gapCards[0]).toHaveTextContent("持仓风险");
    expect(gapCards[0]).toHaveTextContent("缺数据，阻断复核释放");
    expect(gapCards[0]).toHaveAttribute("data-tone", "negative");
    expect(gapCards[1]).toHaveTextContent("PMI");
    expect(gapCards[1]).toHaveTextContent("缺数据，补证警告");
  });

  it("renders closed-loop summary pass states on the first decision surface", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        replayClosure: buildStockAnalysisReplayClosure(),
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
    await openDeepResearch();

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
    expect(summary).toHaveTextContent("当前规则回放已认证");
    expect(screen.getByTestId("stock-analysis-rail-check-matrix")).toBeInTheDocument();
    expect(summary).not.toHaveTextContent("完成日：20/20");
    await userEvent.click(within(screen.getByTestId("stock-analysis-replay-status")).getByText("明细"));
    expect(summary).toHaveTextContent("完成日：20/20");
    expect(summary).toHaveTextContent("批次：cohort-current-rule-20260429");
    expect(summary).toHaveTextContent("血缘状态");
    expect(summary).toHaveTextContent("完整");
  });

  it("renders current-rule replay counts and proxy-only boundaries without implying efficacy", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        replayClosure: buildStockAnalysisReplayClosure({
          data_availability: "fallback",
          status: "blocked",
          certified_start_date: "2026-04-30",
          certified_end_date: "2026-05-08",
          counts: {
            completed_dates: 1,
            pending_tail_dates: 1,
            blocking_pending_dates: 1,
            unsupported_dates: 1,
            proxy_only_dates: 1,
            matched_entry_count: 0,
            t5_usable_count: 0,
            t20_usable_count: 0,
          },
          primary_blocker_code: "current_rule_cohort_not_ready",
          reason_codes: ["blocking_pending_dates", "unsupported_dates", "proxy_only_dates"],
        }),
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
    await openEvidenceDisclosure();

    const replayStatus = await screen.findByTestId("stock-analysis-replay-status");
    await waitFor(() => expect(replayStatus).toHaveTextContent("明细"), {
      timeout: 3_000,
    });
    expect(replayStatus).not.toHaveTextContent("2026-04-30");
    await userEvent.click(within(replayStatus).getByText("明细"));
    expect(replayStatus).toHaveTextContent("认证范围：2026-04-30 至 2026-05-08");
    expect(replayStatus).toHaveTextContent("决策口径：次日开盘、含费、复权净收益");
    expect(replayStatus).toHaveTextContent("完成日：1/20");
    expect(replayStatus).toHaveTextContent("待成熟尾部：1 日");
    expect(replayStatus).toHaveTextContent("阻断待处理：1 日");
    expect(replayStatus).toHaveTextContent("不支持：1 日");
    expect(replayStatus).toHaveTextContent("仅代理：1 日");
    expect(replayStatus).toHaveTextContent("存在阻断待处理日期");
    expect(replayStatus).toHaveTextContent("存在不支持日期");
    expect(replayStatus).toHaveTextContent("存在仅代理证据日期");
    expect(replayStatus).toHaveTextContent("仅作观察，不推导策略有效性");
    expect(replayStatus).not.toHaveTextContent("proxy_theme_only");
    expect(replayStatus).not.toHaveTextContent("do not infer strategy efficacy");
    expect(replayStatus).not.toHaveTextContent("unsupported dates");
    expect(replayStatus).not.toHaveTextContent("proxy-only dates");
  });

  it("renders refresh control and exposes as-of picker", async () => {
    renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });

    expect(await screen.findByTestId("stock-analysis-refresh")).toHaveTextContent("重选标的");
    expect(screen.getByTestId("stock-analysis-as-of-picker")).toBeInTheDocument();
  });

  it("refreshes the resolved trading date after a requested date falls back", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    const strategySpy = mockStrategyLatestSnapshotFallback(client);
    const choiceRefreshSpy = vi.spyOn(client, "refreshChoiceStock");

    renderWorkbenchApp(["/stock-analysis"], { client });

    await requestStockAnalysisAsOfDate(user, strategySpy, "2026-05-08", "2026-04-29");
    await user.click(screen.getByTestId("stock-analysis-refresh"));

    await waitFor(() =>
      expect(choiceRefreshSpy).toHaveBeenCalledWith(
        expect.objectContaining({ asOfDate: "2026-04-29" }),
      ),
    );
    expect(choiceRefreshSpy).not.toHaveBeenCalledWith(
      expect.objectContaining({ asOfDate: "2026-05-08" }),
    );
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

    await openStrategyModuleDetail("events-monitoring");
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

    await openStrategyModuleDetail("events-monitoring");
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

    await openStrategyModuleDetail("events-monitoring");
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
    await openDeepResearch();

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

    expect(await screen.findByTestId("stock-analysis-page-compact-chrome")).toHaveTextContent("股票研究");

    const page = await screen.findByTestId("stock-analysis-page");
    const pageSource = readFileSync(STOCK_ANALYSIS_PAGE_IMPL_PATH, "utf8");

    expect(pageSource).not.toContain("<StockAnalysisPretradeChecklist");
    expect(pageSource).not.toContain("positionSizeHint={buildCandidatePositionSizeHintNotice");
    expect(pageSource).not.toContain("strategyPayload?.stock_candidates?.position_size_hint");

    await waitFor(() => {
      expect(page).not.toHaveTextContent(/买入建议/);
      expect(page).not.toHaveTextContent(/卖出建议/);
      expect(page).not.toHaveTextContent(/下单/);
      expect(page).not.toHaveTextContent(/调仓指令/);
      expect(page).not.toHaveTextContent(/可买/);
      expect(page).not.toHaveTextContent(/建议仓位/);
      expect(page).not.toHaveTextContent(/等权仓位/);
      expect(page).not.toHaveTextContent(/实盘/);
    });

    const evidenceDisclosure = await openEvidenceDisclosure();
    expect(evidenceDisclosure).toHaveTextContent("规则版本已返回");
    expect(evidenceDisclosure).not.toHaveTextContent("已签核");
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
    await openDeepResearch();

    expect(await screen.findByRole("heading", { name: "风险退出观察" })).toBeInTheDocument();
    expect(await screen.findByText("联动观察暂不可用。")).toBeInTheDocument();
  });

  it("preserves supported risk counts in the first-screen queue headline", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({ data_gaps: [] }),
      }),
    });

    await openEvidenceDisclosure();
    const evidenceLedger = await screen.findByTestId("stock-analysis-evidence-ledger");
    expect(evidenceLedger).toHaveTextContent("风险");
    expect(evidenceLedger).toHaveTextContent("触发");
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
    expect(section).toHaveTextContent("风险退出不可用");
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
    expect(section).toHaveTextContent("风险退出不可用");
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
    expect(riskSection).toHaveTextContent("风险退出不可用");
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
    await openDeepResearch();

    expect(await screen.findByTestId("stock-analysis-sector-bars")).toBeInTheDocument();
    expect(screen.getByRole("tablist", { name: "首屏分析视图" })).toBeInTheDocument();
    expect(screen.getByRole("tablist", { name: "板块排行视图" })).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();
    expect(screen.getByTestId("stock-analysis-sector-strength-panel")).not.toHaveTextContent("avg_pctchange");
    expect(screen.getByTestId("stock-analysis-sector-strength-panel")).not.toHaveTextContent("unsupported_notes");

    await user.click(screen.getByRole("button", { name: /多日强弱/ }));

    expect(await screen.findByRole("tablist", { name: "板块序列周期" })).toBeInTheDocument();

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

  it("does not use the requested date for sector rank series when a requested date falls back", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    const strategySpy = mockStrategyLatestSnapshotFallback(client);
    const seriesSpy = vi.spyOn(client, "getLivermoreSectorRankSeries");

    renderWorkbenchApp(["/stock-analysis"], { client });
    await requestStockAnalysisAsOfDate(user, strategySpy);
    await openDeepResearch();
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
          rule_version: "rv_stock_analysis_workbench_v2",
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
    await requestStockAnalysisAsOfDate(user, strategySpy, "2026-05-08", "日期待补");
    expect(screen.queryByText("多日强弱")).not.toBeInTheDocument();
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
    await openDeepResearch();

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
    await openDeepResearch();
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
    await openDeepResearch();
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
    await openDeepResearch();
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

  it("renders strategy replay rows from legacy per-strategy horizon stats", async () => {
    renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });

    await openStrategyModuleDetail("strategy-backtest");
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

    await openStrategyModuleDetail("strategy-backtest");
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

    await openStrategyModuleDetail("market-priority");
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

  it("labels current market strategy priority with the selected T+10 horizon", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategyScore: buildStrategyScorePayload({
          primary_horizon: "return_10d",
          rows: buildStrategyScorePayload().rows.map((row) => ({
            ...row,
            reason: "T+10 sample 20, avg return pending, priority review ranking.",
          })),
          current_market_state_rows: buildStrategyScorePayload().current_market_state_rows.map((row) => ({
            ...row,
            reason: "T+10 sample 20, avg return pending, priority review ranking.",
          })),
        }),
      }),
    });
    await openDeepResearch();

    const summary = await screen.findByTestId("stock-analysis-market-priority-summary");

    await waitFor(() => expect(summary).toHaveTextContent("T+10"), { timeout: 3_000 });
    expect(summary).toHaveTextContent("T+10 排序");
    expect(summary).not.toHaveTextContent("T+5 排序");
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

    await openStrategyModuleDetail("market-priority");
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

    await openStrategyModuleDetail("market-priority");
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

    await openStrategyModuleDetail("market-priority");
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

    await openStrategyModuleDetail("market-priority");
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

    await openStrategyModuleDetail("market-priority");
    const row = await screen.findByTestId("stock-analysis-market-priority-row-OVERHEAT-factor_screen");
    expect(row).toHaveTextContent("排序范围待确认");
    expect(row).not.toHaveTextContent("sourceTableScopeLabel");

    const maturity = await screen.findByTestId("stock-analysis-candidate-maturity");
    expect(maturity).toHaveTextContent("排序范围待确认");
    expect(maturity).not.toHaveTextContent("sourceTableScopeLabel");
  });

  it("localizes strategy priority source-table failures without exposing backend tables", async () => {
    const user = userEvent.setup();
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategyScoreError: new Error(
          "Failed to fetch priority from /ui/market-data/livermore/strategy-score because source_table choice_stock_strategy_score is missing.",
        ),
      }),
    });
    await openDeepResearch();

    const section = await screen.findByTestId("stock-analysis-market-priority-summary");
    await waitFor(() => expect(section).toHaveTextContent("暂不可用"), { timeout: 3_000 });
    expect(section).not.toHaveTextContent("Failed to fetch");
    expect(section).not.toHaveTextContent("source_table");
    expect(section).not.toHaveTextContent("choice_stock_strategy_score");
    expect(section).not.toHaveTextContent("/ui/market-data/livermore/strategy-score");
    await user.click(within(section).getByTestId("stock-analysis-strategy-card-market-priority-toggle"));
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
    await openDeepResearch();

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

    await openStrategyModuleDetail("strategy-optimization");
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

  it("keeps a null optimization result distinct from a zero-sample payload", async () => {
    const user = userEvent.setup();
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({ strategyOptimizationResultNull: true }),
    });
    await openDeepResearch();

    const card = await screen.findByTestId("stock-analysis-strategy-optimization");
    await waitFor(() => expect(card).toHaveTextContent("接口未提供"), { timeout: 3_000 });
    expect(card).not.toHaveTextContent("0 组");
    expect(card).not.toHaveTextContent("阈值 30");
    expect(card).not.toHaveTextContent("优化诊断样本不足");
    expect(card).not.toHaveTextContent("切片样本不足");

    await user.click(screen.getByRole("tab", { name: "优化诊断" }));
    const firstScreen = await screen.findByTestId("stock-analysis-optimization-empty");
    expect(firstScreen).toHaveTextContent("接口未提供");
    expect(firstScreen).not.toHaveTextContent("0");
  });

  it("keeps optimization labels aligned with the configured primary horizon", async () => {
    const basePayload = buildStrategyOptimizationPayload();
    const return10Stats = {
      available_count: 20,
      missing_count: 0,
      positive_count: 12,
      non_positive_count: 8,
      avg_return: 0.031,
      win_rate: 0.6,
    };
    const return10DateWeighted = {
      available_day_count: 4,
      candidate_row_count: 20,
      avg_return: 0.024,
      positive_day_rate: 0.75,
      worst_day_return: -0.01,
      best_day_return: 0.05,
    };
    const payload: LivermoreStrategyOptimizationPayload = {
      ...basePayload,
      primary_horizon: "return_10d",
      strategy_summaries: basePayload.strategy_summaries.map((row) => ({
        ...row,
        stats: { ...row.stats, return_10d: return10Stats },
        date_weighted_stats: { ...row.date_weighted_stats, return_10d: return10DateWeighted },
        recommendation: {
          ...row.recommendation,
          reason: "T+10 样本 20，均值 +3.10%，胜率 60.0%，只读复核排序。",
          primary_horizon: "return_10d",
          available_count: 20,
          avg_return: 0.031,
          win_rate: 0.6,
        },
      })),
      slices: basePayload.slices.map((row) => ({
        ...row,
        stats: { ...row.stats, return_10d: return10Stats },
        date_weighted_stats: { ...row.date_weighted_stats, return_10d: return10DateWeighted },
        recommendation: {
          ...row.recommendation,
          reason: "T+10 样本 20，均值 +3.10%，胜率 60.0%，只读复核排序。",
          primary_horizon: "return_10d",
          available_count: 20,
          avg_return: 0.031,
          win_rate: 0.6,
        },
      })),
      pending_summary: {
        primary_horizon: "return_10d",
        pending_rows: 0,
        pending_dates: [],
        latest_pending_date: null,
        message: "T+10 主期限已有成熟样本。",
      },
      sample_maturity: {
        status: "sufficient",
        primary_horizon: "return_10d",
        min_sample: 20,
        sufficient_count: 2,
        insufficient_count: 0,
      },
    };

    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({ strategyOptimization: payload }),
    });

    await openStrategyModuleDetail("strategy-optimization");
    const card = await screen.findByTestId("stock-analysis-strategy-optimization");
    await waitFor(() => expect(card).toHaveTextContent("三策略 T+10 排名"), { timeout: 3_000 });
    expect(card).toHaveTextContent("切片 T+10");
    expect(card).toHaveTextContent("T+10 收益");
    expect(card).not.toHaveTextContent("切片 T+5");
    expect(card).not.toHaveTextContent("三策略 T+5 排名");
  });

  it("localizes optimization request source-table failures without exposing backend tables", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategyOptimizationError: new Error(
          "Failed to fetch optimization because source_table choice_stock_strategy_optimization is missing.",
        ),
      }),
    });

    await openStrategyModuleDetail("strategy-optimization");
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
          return_10d: {
            available_count: 0,
            missing_count: 8,
            positive_count: 0,
            non_positive_count: 0,
            avg_return: null,
            win_rate: null,
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

    await openStrategyModuleDetail("market-priority");
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
                  return_10d: {
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
                  return_10d: {
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
                  return_10d: {
                    available_count: 0,
                    missing_count: 3,
                    positive_count: 0,
                    non_positive_count: 0,
                    avg_return: null,
                    win_rate: null,
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
                    return_10d: {
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
                    return_10d: {
                      available_count: 0,
                      missing_count: 3,
                      positive_count: 0,
                      non_positive_count: 0,
                      avg_return: null,
                      win_rate: null,
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
                    return_10d: {
                      available_count: 0,
                      missing_count: 20,
                      positive_count: 0,
                      non_positive_count: 0,
                      avg_return: null,
                      win_rate: null,
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

    await openStrategyModuleDetail("strategy-backtest");
    const panel = await screen.findByTestId("stock-analysis-strategy-backtest");
    await waitFor(() => expect(panel).toHaveTextContent("75.0% / +3.21% / 12条"), {
      timeout: 5_000,
    });
    const stockCandidateRow = screen.getByTestId("stock-analysis-strategy-backtest-stock_candidate");
    expect(stockCandidateRow).toHaveTextContent("50.0% / -1.11% / 4条");
    expect(stockCandidateRow).toHaveTextContent("成熟度未提供");
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

  it("does not present decision aggregates under an execution return basis", async () => {
    const candidateHistory = buildCandidateHistoryPayload();
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        candidateHistory: {
          ...candidateHistory,
          summary: {
            ...candidateHistory.summary!,
            execution_usable_stats: {
              metric_basis: "net_next_open_adj",
              row_count: 3,
            },
            by_market_state_signal_kind_execution_stats: undefined,
          },
        },
      }),
    });

    await openStrategyModuleDetail("strategy-backtest");
    const panel = await screen.findByTestId("stock-analysis-strategy-backtest");
    await waitFor(() => expect(panel).toHaveTextContent("T+1开盘成交·含费·复权"), {
      timeout: 5_000,
    });
    expect(panel).toHaveTextContent("市场状态归因未提供");
    expect(panel).not.toHaveTextContent("T+5 有效样本");
    expect(panel).not.toHaveTextContent("已就绪");
    expect(panel).not.toHaveTextContent("25.0% / -1.23% / 4条");
  });
});

describe("StockAnalysisPage current ResearchDesk contract", () => {
  it("shows a loading skeleton with the current stock-research chrome", async () => {
    const client = {
      ...stockClient(),
      getStockAnalysisWorkbench: vi.fn(
        () => new Promise<ApiEnvelope<StockAnalysisWorkbenchPayload>>(() => undefined),
      ),
    };

    renderWorkbenchApp(["/stock-analysis"], { client });

    const loading = await screen.findByTestId("stock-analysis-loading-workbench");
    const compactChrome = screen.getByTestId("stock-analysis-page-compact-chrome");
    const statusStrip = within(compactChrome).getByTestId("stock-analysis-page-status-strip");

    expect(loading).toBeInTheDocument();
    expect(screen.getByText("股票分析加载中")).toBeInTheDocument();
    expect(compactChrome).toHaveTextContent("股票研究");
    expect(compactChrome).toHaveTextContent("口径读取中");
    expect(statusStrip).toHaveTextContent("数据读取中");
    expect(statusStrip).toHaveTextContent("门控读取中");
  });

  it("loads the page from the stock-analysis workbench contract without calling the legacy strategy route", async () => {
    const client = stockClient();
    const workbenchSpy = vi.spyOn(client, "getStockAnalysisWorkbench");
    const strategySpy = vi.spyOn(client, "getLivermoreStrategy");

    renderWorkbenchApp(["/stock-analysis"], { client });

    await screen.findByTestId("stock-analysis-first-screen-workbench");
    expect(workbenchSpy).toHaveBeenCalledWith({ topK: 10 });
    expect(strategySpy).not.toHaveBeenCalled();

    const researchDesk = screen.getByTestId("stock-analysis-research-desk");
    expect(researchDesk).toHaveTextContent("三窗研究台");
    expect(researchDesk).toHaveTextContent("左侧筛池，中部归档，右侧只保留风险与动作");

    await openEvidenceDisclosure();
    const contract = await screen.findByTestId("stock-analysis-workbench-contract");
    expect(contract).toHaveTextContent("数据入口 /ui/market-data/stock-analysis/workbench");
    expect(contract).toHaveTextContent("结果口径 market_data.stock_analysis.workbench");
    expect(contract).toHaveTextContent("使用边界");
    expect(contract).toHaveTextContent("仅供观察");
  });

  it.each([
    { payloadFormalUseAllowed: false, resultMetaFormalUseAllowed: true },
    { payloadFormalUseAllowed: true, resultMetaFormalUseAllowed: false },
  ])(
    "keeps the page observation-only when formal-use flags conflict %#",
    async ({ payloadFormalUseAllowed, resultMetaFormalUseAllowed }) => {
      const strategy = buildStrategyPayload();
      const workbench = buildStockAnalysisWorkbenchPayload(strategy);
      (workbench as unknown as { formal_use_allowed: boolean }).formal_use_allowed =
        payloadFormalUseAllowed;
      const client: ApiClient = {
        ...stockClient({ strategy }),
        getStockAnalysisWorkbench: vi.fn(async () =>
          buildMockApiEnvelope("market_data.stock_analysis.workbench", workbench, {
            basis: "analytical",
            formal_use_allowed: resultMetaFormalUseAllowed,
          }),
        ),
      };

      renderWorkbenchApp(["/stock-analysis"], { client });

      await openEvidenceDisclosure();
      const contract = await screen.findByTestId("stock-analysis-workbench-contract");
      const compactChrome = await screen.findByTestId("stock-analysis-page-compact-chrome");
      const closurePanel = await screen.findByTestId("stock-analysis-observation-closure-panel");

      expect(contract).toHaveTextContent("仅供观察");
      expect(contract).not.toHaveTextContent("正式口径可用");
      expect(compactChrome).toHaveTextContent("仅供观察");
      expect(compactChrome).not.toHaveTextContent("正式口径可用");
      expect(closurePanel).toHaveTextContent("正式用途：否");
      expect(closurePanel.querySelector("[data-formal-use]")).toHaveAttribute("data-formal-use", "false");
    },
  );

  it("uses the workbench review queue as the single candidate source in the research desk", async () => {
    const client = stockClient();
    const strategy = buildStrategyPayload();
    const workbench = buildStockAnalysisWorkbenchPayload(strategy);
    workbench.first_screen.review_queue = [
      {
        stock_code: "600062.SH",
        stock_name: "权威候选",
        sector_code: "801150",
        sector_name: "医药生物",
        rank: 1,
        source_module: "stock_candidates",
        score: 0.91,
      },
    ];
    workbench.decision_summary = {
      ...workbench.decision_summary,
      review_queue_count: 1,
      top_review_stock_code: "600062.SH",
      top_review_stock_name: "权威候选",
    };
    vi.spyOn(client, "getStockAnalysisWorkbench").mockResolvedValue(
      buildMockApiEnvelope("market_data.stock_analysis.workbench", workbench),
    );

    renderWorkbenchApp(["/stock-analysis"], { client });

    const queue = await screen.findByTestId("stock-analysis-review-queue");
    expect(within(queue).getByRole("button", { name: /600062\.SH.*权威候选/ })).toBeInTheDocument();
    expect(within(queue).queryByRole("button", { name: /000001\.SZ.*Alpha/ })).not.toBeInTheDocument();
    expect(queue).toHaveTextContent("1 / 1");
  });

  it("does not repopulate an authoritative empty workbench queue from the strategy payload", async () => {
    const client = stockClient();
    const strategy = buildStrategyPayload();
    const workbench = buildStockAnalysisWorkbenchPayload(strategy);
    workbench.first_screen.review_queue = [];
    workbench.pretrade_qualification = {
      ...workbench.pretrade_qualification,
      status: "ready_empty",
      reason: null,
    };
    workbench.page_question = {
      ...workbench.page_question,
      answer_state: "no_data",
      answer_label: "no_data",
      reason: "No candidates are available for the resolved date.",
    };
    workbench.decision_summary = {
      ...workbench.decision_summary,
      top_review_stock_code: null,
      top_review_stock_name: null,
      review_queue_count: 0,
      can_review_candidates: false,
    };
    vi.spyOn(client, "getStockAnalysisWorkbench").mockResolvedValue(
      buildMockApiEnvelope("market_data.stock_analysis.workbench", workbench),
    );

    renderWorkbenchApp(["/stock-analysis"], { client });

    const queue = await screen.findByTestId("stock-analysis-review-queue");
    expect(within(queue).queryByRole("button", { name: /000001\.SZ.*Alpha/ })).not.toBeInTheDocument();
    expect(queue).toHaveTextContent("当前观察日无候选");
  });

  it("keeps raw fallback codes out of the current page chrome", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({ metaOverrides: { fallback_mode: "latest_snapshot" } }),
    });

    await screen.findByTestId("stock-analysis-first-screen-workbench");
    expect(screen.getByTestId("stock-analysis-page-compact-chrome")).not.toHaveTextContent("latest_snapshot");
    expect(screen.getByTestId("stock-analysis-page-compact-chrome")).toHaveTextContent("观察日");
  });

  it("submits the resolved workbench date through the agent page context after fallback", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    const strategySpy = vi
      .spyOn(client, "getStockAnalysisWorkbench")
      .mockImplementation(async (options) => {
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
            rule_version: "rv_stock_analysis_workbench_v2",
            fallback_mode: options?.asOfDate ? "latest_snapshot" : "none",
          },
        );
      });
    const fetchMock = vi.fn().mockResolvedValueOnce(buildJsonResponse(buildStockAgentResult()));
    vi.stubGlobal("fetch", fetchMock);

    renderWorkbenchApp(["/stock-analysis"], { client });

    await requestStockAnalysisAsOfDate(user, strategySpy);
    expect(screen.getByTestId("stock-analysis-page-compact-chrome")).toHaveTextContent("2026-04-29");
    await user.click(screen.getByTestId("stock-analysis-agent-open"));
    await waitFor(() => {
      const contextSummary = screen.getByText((content, element) => {
        return (
          element?.classList.contains("agent-page-context__code") === true &&
          content.includes("2026-04-29")
        );
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
});
