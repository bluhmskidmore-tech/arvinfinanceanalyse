import type { MacroBondLinkageTopCorrelation } from "../../../../api/contracts";
import type { EChartsOption } from "../../../../lib/echarts";
import {
  LINKAGE_BAR_MAX_WIDTH,
  truncateLinkageCategoryLabel,
} from "./linkageEnvironmentBarChartOption";
import { buildMarketDataChartTooltip, marketDataChartTheme } from "./marketDataChartTheme";

const CORR_WINDOWS = [
  { key: "correlation_3m" as const, label: "3M" },
  { key: "correlation_6m" as const, label: "6M" },
  { key: "correlation_1y" as const, label: "1Y" },
];

function corrColor(value: number | null): string {
  if (value == null) {
    return marketDataChartTheme.neutralBar;
  }
  if (value >= 0) {
    return marketDataChartTheme.positiveBar;
  }
  return marketDataChartTheme.negativeBar;
}

export function buildLinkageCorrelationBarOption(
  correlations: readonly MacroBondLinkageTopCorrelation[],
): EChartsOption | null {
  if (correlations.length === 0) {
    return null;
  }

  const categories = correlations.map(
    (item) => `${item.series_name}${item.lead_lag_days ? ` · lag ${item.lead_lag_days}d` : ""}`,
  );

  return {
    tooltip: buildMarketDataChartTooltip({
      trigger: "axis",
      axisPointer: marketDataChartTheme.axisPointerShadow,
      valueFormatter: (value: unknown) => (typeof value === "number" ? value.toFixed(3) : String(value)),
    }),
    grid: { ...marketDataChartTheme.gridCompact },
    xAxis: {
      type: "category",
      data: categories,
      axisLabel: {
        ...marketDataChartTheme.axisLabel,
        interval: 0,
        rotate: categories.length > 4 ? 24 : 0,
        formatter: (value: string) => truncateLinkageCategoryLabel(value, 10),
      },
      axisLine: marketDataChartTheme.axisLine,
      axisTick: { show: false },
    },
    yAxis: {
      type: "value",
      min: -1,
      max: 1,
      splitNumber: 4,
      axisLabel: marketDataChartTheme.axisLabel,
      splitLine: marketDataChartTheme.splitLine,
      axisLine: marketDataChartTheme.axisLine,
    },
    series: CORR_WINDOWS.map((window) => ({
      name: window.label,
      type: "bar" as const,
      barGap: "12%",
      barCategoryGap: "34%",
      barMaxWidth: LINKAGE_BAR_MAX_WIDTH,
      data: correlations.map((item) => {
        const value = item[window.key];
        return {
          value: value ?? null,
          itemStyle: {
            color: corrColor(value),
            opacity: value == null ? 0.35 : 0.82,
          },
        };
      }),
    })),
  };
}
