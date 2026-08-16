import { describe, expect, it } from "vitest";

import {
  primaryWorkbenchNavigation,
  primaryWorkbenchNavigationGroups,
  resolveWorkbenchGroupKey,
} from "../app/navigation";
import {
  getPortfolioModuleDrilldowns,
  PORTFOLIO_MODULE_DRILLDOWN_COUNT,
} from "../features/workbench/module-home/portfolioModuleDrilldowns";

describe("portfolioModuleDrilldowns", () => {
  it("matches the portfolio navigation group size shown in the workbench shell", () => {
    const portfolioGroup = primaryWorkbenchNavigationGroups.find(
      (group) => group.key === "portfolio",
    );
    expect(portfolioGroup?.sections.length).toBe(16);
    expect(PORTFOLIO_MODULE_DRILLDOWN_COUNT).toBe(16);
    expect(getPortfolioModuleDrilldowns()).toHaveLength(16);
  });

  it("derives drilldown entries from live portfolio navigation sections", () => {
    const expectedKeys = primaryWorkbenchNavigation
      .filter((section) => resolveWorkbenchGroupKey(section) === "portfolio")
      .map((section) => section.key);

    expect(getPortfolioModuleDrilldowns().map((item) => item.key)).toEqual(expectedKeys);
    expect(getPortfolioModuleDrilldowns().map((item) => item.label)).toContain("债券分析");
    expect(getPortfolioModuleDrilldowns().map((item) => item.label)).toContain("日均分析");
    expect(getPortfolioModuleDrilldowns().map((item) => item.path)).toContain("/bond-analysis");
    expect(getPortfolioModuleDrilldowns().map((item) => item.path)).toContain("/pnl-by-business");
    expect(getPortfolioModuleDrilldowns().map((item) => item.path)).toContain(
      "/pnl-by-business-insights",
    );
  });
});
