import type { EChartsOption } from "../../../lib/echarts";
import { designTokens } from "../../../theme/designSystem";
import type { ReturnDecompositionResponse } from "../types";
import {
  returnDecompositionWaterfallDisplayStrings,
  returnDecompositionWaterfallRawSteps,
} from "../adapters/bondAnalyticsAdapter";

const CN_MARKET_UP = designTokens.color.danger[500];
const CN_MARKET_DOWN = designTokens.color.success[600];
const CHART_ACCENT = designTokens.color.info[500];
const CHART_AXIS = { color: designTokens.color.neutral[700], fontSize: designTokens.fontSize[11] };

const TRANSPARENT_BAR = {
  borderColor: "transparent",
  color: "rgba(0,0,0,0)",
  borderWidth: 0,
} as const;

/** 与收益分解瀑布图 X 轴类别一致（导出处便于单测与复用） */
export const RETURN_DECOMPOSITION_WATERFALL_CATEGORIES = [
  "票息",
  "骑乘",
  "利率效应",
  "利差效应",
  "外汇效应",
  "凸性",
  "交易",
  "合计",
] as const;

export const RETURN_DECOMPOSITION_WATERFALL_CATEGORY_COUNT = RETURN_DECOMPOSITION_WATERFALL_CATEGORIES.length;

/**
 * 构建 ECharts 瀑布图 option（原 `ReturnDecompositionView` 内逻辑，无行为变化）。
 */
export function buildReturnDecompositionWaterfallOption(d: ReturnDecompositionResponse): EChartsOption {
  const rawSteps = returnDecompositionWaterfallRawSteps(d);
  const stepValues = rawSteps.slice(0, -1);
  const explained = rawSteps[rawSteps.length - 1] ?? 0;

  const helperRaw: number[] = [];
  const valueRaw: number[] = [];
  const barColors: string[] = [];

  let running = 0;
  for (const v of stepValues) {
    if (v >= 0) {
      helperRaw.push(running);
      valueRaw.push(v);
      barColors.push(CN_MARKET_UP);
      running += v;
    } else {
      helperRaw.push(running + v);
      valueRaw.push(-v);
      barColors.push(CN_MARKET_DOWN);
      running += v;
    }
  }

  helperRaw.push(0);
  valueRaw.push(Number.isFinite(explained) ? explained : 0);
  barColors.push(CHART_ACCENT);

  const displayStrings = returnDecompositionWaterfallDisplayStrings(d);
  const categoryLabels = [...RETURN_DECOMPOSITION_WATERFALL_CATEGORIES];

  return {
    backgroundColor: "transparent",
    textStyle: { color: designTokens.color.neutral[700] },
    tooltip: {
      trigger: "axis",
      axisPointer: { type: "shadow" },
      formatter: (items: unknown) => {
        const list = Array.isArray(items) ? items : [items];
        const bar = list.find((x: { seriesName?: string }) => x.seriesName === "效应");
        const idx = (bar as { dataIndex?: number })?.dataIndex ?? 0;
        const label = categoryLabels[idx];
        return `${label}<br/>${displayStrings[idx] ?? "-"}`;
      },
    },
    grid: { left: 48, right: 24, top: 24, bottom: 32, containLabel: true },
    xAxis: {
      type: "category",
      data: categoryLabels,
      axisLabel: { interval: 0, rotate: 0, ...CHART_AXIS },
      axisLine: { lineStyle: { color: designTokens.color.neutral[200] } },
    },
    yAxis: {
      type: "value",
      axisLabel: CHART_AXIS,
      splitLine: { lineStyle: { color: designTokens.color.neutral[200], type: "dashed" } },
    },
    series: [
      {
        name: "辅助",
        type: "bar",
        stack: "waterfall",
        silent: true,
        itemStyle: TRANSPARENT_BAR,
        emphasis: { itemStyle: TRANSPARENT_BAR },
        data: helperRaw,
      },
      {
        name: "效应",
        type: "bar",
        stack: "waterfall",
        data: valueRaw.map((val, i) => ({
          value: val,
          itemStyle: { color: barColors[i] },
        })),
      },
    ],
  };
}
