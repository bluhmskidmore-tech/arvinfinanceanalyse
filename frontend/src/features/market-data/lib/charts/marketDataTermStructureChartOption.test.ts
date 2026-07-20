import { describe, expect, it } from "vitest";

import type { Numeric, YieldCurveTermStructureCurvePayload } from "../../../../api/contracts";
import { buildMarketDataTermStructureChartOption, pctNumericToAxisPercent } from "./marketDataTermStructureChartOption";

function numeric(raw: number | null, unit: Numeric["unit"], display: string): Numeric {
  return { raw, unit, display, precision: 2, sign_aware: unit === "bp" };
}

// 契约口径：unit="pct" 的 raw 为小数比率（0.012 → 1.20%），
// 见 backend/app/schemas/common_numeric.py::_normalize_numeric_raw。
const curves: YieldCurveTermStructureCurvePayload[] = [
  {
    curve_type: "treasury",
    trade_date_requested: "2026-06-12",
    trade_date_resolved: "2026-06-12",
    source_version: "sv",
    vendor_version: "vv",
    rule_version: "rv",
    vendor_name: "choice",
    points: [
      {
        tenor: "1Y",
        yield_pct: numeric(0.012, "pct", "1.20%"),
        delta_bp_prev: numeric(0, "bp", "0bp"),
      },
      {
        tenor: "5Y",
        yield_pct: numeric(0.0148, "pct", "1.48%"),
        delta_bp_prev: numeric(0, "bp", "0bp"),
      },
      {
        tenor: "10Y",
        yield_pct: numeric(0.0175, "pct", "1.75%"),
        delta_bp_prev: numeric(-1, "bp", "-1bp"),
      },
    ],
  },
  {
    curve_type: "cdb",
    trade_date_requested: "2026-06-12",
    trade_date_resolved: "2026-06-12",
    source_version: "sv",
    vendor_version: "vv",
    rule_version: "rv",
    vendor_name: "choice",
    points: [
      {
        tenor: "1Y",
        yield_pct: numeric(0.0132, "pct", "1.32%"),
        delta_bp_prev: numeric(1, "bp", "+1bp"),
      },
      {
        tenor: "5Y",
        yield_pct: numeric(0.0163, "pct", "1.63%"),
        delta_bp_prev: numeric(2, "bp", "+2bp"),
      },
      {
        tenor: "10Y",
        yield_pct: numeric(0.0189, "pct", "1.89%"),
        delta_bp_prev: numeric(0, "bp", "0bp"),
      },
    ],
  },
];

describe("pctNumericToAxisPercent", () => {
  it("converts contract pct raw (decimal ratio) to axis percent points with a fixed x100", () => {
    expect(pctNumericToAxisPercent(numeric(0.012, "pct", "1.20%"))).toBeCloseTo(1.2);
    expect(pctNumericToAxisPercent(numeric(0.0175, "pct", "1.75%"))).toBeCloseTo(1.75);
  });

  it("passes through non-pct units and returns null for missing raw", () => {
    expect(pctNumericToAxisPercent(numeric(2, "bp", "+2bp"))).toBe(2);
    expect(pctNumericToAxisPercent(numeric(null, "pct", "—"))).toBeNull();
    expect(pctNumericToAxisPercent(null)).toBeNull();
  });
});

describe("buildMarketDataTermStructureChartOption", () => {
  it("maps line series data as percent points from decimal-ratio pct raws", () => {
    const option = buildMarketDataTermStructureChartOption(curves);
    const series = option?.series;
    if (!Array.isArray(series)) {
      throw new Error("Expected series array");
    }
    expect((series[0] as { data?: number[] }).data?.map((v) => Number(v.toFixed(2)))).toEqual([
      1.2, 1.48, 1.75,
    ]);
    expect((series[1] as { data?: number[] }).data?.map((v) => Number(v.toFixed(2)))).toEqual([
      1.32, 1.63, 1.89,
    ]);
  });

  it("renders an institutional term-structure view with weighted curves and subdued delta bars", () => {
    const option = buildMarketDataTermStructureChartOption(curves);

    expect(option).not.toBeNull();
    expect(option?.grid).toMatchObject({ left: 48, right: 56, top: 20 });
    expect((option?.tooltip as { axisPointer?: { type?: string } }).axisPointer?.type).toBe("line");

    const series = option?.series;
    if (!Array.isArray(series)) {
      throw new Error("Expected term-structure chart to expose series array");
    }

    expect(series).toHaveLength(4);
    expect(series[0]).toMatchObject({
      type: "line",
      symbol: "circle",
      symbolSize: 7,
      lineStyle: { width: 2.4 },
      endLabel: { show: true },
    });
    expect(series[1]).toMatchObject({
      type: "line",
      lineStyle: { width: 1.8, opacity: 0.7 },
      endLabel: { show: true },
    });
    expect(series[2]).toMatchObject({
      type: "bar",
      yAxisIndex: 1,
      barMaxWidth: 10,
      itemStyle: { opacity: 0.35 },
    });
  });

  it("renders a quieter sheet variant without delta bars or end labels", () => {
    const option = buildMarketDataTermStructureChartOption(curves, { variant: "sheet" });

    expect(option).not.toBeNull();
    expect(option?.grid).toMatchObject({ left: 34, right: 16, top: 12, bottom: 28 });
    expect(option?.legend).toMatchObject({ show: false });

    const series = option?.series;
    if (!Array.isArray(series)) {
      throw new Error("Expected sheet term-structure chart to expose series array");
    }

    expect(series).toHaveLength(2);
    expect(series[0]).toMatchObject({
      type: "line",
      symbolSize: 5,
      lineStyle: { width: 2 },
      endLabel: { show: false },
      label: { show: true },
    });
    expect(series.some((item) => (item as { type?: string }).type === "bar")).toBe(false);
  });
});
