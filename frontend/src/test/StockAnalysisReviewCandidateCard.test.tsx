import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import {
  StockAnalysisReviewCandidateCard,
} from "../features/stock-analysis/components/StockAnalysisReviewCandidateCard";
import type { StockCandidateReviewQueueItem } from "../features/stock-analysis/lib/stockAnalysisPageModel";

const candidate: StockCandidateReviewQueueItem = {
  rank: 1,
  stockCode: "000001.SZ",
  stockName: "Alpha Bank",
  sectorCode: "BK001",
  sectorName: "Banking",
  headline: "Alpha Bank breakout review",
  pattern: "突破",
  patternNote: "close above breakout",
  distanceToBreakoutPct: "+1.2%",
  reviewFocus: "Review breakout confirmation before action.",
  primaryEvidence: [
    { key: "primary-1", label: "Close", value: "10.20" },
    { key: "primary-2", label: "MA20", value: "9.80" },
  ],
  supportingEvidence: [
    { key: "support-1", label: "Turnover", value: "2.1x" },
    { key: "support-2", label: "Sector", value: "Top 3" },
    { key: "support-3", label: "Breadth", value: "Positive" },
  ],
  boundaryEvidence: ["No formal trading instruction.", "Data lineage pending."],
  invalidationFocus: "Close below MA20 invalidates the setup.",
  invalidationRules: ["Close below MA20", "Volume dries up"],
  rawFields: [
    { key: "close", label: "Close", value: "10.20" },
    { key: "score", label: "Score", value: "0.91" },
  ],
};

describe("StockAnalysisReviewCandidateCard", () => {
  it("renders the review candidate card and reports K-line review intent", () => {
    const onReviewChart = vi.fn();

    render(
      <StockAnalysisReviewCandidateCard
        card={candidate}
        selectedSectorCode="BK001"
        onReviewChart={onReviewChart}
      />,
    );

    expect(screen.getByTestId("stock-candidate-000001.SZ")).toHaveAttribute("data-selected-sector", "true");
    expect(screen.getByText("Alpha Bank breakout review")).toBeInTheDocument();
    expect(screen.getByText("+1 证据")).toBeInTheDocument();
    expect(screen.queryByText("Breadth")).not.toBeInTheDocument();

    fireEvent.click(screen.getByTestId("stock-candidate-review-chart-000001.SZ"));
    expect(onReviewChart).toHaveBeenCalledWith(candidate);
  });
});
