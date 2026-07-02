import { describe, expect, it } from "vitest";

import type {
  LivermoreCandidateHistoryHorizonStats,
  LivermoreStrategyOptimizationPayload,
  LivermoreStrategyOptimizationRecommendation,
} from "../api/contracts";
import {
  buildStrategyOptimizationRows,
  strategyOptimizationDateWeightedText,
  strategyOptimizationPrimaryStats,
  strategyOptimizationReasonLabel,
  strategyOptimizationSliceLabel,
  strategyOptimizationSlicePair,
} from "../features/stock-analysis/lib/stockAnalysisOptimizationModel";

const positiveStats: LivermoreCandidateHistoryHorizonStats = {
  available_count: 24,
  missing_count: 1,
  positive_count: 15,
  non_positive_count: 9,
  avg_return: 0.0265,
  win_rate: 0.625,
};

const fallbackStats: LivermoreCandidateHistoryHorizonStats = {
  available_count: 12,
  missing_count: 0,
  positive_count: 4,
  non_positive_count: 8,
  avg_return: -0.0088,
  win_rate: 0.3333,
};

function buildRecommendation(
  action: LivermoreStrategyOptimizationRecommendation["action"],
  overrides: Partial<LivermoreStrategyOptimizationRecommendation> = {},
): LivermoreStrategyOptimizationRecommendation {
  return {
    action,
    priority_label:
      action === "promote" ? "优先复核" : action === "downgrade" ? "降权观察" : "继续观察",
    reason: "T+5 sample 24, avg return +2.65%, win rate 62.5%, priority review ranking.",
    primary_horizon: "return_10d",
    available_count: 24,
    min_sample: 20,
    avg_return: 0.0265,
    win_rate: 0.625,
    score: 70,
    ...overrides,
  };
}

function buildPayload(): LivermoreStrategyOptimizationPayload {
  const baseDateWeightedStats = {
    return_5d: {
      available_day_count: 0,
      candidate_row_count: 0,
      avg_return: null,
      positive_day_rate: null,
      worst_day_return: null,
      best_day_return: null,
    },
    return_10d: {
      available_day_count: 6,
      candidate_row_count: 24,
      avg_return: 0.0175,
      positive_day_rate: 0.6667,
      worst_day_return: -0.012,
      best_day_return: 0.043,
    },
  };

  return {
    as_of_date: "2026-04-29",
    snapshot_from: "2026-04-01",
    snapshot_to: "2026-04-29",
    primary_horizon: "return_10d",
    min_sample: 20,
    current_market_state: "WARM",
    strategy_summaries: [
      {
        summary_key: "vendor",
        signal_kind: "external_vendor_signal",
        strategy_label: "external_vendor_signal",
        sample_status: "sufficient",
        stats: { return_10d: positiveStats, return_5d: fallbackStats },
        date_weighted_stats: baseDateWeightedStats,
        recommendation: buildRecommendation("promote", { score: 99 }),
      },
      {
        summary_key: "stock",
        signal_kind: "stock_candidate",
        strategy_label: "stock_candidate",
        sample_status: "sufficient",
        stats: { return_10d: positiveStats, return_5d: fallbackStats },
        date_weighted_stats: baseDateWeightedStats,
        recommendation: buildRecommendation("promote", { score: 88 }),
      },
      {
        summary_key: "factor",
        signal_kind: "factor_screen",
        strategy_label: "factor_screen",
        sample_status: "sufficient",
        stats: { return_5d: fallbackStats },
        date_weighted_stats: {
          return_5d: baseDateWeightedStats.return_5d,
        },
        recommendation: buildRecommendation("observe", { avg_return: null, score: 50 }),
      },
      {
        summary_key: "mean",
        signal_kind: "mean_reversion",
        strategy_label: "mean_reversion",
        sample_status: "sufficient",
        stats: { return_10d: positiveStats, return_5d: fallbackStats },
        date_weighted_stats: baseDateWeightedStats,
        recommendation: buildRecommendation("promote", { score: 77 }),
      },
    ],
    slices: [
      {
        slice_key: "pending",
        signal_kind: "stock_candidate",
        strategy_label: "stock_candidate",
        dimension: "rank",
        bucket: "1-10",
        label: "rank 1-10",
        sample_status: "insufficient",
        stats: { return_10d: positiveStats, return_5d: fallbackStats },
        date_weighted_stats: baseDateWeightedStats,
        recommendation: buildRecommendation("pending_more_history", { score: 100 }),
      },
      {
        slice_key: "strong",
        signal_kind: "stock_candidate",
        strategy_label: "stock_candidate",
        dimension: "rank",
        bucket: "1-10",
        label: "rank 1-10",
        sample_status: "sufficient",
        stats: { return_10d: positiveStats, return_5d: fallbackStats },
        date_weighted_stats: baseDateWeightedStats,
        recommendation: buildRecommendation("promote", { score: 81, avg_return: 0.03 }),
      },
      {
        slice_key: "weak",
        signal_kind: "factor_screen",
        strategy_label: "factor_screen",
        dimension: "rank",
        bucket: "21-30",
        label: "rank 21-30",
        sample_status: "sufficient",
        stats: { return_5d: fallbackStats },
        date_weighted_stats: {
          return_5d: baseDateWeightedStats.return_5d,
        },
        recommendation: buildRecommendation("downgrade", { score: 30, avg_return: -0.025 }),
      },
      {
        slice_key: "vendor",
        signal_kind: "stock_candidate",
        strategy_label: "stock_candidate",
        dimension: "external_vendor_bucket",
        bucket: "external_vendor_a",
        label: "external_vendor_a",
        sample_status: "sufficient",
        stats: { return_10d: positiveStats, return_5d: fallbackStats },
        date_weighted_stats: baseDateWeightedStats,
        recommendation: buildRecommendation("observe", { score: 35, avg_return: -0.005 }),
      },
    ],
    recommendations: [],
    pending_summary: {
      primary_horizon: "return_10d",
      pending_rows: 0,
      pending_dates: [],
      latest_pending_date: null,
      message: "ready",
    },
    sample_maturity: null,
  };
}

