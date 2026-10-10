import { describe, expect, it } from "vitest";

import { formatKpiNumeric, parseKpiNumeric } from "./kpiCountUpFormat";

describe("parseKpiNumeric", () => {
  it("parses signed comma decimals", () => {
    expect(parseKpiNumeric("3,708.10")).toEqual({
      sign: "",
      abs: 3708.1,
      decimals: 2,
    });
    expect(parseKpiNumeric("+12.40")).toEqual({
      sign: "+",
      abs: 12.4,
      decimals: 2,
    });
    expect(parseKpiNumeric("-3.86")).toEqual({
      sign: "-",
      abs: 3.86,
      decimals: 2,
    });
  });

  it("rejects gaps, zero, and values with unit residue", () => {
    expect(parseKpiNumeric("—")).toBeNull();
    expect(parseKpiNumeric("0")).toBeNull();
    expect(parseKpiNumeric("0.00")).toBeNull();
    expect(parseKpiNumeric("1.2%")).toBeNull();
    expect(parseKpiNumeric("10,306.54 万")).toBeNull();
  });
});

describe("formatKpiNumeric", () => {
  it("keeps the sign and decimal places of the target display", () => {
    expect(formatKpiNumeric({ sign: "+", decimals: 2 }, 12.4)).toBe("+12.40");
    expect(formatKpiNumeric({ sign: "", decimals: 2 }, 3708.1)).toBe("3,708.10");
  });
});
