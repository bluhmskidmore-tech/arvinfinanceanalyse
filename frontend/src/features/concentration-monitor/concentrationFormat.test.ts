import { describe, expect, it } from "vitest";

import type { Numeric } from "../../api/contracts";
import { formatConcentrationPercent, parseRatio } from "./concentrationFormat";

function ratioNumeric(raw: number | null, display = "—"): Numeric {
  return { raw, unit: "ratio", display, precision: 2, sign_aware: false };
}

describe("formatConcentrationPercent", () => {
  it("converts contract ratio raw (decimal ratio) with a fixed x100", () => {
    // credit-spread-migration 的 hhi / top5_concentration / credit_weight /
    // rating_aa_and_below_weight 契约均为 unit="ratio" 的小数比率。
    expect(formatConcentrationPercent(ratioNumeric(0.41354965))).toBe("41.35%");
    expect(formatConcentrationPercent(ratioNumeric(0.05088252))).toBe("5.09%");
    // 100% 与 0% 边界不再被 [0,1] 区间启发式区别对待。
    expect(formatConcentrationPercent(ratioNumeric(1))).toBe("100.00%");
    expect(formatConcentrationPercent(ratioNumeric(0))).toBe("0.00%");
  });

  it("parses legacy Q8 ratio strings the same way", () => {
    expect(formatConcentrationPercent("0.29250449")).toBe("29.25%");
  });

  it("falls back to display for null raw and em-dash for undefined", () => {
    expect(formatConcentrationPercent(ratioNumeric(null, "—"))).toBe("—");
    expect(formatConcentrationPercent(undefined)).toBe("—");
    expect(formatConcentrationPercent("")).toBe("—");
  });
});

describe("parseRatio", () => {
  it("reads Numeric raw or parses plain strings, never re-scales", () => {
    expect(parseRatio(ratioNumeric(0.1))).toBe(0.1);
    expect(parseRatio("0.15")).toBe(0.15);
    expect(parseRatio(ratioNumeric(null))).toBeNull();
    expect(parseRatio(undefined)).toBeNull();
  });
});
