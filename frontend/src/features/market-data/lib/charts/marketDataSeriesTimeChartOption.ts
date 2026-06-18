import type { ChoiceMacroLatestPoint, ChoiceMacroRecentPoint } from "../../../../api/contracts";
import { createLineChartOption } from "../../../../components/charts/chartTheme";
import type { EChartsOption } from "../../../../lib/echarts";
import { ibTokens } from "../../../../theme/designSystem";
import { marketDataChartTheme } from "./marketDataChartTheme";

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

export function buildMarketDataSeriesTimeChartOption(
  series: MarketDataSeriesTimeInput,
): EChartsOption | null {
  const timeline = sortedRecentPoints(series.recent_points);
  if (timeline.length === 0) {
    return null;
  }

  const categories = timeline.map((point) => point.trade_date);
  const values = timeline.map((point) => point.value_numeric);
  const unit = series.unit?.trim() || undefined;
  const qualityNote =
    series.quality_flag && series.quality_flag !== "ok" ? ` · 质量 ${series.quality_flag}` : "";

  return createLineChartOption({
    color: [marketDataChartTheme.multiSeriesPalette[0]],
    title: {
      text: `${series.series_name}${qualityNote}`,
      left: 0,
      top: 0,
      textStyle: marketDataChartTheme.titleMuted,
    },
    tooltip: { trigger: "axis" },
    legend: undefined,
    grid: marketDataChartTheme.gridWithTitle,
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
      name: unit,
      axisLabel: marketDataChartTheme.axisLabel,
      splitLine: marketDataChartTheme.splitLine,
    },
    series: [
      {
        name: series.series_name,
        type: "line",
        smooth: true,
        symbol: "circle",
        symbolSize: 6,
        showSymbol: categories.length <= 24,
        connectNulls: true,
        lineStyle: { width: 2.1 },
        itemStyle: { borderColor: ibTokens.color.surface, borderWidth: 1.2 },
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
    tooltip: {
      trigger: "axis",
      axisPointer: {
        type: "line",
        lineStyle: { color: ibTokens.color.gold, width: 1, type: "dashed" },
      },
      valueFormatter: (value: unknown) => (typeof value === "number" ? value.toFixed(2) : String(value)),
    },
    legend: {
      bottom: 0,
      type: "scroll",
      itemWidth: 18,
      itemHeight: 8,
      textStyle: marketDataChartTheme.axisLabel,
    },
    grid: { left: 44, right: 48, top: 18, bottom: usable.length > 1 ? 50 : 28 },
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
      return {
        name: item.series_name,
        type: "line" as const,
        smooth: true,
        symbol: "circle",
        symbolSize: index === 0 ? 7 : 6,
        showSymbol: categories.length <= 30,
        connectNulls: true,
        lineStyle: {
          color,
          width: index === 0 ? 2.2 : 1.7,
          opacity: index === 0 ? 1 : 0.72,
        },
        itemStyle: {
          color,
          borderColor: ibTokens.color.surface,
          borderWidth: 1.2,
        },
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
