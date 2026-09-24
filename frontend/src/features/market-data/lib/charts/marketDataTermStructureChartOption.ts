import type { YieldCurveTermStructureCurvePayload } from "../../../../api/contracts";
import type { EChartsOption } from "../../../../lib/echarts";
import { nocturneTokens } from "../../../../theme/designSystem";
import { buildMarketDataChartTooltip, marketDataChartTheme } from "./marketDataChartTheme";

const CURVE_LABEL: Record<string, string> = {
  treasury: "国债",
  cdb: "国开",
};

/** 曲线取色按 curve_type 固定（国债=蓝紫 accent、国开=绿），单选任一曲线时颜色不漂移。 */
const CURVE_COLOR: Record<string, string> = {
  treasury: nocturneTokens.color.blue,
  cdb: nocturneTokens.color.green,
};

const CURVE_FALLBACK_COLOR = nocturneTokens.color.accent400;

type MarketDataTermStructureChartVariant = "default" | "sheet";

/**
 * 后端契约（common_numeric._normalize_numeric_raw）保证 unit="pct" 时 raw 为小数比率
 * （如 0.0175 → 1.75%），坐标轴按百分点展示，固定 ×100，不再使用 |x|<1 启发式。
 */
export function pctNumericToAxisPercent(value: YieldCurveTermStructureCurvePayload["points"][number]["yield_pct"]) {
  if (!value || value.raw == null) {
    return null;
  }
  if (value.unit !== "pct") {
    return value.raw;
  }
  return value.raw * 100;
}

function bpNumericToAxis(value: YieldCurveTermStructureCurvePayload["points"][number]["delta_bp_prev"]) {
  if (!value || value.raw == null) {
    return null;
  }
  return value.raw;
}

const yieldTooltipValueFormatter = (value: unknown) =>
  typeof value === "number" ? `${value.toFixed(2)}%` : "—";

const deltaBpTooltipValueFormatter = (value: unknown) => {
  if (typeof value !== "number") {
    return "—";
  }
  const rounded = Math.round(value);
  return `${rounded > 0 ? "+" : ""}${rounded}bp`;
};

/** Δbp 柱：soft 半透明柱身 + 数值端一段实色收口；负值柱的实色端朝下（绿涨红跌）。 */
function deltaBarFill(value: number) {
  const solid = value > 0 ? nocturneTokens.color.green : nocturneTokens.color.red;
  const soft = value > 0 ? nocturneTokens.color.greenSoft : nocturneTokens.color.redSoft;
  const colorStops =
    value > 0
      ? [
          { offset: 0, color: solid },
          { offset: 0.2, color: soft },
          { offset: 1, color: soft },
        ]
      : [
          { offset: 0, color: soft },
          { offset: 0.8, color: soft },
          { offset: 1, color: solid },
        ];
  return { type: "linear" as const, x: 0, y: 0, x2: 0, y2: 1, colorStops };
}

