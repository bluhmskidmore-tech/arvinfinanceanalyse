import { describe, expect, it } from "vitest";

import type {
  AdvancedAttributionSummary,
  Numeric,
  PnlCompositionPayload,
  ProductCategoryAttributionPayload,
  ProductCategoryPnlPayload,
  TPLMarketCorrelationPayload,
  VolumeRateAttributionPayload,
} from "../../../api/contracts";
import {
  buildVolumeRateBridgeSummary,
  formatMetaDateLabel,
  formatYi,
  formatYiNumeric,
  numericRaw,
  resolveCommonReportDate,
} from "./pnlAttributionViewModel";

function numeric(overrides: Partial<Numeric>): Numeric {
  return {
    raw: overrides.raw ?? null,
    unit: overrides.unit ?? "yuan",
    display: overrides.display ?? "—",
    precision: overrides.precision ?? 2,
    sign_aware: overrides.sign_aware ?? true,
  };
}

describe("PnlAttributionView helpers", () => {
  it("reads raw numeric values without inventing zeros", () => {
    expect(numericRaw(undefined)).toBeUndefined();
    expect(numericRaw(null)).toBeUndefined();
    expect(numericRaw(numeric({ raw: 125000000 }))).toBe(125000000);
    expect(numericRaw(numeric({ raw: 0, display: "+0.00 亿" }))).toBe(0);
    expect(numericRaw(numeric({ raw: null, display: "—" }))).toBeUndefined();
    expect(numericRaw(numeric({ raw: undefined, display: "1.25 亿" }))).toBeUndefined();
  });

  it("formats yi values with explicit sign and missing fallback", () => {
    expect(formatYi(250000000)).toBe("+2.50 亿");
    expect(formatYi(-50000000)).toBe("-0.50 亿");
    expect(formatYi(null)).toBe("—");
  });

  it("prefers governed Numeric.display before recomputing from raw", () => {
    expect(
      formatYiNumeric(
        numeric({
          raw: 125000000,
          display: "+1.30 亿",
        }),
      ),
    ).toBe("+1.30 亿");

    expect(formatYiNumeric(numeric({ raw: 0, display: "+0.00 亿" }))).toBe("+0.00 亿");
    expect(formatYiNumeric(numeric({ raw: null, display: "—" }))).toBe("—");
    expect(formatYiNumeric(numeric({ raw: 125000000, display: "   " }))).toBe("+1.25 亿");
    expect(formatYiNumeric(numeric({ raw: 125000000, display: "  +1.30 亿  " }))).toBe("+1.30 亿");
  });

  it("builds a bridge summary that surfaces cross effect and unexplained residual", () => {
    const summary = buildVolumeRateBridgeSummary({
      current_period: "2026-04",
      previous_period: "2026-03",
      compare_type: "mom",
      total_current_pnl: numeric({ raw: 851_454_959.25 }),
      total_previous_pnl: numeric({ raw: 785_715_634.31 }),
      total_pnl_change: numeric({ raw: 65_739_324.94 }),
      total_volume_effect: numeric({ raw: 11_514_483.36 }),
      total_rate_effect: numeric({ raw: 28_641_449.42 }),
      total_interaction_effect: numeric({ raw: 22_637_086.67 }),
      has_previous_data: true,
      items: [],
    });

    expect(summary).toMatchObject({
      explainedEffect: 62_793_019.45,
      status: "residual",
      statusLabel: "存在未解释差额",
    });
    expect(summary?.unexplainedEffect).toBeCloseTo(2_946_305.49, 2);
    expect(summary?.coveragePct).toBeCloseTo(95.52, 2);
  });

  it("treats fully explained volume-rate attribution as closed", () => {
    const summary = buildVolumeRateBridgeSummary({
      current_period: "2026-04",
      previous_period: "2026-03",
      compare_type: "mom",
      total_current_pnl: numeric({ raw: 110_000 }),
      total_previous_pnl: numeric({ raw: 100_000 }),
      total_pnl_change: numeric({ raw: 10_000 }),
      total_volume_effect: numeric({ raw: 2_000 }),
      total_rate_effect: numeric({ raw: 3_000 }),
      total_interaction_effect: numeric({ raw: 5_000 }),
      has_previous_data: true,
      items: [],
    });

    expect(summary).toMatchObject({
      explainedEffect: 10_000,
      unexplainedEffect: 0,
      coveragePct: 100,
      status: "closed",
    });
  });

  it("selects the current-view date label per tab", () => {
    expect(
      formatMetaDateLabel("volume-rate", {
        volumeRateData: { current_period: "2026-03" } as VolumeRateAttributionPayload,
        tplMarketData: null,
        compositionData: null,
        advancedSummary: null,
      }),
    ).toEqual({
      label: "当前期间",
      value: "2026-03",
    });

    expect(
      formatMetaDateLabel("tpl-market", {
        volumeRateData: null,
        tplMarketData: {
          start_period: "2025-04",
          end_period: "2026-03",
        } as TPLMarketCorrelationPayload,
        compositionData: null,
        advancedSummary: null,
      }),
    ).toEqual({
      label: "观察区间",
      value: "2025-04 ~ 2026-03",
    });

    expect(
      formatMetaDateLabel("composition", {
        volumeRateData: null,
        tplMarketData: null,
        compositionData: { report_period: "2026-03" } as PnlCompositionPayload,
        advancedSummary: null,
      }),
    ).toEqual({
      label: "报告日期",
      value: "2026-03",
    });

    expect(
      formatMetaDateLabel("advanced", {
        volumeRateData: null,
        tplMarketData: null,
        compositionData: null,
        advancedSummary: { report_date: "2026-04-09" } as AdvancedAttributionSummary,
      }),
    ).toEqual({
      label: "报告日期",
      value: "2026-04-09",
    });
  });

  it("keeps missing date labels explicit instead of fabricating values", () => {
    expect(
      formatMetaDateLabel("tpl-market", {
        volumeRateData: null,
        tplMarketData: { start_period: "2025-04", end_period: null } as unknown as TPLMarketCorrelationPayload,
        compositionData: null,
        advancedSummary: null,
      }),
    ).toEqual({
      label: "观察区间",
      value: "—",
    });

    expect(
      formatMetaDateLabel("advanced", {
        volumeRateData: null,
        tplMarketData: null,
        compositionData: null,
        advancedSummary: null,
      }),
    ).toEqual({
      label: "报告日期",
      value: "—",
    });
  });

  it("labels product category attribution by the shared selected report date", () => {
    expect(
      formatMetaDateLabel("product-category", {
        volumeRateData: null,
        tplMarketData: null,
        compositionData: null,
        advancedSummary: null,
        productCategoryAttributionData: {
          current_report_date: "2026-03-31",
        } as ProductCategoryAttributionPayload,
        productCategoryMonthlyData: { report_date: "2026-03-31" } as ProductCategoryPnlPayload,
        productCategoryYtdData: null,
      }),
    ).toMatchObject({
      value: "2026-03-31",
    });
  });

  it("defaults to the latest report date common to business and product category data", () => {
    expect(
      resolveCommonReportDate({
        businessDates: ["2026-04-30", "2026-03-31", "2026-02-28"],
        productCategoryDates: ["2026-03-31", "2026-02-28"],
      }),
    ).toMatchObject({
      reportDate: "2026-03-31",
      hasCommonDate: true,
      missingSource: "none",
    });
  });

  it("keeps an explicitly selected report date only when both sources have it", () => {
    expect(
      resolveCommonReportDate({
        businessDates: ["2026-04-30", "2026-03-31", "2026-02-28"],
        productCategoryDates: ["2026-03-31", "2026-02-28"],
        preferredReportDate: "2026-02-28",
      }).reportDate,
    ).toBe("2026-02-28");

    expect(
      resolveCommonReportDate({
        businessDates: ["2026-04-30", "2026-03-31"],
        productCategoryDates: ["2026-02-28"],
        preferredReportDate: "2026-04-30",
      }),
    ).toMatchObject({
      reportDate: null,
      hasCommonDate: false,
      missingSource: "none",
    });
  });

  it("reports missing source sides instead of fabricating a date", () => {
    expect(
      resolveCommonReportDate({
        businessDates: [],
        productCategoryDates: ["2026-03-31"],
      }),
    ).toMatchObject({
      reportDate: null,
      hasCommonDate: false,
      missingSource: "business",
    });

    expect(
      resolveCommonReportDate({
        businessDates: [],
        productCategoryDates: [],
      }),
    ).toMatchObject({
      reportDate: null,
      hasCommonDate: false,
      missingSource: "both",
    });
  });
});
