import { describe, expect, it } from "vitest";

import type {
  LivermoreSignalConfluencePayload,
  LivermoreStrategyPayload,
} from "../api/contracts";
import {
  buildCandidateReviewQueue,
  buildCandidateEvidenceCards,
  buildDataBoundarySummary,
  buildDecisionSummary,
  buildDailyJudgmentStrip,
  buildDataBoundaryNotes,
  buildMarketStateCard,
  buildRiskExitRows,
  buildSectorRows,
  buildSectorFilterSummary,
  buildSectorViewModel,
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
    sector_count: 2,
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
      {
        rank: 2,
        sector_code: "801002",
        sector_name: "新能源车",
        score: 0.5,
        avg_pctchange: -1.2,
        avg_turn: 5,
        avg_amplitude: 2,
        constituent_count: 20,
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
      evidence: ["风险观察价来自 Livermore EMA10。"],
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
    expect(card.passedLabel).toBe("2 / 4 条件通过");
    expect(card.warnings.join(" ")).toContain("Breadth inputs are unavailable");
    expect(sectors[0].sectorName).toBe("AI");
    expect(sectors[0].pctChange).toBe("4.80%");
  });

  it("builds candidate evidence with counter-evidence and invalidation rules", () => {
    const cards = buildCandidateEvidenceCards(strategyPayload);

    expect(cards[0].stockCode).toBe("000001.SZ");
    expect(cards[0].headline).toContain("观察候选");
    expect(cards[0].pattern).toBe("突破");
    expect(cards[0].distanceToBreakoutPct).toMatch(/%/);
    expect(cards[0].evidence.join(" ")).toContain("行业排名第 1");
    expect(cards[0].evidence.join(" ")).toContain("收盘价 21.90");
    expect(cards[0].evidence.join(" ")).toContain("10EMA 失效观察");
    expect(cards[0].counterEvidence.join(" ")).toContain("基本面与估值证据未接入");
    expect(cards[0].counterEvidence.join(" ")).toContain("新闻、公告、财报事件尚未进入候选卡");
    expect(cards[0].invalidationRules.join(" ")).toContain("10EMA");
    expect(cards[0].invalidationRules.join(" ")).toContain("涨跌停状态");
    expect(cards[0].rawFields.some((row) => row.key === "gap_norm")).toBe(true);
  });

  it("builds a decision summary and review queue without inventing unavailable evidence", () => {
    const summary = buildDecisionSummary(strategyPayload, {
      quality_flag: "warning",
      vendor_status: "ok",
    });
    const queue = buildCandidateReviewQueue(strategyPayload);

    expect(summary.headline).toContain("今日市场状态：进攻");
    expect(summary.gateLabel).toBe("门控 2/4");
    expect(summary.exposureLabel).toBe("观察暴露 40%");
    expect(summary.dataFreshnessLabel).toBe("数据需复核 warning / ok");
    expect(summary.nextReviewAction).toContain("先复核 Alpha");
    expect(summary.nextReviewAction).toContain("距观察位");
    expect(summary.boundaryLabel).toContain("2 条边界");
    expect(queue[0].reviewFocus).toContain("Alpha");
    expect(queue[0].primaryEvidence.map((item) => item.key)).toEqual([
      "sector_rank",
      "close_vs_break",
      "ma_curve",
    ]);
    expect(queue[0].boundaryEvidence.join(" ")).toContain("基本面与估值证据未接入");
    expect(queue[0].invalidationFocus).toContain("10EMA");
    expect(queue[0].reviewFocus).not.toContain("买入");
  });

  it("treats fallback snapshots as data that needs review", () => {
    const summary = buildDecisionSummary(strategyPayload, {
      quality_flag: "ok",
      vendor_status: "ok",
      fallback_mode: "latest_snapshot",
    });

    expect(summary.dataFreshnessLabel).toBe("数据需复核 ok / ok / fallback latest_snapshot");
  });

  it("keeps the decision summary honest when candidates are unavailable", () => {
    const summary = buildDecisionSummary(
      {
        ...strategyPayload,
        stock_candidates: {
          ...strategyPayload.stock_candidates!,
          candidate_count: 0,
          items: [],
        },
        unsupported_outputs: [
          {
            key: "stock_candidates",
            reason: "choice_stock_daily_observation is not landed.",
          },
        ],
      },
      { quality_flag: "ok", vendor_status: "ok" },
    );

    expect(summary.candidateCountLabel).toBe("候选 0");
    expect(summary.nextReviewAction).toBe("暂无候选股，先核对门控、板块强弱和数据边界。");
    expect(summary.boundaryLabel).toContain("3 条边界");
    expect(summary.nextReviewAction).not.toContain("Alpha");
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
    const watch = rows.find((r) => r.stockCode === "000777.SZ");
    expect(watch?.distanceToExitPct).toContain("%");
    expect(watch?.exitDistanceBucket === "triggered" || watch?.exitDistanceBucket === "0-3%").toBe(true);
  });

  it("surfaces data boundary notes and missing evidence", () => {
    const notes = buildDataBoundaryNotes(strategyPayload);

    expect(notes.join(" ")).toContain("basis: analytical");
    expect(notes.join(" ")).toContain("breadth missing");
    expect(notes.join(" ")).toContain("LIVERMORE_BREADTH_MISSING");
    expect(notes.join(" ")).toContain("rv_livermore_sector_rank_provisional_v1");
  });

  it("builds daily judgment strip with sector poles", () => {
    const strip = buildDailyJudgmentStrip(strategyPayload);
    expect(strip.headline).toContain("今日市场状态");
    expect(strip.gateChip).toContain("2/4");
    expect(strip.strongestSectorChip).toContain("AI");
    expect(strip.weakestSectorChip).toContain("新能源车");
  });

  it("orders sector view model by selected metric without changing payload", () => {
    const byScore = buildSectorViewModel(strategyPayload, "score");
    expect(byScore[0].sectorName).toBe("AI");
    const byPct = buildSectorViewModel(strategyPayload, "pctchange");
    expect(byPct[0].sectorName).toBe("AI");
    const byTurn = buildSectorViewModel(strategyPayload, "turnover");
    expect(byTurn[0].sectorName).toBe("新能源车");
  });

  it("flags top and bottom sector rows for charting", () => {
    const rows = buildSectorRows(strategyPayload);
    const top = rows.find((r) => r.sectorCode === "801001");
    const bottom = rows.find((r) => r.sectorCode === "801002");
    expect(top?.isTop).toBe(true);
    expect(bottom?.isBottom).toBe(true);
    expect(typeof top?.scoreNormalized).toBe("number");
  });

  it("builds a boundary summary from existing payload evidence only", () => {
    const summary = buildDataBoundarySummary(
      {
        ...strategyPayload,
        unsupported_outputs: [
          {
            key: "risk_exit",
            reason: "position snapshot not landed",
          },
        ],
      },
      {
        quality_flag: "warning",
        vendor_status: "ok",
        fallback_mode: "latest_snapshot",
      },
    );

    expect(summary.boundaryCount).toBe(3);
    expect(summary.diagnosticsCount).toBe(1);
    expect(summary.dataGapCount).toBe(1);
    expect(summary.unsupportedCount).toBe(1);
    expect(summary.freshnessLabel).toBe("新鲜度 warning / ok / 回退 latest_snapshot");
    expect(summary.summaryLabel).toBe("3 条边界");
    expect(summary.detailLabel).toContain("诊断 1 / 缺口 1 / 未支持 1");
    expect(summary.topMessages.join(" ")).toContain("Breadth inputs are unavailable.");
    expect(summary.topMessages.join(" ")).toContain("position snapshot not landed");
  });

  it("builds current sector filter status for review queue stitching", () => {
    const filtered = buildSectorFilterSummary(strategyPayload, "801001");
    const unfiltered = buildSectorFilterSummary(strategyPayload, null);

    expect(filtered.isFiltered).toBe(true);
    expect(filtered.sectorLabel).toBe("AI");
    expect(filtered.visibleCount).toBe(1);
    expect(filtered.totalCount).toBe(1);
    expect(filtered.summaryLabel).toContain("sector AI (801001)");

    expect(unfiltered.isFiltered).toBe(false);
    expect(unfiltered.sectorLabel).toBe("all sectors");
    expect(unfiltered.summaryLabel).toBe("sector all sectors / showing 1 of 1");
  });

});
