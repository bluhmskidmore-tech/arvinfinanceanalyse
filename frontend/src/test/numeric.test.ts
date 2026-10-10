import { describe, expect, it } from "vitest";

import { isNumeric, normalizeNumeric, parseNumeric, parseNumericOrNull } from "../api/numeric";
import { EM_DASH } from "../utils/format";
import type { Numeric } from "../api/contracts";

describe("isNumeric", () => {
  it("accepts a full valid Numeric with positive yuan value", () => {
    const candidate: Numeric = {
      raw: 12_345_678_900,
      unit: "yuan",
      display: "+123.46 亿",
      precision: 2,
      sign_aware: true,
    };
    expect(isNumeric(candidate)).toBe(true);
  });

  it("accepts Numeric with raw = null", () => {
    const candidate: Numeric = {
      raw: null,
      unit: "pct",
      display: "—",
      precision: 2,
      sign_aware: true,
    };
    expect(isNumeric(candidate)).toBe(true);
  });

  it("accepts Numeric with negative raw", () => {
    const candidate: Numeric = {
      raw: -5_000_000_000,
      unit: "yuan",
      display: "-50.00 亿",
      precision: 2,
      sign_aware: true,
    };
    expect(isNumeric(candidate)).toBe(true);
  });

  it("rejects plain number", () => {
    expect(isNumeric(42)).toBe(false);
  });

  it("rejects string", () => {
    expect(isNumeric("+12.34 亿")).toBe(false);
  });

  it("rejects null", () => {
    expect(isNumeric(null)).toBe(false);
  });

  it("rejects undefined", () => {
    expect(isNumeric(undefined)).toBe(false);
  });

  it("rejects object missing raw field", () => {
    expect(
      isNumeric({ unit: "yuan", display: "x", precision: 0, sign_aware: true }),
    ).toBe(false);
  });

  it("rejects object with unknown unit", () => {
    expect(
      isNumeric({
        raw: 1,
        unit: "bogus",
        display: "1",
        precision: 0,
        sign_aware: true,
      }),
    ).toBe(false);
  });

  it("rejects object with negative precision", () => {
    expect(
      isNumeric({
        raw: 1,
        unit: "yuan",
        display: "1",
        precision: -1,
        sign_aware: true,
      }),
    ).toBe(false);
  });

  it("rejects object with non-string display", () => {
    expect(
      isNumeric({
        raw: 1,
        unit: "yuan",
        display: 12.34,
        precision: 2,
        sign_aware: true,
      }),
    ).toBe(false);
  });

  it("rejects object with non-boolean sign_aware", () => {
    expect(
      isNumeric({
        raw: 1,
        unit: "yuan",
        display: "1",
        precision: 2,
        sign_aware: "yes",
      }),
    ).toBe(false);
  });
});

describe("parseNumeric", () => {
  it("returns Numeric when input is valid", () => {
    const input = {
      raw: 0.0255,
      unit: "pct",
      display: "+2.55%",
      precision: 2,
      sign_aware: true,
    };
    const result = parseNumeric(input);
    expect(result.raw).toBe(0.0255);
    expect(result.unit).toBe("pct");
  });

  it("throws with descriptive message on invalid input", () => {
    expect(() => parseNumeric({ raw: 1, unit: "bogus" })).toThrow(/invalid Numeric/i);
  });

  it("throws on null", () => {
    expect(() => parseNumeric(null)).toThrow(/invalid Numeric/i);
  });
});

describe("parseNumericOrNull", () => {
  it("returns Numeric on valid input", () => {
    const input = {
      raw: 1,
      unit: "count",
      display: "1",
      precision: 0,
      sign_aware: false,
    };
    expect(parseNumericOrNull(input)?.raw).toBe(1);
  });

  it("returns null on invalid input instead of throwing", () => {
    expect(parseNumericOrNull("garbage")).toBeNull();
    expect(parseNumericOrNull(undefined)).toBeNull();
  });
});

describe("normalizeNumeric", () => {
  it("passes a valid Numeric through unchanged (same reference)", () => {
    const input: Numeric = {
      raw: 0.0255,
      unit: "pct",
      display: "+2.55%",
      precision: 2,
      sign_aware: true,
    };
    expect(normalizeNumeric(input, "yuan", false)).toBe(input);
  });

  it("coerces a decimal string with caller unit and precision", () => {
    const result = normalizeNumeric("0.37853183", "bp", false, 2);
    expect(result.raw).toBeCloseTo(0.37853183);
    expect(result.unit).toBe("bp");
    expect(result.display).toBe("0.38 bp");
    expect(result.precision).toBe(2);
    expect(result.sign_aware).toBe(false);
  });

  it("coerces a plain number and honors sign_aware", () => {
    const result = normalizeNumeric(-677_931_223.044133, "yuan", true);
    expect(result.raw).toBeCloseTo(-677_931_223.044133);
    expect(result.display).toBe("-6.78 亿");
    expect(result.sign_aware).toBe(true);
  });

  it("normalizes null, undefined, and empty string to a missing Numeric", () => {
    for (const missing of [null, undefined, ""]) {
      const result = normalizeNumeric(missing, "ratio", false);
      expect(result.raw).toBeNull();
      expect(result.display).toBe(EM_DASH);
    }
  });

  it("normalizes a non-numeric string to a missing Numeric", () => {
    const result = normalizeNumeric("garbage", "ratio", false);
    expect(result.raw).toBeNull();
    expect(result.display).toBe(EM_DASH);
  });

  it("rejects partial-numeric tokens instead of truncating them (审计 F02 #2)", () => {
    // 此前 decimalRaw 用 parseFloat("12abc") → 12（悄然截断非法尾部）。
    // 严格全串校验后必须视为缺失，不得回落到看似可信的 12。
    const trailingGarbage = normalizeNumeric("12abc", "ratio", false);
    expect(trailingGarbage.raw).toBeNull();
    expect(trailingGarbage.display).toBe(EM_DASH);

    const leadingGarbage = normalizeNumeric("abc12", "ratio", false);
    expect(leadingGarbage.raw).toBeNull();
    expect(leadingGarbage.display).toBe(EM_DASH);
  });

  it("accepts a full-string decimal (optionally negative) after trimming whitespace", () => {
    const trimmed = normalizeNumeric(" -12.5 ", "bp", true, 2);
    expect(trimmed.raw).toBeCloseTo(-12.5);
    expect(trimmed.raw_text).toBe("-12.5");
    expect(trimmed.display).toBe("-12.50 bp");
  });

  it("does not accept scientific notation strings (no observed caller emits exponent form)", () => {
    const result = normalizeNumeric("1e5", "ratio", false);
    expect(result.raw).toBeNull();
    expect(result.display).toBe(EM_DASH);
  });
});

describe("Numeric unit literal coverage", () => {
  it("accepts all 8 spec units", () => {
    const units: Array<Numeric["unit"]> = [
      "yuan",
      "pct",
      "bp",
      "ratio",
      "years",
      "count",
      "dv01",
      "yi",
    ];
    for (const unit of units) {
      const candidate: Numeric = {
        raw: 1,
        unit,
        display: "1",
        precision: 0,
        sign_aware: false,
      };
      expect(isNumeric(candidate)).toBe(true);
    }
  });
});
