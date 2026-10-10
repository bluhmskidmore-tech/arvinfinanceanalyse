import { describe, expect, it } from "vitest";

import {
  formatCrossAssetLinkageEvidence,
  formatCrossAssetLinkageSummary,
} from "./crossAssetLinkageSummaries";

describe("formatCrossAssetLinkageSummary", () => {
  it("maps known research and transmission summaries to Chinese", () => {
    expect(formatCrossAssetLinkageSummary("Duration view favors adding exposure.")).toBe(
      "久期判断偏积极，可讨论增加敞口。",
    );
    expect(formatCrossAssetLinkageSummary("Global rates cap aggressive long-end chasing.")).toBe(
      "全球利率制约激进拉长久期。",
    );
  });

  it("parses parameterized equity and mega-cap transmission summaries", () => {
    expect(
      formatCrossAssetLinkageSummary("CSI300 equity-bond spread is 5.10ppt with CSI300 move -0.35%."),
    ).toBe("沪深300股债利差 5.10ppt，沪深300变动 -0.35%。");
    expect(
      formatCrossAssetLinkageSummary("CSI300 top10 weight concentration is 23.54% (top5 15.53%)."),
    ).toBe("沪深300前十大权重集中度 23.54%（前五 15.53%）。");
  });
});

describe("formatCrossAssetLinkageEvidence", () => {
  it("maps known research evidence snippets to Chinese", () => {
    expect(formatCrossAssetLinkageEvidence("Liquidity remains supportive.")).toBe("流动性仍偏支持。");
    expect(formatCrossAssetLinkageEvidence("DR007 remains contained.")).toBe("DR007 仍处可控区间。");
  });
});
