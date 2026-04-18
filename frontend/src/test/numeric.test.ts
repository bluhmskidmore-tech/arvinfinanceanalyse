import { describe, expect, it } from "vitest";

import { isNumeric, parseNumeric, parseNumericOrNull } from "../api/numeric";
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

describe("Numeric unit literal coverage", () => {
  it("accepts all 7 spec units", () => {
    const units: Array<Numeric["unit"]> = [
      "yuan",
      "pct",
      "bp",
      "ratio",
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
