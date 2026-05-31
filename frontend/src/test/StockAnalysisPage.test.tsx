import { screen, waitFor, within } from "@testing-library/react";
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
        reason: "T+5 已成熟快照 2/4，等待更多成熟日。",
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
          reason: "T+5 样本 30，均值 +2.33%，胜率 66.7%，优先复核排序。",
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
  candidateHistoryPortfolioBacktest?: LivermoreCandidateHistoryPortfolioBacktestPayload;
  cycleProxyBacktest?: LivermoreCycleProxyBacktestPayload;
  strategyScore?: LivermoreStrategyScorePayload;
  strategyOptimization?: LivermoreStrategyOptimizationPayload;
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
    getLivermoreCandidateHistory: async (): Promise<ApiEnvelope<LivermoreCandidateHistoryPayload>> =>
      buildMockApiEnvelope(
        "market_data.livermore.candidate_history",
        options?.candidateHistory ?? buildCandidateHistoryPayload(),
      ),
    getLivermoreCandidateHistoryPortfolioBacktest: async (): Promise<
      ApiEnvelope<LivermoreCandidateHistoryPortfolioBacktestPayload>
    > =>
      buildMockApiEnvelope(
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
      ),
    getLivermoreCycleProxyBacktest: async (): Promise<ApiEnvelope<LivermoreCycleProxyBacktestPayload>> =>
      buildMockApiEnvelope(
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
      ),
    getLivermoreStrategyScore: async (): Promise<ApiEnvelope<LivermoreStrategyScorePayload>> =>
      buildMockApiEnvelope(
        "market_data.livermore.strategy_score",
        options?.strategyScore ?? buildStrategyScorePayload(),
      ),
    getLivermoreStrategyOptimization: async (): Promise<ApiEnvelope<LivermoreStrategyOptimizationPayload>> =>
      buildMockApiEnvelope(
        "market_data.livermore.strategy_optimization",
        options?.strategyOptimization ?? buildStrategyOptimizationPayload(),
      ),
  };
}

