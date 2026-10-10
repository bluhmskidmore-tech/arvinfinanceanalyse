import { describe, expect, it } from "vitest";

import {
  REPORT_DATE_AGE_WARN_DAYS,
  reportDateAgeDays,
  reportDateAgeTone,
} from "./homeReportDateLabel";

// 固定基准时刻，避免纯函数测试依赖系统时间。
const NOW = new Date(2026, 8, 2, 15, 3);

describe("reportDateAgeDays", () => {
  it("returns 0 for a same-day report date", () => {
    expect(reportDateAgeDays("2026-09-02", NOW)).toBe(0);
  });

  it("counts natural days for a recent report date", () => {
    expect(reportDateAgeDays("2026-08-30", NOW)).toBe(3);
  });

  it("counts natural days across a month boundary", () => {
    expect(reportDateAgeDays("2026-07-31", NOW)).toBe(33);
  });

  it("ignores a trailing time component and surrounding whitespace", () => {
    expect(reportDateAgeDays(" 2026-07-31 16:00 ", NOW)).toBe(33);
    expect(reportDateAgeDays("2026-07-31T16:00:00", NOW)).toBe(33);
  });

  it("is not affected by the wall-clock time of now", () => {
    expect(reportDateAgeDays("2026-09-01", new Date(2026, 8, 2, 0, 0, 1))).toBe(1);
    expect(reportDateAgeDays("2026-09-01", new Date(2026, 8, 2, 23, 59, 59))).toBe(1);
  });

  it("returns a negative number for a future report date", () => {
    expect(reportDateAgeDays("2026-09-05", NOW)).toBe(-3);
  });

  it("returns null for missing or malformed input", () => {
    expect(reportDateAgeDays(null, NOW)).toBeNull();
    expect(reportDateAgeDays(undefined, NOW)).toBeNull();
    expect(reportDateAgeDays("", NOW)).toBeNull();
    expect(reportDateAgeDays("—", NOW)).toBeNull();
    expect(reportDateAgeDays("2026/07/31", NOW)).toBeNull();
    expect(reportDateAgeDays("07-31", NOW)).toBeNull();
  });

  it("returns null for a calendar date that does not exist", () => {
    expect(reportDateAgeDays("2026-02-30", NOW)).toBeNull();
    expect(reportDateAgeDays("2026-13-01", NOW)).toBeNull();
  });

  it("returns null when now is an invalid date", () => {
    expect(reportDateAgeDays("2026-07-31", new Date(Number.NaN))).toBeNull();
  });
});

describe("reportDateAgeTone", () => {
  it("stays silent for same-day, future, or unknown ages", () => {
    expect(reportDateAgeTone(0)).toBeNull();
    expect(reportDateAgeTone(-2)).toBeNull();
    expect(reportDateAgeTone(null)).toBeNull();
  });

  it("uses the muted tone below the warning threshold", () => {
    expect(reportDateAgeTone(1)).toBe("muted");
    expect(reportDateAgeTone(3)).toBe("muted");
    expect(reportDateAgeTone(REPORT_DATE_AGE_WARN_DAYS - 1)).toBe("muted");
  });

  it("switches to the warning tone at the threshold and beyond", () => {
    expect(reportDateAgeTone(REPORT_DATE_AGE_WARN_DAYS)).toBe("warn");
    expect(reportDateAgeTone(33)).toBe("warn");
  });
});
