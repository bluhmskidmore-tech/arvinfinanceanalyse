import { describe, expect, it } from "vitest";

import { formatLivermoreReadinessSummary } from "./crossAssetLivermoreCopy";

describe("formatLivermoreReadinessSummary", () => {
  it("maps known Livermore readiness summaries to Chinese", () => {
    expect(
      formatLivermoreReadinessSummary(
        "Trend-only market gate is available; breadth and limit-up quality remain missing.",
        "market_gate",
      ),
    ).toBe("趋势门控可用；市场宽度与涨停质量仍缺数。");
    expect(
      formatLivermoreReadinessSummary(
        "Stock pivot candidate screening is available for landed Choice stock inputs.",
        "stock_pivot",
      ),
    ).toBe("个股候选筛选已可由 Choice 个股输入支撑。");
  });

  it("falls back to stock backend localization for unknown summaries", () => {
    expect(formatLivermoreReadinessSummary("breadth inputs are unavailable", "breadth")).toBe(
      "市场宽度输入不可用。",
    );
  });
});
