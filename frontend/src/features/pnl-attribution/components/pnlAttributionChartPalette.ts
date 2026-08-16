import { nocturneTokens } from "../../../theme/designSystem";

/**
 * PnL attribution chart series / tone colors.
 * 本页挂暗色路由（theme-dh-api）且已切首页 Nocturne 色板；ECharts canvas
 * 读不到 CSS 变量，一律走 nocturneTokens 静态镜像 token（token-equal）；
 * no bare hex 原则不变。正负色方向不变：positive=green / negative=red。
 */
export const pnlCompositionSeriesColors = {
  positive: nocturneTokens.color.green,
  neutral: nocturneTokens.color.inkMuted,
  negative: nocturneTokens.color.red,
  interest: nocturneTokens.color.green,
  fairValue: nocturneTokens.color.blue,
  capital: nocturneTokens.color.amber,
  other: nocturneTokens.color.inkMuted,
} as const;

/** ECharts bar label on filled bars — Nocturne ink（近白），保证落在实心柱上的对比度。 */
export const pnlChartLabelOnFill = nocturneTokens.color.ink;
