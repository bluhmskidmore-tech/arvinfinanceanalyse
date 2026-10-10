import { describe, expect, it } from "vitest";

import {
  buildConsensusDetailSelection,
  buildFactorScreenDetailSelection,
  buildMeanReversionDetailSelection,
  buildRankContextDetailSelection,
  buildReviewQueueDetailSelection,
  buildRiskExitDetailSelection,
  buildStockDetailReviewContext,
  STOCK_DETAIL_SOURCE_VALUES,
  type StockDetailSelection,
} from "../features/stock-analysis/lib/stockAnalysisDetailSelection";

describe("stockAnalysisDetailSelection", () => {
  it("keeps the stock detail source values stable", () => {
    expect(STOCK_DETAIL_SOURCE_VALUES).toEqual([
      "review_queue",
      "risk_exit",
      "mean_reversion",
      "factor_screen",
      "hybrid_fusion",
      "consensus",
      "sector_constituent",
      "theme_breakout",
      "livermore",
      "fresh_trend_watchlist",
      "source_unconfirmed",
    ]);
  });

  it("allows rank metadata for drawer context selections", () => {
    const selection: StockDetailSelection = {
      code: "600000.SH",
      name: "Sample Bank",
      source: "hybrid_fusion",
      reviewRank: 1,
      livermoreRank: null,
      meanReversionRank: 3,
      factorScreenRank: 2,
      hybridFusionRank: 1,
    };

    expect(selection.source).toBe("hybrid_fusion");
    expect(selection.hybridFusionRank).toBe(1);
  });

  it("maps consensus candidates into detail drawer selections", () => {
    expect(
      buildConsensusDetailSelection({
        stockCode: "600000.SH",
        stockName: "Sample Bank",
        sectorName: "Banking",
        livermoreRank: 4,
        meanReversionRank: null,
        factorScreenRank: 2,
        hybridFusionRank: 1,
      }),
    ).toEqual({
      code: "600000.SH",
      name: "Sample Bank",
      sectorName: "Banking",
      source: "consensus",
      livermoreRank: 4,
      meanReversionRank: null,
      factorScreenRank: 2,
      hybridFusionRank: 1,
    });
  });

  it("maps review queue candidates with the active queue rank basis", () => {
    const card = {
      stockCode: "600000.SH",
      stockName: "Sample Bank",
      rank: 5,
      sectorCode: "BK001",
      sectorName: "Banking",
      distanceToBreakoutPct: "2.4%",
      reviewFocus: "Sample Bank · Banking · 距观察位 2.4%",
      primaryEvidence: [{ key: "turnover", label: "量比", value: "1.8x" }],
      supportingEvidence: [{ key: "breadth", label: "扩散", value: "行业扩散 3/5" }],
      boundaryEvidence: ["仅作观察与复核，不作为执行依据。", "公告催化尚未核实，边界待复核。"],
      invalidationFocus: "跌回 MA20 下方即降级观察。",
      invalidationRules: ["跌回 MA20 下方即降级观察。"],
    };
    const ranks = {
      livermoreRank: 8,
      meanReversionRank: null,
      factorScreenRank: 3,
      hybridFusionRank: 2,
    };

    expect(
      buildReviewQueueDetailSelection({
        card,
        ranks,
        reviewQueueUsesHybridFusion: false,
      }),
    ).toMatchObject({
      code: "600000.SH",
      source: "review_queue",
      reviewRank: 5,
      livermoreRank: 5,
      hybridFusionRank: 2,
    });

    expect(
      buildReviewQueueDetailSelection({
        card,
        ranks,
        reviewQueueUsesHybridFusion: true,
      }),
    ).toMatchObject({
      code: "600000.SH",
      source: "review_queue",
      reviewRank: 5,
      livermoreRank: 8,
      hybridFusionRank: 5,
      reviewThesis: {
        whySelected: ["Sample Bank · Banking · 距观察位 2.4%", "量比：1.8x", "扩散：行业扩散 3/5"],
        boundaries: ["公告催化尚未核实，边界待复核。"],
        invalidation: ["跌回 MA20 下方即降级观察。"],
        nextActions: ["看 K 线确认价格与量能", "查公告/新闻确认边界", "确认失效条件后再继续观察"],
      },
    });
  });

  it("keeps every explicit theme membership visible in review detail selection", () => {
    const selection = buildReviewQueueDetailSelection({
      card: {
        stockCode: "600000.SH",
        stockName: "Sample Bank",
        rank: 1,
        sectorCode: "BK001",
        sectorName: "Banking",
        distanceToBreakoutPct: "1.2%",
        reviewFocus: "Sample Bank · Banking",
        primaryEvidence: [
          { label: "趋势", value: "站上 MA20" },
          {
            label: "题材归属",
            value: "机器人 #1 · 当前概念覆盖 · 成分 #2",
          },
        ],
        supportingEvidence: [
          {
            label: "题材归属",
            value: "工业母机 #3 · 时点概念成分 · 成分 #1",
          },
        ],
        boundaryEvidence: ["当前覆盖 · 非时点 · 不可历史使用 · 仅观察"],
        invalidationFocus: "跌回 MA20 下方即降级观察。",
        invalidationRules: ["跌回 MA20 下方即降级观察。"],
      },
      ranks: {
        livermoreRank: 1,
        meanReversionRank: null,
        factorScreenRank: null,
        hybridFusionRank: null,
      },
      reviewQueueUsesHybridFusion: false,
    });

    expect(selection.reviewThesis?.whySelected).toEqual(
      expect.arrayContaining([
        "题材归属：机器人 #1 · 当前概念覆盖 · 成分 #2",
        "题材归属：工业母机 #3 · 时点概念成分 · 成分 #1",
      ]),
    );
    expect(selection.reviewThesis?.boundaries).toContain("当前覆盖 · 非时点 · 不可历史使用 · 仅观察");
  });

  it("maps risk exit rows into detail drawer selections", () => {
    expect(
      buildRiskExitDetailSelection({
        row: {
          stockCode: "600000.SH",
          stockName: "Sample Bank",
        },
        ranks: {
          livermoreRank: 8,
          meanReversionRank: null,
          factorScreenRank: 3,
          hybridFusionRank: 2,
        },
      }),
    ).toEqual({
      code: "600000.SH",
      name: "Sample Bank",
      source: "risk_exit",
      livermoreRank: 8,
      meanReversionRank: null,
      factorScreenRank: 3,
      hybridFusionRank: 2,
    });
  });

  it("maps mean reversion rows into detail drawer selections", () => {
    expect(
      buildMeanReversionDetailSelection({
        row: {
          stock_code: "600000.SH",
          stock_name: "Sample Bank",
          rank: 6,
          sector_code: "BK001",
          sector_name: "Banking",
        },
        ranks: {
          livermoreRank: 8,
          meanReversionRank: null,
          factorScreenRank: 3,
          hybridFusionRank: 2,
        },
      }),
    ).toEqual({
      code: "600000.SH",
      name: "Sample Bank",
      sectorCode: "BK001",
      sectorName: "Banking",
      source: "mean_reversion",
      livermoreRank: 8,
      meanReversionRank: 6,
      factorScreenRank: 3,
      hybridFusionRank: 2,
    });
  });

  it("maps factor screen rows into detail drawer selections and falls back to industry name", () => {
    expect(
      buildFactorScreenDetailSelection({
        row: {
          stock_code: "600000.SH",
          stock_name: "Sample Bank",
          rank: 7,
          sector_code: "BK001",
          industry: "Banking",
        },
        ranks: {
          livermoreRank: 8,
          meanReversionRank: null,
          factorScreenRank: 3,
          hybridFusionRank: 2,
        },
      }),
    ).toEqual({
      code: "600000.SH",
      name: "Sample Bank",
      sectorCode: "BK001",
      sectorName: "Banking",
      source: "factor_screen",
      livermoreRank: 8,
      meanReversionRank: null,
      factorScreenRank: 7,
      hybridFusionRank: 2,
    });
  });

  it("maps stock rows with strategy rank context into detail drawer selections", () => {
    expect(
      buildRankContextDetailSelection({
        stockCode: "600000.SH",
        stockName: "Sample Bank",
        sectorCode: "BK001",
        sectorName: "Banking",
        source: "source_unconfirmed",
        ranks: {
          livermoreRank: 8,
          meanReversionRank: null,
          factorScreenRank: 3,
          hybridFusionRank: 2,
        },
      }),
    ).toEqual({
      code: "600000.SH",
      name: "Sample Bank",
      sectorCode: "BK001",
      sectorName: "Banking",
      source: "source_unconfirmed",
      livermoreRank: 8,
      meanReversionRank: null,
      factorScreenRank: 3,
      hybridFusionRank: 2,
    });

    const context = buildStockDetailReviewContext({
      code: "600000.SH",
      source: "source_unconfirmed",
    });
    expect(context).toMatchObject({
      sourceLabel: "来源待确认",
    });
    expect(context?.sourceLabel).not.toBe("复核队列");
  });

  it("builds stock detail drawer review context from a selection", () => {
    expect(
      buildStockDetailReviewContext({
        code: "600000.SH",
        name: "Sample Bank",
        sectorName: "Banking",
        reviewRank: 5,
        distanceToBreakoutPct: "2.4%",
        source: "factor_screen",
        livermoreRank: 8,
        meanReversionRank: null,
        factorScreenRank: 7,
        hybridFusionRank: 2,
      }),
    ).toEqual({
      sourceLabel: "多因子选股",
      sectorName: "Banking",
      reviewRank: 5,
      distanceToBreakoutPct: "2.4%",
      livermoreRank: 8,
      meanReversionRank: null,
      factorScreenRank: 7,
      hybridFusionRank: 2,
      reviewThesis: undefined,
    });

    expect(buildStockDetailReviewContext(null)).toBeNull();
  });
});
