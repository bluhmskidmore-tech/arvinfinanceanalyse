import { render, screen, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { StockCandidateReviewQueueItem } from "../lib/stockAnalysisPageModel";
import { StockAnalysisCandidateComparison } from "./StockAnalysisCandidateComparison";

function buildBoundaryLeadCandidate(): StockCandidateReviewQueueItem {
  return {
    rank: 1,
    stockCode: "000001.SZ",
    stockName: "边界候选",
    sectorCode: "801001",
    sectorName: "测试行业",
    headline: "首位候选仍有待核实边界",
    pattern: "突破",
    patternNote: "量价结构已返回。",
    distanceToBreakoutPct: "MA20 +1.2%",
    reviewFocus: "核实公告催化后再确认候选状态。",
    primaryEvidence: [
      { key: "turnover", label: "量比", value: "1.8x" },
      { key: "strength", label: "强度", value: "站上 20 日均线" },
    ],
    supportingEvidence: [{ key: "breadth", label: "扩散", value: "行业扩散 3/5" }],
    boundaryEvidence: ["公告催化尚未核实，边界待复核。"],
    invalidationFocus: "跌回 MA20 下方即降级观察。",
    invalidationRules: ["跌回 MA20 下方即降级观察。"],
    rawFields: [],
  };
}

describe("StockAnalysisCandidateComparison", () => {
  it("keeps a lead candidate with a real boundary waiting for confirmation", () => {
    const candidate = buildBoundaryLeadCandidate();

    render(
      <StockAnalysisCandidateComparison
        candidates={[candidate]}
        usesHybridFusion={false}
        asOfLabel="2026-07-16"
        onReviewCandidate={vi.fn()}
      />,
    );

    const row = screen.getByTestId(`stock-comparison-candidate-row-${candidate.stockCode}`);

    expect(within(row).getByText(/等待确认/)).toBeInTheDocument();
    expect(row).toHaveTextContent("边界待核实");
    expect(row).not.toHaveTextContent("优先复核");
  });
});
