import type { EChartsOption } from "../../../lib/echarts";
import type { Numeric, YieldCurveTermStructureCurvePayload } from "../../../api/contracts";
import { designTokens } from "../../../theme/designSystem";

const c = designTokens.color;

const CURVE_LABEL: Record<string, string> = {
  treasury: "国债",
  cdb: "国开",
  aaa_credit: "AAA 信用",
};

function pctNumericToAxisPercent(n: Numeric | null | undefined): number | null {
  if (!n || n.raw == null) return null;
  if (n.unit !== "pct") return n.raw;
  return Math.abs(n.raw) < 1 ? n.raw * 100 : n.raw;
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

  const palette = [c.primary[500], c.info[500], c.warning[500]];

  const lineSeries = curves.map((curve, idx) => {
    const col = palette[idx % palette.length]!;
    return {
      name: `${CURVE_LABEL[curve.curve_type] ?? curve.curve_type} 收益率`,
      type: "line" as const,
      yAxisIndex: 0,
      connectNulls: true,
      showSymbol: true,
      itemStyle: { color: col },
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
      itemStyle: { color: col, opacity: 0.6 },
    };
  });

  return {
    color: curves.map((_, i) => palette[i % palette.length]!),
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross" },
    },
    legend: { bottom: 0, type: "scroll" },
    grid: { left: 56, right: 56, top: 28, bottom: 72 },
    xAxis: { type: "category", data: categories },
    yAxis: [
      {
        type: "value",
        name: "收益率 (%)",
        scale: true,
        axisLabel: { formatter: (v: number) => `${v}` },
      },
      {
        type: "value",
        name: "Δ (bp)",
        scale: true,
        splitLine: { show: false },
      },
    ],
    series: [...lineSeries, ...barSeries],
  };
}
