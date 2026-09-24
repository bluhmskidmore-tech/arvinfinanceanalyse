import { describe, expect, it } from "vitest";

import type { Numeric, YieldCurveTermStructureCurvePayload } from "../../../api/contracts";
import {
  buildYieldCurveTermStructureChartOption,
  pctNumericToAxisPercent,
} from "./yieldCurveTermStructureChartOption";

function numeric(raw: number | null, unit: Numeric["unit"], display: string): Numeric {
  return { raw, unit, display, precision: 2, sign_aware: unit === "bp" };
}

describe("pctNumericToAxisPercent", () => {
  it("converts contract pct raw (decimal ratio) to axis percent points with a fixed x100", () => {
    // 后端 common_numeric._normalize_numeric_raw 保证 pct raw 为小数比率。
    expect(pctNumericToAxisPercent(numeric(0.0175, "pct", "1.75%"))).toBeCloseTo(1.75);
    // 旧启发式在 |raw|>=1 时原样透传；新实现信任契约固定 ×100。
    expect(pctNumericToAxisPercent(numeric(0.012, "pct", "1.20%"))).toBeCloseTo(1.2);
  });

  it("passes through non-pct units and returns null for missing raw", () => {
    expect(pctNumericToAxisPercent(numeric(2.4, "bp", "+2.4 bp"))).toBe(2.4);
    expect(pctNumericToAxisPercent(numeric(null, "pct", "—"))).toBeNull();
    expect(pctNumericToAxisPercent(null)).toBeNull();
    expect(pctNumericToAxisPercent(undefined)).toBeNull();
  });
});

describe("buildYieldCurveTermStructureChartOption", () => {
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
          yield_pct: numeric(0.0132, "pct", "1.32%"),
          delta_bp_prev: numeric(1, "bp", "+1bp"),
        },
        {
          tenor: "10Y",
          yield_pct: numeric(null, "pct", "—"),
          delta_bp_prev: numeric(null, "bp", "—"),
        },
      ],
    },
  ];

  it("maps line series data as percent points and keeps null points as gaps", () => {
    const option = buildYieldCurveTermStructureChartOption(curves);
    expect(option).not.toBeNull();
    const series = option?.series;
    if (!Array.isArray(series)) {
      throw new Error("Expected series array");
    }
    expect((series[0] as { data?: unknown[] }).data?.[0]).toBeCloseTo(1.32);
    expect((series[0] as { data?: unknown[] }).data?.[1]).toBeNull();
    expect((series[1] as { data?: unknown[] }).data).toEqual([1, null]);
  });

  it("returns null when no curves or no points", () => {
    expect(buildYieldCurveTermStructureChartOption([])).toBeNull();
    expect(
      buildYieldCurveTermStructureChartOption([{ ...curves[0]!, points: [] }]),
    ).toBeNull();
  });
});
