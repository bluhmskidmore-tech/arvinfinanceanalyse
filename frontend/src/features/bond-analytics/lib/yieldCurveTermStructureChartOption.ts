import type { EChartsOption } from "../../../lib/echarts";
import type { Numeric, YieldCurveTermStructureCurvePayload } from "../../../api/contracts";
import { mossChartCategoricalPalette } from "../../../components/charts/chartTheme";
import { ibTokens } from "../../../theme/designSystem";

const CURVE_LABEL: Record<string, string> = {
  treasury: "国债",
  cdb: "国开",
  aaa_credit: "AAA 信用",
};

const YIELD_CURVE_PALETTE = [
  ibTokens.color.accent,
  mossChartCategoricalPalette[2],
  mossChartCategoricalPalette[3],
] as const;
const IB_GRID = ibTokens.color.hairline;
const IB_AXIS = ibTokens.color.inkMuted;

/**
 * 后端契约（common_numeric._normalize_numeric_raw）保证 unit="pct" 时 raw 为小数比率
 * （如 0.0175 → 1.75%），坐标轴按百分点展示，固定 ×100，不再使用 |x|<1 启发式。
 */
export function pctNumericToAxisPercent(n: Numeric | null | undefined): number | null {
  if (!n || n.raw == null) return null;
  if (n.unit !== "pct") return n.raw;
  return n.raw * 100;
}

function bpNumericToAxis(n: Numeric | null | undefined): number | null {
  if (!n || n.raw == null) return null;
  return n.raw;
}

export function buildYieldCurveTermStructureChartOption(
  curves: YieldCurveTermStructureCurvePayload[],
): EChartsOption | null {
  if (!curves.length) return null;
  const categories = curves[0]?.points.map((p) => p.tenor) ?? [];
  if (!categories.length) return null;

  const palette = YIELD_CURVE_PALETTE;

  const lineSeries = curves.map((curve, idx) => {
    const col = palette[idx % palette.length]!;
    return {
      name: `${CURVE_LABEL[curve.curve_type] ?? curve.curve_type} 收益率`,
      type: "line" as const,
      yAxisIndex: 0,
      connectNulls: true,
      showSymbol: true,
      itemStyle: { color: col },
      lineStyle: { color: col, width: idx === 0 ? 2 : 1.5 },
      data: curve.points.map((p) => pctNumericToAxisPercent(p.yield_pct)),
    };
  });

  const barSeries = curves.map((curve, idx) => {
    const col = palette[idx % palette.length]!;
    return {
      name: `${CURVE_LABEL[curve.curve_type] ?? curve.curve_type} 日变动 (bp)`,
      type: "bar" as const,
      yAxisIndex: 1,
      data: curve.points.map((p) => bpNumericToAxis(p.delta_bp_prev)),
      barGap: "8%",
      barMaxWidth: 18,
      itemStyle: { color: col, opacity: 0.55 },
    };
  });

  const axisLabel = { color: IB_AXIS, fontSize: 11 };

  return {
    color: curves.map((_, i) => palette[i % palette.length]!),
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
    },
    legend: { bottom: 0, type: "scroll", textStyle: axisLabel },
    grid: { left: 56, right: 56, top: 28, bottom: 72 },
    xAxis: {
      type: "category",
      data: categories,
      axisLabel,
      axisLine: { lineStyle: { color: IB_GRID } },
    },
    yAxis: [
      {
        type: "value",
        name: "收益率 (%)",
        scale: true,
        axisLabel: { ...axisLabel, formatter: (v: number) => `${v}` },
        splitLine: { lineStyle: { color: IB_GRID, width: 1 } },
      },
      {
        type: "value",
        name: "Δ (bp)",
        scale: true,
        axisLabel,
        splitLine: { show: false },
      },
    ],
    series: [...lineSeries, ...barSeries],
  };
}
