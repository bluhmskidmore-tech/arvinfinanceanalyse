import { describe, expect, it } from "vitest";

import { percentageDisplayRaw } from "./dashboardHomeBodyView";

describe("percentageDisplayRaw", () => {
  it("converts contract pct raw (decimal ratio) to 0-100 percent with a fixed x100", () => {
    // 后端 percentage 字段为 unit="pct" 的 Numeric，raw 恒为小数比率（0.6 → 60%）。
    expect(percentageDisplayRaw(0.6)).toBeCloseTo(60);
    expect(percentageDisplayRaw(0.0486)).toBeCloseTo(4.86);
    // 100% 边界（raw=1）不再被启发式误判。
    expect(percentageDisplayRaw(1)).toBeCloseTo(100);
    expect(percentageDisplayRaw(0)).toBe(0);
  });

  it("returns null for missing or non-finite raw", () => {
    expect(percentageDisplayRaw(null)).toBeNull();
    expect(percentageDisplayRaw(undefined)).toBeNull();
    expect(percentageDisplayRaw(Number.NaN)).toBeNull();
  });
});
