import { describe, expect, it } from "vitest";

import type { Numeric, YieldCurveTermStructureCurvePayload } from "../../../../api/contracts";
import { nocturneTokens } from "../../../../theme/designSystem";
import { buildMarketDataTermStructureChartOption, pctNumericToAxisPercent } from "./marketDataTermStructureChartOption";

function numeric(raw: number | null, unit: Numeric["unit"], display: string): Numeric {
  return { raw, unit, display, precision: 2, sign_aware: unit === "bp" };
}

type ChartSeriesShape = {
  name?: string;
  type?: string;
  symbol?: string;
  symbolSize?: number;
  z?: number;
  yAxisIndex?: number;
  barMaxWidth?: number;
  lineStyle?: { color?: string; width?: number };
  areaStyle?: unknown;
  endLabel?: unknown;
  label?: unknown;
  tooltip?: { valueFormatter?: (value: unknown) => string };
  data?: unknown[];
};

type BarPointShape = {
  value: number | null;
  itemStyle?: {
    color?: string | { colorStops?: Array<{ offset: number; color: string }> };
    opacity?: number;
  };
};

function seriesOf(option: ReturnType<typeof buildMarketDataTermStructureChartOption>): ChartSeriesShape[] {
  const series = option?.series;
  if (!Array.isArray(series)) {
    throw new Error("Expected term-structure chart to expose series array");
  }
  return series as ChartSeriesShape[];
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
    const series = seriesOf(option);
    expect((series[0]?.data as number[] | undefined)?.map((v) => Number(v.toFixed(2)))).toEqual([
      1.2, 1.48, 1.75,
    ]);
    expect((series[1]?.data as number[] | undefined)?.map((v) => Number(v.toFixed(2)))).toEqual([
      1.32, 1.63, 1.89,
    ]);
  });

  it("renders nocturne curves without point labels and with a plain single-row legend", () => {
    const option = buildMarketDataTermStructureChartOption(curves);

    expect(option).not.toBeNull();
    expect(option?.grid).toMatchObject({ containLabel: true });
    expect(option?.legend).toMatchObject({
      show: true,
      type: "plain",
      itemWidth: 14,
      textStyle: { color: nocturneTokens.color.inkSoft },
    });
    expect((option?.tooltip as { axisPointer?: { type?: string } }).axisPointer?.type).toBe("line");

    const series = seriesOf(option);
    expect(series).toHaveLength(4);

    expect(series[0]).toMatchObject({
      name: "国债",
      type: "line",
      symbol: "circle",
      symbolSize: 4,
      z: 3,
    });
    expect(series[0]?.lineStyle).toMatchObject({ color: nocturneTokens.color.blue, width: 2 });
    expect(series[0]?.endLabel).toBeUndefined();
    expect(series[0]?.label).toBeUndefined();
    expect(series[0]?.areaStyle).toBeDefined();

    expect(series[1]).toMatchObject({ name: "国开", type: "line", symbolSize: 4 });
    expect(series[1]?.lineStyle).toMatchObject({ color: nocturneTokens.color.green, width: 2 });
    expect(series[1]?.endLabel).toBeUndefined();
    expect(series[1]?.label).toBeUndefined();
  });

  it("keeps delta bars on the secondary axis, narrow and below the curves with sign-aware soft fills", () => {
    const option = buildMarketDataTermStructureChartOption(curves);
    const series = seriesOf(option);

    expect(series[2]).toMatchObject({
      name: "国债 日变动",
      type: "bar",
      yAxisIndex: 1,
      barMaxWidth: 10,
      z: 1,
    });
    expect(series[3]).toMatchObject({ name: "国开 日变动", type: "bar", z: 1 });

    const treasuryBars = series[2]?.data as BarPointShape[] | undefined;
    const negative = treasuryBars?.[2];
    expect(negative?.value).toBe(-1);
    const negativeStops =
      typeof negative?.itemStyle?.color === "object" ? negative.itemStyle.color.colorStops : undefined;
    expect(negativeStops?.[0]?.color).toBe(nocturneTokens.color.redSoft);
    expect(negativeStops?.[negativeStops.length - 1]?.color).toBe(nocturneTokens.color.red);

    const cdbBars = series[3]?.data as BarPointShape[] | undefined;
    const positive = cdbBars?.[0];
    expect(positive?.value).toBe(1);
    const positiveStops =
      typeof positive?.itemStyle?.color === "object" ? positive.itemStyle.color.colorStops : undefined;
    expect(positiveStops?.[0]?.color).toBe(nocturneTokens.color.green);
    expect(positiveStops?.[positiveStops.length - 1]?.color).toBe(nocturneTokens.color.greenSoft);

    const neutral = treasuryBars?.[0];
    expect(neutral?.value).toBe(0);
    expect(neutral?.itemStyle?.opacity).toBe(0.35);
  });

  it("formats tooltip values as two-decimal percent for curves and signed integer bp for bars", () => {
    const option = buildMarketDataTermStructureChartOption(curves);
    const series = seriesOf(option);

    expect(series[0]?.tooltip?.valueFormatter?.(1.746)).toBe("1.75%");
    expect(series[0]?.tooltip?.valueFormatter?.(null)).toBe("—");
    expect(series[2]?.tooltip?.valueFormatter?.(2)).toBe("+2bp");
    expect(series[2]?.tooltip?.valueFormatter?.(-1)).toBe("-1bp");
    expect(series[2]?.tooltip?.valueFormatter?.(0)).toBe("0bp");
    expect(series[2]?.tooltip?.valueFormatter?.(null)).toBe("—");
  });

  it("keeps horizontal split lines on the yield axis only and quiets the bp axis", () => {
    const option = buildMarketDataTermStructureChartOption(curves);
    const axes = option?.yAxis as Array<{ splitNumber?: number; splitLine?: { show?: boolean } }> | undefined;

    expect(axes?.[0]?.splitNumber).toBe(4);
    expect(axes?.[1]?.splitNumber).toBe(4);
    expect(axes?.[1]?.splitLine).toMatchObject({ show: false });
  });

  it("renders a quieter sheet variant without delta bars, legend or point labels", () => {
    const option = buildMarketDataTermStructureChartOption(curves, { variant: "sheet" });

    expect(option).not.toBeNull();
    expect(option?.grid).toMatchObject({ left: 34, right: 16, top: 12, bottom: 28 });
    expect(option?.legend).toMatchObject({ show: false });

    const series = seriesOf(option);
    expect(series).toHaveLength(2);
    expect(series[0]).toMatchObject({ type: "line", symbolSize: 4 });
    expect(series[0]?.lineStyle).toMatchObject({ color: nocturneTokens.color.blue, width: 2 });
    expect(series[0]?.endLabel).toBeUndefined();
    expect(series[0]?.label).toBeUndefined();
    expect(series.some((item) => item.type === "bar")).toBe(false);
  });
});
