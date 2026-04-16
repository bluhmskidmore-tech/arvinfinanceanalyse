import type { ChoiceMacroLatestPoint } from "../../../api/contracts";
import type { EChartsOption } from "../../../lib/echarts";

import { crossAssetTrendLines } from "./crossAssetKpiModel";

const CHART_COLORS = ["#1890ff", "#f5222d", "#52c41a", "#fa8c16", "#722ed1", "#13c2c2", "#eb2f96"];

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

  return {
    color: CHART_COLORS,
    grid: { left: 48, right: 16, top: 40, bottom: 28 },
    legend: {
      type: "scroll",
      top: 4,
      textStyle: { fontSize: 11, color: "#64748b" },
    },
    tooltip: {
      trigger: "axis",
    },
    xAxis: {
      type: "category",
      data: axisDates,
      axisLabel: { fontSize: 10, color: "#94a3b8" },
      axisLine: { lineStyle: { color: "#e2e8f0" } },
    },
    yAxis: {
      type: "value",
      name: "基期=100",
      nameTextStyle: { fontSize: 11, color: "#94a3b8" },
      axisLabel: { fontSize: 10, color: "#94a3b8" },
      splitLine: { lineStyle: { color: "#f1f5f9" } },
    },
    series: echartsSeries,
  };
}
