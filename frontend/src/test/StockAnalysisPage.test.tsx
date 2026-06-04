import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import type { CSSProperties } from "react";

import { createApiClient, type ApiClient } from "../api/client";
import type {
  ApiEnvelope,
  ConfluenceReplayStatus,
  LivermoreCandidateHistoryPayload,
  LivermoreCandidateHistoryPortfolioBacktestPayload,
  LivermoreCycleProxyBacktestPayload,
  LivermoreSignalConfluencePayload,
  LivermoreStrategyOptimizationPayload,
  LivermoreStrategyScorePayload,
  LivermoreStrategyPayload,
} from "../api/contracts";
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

const STOCK_ANALYSIS_CSS_PATH = resolve(
  process.cwd(),
  "src/features/stock-analysis/pages/StockAnalysisPage.css",
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

afterEach(() => {
  vi.unstubAllGlobals();
});

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

function buildStrategyPayload(
  overrides: Partial<LivermoreStrategyPayload> = {},
): LivermoreStrategyPayload {
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
      formula_version: "rv_livermore_sector_rank_provisional_v1",
      is_provisional: true,
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
          reason: "T+5 可用样本 2/20，样本不足，只展示不作为调参依据。",
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

  return vi.spyOn(client, "getLivermoreStrategy").mockImplementation(async (options) =>
    buildMockApiEnvelope(
      "market_data.livermore",
      buildStrategyPayload({
        as_of_date: options?.asOfDate ? resolvedAsOfDate : initialAsOfDate,
        requested_as_of_date: options?.asOfDate ?? null,
        ...dates.payloadOverrides,
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

  await waitFor(() => expect(strategySpy).toHaveBeenCalledWith({ asOfDate: requestedAsOfDate }));
  await waitFor(() =>
    expect(screen.getByTestId("stock-analysis-decision-panel")).toHaveTextContent(resolvedAsOfDate),
  );
}

describe("StockAnalysisPage", () => {
  it("shows a dashboard skeleton while the stock analysis payload is loading", async () => {
    const client = {
      ...stockClient(),
      getLivermoreStrategy: vi.fn(() => new Promise<ApiEnvelope<LivermoreStrategyPayload>>(() => undefined)),
    };

    renderWorkbenchApp(["/stock-analysis"], { client });

    const loading = await screen.findByTestId("stock-analysis-loading-workbench");
    expect(loading).toBeInTheDocument();
    expect(screen.queryByText("正在加载股票分析结果。")).not.toBeInTheDocument();
    expect(screen.getByText("股票分析加载中")).toBeInTheDocument();
  });

  it("marks the backend-supply cockpit without changing the stock data path", async () => {
    renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });

    const page = await screen.findByTestId("stock-analysis-page");
    expect(page.querySelector(".stock-analysis-page")).toHaveAttribute("data-layout-rev", "2026-05-31e");
    expect(page.querySelector(".stock-analysis-page")).toHaveAttribute("data-data-viz-rev", "2026-05-31e");
    const cockpit = await screen.findByTestId("stock-analysis-tailwind-cockpit");
    expect(cockpit.className).toContain("bg-white");
    expect(cockpit).toHaveTextContent("数据日");
    expect(cockpit).toHaveTextContent("门控 温和");
    expect(cockpit).toHaveTextContent("条件 2/4");
    expect(cockpit).toHaveTextContent("缺口 1");
    expect(cockpit).toHaveTextContent("阻断 0");
    expect(cockpit).not.toHaveTextContent("查看今日门控、候选队列与证据是否齐全");
    expect(cockpit).not.toHaveTextContent("TAILWIND");
    expect(cockpit).not.toHaveTextContent("后端供数");
    expect(cockpit).not.toHaveTextContent("门控 WARM");
    expect(cockpit).not.toHaveTextContent("Livermore");

    const kpiSection = await screen.findByTestId("stock-analysis-kpi-section");
    expect(kpiSection).toHaveTextContent("市场状态");
    expect(kpiSection).toHaveTextContent("温和");
    expect(kpiSection).not.toHaveTextContent("WARM");
    expect(screen.getByTestId("stock-analysis-kpi-market-state")).toHaveAttribute("data-equity-kpi-card");
    expect(screen.getByTestId("stock-analysis-kpi-review-queue")).toHaveAttribute("data-equity-kpi-card");

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
    expect(await screen.findByTestId("stock-analysis-strategy-lens")).toBeInTheDocument();
    expect(await screen.findByTestId("stock-analysis-review-queue-ranking-chart")).toHaveTextContent("队列排序");
    expect(await screen.findByTestId("stock-analysis-risk-section")).toBeInTheDocument();
    expect(await screen.findByTestId("stock-analysis-deep-zone")).toBeInTheDocument();
    expect(await screen.findByTestId("stock-analysis-deep-zone-gate-summary")).toBeInTheDocument();
    expect(page).not.toHaveTextContent("策略池暂无候选");
    expect(page).not.toHaveTextContent("当前状态样本不足");
    expect(page).not.toHaveTextContent("暂无优化诊断结果");

    const user = userEvent.setup();
    await user.click(screen.getByTestId("stock-analysis-supply-details-toggle"));

    const sectorMiniChart = await screen.findByTestId("stock-analysis-sector-mini-chart");
    const reviewMiniChart = await screen.findByTestId("stock-analysis-review-mini-chart");
    const outputMiniChart = await screen.findByTestId("stock-analysis-event-mini-chart");
    const riskMiniChart = await screen.findByTestId("stock-analysis-risk-mini-chart");
    expect(sectorMiniChart.closest(".stock-analysis-page__visually-hidden")).toBeNull();
    expect(reviewMiniChart.closest(".stock-analysis-page__visually-hidden")).toBeNull();
    expect(outputMiniChart.closest(".stock-analysis-page__visually-hidden")).toBeNull();
    expect(riskMiniChart.closest(".stock-analysis-page__visually-hidden")).toBeNull();
    expect(await screen.findByTestId("stock-analysis-historical-review-section")).toHaveTextContent("历史复核");
    expect(await screen.findByTestId("stock-analysis-consensus-panel-summary")).toBeInTheDocument();
    expect(await screen.findByTestId("stock-analysis-theme-panel-summary")).toBeInTheDocument();
    expect(await screen.findByTestId("stock-analysis-events-panel-summary")).toBeInTheDocument();
  });

  it("does not fan out lower-page diagnostics before the first screen", async () => {
    const client = stockClient();
    const strategyScoreSpy = vi.spyOn(client, "getLivermoreStrategyScore");
    const strategyOptimizationSpy = vi.spyOn(client, "getLivermoreStrategyOptimization");
    const candidateHistorySpy = vi.spyOn(client, "getLivermoreCandidateHistory");
    const cycleProxySpy = vi.spyOn(client, "getLivermoreCycleProxyBacktest");
    const portfolioBacktestSpy = vi.spyOn(client, "getLivermoreCandidateHistoryPortfolioBacktest");

    renderWorkbenchApp(["/stock-analysis"], { client });

    expect(await screen.findByTestId("stock-analysis-tailwind-cockpit")).toBeInTheDocument();
    expect(strategyScoreSpy).not.toHaveBeenCalled();
    expect(strategyOptimizationSpy).not.toHaveBeenCalled();
    expect(candidateHistorySpy).not.toHaveBeenCalled();
    expect(cycleProxySpy).not.toHaveBeenCalled();
    expect(portfolioBacktestSpy).not.toHaveBeenCalled();
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
    expect(css).toContain("box-shadow: var(--moss-shadow-card)");
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

  it("keeps the narrow first screen focused on summary, KPI, and sector chart", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const finalRailStart = css.indexOf("Right rail final polish");
    const narrowRailStart = css.indexOf("@media (max-width: 1279px)", finalRailStart);
    const narrowRailCss = css.slice(narrowRailStart);

    expect(narrowRailCss).toContain('[data-testid="stock-analysis-first-screen-rail"]');
    expect(narrowRailCss).toContain('[data-testid="stock-analysis-first-screen-primary"]');
    expect(narrowRailCss).toMatch(
      /\[data-testid="stock-analysis-first-screen-primary"\]\s*\{[\s\S]*?order:\s*4\s*!important/,
    );
    expect(narrowRailCss).toMatch(
      /\[data-testid="stock-analysis-sector-strength-panel"\]\s*\{[\s\S]*?order:\s*1\s*!important/,
    );
    expect(narrowRailCss).toMatch(
      /\[data-testid="stock-analysis-review-queue"\]\s*\{[\s\S]*?order:\s*5\s*!important/,
    );
    expect(narrowRailCss).toMatch(
      /\[data-testid="stock-analysis-consensus-first-screen"\]\s*\{[\s\S]*?order:\s*6\s*!important/,
    );
    expect(narrowRailCss).toContain("grid-template-columns: repeat(4, minmax(0, 1fr))");
    expect(narrowRailCss).toMatch(
      /\[data-testid="stock-analysis-first-screen-rail"\]\s*>\s*\[data-testid="stock-analysis-risk-section"\][\s\S]*?display:\s*none/,
    );
    expect(narrowRailCss).toMatch(
      /\[data-testid="stock-analysis-first-screen-rail"\]\s*>\s*\[data-testid="stock-analysis-boundary-rail"\][\s\S]*?display:\s*none/,
    );
    expect(narrowRailCss).toMatch(/\.stock-analysis-page__rail-check-list\s*\{[\s\S]*?display:\s*none\s*!important/);
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

  it("keeps the stock dashboard aligned to homepage-style fine divider panels", () => {
    const css = readFileSync(STOCK_ANALYSIS_CSS_PATH, "utf8");
    const finalLayoutStart = css.indexOf("Final homepage-rhythm pass");
    const finalLayoutCss = css.slice(finalLayoutStart);

    expect(finalLayoutStart).toBeGreaterThan(-1);
    expect(finalLayoutCss).toContain('[data-testid="stock-analysis-tailwind-cockpit"]');
    expect(finalLayoutCss).toContain("border-color: #dfe7f1");
    expect(finalLayoutCss).toContain(".stock-analysis-page__dh-kpi-strip");
    expect(finalLayoutCss).toContain(".stock-analysis-page__strategy-lens-grid");
    expect(finalLayoutCss).toMatch(
      /\.stock-analysis-page__strategy-lens-card\s*\{[\s\S]*?min-height:\s*46px/,
    );
    expect(finalLayoutCss).toMatch(
      /\.stock-analysis-page__strategy-lens-detail\s*\{[\s\S]*?display:\s*none/,
    );
    expect(finalLayoutCss).toContain(".stock-analysis-page__review-workbench-strip");
    expect(finalLayoutCss).toContain(".stock-analysis-page__consensus-workbench-strip");
    expect(finalLayoutCss).toContain("box-shadow: none");
    expect(finalLayoutCss).toMatch(
      /@media \(min-width:\s*1600px\)[\s\S]*?grid-template-columns:\s*minmax\(0,\s*1fr\)\s*320px/,
    );
    expect(finalLayoutCss).toMatch(
      /@media \(min-width:\s*1280px\)[\s\S]*?\.stock-analysis-page__first-screen-main\s*\{[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/,
    );
    expect(finalLayoutCss).toMatch(
      /@media \(min-width:\s*1280px\)[\s\S]*?\[data-testid="stock-analysis-sector-strength-panel"\]\s*\{[\s\S]*?min-height:\s*320px/,
    );
    expect(finalLayoutCss).toMatch(
      /\[data-testid="stock-analysis-sector-strength-panel"\]\s*\.stock-analysis-page__sector-chart-wrap\s*\{[\s\S]*?min-height:\s*176px\s*!important/,
    );
    expect(finalLayoutCss).toMatch(
      /\[data-testid="stock-analysis-sector-strength-panel"\]\s*\.stock-analysis-page__echart--sector-strength\s*\{[\s\S]*?height:\s*176px\s*!important/,
    );
    expect(finalLayoutCss).toMatch(
      /\[data-testid="stock-analysis-review-queue"\],[\s\S]*?\[data-testid="stock-analysis-consensus-first-screen"\]\s*\{[\s\S]*?grid-template-rows:\s*30px\s*minmax\(72px,\s*1fr\)/,
    );
    expect(finalLayoutCss).toMatch(
      /\.stock-analysis-page__review-workbench-strip,[\s\S]*?\.stock-analysis-page__consensus-workbench-strip\s*\{[\s\S]*?height:\s*72px/,
    );
    expect(finalLayoutCss).toMatch(
      /\[data-testid="stock-analysis-review-queue"\]\s*\.stock-analysis-page__review-workbench-strip\s*\{[\s\S]*?grid-template-columns:\s*repeat\(2,\s*minmax\(0,\s*1fr\)\)/,
    );
    expect(finalLayoutCss).toMatch(
      /\[data-testid="stock-analysis-review-queue"\]\s*\.stock-analysis-page__review-workbench-strip svg\s*\{[\s\S]*?display:\s*none/,
    );
    expect(finalLayoutCss).toMatch(
      /\[data-testid="stock-analysis-sector-strength-panel"\]\s*\.stock-analysis-page__sector-workbench-strip svg\s*\{[\s\S]*?display:\s*none/,
    );
    expect(finalLayoutCss).toContain("Decision rail cleanup");
    expect(finalLayoutCss).toMatch(
      /\.stock-analysis-page__rail-verdict\s*\{[\s\S]*?border-width:\s*1px\s*0/,
    );
    expect(finalLayoutCss).toMatch(
      /\.stock-analysis-page__rail-check-row,[\s\S]*?\.stock-analysis-page__rail-risk-row\s*\{[\s\S]*?min-height:\s*44px/,
    );
    expect(finalLayoutCss).toMatch(
      /\[data-testid="stock-analysis-first-screen-rail"\]\s*\.stock-analysis-page__rail-collapse\s*\{[\s\S]*?display:\s*none\s*!important/,
    );
    expect(finalLayoutCss).toMatch(
      /\[data-testid="stock-analysis-first-screen-rail"\]\s*\.stock-analysis-page__rail-risk-row:nth-child\(n \+ 3\)\s*\{[\s\S]*?display:\s*none/,
    );
    expect(finalLayoutCss).toMatch(
      /\[data-testid="stock-analysis-first-screen-rail"\]\s*\.stock-analysis-page__rail-risk-meta\s*\{[\s\S]*?grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)/,
    );
    expect(finalLayoutCss).toContain("min-height: 316px");
    expect(finalLayoutCss).not.toContain("grid-template-columns: repeat(3, minmax(0, 1fr)) 320px");
  });

  it("surfaces backend supply status and stock selection on the first screen", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({ metaOverrides: { quality_flag: "warning" } }),
    });

    const decisionPanel = await screen.findByTestId("stock-analysis-decision-panel");
    expect(decisionPanel).toHaveTextContent("数据日");
    expect(decisionPanel).toHaveTextContent("门控 温和");
    expect(decisionPanel).toHaveTextContent("暴露 40%");
    expect(decisionPanel).toHaveTextContent("就绪 0/1");
    expect(decisionPanel).toHaveTextContent("可用 4");
    expect(decisionPanel).toHaveTextContent("阻断 0");
    expect(decisionPanel).toHaveTextContent("质量 需复核");
    expect(decisionPanel).not.toHaveTextContent("后端供数");
    expect(decisionPanel).not.toHaveTextContent("门控 WARM");

    const supplyStatus = await screen.findByTestId("stock-analysis-backend-supply-status");
    expect(supplyStatus).toHaveTextContent("市场门控");
    expect(supplyStatus).toHaveTextContent("部分");
    expect(supplyStatus).toHaveTextContent("市场宽度");
    expect(supplyStatus).not.toHaveTextContent("Market gate");
    expect(supplyStatus).not.toHaveTextContent("partial");
    expect(supplyStatus).not.toHaveTextContent("breadth");

    await userEvent.click(screen.getByTestId("stock-analysis-supply-details-toggle"));
    const reviewMiniChartOption = JSON.parse(
      within(screen.getByTestId("stock-analysis-review-mini-chart"))
        .getByTestId("stock-analysis-echarts-stub")
        .getAttribute("data-option") ?? "null",
    );
    expect(reviewMiniChartOption?.yAxis?.data).toContain("部分");
    expect(reviewMiniChartOption?.yAxis?.data).not.toContain("partial");
    const outputMiniChartOption = JSON.parse(
      within(screen.getByTestId("stock-analysis-event-mini-chart"))
        .getByTestId("stock-analysis-echarts-stub")
        .getAttribute("data-option") ?? "null",
    );
    expect(outputMiniChartOption?.yAxis?.data).toContain("输出");
    expect(outputMiniChartOption?.yAxis?.data).not.toContain("events");

    const selection = await screen.findByTestId("stock-analysis-stock-selection");
    expect(selection).toHaveTextContent("多因子");
    expect(selection).toHaveTextContent("复核 K 线");

    const queue = await screen.findByTestId("stock-analysis-review-queue");
    expect(queue).toHaveTextContent("复核队列");
    expect(queue).toHaveTextContent("证据明细");
    expect(queue).not.toHaveTextContent("为什么先看");
    expect(queue).not.toHaveTextContent("反证与待补");
    expect(queue).toHaveTextContent("复核 K 线");
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
    expect(decisionPanel).toHaveTextContent("通道待确认");
    expect(decisionPanel).toHaveTextContent("回退待确认");
    expect(decisionPanel).not.toHaveTextContent("quality_vendor_unknown");
    expect(decisionPanel).not.toHaveTextContent("vendor_paused");
    expect(decisionPanel).not.toHaveTextContent("external_vendor_snapshot");
  });

  it("localizes unknown strategy basis before showing supply details", async () => {
    const user = userEvent.setup();

    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          basis: "external_vendor_basis" as LivermoreStrategyPayload["basis"],
        }),
      }),
    });

    await user.click(await screen.findByTestId("stock-analysis-supply-details-toggle"));

    const decisionPanel = await screen.findByTestId("stock-analysis-decision-panel");
    expect(decisionPanel).toHaveTextContent("口径待确认");
    expect(decisionPanel).not.toHaveTextContent("external_vendor_basis");
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

    const analytics = await screen.findByTestId("stock-analysis-first-screen-analytics");
    expect(analytics).toHaveTextContent("回测诊断");
    expect(analytics).not.toHaveTextContent("历史共振 / 策略优先级 / 优化诊断");
    expect(analytics).toHaveTextContent("历史共振");
    expect(screen.getByRole("tab", { name: "策略优先级" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "优化诊断" })).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "策略优先级" }));
    expect(
      await screen.findByTestId("first-screen-priority-row-OVERHEAT-factor_screen"),
    ).toBeInTheDocument();
  });

  it("loads strategy priority when first-screen analytics priority tab is opened", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    const strategyScoreSpy = vi.spyOn(client, "getLivermoreStrategyScore");

    renderWorkbenchApp(["/stock-analysis"], { client });

    await screen.findByTestId("stock-analysis-first-screen-analytics");
    expect(strategyScoreSpy).not.toHaveBeenCalled();

    await user.click(screen.getByRole("tab", { name: "策略优先级" }));
    await waitFor(() => {
      expect(strategyScoreSpy).toHaveBeenCalled();
    });
  });

  it("renders core sections and candidate evidence", async () => {
    const user = userEvent.setup();
    renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });

    expect(await screen.findByRole("heading", { name: "股票分析" })).toBeInTheDocument();
    expect(await screen.findByTestId("stock-analysis-decision-panel")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "板块强弱" })).toBeInTheDocument();
    const pagePurpose = await screen.findByTestId("stock-analysis-page-purpose");
    expect(pagePurpose).toHaveTextContent("股票策略复核台");
    expect(pagePurpose).not.toHaveTextContent("查看今日门控、候选队列与证据是否齐全");
    expect(await screen.findByTestId("stock-analysis-deep-zone")).toHaveTextContent("供数闭环");
    expect(await screen.findByRole("heading", { name: "题材突变观察" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "复核队列" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "风险退出观察" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "数据口径与边界" })).toBeInTheDocument();

    const candidate = screen.getByTestId("stock-candidate-000001.SZ");
    expect(candidate).toHaveTextContent("Alpha");
    expect(candidate).toHaveTextContent("行业排名第 1");
    expect(candidate).toHaveTextContent("边界 3");
    expect(candidate).toHaveTextContent("+7 证据");
    expect(candidate).toHaveTextContent("证据明细");
    expect(candidate).not.toHaveTextContent("进入依据");
    expect(candidate).not.toHaveTextContent("10EMA 失效观察");
    expect(candidate).not.toHaveTextContent("基本面 overlay 已接入候选排序");

    await user.click(within(candidate).getByText("证据明细"));

    expect(candidate).toHaveTextContent("进入依据");
    expect(candidate).toHaveTextContent("10EMA 失效观察");
    expect(candidate).toHaveTextContent("基本面 overlay");
    expect(candidate).toHaveTextContent("因子分 0.4812");
    expect(candidate).toHaveTextContent("基本面 overlay 已接入候选排序");
    expect(candidate).toHaveTextContent("新闻、公告、财报事件尚未进入候选卡");
    expect(candidate).toHaveTextContent("10EMA");
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
    expect(framework).toHaveTextContent("宏观层");
    expect(framework).toHaveTextContent("PMI");
    expect(framework).toHaveTextContent("信用脉冲");
    expect(framework).toHaveTextContent("行业上限 25%");
    expect(framework).toHaveTextContent("证据待齐");
    expect(framework).toHaveTextContent("输入待补");
    expect(framework).toHaveTextContent("市场门控已接入");
    expect(framework).toHaveTextContent("板块强弱已接入");
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
    expect(section).toHaveTextContent("源表缺失");
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
    expect(section).toHaveTextContent("源表缺失");
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
              display_name: "生命法庭层",
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
    expect(section).toHaveTextContent("半导体");
    expect(section).toHaveTextContent("电子 #9");
    expect(section).toHaveTextContent("代理题材观察");
    expect(section).toHaveTextContent("Alpha Semiconductor");
    expect(section).not.toHaveTextContent("Semiconductor proxy");
    expect(screen.getByTestId("stock-analysis-theme-evidence-state")).toHaveTextContent("目录待确认");
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
            coverage_note: "因子数据覆盖 643/5201 只，仅在有因子数据的股票中筛选",
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
    const user = userEvent.setup();
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
                sector_name: "机器人",
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
    expect(queue).toHaveTextContent("融合分");
    expect(queue).toHaveTextContent("生命法庭代理");
    expect(queue).toHaveTextContent("+6 证据");
    expect(queue).not.toHaveTextContent("代理信号");

    await user.click(within(queue).getByText("证据明细"));

    expect(queue).toHaveTextContent("代理信号");
    expect(queue).not.toHaveTextContent("买入");
  });

  it("shows staleness banner when quality_flag is not ok", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({ metaOverrides: { quality_flag: "warning" } }),
    });

    expect(await screen.findByTestId("stock-analysis-stale-banner")).toHaveTextContent(
      "仅供复核参考",
    );
  });

  it("shows fallback snapshots as data that needs review", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({ metaOverrides: { fallback_mode: "latest_snapshot" } }),
    });

    const purpose = await screen.findByTestId("stock-analysis-page-purpose");
    const decisionPanel = await screen.findByTestId("stock-analysis-decision-panel");
    expect(purpose).toHaveTextContent("回退快照");
    expect(purpose).not.toHaveTextContent("latest_snapshot");
    expect(decisionPanel).toHaveTextContent("质量 正常");
    expect(decisionPanel).toHaveTextContent("回退快照");
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
    expect(summary).toHaveTextContent("可复核");
    expect(summary).toHaveTextContent("入场观察门");
    expect(summary).toHaveTextContent("开放");
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
    expect(decisionPanel).toHaveTextContent("供数闭环");
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).toHaveTextContent("门控 温和");
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).not.toHaveTextContent("今日市场状态");
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).not.toHaveTextContent("闭环阻断，先复核约束项");
    expect(summary).toHaveTextContent("拦截");
    expect(summary).toHaveTextContent("阻断");
    expect(summary).toHaveTextContent("已触发");
    expect(summary).toHaveTextContent("降级");
    expect(summary).toHaveTextContent("依据明细");
    expect(summary).not.toHaveTextContent("crowded leaders without breadth confirmation");
    await userEvent.click(within(verdict).getByText("依据明细"));
    expect(summary).toHaveTextContent("强势样本拥挤，市场宽度未确认。");
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
    expect(decisionPanel).toHaveTextContent("供数闭环");
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).toHaveTextContent("门控 温和");
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).not.toHaveTextContent("今日市场状态");
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).not.toHaveTextContent("证据不足，不形成有效观察结论");
    expect(summary).toHaveTextContent("数据不足");
    expect(summary).toHaveTextContent("待补");
    expect(summary).not.toHaveTextContent("不能视为中性证明");
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
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).toHaveTextContent("门控 温和");
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

  it("filters candidates when industry chip clicked", async () => {
    const user = userEvent.setup();
    renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });

    expect(await screen.findByTestId("stock-candidate-000001.SZ")).toBeInTheDocument();
    expect(screen.getByTestId("stock-analysis-sector-review-link")).toHaveTextContent("全部行业");
    expect(screen.getByTestId("stock-analysis-sector-review-link")).toHaveTextContent("2 个候选");
    expect(screen.getByTestId("stock-review-filter-status")).toHaveTextContent("全部行业");
    expect(screen.getByTestId("stock-review-filter-status")).toHaveTextContent("显示 2 / 2 个候选");
    await user.click(screen.getByTestId("sector-filter-chip-801002"));

    await waitFor(() => {
      expect(screen.queryByTestId("stock-candidate-000001.SZ")).not.toBeInTheDocument();
      expect(screen.getByTestId("stock-candidate-000002.SZ")).toBeInTheDocument();
    });
    expect(screen.getByTestId("sector-filter-chip-801002")).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "全部行业" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByTestId("stock-review-filter-status")).toHaveTextContent("新能源车");
    expect(screen.getByTestId("stock-review-filter-status")).toHaveTextContent("显示 1 / 2 个候选");
    expect(screen.getByTestId("stock-analysis-sector-review-link")).toHaveTextContent("新能源车");
    expect(screen.getByTestId("stock-analysis-sector-review-link")).toHaveTextContent("1 个候选");
    expect(screen.getByTestId("stock-analysis-sector-review-link")).toHaveTextContent("Beta");
    expect(screen.getByTestId("stock-candidate-000002.SZ")).toHaveAttribute("data-selected-sector", "true");

    await user.click(screen.getByRole("button", { name: "全部行业" }));
    await screen.findByTestId("stock-candidate-000001.SZ");
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
    const cards = Array.from(queue.querySelectorAll("article[data-testid^='stock-candidate-']")).map((node) =>
      node.getAttribute("data-testid"),
    );
    expect(cards).toEqual(["stock-candidate-000101.SZ", "stock-candidate-000202.SZ"]);
    expect(screen.getByTestId("stock-analysis-review-queue-ranking-chart")).toHaveTextContent(
      "#1 Rank One Consolidation",
    );
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
                sector_name: "无候选行业",
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

    expect(await screen.findByTestId("stock-candidate-000001.SZ")).toBeInTheDocument();
    await user.click(screen.getByTestId("sector-bar-801003"));

    await waitFor(() => {
      expect(screen.queryByTestId("stock-candidate-000001.SZ")).not.toBeInTheDocument();
      expect(screen.queryByTestId("stock-candidate-000002.SZ")).not.toBeInTheDocument();
    });
    expect(screen.getByTestId("stock-review-filter-status")).toHaveTextContent("无候选行业");
    expect(screen.getByTestId("stock-review-filter-status")).toHaveTextContent("显示 0 / 2 个候选");
    expect(screen.getByTestId("stock-analysis-sector-review-link")).toHaveTextContent("无候选行业");
    expect(screen.getByTestId("stock-analysis-sector-review-link")).toHaveTextContent("无候选");
    expect(screen.getByTestId("stock-analysis-sector-review-link")).toHaveTextContent("该行业暂无线索");
    expect(screen.getByTestId("stock-analysis-review-queue-filter-empty")).toHaveTextContent("筛选");
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
    expect(boundarySummary).toHaveTextContent("诊断 1 / 缺口 1 / 未支持 1");
    const boundaryRail = screen.getByTestId("stock-analysis-boundary-rail");
    expect(boundaryRail).toHaveTextContent("数据日期");
    expect(boundaryRail).toHaveTextContent("规则版本");
    expect(boundaryRail).toHaveTextContent("数据质量");
    expect(boundaryRail).toHaveTextContent("例外状态");
    expect(boundaryRail).not.toHaveTextContent("sv_livermore_test");
    expect(boundaryRail).not.toHaveTextContent("trace");
    expect(boundaryRail).not.toHaveTextContent("Breadth inputs are unavailable.");

    await user.click(screen.getByRole("button", { name: "查看完整诊断" }));

    expect(await screen.findByText("数据口径诊断")).toBeInTheDocument();
    expect(screen.getByText("警告")).toBeInTheDocument();
    expect(screen.queryByText("严重 / Error")).not.toBeInTheDocument();
    expect(screen.queryByText("警告 / Warning")).not.toBeInTheDocument();
    expect(screen.queryByText("信息 / Info")).not.toBeInTheDocument();
    expect(screen.getAllByText("市场宽度输入不可用。").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("数据缺口")).toBeInTheDocument();
    expect(screen.getByText(/输入待确认\s+状态待确认/)).toBeInTheDocument();
    expect(screen.queryAllByText(/breadth/)).toHaveLength(0);
    expect(screen.queryByText(/vendor_sync_delayed/)).not.toBeInTheDocument();
    expect(screen.queryByText(/external_vendor_factor_feed/)).not.toBeInTheDocument();
    expect(screen.getByText("可用输出")).toBeInTheDocument();
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
    expect(section).toHaveTextContent("概念归属表待确认");
    expect(section).toHaveTextContent("中");
    expect(section).toHaveTextContent("高");
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

    expect(await screen.findByRole("heading", { name: "股票分析" })).toBeInTheDocument();

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

  it("localizes strategy source-table failures without exposing backend tables", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategyError: new Error(
          "Request failed: /ui/market-data/livermore because source_table choice_stock_strategy_payload is missing.",
        ),
      }),
    });

    const errorPanel = await screen.findByTestId("stock-analysis-error-workbench");
    expect(errorPanel).toHaveTextContent("源表缺失");
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
    expect(section).not.toHaveTextContent("触发复核：2d_below_ema10");
    expect(section).not.toHaveTextContent("连续 2 日收盘低于 10 日均线");

    await userEvent.click(within(section).getAllByText("供数原因")[0]);

    expect(section).toHaveTextContent("触发复核：连续 2 日收盘低于 10 日均线");
    expect(section).not.toHaveTextContent("触发复核：2d_below_ema10");
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

    const user = userEvent.setup();
    await user.click(await screen.findByTestId("stock-analysis-supply-details-toggle"));

    const details = await screen.findByTestId("stock-analysis-decision-panel");
    const supplyRow = within(details).getByLabelText("供数首屏摘要");
    expect(supplyRow).toHaveTextContent("阻断");
    expect(supplyRow).toHaveTextContent("风险退出");
    expect(supplyRow).not.toHaveTextContent("risk_exit");
    expect(within(supplyRow).getByText("风险退出")).toHaveAttribute(
      "title",
      "持仓快照缺失，暂无可执行风险退出样本。",
    );
    expect(within(supplyRow).getByText("风险退出")).not.toHaveAttribute(
      "title",
      expect.stringContaining("livermore_position_snapshot"),
    );
    expect(supplyRow).toHaveTextContent("缺口");
    expect(within(supplyRow).getByText("持仓风险")).toHaveAttribute(
      "title",
      "持仓快照缺失，暂无可执行风险退出样本。",
    );
    expect(within(supplyRow).getByText("持仓风险")).not.toHaveAttribute(
      "title",
      expect.stringContaining("Position snapshot"),
    );
    expect(supplyRow).not.toHaveTextContent(/阻断阻断|缺口缺口/);
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

    await user.click(screen.getByText("多日强弱"));

    await waitFor(() => {
      expect(spy).toHaveBeenCalled();
    });

    await screen.findByTestId("sector-series-row-801001");
    expect(screen.getByTestId("sector-series-row-801001")).toHaveTextContent("AI");
    spy.mockRestore();
  });

  it("loads sector rank series with the resolved data date when a requested date falls back", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    const strategySpy = mockStrategyLatestSnapshotFallback(client);
    const seriesSpy = vi.spyOn(client, "getLivermoreSectorRankSeries");

    renderWorkbenchApp(["/stock-analysis"], { client });

    await requestStockAnalysisAsOfDate(user, strategySpy);
    await user.click(screen.getByText("多日强弱"));

    await waitFor(() =>
      expect(seriesSpy).toHaveBeenCalledWith(
        expect.objectContaining({ asOfDate: "2026-04-29", windowDays: 5, topK: 10 }),
      ),
    );
    expect(seriesSpy).not.toHaveBeenCalledWith(
      expect.objectContaining({ asOfDate: "2026-05-08" }),
    );
  });

  it("does not load sector rank series with only the requested date when no data date is resolved", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    const strategySpy = vi.spyOn(client, "getLivermoreStrategy").mockImplementation(async (options) =>
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
    expect(panel).toHaveTextContent("源表缺失");
    expect(panel).not.toHaveTextContent("Failed to fetch");
    expect(panel).not.toHaveTextContent("/ui/market-data/livermore/sector-rank-series");
    expect(panel).not.toHaveTextContent("source_table");
    expect(panel).not.toHaveTextContent("choice_stock_sector_rank_series");
    expect(screen.getByTestId("stock-analysis-sector-bars")).toBeInTheDocument();
  });

  it("opens stock detail drawer when 复核 K 线 is clicked", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    const spy = vi.spyOn(client, "getLivermoreStockDetail");

    renderWorkbenchApp(["/stock-analysis"], { client });

    await screen.findByTestId("stock-candidate-000001.SZ");
    await user.click(screen.getByTestId("stock-candidate-review-chart-000001.SZ"));

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

    await user.click(screen.getByTestId("stock-candidate-review-chart-000001.SZ"));

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
    const [, priorityTab] = within(analytics).getAllByRole("tab");
    await user.click(priorityTab);

    await waitFor(() =>
      expect(strategyScoreSpy).toHaveBeenCalledWith(
        expect.objectContaining({ snapshotTo: "2026-04-29", currentMarketState: "WARM" }),
      ),
    );
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

    await screen.findByTestId("stock-candidate-000001.SZ");
    await user.click(screen.getByTestId("stock-analysis-agent-open"));

    const drawer = await screen.findByTestId("stock-analysis-agent-drawer");
    expect(drawer).toBeInTheDocument();
    expect(within(drawer).getByText("复核助手")).toBeInTheDocument();
    expect(screen.queryByText("Agent 复核当前观察")).not.toBeInTheDocument();
    expect(screen.getByTestId("agent-panel")).toBeInTheDocument();

    await user.type(screen.getByTestId("agent-panel-question"), "please judge current risk");
    await user.click(screen.getByTestId("agent-panel-submit"));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [, options] = fetchMock.mock.calls[0] ?? [];
    const submitted = JSON.parse(String((options as RequestInit | undefined)?.body));
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
    const strategySpy = vi.spyOn(client, "getLivermoreStrategy").mockImplementation(async (options) =>
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

    await screen.findByTestId("stock-analysis-decision-panel");
    const picker = screen.getByTestId("stock-analysis-as-of-picker");
    const pickerInput = picker instanceof HTMLInputElement ? picker : picker.querySelector("input");
    expect(pickerInput).toBeInstanceOf(HTMLInputElement);
    await user.clear(pickerInput as HTMLInputElement);
    await user.type(pickerInput as HTMLInputElement, "2026-05-08");
    await user.keyboard("{Enter}");

    await waitFor(() => expect(strategySpy).toHaveBeenCalledWith({ asOfDate: "2026-05-08" }));
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
    const [, options] = fetchMock.mock.calls[0] ?? [];
    const submitted = JSON.parse(String((options as RequestInit | undefined)?.body));
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

    await screen.findByTestId("stock-candidate-000001.SZ");

    await user.click(screen.getByTestId("sector-filter-chip-801002"));
    await screen.findByTestId("stock-candidate-000002.SZ");

    await user.click(screen.getByTestId("stock-candidate-review-chart-000002.SZ"));
    await screen.findByTestId("stock-detail-drawer");

    await user.click(screen.getByTestId("stock-analysis-agent-open"));
    await user.type(screen.getByTestId("agent-panel-question"), "please judge current risk");
    await user.click(screen.getByTestId("agent-panel-submit"));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [, options] = fetchMock.mock.calls[0] ?? [];
    const submitted = JSON.parse(String((options as RequestInit | undefined)?.body));
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
    expect(panel).toHaveTextContent("源表缺失");
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
    expect(section).toHaveTextContent("源表缺失");
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
    expect(section).toHaveTextContent("源表缺失");
    expect(section).not.toHaveTextContent("Failed to fetch");
    expect(section).not.toHaveTextContent("source_table");
    expect(section).not.toHaveTextContent("choice_stock_strategy_score");
    expect(section).not.toHaveTextContent("/ui/market-data/livermore/strategy-score");
    const detail = within(section).getByTestId("stock-analysis-strategy-card-market-priority-detail");
    const summaryDetail = detail.querySelector(".stock-analysis-strategy-module-card__detail-line");
    expect(summaryDetail).toHaveTextContent("必需源表缺失");
    expect(summaryDetail).not.toHaveTextContent("无法连接策略分析服务");
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
    expect(card).toHaveTextContent("源表缺失");
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
