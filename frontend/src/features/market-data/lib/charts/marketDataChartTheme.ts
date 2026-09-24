import type { TooltipComponentOption } from "echarts";

import { designTokens, nocturneTokens } from "../../../../theme/designSystem";

/**
 * Nocturne 多系列序（DESIGN.md §2.2：深色页只用去饱和色阶）：
 * 强调蓝紫 → 绿 → 琥珀 → 强调-400 → 红 → 次级墨 → 强调-300 → muted。
 */
const nocturnePalette = [
  nocturneTokens.color.blue,
  nocturneTokens.color.green,
  nocturneTokens.color.amber,
  nocturneTokens.color.accent400,
  nocturneTokens.color.red,
  nocturneTokens.color.inkSoft,
  nocturneTokens.color.accent300,
  nocturneTokens.color.inkMuted,
] as const;

const marketDataTooltipBase: TooltipComponentOption = {
  confine: true,
  backgroundColor: nocturneTokens.color.panel3,
  borderColor: nocturneTokens.color.line,
  borderWidth: 1,
  padding: [8, 10],
  extraCssText: `box-shadow: 0 10px 24px rgba(0, 0, 0, 0.28); border-radius: ${nocturneTokens.radius}px; font-variant-numeric: tabular-nums;`,
  textStyle: {
    color: nocturneTokens.color.ink,
    fontSize: designTokens.fontSize[12],
    fontFamily: designTokens.fontFamily.sans,
  },
};

export function buildMarketDataChartTooltip(
  overrides: TooltipComponentOption = {},
): TooltipComponentOption {
  return {
    ...marketDataTooltipBase,
    ...overrides,
    textStyle: {
      ...marketDataTooltipBase.textStyle,
      ...overrides.textStyle,
    },
  };
}

/** Shared palette / axis styling for market-data ECharts option builders. */
export const marketDataChartTheme = {
  multiSeriesPalette: [...nocturnePalette] as string[],
  axisLabel: {
    color: nocturneTokens.color.inkMuted,
    fontSize: designTokens.fontSize[11],
    fontFamily: designTokens.fontFamily.tabular,
  },
  axisLine: {
    lineStyle: {
      color: nocturneTokens.color.lineSoft,
    },
  },
  /** 更轻的分割线：虚线 + 半透明，减少视觉噪音 */
  splitLine: {
    lineStyle: {
      color: nocturneTokens.color.lineSoft,
      type: "dashed" as const,
      opacity: 0.6,
    },
  },
  axisPointerLine: {
    type: "line" as const,
    lineStyle: { color: nocturneTokens.color.blue, width: 1, type: "dashed" as const },
  },
  axisPointerShadow: {
    type: "shadow" as const,
    // blueSoft 自带 12% 透明度，再乘 0.4 得到 ~5% 的安静悬停带。
    shadowStyle: { color: nocturneTokens.color.blueSoft, opacity: 0.4 },
  },
  gridCompact: { left: 52, right: 44, top: 20, bottom: 34, containLabel: true },
  gridWithTitle: { left: 52, right: 52, top: 36, bottom: 34, containLabel: true },
  /** 深色阶：低值沉入 panel-2 深井，高值抬到强调蓝紫。 */
  heatmapRange: [nocturneTokens.color.panel2, nocturneTokens.color.blue] as const,
  heatmapEmptyColor: nocturneTokens.color.panel2,
  positiveBar: nocturneTokens.color.green,
  negativeBar: nocturneTokens.color.red,
  neutralBar: nocturneTokens.color.inkMuted,
  derivedSpreadColor: nocturneTokens.color.accent400,
  titleMuted: {
    color: nocturneTokens.color.inkSoft,
    fontSize: designTokens.fontSize[12],
    fontFamily: designTokens.fontFamily.sans,
    fontWeight: 600 as const,
  },
  chartSurface: nocturneTokens.color.panel,
} as const;
