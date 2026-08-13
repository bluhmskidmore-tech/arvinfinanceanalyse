import { describe, expect, it } from "vitest";

import type { Numeric } from "../../../api/contracts";
import type { CashflowProjectionVM } from "../adapters/cashflowProjectionAdapter";
import {
  selectCashflowDurationGapTone,
  selectCashflowMonthlyProjectionSeries,
  selectCashflowProjectionRiskReadout,
  selectCashflowRateSensitivitySemantic,
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
            assetInflow: n({ raw: 100, display: "100.00" }),
            liabilityOutflow: n({ raw: 40, display: "40.00" }),
            netCashflow: n({ raw: 60, display: "60.00" }),
            cumulativeNet: n({ raw: 60, display: "60.00" }),
          },
          {
            yearMonth: "2026-05",
            assetInflow: n({ raw: 10, display: "10.00" }),
            liabilityOutflow: n({ raw: 140, display: "140.00" }),
            netCashflow: n({ raw: -130, display: "-130.00" }),
            cumulativeNet: n({ raw: -70, display: "-70.00" }),
          },
          {
            yearMonth: "2026-06",
            assetInflow: n({ raw: 80, display: "80.00" }),
            liabilityOutflow: n({ raw: 30, display: "30.00" }),
            netCashflow: n({ raw: 50, display: "50.00" }),
            cumulativeNet: n({ raw: -20, display: "-20.00" }),
          },
        ],
      }),
    );

    expect(readout).toMatchObject({
      tone: "warning",
      summary: "2 个月累计净现金流为负",
      negativeCumulativeMonths: 2,
      worstCumulativeMonth: "2026-05",
      worstCumulativeDisplay: "-70.00",
      largestOutflowMonth: "2026-05",
      largestOutflowDisplay: "140.00",
      finalCumulativeDisplay: "-20.00",
    });
  });

  it("marks a projection positive when cumulative net cashflow never goes negative", () => {
    const readout = selectCashflowProjectionRiskReadout(
      makeVM({
        monthlyBuckets: [
          {
            yearMonth: "2026-04",
            assetInflow: n({ raw: 100, display: "100.00" }),
            liabilityOutflow: n({ raw: 40, display: "40.00" }),
            netCashflow: n({ raw: 60, display: "60.00" }),
            cumulativeNet: n({ raw: 60, display: "60.00" }),
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
      finalCumulativeDisplay: "60.00",
    });
  });

  it("never reads positive while cumulative months are missing", () => {
    const readout = selectCashflowProjectionRiskReadout(
      makeVM({
        monthlyBuckets: [
          {
            yearMonth: "2026-04",
            assetInflow: n({ raw: 100, display: "100.00" }),
            liabilityOutflow: n({ raw: 40, display: "40.00" }),
            netCashflow: n({ raw: 60, display: "60.00" }),
            cumulativeNet: n({ raw: 60, display: "60.00" }),
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
      worstCumulativeDisplay: "60.00",
      largestOutflowMonth: "2026-04",
      largestOutflowDisplay: "40.00",
      finalCumulativeDisplay: "—",
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
      largestOutflowMonth: "—",
      largestOutflowDisplay: "—",
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