describe("stockAnalysisOptimizationModel", () => {
  it("keeps optimization rows on governed core strategies before vendor or non-core summaries", () => {
    expect(buildStrategyOptimizationRows(buildPayload()).map((row) => row.summary_key)).toEqual([
      "stock",
      "factor",
    ]);
    expect(buildStrategyOptimizationRows(null)).toEqual([]);
  });

  it("accepts enriched strategy family metadata without changing optimization rows", () => {
    const payload = buildPayload();
    const enrichedPayload: LivermoreStrategyOptimizationPayload = {
      ...payload,
      strategy_summaries: payload.strategy_summaries.map((row) => ({
        ...row,
        family_key: row.signal_kind === "stock_candidate" ? "trend_core" : row.signal_kind,
        family_label: row.strategy_label,
        family_contract_version: "rv_livermore_strategy_family_contract_v1",
        primary_sample_size: row.stats[payload.primary_horizon]?.available_count ?? null,
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
      })),
      slices: payload.slices.map((row) => ({
        ...row,
        family_key: row.signal_kind === "stock_candidate" ? "trend_core" : row.signal_kind,
        family_label: row.strategy_label,
        family_contract_version: "rv_livermore_strategy_family_contract_v1",
        primary_sample_size: row.stats[payload.primary_horizon]?.available_count ?? null,
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
      })),
      recommendations: [
        {
          ...buildRecommendation("promote"),
          target_type: "strategy",
          target_key: "stock",
          signal_kind: "stock_candidate",
          label: "stock_candidate",
          family_key: "trend_core",
          family_label: "Trend core",
          family_contract_version: "rv_livermore_strategy_family_contract_v1",
          primary_sample_size: 24,
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
        },
      ],
    };

    expect(buildStrategyOptimizationRows(enrichedPayload).map((row) => row.summary_key)).toEqual(
      buildStrategyOptimizationRows(payload).map((row) => row.summary_key),
    );
    const enrichedPair = strategyOptimizationSlicePair(enrichedPayload);
    const basePair = strategyOptimizationSlicePair(payload);
    expect(enrichedPair.strongest?.slice_key).toBe(basePair.strongest?.slice_key);
    expect(enrichedPair.weakest?.slice_key).toBe(basePair.weakest?.slice_key);
  });

  it("formats primary horizon stats and date-weighted maturity without inventing unavailable data", () => {
    const [stockRow, factorRow] = buildStrategyOptimizationRows(buildPayload());

    expect(strategyOptimizationPrimaryStats(stockRow, buildPayload())).toBe(positiveStats);
    expect(strategyOptimizationPrimaryStats(factorRow, buildPayload())).toBe(fallbackStats);
    expect(strategyOptimizationDateWeightedText(stockRow, buildPayload())).toBe(
      "6日等权 +1.75% / 正收益日 66.7%",
    );
    expect(strategyOptimizationDateWeightedText(factorRow, buildPayload())).toBe("待补");
    expect(strategyOptimizationReasonLabel(stockRow)).toContain("优先复核");
  });

  it("localizes slice labels and excludes immature slices from strongest or weakest selection", () => {
    const pair = strategyOptimizationSlicePair(buildPayload());

    expect(pair.strongest?.slice_key).toBe("strong");
    expect(pair.weakest?.slice_key).toBe("weak");
    expect(strategyOptimizationSliceLabel(pair.strongest!)).toBe("第 1-10 名");
    expect(strategyOptimizationSliceLabel(pair.weakest!)).toBe("第 21-30 名");
    expect(strategyOptimizationSliceLabel(buildPayload().slices[3])).toBe("切片待确认");
    expect(strategyOptimizationSlicePair(null)).toEqual({ strongest: null, weakest: null });
  });
});
