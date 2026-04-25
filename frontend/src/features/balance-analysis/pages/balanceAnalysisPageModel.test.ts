import { describe, expect, it } from "vitest";

import {
  BALANCE_ANALYSIS_MIN_CHART_BAR_WIDTH_PCT,
  distributionChartBarWidthPercent,
  formatBalanceAmountToYiFromWan,
  formatBalanceAmountToYiFromYuan,
  formatBalanceGridThousandsValue,
  formatBalanceOverviewNumber,
  formatBalanceScopeTotalAmountToYi,
  formatBalanceWorkbookCellDisplay,
  formatBalanceWorkbookWanAmountDisplay,
  formatBalanceWorkbookWanTextDisplay,
  gapChartBarWidthPercent,
  maxAbsFiniteChartScale,
  maxFiniteChartScale,
  parseBalanceChartMagnitude,
  summarizeBalanceAmountsByPositionScope,
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
      expect(formatBalanceAmountToYiFromYuan("0E-8")).toBe("0.00");
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

    it("adds yi unit labels for workbook wan-yuan amount cells", () => {
      expect(formatBalanceWorkbookWanAmountDisplay("4290357.07")).toBe("429.04 亿元");
      expect(formatBalanceWorkbookWanAmountDisplay("-128000.00")).toBe("-12.80 亿元");
      expect(formatBalanceWorkbookWanAmountDisplay("n/a")).toBe("n/a");
    });

    it("rewrites governed workbook reason text from wan yuan to yi yuan", () => {
      expect(formatBalanceWorkbookWanTextDisplay("Bucket gap is 4290357.07 wan yuan.")).toBe(
        "Bucket gap is 429.04 亿元.",
      );
      expect(formatBalanceWorkbookWanTextDisplay("Gap dropped to -128000.00 wan yuan.")).toBe(
        "Gap dropped to -12.80 亿元.",
      );
      expect(formatBalanceWorkbookWanTextDisplay("No numeric amount here.")).toBe("No numeric amount here.");
    });

    it("rewrites 万元 (Chinese) amounts in workbook notes the same as wan yuan", () => {
      expect(formatBalanceWorkbookWanTextDisplay("观测峰值 99.00 万元。")).toBe("观测峰值 0.01 亿元。");
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

  describe("position-scope amount summaries", () => {
    it("separates asset and liability totals instead of combining them", () => {
      const totals = summarizeBalanceAmountsByPositionScope([
        {
          position_scope: "asset",
          row_count: 174,
          market_value_amount: "24145782559.52",
          amortized_cost_amount: "24145782559.52",
          accrued_interest_amount: "186447192.86",
        },
        {
          position_scope: "liability",
          row_count: 2125,
          market_value_amount: "64768888887.83",
          amortized_cost_amount: "64768888887.83",
          accrued_interest_amount: "13996586.21",
        },
        {
          position_scope: "asset",
          row_count: 1711,
          market_value_amount: "333925726735.544",
          amortized_cost_amount: "327352769214.272",
          accrued_interest_amount: "25793215.37",
        },
        {
          position_scope: "liability",
          row_count: 129,
          market_value_amount: "119804097177.69",
          amortized_cost_amount: "120453500738.43",
          accrued_interest_amount: "0E-8",
        },
      ]);

      expect(totals.asset.rowCount).toBe(1885);
      expect(formatBalanceScopeTotalAmountToYi(totals.asset, "marketValueAmount")).toBe("3,580.72");
      expect(formatBalanceScopeTotalAmountToYi(totals.asset, "amortizedCostAmount")).toBe("3,514.99");
      expect(formatBalanceScopeTotalAmountToYi(totals.asset, "accruedInterestAmount")).toBe("2.12");
      expect(totals.liability.rowCount).toBe(2254);
      expect(formatBalanceScopeTotalAmountToYi(totals.liability, "marketValueAmount")).toBe("1,845.73");
      expect(formatBalanceScopeTotalAmountToYi(totals.liability, "amortizedCostAmount")).toBe("1,852.22");
      expect(formatBalanceScopeTotalAmountToYi(totals.liability, "accruedInterestAmount")).toBe("0.14");
    });
  });
});
