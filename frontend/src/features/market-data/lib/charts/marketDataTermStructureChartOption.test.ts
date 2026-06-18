import { describe, expect, it } from "vitest";

import type { Numeric, YieldCurveTermStructureCurvePayload } from "../../../../api/contracts";
import { buildMarketDataTermStructureChartOption } from "./marketDataTermStructureChartOption";

function numeric(raw: number, unit: Numeric["unit"], display: string): Numeric {
  return { raw, unit, display, precision: 2, sign_aware: unit === "bp" };
}

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
        yield_pct: numeric(1.2, "pct", "1.20%"),
        delta_bp_prev: numeric(0, "bp", "0bp"),
      },
      {
        tenor: "5Y",
        yield_pct: numeric(1.48, "pct", "1.48%"),
        delta_bp_prev: numeric(0, "bp", "0bp"),
      },
      {
        tenor: "10Y",
        yield_pct: numeric(1.75, "pct", "1.75%"),
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
        yield_pct: numeric(1.32, "pct", "1.32%"),
        delta_bp_prev: numeric(1, "bp", "+1bp"),
      },
      {
        tenor: "5Y",
        yield_pct: numeric(1.63, "pct", "1.63%"),
        delta_bp_prev: numeric(2, "bp", "+2bp"),
      },
      {
        tenor: "10Y",
        yield_pct: numeric(1.89, "pct", "1.89%"),
        delta_bp_prev: numeric(0, "bp", "0bp"),
      },
    ],
  },
];

describe("buildMarketDataTermStructureChartOption", () => {
  it("renders an institutional term-structure view with weighted curves and subdued delta bars", () => {
    const option = buildMarketDataTermStructureChartOption(curves);

    expect(option).not.toBeNull();
    expect(option?.grid).toMatchObject({ left: 44, right: 42, top: 18 });
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
      itemStyle: { opacity: 0.18 },
    });
  });
});
