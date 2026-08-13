import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BondAnalyticsMarketContextStrip } from "../features/bond-analytics/components/BondAnalyticsMarketContextStrip";
import type { BondAnalyticsTruthStrip } from "../features/bond-analytics/lib/bondAnalyticsOverviewModel";

function createTruthStrip(): BondAnalyticsTruthStrip {
  return {
    title: "真值与证据",
    items: [
      { key: "basis", label: "口径", value: "正式口径", tone: "positive" },
      { key: "freshness", label: "新鲜度", value: "2026-04-10 12:00", tone: "neutral" },
    ],
  };
}

describe("BondAnalyticsMarketContextStrip", () => {
  it("renders cockpit framing, date context, lead module, and truth strip values", () => {
    const truthStrip = createTruthStrip();

    render(
      <BondAnalyticsMarketContextStrip
        leadModuleLabel="动作归因"
        leadPromotionLabel="可进入下钻"
        truthStrip={truthStrip}
      />,
    );

    expect(screen.getByTestId("bond-analysis-market-context-strip")).toBeInTheDocument();
    expect(screen.getByText("真值与证据")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "债券分析" })).not.toBeInTheDocument();

    const leadModule = screen.getByTestId("bond-analysis-lead-module");
    expect(within(leadModule).getByText("下钻主线")).toBeInTheDocument();
    expect(within(leadModule).getByText("动作归因")).toBeInTheDocument();
    expect(within(leadModule).getByText("可进入下钻")).toBeInTheDocument();

    const strip = screen.getByTestId("bond-analysis-truth-strip");
    expect(within(strip).getByText("口径")).toBeInTheDocument();
    expect(within(strip).getByText("正式口径")).toBeInTheDocument();
    expect(within(strip).getByText("新鲜度")).toBeInTheDocument();
    expect(within(strip).getByText("2026-04-10 12:00")).toBeInTheDocument();
  });
});
