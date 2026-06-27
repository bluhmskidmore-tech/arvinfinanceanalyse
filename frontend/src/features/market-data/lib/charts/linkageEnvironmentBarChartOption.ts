import type { MacroBondLinkageEnvironmentScore } from "../../../../api/contracts";
import { createBarChartOption } from "../../../../components/charts/chartTheme";
import type { EChartsOption } from "../../../../lib/echarts";
import { buildMarketDataChartTooltip, marketDataChartTheme } from "./marketDataChartTheme";

type EnvironmentScoreInput = Partial<MacroBondLinkageEnvironmentScore>;

const ENVIRONMENT_FIELDS: Array<{ key: keyof EnvironmentScoreInput; label: string }> = [
  { key: "liquidity_score", label: "流动性" },
  { key: "growth_score", label: "增长" },
  { key: "inflation_score", label: "通胀" },
  { key: "rate_direction_score", label: "利率方向" },
  { key: "composite_score", label: "综合" },
];

export function buildLinkageEnvironmentBarOption(
  environmentScore: EnvironmentScoreInput | undefined,
): EChartsOption | null {
  if (!environmentScore) {
    return null;
  }

  const categories: string[] = [];
  const values: number[] = [];

  for (const field of ENVIRONMENT_FIELDS) {
    const raw = environmentScore[field.key];
    if (typeof raw !== "number" || !Number.isFinite(raw)) {
      continue;
    }
    categories.push(field.label);
    values.push(raw);
  }

  if (categories.length === 0) {
    return null;
  }

  return createBarChartOption({
    color: [marketDataChartTheme.positiveBar],
    tooltip: buildMarketDataChartTooltip({
      trigger: "axis",
      axisPointer: marketDataChartTheme.axisPointerShadow,
      valueFormatter: (value: unknown) => (typeof value === "number" ? value.toFixed(2) : String(value)),
    }),
    legend: undefined,
    grid: marketDataChartTheme.gridCompact,
    xAxis: {
      type: "category",
      data: categories,
      axisLabel: marketDataChartTheme.axisLabel,
      axisLine: marketDataChartTheme.axisLine,
      axisTick: { show: false },
    },
    yAxis: {
      type: "value",
      scale: true,
      axisLabel: marketDataChartTheme.axisLabel,
      splitLine: marketDataChartTheme.splitLine,
    },
    series: [
      {
        name: "环境分项",
        type: "bar",
        barMaxWidth: 30,
        barCategoryGap: "42%",
        data: values.map((value) => ({
          value,
          itemStyle: {
            color: value >= 0 ? marketDataChartTheme.positiveBar : marketDataChartTheme.negativeBar,
            opacity: 0.84,
            borderRadius: [3, 3, 0, 0],
          },
        })),
      },
    ],
  });
}

export function buildDerivedSpreadsBarOption(
  derivedSpreads: Partial<Record<string, number | null>> | undefined,
): EChartsOption | null {
  if (!derivedSpreads) {
    return null;
  }

  const entries = Object.entries(derivedSpreads).filter(
    (entry): entry is [string, number] => typeof entry[1] === "number" && Number.isFinite(entry[1]),
  );
  if (entries.length === 0) {
    return null;
  }

  return {
    color: [marketDataChartTheme.derivedSpreadColor],
    tooltip: buildMarketDataChartTooltip({
      trigger: "axis",
      axisPointer: marketDataChartTheme.axisPointerShadow,
      valueFormatter: (value: unknown) => (typeof value === "number" ? value.toFixed(2) : String(value)),
    }),
    grid: { left: 120, right: 24, top: 10, bottom: 28, containLabel: true },
    xAxis: {
      type: "value",
      axisLabel: marketDataChartTheme.axisLabel,
      splitLine: marketDataChartTheme.splitLine,
      axisLine: marketDataChartTheme.axisLine,
    },
    yAxis: {
      type: "category",
      data: entries.map(([key]) => key),
      axisLabel: marketDataChartTheme.axisLabel,
      axisLine: marketDataChartTheme.axisLine,
      axisTick: { show: false },
    },
    series: [
      {
        name: "衍生利差",
        type: "bar",
        data: entries.map(([, value]) => ({
          value,
          itemStyle: {
            color: value >= 0 ? marketDataChartTheme.derivedSpreadColor : marketDataChartTheme.negativeBar,
            opacity: 0.84,
            borderRadius: [0, 3, 3, 0],
          },
        })),
        barMaxWidth: 18,
      },
    ],
  };
}
