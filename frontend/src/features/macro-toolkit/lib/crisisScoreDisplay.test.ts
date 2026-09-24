import { describe, expect, it } from "vitest";

import { formatCrisisTopContributorSummary } from "./crisisScoreDisplay";

describe("formatCrisisTopContributorSummary", () => {
  it("formats top absolute z contributors without recalculating score", () => {
    const summary = formatCrisisTopContributorSummary([
      { key: "credit_spread", label: "AA 5Y - treasury 5Y", z_score: -0.35 },
      { key: "equity_vol", label: "HS300 realized volatility", z_score: -0.42 },
      { key: "fx_vol", label: "USDCNY vol", z_score: 0.11 },
    ]);

    expect(summary).toBe(
      "HS300 realized volatility z=-0.42 · AA 5Y - treasury 5Y z=-0.35",
    );
  });

  it("returns null when no finite z scores exist", () => {
    expect(formatCrisisTopContributorSummary([{ key: "equity_vol", label: "equity", z_score: null }])).toBeNull();
  });
});
