import { describe, expect, it } from "vitest";

import {
  BALANCE_ANALYSIS_MIN_CHART_BAR_WIDTH_PCT,
  distributionChartBarWidthPercent,
  formatBalanceAmountToYiFromWan,
  formatBalanceAmountToYiFromYuan,
  formatBalanceGridThousandsValue,
  formatBalanceOverviewNumber,
  formatBalanceWorkbookCellDisplay,
  gapChartBarWidthPercent,
  maxAbsFiniteChartScale,
  maxFiniteChartScale,
  parseBalanceChartMagnitude,
} from "./balanceAnalysisPageModel";

describe("balanceAnalysisPageModel", () => {
  describe("display formatters", () => {
    it("shows em dash for null, undefined, and empty string", () => {
      expect(formatBalanceOverviewNumber(null)).toBe("—");
      expect(formatBalanceOverviewNumber(undefined)).toBe("—");
      expect(formatBalanceOverviewNumber("")).toBe("—");
      expect(formatBalanceAmountToYiFromYuan(null)).toBe("—");
      expect(formatBalanceAmountToYiFromYuan(undefined)).toBe("—");
      expect(formatBalanceAmountToYiFromYuan("")).toBe("—");
      expect(formatBalanceAmountToYiFromWan(null)).toBe("—");
      expect(formatBalanceWorkbookCellDisplay(null)).toBe("—");
      expect(formatBalanceWorkbookCellDisplay(undefined)).toBe("—");
      expect(formatBalanceWorkbookCellDisplay("")).toBe("—");
      expect(formatBalanceGridThousandsValue(null)).toBe("—");
      expect(formatBalanceGridThousandsValue(undefined)).toBe("—");
      expect(formatBalanceGridThousandsValue("")).toBe("—");
    });

    it("treats string zero as a legitimate numeric zero, not missing", () => {
      expect(formatBalanceOverviewNumber("0")).toBe("0");
      expect(parseBalanceChartMagnitude("0")).toEqual({ kind: "finite", value: 0 });
      expect(formatBalanceWorkbookCellDisplay("0")).toBe("0");
      expect(formatBalanceGridThousandsValue("0")).toBe("0");
    });

    it("keeps invalid strings visible as the original input for overview and yi formatters", () => {
      expect(formatBalanceOverviewNumber("not-a-number")).toBe("not-a-number");
      expect(formatBalanceAmountToYiFromYuan("12abc")).toBe("12abc");
      expect(formatBalanceAmountToYiFromWan("n/a")).toBe("n/a");
    });

    it("formats comma-containing numeric strings like the page helpers", () => {
      expect(formatBalanceOverviewNumber("1,234.5")).toBe("1,234.5");
      expect(formatBalanceGridThousandsValue("1,234")).toBe("1,234");
      expect(formatBalanceAmountToYiFromYuan("100,000,000")).toBe("1.00");
    });

    it("matches yuan-to-yi and wan-to-yi locale precision (zh-CN, 2 decimals)", () => {
      expect(formatBalanceAmountToYiFromYuan(100_000_000)).toBe("1.00");
      expect(formatBalanceAmountToYiFromYuan("123456789")).toBe(
        (123_456_789 / 100_000_000).toLocaleString("zh-CN", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        }),
      );
      expect(formatBalanceAmountToYiFromWan(10_000)).toBe("1.00");
      expect(formatBalanceAmountToYiFromWan("25000.25")).toBe(
        (25_000.25 / 10_000).toLocaleString("zh-CN", {
          minimumFractionDigits: 2,
          maximumFractionDigits: 2,
        }),
      );
    });
  });

  describe("chart magnitude and widths", () => {
    it("does not treat invalid magnitudes as legitimate zero-width bars (null, not min bar)", () => {
      const invalid = parseBalanceChartMagnitude("oops");
      expect(invalid.kind).toBe("invalid");
      expect(distributionChartBarWidthPercent(invalid, 100)).toBeNull();
      expect(gapChartBarWidthPercent(invalid, 100)).toBeNull();
    });

    it("treats finite zero as a real zero magnitude with the minimum bar width", () => {
      const zero = parseBalanceChartMagnitude("0");
      expect(zero).toEqual({ kind: "finite", value: 0 });
      expect(distributionChartBarWidthPercent(zero, 100)).toBe(BALANCE_ANALYSIS_MIN_CHART_BAR_WIDTH_PCT);
      expect(gapChartBarWidthPercent(zero, 100)).toBe(BALANCE_ANALYSIS_MIN_CHART_BAR_WIDTH_PCT);
    });

    it("uses absolute magnitude for gap bar width while preserving negative sign in workbook display", () => {
      const neg = parseBalanceChartMagnitude("-40");
      expect(neg).toEqual({ kind: "finite", value: -40 });
      expect(formatBalanceWorkbookCellDisplay(-40)).toBe("-40");
      expect(formatBalanceWorkbookCellDisplay("-40")).toBe("-40");
      expect(maxAbsFiniteChartScale(["-40", "10"])).toBe(40);
      expect(gapChartBarWidthPercent(neg, 40)).toBe(
        Math.max(BALANCE_ANALYSIS_MIN_CHART_BAR_WIDTH_PCT, (40 / 40) * 100),
      );
    });

    it("ignores invalid cells when computing max scale so bars are not pinned to a fake zero denominator", () => {
      expect(maxFiniteChartScale(["bad", 50, 30])).toBe(50);
      expect(maxAbsFiniteChartScale(["bad", "-30", 10])).toBe(30);
    });
  });
});
