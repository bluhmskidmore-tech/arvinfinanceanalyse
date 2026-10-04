import { describe, expect, it } from "vitest";

import type { Numeric } from "../../../api/contracts";
import {
  computeFallbackPercentages,
  exactDecimalOrNull,
  formatDv01Wan,
  formatEvidenceTimestamp,
  formatMomChange,
  formatMomRatio,
  formatRatioPercent,
  formatRatePercent,
  formatYears,
  formatYi,
  nativeToNumber,
} from "./format";

function num(raw: number | null, unit: Numeric["unit"] = "ratio", rawText?: string): Numeric {
  return {
    raw,
    ...(rawText === undefined ? {} : { raw_text: rawText }),
    unit,
    display: raw === null ? "—" : String(raw),
    precision: 2,
    sign_aware: false,
  };
}

describe("bond dashboard numeric formatters", () => {
  it("prefers raw_text for yi display when the float raw is approximate", () => {
    expect(formatYi(num(100_000_000, "yuan", "150000000.00000000"))).toBe("1.50");
  });

  it("does not treat raw-only governed numerics as exact decimals", () => {
    expect(exactDecimalOrNull(num(150_000_000, "yuan"))).toBeNull();
    expect(exactDecimalOrNull(num(100_000_000, "yuan", "150000000.00000000"))?.toString()).toBe(
      "150000000",
    );
  });

  it("keeps the legacy raw-only yi display path unchanged", () => {
    expect(formatYi(num(150_000_000, "yuan"))).toBe("1.50");
  });

  it("prefers raw_text for ratio-percent display when the float raw is approximate", () => {
    expect(formatRatioPercent(num(0.1, "ratio", "0.123456"))).toBe("12.35");
  });

  it("preserves missing governed numerics instead of rendering zero", () => {
    expect(nativeToNumber(num(null))).toBeNull();
    expect(nativeToNumber(undefined)).toBeNull();
    expect(formatYi(num(null))).toBe("—");
    expect(formatRatePercent(num(null))).toBe("—");
    expect(formatDv01Wan(num(null))).toBe("—");
    expect(formatYears(num(null))).toBe("—");
  });

  it("does not emit a fake -100% MoM when the current value is missing", () => {
    expect(formatMomRatio(num(null), num(100))).toBeNull();
  });

  it("uses the absolute previous value as the MoM denominator", () => {
    expect(formatMomRatio(num(-80), num(-100))).toBe("+20.00%");
    expect(formatMomRatio(num(-120), num(-100))).toBe("-20.00%");
    expect(formatMomRatio(num(120), num(100))).toBe("+20.00%");
  });

  it("returns null when either value is missing or the previous value is zero", () => {
    expect(formatMomRatio(num(100), null)).toBeNull();
    expect(formatMomRatio(num(100), num(null))).toBeNull();
    expect(formatMomRatio(num(100), num(0))).toBeNull();
    expect(formatMomRatio(null, num(-100))).toBeNull();
    expect(formatMomRatio(num(null), num(-100))).toBeNull();
  });
});

describe("formatEvidenceTimestamp", () => {
  it("collapses microsecond ISO timestamps to second precision", () => {
    // 无时区标记的 ISO 按本地时间解析，格式化结果与输入同钟面（跨 TZ 稳定）。
    expect(formatEvidenceTimestamp("2026-08-13T21:05:33.123456")).toBe("2026-08-13 21:05:33");
    expect(formatEvidenceTimestamp("2026-08-13T00:00:00")).toBe("2026-08-13 00:00:00");
  });

  it("returns unparseable values unchanged instead of fabricating a time", () => {
    expect(formatEvidenceTimestamp("")).toBe("");
    expect(formatEvidenceTimestamp("not-a-timestamp")).toBe("not-a-timestamp");
  });
});

