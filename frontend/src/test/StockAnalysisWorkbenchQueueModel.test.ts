import { describe, expect, it } from "vitest";

import type { StockAnalysisWorkbenchPayload } from "../api/contracts";
import type { StockCandidateReviewQueueItem } from "../features/stock-analysis/lib/stockAnalysisPageModel";
import {
  buildStockAnalysisWorkbenchReviewQueue,
  enrichStockAnalysisWorkbenchReviewQueue,
  mergeStockAnalysisWorkbenchThemeEvidence,
  resolveStockAnalysisFormalUseAllowed,
} from "../features/stock-analysis/lib/stockAnalysisWorkbenchQueueModel";

function buildStrategyCandidate(
  overrides: Partial<StockCandidateReviewQueueItem> = {},
): StockCandidateReviewQueueItem {
  return {
    rank: 1,
    stockCode: "000001.SZ",
    stockName: "样本股份",
    sectorCode: "801730",
    sectorName: "机械设备",
    headline: "趋势候选 #1 · 样本股份",
    pattern: "突破",
    patternNote: "趋势形态待复核。",
    distanceToBreakoutPct: "+1.20%",
    reviewFocus: "样本股份 · 机械设备 · 趋势候选",
    primaryEvidence: [{ key: "trend", label: "趋势", value: "站上 MA20" }],
    supportingEvidence: [{ key: "volume", label: "量能", value: "1.5x" }],
    boundaryEvidence: [],
    invalidationFocus: "跌破 MA20 后降级观察。",
    invalidationRules: ["跌破 MA20 后降级观察。"],
    rawFields: [{ key: "source", label: "来源", value: "stock_candidates" }],
    ...overrides,
  };
}

