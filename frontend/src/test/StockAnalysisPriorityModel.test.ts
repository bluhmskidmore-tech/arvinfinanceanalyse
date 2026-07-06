import { describe, expect, it } from "vitest";

import type {
  LivermoreCandidateHistoryPayload,
  LivermoreStrategyScorePayload,
  LivermoreStrategyScoreRow,
} from "../api/contracts";
import {
  buildStrategyMaturityCandidates,
  buildStrategyMaturityWindow,
  buildStrategyPriorityHeadline,
  formatPriorityScore,
  localizeRankRangeLabel,
  resolvePanelQueryState,
  resolveStrategyMaturityRow,
  strategyCandidateReturnText,
  strategyMaturityHorizonText,
  strategyMaturityRemainingText,
  strategyPriorityDiagnosticLabels,
  strategyPriorityReasonLabel,
  strategyPriorityScopeLabel,
  strategyPriorityStatusLabel,
  strategyPrioritySummaryReason,
  strategyRiskFlagLabel,
} from "../features/stock-analysis/lib/stockAnalysisPriorityModel";

const horizonStats = {
  available_count: 8,
  missing_count: 1,
  positive_count: 5,
  non_positive_count: 3,
  avg_return: 0.018,
  win_rate: 0.625,
};

const pendingStats = {
  available_count: 0,
  missing_count: 4,
  positive_count: 0,
  non_positive_count: 0,
  avg_return: null,
  win_rate: null,
  status: "pending",
} as const;

const trackedSnapshot = {
  snapshot_as_of_date: "2026-04-29",
  candidate_count: 12,
  horizons: {
    return_1d: { ...horizonStats, status: "complete" },
    return_5d: { ...horizonStats, status: "partial" },
    return_10d: pendingStats,
    return_20d: pendingStats,
  },
};

function buildPriorityRow(overrides: Partial<LivermoreStrategyScoreRow> = {}): LivermoreStrategyScoreRow {
  return {
    market_state: "WARM",
    signal_kind: "stock_candidate",
    strategy_label: "stock_candidate",
    sample_status: "sufficient",
    priority_score: 72.34,
    priority_rank: 1,
    priority_label: "优先复核",
    reason: "T+5 sample 20, avg return +2.3%, win rate 62.5%, priority review ranking.",
    stats: {
      return_1d: horizonStats,
      return_5d: horizonStats,
      return_10d: pendingStats,
      return_20d: pendingStats,
    },
    ...overrides,
  };
}

const scorePayloadRows: LivermoreStrategyScorePayload["rows"] = [
  buildPriorityRow({
    diagnostics: {
      priority_scope: "rank<=10",
      priority_scope_label: "rank 1-10",
      priority_scope_stats: {
        return_1d: horizonStats,
        return_5d: horizonStats,
        return_10d: pendingStats,
        return_20d: pendingStats,
      },
      maturity: {
        status: "narrow",
        label: "成熟样本偏窄",
        reason: "waiting for more mature days",
        min_mature_snapshot_count: 5,
        mature_snapshot_count: 3,
        snapshot_stats: [],
        tracked_snapshots: [trackedSnapshot],
        worst_snapshot: null,
      },
      rank_buckets: [
        {
          label: "rank 11-20",
          rank_from: 11,
          rank_to: 20,
          sample_status: "sufficient",
          priority_label: "降权观察",
          included_in_priority: false,
          reason: "lower bucket",
          stats: {
            return_1d: horizonStats,
            return_5d: horizonStats,
            return_10d: pendingStats,
            return_20d: pendingStats,
          },
        },
      ],
      risk_flags: [
        {
          kind: "long_window_risk",
          label: "long_window_risk",
          reason: "risk",
        },
        {
          kind: "vendor",
          label: "external_vendor_risk",
          reason: "vendor",
        },
      ],
    },
  }),
  buildPriorityRow({
    signal_kind: "factor_screen",
    strategy_label: "factor_screen",
    priority_label: "降权观察",
    priority_rank: 2,
  }),
];