describe("bond dashboard month-over-month change by KPI kind", () => {
  it("reports rate and spread moves as a basis-point difference", () => {
    expect(formatMomChange("rateBp", num(0.026), num(0.025))).toBe("+10.0bp");
    expect(formatMomChange("rateBp", num(0.024), num(0.025))).toBe("-10.0bp");
    expect(formatMomChange("rateBp", num(0.025), num(0.025))).toBe("0.0bp");
    // A rate baseline of zero is a valid starting point, unlike a ratio denominator.
    expect(formatMomChange("rateBp", num(0.0125), num(0))).toBe("+125.0bp");
  });

  it("respects the declared unit when a spread already arrives in bp", () => {
    expect(formatMomChange("rateBp", num(72, "bp"), num(69, "bp"))).toBe("+3.0bp");
    // Mixed bases cannot be differenced without silently rescaling by 10,000.
    expect(formatMomChange("rateBp", num(72, "bp"), num(0.0069, "pct"))).toBeNull();
  });

  it("never renders a near-zero bp delta as -0.0bp", () => {
    // A direct bp-unit delta that is small and negative: naive (-0.03).toFixed(1) is
    // the JS classic "-0.0" bug (sign kept even though the value floors to zero).
    expect(formatMomChange("rateBp", num(-0.03, "bp"), num(0, "bp"))).toBe("0.0bp");
    // A ratio-unit pair whose *10,000 multiplication leaves float tail noise
    // (delta ~= -0.0200000007bp), captured verbatim from a randomized float search.
    expect(
      formatMomChange("rateBp", num(0.0067120000000096885), num(0.006714000000716368)),
    ).toBe("0.0bp");
  });

  it("rounds a bp delta to one decimal via integer scaling instead of raw toFixed", () => {
    // (72.05 - 69).toFixed(1) already truncates to "3.0" from float subtraction tail;
    // the integer-scaled path must reproduce the same, stable, non-negative-zero output.
    expect(formatMomChange("rateBp", num(72.05, "bp"), num(69, "bp"))).toBe("+3.0bp");
  });

  it("reports sign-variable P&L as an absolute yi difference", () => {
    expect(formatMomChange("amountYi", num(35_000_000), num(0))).toBe("+0.35 亿");
    expect(formatMomChange("amountYi", num(-20_000_000), num(15_000_000))).toBe("-0.35 亿");
    expect(formatMomChange("amountYi", num(15_000_000), num(15_000_000))).toBe("0.00 亿");
  });

  it("keeps level amounts on the relative percent change", () => {
    expect(formatMomChange("percent", num(120), num(100))).toBe("+20.00%");
    expect(formatMomChange("percent", num(100), num(0))).toBeNull();
  });

  it("returns null for every kind when a side is missing", () => {
    expect(formatMomChange("rateBp", num(null), num(0.025))).toBeNull();
    expect(formatMomChange("rateBp", num(0.025), num(null))).toBeNull();
    expect(formatMomChange("rateBp", num(0.025), null)).toBeNull();
    expect(formatMomChange("amountYi", num(null), num(100))).toBeNull();
    expect(formatMomChange("amountYi", num(100), undefined)).toBeNull();
  });
});

describe("computeFallbackPercentages", () => {
  it("corrects independent per-item truncation so the fallback set foots to 100.00", () => {
    // 1 : 1 : 4 shares -> raw 16.6667% / 16.6667% / 66.6667%; naive toFixed(2) on each
    // gives 16.67 + 16.67 + 66.67 = 100.01. The largest holding (index 2) absorbs the
    // -0.01 residual instead of every category truncating independently.
    const items = [
      { total_market_value: num(1), percentage: null },
      { total_market_value: num(1), percentage: null },
      { total_market_value: num(4), percentage: null },
    ];
    const result = computeFallbackPercentages(items);
    expect(result).toEqual([16.67, 16.67, 66.66]);
    expect(result.reduce<number>((sum, v) => sum + (v ?? 0), 0)).toBeCloseTo(100, 10);
  });

  it("breaks an exact three-way tie by correcting the earliest item", () => {
    // 1 : 1 : 1 shares -> 33.3333% each; naive toFixed(2) sums to 99.99.
    const items = [
      { total_market_value: num(1), percentage: null },
      { total_market_value: num(1), percentage: null },
      { total_market_value: num(1), percentage: null },
    ];
    const result = computeFallbackPercentages(items);
    expect(result).toEqual([33.34, 33.33, 33.33]);
    expect(result.reduce<number>((sum, v) => sum + (v ?? 0), 0)).toBeCloseTo(100, 10);
  });

  it("leaves backend-supplied percentages untouched and only corrects the fallback subset", () => {
    const items = [
      { total_market_value: num(60), percentage: num(0.2) },
      { total_market_value: num(20), percentage: null },
      { total_market_value: num(20), percentage: null },
    ];
    const result = computeFallbackPercentages(items);
    // Backend item is unaffected (null = "not this path"); fallback subset foots to
    // 100 - 20 (the backend item's own percent), not to 100 on its own.
    expect(result[0]).toBeNull();
    expect(result[1]).toBe(40);
    expect(result[2]).toBe(40);
    expect((result[1] ?? 0) + (result[2] ?? 0)).toBeCloseTo(80, 10);
  });

  it("weights the mixed exact fallback subset by its own subtotal instead of the full portfolio", () => {
    const items = [
      { total_market_value: num(60, "yuan", "60.00000000"), percentage: num(0.2, "ratio", "0.20000000") },
      { total_market_value: num(20, "yuan", "20.00000000"), percentage: null },
      { total_market_value: num(20, "yuan", "20.00000000"), percentage: null },
    ];
    expect(computeFallbackPercentages(items)).toEqual([null, 40, 40]);
  });

  it("preserves the deterministic zero-subtotal residual assignment on the mixed path", () => {
    const items = [
      { total_market_value: num(60), percentage: num(0.2) },
      { total_market_value: num(0), percentage: null },
      { total_market_value: num(0), percentage: null },
    ];
    expect(computeFallbackPercentages(items)).toEqual([null, 80, 0]);
  });

  it("returns all-null when every item already carries a backend percentage", () => {
    const items = [
      { total_market_value: num(60), percentage: num(0.6) },
      { total_market_value: num(40), percentage: num(0.4) },
    ];
    expect(computeFallbackPercentages(items)).toEqual([null, null]);
  });
});
