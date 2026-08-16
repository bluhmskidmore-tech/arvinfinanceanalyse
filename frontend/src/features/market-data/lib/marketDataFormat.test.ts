import { describe, expect, it } from "vitest";

import { EM_DASH } from "../../../utils/format";
import { formatPct, formatSignedCompactAmount, formatSignedNumber } from "./marketDataFormat";

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

describe("formatSignedCompactAmount", () => {
  it("abbreviates yuan amounts to 亿 / 万 tiers with sign", () => {
    expect(formatSignedCompactAmount("1082495420.80")).toBe("+10.82 亿");
    expect(formatSignedCompactAmount(-1295506312.56)).toBe("-12.96 亿");
    expect(formatSignedCompactAmount("1820000.50")).toBe("+182.00 万");
    expect(formatSignedCompactAmount(12)).toBe("+12.00");
    expect(formatSignedCompactAmount(0)).toBe("0.00");
  });

  it("keeps formatSignedNumber empty/passthrough semantics", () => {
    expect(formatSignedCompactAmount(null)).toBe("不可用");
    expect(formatSignedCompactAmount("")).toBe("不可用");
    expect(formatSignedCompactAmount("n/a")).toBe("n/a");
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
    // 委托 pageModel pctOrDash 后与共享基元对齐：非有限数也回退 EM_DASH。
    expect(formatPct(Number.POSITIVE_INFINITY)).toBe(EM_DASH);
  });
});
