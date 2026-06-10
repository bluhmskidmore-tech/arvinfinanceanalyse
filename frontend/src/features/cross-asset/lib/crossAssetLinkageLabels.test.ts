import { describe, expect, it } from "vitest";

import {
  formatLinkageCorrelationTarget,
  formatLinkageEnvironmentScoreDetail,
  formatLinkageRateDirection,
  formatWaterfallContributingFactorName,
  formatWaterfallContributingFactorSummary,
} from "./crossAssetLinkageLabels";

describe("crossAssetLinkageLabels", () => {
  it("maps backend rate_direction enums to Chinese labels", () => {
    expect(formatLinkageRateDirection("falling")).toBe("下行");
    expect(formatLinkageRateDirection("rising")).toBe("上行");
    expect(formatLinkageRateDirection("neutral")).toBe("中性");
    expect(formatLinkageRateDirection(null)).toBe("不可用");
  });

  it("formats environment score detail copy in Chinese", () => {
    expect(formatLinkageEnvironmentScoreDetail("方向分值", -0.5569)).toBe("方向分值 -0.56");
    expect(formatLinkageEnvironmentScoreDetail("方向分值", null, "缺少方向评分。")).toBe("缺少方向评分。");
  });

  it("formats correlation target summaries with an arrow", () => {
    expect(formatLinkageCorrelationTarget("DR007", "cdb", "7Y")).toBe("DR007 → cdb 7Y");
  });

  it("localizes waterfall contributing factor proxy names", () => {
    expect(formatWaterfallContributingFactorName("Liquidity proxy", "liquidity")).toBe("流动性代理");
    expect(formatWaterfallContributingFactorName("Rate proxy", "rate")).toBe("利率代理");
    expect(formatWaterfallContributingFactorName("SHIBOR:隔夜", "liquidity")).toBe("Shibor 隔夜");
    expect(formatWaterfallContributingFactorSummary([
      { series_name: "Liquidity proxy", category: "liquidity" },
      { series_name: "Rate proxy", category: "rate" },
    ])).toBe("流动性代理、利率代理");
  });
});
