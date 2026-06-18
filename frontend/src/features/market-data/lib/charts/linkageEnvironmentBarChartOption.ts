import type { MacroBondLinkageEnvironmentScore } from "../../../../api/contracts";
import { createBarChartOption } from "../../../../components/charts/chartTheme";
import type { EChartsOption } from "../../../../lib/echarts";
import { marketDataChartTheme } from "./marketDataChartTheme";

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
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    legend: undefined,
    grid: marketDataChartTheme.gridCompact,
    xAxis: {
      type: "category",
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
    series: [
      {
        name: "环境分项",
        type: "bar",
        barMaxWidth: 36,
        data: values.map((value) => ({
          value,
          itemStyle: {
            color: value >= 0 ? marketDataChartTheme.positiveBar : marketDataChartTheme.negativeBar,
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
    tooltip: { trigger: "axis", axisPointer: { type: "shadow" } },
    grid: { left: 120, right: 16, top: 8, bottom: 24 },
    xAxis: {
      type: "value",
      axisLabel: marketDataChartTheme.axisLabel,
      splitLine: marketDataChartTheme.splitLine,
    },
    yAxis: {
      type: "category",
      data: entries.map(([key]) => key),
      axisLabel: marketDataChartTheme.axisLabel,
    },
    series: [
      {
        name: "衍生利差",
        type: "bar",
        data: entries.map(([, value]) => value),
        barMaxWidth: 18,
      },
    ],
  };
}
