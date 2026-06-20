import { describe, expect, it } from "vitest";

import { formatAnnualizedYieldPctDisplay, inclusiveCalendarDays } from "./pnlByBusinessAnnualizedYield";

describe("pnlByBusinessAnnualizedYield", () => {
  it("counts inclusive calendar days", () => {
    expect(inclusiveCalendarDays("2025-01-01", "2025-01-01")).toBe(1);
    expect(inclusiveCalendarDays("2025-01-01", "2025-01-02")).toBe(2);
    expect(inclusiveCalendarDays("2025-01-01", "2025-12-31")).toBe(365);
    expect(inclusiveCalendarDays("2024-01-01", "2024-12-31")).toBe(366);
  });

  it("formats backend annualized yield pct points without recalculating", () => {
    expect(formatAnnualizedYieldPctDisplay("9.876543")).toBe("9.88%");
    expect(formatAnnualizedYieldPctDisplay(0)).toBe("0.00%");
  });

  it("returns dash when inputs are unusable", () => {
    expect(formatAnnualizedYieldPctDisplay(null)).toBe("-");
    expect(formatAnnualizedYieldPctDisplay(undefined)).toBe("-");
    expect(formatAnnualizedYieldPctDisplay("")).toBe("-");
    expect(formatAnnualizedYieldPctDisplay("not-a-number")).toBe("-");
  });
});
