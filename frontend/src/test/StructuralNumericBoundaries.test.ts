import { describe, expect, it } from "vitest";

import { isNumeric, normalizeNumeric } from "../api/numeric";
import * as bond from "../features/bond-analytics/utils/formatters";
import {
  EM_DASH,
  formatBp,
  formatPercent,
  formatRawAsNumeric,
  formatWanAmountAsYiPlain,
  formatYuanAmountAsWanPlain,
  formatYuanAmountAsYiPlain,
} from "../utils/format";

describe("structural numeric boundary regressions", () => {
  it.each([
    "123abc", "1.2.3", "12,34", "1,,000", "Infinity", "-Infinity", "NaN", "   ",
    "1e8junk", "1e+", "1e309", "1e9999999", "1,00e8", "1e8.5",
  ])("never displays an invalid amount token %j as a real value", (raw) => {
    expect(formatYuanAmountAsYiPlain(raw)).toBe(EM_DASH);
    expect(formatYuanAmountAsWanPlain(raw)).toBe(EM_DASH);
    expect(formatWanAmountAsYiPlain(raw)).toBe(EM_DASH);
    expect(bond.formatYi(raw)).toBe(EM_DASH);
    expect(bond.formatWan(raw)).toBe(EM_DASH);
    expect(bond.formatDv01Wan(raw)).toBe(EM_DASH);
    expect(bond.formatPct(raw)).toBe(EM_DASH);
    expect(bond.formatBp(raw)).toBe(EM_DASH);
  });

  it("retains full finite exponent amount tokens without widening the API decimal contract", () => {
    // Amount helpers formerly accepted full finite scientific tokens via parseFloat.
    expect(formatYuanAmountAsYiPlain("1e8")).toBe("1.00");
    expect(formatYuanAmountAsWanPlain("1E+4")).toBe("1.00");
    expect(formatWanAmountAsYiPlain("1e4")).toBe("1.00");
    expect(formatYuanAmountAsYiPlain("1,000e5")).toBe("1.00");
    expect(formatYuanAmountAsYiPlain("-.5e8")).toBe("-0.50");
    expect(formatYuanAmountAsYiPlain("100000000.")).toBe("1.00");
    expect(bond.formatYi("1e8")).toBe("1.00 亿");
    expect(bond.formatWan("1e4")).toBe("1 万");
    expect(bond.formatDv01Wan("1e4")).toBe("1.00");
    expect(bond.formatPct("1.5e-4")).toBe("0.02%");
    expect(bond.formatBp("9.5e-1")).toBe("1.0 bp");
    expect(normalizeNumeric("1e8", "yuan", false).raw).toBeNull();
  });

  it("preserves legal grouped amounts, unit conversions, and real zero", () => {
    expect(formatYuanAmountAsYiPlain("100,000,000.00")).toBe("1.00");
    expect(formatYuanAmountAsWanPlain("+10,000.00")).toBe("1.00");
    expect(formatWanAmountAsYiPlain("10,000.00")).toBe("1.00");
    expect(bond.formatWan("15,000")).toBe("2 万");
    expect(formatYuanAmountAsWanPlain("0")).toBe("0.00");
    expect(formatYuanAmountAsWanPlain(null)).toBe(EM_DASH);
    expect(formatYuanAmountAsWanPlain("100.005")).toBe("0.01");
  });

  it.each([1, -1])("uses the same half-up policy at positive/negative ties (%s)", (sign) => {
    expect(formatRawAsNumeric({ raw: sign * 0.95, unit: "bp", sign_aware: true }).display)
      .toBe(formatBp(sign * 0.95, true));
    expect(normalizeNumeric(String(sign * 0.00015), "pct", true).display)
      .toBe(formatPercent(sign * 0.00015, true));
    expect(bond.formatBp(String(sign * 0.95))).toBe(sign > 0 ? "1.0 bp" : "-1.0 bp");
    expect(bond.formatPct(String(sign * 0.00015))).toBe(sign > 0 ? "0.02%" : "-0.02%");
    for (const unit of ["years", "ratio"] as const) {
      expect(formatRawAsNumeric({ raw: sign * 1.005, unit, sign_aware: false }).display)
        .toBe(sign > 0 ? "1.01" : "-1.01");
    }
    expect(formatRawAsNumeric({ raw: sign * 0.5, unit: "dv01", sign_aware: false }).display)
      .toBe(sign > 0 ? "1" : "-1");
  });

  it("honors precision overrides and leaves valid server Numeric unchanged", () => {
    expect(formatRawAsNumeric({ raw: 150000, unit: "yuan", sign_aware: false, precision: 3 }).display)
      .toBe("0.002 亿");
    expect(formatRawAsNumeric({ raw: -0.0000015, unit: "pct", sign_aware: false, precision: 4 }).display)
      .toBe("-0.0002%");
    const serverValue = { raw: 0.95, raw_text: "0.95", unit: "bp" as const, display: "source display", precision: 1, sign_aware: false };
    expect(normalizeNumeric(serverValue, "bp", true)).toBe(serverValue);
    expect(bond.formatBp(serverValue)).toBe("source display");
  });

  it("does not round large decimal amounts through a binary-number intermediate", () => {
    expect(formatYuanAmountAsWanPlain("9007199254740949.995")).toBe("900,719,925,474.09");
    expect(formatYuanAmountAsWanPlain("9007199254740950.005")).toBe("900,719,925,474.10");
  });

  it.each([
    ["0.00014999999999999999999", "pct", "+0.01%"],
    ["-0.00014999999999999999999", "pct", "-0.01%"],
    ["0.00015000000000000000001", "pct", "+0.02%"],
    ["-0.00015000000000000000001", "pct", "-0.02%"],
    ["0.94999999999999999999", "bp", "+0.9 bp"],
    ["-0.94999999999999999999", "bp", "-0.9 bp"],
    ["0.95000000000000000001", "bp", "+1.0 bp"],
    ["-0.95000000000000000001", "bp", "-1.0 bp"],
  ] as const)("normalizes exact text %s without crossing its rounding boundary", (raw, unit, expected) => {
    const result = normalizeNumeric(raw, unit, true);
    expect(result.display).toBe(expected);
    expect(result.raw_text).toBe(raw);
    expect(result.raw).toBe(Number(raw)); // Approximate chart compatibility remains explicit.
  });

  it("retains accepted raw_text in a constructed Numeric for later scaled consumers", () => {
    const rawText = "100499999.99999999999";
    const result = formatRawAsNumeric({ raw: Number(rawText), raw_text: rawText, unit: "yuan", sign_aware: false });
    expect(result.raw_text).toBe(rawText);
    expect(result.display).toBe("1.00 亿");
    expect(bond.formatYi(result)).toBe("1.00 亿");
    expect(isNumeric(result)).toBe(true);
  });

  it.each(["1e8", "+1", " 1 ", "12,000", "123abc"])("does not store invalid Numeric raw_text %j", (rawText) => {
    const result = formatRawAsNumeric({ raw: 1, raw_text: rawText, unit: "bp", sign_aware: false });
    expect(result.raw_text).toBeUndefined();
    expect(result.display).toBe("1.0 bp");
    expect(isNumeric(result)).toBe(true);
  });

  it.each([null, undefined, Number.NaN, Number.POSITIVE_INFINITY])("does not revive missing raw %s from decimal text", (raw) => {
    const result = formatRawAsNumeric({ raw, raw_text: "1.2500", unit: "yuan", sign_aware: true });
    expect(result.raw).toBeNull();
    expect(result.raw_text).toBeUndefined();
    expect(result.display).toBe(EM_DASH);
    expect(bond.formatYi({ ...result, raw_text: "1.2500" })).toBe(EM_DASH);
    expect(isNumeric(result)).toBe(true);
  });

  it("omits exact text when its compatibility number overflows", () => {
    const result = normalizeNumeric("9".repeat(400), "yuan", false);
    expect(result.raw).toBeNull();
    expect(result.raw_text).toBeUndefined();
    expect(result.display).toBe(EM_DASH);
    expect(isNumeric(result)).toBe(true);
  });

  it.each([
    ["9007199254740993", "9,007,199,254,740,993"],
    ["-9007199254740993", "-9,007,199,254,740,993"],
  ])("shows every digit in exact integer count %s", (raw, expected) => {
    const result = normalizeNumeric(raw, "count", false);
    expect(result.display).toBe(expected);
    expect(result.raw_text).toBe(raw);
    expect(result.precision).toBe(0);
  });

  it("retains fractional count display compatibility", () => {
    expect(normalizeNumeric("1.2345", "count", false).display).toBe("1.235");
    expect(normalizeNumeric("-1.2345", "count", true).display).toBe("-1.235");
  });

  it("uses the exact display sign when chart compatibility underflows to negative zero", () => {
    const raw = `-0.${"0".repeat(330)}1`;
    const result = normalizeNumeric(raw, "pct", true);
    expect(Object.is(result.raw, -0)).toBe(true);
    expect(result.display).toBe("-0.00%");
    expect(normalizeNumeric("0", "pct", true).display).toBe("+0.00%");
    expect(normalizeNumeric("-0", "pct", true).display).toBe("+0.00%");
  });
});
