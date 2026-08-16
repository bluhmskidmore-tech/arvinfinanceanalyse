import { describe, expect, it } from "vitest";

import type { Numeric } from "../../../api/contracts";
import {
  formatDv01Wan,
  formatEvidenceTimestamp,
  formatMomChange,
  formatMomRatio,
  formatRatePercent,
  formatYears,
  formatYi,
  nativeToNumber,
} from "./format";

function num(raw: number | null, unit: Numeric["unit"] = "ratio"): Numeric {
  return {
    raw,
    unit,
    display: raw === null ? "—" : String(raw),
    precision: 2,
    sign_aware: false,
  };
}

describe("bond dashboard numeric formatters", () => {
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
