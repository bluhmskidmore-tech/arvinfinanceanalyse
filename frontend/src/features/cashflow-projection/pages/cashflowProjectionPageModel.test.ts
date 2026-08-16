import { describe, expect, it } from "vitest";

import type { Numeric } from "../../../api/contracts";
import type { CashflowProjectionVM } from "../adapters/cashflowProjectionAdapter";
import {
  describeCashflowWarning,
  selectCashflowDurationGapTone,
  selectCashflowMonthlyProjectionSeries,
  selectCashflowProjectionRiskReadout,
  selectCashflowRateSensitivitySemantic,
  tooltipYi,
} from "./cashflowProjectionPageModel";

function n(partial: Partial<Numeric> = {}): Numeric {
  return {
    raw: 1,
    unit: "yuan",
    display: "1.00",
    precision: 2,
    sign_aware: false,
    ...partial,
  };
}

function makeVM(partial: Partial<CashflowProjectionVM> = {}): CashflowProjectionVM {
  return {
    reportDate: "2026-04-01",
    kpis: {
      durationGap: n({ unit: "years" }),
      assetDuration: n({ unit: "years" }),
      liabilityDuration: n({ unit: "years" }),
      equityDuration: n({ unit: "years" }),
      rateSensitivity1bp: n(),
      reinvestmentRisk12m: n({ unit: "pct" }),
    },
    monthlyBuckets: [],
    topMaturingAssets: [],
    warnings: [],
    ...partial,
  };
}

describe("selectCashflowMonthlyProjectionSeries", () => {
  it("returns null when there is no projection bucket", () => {
    expect(selectCashflowMonthlyProjectionSeries(null)).toBeNull();
    expect(selectCashflowMonthlyProjectionSeries(makeVM())).toBeNull();
  });

  it("projects monthly buckets into chart series in source order", () => {
    const series = selectCashflowMonthlyProjectionSeries(
      makeVM({
        monthlyBuckets: [
          {
            yearMonth: "2026-04",
            assetInflow: n({ raw: 100 }),
            liabilityOutflow: n({ raw: 40 }),
            netCashflow: n({ raw: 60 }),
            cumulativeNet: n({ raw: 60 }),
          },
          {
            yearMonth: "2026-05",
            assetInflow: n({ raw: 120 }),
            liabilityOutflow: n({ raw: 140 }),
            netCashflow: n({ raw: -20 }),
            cumulativeNet: n({ raw: 40 }),
          },
        ],
      }),
    );

    expect(series).toEqual({
      categories: ["2026-04", "2026-05"],
      assetInflow: [100, 120],
      liabilityOutflow: [40, 140],
      cumulativeNet: [60, 40],
    });
  });

  it("keeps missing or non-finite raw values as null so the chart breaks instead of plotting zero", () => {
    const series = selectCashflowMonthlyProjectionSeries(
      makeVM({
        monthlyBuckets: [
          {
            yearMonth: "2026-04",
            assetInflow: n({ raw: null }),
            liabilityOutflow: n({ raw: Number.NaN }),
            netCashflow: n({ raw: null }),
            cumulativeNet: n({ raw: Number.POSITIVE_INFINITY }),
          },
          {
            yearMonth: "2026-05",
            assetInflow: n({ raw: 0 }),
            liabilityOutflow: n({ raw: 0 }),
            netCashflow: n({ raw: 0 }),
            cumulativeNet: n({ raw: 0 }),
          },
        ],
      }),
    );

    expect(series?.assetInflow).toEqual([null, 0]);
    expect(series?.liabilityOutflow).toEqual([null, 0]);
    expect(series?.cumulativeNet).toEqual([null, 0]);
  });
});

