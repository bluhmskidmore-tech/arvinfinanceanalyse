import type { ChoiceMacroLatestPoint, ChoiceMacroRecentPoint } from "../../../../api/contracts";
import { createLineChartOption } from "../../../../components/charts/chartTheme";
import type { EChartsOption } from "../../../../lib/echarts";
import { nocturneTokens } from "../../../../theme/designSystem";
import { buildMarketDataChartTooltip, marketDataChartTheme } from "./marketDataChartTheme";

export type MarketDataSeriesTimeInput = Pick<
  ChoiceMacroLatestPoint,
  "series_id" | "series_name" | "unit" | "recent_points" | "quality_flag"
>;

/** 多系列时默认点亮的主系列数量；其余进图例（legend.selected=false），可点开关。 */
export const MARKET_DATA_MULTI_SERIES_DEFAULT_VISIBLE = 4;

function sortedRecentPoints(points: ChoiceMacroRecentPoint[] | undefined): ChoiceMacroRecentPoint[] {
  return [...(points ?? [])].sort((left, right) => left.trade_date.localeCompare(right.trade_date));
}

function formatAxisMagnitude(scaled: number): string {
  const rounded = Math.round(scaled * 10) / 10;
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
}

/** y 轴大数缩写：≥1e8 → 亿、≥1e4 → 万（保留 1 位小数，整数不带小数位），小数值原样。 */
function formatMarketDataAxisValue(value: number): string {
  if (!Number.isFinite(value)) {
    return "";
  }
  const abs = Math.abs(value);
  const sign = value < 0 ? "-" : "";
  if (abs >= 1e8) {
    return `${sign}${formatAxisMagnitude(abs / 1e8)}亿`;
  }
  if (abs >= 1e4) {
    return `${sign}${formatAxisMagnitude(abs / 1e4)}万`;
  }
  return String(value);
}

/** 日期标签 MM-DD；时间轴跨年时，起点及每次跨年处补 YYYY-MM 标出年份切换。 */
function buildDateAxisLabelFormatter(categories: readonly string[]) {
  const spansMultipleYears = new Set(categories.map((date) => date.slice(0, 4))).size > 1;
  return (value: string, index: number): string => {
    if (!spansMultipleYears) {
      return value.slice(5);
    }
    const previousYear = index > 0 ? categories[index - 1]?.slice(0, 4) : undefined;
    return previousYear === value.slice(0, 4) ? value.slice(5) : value.slice(0, 7);
  };
}

function buildDateCategoryAxis(categories: string[], axisLabel: object) {
  return {
    type: "category" as const,
    boundaryGap: false,
    data: categories,
    axisTick: { show: false },
    axisLine: marketDataChartTheme.axisLine,
    axisLabel: {
      ...axisLabel,
      interval: "auto" as const,
      hideOverlap: true,
      formatter: buildDateAxisLabelFormatter(categories),
    },
  };
}

function buildCompactValueAxis(
  axisLabel: object,
  options: { unitName?: string; splitNumber?: number } = {},
) {
  return {
    type: "value" as const,
    scale: true,
    ...(options.unitName !== undefined
      ? {
          name: options.unitName,
          nameTextStyle: {
            color: marketDataChartTheme.axisLabel.color,
            fontFamily: marketDataChartTheme.axisLabel.fontFamily,
            fontSize: 11,
          },
        }
      : {}),
    splitNumber: options.splitNumber ?? 4,
    axisLabel: { ...axisLabel, formatter: formatMarketDataAxisValue },
    splitLine: marketDataChartTheme.splitLine,
  };
}

function buildSoftAreaGradient(color: string) {
  return {
    color: {
      type: "linear" as const,
      x: 0,
      y: 0,
      x2: 0,
      y2: 1,
      colorStops: [
        { offset: 0, color: `${color}22` },
        { offset: 1, color: `${color}00` },
      ],
    },
  };
}

type MarketDataSeriesTimeChartVariant = "default" | "sheet";

