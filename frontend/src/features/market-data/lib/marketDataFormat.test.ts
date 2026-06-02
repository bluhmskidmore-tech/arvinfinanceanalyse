import { describe, expect, it } from "vitest";

import { formatSignedNumber } from "./marketDataFormat";

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
