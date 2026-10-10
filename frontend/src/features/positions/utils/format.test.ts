import { describe, expect, it } from "vitest";

import { EM_DASH } from "../../../utils/format";
import {
  formatAmountWan,
  formatAmountWanYi,
  formatAmountYi,
  formatAmountYiAuto,
  formatAmountYiNumber,
  formatDecimalFixed,
  formatPercentValue,
  formatRatePercent,
} from "./format";

describe("positions formatters", () => {
  it("rounds money half up without using floating point display math", () => {
    expect(formatAmountYi("39560735660139.14998465")).toBe("395,607.36 亿元");
    expect(formatAmountWan("123456789.99500000")).toBe("12,345.68 万元");
  });

  it("formats bare yi numbers for table cells with unit lifted to the header", () => {
    expect(formatAmountYiNumber("115000000.00000000")).toBe("1.15");
    expect(formatAmountYiNumber("39560735660139.14998465")).toBe("395,607.36");
    expect(formatAmountYiNumber("0")).toBe("0.00");
    expect(formatAmountYiNumber(null)).toBe(EM_DASH);
  });

  it("formats wan-yi amounts with half-up rounding", () => {
    expect(formatAmountWanYi("70962388000000")).toBe("70.96 万亿元");
    expect(formatAmountWanYi(null)).toBe(EM_DASH);
  });

  it("switches KPI amounts to wan-yi only at or above the 1e12-yuan threshold", () => {
    // 709,623.88 亿元量级的区间累计单行显示为万亿
    expect(formatAmountYiAuto("70962388000000")).toBe("70.96 万亿元");
    // 阈值下 0.99 万亿保持亿元
    expect(formatAmountYiAuto("990000000000")).toBe("9,900.00 亿元");
    // 恰好 1 万亿切换
    expect(formatAmountYiAuto("1000000000000")).toBe("1.00 万亿元");
    // 真实零是 0.00 亿元，不是 EM_DASH
    expect(formatAmountYiAuto("0")).toBe("0.00 亿元");
    expect(formatAmountYiAuto(null)).toBe(EM_DASH);
  });

  it("rounds decimal rates to displayed percentages", () => {
    expect(formatRatePercent("0.02409626")).toBe("2.41%");
    expect(formatRatePercent("0.02072113")).toBe("2.07%");
  });

  it("rounds raw percent strings half-up for display", () => {
    expect(formatPercentValue("84.48287107")).toBe("84.48%");
    expect(formatPercentValue("51.111154499")).toBe("51.11%");
    expect(formatPercentValue("99.995")).toBe("100.00%");
    expect(formatPercentValue("0")).toBe("0.00%");
    expect(formatPercentValue(null)).toBe(EM_DASH);
  });

  it("rounds decimal strings to a fixed display precision without units", () => {
    // 估值净价 8 位原始精度收敛 4 位（half-up），真实零保留为 0.0000。
    expect(formatDecimalFixed("100.00000000")).toBe("100.0000");
    expect(formatDecimalFixed("99.12345678")).toBe("99.1235");
    expect(formatDecimalFixed("99.12344999")).toBe("99.1234");
    expect(formatDecimalFixed("-1.00005000")).toBe("-1.0001");
    expect(formatDecimalFixed("0.00000000")).toBe("0.0000");
    expect(formatDecimalFixed(null)).toBe(EM_DASH);
    expect(formatDecimalFixed(undefined)).toBe(EM_DASH);
  });
});