export function buildMarketDataSeriesTimeChartOption(
  series: MarketDataSeriesTimeInput,
  options: { variant?: MarketDataSeriesTimeChartVariant } = {},
): EChartsOption | null {
  const timeline = sortedRecentPoints(series.recent_points);
  if (timeline.length === 0) {
    return null;
  }

  const isSheetVariant = options.variant === "sheet";
  const categories = timeline.map((point) => point.trade_date);
  const values = timeline.map((point) => point.value_numeric);
  const unit = series.unit?.trim() || undefined;
  const qualityNote =
    series.quality_flag && series.quality_flag !== "ok" ? ` · 质量 ${series.quality_flag}` : "";
  const axisLabel = isSheetVariant
    ? { ...marketDataChartTheme.axisLabel, fontSize: 10, fontWeight: 600 }
    : marketDataChartTheme.axisLabel;
  const lineColor = marketDataChartTheme.multiSeriesPalette[0]!;

  return createLineChartOption({
    color: [lineColor],
    title: isSheetVariant
      ? undefined
      : {
          text: `${series.series_name}${qualityNote}`,
          left: 0,
          top: 0,
          textStyle: marketDataChartTheme.titleMuted,
        },
    tooltip: buildMarketDataChartTooltip({
      trigger: "axis",
      axisPointer: marketDataChartTheme.axisPointerLine,
    }),
    legend: undefined,
    grid: isSheetVariant
      ? { left: 8, right: 12, top: 10, bottom: 6, containLabel: true }
      : { left: 8, right: 12, top: 32, bottom: 8, containLabel: true },
    xAxis: buildDateCategoryAxis(categories, axisLabel),
    yAxis: buildCompactValueAxis(axisLabel, {
      unitName: isSheetVariant ? "" : unit,
      splitNumber: isSheetVariant ? 3 : 4,
    }),
    series: [
      {
        name: series.series_name,
        type: "line",
        smooth: true,
        symbol: "circle",
        symbolSize: isSheetVariant ? 4 : 5,
        showSymbol: false,
        connectNulls: true,
        lineStyle: { width: isSheetVariant ? 1.5 : 2 },
        itemStyle: { borderColor: marketDataChartTheme.chartSurface, borderWidth: 1.2 },
        areaStyle: isSheetVariant ? undefined : buildSoftAreaGradient(lineColor),
        data: values,
      },
    ],
  });
}

export function buildMarketDataMultiSeriesTimeChartOption(
  seriesList: MarketDataSeriesTimeInput[],
): EChartsOption | null {
  const usable = seriesList.filter((item) => (item.recent_points?.length ?? 0) > 0);
  if (usable.length === 0) {
    return null;
  }

  const dateSet = new Set<string>();
  const timelines = usable.map((item) => {
    const map = new Map<string, number>();
    for (const point of sortedRecentPoints(item.recent_points)) {
      map.set(point.trade_date, point.value_numeric);
      dateSet.add(point.trade_date);
    }
    return map;
  });
  const categories = [...dateSet].sort((left, right) => left.localeCompare(right));
  const legendSelected =
    usable.length > MARKET_DATA_MULTI_SERIES_DEFAULT_VISIBLE
      ? Object.fromEntries(
          usable.map((item, index) => [
            item.series_name,
            index < MARKET_DATA_MULTI_SERIES_DEFAULT_VISIBLE,
          ]),
        )
      : undefined;
  // plain 图例在窄卡（约 320-360px）实测每行只放得下 2 项，按 2 项/行预留底部，
  // 行数封顶 4 行防止极端多系列把绘图区吃光（其余交给图例开关与 tooltip）。
  const legendRows = Math.min(4, Math.max(1, Math.ceil(usable.length / 2)));
  const legendReservedBottom = 10 + legendRows * 18;

  return createLineChartOption({
    color: marketDataChartTheme.multiSeriesPalette,
    tooltip: buildMarketDataChartTooltip({
      trigger: "axis",
      axisPointer: marketDataChartTheme.axisPointerLine,
      valueFormatter: (value: unknown) => (typeof value === "number" ? value.toFixed(2) : String(value)),
    }),
    legend: {
      type: "plain",
      bottom: 0,
      itemWidth: 12,
      itemHeight: 8,
      itemGap: 12,
      textStyle: {
        color: nocturneTokens.color.inkSoft,
        fontSize: 11,
        overflow: "truncate",
        width: 96,
      },
      ...(legendSelected ? { selected: legendSelected } : {}),
    },
    grid: { left: 8, right: 12, top: 16, bottom: legendReservedBottom, containLabel: true },
    xAxis: buildDateCategoryAxis(categories, marketDataChartTheme.axisLabel),
    yAxis: buildCompactValueAxis(marketDataChartTheme.axisLabel, { splitNumber: 4 }),
    // 系列只用颜色区分（虚线保留给「预测/代理」语义，当前多系列无此语义）。
    series: usable.map((item, index) => {
      const color = marketDataChartTheme.multiSeriesPalette[index % marketDataChartTheme.multiSeriesPalette.length]!;
      const isPrimary = index === 0;
      return {
        name: item.series_name,
        type: "line" as const,
        smooth: true,
        symbol: "circle",
        symbolSize: 5,
        showSymbol: false,
        connectNulls: true,
        lineStyle: {
          color,
          width: isPrimary ? 2 : 1.5,
        },
        itemStyle: {
          color,
          borderColor: marketDataChartTheme.chartSurface,
          borderWidth: 1.2,
        },
        areaStyle: isPrimary ? buildSoftAreaGradient(color) : undefined,
        emphasis: { focus: "series" as const },
        data: categories.map((date) => timelines[index]?.get(date) ?? null),
      };
    }),
  });
}
