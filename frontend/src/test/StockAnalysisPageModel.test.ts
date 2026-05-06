import { describe, expect, it } from "vitest";

import type {
  LivermoreSignalConfluencePayload,
  LivermoreStrategyPayload,
} from "../api/contracts";
import {
  buildCandidateEvidenceCards,
  buildDataBoundaryNotes,
  buildMarketStateCard,
  buildRiskExitRows,
  buildSectorRows,
} from "../features/stock-analysis/lib/stockAnalysisPageModel";

const strategyPayload: LivermoreStrategyPayload = {
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
    sector_count: 1,
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
    market_state: "WARM",
    input_stock_count: 1,
    candidate_count: 1,
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
};

const confluencePayload: LivermoreSignalConfluencePayload = {
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
      evidence: ["退出观察价来自 Livermore EMA10。"],
    },
  ],
  diagnostics: [],
  disclaimer: "Observation-only output.",
};

describe("stockAnalysisPageModel", () => {
  it("builds market state and sector rows from the Livermore strategy payload", () => {
    const card = buildMarketStateCard(strategyPayload);
    const sectors = buildSectorRows(strategyPayload);

    expect(card.title).toBe("市场状态");
    expect(card.state).toBe("WARM");
    expect(card.exposureLabel).toBe("40%");
    expect(card.passedLabel).toBe("2 / 4 条条件通过");
    expect(card.warnings.join(" ")).toContain("Breadth inputs are unavailable");
    expect(sectors[0].sectorName).toBe("AI");
    expect(sectors[0].pctChange).toBe("4.80%");
  });

  it("builds candidate evidence with counter-evidence and invalidation rules", () => {
    const cards = buildCandidateEvidenceCards(strategyPayload);

    expect(cards[0].stockCode).toBe("000001.SZ");
    expect(cards[0].headline).toContain("观察候选");
    expect(cards[0].evidence.join(" ")).toContain("行业排名第 1");
    expect(cards[0].evidence.join(" ")).toContain("收盘价 21.90");
    expect(cards[0].counterEvidence.join(" ")).toContain("基本面与估值证据未接入");
    expect(cards[0].counterEvidence.join(" ")).toContain("新闻、公告、财报事件尚未进入候选卡");
    expect(cards[0].invalidationRules.join(" ")).toContain("10EMA");
  });

  it("combines risk exits and confluence exit observations without trading labels", () => {
    const rows = buildRiskExitRows(strategyPayload, confluencePayload);

    expect(rows).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          stockCode: "000001.SZ",
          status: "triggered",
          exitWatchPrice: "10.20",
        }),
        expect.objectContaining({
          stockCode: "000777.SZ",
          status: "watch",
          exitWatchPrice: "20.10",
        }),
      ]),
    );
    expect(rows.map((row) => row.reason).join(" ")).not.toContain("卖出");
  });

  it("surfaces data boundary notes and missing evidence", () => {
    const notes = buildDataBoundaryNotes(strategyPayload);

    expect(notes.join(" ")).toContain("basis: analytical");
    expect(notes.join(" ")).toContain("breadth missing");
    expect(notes.join(" ")).toContain("rv_livermore_sector_rank_provisional_v1");
  });
});
