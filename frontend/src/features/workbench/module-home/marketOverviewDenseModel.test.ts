import { describe, expect, it } from "vitest";

import {
  compactNumber,
  denseUnitSuffix,
  directionTone,
  formatDenseNewsTopicLabel,
  formatDenseValue,
  formatSignedPointValue,
  normalizeTapeDelta,
  rateDirectionTone,
} from "./marketOverviewDenseModel";

describe("marketOverviewDenseModel formatting", () => {
  it("keeps compact values and API units stable", () => {
    expect(compactNumber(1.23456)).toBe("1.2346");
    expect(denseUnitSuffix("point")).toBe(" 点");
    expect(denseUnitSuffix("%")).toBe("%");
    expect(formatDenseValue(4386.32, "point")).toBe("4,386.32 点");
    expect(formatDenseValue(null, "%")).toBe("—");
  });

  it("keeps rate rises on warning semantics", () => {
    expect(directionTone(0.1)).toBe("up");
    expect(directionTone(-0.1)).toBe("down");
    expect(rateDirectionTone(0.1)).toBe("warn");
    expect(rateDirectionTone(-0.1)).toBe("muted");
  });

  it("normalizes zero and missing deltas", () => {
    expect(normalizeTapeDelta("+0.00bp")).toBe("持平");
    expect(normalizeTapeDelta("无前值")).toBe("未返回");
    expect(
      formatSignedPointValue({ value_numeric: 0.35, unit: "%" } as never),
    ).toBe("+0.35%");
  });

  it("friendly-labels only governed news topics", () => {
    expect(formatDenseNewsTopicLabel("tushare_news")).toBe("新浪");
    expect(formatDenseNewsTopicLabel("tushare.research_report.20260901")).toBe(
      "研究报告",
    );
    expect(formatDenseNewsTopicLabel("custom-topic")).toBe("custom-topic");
  });
});
