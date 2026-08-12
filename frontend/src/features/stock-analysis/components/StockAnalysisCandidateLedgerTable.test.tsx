import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { StockCandidateReviewQueueItem } from "../lib/stockAnalysisPageModel";
import { StockAnalysisCandidateLedgerTable } from "./StockAnalysisCandidateLedgerTable";

function buildCandidate(overrides: Partial<StockCandidateReviewQueueItem> = {}): StockCandidateReviewQueueItem {
  return {
    rank: 1,
    stockCode: "000001.SZ",
    stockName: "Alpha",
    sectorCode: "801001",
    sectorName: "AI",
    headline: "观察候选 #1 · Alpha",
    pattern: "突破",
    patternNote: "量价结构已返回。",
    distanceToBreakoutPct: "+1.2%",
    reviewFocus: "核实公告催化后再确认候选状态。",
    primaryEvidence: [{ key: "close_vs_break", label: "收盘 vs 观察位", value: "21.9 / 21.8" }],
    supportingEvidence: [],
    boundaryEvidence: [],
    invalidationFocus: "跌回 MA20 下方即降级观察。",
    invalidationRules: ["跌回 MA20 下方即降级观察。"],
    rawFields: [],
    ...overrides,
  };
}

describe("StockAnalysisCandidateLedgerTable", () => {
  it("shows the low-liquidity badge with the daily amount as a tooltip when liquidityFloorPass is false", () => {
    render(
      <StockAnalysisCandidateLedgerTable
        candidates={[buildCandidate({ liquidityFloorPass: false, dailyAmountLabel: "日成交 0.80 亿" })]}
        usesHybridFusion={false}
        selectedSectorCode={null}
        onReviewCandidate={vi.fn()}
      />,
    );

    const badge = screen.getByText("低流动");
    expect(badge).toBeInTheDocument();
    expect(badge).toHaveAttribute("title", "日成交 0.80 亿");
  });

  it("hides the badge when the row passes the liquidity floor", () => {
    render(
      <StockAnalysisCandidateLedgerTable
        candidates={[buildCandidate({ liquidityFloorPass: true, dailyAmountLabel: "日成交 5.00 亿" })]}
        usesHybridFusion={false}
        selectedSectorCode={null}
        onReviewCandidate={vi.fn()}
      />,
    );

    expect(screen.queryByText("低流动")).not.toBeInTheDocument();
  });

  it("hides the badge when liquidity data is missing (null)", () => {
    render(
      <StockAnalysisCandidateLedgerTable
        candidates={[buildCandidate({ liquidityFloorPass: null, dailyAmountLabel: null })]}
        usesHybridFusion={false}
        selectedSectorCode={null}
        onReviewCandidate={vi.fn()}
      />,
    );

    expect(screen.queryByText("低流动")).not.toBeInTheDocument();
  });

  it("shows the position size hint badge with the disclosure detail as a tooltip", () => {
    render(
      <StockAnalysisCandidateLedgerTable
        candidates={[
          buildCandidate({
            sizeHintLabel: "仓位 ≤ 8.4%",
            sizeHintDetail: "建议仓位为单票权重上限参考（EMA10 止损距离折算）\n样本外验证：仅供参考",
          }),
        ]}
        usesHybridFusion={false}
        selectedSectorCode={null}
        onReviewCandidate={vi.fn()}
      />,
    );

    const badge = screen.getByText("仓位 ≤ 8.4%");
    expect(badge).toBeInTheDocument();
    expect(badge.closest("[title]")).toHaveAttribute(
      "title",
      "建议仓位为单票权重上限参考（EMA10 止损距离折算）\n样本外验证：仅供参考",
    );
  });

  it("hides the position size hint badge when the backend omits the hint", () => {
    render(
      <StockAnalysisCandidateLedgerTable
        candidates={[buildCandidate({ sizeHintLabel: null, sizeHintDetail: null })]}
        usesHybridFusion={false}
        selectedSectorCode={null}
        onReviewCandidate={vi.fn()}
      />,
    );

    expect(screen.queryByText(/仓位 ≤/)).not.toBeInTheDocument();
  });
});
