import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import {
  StockAnalysisClosedLoopSummaryRail,
} from "../features/stock-analysis/components/StockAnalysisClosedLoopRail";
import {
  closedLoopRailIcon,
  type ClosedLoopRailKey,
} from "../features/stock-analysis/components/stockAnalysisClosedLoopRailIcons";
import type { StockClosedLoopSummary } from "../features/stock-analysis/lib/stockAnalysisPageModel";

const closedLoopSummary: StockClosedLoopSummary = {
  summaryLabel: "Reviewable",
  boundaryCount: 2,
  referenceRating: {
    code: "reviewable",
    label: "可复核",
    tone: "positive",
    detail: "Reference path is reviewable.",
  },
  verdict: {
    code: "reviewable",
    tone: "positive",
    label: "可复核",
    headline: "Can enter manual review queue.",
    primaryReason: "All required gates are connected.",
    nextStep: "Review the top candidate.",
    evidence: ["Entry gate open", "Replay connected"],
  },
  items: [
    {
      key: "entry_gate",
      label: "入场观察门",
      status: "open",
      statusLabel: "开放",
      tone: "positive",
      detail: "Market gate is open.",
    },
    {
      key: "replay",
      label: "回放证据",
      status: "available",
      statusLabel: "已接通",
      tone: "warning",
      detail: "2 snapshots cover the current queue.",
      badges: ["lineage-ok"],
    },
  ],
};

describe("StockAnalysisClosedLoopRail", () => {
  it.each([
    ["entry_gate", "line-chart"] as const,
    ["adversarial_gate", "thunderbolt"] as const,
    ["risk_exit", "fire"] as const,
    ["replay", "bar-chart"] as const,
    ["lineage", "database"] as const,
  ])("maps %s to the expected decorative icon", (key: ClosedLoopRailKey, iconName: string) => {
    render(<span data-testid="rail-icon">{closedLoopRailIcon(key)}</span>);

    expect(screen.getByTestId("rail-icon").querySelector(`[aria-label="${iconName}"]`)).toBeInTheDocument();
  });

  it("renders the closed-loop summary rail with compact verdict details", () => {
    render(
      <StockAnalysisClosedLoopSummaryRail
        summary={closedLoopSummary}
        riskTone="negative"
        riskTriggeredCount={1}
        boundaryIssueCount={2}
        reviewQueueCount={3}
        nextActionLabel="首位 Alpha Bank"
        nextActionFullLabel="Alpha Bank · 距观察 +1.2%"
      />,
    );

    const summary = screen.getByTestId("stock-analysis-closed-loop-summary");
    const verdict = screen.getByTestId("stock-analysis-closed-loop-verdict");

    expect(summary).toHaveTextContent("闭环摘要");
    expect(verdict).toHaveAttribute("data-tone", "positive");
    expect(verdict).toHaveTextContent("Can enter manual review queue.");
    expect(verdict).toHaveTextContent("边界");
    expect(verdict).toHaveTextContent("依据");
    expect(within(summary).getByTestId("stock-analysis-rail-check-matrix")).toBeInTheDocument();
    expect(screen.getByTestId("stock-analysis-replay-status")).toHaveAttribute("data-tone", "warning");
    expect(screen.getByText("首位 Alpha Bank")).toBeInTheDocument();
    expect(screen.getByText("首位 Alpha Bank").closest("p")).toHaveAttribute(
      "title",
      "Alpha Bank · 距观察 +1.2%",
    );
    expect(summary).not.toHaveTextContent("All required gates are connected.");
    expect(summary).not.toHaveTextContent("2 snapshots cover the current queue.");

    fireEvent.click(within(verdict).getByText("依据明细"));
    expect(summary).toHaveTextContent("All required gates are connected.");

    fireEvent.click(within(screen.getByTestId("stock-analysis-replay-status")).getByText("明细"));
    expect(summary).toHaveTextContent("2 snapshots cover the current queue.");
  });
});