const candidateHistoryPayload: LivermoreCandidateHistoryPayload = {
  stock_code: null,
  snapshot_from: "2026-04-01",
  snapshot_to: "2026-04-29",
  limit: 50,
  summary: null,
  items: [
    {
      snapshot_as_of_date: "2026-04-29",
      stock_code: "000003.SZ",
      stock_name: "Gamma",
      signal_kind: "stock_candidate",
      candidate_rank: 11,
      selection_close: 11,
      forward_trade_date_1d: null,
      forward_trade_date_5d: null,
      forward_trade_date_20d: null,
      return_1d: null,
      return_5d: null,
      return_20d: null,
      data_status: "pending",
    },
    {
      snapshot_as_of_date: "2026-04-29",
      stock_code: "000001.SZ",
      stock_name: "Alpha",
      signal_kind: "stock_candidate",
      candidate_rank: 2,
      selection_close: 21,
      forward_trade_date_1d: null,
      forward_trade_date_5d: null,
      forward_trade_date_20d: null,
      return_1d: 0.012,
      return_5d: -0.01,
      return_20d: null,
      data_status: "complete",
    },
    {
      snapshot_as_of_date: "2026-04-28",
      stock_code: "000002.SZ",
      stock_name: "Beta",
      signal_kind: "stock_candidate",
      candidate_rank: 1,
      selection_close: 18,
      forward_trade_date_1d: null,
      forward_trade_date_5d: null,
      forward_trade_date_20d: null,
      return_1d: 0.02,
      return_5d: 0.03,
      return_20d: 0.04,
      data_status: "complete",
    },
  ],
};

