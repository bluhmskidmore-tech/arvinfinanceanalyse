import { describe, expect, it } from "vitest";

import { dashboardBondHeadlineQueryKey } from "../features/executive-dashboard/components/dashboardBondHeadlineQuery";
import { apiQueryKeys } from "./queryKeys";

describe("apiQueryKeys", () => {
  it("shares cache keys for the same cross-page read models", () => {
    expect(apiQueryKeys.marketRates("real", "2026-04-30")).toEqual([
      "market-data",
      "formal-rates",
      "real",
      "2026-04-30",
    ]);
    expect(dashboardBondHeadlineQueryKey("real", "2026-04-30")).toEqual(
      apiQueryKeys.bondDashboardHeadline("real", "2026-04-30"),
    );
    expect(apiQueryKeys.bondAnalyticsPortfolioHeadlines("real", "2026-04-30")).toEqual([
      "bond-analytics",
      "portfolio-headlines",
      "real",
      "2026-04-30",
    ]);
    expect(apiQueryKeys.bondDashboardPortfolioComparison("real", "2026-04-30")).toEqual([
      "bond-dashboard",
      "portfolio-comparison",
      "real",
      "2026-04-30",
    ]);
    expect(apiQueryKeys.bondAnalyticsCreditSpreadMigration("real", "2026-04-30")).toEqual([
      "bond-analytics",
      "credit-spread-migration",
      "real",
      "2026-04-30",
      "10,25,50",
    ]);
    expect(apiQueryKeys.homeIncomeTrend("real", "2026-04-30", 7)).toEqual([
      "home",
      "income-trend",
      "real",
      "2026-04-30",
      7,
    ]);
    expect(apiQueryKeys.balanceAnalysisDecisionItems("real", "2026-04-30", "all", "CNY")).toEqual([
      "balance-analysis",
      "decision-items",
      "real",
      "2026-04-30",
      "all",
      "CNY",
    ]);
    expect(
      apiQueryKeys.pnlByBusinessAnalysis("real", 2026, "2026-04-30", "bond_bucket"),
    ).toEqual([
      "pnl-by-business",
      "analysis",
      "real",
      2026,
      "2026-04-30",
      null,
      "bond_bucket",
    ]);
  });

  it("normalizes blank report dates to the dashboard pending sentinel", () => {
    expect(apiQueryKeys.bondDashboardHeadline("real", "")).toEqual([
      "bond-dashboard",
      "headline",
      "real",
      "pending-snapshot",
    ]);
  });
});