describe("StockAnalysisPage", () => {
  it("marks the backend-supply cockpit without changing the stock data path", async () => {
    renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });

    const page = await screen.findByTestId("stock-analysis-page");
    expect(page.querySelector(".stock-analysis-page")).toHaveAttribute("data-layout-rev", "2026-05-16b");
    expect(page.querySelector(".stock-analysis-page")).toHaveAttribute("data-data-viz-rev", "2026-05-16c");
    const cockpit = await screen.findByTestId("stock-analysis-tailwind-cockpit");
    expect(cockpit.className).toContain("bg-white");
    expect(cockpit).toHaveTextContent("后端供数");
    expect(cockpit).toHaveTextContent("门控 WARM");
    expect(cockpit).toHaveTextContent("条件 2/4");
    expect(cockpit).toHaveTextContent("缺口 1");
    expect(cockpit).toHaveTextContent("阻断 0");
    expect(cockpit).not.toHaveTextContent("TAILWIND");

    const workbench = await screen.findByTestId("stock-analysis-first-screen-workbench");
    expect(workbench).toHaveTextContent("板块供数");
    expect(workbench).toHaveTextContent("规则就绪");
    expect(workbench).toHaveTextContent("输出可用");
    expect(workbench).toHaveTextContent("风险供数");
    expect(workbench).not.toHaveTextContent("多策略共振");
    expect(workbench).toHaveTextContent("复核队列");
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

    expect(css).toContain("@media (min-width: 901px)");
    expect(css).toContain(
      '.workbench-shell-grid--desktop-aligned:has([data-testid="stock-analysis-page"])',
    );
    expect(css).toContain('[data-testid="workbench-section-subnav"]');
    expect(css).toContain('[data-testid="workbench-governance-banner"]');
  });

  it("surfaces backend supply status and keeps review work out of the first screen", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({ metaOverrides: { quality_flag: "warning" } }),
    });

    const decisionPanel = await screen.findByTestId("stock-analysis-decision-panel");
    expect(decisionPanel).toHaveTextContent("后端供数");
    expect(decisionPanel).toHaveTextContent("门控 WARM");
    expect(decisionPanel).toHaveTextContent("暴露 40%");
    expect(decisionPanel).toHaveTextContent("就绪 0/1");
    expect(decisionPanel).toHaveTextContent("可用 4");
    expect(decisionPanel).toHaveTextContent("阻断 0");
    expect(decisionPanel).toHaveTextContent("质量 warning");

    const supplyStatus = await screen.findByTestId("stock-analysis-backend-supply-status");
    expect(supplyStatus).toHaveTextContent("Market gate");
    expect(supplyStatus).toHaveTextContent("partial");
    expect(supplyStatus).toHaveTextContent("breadth");

    const workbench = await screen.findByTestId("stock-analysis-first-screen-workbench");
    expect(workbench).toHaveTextContent("候选 2");
    expect(workbench).toHaveTextContent("持仓 1");
    expect(workbench).toHaveTextContent("触发 1");
    expect(workbench).toHaveTextContent("观察 1");
    expect(workbench).not.toHaveTextContent("先复核 Alpha");

    const queue = await screen.findByTestId("stock-analysis-review-queue");
    expect(queue).toHaveTextContent("复核队列");
    expect(queue).toHaveTextContent("为什么先看");
    expect(queue).toHaveTextContent("反证与待补");
    expect(queue).toHaveTextContent("失效条件");
    expect(queue).toHaveTextContent("复核 K 线");
  });

  it("renders core sections and candidate evidence", async () => {
    renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });

    expect(await screen.findByRole("heading", { name: "股票分析" })).toBeInTheDocument();
    expect(await screen.findByTestId("stock-analysis-decision-panel")).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "板块强弱" })).toBeInTheDocument();
    expect(await screen.findByTestId("stock-analysis-page-purpose")).toHaveTextContent("股票策略复核台");
    expect(await screen.findByTestId("stock-analysis-deep-zone")).toHaveTextContent("供数闭环");
    expect(await screen.findByRole("heading", { name: "题材突变观察" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "复核队列" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "风险退出观察" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "数据口径与边界" })).toBeInTheDocument();

    const candidate = screen.getByTestId("stock-candidate-000001.SZ");
    expect(candidate).toHaveTextContent("Alpha");
    expect(candidate).toHaveTextContent("行业排名第 1");
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
    expect(framework).toHaveTextContent("CycleScore");
    expect(framework).toHaveTextContent("Macro direction");
    expect(framework).toHaveTextContent("PMI");
    expect(framework).toHaveTextContent("industry cap 25%");
    expect(framework).toHaveTextContent("证据待齐");
    expect(within(framework).getByTestId("stock-analysis-candidate-history-portfolio-backtest")).toHaveTextContent("组合回测");
    expect(within(framework).getByTestId("stock-analysis-cycle-proxy-backtest")).toHaveTextContent("代理回测");
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
                reason: "Review-only proxy cluster missed selection: strong rows 2 below gate 3.",
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
    expect(section).toHaveTextContent("Semiconductor proxy");
    expect(section).toHaveTextContent("Electronic #9");
    expect(section).toHaveTextContent("代理题材观察");
    expect(section).toHaveTextContent("Alpha Semiconductor");
    expect(screen.getByTestId("stock-analysis-theme-evidence-state")).toHaveTextContent("catalog_unconfirmed");
    expect(screen.getByTestId("stock-analysis-theme-review-items")).toHaveTextContent("insufficient_cluster_strength");
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

    expect(await screen.findByText("Factor Alpha")).toBeInTheDocument();
    expect(screen.getByText("600000.SH")).toBeInTheDocument();
    expect(screen.getAllByText(/因子数据覆盖 643\/5201 只/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("得分 0.812")).toBeInTheDocument();

    const page = screen.getByTestId("stock-analysis-page");
    expect(page).not.toHaveTextContent("买入");
    expect(page).not.toHaveTextContent("卖出");
    expect(page).not.toHaveTextContent("下单");
    expect(page).not.toHaveTextContent("调仓指令");
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

    const decisionPanel = await screen.findByTestId("stock-analysis-decision-panel");
    expect(decisionPanel).toHaveTextContent("质量 ok");
    expect(decisionPanel).toHaveTextContent("回退 latest_snapshot");
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
    expect(verdict).toHaveTextContent("保持仅观察输出");
    expect(decisionPanel).toHaveTextContent("供数明细与闭环");
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).toHaveTextContent("门控 WARM");
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).not.toHaveTextContent("今日市场状态");
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).not.toHaveTextContent("闭环阻断，先复核约束项");
    expect(summary).toHaveTextContent("拦截");
    expect(summary).toHaveTextContent("阻断");
    expect(summary).toHaveTextContent("已触发");
    expect(summary).toHaveTextContent("降级");
    expect(summary).toHaveTextContent("crowded leaders without breadth confirmation");
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
    expect(verdict).toHaveTextContent("先补齐宏观反拥挤");
    expect(decisionPanel).toHaveTextContent("供数明细与闭环");
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).toHaveTextContent("门控 WARM");
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).not.toHaveTextContent("今日市场状态");
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).not.toHaveTextContent("证据不足，不形成有效观察结论");
    expect(summary).toHaveTextContent("数据不足");
    expect(summary).toHaveTextContent("待补");
    expect(summary).toHaveTextContent("不能视为中性证明");
    expect(summary).toHaveTextContent("latest_snapshot");
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
    expect(verdict).toHaveTextContent("保留观察队列");
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).toHaveTextContent("门控 WARM");
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).not.toHaveTextContent("暂缓复核，存在降级边界");
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).not.toHaveTextContent("今日市场状态");
    expect(summary).toHaveTextContent("暂缓");
    expect(summary).toHaveTextContent("降级");
    expect(summary).toHaveTextContent("仍有降级或仅观察边界");
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
    await waitFor(() => expect(replayStatus).toHaveTextContent("2026-04-30"), {
      timeout: 3_000,
    });
    expect(replayStatus).toHaveTextContent("missing_daily_limit_flags");
    expect(replayStatus).toHaveTextContent("2026-05-08");
    expect(replayStatus).toHaveTextContent("forward_returns_pending");
    expect(replayStatus).toHaveTextContent("2026-05-07");
    expect(replayStatus).toHaveTextContent("proxy_theme_only");
    expect(replayStatus).toHaveTextContent("completed zero-signal dates: 2026-05-06");
    expect(replayStatus).toHaveTextContent("do not infer strategy efficacy");
    expect(replayStatus).toHaveTextContent("completed dates 1");
    expect(replayStatus).toHaveTextContent("pending dates 1");
    expect(replayStatus).toHaveTextContent("unsupported dates 1");
    expect(replayStatus).toHaveTextContent("proxy-only dates 1");
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

    await user.click(screen.getByRole("button", { name: "全部行业" }));
    await screen.findByTestId("stock-candidate-000001.SZ");
    expect(screen.getByRole("button", { name: "全部行业" })).toHaveAttribute("aria-pressed", "true");
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
    expect(screen.getByText("该行业暂无候选复核项，可切换到其他行业复核。")).toBeInTheDocument();
  });

  it("connects the boundary summary to the full diagnostics drawer", async () => {
    const user = userEvent.setup();
    renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });

    const decisionPanel = await screen.findByTestId("stock-analysis-decision-panel");
    expect(decisionPanel).toHaveTextContent("边界");

    const boundarySummary = screen.getByTestId("stock-analysis-boundary-summary");
    expect(boundarySummary).toHaveTextContent("2 条边界");
    expect(boundarySummary).toHaveTextContent("诊断 1 / 缺口 1 / 未支持 0");
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
    expect(screen.getByText("警告 / Warning")).toBeInTheDocument();
    expect(screen.getAllByText("Breadth inputs are unavailable.").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("data_gaps")).toBeInTheDocument();
    expect(screen.getAllByText(/breadth/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("supported_outputs")).toBeInTheDocument();
    expect(screen.getByText("unsupported_outputs")).toBeInTheDocument();
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

    expect(await screen.findByText("股票分析结果加载失败。")).toBeInTheDocument();
    expect(screen.getByText("strategy unavailable")).toBeInTheDocument();
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
    expect(within(section).getByText("风险退出观察暂不可用。")).toBeInTheDocument();
    expect(
      within(section).getByText("livermore_position_snapshot has no ACTIVE A-share rows."),
    ).toBeInTheDocument();
  });

  it("surfaces blocked backend outputs in the first-screen supply strip", async () => {
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

    const workbench = await screen.findByTestId("stock-analysis-first-screen-workbench");
    expect(workbench).toHaveTextContent("阻断 1");
    expect(workbench).toHaveTextContent("风险退出");
    expect(workbench).not.toHaveTextContent("risk_exit");
    expect(workbench).toHaveTextContent("持仓风险");
    expect(workbench).not.toHaveTextContent("position_risk");
    expect(workbench).toHaveTextContent("缺口 1");
  });

  it("loads sector rank series when multi-day collapse opens", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    const spy = vi.spyOn(client, "getLivermoreSectorRankSeries");

    renderWorkbenchApp(["/stock-analysis"], { client });

    expect(await screen.findByTestId("stock-analysis-sector-bars")).toBeInTheDocument();
    expect(spy).not.toHaveBeenCalled();

    await user.click(screen.getByText("多日累计强度（窗口聚合）"));

    await waitFor(() => {
      expect(spy).toHaveBeenCalled();
    });

    await screen.findByTestId("sector-series-row-801001");
    expect(screen.getByTestId("sector-series-row-801001")).toHaveTextContent("AI");
    spy.mockRestore();
  });

  it("shows sector series failure alert without breaking sector bars", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    vi.spyOn(client, "getLivermoreSectorRankSeries").mockRejectedValue(new Error("series fetch failed"));

    renderWorkbenchApp(["/stock-analysis"], { client });

    expect(await screen.findByTestId("stock-analysis-sector-bars")).toBeInTheDocument();
    await user.click(screen.getByText("多日累计强度（窗口聚合）"));

    expect(await screen.findByText("多日板块序列加载失败")).toBeInTheDocument();
    expect(screen.getByText("series fetch failed")).toBeInTheDocument();
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

  it("opens Agent drawer and submits page_context.page_id stock-analysis + filters", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    const fetchMock = vi.fn().mockResolvedValueOnce(buildJsonResponse(buildStockAgentResult()));
    vi.stubGlobal("fetch", fetchMock);

    renderWorkbenchApp(["/stock-analysis"], { client });

    await screen.findByTestId("stock-candidate-000001.SZ");
    await user.click(screen.getByTestId("stock-analysis-agent-open"));

    expect(await screen.findByTestId("stock-analysis-agent-drawer")).toBeInTheDocument();
    expect(screen.getByText("Agent 复核当前观察")).toBeInTheDocument();
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
    expect(panel).toHaveTextContent(/已完成日计胜率/);
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
    expect(factorRow.getByText("11-20 降权观察")).toBeInTheDocument();

    const trendRow = within(screen.getByTestId("stock-analysis-market-priority-row-OVERHEAT-stock_candidate"));
    expect(trendRow.getByText("长窗口风险")).toBeInTheDocument();
    expect(summary).toHaveTextContent("优先观察：多因子");
    expect(summary).not.toHaveTextContent("优先复核：多因子、趋势突破");
    expect(summary).toHaveTextContent("样本偏窄");
    expect(summary).toHaveTextContent("T+5 已成熟快照 2/4");
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

  it("shows the T+5 optimization diagnosis without turning it into trading rules", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({
        strategy: buildStrategyPayload({
          market_gate: {
            ...buildStrategyPayload().market_gate,
            state: "HOT",
          },
        }),
        strategyOptimization: buildStrategyOptimizationPayload(),
      }),
    });

    const card = await screen.findByTestId("stock-analysis-strategy-optimization");
    await waitFor(() => expect(card).toHaveTextContent("多因子"), { timeout: 3_000 });
    expect(card).toHaveTextContent("三策略 T+5 排名");
    expect(card).toHaveTextContent("多因子");
    expect(card).toHaveTextContent("优先复核");
    expect(card).toHaveTextContent("题材突变");
    expect(card).toHaveTextContent("样本不足");
    expect(card).toHaveTextContent("rank 21-30");
    expect(card).toHaveTextContent("降权观察");
    expect(card).toHaveTextContent("最新 pending 日期 2026-05-13");
    expect(card).toHaveTextContent("建议只用于复核排序，不自动改交易规则");
    expect(card).not.toHaveTextContent("买入");
    expect(card).not.toHaveTextContent("下单");
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
        reason: "当前状态样本不足：T+5 可用样本 6/20，仅作观察。",
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
    expect(summary).toHaveTextContent("当前状态样本不足");
    expect(summary).toHaveTextContent("样本不足");
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

    const marketStateTable = await screen.findByTestId("stock-analysis-strategy-backtest-market-state");
    expect(marketStateTable).toHaveTextContent(/市场状态/);
    expect(marketStateTable).toHaveTextContent(/策略/);

    const warmRow = within(screen.getByTestId("stock-analysis-strategy-backtest-market-state-WARM-stock_candidate"));
    expect(warmRow.getByText(/WARM/)).toBeInTheDocument();
    expect(warmRow.getByText("趋势突破")).toBeInTheDocument();
    expect(warmRow.getByText("75.0% / +3.21% / 12条")).toBeInTheDocument();
    expect(warmRow.getByText("50.0% / -1.11% / 4条")).toBeInTheDocument();

    const hotRow = within(screen.getByTestId("stock-analysis-strategy-backtest-market-state-HOT-factor_screen"));
    expect(hotRow.getByText(/HOT/)).toBeInTheDocument();
    expect(hotRow.getByText("多因子")).toBeInTheDocument();
    expect(hotRow.getByText("25.0% / -2.10% / 8条")).toBeInTheDocument();
    expect(hotRow.getByText("50.0% / +1.40% / 6条")).toBeInTheDocument();
  });
});
