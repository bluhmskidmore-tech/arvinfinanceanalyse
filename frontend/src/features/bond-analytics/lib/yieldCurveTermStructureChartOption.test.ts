import { describe, expect, it } from "vitest";

import type { YieldCurveTermStructureCurvePayload } from "../../../api/contracts";
import { buildYieldCurveTermStructureChartOption } from "./yieldCurveTermStructureChartOption";

function curveWithRawYields(rawValues: number[]): YieldCurveTermStructureCurvePayload {
  return {
    curve_type: "treasury",
    trade_date_requested: "2026-04-10",
    trade_date_resolved: "2026-04-10",
    points: rawValues.map((raw, index) => ({
      tenor: `${index + 1}Y`,
      yield_pct: {
        raw,
        unit: "pct",
        display: `+${(raw * 100).toFixed(2)}%`,
        precision: 2,
        sign_aware: true,
      },
      delta_bp_prev: null,
    })),
    source_version: "test",
    rule_version: "test",
    vendor_name: "test",
    vendor_version: "test",
  };
}

describe("buildYieldCurveTermStructureChartOption", () => {
  it("converts governed decimal pct raw values to percentage points without threshold guessing", () => {
    const option = buildYieldCurveTermStructureChartOption([curveWithRawYields([0.008, 0.01, 1])]);

    const series = option?.series as Array<{ type: string; data: Array<number | null> }>;

    expect(series[0]?.data).toEqual([0.8, 1, 100]);
  });
});
