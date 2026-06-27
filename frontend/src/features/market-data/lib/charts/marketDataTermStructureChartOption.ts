import type { YieldCurveTermStructureCurvePayload } from "../../../../api/contracts";
import type { EChartsOption } from "../../../../lib/echarts";
import { buildMarketDataChartTooltip, marketDataChartTheme } from "./marketDataChartTheme";

const CURVE_LABEL: Record<string, string> = {
  treasury: "国债",
  cdb: "国开",
};

type MarketDataTermStructureChartVariant = "default" | "sheet";

function pctNumericToAxisPercent(value: YieldCurveTermStructureCurvePayload["points"][number]["yield_pct"]) {
  if (!value || value.raw == null) {
    return null;
  }
  if (value.unit !== "pct") {
    return value.raw;
  }
  return Math.abs(value.raw) < 1 ? value.raw * 100 : value.raw;
}

function bpNumericToAxis(value: YieldCurveTermStructureCurvePayload["points"][number]["delta_bp_prev"]) {
  if (!value || value.raw == null) {
    return null;
  }
  return value.raw;
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

  const palette = [
    marketDataChartTheme.multiSeriesPalette[0]!,
    marketDataChartTheme.multiSeriesPalette[1]!,
    marketDataChartTheme.multiSeriesPalette[2]!,
  ];
  const lineSeries = curves.map((curve, index) => {
    const color = palette[index % palette.length]!;
    const label = CURVE_LABEL[curve.curve_type] ?? curve.curve_type;
    const isPrimary = index === 0;

    return {
      name: `${label} 收益率`,
      type: "line" as const,
      yAxisIndex: 0,
      smooth: false,
      symbol: "circle",
      symbolSize: isSheetVariant ? 5 : isPrimary ? 7 : 6,
      connectNulls: true,
      itemStyle: {
        color,
        borderColor: marketDataChartTheme.chartSurface,
        borderWidth: isSheetVariant ? 1 : 1.5,
      },
      lineStyle: {
        color,
        width: isSheetVariant ? (isPrimary ? 2 : 1.4) : isPrimary ? 2.4 : 1.8,
        opacity: isPrimary ? 1 : 0.7,
      },
      areaStyle: isPrimary && !isSheetVariant
        ? {
            color: {
              type: "linear" as const,
              x: 0,
              y: 0,
              x2: 0,
              y2: 1,
              colorStops: [
                { offset: 0, color: `${color}26` },
                { offset: 1, color: `${color}00` },
              ],
            },
          }
        : undefined,
      endLabel: {
        show: !isSheetVariant,
        formatter: "{a}",
        color,
        fontSize: 10,
        distance: 8,
      },
      label: isSheetVariant
        ? {
            show: true,
            position: "top" as const,
            color,
            fontSize: 10,
            fontWeight: 650,
            formatter: (params: { value?: unknown }) =>
              typeof params.value === "number" ? params.value.toFixed(2) : "",
          }
        : undefined,
      emphasis: { focus: "series" as const },
      data: curve.points.map((point) => pctNumericToAxisPercent(point.yield_pct)),
    };
  });

  const barSeries = curves.map((curve) => {
    const label = CURVE_LABEL[curve.curve_type] ?? curve.curve_type;

    return {
      name: `${label} 日变动(bp)`,
      type: "bar" as const,
      yAxisIndex: 1,
      barGap: "18%",
      barMaxWidth: 10,
      itemStyle: {
        color: marketDataChartTheme.neutralBar,
        opacity: 0.35,
        borderRadius: [2, 2, 0, 0],
      },
      emphasis: { disabled: true },
      data: curve.points.map((point) => {
        const value = bpNumericToAxis(point.delta_bp_prev);
        return {
          value,
          itemStyle: {
            color:
              value == null || value === 0
                ? marketDataChartTheme.neutralBar
                : value > 0
                  ? marketDataChartTheme.positiveBar
                  : marketDataChartTheme.negativeBar,
          },
        };
      }),
    };
  });

  const sheetAxisLabel = { ...marketDataChartTheme.axisLabel, fontSize: 10, fontWeight: 600 };

  return {
    color: palette,
    tooltip: buildMarketDataChartTooltip({
      trigger: "axis",
      axisPointer: marketDataChartTheme.axisPointerLine,
      valueFormatter: (value: unknown) => (typeof value === "number" ? value.toFixed(2) : String(value)),
    }),
    legend: {
      show: !isSheetVariant,
      bottom: 0,
      type: "scroll",
      itemWidth: 18,
      itemHeight: 8,
      textStyle: marketDataChartTheme.axisLabel,
    },
    grid: isSheetVariant
      ? { left: 34, right: 16, top: 12, bottom: 28, containLabel: true }
      : { left: 48, right: 56, top: 20, bottom: 56, containLabel: true },
    xAxis: {
      type: "category",
      boundaryGap: true,
      data: categories,
      axisLabel: isSheetVariant ? sheetAxisLabel : { ...marketDataChartTheme.axisLabel, fontSize: 11, fontWeight: 600 },
      axisLine: marketDataChartTheme.axisLine,
      axisTick: { alignWithLabel: true, lineStyle: marketDataChartTheme.axisLine.lineStyle },
    },
    yAxis: [
      {
        type: "value",
        name: isSheetVariant ? "" : "收益率 (%)",
        scale: true,
        nameTextStyle: { ...marketDataChartTheme.axisLabel, align: "left" },
        axisLabel: { ...(isSheetVariant ? sheetAxisLabel : marketDataChartTheme.axisLabel), formatter: "{value}" },
        splitLine: marketDataChartTheme.splitLine,
      },
      {
        type: "value",
        name: "Δ (bp)",
        scale: true,
        nameTextStyle: marketDataChartTheme.axisLabel,
        axisLabel: marketDataChartTheme.axisLabel,
        splitLine: { show: false },
      },
    ],
    series: isSheetVariant ? lineSeries : [...lineSeries, ...barSeries],
  };
}
