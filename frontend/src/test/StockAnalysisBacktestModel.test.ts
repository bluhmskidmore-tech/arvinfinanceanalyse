import { describe, expect, it } from "vitest";

import type {
  LivermoreCandidateHistoryHorizonStats,
  LivermoreCandidateHistoryPayload,
} from "../api/contracts";
import {
  backtestStatsText,
  buildStrategyBacktestMarketStateRows,
  buildStrategyBacktestRows,
  formatBacktestPercent,
  formatBacktestSignedPercent,
  formatCostBasisLabel,
  resolveStrategyBacktestMetricBasisLabel,
  resolveStrategyBacktestSampleCount,
  strategyBacktestHorizonLabels,
  strategyBacktestHorizonShortLabels,
  strategyBacktestHorizons,
  strategyDisplayLabel,
} from "../features/stock-analysis/lib/stockAnalysisBacktestModel";

const positiveStats: LivermoreCandidateHistoryHorizonStats = {
  available_count: 12,
  missing_count: 1,
  positive_count: 7,
  non_positive_count: 5,
  avg_return: 0.0234,
  win_rate: 0.5833,
};

const negativeStats: LivermoreCandidateHistoryHorizonStats = {
  available_count: 4,
  missing_count: 0,
  positive_count: 1,
  non_positive_count: 3,
  avg_return: -0.0123,
  win_rate: 0.25,
};

const emptyStats: LivermoreCandidateHistoryHorizonStats = {
  available_count: 0,
  missing_count: 2,
  positive_count: 0,
  non_positive_count: 0,
  avg_return: null,
  win_rate: null,
};

const executionStats: LivermoreCandidateHistoryHorizonStats = {
  available_count: 3,
  missing_count: 0,
  positive_count: 3,
  non_positive_count: 0,
  avg_return: 0.055,
  win_rate: 1,
  n: 3,
  adj_missing_n: 0,
  win: 1,
  avg: 0.055,
  median: 0.05,
  p10: 0.03,
  p90: 0.08,
};

function buildPayload(): LivermoreCandidateHistoryPayload {
  return {
    stock_code: null,
    snapshot_from: "2026-04-01",
    snapshot_to: "2026-04-29",
    limit: 50,
    items: [],
    summary: {
      row_count: 16,
      by_signal_kind: {
        stock_candidate: 12,
        factor_screen: 4,
      },
      by_signal_kind_horizon_stats: {
        stock_candidate: {
          return_1d: positiveStats,
          return_5d: negativeStats,
          return_10d: emptyStats,
          return_20d: emptyStats,
        },
        factor_screen: {
          return_1d: negativeStats,
          return_5d: positiveStats,
          return_10d: emptyStats,
          return_20d: emptyStats,
        },
        external_vendor_signal: {
          return_1d: positiveStats,
          return_5d: emptyStats,
          return_10d: emptyStats,
          return_20d: emptyStats,
        },
      },
      by_market_state_signal_kind_horizon_stats: {
        WARM: {
          stock_candidate: {
            return_1d: positiveStats,
            return_5d: negativeStats,
            return_10d: emptyStats,
            return_20d: emptyStats,
          },
        },
        CUSTOM_STATE: {
          external_vendor_signal: {
            return_1d: positiveStats,
            return_5d: emptyStats,
            return_10d: emptyStats,
            return_20d: emptyStats,
          },
        },
      },
    },
  };
}

function buildExecutionPayload(): LivermoreCandidateHistoryPayload {
  const payload = buildPayload();
  return {
    ...payload,
    summary: {
      ...payload.summary!,
      execution_usable_stats: {
        metric_basis: "net_next_open_adj",
        row_count: 3,
        execution_row_count: 4,
        entry_executable_count: 3,
        horizon_usable_stats: {
          return_1d: executionStats,
          return_5d: executionStats,
          return_10d: emptyStats,
          return_20d: emptyStats,
        },
        by_signal_kind: {
          stock_candidate: 3,
        },
        by_signal_kind_horizon_usable_stats: {
          stock_candidate: {
            return_1d: executionStats,
            return_5d: executionStats,
            return_10d: emptyStats,
            return_20d: emptyStats,
          },
        },
      },
      by_market_state_signal_kind_execution_stats: {
        HOT: {
          stock_candidate: {
            return_1d: executionStats,
            return_5d: executionStats,
            return_10d: emptyStats,
            return_20d: emptyStats,
          },
        },
      },
    },
  };
}

