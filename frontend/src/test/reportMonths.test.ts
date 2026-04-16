import { describe, expect, it } from "vitest";

import { getCompleteMonthOptions } from "../features/bond-analytics/utils/reportMonths";

describe("getCompleteMonthOptions", () => {
  const referenceDate = new Date(2026, 3, 15);

  it("returns empty array for empty input", () => {
    expect(getCompleteMonthOptions([], referenceDate)).toEqual([]);
  });

  it("dedupes duplicate dates", () => {
    const opts = getCompleteMonthOptions(
      ["2026-03-10", "2026-03-10", "2026-02-01"],
      referenceDate,
    );
    expect(opts.map((o) => o.value)).toEqual(["2026-03-10", "2026-02-01"]);
  });

  it("keeps only the latest date within each month and sorts months descending", () => {
    const opts = getCompleteMonthOptions(
      ["2026-02-01", "2026-03-05", "2026-03-20", "2026-01-10"],
      referenceDate,
    );
    expect(opts.map((o) => o.value)).toEqual([
      "2026-03-20",
      "2026-02-01",
      "2026-01-10",
    ]);
    expect(opts.map((o) => o.label)).toEqual([
      "2026年3月",
      "2026年2月",
      "2026年1月",
    ]);
  });

  it("excludes the reference calendar month", () => {
    const opts = getCompleteMonthOptions(
      ["2026-04-30", "2026-03-01"],
      referenceDate,
    );
    expect(opts.map((o) => o.month)).toEqual(["2026-03"]);
    expect(opts[0]?.label).toBe("2026年3月");
  });

  it("uses label format 年/月 with no leading zero on month number", () => {
    const opts = getCompleteMonthOptions(["2026-03-01"], referenceDate);
    expect(opts[0]?.label).toMatch(/^2026年3月$/);
  });
});
