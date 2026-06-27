import type { TooltipComponentOption } from "echarts";

import {
  mossChartAxisLabel,
  mossChartAxisLine,
} from "../../../../components/charts/chartTheme";
import { designTokens, ibTokens } from "../../../../theme/designSystem";

const institutionalPalette = [
  designTokens.color.primary[600],
  designTokens.color.institutional.accentCyan,
  designTokens.color.institutional.accentGold,
  designTokens.color.cockpit.ink650,
  designTokens.color.warm.slateBlue,
  designTokens.color.success[500],
  designTokens.color.cockpit.red700,
  designTokens.color.neutral[500],
] as const;

const marketDataTooltipBase: TooltipComponentOption = {
  confine: true,
  backgroundColor: designTokens.color.institutional.surfaceRaised,
  borderColor: designTokens.color.cockpit.border175,
  borderWidth: 1,
  padding: [8, 10],
  extraCssText:
    "box-shadow: 0 10px 24px rgba(15, 35, 56, 0.10); border-radius: 6px; font-variant-numeric: tabular-nums;",
  textStyle: {
    color: designTokens.color.cockpit.ink800,
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
  multiSeriesPalette: [...institutionalPalette] as string[],
  axisLabel: {
    ...mossChartAxisLabel,
    color: designTokens.color.cockpit.ink600,
    fontSize: designTokens.fontSize[11],
    fontFamily: designTokens.fontFamily.tabular,
  },
  axisLine: {
    ...mossChartAxisLine,
    lineStyle: {
      color: designTokens.color.cockpit.border150,
    },
  },
  /** 更轻的分割线：虚线 + 半透明，减少视觉噪音 */
  splitLine: {
    lineStyle: {
      color: designTokens.color.cockpit.border100,
      type: "dashed" as const,
      opacity: 0.78,
    },
  },
  axisPointerLine: {
    type: "line" as const,
    lineStyle: { color: designTokens.color.institutional.accentGold, width: 1, type: "dashed" as const },
  },
  axisPointerShadow: {
    type: "shadow" as const,
    shadowStyle: { color: "rgba(24, 80, 161, 0.07)" },
  },
  gridCompact: { left: 52, right: 44, top: 20, bottom: 34, containLabel: true },
  gridWithTitle: { left: 52, right: 52, top: 36, bottom: 34, containLabel: true },
  heatmapRange: [designTokens.color.cockpit.blueMist, designTokens.color.primary[600]] as const,
  heatmapEmptyColor: designTokens.color.cockpit.surface40,
  positiveBar: designTokens.color.success[500],
  negativeBar: designTokens.color.danger[600],
  neutralBar: designTokens.color.cockpit.ink450,
  derivedSpreadColor: designTokens.color.institutional.accentCyan,
  titleMuted: {
    ...mossChartAxisLabel,
    color: designTokens.color.cockpit.ink650,
    fontSize: designTokens.fontSize[12],
    fontWeight: 600 as const,
  },
  chartSurface: ibTokens.color.surface,
} as const;