describe("stockAnalysisBacktestModel", () => {
  it("formats backtest rates and horizon stats without inventing missing data", () => {
    expect(formatBacktestPercent(0.4567)).toBe("45.7%");
    expect(formatBacktestPercent(null)).toBe("待补");
    expect(formatBacktestSignedPercent(0.0234)).toBe("+2.34%");
    expect(formatBacktestSignedPercent(-0.0123)).toBe("-1.23%");
    expect(formatBacktestSignedPercent(null)).toBe("待补");
    expect(backtestStatsText(positiveStats)).toBe("58.3% / +2.34% / 12条");
    expect(backtestStatsText(emptyStats)).toBe("待补");
  });

  it("uses stable strategy labels and hides external vendor strategy names", () => {
    expect(strategyDisplayLabel("stock_candidate")).toBe("趋势突破");
    expect(strategyDisplayLabel(null, "factor-screen")).toBe("多因子");
    expect(strategyDisplayLabel("external_vendor_signal")).toBe("策略待确认");
    expect(strategyDisplayLabel(null, null)).toBe("策略待确认");
  });

  it("builds ordered strategy backtest rows and sample counts from signal stats", () => {
    const rows = buildStrategyBacktestRows(buildPayload());

    expect(rows.slice(0, 3).map((row) => row.kind)).toEqual([
      "hybrid_fusion",
      "stock_candidate",
      "factor_screen",
    ]);
    expect(rows.find((row) => row.kind === "stock_candidate")).toMatchObject({
      label: "趋势突破",
      count: 12,
      stats: {
        return_1d: "58.3% / +2.34% / 12条",
        return_5d: "25.0% / -1.23% / 4条",
        return_10d: "成熟度未提供",
        return_20d: "成熟度未提供",
      },
    });
    expect(rows.find((row) => row.kind === "external_vendor_signal")?.label).toBe("策略待确认");
    expect(resolveStrategyBacktestSampleCount(buildPayload())).toBe(28);
  });

  it("labels unavailable horizons from backend maturity states instead of generic pending copy", () => {
    const payload = buildPayload();
    payload.items = [
      {
        snapshot_as_of_date: "2026-04-29",
        stock_code: "000001.SZ",
        signal_kind: null,
        candidate_rank: 1,
        selection_close: 10,
        forward_trade_date_1d: null,
        forward_trade_date_5d: null,
        forward_trade_date_20d: null,
        return_1d: null,
        return_5d: null,
        return_20d: null,
        data_status: "pending",
        forward_maturity: {
          evaluation_as_of_date: "2026-04-29",
          source_status: "available",
          classification_available: true,
          horizons: {
            "10d": { status: "natural_pending", horizon_bars: 10 },
            "20d": { status: "raw_matured_adjustment_missing", horizon_bars: 20 },
          },
        },
      },
    ];

    const row = buildStrategyBacktestRows(payload).find((item) => item.kind === "stock_candidate");
    const marketRow = buildStrategyBacktestMarketStateRows(payload).find(
      (item) => item.marketState === "WARM" && item.kind === "stock_candidate",
    );

    expect(row?.stats.return_10d).toBe("自然待成熟 · 1条");
    expect(row?.stats.return_20d).toBe("复权待补 · 1条");
    expect(marketRow?.stats.return_10d).toBe("市场状态成熟度未提供");
  });

  it("keeps mixed maturity evidence scoped to the current horizon", () => {
    const payload = buildPayload();
    payload.items = [
      {
        snapshot_as_of_date: "2026-04-29",
        stock_code: "000001.SZ",
        signal_kind: "stock_candidate",
        candidate_rank: 1,
        selection_close: 10,
        forward_trade_date_1d: null,
        forward_trade_date_5d: null,
        forward_trade_date_20d: null,
        return_1d: null,
        return_5d: null,
        return_20d: null,
        data_status: "pending",
        forward_maturity: {
          evaluation_as_of_date: "2026-04-29",
          source_status: "available",
          classification_available: true,
          horizons: {
            "10d": { status: "natural_pending", horizon_bars: 10 },
          },
        },
      },
      {
        snapshot_as_of_date: "2026-04-29",
        stock_code: "000002.SZ",
        signal_kind: "stock_candidate",
        candidate_rank: 2,
        selection_close: 11,
        forward_trade_date_1d: null,
        forward_trade_date_5d: null,
        forward_trade_date_20d: null,
        return_1d: null,
        return_5d: null,
        return_20d: null,
        data_status: "pending",
        forward_maturity: {
          evaluation_as_of_date: "2026-04-29",
          source_status: "unavailable",
          classification_available: false,
          horizons: {},
        },
      },
    ];

    const row = buildStrategyBacktestRows(payload).find((item) => item.kind === "stock_candidate");

    expect(row?.stats.return_10d).toBe("自然待成熟 1条 / 成熟分类不可用 1条");
  });

  it("does not attribute aggregate-only unsupported replay counts to every strategy row", () => {
    const payload = buildPayload();
    payload.items = [];
    payload.backtest_window_summary = {
      status: "unsupported",
      snapshot_from: "2026-04-01",
      snapshot_to: "2026-04-29",
      replay_dates_total: 3,
      replay_dates_completed: 0,
      replay_dates_pending: 0,
      replay_dates_unsupported: 3,
      replay_dates_proxy_only: 0,
      completed_rows: 0,
      pending_rows: 0,
      unsupported_rows: 30,
      proxy_only_rows: 0,
      included_completed_stats_dates: [],
      excluded_from_completed_stats_dates: ["2026-04-01", "2026-04-02", "2026-04-03"],
      date_reasons: [],
    };

    const row = buildStrategyBacktestRows(payload).find((item) => item.kind === "stock_candidate");

    expect(row?.stats.return_10d).toBe("成熟度未提供");
    expect(row?.stats.return_20d).toBe("成熟度未提供");
  });

  it("scopes replay source gaps and pending dates to the affected signal kind", () => {
    const payload = buildPayload();
    payload.items = [];
    payload.summary = {
      row_count: 0,
      by_signal_kind: {},
    };
    payload.backtest_window_summary = {
      status: "unsupported",
      snapshot_from: "2026-04-28",
      snapshot_to: "2026-04-29",
      replay_dates_total: 2,
      replay_dates_completed: 0,
      replay_dates_pending: 1,
      replay_dates_unsupported: 1,
      replay_dates_proxy_only: 0,
      completed_rows: 0,
      pending_rows: 10,
      unsupported_rows: 10,
      proxy_only_rows: 0,
      included_completed_stats_dates: [],
      excluded_from_completed_stats_dates: ["2026-04-28", "2026-04-29"],
      date_reasons: [
        {
          trade_date: "2026-04-28",
          status: "unsupported",
          reason_code: "missing_required_source_table",
          message: "missing",
          affects_completed_stats: false,
          signal_kinds: ["stock_candidate"],
        },
        {
          trade_date: "2026-04-29",
          status: "pending",
          reason_code: "forward_returns_pending",
          message: "pending",
          affects_completed_stats: false,
          signal_kinds: ["factor_screen"],
        },
      ],
    };

    const rows = buildStrategyBacktestRows(payload);

    expect(rows.find((row) => row.kind === "stock_candidate")?.stats.return_10d).toBe("历史源不足 · 1日");
    expect(rows.find((row) => row.kind === "factor_screen")?.stats.return_10d).toBe("自然待成熟 · 1日");
    expect(rows.find((row) => row.kind === "theme_breakout")?.stats.return_10d).toBe("本窗口无样本");
  });

  it("prefers execution net adjusted stats when present", () => {
    const payload = buildExecutionPayload();
    const rows = buildStrategyBacktestRows(payload);
    const marketRows = buildStrategyBacktestMarketStateRows(payload);

    expect(resolveStrategyBacktestMetricBasisLabel(payload)).toBe("T+1开盘成交·含费·复权");
    expect(resolveStrategyBacktestSampleCount(payload)).toBe(3);
    expect(rows.find((row) => row.kind === "stock_candidate")).toMatchObject({
      count: 3,
      stats: {
        return_5d: "100.0% / +5.50% / 3条",
      },
    });
    expect(marketRows.map((row) => `${row.marketState}:${row.kind}`)).toEqual(["HOT:stock_candidate"]);
    expect(marketRows[0].stats.return_5d).toBe("100.0% / +5.50% / 3条");
  });

  it("does not relabel decision or legacy aggregates as execution when execution sub-aggregates are absent", () => {
    const payload = buildExecutionPayload();
    payload.summary = {
      ...payload.summary!,
      execution_usable_stats: {
        metric_basis: "net_next_open_adj",
        row_count: 3,
      },
      by_market_state_signal_kind_execution_stats: undefined,
    };

    const rows = buildStrategyBacktestRows(payload);

    expect(resolveStrategyBacktestMetricBasisLabel(payload)).toBe("T+1开盘成交·含费·复权");
    expect(resolveStrategyBacktestSampleCount(payload)).toBe(0);
    expect(rows.find((row) => row.kind === "stock_candidate")?.count).toBe(0);
    expect(rows.find((row) => row.kind === "stock_candidate")?.stats.return_5d).not.toBe(
      "25.0% / -1.23% / 4条",
    );
    expect(buildStrategyBacktestMarketStateRows(payload)).toEqual([]);
  });

  it("builds market-state rows in governed order with discovered states appended", () => {
    const rows = buildStrategyBacktestMarketStateRows(buildPayload());

    expect(rows.map((row) => `${row.marketState}:${row.kind}`)).toEqual([
      "WARM:stock_candidate",
      "CUSTOM_STATE:external_vendor_signal",
    ]);
    expect(rows[0].stats.return_1d).toBe("58.3% / +2.34% / 12条");
    expect(rows[1].label).toBe("策略待确认");
  });

  it("formats the proxy cost basis disclosure, degrading gracefully when absent", () => {
    expect(
      formatCostBasisLabel({
        source: "core_finance.strategy_policy.POLICY",
        buy_cost_rate: 0.0005,
        sell_cost_rate: 0.0015,
        slippage_rate: 0.0005,
        round_trip_cost_rate: 0.0035,
      }),
    ).toBe("双边成本 0.35%（含双向滑点）");
    expect(formatCostBasisLabel(null)).toBeNull();
    expect(formatCostBasisLabel(undefined)).toBeNull();
  });

  it("exports horizon metadata for table rendering", () => {
    expect(strategyBacktestHorizons).toEqual(["return_1d", "return_5d", "return_10d", "return_20d"]);
    expect(strategyBacktestHorizonLabels.return_5d).toBe("T+5 胜率 / 均值 / 样本");
    expect(strategyBacktestHorizonShortLabels.return_10d).toBe("T+10");
    expect(strategyBacktestHorizonShortLabels.return_20d).toBe("T+20");
  });
});
