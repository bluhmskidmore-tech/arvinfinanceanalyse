/**
 * ChartCard 尺度阶梯（DESIGN.md §5 / 视觉方案 §7.2）：全站图表画布只允许三档高度，
 * 补图与迁移时就近取档，不再各图自定义。图例按行数在底部预留空间。
 */
export const CHART_CARD_HEIGHTS = {
  compact: 160,
  default: 220,
  hero: 280,
} as const;

export type ChartCardHeight = (typeof CHART_CARD_HEIGHTS)[keyof typeof CHART_CARD_HEIGHTS];

export const CHART_CARD_HEIGHT_VALUES: readonly ChartCardHeight[] = [
  CHART_CARD_HEIGHTS.compact,
  CHART_CARD_HEIGHTS.default,
  CHART_CARD_HEIGHTS.hero,
];

/** 统一图例在画布底部占的高度：一行 18px，外加 6px 与绘图区的间距。 */
export const CHART_CARD_LEGEND_ROW_PX = 18;
export const CHART_CARD_LEGEND_GAP_PX = 6;

export function chartCardLegendReservedBottom(rows: number): number {
  const clamped = Math.max(0, Math.min(4, Math.floor(rows)));
  return clamped === 0 ? 0 : CHART_CARD_LEGEND_GAP_PX + clamped * CHART_CARD_LEGEND_ROW_PX;
}

export function isChartCardHeight(value: number): value is ChartCardHeight {
  return (CHART_CARD_HEIGHT_VALUES as readonly number[]).includes(value);
}
