import type { ChoiceMacroLatestPoint, ChoiceMacroRecentPoint } from "../../../../api/contracts";
import { createLineChartOption } from "../../../../components/charts/chartTheme";
import type { EChartsOption } from "../../../../lib/echarts";
import { buildMarketDataChartTooltip, marketDataChartTheme } from "./marketDataChartTheme";

export type MarketDataSeriesTimeInput = Pick<
  ChoiceMacroLatestPoint,
  "series_id" | "series_name" | "unit" | "recent_points" | "quality_flag"
>;

function sortedRecentPoints(points: ChoiceMacroRecentPoint[] | undefined): ChoiceMacroRecentPoint[] {
  return [...(points ?? [])].sort((left, right) => left.trade_date.localeCompare(right.trade_date));
}

function compactSeriesEndLabel(seriesName: string) {
  const name = seriesName.trim();
  const tenorMatch = name.match(/(\d+)\s*年/);
  const tenor = tenorMatch ? `${tenorMatch[1]}Y` : "";

  if (/dr\s*0?07/i.test(name)) {
    return "DR007";
  }
  if (/shibor[:：.]?on|shibor.*o\/?n/i.test(name)) {
    return "SHIBOR O/N";
  }
  if (/国开|政策性金融债|cdb/i.test(name)) {
    return tenor ? `${tenor} CDB` : "CDB";
  }
  if (/国债|cgb|cn_gov/i.test(name)) {
    return tenor ? `${tenor} CGB` : "CGB";
  }

  return name.length > 12 ? `${name.slice(0, 12)}...` : name;
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

  return createLineChartOption({
    color: [marketDataChartTheme.multiSeriesPalette[0]],
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
      ? { left: 34, right: 20, top: 12, bottom: 28, containLabel: true }
      : marketDataChartTheme.gridWithTitle,
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: categories,
      axisLabel,
      axisLine: marketDataChartTheme.axisLine,
    },
    yAxis: {
      type: "value",
      scale: true,
      name: isSheetVariant ? "" : unit,
      axisLabel,
      splitLine: marketDataChartTheme.splitLine,
    },
    series: [
      {
        name: series.series_name,
        type: "line",
        smooth: true,
        symbol: "circle",
        symbolSize: isSheetVariant ? 4 : 6,
        showSymbol: categories.length <= (isSheetVariant ? 12 : 24),
        connectNulls: true,
        lineStyle: { width: isSheetVariant ? 2 : 2.35 },
        itemStyle: { borderColor: marketDataChartTheme.chartSurface, borderWidth: 1.2 },
        areaStyle: isSheetVariant
          ? undefined
          : {
              color: {
                type: "linear",
                x: 0,
                y: 0,
                x2: 0,
                y2: 1,
                colorStops: [
                  { offset: 0, color: `${marketDataChartTheme.multiSeriesPalette[0]}22` },
                  { offset: 1, color: `${marketDataChartTheme.multiSeriesPalette[0]}00` },
                ],
              },
            },
        endLabel: {
          show: true,
          formatter: compactSeriesEndLabel(series.series_name),
          fontSize: 10,
          distance: 8,
        },
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
  return createLineChartOption({
    color: marketDataChartTheme.multiSeriesPalette,
    tooltip: buildMarketDataChartTooltip({
      trigger: "axis",
      axisPointer: marketDataChartTheme.axisPointerLine,
      valueFormatter: (value: unknown) => (typeof value === "number" ? value.toFixed(2) : String(value)),
    }),
    legend: {
      bottom: 0,
      type: "scroll",
      itemWidth: 18,
      itemHeight: 8,
      textStyle: marketDataChartTheme.axisLabel,
    },
    grid: { left: 48, right: 56, top: 20, bottom: usable.length > 1 ? 52 : 32, containLabel: true },
    xAxis: {
      type: "category",
      boundaryGap: false,
      data: categories,
      axisLabel: marketDataChartTheme.axisLabel,
      axisLine: marketDataChartTheme.axisLine,
    },
    yAxis: {
      type: "value",
      scale: true,
      axisLabel: marketDataChartTheme.axisLabel,
      splitLine: marketDataChartTheme.splitLine,
    },
    series: usable.map((item, index) => {
      const color = marketDataChartTheme.multiSeriesPalette[index % marketDataChartTheme.multiSeriesPalette.length]!;
      const isPrimary = index === 0;
      return {
        name: item.series_name,
        type: "line" as const,
        smooth: true,
        symbol: "circle",
        symbolSize: isPrimary ? 7 : 6,
        showSymbol: categories.length <= 30,
        connectNulls: true,
        lineStyle: {
          color,
          width: isPrimary ? 2.2 : 1.7,
          opacity: isPrimary ? 1 : 0.72,
        },
        itemStyle: {
          color,
          borderColor: marketDataChartTheme.chartSurface,
          borderWidth: 1.2,
        },
        areaStyle: isPrimary
          ? {
              color: {
                type: "linear" as const,
                x: 0,
                y: 0,
                x2: 0,
                y2: 1,
                colorStops: [
                  { offset: 0, color: `${color}1e` },
                  { offset: 1, color: `${color}00` },
                ],
              },
            }
          : undefined,
        endLabel: {
          show: true,
          formatter: compactSeriesEndLabel(item.series_name),
          color,
          fontSize: 10,
          distance: 8,
        },
        emphasis: { focus: "series" },
        data: categories.map((date) => timelines[index]?.get(date) ?? null),
      };
    }),
  });
}