export function buildMarketDataTermStructureChartOption(
  curves: YieldCurveTermStructureCurvePayload[],
  options: { variant?: MarketDataTermStructureChartVariant } = {},
): EChartsOption | null {
  if (!curves.length) {
    return null;
  }
  const categories = curves[0]?.points.map((point) => point.tenor) ?? [];
  if (!categories.length) {
    return null;
  }
  const isSheetVariant = options.variant === "sheet";

  const lineSeries = curves.map((curve, index) => {
    const color = CURVE_COLOR[curve.curve_type] ?? CURVE_FALLBACK_COLOR;
    const label = CURVE_LABEL[curve.curve_type] ?? curve.curve_type;
    const isPrimary = index === 0;

    return {
      name: label,
      type: "line" as const,
      yAxisIndex: 0,
      z: 3,
      smooth: false,
      symbol: "circle",
      symbolSize: 4,
      connectNulls: true,
      itemStyle: {
        color,
        borderColor: marketDataChartTheme.chartSurface,
        borderWidth: 1,
      },
      lineStyle: { color, width: 2 },
      areaStyle:
        isPrimary && !isSheetVariant
          ? {
              color: {
                type: "linear" as const,
                x: 0,
                y: 0,
                x2: 0,
                y2: 1,
                colorStops: [
                  { offset: 0, color: `${color}1f` },
                  { offset: 1, color: `${color}00` },
                ],
              },
            }
          : undefined,
      emphasis: { focus: "series" as const },
      tooltip: { valueFormatter: yieldTooltipValueFormatter },
      data: curve.points.map((point) => pctNumericToAxisPercent(point.yield_pct)),
    };
  });

  const barSeries = curves.map((curve) => {
    const label = CURVE_LABEL[curve.curve_type] ?? curve.curve_type;

    return {
      name: `${label} 日变动`,
      type: "bar" as const,
      yAxisIndex: 1,
      z: 1,
      barGap: "18%",
      barMaxWidth: 10,
      itemStyle: {
        color: marketDataChartTheme.neutralBar,
        borderRadius: [2, 2, 0, 0],
      },
      emphasis: { disabled: true },
      tooltip: { valueFormatter: deltaBpTooltipValueFormatter },
      data: curve.points.map((point) => {
        const value = bpNumericToAxis(point.delta_bp_prev);
        if (value == null || value === 0) {
          return {
            value,
            itemStyle: { color: marketDataChartTheme.neutralBar, opacity: 0.35 },
          };
        }
        return {
          value,
          itemStyle: {
            color: deltaBarFill(value),
            borderRadius: value > 0 ? [2, 2, 0, 0] : [0, 0, 2, 2],
          },
        };
      }),
    };
  });

  const sheetAxisLabel = { ...marketDataChartTheme.axisLabel, fontSize: 10, fontWeight: 600 };
  // 曲线 + 日变动柱的图例条目在窄面板会折成两行，底部按行数预留避免压住期限轴标签。
  const legendEntryCount = lineSeries.length + barSeries.length;
  const legendReservedBottom = legendEntryCount >= 3 ? 54 : 36;

  return {
    color: [nocturneTokens.color.blue, nocturneTokens.color.green, CURVE_FALLBACK_COLOR],
    tooltip: buildMarketDataChartTooltip({
      trigger: "axis",
      axisPointer: marketDataChartTheme.axisPointerLine,
    }),
    legend: {
      show: !isSheetVariant,
      bottom: 0,
      type: "plain" as const,
      itemWidth: 14,
      itemHeight: 8,
      itemGap: 10,
      textStyle: { ...marketDataChartTheme.axisLabel, color: nocturneTokens.color.inkSoft },
    },
    grid: isSheetVariant
      ? { left: 34, right: 16, top: 12, bottom: 28, containLabel: true }
      : { left: 16, right: 16, top: 24, bottom: legendReservedBottom, containLabel: true },
    xAxis: {
      type: "category",
      boundaryGap: true,
      data: categories,
      axisLabel: isSheetVariant ? sheetAxisLabel : { ...marketDataChartTheme.axisLabel, fontWeight: 600 },
      axisLine: marketDataChartTheme.axisLine,
      axisTick: { alignWithLabel: true, lineStyle: marketDataChartTheme.axisLine.lineStyle },
    },
    yAxis: [
      {
        type: "value",
        name: isSheetVariant ? "" : "收益率 (%)",
        scale: true,
        splitNumber: 4,
        nameTextStyle: { ...marketDataChartTheme.axisLabel, align: "left" },
        axisLabel: { ...(isSheetVariant ? sheetAxisLabel : marketDataChartTheme.axisLabel), formatter: "{value}" },
        splitLine: marketDataChartTheme.splitLine,
      },
      {
        type: "value",
        name: "Δ (bp)",
        scale: true,
        splitNumber: 4,
        nameTextStyle: marketDataChartTheme.axisLabel,
        axisLabel: isSheetVariant ? sheetAxisLabel : marketDataChartTheme.axisLabel,
        splitLine: { show: false },
      },
    ],
    series: isSheetVariant ? lineSeries : [...lineSeries, ...barSeries],
  };
}
