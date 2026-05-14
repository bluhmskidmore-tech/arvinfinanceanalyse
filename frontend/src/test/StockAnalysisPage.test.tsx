import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { createApiClient, type ApiClient } from "../api/client";
import type {
  ApiEnvelope,
  ConfluenceReplayStatus,
  LivermoreCandidateHistoryPayload,
  LivermoreSignalConfluencePayload,
  LivermoreStrategyScorePayload,
  LivermoreStrategyPayload,
} from "../api/contracts";
import { buildMockApiEnvelope } from "../mocks/mockApiEnvelope";
import { renderWorkbenchApp } from "./renderWorkbenchApp";

vi.mock("../components/charts/BaseChart", () => ({
  BaseChart: function MockBaseChart() {
    return <div data-testid="stock-detail-chart-canvas-stub" />;
  },
}));

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

function buildCandidateHistoryPayload(): LivermoreCandidateHistoryPayload {
  return {
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

function stockClient(options?: {
  strategy?: LivermoreStrategyPayload;
  strategyError?: Error;
  confluence?: LivermoreSignalConfluencePayload;
  confluenceError?: Error;
  candidateHistory?: LivermoreCandidateHistoryPayload;
  strategyScore?: LivermoreStrategyScorePayload;
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
    getLivermoreStrategyScore: async (): Promise<ApiEnvelope<LivermoreStrategyScorePayload>> =>
      buildMockApiEnvelope(
        "market_data.livermore.strategy_score",
        options?.strategyScore ?? buildStrategyScorePayload(),
      ),
  };
}

describe("StockAnalysisPage", () => {
  it("puts the decision summary and review queue on the first analysis surface", async () => {
    renderWorkbenchApp(["/stock-analysis"], {
      client: stockClient({ metaOverrides: { quality_flag: "warning" } }),
    });

    const decisionPanel = await screen.findByTestId("stock-analysis-decision-panel");
    expect(decisionPanel).toHaveTextContent("今日判断");
    expect(decisionPanel).toHaveTextContent("今日市场状态：进攻");
    expect(decisionPanel).toHaveTextContent("门控 2/4");
    expect(decisionPanel).toHaveTextContent("观察暴露 40%");
    expect(decisionPanel).toHaveTextContent("最强 AI");
    expect(decisionPanel).toHaveTextContent("最弱 新能源车");
    expect(decisionPanel).toHaveTextContent("数据需复核 warning / ok");
    expect(decisionPanel).toHaveTextContent("先复核 Alpha");
    expect(decisionPanel).toHaveTextContent("边界");

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
    expect(await screen.findByRole("heading", { name: "题材突变雷达" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "复核队列" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "风险退出观察" })).toBeInTheDocument();
    expect(await screen.findByRole("heading", { name: "数据口径与边界" })).toBeInTheDocument();

    const candidate = screen.getByTestId("stock-candidate-000001.SZ");
    expect(candidate).toHaveTextContent("Alpha");
    expect(candidate).toHaveTextContent("行业排名第 1");
    expect(candidate).toHaveTextContent("10EMA 失效观察");
    expect(candidate).toHaveTextContent("基本面与估值证据未接入");
    expect(candidate).toHaveTextContent("新闻、公告、财报事件尚未进入候选卡");
    expect(candidate).toHaveTextContent("10EMA");
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
    expect(section).toHaveTextContent("题材突变雷达");
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

    await user.click(await screen.findByText(/多因子选股/));

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
    expect(decisionPanel).toHaveTextContent("数据需复核 ok / ok / fallback latest_snapshot");
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
    expect(verdict).toHaveTextContent("可复核");
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
    expect(verdict).toHaveTextContent("拦截");
    expect(verdict).toHaveTextContent("闭环阻断，先复核约束项");
    expect(verdict).toHaveTextContent("保持仅观察输出");
    expect(decisionPanel).toHaveTextContent("闭环结论优先");
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).toHaveTextContent("闭环阻断，先复核约束项");
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).not.toHaveTextContent("今日市场状态");
    expect(decisionPanel).not.toHaveTextContent("先复核 Alpha");
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
    expect(decisionPanel).toHaveTextContent("闭环结论优先");
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).toHaveTextContent("证据不足，不形成有效观察结论");
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).not.toHaveTextContent("今日市场状态");
    expect(decisionPanel).not.toHaveTextContent("先复核 Alpha");
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
    expect(verdict).toHaveTextContent("暂缓");
    expect(verdict).toHaveTextContent("暂缓复核，存在降级边界");
    expect(verdict).toHaveTextContent("保留观察队列");
    expect(within(decisionPanel).getByRole("heading", { level: 1 })).toHaveTextContent("暂缓复核，存在降级边界");
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
    expect(replayStatus).toHaveTextContent("2026-04-30");
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
    const queryAgentSpy = vi.spyOn(client, "queryAgent");

    renderWorkbenchApp(["/stock-analysis"], { client });

    await screen.findByTestId("stock-candidate-000001.SZ");
    await user.click(screen.getByTestId("stock-analysis-agent-open"));

    expect(await screen.findByTestId("stock-analysis-agent-drawer")).toBeInTheDocument();
    expect(screen.getByText("Agent 复核当前观察")).toBeInTheDocument();
    expect(screen.getByTestId("agent-panel")).toBeInTheDocument();

    await user.type(screen.getByTestId("agent-panel-question"), "请简述当前快照门控摘要");
    await user.click(screen.getByTestId("agent-panel-submit"));

    await waitFor(() => expect(queryAgentSpy).toHaveBeenCalled());
    const submitted = queryAgentSpy.mock.calls[0]?.[0];
    expect(submitted?.page_context?.page_id).toBe("stock-analysis");
    expect(submitted?.page_context?.current_filters).toMatchObject({
      as_of_date: "2026-04-29",
      sector_filter: null,
      sector_filter_label: null,
      sector_view: "score",
      current_view: "decision",
    });
    expect(Array.isArray(submitted?.page_context?.selected_rows)).toBe(true);
    expect(submitted?.page_context?.selected_rows ?? []).toEqual([]);
    queryAgentSpy.mockRestore();
  });

  it("reflects sector filter and drawer selection in Agent page_context", async () => {
    const user = userEvent.setup();
    const client = stockClient();
    const queryAgentSpy = vi.spyOn(client, "queryAgent");

    renderWorkbenchApp(["/stock-analysis"], { client });

    await screen.findByTestId("stock-candidate-000001.SZ");

    await user.click(screen.getByTestId("sector-filter-chip-801002"));
    await screen.findByTestId("stock-candidate-000002.SZ");

    await user.click(screen.getByTestId("stock-candidate-review-chart-000002.SZ"));
    await screen.findByTestId("stock-detail-drawer");

    await user.click(screen.getByTestId("stock-analysis-agent-open"));
    await user.type(screen.getByTestId("agent-panel-question"), "复核当前截面数据质量");
    await user.click(screen.getByTestId("agent-panel-submit"));

    await waitFor(() => expect(queryAgentSpy).toHaveBeenCalled());
    const submitted = queryAgentSpy.mock.calls[0]?.[0];
    expect(submitted?.page_context?.current_filters?.sector_filter).toBe("801002");
    expect(submitted?.page_context?.current_filters?.sector_filter_label).toBe("新能源车");
    expect(submitted?.page_context?.current_filters?.sector_view).toBe("score");
    expect(submitted?.page_context?.current_filters?.current_view).toBe("stock_detail");
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
    expect(submitted?.filters).toEqual({ research_domain: "stock" });
    queryAgentSpy.mockRestore();
  });

  it("renders strategy replay rows from legacy per-strategy horizon stats", async () => {
    renderWorkbenchApp(["/stock-analysis"], { client: stockClient() });

    const trend = within(await screen.findByTestId("stock-analysis-strategy-backtest-stock_candidate"));
    const panel = screen.getByTestId("stock-analysis-strategy-backtest");
    expect(panel).toHaveTextContent(/策略回溯表现/);
    expect(panel).toHaveTextContent(/仅使用已完成回溯日期计算胜率/);
    expect(panel).toHaveTextContent(/有效样本/);
    expect(panel).toHaveTextContent(/180 条/);
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
      }),
    });

    const summary = await screen.findByTestId("stock-analysis-market-priority-summary");
    await waitFor(() => expect(summary).toHaveTextContent("优先复核"));
    await screen.findByTestId("stock-analysis-market-priority-row-OVERHEAT-factor_screen");
    expect(summary).toHaveTextContent("当前市场策略优先级");
    expect(summary).toHaveTextContent("OVERHEAT");
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

    const page = screen.getByTestId("stock-analysis-page");
    expect(page).not.toHaveTextContent("买入");
    expect(page).not.toHaveTextContent("卖出");
    expect(page).not.toHaveTextContent("下单");
    expect(page).not.toHaveTextContent("调仓");
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
    await waitFor(() => expect(summary).toHaveTextContent("当前状态样本不足"));
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

    const stockCandidateRow = await screen.findByTestId("stock-analysis-strategy-backtest-stock_candidate");
    expect(stockCandidateRow).toHaveTextContent("75.0% / +3.21% / 12条");
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
