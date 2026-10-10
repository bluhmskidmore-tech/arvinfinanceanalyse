import { render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BondAnalyticsMarketContextStrip } from "../features/bond-analytics/components/BondAnalyticsMarketContextStrip";
import type { BondAnalyticsTruthStrip } from "../features/bond-analytics/lib/bondAnalyticsOverviewModel";

function createTruthStrip(): BondAnalyticsTruthStrip {
  return {
    title: "数据说明",
    items: [
      { key: "basis", label: "口径", value: "正式口径", tone: "positive" },
      { key: "freshness", label: "更新时间", value: "2026-04-10 12:00", tone: "neutral" },
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
    expect(screen.getByText("数据说明")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "债券分析" })).not.toBeInTheDocument();

    const leadModule = screen.getByTestId("bond-analysis-lead-module");
    expect(within(leadModule).getByText("当前分析")).toBeInTheDocument();
    expect(within(leadModule).getByText("动作归因")).toBeInTheDocument();
    expect(within(leadModule).getByText("可进入下钻")).toBeInTheDocument();

    const strip = screen.getByTestId("bond-analysis-truth-strip");
    expect(within(strip).getByText("口径")).toBeInTheDocument();
    expect(within(strip).getByText("正式口径")).toBeInTheDocument();
    expect(within(strip).getByText("更新时间")).toBeInTheDocument();
    expect(within(strip).getByText("2026-04-10 12:00")).toBeInTheDocument();
  });
});
