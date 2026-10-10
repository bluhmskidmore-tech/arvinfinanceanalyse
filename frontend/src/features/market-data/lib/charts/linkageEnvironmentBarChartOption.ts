import type { MacroBondLinkageEnvironmentScore } from "../../../../api/contracts";
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

export const LINKAGE_BAR_MAX_WIDTH = 14;

/** 类目轴超长名称截断；tooltip 仍然展示完整类目名。 */
export function truncateLinkageCategoryLabel(value: string, maxChars = 10): string {
  return value.length > maxChars ? `${value.slice(0, maxChars)}…` : value;
}

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

  return {
    color: [marketDataChartTheme.positiveBar],
    tooltip: buildMarketDataChartTooltip({
      trigger: "axis",
      axisPointer: marketDataChartTheme.axisPointerShadow,
      valueFormatter: (value: unknown) => (typeof value === "number" ? value.toFixed(2) : String(value)),
    }),
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
      splitNumber: 3,
      axisLabel: marketDataChartTheme.axisLabel,
      splitLine: marketDataChartTheme.splitLine,
    },
    series: [
      {
        name: "环境分项",
        type: "bar",
        barMaxWidth: LINKAGE_BAR_MAX_WIDTH,
        barCategoryGap: "42%",
        data: values.map((value) => ({
          value,
          itemStyle: {
            color: value >= 0 ? marketDataChartTheme.positiveBar : marketDataChartTheme.negativeBar,
            opacity: 0.84,
          },
        })),
      },
    ],
  };
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
      valueFormatter: (value: unknown) =>
        typeof value === "number" ? `${value.toFixed(2)} bp` : String(value),
    }),
    grid: { left: 120, right: 24, top: 10 },
    xAxis: {
      type: "value",
      name: "bp",
      splitNumber: 3,
      axisLabel: marketDataChartTheme.axisLabel,
      splitLine: marketDataChartTheme.splitLine,
      axisLine: marketDataChartTheme.axisLine,
    },
    yAxis: {
      type: "category",
      data: entries.map(([key]) => key),
      axisLabel: {
        ...marketDataChartTheme.axisLabel,
        formatter: (value: string) => truncateLinkageCategoryLabel(value, 14),
      },
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
          },
        })),
        barMaxWidth: LINKAGE_BAR_MAX_WIDTH,
      },
    ],
  };
}
