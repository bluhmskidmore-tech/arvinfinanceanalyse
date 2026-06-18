import type { MacroBondLinkageTopCorrelation } from "../../../../api/contracts";
import type { EChartsOption } from "../../../../lib/echarts";
import { marketDataChartTheme } from "./marketDataChartTheme";

const CORR_WINDOWS = [
  { key: "correlation_3m" as const, label: "3M" },
  { key: "correlation_6m" as const, label: "6M" },
  { key: "correlation_1y" as const, label: "1Y" },
];

function corrColor(value: number | null): string {
  if (value == null) {
    return marketDataChartTheme.axisLabel.color as string;
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
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    legend: { bottom: 0, textStyle: marketDataChartTheme.axisLabel },
    grid: { ...marketDataChartTheme.gridCompact, bottom: correlations.length > 3 ? 72 : 52 },
    xAxis: {
      type: "category",
      data: categories,
      axisLabel: {
        ...marketDataChartTheme.axisLabel,
        interval: 0,
        rotate: categories.length > 4 ? 24 : 0,
      },
      axisLine: marketDataChartTheme.axisLine,
    },
    yAxis: {
      type: "value",
      min: -1,
      max: 1,
      axisLabel: marketDataChartTheme.axisLabel,
      splitLine: marketDataChartTheme.splitLine,
    },
    series: CORR_WINDOWS.map((window) => ({
      name: window.label,
      type: "bar" as const,
      barGap: "12%",
      barMaxWidth: 18,
      data: correlations.map((item) => {
        const value = item[window.key];
        return {
          value: value ?? null,
          itemStyle: { color: corrColor(value) },
        };
      }),
    })),
  };
}