describe("buildStockAnalysisWorkbenchReviewQueue", () => {
  it("keeps the workbench membership and order while enriching matching strategy evidence", () => {
    const rows = [
      {
        stock_code: "000002.SZ",
        stock_name: "Queue Two",
        rank: 1,
        source_module: "factor_screen_candidates",
      },
      {
        stock_code: "000001.SZ",
        stock_name: "Queue One",
        rank: 2,
        source_module: "hybrid_fusion_candidates",
      },
    ] as StockAnalysisWorkbenchPayload["first_screen"]["review_queue"];
    const workbenchQueue = buildStockAnalysisWorkbenchReviewQueue(rows);
    const strategyQueue = [
      buildStrategyCandidate({
        rank: 8,
        rawFields: [
          { key: "source_module_key", label: "Source module", value: "hybrid_fusion_candidates" },
          { key: "fusion_score", label: "Fusion", value: "0.812345" },
        ],
      }),
      buildStrategyCandidate({ stockCode: "999999.SZ", stockName: "Not in workbench" }),
    ];

    const enriched = enrichStockAnalysisWorkbenchReviewQueue(workbenchQueue, strategyQueue);

    expect(enriched.map((item) => item.stockCode)).toEqual(["000002.SZ", "000001.SZ"]);
    expect(enriched.map((item) => item.rank)).toEqual([1, 2]);
    expect(enriched[1]).toMatchObject({
      stockName: "Queue One",
      distanceToBreakoutPct: "+1.20%",
    });
    expect(enriched[1].rawFields).toContainEqual({
      key: "fusion_score",
      label: "Fusion",
      value: "0.812345",
    });
    expect(enriched[1].boundaryEvidence).toEqual(workbenchQueue[1].boundaryEvidence);
  });


  it("does not enrich a same-code workbench row from a different source module", () => {
    const workbenchQueue = buildStockAnalysisWorkbenchReviewQueue([
      {
        stock_code: "000001.SZ",
        stock_name: "Factor row",
        source_module: "factor_screen_candidates",
      },
    ] as StockAnalysisWorkbenchPayload["first_screen"]["review_queue"]);
    const strategyQueue = [
      buildStrategyCandidate({
        rawFields: [
          { key: "source_module_key", label: "Source module", value: "hybrid_fusion_candidates" },
          { key: "fusion_score", label: "Fusion", value: "0.812345" },
        ],
      }),
    ];

    const [enriched] = enrichStockAnalysisWorkbenchReviewQueue(workbenchQueue, strategyQueue);

    expect(enriched.rawFields).not.toContainEqual({
      key: "fusion_score",
      label: "Fusion",
      value: "0.812345",
    });
  });

  it("keeps authoritative workbench rows when legacy module state marks a source as evidence-only", () => {
    const rows = [
      {
        stock_code: "600062.SH",
        stock_name: "Evidence only",
        source_module: "factor_screen_candidates",
      },
      {
        stock_code: "000001.SZ",
        stock_name: "Primary candidate",
        source_module: "fresh_trend_watchlist",
      },
    ] as StockAnalysisWorkbenchPayload["first_screen"]["review_queue"];

    const queue = buildStockAnalysisWorkbenchReviewQueue(rows);

    expect(queue.map((candidate) => candidate.stockCode)).toEqual(["600062.SH", "000001.SZ"]);
  });

  it("preserves an authoritative workbench sector name when its sector code is absent", () => {
    const workbenchQueue = buildStockAnalysisWorkbenchReviewQueue([
      {
        stock_code: "000001.SZ",
        stock_name: "样本股份",
        sector_name: "医药生物",
        source_module: "factor_screen_candidates",
      },
    ] as StockAnalysisWorkbenchPayload["first_screen"]["review_queue"]);

    const [enriched] = enrichStockAnalysisWorkbenchReviewQueue(workbenchQueue, [
      buildStrategyCandidate({ sectorCode: "801730", sectorName: "机械设备" }),
    ]);

    expect(enriched.sectorName).toBe("医药生物");
    expect(enriched.sectorCode).toBe("");
  });

  it("keeps every backend theme membership and its provenance visible", () => {
    const rows = [
      {
        stock_code: "000001.SZ",
        stock_name: "样本股份",
        sector_code: "801730",
        sector_name: "机械设备",
        rank: 2,
        source_module: "theme_breakout",
        theme_memberships: [
          {
            theme_key: "concept:C001",
            theme_name: "机器人",
            rank: 1,
            member_rank: 2,
            source_kind: "tushare_current_overlay",
          },
          {
            theme_key: "concept:C002",
            theme_name: "工业母机",
            rank: 3,
            member_rank: 1,
            source_kind: "real_concept",
          },
        ],
      },
    ] as StockAnalysisWorkbenchPayload["first_screen"]["review_queue"];

    const [candidate] = buildStockAnalysisWorkbenchReviewQueue(rows);
    const membershipEvidence = candidate.rawFields.filter((item) => item.key.startsWith("theme_membership:"));

    expect(membershipEvidence).toEqual([
      {
        key: "theme_membership:concept:C001:0",
        label: "题材归属",
        value: "机器人 #1 · 当前概念覆盖 · 成分 #2",
      },
      {
        key: "theme_membership:concept:C002:1",
        label: "题材归属",
        value: "工业母机 #3 · 时点概念成分 · 成分 #1",
      },
    ]);
    expect(candidate.primaryEvidence).toContainEqual(membershipEvidence[0]);
    expect(candidate.rawFields).toContainEqual({
      key: "source_module_key",
      label: "来源模块标识",
      value: "theme_breakout",
    });
    expect(candidate.reviewFocus).toContain("机器人");
    expect(candidate.boundaryEvidence).toContain("当前覆盖 · 非时点 · 不可历史使用 · 仅观察");
  });

  it("maps backend breakout geometry onto the pattern and distance columns", () => {
    const rows = [
      {
        stock_code: "601156.SH",
        stock_name: "东航物流",
        source_module: "factor_screen_candidates",
        pattern: "突破（参考）",
        distance_to_breakout_pct: 1.0585,
        close: 18.14,
        breakout_level: 17.95,
      },
      {
        stock_code: "601918.SH",
        stock_name: "新集能源",
        source_module: "factor_screen_candidates",
        pattern: "回踩（参考）",
        distance_to_breakout_pct: -11.4362,
        close: 9.99,
        breakout_level: 11.28,
      },
    ] as StockAnalysisWorkbenchPayload["first_screen"]["review_queue"];

    const [breakout, pullback] = buildStockAnalysisWorkbenchReviewQueue(rows);

    expect(breakout.pattern).toBe("突破（参考）");
    expect(breakout.distanceToBreakoutPct).toBe("1.06%");
    expect(breakout.patternNote).toBe("收盘 18.14 / 突破位 17.95（观察口径）");
    expect(breakout.rawFields).toContainEqual({ key: "close", label: "收盘价", value: "18.14" });
    expect(breakout.rawFields).toContainEqual({ key: "breakout_level", label: "突破位", value: "17.95" });
    expect(pullback.pattern).toBe("回踩（参考）");
    expect(pullback.distanceToBreakoutPct).toBe("-11.44%");
  });

  it("discloses a stale price anchor date for suspended candidates", () => {
    const rows = [
      {
        stock_code: "000006.SZ",
        stock_name: "停牌样本",
        source_module: "factor_screen_candidates",
        pattern: "回踩（参考）",
        distance_to_breakout_pct: -2.0,
        close: 98,
        breakout_level: 100,
        price_as_of_date: "2026-08-08",
        price_stale: true,
      },
    ] as StockAnalysisWorkbenchPayload["first_screen"]["review_queue"];

    const [candidate] = buildStockAnalysisWorkbenchReviewQueue(rows);

    expect(candidate.patternNote).toBe("收盘 98 / 突破位 100（价格日 2026-08-08，停牌滞后）");
  });

  it("keeps the placeholder when the backend pattern label is unknown or malformed", () => {
    const rows = [
      {
        stock_code: "000005.SZ",
        stock_name: "异常标签",
        source_module: "factor_screen_candidates",
        pattern: "unknown_label",
        distance_to_breakout_pct: "not-a-number",
      },
    ] as StockAnalysisWorkbenchPayload["first_screen"]["review_queue"];

    const [candidate] = buildStockAnalysisWorkbenchReviewQueue(rows);

    expect(candidate.pattern).toBe("接口未提供");
    expect(candidate.patternNote).toBe("首屏候选接口未提供形态标签，页面不补算。");
    expect(candidate.distanceToBreakoutPct).toBe("待复核");
  });

  it("does not invent theme membership evidence when the backend omits it", () => {
    const rows = [
      {
        stock_code: "000002.SZ",
        stock_name: "普通候选",
        source_module: "stock_candidates",
      },
    ] as StockAnalysisWorkbenchPayload["first_screen"]["review_queue"];

    const [candidate] = buildStockAnalysisWorkbenchReviewQueue(rows);

    expect(candidate.pattern).toBe("接口未提供");
    expect(candidate.patternNote).toBe("首屏候选接口未提供形态标签，页面不补算。");
    expect(candidate.sectorName).toBe("接口未提供");
    expect(candidate.rawFields.some((item) => item.label === "题材归属")).toBe(false);
    expect(candidate.reviewFocus).not.toContain("题材待补");
  });

  it("merges every workbench theme membership into an active strategy candidate and keeps theme-only stocks", () => {
    const rows = [
      {
        stock_code: "000001.SZ",
        stock_name: "样本股份",
        rank: 4,
        source_module: "theme_breakout",
        theme_memberships: [
          {
            theme_key: "concept:C001",
            theme_name: "机器人",
            rank: 1,
            member_rank: 2,
            source_kind: "tushare_current_overlay",
          },
          {
            theme_key: "concept:C002",
            theme_name: "工业母机",
            rank: 3,
            member_rank: 1,
            source_kind: "real_concept",
          },
        ],
      },
      {
        stock_code: "000003.SZ",
        stock_name: "主题独有",
        rank: 2,
        source_module: "theme_breakout",
        theme_memberships: [
          {
            theme_key: "concept:C003",
            theme_name: "低空经济",
            rank: 2,
            member_rank: 4,
            source_kind: "real_concept",
          },
        ],
      },
      {
        stock_code: "000004.SZ",
        stock_name: "非题材队列",
        rank: 3,
        source_module: "factor_screen_candidates",
      },
    ] as StockAnalysisWorkbenchPayload["first_screen"]["review_queue"];

    const merged = mergeStockAnalysisWorkbenchThemeEvidence([buildStrategyCandidate()], rows);
    const activeCandidate = merged[0];
    const memberships = [...activeCandidate.primaryEvidence, ...activeCandidate.supportingEvidence].filter(
      (item) => item.label === "题材归属",
    );

    expect(merged.map((item) => item.stockCode)).toEqual(["000001.SZ", "000003.SZ"]);
    expect(activeCandidate.rank).toBe(1);
    expect(memberships.map((item) => item.value)).toEqual([
      "机器人 #1 · 当前概念覆盖 · 成分 #2",
      "工业母机 #3 · 时点概念成分 · 成分 #1",
    ]);
    expect(activeCandidate.primaryEvidence.slice(0, 2)).toEqual(memberships);
    expect(activeCandidate.reviewFocus).toContain("题材归属");
    expect(activeCandidate.boundaryEvidence).toContain("当前覆盖 · 非时点 · 不可历史使用 · 仅观察");
    expect(merged[1].primaryEvidence[0]).toMatchObject({
      label: "题材归属",
      value: "低空经济 #2 · 时点概念成分 · 成分 #4",
    });
  });

  it.each([
    { payload: false, resultMeta: true },
    { payload: true, resultMeta: false },
    { payload: true, resultMeta: undefined },
  ])("keeps formal use fail-closed for conflicting or incomplete flags %#", ({ payload, resultMeta }) => {
    expect(resolveStockAnalysisFormalUseAllowed(payload, resultMeta)).toBe(false);
  });

  it("allows formal use only when both payload and result metadata explicitly allow it", () => {
    expect(resolveStockAnalysisFormalUseAllowed(true, true)).toBe(true);
  });
});
