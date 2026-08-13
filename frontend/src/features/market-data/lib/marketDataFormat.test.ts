import { describe, expect, it } from "vitest";

import { EM_DASH } from "../../../utils/format";
import { formatPct, formatSignedNumber } from "./marketDataFormat";

describe("formatSignedNumber", () => {
  it("formats numeric values with sign and suffix", () => {
    expect(formatSignedNumber(1.2, " bp")).toBe("+1.20 bp");
    expect(formatSignedNumber(-0.5)).toBe("-0.50");
  });

  it("returns 不可用 for nullish", () => {
    expect(formatSignedNumber(null)).toBe("不可用");
    expect(formatSignedNumber("")).toBe("不可用");
  });
});

describe("formatPct", () => {
  it("formats to two decimals with percent suffix", () => {
    expect(formatPct(3.456)).toBe("3.46%");
    expect(formatPct(-0.5)).toBe("-0.50%");
  });

  it("returns EM_DASH for missing values", () => {
    expect(formatPct(null)).toBe(EM_DASH);
    expect(formatPct(undefined)).toBe(EM_DASH);
    expect(formatPct(Number.NaN)).toBe(EM_DASH);
  });
});
