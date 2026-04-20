import type { ChoiceMacroLatestPoint } from "../../../api/contracts";
import type { EChartsOption } from "../../../lib/echarts";
import { designTokens } from "../../../theme/designSystem";

import { crossAssetTrendLines } from "./crossAssetKpiModel";

const { color: c } = designTokens;
const CHART_COLORS = [
  c.primary[500],
  c.danger[500],
  c.success[500],
  c.warning[500],
  c.primary[700],
  c.info[400],
  c.danger[400],
];

function normalizedAligned(values: (number | null)[]): (number | null)[] {
  const first = values.find((v) => v != null && !Number.isNaN(v));
  if (first == null || first === 0) {
    return values.map(() => (values.some((v) => v != null) ? 100 : null));
  }
  return values.map((v) => {
    if (v == null || Number.isNaN(v)) {
      return null;
    }
    return (v / first) * 100;
  });
}

export function buildCrossAssetTrendOption(series: ChoiceMacroLatestPoint[]): EChartsOption | null {
  const lineInputs = crossAssetTrendLines(series);
  if (lineInputs.length === 0) {
    return null;
  }

  const dates = new Set<string>();
  for (const line of lineInputs) {
    for (const d of line.dates) {
      dates.add(d);
    }
  }
  const axisDates = [...dates].sort((a, b) => a.localeCompare(b));

  const echartsSeries = lineInputs.map((line, idx) => {
    const byDate = new Map(line.dates.map((d, i) => [d, line.values[i]]));
    const aligned = axisDates.map((d) => byDate.get(d) ?? null);
    const display = normalizedAligned(aligned);
    return {
      name: line.name,
      type: "line" as const,
      smooth: 0.25,
      showSymbol: false,
      lineStyle: { width: 2, color: CHART_COLORS[idx % CHART_COLORS.length] },
      data: display,
    };
  });

  const s = designTokens.space;
  const fs = designTokens.fontSize;
  return {
    color: CHART_COLORS,
    grid: { left: s[9], right: s[4], top: s[8], bottom: s[7] },
    legend: {
      type: "scroll",
      top: s[1],
      textStyle: { fontSize: fs[11], color: c.neutral[600] },
    },
    tooltip: {
      trigger: "axis",
    },
    xAxis: {
      type: "category",
      data: axisDates,
      axisLabel: { fontSize: fs[11], color: c.neutral[500] },
      axisLine: { lineStyle: { color: c.neutral[200] } },
    },
    yAxis: {
      type: "value",
      name: "基期=100",
      nameTextStyle: { fontSize: fs[11], color: c.neutral[500] },
      axisLabel: { fontSize: fs[11], color: c.neutral[500] },
      splitLine: { lineStyle: { color: c.neutral[100] } },
    },
    series: echartsSeries,
  };
}
