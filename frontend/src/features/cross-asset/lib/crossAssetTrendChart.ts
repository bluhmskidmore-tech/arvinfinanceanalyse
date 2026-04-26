import type { ChoiceMacroLatestPoint } from "../../../api/contracts";
import type { EChartsOption } from "../../../lib/echarts";
import { designTokens } from "../../../theme/designSystem";

import { crossAssetTrendLines } from "./crossAssetKpiModel";

/** Must match section copy on cross-asset ("近 N 日"). */
export const CROSS_ASSET_TREND_WINDOW_DAYS = 20;

const { color: c } = designTokens;
/** Staggered hues so 10+ series stay distinguishable without rainbow noise. */
const CHART_COLORS = [
  c.primary[600],
  c.neutral[800],
  c.success[600],
  c.warning[600],
  c.danger[500],
  c.info[500],
  c.primary[400],
  c.neutral[600],
  c.success[400],
  c.warning[700],
  c.info[400],
  c.danger[400],
];

/**
 * Last observation carried forward on the **shared** date index.
 * US/CN/商品发布与休市日不同，轴上无值的日期并非“跳空”，不 LOCF 就会整段 `null` + connectNulls=false 变成碎线、不可读。
 */
export function locfForward(values: (number | null)[]): (number | null)[] {
  let last: number | null = null;
  return values.map((v) => {
    if (typeof v === "number" && !Number.isNaN(v)) {
      last = v;
    }
    return last;
  });
}

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
  const allSorted = [...dates].sort((a, b) => a.localeCompare(b));
  const axisDates =
    allSorted.length > CROSS_ASSET_TREND_WINDOW_DAYS
      ? allSorted.slice(-CROSS_ASSET_TREND_WINDOW_DAYS)
      : allSorted;

  if (axisDates.length === 0) {
    return null;
  }

  const echartsSeries = lineInputs.map((line, idx) => {
    const byDate = new Map(line.dates.map((d, i) => [d, line.values[i]]));
    const aligned = axisDates.map((d) => byDate.get(d) ?? null);
    const leveled = locfForward(aligned);
    const display = normalizedAligned(leveled);
    return {
      name: line.name,
      type: "line" as const,
      /** LOCF 段在 0.25 smooth 下会像扭结；0 为阶梯/持有水平，和填充语义一致。 */
      smooth: 0,
      showSymbol: false,
      /** LOCF 后序列在窗口内无“中间空档”，可连线；仅最早未上市段仍为 null。 */
      connectNulls: true,
      lineStyle: { width: 1.5, color: CHART_COLORS[idx % CHART_COLORS.length] },
      data: display,
      emphasis: { lineStyle: { width: 2.25 } },
    };
  });

  const fs = designTokens.fontSize;
  return {
    color: CHART_COLORS,
    grid: { left: 8, right: 16, top: 36, bottom: 104, containLabel: true },
    legend: {
      type: "scroll",
      orient: "horizontal",
      bottom: 0,
      left: "center",
      width: "92%",
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
      order: "valueDesc",
      enterable: false,
      extraCssText: "max-height:min(45vh,280px);overflow-y:auto;white-space:pre-line;text-align:left;",
      axisPointer: { type: "line", lineStyle: { color: c.neutral[300], width: 1, type: "dashed" } },
      backgroundColor: c.neutral[50],
      borderColor: c.neutral[200],
      borderWidth: 1,
      textStyle: { fontSize: fs[11], color: c.neutral[700] },
      position(point, _params, _dom, _rect, size) {
        if (!size?.viewSize) {
          return point;
        }
        const margin = 8;
        const tooltipWidth = Math.min(288, Math.max(0, size.viewSize[0] - margin * 2));
        const maxX = Math.max(margin, size.viewSize[0] - tooltipWidth - margin);
        const x = Math.min(Math.max(margin, point[0] - tooltipWidth / 2), maxX);
        return [x, margin];
      },
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
      boundaryGap: false,
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
