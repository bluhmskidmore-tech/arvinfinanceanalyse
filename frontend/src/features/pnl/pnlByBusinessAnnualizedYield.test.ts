import { describe, expect, it } from "vitest";

import { formatAnnualizedYieldPctDisplay, inclusiveCalendarDays } from "./pnlByBusinessAnnualizedYield";

describe("pnlByBusinessAnnualizedYield", () => {
  it("counts inclusive calendar days", () => {
    expect(inclusiveCalendarDays("2025-01-01", "2025-01-01")).toBe(1);
    expect(inclusiveCalendarDays("2025-01-01", "2025-01-02")).toBe(2);
    expect(inclusiveCalendarDays("2025-01-01", "2025-12-31")).toBe(365);
    expect(inclusiveCalendarDays("2024-01-01", "2024-12-31")).toBe(366);
  });

  it("formats annualized yield from PnL, ADB, and days", () => {
    const pnl = 130_000;
    const adb = 100_000_000;
    const days = 365;
    expect(formatAnnualizedYieldPctDisplay(pnl, adb, days)).toBe("0.13%");
  });

  it("returns dash when inputs are unusable", () => {
    expect(formatAnnualizedYieldPctDisplay(null, 1, 30)).toBe("-");
    expect(formatAnnualizedYieldPctDisplay(1, undefined, 30)).toBe("-");
    expect(formatAnnualizedYieldPctDisplay(1, 0, 30)).toBe("-");
    expect(formatAnnualizedYieldPctDisplay(1, 100, null)).toBe("-");
    expect(formatAnnualizedYieldPctDisplay(1, 100, 0)).toBe("-");
  });
});
