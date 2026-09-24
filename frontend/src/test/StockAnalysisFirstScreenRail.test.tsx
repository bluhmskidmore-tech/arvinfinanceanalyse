import { render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { StockAnalysisFirstScreenRail } from "../features/stock-analysis/components/StockAnalysisFirstScreenRail";
import type { StockCandidateReviewQueueItem } from "../features/stock-analysis/lib/stockAnalysisPageModel";
import type { StockDataGapOverview } from "../features/stock-analysis/lib/stockAnalysisFirstScreenModel";

function buildCandidate(
  overrides: Partial<StockCandidateReviewQueueItem> = {},
): StockCandidateReviewQueueItem {
  return {
    rank: 1,
    stockCode: "000001.SZ",
    stockName: "平安银行",
    sectorCode: "801780",
    sectorName: "银行",
    headline: "趋势候选 #1 · 平安银行",
    pattern: "突破",
    patternNote: "量价结构已返回。",
    distanceToBreakoutPct: "+1.2%",
    reviewFocus: "核实催化后再确认候选状态。",
    primaryEvidence: [],
    supportingEvidence: [],
    boundaryEvidence: [],
    invalidationFocus: "跌回 MA20 下方即降级观察。",
    invalidationRules: ["跌回 MA20 下方即降级观察。"],
    rawFields: [],
    ...overrides,
  };
}

const emptyGapOverview: StockDataGapOverview = {
  activeGaps: [],
  blockingGaps: [],
  missingCount: 0,
  partialCount: 0,
  countLabel: "0 项缺口",
  primaryGapLabel: "无未闭合缺口",
  maxStaleAgeDays: null,
  maxStaleAgeFamilyLabel: null,
};

describe("StockAnalysisFirstScreenRail", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("renders the same stock from two source modules without duplicate React keys", () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    // 后端 review_queue 按 (source_module, stock_code) 去重：同一股票可在
    // 趋势候选与多因子候选各占一行，且都携带模块内 rank=1。
    const candidates = [
      buildCandidate({ headline: "趋势候选 #1 · 平安银行" }),
      buildCandidate({ headline: "多因子候选 #1 · 平安银行" }),
    ];

    render(
      <StockAnalysisFirstScreenRail
        queueTotalCount={2}
        queueVisibleCount={2}
        canReviewCandidates={true}
        emptyState={null}
        primaryBlockerLabel={null}
        topCandidates={candidates}
        onOpenCandidate={vi.fn()}
        onJumpToQueue={vi.fn()}
        gapOverview={emptyGapOverview}
      />,
    );

    const rail = screen.getByTestId("stock-analysis-first-screen-rail");
    expect(within(rail).getAllByTestId("stock-analysis-rail-queue-000001.SZ")).toHaveLength(2);

    const duplicateKeyWarnings = consoleError.mock.calls.filter((call) =>
      call.some(
        (arg) =>
          typeof arg === "string" && arg.includes("Encountered two children with the same key"),
      ),
    );
    expect(duplicateKeyWarnings).toEqual([]);
  });
});