describe("selectCashflowProjectionRiskReadout", () => {
  it("summarizes negative cumulative months and peak liability outflow", () => {
    const readout = selectCashflowProjectionRiskReadout(
      makeVM({
        monthlyBuckets: [
          {
            yearMonth: "2026-04",
            assetInflow: n({ raw: 100_0000_0000, display: "10,000,000,000.00" }),
            liabilityOutflow: n({ raw: 40_0000_0000, display: "4,000,000,000.00" }),
            netCashflow: n({ raw: 60_0000_0000, display: "6,000,000,000.00" }),
            cumulativeNet: n({ raw: 60_0000_0000, display: "6,000,000,000.00" }),
          },
          {
            yearMonth: "2026-05",
            assetInflow: n({ raw: 10_0000_0000, display: "1,000,000,000.00" }),
            liabilityOutflow: n({ raw: 140_0000_0000, display: "14,000,000,000.00" }),
            netCashflow: n({ raw: -130_0000_0000, display: "-13,000,000,000.00" }),
            cumulativeNet: n({ raw: -70_0000_0000, display: "-7,000,000,000.00" }),
          },
          {
            yearMonth: "2026-06",
            assetInflow: n({ raw: 80_0000_0000, display: "8,000,000,000.00" }),
            liabilityOutflow: n({ raw: 30_0000_0000, display: "3,000,000,000.00" }),
            netCashflow: n({ raw: 50_0000_0000, display: "5,000,000,000.00" }),
            cumulativeNet: n({ raw: -20_0000_0000, display: "-2,000,000,000.00" }),
          },
        ],
      }),
    );

    // 主值按亿元缩写展示，后端原始精度串收进 title。
    expect(readout).toMatchObject({
      tone: "warning",
      summary: "2 个月累计净现金流为负",
      negativeCumulativeMonths: 2,
      worstCumulativeMonth: "2026-05",
      worstCumulativeDisplay: "-70.00 亿",
      worstCumulativeTitle: "-7,000,000,000.00",
      largestOutflowMonth: "2026-05",
      largestOutflowDisplay: "140.00 亿",
      largestOutflowTitle: "14,000,000,000.00",
      finalCumulativeDisplay: "-20.00 亿",
      finalCumulativeTitle: "-2,000,000,000.00",
    });
  });

  it("marks a projection positive when cumulative net cashflow never goes negative", () => {
    const readout = selectCashflowProjectionRiskReadout(
      makeVM({
        monthlyBuckets: [
          {
            yearMonth: "2026-04",
            assetInflow: n({ raw: 100_0000_0000, display: "10,000,000,000.00" }),
            liabilityOutflow: n({ raw: 40_0000_0000, display: "4,000,000,000.00" }),
            netCashflow: n({ raw: 60_0000_0000, display: "6,000,000,000.00" }),
            cumulativeNet: n({ raw: 60_0000_0000, display: "6,000,000,000.00" }),
          },
        ],
      }),
    );

    expect(readout).toMatchObject({
      tone: "positive",
      summary: "未见累计净现金流为负月份",
      negativeCumulativeMonths: 0,
      missingCumulativeMonths: 0,
      worstCumulativeMonth: "2026-04",
      finalCumulativeDisplay: "60.00 亿",
      finalCumulativeTitle: "6,000,000,000.00",
    });
  });

  it("never reads positive while cumulative months are missing", () => {
    const readout = selectCashflowProjectionRiskReadout(
      makeVM({
        monthlyBuckets: [
          {
            yearMonth: "2026-04",
            assetInflow: n({ raw: 100_0000_0000, display: "10,000,000,000.00" }),
            liabilityOutflow: n({ raw: 40_0000_0000, display: "4,000,000,000.00" }),
            netCashflow: n({ raw: 60_0000_0000, display: "6,000,000,000.00" }),
            cumulativeNet: n({ raw: 60_0000_0000, display: "6,000,000,000.00" }),
          },
          {
            yearMonth: "2026-05",
            assetInflow: n({ raw: null, display: "—" }),
            liabilityOutflow: n({ raw: null, display: "—" }),
            netCashflow: n({ raw: null, display: "—" }),
            cumulativeNet: n({ raw: null, display: "—" }),
          },
        ],
      }),
    );

    expect(readout).toMatchObject({
      tone: "neutral",
      summary: "1 个月累计净现金流缺数",
      negativeCumulativeMonths: 0,
      missingCumulativeMonths: 1,
      // Missing buckets must not win the worst/largest reduce.
      worstCumulativeMonth: "2026-04",
      worstCumulativeDisplay: "60.00 亿",
      worstCumulativeTitle: "6,000,000,000.00",
      largestOutflowMonth: "2026-04",
      largestOutflowDisplay: "40.00 亿",
      largestOutflowTitle: "4,000,000,000.00",
      // 期末桶缺数：回退后端 display，title 不重复同一占位。
      finalCumulativeDisplay: "—",
      finalCumulativeTitle: null,
    });
  });

  it("reports negative and missing months together and stays on warning", () => {
    const readout = selectCashflowProjectionRiskReadout(
      makeVM({
        monthlyBuckets: [
          {
            yearMonth: "2026-04",
            assetInflow: n({ raw: 10, display: "10.00" }),
            liabilityOutflow: n({ raw: 90, display: "90.00" }),
            netCashflow: n({ raw: -80, display: "-80.00" }),
            cumulativeNet: n({ raw: -80, display: "-80.00" }),
          },
          {
            yearMonth: "2026-05",
            assetInflow: n({ raw: null, display: "—" }),
            liabilityOutflow: n({ raw: null, display: "—" }),
            netCashflow: n({ raw: null, display: "—" }),
            cumulativeNet: n({ raw: null, display: "—" }),
          },
        ],
      }),
    );

    expect(readout).toMatchObject({
      tone: "warning",
      summary: "1 个月累计净现金流为负 · 1 个月累计净现金流缺数",
      negativeCumulativeMonths: 1,
      missingCumulativeMonths: 1,
    });
  });

  it("falls back to the em dash when every bucket value is missing", () => {
    const readout = selectCashflowProjectionRiskReadout(
      makeVM({
        monthlyBuckets: [
          {
            yearMonth: "2026-04",
            assetInflow: n({ raw: null, display: "—" }),
            liabilityOutflow: n({ raw: null, display: "—" }),
            netCashflow: n({ raw: null, display: "—" }),
            cumulativeNet: n({ raw: null, display: "—" }),
          },
        ],
      }),
    );

    expect(readout).toMatchObject({
      tone: "neutral",
      negativeCumulativeMonths: 0,
      missingCumulativeMonths: 1,
      worstCumulativeMonth: "—",
      worstCumulativeDisplay: "—",
      worstCumulativeTitle: null,
      largestOutflowMonth: "—",
      largestOutflowDisplay: "—",
      largestOutflowTitle: null,
    });
  });
});

