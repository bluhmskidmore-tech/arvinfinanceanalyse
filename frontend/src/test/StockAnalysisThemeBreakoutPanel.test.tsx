import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { StockAnalysisThemeBreakoutPanel } from "../features/stock-analysis/components/StockAnalysisThemeBreakoutPanel";
import type {
  StockThemeBreakoutCard,
  StockThemeBreakoutReviewItem,
  StockThemeEvidenceStateRow,
} from "../features/stock-analysis/lib/stockAnalysisPageModel";

const leader = {
  stockCode: "000001.SZ",
  stockName: "Alpha Bank",
  pctChange: "+8.20%",
  turn: "2.1x",
  closeStrength: "0.92",
  tags: ["leader", "volume"],
  sourceKindLabel: "当前概念覆盖",
};

const card: StockThemeBreakoutCard = {
  rank: 1,
  themeKey: "theme-ai",
  themeName: "AI Finance",
  parentSectorLabel: "Software",
  summary: "Momentum extension",
  reason: "Breadth and leaders both improved.",
  boundaryLabel: "Observation only.",
  strongCountLabel: "强势 4",
  limitCountLabel: "涨停 1",
  advanceRatioLabel: "上涨 80%",
  avgPctChangeLabel: "均涨 +3.2%",
  movementLabel: "扩散",
  latestEventLabel: "Latest event: sector breadth improved.",
  sourceKindLabel: "当前概念覆盖",
  leaders: [leader],
};

const evidenceRow: StockThemeEvidenceStateRow = {
  key: "theme-membership",
  label: "Theme membership",
  status: "ready",
  statusLabel: "ready",
  detail: "Source table is landed.",
  rowCountLabel: "120 rows",
};

const reviewItem: StockThemeBreakoutReviewItem = {
  rank: 2,
  themeKey: "theme-robotics",
  themeName: "Robotics",
  sourceKindLabel: "candidate",
  parentSectorLabel: "Manufacturing",
  summary: "Gate pending",
  failedGateLabel: "breadth pending",
  reason: "Needs review before promotion.",
  leaders: [leader],
};

describe("StockAnalysisThemeBreakoutPanel", () => {
  it("renders theme breakout cards, evidence rows, and review items", () => {
    render(
      <StockAnalysisThemeBreakoutPanel
        cards={[card]}
        evidenceRows={[evidenceRow]}
        reviewItems={[reviewItem]}
        emptyMessage="当前没有题材观察样本。"
      />,
    );

    expect(screen.getByTestId("stock-analysis-theme-breakout-cards")).toHaveTextContent("AI Finance");
    expect(screen.getAllByText("Alpha Bank")).toHaveLength(2);
    expect(screen.getByTestId("stock-analysis-theme-evidence-state")).toHaveTextContent("Theme membership");
    expect(screen.getByTestId("stock-analysis-theme-review-items")).toHaveTextContent("Robotics");
    expect(screen.getByText("Needs review before promotion.")).toBeInTheDocument();
    expect(screen.getAllByText("当前概念覆盖").length).toBeGreaterThanOrEqual(2);
  });

  it("renders the provided empty message when there are no breakout cards", () => {
    render(
      <StockAnalysisThemeBreakoutPanel
        cards={[]}
        evidenceRows={[]}
        reviewItems={[]}
        emptyMessage="当前没有题材观察样本。"
      />,
    );

    expect(screen.getByText("当前没有题材观察样本。")).toBeInTheDocument();
    expect(screen.queryByText(/No theme/i)).not.toBeInTheDocument();
    expect(screen.queryByTestId("stock-analysis-theme-evidence-state")).not.toBeInTheDocument();
    expect(screen.queryByTestId("stock-analysis-theme-review-items")).not.toBeInTheDocument();
  });
});
