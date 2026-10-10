import { describe, expect, it } from "vitest";

import {
  primaryWorkbenchNavigation,
  primaryWorkbenchNavigationGroups,
  resolveWorkbenchGroupKey,
} from "../app/navigation";
import {
  getMarketModuleDrilldowns,
  MARKET_MODULE_DRILLDOWN_COUNT,
} from "../features/workbench/module-home/marketModuleDrilldowns";

describe("marketModuleDrilldowns", () => {
  it("matches the market navigation group size shown in the workbench shell", () => {
    const marketGroup = primaryWorkbenchNavigationGroups.find((group) => group.key === "market");
    expect(marketGroup?.sections.length).toBe(MARKET_MODULE_DRILLDOWN_COUNT);
    expect(getMarketModuleDrilldowns()).toHaveLength(MARKET_MODULE_DRILLDOWN_COUNT);
  });

  it("derives drilldown entries from live market navigation sections", () => {
    const expectedKeys = primaryWorkbenchNavigation
      .filter((section) => resolveWorkbenchGroupKey(section) === "market")
      .map((section) => section.key);

    expect(getMarketModuleDrilldowns().map((item) => item.key)).toEqual(expectedKeys);
    expect(getMarketModuleDrilldowns().map((item) => item.label)).toContain("市场数据");
    expect(getMarketModuleDrilldowns().map((item) => item.label)).toContain("跨资产驱动");
    expect(getMarketModuleDrilldowns().map((item) => item.path)).toContain("/macro-toolkit");
    expect(getMarketModuleDrilldowns().map((item) => item.path)).toContain("/news-events");
  });
});