describe("tooltipYi", () => {
  it("keeps missing bucket values as EM_DASH instead of coercing them to 0.00 亿", () => {
    // 图表 tooltip 直接透传 value：null/undefined/"" 不得先被 Number() 变成 0。
    expect(tooltipYi(null)).toBe("—");
    expect(tooltipYi(undefined)).toBe("—");
    expect(tooltipYi("")).toBe("—");
    expect(tooltipYi(Number.NaN)).toBe("—");
    expect(tooltipYi("not-a-number")).toBe("—");
    expect(tooltipYi(Number.POSITIVE_INFINITY)).toBe("—");
  });

  it("formats finite yuan values into yi with two decimals", () => {
    expect(tooltipYi(-97_566_311_714.31)).toBe("-975.66 亿");
    expect(tooltipYi(6_000_000_000)).toBe("60.00 亿");
    expect(tooltipYi("125000000")).toBe("1.25 亿");
    expect(tooltipYi(123_456_000_000)).toBe("1,234.56 亿");
    expect(tooltipYi(0)).toBe("0.00 亿");
  });
});

describe("describeCashflowWarning", () => {
  it("maps the liability remaining-term proxy caveat to a Chinese summary and keeps the original", () => {
    const original =
      "Liability duration uses a remaining-term proxy (years to maturity), not a cashflow-weighted duration.";
    expect(describeCashflowWarning(original)).toEqual({
      summary: "负债久期为剩余期限（到期年限）代理，非现金流加权久期。",
      original,
    });
  });

  it("maps the floating-rate frozen-coupon caveat and abbreviates the embedded amount into yi", () => {
    const original =
      "231 floating-rate rows with market_value=97566311714.31234567 use the current coupon rate as a frozen proxy for the full projection horizon; reset rates are not modeled.";
    expect(describeCashflowWarning(original)).toEqual({
      summary: "231 个浮息行按当前票息冻结推演全期，不建模利率重定价（市值 975.66 亿）。",
      original,
    });
  });

  it("maps the annual payment-frequency proxy caveat with the amount in yi", () => {
    const original =
      "1872 rows with market_value=310905462685.36000000 lack an explicit payment frequency; annual coupon frequency is used as a proxy.";
    expect(describeCashflowWarning(original)).toEqual({
      summary: "1872 行缺付息频率，按年付代理（市值 3,109.05 亿）。",
      original,
    });
  });

  it("maps the bullet value_date fallback caveat with the amount in yi", () => {
    const original =
      "3 explicit bullet rows with market_value=1200000000.00000000 lack a valid value_date; a one-year interest proxy is used.";
    expect(describeCashflowWarning(original)).toEqual({
      summary: "3 个一次性还本付息行缺有效起息日，按一年期利息代理（市值 12.00 亿）。",
      original,
    });
  });

  it("maps the excluded duration-balance caveat for both asset and liability sides", () => {
    const asset =
      "1000000000.00000000 of 4000000000.00000000 asset market value lacks duration information; the duration gap uses only the duration-covered balance and does not extrapolate the covered average duration onto the excluded balance.";
    expect(describeCashflowWarning(asset).summary).toBe(
      "资产市值 10.00 亿（合计 40.00 亿）缺久期信息；久期缺口仅按久期覆盖余额计算，不向缺失部分外推。",
    );
    const liability =
      "500000000.00000000 of 2000000000.00000000 liability value lacks duration information; the duration gap uses only the duration-covered balance and does not extrapolate the covered average duration onto the excluded balance.";
    expect(describeCashflowWarning(liability).summary).toBe(
      "负债价值 5.00 亿（合计 20.00 亿）缺久期信息；久期缺口仅按久期覆盖余额计算，不向缺失部分外推。",
    );
  });

  it("passes through unregistered sentences verbatim without a duplicated original", () => {
    const unregistered = "Equity is zero; equity duration and 1bp sensitivity were set to zero.";
    expect(describeCashflowWarning(unregistered)).toEqual({
      summary: unregistered,
      original: null,
    });
  });

  it("falls back to verbatim passthrough when the embedded amount cannot be parsed", () => {
    const overflow =
      "2 floating-rate rows with market_value=1E+400 use the current coupon rate as a frozen proxy for the full projection horizon; reset rates are not modeled.";
    expect(describeCashflowWarning(overflow)).toEqual({
      summary: overflow,
      original: null,
    });
  });
});

