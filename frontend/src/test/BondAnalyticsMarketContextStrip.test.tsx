import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BondAnalyticsMarketContextStrip } from "../features/bond-analytics/components/BondAnalyticsMarketContextStrip";
import type { BondAnalyticsTruthStrip } from "../features/bond-analytics/lib/bondAnalyticsOverviewModel";

function createTruthStrip(): BondAnalyticsTruthStrip {
  return {
    title: "Truth and provenance",
    items: [
      { key: "basis", label: "Basis", value: "Formal", tone: "success" },
      { key: "freshness", label: "Freshness", value: "2026-04-10 12:00", tone: "neutral" },
    ],
  };
}

describe("BondAnalyticsMarketContextStrip", () => {
  it("renders cockpit framing, date context, lead module, and truth strip values", () => {
    const truthStrip = createTruthStrip();

    render(
      <BondAnalyticsMarketContextStrip
        reportDate="2026-03-31"
        periodType="MoM"
        leadModuleLabel="动作归因"
        leadPromotionLabel="Headline eligible"
        truthStrip={truthStrip}
      />,
    );

    expect(screen.getByTestId("bond-analysis-market-context-strip")).toBeInTheDocument();
    expect(screen.getByText("Bond analytics cockpit")).toBeInTheDocument();
    expect(screen.getByText("债券分析")).toBeInTheDocument();
    expect(screen.getByText("Governed homepage")).toBeInTheDocument();

    expect(screen.getByText("Report date")).toBeInTheDocument();
    expect(screen.getByText("2026-03-31")).toBeInTheDocument();
    expect(screen.getByText("Period")).toBeInTheDocument();
    expect(screen.getByText("月度环比")).toBeInTheDocument();
    expect(screen.getByText("Drill lead")).toBeInTheDocument();
    expect(screen.getByText("动作归因")).toBeInTheDocument();
    expect(screen.getByText("Headline eligible")).toBeInTheDocument();

    const strip = screen.getByTestId("bond-analysis-truth-strip");
    expect(within(strip).getByText("Basis")).toBeInTheDocument();
    expect(within(strip).getByText("Formal")).toBeInTheDocument();
    expect(within(strip).getByText("Freshness")).toBeInTheDocument();
    expect(within(strip).getByText("2026-04-10 12:00")).toBeInTheDocument();
  });
});
