import { describe, expect, it } from "vitest";

import type {
  AdvancedAttributionSummary,
  Numeric,
  PnlCompositionPayload,
  TPLMarketCorrelationPayload,
  VolumeRateAttributionPayload,
} from "../../../api/contracts";
import {
  formatMetaDateLabel,
  formatYi,
  formatYiNumeric,
  numericRaw,
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
});
