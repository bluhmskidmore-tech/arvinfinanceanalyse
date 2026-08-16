import type { EChartsOption } from "../../../lib/echarts";
import type { Numeric, YieldCurveTermStructureCurvePayload } from "../../../api/contracts";
import { nocturneChartTheme } from "../../../components/charts/chartTheme";
import { nocturneTokens } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";

const CURVE_LABEL: Record<string, string> = {
  treasury: "国债",
  cdb: "国开",
  aaa_credit: "AAA 信用",
};

/* ECharts canvas 不消费 CSS 变量：取 Nocturne 常量（与页面 scope 同源）。
   曲线配色沿市场数据页已验收语义：国债=accent、国开=green、第三条=amber。 */
const YIELD_CURVE_PALETTE = [
  nocturneTokens.color.blue,
  nocturneTokens.color.green,
  nocturneTokens.color.amber,
] as const;

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

type CurveTooltipParam = {
  seriesName?: string;
  seriesType?: string;
  axisValueLabel?: string;
  marker?: string;
  value?: number | null;
};

/** tooltip 数值随序列单位格式化：折线=收益率 %、柱=日变动 bp（缺口保持 —）。 */
function formatCurveTooltip(params: unknown): string {
  const list = (Array.isArray(params) ? params : [params]) as CurveTooltipParam[];
  if (!list.length) return "";
  const heading = list[0]?.axisValueLabel ?? "";
  const rows = list.map((item) => {
    const value =
      typeof item.value === "number" && Number.isFinite(item.value)
        ? item.seriesType === "bar"
          ? `${item.value > 0 ? "+" : ""}${item.value.toFixed(1)} bp`
          : `${item.value.toFixed(2)}%`
        : EM_DASH;
    return `${item.marker ?? ""}${item.seriesName ?? ""}&nbsp;&nbsp;<strong>${value}</strong>`;
  });
  return [heading, ...rows].filter(Boolean).join("<br/>");
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
      symbolSize: 5,
      itemStyle: { color: col },
      lineStyle: { color: col, width: idx === 0 ? 2 : 1.5 },
      data: curve.points.map((p) => pctNumericToAxisPercent(p.yield_pct)),
    };
  });

  /* Δbp 柱按市场数据页语言降权沉底：同色系低不透明度，不与主线抢层级。 */
  const barSeries = curves.map((curve, idx) => {
    const col = palette[idx % palette.length]!;
    return {
      name: `${CURVE_LABEL[curve.curve_type] ?? curve.curve_type} 日变动 (bp)`,
      type: "bar" as const,
      yAxisIndex: 1,
      data: curve.points.map((p) => bpNumericToAxis(p.delta_bp_prev)),
      barGap: "10%",
      barMaxWidth: 12,
      itemStyle: { color: col, opacity: 0.3 },
      emphasis: { itemStyle: { opacity: 0.6 } },
    };
  });

  const theme = nocturneChartTheme;
  const axisLabel = theme.axisLabel;

  return theme.createBaseChartOption({
    color: curves.map((_, i) => palette[i % palette.length]!),
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "cross", label: { show: false } },
      formatter: formatCurveTooltip,
    },
    legend: {
      type: "plain",
      bottom: 0,
      itemWidth: 12,
      itemHeight: 8,
      textStyle: axisLabel,
    },
    grid: { left: 52, right: 52, top: 24, bottom: 56, containLabel: false },
    xAxis: {
      type: "category",
      data: categories,
      axisLabel,
      axisLine: { lineStyle: { color: nocturneTokens.color.lineSoft } },
    },
    yAxis: [
      {
        type: "value",
        name: "收益率 (%)",
        nameTextStyle: axisLabel,
        scale: true,
        axisLabel: { ...axisLabel, formatter: (v: number) => `${v}` },
        splitLine: { lineStyle: { color: nocturneTokens.color.lineSoft, width: 1 } },
      },
      {
        type: "value",
        name: "Δ (bp)",
        nameTextStyle: axisLabel,
        scale: true,
        axisLabel,
        splitLine: { show: false },
      },
    ],
    series: [...lineSeries, ...barSeries],
  } as EChartsOption);
}
