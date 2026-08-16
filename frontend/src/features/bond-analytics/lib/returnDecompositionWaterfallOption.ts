import { nocturneChartTheme } from "../../../components/charts/chartTheme";
import type { EChartsOption } from "../../../lib/echarts";
import { nocturneTokens } from "../../../theme/designSystem";
import { EM_DASH } from "../../../utils/format";
import type { ReturnDecompositionResponse } from "../types";
import {
  returnDecompositionWaterfallDisplayStrings,
  returnDecompositionWaterfallRawSteps,
} from "../adapters/bondAnalyticsAdapter";

/* 2026-08-11 全站决议（DESIGN §4）：绿涨红跌。瀑布正贡献柱=绿、负贡献柱=红；
   色值收敛到 Nocturne 去饱和语义常量（§2.2）。 */
const POSITIVE_CONTRIBUTION = nocturneTokens.color.green;
const NEGATIVE_CONTRIBUTION = nocturneTokens.color.red;
const CHART_ACCENT = nocturneTokens.color.blue;

const TRANSPARENT_BAR = {
  borderColor: "transparent",
  color: "transparent",
  borderWidth: 0,
} as const;

/** 金额轴刻度按亿/万缩写（市场数据页 y 轴缩写先例），不再直出 700,000,000 级原始数。 */
export function formatMoneyAxisTick(value: number): string {
  if (!Number.isFinite(value)) return EM_DASH;
  const abs = Math.abs(value);
  if (abs >= 1e8) return `${trimTrailingZero(value / 1e8)} 亿`;
  if (abs >= 1e4) return `${trimTrailingZero(value / 1e4)} 万`;
  return `${trimTrailingZero(value)}`;
}

function trimTrailingZero(value: number): string {
  const fixed = value.toFixed(1);
  return fixed.endsWith(".0") ? fixed.slice(0, -2) : fixed;
}

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
  const explained = rawSteps[rawSteps.length - 1] ?? null;

  /* 缺失效应保留 null：该柱断开（ECharts 对 null 不画柱），累计跳过缺失项继续；
     缺口由消费方（ReturnDecompositionView）在区头 partial 注记披露，禁止补 0 画假柱。 */
  const helperRaw: Array<number | null> = [];
  const valueRaw: Array<number | null> = [];
  const barColors: string[] = [];

  let running = 0;
  for (const v of stepValues) {
    if (v === null) {
      helperRaw.push(null);
      valueRaw.push(null);
      barColors.push("transparent");
      continue;
    }
    if (v >= 0) {
      helperRaw.push(running);
      valueRaw.push(v);
      barColors.push(POSITIVE_CONTRIBUTION);
      running += v;
    } else {
      helperRaw.push(running + v);
      valueRaw.push(-v);
      barColors.push(NEGATIVE_CONTRIBUTION);
      running += v;
    }
  }

  helperRaw.push(0);
  valueRaw.push(explained);
  barColors.push(CHART_ACCENT);

  const displayStrings = returnDecompositionWaterfallDisplayStrings(d);
  const categoryLabels = [...RETURN_DECOMPOSITION_WATERFALL_CATEGORIES];

  return {
    backgroundColor: "transparent",
    textStyle: { color: nocturneTokens.color.inkSoft },
    tooltip: {
      trigger: "axis",
      confine: true,
      backgroundColor: nocturneTokens.color.panel,
      borderColor: nocturneTokens.color.line,
      borderWidth: 1,
      padding: [8, 10],
      textStyle: { color: nocturneTokens.color.ink, fontSize: 12 },
      axisPointer: { type: "shadow" },
      formatter: (items: unknown) => {
        const list = Array.isArray(items) ? items : [items];
        const bar = list.find((x: { seriesName?: string }) => x.seriesName === "效应");
        const idx = (bar as { dataIndex?: number })?.dataIndex ?? 0;
        const label = categoryLabels[idx];
        return `${label}<br/>${displayStrings[idx] ?? EM_DASH}`;
      },
    },
    grid: { left: 48, right: 24, top: 24, bottom: 32, containLabel: true },
    xAxis: {
      type: "category",
      data: categoryLabels,
      axisLabel: { interval: 0, rotate: 0, ...nocturneChartTheme.axisLabel },
      axisLine: { lineStyle: { color: nocturneTokens.color.lineSoft } },
    },
    yAxis: {
      type: "value",
      axisLabel: { ...nocturneChartTheme.axisLabel, formatter: formatMoneyAxisTick },
      splitLine: { lineStyle: { color: nocturneTokens.color.lineSoft, type: "dashed" } },
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
