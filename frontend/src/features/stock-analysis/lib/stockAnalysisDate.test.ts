import { describe, expect, it } from "vitest";

import { normalizeIsoCalendarDate, subtractIsoCalendarDays } from "./stockAnalysisDate";

describe("stockAnalysisDate", () => {
  it("normalizes valid ISO calendar dates without applying a timezone", () => {
    expect(normalizeIsoCalendarDate("2026-04-29")).toBe("2026-04-29");
    expect(normalizeIsoCalendarDate(" 2024-02-29 ")).toBe("2024-02-29");
  });

  it("rejects malformed or impossible calendar dates", () => {
    expect(normalizeIsoCalendarDate(null)).toBeNull();
    expect(normalizeIsoCalendarDate("")).toBeNull();
    expect(normalizeIsoCalendarDate("2026-2-09")).toBeNull();
    expect(normalizeIsoCalendarDate("2026-02-29")).toBeNull();
    expect(normalizeIsoCalendarDate("2026-13-01")).toBeNull();
    expect(normalizeIsoCalendarDate("0000-01-01")).toBeNull();
  });

  it("subtracts UTC calendar days across month, year, and leap-day boundaries", () => {
    expect(subtractIsoCalendarDays("2026-04-29", 10)).toBe("2026-04-19");
    expect(subtractIsoCalendarDays("2026-01-05", 10)).toBe("2025-12-26");
    expect(subtractIsoCalendarDays("2026-03-01", 1)).toBe("2026-02-28");
    expect(subtractIsoCalendarDays("2024-03-01", 1)).toBe("2024-02-29");
    expect(subtractIsoCalendarDays("2026-04-29", 0)).toBe("2026-04-29");
  });

  it("fails closed for invalid dates or day offsets", () => {
    expect(subtractIsoCalendarDays("2026-02-29", 10)).toBeNull();
    expect(subtractIsoCalendarDays("2026-04-29", -1)).toBeNull();
    expect(subtractIsoCalendarDays("2026-04-29", 1.5)).toBeNull();
    expect(subtractIsoCalendarDays("2026-04-29", Number.NaN)).toBeNull();
  });
});
