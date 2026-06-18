import {
  mossChartAxisLabel,
  mossChartAxisLine,
  mossChartPalette,
  mossChartSplitLine,
} from "../../../../components/charts/chartTheme";
import { ibTokens } from "../../../../theme/designSystem";

/** Shared palette / axis styling for market-data ECharts option builders. */
export const marketDataChartTheme = {
  multiSeriesPalette: [...mossChartPalette] as string[],
  axisLabel: mossChartAxisLabel,
  axisLine: mossChartAxisLine,
  splitLine: mossChartSplitLine,
  gridCompact: { left: 48, right: 16, top: 16, bottom: 28 },
  gridWithTitle: { left: 48, right: 16, top: 32, bottom: 28 },
  heatmapRange: [ibTokens.color.accentSurface, ibTokens.color.accent] as const,
  positiveBar: ibTokens.color.up,
  negativeBar: ibTokens.color.down,
  derivedSpreadColor: mossChartPalette[1],
  titleMuted: { ...mossChartAxisLabel, fontWeight: 400 as const },
} as const;