describe("stockAnalysisPriorityModel", () => {
  it("formats priority scores, query state, headline, and reason copy", () => {
    expect(formatPriorityScore(72.34)).toBe("72.3");
    expect(formatPriorityScore(null)).toBe("-");
    expect(resolvePanelQueryState({ enabled: false, isLoading: false, isError: false })).toBe("idle");
    expect(resolvePanelQueryState({ enabled: true, isLoading: true, isError: false })).toBe("loading");
    expect(resolvePanelQueryState({ enabled: true, isLoading: false, isError: true })).toBe("error");
    expect(resolvePanelQueryState({ enabled: true, isLoading: false, isError: false })).toBe("ready");
    expect(buildStrategyPriorityHeadline(scorePayloadRows)).toBe("当前状态降权观察");
    expect(
      buildStrategyPriorityHeadline([
        buildPriorityRow({
          diagnostics: {
            priority_scope: "rank<=10",
            priority_scope_label: "rank 1-10",
            maturity: {
              status: "narrow",
              label: "成熟样本偏窄",
              reason: "waiting for more mature days",
              min_mature_snapshot_count: 5,
              mature_snapshot_count: 3,
              snapshot_stats: [],
              tracked_snapshots: [trackedSnapshot],
              worst_snapshot: null,
            },
            rank_buckets: [],
            risk_flags: [],
          },
        }),
      ]),
    ).toBe("优先观察：趋势突破");
    expect(strategyPrioritySummaryReason(scorePayloadRows)).toContain("T+5 样本 20");
    expect(strategyPriorityReasonLabel(scorePayloadRows[0])).toContain("优先复核");
  });

  it("accepts enriched strategy family metadata without changing priority copy", () => {
    const enrichedRows = scorePayloadRows.map((row) => ({
      ...row,
      family_key: row.signal_kind === "stock_candidate" ? "trend_core" : row.signal_kind,
      family_label: row.signal_kind === "stock_candidate" ? "Trend core" : row.strategy_label,
      family_contract_version: "rv_livermore_strategy_family_contract_v1",
      primary_sample_size: row.stats.return_5d.available_count,
      family_readiness: {
        readiness_contract_version: "rv_livermore_strategy_family_readiness_v1",
        readiness_state: "degraded_observation",
        macro_context_id: "macroctx_unit",
        market_gate_context_id: null,
        macro_compatibility: "compatible",
        market_gate_compatibility: "unknown",
        data_readiness: "ready",
        sample_maturity: "insufficient",
        readiness_reasons: ["OBSERVATION_ONLY_BOUNDARY"],
        observational_only: true,
        formal_use_allowed: false,
      },
    }));

    expect(buildStrategyPriorityHeadline(enrichedRows)).toBe(buildStrategyPriorityHeadline(scorePayloadRows));
    expect(strategyPrioritySummaryReason(enrichedRows)).toBe(strategyPrioritySummaryReason(scorePayloadRows));
    expect(strategyPriorityReasonLabel(enrichedRows[0])).toBe(strategyPriorityReasonLabel(scorePayloadRows[0]));
  });

  it("localizes rank, scope, risk, and status labels without leaking vendor codes", () => {
    expect(localizeRankRangeLabel("rank 11-20")).toBe("第 11-20 名");
    expect(localizeRankRangeLabel(null, 21, 30)).toBe("第 21-30 名");
    expect(strategyPriorityScopeLabel("external_vendor_scope")).toBe("排序范围待确认");
    expect(strategyPriorityScopeLabel("rank 1-10")).toBe("rank 1-10");
    expect(strategyRiskFlagLabel("long_window_risk")).toBe("长窗口风险");
    expect(strategyRiskFlagLabel("source_table missing")).toBe("风险待确认");
    expect(strategyPriorityStatusLabel("优先复核")).toBe("优先复核");
    expect(strategyPriorityStatusLabel("external_vendor_status")).toBe("状态待确认");
  });

  it("builds diagnostic labels and maturity status copy", () => {
    const labels = strategyPriorityDiagnosticLabels(scorePayloadRows[0]);

    expect(labels).toContain("rank 1-10 62.5% / +1.80% / 8条");
    expect(labels).toContain("成熟样本偏窄 waiting for more mature days");
    expect(labels).toContain("第 11-20 名 降权观察");
    expect(labels).toContain("长窗口风险");
    expect(labels).not.toContain("external_vendor_risk");

    const maturity = scorePayloadRows[0].diagnostics?.maturity;
    expect(maturity && strategyMaturityRemainingText(maturity)).toBe("还差 2 个成熟快照");
    expect(strategyMaturityHorizonText(trackedSnapshot, "return_1d")).toBe("T+1 已成熟 62.5% / +1.80% / 8条");
    expect(strategyMaturityHorizonText(trackedSnapshot, "return_5d")).toBe("T+5 部分成熟 62.5% / +1.80% / 8条");
    expect(strategyMaturityHorizonText(trackedSnapshot, "return_20d")).toBe("T+20 待成熟");
    expect(strategyCandidateReturnText(0.012)).toBe("+1.20%");
    expect(strategyCandidateReturnText(null)).toBe("待成熟");
  });

  it("selects maturity rows and filters maturity candidates by snapshot, signal kind, and rank scope", () => {
    const row = resolveStrategyMaturityRow(scorePayloadRows);
    const candidates = buildStrategyMaturityCandidates(
      candidateHistoryPayload,
      row,
      row?.diagnostics?.maturity?.tracked_snapshots ?? [],
    );

    expect(row?.signal_kind).toBe("stock_candidate");
    expect(candidates.map((candidate) => candidate.stock_code)).toEqual(["000001.SZ"]);
  });

  it("builds the maturity detail query window from the most recent tracked snapshots", () => {
    const snapshots = Array.from({ length: 8 }, (_, index) => ({
      ...trackedSnapshot,
      snapshot_as_of_date: `2026-04-${String(20 + index).padStart(2, "0")}`,
    }));

    const window = buildStrategyMaturityWindow({ ...scorePayloadRows[0], diagnostics: {
      ...scorePayloadRows[0].diagnostics!,
      maturity: {
        ...scorePayloadRows[0].diagnostics!.maturity!,
        tracked_snapshots: snapshots,
      },
    } });

    expect(window.snapshots.map((snapshot) => snapshot.snapshot_as_of_date)).toEqual([
      "2026-04-27",
      "2026-04-26",
      "2026-04-25",
      "2026-04-24",
      "2026-04-23",
      "2026-04-22",
    ]);
    expect(window.snapshotFrom).toBe("2026-04-22");
    expect(window.snapshotTo).toBe("2026-04-27");
    expect(buildStrategyMaturityWindow(null)).toEqual({
      maturity: null,
      snapshots: [],
      snapshotFrom: null,
      snapshotTo: null,
    });
  });
});
