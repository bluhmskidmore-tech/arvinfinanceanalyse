import { describe, expect, it } from "vitest";

import { formatAmountWan, formatAmountYi, formatRatePercent } from "./format";

describe("positions formatters", () => {
  it("rounds money half up without using floating point display math", () => {
    expect(formatAmountYi("39560735660139.14998465")).toBe("395,607.36 亿元");
    expect(formatAmountWan("123456789.99500000")).toBe("12,345.68 万元");
  });

  it("rounds decimal rates to displayed percentages", () => {
    expect(formatRatePercent("0.02409626")).toBe("2.41%");
    expect(formatRatePercent("0.02072113")).toBe("2.07%");
  });
});
