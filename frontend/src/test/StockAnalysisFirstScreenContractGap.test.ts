import { describe, expect, it } from "vitest";

import type { LivermoreStrategyPayload } from "../api/contracts";
import { buildCandidateReviewQueue } from "../features/stock-analysis/lib/stockAnalysisPageModel";

function primaryStockCandidatePayload(): LivermoreStrategyPayload {
  return {
    as_of_date: "2026-06-26",
    requested_as_of_date: null,
    strategy_name: "Contract snapshot",
    basis: "analytical",
    market_gate: {
      state: "WARM",
      exposure: 0.4,
      passed_conditions: 2,
      available_conditions: 2,
      required_conditions: 4,
      conditions: [],
    },
    rule_readiness: [],
    diagnostics: [],
    data_gaps: [],
    supported_outputs: ["market_gate", "stock_candidates"],
    unsupported_outputs: [],
    module_states: [
      {
        key: "stock_candidates",
        state: "ready",
        render_mode: "primary",
        source_date: "2026-06-26",
        lag_days: 0,
        threshold_days: null,
        reasons: [],
        evidence_scope: "primary",
        excludes_from_primary: false,
      },
    ],
    stock_candidates: {
      as_of_date: "2026-06-26",
      formula_version: "rv_livermore_stock_candidates_bundle_v1",
      market_state: "WARM",
      input_stock_count: 2,
      candidate_count: 2,
      excluded_stock_count: 0,
      insufficient_history_count: 0,
      items: [
        {
          rank: 2,
          stock_code: "000002.SZ",
          stock_name: "Beta Watch",
          sector_code: "801020",
          sector_name: "Software",
          sector_rank: 2,
          close: 19.8,
          breakout_level: 20,
          ema10: 19.2,
          ma20: 19,
          ma60: 18,
          ma120: 17,
          close_strength: 0.64,
          gap_norm: 0.02,
          breakout_extension_norm: -0.01,
          abnormal_turnover: 0.9,
          pe: 18,
          pb: 2.1,
          ps: 3.2,
          roe: 0.14,
          gross_margin: 0.36,
          three_month_return: 0.07,
          twelve_month_return: 0.18,
          factor_score: 0.52,
          factor_overlay_rank: 8,
        },
        {
          rank: 1,
          stock_code: "000001.SZ",
          stock_name: "Alpha Leader",
          sector_code: "801010",
          sector_name: "Banks",
          sector_rank: 1,
          close: 21.9,
          breakout_level: 21.8,
          ema10: 20.6,
          ma20: 21.05,
          ma60: 19.05,
          ma120: 16.05,
          close_strength: 0.833333,
          gap_norm: -0.114679,
          breakout_extension_norm: 0.045872,
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
      ],
    },
  };
}

describe("stock analysis first-screen contract gap", () => {
  it("snapshots buildCandidateReviewQueue key fields from the frontend-owned queue", () => {
    const queue = buildCandidateReviewQueue(primaryStockCandidatePayload());

    expect(queue).toHaveLength(2);
    expect(queue.map((item) => item.stockCode)).toEqual(["000001.SZ", "000002.SZ"]);
    expect(Object.keys(queue[0])).toEqual([
      "rank",
      "stockCode",
      "stockName",
      "sectorCode",
      "sectorName",
      "headline",
      "pattern",
      "patternNote",
      "distanceToBreakoutPct",
      "reviewFocus",
      "primaryEvidence",
      "supportingEvidence",
      "boundaryEvidence",
      "invalidationFocus",
      "invalidationRules",
      "rawFields",
    ]);
    expect(queue[0]).toMatchObject({
      rank: 1,
      stockCode: "000001.SZ",
      stockName: "Alpha Leader",
      sectorCode: "801010",
      sectorName: "Banks",
      distanceToBreakoutPct: "0.46%",
    });
    expect(queue[0].reviewFocus).toContain("Alpha Leader");
    expect(queue[0].reviewFocus).toContain("Banks");
    expect(queue[0].primaryEvidence.map((item) => item.key)).toEqual([
      "sector_rank",
      "close_vs_break",
      "ma_curve",
    ]);
    expect(queue[0].supportingEvidence.map((item) => item.key)).toEqual([
      "strength_turnover",
      "fundamental_overlay",
      "valuation",
      "quality",
      "fundamental_momentum",
      "gap_norm",
      "breakout_extension_norm",
      "ema10_watch",
    ]);
    expect(queue[0].boundaryEvidence).toHaveLength(3);
    expect(queue[0].invalidationFocus).toContain("10EMA");
    expect(queue[0].rawFields.map((item) => item.key)).toEqual([
      "ema10",
      "ma20",
      "ma60",
      "ma120",
      "abnormal_turnover",
      "gap_norm",
      "breakout_extension_norm",
      "close_strength",
      "factor_score",
      "factor_overlay_rank",
      "pe",
      "pb",
      "ps",
      "roe",
      "gross_margin",
    ]);
  });
});
