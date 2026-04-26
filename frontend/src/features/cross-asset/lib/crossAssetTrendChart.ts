import type { ChoiceMacroLatestPoint } from "../../../api/contracts";
import type { EChartsOption } from "../../../lib/echarts";
import { designTokens } from "../../../theme/designSystem";

import { crossAssetTrendLines } from "./crossAssetKpiModel";

const { color: c } = designTokens;
const CHART_COLORS = [
  c.primary[500],
  c.neutral[700],
  c.success[600],
  c.warning[600],
  c.info[400],
  c.primary[400],
  c.danger[600],
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
      connectNulls: true,
      lineStyle: { width: 1.5, color: CHART_COLORS[idx % CHART_COLORS.length] },
      data: display,
      emphasis: { lineStyle: { width: 2.25 } },
    };
  });

  const fs = designTokens.fontSize;
  return {
    color: CHART_COLORS,
    grid: { left: 8, right: 16, top: 20, bottom: 104, containLabel: true },
    legend: {
      type: "scroll",
      orient: "horizontal",
      bottom: 0,
      left: "center",
      width: "92%",
      /** Thin line cap matches line series; avoids tall color blocks that read like unrelated icons. */
      itemWidth: 16,
      itemHeight: 2,
      itemGap: 10,
      pageIconSize: 10,
      pageTextStyle: { color: c.neutral[500] },
      textStyle: { fontSize: fs[11], color: c.neutral[500] },
      padding: [2, 4, 8, 4],
    },
    tooltip: {
      trigger: "axis",
      confine: true,
      axisPointer: { type: "line", lineStyle: { color: c.neutral[300], width: 1, type: "dashed" } },
      backgroundColor: c.neutral[50],
      borderColor: c.neutral[200],
      borderWidth: 1,
      textStyle: { fontSize: fs[11], color: c.neutral[700] },
      formatter: (raw: unknown) => {
        if (!Array.isArray(raw) || raw.length === 0) {
          return "";
        }
        const first = raw[0] as { axisValueLabel?: string; axisValue?: string };
        const date = first.axisValueLabel ?? first.axisValue ?? "";
        const lines = (raw as Array<{ marker?: string; seriesName?: string; value?: unknown }>).map((p) => {
          const v = p.value;
          const str =
            v == null || (typeof v === "number" && Number.isNaN(v))
              ? "—"
              : typeof v === "number"
                ? v.toFixed(1)
                : String(v);
          return `${p.marker ?? ""}${p.seriesName ?? ""}：${str}`;
        });
        return `${date}\n${lines.join("\n")}`;
      },
    },
    xAxis: {
      type: "category",
      data: axisDates,
      axisLabel: { fontSize: fs[11], color: c.neutral[500], hideOverlap: true, margin: 10 },
      axisLine: { lineStyle: { color: c.neutral[300] } },
      axisTick: { alignWithLabel: true },
    },
    yAxis: {
      type: "value",
      scale: true,
      axisLabel: { fontSize: fs[11], color: c.neutral[500] },
      splitLine: { lineStyle: { color: c.neutral[200], opacity: 0.65 } },
    },
    series: echartsSeries,
  };
}