describe("selectCashflowRateSensitivitySemantic", () => {
  it("marks negative 1bp sensitivity as equity-loss semantics", () => {
    expect(selectCashflowRateSensitivitySemantic(n({ raw: -80_000_000, unit: "yuan" }))).toEqual({
      tone: "negative",
      detail: "利率上行 1bp → 权益减少（原始单位：元）",
    });
  });

  it("marks positive 1bp sensitivity as equity-gain semantics", () => {
    expect(selectCashflowRateSensitivitySemantic(n({ raw: 20_000_000, unit: "yuan" }))).toEqual({
      tone: "positive",
      detail: "利率上行 1bp → 权益增加（原始单位：元）",
    });
  });
});

describe("selectCashflowDurationGapTone", () => {
  it("never maps a positive duration gap to up/green positive tone", () => {
    expect(selectCashflowDurationGapTone(n({ raw: 1.25, unit: "years" }))).toBe("warning");
    expect(selectCashflowDurationGapTone(n({ raw: 0.02, unit: "years" }))).toBe("gapPositive");
    expect(selectCashflowDurationGapTone(n({ raw: 0, unit: "years" }))).toBe("default");
  });

  it("keeps negative duration gap as directional down tone", () => {
    expect(selectCashflowDurationGapTone(n({ raw: -0.75, unit: "years" }))).toBe("negative");
  });

  it("marks missing duration gap as warning", () => {
    expect(selectCashflowDurationGapTone(n({ raw: null, unit: "years" }))).toBe("warning");
    expect(selectCashflowDurationGapTone(undefined)).toBe("warning");
  });
});
