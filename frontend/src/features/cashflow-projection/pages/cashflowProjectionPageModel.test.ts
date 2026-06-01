import { describe, expect, it } from "vitest";

import type { Numeric } from "../../../api/contracts";
import type { CashflowProjectionVM } from "../adapters/cashflowProjectionAdapter";
import {
  selectCashflowMonthlyProjectionSeries,
  selectCashflowProjectionRiskReadout,
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
      durationGap: n({ unit: "ratio" }),
      assetDuration: n({ unit: "ratio" }),
      liabilityDuration: n({ unit: "ratio" }),
      equityDuration: n({ unit: "ratio" }),
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

  it("treats missing or non-finite raw values as zero for chart safety", () => {
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
        ],
      }),
    );

    expect(series?.assetInflow).toEqual([0]);
    expect(series?.liabilityOutflow).toEqual([0]);
    expect(series?.cumulativeNet).toEqual([0]);
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
      worstCumulativeMonth: "2026-04",
      finalCumulativeDisplay: "60.00",
    });
  });
});
